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

- a key and each of its streams have a bucket, debited only by frames whose signature verified. A key's cap is shared
  round-robin by its streams, and one stream's cap is below it, so a flooding stream leaves its siblings room;
- a failed check is charged to the source it came from: each address a new frame of this key was verified from (at
  most KNOWN_MAX, the latest) has a budget of its own, and all other addresses claiming the key share one. So
  forgeries can use up neither the honest station's verify work nor its bucket;
- beacons have their own bucket: an old beacon verifies whenever it is replayed (it has no expiry, §14.1 step 1), and
  must not spend what items need.

What this does not do:

- **A source address is not trusted, only queued by.** It admits nothing and refuses nothing (I-11). It is as good as
  the network's enforcement: a sender that spoofs the station's exact address and port shares the station's own
  queue and budget, and then each honest frame is verified only as often as chance picks it among the forgeries.
  Other keys are unaffected and every refusal is counted, but nothing before the signature can tell the two apart.
- **A cold start under a flood from many addresses.** Until a frame of a key has verified, its station is one
  stranger among those claiming the key. Up to STRANGERS_MAX addresses queue apart; beyond that they share one.
- **Source binding and a house MAC** (RFC §10.2) are not here. A binding is only as good as the switch's enforcement.
  A MAC excludes outsiders but not another key holder. Neither replaces the signature.
- **The reader can be outrun.** Then the kernel drops datagrams, whoever sent them: counted (``socket_drops``), and
  never hidden among the refusals.

The buckets' sizes are [PROPOSED DEFAULT]s of this spike. RFC §14.1 checks the per-key rate and deduplicates in
another order: see the departures in the prototype README.
"""

from __future__ import annotations

import ctypes
import errno
import heapq
import os
import socket
import struct
import threading
import time
from collections import OrderedDict, deque
from hashlib import sha256
from typing import Callable, Optional

from . import wire

KEY_RATE, KEY_BURST = 64.0, 128.0           # verified frames a second, and at once, per key (beacons apart)
STREAM_RATE, STREAM_BURST = 48.0, 96.0      # the same for one stream of it: below the key's, so a sibling has room
BEACON_RATE, BEACON_BURST = 8.0, 16.0       # verified beacons per key
KNOWN_RATE, KNOWN_BURST = 50.0, 50.0        # failed checks per key and known source
STRANGER_RATE, STRANGER_BURST = 50.0, 50.0  # failed checks per key, all other sources together
UNLISTED_RATE, UNLISTED_BURST = 500.0, 500.0  # datagrams of no listed key examined a second, all together
KNOWN_MAX, KNOWN_DEPTH = 4, 64              # known sources per key; datagrams waiting per stream and known source
STRANGERS_MAX, STRANGER_DEPTH = 12, 8       # other sources per key that queue apart; datagrams waiting for each
CROWD_DEPTH = 16                            # datagrams waiting per stream for every source beyond those
UNLISTED_DEPTH = 64
RECLAIM_S = 0.1                             # how often a full table of strangers is searched for idle ones
BEACON_REPEATS = 64                         # beacon digests kept per key
RCVBUF = 4 << 20                            # asked of the kernel (capped by net.core.rmem_max)
READ_TIMEOUT_S = 0.25                       # how long the reader waits before it looks whether to stop
READ_BATCH = 256                            # datagrams per read
REFUSED = ("unlisted", "unverified", "over_rate", "backlog")

SO_RXQ_OVFL, SO_MEMINFO = 40, 55            # Linux (asm-generic); the socket module names neither
MEMINFO_WORDS, MEMINFO_DROPS = 9, 8         # SK_MEMINFO_VARS, SK_MEMINFO_DROPS (linux/sock_diag.h)
MSG_WAITFORONE = 0x10000
_KINDS = (wire.KIND_ITEM, wire.KIND_BEACON, wire.KIND_PLUCK)
_HEAD = wire.MAGIC + bytes([wire.VERSION])
_MIN_FRAME = wire.HEADER_LEN + 1 + wire.SIG_LEN
_SLOT = 1216                                # bytes read per datagram: more than MAX_DATAGRAM, so oversize shows
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
    """One address claiming one key, or (``crowd``) every address beyond the table's bound."""

    __slots__ = ("budget", "depth", "queued")

    def __init__(self, budget: Bucket, depth: int):
        self.budget, self.depth, self.queued = budget, depth, 0


class Lane:
    """What one source has waiting for one stream. It exists while something waits."""

    __slots__ = ("source", "queue")

    def __init__(self, source: Source):
        self.source, self.queue = source, deque()


class StreamQueue:
    __slots__ = ("bucket", "beacon", "lanes", "ready")

    def __init__(self, bucket: Bucket, beacon: bool = False):
        self.bucket, self.beacon = bucket, beacon
        self.lanes: dict = {}          # Source -> Lane
        self.ready: deque = deque()    # the same lanes, in turn

    def pick(self, now: float) -> Optional[tuple]:
        for _ in range(len(self.ready)):
            lane = self.ready[0]
            self.ready.rotate(-1)
            source = lane.source
            if not source.budget.ready(now):
                continue
            got = lane.queue.popleft()
            source.queued -= 1
            source.budget.take()
            if not lane.queue:
                self.ready.pop()
                del self.lanes[source]
            return (*got, source.budget)
        return None


