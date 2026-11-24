"""The host daemon's intake (``canticle/intake.py``, #171): what may be skipped before verify, and what is counted.

Two kinds of test. ``IntakeCase`` drives an ``Intake`` with no thread and no socket traffic: ``offer`` places datagrams,
``take`` and ``settle`` are the event loop's half. ``DaemonIntakeTest`` sends real frames to a real in-process daemon
over loopback UDP. The floods are in ``test_intake_floods``.
"""

import errno
import hashlib
import json
import random
import socket
import sys
import threading
import time
import unittest
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import intake, listener, runner, wire
from canticle.ids import stream_id
from canticle.intake import Intake
from canticle.manifest import Manifest, StationEntry
from test_daemon import SK, DaemonCase, until

A, B = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
KID_A, KID_B = (wire.key_id(wire.public_key_bytes(k)) for k in (A, B))


def item(sk=A, seq=1, stream="chatter", epoch=5, body=b"x", now=None, **kw):
    now = runner.now_ms() if now is None else now
    kw = {"scope": 1, "cls": 1, "ctype": 1, "expires_at": now + 60_000, **kw}
    return wire.encode_item(sk, wire.Item(epoch=epoch, stream=stream_id(stream), seq=seq, issued_at=now, body=body, **kw))


def beacon(sk=A, bseq=1, epoch=5):
    return wire.encode_beacon(sk, wire.Beacon(epoch=epoch, bseq=bseq, wallclock=runner.now_ms(), next_beacon_ms=1000,
                                              profile="canticle-regulation/1", streams=(), b_station=16_000))


def forge(frame: bytes, n: int = 0) -> bytes:
    """The same frame with another, invalid signature (canonical S, so it reaches the signature check)."""
    return frame[:-64] + n.to_bytes(32, "big") + frame[-32:]


