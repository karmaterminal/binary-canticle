"""E5: 1 000 listeners come back after a relay restart. TCP versus UDP leases.

A relay serves N = 1 000 listeners a 20-item snapshot (330 B frames). It is
killed with SIGKILL and a new relay process starts at once on the same port.
We measure the time from the kill until every listener holds the 20 items
again, packets offered in the namespace, and the kernel's listen-queue and SYN
counters. The new relay's syscalls are counted in a second, separate pass with
``strace -c -f`` attached for the recovery only (strace slows every syscall, so
that pass is not timed).

- ``tcp``: listeners reconnect at once on EOF/RST and retry every 100 ms while
  the port refuses. A listener that has no snapshot 5 s after connecting gives
  up and reconnects (without that timeout, connections whose final ACK was
  dropped by a full accept queue hang forever: the relay speaks first, and
  with SYN cookies it keeps no state to retransmit from). Relay listen backlog
  128 (a common default) or 4 096 (somaxconn here).
- ``udp-lease``: RFC-0001 §11.3 leases. The new relay knows no leases and
  cannot validate the old cookies, so it stays silent (§11.3.1). Listeners
  notice only when relay beacons (every 5 s) stop for 3 × 5 s (§11.3.5), then
  HELLO → COOKIE → LISTEN (retransmit 1, 2, 4, 8 s); the relay answers
  LISTEN_OK and a snapshot paced at 32 kbit/s. The relay's receive buffer is
  the default (212 992 B), so the HELLO burst can overflow it.

No loss is applied. Frames are not signed here: E5 is about connection and
lease dynamics, not verification.

    python e5_reconnect_storm.py all
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import random
import signal
import socket
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import netns, stats  # noqa: E402

ITEMS, FRAME = 20, 330
PORT = 7400
BEACON_S, LEASE_S, MISSED = 5, 75, 3
GRANTED_BPS = 32_000
RETRY_S = (1, 2, 4, 8)
SNAPSHOT_TIMEOUT_S = 5
HELLO, COOKIE, LISTEN, LISTEN_OK, RENEW, BEACON = 0x10, 0x11, 0x12, 0x13, 0x14, 0x20
HDR = b"BC\x02"


def frames() -> list[bytes]:
    return [struct.pack(">HI", FRAME - 2, i) + bytes(FRAME - 6) for i in range(ITEMS)]


def msg(kind: int, *parts: bytes, pad_to: int = 0) -> bytes:
    m = HDR + bytes([kind]) + b"".join(parts)
    return m + bytes(max(0, pad_to - len(m)))


# ---------------------------------------------------------------- relays

async def tcp_relay(backlog: int) -> None:
    snap = b"".join(frames())

    async def serve(reader, writer):
        writer.write(snap)
        try:
            await writer.drain()
            await reader.read()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    ls = socket.socket()
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind(("127.0.0.1", PORT))
    ls.listen(backlog)
    srv = await asyncio.start_server(serve, sock=ls, backlog=backlog)   # asyncio re-listens; pass it on
    print("ready", flush=True)
    await srv.serve_forever()


async def udp_relay() -> None:
    loop = asyncio.get_running_loop()
    secret = os.urandom(32)                          # a restarted relay has a new secret and no leases
    leases: dict = {}
    snap = frames()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT))
    s.setblocking(False)

    def cookie(addr, nonce):
        return hmac.new(secret, socket.inet_aton(addr[0]) + struct.pack(">H", addr[1]) + nonce,
                        hashlib.sha256).digest()[:16]

    async def snapshot(addr):
        for f in snap:
            s.sendto(f, addr)
            await asyncio.sleep(8 * len(f) / GRANTED_BPS)

    def readable():
        while True:
            try:
                data, addr = s.recvfrom(2048)
            except BlockingIOError:
                return
            if len(data) < 20 or data[:3] != HDR:
                continue
            kind, nonce = data[3], data[4:20]
            if kind == HELLO and len(data) >= 256:
                s.sendto(msg(COOKIE, nonce, cookie(addr, nonce)), addr)
            elif kind in (LISTEN, RENEW) and hmac.compare_digest(data[20:36], cookie(addr, nonce)):
                new = addr not in leases
                leases[addr] = time.time() + LEASE_S
                if kind == LISTEN:
                    s.sendto(msg(LISTEN_OK, nonce, bytes(40)), addr)
                    if new:
                        loop.create_task(snapshot(addr))

    loop.add_reader(s, readable)
    print("ready", flush=True)
    while True:
        await asyncio.sleep(BEACON_S * random.uniform(0.9, 1.1))
        now = time.time()
        for addr, exp in list(leases.items()):
            if now > exp:
                del leases[addr]
            else:
                s.sendto(msg(BEACON, bytes(16)), addr)


# ---------------------------------------------------------------- listeners

async def tcp_listeners(n: int) -> None:
    """Keep n connections; print when all hold the snapshot, and again after every recovery."""
    served: dict[int, float] = {}
    attempts = {"connect": 0, "refused": 0, "snapshot_timeout": 0}
    first = asyncio.Event()

    async def one(i: int):
        while True:
            try:
                attempts["connect"] += 1
                r, w = await asyncio.open_connection("127.0.0.1", PORT)
            except (ConnectionRefusedError, OSError):
                attempts["refused"] += 1
                await asyncio.sleep(0.1)
                continue
            try:
                try:
                    await asyncio.wait_for(r.readexactly(ITEMS * FRAME), SNAPSHOT_TIMEOUT_S)
                except asyncio.TimeoutError:
                    attempts["snapshot_timeout"] += 1       # a half-open ghost: the relay never accepted it
                    continue
                served[i] = time.time()
                if len(served) == n:
                    first.set()
                await r.read()                       # returns b"" when the relay dies
            except (asyncio.IncompleteReadError, ConnectionError, OSError):
                pass
            finally:
                w.close()
            served.pop(i, None)

    tasks = [asyncio.create_task(one(i)) for i in range(n)]
    await _report(served, n, attempts, first)
    for t in tasks:
        t.cancel()


async def udp_listeners(n: int) -> None:
    loop = asyncio.get_running_loop()
    served: dict[int, float] = {}
    attempts = {"hello": 0, "listen": 0, "renew": 0}
    first = asyncio.Event()
    relay = ("127.0.0.1", PORT)

    async def one(i: int):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        s.setblocking(False)
        inbox: asyncio.Queue = asyncio.Queue()
        loop.add_reader(s, lambda: _drain(s, inbox))
        while True:
            nonce = os.urandom(16)
            got = await _exchange(s, inbox, relay, msg(HELLO, nonce, pad_to=256), COOKIE, nonce, attempts, "hello")
            cookie = got[20:36]
            await _exchange(s, inbox, relay, msg(LISTEN, nonce, cookie, bytes(28)), LISTEN_OK, nonce, attempts,
                            "listen")
            have, last_beacon = set(), time.time()
            next_renew = time.time() + 22 * random.uniform(0.8, 1.2)
            while time.time() - last_beacon < MISSED * BEACON_S:          # relay unobservable after 3 beacons
                try:
                    d = await asyncio.wait_for(inbox.get(), 0.5)
                except asyncio.TimeoutError:
                    d = None
                if d is not None:
                    if d[:3] == HDR and d[3] == BEACON:
                        last_beacon = time.time()
                    elif d[:3] != HDR:
                        have.add(struct.unpack_from(">I", d, 2)[0])
                        if len(have) == ITEMS and i not in served:
                            served[i] = time.time()
                            if len(served) == n:
                                first.set()
                if time.time() >= next_renew:
                    s.sendto(msg(RENEW, nonce, cookie, bytes(60)), relay)
                    attempts["renew"] += 1
                    next_renew = time.time() + 22 * random.uniform(0.8, 1.2)
            served.pop(i, None)

    tasks = [asyncio.create_task(one(i)) for i in range(n)]
    await _report(served, n, attempts, first)
    for t in tasks:
        t.cancel()


def _drain(s, inbox):
    while True:
        try:
            inbox.put_nowait(s.recv(2048))
        except BlockingIOError:
            return


async def _exchange(s, inbox, relay, out: bytes, want: int, nonce: bytes, attempts: dict, name: str) -> bytes:
    for wait in RETRY_S + (8,) * 1000:
        s.sendto(out, relay)
        attempts[name] += 1
        end = time.time() + wait
        while (left := end - time.time()) > 0:
            try:
                d = await asyncio.wait_for(inbox.get(), left)
            except asyncio.TimeoutError:
                break
            if d[:3] == HDR and d[3] == want and d[4:20] == nonce:
                return d
    raise RuntimeError("unreachable")


async def _report(served: dict, n: int, attempts: dict, first: asyncio.Event) -> None:
    """Print 'up' once all n are served, then wait for SIGUSR1 (relay killed) and time the recovery."""
    await first.wait()
    print(json.dumps({"up": True, **attempts}), flush=True)
    killed = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, killed.set)
    await killed.wait()
    t_kill = time.time()
    before = dict(attempts)
    while True:
        await asyncio.sleep(0.01)
        back = [t for t in served.values() if t > t_kill]
        if len(back) == n:
            break
    print(json.dumps({"t_kill": t_kill, "recover_s": [round(t - t_kill, 4) for t in sorted(back)],
                      "attempts_during": {k: attempts[k] - before[k] for k in attempts}}), flush=True)


# ---------------------------------------------------------------- orchestration (inside a namespace)

def _strace_counts(path: str) -> dict:
    """Parse ``strace -c`` output into {syscall: calls} and a total."""
    out = {}
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) >= 5 and p[0].replace(".", "").isdigit() and not line.startswith("100.00"):
                out[p[-1]] = int(p[3])
    return {"total": sum(out.values()), "by_call": dict(sorted(out.items(), key=lambda kv: -kv[1])[:12])}


def _cpu(pid: int) -> float:
    with open(f"/proc/{pid}/stat") as f:
        p = f.read().rsplit(")", 1)[1].split()
    return (int(p[11]) + int(p[12])) / os.sysconf("SC_CLK_TCK")


def run_one(a) -> None:
    lossy = netns.Lossy()
    me = [sys.executable, os.path.abspath(__file__)]
    relay_argv = [*me, "relay", "--mode", a.mode, "--backlog", str(a.backlog)]
    relay = subprocess.Popen(relay_argv, stdout=subprocess.PIPE, text=True)
    assert relay.stdout.readline().strip() == "ready"
    snmp_start, t_start = netns.snmp(), time.time()
    lis = subprocess.Popen([*me, "listeners", "--mode", a.mode, "--n", str(a.n)], stdout=subprocess.PIPE, text=True)
    up = json.loads(lis.stdout.readline())
    up["all_served_after_start_s"] = round(time.time() - t_start, 3)
    up["kernel"] = netns.snmp_delta(snmp_start, netns.snmp(), {
        "TcpExt": ["ListenOverflows", "SyncookiesSent", "TCPSynRetrans"], "Udp": ["RcvbufErrors"]})
    time.sleep(2)
    snmp0, c0 = netns.snmp(), lossy.counters()
    t_kill = time.time()
    relay.send_signal(signal.SIGKILL)
    lis.send_signal(signal.SIGUSR1)
    relay.wait()
    relay2 = subprocess.Popen(relay_argv, stdout=subprocess.PIPE, text=True)
    assert relay2.stdout.readline().strip() == "ready"
    t_ready = time.time()
    tracer, trace_file = None, f"/tmp/pd-e5-strace-{os.getpid()}.txt"
    if a.strace:
        tracer = subprocess.Popen(["strace", "-c", "-f", "-o", trace_file, "-p", str(relay2.pid)],
                                  stderr=subprocess.DEVNULL)
    cpu0 = _cpu(relay2.pid)
    rec = json.loads(lis.stdout.readline())
    cpu1 = _cpu(relay2.pid)
    snmp1, c1 = netns.snmp(), lossy.counters()
    syscalls = None
    if tracer:
        tracer.send_signal(signal.SIGINT)
        tracer.wait()
        syscalls = _strace_counts(trace_file)
        os.unlink(trace_file)
    lis.kill(), relay2.kill()
    lis.wait(), relay2.wait()
    r = rec["recover_s"]
    print(json.dumps({"strace_pass": a.strace,
        "mode": a.mode, "n": a.n, "backlog": a.backlog if a.mode == "tcp" else None,
        "new_relay_ready_after_kill_s": round(t_ready - t_kill, 3),
        "all_served_after_kill_s": r[-1], "served_after_kill_s": stats.summary(r, "s"),
        "served_within_s": {str(x): sum(1 for v in r if v <= x) for x in (0.5, 1, 2, 4, 8, 16, 32)},
        "listener_attempts_during": rec["attempts_during"], "initial_attempts": up,
        "new_relay_syscalls": syscalls, "new_relay_cpu_s": round(cpu1 - cpu0, 3),
        "packets_offered": c1["offered"] - c0["offered"],
        "snmp": netns.snmp_delta(snmp0, snmp1, {
            "Tcp": ["ActiveOpens", "PassiveOpens", "AttemptFails", "OutRsts", "OutSegs"],
            "TcpExt": ["ListenOverflows", "ListenDrops", "TCPSynRetrans", "SyncookiesSent", "TCPReqQFullDrop",
                       "TCPReqQFullDoCookies", "TCPTimeouts"],
            "Udp": ["InDatagrams", "OutDatagrams", "RcvbufErrors", "NoPorts"]})}))


def run_all(a) -> None:
    runs = []
    for rep in range(a.repeats):
        for strace in (False, True) if rep == 0 else (False,):
            for mode, backlog in (("tcp", 128), ("tcp", 4096), ("udp-lease", 0)):
                ns = netns.name(f"e5-{mode}-{backlog}")
                with netns.netns(ns):
                    argv = [sys.executable, os.path.abspath(__file__), "one", "--mode", mode, "--backlog",
                            str(backlog), "--n", str(a.n)] + (["--strace"] if strace else [])
                    runs.append({"repeat": rep, **json.loads(netns.run(*netns.ns_exec(ns, *argv)).splitlines()[-1])})
                print(json.dumps({k: runs[-1][k] for k in ("repeat", "strace_pass", "mode", "backlog",
                                                           "all_served_after_kill_s")}), flush=True)
    stats.write_json(os.path.join(HERE, "results", "e5_reconnect_storm.json"),
                     {"experiment": "e5_reconnect_storm", "n": a.n, "items": ITEMS, "frame_bytes": FRAME,
                      "runs": runs, "env": stats.env()})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("relay")
    r.add_argument("--mode", required=True)
    r.add_argument("--backlog", type=int, default=128)
    li = sub.add_parser("listeners")
    li.add_argument("--mode", required=True)
    li.add_argument("--n", type=int, default=1000)
    one = sub.add_parser("one")
    one.add_argument("--mode", required=True)
    one.add_argument("--backlog", type=int, default=128)
    one.add_argument("--n", type=int, default=1000)
    one.add_argument("--strace", action="store_true", help="count the new relay's syscalls (not timed)")
    al = sub.add_parser("all")
    al.add_argument("--n", type=int, default=1000)
    al.add_argument("--repeats", type=int, default=3)
    a = p.parse_args()
    if a.cmd == "relay":
        asyncio.run(tcp_relay(a.backlog) if a.mode == "tcp" else udp_relay())
    elif a.cmd == "listeners":
        asyncio.run(tcp_listeners(a.n) if a.mode == "tcp" else udp_listeners(a.n))
    elif a.cmd == "one":
        run_one(a)
    else:
        run_all(a)


if __name__ == "__main__":
    main()