class KeyQueue:
    """Everything that waits under one listed key."""

    __slots__ = ("bucket", "streams", "ready", "known", "strangers", "stranger_budget", "crowd", "reclaimed")

    def __init__(self, stream_ids):
        self.bucket = Bucket(KEY_RATE, KEY_BURST)
        self.streams = {sid: StreamQueue(Bucket(STREAM_RATE, STREAM_BURST)) for sid in (*stream_ids, OTHER)}
        self.streams[BEACON] = StreamQueue(Bucket(BEACON_RATE, BEACON_BURST), beacon=True)
        self.ready: deque = deque()
        self.known: OrderedDict = OrderedDict()   # address -> Source, oldest first
        self.strangers: dict = {}                 # address -> Source
        self.stranger_budget = Bucket(STRANGER_RATE, STRANGER_BURST)
        self.crowd = Source(self.stranger_budget, CROWD_DEPTH)
        self.reclaimed = 0.0

    def source(self, addr, now: float) -> Source:
        got = self.known.get(addr) or self.strangers.get(addr)
        if got is not None:
            return got
        if len(self.strangers) >= STRANGERS_MAX and now - self.reclaimed >= RECLAIM_S:
            self.reclaimed = now
            for a in [a for a, s in self.strangers.items() if not s.queued]:
                del self.strangers[a]
        if len(self.strangers) >= STRANGERS_MAX:
            return self.crowd
        got = self.strangers[addr] = Source(self.stranger_budget, STRANGER_DEPTH)
        return got

    def know(self, addr) -> int:
        """A new frame of this key was verified from ``addr``. Returns how many waiting datagrams that displaced."""
        got = self.known.pop(addr, None)
        if got is None:
            got = self.strangers.pop(addr, None) or Source(None, 0)
            got.budget, got.depth = Bucket(KNOWN_RATE, KNOWN_BURST), KNOWN_DEPTH
        self.known[addr] = got
        if len(self.known) <= KNOWN_MAX:
            return 0
        old_addr, old = self.known.popitem(last=False)
        if len(self.strangers) < STRANGERS_MAX:
            old.budget, old.depth = self.stranger_budget, STRANGER_DEPTH
            self.strangers[old_addr] = old
            return 0
        # No room to keep it apart: what it had waiting goes, so lanes stay bounded by the two tables.
        gone = old.queued
        for s in self.streams.values():
            lane = s.lanes.pop(old, None)
            if lane is not None:
                s.ready.remove(lane)
                if not s.ready and s in self.ready:
                    self.ready.remove(s)
        return gone

    def pick(self, now: float) -> Optional["Ticket"]:
        for _ in range(len(self.ready)):
            s = self.ready[0]
            self.ready.rotate(-1)
            if not s.bucket.ready(now) or not (s.beacon or self.bucket.ready(now)):
                continue
            got = s.pick(now)
            if got is None:
                continue
            if not s.ready:
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
        return Ticket(self.ready.popleft(), None, None, None, None, None)


class Ticket:
    """A datagram whose turn has come. It holds one token of each bucket it might pay from until ``settle``."""

    __slots__ = ("data", "digest", "addr", "budget", "key", "stream", "copies")

    def __init__(self, data: bytes, digest: Optional[bytes], addr, budget: Optional[Bucket],
                 key: Optional[KeyQueue], stream: Optional[StreamQueue]):
        self.data, self.digest, self.addr = data, digest, addr
        self.budget, self.key, self.stream = budget, key, stream
        self.copies = 0        # identical datagrams that had their turn in the same batch: they share its verdict


class Repeat:
    """A frame whose exact bytes are a no-op until ``until``, and the copies heard of it."""

    __slots__ = ("ident", "until", "count", "noted", "last_ms", "touched")

    def __init__(self, ident: Optional[tuple], until: int):
        self.ident, self.until = ident, until      # ident: the item's or PLUCK's tuple, None for a beacon
        self.count = self.noted = self.last_ms = 0
        self.touched = False


