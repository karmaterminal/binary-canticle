"""The host daemon's intake: fair admission before verify and durable write (binary-canticle#171, design #168 §2.4 step 2).

A datagram costs the daemon a signature check, and a new item a durable save. Served in arrival order, whoever sends
most decides what everyone hears (#171). So a reader thread takes every datagram off the socket in microseconds and
decides only whether it gets a place to wait; ``take`` then hands out what waits in a fair order:

1. **Not a frame of a listed key** (framing, unknown or revoked key id): one small shared queue with its own budget.
   Only keys, and streams, that the manifest lists ever get a queue of their own.
2. **An exact repeat** of a frame already verified and accepted in this run, by SHA-256 of the whole datagram: counted
   and dropped. It is never verified, queued or debited. The digest is recorded only after the signature verified and
   the save that covers the frame landed, so nothing a sender claims (a key, a seq) can reserve a place here and shut
   out the valid frame behind it.
3. **Everything else** waits in the queue of the key, stream and source address it claims, round-robin at each level:
   over keys, over a key's streams, over the sources of a stream. A queue that is full refuses, and counts why.

What is spent, and by whom:

- a key and each of its streams have a bucket, spent only by frames whose signature verified and that were new. A
  key's cap is shared round-robin by its streams, and one stream's cap is below it, so a flooding stream leaves its
  siblings room. Beacons have their own bucket;
- a check that comes to nothing (it failed, or it verified a frame that changed nothing, such as a replayed beacon,
  which has no expiry and verifies for ever) is charged to the source it came from. Each address a new frame of the
  key was verified from (the latest KNOWN_MAX) has a budget of its own, and all other addresses claiming the key
  share one. All of them together have one bound, which is what the daemon spends on checks that come to nothing;
- in a stream, the known sources get every other turn however many strangers claim it. Strangers queue apart too, in
  a pool the stream's longest queue pays for, so a flood can fill it but not keep a station's first frame out.

What this does not do:

- **A source address is not trusted, only queued by.** It admits nothing and refuses nothing (I-11). It is as good as
  the network's enforcement: a sender that spoofs the station's exact address and port shares the station's own
  queue and budget. Beyond SOURCE_RATE forgeries a second, each honest frame is then verified only as often as
  chance picks it among them. Other keys are unaffected and every refusal is counted, but nothing before the
  signature can tell the two apart.
- **A station that is still a stranger, among many.** Until one of its frames verifies from a new address (a cold
  start, or its restart on a new port), it competes with every other stranger claiming its key. STRANGERS_PER_HOST
  ports of a host, and STRANGERS_MAX in all, queue apart; beyond that they share one queue, and chance decides.
- **Source binding and a house MAC** (RFC §10.2) are not here. A binding is only as good as the switch's enforcement.
  A MAC excludes outsiders but not another key holder. Neither replaces the signature.
- **The reader can be outrun.** Then the kernel drops datagrams, whoever sent them: counted (``socket_drops``), and
  never hidden among the refusals.

The sizes are [PROPOSED DEFAULT]s of this spike. RFC §14.1 checks the per-key rate and deduplicates in another order:
see the departures in the prototype README.
"""

from __future__ import annotations

import ctypes
import errno
import heapq
import os
import socket
import struct
import sys
import threading
import time
from collections import Counter, OrderedDict, deque
from hashlib import sha256
from typing import Callable, Optional

from . import wire

