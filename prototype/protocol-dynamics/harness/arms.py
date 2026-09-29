"""The canticle side of each experiment: a real Station driven over UDP, real Listeners.

``CarouselSender`` is ``canticle.runner.run_station`` with one change: the
publisher calls ``publish()`` in-process and wakes the loop at once, instead of
going through the unix control socket. Scheduling, burst, jitter, supersede
and beacons are the unmodified ``canticle.station.Station``.

``frame_for()`` signs an item through the same ``Station.sing`` path, so the
TCP arms carry byte-for-byte the same kind of frame as the UDP arms.
"""

from __future__ import annotations

import asyncio
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import wire
from canticle.ids import CLASS_BY_NAME
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig

UDP_RCVBUF = 4 * 1024 * 1024   # large enough that socket overflow never masquerades as loss


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def wall() -> float:
    """Issue and receive times share CLOCK_REALTIME (kernel receive stamps use it)."""
    return time.time()


def body_text(k: int, size: int) -> str:
    """Update ``k`` padded to ``size`` bytes of body."""
    head = f"u={k:08d} "
    return head + "x" * max(0, size - len(head))


def update_index(text: str) -> int:
    return int(text[2:10])


def make_station(name: str, streams: list[StreamConfig], **kw) -> tuple[Station, StationEntry]:
    sk = Ed25519PrivateKey.generate()
    classes = frozenset(CLASS_BY_NAME[c.cls].code for c in streams)
    entry = StationEntry(name, wire.public_key_bytes(sk), classes, tuple(c.name for c in streams))
    return Station(sk, streams, now_ms=now_ms(), **kw), entry


def frame_for(station: Station, stream: str, k: int, body_size: int, **sing) -> bytes:
    """Sing update ``k`` and return the signed frame (the TCP arms send these bytes)."""
    r = station.sing(now_ms(), stream, text=body_text(k, body_size), **sing)
    return station.streams[stream].ring[r.seq].frame


@dataclass
class SendStats:
    frames: int = 0          # frames handed to the kernel (one per destination)
    bytes: int = 0
    item_frames: int = 0     # of which item copies (not beacons)
    errors: int = 0


class CarouselSender:
    """One station looping one keyed item to ``dests`` over UDP unicast."""

    def __init__(self, station: Station, stream: str, dests: list[tuple[str, int]], body_size: int,
                 loop="fast", ttl_s: Optional[float] = None):
        self.station, self.stream, self.dests = station, stream, dests
        self.body_size, self.loop, self.ttl_s = body_size, loop, ttl_s
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        self.sock.setblocking(False)
        self.wake = asyncio.Event()
        self.stats = SendStats()
        self.sing_results: list[dict] = []
        self.issue: dict[int, float] = {}   # update index -> issue time (wall())

    def publish(self, k: int, state_key: str = "now", t: Optional[float] = None) -> None:
        kw = {"ttl_s": self.ttl_s} if self.ttl_s else {}
        self.issue[k] = wall() if t is None else t
        r = self.station.sing(now_ms(), self.stream, text=body_text(k, self.body_size), state_key=state_key,
                              loop=self.loop, **kw)
        if len(self.sing_results) < 3:
            self.sing_results.append(r.to_json())
        self._flush()  # the immediate copy goes out now, not at the next poll
        self.wake.set()

    def _flush(self) -> None:
        for frame in self.station.poll(now_ms()):
            is_item = frame[3] == wire.KIND_ITEM
            for d in self.dests:
                try:
                    self.sock.sendto(frame, d)
                except OSError:
                    self.stats.errors += 1
                    continue
                self.stats.frames += 1
                self.stats.bytes += len(frame)
                self.stats.item_frames += is_item

    async def run(self, stop: asyncio.Event) -> None:
        try:
            while not stop.is_set():
                self._flush()
                delay = max(0, min(self.station.next_due(), now_ms() + 500) - now_ms()) / 1000
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.sock.close()


@dataclass
class Heard:
    """What one receiver saw: (receive time, update index) for each *new* item surfaced."""
    arrivals: list = field(default_factory=list)
    datagrams: int = 0
    evidence: dict = field(default_factory=dict)


SO_TIMESTAMPNS = 35     # asm-generic/socket.h (SO_TIMESTAMPNS_OLD); SCM_TIMESTAMPNS has the same value


def enable_rx_timestamps(sock: socket.socket) -> None:
    """Ask the kernel to stamp each received skb (CLOCK_REALTIME at netif_rx)."""
    sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPNS, 1)


def rx_time(ancdata) -> float:
    for level, typ, data in ancdata:
        if level == socket.SOL_SOCKET and typ == SO_TIMESTAMPNS:
            sec, nsec = struct.unpack("qq", data[:16])
            return sec + nsec / 1e9
    return time.time()


class UdpListener:
    """A UDP socket feeding a real ``canticle.listener.Listener``, with kernel receive timestamps."""

    def __init__(self, manifest: Manifest, port: int = 0, host: str = "127.0.0.1",
                 on_item: Optional[Callable[[int, float, object], None]] = None):
        self.listener = Listener(manifest, warmup=False, ephemeral=True)   # transport freshness: no §7.8 rule 4 hold; restarts not under test
        self.heard = Heard()
        self.on_item = on_item
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF)
        enable_rx_timestamps(self.sock)
        self.sock.bind((host, port))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.loop = asyncio.get_running_loop()
        self.loop.add_reader(self.sock, self._readable)

    def _readable(self) -> None:
        while True:
            try:
                data, anc, _, _ = self.sock.recvmsg(2048, 64)
            except (BlockingIOError, InterruptedError):
                return
            self.hear(data, rx_time(anc))

    def hear(self, data: bytes, t: float) -> None:
        self.heard.datagrams += 1
        for ev in self.listener.hear(data, now_ms()):
            if ev.kind == "item":
                k = update_index(ev.data["text"])
                self.heard.arrivals.append((t, k))
                if self.on_item:
                    self.on_item(k, t, ev)
            elif ev.kind == "evidence":
                r = ev.data.get("reason", "?")
                self.heard.evidence[r] = self.heard.evidence.get(r, 0) + 1

    def close(self) -> None:
        self.loop.remove_reader(self.sock)
        self.sock.close()


class TcpFrameReader:
    """A TCP client reading 2-byte length-prefixed frames, stamped with the kernel receive time.

    The stamp is that of the last skb consumed by the read that completed the
    frame (SO_TIMESTAMPNS on TCP), which is exact for frames that arrive alone.
    """

    def __init__(self, port: int, on_frame: Callable[[bytes, float], None], host: str = "127.0.0.1"):
        self.sock = socket.create_connection((host, port))
        enable_rx_timestamps(self.sock)
        self.sock.setblocking(False)
        self.buf = bytearray()
        self.on_frame = on_frame
        self.error: Optional[str] = None
        self.loop = asyncio.get_running_loop()
        self.loop.add_reader(self.sock, self._readable)

    def _readable(self) -> None:
        while True:
            try:
                data, anc, _, _ = self.sock.recvmsg(65536, 64)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as e:
                self.error = type(e).__name__
                self.close()
                return
            if not data:
                self.error = "EOF"
                self.close()
                return
            t = rx_time(anc)
            self.buf += data
            while len(self.buf) >= 2:
                n = struct.unpack_from(">H", self.buf)[0]
                if len(self.buf) < 2 + n:
                    break
                frame = bytes(self.buf[2:2 + n])
                del self.buf[:2 + n]
                self.on_frame(frame, t)

    def close(self) -> None:
        try:
            self.loop.remove_reader(self.sock)
        except (ValueError, OSError):
            pass
        self.sock.close()
