"""E3: slow and dead consumers, TCP versus UDP.

A relay sends one 700 B frame at 10 frames/s to N = 100 listeners on loopback,
inside a private namespace. One listener misbehaves.

``slow``: listener 0 stops reading at t = 10 s. Its process is alive and its
kernel keeps ACKing. Run twice: with the victim's SO_RCVBUF fixed at 64 KiB
(the kernel doubles it and turns off autotuning), and with Linux's autotuned
receive buffer, which on this kernel keeps growing for a reader that has
stopped (see SUMMARY.md). Sender variants:

- ``tcp-blocking``: blocking sockets, one sendall() per listener in turn;
- ``tcp-queue``: non-blocking sockets and an unbounded per-listener queue;
- ``tcp-drop``: the queue is capped at 64 KiB and the oldest whole frames are
  dropped (latest-only);
- ``tcp-disconnect``: the same cap, but the listener is disconnected instead;
- ``udp``: sendto() to 100 ports; the slow socket's buffer simply overflows.

``dead``: listeners vanish.

- ``tcp-kill``: listener 0's process gets SIGKILL at t = 10 s (its kernel sends RST).
- ``tcp-silent``: at t = 10 s every packet to and from listener 0's port is
  dropped and its process is stopped (host or path gone). The sender keeps an
  unbounded queue; we watch TCP retransmit and back off until the kernel
  aborts (tcp_retries2 = 15), or until TCP_USER_TIMEOUT when one is set.
- ``udp-lease``: relay leases per RFC-0001 §11.3.5 (lease 75 s, RENEW every
  22 s × U(0.8, 1.2)); 20 of 100 listeners die at random times in 30-60 s and
  their leases simply lapse.

Listeners stamp arrivals with the kernel receive time, and each frame carries
the time it was scheduled, so latency includes time queued at the sender.

    python e3_consumers.py slow        # about 5 min (variants run in parallel)
    python e3_consumers.py dead        # about 17 min (tcp-silent waits for the kernel to give up)
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import random
import selectors
import signal
import socket
import struct
import subprocess
import sys
import termios
import threading
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import netns, stats, tcpinfo  # noqa: E402
from harness.arms import enable_rx_timestamps, rx_time  # noqa: E402

HOST = "127.0.0.1"
HDR = struct.Struct(">HId")          # length, frame index, scheduled send time
CAP = 64 * 1024                      # per-listener queue cap for tcp-drop and tcp-disconnect
LEASE_S, RENEW_S = 75, 22            # RFC-0001 §11.3.5 proposed defaults


def frame_bytes(k: int, t: float, size: int) -> bytes:
    head = HDR.pack(size - 2, k, t)
    return head + bytes(size - len(head))


def rss_kb() -> int:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


# ---------------------------------------------------------------- TCP relay

class Client:
    __slots__ = ("sock", "role", "q", "qbytes", "partial", "dropped", "error", "closed_at")

    def __init__(self, sock: socket.socket, role: str):
        self.sock, self.role = sock, role
        self.q: deque = deque()     # whole frames not yet in the kernel; q[0] may be partly written
        self.qbytes = 0
        self.partial = False
        self.dropped = 0
        self.error = None
        self.closed_at = None


class TcpRelay:
    def __init__(self, a):
        self.a = a
        self.t0 = time.time()
        self.sel = selectors.DefaultSelector()
        self.clients: list[Client] = []
        self.in_send = None          # (role, start) while a blocking sendall() is in progress
        self.timeline: list[dict] = []

    def accept(self) -> None:
        ls = socket.socket()
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((HOST, self.a.port))
        ls.listen(1024)
        print("listening", flush=True)
        while len(self.clients) < self.a.n:
            s, _ = ls.accept()
            role = s.recv(1).decode()              # 'V' = the victim, 'H' = healthy
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            netns.set_cubic(s)
            if self.a.user_timeout_ms:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, self.a.user_timeout_ms)
            c = Client(s, role)
            if self.a.mode != "tcp-blocking":
                s.setblocking(False)
                self.sel.register(s, selectors.EVENT_READ, c)   # a read event reports RST/EOF/errors
            self.clients.append(c)
        self.victim = next(c for c in self.clients if c.role == "V")
        print("ready", flush=True)

    # the watchdog samples, and ends the run even if the main thread is stuck in sendall()
    def watchdog(self) -> None:
        end = self.t0 + self.a.duration
        while time.time() < end:
            time.sleep(self.a.sample_s)
            v = self.victim
            try:
                ti = tcpinfo.brief(v.sock) if v.closed_at is None else None
            except OSError:
                ti = None
            blocked = None
            if self.in_send is not None:
                blocked = {"on": self.in_send[0], "for_s": round(time.time() - self.in_send[1], 2)}
            self.timeline.append({
                "t": round(time.time() - self.t0, 2), "rss_kb": rss_kb(), "blocked": blocked,
                "victim_queue_bytes": v.qbytes, "victim_dropped": v.dropped,
                "healthy_queue_bytes": sum(c.qbytes for c in self.clients if c.role == "H"),
                "victim_tcp": ti and {k: ti[k] for k in ("state", "ca_state", "rto_ms", "backoff", "retransmits",
                                                         "total_retrans", "unacked", "notsent_bytes",
                                                         "bytes_retrans")}})
        v = self.victim
        stall = next((s for s in self.timeline if s["blocked"] and s["blocked"]["for_s"] > 1), None)
        print(json.dumps({
            "mode": self.a.mode, "n": self.a.n, "t0": self.t0, "user_timeout_ms": self.a.user_timeout_ms,
            "stalled_at_s": round(stall["t"] - stall["blocked"]["for_s"], 2) if stall else None,
            "victim": {"error": v.error, "closed_at_s": v.closed_at, "dropped": v.dropped,
                       "queue_bytes_end": v.qbytes},
            "healthy_errors": sum(1 for c in self.clients if c.role == "H" and c.error),
            "rss_kb_end": rss_kb(), "timeline": self.timeline}), flush=True)
        os._exit(0)

    def run(self) -> None:
        threading.Thread(target=self.watchdog, daemon=True).start()
        period, start, k = 1 / self.a.rate, time.time() + 0.5, 0
        while True:
            due = start + k * period
            if self.a.mode == "tcp-blocking":
                time.sleep(max(0, due - time.time()))
                f = frame_bytes(k, due, self.a.size)
                for c in self.clients:
                    self.in_send = (c.role, time.time())
                    try:
                        c.sock.sendall(f)                   # blocks while this listener's buffers are full
                    except OSError as e:
                        c.error = c.error or type(e).__name__
                    self.in_send = None
            else:
                self._serve_until(due)
                f = frame_bytes(k, due, self.a.size)
                for c in self.clients:
                    if c.closed_at is None:
                        self._enqueue(c, f)
            k += 1

    def _serve_until(self, due: float) -> None:
        while (wait := due - time.time()) > 0:
            for key, ev in self.sel.select(timeout=wait):
                c = key.data
                if ev & selectors.EVENT_READ:
                    self._read(c)
                if ev & selectors.EVENT_WRITE and c.closed_at is None:
                    self._flush(c)

    def _enqueue(self, c: Client, f: bytes) -> None:
        c.q.append(f)
        c.qbytes += len(f)
        if c.qbytes > CAP and self.a.mode == "tcp-disconnect":
            return self._close(c, "slow-consumer")
        if c.qbytes > CAP and self.a.mode == "tcp-drop":
            while c.qbytes > CAP and len(c.q) > 1:
                i = 1 if c.partial else 0               # never cut a frame already partly written
                c.qbytes -= len(c.q[i])
                del c.q[i]
                c.dropped += 1
        self._flush(c)

    def _flush(self, c: Client) -> None:
        try:
            while c.q:
                n = c.sock.send(c.q[0])
                c.qbytes -= n
                if n < len(c.q[0]):
                    c.q[0], c.partial = c.q[0][n:], True
                    break
                c.q.popleft()
                c.partial = False
        except BlockingIOError:
            pass
        except OSError as e:
            return self._close(c, type(e).__name__)
        self.sel.modify(c.sock, selectors.EVENT_READ | (selectors.EVENT_WRITE if c.q else 0), c)

    def _read(self, c: Client) -> None:
        try:
            if not c.sock.recv(4096):
                self._close(c, "EOF")
        except BlockingIOError:
            pass
        except OSError as e:
            self._close(c, type(e).__name__)

    def _close(self, c: Client, why: str) -> None:
        if c.closed_at is not None:
            return
        c.closed_at = round(time.time() - self.t0, 2)
        c.error = c.error or why
        self.sel.unregister(c.sock)
        c.sock.close()


# ---------------------------------------------------------------- UDP relay

def udp_relay(a) -> None:
    """UDP to N ports. With ``udp-lease`` each destination is a lease that lapses without RENEW."""
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, a.port))
    s.setblocking(False)
    dests = [(HOST, a.base + i) for i in range(a.n)]
    expires = {d: t0 + LEASE_S for d in dests}      # every listener sent LISTEN at t0
    lapsed: dict[int, float] = {}
    sent_to: dict[int, int] = {i: 0 for i in range(a.n)}
    sel = selectors.DefaultSelector()
    sel.register(s, selectors.EVENT_READ)
    print("ready", flush=True)
    period, start, k, timeline = 1 / a.rate, time.time() + 0.5, 0, []
    while time.time() - t0 < a.duration:
        due = start + k * period
        while (wait := due - time.time()) > 0:
            for _ in sel.select(timeout=wait):
                try:
                    while True:
                        data, _ = s.recvfrom(64)          # RENEW: the listener's port number
                        d = (HOST, int(data))
                        if d in expires and d[1] - a.base not in lapsed:
                            expires[d] = time.time() + LEASE_S
                except BlockingIOError:
                    pass
        now = time.time()
        f = frame_bytes(k, due, a.size)
        for i, d in enumerate(dests):
            if a.mode == "udp-lease" and i not in lapsed and now >= expires[d]:
                lapsed[i] = now                            # the relay deletes the lease silently
            if i in lapsed:
                continue
            try:
                s.sendto(f, d)
                sent_to[i] += 1
            except OSError:
                pass
        if not timeline or now - t0 - timeline[-1]["t"] >= a.sample_s:
            timeline.append({"t": round(now - t0, 2), "rss_kb": rss_kb(), "leases": a.n - len(lapsed)})
        k += 1
    print(json.dumps({"mode": a.mode, "n": a.n, "t0": t0, "frames_scheduled": k,
                      "lapsed_at_s": {i: round(t - t0, 2) for i, t in lapsed.items()},
                      "datagrams_to": sent_to, "rss_kb_end": rss_kb(), "timeline": timeline}), flush=True)


# ---------------------------------------------------------------- listeners

def listeners(a) -> None:
    """Listeners ``first .. first+count-1`` in this process."""
    t0 = time.time()
    idx = list(range(a.first, a.first + a.count))
    socks: dict[int, socket.socket] = {}
    for i in idx:
        if a.mode.startswith("udp"):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if i == a.victim and a.victim_rcvbuf:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, a.victim_rcvbuf)
            s.bind((HOST, a.base + i))
        else:
            s = socket.socket()
            if i == a.victim and a.victim_rcvbuf:     # set before connect: fixes the window, no autotuning
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, a.victim_rcvbuf)
            s.connect((HOST, a.port))
            s.sendall(b"V" if i == a.victim else b"H")
        enable_rx_timestamps(s)
        s.setblocking(False)
        socks[i] = s
    print("connected", flush=True)
    sel = selectors.DefaultSelector()
    for i, s in socks.items():
        sel.register(s, selectors.EVENT_READ, i)
    lat: dict[int, list] = {i: [] for i in idx}
    bufs = {i: bytearray() for i in idx}
    rng = random.Random(a.seed)
    renew_at = {i: t0 + RENEW_S * rng.uniform(0.8, 1.2) for i in idx}
    dies = {i: t0 + rng.uniform(30, 60) for i in rng.sample(idx, a.die)} if a.die else {}
    died: dict[int, float] = {}
    stopped = False
    while time.time() - t0 < a.duration:
        now = time.time()
        if a.slow_at and not stopped and now - t0 >= a.slow_at and a.victim in socks:
            sel.unregister(socks[a.victim])        # stop reading; the socket stays open
            stopped = True
        for i, t in dies.items():
            if i not in died and now >= t:
                sel.unregister(socks[i])
                socks[i].close()                   # process gone: no reads, no RENEW
                died[i] = now
        if a.mode == "udp-lease":
            for i in idx:
                if i not in died and now >= renew_at[i]:
                    socks[i].sendto(str(a.base + i).encode(), (HOST, a.port))
                    renew_at[i] = now + RENEW_S * rng.uniform(0.8, 1.2)
        for key, _ in sel.select(timeout=0.1):
            i, s = key.data, key.fileobj
            while True:
                try:
                    data, anc, _, _ = s.recvmsg(65536, 64)
                except (BlockingIOError, InterruptedError):
                    break
                except OSError:
                    sel.unregister(s)
                    break
                if not data:
                    sel.unregister(s)
                    break
                t = rx_time(anc)
                if a.mode.startswith("udp"):
                    _, k, due = HDR.unpack_from(data)
                    lat[i].append((round(t, 4), round((t - due) * 1000, 3)))
                    continue
                bufs[i] += data
                while len(bufs[i]) >= a.size:
                    _, k, due = HDR.unpack_from(bufs[i])
                    del bufs[i][:a.size]
                    lat[i].append((round(t, 4), round((t - due) * 1000, 3)))
    unread = None
    if a.victim in socks and a.victim not in died:
        try:
            unread = struct.unpack("i", fcntl.ioctl(socks[a.victim], termios.FIONREAD, b"\0" * 4))[0]
        except OSError:
            pass
    print(json.dumps({"t0": t0, "died_at": died, "victim_unread_bytes": unread,
                      "latency": {str(i): v for i, v in lat.items()}}), flush=True)


# ---------------------------------------------------------------- one run, in the current namespace

def _spawn(argv: list[str]) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, os.path.abspath(__file__), *argv], stdout=subprocess.PIPE, text=True)


def _last_json(p: subprocess.Popen) -> dict:
    lines = [ln for ln in p.stdout.read().splitlines() if ln.startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def _healthy(lat: dict, skip: set, t0: float, after: float, until: float, rate: float) -> dict:
    """Latency, gaps and starvation of the listeners that behaved, over [t0+after, t0+until] (relay clock)."""
    vals, gaps, frames, last = [], [], [], []
    lat = {i: [(p[0] - t0, p[1]) for p in v if p[0] - t0 <= until] for i, v in lat.items()}
    for i, v in lat.items():
        if int(i) in skip:
            continue
        pts = [p for p in v if p[0] >= after]
        frames.append(len(pts))
        vals += [p[1] for p in pts]
        ts = [p[0] for p in pts]
        gaps += [(b - c) * 1000 for c, b in zip(ts, ts[1:])]
        last.append(ts[-1] if ts else after)
    return {"latency_ms": stats.summary(vals), "max_gap_ms": round(max(gaps), 1) if gaps else None,
            "frames_per_listener_min": min(frames) if frames else 0,
            "frames_expected_per_listener": int((until - after) * rate),
            "last_frame_at_s_median": round(sorted(last)[len(last) // 2], 2) if last else None}


def run_one(a) -> None:
    lossy = netns.Lossy()
    snmp0 = netns.snmp()
    port, base = 7100, 30000
    common = ["--port", str(port), "--base", str(base), "--duration", str(a.duration)]
    relay_mode = {"tcp-kill": "tcp-queue", "tcp-silent": "tcp-queue"}.get(a.mode, a.mode)
    lmode = relay_mode if relay_mode.startswith("udp") else "tcp"     # 'udp-lease' listeners send RENEW
    argv = ["relay", "--mode", relay_mode, "--n", str(a.n), *common]
    if a.user_timeout_ms:
        argv += ["--user-timeout-ms", str(a.user_timeout_ms)]
    lis_args = ["listeners", "--mode", lmode, *common[:4], "--victim", "0", "--duration", str(a.duration + 2)]
    if lmode.startswith("udp"):  # UDP listeners bind before the relay starts sending
        extra = (["--die", "20", "--seed", "7"] if a.mode == "udp-lease"
                 else ["--slow-at", "10", "--victim-rcvbuf", str(a.victim_rcvbuf)])
        rest = _spawn([*lis_args, "--first", "0", "--count", str(a.n), *extra])
        assert rest.stdout.readline().strip() == "connected"
        relay = _spawn(argv)
        assert relay.stdout.readline().strip() == "ready"
        victim = None
    else:
        relay = _spawn(argv)
        assert relay.stdout.readline().strip() == "listening"
        if a.experiment == "slow":
            rest = _spawn([*lis_args, "--first", "0", "--count", str(a.n), "--slow-at", "10",
                           "--victim-rcvbuf", str(a.victim_rcvbuf)])
            victim = None
        else:
            victim = _spawn([*lis_args, "--first", "0", "--count", "1"])
            assert victim.stdout.readline().strip() == "connected"
            rest = _spawn([*lis_args, "--first", "1", "--count", str(a.n - 1)])
        assert rest.stdout.readline().strip() == "connected"
    t_death = None
    if victim is not None:
        time.sleep(10)
        t_death = time.time()
        if a.mode == "tcp-kill":
            victim.send_signal(signal.SIGKILL)
        else:
            lossy.drop_port(_victim_port(port, victim.pid))
            victim.send_signal(signal.SIGSTOP)
    out = _last_json(relay)
    lis = _last_json(rest)
    if victim is not None:
        victim.kill()
        victim.wait()
    relay.wait(), rest.wait()
    snmp1 = netns.snmp()
    lat = lis["latency"]
    skip = {0} if a.mode != "udp-lease" else {int(i) for i in lis["died_at"]}
    t0 = out["t0"]
    res = {"mode": a.mode, "relay": out, "healthy": _healthy(lat, skip, t0, 10.5, a.duration - 0.5, 10),
           "snmp": netns.snmp_delta(snmp0, snmp1, {
               "Udp": ["RcvbufErrors", "InDatagrams", "OutDatagrams", "NoPorts"],
               "Tcp": ["RetransSegs", "OutRsts", "EstabResets"],
               "TcpExt": ["TCPTimeouts", "TCPAbortOnTimeout", "TCPAbortOnData", "TCPAbortOnClose"]})}
    if a.experiment == "slow":
        res["victim_frames_received"] = len(lat.get("0", []))
        res["victim_rcvbuf_set"] = a.victim_rcvbuf or "autotuned"
        res["victim_unread_bytes_at_end"] = lis.get("victim_unread_bytes")
    if t_death is not None:
        res["death_at_s"] = round(t_death - t0, 2)
        closed = out["victim"]["closed_at_s"]
        res["victim_closed_after_death_s"] = round(t0 + closed - t_death, 3) if closed is not None else None
    if a.mode == "udp-lease":
        died = {int(i): t for i, t in lis["died_at"].items()}
        lapse = {i: (t0 + out["lapsed_at_s"][str(i)]) if str(i) in out["lapsed_at_s"] else None for i in died}
        res["leases"] = {
            "died": len(died), "lapsed": sum(1 for v in lapse.values() if v is not None),
            "healthy_lapsed": sum(1 for i in out["lapsed_at_s"] if int(i) not in died),
            "lapse_after_death_s": stats.summary([lapse[i] - died[i] for i in died if lapse[i] is not None], "s"),
            "datagrams_after_death_approx": stats.summary(
                [round((lapse[i] - died[i]) * 10) for i in died if lapse[i] is not None], "datagrams")}
        for s in out.get("timeline", []):
            s.pop("rss_kb", None)
    print(json.dumps(res))


def _thin(timeline: list[dict], every: int = 10) -> list[dict]:
    """Keep every 10th sample, plus every sample where the victim's TCP state or backoff changed."""
    out, prev = [], None
    for i, s in enumerate(timeline):
        v = s.get("victim_tcp") or {}
        key = (v.get("state"), v.get("backoff"), s.get("blocked") is None, v.get("ca_state"))
        if i % every == 0 or key != prev or i == len(timeline) - 1:
            out.append(s)
        prev = key
    return out