def peek_stream(data: bytes) -> Optional[int]:
    """The stream id an ITEM or PLUCK claims (key 2), read from its first bytes. It only picks a queue: the strict
    decoder reads the frame again before anything comes of it. None when key 1 and 2 are not where deterministic
    encoding puts them (a frame with ``crit``, or no frame at all)."""
    try:
        p = 14 if data[12] == 0xB8 else 13
        if data[p] != 1:
            return None
        ai = data[p + 1]
        p += 2 if ai < 24 else 2 + (1 << (ai - 24))
        if data[p] != 2:
            return None
        ai = data[p + 1]
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
        sec = int(READ_TIMEOUT_S)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack("@ll", sec, int((READ_TIMEOUT_S - sec) * 1e6)))
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

    # ------------------------------------------------------------ the reader thread

    def _run(self) -> None:
        try:
            while not self._stop:
                batch, drops = self._reader.read()
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
        repeated = 0
        for data, addr in batch:
            key = keys.get(data[4:12])
            if (key is None or data[:3] != _HEAD or not _MIN_FRAME <= len(data) <= wire.MAX_FRAME
                    or data[3] not in _KINDS):
                strange.append(data)
                continue
            digest = sha256(data).digest()
            rep = repeats.get(digest)
            if rep is not None and rep.until > now_ms:
                repeated += 1
                self._copy(rep, now_ms)
            else:
                claims.append((key, data, digest, addr))
        fresh = False
        with self._lock:
            self.read += len(batch)
            self.repeated += repeated
            self.last_datagram_at = now_ms
            for key, data, digest, addr in claims:
                fresh |= self._place(key, data, digest, addr, now)
            if strange:
                fresh |= self._place_unlisted(strange)
        if fresh:
            self.wake()

    def _copy(self, rep: Repeat, now_ms: int, n: int = 1) -> None:
        rep.count += n
        rep.last_ms = now_ms
        if not rep.touched:
            rep.touched = True
            self._touched.append(rep)

    def _place(self, key: KeyQueue, data: bytes, digest: bytes, addr, now: float) -> bool:
        """Queue one claim, or refuse it. True when its stream had nothing waiting from that source."""
        stream = key.streams.get(BEACON if data[3] == wire.KIND_BEACON else peek_stream(data)) or key.streams[OTHER]
        source = key.source(addr, now)
        lane = stream.lanes.get(source)
        new = lane is None
        if new:
            lane = stream.lanes[source] = Lane(source)
            stream.ready.append(lane)
            if len(stream.ready) == 1:
                key.ready.append(stream)
                if len(key.ready) == 1:
                    self._ready.append(key)
        elif len(lane.queue) >= source.depth:
            self.refused["unverified" if source.budget.tokens < 1.0 else
                         "over_rate" if stream.bucket.tokens < 1.0 or (key.bucket.tokens < 1.0 and not stream.beacon)
                         else "backlog"] += 1
            return False
        lane.queue.append((data, digest, addr))
        source.queued += 1
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
                    self.repeated += 1
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
            t = key.pick(now)
            if not key.ready:
                self._ready.pop()
            if t is not None:
                return t
        return None

    def waiting(self) -> bool:
        return bool(self._ready)

    @staticmethod
    def _release(t: Ticket, verified: Optional[bool] = None) -> None:
        """Give back what a ticket held: all of it, or (by verdict) all but the bucket that pays."""
        if t.key is None:
            return
        if verified is not False:
            t.budget.give()
        if verified is not True:
            t.stream.bucket.give()
            if not t.stream.beacon:
                t.key.bucket.give()

    def settle(self, t: Ticket, verified: bool, fresh: bool) -> None:
        """The verdict on a ticket. A verified frame pays from its station's buckets, anything else from its source's
        budget for failed checks. ``fresh`` (a verified frame not accepted before, at the key's current epoch) makes
        its address a known source of the key: an old frame replayed from elsewhere does not."""
        with self._lock:
            self._release(t, verified)
            if not verified:
                self.unverified += 1
                if t.copies:
                    self.refused["unverified"] += t.copies
                return
            self.verified += 1
            self.repeated += t.copies
            if fresh and t.key is not None:
                self.refused["unverified"] += t.key.know(t.addr)

    def remember(self, t: Ticket, ident: Optional[tuple], until: int) -> None:
        """From now until ``until``, a copy of this verified, accepted and durably saved frame is a repeat. There is
        one entry per live dedup entry (``until`` is inside its retention), so the listener's per-key quotas bound
        them and no key can push out another's, plus the latest BEACON_REPEATS beacons of each key."""
        rep = self.repeats[t.digest] = Repeat(ident, until)
        if t.copies:
            self._copy(rep, self.now_ms(), t.copies)
        if ident is not None:
            heapq.heappush(self._due, (until, t.digest))
            return
        kept = self._beacons[t.data[4:12]]
        kept.append(t.digest)
        if len(kept) > BEACON_REPEATS:
            self.repeats.pop(kept.popleft(), None)

    def forget(self, now_ms: int) -> None:
        while self._due and self._due[0][0] <= now_ms:
            self.repeats.pop(heapq.heappop(self._due)[1], None)

    def copies(self) -> list:
        """[(ident or None for a beacon, copies since the last call, when the last was heard)]"""
        out = []
        for _ in range(len(self._touched)):
            rep = self._touched.popleft()
            rep.touched = False                    # before the count is read: a copy after this touches it again
            n, rep.noted = rep.count - rep.noted, rep.count
            if n:
                out.append((rep.ident, n, rep.last_ms))
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
