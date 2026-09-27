"""E4: how long a late joiner needs to hold the full live set of 20 items.

A real Station keeps 20 keyed live-state items on air (one per ``state_key``).
Joiners arrive at random times with an empty Listener and are done when they
hold a current item for all 20 keys. Arms, all under the same loss:

- ``carousel-4kbps``: passive catch-up from the carousel at the default stream
  budget (B_stream = 4 000 bit/s). The regulator's fair share, not the class
  floor, sets the loop: 20 × ~330 B → about 13 s.
- ``carousel-1s``: the same, on a control-class stream whose budget is raised
  (64 kbit/s) so the 1 s class floor binds; the loop the RFC's broker test used.
- ``tcp-snapshot``: SeedLink-style. The joiner connects and the server writes
  the 20 current frames at once. The clock starts at connect().
- ``lease-snapshot``: the RFC-0001 §11.3 relay lease. HELLO (256 B) → COOKIE →
  LISTEN → LISTEN_OK, retransmitted after 1, 2, 4, 8 s. The relay then sends
  its verified live set once, paced at granted_bps = 32 kbit/s (§7.10), and
  forwards the station's carousel (the 4 kbit/s one) after that. The clock
  starts at the first HELLO. Each trial is a new session from a new socket
  with a fresh client nonce; the relay keys leases by session (address and
  nonce, i.e. the cookie it validated), so every new session gets a snapshot
  even when an earlier session's BYE was lost. The joiner RENEWs every
  22 s × U(0.8, 1.2) (§11.3.5), so a long trial does not lose its lease.

The station → relay ingress is exempt from loss (it is a separate path in a
real deployment); everything else in the namespace is dropped at rate p.

A join that has not completed when it times out (120 s) or when the run ends
is right-censored: ``t_full_km_ms`` is the Kaplan–Meier estimate over all
joins, ``t_full_completed_ms`` is conditional on completion.

    python e4_late_joiner.py all --duration 600
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import random
import socket
import struct
import subprocess
import sys
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from canticle import wire  # noqa: E402
from canticle.listener import Listener  # noqa: E402
from canticle.manifest import Manifest  # noqa: E402
from canticle.station import StreamConfig  # noqa: E402

from harness import netns, runs, stats  # noqa: E402
from harness.arms import CarouselSender, enable_rx_timestamps, make_station, now_ms, rx_time, wall  # noqa: E402

ITEMS = 20
BODY = 200
SLOTS = 10                      # concurrent joiners per arm
TRIAL_TIMEOUT_S = 120
GRANTED_BPS = 32_000            # §11.3.7 default per lease
RETRY_S = (1, 2, 4, 8)          # §11.3.5 HELLO retransmit
LEASE_S, RENEW_S = 75, 22       # §11.3.5
HELLO, COOKIE, LISTEN, LISTEN_OK, RENEW, BYE = 0x10, 0x11, 0x12, 0x13, 0x14, 0x15
LEASE_HDR = b"BC\x02"
KEYS = [f"k{i:02d}" for i in range(ITEMS)]


def lease_msg(kind: int, *parts: bytes, pad_to: int = 0) -> bytes:
    m = LEASE_HDR + bytes([kind]) + b"".join(parts)
    return m + bytes(max(0, pad_to - len(m)))


class Joined:
    """A fresh listener that reports when it holds all 20 keys."""

    def __init__(self, manifest: Manifest, t_start: float):
        self.listener = Listener(manifest)
        self.t_start = t_start
        self.keys: set = set()
        self.done: asyncio.Future = asyncio.get_running_loop().create_future()
        self.frames = 0

    def hear(self, data: bytes, t: float) -> None:
        if self.done.done() or t < self.t_start:
            return
        self.frames += 1
        for ev in self.listener.hear(data, now_ms()):
            if ev.kind == "item" and ev.data.get("state_key") in KEYS:
                self.keys.add(ev.data["state_key"])
        if len(self.keys) == ITEMS:
            self.done.set_result(t)


class UdpSlot:
    """A joiner's UDP socket; datagrams go to the current trial's handler."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        enable_rx_timestamps(self.sock)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.handler = None
        self.loop = asyncio.get_running_loop()
        self.loop.add_reader(self.sock, self._readable)

    def close(self) -> None:
        self.loop.remove_reader(self.sock)
        self.sock.close()

    def _readable(self) -> None:
        while True:
            try:
                data, anc, _, src = self.sock.recvmsg(2048, 64)
            except (BlockingIOError, InterruptedError):
                return
            if self.handler:
                self.handler(data, rx_time(anc), src)