def _victim_port(port: int, pid: int) -> int:
    """Local port of the victim listener's connection (the one owned by ``pid``)."""
    out = netns.run("ss", "-tnpH", "state", "established", f"dport = :{port}")
    for line in out.splitlines():
        if f"pid={pid}," in line:
            return int(line.split()[2].rsplit(":", 1)[1])
    raise RuntimeError("victim connection not found")


def run_many(experiment: str, modes: list[tuple], n: int) -> dict:
    """Each variant in its own namespace, all in parallel (they are light)."""
    procs = {}
    with contextlib.ExitStack() as stack:
        for mode, uto, dur, *rest in modes:
            rcvbuf = rest[0] if rest else 0
            name = mode + (f"-uto{uto // 1000}s" if uto else "") + ("-autotuned" if experiment == "slow"
                                                                     and not rcvbuf else "")
            ns = stack.enter_context(netns.netns(f"pd-e3-{name}"))
            argv = [sys.executable, os.path.abspath(__file__), "one", "--experiment", experiment, "--mode", mode,
                    "--n", str(n), "--duration", str(dur), "--victim-rcvbuf", str(rcvbuf)]
            if uto:
                argv += ["--user-timeout-ms", str(uto)]
            procs[name] = subprocess.Popen(netns.ns_exec(ns, *argv), stdout=subprocess.PIPE, text=True)
        runs = {}
        for name, p in procs.items():
            out, _ = p.communicate()
            runs[name] = json.loads(out.splitlines()[-1]) if p.returncode == 0 else {"error": p.returncode}
            if isinstance(runs[name].get("relay"), dict) and "timeline" in runs[name]["relay"]:
                runs[name]["relay"]["timeline"] = _thin(runs[name]["relay"]["timeline"])
    return {"experiment": f"e3_{experiment}", "n": n, "rate": 10, "frame_bytes": 700, "event_at_s": 10,
            "queue_cap_bytes": CAP, "runs": runs, "env": stats.env()}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("relay")
    li = sub.add_parser("listeners")
    for s in (r, li):
        s.add_argument("--mode", required=True)
        s.add_argument("--n", type=int, default=100)
        s.add_argument("--port", type=int, default=7100)
        s.add_argument("--base", type=int, default=30000)
        s.add_argument("--rate", type=float, default=10)
        s.add_argument("--size", type=int, default=700)
        s.add_argument("--duration", type=float, default=120)
        s.add_argument("--sample-s", type=float, default=1)
        s.add_argument("--user-timeout-ms", type=int, default=0)
    li.add_argument("--first", type=int, default=0)
    li.add_argument("--count", type=int, default=100)
    li.add_argument("--victim", type=int, default=0)
    li.add_argument("--slow-at", type=float, default=0)
    li.add_argument("--victim-rcvbuf", type=int, default=0, help="SO_RCVBUF for the victim (0 = autotuned)")
    li.add_argument("--die", type=int, default=0, help="udp-lease: this many listeners die at U(30, 60) s")
    li.add_argument("--seed", type=int, default=1)
    one = sub.add_parser("one")
    one.add_argument("--experiment", choices=["slow", "dead"], required=True)
    one.add_argument("--mode", required=True)
    one.add_argument("--n", type=int, default=100)
    one.add_argument("--duration", type=float, default=120)
    one.add_argument("--user-timeout-ms", type=int, default=0)
    one.add_argument("--victim-rcvbuf", type=int, default=0)
    for name in ("slow", "dead"):
        s = sub.add_parser(name)
        s.add_argument("--n", type=int, default=100)
        s.add_argument("--out", default=os.path.join(HERE, "results", f"e3_{name}.json"))
    a = p.parse_args()
    if a.cmd == "relay":
        if a.mode.startswith("udp"):
            udp_relay(a)
        else:
            relay = TcpRelay(a)
            relay.accept()
            relay.run()
    elif a.cmd == "listeners":
        listeners(a)
    elif a.cmd == "one":
        run_one(a)
    elif a.cmd == "slow":
        # the victim fixes SO_RCVBUF at 64 KiB (the kernel doubles it); plus the autotuned default
        modes = [(m, 0, 600, 65536) for m in ("tcp-blocking", "tcp-queue", "tcp-drop", "tcp-disconnect", "udp")]
        modes += [("tcp-blocking", 0, 600, 0), ("udp", 0, 600, 0)]
        stats.write_json(a.out, run_many("slow", modes, a.n))
    else:
        modes = [("tcp-kill", 0, 60), ("tcp-silent", 30_000, 90), ("tcp-silent", 0, 1000), ("udp-lease", 0, 150)]
        stats.write_json(a.out, run_many("dead", modes, a.n))


if __name__ == "__main__":
    main()
