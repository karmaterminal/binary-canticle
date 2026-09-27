"""E1: freshness and head-of-line blocking for one superseding live-state value.

A value is updated every U seconds; each update supersedes the last. Four arms
run side by side in one network namespace, under the same loss process, each
with R receivers:

- ``udp-live``: the real canticle Station and Listener, one keyed live-state
  item, ``loop="fast"`` (5 s class floor), UDP unicast to R ports.
- ``udp-ctl``: the same on a control-class stream (1 s floor), to show the knob.
- ``tcp-stream``: every update sent once, in order, TCP_NODELAY, 2-byte
  length-prefixed frames carrying the same kind of signed bytes.
- ``tcp-latest``: TCP_NOTSENT_LOWAT = 1; the sender keeps only the newest
  pending frame per connection and writes it when the socket reports writable
  (all earlier bytes have left the not-sent queue).

Conditions: Bernoulli loss (``--loss`` permille) on every packet in both
directions, or with ``--data-only`` on data packets only (pure ACKs spared);
or periodic outages (``--outage`` seconds, every TCP/UDP packet dropped), each
placed so that one update is issued inside it.

Run everything (root, creates namespaces ``pd-e1-*``)::

    python e1_freshness.py all --duration 900 --receivers 20

Run one condition in the current namespace::

    python e1_freshness.py one --update-s 2 --loss 50 --duration 120 --out /tmp/x.json
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import random
import select
import socket
import struct
import subprocess
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from canticle import wire  # noqa: E402
from canticle.manifest import Manifest  # noqa: E402
from canticle.station import StreamConfig  # noqa: E402

from harness import netns, stats, tcpinfo  # noqa: E402
from harness.arms import (CarouselSender, TcpFrameReader, UdpListener, frame_for, make_station, now_ms,  # noqa: E402
                          update_index, wall)

BODY = 200              # body bytes; frames are ~330 B
DRAIN_S = 20            # receivers keep listening after the last update
WARMUP_S = 5            # updates in the first seconds are excluded
OUTAGE_GAP_S = 15       # quiet time after an outage before the next may start
SAMPLE_DT = 0.005       # staleness signal sampled every 5 ms
TCP_ARMS = ("tcp-stream", "tcp-latest")
UDP_ARMS = ("udp-live", "udp-ctl")


# ---------------------------------------------------------------- TCP arms

class _Conn:
    __slots__ = ("sock", "buf", "pending", "written", "coalesced", "error")

    def __init__(self, sock: socket.socket):
        self.sock, self.buf, self.pending = sock, bytearray(), None
        self.written = self.coalesced = 0
        self.error = None


class TcpFanout:
    """One TCP sender, one connection per receiver. ``mode`` is 'stream' or 'latest'."""

    def __init__(self, mode: str):
        self.mode = mode
        self.lsock = socket.socket()
        self.lsock.bind(("127.0.0.1", 0))
        self.lsock.listen(1024)
        self.lsock.setblocking(False)
        self.port = self.lsock.getsockname()[1]
        self.conns: list[_Conn] = []
        self.issue: dict[int, float] = {}
        self.loop = asyncio.get_running_loop()

    async def accept(self, n: int) -> None:
        while len(self.conns) < n:
            s, _ = await self.loop.sock_accept(self.lsock)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            netns.set_cubic(s)
            if self.mode == "latest":
                s.setsockopt(socket.IPPROTO_TCP, tcpinfo.TCP_NOTSENT_LOWAT, 1)
            s.setblocking(False)
            self.conns.append(_Conn(s))

    def publish(self, k: int, frame: bytes, t: float) -> None:
        self.issue[k] = t
        rec = struct.pack(">H", len(frame)) + frame
        for c in self.conns:
            if c.error:
                continue
            if self.mode == "stream":
                c.buf += rec
            else:
                if c.pending is not None:
                    c.coalesced += 1
                c.pending = rec
            self._flush(c)

    def _flush(self, c: _Conn) -> None:
        try:
            if c.buf:
                n = c.sock.send(c.buf)
                del c.buf[:n]
            if not c.buf and c.pending is not None and _writable(c.sock):
                rec, c.pending = c.pending, None
                n = c.sock.send(rec)
                c.buf += rec[n:]
                c.written += 1
        except BlockingIOError:
            pass
        except OSError as e:
            c.error = f"{type(e).__name__}: {e}"
            self.loop.remove_writer(c.sock)
            return
        if c.buf or c.pending is not None:
            self.loop.add_writer(c.sock, self._flush, c)
        else:
            self.loop.remove_writer(c.sock)

    def close(self) -> None:
        for c in self.conns:
            self.loop.remove_writer(c.sock)
            c.sock.close()
        self.lsock.close()


def _writable(s: socket.socket) -> bool:
    """poll() honours TCP_NOTSENT_LOWAT: writable only once nothing is left unsent."""
    return bool(select.select([], [s], [], 0)[1])


# ---------------------------------------------------------------- analysis

def analyze(issue: dict[int, float], receivers: list[list], w0: float, w1: float, t_end: float,
            outages: list[tuple[float, float]]) -> dict:
    """Freshness of one arm. ``receivers[r]`` is a list of (time, update index) arrivals."""
    ks = np.array(sorted(issue))
    t_issue = np.full(ks.max() + 2, np.inf)
    for k in ks:
        t_issue[k] = issue[k]
    meas = ks[(t_issue[ks] >= w0) & (t_issue[ks] <= w1)]
    catchup, exact, censored, skipped, superseded, arrivals_n = [], [], 0, 0, 0, 0
    recov, affected, in_outage = [], 0, []
    grid = np.arange(w0, w1, SAMPLE_DT)
    newest = np.searchsorted(t_issue[1:ks.max() + 1], grid, side="right")   # newest index issued by t
    stale_s = []
    for arr in receivers:
        arrivals_n += len(arr)
        t_arr = np.array([a[0] for a in arr]) if arr else np.zeros(0)
        k_arr = np.array([a[1] for a in arr], dtype=int) if arr else np.zeros(0, dtype=int)
        superseded += int(np.sum(t_arr > t_issue[k_arr + 1])) if arr else 0
        run_max = np.maximum.accumulate(k_arr) if arr else k_arr
        rise = np.ones(len(k_arr), bool)
        if len(k_arr) > 1:
            rise[1:] = run_max[1:] > run_max[:-1]
        ch_t, ch_v = t_arr[rise], run_max[rise]                             # when the held value advanced
        held_exact = {int(v): float(t) for t, v in zip(ch_t, ch_v)}
        for k in meas:
            i = np.searchsorted(ch_v, k)                                    # first change with value >= k
            if i < len(ch_v):
                catchup.append((ch_t[i] - t_issue[k]) * 1000)
            else:
                catchup.append((t_end - t_issue[k]) * 1000)
                censored += 1
            if k in held_exact:
                exact.append((held_exact[k] - t_issue[k]) * 1000)
            else:
                skipped += 1
        for (s, e) in outages:
            ks_in = meas[(t_issue[meas] >= s) & (t_issue[meas] <= e)]
            for k in ks_in:
                i = np.searchsorted(ch_v, k)
                in_outage.append(((ch_t[i] if i < len(ch_v) else t_end) - t_issue[k]) * 1000)
            want = np.searchsorted(t_issue[1:ks.max() + 1], e, side="right")
            j = np.searchsorted(ch_t, e, side="right")
            have = ch_v[j - 1] if j > 0 else 0
            if have >= want:
                recov.append(0.0)
                continue
            affected += 1
            i = np.searchsorted(ch_v, want)
            recov.append(((ch_t[i] if i < len(ch_v) else t_end) - e) * 1000)
        idx = np.searchsorted(ch_t, grid, side="right")
        held = np.where(idx > 0, ch_v[np.maximum(idx - 1, 0)], 0)
        s = np.where(held < newest, grid - t_issue[np.minimum(held + 1, ks.max() + 1)], 0.0)
        stale_s.append(s)
    st = np.concatenate(stale_s) * 1000 if stale_s else np.zeros(0)
    out = {
        "updates_measured": int(len(meas)), "samples": len(meas) * len(receivers),
        "update_latency_ms": stats.summary(catchup),
        "exact_hold_latency_ms": stats.summary(exact),
        "skipped_updates": skipped, "censored": censored,
        "stale_time_fraction": round(float(np.mean(st > 0)), 6) if st.size else None,
        "staleness_ms_time_weighted": {**stats.weighted_quantiles(st, np.ones_like(st)),
                                       "max": round(float(st.max()), 1) if st.size else None},
        "arrivals": arrivals_n,
        "superseded_deliveries": superseded,
        "superseded_delivery_fraction": round(superseded / arrivals_n, 6) if arrivals_n else None,
    }
    if outages:
        out["outage_recovery_ms"] = stats.summary(recov)
        out["outage_recovery_ms_affected_only"] = stats.summary([r for r in recov if r > 0])
        out["outages_x_receivers"] = len(recov)
        out["affected"] = affected
        out["latency_of_updates_issued_in_outage_ms"] = stats.summary(in_outage)
    return out


# ---------------------------------------------------------------- one condition

async def condition(a) -> dict:
    rng = random.Random(a.seed)
    lossy = netns.Lossy()
    snmp0 = netns.snmp()

    live, e_live = make_station("live", [StreamConfig("lens.state", cls="live-state")])
    ctl, e_ctl = make_station("ctl", [StreamConfig("ctl.state", cls="control")])
    signer, e_tcp = make_station("tcp", [StreamConfig("lens.state", cls="live-state")])
    manifest = Manifest([e_live, e_ctl, e_tcp])

    udp_rx: dict[str, list[UdpListener]] = {}
    senders = {}
    for arm, st, stream in (("udp-live", live, "lens.state"), ("udp-ctl", ctl, "ctl.state")):
        udp_rx[arm] = [UdpListener(manifest) for _ in range(a.receivers)]
        senders[arm] = CarouselSender(st, stream, [("127.0.0.1", u.port) for u in udp_rx[arm]], BODY, loop="fast")

    tcp = {"tcp-stream": TcpFanout("stream"), "tcp-latest": TcpFanout("latest")}
    tcp_rx = {arm: [[] for _ in range(a.receivers)] for arm in TCP_ARMS}
    readers: dict[str, list[TcpFrameReader]] = {arm: [] for arm in TCP_ARMS}

    rejected = {arm: [] for arm in TCP_ARMS}    # frames TCP delivered that a receiver must refuse

    def on_frame(arrivals: list, rej: list):
        def cb(frame: bytes, t: float) -> None:
            try:
                f = wire.parse(frame, manifest.resolve, now_ms())
            except wire.Reject as r:
                rej.append(r.reason)                # e.g. "expired": delivered after its signed expiry
                return
            arrivals.append((t, update_index(f.body.body.decode())))
        return cb

    for arm, fan in tcp.items():
        acc = asyncio.create_task(fan.accept(a.receivers))
        for r in range(a.receivers):
            readers[arm].append(TcpFrameReader(fan.port, on_frame(tcp_rx[arm][r], rejected[arm])))
            await asyncio.sleep(0)
        await acc

    stop = asyncio.Event()
    loops = [asyncio.create_task(s.run(stop)) for s in senders.values()]

    # the loss process starts only after every TCP connection is up
    lossy.set_loss(a.loss, data_only=a.data_only)
    t0 = wall() + 1.0
    n_updates = int(a.duration / a.update_s)
    t_issue = [t0 + i * a.update_s for i in range(n_updates)]
    outages: list[tuple[float, float]] = []
    traces = {arm: [] for arm in TCP_ARMS}
    episodes = {arm: [] for arm in TCP_ARMS}
    open_ep: dict = {}

    async def outage_task():
        nxt = t0 + WARMUP_S
        while True:
            cands = [t for t in t_issue if t >= nxt + a.outage]
            if not cands:
                return
            tk = cands[0]
            start = tk - a.outage * rng.uniform(0.05, 0.95)
            await asyncio.sleep(max(0, start - wall()))
            lossy.outage_on()
            s = wall()
            await asyncio.sleep(max(0, s + a.outage - wall()))
            lossy.outage_off()
            e = wall()
            outages.append((s, e))
            nxt = e + OUTAGE_GAP_S

    async def trace_task():
        """Sample TCP_INFO on every sender socket every 20 ms; keep loss episodes and a conn-0 trace."""
        last = {}
        for arm in TCP_ARMS:
            for i, c in enumerate(tcp[arm].conns):
                last[(arm, i)] = None
        while True:
            for arm in TCP_ARMS:
                for i, c in enumerate(tcp[arm].conns):
                    try:
                        b = tcpinfo.brief(c.sock)
                    except OSError:
                        continue
                    t = wall()
                    ep = open_ep.get((arm, i))
                    if b["retransmits"] > 0 or b["backoff"] > 0:
                        if ep is None:
                            ep = open_ep[(arm, i)] = {"start": t, "max_backoff": 0, "max_rto_ms": 0}
                        ep["max_backoff"] = max(ep["max_backoff"], b["backoff"])
                        ep["max_rto_ms"] = max(ep["max_rto_ms"], b["rto_ms"])
                    elif ep is not None:
                        episodes[arm].append({"dur_ms": round((t - ep["start"]) * 1000, 1),
                                              "max_backoff": ep["max_backoff"], "max_rto_ms": ep["max_rto_ms"],
                                              "start": round(ep["start"] - t0, 3)})
                        del open_ep[(arm, i)]
                    if i == 0:
                        key = (b["rto_ms"], b["backoff"], b["retransmits"], b["ca_state"])
                        if key != last[(arm, i)] and len(traces[arm]) < 4000:
                            traces[arm].append({"t": round(t - t0, 3), **{k: b[k] for k in (
                                "rto_ms", "backoff", "retransmits", "unacked", "notsent_bytes", "ca_state")}})
                            last[(arm, i)] = key
            await asyncio.sleep(0.02)

    aux = [asyncio.create_task(trace_task())]
    if a.outage:
        aux.append(asyncio.create_task(outage_task()))

    for k, t in enumerate(t_issue, start=1):
        await asyncio.sleep(max(0, t - wall()))
        tk = wall()                 # the value changes now; every arm is measured from here
        frame = frame_for(signer, "lens.state", k, BODY, state_key="now", loop="fast")
        order = list(senders.items()) + list(tcp.items())
        rng.shuffle(order)          # no arm is always first
        for arm, s in order:
            if arm in senders:
                s.publish(k, t=tk)
            else:
                s.publish(k, frame, tk)
    t_last = wall()
    await asyncio.sleep(DRAIN_S)
    t_end = wall()
    lossy.outage_off()
    counters = lossy.counters()
    snmp1 = netns.snmp()
    for t in aux:
        t.cancel()
    stop.set()
    await asyncio.gather(*loops, return_exceptions=True)

    tcp_final = {}
    for arm, fan in tcp.items():
        infos = []
        for c in fan.conns:
            try:
                infos.append(tcpinfo.brief(c.sock))
            except OSError:
                pass
        tcp_final[arm] = {
            "total_retrans": [i["total_retrans"] for i in infos],
            "frames_written": sum(c.written for c in fan.conns) if arm == "tcp-latest" else None,
            "coalesced": sum(c.coalesced for c in fan.conns) if arm == "tcp-latest" else None,
            "sender_errors": [c.error for c in fan.conns if c.error],
            "receiver_errors": [r.error for r in readers[arm] if r.error],
            "rejected_on_arrival": {k: rejected[arm].count(k) for k in sorted(set(rejected[arm]))},
        }
    for arm in TCP_ARMS:
        for r in readers[arm]:
            if not r.error:
                r.close()
    for fan in tcp.values():
        fan.close()
    for arm in UDP_ARMS:
        for u in udp_rx[arm]:
            u.close()

    w0, w1 = t0 + WARMUP_S, t_last
    arms = {}
    for arm in UDP_ARMS:
        s = senders[arm]
        arms[arm] = analyze(s.issue, [p.heard.arrivals for p in udp_rx[arm]], w0, w1, t_end, outages)
        arms[arm]["sender"] = {"datagrams": s.stats.frames, "item_datagrams": s.stats.item_frames,
                               "bytes": s.stats.bytes, "errors": s.stats.errors,
                               "sing": s.sing_results[:1]}
        arms[arm]["receiver"] = {"datagrams": sum(p.heard.datagrams for p in udp_rx[arm]),
                                 "evidence": _merge(p.heard.evidence for p in udp_rx[arm])}
    for arm in TCP_ARMS:
        arms[arm] = analyze(tcp[arm].issue, tcp_rx[arm], w0, w1, t_end, outages)
        arms[arm]["tcp"] = tcp_final[arm]
        eps = episodes[arm]
        arms[arm]["tcp"]["loss_episodes"] = {
            "count": len(eps), "duration_ms": stats.summary(e["dur_ms"] for e in eps),
            "max_backoff_hist": {str(b): sum(1 for e in eps if e["max_backoff"] == b)
                                 for b in sorted({e["max_backoff"] for e in eps})},
            "longest": sorted(eps, key=lambda e: -e["dur_ms"])[:5]}
        arms[arm]["tcp_info_trace_conn0"] = traces[arm][:1500]

    return {
        "experiment": "e1_freshness", "update_s": a.update_s, "loss_permille": a.loss,
        "loss_direction": "data-only" if a.data_only else "both", "outage_s": a.outage,
        "duration_s": a.duration, "receivers": a.receivers, "body_bytes": BODY, "frame_bytes": len(frame),
        "warmup_s": WARMUP_S, "drain_s": DRAIN_S,
        "outages": [(round(s - t0, 3), round(e - t0, 3)) for s, e in outages],
        "nft": {**counters, "measured_loss": round(counters["dropped_loss"] / counters.get("eligible", counters["offered"]), 5)
                if counters["offered"] else None},
        "snmp": netns.snmp_delta(snmp0, snmp1, {
            "Tcp": ["OutSegs", "InSegs", "RetransSegs", "OutRsts", "EstabResets"],
            "Udp": ["OutDatagrams", "InDatagrams", "RcvbufErrors", "InErrors"],
            "TcpExt": ["TCPTimeouts", "TCPLossProbes", "TCPLossProbeRecovery", "TCPFastRetrans",
                       "TCPSlowStartRetrans", "TCPSpuriousRTOs", "TCPAbortOnTimeout", "TCPRetransFail"]}),
        "arms": arms, "env": stats.env(),
    }


def _merge(dicts) -> dict:
    out: dict = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return out


# ---------------------------------------------------------------- all conditions

CONDITIONS = ([("loss", p) for p in (0, 10, 50, 100, 200, 300)] + [("outage", o) for o in (1, 3, 10)]
              + [("lossdata", p) for p in (100, 200, 300)])


def run_all(a) -> None:
    raw = os.path.join(HERE, "results", "raw")
    os.makedirs(raw, exist_ok=True)
    jobs = []
    for u in a.update_values:
        for kind, v in CONDITIONS:
            tag = f"u{u:g}-{kind}{v:g}".replace(".", "p")
            if a.only and tag not in a.only:
                continue
            jobs.append((f"pd-e1-{tag}", tag, u, kind, v))
    procs = []
    with contextlib.ExitStack() as stack:
        for ns, tag, u, kind, v in jobs:
            stack.enter_context(netns.netns(ns))
            out = os.path.join(raw, f"e1-{tag}.json")
            argv = [sys.executable, os.path.abspath(__file__), "one", "--update-s", str(u), "--duration",
                    str(a.duration), "--receivers", str(a.receivers), "--seed", str(zlib.crc32(tag.encode())),
                    "--out", out]
            argv += {"loss": ["--loss", str(v)], "lossdata": ["--loss", str(v), "--data-only"],
                     "outage": ["--outage", str(v)]}[kind]
            log = open(os.path.join(raw, f"e1-{tag}.log"), "w")
            procs.append((tag, subprocess.Popen(netns.ns_exec(ns, *argv), stdout=log, stderr=subprocess.STDOUT)))
        failed = [tag for tag, p in procs if p.wait() != 0]
    if failed:
        print("failed conditions:", failed, file=sys.stderr)
    collate(raw, os.path.join(HERE, "results", "e1_freshness.json"))


def collate(raw: str, out: str) -> None:
    rows = []
    for name in sorted(os.listdir(raw)):
        if not (name.startswith("e1-") and name.endswith(".json")):
            continue
        with open(os.path.join(raw, name)) as f:
            d = json.load(f)
        for arm, m in d["arms"].items():
            rows.append({"update_s": d["update_s"], "loss_permille": d["loss_permille"],
                         "loss_direction": d.get("loss_direction", "both"), "outage_s": d["outage_s"],
                         "arm": arm, "measured_loss": d["nft"]["measured_loss"],
                         **{k: v for k, v in m.items() if k not in ("tcp_info_trace_conn0",)}})
    stats.write_json(out, {"experiment": "e1_freshness", "rows": rows})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("one")
    one.add_argument("--update-s", type=float, required=True)
    one.add_argument("--loss", type=int, default=0, help="permille, both directions")
    one.add_argument("--data-only", action="store_true", help="spare pure ACKs (IP length <= 100)")
    one.add_argument("--outage", type=float, default=0, help="outage length in s (0 = none)")
    one.add_argument("--duration", type=float, default=120)
    one.add_argument("--receivers", type=int, default=20)
    one.add_argument("--seed", type=int, default=1)
    one.add_argument("--out", required=True)
    al = sub.add_parser("all")
    al.add_argument("--duration", type=float, default=900)
    al.add_argument("--receivers", type=int, default=20)
    al.add_argument("--update-values", type=float, nargs="+", default=[0.5, 2, 10])
    al.add_argument("--only", nargs="*", help="condition tags to run, e.g. u2-loss300 u10-lossdata200")
    sub.add_parser("collate")
    a = p.parse_args()
    if a.cmd == "one":
        stats.write_json(a.out, asyncio.run(condition(a)))
    elif a.cmd == "all":
        run_all(a)
    else:
        collate(os.path.join(HERE, "results", "raw"), os.path.join(HERE, "results", "e1_freshness.json"))


if __name__ == "__main__":
    main()