# ---------------------------------------------------------------- relay (lease + snapshot)

class Relay:
    """A minimal §11.3 relay: stateless cookie, lease table, paced snapshot, fan-out."""

    def __init__(self, manifest: Manifest):
        self.listener = Listener(manifest)          # the membrane: verify, supersede, expire
        self.frames: dict = {}                      # identity -> raw frame, for what is current
        self.secret = os.urandom(32)
        self.leases: dict = {}                      # (addr, client nonce) -> expiry (wall): one per session
        self.loop = asyncio.get_running_loop()
        self.ingress = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ingress.bind(("127.0.0.1", 0))
        self.ingress.setblocking(False)
        self.port_ingress = self.ingress.getsockname()[1]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.loop.add_reader(self.ingress, self._on_ingress)
        self.loop.add_reader(self.sock, self._on_lease)
        self.snapshots = 0
        self.renewals = 0

    def _cookie(self, addr, nonce: bytes) -> bytes:
        msg = socket.inet_aton(addr[0]) + struct.pack(">H", addr[1]) + nonce
        return hmac.new(self.secret, msg, hashlib.sha256).digest()[:16]

    def _on_ingress(self) -> None:
        while True:
            try:
                data = self.ingress.recv(2048)
            except BlockingIOError:
                return
            try:
                f = wire.parse(data, self.listener.manifest.resolve, now_ms())
            except wire.Reject:
                continue
            self.listener.hear(data, now_ms())
            if f.kind == wire.KIND_ITEM:
                self.frames[f.identity] = data
                self.frames = {k: v for k, v in self.frames.items() if k in self.listener.current}
            now = wall()
            dests = set()
            for key, exp in list(self.leases.items()):
                if now > exp:
                    del self.leases[key]
                else:
                    dests.add(key[0])
            for addr in dests:                          # once per address, however many sessions it holds
                self.sock.sendto(data, addr)            # byte-identical forwarding (I-8)

    def _on_lease(self) -> None:
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except BlockingIOError:
                return
            if len(data) < 4 or data[:3] != LEASE_HDR:
                continue
            kind = data[3]
            if kind == HELLO and len(data) >= 256:
                nonce = data[4:20]
                self.sock.sendto(lease_msg(COOKIE, nonce, self._cookie(addr, nonce)), addr)   # 40 B, no state
            elif kind in (LISTEN, RENEW, BYE):
                nonce, cookie = data[4:20], data[20:36]
                if not hmac.compare_digest(cookie, self._cookie(addr, nonce)):
                    continue                                                              # silent
                session = (addr, nonce)                 # the cookie-validated session, not the address
                if kind == BYE:
                    self.leases.pop(session, None)
                elif kind == RENEW:
                    if session in self.leases:
                        self.leases[session] = wall() + LEASE_S
                        self.renewals += 1
                else:
                    new = session not in self.leases    # a retransmitted LISTEN is the same session
                    self.leases[session] = wall() + LEASE_S
                    self.sock.sendto(lease_msg(LISTEN_OK, nonce, os.urandom(8), bytes(56)), addr)
                    if new:                             # at most one snapshot per lease (§11.3.5)
                        self.snapshots += 1
                        self.loop.create_task(self._snapshot(addr))

    async def _snapshot(self, addr) -> None:
        """The verified live set once, paced at granted_bps (§7.10)."""
        for frame in list(self.frames.values()):
            self.sock.sendto(frame, addr)
            await asyncio.sleep(8 * len(frame) / GRANTED_BPS)


