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
  starts at the first HELLO.

The station → relay ingress is exempt from loss (it is a separate path in a
real deployment); everything else in the namespace is dropped at rate p.

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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from canticle import wire  # noqa: E402
from canticle.listener import Listener  # noqa: E402
from canticle.manifest import Manifest  # noqa: E402
from canticle.station import StreamConfig  # noqa: E402

from harness import netns, stats  # noqa: E402
from harness.arms import CarouselSender, enable_rx_timestamps, make_station, now_ms, rx_time, wall  # noqa: E402

ITEMS = 20
BODY = 200
SLOTS = 10                      # concurrent joiners per arm
TRIAL_TIMEOUT_S = 120
GRANTED_BPS = 32_000            # §11.3.7 default per lease
RETRY_S = (1, 2, 4, 8)          # §11.3.5 HELLO retransmit
HELLO, COOKIE, LISTEN, LISTEN_OK, BYE = 0x10, 0x11, 0x12, 0x13, 0x15
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
        asyncio.get_running_loop().add_reader(self.sock, self._readable)

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
        self.leases: dict = {}                      # addr -> expiry (wall)
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
            for addr, exp in list(self.leases.items()):
                if now > exp:
                    del self.leases[addr]
                    continue
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
            elif kind == LISTEN:
                nonce, cookie = data[4:20], data[20:36]
                if not hmac.compare_digest(cookie, self._cookie(addr, nonce)):
                    continue                                                              # silent
                new = addr not in self.leases
                self.leases[addr] = wall() + 75
                self.sock.sendto(lease_msg(LISTEN_OK, nonce, os.urandom(8), bytes(56)), addr)
                if new:
                    self.snapshots += 1
                    self.loop.create_task(self._snapshot(addr))
            elif kind == BYE:
                self.leases.pop(addr, None)

    async def _snapshot(self, addr) -> None:
        """The verified live set once, paced at granted_bps (§7.10)."""
        for frame in list(self.frames.values()):
            self.sock.sendto(frame, addr)
            await asyncio.sleep(8 * len(frame) / GRANTED_BPS)


# ---------------------------------------------------------------- trials

async def trial_passive(slot: UdpSlot, manifest) -> dict:
    await asyncio.sleep(0)
    j = Joined(manifest, wall())
    slot.handler = lambda d, t, src: j.hear(d, t)
    try:
        t = await asyncio.wait_for(j.done, TRIAL_TIMEOUT_S)
        return {"t_full_ms": (t - j.t_start) * 1000, "frames": j.frames}
    except asyncio.TimeoutError:
        return {"timeout": True, "keys": len(j.keys)}
    finally:
        slot.handler = None


async def trial_lease(slot: UdpSlot, manifest, relay_addr) -> dict:
    t0 = wall()
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
    tries = {"hello": 0, "listen": 0}
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
            return {"timeout": True, "stage": "cookie", **tries}
        cookie = got[COOKIE][1][20:36]
        if not await exchange(LISTEN_OK, lambda: lease_msg(LISTEN, nonce, cookie, bytes(28)), "listen"):
            return {"timeout": True, "stage": "listen_ok", **tries}
        t_ok = got[LISTEN_OK][0]
        t = await asyncio.wait_for(j.done, max(1, TRIAL_TIMEOUT_S - (wall() - t0)))
        return {"t_full_ms": (t - t0) * 1000, "handshake_ms": (t_ok - t0) * 1000, **tries}
    except asyncio.TimeoutError:
        return {"timeout": True, "stage": "items", "keys": len(j.keys), **tries}
    finally:
        slot.sock.sendto(lease_msg(BYE, nonce), relay_addr)
        slot.handler = None


async def trial_tcp(manifest, server_port: int) -> dict:
    loop = asyncio.get_running_loop()
    s = socket.socket()
    netns.set_cubic(s)
    enable_rx_timestamps(s)
    s.setblocking(False)
    t0 = wall()
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
        return {"timeout": True, "error": type(e).__name__, "keys": len(j.keys)}
    finally:
        try:
            loop.remove_reader(s)
        except (ValueError, OSError):
            pass
        s.close()


