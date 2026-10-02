"""The host daemon (RFC-0001 §11.1, §14.18.2, D35): the local mixed-host proof cases 1, 2, 3, 5 and 7.

Everything runs in one event loop on loopback: UDP on an ephemeral 127.0.0.1 port, the unix socket in a
temporary directory. No multicast, no fixed port, nothing under ~/.binary-canticle.
"""

import asyncio
import errno
import json
import os
import random
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import runner, wire
from canticle.daemon import Daemon, DaemonConfig
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.records import MAX_LINE
from canticle.station import Station, StreamConfig

ROOT = Path(__file__).resolve().parents[1]
SK = Ed25519PrivateKey.generate()


class Client:
    """A binding's socket: reads lines into ``lines`` until end of stream."""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.lines: list = []
        self.eof = False
        self.task = asyncio.create_task(self._read())

    async def _read(self):
        try:
            while line := await self.reader.readline():
                self.lines.append(line)
        except (ConnectionError, OSError):
            pass
        self.eof = True

    @property
    def recs(self):
        return [json.loads(x) for x in self.lines]

    def seqs(self):
        return [r["rec_seq"] for r in self.recs]

    def close(self):
        self.writer.close()
        self.task.cancel()


async def until(pred, timeout=5.0, what="condition"):
    deadline = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        await asyncio.sleep(0.005)


class DaemonCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3}), ("chatter", "lens.threat"))])
        self.manifest = os.path.join(self.dir, "fleet.json")
        Path(self.manifest).write_text(json.dumps(m.to_json()))
        self.logs: list = []
        self.clients: list = []

    def cfg(self, name="d", **kw):
        base = dict(manifest=self.manifest, bind="127.0.0.1:0", socket_path=os.path.join(self.dir, name, "run", "daemon.sock"),
                    state_dir=os.path.join(self.dir, name, "state"), health_interval_ms=None, tick_ms=None,
                    log=self.logs.append)
        base.update(kw)
        return DaemonConfig(**base)

    def fatal(self) -> str:
        return [x for x in self.logs if '"type":"fatal"' in x][-1]

    def run_with(self, scenario, **kw):
        """Start a daemon, run ``scenario(daemon, port)``, stop it; returns (scenario result, exit code)."""
        async def main():
            stop = asyncio.Event()
            ready = asyncio.Event()
            d = Daemon(self.cfg(**kw))
            task = asyncio.create_task(d.run(stop, started=lambda _: ready.set()))
            done, _ = await asyncio.wait({task, asyncio.create_task(ready.wait())}, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                return None, task.result()
            try:
                result = await scenario(d, d.udp.getsockname()[1])
            finally:
                stop.set()
                code = await task
                await asyncio.sleep(0.2)   # let clients read the bye and the end of stream
                for c in self.clients:
                    c.close()
                await asyncio.sleep(0)
            return result, code
        return asyncio.run(main())

    async def connect(self, d):
        c = Client(*await asyncio.open_unix_connection(d.cfg.socket_path))
        self.clients.append(c)
        return c

    def station(self):
        return Station(SK, [StreamConfig("chatter"), StreamConfig("lens.threat", cls="live-state")], epoch=1,
                       rng=random.Random(3), now_ms=runner.now_ms())


class SocketTest(DaemonCase):
    def test_modes_bootstrap_and_clean_stop(self):
        async def scenario(d, port):
            sock = d.cfg.socket_path
            self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(sock)).st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(os.stat(sock).st_mode), 0o600)
            self.assertTrue(stat.S_ISSOCK(os.stat(sock).st_mode))
            c = await self.connect(d)
            await until(lambda: len(c.lines) == 2)
            hello, landing = c.recs
            self.assertEqual((hello["type"], hello["rec_seq"], landing["type"], landing["rec_seq"]),
                             ("hello", 1, "landing_state", 2))
            self.assertEqual(hello["bind"], f"127.0.0.1:{port}")
            c.writer.write(b'{"op":"sing","stream":"chatter","text":"x"}\n')   # publishing is not served here
            await c.writer.drain()
            await until(lambda: sum(p.inbound_bytes for p in d.peers) > 0)
            return c
        c, code = self.run_with(scenario)
        self.assertEqual(code, 0)
        self.assertTrue(c.eof)
        self.assertEqual([r["type"] for r in c.recs], ["hello", "landing_state", "bye"])
        self.assertFalse(os.path.exists(self.cfg().socket_path))
        self.assertTrue(any('"type":"bye"' in x for x in self.logs))

    def test_peer_uid_not_allowed_is_refused(self):
        async def scenario(d, port):
            c = await self.connect(d)
            await until(lambda: c.eof)
            return c.lines, d.counts["refused_uid"]
        (lines, refused), _ = self.run_with(scenario, allowed_uids=frozenset({os.getuid() + 1}))
        self.assertEqual((lines, refused), ([], 1))

    def test_peers_beyond_the_bound_are_refused_at_accept(self):
        async def scenario(d, port):
            cs = [await self.connect(d) for _ in range(4)]
            await until(lambda: all(len(c.lines) == 2 for c in cs[:3]) and cs[3].eof)
            return [len(c.lines) for c in cs], d.counts["refused_full"]
        (sizes, refused), _ = self.run_with(scenario, max_peers=3)
        self.assertEqual((sizes, refused), ([2, 2, 2, 0], 1))

    def test_a_live_socket_is_not_taken_over_and_a_loose_directory_is_refused(self):
        async def scenario(d, port):
            other = Daemon(self.cfg(name="e", socket_path=d.cfg.socket_path))
            return await other.run(asyncio.Event())
        code, _ = self.run_with(scenario)
        self.assertEqual(code, 1)
        self.assertIn('"reason":"socket_failed"', self.fatal())
        loose = os.path.join(self.dir, "loose")
        os.mkdir(loose, 0o755)
        os.chmod(loose, 0o755)
        _, code = self.run_with(lambda d, p: None, name="f", socket_path=os.path.join(loose, "daemon.sock"))
        self.assertEqual(code, 1)
        self.assertIn("mode 0700", self.fatal())