# ---------------------------------------------------------------- trials

# Every trial fills ``info["t0"]`` when its clock starts, so a trial cut off by the
# end of the run can be recorded as censored at its elapsed time. A trial that
# does not complete returns ``elapsed_ms`` (the censoring time) instead of ``t_full_ms``.

async def trial_passive(slot: UdpSlot, manifest, info: dict) -> dict:
    await asyncio.sleep(0)
    j = Joined(manifest, wall())
    info["t0"] = j.t_start
    slot.handler = lambda d, t, src: j.hear(d, t)
    try:
        t = await asyncio.wait_for(j.done, TRIAL_TIMEOUT_S)
        return {"t_full_ms": (t - j.t_start) * 1000, "frames": j.frames}
    except asyncio.TimeoutError:
        return {"timeout": True, "elapsed_ms": (wall() - j.t_start) * 1000, "keys": len(j.keys)}
    finally:
        slot.handler = None


async def trial_lease(manifest, relay_addr, info: dict) -> dict:
    """A new session from a new socket: fresh client nonce, HELLO → COOKIE → LISTEN → LISTEN_OK, RENEW, BYE."""
    slot = UdpSlot()
    t0 = wall()
    info["t0"] = t0
    j = Joined(manifest, t0)
    nonce = os.urandom(16)
    got: dict = {}
    ev = {k: asyncio.Event() for k in (COOKIE, LISTEN_OK)}

    def handler(data, t, src):
        if len(data) >= 4 and data[:3] == LEASE_HDR and data[3] in ev:
            if data[4:20] == nonce and data[3] not in got:
                got[data[3]] = (t, data)
                ev[data[3]].set()
            return
        j.hear(data, t)

    slot.handler = handler
    tries = {"hello": 0, "listen": 0, "renew": 0}
    cookie = None
    renewer = None

    async def renew():
        while True:
            await asyncio.sleep(RENEW_S * random.uniform(0.8, 1.2))
            slot.sock.sendto(lease_msg(RENEW, nonce, cookie, pad_to=96), relay_addr)
            tries["renew"] += 1

    try:
        async def exchange(kind_wait, make, name):
            for wait in RETRY_S + (8,) * 20:
                slot.sock.sendto(make(), relay_addr)
                tries[name] += 1
                try:
                    await asyncio.wait_for(ev[kind_wait].wait(), wait)
                    return True
                except asyncio.TimeoutError:
                    if wall() - t0 > TRIAL_TIMEOUT_S:
                        return False
            return False

        if not await exchange(COOKIE, lambda: lease_msg(HELLO, nonce, pad_to=256), "hello"):
            return {"timeout": True, "elapsed_ms": (wall() - t0) * 1000, "stage": "cookie", **tries}
        cookie = got[COOKIE][1][20:36]
        if not await exchange(LISTEN_OK, lambda: lease_msg(LISTEN, nonce, cookie, bytes(28)), "listen"):
            return {"timeout": True, "elapsed_ms": (wall() - t0) * 1000, "stage": "listen_ok", **tries}
        renewer = asyncio.create_task(renew())
        t_ok = got[LISTEN_OK][0]
        t = await asyncio.wait_for(j.done, max(1, TRIAL_TIMEOUT_S - (wall() - t0)))
        return {"t_full_ms": (t - t0) * 1000, "handshake_ms": (t_ok - t0) * 1000, **tries}
    except asyncio.TimeoutError:
        return {"timeout": True, "elapsed_ms": (wall() - t0) * 1000, "stage": "items", "keys": len(j.keys), **tries}
    finally:
        if renewer:
            renewer.cancel()
        if cookie is not None:
            slot.sock.sendto(lease_msg(BYE, nonce, cookie), relay_addr)
        slot.close()


