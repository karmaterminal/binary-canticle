"""Network namespaces and nftables loss for the protocol-dynamics testbed.

The kernel here has no netem, so loss is emulated by dropping packets in an
nftables ``input`` hook inside a private namespace:

- Bernoulli loss: ``numgen random mod 1000 < p`` on every TCP and UDP packet.
- Outage: a second rule that drops every TCP and UDP packet, added and later
  deleted by its handle.

Everything in one namespace shares ``lo``, so the input hook sees both
directions of every flow: TCP data *and* ACKs are dropped at rate p, as on a
lossy radio link. The ``output`` hook is not used because a drop there makes
``sendto()`` fail with EPERM, which a real lossy link never does.

There is no delay emulation: RTT on ``lo`` is tens of microseconds.

Namespace names carry a per-run prefix, ``PD_NS_PREFIX`` (``run_all.sh``
sets ``pd<its pid>-``; a script run on its own defaults to ``pd<pid>-``).
This module creates namespaces only under fresh names (``ip netns add`` fails
if the name exists) and deletes only the ones it created. When ``PD_NS_TRACK``
names a file, every namespace created is appended to it, so ``run_all.sh`` can
delete exactly what its run made even if a script was killed.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from typing import Iterator, Optional

TABLE = "lossy"
CHAIN = "inp"
PREFIX = os.environ.get("PD_NS_PREFIX") or f"pd{os.getpid()}-"
TRACK = os.environ.get("PD_NS_TRACK")
_created: set[str] = set()


def run(*argv: str, check: bool = True) -> str:
    return subprocess.run(argv, check=check, capture_output=True, text=True).stdout


def ns_exec(ns: str, *argv: str) -> list[str]:
    return ["ip", "netns", "exec", ns, *argv]


def name(suffix: str) -> str:
    """This run's name for a namespace, e.g. ``pd4242-e1-u2-loss50``."""
    return PREFIX + suffix


def add(ns: str) -> str:
    """Create namespace ``ns``. Raises if it already exists: another run's namespace is never adopted."""
    run("ip", "netns", "add", ns)
    _created.add(ns)
    if TRACK:
        with open(TRACK, "a") as f:
            f.write(ns + "\n")
    return ns


def delete(ns: str) -> None:
    """Delete ``ns`` if this process created it; anything else is left alone."""
    if ns in _created:
        run("ip", "netns", "del", ns, check=False)
        _created.discard(ns)


LO_MTU = 1500


@contextlib.contextmanager
def netns(ns: str) -> Iterator[str]:
    """A fresh namespace with ``lo`` up at MTU 1500; always deleted on the way out.

    The default ``lo`` MTU of 65536 gives TCP a 64 KiB MSS, which lets one
    retransmission carry a whole backlog and makes Linux autotune the send
    buffer straight to ``tcp_wmem[2]`` (4 MiB here). MTU 1500 gives the MSS
    (1448 with timestamps) and buffer sizes of an Ethernet path.
    """
    add(ns)
    try:
        run(*ns_exec(ns, "ip", "link", "set", "lo", "mtu", str(LO_MTU), "up"))
        yield ns
    finally:
        delete(ns)


class Lossy:
    """Loss control for the namespace this process runs in (call nft directly)."""

    def __init__(self) -> None:
        run("nft", "add", "table", "inet", TABLE)
        run("nft", "add", "chain", "inet", TABLE, CHAIN, "{ type filter hook input priority 0; }")
        self._seen = self._add("meta l4proto { tcp, udp } counter")   # every TCP/UDP packet offered
        self._loss: Optional[int] = None
        self._eligible: Optional[int] = None
        self._outage: Optional[int] = None
        self.outages = 0

    def _add(self, rule: str) -> int:
        out = run("nft", "--echo", "--handle", "add", "rule", "inet", TABLE, CHAIN, *rule.split())
        return int(out.split("# handle ")[1].split()[0])

    def _delete(self, handle: int) -> None:
        run("nft", "delete", "rule", "inet", TABLE, CHAIN, "handle", str(handle))

    def set_loss(self, permille: int, data_only: bool = False) -> None:
        """Bernoulli drop of each TCP/UDP packet with probability permille/1000.

        ``data_only`` spares packets of 100 IP bytes or less: pure TCP ACKs
        (52 B with timestamps), SYN and FIN. Every data frame here is larger.
        """
        if self._loss is not None:
            self._delete(self._loss)
            self._loss = None
        if permille > 0:
            size = "ip length > 100 " if data_only else ""
            if data_only:
                self._eligible = self._add(f"meta l4proto {{ tcp, udp }} {size}counter")
            self._loss = self._add(f"meta l4proto {{ tcp, udp }} {size}numgen random mod 1000 < {permille} counter drop")

    def outage_on(self) -> None:
        if self._outage is None:
            self._outage = self._add("meta l4proto { tcp, udp } counter drop")
            self.outages += 1

    def outage_off(self) -> None:
        if self._outage is not None:
            self._delete(self._outage)
            self._outage = None

    def drop_port(self, port: int) -> tuple[int, int]:
        """Silently black-hole one TCP/UDP port in both directions (a host that vanished)."""
        return (self._add(f"meta l4proto {{ tcp, udp }} th dport {port} counter drop"),
                self._add(f"meta l4proto {{ tcp, udp }} th sport {port} counter drop"))

    def undrop_port(self, handles: tuple[int, int]) -> None:
        for h in handles:
            self._delete(h)

    def exempt_udp_port(self, port: int) -> int:
        """Never drop UDP to ``port`` (inserted ahead of every other rule)."""
        out = run("nft", "--echo", "--handle", "insert", "rule", "inet", TABLE, CHAIN, "udp", "dport", str(port), "accept")
        return int(out.split("# handle ")[1].split()[0])

    def unexempt(self, handle: int) -> None:
        self._delete(handle)

    def counters(self) -> dict:
        """Packets offered to the hook and packets dropped by the loss rule."""
        rules = json.loads(run("nft", "-j", "list", "chain", "inet", TABLE, CHAIN))["nftables"]
        by_handle = {}
        for r in rules:
            if "rule" in r:
                for e in r["rule"]["expr"]:
                    if "counter" in e:
                        by_handle[r["rule"]["handle"]] = e["counter"]["packets"]
        out = {"offered": by_handle.get(self._seen, 0),
               "dropped_loss": by_handle.get(self._loss, 0) if self._loss else 0}
        if self._eligible:
            out["eligible"] = by_handle.get(self._eligible, 0)
        return out


def snmp() -> dict:
    """This namespace's /proc/net/snmp and /proc/net/netstat as {"Tcp": {...}, "TcpExt": {...}, ...}."""
    out: dict[str, dict] = {}
    for path in ("/proc/net/snmp", "/proc/net/netstat"):
        with open(path) as f:
            lines = f.read().splitlines()
        for head, vals in zip(lines[::2], lines[1::2]):
            proto, keys = head.split(":", 1)
            out[proto] = dict(zip(keys.split(), (int(v) for v in vals.split(":", 1)[1].split())))
    return out


def snmp_delta(before: dict, after: dict, keys: dict) -> dict:
    return {f"{proto}.{k}": after[proto][k] - before[proto][k] for proto, ks in keys.items() for k in ks
            if k in after.get(proto, {})}


def this_ns() -> str:
    return os.readlink("/proc/self/ns/net")


def set_cubic(sock) -> None:
    """Use cubic, the upstream Linux default, on a TCP socket.

    This host defaults to BBR, and a non-initial namespace may not change its
    default to a restricted algorithm (EPERM), so it is set per socket (root).
    """
    import socket
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, b"cubic")