class IntakeCase(unittest.TestCase):
    def setUp(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.addCleanup(self.sock.close)
        self.woken = 0
        entry = lambda name, sk, streams, **kw: StationEntry(name, wire.public_key_bytes(sk), frozenset({1}), streams, **kw)
        self.manifest = Manifest([entry("a", A, ("chatter", "other")), entry("b", B, ("chatter",))])
        self.intake = self.make()

    def make(self, manifest=None):
        def wake():
            self.woken += 1
        return Intake(self.sock, manifest or self.manifest, now_ms=runner.now_ms, wake=wake)

    def offer(self, *datagrams):
        self.intake.offer(list(datagrams))

    def serve(self, limit=32, verified=lambda t: True):
        """One turn of the event loop, with a given verdict per ticket. Returns the datagrams in the order served."""
        batch = self.intake.take(limit)
        for t in batch:
            self.intake.settle(verified(t))
        return [t.data for t in batch]

    def accept(self, limit=32):
        """One turn in which everything verifies, is accepted and is saved."""
        batch = self.intake.take(limit)
        for t in batch:
            self.intake.remember(t, (t.data[4:12], 5, 0, 1), runner.now_ms() + 60_000)
            self.intake.settle(True)
        return [t.data for t in batch]

    @property
    def refused(self):
        return {k: v for k, v in self.intake.stats()["refused"].items() if v}


class QueueTest(IntakeCase):
    def test_what_waits_is_served_in_the_order_it_came(self):
        frames = [item(A, 1), forge(item(B, 1)), b"not a frame", item(B, 2), b"", item(A, 2, "other"), beacon(B)]
        self.offer(*frames[:3])
        self.offer(*frames[3:])
        self.assertEqual(self.serve(2) + self.serve(), frames)
        self.assertEqual((self.serve(), self.intake.waiting()), ([], False))

    def test_the_loop_is_woken_when_something_waits_and_not_for_every_datagram(self):
        self.offer(*[item(A, n) for n in range(1, 10)])
        self.offer(item(B, 1))
        self.assertEqual(self.woken, 1)
        self.serve()
        self.offer(item(A, 10))
        self.assertEqual(self.woken, 2)
        f = item(A, 11)
        self.offer(f)
        self.accept()
        self.offer(f)                                          # a repeat: nothing waits
        self.assertEqual((self.woken, self.intake.waiting()), (2, False))

    def test_a_full_queue_refuses_what_comes_and_counts_it(self):
        waits = [forge(item(A, 1), n) for n in range(intake.DEPTH)]
        self.offer(*waits)
        self.offer(item(A, 2), b"not a frame", waits[3])       # the last one waits already: a copy, not refused
        self.assertEqual((self.refused, self.intake.copied), ({"backlog": 2}, 1))
        self.assertEqual(self.serve(intake.DEPTH), waits)
        self.offer(item(A, 2))
        self.assertEqual(len(self.serve()), 1)

    def test_what_is_no_frame_of_a_listed_key_waits_undigested_like_the_rest(self):
        """It is judged and counted by reason (D34), as ever, and no digest of it is kept."""
        revoked = Manifest([StationEntry("a", wire.public_key_bytes(A), frozenset({1}), ("chatter",), revoked=True)])
        self.intake = self.make(revoked)
        for d in (item(A, 1), item(B, 1), b"x" * 300, item(A, 1)[:60], bytes(intake._SLOT)):
            self.offer(d, d)
            self.assertEqual([t.digest for t in self.intake.take(9)], [None, None])
        self.assertEqual(self.intake.copied, 0)


class RepeatTest(IntakeCase):
    """🌫's first condition on #171: only the exact bytes of a frame already verified are skipped."""

    def test_an_exact_copy_of_an_accepted_frame_is_counted_and_never_queued(self):
        f = item(A, 1)
        self.offer(f)
        self.accept()
        self.offer(f, f)
        self.assertEqual((self.intake.stats()["queued"], self.intake.repeated), (0, 2))
        self.assertEqual([(i, n) for i, n, _ in self.intake.heard_again()], [((KID_A, 5, 0, 1), 2)])
        self.assertEqual(self.intake.heard_again(), [])

    def test_a_frame_that_was_not_accepted_skips_nothing(self):
        """Failed, or verified but refused at steps 3-4 (and so perhaps admitted next time): heard again."""
        f = item(A, 1)
        for verdict in (False, True):
            self.offer(f)
            self.assertEqual(self.serve(verified=lambda t: verdict), [f])
        self.offer(f)
        self.assertEqual(self.serve(), [f])

    def test_an_invalid_frame_with_the_same_identity_suppresses_nothing(self):
        """Same key, epoch, stream, seq and body, invalid signature, arriving first and many times over: the valid
        frame behind it is still served, whether the forgeries were verified (and failed) before it or still wait."""
        f = item(A, 1)
        self.offer(*[forge(f, n) for n in range(4)])
        self.assertEqual(len(self.serve(verified=lambda t: t.data == f)), 4)
        self.offer(forge(f, 9))
        self.offer(f)
        self.assertIn(f, self.serve(verified=lambda t: t.data == f))

    def test_one_changed_byte_is_not_a_repeat(self):
        f = item(A, 1)
        self.offer(f)
        self.accept()
        for at in (12, 20, len(f) - 70, len(f) - 64, len(f) - 1):
            self.offer(f[:at] + bytes([f[at] ^ 1]) + f[at + 1:])
        self.assertEqual((self.intake.repeated, self.intake.stats()["queued"]), (0, 5))

    def test_copies_that_wait_together_are_verified_once_and_share_the_verdict(self):
        """Counted as copies: neither a repeat (nothing has verified yet) nor refused (the same bytes wait)."""
        f, bad = item(A, 1), forge(item(A, 1))
        for frame, verified in ((f, True), (bad, False)):
            self.offer(frame, frame, frame)
            self.offer(frame)
            self.assertEqual(self.serve(verified=lambda t: verified), [frame])
        self.assertEqual((self.intake.verified, self.intake.unverified, self.intake.copied, self.intake.repeated),
                         (1, 1, 6, 0))
        self.assertEqual(self.refused, {})

    def test_copies_take_one_place_in_a_queue(self):
        """However often one sender resends a frame, the queue's other places stay free."""
        bad = forge(item(A, 1))
        self.offer(*[bad] * 10_000)
        others = [item(A, n + 2) for n in range(5)]
        self.offer(*others, *[bad] * 10_000)
        self.assertEqual((self.intake.stats()["queued"], self.intake.copied), (6, 19_999))
        self.assertEqual(self.serve(verified=lambda t: t.data != bad), [bad, *others])
        self.offer(bad)                             # it waits no more, so a copy waits for itself
        self.assertEqual(self.serve(verified=lambda t: False), [bad])
        self.assertEqual(self.refused, {})

    def test_a_turn_is_bounded_however_many_repeats_wait(self):
        """Frames accepted since their copies were queued: a turn must not hold the lock while it goes through them all."""
        frames = [item(A, n + 1) for n in range(60)]
        self.offer(*frames)
        for t in self.intake.take(60):
            self.intake._queue.append(t)                       # as if a copy of each came while it was being verified
            self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000)
            self.intake.settle(True)
        self.assertEqual((self.intake.take(8), self.intake.stats()["queued"]), ([], 60 - 8 * intake.TURN))
        self.assertTrue(self.intake.waiting())

    def test_a_copy_queued_before_the_verdict_is_a_repeat_after_it(self):
        f = item(A, 1)
        self.offer(f)
        batch = self.intake.take(1)
        self.offer(f)                                         # arrives while the first is being verified
        for t in batch:
            self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000)
            self.intake.settle(True)
        self.assertEqual((self.serve(), self.intake.repeated, self.intake.verified), ([], 1, 1))

    def test_a_digest_lasts_as_long_as_the_frame(self):
        f = item(A, 1)
        self.offer(f)
        (t,) = self.intake.take(1)
        self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() - 1)
        self.intake.settle(True)
        self.offer(f)
        self.assertEqual(self.serve(), [f])                   # past its life: judged again (as `expired`)
        self.intake.forget(runner.now_ms())
        self.assertEqual(self.intake.repeats, {})

    def test_counts_are_exact_with_two_threads_at_it(self):
        """The reader counts copies while the event loop reads the counts and serves copies of its own."""
        f = item(A, 1)
        self.offer(f)
        self.accept()
        n, total = 20_000, 0
        reader = threading.Thread(target=lambda: [self.intake.offer([f]) for _ in range(n)])
        old = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        self.addCleanup(sys.setswitchinterval, old)
        reader.start()
        while reader.is_alive():
            total += sum(c for _, c, _ in self.intake.heard_again())
        reader.join()
        total += sum(c for _, c, _ in self.intake.heard_again())
        self.assertEqual(self.intake.repeated, n)
        self.assertEqual(total, n)

    def test_beacon_digests_are_a_bounded_number_per_key(self):
        for n in range(1, intake.BEACON_REPEATS + 20):
            self.offer(beacon(A, n))
            (t,) = self.intake.take(1)
            self.intake.remember(t, None, runner.now_ms() + 10**9)
            self.intake.settle(True)
        self.assertEqual(len(self.intake.repeats), intake.BEACON_REPEATS)