async def tcp_snapshot_server(station, stream: str) -> tuple[asyncio.AbstractServer, int]:
    async def serve(reader, writer):
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

    slots = {arm: [UdpSlot() for _ in range(SLOTS)] for arm in ("carousel-4kbps", "carousel-1s", "lease-snapshot")}
    senders = {
        "slow": CarouselSender(slow, "lens.state", [("127.0.0.1", s.port) for s in slots["carousel-4kbps"]]
                               + [("127.0.0.1", relay.port_ingress)], BODY, loop="fast"),
        "fast": CarouselSender(fast, "ctl.state", [("127.0.0.1", s.port) for s in slots["carousel-1s"]], BODY,
                               loop="fast"),
    }
    stop = asyncio.Event()
    runs = [asyncio.create_task(s.run(stop)) for s in senders.values()]
    for k, key in enumerate(KEYS):
        for s in senders.values():
            s.publish(k, state_key=key)
    sing = {name: s.sing_results[0] for name, s in senders.items()}
    srv, tcp_port = await tcp_snapshot_server(slow, "lens.state")
    await asyncio.sleep(6)          # past every item's burst: joiners see the steady-state loop
    lossy.set_loss(a.loss)

    results = {arm: [] for arm in ("carousel-4kbps", "carousel-1s", "tcp-snapshot", "lease-snapshot")}
    t_end = wall() + a.duration

    async def worker(arm: str, i: int):
        await asyncio.sleep(rng.uniform(0, 10))
        while wall() + 5 < t_end:
            if arm in ("carousel-4kbps", "carousel-1s"):
                r = await trial_passive(slots[arm][i], manifest)
            elif arm == "lease-snapshot":
                r = await trial_lease(slots[arm][i], manifest, ("127.0.0.1", relay.port))
            else:
                r = await trial_tcp(manifest, tcp_port)
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
    await asyncio.gather(*runs, return_exceptions=True)
    srv.close()
    lossy.unexempt(exempt)

    arms = {}
    for arm, rs in results.items():
        ok = [r for r in rs if not r.get("timeout")]
        arms[arm] = {"trials": len(rs), "timeouts": len(rs) - len(ok),
                     "t_full_ms": stats.summary(r["t_full_ms"] for r in ok)}
        if arm == "lease-snapshot":
            arms[arm]["handshake_ms"] = stats.summary(r["handshake_ms"] for r in ok)
            arms[arm]["hello_sent"] = stats.summary((r["hello"] for r in rs), "datagrams")
            arms[arm]["timeout_stages"] = [r.get("stage") for r in rs if r.get("timeout")]
        if arm == "tcp-snapshot":
            arms[arm]["connect_ms"] = stats.summary(r["connect_ms"] for r in ok)
            arms[arm]["errors"] = [r.get("error") for r in rs if r.get("timeout")]
    return {"experiment": "e4_late_joiner", "loss_permille": a.loss, "duration_s": a.duration, "items": ITEMS,
            "slots_per_arm": SLOTS, "frame_bytes": sing["slow"]["size"], "sing": sing, "loop_ms": loops,
            "relay_snapshots": relay.snapshots, "granted_bps": GRANTED_BPS,
            "nft": {**counters, "measured_loss": round(counters["dropped_loss"] / counters["offered"], 5)
                    if counters["offered"] else None},
            "arms": arms, "env": stats.env()}


def run_all(a) -> None:
    procs = {}
    raw = os.path.join(HERE, "results", "raw")
    os.makedirs(raw, exist_ok=True)
    with contextlib.ExitStack() as stack:
        for loss in a.losses:
            ns = stack.enter_context(netns.netns(f"pd-e4-loss{loss}"))
            out = os.path.join(raw, f"e4-loss{loss}.json")
            argv = [sys.executable, os.path.abspath(__file__), "one", "--loss", str(loss), "--duration",
                    str(a.duration), "--seed", str(loss + 1), "--out", out]
            procs[loss] = (subprocess.Popen(netns.ns_exec(ns, *argv)), out)
        for loss, (p, out) in procs.items():
            p.wait()
    rows = []
    for loss, (p, out) in procs.items():
        with open(out) as f:
            rows.append(json.load(f))
    stats.write_json(os.path.join(HERE, "results", "e4_late_joiner.json"), {"experiment": "e4_late_joiner",
                                                                             "conditions": rows})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("one")
    one.add_argument("--loss", type=int, default=0, help="permille, both directions")
    one.add_argument("--duration", type=float, default=600)
    one.add_argument("--seed", type=int, default=1)
    one.add_argument("--out", required=True)
    al = sub.add_parser("all")
    al.add_argument("--duration", type=float, default=600)
    al.add_argument("--losses", type=int, nargs="+", default=[0, 50, 300])
    a = p.parse_args()
    if a.cmd == "one":
        stats.write_json(a.out, asyncio.run(condition(a)))
    else:
        run_all(a)


if __name__ == "__main__":
    main()