class ProofCase1Test(DaemonCase):
    """(1) Exactly one process, the daemon, has the canticle port bound."""

    def test_second_daemon_on_one_state_dir_refuses(self):
        async def scenario(d, port):
            return await Daemon(self.cfg(socket_path=os.path.join(self.dir, "x", "daemon.sock"))).run(asyncio.Event())
        code, _ = self.run_with(scenario)
        self.assertEqual(code, 1)
        self.assertIn('"reason":"state_locked"', self.fatal())

    def test_the_port_is_exclusive(self):
        async def scenario(d, port):
            # another daemon (its own state) and an embedded listener (SO_REUSEADDR) both fail to bind
            code = await Daemon(self.cfg(name="e", bind=f"127.0.0.1:{port}")).run(asyncio.Event())
            fatal = self.fatal()
            lst = Listener(Manifest(), ephemeral=True)
            with self.assertRaises(OSError) as cm:
                await runner.run_listener(lst, ("127.0.0.1", port), lambda ev: None)
            env = {**os.environ, "PYTHONPATH": str(ROOT), "XDG_STATE_HOME": os.path.join(self.dir, "xdg")}
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "canticle", "listen", "--manifest", self.manifest, "--bind",
                f"127.0.0.1:{port}", "--ephemeral", env=env, stderr=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL)
            _, err = await asyncio.wait_for(proc.communicate(), 30)
            return code, fatal, cm.exception.errno, proc.returncode, err.decode()
        (code, fatal, err_no, listen_code, listen_err), _ = self.run_with(scenario)
        self.assertEqual(code, 1)
        self.assertIn('"reason":"bind_failed"', fatal)
        self.assertEqual(err_no, errno.EADDRINUSE)
        self.assertEqual(listen_code, 1)
        self.assertIn("address in use; refusing to listen", listen_err)


