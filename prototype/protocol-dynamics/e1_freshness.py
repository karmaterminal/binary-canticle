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

An update a receiver has not caught up to when the run ends is right-censored:
latencies are Kaplan–Meier estimates (``update_latency_km_ms``), with the
delivered fraction and censored count beside them; ``delivered_latency_ms``
is conditional on delivery.

Run everything (root; namespaces are named ``<PD_NS_PREFIX>e1-*``, see
harness/netns.py). ``results/e1/`` (``e1_freshness.json``, ``manifest.json``,
``raw/``) is replaced as a whole, and only if every condition succeeds and no
source file differs from HEAD (see harness/runs.py)::

    python e1_freshness.py all --duration 900 --receivers 20
    python e1_freshness.py all --duration 30 --only u2-loss50 --results-dir /tmp/smoke --allow-dirty   # a partial run

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
from typing import Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from canticle import wire  # noqa: E402
from canticle.manifest import Manifest  # noqa: E402
from canticle.station import StreamConfig  # noqa: E402

from harness import netns, runs, stats, tcpinfo  # noqa: E402
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

class _Censored:
    """Durations that are either observed or right-censored at the end of the run."""

    def __init__(self):
        self.t: list[float] = []
        self.seen: list[bool] = []

    def add(self, done_at: Optional[float], start: float, t_end: float) -> None:
        """``done_at`` is when the event happened, or None if it had not by ``t_end`` (censored there)."""
        self.t.append(((done_at if done_at is not None else t_end) - start) * 1000)
        self.seen.append(done_at is not None)

    def observed(self) -> list[float]:
        return [t for t, s in zip(self.t, self.seen) if s]

    def km(self) -> dict:
        return stats.km(self.t, self.seen)