# New verified frames a second, and at once, per key (beacons apart) and per stream of it. B_station (§7.5: 16 kbit/s)
# carries about 10 frames of 190 B a second, repeats included, and repeats cost nothing here. A stream's cap is below
# its key's, so its siblings have room.
KEY_RATE, KEY_BURST = 16.0, 64.0
STREAM_RATE, STREAM_BURST = 12.0, 48.0
BEACON_RATE, BEACON_BURST = 8.0, 16.0       # new beacons per key
# Checks a second, and at once, that come to nothing: per known source of a key, and per key for all its strangers;
# and for everything that claims a listed key, together (a check is 60-140 µs on ronan, #171).
SOURCE_RATE, SOURCE_BURST = 1_000.0, 100.0
CHECK_RATE, CHECK_BURST = 2_000.0, 200.0
UNLISTED_RATE, UNLISTED_BURST = 500.0, 500.0  # datagrams of no listed key examined a second, all together
UNLISTED_DEPTH = 64
KNOWN_MAX, KNOWN_DEPTH = 4, 64              # known sources per key; datagrams waiting per stream and known source
STRANGERS_MAX = 64                          # other sources per key that queue apart
STRANGERS_PER_HOST = 16                     # of them, at one address: ports are free, so they must not fill the table
STRANGER_POOL = 256                         # datagrams waiting per stream for all strangers together
RECLAIM_S = 0.1                             # how often a full table of strangers is searched for idle ones
BEACON_REPEATS = 64                         # beacon digests kept per key
RCVBUF = 4 << 20                            # asked of the kernel (capped by net.core.rmem_max)
READ_TIMEOUT_S = 0.25                       # how long the reader waits before it looks whether to stop
READ_BATCH = 256                            # datagrams per read
PAUSE_S = 0.01                              # after a read that failed for now
REFUSED = ("unlisted", "unverified", "over_rate", "backlog")

SO_RXQ_OVFL, SO_MEMINFO = 40, 55            # Linux (asm-generic); the socket module names neither
MEMINFO_WORDS, MEMINFO_DROPS = 9, 8         # SK_MEMINFO_VARS, SK_MEMINFO_DROPS (linux/sock_diag.h)
MSG_WAITFORONE = 0x10000
_KINDS = (wire.KIND_ITEM, wire.KIND_BEACON, wire.KIND_PLUCK)
_HEAD = wire.MAGIC + bytes([wire.VERSION])
_MIN_FRAME = wire.HEADER_LEN + 1 + wire.SIG_LEN
_SLOT = 1216                                # bytes read per datagram: more than MAX_DATAGRAM, so oversize shows
_BROKEN = (errno.EBADF, errno.ENOTSOCK, errno.EFAULT, errno.EINVAL)   # a read that fails so always will
BEACON, OTHER = "beacon", "other"           # the queues of a key beside its listed streams


class Bucket:
    """A token bucket. Full at the start."""

    __slots__ = ("rate", "burst", "tokens", "at")

    def __init__(self, rate: float, burst: float):
        self.rate, self.burst, self.tokens, self.at = rate, burst, burst, 0.0

    def ready(self, now: float) -> bool:
        if now > self.at:
            self.tokens = min(self.burst, self.tokens + (now - self.at) * self.rate) if self.at else self.tokens
            self.at = now
        return self.tokens >= 1.0

    def take(self) -> None:
        self.tokens -= 1.0

    def give(self) -> None:
        self.tokens = min(self.burst, self.tokens + 1.0)


class Source:
    """One address and port claiming one key, or (``crowd``) every one beyond the table's bound."""

    __slots__ = ("budget", "known", "queued")

    def __init__(self, budget: Bucket):
        self.budget, self.known, self.queued = budget, False, 0


def host_of(addr):
    """The host of a source, as the reader gives it: the sockaddr_in's first 8 bytes as an integer (family, port,
    address), or recvmsg's tuple."""
    if isinstance(addr, tuple):
        return addr[0]
    return addr >> 32 if sys.byteorder == "little" else addr & 0xFFFFFFFF


class Lane:
    """What one source has waiting for one stream. It exists while something waits."""

    __slots__ = ("source", "queue")

    def __init__(self, source: Source):
        self.source, self.queue = source, deque()