async def trial_tcp(manifest, server_port: int, info: dict) -> dict:
    loop = asyncio.get_running_loop()
    s = socket.socket()
    netns.set_cubic(s)
    enable_rx_timestamps(s)
    s.setblocking(False)
    t0 = wall()
    info["t0"] = t0
    j = Joined(manifest, t0)
    buf = bytearray()
    try:
        await asyncio.wait_for(loop.sock_connect(s, ("127.0.0.1", server_port)), TRIAL_TIMEOUT_S)
        t_conn = wall()

        def readable():
            while True:
                try:
                    data, anc, _, _ = s.recvmsg(65536, 64)
                except (BlockingIOError, InterruptedError):
                    return
                if not data:
                    loop.remove_reader(s)
                    return
                t = rx_time(anc)
                buf.extend(data)
                while len(buf) >= 2 and len(buf) >= 2 + struct.unpack_from(">H", buf)[0]:
                    n = struct.unpack_from(">H", buf)[0]
                    j.hear(bytes(buf[2:2 + n]), t)
                    del buf[:2 + n]

        loop.add_reader(s, readable)
        t = await asyncio.wait_for(j.done, max(1, TRIAL_TIMEOUT_S - (wall() - t0)))
        return {"t_full_ms": (t - t0) * 1000, "connect_ms": (t_conn - t0) * 1000}
    except (asyncio.TimeoutError, OSError) as e:
        return {"timeout": True, "elapsed_ms": (wall() - t0) * 1000, "error": type(e).__name__, "keys": len(j.keys)}
    finally:
        try:
            loop.remove_reader(s)
        except (ValueError, OSError):
            pass
        s.close()


async def tcp_snapshot_server(station, stream: str, served: list) -> tuple[asyncio.AbstractServer, int]:
    """Every accepted connection gets the 20 current frames at once (one snapshot per connection)."""
    async def serve(reader, writer):
        served[0] += 1
        sock = writer.get_extra_info("socket")
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        netns.set_cubic(sock)
        for oa in list(station.streams[stream].ring.values()):
            writer.write(struct.pack(">H", len(oa.frame)) + oa.frame)
        try:
            await writer.drain()
            await reader.read()             # until the joiner closes
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
    srv = await asyncio.start_server(serve, "127.0.0.1", 0, backlog=1024)
    return srv, srv.sockets[0].getsockname()[1]


# ---------------------------------------------------------------- one condition