class AccountingTest(IntakeCase):
    def test_every_datagram_read_is_accounted_for_once(self):
        """Random traffic: at every step, what was read is the sum of what became of it."""
        rng = random.Random(11)
        pool = [item(A, n + 1) for n in range(20)] + [beacon(B, n + 1) for n in range(90)] + [b"junk", item(B, 7)[:50]]
        pool += [forge(p, n) for n, p in enumerate(pool[:40])]
        with mock.patch.object(intake, "DEPTH", 30):
            for step in range(3_000):
                self.offer(*rng.choices(pool, k=rng.randrange(12)))
                for t in self.intake.take(rng.randrange(9)) if rng.random() < 0.6 else ():
                    ok = t.digest is not None and rng.random() < 0.5
                    if ok:
                        self.intake.remember(t, (t.data[4:12], 5), runner.now_ms() + rng.choice((-1, 10**6)))
                    self.intake.settle(ok)
                if rng.random() < 0.02:
                    self.intake.forget(runner.now_ms() + rng.choice((0, 10**7)))
                s = self.intake.stats()
                self.assertEqual(s["read"], s["repeats"] + s["copies"] + s["verified"] + s["unverified"] + s["queued"]
                                 + sum(s["refused"].values()), step)
                self.assertEqual(self.intake._digests, {t.digest for t in self.intake._queue if t.digest})
                self.assertLessEqual(s["queued"], 30)
                self.assertLessEqual(len(self.intake.repeats), sum(d[3:4] == b"\x01" for d in pool) + intake.BEACON_REPEATS)
        for what in ("repeats", "copies", "verified", "unverified"):
            self.assertGreater(s[what], 100)
        self.assertGreater(self.refused["backlog"], 100)