class StreamQueue:
    """What waits for one stream of a key: a lane per source, the known ones and the strangers in turn."""

    __slots__ = ("bucket", "beacon", "lanes", "known", "strange", "pool", "known_next")

    def __init__(self, bucket: Bucket, beacon: bool = False):
        self.bucket, self.beacon = bucket, beacon
        self.lanes: dict = {}                           # Source -> Lane: every lane of the two rings below
        self.known, self.strange = deque(), deque()
        self.pool = 0                                   # datagrams waiting in the strangers' lanes
        self.known_next = True

    def put(self, source: Source, entry: tuple) -> tuple:
        """(whether a lane was opened, datagrams of which source lost their place or None): at most one, the new
        one or, when a stranger below its share of a full pool comes, the newest of the longest lane."""
        lane = self.lanes.get(source)
        out = None
        if source.known:
            if lane is not None and len(lane.queue) >= KNOWN_DEPTH:
                return False, source
        elif self.pool >= STRANGER_POOL:
            if lane is not None and len(lane.queue) >= STRANGER_POOL // len(self.strange):
                return False, source
            longest = max(self.strange, key=lambda o: len(o.queue))
            out = longest.source
            longest.queue.pop()
            out.queued -= 1
            self.pool -= 1
        new = lane is None
        if new:
            lane = self.lanes[source] = Lane(source)
            (self.known if source.known else self.strange).append(lane)
        lane.queue.append(entry)
        source.queued += 1
        self.pool += not source.known
        return new, out

    def pick(self, now: float) -> Optional[tuple]:
        for ring in ((self.known, self.strange) if self.known_next else (self.strange, self.known)):
            for _ in range(len(ring)):
                lane = ring[0]
                ring.rotate(-1)
                source = lane.source
                if not source.budget.ready(now):
                    continue
                entry = lane.queue.popleft()
                source.queued -= 1
                source.budget.take()
                self.pool -= ring is self.strange
                self.known_next = ring is self.strange
                if not lane.queue:
                    ring.pop()
                    del self.lanes[source]
                return (*entry, source)
        return None

    def change(self, source: Source) -> None:
        """``source`` has just become known, or a stranger again: its lane goes to the other ring."""
        lane = self.lanes.get(source)
        if lane is not None:
            old, new = (self.strange, self.known) if source.known else (self.known, self.strange)
            old.remove(lane)
            new.append(lane)
            self.pool += -len(lane.queue) if source.known else len(lane.queue)

    def drop(self, source: Source) -> None:
        """Forget what a source that is no longer known has waiting."""
        lane = self.lanes.pop(source, None)
        if lane is not None:
            self.known.remove(lane)