class ProofCase2And3Test(DaemonCase):
    def _carousel(self, st, port, sock, seconds):
        async def go():
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                for f in st.poll(runner.now_ms()):
                    sock.sendto(f, ("127.0.0.1", port))
                await asyncio.sleep(0.02)
        return go()

    def test_two_bindings_see_one_stream(self):
        """(2) Every binding receives the same rec_seq stream for a test station's carousel."""
        async def scenario(d, port):
            a, b = await self.connect(d), await self.connect(d)
            await until(lambda: len(a.lines) == 2 and len(b.lines) == 2)
            st = self.station()
            st.sing(runner.now_ms(), "chatter", text="one", ttl_s=30)
            st.sing(runner.now_ms(), "lens.threat", text="two", state_key="k", ttl_s=30)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                await self._carousel(st, port, s, 1.2)
                d.receptor.health(runner.now_ms())
                n = d.emitter.rec_seq
                await until(lambda: a.seqs()[-1:] == [n] and b.seqs()[-1:] == [n])
            return a.lines, b.lines
        (la, lb), _ = self.run_with(scenario)
        self.assertEqual(la, lb)                               # byte for byte, bootstrap included
        recs = [json.loads(x) for x in la]
        self.assertEqual([r["rec_seq"] for r in recs], list(range(1, len(recs) + 1)))
        frames = [r for r in recs if r["type"] == "frame"]
        self.assertEqual(sorted((f["stream"], f["disposition"]) for f in frames),
                         [("chatter", "surface"), ("lens.threat", "ringbuffer_only")])   # live-state: warm-up hold

    def test_a_binding_leaving_and_rejoining_changes_nothing_for_the_other(self):
        """(3) Stopping or restarting one binding changes neither the other's stream nor the daemon."""
        async def scenario(d, port):
            emitted = []
            sink = d.emitter.sink
            d.emitter.sink = lambda t, line: (emitted.append(line), sink(t, line))
            a, b = await self.connect(d), await self.connect(d)
            await until(lambda: len(a.lines) == 2 and len(b.lines) == 2)
            st = self.station()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                for i in range(6):
                    st.sing(runner.now_ms(), "chatter", text=f"n{i}", ttl_s=30)
                    if i == 2:
                        a.close()                       # the binding stops
                        await until(lambda: len(d.peers) == 1)
                    if i == 4:
                        a = await self.connect(d)       # and comes back
                        await until(lambda: len(a.lines) >= 2)
                    await self._carousel(st, port, s, 0.15)
                n = d.emitter.rec_seq
                await until(lambda: b.seqs()[-1:] == [n] and a.seqs()[-1:] == [n])
            return a, b, emitted, d.counts
        (a, b, emitted, counts), code = self.run_with(scenario)
        self.assertEqual(code, 0)
        self.assertEqual(b.lines[2:], emitted)                 # nothing lost, nothing extra
        self.assertEqual(b.seqs(), [1, 2] + list(range(3, 3 + len(emitted))))
        ra = a.recs
        self.assertEqual([r["type"] for r in ra[:2]], ["hello", "landing_state"])
        self.assertEqual(a.lines[:2], b.lines[:2])            # the rejoin's bootstrap: the same two records
        self.assertEqual(a.lines[2:], b.lines[-(len(a.lines) - 2):])
        self.assertEqual((counts["accepted"], counts["closed_eof"]), (3, 1))


class ProofCase5Test(DaemonCase):
    def test_late_join_with_noncontiguous_seqs(self):
        """(5) hello 1, latest landing_state 50, B connects at 99; both see the same records from 100."""
        async def scenario(d, port):
            r = d.receptor
            pad = lambda n: [r.health(runner.now_ms()) for _ in range(n - d.emitter.rec_seq)]
            a = await self.connect(d)
            await until(lambda: len(a.lines) == 2)
            pad(49)
            r.set_landing(breaker="half_open", until=runner.now_ms() + 60_000)
            self.assertEqual(d.emitter.rec_seq, 50)
            pad(99)
            b = await self.connect(d)
            await until(lambda: len(d.peers) == 2)   # attached: the next record is B's first live one
            st = self.station()
            st.sing(runner.now_ms(), "chatter", text="after the join", ttl_s=30)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                for f in st.poll(runner.now_ms()):
                    if f[3] == wire.KIND_ITEM:   # the item alone: exactly one record (no beacon, no presence)
                        s.sendto(f, ("127.0.0.1", port))
            await until(lambda: d.emitter.rec_seq >= 100)
            pad(103)
            await until(lambda: b.seqs()[-1:] == [103] and a.seqs()[-1:] == [103])
            return a, b
        (a, b), _ = self.run_with(scenario)
        self.assertEqual([r["type"] for r in (a.recs[-1], b.recs[-1])], ["bye", "bye"])   # the clean stop, 104
        self.assertEqual(b.seqs(), [1, 50, 100, 101, 102, 103, 104])
        self.assertEqual(a.seqs(), list(range(1, 105)))
        by_seq = dict(zip(a.seqs(), a.lines))
        self.assertEqual(b.lines, [by_seq[s] for s in b.seqs()])   # byte for byte, original rec_seq
        self.assertEqual(b.recs[2]["type"], "frame")
        self.assertEqual(b.recs[1]["breaker"], "half_open")