async def condition(a) -> dict:
    rng = random.Random(a.seed)
    lossy = netns.Lossy()

    slow, e_slow = make_station("slow", [StreamConfig("lens.state", cls="live-state", default_ttl_s=900,
                                                      max_ttl_s=900)])
    fast, e_fast = make_station("fast", [StreamConfig("ctl.state", cls="control", default_ttl_s=900, max_ttl_s=900,
                                                      b_stream=64_000)], b_station=64_000)
    manifest = Manifest([e_slow, e_fast])
    relay = Relay(manifest)
    exempt = lossy.exempt_udp_port(relay.port_ingress)

    slots = {arm: [UdpSlot() for _ in range(SLOTS)] for arm in ("carousel-4kbps", "carousel-1s")}
    senders = {
        "slow": CarouselSender(slow, "lens.state", [("127.0.0.1", s.port) for s in slots["carousel-4kbps"]]
                               + [("127.0.0.1", relay.port_ingress)], BODY, loop="fast"),
        "fast": CarouselSender(fast, "ctl.state", [("127.0.0.1", s.port) for s in slots["carousel-1s"]], BODY,
                               loop="fast"),
    }
    stop = asyncio.Event()
    sender_tasks = [asyncio.create_task(s.run(stop)) for s in senders.values()]
    for k, key in enumerate(KEYS):
        for s in senders.values():
            s.publish(k, state_key=key)
    sing = {name: s.sing_results[0] for name, s in senders.items()}
    tcp_served = [0]
    srv, tcp_port = await tcp_snapshot_server(slow, "lens.state", tcp_served)
    await asyncio.sleep(6)          # past every item's burst: joiners see the steady-state loop
    lossy.set_loss(a.loss)

    results = {arm: [] for arm in ("carousel-4kbps", "carousel-1s", "tcp-snapshot", "lease-snapshot")}
    t_end = wall() + a.duration

    async def worker(arm: str, i: int):
        await asyncio.sleep(rng.uniform(0, 10))
        while wall() + 5 < t_end:
            info: dict = {}
            try:
                if arm in ("carousel-4kbps", "carousel-1s"):
                    r = await trial_passive(slots[arm][i], manifest, info)
                elif arm == "lease-snapshot":
                    r = await trial_lease(manifest, ("127.0.0.1", relay.port), info)
                else:
                    r = await trial_tcp(manifest, tcp_port, info)
            except asyncio.CancelledError:
                if "t0" in info:                        # cut off by the end of the run: censored, not dropped
                    results[arm].append({"cut_at_end": True, "elapsed_ms": (wall() - info["t0"]) * 1000})
                raise
            results[arm].append(r)
            await asyncio.sleep(rng.uniform(0.5, 5))    # random arrival phase for the next joiner

    workers = [asyncio.create_task(worker(arm, i)) for arm in results for i in range(SLOTS)]
    await asyncio.sleep(a.duration)
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    counters = lossy.counters()
    loops = {name: sorted({oa.loop_ms for oa in s.station.streams[s.stream].ring.values()})   # after reconsideration
             for name, s in senders.items()}
    stop.set()
    await asyncio.gather(*sender_tasks, return_exceptions=True)
    srv.close()
    lossy.unexempt(exempt)

    arms = {}
    for arm, rs in results.items():
        ok = [r for r in rs if "t_full_ms" in r]
        timed_out = [r for r in rs if r.get("timeout") and r.get("error", "TimeoutError") == "TimeoutError"]
        arms[arm] = {"trials": len(rs), "completed": len(ok), "timeouts": len(timed_out),
                     "errors": sum(1 for r in rs if r.get("error", "TimeoutError") != "TimeoutError"),
                     "cut_at_end": sum(1 for r in rs if r.get("cut_at_end")),
                     "t_full_km_ms": stats.km([r.get("t_full_ms", r.get("elapsed_ms")) for r in rs],
                                              ["t_full_ms" in r for r in rs]),
                     "t_full_completed_ms": {**stats.summary(r["t_full_ms"] for r in ok),
                                             "conditional_on": "completion: timed-out and cut-off joins excluded"}}
        if arm == "lease-snapshot":
            arms[arm]["handshake_ms"] = stats.summary(r["handshake_ms"] for r in ok)
            arms[arm]["hello_sent"] = stats.summary((r["hello"] for r in rs if "hello" in r), "datagrams")
            arms[arm]["renew_sent"] = sum(r.get("renew", 0) for r in rs)
            arms[arm]["timeout_stages"] = [r.get("stage") for r in rs if r.get("timeout")]
            arms[arm]["sessions_with_listen_ok"] = sum(1 for r in rs if "t_full_ms" in r or r.get("stage") == "items")
        if arm == "tcp-snapshot":
            arms[arm]["connect_ms"] = stats.summary(r["connect_ms"] for r in ok)
            arms[arm]["error_kinds"] = [r.get("error") for r in rs if r.get("timeout")]
    return {"experiment": "e4_late_joiner", "run_id": a.run_id, "tag": a.tag, "loss_permille": a.loss,
            "duration_s": a.duration, "items": ITEMS, "trial_timeout_s": TRIAL_TIMEOUT_S,
            "slots_per_arm": SLOTS, "frame_bytes": sing["slow"]["size"], "sing": sing, "loop_ms": loops,
            "relay_snapshots": relay.snapshots, "relay_renewals": relay.renewals, "tcp_snapshots": tcp_served[0],
            "granted_bps": GRANTED_BPS,
            "nft": {**counters, "measured_loss": round(counters["dropped_loss"] / counters["offered"], 5)
                    if counters["offered"] else None},
            "arms": arms, "env": stats.env()}