class KeyQueue:
    """Everything that waits under one listed key."""

    __slots__ = ("bucket", "streams", "ready", "known", "strangers", "hosts", "stranger_budget", "crowd", "reclaimed")

    def __init__(self, stream_ids):
        self.bucket = Bucket(KEY_RATE, KEY_BURST)
        self.streams = {sid: StreamQueue(Bucket(STREAM_RATE, STREAM_BURST)) for sid in (*stream_ids, OTHER)}
        self.streams[BEACON] = StreamQueue(Bucket(BEACON_RATE, BEACON_BURST), beacon=True)
        self.ready: deque = deque()               # the streams with something waiting, in turn
        self.known: OrderedDict = OrderedDict()   # address -> Source, oldest first
        self.strangers: dict = {}                 # address -> Source
        self.hosts: Counter = Counter()           # host -> how many of the strangers are there
        self.stranger_budget = Bucket(SOURCE_RATE, SOURCE_BURST)
        self.crowd = Source(self.stranger_budget)
        self.reclaimed = 0.0

    def source(self, addr, now: float) -> Source:
        got = self.known.get(addr) or self.strangers.get(addr)
        if got is not None:
            return got
        host = host_of(addr)
        if not self._room(host) and now - self.reclaimed >= RECLAIM_S:
            self.reclaimed = now
            for a in [a for a, s in self.strangers.items() if not s.queued]:
                self._leave(a)
        if not self._room(host):
            return self.crowd
        return self._enter(addr, Source(self.stranger_budget))

    def _room(self, host) -> bool:
        return len(self.strangers) < STRANGERS_MAX and self.hosts[host] < STRANGERS_PER_HOST

    def _enter(self, addr, source: Source) -> Source:
        self.hosts[host_of(addr)] += 1
        self.strangers[addr] = source
        return source

    def _leave(self, addr) -> Optional[Source]:
        got = self.strangers.pop(addr, None)
        if got is not None:
            host = host_of(addr)
            self.hosts[host] -= 1
            if not self.hosts[host]:
                del self.hosts[host]
        return got

    def know(self, addr) -> int:
        """A new frame of this key was verified from ``addr``. Returns how many waiting datagrams that displaced."""
        got = self.known.pop(addr, None)
        if got is None:
            got = self._leave(addr) or Source(self.stranger_budget)
            got.budget, got.known = Bucket(SOURCE_RATE, SOURCE_BURST), True
            for s in self.streams.values():
                s.change(got)
        self.known[addr] = got
        if len(self.known) <= KNOWN_MAX:
            return 0
        old_addr, old = self.known.popitem(last=False)
        old.budget, old.known = self.stranger_budget, False
        if self._room(host_of(old_addr)):
            self._enter(old_addr, old)
            for s in self.streams.values():
                s.change(old)
            return 0
        # No room to keep it apart: what it had waiting goes, so lanes stay bounded by the two tables.
        for s in self.streams.values():
            s.drop(old)
            if not s.lanes and s in self.ready:
                self.ready.remove(s)
        return old.queued

    def pick(self, now: float) -> Optional["Ticket"]:
        for _ in range(len(self.ready)):
            s = self.ready[0]
            self.ready.rotate(-1)
            if not s.bucket.ready(now) or not (s.beacon or self.bucket.ready(now)):
                continue
            got = s.pick(now)
            if got is None:
                continue
            if not s.lanes:
                self.ready.pop()
            s.bucket.take()
            if not s.beacon:
                self.bucket.take()
            return Ticket(*got, self, s)
        return None


class Unlisted:
    """The one queue of datagrams that claim no listed key, or are not frames: bounded, and examined on a budget."""

    __slots__ = ("bucket", "ready")

    def __init__(self):
        self.bucket, self.ready = Bucket(UNLISTED_RATE, UNLISTED_BURST), deque()

    def pick(self, now: float) -> Optional["Ticket"]:
        if not self.ready or not self.bucket.ready(now):
            return None
        self.bucket.take()
        data, at = self.ready.popleft()
        return Ticket(data, None, None, at, None, None, None)


class Ticket:
    """A datagram whose turn has come. It holds one token of each bucket it might pay from until ``settle``."""

    __slots__ = ("data", "digest", "addr", "at", "budget", "known", "key", "stream", "copies")

    def __init__(self, data: bytes, digest: Optional[bytes], addr, at: int, source: Optional[Source],
                 key: Optional[KeyQueue], stream: Optional[StreamQueue]):
        self.data, self.digest, self.addr, self.at = data, digest, addr, at    # at: when it arrived
        self.budget, self.known = (source.budget, source.known) if source is not None else (None, False)
        self.key, self.stream = key, stream
        self.copies = 0        # identical datagrams that had their turn in the same batch: they share its verdict


class Repeat:
    """A frame whose exact bytes are a no-op until ``until``, and the copies of it that came."""

    __slots__ = ("ident", "until", "copies", "last_ms")

    def __init__(self, ident: tuple, until: int):
        self.ident, self.until = ident, until      # ident: an item's or PLUCK's tuple, a beacon's (key id, epoch)
        self.copies = self.last_ms = 0             # since the event loop last asked, and when the last one came