class SocketTest(IntakeCase):
    def test_recvmmsg_and_recvmsg_read_the_same(self):
        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(out.close)
        sent = [bytes([n]) * (n * 37 % 1200 + 1) for n in range(60)] + [b"", bytes(1300)]
        for make in (intake._Mmsg, intake._Msg):
            for d in sent:
                out.sendto(d, self.sock.getsockname())
            reader, got = make(self.sock), []
            while len(got) < len(sent):
                batch, drops = reader.read()
                got += batch
                self.assertIn(drops, (0, None))
            self.assertEqual(got, [d[:intake._SLOT] for d in sent])
            self.assertEqual(reader.read(), ([], None))        # the timeout, so a stop is noticed
        self.assertGreater(intake._SLOT, wire.MAX_DATAGRAM)

    def test_the_drop_count_survives_the_32_bit_wrap_and_late_readings(self):
        i = self.intake
        for raw, total in ((10, 10), (5, 10), (12, 12)):       # 5 is an older reading that came late
            i._note_drops(raw)
            self.assertEqual(i._drops, total)
        i._drops_raw = 2**32 - 5
        i._note_drops(3)
        self.assertEqual(i._drops, 12 + 8)
        i._note_drops(2**32 - 2)
        self.assertEqual(i._drops, 12 + 8)

    def test_both_readings_of_the_drop_count_agree_with_the_kernel(self):
        """SO_RXQ_OVFL on what is read, SO_MEMINFO now: the same counter (what R5 of test_intake_floods reports)."""
        i = Intake(self.sock, self.manifest, now_ms=runner.now_ms, wake=lambda: None, rcvbuf=1)
        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(out.close)
        for _ in range(500):
            out.sendto(b"x" * 100, self.sock.getsockname())
        lost = i.socket_drops()
        self.assertGreater(lost, 0)
        while i._reader.read()[0]:
            pass
        out.sendto(b"the next one carries the count", self.sock.getsockname())
        for make in (intake._Mmsg, intake._Msg):
            batch, drops = make(self.sock).read()
            self.assertEqual((len(batch), drops), (1, lost))
            out.sendto(b"and again", self.sock.getsockname())

    def test_stop_wakes_a_reader_that_waits(self):
        self.intake.start()
        t0 = time.perf_counter()
        self.intake.stop()
        self.assertLess(time.perf_counter() - t0, 0.2)
        self.assertFalse(self.intake._thread.is_alive())

    def test_a_reader_that_fails_says_so(self):
        failed = []
        self.intake = Intake(self.sock, self.manifest, now_ms=runner.now_ms, wake=lambda: None, failed=failed.append)
        with mock.patch.object(self.intake._reader, "read", side_effect=OSError(errno.EBADF, "gone")):
            self.intake.start()
            self.intake._thread.join(5)
        self.assertEqual([type(e) for e in failed], [OSError])

    def test_an_error_that_does_not_pass_ends_it(self):
        failed = []
        i = Intake(self.sock, self.manifest, now_ms=runner.now_ms, wake=lambda: None, failed=failed.append)
        with mock.patch.object(i._reader, "read", side_effect=OSError(errno.ENOBUFS, "still")), \
                mock.patch.object(intake, "PAUSE_S", 0.0):
            i.start()
            i._thread.join(5)
        self.assertEqual([e.errno for e in failed], [errno.ENOBUFS])

    def test_a_passing_error_is_survived_and_a_forbidden_recvmmsg_is_replaced(self):
        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(out.close)
        failed, f = [], item(A, 1)
        for code in (errno.ENOBUFS, errno.ENOSYS):
            i = Intake(self.sock, self.manifest, now_ms=runner.now_ms, wake=lambda: None, failed=failed.append)
            real, calls = i._reader.read, []
            def read(real=real, calls=calls, code=code):
                calls.append(1)
                if len(calls) == 1:
                    raise OSError(code, "for now")
                return real()
            i._reader.read = read
            i.start()
            out.sendto(f, self.sock.getsockname())
            deadline = time.perf_counter() + 5
            while not i.read and time.perf_counter() < deadline:
                threading.Event().wait(0.01)
            kind = type(i._reader)
            i._stop = True
            i._thread.join(5)
            self.assertEqual((i.read, failed, kind), (1, [], intake._Mmsg if code == errno.ENOBUFS else intake._Msg))


