"""The standalone host daemon (RFC-0001 §4.2, §11.1, §14.18.2; amendment BC-1a, D35).

One process per host owns the UDP listener and carries receptor record v1
(``records.py``) to every harness binding on the host over a unix ``SOCK_STREAM``
socket:

- the socket lives in a directory of mode 0700 and has mode 0600; every accepted
  connection's ``SO_PEERCRED`` uid must be an allowed one (default: the daemon's own);
- each connection opens with the run's ``hello`` and latest ``landing_state``, byte for
  byte as first emitted, then carries the live stream. Taking the two and attaching the
  connection happen in one step of the event loop, so no record falls between them;
- connections are accepted only after the run's first ``landing_state``;
- per-connection isolation: a bounded queue each (1 024 records). A ``frame``,
  ``presence`` or ``health`` record that does not fit is dropped for that connection
  only, and counted; its ``rec_seq`` is not reused. A ``retract``, ``landing_state``,
  ``hello``, ``fatal`` or ``bye`` that does not fit, or is not accepted by the kernel
  within 2 s, closes that connection only. At most 16 connections; more are refused at
  accept. The receive path never waits on a connection;
- a clean stop emits ``bye``; a failure to start emits ``fatal`` (on stderr: no
  connection exists yet) and exits non-zero;
- write-ahead: a datagram's or tick's records go out only after the safety state they
  imply is saved. A failed save sends none of them and ends the run with ``fatal``
  (``state_not_durable``) and exit 1; the binding's supervision restarts it (§14.18.2).

The daemon binds its UDP port without ``SO_REUSEADDR``, so no other socket can share it
(proof case 1, §14.18.2), and holds a lease on its state directory, so a second daemon
on the same state refuses to start. Publishing (sing/hush over this socket, §15) is not
implemented: bytes a peer sends are read, counted and discarded.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import socket
import stat
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import runner
from .listener import Listener
from .manifest import Manifest
from .records import DROPPABLE, HEALTH_INTERVAL_MS, Emitter, Receptor, StateNotDurable

QUEUE_MAX = 1024          # records per connection (§14.18.2 [PROPOSED DEFAULT])
MAX_PEERS = 16            # connections (§14.18.2 [PROPOSED DEFAULT])
WRITE_BOUND_S = 2.0       # a non-droppable record unwritten this long closes its connection
WATCH_S = 0.05            # how often the write bound is checked
TICK_MS = 250
SHUTDOWN_FLUSH_S = 2.0    # how long a clean stop waits for `bye` to reach each connection
LOG_TYPES = ("hello", "fatal", "bye")   # records copied to stderr (no item text in any of them)


def default_socket_path() -> Optional[str]:
    base = os.environ.get("XDG_RUNTIME_DIR")
    return os.path.join(base, "canticle", "daemon.sock") if base else None


def default_state_dir() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "canticle", "daemon")


@dataclass
class DaemonConfig:
    manifest: str
    bind: str
    socket_path: str
    state_dir: str
    multicast: bool = False
    allowed_uids: frozenset = field(default_factory=lambda: frozenset({os.getuid()}))
    max_peers: int = MAX_PEERS
    queue_max: int = QUEUE_MAX
    write_bound_s: float = WRITE_BOUND_S
    health_interval_ms: Optional[int] = HEALTH_INTERVAL_MS   # None: no periodic health (tests)
    tick_ms: Optional[int] = TICK_MS                         # None: no periodic tick (tests)
    log: Callable[[str], None] = field(default=lambda s: print(s, file=sys.stderr, flush=True))


class StartError(Exception):
    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


class Peer:
    """One connection: a bounded queue of encoded lines and one writer task."""

    def __init__(self, daemon: "Daemon", writer: asyncio.StreamWriter, bootstrap: list):
        self.daemon, self.writer = daemon, writer
        self.queue: deque = deque()      # (droppable, line)
        self.unwritten: deque = deque()  # monotonic enqueue times of non-droppable lines not yet written
        self.wake = asyncio.Event()
        self.dropped = 0
        self.inbound_bytes = 0
        self.closed = False
        self.tasks: list = []
        for type_, line in bootstrap:
            self.offer(type_, line)

    def offer(self, type_: str, line: bytes) -> bool:
        """Queue a line; False when a non-droppable one does not fit (the caller closes this peer)."""
        droppable = type_ in DROPPABLE
        if len(self.queue) >= self.daemon.cfg.queue_max:
            if droppable:
                self.dropped += 1
                return True
            return False
        self.queue.append((droppable, line))
        if not droppable:
            self.unwritten.append(time.monotonic())
        self.wake.set()
        return True

    def overdue(self, now: float) -> bool:
        return bool(self.unwritten) and now - self.unwritten[0] > self.daemon.cfg.write_bound_s

    async def write_loop(self) -> None:
        try:
            while True:
                while not self.queue:
                    self.wake.clear()
                    await self.wake.wait()
                droppable, line = self.queue.popleft()
                self.writer.write(line)
                await self.writer.drain()   # returns once the kernel holds the line (write buffer limit 0)
                if not droppable:
                    self.unwritten.popleft()
        except (ConnectionError, OSError):
            self.daemon.close_peer(self, "write_error")

    async def read_loop(self, reader: asyncio.StreamReader) -> None:
        """Requests are not served in this slice (§15 is out of scope): read, count and discard."""
        try:
            while data := await reader.read(65536):
                self.inbound_bytes += len(data)
        except (ConnectionError, OSError):
            pass
        self.daemon.close_peer(self, "eof")


class Daemon:
    def __init__(self, cfg: DaemonConfig):
        self.cfg = cfg
        self.peers: set = set()
        self.hello: Optional[bytes] = None
        self.landing: Optional[bytes] = None
        self.ready = False
        self.counts = {"accepted": 0, "refused_uid": 0, "refused_full": 0, "refused_not_ready": 0,
                       "closed_stalled": 0, "closed_queue_full": 0, "closed_eof": 0, "closed_write_error": 0,
                       "dropped": 0, "receive_errors": 0}
        self.emitter = Emitter(self.publish)
        self.receptor: Optional[Receptor] = None
        self.udp: Optional[socket.socket] = None
        self.server: Optional[asyncio.base_events.Server] = None
        self._lease = None
        self._stop: Optional[asyncio.Event] = None
        self.failed: Optional[tuple] = None   # (reason, detail) once the run must end with `fatal`

    # ------------------------------------------------------------ fan-out (never blocks)

    def publish(self, type_: str, line: bytes) -> None:
        if type_ == "hello":
            self.hello = line
        elif type_ == "landing_state":
            self.landing = line
            self.ready = True
        if type_ in LOG_TYPES:
            self.cfg.log(line.decode().rstrip("\n"))
        for peer in list(self.peers):
            before = peer.dropped
            if not peer.offer(type_, line):
                self.close_peer(peer, "queue_full")
            elif peer.dropped != before:
                self.counts["dropped"] += 1
                if self.receptor is not None:
                    self.receptor.records_dropped += 1

    def close_peer(self, peer: Peer, why: str) -> None:
        if peer.closed:
            return
        peer.closed = True
        self.peers.discard(peer)
        self.counts[f"closed_{why}"] += 1
        if why in ("stalled", "queue_full") and self.receptor is not None:
            self.receptor.peers_closed += 1
        peer.writer.transport.abort()
        current = asyncio.current_task()
        for t in peer.tasks:
            if t is not current:
                t.cancel()

    # ------------------------------------------------------------ accept (§11.1)

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            uid = runner._peer_uid(writer)
        except OSError:
            uid = None
        if uid is None or uid not in self.cfg.allowed_uids:
            self.counts["refused_uid"] += 1
            writer.transport.abort()
            return
        if not self.ready or self.hello is None or self.landing is None:
            self.counts["refused_not_ready"] += 1
            writer.transport.abort()
            return
        if len(self.peers) >= self.cfg.max_peers:
            self.counts["refused_full"] += 1
            writer.transport.abort()
            return
        # One step, no await: the bootstrap is the latest hello and landing_state, and the peer joins the
        # fan-out before any other record can be emitted (§11.1, §14.18.3 "Joining a run").
        writer.transport.set_write_buffer_limits(high=0)
        peer = Peer(self, writer, [("hello", self.hello), ("landing_state", self.landing)])
        self.peers.add(peer)
        self.counts["accepted"] += 1
        peer.tasks = [asyncio.create_task(peer.write_loop()), asyncio.create_task(peer.read_loop(reader))]

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(WATCH_S)
            now = time.monotonic()
            for peer in [p for p in self.peers if p.overdue(now)]:
                self.close_peer(peer, "stalled")

    # ------------------------------------------------------------ start

    def _take_lease(self) -> None:
        os.makedirs(self.cfg.state_dir, mode=0o700, exist_ok=True)
        lease = open(os.path.join(self.cfg.state_dir, "daemon.lease"), "a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise StartError("state_locked", f"another daemon holds {self.cfg.state_dir}") from None
        self._lease = lease

    def _load(self) -> Receptor:
        try:
            with open(self.cfg.manifest, "rb") as fh:
                raw = fh.read()
            manifest = Manifest.from_json(json.loads(raw))
            label = json.loads(raw).get("manifest", "")
        except Exception as e:
            raise StartError("manifest_invalid", f"{self.cfg.manifest}: {type(e).__name__}: {e}") from None
        try:
            lst = Listener(manifest, state_path=os.path.join(self.cfg.state_dir, "listener.json"),
                           receptor_mode=True, binding="lan")
            group = runner.MCAST_GROUP if self.cfg.multicast else None
            return Receptor(lst, self.emitter, bind=self.cfg.bind, multicast=group, transport="lan",
                            manifest_sha256=hashlib.sha256(raw).hexdigest(), manifest_label=str(label),
                            now_ms=runner.now_ms())
        except Exception as e:
            raise StartError("state_corrupt", f"{self.cfg.state_dir}: {type(e).__name__}: {e}") from None

    def _bind_udp(self) -> socket.socket:
        host, port = runner.parse_addr(self.cfg.bind)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No SO_REUSEADDR or SO_REUSEPORT: the port is this process's alone (§4.2, §14.18.2 case 1).
            sock.bind((host, port))
            if self.cfg.multicast:
                mreq = socket.inet_aton(runner.MCAST_GROUP) + socket.inet_aton("0.0.0.0")
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            sock.close()
            raise StartError("bind_failed", f"{self.cfg.bind}: {e.strerror or e}") from None
        sock.setblocking(False)
        return sock

    def _prepare_socket_path(self) -> None:
        path = self.cfg.socket_path
        d = os.path.dirname(os.path.abspath(path))
        try:
            if not os.path.isdir(d):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                os.mkdir(d, 0o700)
            st = os.lstat(d)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise StartError("socket_failed", f"{d} must be a directory owned by uid {os.getuid()} "
                                 f"with mode 0700 (it is {stat.filemode(st.st_mode)})")
            if os.path.lexists(path):
                if not stat.S_ISSOCK(os.lstat(path).st_mode):
                    raise StartError("socket_failed", f"{path} exists and is not a socket")
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.connect(path)
                    raise StartError("socket_failed", f"{path}: another daemon answers there")
                except (ConnectionRefusedError, FileNotFoundError):
                    os.unlink(path)  # left by a daemon that is gone
                finally:
                    probe.close()
        except OSError as e:
            raise StartError("socket_failed", f"{path}: {e.strerror or e}") from None

    async def _serve_socket(self) -> None:
        self._prepare_socket_path()
        old = os.umask(0o177)
        try:
            self.server = await asyncio.start_unix_server(self._accept, path=self.cfg.socket_path)
        except OSError as e:
            raise StartError("socket_failed", f"{self.cfg.socket_path}: {e.strerror or e}") from None
        finally:
            os.umask(old)
        os.chmod(self.cfg.socket_path, 0o600)

    # ------------------------------------------------------------ run

    async def run(self, stop: asyncio.Event, started: Optional[Callable[["Daemon"], None]] = None) -> int:
        """Run until ``stop`` is set. Returns 0 after a clean stop (`bye`), 1 after `fatal`."""
        loop = asyncio.get_running_loop()
        tasks: list = []
        try:
            self._take_lease()
            self.receptor = self._load()
            self.udp = self._bind_udp()
            self.receptor.bind = "%s:%d" % self.udp.getsockname()[:2]   # the port actually bound (port 0 in tests)
            try:
                self.receptor.start(runner.now_ms())   # hello, then the first landing_state, after the save
            except StateNotDurable as e:
                raise StartError("state_not_durable", str(e)) from None
            await self._serve_socket()
        except StartError as e:
            self.emitter.emit("fatal", reason=e.reason, detail=e.detail[:200])
            self._cleanup_files()
            return 1

        daemon = self

        class Proto(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                daemon._call(daemon.receptor.hear, data, runner.now_ms())

        transport, _ = await loop.create_datagram_endpoint(Proto, sock=self.udp)
        tasks.append(asyncio.create_task(self._watch()))
        if self.cfg.tick_ms:
            tasks.append(asyncio.create_task(self._every(self.cfg.tick_ms, self.receptor.tick)))
        if self.cfg.health_interval_ms:
            tasks.append(asyncio.create_task(self._every(self.cfg.health_interval_ms, self.receptor.health)))
        self._stop = stop
        if started is not None:
            started(self)
        try:
            await stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            transport.close()
            self.server.close()
            if self.failed is None:
                try:
                    self.receptor.bye()
                except StateNotDurable as e:
                    self._fail("state_not_durable", str(e))
            await self._flush_peers()
            self._cleanup_files()
        return 1 if self.failed else 0

    def _call(self, fn, *args) -> None:
        """Run a receptor step. A failed save (or any error in the record path) ends the run with `fatal`:
        the state that guards against stale or withdrawn items is not durable, and records implied by it
        were not sent (write-ahead, #79 review). The binding's supervision restarts the daemon (§14.18.2)."""
        if self.failed is not None:
            return
        try:
            fn(*args)
        except StateNotDurable as e:
            self._fail("state_not_durable", str(e))
        except Exception as e:
            self._fail("internal", type(e).__name__)

    def _fail(self, reason: str, detail: str) -> None:
        if self.failed is not None:
            return
        self.failed = (reason, detail)
        self.counts["receive_errors"] += 1
        self.emitter.discard()
        self.emitter.emit("fatal", reason=reason, detail=detail[:200])
        if self._stop is not None:
            self._stop.set()

    async def _every(self, period_ms: int, fn) -> None:
        while True:
            await asyncio.sleep(period_ms / 1000)
            self._call(fn, runner.now_ms())

    async def _flush_peers(self) -> None:
        deadline = time.monotonic() + SHUTDOWN_FLUSH_S
        while any(p.queue or p.unwritten for p in self.peers) and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        for peer in list(self.peers):
            peer.closed = True
            for t in peer.tasks:
                t.cancel()
            if peer.queue or peer.unwritten:
                peer.writer.transport.abort()   # it never took `bye`: it sees an exit without bye
            else:
                peer.writer.close()
        self.peers.clear()

    def _cleanup_files(self) -> None:
        if self.server is not None and os.path.lexists(self.cfg.socket_path):
            try:
                os.unlink(self.cfg.socket_path)
            except OSError:
                pass
        if self.udp is not None:
            self.udp.close()
        if self._lease is not None:
            self._lease.close()
            self._lease = None