def peek_stream(data: bytes) -> Optional[int]:
    """The stream id an ITEM or PLUCK claims (key 2), read from its first bytes. It only picks a queue: the strict
    decoder reads the frame again before anything comes of it. None when key 1 and 2 are not where deterministic
    encoding puts them (a frame with ``crit``, or no frame at all)."""
    try:
        p = 14 if data[12] == 0xB8 else 13
        ai = data[p + 1]           # the head of key 1's value: an unsigned integer is 0x00-0x1b
        if data[p] != 1 or ai > 0x1B:
            return None
        p += 2 if ai < 24 else 2 + (1 << (ai - 24))
        ai = data[p + 1]
        if data[p] != 2 or ai > 0x1B:
            return None
        return ai if ai < 24 else int.from_bytes(data[p + 2:p + 2 + (1 << (ai - 24))], "big")
    except IndexError:
        return None


class _Mmsg:
    """Reads the socket with recvmmsg(2), many datagrams a call: the reader gives up the interpreter lock once per
    call, so a busy event loop costs it a batch, not a datagram (and only a batch of them, at that)."""

    class _Iovec(ctypes.Structure):
        _fields_ = [("base", ctypes.c_void_p), ("len", ctypes.c_size_t)]

    class _Msghdr(ctypes.Structure):
        pass

    _Msghdr._fields_ = [("name", ctypes.c_void_p), ("namelen", ctypes.c_uint), ("iov", ctypes.POINTER(_Iovec)),
                        ("iovlen", ctypes.c_size_t), ("control", ctypes.c_void_p), ("controllen", ctypes.c_size_t),
                        ("flags", ctypes.c_int)]

    class _Mmsghdr(ctypes.Structure):
        pass

    _Mmsghdr._fields_ = [("hdr", _Msghdr), ("len", ctypes.c_uint)]

    def __init__(self, sock: socket.socket):
        self.call = ctypes.CDLL(None, use_errno=True).recvmmsg    # AttributeError where the C library has none
        self.call.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
        self.fd, n = sock.fileno(), READ_BATCH
        self.data = bytearray(n * _SLOT)
        self.names = bytearray(n * 16)                            # struct sockaddr_in
        self.control = ctypes.create_string_buffer(socket.CMSG_SPACE(4))
        self.iov = (self._Iovec * n)()
        raw = bytearray(n * ctypes.sizeof(self._Mmsghdr))
        self.msgs = (self._Mmsghdr * n).from_buffer(raw)
        data = ctypes.addressof((ctypes.c_char * len(self.data)).from_buffer(self.data))
        names = ctypes.addressof((ctypes.c_char * len(self.names)).from_buffer(self.names))
        for i in range(n):
            self.iov[i] = self._Iovec(data + i * _SLOT, _SLOT)
            h = self.msgs[i].hdr
            h.name, h.namelen = names + i * 16, 16
            h.iov, h.iovlen = ctypes.pointer(self.iov[i]), 1
        # Only the first datagram of a call carries the drop count: it is cumulative, and one a call is enough.
        self.msgs[0].hdr.control = ctypes.addressof(self.control)
        self.offsets = [i * _SLOT for i in range(n)]
        self.view = memoryview(self.data)
        # msg_len and the sockaddr's family, port and address, as arrays: no ctypes access per datagram.
        self.lens = memoryview(raw).cast("I")[self._Mmsghdr.len.offset // 4::ctypes.sizeof(self._Mmsghdr) // 4]
        self.addrs = memoryview(self.names).cast("Q")[::2]

    def read(self) -> tuple:
        """([(datagram, source)], the socket's drop count or None). Waits for the first datagram only, at most
        READ_TIMEOUT_S; ([], None) when there was none. A source is an opaque integer: address and port."""
        self.msgs[0].hdr.controllen = len(self.control)
        n = self.call(self.fd, ctypes.addressof(self.msgs), READ_BATCH, MSG_WAITFORONE, None)
        if n < 0:
            e = ctypes.get_errno()
            if e in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR):
                return [], None
            raise OSError(e, os.strerror(e))
        view = self.view
        out = [(view[o:o + size].tobytes(), addr) for o, size, addr in
               zip(self.offsets, self.lens[:n].tolist(), self.addrs[:n].tolist())]
        drops = None
        if n and self.msgs[0].hdr.controllen >= socket.CMSG_LEN(4):
            size, level, kind = struct.unpack_from("@Nii", self.control)
            if (level, kind) == (socket.SOL_SOCKET, SO_RXQ_OVFL):
                drops = struct.unpack_from("@I", self.control, socket.CMSG_LEN(0))[0]
        return out, drops