def _spawn(ns: str, argv: list[str], log_path: str) -> subprocess.Popen:
    """One loss level's worker, inside namespace ``ns`` (tests replace this)."""
    with open(log_path, "w") as log:
        return subprocess.Popen(netns.ns_exec(ns, *argv), stdout=log, stderr=subprocess.STDOUT)


PROVENANCE = ("run_id", "duration_s", "items", "slots_per_arm", "trial_timeout_s", "granted_bps")


def run_all(a) -> int:
    """All loss levels in parallel namespaces; publish only if every one succeeds (see harness/runs.py)."""
    results = os.path.abspath(a.results_dir)
    if a.losses != DEFAULT_LOSSES and results == runs.RESULTS:
        raise SystemExit("a subset of loss levels writes a partial aggregate; pass --results-dir to put it "
                         "somewhere other than results/")
    run_id = runs.new_run_id()
    stage = runs.stage_dir(results, "e4", run_id)
    tags = [f"loss{loss}" for loss in a.losses]
    manifest = runs.manifest("e4_late_joiner", run_id, tags, {"duration_s": a.duration, "losses": a.losses},
                             os.path.abspath(__file__))
    procs = []
    try:
        with contextlib.ExitStack() as stack:
            for loss, tag in zip(a.losses, tags):
                ns = stack.enter_context(netns.netns(netns.name(f"e4-{tag}")))
                out = os.path.join(stage, f"e4-{tag}.json")
                argv = [sys.executable, os.path.abspath(__file__), "one", "--loss", str(loss), "--duration",
                        str(a.duration), "--seed", str(loss + 1), "--run-id", run_id, "--tag", tag, "--out", out]
                procs.append((tag, out, _spawn(ns, argv, os.path.join(stage, f"e4-{tag}.log"))))
            runs.wait_all(procs)
        aggregate = collate([out for _, out, _ in procs], manifest,
                            expect={"run_id": run_id, "duration_s": a.duration})
    except runs.RunFailed as e:
        print(f"e4: {e}. Nothing was published; worker logs are in {stage}", file=sys.stderr)
        return 1
    finally:
        for _, _, p in procs:
            if p.poll() is None:
                p.kill()
    runs.publish(stage, os.path.join(results, "raw"), os.path.join(results, "e4_late_joiner.json"), aggregate)
    return 0


def collate(files: list[str], manifest: dict, expect: Optional[dict] = None) -> dict:
    stats.km_selfcheck()
    docs = {}
    for path in files:
        with open(path) as f:
            docs[os.path.basename(path)] = json.load(f)
    if not docs:
        raise runs.RunFailed("no raw files to collate")
    runs.check_consistent(docs, PROVENANCE, expect)
    return {"experiment": "e4_late_joiner",
            "manifest": {**manifest, "finished": stats.env()["date"], "raw_files": sorted(docs)},
            "conditions": sorted(docs.values(), key=lambda d: d["loss_permille"])}


DEFAULT_LOSSES = [0, 50, 300]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("one")
    one.add_argument("--loss", type=int, default=0, help="permille, both directions")
    one.add_argument("--duration", type=float, default=600)
    one.add_argument("--seed", type=int, default=1)
    one.add_argument("--run-id", default="adhoc")
    one.add_argument("--tag", default="adhoc")
    one.add_argument("--out", required=True)
    al = sub.add_parser("all")
    al.add_argument("--duration", type=float, default=600)
    al.add_argument("--losses", type=int, nargs="+", default=DEFAULT_LOSSES)
    al.add_argument("--results-dir", default=runs.RESULTS,
                    help="where raw/ and e4_late_joiner.json are published (default: results/)")
    a = p.parse_args()
    if a.cmd == "one":
        stats.write_json(a.out, asyncio.run(condition(a)))
    else:
        sys.exit(run_all(a))


if __name__ == "__main__":
    main()