class DaemonIntakeTest(DaemonCase):
    """Real frames, over loopback UDP, to a real daemon in this process."""

    def send(self, port, *frames, sock=None):
        with sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            for f in frames:
                s.sendto(f, ("127.0.0.1", port))

    async def joined(self, d):
        c = await self.connect(d)
        await until(lambda: len(c.lines) == 2)
        return c

    def frames(self, c):
        return [r for r in c.recs if r["type"] == "frame"]

    def test_an_invalid_packet_with_the_same_identity_arrives_first_and_the_valid_one_is_admitted(self):
        """🌫's condition on #171: an invalid packet must not reserve an identity and suppress the valid one."""
        valid = item(SK, 1, body=b"the station's own")
        async def scenario(d, port):
            c = await self.joined(d)
            self.send(port, *[forge(valid, n) for n in range(5)])
            await until(lambda: d.receptor.counters["unverified"]["bad_signature"] == 5)
            self.send(port, forge(valid, 9), valid, forge(valid, 10))
            await until(lambda: self.frames(c))
            return self.frames(c), d.receptor.counters["unverified"]["bad_signature"]
        (recs, bad), _ = self.run_with(scenario)
        self.assertEqual([(r["admission"], r["frame"]["seq"], r["body"]["text"]) for r in recs],
                         [("verified", 1, "the station's own")])
        self.assertGreaterEqual(bad, 5)

    def test_repeats_are_never_verified_again_and_are_still_heard(self):
        """Counted as the duplicates they are, and noted for presence and the on-air item, as a repeat heard is."""
        f, b = item(SK, 1), beacon(SK, 1)
        async def scenario(d, port):
            c = await self.joined(d)
            self.send(port, b, f)
            await until(lambda: self.frames(c) and d.receptor.counters["beacon"]["verified"])
            lst, at = d.receptor.lst, d.receptor.last_datagram_at
            st = lst.stations[wire.key_id(wire.public_key_bytes(SK))]
            first = st.last_stream_item[stream_id("chatter")]
            time.sleep(0.02)
            with mock.patch("canticle.wire.parse", side_effect=AssertionError("a repeat was parsed")):
                self.send(port, *[f, b] * 10)
                await until(lambda: d.intake.repeated == 20)
                health = json.loads(d.receptor.health(runner.now_ms()))
            (heard,) = lst.current.values()
            return health, at, (first, st.last_stream_item[stream_id("chatter")]), heard.copies
        (h, at, (first, last), copies), _ = self.run_with(scenario)
        self.assertEqual((h["counters"]["admission"]["duplicate"], h["counters"]["disposition"]["no_op"],
                          h["counters"]["beacon"]), (10, 10, {"verified": 1, "duplicate": 10, "epoch_regression": 0}))
        self.assertEqual((h["receive"]["repeats"], h["receive"]["verified"], copies), (20, 2, 11))
        self.assertGreater(last, first)
        self.assertGreater(h["last_datagram_at"], at)

    def test_a_beacon_is_timed_when_it_arrives_not_when_its_turn_comes(self):
        """The clock offset (§8.2) must not absorb the time a beacon waited: an inflated one refuses fresh items as
        not yet valid."""
        async def scenario(d, port):
            with mock.patch.object(d, "_hear_queued"):          # the loop is too busy to hear it yet
                self.send(port, beacon(SK, 1))
                await until(lambda: d.intake.read == 1)
                time.sleep(0.3)
            d._hear_queued()
            (st,) = d.receptor.lst.stations.values()
            return st.offset_ms, runner.now_ms() - st.last_beacon
        (offset, age), _ = self.run_with(scenario)
        self.assertLess(offset, 150)
        self.assertGreaterEqual(age, 300)

    def test_old_beacons_replayed_push_no_fresh_one_out(self):
        """An old beacon verifies whenever it is replayed. It is not kept, so the digests are the latest beacons'."""
        old, new = [beacon(SK, n) for n in range(1, 9)], beacon(SK, 100)
        async def scenario(d, port):
            self.send(port, new)
            await until(lambda: d.receptor.counters["beacon"]["verified"] == 1)
            self.send(port, *old)
            await until(lambda: d.receptor.counters["beacon"]["duplicate"] == 8)
            return list(d.intake.repeats)
        self.assertEqual(self.run_with(scenario)[0], [hashlib.sha256(new).digest()])

    def test_a_restart_forgets_the_digests_so_the_first_copy_resurfaces(self):
        f = item(SK, 1)
        async def scenario(d, port):
            c = await self.joined(d)
            self.send(port, f, f)
            await until(lambda: self.frames(c))
            return self.frames(c)[0]["dedup"]
        self.assertEqual([self.run_with(scenario)[0] for _ in range(2)], ["first", "resurfaced"])

    def test_a_frame_refused_for_want_of_room_is_judged_again(self):
        """Verified but `over_quota`: its digest is not kept, so its next copy can still be admitted."""
        f, g = item(SK, 1), item(SK, 2)
        async def scenario(d, port):
            c = await self.joined(d)
            d.receptor.lst.per_key_quota = 1
            self.send(port, f)
            await until(lambda: len(self.frames(c)) == 1)
            self.send(port, g)
            await until(lambda: len(self.frames(c)) == 2)
            d.receptor.lst.per_key_quota = 10
            self.send(port, g)
            await until(lambda: len(self.frames(c)) == 3)
            return [r["admission"] for r in self.frames(c)]
        self.assertEqual(self.run_with(scenario)[0], ["verified", "over_quota", "verified"])

    def test_a_copy_of_an_earlier_epochs_beacon_is_counted_as_one(self):
        b = beacon(SK, 9, epoch=5)
        async def scenario(d, port):
            self.send(port, b)
            await until(lambda: d.receptor.counters["beacon"]["verified"] == 1)
            self.send(port, beacon(SK, 1, epoch=6))
            await until(lambda: d.receptor.counters["beacon"]["verified"] == 2)
            self.send(port, b, b)
            await until(lambda: d.intake.repeated == 2)
            d.receptor.tick(runner.now_ms())
            return d.receptor.counters["beacon"]
        self.assertEqual(self.run_with(scenario)[0], {"verified": 2, "duplicate": 0, "epoch_regression": 2})

    def test_an_item_held_back_at_its_restart_is_judged_again(self):
        """Restored from before the restart but refused a mark slot: not surfaced, so its digest is not kept."""
        f = item(SK, 1, stream="lens.threat", cls=3, state_key="k")
        async def first(d, port):
            c = await self.joined(d)
            self.send(port, f)
            await until(lambda: self.frames(c))
        async def second(d, port):
            c = await self.joined(d)
            d.receptor.lst.hwm.clear()
            d.receptor.lst.hwm_per_key = {wire.key_id(wire.public_key_bytes(SK)): 10}
            d.receptor.lst.per_key_mark_quota = 10
            self.send(port, f)
            await until(lambda: self.frames(c))
            kept = len(d.intake.repeats)
            d.receptor.lst.per_key_mark_quota = 11
            self.send(port, f)
            await until(lambda: len(self.frames(c)) == 2)
            return kept, [(r["admission"], r["dedup"]) for r in self.frames(c)]
        self.run_with(first)
        (kept, got), _ = self.run_with(second)
        self.assertEqual((kept, got), (0, [("over_quota", "first"), ("verified", "resurfaced")]))

    def test_a_copy_past_the_items_life_is_expired_again(self):
        now = runner.now_ms()
        f = item(SK, 1, now=now - 1_000, expires_at=now + 300)
        async def scenario(d, port):
            c = await self.joined(d)
            self.send(port, f)
            await until(lambda: self.frames(c))
            self.send(port, f)
            await until(lambda: d.intake.repeated == 1)
            await until(lambda: runner.now_ms() > now + 320)
            self.send(port, f)
            await until(lambda: d.receptor.counters["unverified"]["expired"] == 1)
        self.assertEqual(self.run_with(scenario)[1], 0)

    def test_one_save_covers_a_batch_and_nothing_counts_before_it(self):
        """Group commit is still write-ahead: a batch whose save fails sends none of its records, its digests are
        never kept, and the run ends."""
        frames = [item(SK, n + 1) for n in range(8)]
        async def scenario(d, port):
            c = await self.joined(d)
            saves = []
            real = listener.atomic_write_json
            with mock.patch("canticle.listener.atomic_write_json", side_effect=lambda *a: (saves.append(1), real(*a))):
                d.intake.offer(frames)
                await until(lambda: len(self.frames(c)) == 8)
            with mock.patch("canticle.listener.atomic_write_json", side_effect=OSError(28, "No space left on device")):
                d.intake.offer([item(SK, n + 20) for n in range(3)])
                await until(lambda: c.eof)
            return len(saves), [r["type"] for r in c.recs[2:]], len(d.intake.repeats)
        (saves, types, kept), code = self.run_with(scenario)
        self.assertEqual((saves, types, kept, code), (1, ["frame"] * 8 + ["fatal"], 8, 1))

    def test_health_tells_the_kinds_of_loss_apart(self):
        async def scenario(d, port):
            health = lambda: json.loads(d.receptor.health(runner.now_ms()))
            quiet = health()
            with mock.patch.object(d, "_hear_queued"):          # the loop is too busy to hear them yet
                d.intake.offer([forge(item(SK, 1), n) for n in range(intake.DEPTH + 7)])
                refused, later = health(), health()
            return quiet, refused, later
        (quiet, refused, later), _ = self.run_with(scenario)
        self.assertEqual((quiet["state"], quiet["records"]["socket_dropped"]), ("ok", 0))
        self.assertEqual(set(quiet["receive"]), {"read", "repeats", "copies", "verified", "unverified", "queued", "refused"})
        self.assertEqual(tuple(quiet["receive"]["refused"]), intake.REFUSED)
        self.assertEqual(refused["receive"]["refused"], {"backlog": 7})
        self.assertEqual((refused["state"], refused["reasons"]), ("degraded", ["datagrams_refused"]))
        self.assertEqual((later["state"], later["reasons"]), ("ok", []))     # reported once per loss
        self.assertEqual(later["records"]["dropped"], 0)

    def test_an_error_in_taking_a_batch_ends_the_run(self):
        async def scenario(d, port):
            c = await self.joined(d)
            with mock.patch.object(d.intake, "take", side_effect=ZeroDivisionError):
                self.send(port, item(SK, 1))
                await until(lambda: c.eof)
            return c.recs[-1]
        rec, code = self.run_with(scenario)
        self.assertEqual((rec["type"], rec["reason"], rec["detail"], code), ("fatal", "internal", "ZeroDivisionError", 1))

    def test_a_socket_that_cannot_be_set_up_is_a_failure_to_start(self):
        with mock.patch("canticle.daemon.Intake", side_effect=OSError(1, "Operation not permitted")):
            _, code = self.run_with(lambda d, p: None)
        self.assertEqual(code, 1)
        self.assertIn('"reason":"bind_failed"', self.fatal())

    def test_the_reader_failing_ends_the_run(self):
        async def scenario(d, port):
            c = await self.joined(d)
            with mock.patch.object(d.intake._reader, "read", side_effect=OSError(errno.EBADF, "gone")):
                self.send(port, item(SK, 1))                    # the read in progress returns, the next one fails
                await until(lambda: c.eof)
            return c.recs[-1]
        rec, code = self.run_with(scenario)
        self.assertEqual((rec["type"], rec["reason"], rec["detail"], code), ("fatal", "internal", "OSError", 1))


if __name__ == "__main__":
    unittest.main()
