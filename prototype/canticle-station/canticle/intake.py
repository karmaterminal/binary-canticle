"""The host daemon's intake: a fast reader, exact repeats dropped before verify, and every loss counted
(binary-canticle#171; split from #173, whose scheduling is not here).

A datagram costs the daemon a signature check, and a new item a durable save. While the event loop does either, the
kernel's small socket buffer fills and drops, and nothing says so (#171). So a reader thread takes every datagram off
the socket in microseconds:

1. **An exact repeat** of a frame already verified and accepted in this run, by SHA-256 of the whole datagram, is counted
   and dropped: never verified, never queued. The digest is recorded only after the signature verified and the save that
   covers the frame landed, so nothing a sender claims (a key, a seq) can reserve a place here and shut out the valid
   frame behind it.
2. **Everything else** waits in one bounded queue in arrival order, and is heard from it. A queue that is full refuses,
   and counts it. A copy of what already waits takes no second place: the same bytes get the same verdict.

What this does not do: **it schedules nothing.** Who sends most still decides what everyone hears, as without it: a flood
of datagrams that must each be verified fills the queue, and a station's are heard as often as chance picks them.
It says so (``refused``), where without it the kernel dropped them and nothing did. Order of service is #173's.
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
from collections import deque
from hashlib import sha256
from typing import Callable, Optional

from . import wire

DEPTH = 1024                                # datagrams that wait to be heard, [PROPOSED DEFAULT]
TURN = 4                                    # places looked at per datagram a turn may serve
BEACON_REPEATS = 64                         # beacon digests kept per key
RCVBUF = 4 << 20                            # asked of the kernel (capped by net.core.rmem_max)
READ_TIMEOUT_S = 0.25                       # how long the reader waits before it looks whether to stop
READ_BATCH = 256                            # datagrams per read
PAUSE_S, PAUSES = 0.01, 100                 # after a read that failed for now, and how often in a row
REFUSED = ("backlog",)

SO_RXQ_OVFL, SO_MEMINFO = 40, 55            # Linux (asm-generic); the socket module names neither
MEMINFO_WORDS, MEMINFO_DROPS = 9, 8         # SK_MEMINFO_VARS, SK_MEMINFO_DROPS (linux/sock_diag.h)
MSG_WAITFORONE = 0x10000
_KINDS = (wire.KIND_ITEM, wire.KIND_BEACON, wire.KIND_PLUCK)
_HEAD = wire.MAGIC + bytes([wire.VERSION])
_MIN_FRAME = wire.HEADER_LEN + 1 + wire.SIG_LEN
_SLOT = 1216                                # bytes read per datagram: more than MAX_DATAGRAM, so oversize shows
_BROKEN = (errno.EBADF, errno.ENOTSOCK, errno.EFAULT, errno.EINVAL)   # a read that fails so always will


class Ticket:
    """A datagram that waits, or whose turn has come."""

    __slots__ = ("data", "digest", "at")

    def __init__(self, data: bytes, digest: Optional[bytes], at: int):
        self.data, self.digest, self.at = data, digest, at      # digest: None for what is no frame of a listed key


class Repeat:
    """A frame whose exact bytes are a no-op until ``until``, and the copies of it that came."""

    __slots__ = ("ident", "until", "copies", "last_ms")

    def __init__(self, ident: tuple, until: int):
        self.ident, self.until = ident, until      # ident: an item's or PLUCK's tuple, a beacon's (key id, epoch)
        self.copies = self.last_ms = 0             # since the event loop last asked, and when the last one came


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
        self.control = ctypes.create_string_buffer(socket.CMSG_SPACE(4))
        self.iov = (self._Iovec * n)()
        raw = bytearray(n * ctypes.sizeof(self._Mmsghdr))
        self.msgs = (self._Mmsghdr * n).from_buffer(raw)
        data = ctypes.addressof((ctypes.c_char * len(self.data)).from_buffer(self.data))
        for i in range(n):
            self.iov[i] = self._Iovec(data + i * _SLOT, _SLOT)
            h = self.msgs[i].hdr
            h.iov, h.iovlen = ctypes.pointer(self.iov[i]), 1
        # Only the first datagram of a call carries the drop count: it is cumulative, and one a call is enough.
        self.msgs[0].hdr.control = ctypes.addressof(self.control)
        self.offsets = [i * _SLOT for i in range(n)]
        self.view = memoryview(self.data)
        # msg_len as an array: no ctypes access per datagram.
        self.lens = memoryview(raw).cast("I")[self._Mmsghdr.len.offset // 4::ctypes.sizeof(self._Mmsghdr) // 4]

    def read(self) -> tuple:
        """([datagram], the socket's drop count or None). Waits for the first datagram only, at most READ_TIMEOUT_S;
        ([], None) when there was none."""
        self.msgs[0].hdr.controllen = len(self.control)
        n = self.call(self.fd, ctypes.addressof(self.msgs), READ_BATCH, MSG_WAITFORONE, None)
        if n < 0:
            e = ctypes.get_errno()
            if e in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR):
                return [], None
            raise OSError(e, os.strerror(e))
        view = self.view
        out = [view[o:o + size].tobytes() for o, size in zip(self.offsets, self.lens[:n].tolist())]
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
            data, anc, _, _ = self.sock.recvmsg(_SLOT, socket.CMSG_SPACE(4))
        except (BlockingIOError, InterruptedError):
            return [], None
        drops = next((struct.unpack("@I", v)[0] for level, kind, v in anc
                      if (level, kind) == (socket.SOL_SOCKET, SO_RXQ_OVFL)), None)
        return [data], drops


class Intake:
    """The socket's reader thread and what waits. ``take``, ``settle`` and the rest are the event loop's; the reader
    shares the queue with them under one lock."""

    def __init__(self, sock: socket.socket, manifest, *, now_ms: Callable[[], int], wake: Callable[[], None],
                 failed: Callable[[BaseException], None] = lambda e: None, rcvbuf: int = RCVBUF):
        self.sock, self.now_ms, self.wake, self.failed = sock, now_ms, wake, failed
        self.keys = frozenset(e.key_id for e in manifest if not e.revoked)
        self.repeats: dict = {}                    # digest -> Repeat (recorded by ``remember`` only)
        self._due: list = []                       # heap of (until, digest) over the items and PLUCKs in it
        self._beacons = {kid: deque() for kid in self.keys}
        self._touched: deque = deque()             # Repeats with copies the event loop has not been told of
        self._queue: deque = deque()               # Tickets, in arrival order
        self._digests: set = set()                 # of those that have one
        self._lock = threading.Lock()
        self._stop = False
        self.read = self.repeated = self.copied = self.verified = self.unverified = 0
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
        failures = 0
        try:
            while not self._stop:
                try:
                    batch, drops = self._reader.read()
                except OSError as e:
                    if e.errno in (errno.ENOSYS, errno.EPERM) and isinstance(self._reader, _Mmsg):
                        self._reader = _Msg(self.sock)    # a sandbox without recvmmsg
                        continue
                    failures += 1
                    if e.errno in _BROKEN or failures > PAUSES:
                        raise
                    time.sleep(PAUSE_S)
                    continue
                failures = 0
                if drops is not None:
                    self._note_drops(drops)
                if batch and not self._stop:
                    self.offer(batch)
        except BaseException as e:
            if not self._stop:
                self.failed(e)

    def offer(self, batch: list) -> None:
        """Place each datagram: a repeat, or a copy of what waits, is counted; the rest wait, or are refused."""
        now_ms = self.now_ms()
        keys, repeats = self.keys, self.repeats
        claims: list = []
        copies: dict = {}
        for data in batch:
            digest = None
            if (data[4:12] in keys and data[:3] == _HEAD and _MIN_FRAME <= len(data) <= wire.MAX_FRAME
                    and data[3] in _KINDS):
                digest = sha256(data).digest()
                rep = repeats.get(digest)
                if rep is not None and rep.until > now_ms:
                    copies[rep] = copies.get(rep, 0) + 1
                    continue
            claims.append(Ticket(data, digest, now_ms))
        with self._lock:
            self.read += len(batch)
            self.last_datagram_at = now_ms
            for rep, n in copies.items():
                self._copy(rep, now_ms, n)
            idle = not self._queue
            for t in claims:
                if t.digest in self._digests:
                    self.copied += 1
                elif len(self._queue) >= DEPTH:
                    self.refused["backlog"] += 1
                else:
                    self._queue.append(t)
                    if t.digest is not None:
                        self._digests.add(t.digest)
            wake = idle and bool(self._queue)
        if wake:
            self.wake()

    def _copy(self, rep: Repeat, now_ms: int, n: int = 1) -> None:
        self.repeated += n
        if not rep.copies:
            self._touched.append(rep)
        rep.copies += n
        rep.last_ms = now_ms

    # ------------------------------------------------------------ the event loop

    def take(self, limit: int) -> list:
        """Up to ``limit`` tickets, in arrival order. A copy of a frame accepted since it was queued is a repeat. At most
        TURN times as many places are looked at, so a turn never holds the lock for long."""
        out: list = []
        now_ms = self.now_ms()
        with self._lock:
            for _ in range(min(limit * TURN, len(self._queue))):
                if len(out) == limit:
                    break
                t = self._queue.popleft()
                self._digests.discard(t.digest)
                rep = self.repeats.get(t.digest)
                if rep is not None and rep.until > now_ms:
                    self._copy(rep, now_ms)
                else:
                    out.append(t)
        return out

    def waiting(self) -> bool:
        return bool(self._queue)

    def settle(self, verified: bool) -> None:
        """The verdict on a ticket."""
        if verified:
            self.verified += 1
        else:
            self.unverified += 1

    def remember(self, t: Ticket, ident: tuple, until: int) -> None:
        """From now until ``until``, a copy of this verified, accepted and durably saved frame is a repeat. There is
        one entry per live dedup entry (``until`` is inside its retention), so the listener's per-key quotas bound
        them and no key can push out another's, plus the latest BEACON_REPEATS beacons of each key."""
        self.repeats[t.digest] = Repeat(ident, until)
        if t.data[3] == wire.KIND_BEACON:
            kept = self._beacons[t.data[4:12]]
            kept.append(t.digest)
            if len(kept) > BEACON_REPEATS:
                self.repeats.pop(kept.popleft(), None)
        else:
            heapq.heappush(self._due, (until, t.digest))

    def forget(self, now_ms: int) -> None:
        while self._due and self._due[0][0] <= now_ms:
            self.repeats.pop(heapq.heappop(self._due)[1], None)

    def heard_again(self) -> list:
        """[(ident as remembered, repeats since the last call, when the last one came)]"""
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
        """What became of every datagram read: ``read`` is the sum of the rest (the event loop asks between turns)."""
        with self._lock:
            return {"read": self.read, "repeats": self.repeated, "copies": self.copied, "verified": self.verified,
                    "unverified": self.unverified, "queued": len(self._queue), "refused": dict(self.refused)}