class ProofCase7Test(DaemonCase):
    """(7) A stalled binding: the healthy one gets frame, retract and landing_state in order and on time."""

    def _stall(self, d):
        """A peer that never reads: connect a raw socket and leave it."""
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        s.connect(d.cfg.socket_path)
        s.setblocking(False)
        return s

    async def _pump(self, d, healthy, n, stalled_peer=None, watermarks=None):
        for _ in range(n // 50):
            for _ in range(50):
                d.receptor.health(runner.now_ms())
            if stalled_peer is not None and watermarks is not None:
                watermarks.append((len(stalled_peer.queue), stalled_peer.writer.transport.get_write_buffer_size()))
            target = d.emitter.rec_seq
            await until(lambda: healthy.seqs()[-1:] == [target], what="healthy peer keeping up")

    def _scenario(self, overflow: bool):
        async def scenario(d, port):
            stalled = self._stall(d)
            await until(lambda: len(d.peers) == 1)
            a = next(iter(d.peers))
            b = await self.connect(d)
            await until(lambda: len(b.lines) == 2)
            marks: list = []
            # Fill A: its kernel buffer, then its queue (to the brim when overflow, else part way).
            await self._pump(d, b, 2_000 if overflow else 300, a, marks)
            if overflow:
                self.assertEqual(len(a.queue), d.cfg.queue_max)
                self.assertGreater(a.dropped, 0)
            else:
                self.assertLess(len(a.queue), d.cfg.queue_max)
                self.assertGreater(len(a.queue), 0)
            st = self.station()
            t_send = time.monotonic()
            res = st.sing(runner.now_ms(), "chatter", text="still heard", ttl_s=30)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                for f in st.poll(runner.now_ms()):
                    s.sendto(f, ("127.0.0.1", port))
                await until(lambda: any(r["type"] == "frame" for r in b.recs[-3:]))
                st.hush(runner.now_ms(), "chatter", res.seq)
                for f in st.poll(runner.now_ms()):
                    s.sendto(f, ("127.0.0.1", port))
                await until(lambda: any(r["type"] == "retract" for r in b.recs[-3:]))
            d.receptor.set_landing(breaker="open", until=runner.now_ms() + 60_000)
            await until(lambda: b.recs[-1]["type"] == "landing_state")
            on_time = time.monotonic() - t_send
            t_closed = None
            if not overflow:
                await until(lambda: a.closed, timeout=d.cfg.write_bound_s + 1.5, what="stalled peer closed")
            t_closed = time.monotonic() - t_send
            n = d.emitter.rec_seq
            # the daemon still receives datagrams after the close
            st.sing(runner.now_ms(), "chatter", text="after", ttl_s=30)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                for f in st.poll(runner.now_ms()):
                    s.sendto(f, ("127.0.0.1", port))
            await until(lambda: d.emitter.rec_seq > n and b.seqs()[-1] == d.emitter.rec_seq)
            stalled.close()
            return a, b, marks, on_time, t_closed, dict(d.counts)
        return scenario

    def _check(self, a, b, marks, counts, d_queue_max=1024):
        self.assertTrue(a.closed)
        self.assertEqual(b.seqs(), list(range(1, len(b.lines) + 1)))   # B: no gap at all
        tail = [r["type"] for r in b.recs if r["type"] in ("frame", "retract", "landing_state")]
        self.assertEqual(tail[-4:-1], ["frame", "retract", "landing_state"])
        self.assertTrue(all(q <= d_queue_max and buf <= MAX_LINE for q, buf in marks), marks)

    def test_stalled_peer_closed_when_a_non_droppable_record_does_not_fit(self):
        (a, b, marks, on_time, t_closed, counts), code = self.run_with(self._scenario(overflow=True))
        self.assertEqual(code, 0)
        self._check(a, b, marks, counts)
        self.assertEqual(counts["closed_queue_full"], 1)
        self.assertGreater(counts["dropped"], 0)
        self.assertLess(on_time, 1.0)

    def test_stalled_peer_closed_when_a_non_droppable_record_waits_past_the_bound(self):
        (a, b, marks, on_time, t_closed, counts), code = self.run_with(self._scenario(overflow=False))
        self.assertEqual(code, 0)
        self._check(a, b, marks, counts)
        self.assertEqual((counts["closed_stalled"], counts["closed_queue_full"]), (1, 0))
        self.assertLess(on_time, 1.0)
        self.assertLess(t_closed, 2.0 + 1.0)    # retract queued ~at t_send; bound 2 s plus the watch period


if __name__ == "__main__":
    unittest.main()