class _Msg:
    """The same through recvmsg(2), one datagram a call, where the C library has no recvmmsg."""

    def __init__(self, sock: socket.socket):
        self.sock = sock

    def read(self) -> tuple:
        try:
            data, anc, _, addr = self.sock.recvmsg(_SLOT, socket.CMSG_SPACE(4))
        except (BlockingIOError, InterruptedError):
            return [], None
        drops = next((struct.unpack("@I", v)[0] for level, kind, v in anc
                      if (level, kind) == (socket.SOL_SOCKET, SO_RXQ_OVFL)), None)
        return [(data, addr)], drops


class Intake:
    """The socket's reader thread, what waits, and the order it is served in. ``take``, ``settle`` and the rest are
    the event loop's; the reader shares the queues with them under one lock."""

    def __init__(self, sock: socket.socket, manifest, *, now_ms: Callable[[], int], wake: Callable[[], None],
                 failed: Callable[[BaseException], None] = lambda e: None, rcvbuf: int = RCVBUF):
        self.sock, self.now_ms, self.wake, self.failed = sock, now_ms, wake, failed
        self.keys = {e.key_id: KeyQueue(e.stream_names) for e in manifest if not e.revoked}
        self.unlisted = Unlisted()
        self.checks = Bucket(CHECK_RATE, CHECK_BURST)
        self.repeats: dict = {}                    # digest -> Repeat (recorded by ``remember`` only)
        self._due: list = []                       # heap of (until, digest) over the items and PLUCKs in it
        self._beacons = {kid: deque() for kid in self.keys}
        self._touched: deque = deque()             # Repeats with copies the event loop has not been told of
        self._ready: deque = deque()               # keys (and the unlisted queue) with something waiting, in turn
        self._lock = threading.Lock()
        self._stop = False
        self.read = self.repeated = self.verified = self.unverified = 0
        self.refused = dict.fromkeys(REFUSED, 0)
        self.last_datagram_at: Optional[int] = None
        self._drops = 0                            # total; the kernel's own counter is 32 bits wide
        self._drops_raw = 0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        try:
            sock.setsockopt(socket.SOL_SOCKET, SO_RXQ_OVFL, 1)
        except OSError:
            pass                                   # not Linux: socket_drops() then stays what it can see
        sock.settimeout(None)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack("@ll", 0, int(READ_TIMEOUT_S * 1e6)))
        try:
            self._reader = _Mmsg(sock)
        except AttributeError:
            self._reader = _Msg(sock)
        self._thread = threading.Thread(target=self._run, name="canticle-intake", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        try:
            self.sock.shutdown(socket.SHUT_RD)     # ENOTCONN on an unconnected socket, but it wakes the reader
        except OSError:
            pass
        if self._thread.is_alive():
            self._thread.join()

    @property
    def stopped(self) -> bool:
        return self._stop

    # ------------------------------------------------------------ the reader thread

    def _run(self) -> None:
        try:
            while not self._stop:
                try:
                    batch, drops = self._reader.read()
                except OSError as e:
                    if e.errno in (errno.ENOSYS, errno.EPERM) and isinstance(self._reader, _Mmsg):
                        self._reader = _Msg(self.sock)    # a sandbox without recvmmsg
                    elif e.errno in _BROKEN:
                        raise
                    else:
                        time.sleep(PAUSE_S)
                    continue
                if drops is not None:
                    self._note_drops(drops)
                if batch and not self._stop:
                    self.offer(batch)
        except BaseException as e:
            if not self._stop:
                self.failed(e)

    def offer(self, batch: list) -> None:
        """Place each (datagram, source): a repeat is counted, the rest wait or are refused."""
        now_ms, now = self.now_ms(), time.monotonic()
        keys, repeats = self.keys, self.repeats
        claims: list = []
        strange: list = []
        copies: dict = {}
        for data, addr in batch:
            key = keys.get(data[4:12])
            if (key is None or data[:3] != _HEAD or not _MIN_FRAME <= len(data) <= wire.MAX_FRAME
                    or data[3] not in _KINDS):
                strange.append((data, now_ms))
                continue
            digest = sha256(data).digest()
            rep = repeats.get(digest)
            if rep is not None and rep.until > now_ms:
                copies[rep] = copies.get(rep, 0) + 1
            else:
                claims.append((key, (data, digest, addr, now_ms)))
        fresh = False
        with self._lock:
            self.read += len(batch)
            self.last_datagram_at = now_ms
            for rep, n in copies.items():
                self._copy(rep, now_ms, n)
            for key, entry in claims:
                fresh |= self._place(key, entry, now)
            if strange:
                fresh |= self._place_unlisted(strange)
        if fresh:
            self.wake()

    def _copy(self, rep: Repeat, now_ms: int, n: int = 1) -> None:
        self.repeated += n
        if not rep.copies:
            self._touched.append(rep)
        rep.copies += n
        rep.last_ms = now_ms

    def _place(self, key: KeyQueue, entry: tuple, now: float) -> bool:
        """Queue one claim, or refuse it (or the one it displaces). True when a source has something waiting for
        the stream that had nothing."""
        data = entry[0]
        stream = key.streams.get(BEACON if data[3] == wire.KIND_BEACON else peek_stream(data)) or key.streams[OTHER]
        source = key.source(entry[2], now)
        idle = not stream.lanes
        new, out = stream.put(source, entry)
        if out is not None:
            self.refused["unverified" if out.budget.tokens < 1.0 or self.checks.tokens < 1.0 else
                         "over_rate" if stream.bucket.tokens < 1.0 or (key.bucket.tokens < 1.0 and not stream.beacon)
                         else "backlog"] += 1
        if idle:
            key.ready.append(stream)
            if len(key.ready) == 1:
                self._ready.append(key)
        return new

    def _place_unlisted(self, datagrams: list) -> bool:
        q = self.unlisted.ready
        room = datagrams[:UNLISTED_DEPTH - len(q)]
        self.refused["unlisted"] += len(datagrams) - len(room)
        new = bool(room) and not q
        q.extend(room)
        if new:
            self._ready.append(self.unlisted)
        return new

    # ------------------------------------------------------------ the event loop

    def take(self, limit: int) -> list:
        """Up to ``limit`` tickets in fair order, each holding its budgets. The same bytes never appear twice: a copy
        of a frame accepted since it was queued is a repeat, and one of a ticket already in the list shares it."""
        out: list = []
        seen: dict = {}
        now_ms, now = self.now_ms(), time.monotonic()
        with self._lock:
            while len(out) < limit:
                t = self._pick(now)
                if t is None:
                    break
                rep = self.repeats.get(t.digest)
                if rep is not None and rep.until > now_ms:
                    self._copy(rep, now_ms)
                    self._release(t)
                elif t.digest in seen and t.digest is not None:
                    seen[t.digest].copies += 1
                    self._release(t)
                else:
                    seen[t.digest] = t
                    out.append(t)
        return out

    def _pick(self, now: float) -> Optional[Ticket]:
        for _ in range(len(self._ready)):
            key = self._ready[0]
            self._ready.rotate(-1)
            if key is not self.unlisted and not self.checks.ready(now):
                continue
            t = key.pick(now)
            if not key.ready:
                self._ready.pop()
            if t is not None:
                if t.key is not None:
                    self.checks.take()
                return t
        return None

    def waiting(self) -> bool:
        return bool(self._ready)

    def _release(self, t: Ticket, station_pays: Optional[bool] = None) -> None:
        """Give back what a ticket held: all of it (no verdict was needed), or all but what the verdict costs."""
        if t.key is None:
            return
        if station_pays is not False:
            t.budget.give()
            self.checks.give()
        if station_pays is not True:
            t.stream.bucket.give()
            if not t.stream.beacon:
                t.key.bucket.give()

    def settle(self, t: Ticket, verified: bool, fresh: bool) -> None:
        """The verdict on a ticket. ``fresh`` is a verified frame not accepted before, at its key's current epoch: its
        station pays, and its address is a known source of the key from now on. A check that came to nothing is paid
        by the source it came from: forgeries by their sender, and so is a replay that verified and changed nothing.
        The exception is an ITEM or PLUCK from a known source: its station answers for it, so that the records of
        what it keeps having refused stay within its rate. Copies that had their turn beside the ticket were not
        looked at: they are repeats of a frame that verified, or refused with one that did not."""
        with self._lock:
            self._release(t, verified and (fresh or t.known and not t.stream.beacon))
            if not verified:
                self.unverified += 1
                self.refused["unverified"] += t.copies
                return
            rep = self.repeats.get(t.digest)
            if rep is not None and t.copies:
                self._copy(rep, self.now_ms(), t.copies)
            else:
                self.repeated += t.copies
            self.verified += 1
            if fresh and t.key is not None:
                self.refused["unverified"] += t.key.know(t.addr)
                if not t.key.ready and t.key in self._ready:
                    self._ready.remove(t.key)

    def remember(self, t: Ticket, ident: tuple, until: int) -> None:
        """From now until ``until``, a copy of this verified, accepted and durably saved frame is a repeat. There is
        one entry per live dedup entry (``until`` is inside its retention), so the listener's per-key quotas bound
        them and no key can push out another's, plus the latest BEACON_REPEATS beacons of each key."""
        self.repeats[t.digest] = Repeat(ident, until)
        if t.stream is not None and t.stream.beacon:
            kept = self._beacons[t.data[4:12]]
            kept.append(t.digest)
            if len(kept) > BEACON_REPEATS:
                self.repeats.pop(kept.popleft(), None)
        else:
            heapq.heappush(self._due, (until, t.digest))

    def forget(self, now_ms: int) -> None:
        while self._due and self._due[0][0] <= now_ms:
            self.repeats.pop(heapq.heappop(self._due)[1], None)

    def copies(self) -> list:
        """[(ident as remembered, copies since the last call, when the last one came)]"""
        out = []
        with self._lock:
            while self._touched:
                rep = self._touched.popleft()
                out.append((rep.ident, rep.copies, rep.last_ms))
                rep.copies = 0
        return out

    # ------------------------------------------------------------ what was lost, and where

    def _note_drops(self, raw: int) -> None:
        with self._lock:
            delta = (raw - self._drops_raw) & 0xFFFFFFFF
            if delta < 1 << 31:                    # else an older reading: the two sources below race
                self._drops += delta
                self._drops_raw = raw

    def socket_drops(self) -> int:
        """Datagrams the kernel dropped at this socket since it was opened. SO_RXQ_OVFL gives the count as of each
        datagram it queued, so drops after the last one would show only with the next; SO_MEMINFO reads the same
        counter now."""
        try:
            info = self.sock.getsockopt(socket.SOL_SOCKET, SO_MEMINFO, 4 * MEMINFO_WORDS)
            if len(info) == 4 * MEMINFO_WORDS:
                self._note_drops(struct.unpack(f"@{MEMINFO_WORDS}I", info)[MEMINFO_DROPS])
        except OSError:
            pass
        return self._drops

    def stats(self) -> dict:
        with self._lock:
            queued = len(self.unlisted.ready) + sum(
                len(lane.queue) for k in self.keys.values() for s in k.streams.values() for lane in s.lanes.values())
            return {"read": self.read, "repeats": self.repeated, "verified": self.verified,
                    "unverified": self.unverified, "queued": queued, "refused": dict(self.refused)}