def analyze(issue: dict[int, float], receivers: list[list], w0: float, w1: float, t_end: float,
            outages: list[tuple[float, float]]) -> dict:
    """Freshness of one arm. ``receivers[r]`` is a list of (time, update index) arrivals.

    An update a receiver had not caught up to by ``t_end`` is right-censored at
    ``t_end - t_issue``: that is a lower bound on its latency, not a latency. It
    enters only the Kaplan–Meier estimate (``update_latency_km_ms``) and the
    counts; ``delivered_latency_ms`` summarises the observed catch-ups alone and
    is conditional on delivery. Outage recovery is treated the same way.
    """
    ks = np.array(sorted(issue))
    t_issue = np.full(ks.max() + 2, np.inf)
    for k in ks:
        t_issue[k] = issue[k]
    meas = ks[(t_issue[ks] >= w0) & (t_issue[ks] <= w1)]
    catchup, recov, recov_aff, in_outage = _Censored(), _Censored(), _Censored(), _Censored()
    exact, skipped, superseded, arrivals_n, affected = [], 0, 0, 0, 0
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

        def caught(k: int) -> Optional[float]:
            """When this receiver first held update k or newer; None if not by the end of the run."""
            i = np.searchsorted(ch_v, k)                                    # first change with value >= k
            return float(ch_t[i]) if i < len(ch_v) else None

        for k in meas:
            catchup.add(caught(k), t_issue[k], t_end)
            if k in held_exact:
                exact.append((held_exact[k] - t_issue[k]) * 1000)
            else:
                skipped += 1
        for (s, e) in outages:
            for k in meas[(t_issue[meas] >= s) & (t_issue[meas] <= e)]:
                in_outage.add(caught(k), t_issue[k], t_end)
            want = np.searchsorted(t_issue[1:ks.max() + 1], e, side="right")
            j = np.searchsorted(ch_t, e, side="right")
            have = ch_v[j - 1] if j > 0 else 0
            if have >= want:
                recov.add(e, e, t_end)                                      # held the newest value already: 0
                continue
            affected += 1
            done = caught(want)
            recov.add(done, e, t_end)
            recov_aff.add(done, e, t_end)
        idx = np.searchsorted(ch_t, grid, side="right")
        held = np.where(idx > 0, ch_v[np.maximum(idx - 1, 0)], 0)
        s = np.where(held < newest, grid - t_issue[np.minimum(held + 1, ks.max() + 1)], 0.0)
        stale_s.append(s)
    st = np.concatenate(stale_s) * 1000 if stale_s else np.zeros(0)
    n = len(catchup.t)
    delivered = sum(catchup.seen)
    out = {
        "updates_measured": int(len(meas)), "samples": n,
        "delivered": delivered, "censored": n - delivered,
        "delivered_fraction": round(delivered / n, 6) if n else None,
        "update_latency_km_ms": catchup.km(),
        "delivered_latency_ms": {**stats.summary(catchup.observed()),
                                 "conditional_on": "delivery: observed catch-ups only, censored samples excluded"},
        "exact_hold_latency_ms": stats.summary(exact),
        "skipped_updates": skipped,
        "stale_time_fraction": round(float(np.mean(st > 0)), 6) if st.size else None,
        "staleness_ms_time_weighted": {**stats.weighted_quantiles(st, np.ones_like(st)),
                                       "max": round(float(st.max()), 1) if st.size else None},
        "arrivals": arrivals_n,
        "superseded_deliveries": superseded,
        "superseded_delivery_fraction": round(superseded / arrivals_n, 6) if arrivals_n else None,
    }
    if outages:
        out["outages_x_receivers"] = len(recov.t)
        out["affected"] = affected
        out["outage_recovery_censored"] = len(recov.t) - sum(recov.seen)
        out["outage_recovery_km_ms"] = recov.km()
        out["outage_recovery_affected_km_ms"] = recov_aff.km()
        out["updates_issued_in_outage_censored"] = len(in_outage.t) - sum(in_outage.seen)
        out["latency_of_updates_issued_in_outage_km_ms"] = in_outage.km()
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
                                              "start": round(ep["start"] - t0, 3), "open_at_end": False})
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
    for (arm, i), ep in open_ep.items():     # still retransmitting at the end: duration is a lower bound
        episodes[arm].append({"dur_ms": round((t_end - ep["start"]) * 1000, 1), "max_backoff": ep["max_backoff"],
                              "max_rto_ms": ep["max_rto_ms"], "start": round(ep["start"] - t0, 3),
                              "open_at_end": True})
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
            "count": len(eps), "open_at_end": sum(e["open_at_end"] for e in eps),
            "closed_duration_ms": stats.summary(e["dur_ms"] for e in eps if not e["open_at_end"]),
            "max_backoff_hist": {str(b): sum(1 for e in eps if e["max_backoff"] == b)
                                 for b in sorted({e["max_backoff"] for e in eps})},
            "longest": sorted(eps, key=lambda e: -e["dur_ms"])[:5]}
        arms[arm]["tcp_info_trace_conn0"] = traces[arm][:1500]

    return {
        "experiment": "e1_freshness", "run_id": a.run_id, "tag": a.tag,
        "update_s": a.update_s, "loss_permille": a.loss,
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


def jobs_for(update_values, only) -> list[tuple[str, float, str, float]]:
    jobs = []
    for u in update_values:
        for kind, v in CONDITIONS:
            tag = f"u{u:g}-{kind}{v:g}".replace(".", "p")
            if not only or tag in only:
                jobs.append((tag, u, kind, v))
    unknown = set(only or ()) - {j[0] for j in jobs}
    if unknown:
        raise SystemExit(f"unknown condition tags: {sorted(unknown)}")
    return jobs


def _spawn(ns: str, argv: list[str], log_path: str) -> subprocess.Popen:
    """One condition's worker, inside namespace ``ns`` (tests replace this)."""
    with open(log_path, "w") as log:
        return subprocess.Popen(netns.ns_exec(ns, *argv), stdout=log, stderr=subprocess.STDOUT)


def run_all(a) -> int:
    """Run the conditions in parallel namespaces; publish ``results/e1/`` only if all succeed.

    Refuses a dirty source tree unless ``--allow-dirty`` (see harness/runs.py).
    Workers write into a fresh staging directory. Any nonzero exit, missing
    output, provenance mismatch or source change during the run leaves
    ``results/`` untouched and returns 1.
    """
    results = os.path.abspath(a.results_dir)
    if a.only and results == runs.RESULTS:
        raise SystemExit("--only writes an aggregate of just those conditions; pass --results-dir to put it "
                         "somewhere other than results/")
    jobs = jobs_for(a.update_values, a.only)
    config = {"duration_s": a.duration, "receivers": a.receivers, "update_values": a.update_values,
              "warmup_s": WARMUP_S, "drain_s": DRAIN_S, "body_bytes": BODY}
    try:
        run = runs.Run(UNIT, "e1_freshness", __file__, config, results_dir=results, allow_dirty=a.allow_dirty,
                       conditions=[j[0] for j in jobs])
    except runs.RunFailed as e:
        print(f"e1: {e}. Nothing was run or published.", file=sys.stderr)
        return 1
    procs = []
    try:
        with contextlib.ExitStack() as stack:
            for tag, u, kind, v in jobs:
                ns = stack.enter_context(netns.netns(netns.name(f"e1-{tag}")))
                out = run.raw(f"e1-{tag}.json")
                argv = [sys.executable, os.path.abspath(__file__), "one", "--update-s", str(u), "--duration",
                        str(a.duration), "--receivers", str(a.receivers), "--seed", str(zlib.crc32(tag.encode())),
                        "--run-id", run.id, "--tag", tag, "--out", out]
                argv += {"loss": ["--loss", str(v)], "lossdata": ["--loss", str(v), "--data-only"],
                         "outage": ["--outage", str(v)]}[kind]
                procs.append((tag, out, _spawn(ns, argv, run.raw(f"e1-{tag}.log"))))
            runs.wait_all(procs)
        aggregate = collate([out for _, out, _ in procs],
                            expect={"run_id": run.id, "duration_s": a.duration, "receivers": a.receivers})
        run.publish(AGGREGATE, aggregate)
    except runs.RunFailed as e:
        print(f"e1: {e}. Nothing was published; worker logs are in {run.stage}", file=sys.stderr)
        return 1
    finally:
        for _, _, p in procs:
            if p.poll() is None:
                p.kill()
    return 0


UNIT, AGGREGATE = "e1", "e1_freshness.json"
PROVENANCE = ("run_id", "duration_s", "receivers", "warmup_s", "drain_s", "body_bytes")


def collate(files: list[str], expect: Optional[dict] = None) -> dict:
    """One row per (condition, arm) from exactly ``files``, which must share one run and configuration."""
    stats.km_selfcheck()
    docs = {}
    for path in files:
        with open(path) as f:
            docs[os.path.basename(path)] = json.load(f)
    if not docs:
        raise runs.RunFailed("no raw files to collate")
    runs.check_consistent(docs, PROVENANCE, expect)
    tags = [d.get("tag") for d in docs.values()]
    if len(set(tags)) != len(tags):
        raise runs.RunFailed(f"duplicate condition tags: {tags}")
    rows = []
    for d in docs.values():
        for arm, m in d["arms"].items():
            rows.append({"tag": d["tag"], "update_s": d["update_s"], "loss_permille": d["loss_permille"],
                         "loss_direction": d.get("loss_direction", "both"), "outage_s": d["outage_s"],
                         "arm": arm, "measured_loss": d["nft"]["measured_loss"],
                         **{k: d[k] for k in PROVENANCE},
                         **{k: v for k, v in m.items() if k not in ("tcp_info_trace_conn0",)}})
    return {"experiment": "e1_freshness", "rows": rows}


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
    one.add_argument("--run-id", default="adhoc")
    one.add_argument("--tag", default="adhoc")
    one.add_argument("--out", required=True)
    al = sub.add_parser("all")
    al.add_argument("--duration", type=float, default=900)
    al.add_argument("--receivers", type=int, default=20)
    al.add_argument("--update-values", type=float, nargs="+", default=[0.5, 2, 10])
    al.add_argument("--only", nargs="*", help="condition tags to run, e.g. u2-loss300 u10-lossdata200")
    al.add_argument("--results-dir", default=runs.RESULTS,
                    help="publish into <dir>/e1/ (default: results/, i.e. results/e1/)")
    al.add_argument("--allow-dirty", action="store_true",
                    help="run even if source files differ from HEAD; the manifest then embeds the diff")
    co = sub.add_parser("collate", help="re-collate <results>/e1/raw/e1-*.json (read-only; refuses mixed runs)")
    co.add_argument("--results-dir", default=runs.RESULTS)
    co.add_argument("--out", help="write the aggregate here (default: stdout); never into the published generation")
    a = p.parse_args()
    if a.cmd == "one":
        stats.write_json(a.out, asyncio.run(condition(a)))
    elif a.cmd == "all":
        sys.exit(run_all(a))
    else:
        gen = os.path.join(os.path.abspath(a.results_dir), UNIT)
        raw = os.path.join(gen, "raw")
        files = sorted(os.path.join(raw, n) for n in os.listdir(raw) if n.startswith("e1-") and n.endswith(".json"))
        if a.out and os.path.realpath(a.out).startswith(os.path.realpath(gen) + os.sep):
            sys.exit("e1 collate: --out must not be inside the published generation")
        try:
            agg = collate(files)
        except runs.RunFailed as e:
            sys.exit(f"e1 collate: {e}")
        agg = {"run_id": agg["rows"][0]["run_id"], "recollated_from": raw, **agg}
        if a.out:
            stats.write_json(a.out, agg)
        else:
            json.dump(agg, sys.stdout, indent=1)
            print()


if __name__ == "__main__":
    main()
