"""The host daemon's intake (``canticle/intake.py``, #171): what may be skipped before verify, who pays, what is bounded.

Two kinds of test. ``IntakeCase`` drives an ``Intake`` with no thread and no socket traffic: ``offer`` places datagrams,
``take`` and ``settle`` are the event loop's half. ``DaemonIntakeTest`` sends real frames to a real in-process daemon
over loopback UDP. The floods are in ``test_fair_admission``.
"""

import asyncio
import errno
import hashlib
import json
import random
import socket
import sys
import threading
import time
import unittest
from collections import Counter, deque
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import intake, listener, runner, wire
from canticle.ids import stream_id
from canticle.intake import BEACON, OTHER, Intake, READ_BATCH, peek_stream
from canticle.daemon import RETRY_S, Daemon
from canticle.manifest import Manifest, StationEntry
from test_daemon import SK, DaemonCase, until

A, B = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
KID_A, KID_B = (wire.key_id(wire.public_key_bytes(k)) for k in (A, B))


def addr(host: int, port: int = 9) -> tuple:
    """A source address, as ``recvmsg`` gives it."""
    return f"192.0.2.{host}", port


HERE, THERE = addr(1), addr(2)


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
        self.now = 1_000.0
        clock = mock.patch("canticle.intake.time.monotonic", lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        entry = lambda name, sk, streams, **kw: StationEntry(name, wire.public_key_bytes(sk), frozenset({1}), streams, **kw)
        self.manifest = Manifest([entry("a", A, ("chatter", "other")), entry("b", B, ("chatter",))])
        self.intake = self.make()

    def make(self, manifest=None):
        def wake():
            self.woken += 1
        return Intake(self.sock, manifest or self.manifest, now_ms=runner.now_ms, wake=wake)

    def offer(self, *datagrams, src=HERE):
        self.intake.offer([(d, src) for d in datagrams])

    def serve(self, limit=32, verified=lambda t: True, fresh=True):
        """One turn of the event loop, with a given verdict per ticket. Returns the datagrams in the order served."""
        batch = self.intake.take(limit)
        for t in batch:
            self.intake.settle(t, verified(t), fresh and verified(t))
        return [t.data for t in batch]

    def serve_queues(self, limit, verified):
        """One turn; what came out of the queues, in their order, without what the slots had beside it."""
        batch = self.intake.take(limit)
        for t in batch:
            self.intake.settle(t, verified(t), verified(t))
        return [t.data for t in batch if t.budget is not self.intake.slice]

    def accept(self, limit=32):
        """One turn in which everything verifies, is accepted and is saved."""
        batch = self.intake.take(limit)
        for t in batch:
            self.intake.remember(t, (t.data[4:12], 5, 0, 1), runner.now_ms() + 60_000)
            self.intake.settle(t, True, True)
        return [t.data for t in batch]

    @property
    def refused(self):
        return {k: v for k, v in self.intake.stats()["refused"].items() if v}


class ReaderWakeTest(DaemonCase):
    def test_thirty_seconds_of_flood_batches_leave_one_turn_ahead_of_a_newcomer(self):
        """#177 RED: lifted check budgets must not expose a callback backlog that grows with flood age.

        At 20k datagrams/s the reader can hand off at least this many full batches in 30 seconds.  Model each queued
        intake turn as only 1 ms of event-loop work (less than the measured pass-3 cost), then put the newcomer's
        client-publication marker behind them.  It must keep the predeclared one-second first-frame deadline.  The
        wake is a level trigger for the ready set, so all of those handoffs need exactly one pending turn.
        """
        batches = (20_000 * 30 + READ_BATCH - 1) // READ_BATCH

        async def run():
            d = Daemon(self.cfg())
            calls = 0

            def drain_one_batch():
                nonlocal calls
                calls += 1
                time.sleep(0.001)

            d._hear_queued = drain_one_batch
            loop = asyncio.get_running_loop()
            started = time.monotonic()
            for _ in range(batches):
                d._wake_from_reader(loop)
            published = asyncio.Event()
            loop.call_soon(published.set)
            await asyncio.wait_for(published.wait(), 5.0)
            return time.monotonic() - started, calls

        elapsed, calls = asyncio.run(run())
        self.assertLessEqual(elapsed, 1.0)
        self.assertEqual(calls, 1)

    def test_a_wake_may_be_posted_again_after_the_pending_turn_starts(self):
        async def run():
            d = Daemon(self.cfg())
            called = asyncio.Event()
            d._hear_queued = called.set
            loop = asyncio.get_running_loop()
            d._wake_from_reader(loop)
            await asyncio.wait_for(called.wait(), 1.0)
            called.clear()
            d._wake_from_reader(loop)
            await asyncio.wait_for(called.wait(), 1.0)

        asyncio.run(run())

    def test_a_closed_loop_does_not_leave_the_wake_latched(self):
        class Closed:
            @staticmethod
            def call_soon_threadsafe(fn, *args):
                raise RuntimeError("closed")

        d = Daemon(self.cfg())
        d._wake_from_reader(Closed())
        self.assertFalse(d._reader_wake_pending)


class PeekTest(unittest.TestCase):
    def test_it_reads_what_the_strict_decoder_reads(self):
        for epoch in (0, 23, 24, 255, 256, 65_535, 65_536, 2**32 - 1):
            for stream in ("chatter", "root", "a", "b.c"):
                f = item(epoch=epoch, stream=stream, seq=2**40)
                got = wire.parse(f, lambda kid: A.public_key())
                self.assertEqual((peek_stream(f), peek_stream(f)), (got.body.stream, stream_id(stream)))
        for sid in (0, 23, 24, 255, 256, 65_535, 65_536):      # small ids: every integer width
            f = wire.encode_item(A, wire.Item(epoch=1, stream=sid, seq=1, issued_at=1, expires_at=2, cls=1, ctype=1, body=b""))
            self.assertEqual(peek_stream(f), sid)

    def test_anything_else_is_none_and_never_raises(self):
        crit = wire.sign_frame(wire.KIND_ITEM, A, {0: [1], 1: 1, 2: 7})
        self.assertIsNone(peek_stream(crit))
        for cut in range(0, 40):
            peek_stream(item()[:cut])
        for junk in (b"", bytes(200), b"\xff" * 200, b"BC\x02\x01" + bytes(8) + b"\xb9\xff\xff" + bytes(90)):
            self.assertIsNone(peek_stream(junk))
        head = b"BC\x02\x01" + bytes(8) + b"\xa9\x01\x05\x02"
        for byte in range(256):                                # only an unsigned integer is a stream id
            got = peek_stream(head + bytes([byte]) + b"\x01" * 900)
            self.assertEqual(got is None, byte > 0x1B, hex(byte))


class OrderTest(IntakeCase):
    def test_a_quiet_key_waits_behind_one_datagram_of_a_flooding_key(self):
        self.offer(*[item(B, n) for n in range(1, 50)])
        quiet = item(A, 1)
        self.offer(quiet)
        self.assertEqual(self.serve(4).index(quiet), 1)

    def test_a_quiet_stream_waits_behind_one_datagram_of_its_flooding_sibling(self):
        self.offer(*[item(A, n, "other") for n in range(1, 50)])
        quiet = item(A, 1)
        self.offer(quiet)
        self.assertEqual(self.serve(4).index(quiet), 1)

    def test_a_known_source_gets_every_other_turn_however_many_strangers_claim_its_stream(self):
        self.offer(item(A, 1), src=HERE)
        self.serve()
        for n in range(intake.STRANGERS_MAX):
            self.offer(*[forge(item(A, 1), 100 * n + i) for i in range(3)], src=addr(20 + n))
        quiet = [item(A, n + 2) for n in range(5)]
        self.offer(*quiet, src=HERE)
        served = self.serve(12, verified=lambda t: t.data in quiet)
        self.assertLessEqual(set(quiet), set(served))
        self.assertEqual([served.index(q) for q in quiet], sorted(served.index(q) for q in quiet))
        self.assertLessEqual(served.index(quiet[-1]), 2 * len(quiet))

    def test_a_quiet_source_waits_behind_one_datagram_of_another_claiming_its_stream(self):
        self.offer(*[forge(item(A, n), n) for n in range(1, 50)], src=THERE)
        quiet = item(A, 1)
        self.offer(quiet, src=HERE)
        self.assertIn(quiet, self.serve(4))                    # it has a place in the key's slot, beside its turn in the queue

    def test_junk_that_is_served_takes_no_keys_turn(self):
        """Checks are spent, and datagrams that are no frames are served meanwhile, on their own budget. (It reads no state that #173
        has not: on a0862c3 the first token there is again is always for B, whose turn came after A's.)"""
        checks = [b for b in (self.intake.checks, getattr(self.intake, "strange", None)) if b is not None]
        for b in checks:
            b.tokens, b.at = 0.0, self.now
        first = forge(item(A, 1))
        self.offer(first, src=THERE)
        for n in range(20):
            self.offer(b"junk %d" % n, src=addr(5))
            self.offer(forge(item(B, 1), n), src=THERE)
            self.assertEqual(self.serve(32, verified=lambda t: False), [b"junk %d" % n])
            for b in checks:
                b.tokens = 1.0
            got = self.serve(32, verified=lambda t: False)
            for b in checks:
                b.tokens = 0.0
            if first in got:
                break
        self.assertEqual(n, 0, "turns that A's datagram lost")

    def test_a_key_or_stream_that_is_passed_over_keeps_its_turn(self):
        """Strangers' checks are spent, and an established station is served meanwhile: the first token there is again is for
        whoever waited longest, not for whoever comes behind what was served."""
        sks = [A, B, Ed25519PrivateKey.generate()]
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(sks)]))
        self.offer(item(sks[2], 1), src=HERE)                  # established
        self.serve()
        strange = self.intake.strange
        strange.tokens, strange.at = 0.0, self.now
        first = forge(item(sks[0], 1))
        self.offer(first, src=THERE)
        waited = 0
        for n in range(20):
            self.offer(item(sks[2], 2 + n), src=HERE)
            self.offer(forge(item(sks[1], 1), n), src=THERE)
            self.serve(32, verified=lambda t: t.addr == HERE)  # the station's, and no stranger's
            strange.tokens = 1.0
            got = self.serve(32, verified=lambda t: t.addr == HERE)
            strange.tokens = 0.0
            if first in got:
                break
            waited += 1
        self.assertEqual(waited, 0)

    def test_so_does_one_that_is_passed_over_in_a_turn_that_fills_up(self):
        sks = [Ed25519PrivateKey.generate() for _ in range(3)]
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(sks)]))
        for sk in sks[1:]:
            self.offer(item(sk, 1), src=HERE)                  # established
        self.serve()
        self.intake.strange.tokens, self.intake.strange.at = 0.0, self.now
        self.offer(first := forge(item(sks[0], 1)), src=THERE)
        self.offer(*[item(sk, 2 + n) for n in range(4) for sk in sks[1:]], src=HERE)
        self.assertEqual(len(self.serve(3, verified=lambda t: t.addr == HERE)), 3)       # the turn is full, and more waits
        self.intake.strange.tokens = 1.0
        self.assertEqual(self.serve(1, verified=lambda t: False), [first])

    def test_and_a_stream_within_its_key(self):
        key = self.intake.keys[KID_A]
        self.offer(item(A, 1, "other"), src=HERE)              # established
        self.serve()
        self.intake.strange.tokens, self.intake.strange.at = 0.0, self.now
        self.offer(first := forge(item(A, 1)), src=THERE)
        self.offer(*[item(A, 2 + n, "other") for n in range(3)], src=HERE)
        self.offer(forge(beacon(A, 1)), src=THERE)             # behind it
        self.assertEqual(len(self.serve(2, verified=lambda t: t.addr == HERE)), 2)
        self.intake.strange.tokens = 1.0
        self.assertEqual(self.serve(1, verified=lambda t: False), [first])
        self.assertTrue(key.ready)

    def test_one_source_of_one_stream_is_served_in_order(self):
        frames = [item(A, n) for n in range(1, 6)]
        self.offer(*frames)
        self.assertEqual(self.serve(), frames)

    def test_the_loop_is_woken_when_something_new_waits_and_not_for_every_datagram(self):
        self.offer(*[item(A, n) for n in range(1, 9)])
        self.offer(item(A, 9))
        self.assertEqual(self.woken, 1)
        self.offer(item(B, 1))
        self.assertEqual(self.woken, 2)
        self.assertTrue(self.intake.waiting())
        self.serve()
        self.assertFalse(self.intake.waiting())


class BoundTest(IntakeCase):
    def test_only_listed_keys_and_streams_get_queues(self):
        """Keys and streams no manifest lists share one queue each, whatever a sender invents."""
        before = (set(self.intake.keys), {k: set(q.streams) for k, q in self.intake.keys.items()})
        for n in range(200):
            self.offer(item(Ed25519PrivateKey.generate(), 1), item(A, n + 1, stream=f"s{n}"))
        self.assertEqual((set(self.intake.keys), {k: set(q.streams) for k, q in self.intake.keys.items()}), before)
        self.assertEqual(before[0], {KID_A, KID_B})
        self.assertEqual(before[1][KID_A], {stream_id("chatter"), stream_id("other"), OTHER, BEACON})
        self.assertEqual(len(self.intake.unlisted.ready), intake.UNLISTED_DEPTH)
        self.assertEqual(self.refused["unlisted"], 200 - intake.UNLISTED_DEPTH)

    def test_a_revoked_key_is_not_a_listed_one(self):
        self.intake = self.make(Manifest([StationEntry("a", wire.public_key_bytes(A), frozenset({1}), ("chatter",),
                                                       revoked=True)]))
        self.offer(item(A, 1))
        self.assertEqual((self.intake.keys, len(self.intake.unlisted.ready)), ({}, 1))

    def test_what_waits_is_bounded_whatever_claims_it(self):
        """A flood of one key from 5 000 addresses: at most one table of sources, one queue each, and the rest
        counted."""
        for n in range(5_000):
            self.intake.offer([(forge(item(A, 1), n), addr(n % 250, n))])
        key = self.intake.keys[KID_A]
        self.assertLessEqual(len(key.strangers), intake.STRANGERS_MAX)
        waiting = self.intake.stats()["queued"]                # the pool's, and what it refused that waits in the key's slot
        self.assertTrue(intake.STRANGER_POOL <= waiting <= intake.STRANGER_POOL + intake.SLOT_MAX, waiting)
        self.assertEqual(waiting + sum(self.refused.values()), 5_000)

    def test_a_newcomer_gets_a_queue_once_idle_strangers_are_gone(self):
        for n in range(intake.STRANGERS_MAX):
            self.intake.offer([(item(A, n + 1), addr(10 + n))])
        self.now += 1
        self.assertIn(self.intake.keys[KID_A].source(THERE, self.now), self.intake.keys[KID_A].crowd)
        self.serve(fresh=False)
        self.now += 1
        self.offer(item(A, 99), src=THERE)
        self.assertIn(THERE, self.intake.keys[KID_A].strangers)

    def test_one_host_cannot_fill_the_table_with_its_ports(self):
        """A port costs a sender nothing. Whatever one host opens, a station on another host still queues apart."""
        for n in range(1_000):
            self.intake.offer([(forge(item(A, 1), n), addr(7, n))])
        self.assertEqual(len(self.intake.keys[KID_A].strangers), intake.STRANGERS_PER_HOST)
        quiet = item(A, 1)
        self.offer(quiet, src=HERE)                            # the host's ports have the slot's places: it queues
        lanes = intake.STRANGERS_PER_HOST + intake.CROWD_LANES + 1
        served = [d for _ in range(lanes // 16 + 1) for d in self.serve_queues(16, lambda t: t.data == quiet)]
        self.assertIn(quiet, served[:lanes])
        self.drain_host(7)
        self.assertEqual(self.intake.stats()["queued"], 0)
        for n in range(10):                                    # and once they are gone, its ports count no more
            self.now += 1
            self.offer(item(A, 10 + n), src=addr(7, 5_000 + n))
            self.assertIn(addr(7, 5_000 + n), self.intake.keys[KID_A].strangers)
            self.serve(fresh=False)

    def test_a_newcomer_beyond_the_table_still_gets_its_turn(self):
        """A host with more ports than queue apart: the rest share many lanes, by a salted hash, not one. So a
        station starting on that host is crowded by the few ports that fall in its lane, not by all of them."""
        key = self.intake.keys[KID_A]
        for n in range(40):
            self.offer(*[forge(item(A, 1), 100 * n + i) for i in range(20)], src=addr(7, n))
        mine = {key.source(addr(7, n), self.now) for n in range(40)}
        quiet = next(addr(7, port) for port in range(1_000, 2_000) if key.source(addr(7, port), self.now) not in mine)
        f = item(A, 1)
        self.offer(f, src=quiet)
        served = [d for _ in range(len(mine) // 16 + 1) for d in self.serve(16, verified=lambda t: t.data == f)]
        self.assertIn(f, served)

    def test_the_lane_of_a_crowded_address_cannot_be_chosen(self):
        lanes = []
        for _ in range(2):
            self.intake = self.make()
            key = self.intake.keys[KID_A]
            for n in range(intake.STRANGERS_PER_HOST):
                self.offer(item(A, n + 1), src=addr(7, n))
            lanes.append([key.crowd.index(key.source(addr(7, 100 + n), self.now)) for n in range(40)])
        self.assertNotEqual(*lanes)

    def test_the_pool_holds_more_than_one_datagram_per_lane(self):
        """Or the longest lane could be emptied to make room (``StreamQueue.put``)."""
        self.assertGreater(intake.STRANGER_POOL, 2 * (intake.STRANGERS_MAX + intake.CROWD_LANES) - 1)

    def test_a_burst_from_an_unknown_port_waits_whole(self):
        frames = [item(A, n + 1) for n in range(40)]
        self.offer(*frames)
        self.assertEqual((self.serve(64), self.refused), (frames, {}))

    def test_a_full_pool_refuses_its_longest_queue_and_never_a_newcomer(self):
        """The strangers of a stream share one pool. Full, it takes a newcomer's datagram out of the longest queue's
        place: a flood can fill the pool, but not keep a station's first frame out of it."""
        self.offer(*[forge(item(A, 1), n) for n in range(2 * intake.STRANGER_POOL)], src=THERE)
        self.assertEqual(self.intake.stats()["queued"], intake.STRANGER_POOL)
        quiet = [item(A, n + 1) for n in range(4)]
        self.offer(*quiet, src=HERE)
        self.assertEqual(self.intake.stats()["queued"], intake.STRANGER_POOL)
        self.assertEqual(sum(self.refused.values()), intake.STRANGER_POOL + 4)
        served = self.serve(8, verified=lambda t: t.data in quiet)
        self.assertEqual([d for d in served if d in quiet], [*quiet[1:], quiet[0]])  # the slots come after the queues

    def drain_host(self, host):
        while self.intake.stats()["queued"]:
            self.now += 1
            self.serve(verified=lambda t: False)

    def test_what_is_not_a_frame_goes_to_the_shared_queue(self):
        f = item(A, 1)
        bad = [b"", b"BC", f[:60], b"XX" + f[2:], f[:2] + b"\x03" + f[3:], f[:3] + b"\x09" + f[4:], f + bytes(1200)]
        self.offer(*bad)
        self.assertEqual(sorted(self.serve(), key=len), sorted(bad, key=len))
        self.assertEqual(self.intake.stats()["queued"], 0)


class RepeatTest(IntakeCase):
    """🌫's first condition on #171: only the exact bytes of a frame already verified are skipped."""

    def test_an_exact_copy_of_an_accepted_frame_is_counted_and_never_queued(self):
        f = item(A, 1)
        self.offer(f)
        self.accept()
        self.offer(f, f, src=THERE)
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
        self.offer(*[forge(f, n) for n in range(4)], src=THERE)
        self.assertEqual(len(self.serve(verified=lambda t: t.data == f)), 4)
        self.offer(forge(f, 9), src=THERE)
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
            self.offer(frame, src=THERE)
            self.assertEqual(self.serve(verified=lambda t: verified), [frame])
        self.assertEqual((self.intake.verified, self.intake.unverified, self.intake.copied, self.intake.repeated),
                         (1, 1, 6, 0))
        self.assertEqual(self.refused, {})

    def test_copies_take_one_place_in_a_queue(self):
        """However often one sender resends a frame, its stream's other places, and its own queue's, stay free."""
        bad = forge(item(A, 1))
        self.offer(*[bad] * 10_000, src=THERE)
        others = [item(A, n + 2) for n in range(5)]
        self.offer(*others, *[bad] * 10_000, src=THERE)
        self.assertEqual((self.intake.stats()["queued"], self.intake.copied), (6, 19_999))
        self.assertEqual(self.serve(verified=lambda t: t.data != bad), [bad, *others])
        self.offer(bad, src=THERE)                             # it waits no more, so a copy waits for itself
        self.assertEqual(self.serve(verified=lambda t: False), [bad])
        self.assertEqual(self.refused, {})

    def test_a_turn_is_bounded_however_many_copies_wait(self):
        """The same forgeries from every port: a batch must not hold the lock while it goes through all of them."""
        bad = [forge(item(A, 1), n) for n in range(4)]
        for n in range(intake.STRANGERS_MAX):
            self.offer(*bad, src=addr(n))
        before = self.intake.stats()["queued"]
        self.intake.take(8)
        self.assertLessEqual(before - self.intake.stats()["queued"], (8 + 4) * intake.TURN)

    def test_a_copy_queued_before_the_verdict_is_a_repeat_after_it(self):
        f = item(A, 1)
        self.offer(f)
        batch = self.intake.take(1)
        self.offer(f, src=THERE)                              # arrives while the first is being verified
        for t in batch:
            self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000)
            self.intake.settle(t, True, True)
        self.assertEqual((self.serve(), self.intake.repeated, self.intake.verified), ([], 1, 1))

    def test_a_digest_lasts_as_long_as_the_frame(self):
        f = item(A, 1)
        self.offer(f)
        (t,) = self.intake.take(1)
        self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() - 1)
        self.intake.settle(t, True, True)
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
        reader = threading.Thread(target=lambda: [self.intake.offer([(f, HERE)]) for _ in range(n)])
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
            self.now += 1
            self.offer(beacon(A, n))
            (t,) = self.intake.take(1)
            self.intake.remember(t, None, runner.now_ms() + 10**9)
            self.intake.settle(t, True, True)
        self.assertEqual(len(self.intake.repeats), intake.BEACON_REPEATS)


class BudgetTest(IntakeCase):
    def drain(self, seconds, **kw):
        """Serve for ``seconds`` of clock time; returns everything served."""
        out = []
        for _ in range(int(seconds * 20)):
            out += self.serve(**kw)
            self.now += 0.05
        return out

    def test_a_forged_flood_spends_its_own_budget_and_none_of_the_station(self):
        """Debit after verify: what fails costs its source, never the bucket of the key it names."""
        key = self.intake.keys[KID_A]
        n = 0
        for _ in range(100):
            self.offer(*[forge(item(A, 1), n + i) for i in range(400)], src=THERE)
            n += 400
            self.serve(64, verified=lambda t: False)
            self.now += 0.01
        self.assertLessEqual(self.intake.unverified, intake.SOURCE_BURST + 1.0 * intake.SOURCE_RATE + 1)
        self.assertEqual(key.bucket.tokens, intake.KEY_BURST)
        self.assertEqual(key.streams[stream_id("chatter")].bucket.tokens, intake.STREAM_BURST)
        self.assertGreater(self.refused["unverified"], 0)

    def test_forgeries_from_everywhere_never_touch_a_known_source(self):
        """An address a new frame of the key was verified from keeps its turn and its own budget, whatever claims
        the key from 2 000 other addresses."""
        self.offer(item(A, 1), src=HERE)
        self.accept()
        for n in range(2_000):
            self.intake.offer([(forge(item(A, 1), n), addr(n % 250, 100 + n))])
            if n % 20 == 0:
                self.serve(verified=lambda t: False)
        for seq in range(2, 30):
            f = item(A, seq)
            self.offer(f, src=HERE)
            for n in range(40):
                self.intake.offer([(forge(item(A, 1), 10_000 + seq * 40 + n), addr(n, 9_000 + n))])
            self.assertIn(f, self.serve(verified=lambda t: t.data == f))
            self.now += 0.1

    def test_another_keys_verify_share_is_its_own(self):
        for n in range(int(intake.CHECK_BURST) - 1):
            self.offer(forge(item(A, 1), n), src=THERE)
            self.serve(verified=lambda t: False)
        f = item(B, 1)
        self.offer(f, src=THERE)
        self.assertEqual(self.serve(), [f])

    def test_all_checks_that_come_to_nothing_share_one_bound(self):
        """Whatever keys and addresses a flood spoofs, the daemon's work on it is bounded, and a key that forges
        nothing still gets its turn within a round of the refill."""
        for sk in (A, B):
            self.offer(item(sk, 1), src=HERE)
            self.serve()
        n = 0
        for _ in range(100):
            for sk in (A, B):
                self.offer(*[forge(item(sk, 1), n + i) for i in range(40)], src=HERE)     # spoofing known sources
                n += 40
            self.serve(64, verified=lambda t: False)
            self.now += 0.01
        self.assertLessEqual(self.intake.unverified, intake.CHECK_BURST + 1.0 * intake.CHECK_RATE + 1)
        self.assertGreater(self.intake.unverified, 0.9 * intake.CHECK_RATE)

    def test_verified_frames_are_held_to_the_key_and_stream_rates(self):
        seq = iter(range(1, 10**6))
        served = Counter()
        for _ in range(200):                                  # ten seconds, two streams flooding
            for stream in ("chatter", "other"):
                self.offer(*[item(A, next(seq), stream) for _ in range(4)])
            for d in self.serve():
                served[peek_stream(d)] += 1
            self.now += 0.05
        self.assertLessEqual(sum(served.values()), intake.KEY_BURST + 10 * intake.KEY_RATE + 1)
        self.assertGreaterEqual(sum(served.values()), 10 * intake.KEY_RATE)
        self.assertAlmostEqual(served[stream_id("chatter")], served[stream_id("other")], delta=2)   # shared, not raced
        self.assertGreater(self.refused["over_rate"], 0)

    def test_one_stream_cannot_spend_the_keys_whole_cap(self):
        self.assertLess(intake.STREAM_RATE, intake.KEY_RATE)
        self.assertLess(intake.STREAM_BURST, intake.KEY_BURST)
        seq = iter(range(1, 10**6))
        for _ in range(100):
            self.offer(*[item(A, next(seq), "other") for _ in range(8)])
            self.serve()
            self.now += 0.05
        f = item(A, 1)
        self.offer(f)
        self.assertIn(f, self.serve(2))

    def test_only_new_frames_spend_the_stations_buckets(self):
        """A replay that verifies and changes nothing (an old beacon, which verifies whenever it is replayed, or a
        frame refused at steps 3-4) is charged to whoever sent it, not to the station that signed it. From the
        station's own address too: a sender may spoof that."""
        key = self.intake.keys[KID_A]
        self.offer(item(A, 1_000), beacon(A, 1_000), src=HERE)
        self.serve()
        full = intake.KEY_BURST - 1, intake.STREAM_BURST - 1, intake.BEACON_BURST - 1
        for src in (HERE, THERE):
            for n in range(1, 200):
                self.offer(beacon(A, n), item(A, n), src=src)
                self.serve(fresh=False)
            self.assertEqual((key.bucket.tokens, key.streams[stream_id("chatter")].bucket.tokens,
                              key.streams[BEACON].bucket.tokens), full)
            self.assertLess(key.source(src, self.now).budget.tokens, 1.0)
        new = [item(A, 500), beacon(A, 500)]
        self.offer(*new, src=addr(3))                          # its station, on another port
        self.now += 0.5
        batch = self.intake.take(32)
        for t in batch:
            self.intake.settle(t, True, t.data in new)
        self.assertLessEqual(set(new), {t.data for t in batch})
        self.assertIn(addr(3), key.known)

    def test_items_that_change_nothing_cost_their_sender_more(self):
        """Each makes a record (a refused one, §14.18.3) for every binding, so fewer are heard than forgeries are
        checked, whoever sends them."""
        for n in range(1, 1_000):
            self.offer(item(A, n))
            self.serve(fresh=False)
        self.assertLessEqual(self.intake.verified, intake.SOURCE_BURST / intake.NO_OP_COST + 1)
        before = self.intake.verified
        for n in range(1_000, 6_000):                          # ten seconds: the rate, and at most one batch beyond it
            self.offer(item(A, n))
            self.serve(fresh=False)
            self.now += 0.002
        self.assertLessEqual(self.intake.verified - before, 10 * intake.SOURCE_RATE / intake.NO_OP_COST + 32)

    def test_old_beacons_from_a_known_source_spend_no_beacons_turn(self):
        """Not even those of a sender that spoofs the station's address: they make no records, so nothing needs the
        station's bucket to bound them."""
        self.offer(beacon(A, 1_000), src=HERE)
        self.serve()
        for n in range(1, 90):
            self.offer(beacon(A, n), src=HERE)
            self.serve(fresh=False)
        self.assertEqual(self.intake.keys[KID_A].streams[BEACON].bucket.tokens, intake.BEACON_BURST - 1)

    def test_only_a_fresh_frame_makes_its_address_known(self):
        self.offer(item(A, 1), src=THERE)
        self.serve(fresh=False)                                # a replay of an old frame: verified, not fresh
        self.assertEqual(list(self.intake.keys[KID_A].known), [])
        self.offer(item(A, 2), src=HERE)
        self.serve()
        self.assertEqual(list(self.intake.keys[KID_A].known), [HERE])

    def test_known_sources_are_the_latest_few(self):
        for n in range(intake.KNOWN_MAX + 3):
            self.offer(item(A, n + 1), src=addr(50 + n))
            self.serve()
        self.assertEqual(list(self.intake.keys[KID_A].known), [addr(50 + n) for n in range(3, intake.KNOWN_MAX + 3)])

    def test_displacing_a_known_source_leaves_the_queues_consistent(self):
        """A known source pushed out while it has datagrams waiting queues on as a stranger, or, with that table
        full, what it had waiting is counted and gone."""
        for n in range(intake.KNOWN_MAX):
            self.offer(item(A, n + 1), src=addr(50 + n))
            self.serve()
        known = [addr(51), addr(52), addr(53)]
        self.offer(item(A, 70), item(A, 71), src=addr(50))     # the oldest known source, waiting
        key = self.intake.keys[KID_A]
        with self.intake._lock:
            key.know(addr(90))
        self.assertEqual(list(key.known), [*known, addr(90)])
        self.assertIn(addr(50), key.strangers)
        self.assertEqual((len(self.serve(fresh=False)), self.intake.waiting()), (2, False))

        for n in range(intake.STRANGERS_MAX + 1):              # every place in the table has something waiting
            self.now += 1
            self.offer(forge(item(A, 1), n), src=addr(100 + n))
        self.offer(item(A, 80), item(A, 81), src=addr(51))
        newcomer = item(A, 99)
        self.offer(newcomer, src=addr(250))                    # beyond the table: in the crowd
        while (t := self.intake.take(1)[0]).data != newcomer:
            self.intake.settle(t, False, False)
            if t.addr == addr(51):
                self.offer(t.data, src=addr(51))               # so it still has two waiting when the newcomer is verified
        self.intake.settle(t, True, True)
        self.assertNotIn(addr(51), key.known)
        self.assertNotIn(addr(51), key.strangers)
        self.assertEqual(self.refused.get("backlog"), 2)
        for _ in range(3):
            self.now += 1
            self.serve(200, verified=lambda t: False)
        self.assertEqual((self.intake.stats()["queued"], self.intake.waiting()), (0, False))
        self.assertEqual([(s.pool, s.lanes) for s in key.streams.values()], [(0, {})] * len(key.streams))

    def test_the_unlisted_queue_is_examined_on_a_budget(self):
        unknown = Ed25519PrivateKey.generate()
        for n in range(2_000):
            self.offer(item(unknown, n + 1))
            self.serve(verified=lambda t: False)
        self.assertLessEqual(self.intake.unverified, intake.UNLISTED_BURST)


class ChurnTest(IntakeCase):
    """🌫's condition on #173: a source is an address and a port, and ports cost a sender nothing. Whatever churns
    them, the tables, what waits and a turn's work stay bounded, and an established source loses nothing uncounted."""

    @property
    def shares(self):
        """(sources that were given a share of their own, how many of them lost it to a newer one), as reported."""
        return tuple(self.intake.stats().get(k) for k in ("known", "displaced"))

    def accept_from(self, src, *frames):
        self.offer(*frames, src=src)
        self.assertEqual(set(self.accept()), set(frames))

    def test_forged_churn_costs_an_established_source_nothing(self):
        """Every forgery from an address and port never seen before, half of them on the station's own host."""
        self.accept_from(HERE, item(A, 1))
        key, n = self.intake.keys[KID_A], 0
        for seq in range(2, 40):
            for _ in range(500):
                n += 1
                src = (HERE[0], 1_000 + n) if n % 2 else (f"198.51.{n >> 8}.{n & 255}", 1_000 + n)
                self.intake.offer([(forge(item(A, 1), n), src)])
            f = item(A, seq)
            self.offer(f, src=HERE)
            self.assertLessEqual(self.serve(8, verified=lambda t: t.data == f).index(f), 1)
            self.now += 0.1
        self.assertEqual(list(key.known), [HERE])
        self.assertLessEqual((len(key.strangers), len(key.hosts)), (intake.STRANGERS_MAX, intake.STRANGERS_MAX))

    def test_a_source_that_loses_its_share_to_newer_ones_is_counted(self):
        """What the daemon hears first from a port makes that port known, so a relay without a key, heard before the
        station with a copy of each of its frames and from a port of its own each, displaces it. Nothing waited, so
        nothing is refused: only this count says that the station is a stranger again."""
        self.accept_from(HERE, item(A, 1))
        for n in range(intake.KNOWN_MAX):
            f = item(A, n + 2)
            self.accept_from(addr(7, 5_000 + n), f)
            self.offer(f, src=HERE)                            # the station's own copy: a repeat
        self.assertNotIn(HERE, self.intake.keys[KID_A].known)
        self.assertEqual(self.refused, {})
        self.assertEqual(self.shares, (1 + intake.KNOWN_MAX, 1))
        self.accept_from(HERE, item(A, 90))                    # its next frame heard first from there restores it
        self.assertIn(HERE, self.intake.keys[KID_A].known)
        self.assertEqual(self.shares, (2 + intake.KNOWN_MAX, 2))

    def test_known_sources_and_strangers_dilute_an_established_source_by_a_bound(self):
        """The worst that is left: every other known place is a relay's and forges, and so does a full table of
        strangers. The station's frame is at most KNOWN_MAX known turns away, each beside one of a stranger."""
        relays = [addr(7, 5_000 + n) for n in range(intake.KNOWN_MAX - 1)]
        for n, src in enumerate((*relays, HERE)):
            self.accept_from(src, item(A, n + 1))
        for n, src in enumerate((*relays, *(addr(20 + n) for n in range(intake.STRANGERS_MAX)))):
            self.offer(*[forge(item(A, 1), 100 * n + i) for i in range(4)], src=src)
        f = item(A, 50)
        self.offer(f, src=HERE)
        self.assertIn(f, self.serve(2 * intake.KNOWN_MAX, verified=lambda t: t.data == f))

    def test_what_waits_is_bounded_however_many_sources_become_known(self):
        """Each in turn has a new frame verified, then fills its lanes and is displaced with them full."""
        key = self.intake.keys[KID_A]
        chatter, most = key.streams[stream_id("chatter")], Counter()
        for n in range(3 * intake.STRANGERS_MAX):
            src, f = addr(1 + n % 250, 4_000 + n), item(A, n + 1)
            self.offer(f, src=src)
            while True:
                self.now += 0.5
                (t,) = self.intake.take(1)
                self.intake.settle(t, t.data == f, t.data == f)
                if t.data == f:
                    break
            self.offer(*[forge(item(A, 1), 1_000 * n + i) for i in range(300)], src=src)
            most["pool"] = max(most["pool"], chatter.pool)
            most["queued"] = max(most["queued"], self.intake.stats()["queued"])
        self.assertLessEqual(most["pool"], intake.STRANGER_POOL)
        # A known source's lane holds KNOWN_DEPTH, or what it had waiting when it became known: at most the pool.
        self.assertLessEqual(most["queued"], (1 + intake.KNOWN_MAX) * intake.STRANGER_POOL)
        self.assertEqual(self.intake.read, self.intake.verified + self.intake.unverified + sum(self.refused.values())
                         + self.intake.stats()["queued"])

    def test_a_stranger_that_becomes_known_keeps_its_places(self):
        """A station that starts in a flood does not lose what it had waiting by being verified."""
        frames = [item(A, n + 1) for n in range(100)]
        self.offer(*frames, src=THERE)
        self.accept(1)
        self.assertEqual((self.intake.stats()["queued"], self.refused), (99, {}))

    def test_placing_and_serving_look_at_a_bounded_number_of_lanes(self):
        """The scheduler's work is per lane, and 100 000 ports open at most KNOWN_MAX + STRANGERS_MAX + CROWD_LANES
        lanes of a stream, however they come and go."""
        key = self.intake.keys[KID_A]
        chatter, most = key.streams[stream_id("chatter")], 0
        for n in range(100_000):
            self.intake.offer([(forge(item(A, 1), n) if n < 1_000 else self.cheap(n), (f"198.51.{n >> 8 & 255}.{n & 255}", n))])
            most = max(most, len(chatter.lanes))
            if n % 100 == 0:
                self.now += 0.05
                self.serve(8, verified=lambda t: False)
        self.assertLessEqual(most, intake.KNOWN_MAX + intake.STRANGERS_MAX + intake.CROWD_LANES)
        self.assertLessEqual(len(key.strangers), intake.STRANGERS_MAX)
        self.assertEqual((key.known, self.intake.repeats), ({}, {}))

    def cheap(self, n: int) -> bytes:
        self._one = getattr(self, "_one", None) or item(A, 1)
        return forge(self._one, n)


def udp(port: int, host: int = 1) -> int:
    """A source as ``recvmmsg`` gives it (a sockaddr_in's first 8 bytes), so that the salted lanes depend on the salt alone."""
    return int.from_bytes(bytes((2, 0)) + port.to_bytes(2, "big") + bytes((127, 0, 0, host)), sys.byteorder)


C_SLICE, C_ALL = 500.0, 2_000.0     # the newcomer-recovery report's PLAN.md: the slice's checks a second, and the daemon's
M = 4                               # and the share of a key's turns of those that were tried, one in so many
CAP, PENDING = 256, 64              # the marks a key holds, and the sources that wait in its slot, of each tier
CHECK_S = 0.00014                   # the dearest check of #171 (60-140 µs on ronan)
TURN_S = 48 * CHECK_S               # a turn of the event loop, its durable save apart
SAVE_TURN_S = 0.045                 # and with it


class NewcomerCase(IntakeCase):
    """A flood and a newcomer in virtual time: each millisecond the reader places what came, and the event loop, when it is not
    busy with the checks of its last turn, runs at most one turn, as ``Daemon._hear_queued`` would: at once when the last one
    looked at something, RETRY_S later when it did not, and when it is woken. A turn's verdicts come when it is over: what
    arrives meanwhile is placed before them."""

    K, RATE, PORTS = 16, 20_000, 40

    def setUp(self):
        super().setUp()
        self.stations(self.K)

    def stations(self, n):
        self.sks = [Ed25519PrivateKey.generate() for _ in range(n)]
        self.kids = [wire.key_id(wire.public_key_bytes(sk)) for sk in self.sks]
        self.frames = [(item(sk, 1), beacon(sk, 1)) for sk in self.sks]      # to forge from
        self.old = [[beacon(sk, 1_000 + n) for n in range(4)] for sk in self.sks]    # captured: they verify, and change nothing
        self.noop = [[item(sk, 10**6 + n) for n in range(0)] for sk in self.sks]
        self.fresh()

    def fresh(self):
        """A new intake of K stations, at a time of its own. ``checked``: the verdicts so far, by key id."""
        self.now += 100
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(self.sks)]))
        self.n, self.rng, self.busy, self.due = 0, random.Random(7), self.now, self.now
        self.checked, self.slots, self.flight = Counter(), Counter(), []
        self.waits: dict = {}           # newcomer's frame -> when it was sent, then how long it waited for its check

    def forged(self, keys, churn=False):
        """The next datagram of the flood: distinct, claiming ``keys`` in turn, items and beacons, from a port of its own or one
        of PORTS in turn."""
        self.n += 1
        k = keys[self.n % len(keys)]
        kind = self.n // len(keys) // self.PORTS % 2
        if churn == "replay" and self.n // len(keys) // self.PORTS % 2:
            return self.old[k][self.n % 4], udp(40_000 + self.n // len(keys) % self.PORTS)
        if churn == "noop":                     # captured items that verify, and change nothing
            return self.noop[k][self.n // len(keys) % self.PORTS], udp(40_000 + self.n // len(keys) % self.PORTS)
        if churn == "junk" and self.n % 2:
            return b"junk %d" % self.n, udp(39_000)
        if churn == "hold" and self.n // len(keys) % 4 == 0:
            m = self.n // len(keys) // 4 % len(self.old[k])
            return self.old[k][m], udp(39_000 + m)
        if churn == "once":                     # never the same source twice
            return forge(self.frames[k][kind], self.n), udp(1_024 + self.n % 60_000, 10 + self.n // 60_000)
        port = self.rng.randrange(32_768, 61_000) if churn is True else 40_000 + self.n // len(keys) % self.PORTS
        return forge(self.frames[k][kind], self.n), udp(port)

    def play(self, seconds, keys=(), churn=False, copies=(), rate=None, turn_s=0.0):
        """``seconds`` of a flood over ``keys`` and of ``copies`` [(when, frame, source)] of stations. Returns how long each of
        them waited for its check: negative when it had none."""
        start, copies = self.now, sorted(copies, key=lambda c: c[0])
        mine = {f for _, f, _ in copies}
        for ms in range(round(seconds * 1000)):
            batch = [self.forged(keys, churn) for _ in range((rate or self.RATE) // 1000)] if keys else []
            while copies and copies[0][0] * 1000 <= ms:
                _, frame, src = copies.pop(0)
                self.waits[frame] = -self.now
                batch.insert(self.rng.randrange(len(batch) + 1), (frame, src))
            woken = self.woken
            if batch:
                self.intake.offer(batch)
            if self.woken != woken:
                self.due = self.now
            if self.flight and self.now >= self.busy:
                self.settled(mine)
            if not self.flight and self.now >= self.due:
                self.turn(turn_s)
            self.now = start + (ms + 1) / 1000
        return [self.waits[f] for f in mine]

    def turn(self, turn_s):
        self.flight = self.intake.take(32)
        self.busy = self.now + max(turn_s, len(self.flight) * CHECK_S)
        if not self.flight:
            self.due = float("inf") if not self.intake.waiting() else self.now + RETRY_S

    def settled(self, mine):
        for t in self.flight:
            ok = t.data in mine
            if ok and self.waits.get(t.data, 1) < 0:
                self.waits[t.data] += self.now
            if t.key is not None:
                self.checked[t.data[4:12], ok] += 1
                self.slots[t.data[4:12]] += t.budget is getattr(self.intake, "slice", None)
            k = self.kids.index(t.data[4:12]) if t.key is not None else None
            self.intake.settle(t, ok or k is not None and (t.data in self.old[k] or t.data in self.noop[k]), ok)
        self.flight, self.due = [], self.now if self.intake.waiting() else float("inf")

    def shares_a_lane(self, k, src) -> bool:
        """Whether ``src`` falls in a lane of the crowd that one of the flood's ports has too."""
        key = self.intake.keys[self.kids[k]]
        mine = key.source(src, self.now)
        return mine in key.crowd and any(key.source(udp(40_000 + p), self.now) is mine for p in range(self.PORTS))

    def salted(self, want, tries=60):
        """Intakes, one per salt, after a second of a flood of key 0 from PORTS ports, until ``want`` of them have put the
        newcomer's port (50 001) in a lane that the flood shares."""
        shared = 0
        for salt in range(tries):
            self.fresh()
            self.intake.keys[self.kids[0]].salt = salt
            self.play(0.3, keys=(0,))
            one = self.shares_a_lane(0, udp(50_001))
            shared += one
            yield one
            if shared == want:
                return
        self.fail(f"{shared} salts of {tries} made the newcomer share a lane: nothing was shown")

    def assertChecked(self, waits, within, why):
        late = [w for w in waits if not 0 <= w <= within + 0.002]     # two steps of the clock
        self.assertEqual(late, [], f"{why}: {len(late)} of {len(waits)} not checked within {within * 1000:.0f} ms")


class NewcomerTest(NewcomerCase):
    """The time to a newcomer's first check in a flood that goes on (#173's newcomer recovery; PLAN.md's B1-B3)."""

    def within(self, keys, sources=0, turn_s=TURN_S):
        """The bound: (S + 1) turns of the key's slot, one in M of them a demoted source's, when ``keys`` keys contend; the turn
        that runs when it comes, and its own."""
        return (sources + 1) * M / (M - 1) * keys / min(C_SLICE, 16 / turn_s) + RETRY_S + 2 * turn_s

    def test_a_flood_over_the_other_keys_does_not_delay_a_newcomer(self):
        """A guard, not a RED: the round-robin over keys already gives this (K picks of the general budget)."""
        for churn in (False, True):                             # fixed ports; and churned ones of the newcomer's own host
            for rate in (20_000, 100_000):
                self.fresh()
                self.play(0.3, keys=range(1, self.K), churn=churn, rate=rate)
                waits = self.play(0.4, keys=range(1, self.K), churn=churn, rate=rate,
                                  copies=[(0.0, item(self.sks[0], 1), udp(50_001))])
                self.assertChecked(waits, self.within(self.K), f"churn={churn}, {rate}/s")

    def test_ports_that_stay_and_forge_its_key_do_not_delay_a_newcomer_whatever_the_salt(self):
        """The fixed-40 companion of pass 3: 16 ports of its host have places of their own, 24 share salted lanes, and a
        newcomer whose lane one of them shares was verified as chance had it, up to 49 s late."""
        late = []
        for shared in self.salted(want=4):
            waits = self.play(0.4, keys=(0,), copies=[(0.0, item(self.sks[0], 1), udp(50_001))])
            late += [(shared, w) for w in waits if not 0 <= w <= self.within(1) + 0.002]
        self.assertEqual(late, [], "(lane shared, wait): checked later than the slice's one round, or not at all (< 0)")

    def test_newcomers_of_every_key_at_once_wait_for_one_round_of_the_keys(self):
        """Every key is forged from the 40 ports, and on every key a station starts at the same moment, in a shared lane."""
        self.play(1.0, keys=range(self.K))
        for k in range(self.K):                                  # in every key, a salt that makes the newcomer share
            key = self.intake.keys[self.kids[k]]
            key.salt = next(s for s in range(500) if (setattr(key, "salt", s), self.shares_a_lane(k, udp(50_001 + k)))[1])
        waits = self.play(0.6, keys=range(self.K),
                          copies=[(0.0, item(self.sks[k], 1), udp(50_001 + k)) for k in range(self.K)])
        self.assertChecked(waits, self.within(self.K), "a newcomer on each of 16 keys")

    def test_two_hundred_ports_that_stay_do_not_delay_a_newcomer_either(self):
        self.PORTS = 200
        self.play(1.0, keys=(0,))
        waits = self.play(0.4, keys=(0,), copies=[(0.0, item(self.sks[0], 1), udp(50_001))])
        self.assertChecked(waits, self.within(1), "200 ports")

    def test_sources_that_stay_cost_a_turn_each_however_many_start_with_it(self):
        """🍃's rule (#173 issuecomment-7138942171): S sources that forge K cost S checks of K's slot, once, and every one of them
        is then behind the newcomer: its first check comes within S + 1 turns, at any rate, though the flood starts with it."""
        for sources in (1, 4, 16, 40, PENDING - 1):
            for rate in (20_000, 100_000):
                with self.subTest(sources=sources, rate=rate):
                    self.PORTS = sources
                    self.fresh()
                    waits = self.play(0.5, keys=(0,), rate=rate, copies=[(0.0, item(self.sks[0], 1), udp(50_001))])
                    self.assertChecked(waits, self.within(1, sources), f"{sources} sources")

    def test_no_demotion_ends_or_is_lost_before_a_newcomers_turn(self):
        """🌫: the bound holds while the demotions are retained for at least the claimed wait. Newcomers come through three
        times the longest retention, so one meets whatever ends; and with as many sources as a key can hold demoted."""
        for sources in (16, CAP):
            with self.subTest(sources=sources):
                self.PORTS = sources
                self.stations(1)                                 # K = 1: the retention is at its shortest
                self.play(2.0 * (CAP + 1) / C_SLICE, keys=(0,))
                waits = self.play(3.5, keys=(0,), copies=[(0.041 * n, item(self.sks[0], n + 1), udp(50_001 + n)) for n in range(80)])
                self.assertChecked(waits, self.within(1, 16), f"{sources} sources that stay")

    def test_sources_that_replay_what_they_captured_are_behind_a_newcomer_too(self):
        """An old beacon verifies whenever it is replayed, and proves nothing about who sends it. Were it to clear a demotion,
        a source that sends one now and then would be untried for ever (an independent review's finding, at 2b15ed8: 63 of them
        delayed a station by 2.6 s at 16 keys)."""
        for sources in (63, 200):
            with self.subTest(sources=sources):
                self.PORTS = sources
                self.stations(1)
                self.play(2.0, keys=(0,), churn="replay")
                waits = self.play(3.5, keys=(0,), churn="replay",
                                  copies=[(0.041 * n, item(self.sks[0], n + 1), udp(50_001 + n)) for n in range(80)])
                self.assertChecked(waits, self.within(1, 16), f"{sources} sources that stay and replay")

    def test_replayed_records_keep_no_newcomer_waiting(self):
        """Items that verify, change nothing and make a record cost ten turns each: the turns of those that were tried."""
        for sources in (63, 200):
            with self.subTest(sources=sources):
                self.PORTS = sources
                self.stations(1)
                self.noop = [[item(sk, 10**6 + n) for n in range(sources)] for sk in self.sks]
                self.play(4.0, keys=(0,), churn="noop")
                waits = self.play(3.5, keys=(0,), churn="noop",
                                  copies=[(0.041 * n, item(self.sks[0], n + 1), udp(50_001 + n)) for n in range(80)])
                self.assertChecked(waits, self.within(1, 16), f"{sources} sources that stay and replay items")

    def test_junk_and_established_stations_take_no_turn_of_a_newcomers(self):
        """64 keys, 59 of them forged at, half the flood no frames at all, four stations established and singing: a newcomer of a
        key that nobody forges waits for a round of the keys, whatever is served between."""
        self.stations(64)
        for k in range(4):
            self.offer(item(self.sks[k], 1), src=udp(60_000 + k))
            self.serve(64)
        flood = range(4, 60)
        self.play(1.0, keys=flood, churn="junk")
        new = [(0.029 * n, item(self.sks[60 + n % 4], 1 + n), udp(50_001 + n)) for n in range(100)]
        sung = [(0.14 * n + 0.01 * k, item(self.sks[k], 2 + n), udp(60_000 + k)) for n in range(21) for k in range(4)]
        self.play(3.2, keys=flood, churn="junk", copies=[*new, *sung])
        for what, copies in (("newcomers", new), ("established", sung)):
            self.assertChecked([self.waits[f] for _, f, _ in copies], self.within(64), what)

    def test_sources_that_only_replay_hold_no_untried_place_for_good(self):
        """64 sources with an old beacon each, and 100 that forge, all of them staying: within what a key can hold demoted. Were
        a replay to leave its source untried, the 64 would have every untried place at every moment, and a newcomer whose
        lane the forgers fill would have none (22 of 80 never checked at K = 1, 51 of 80 at K = 16)."""
        for keys in (1, 16):
            with self.subTest(keys=keys):
                self.PORTS = 100
                self.stations(keys)
                self.old = [[beacon(sk, 1_000 + n) for n in range(PENDING)] for sk in self.sks]
                self.play(3.0, keys=range(keys), churn="hold")
                waits = self.play(3.5, keys=range(keys), churn="hold",
                                  copies=[(0.041 * n, item(self.sks[0], n + 1), udp(50_001 + n)) for n in range(80)])
                self.assertChecked(waits, self.within(keys, 16), "64 that replay, 100 that forge")

    def test_a_source_that_is_being_checked_takes_no_place_meanwhile(self):
        """In a long turn a source's next frame comes before the verdict on its last one. It would be untried again: with every
        turn saving, 200 sources that stay would cost a newcomer their turns over and over."""
        self.PORTS = 200
        self.stations(1)
        self.play(3.0, keys=(0,), turn_s=SAVE_TURN_S)
        waits = self.play(4.0, keys=(0,), turn_s=SAVE_TURN_S,
                          copies=[(0.15 * n, item(self.sks[0], n + 1), udp(50_001 + n)) for n in range(24)])
        self.assertChecked(waits, self.within(1, 1, SAVE_TURN_S), "200 sources that stay, a save in every turn")

    def test_more_sources_than_a_key_can_hold_demoted_are_outside_and_grow_nothing(self):
        """🌫: the exclusion. Nothing is claimed of the wait; what a key holds is bounded, and it still forgets nobody early."""
        self.PORTS = 4 * CAP
        self.play(1.5, keys=(0,), rate=100_000)
        key = self.intake.keys[self.kids[0]]
        self.assertEqual(len(key.marks), CAP)
        self.assertLessEqual(max(len(ring) for ring in key.slot.rings), PENDING)

    def test_a_demoted_source_that_sends_a_valid_frame_is_heard_while_untried_ones_keep_coming(self):
        """A failed frame is evidence against the frame, not against its source (🌫): demotion is a priority, not a ban. One turn
        in M of the key's slot is a demoted source's, and the valid frame clears it: no lasting penalty."""
        self.offer(forge(self.frames[0][0], 1), src=udp(50_001))
        self.serve(verified=lambda t: False)
        key = self.intake.keys[self.kids[0]]
        self.play(1.0, keys=(0,), churn="once")
        with self.intake._lock:
            key.mark(udp(50_001), self.now, failed=True)
        f = item(self.sks[0], 1)
        waits = self.play(0.5, keys=(0,), churn="once", copies=[(0.0, f, udp(50_001))])
        self.assertChecked(waits, M / C_SLICE + RETRY_S + TURN_S, "a demoted source's valid frame")
        self.assertNotEqual(key.tier(udp(50_001), self.now), intake.DEMOTED)
        self.assertIn(udp(50_001), key.known)

    def test_a_source_that_was_tried_and_did_not_fail_is_heard_in_a_churned_flood_of_its_key(self):
        """A station that lost its place, or is heard again after a restart of the daemon, whose frames its key's flood would
        otherwise leave to chance for ever: one turn in M is for those that were tried, however many untried ones keep coming
        and however many that failed wait."""
        key = self.intake.keys[self.kids[0]]
        self.play(1.0, keys=(0,), churn=True, rate=100_000)
        with self.intake._lock:
            for n in range(100):
                key.mark(udp(45_000 + n), self.now, failed=True)
            key.mark(udp(50_001), self.now, failed=False)
        f = item(self.sks[0], 1)
        waits = self.play(0.5, keys=(0,), churn=True, rate=100_000, copies=[(0.0, f, udp(50_001))])
        self.assertChecked(waits, 2 * M / C_SLICE + RETRY_S + 2 * TURN_S, "tried, and not failed")

    def test_what_waits_in_the_slot_survives_whatever_comes_after_it(self):
        """🌫: a bound on rounds is a deadline only if the newcomer's frame is there when its turn comes."""
        f = item(self.sks[0], 1)
        self.offer(*[forge(self.frames[0][0], n) for n in range(4)], src=udp(40_000))
        self.offer(f, src=udp(50_001))
        for n in range(20_000):
            self.offer(forge(self.frames[0][n % 2], 10**6 + n), src=udp(1_024 + n % 60_000, 20))
        served = [t.data for t in self.intake.take(32) if t.budget is self.intake.slice]
        self.assertIn(f, served)

    def test_every_key_gets_its_turns_of_the_slice_under_a_full_flood(self):
        """🌫: each key actually receives its service. Every key forged at from churned sources: no key is served more than
        another, and together they have what the slice promises; with a durable save in every turn too, where it is half of each
        turn's places that decides; and one key alone has all of it."""
        for keys, turn_s, least in ((range(self.K), 0.0, C_SLICE), (range(self.K), SAVE_TURN_S, 16 / SAVE_TURN_S),
                                    ((0,), 0.0, C_SLICE), ((0,), SAVE_TURN_S, 16 / SAVE_TURN_S)):
            with self.subTest(keys=len(keys), turn_s=turn_s):
                self.fresh()
                self.play(0.5, keys=keys, churn="once", rate=100_000, turn_s=turn_s)
                before = Counter(self.slots)
                self.play(2.0, keys=keys, churn="once", rate=100_000, turn_s=turn_s)
                got = [self.slots[self.kids[k]] - before[self.kids[k]] for k in keys]
                self.assertGreaterEqual(sum(got), 0.9 * 2.0 * min(C_SLICE, least))
                self.assertLessEqual(max(got) - min(got), 0.1 * max(got) + 2, got)

    def test_a_churned_forgery_of_its_own_key_stays_a_lottery_with_a_slightly_better_chance(self):
        """The honest limit: distinct forgeries of the newcomer's own key, each from a port of its own, look like it in
        everything that is read before the signature. What is checked of them a second is bounded below by what the key's
        strangers and the slice have, and above, so no copy's chance is better than that over the flood's rate."""
        self.play(1.0, keys=(0,), churn=True)                    # the buckets' bursts are spent
        before = self.checked.total()
        self.play(4.0, keys=(0,), churn=True)
        done = (self.checked.total() - before) / 4.0
        self.assertGreater(done, intake.SOURCE_RATE + 0.3 * C_SLICE)
        self.assertLessEqual(done, 1.01 * (intake.SOURCE_RATE + C_SLICE))

    def test_what_comes_to_nothing_is_bounded_as_before_and_the_slice_by_itself(self):
        """Every key forged, every slot contended, for two seconds: the daemon's checks stay within 2 000 a second."""
        for churn in (False, True):
            self.fresh()
            self.play(0.5, keys=range(self.K), churn=churn, rate=100_000)
            before = self.checked.total()
            self.play(2.0, keys=range(self.K), churn=churn, rate=100_000)
            self.assertLessEqual(self.checked.total() - before, 2.0 * C_ALL + 250)
        spare = getattr(intake, "SLICE_RATE", 0.0)
        self.assertEqual((intake.CHECK_RATE, getattr(intake, "STRANGE_RATE", intake.CHECK_RATE) + spare, spare), (C_ALL, C_ALL, C_SLICE))

    def test_established_sources_are_served_as_before_while_every_slot_is_contended(self):
        """A guard: a known source of each key, its key forged at from churned ports, is served within a round of the keys and
        its own two turns."""
        for k, sk in enumerate(self.sks):
            self.offer(item(sk, 1), src=udp(60_000 + k))
        self.serve(64)
        self.play(0.5, keys=range(self.K), churn=True, rate=100_000)
        waits = self.play(0.5, keys=range(self.K), churn=True, rate=100_000,
                          copies=[(0.1 * n, item(self.sks[k], 2 + n), udp(60_000 + k)) for n in range(4) for k in range(self.K)])
        self.assertChecked(waits, 4 * self.K / (C_ALL - C_SLICE) + RETRY_S + TURN_S, "established")

    def test_the_slice_is_paid_for_by_strangers_and_not_by_established_stations(self):
        """One established station among 64 keys that are all forged at, singing seven items a second: it has its turn of each
        fourth round of the keys, which is in time while a round costs what it did."""
        self.stations(64)
        self.offer(item(self.sks[0], 1), src=udp(60_000))
        self.serve(64)
        self.play(0.5, keys=range(64), churn=True, rate=100_000)
        waits = self.play(5.0, keys=range(64), churn=True, rate=100_000,
                          copies=[(0.14 * n, item(self.sks[0], 2 + n), udp(60_000)) for n in range(34)])
        self.assertChecked(waits, 4 * 64 / C_ALL + RETRY_S + 2 * TURN_S, "an established station")

    def test_a_key_that_is_not_listed_never_reaches_the_slice(self):
        stranger = Ed25519PrivateKey.generate()
        f = item(stranger, 1)
        for n in range(2_000):
            self.offer(forge(f, n), src=udp(40_000 + n))
        self.assertEqual((len(self.intake.unlisted.ready), self.intake.stats()["queued"]), (intake.UNLISTED_DEPTH, intake.UNLISTED_DEPTH))


class SlotTest(IntakeCase):
    """What a key has waiting for the slice, rule by rule."""

    TIERS = "untried", "tried", "demoted"

    def setUp(self):
        super().setUp()
        self.key = self.intake.keys[KID_A]
        self.offer(*[forge(item(A, 1), n) for n in range(4)], src=THERE)       # so that others wait in the stream

    def waits(self, ring="untried", key=None):
        return [claim.entry[0] for claim in (key or self.key).slot.rings[self.TIERS.index(ring)].values()]

    def demote(self, *srcs, failed=True):
        with self.intake._lock:
            for src in srcs:
                self.key.mark(src, self.now, failed)

    def tier(self, src):
        return self.TIERS[self.key.tier(src, self.now)]

    def taken(self, frame, limit):
        """The turn that takes ``frame``; what comes before it fails."""
        for _ in range(1_000):
            got = self.intake.take(limit)
            if frame in [t.data for t in got]:
                return got
            for t in got:
                self.intake.settle(t, False, False)
        self.fail("it never came")

    def test_a_source_that_waits_alone_queues_as_ever(self):
        f = item(B, 1)
        self.offer(f, src=HERE)
        self.assertEqual((self.waits(key=self.intake.keys[KID_B]), self.serve(8).count(f)), ([], 1))

    def test_each_newcomer_has_one_place_and_they_are_served_in_the_order_they_came(self):
        frames = [item(A, n + 1) for n in range(3)]
        for n, f in enumerate(frames):
            self.offer(f, src=addr(20 + n))
        self.assertEqual((self.waits(), self.intake.stats()["queued"]), (frames, 7))
        served = self.serve(32, verified=lambda t: t.data in frames)
        self.assertEqual((served[-3:], len(served), self.refused), (frames, 7, {}))

    def test_a_source_that_has_a_place_queues_the_rest(self):
        frames = [item(A, n + 1) for n in range(5)]
        self.offer(*frames, src=HERE)
        self.assertEqual(self.waits(), frames[:1])
        self.assertEqual([d for d in self.serve(32) if d in frames], [*frames[1:], frames[0]])

    def test_a_lane_of_the_crowd_is_nobodys_own(self):
        """A port that shares a lane with another's datagrams is not alone, though no other lane of the stream is open."""
        for n in range(intake.STRANGERS_PER_HOST):             # the host's places are taken, by what waits in another stream
            self.offer(item(B, n + 1), src=udp(40_000 + n))
        key = self.intake.keys[KID_B]
        with self.intake._lock:
            lanes = {port: key.source(udp(port), self.now) for port in range(50_000, 50_400)}
        one, other = next((a, b) for a in lanes for b in lanes if a < b and lanes[a] is lanes[b])
        self.offer(*[forge(beacon(B, 1), n) for n in range(3)], src=udp(one))
        f = beacon(B, 2)
        self.offer(f, src=udp(other))
        self.assertIn(f, self.waits(key=key))

    def test_a_copy_of_what_waits_there_is_one(self):
        f = item(A, 1)
        self.offer(f, f, f, src=HERE)
        self.assertEqual((self.waits(), self.intake.copied, self.intake.stats()["queued"]), ([f], 2, 5))

    def test_its_places_are_bounded_and_whoever_finds_none_queues(self):
        for n in range(3 * intake.SLOT_MAX):
            self.offer(item(A, n + 1), src=udp(40_000 + n))
        self.demote(*[udp(50_000 + n) for n in range(3 * intake.SLOT_MAX)])
        for n in range(3 * intake.SLOT_MAX):
            self.offer(item(A, 1_000 + n), src=udp(50_000 + n))
        self.assertEqual([len(self.waits(r)) for r in self.TIERS], [intake.SLOT_MAX, 0, intake.SLOT_MAX])
        self.assertEqual(self.intake.stats()["queued"] + sum(self.refused.values()), 4 + 6 * intake.SLOT_MAX)

    def test_a_source_whose_frame_failed_waits_behind_those_that_were_not_tried(self):
        self.offer(bad := forge(item(A, 1), 100), src=HERE)
        self.assertEqual(self.serve(2, verified=lambda t: False)[-1], bad)
        late, untried = item(A, 2), [item(A, 10 + n) for n in range(3)]
        self.offer(late, src=HERE)
        self.assertEqual((self.waits(), self.waits("demoted")), ([], [late]))
        for n, f in enumerate(untried):
            self.offer(f, src=addr(20 + n))
        self.key.slot.turns = 0
        self.assertEqual(self.serve(8, verified=lambda t: t.data in (late, *untried))[-4:], [*untried, late])

    def test_a_demoted_source_has_one_turn_in_m_and_those_behind_it_the_rest(self):
        """A failed frame is evidence against the frame, and no proof against its source: a priority, not a ban."""
        self.demote(*[addr(60 + n) for n in range(3)])
        for n in range(12):
            self.offer(item(A, 100 + n), src=addr(20 + n))
        for n in range(3):
            self.offer(item(A, 200 + n), src=addr(60 + n))
        self.key.slot.turns = 0
        served = [t.addr for t in self.intake.take(24) if t.budget is self.intake.slice]
        self.assertEqual([n for n, a in enumerate(served) if a[0] in {addr(60 + k)[0] for k in range(3)}],
                         [intake.SLOT_M - 1, 2 * intake.SLOT_M - 1, 3 * intake.SLOT_M - 1])

    def test_only_a_new_frame_clears_its_source(self):
        """🍃 (#173 issuecomment-7140567401): a valid signature alone doesn't. A replayed old beacon verifies for ever, and what
        resurfaced after a restart is kept and is not new: the demotion stays in place."""
        for kept, fresh in ((True, True), (True, False), (False, False)):
            src = addr(70 + 2 * kept + fresh)
            self.demote(src)
            self.assertEqual(self.tier(src), "demoted")
            self.offer(*[forge(item(A, 1), 200 + n) for n in range(4)], src=THERE)
            self.offer(f := item(A, 10 + 2 * kept + fresh), src=src)
            (t,) = [t for t in self.intake.take(32) if t.data == f]
            if kept:
                self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000, fresh)
            self.intake.settle(t, True, fresh)
            self.assertEqual(self.tier(src), "tried" if fresh else "demoted", (kept, fresh))

    def test_a_source_whose_replay_changed_nothing_is_no_longer_untried(self):
        """It is no failure. But the first places are the untried sources', and it has been tried: 🍃's second tier (7142734748)."""
        self.offer(f := beacon(A, 1), src=HERE)
        (t,) = [t for t in self.intake.take(32) if t.data == f]
        self.intake.settle(t, True, False)
        self.offer(*[forge(item(A, 1), 300 + n) for n in range(4)], src=THERE)
        self.offer(g := item(A, 2), src=HERE)
        self.assertEqual((self.tier(HERE), self.waits(), self.waits("tried")), ("tried", [], [g]))

    def test_the_tiers_come_in_their_order(self):
        """Untried first, in the order they came; those that were tried and did not fail behind them, in turn; a source whose frame
        failed behind those. Of a key's turns one in M is for one that was tried, the two kinds in turn."""
        self.demote(*[addr(60 + n) for n in range(4)])
        self.demote(*[addr(80 + n) for n in range(4)], failed=False)
        kind = {}
        for n in range(4):
            for first, name in ((80, "t"), (60, "d"), (20, "u"), (40, "u")):
                self.offer(f := item(A, 10 * first + n), src=addr(first + n))
                kind[f] = name
        self.key.slot.turns = 0
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now     # the queues serve nothing
        self.assertEqual("".join(kind[t.data] for t in self.intake.take(32)), "uuud" "uuut" "uutd" "ttdd")

    def test_one_that_replays_all_the_time_keeps_no_other_of_its_tier_waiting(self):
        """In turn, not the latest first (🍃's first condition)."""
        noisy, quiet = addr(60), addr(61)
        self.demote(noisy, quiet, failed=False)
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now
        self.offer(beacon(A, 1), src=noisy)
        self.offer(q := item(A, 2), src=quiet)
        for n in range(5):
            self.offer(beacon(A, 10 + n), src=noisy)
            got = self.intake.take(1)
            for t in got:
                self.intake.settle(t, True, False)
            if got[0].data == q:
                break
        self.assertLessEqual(n, 1)

    def test_no_replay_moves_a_source_up_and_only_a_new_frame_does(self):
        """🍃's second condition. From the third tier to the second, never to the first; a replay from the first to the second."""
        with self.intake._lock:
            self.key.mark(HERE, self.now, failed=True)
            self.assertEqual(self.tier(HERE), "demoted")
            self.key.mark(HERE, self.now, failed=False)
            self.assertEqual(self.tier(HERE), "demoted")
            self.key.admit(HERE, self.now)
            self.assertEqual(self.tier(HERE), "tried")
            self.key.admit(HERE, self.now)
            self.assertEqual(self.tier(HERE), "tried")
            self.key.mark(THERE, self.now, failed=False)
            self.assertEqual(self.tier(THERE), "tried")

    def test_a_replay_keeps_no_demotion_alive(self):
        """It leaves it as it is: the failure is as old as it is."""
        self.demote(HERE)
        self.now += self.intake.retain - 0.1
        self.demote(HERE, failed=False)
        self.assertEqual(self.tier(HERE), "demoted")
        self.now += 0.2
        self.assertEqual(self.tier(HERE), "tried")

    def test_a_source_that_lost_its_known_place_has_been_tried(self):
        for n in range(intake.KNOWN_MAX + 1):
            self.offer(item(A, 10 + n), src=addr(50 + n))
            self.serve(32, verified=lambda t: t.addr == addr(50 + n))
        self.assertEqual((self.tier(addr(50)), self.tier(addr(51))), ("tried", "untried"))

    def test_what_waits_in_the_slot_waits_in_its_lane_as_well_and_is_served_once(self):
        """So the slot is never a worse place to wait than the queues are: whichever comes first serves it."""
        for spent in (True, False):
            with self.subTest(slice_spent=spent):
                self.setUp()
                f = item(A, 1)
                self.offer(f, src=HERE)
                if spent:
                    self.intake.slice.tokens, self.intake.slice.at = 0.0, self.now
                self.assertEqual((self.waits(), self.intake.stats()["queued"]), ([f], 5))
                served = self.serve(32, verified=lambda t: t.data == f)
                self.assertEqual((served.count(f), len(served), self.waits(), self.intake.stats()["queued"]), (1, 5, [], 0))
                self.assertFalse(self.intake.waiting())

    def test_what_the_queues_refuse_or_shed_still_waits_in_the_slot_and_is_not_counted_lost(self):
        self.offer(*[forge(item(A, 1), 100 + n) for n in range(2 * intake.STRANGER_POOL)], src=THERE)
        frames = [item(A, n + 1) for n in range(3 * intake.STRANGER_POOL)]
        lost = sum(self.refused.values())
        self.offer(frames[0], src=HERE)                        # sheds one of THERE's, and has a lane and a place
        self.offer(*frames[1:], src=HERE)                      # its lane fills up, and refuses
        for n in range(40):
            self.offer(forge(item(A, 1), 5_000 + n), src=addr(100 + n))       # others take its lane's places back
        self.assertEqual(self.waits()[0], frames[0])
        s = self.intake.stats()
        self.assertEqual(s["read"], s["repeats"] + s["copies"] + s["verified"] + s["unverified"] + sum(s["refused"].values()) + s["queued"])
        self.assertGreater(sum(self.refused.values()), lost)
        self.assertIn(frames[0], self.serve(2, verified=lambda t: t.data == frames[0]))

    def test_what_a_source_has_waiting_follows_it(self):
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.demote(HERE, failed=False)
        self.assertEqual([self.waits(r) for r in self.TIERS], [[], [f], []])
        self.demote(HERE)
        self.assertEqual([self.waits(r) for r in self.TIERS], [[], [], [f]])
        with self.intake._lock:
            self.key.admit(HERE, self.now)
        self.assertEqual([self.waits(r) for r in self.TIERS], [[], [f], []])
        self.demote(HERE)
        self.now += self.intake.retain                         # the marks have ended: its next copy finds it so
        self.offer(item(A, 2), src=HERE)
        self.assertEqual([self.waits(r) for r in self.TIERS], [[f], [], []])

    def test_marks_are_a_bounded_number_the_oldest_forgotten_first_and_kept_for_the_longest_wait(self):
        self.demote(*[udp(40_000 + n) for n in range(3 * intake.MARKS_MAX)])
        self.assertEqual(list(self.key.marks), [udp(40_000 + n) for n in range(2 * intake.MARKS_MAX, 3 * intake.MARKS_MAX)])
        for keys in (1, 16, 64):
            self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(Ed25519PrivateKey.generate()),
                                                           frozenset({1}), ()) for n in range(keys)]))
            wait = (intake.MARKS_MAX + 1) * intake.SLOT_M / (intake.SLOT_M - 1) * keys / intake.SLICE_RATE
            self.assertGreaterEqual(self.intake.retain, wait + RETRY_S + TURN_S)

    def test_a_known_source_is_not_demoted(self):
        self.offer(item(A, 2), src=HERE)
        self.serve()
        self.offer(forge(item(A, 1), 9), src=HERE)             # somebody's, from its address and port
        self.serve(verified=lambda t: False)
        self.assertEqual(self.tier(HERE), "untried")

    def test_the_slots_come_after_the_queues_and_have_half_a_turns_places_of_their_own(self):
        sks = [Ed25519PrivateKey.generate() for _ in range(24)]
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(sks)]))
        first = {sk: item(sk, 1) for sk in sks}
        for sk in sks:
            self.offer(*[forge(item(sk, 1), n) for n in range(8)], src=THERE)
            self.offer(first[sk], src=HERE)
        served = self.serve(32, verified=lambda t: t.data in first.values())
        slots = [n for n, d in enumerate(served) if d in first.values()]
        self.assertEqual((len(served), slots), (48, list(range(32, 48))))
        self.assertLessEqual(set(first.values()), set(served) | set(self.serve(32)))

    def test_what_the_queues_leave_of_a_turn_is_the_slots(self):
        """Frames that no lane took wait in the slot only: 40 of them, and the queues are empty."""
        self.offer(*[forge(item(A, 1), 100 + n) for n in range(2 * intake.STRANGER_POOL)], src=THERE)
        for n in range(40):
            self.offer(item(A, n + 1), src=addr(20 + n))
        key = self.key
        with self.intake._lock:                                # every lane loses what it holds, as when its source is displaced
            for s in key.streams.values():
                for source in list(s.lanes):
                    s.known, s.strange, s.pool = deque([*s.known, *s.strange]), deque(), 0
                    key.lost(s.drop(source))
                    key.ready.clear()
            self.intake._ready.clear()
        self.assertEqual((self.intake.stats()["queued"], self.intake.waiting()), (40, True))
        self.assertEqual(len(self.intake.take(32)), 40)

    def test_no_queue_full_of_copies_keeps_the_slots_from_their_places(self):
        """The same forgery from every port: a turn looks at a bounded number of places, and the slots' come first."""
        for n in range(intake.STRANGERS_MAX):
            self.offer(*[forge(item(A, 1), k) for k in range(4)], src=addr(100 + n))
        self.demote(*[addr(100 + n) for n in range(intake.STRANGERS_MAX)])
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.assertIn(f, self.serve(8, verified=lambda t: t.data == f))

    def test_what_the_queues_hold_of_a_stations_buckets_keeps_no_slot_waiting(self):
        """A ticket of a queue holds a token of its stream until it is settled, and there are only 16 of a key's beacons."""
        self.offer(*[forge(beacon(A, 1), n) for n in range(60)], src=THERE)
        f = beacon(A, 1)
        self.offer(f, src=HERE)
        self.assertIn(f, self.serve(32, verified=lambda t: t.data == f))

    def test_the_keys_take_turns_however_many_wait_in_one_of_them(self):
        for n in range(20):
            self.offer(item(A, n + 1), src=addr(20 + n))
        self.offer(*[forge(item(B, 1), n) for n in range(4)], src=THERE)
        late = [item(B, n + 1) for n in range(3)]
        for n, f in enumerate(late):
            self.offer(f, src=addr(50 + n))
        served = [t.data for t in self.intake.take(32) if t.budget is self.intake.slice]
        self.assertEqual([served.index(f) for f in late], [1, 3, 5])

    def test_a_key_whose_station_is_over_its_rate_keeps_its_turn_of_the_slots(self):
        sks = [Ed25519PrivateKey.generate() for _ in range(3)]
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(sks)]))
        frames = [item(sk, 1) for sk in sks]
        for f in frames:
            self.offer(*[forge(f, 90 + n) for n in range(4)], src=THERE)
            self.offer(f, src=HERE)
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now      # the queues serve nothing
        bucket = self.intake.keys[frames[0][4:12]].streams[stream_id("chatter")].bucket
        bucket.tokens, bucket.at = 0.0, self.now
        self.assertEqual(self.serve(1), [frames[1]])
        bucket.tokens = 2.0
        self.assertEqual([self.serve(1), self.serve(1)], [[frames[0]], [frames[2]]])

    def test_a_turn_of_one_still_comes_to_it(self):
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.assertIn(f, [d for _ in range(5) for d in self.serve(1)])
        self.assertFalse(self.intake.waiting())

    def test_a_new_frame_costs_the_slice_nothing_and_a_forgery_one(self):
        f = item(A, 1)
        self.offer(f, src=HERE)
        (t,) = [t for t in self.intake.take(2) if t.data == f]
        self.assertEqual(self.intake.slice.tokens, intake.SLICE_BURST - 1)
        checks = self.intake.checks.tokens
        self.intake.settle(t, True, True)
        self.assertEqual((self.intake.slice.tokens, self.intake.checks.tokens), (intake.SLICE_BURST, checks))
        self.offer(forge(f, 99), src=addr(30))
        (t,) = [t for t in self.intake.take(2) if t.data == forge(f, 99)]
        self.intake.settle(t, False, False)
        self.assertEqual(self.intake.slice.tokens, intake.SLICE_BURST - 1)
        self.assertEqual(self.intake.stats()["reserved"], 2)

    def test_when_the_slice_is_spent_the_slots_wait_and_the_loop_comes_back_for_them(self):
        for bucket in (self.intake.slice, self.intake.checks):
            bucket.tokens, bucket.at = -0.5, self.now
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.assertEqual((self.serve(32), self.waits()), ([], [f]))
        self.assertTrue(self.intake.waiting())
        self.intake.checks.tokens = -1e9
        self.now += 1.501 / intake.SLICE_RATE
        self.assertEqual(self.serve(32), [f])

    def test_a_record_that_changes_nothing_costs_turns_of_its_keys_tried_sources_only(self):
        """A verified ITEM that is not new makes a record, so from a queue it costs its sender ten checks. From a slot, what its
        key's tried sources have waiting waits for nine more turns: neither an untried one nor another key does."""
        self.offer(*[forge(item(B, 1), n) for n in range(4)], src=THERE)
        self.offer(item(A, 1), src=HERE)
        (t,) = [t for t in self.intake.take(2) if t.budget is self.intake.slice]
        self.intake.settle(t, True, False)
        a, b, new = item(A, 2), item(B, 2), item(A, 3)
        self.offer(*[forge(item(A, 1), 50 + n) for n in range(4)], src=THERE)
        self.offer(a, src=HERE)                                # the same source again
        self.offer(b, src=addr(32))
        self.offer(new, src=addr(33))
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now     # so that the queues serve nothing
        self.assertEqual((set(self.serve(32)), self.waits("tried")), ({b, new}, [a]))
        self.now += intake.SLICE_PAUSE_S
        self.assertEqual(self.serve(32), [a])

    def test_whoever_sends_the_bytes_that_fail_has_been_tried(self):
        bad = forge(item(A, 1), 70)
        for n in range(3):
            self.offer(bad, src=addr(40 + n))
        self.assertEqual(self.serve(32, verified=lambda t: False).count(bad), 1)
        self.assertEqual([self.tier(addr(40 + n)) for n in range(3)], ["demoted"] * 3)

    def test_the_same_bytes_again_in_a_lane_while_they_wait_in_the_slot_are_a_copy(self):
        """Its lane lost the first, its source has become known since, and sends it again."""
        f = item(A, 1)
        self.offer(f, src=HERE)
        stream = self.key.streams[stream_id("chatter")]
        with self.intake._lock:
            for lane in list(stream.strange):
                if lane.source is self.key.strangers[HERE]:
                    stream.remove(lane.source, f_entry := lane.queue[0])
                    self.key.lost([f_entry])
            self.key.know(HERE)
        self.offer(f, src=HERE)
        self.intake.slice.tokens, self.intake.slice.at = -100.0, self.now
        self.assertEqual(self.serve(32, verified=lambda t: t.data == f).count(f), 1)
        s = self.intake.stats()
        self.assertEqual(s["read"], s["repeats"] + s["copies"] + s["verified"] + s["unverified"] + sum(s["refused"].values()) + s["queued"])

    def test_every_one_of_them_costs_turns_however_many_come_in_a_turn(self):
        for n in range(3):
            self.offer(item(A, n + 1), src=addr(40 + n))
        got = [t for t in self.intake.take(32) if t.budget is self.intake.slice]
        for t in got:
            self.intake.settle(t, True, False)
        self.assertAlmostEqual(self.key.slot.due, self.now + len(got) * intake.SLICE_PAUSE_S)
        self.assertEqual(len(got), 3)

    def test_an_old_beacon_costs_no_turns(self):
        self.offer(beacon(A, 9), beacon(A, 8), src=THERE)
        self.offer(beacon(A, 1), src=HERE)
        (t,) = [t for t in self.intake.take(2) if t.budget is self.intake.slice]
        self.intake.settle(t, True, False)
        self.assertLessEqual(self.key.slot.due, self.now)

    def test_it_is_held_to_the_keys_and_streams_rates(self):
        for which in (lambda: self.key.bucket, lambda: self.key.streams[stream_id("chatter")].bucket):
            bucket = which()
            f = item(A, 1 + int(bucket.rate))
            self.offer(f, src=addr(40 + int(bucket.rate)))
            bucket.tokens, bucket.at = 0.0, self.now
            self.assertNotIn(f, self.serve(32, verified=lambda t: False))
            self.assertEqual(self.waits(), [f])
            self.now += 1 / bucket.rate + 0.001
            self.assertIn(f, self.serve(32, verified=lambda t: t.data == f))
            self.assertLess(bucket.tokens, 1.0)                # its station paid
            self.setUp()

    def test_a_stream_over_its_rate_holds_up_no_other_stream_of_the_key(self):
        f, b = item(A, 1), beacon(A, 1)
        self.offer(f, src=addr(40))
        self.offer(*[forge(b, n) for n in range(2)], src=THERE)
        self.offer(b, src=addr(41))
        bucket = self.key.streams[stream_id("chatter")].bucket
        bucket.tokens, bucket.at = 0.0, self.now
        self.assertEqual([t.data for t in self.intake.take(2) if t.budget is self.intake.slice], [b])
        self.assertEqual(self.waits(), [f])

    def test_a_slot_that_serves_the_last_of_what_waits_takes_the_key_out_of_the_turns(self):
        self.serve(8, verified=lambda t: False)
        f = item(A, 1)
        self.offer(forge(f, 9), src=THERE)
        self.offer(f, src=HERE)
        self.assertEqual(len(self.serve(1, verified=lambda t: False)), 1)      # the other's, and it is left
        self.assertEqual((self.waits(), len(self.key.ready)), ([f], 1))
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now      # the queues serve nothing
        (t,) = self.intake.take(4)
        self.assertEqual((t.data, list(self.key.ready), list(self.intake._ready), self.intake.waiting()), (f, [], [], False))

    def test_what_waits_for_its_streams_rate_keeps_its_turn(self):
        frames = [item(A, n + 1) for n in range(6)]
        for n, f in enumerate(frames):
            self.offer(f, src=addr(40 + n))
        bucket = self.key.streams[stream_id("chatter")].bucket
        bucket.tokens, bucket.at = 0.0, self.now
        self.serve(8, verified=lambda t: False)
        self.assertEqual(self.waits(), frames)

    def test_the_first_in_it_wakes_the_loop_while_the_slice_can_pay(self):
        """Where no lane was opened, which would wake it: the source's own was full."""
        for spent in (False, True):
            self.setUp()
            self.serve(32, verified=lambda t: False)
            self.offer(*[item(A, n + 1) for n in range(200)], src=HERE)          # alone: in its lane only
            self.offer(*[forge(item(A, 1), n) for n in range(300)], src=THERE)
            self.serve(1, verified=lambda t: False)
            while self.key.slot:
                self.intake.settle(self.intake.take(2)[-1], False, False)
            self.intake.slice.tokens, self.woken = -50.0 if spent else 10.0, 0
            self.offer(f := item(A, 999), src=HERE)
            self.assertEqual((self.waits() + self.waits("demoted"), self.woken), ([f], int(not spent)))

    def test_a_frame_that_was_accepted_while_it_waited_there_costs_nothing(self):
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.offer(f, src=addr(34))                                  # the same bytes, from two sources
        (t,) = [t for t in self.intake.take(2) if t.data == f]
        self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000)
        self.intake.settle(t, True, True)
        self.serve(32, verified=lambda t: False)
        self.offer(f, src=addr(35))
        self.assertEqual((self.waits(), self.intake.repeated + self.intake.copied), ([], 2))
        before = self.intake.repeated
        self.offer(*[forge(item(A, 1), 50 + n) for n in range(4)], src=THERE)
        self.offer(g := item(A, 2), src=HERE)
        self.offer(*[forge(g, n) for n in range(2)], src=addr(36))
        self.offer(g, src=addr(37))                                  # waits in the slot while a copy is accepted elsewhere
        (t,) = self.taken(g, 1)
        self.intake.remember(t, (KID_A, 5, 0, 2), runner.now_ms() + 60_000)
        self.intake.settle(t, True, True)
        self.assertEqual((self.serve(32, verified=lambda t: False).count(g), self.waits()), (0, []))
        self.assertGreater(self.intake.repeated, before)

    def test_a_repeat_or_a_copy_out_of_a_slot_costs_no_token_and_is_no_check(self):
        f = item(A, 1)
        self.offer(f, src=HERE)
        self.offer(f, src=addr(34))                                  # the same bytes from two sources: one verdict
        got = [t for t in self.intake.take(32) if t.budget is self.intake.slice]
        self.assertEqual((len(got), self.intake.slice.tokens, self.intake.copied), (1, intake.SLICE_BURST - 1, 1))
        self.offer(*[forge(f, 60 + n) for n in range(4)], src=THERE)
        self.offer(f, src=addr(35))                                  # comes while it is being verified
        self.assertEqual(self.waits(), [f])
        self.intake.remember(got[0], (KID_A, 5, 0, 1), runner.now_ms() + 60_000)
        self.intake.settle(got[0], True, True)
        self.assertEqual(self.serve(32, verified=lambda t: False).count(f), 0)
        self.assertEqual((self.intake.slice.tokens, self.intake.repeated, self.intake.stats()["reserved"]), (intake.SLICE_BURST, 1, 1))

    def test_a_frame_that_resurfaced_costs_its_key_no_turns(self):
        """It is kept, so it can be that once: a station that goes on after the daemon's restart must not wait for it."""
        self.offer(item(A, 1), src=HERE)
        (t,) = [t for t in self.intake.take(32) if t.budget is self.intake.slice]
        self.intake.remember(t, (KID_A, 5, 0, 1), runner.now_ms() + 60_000, fresh=False)
        self.intake.settle(t, True, False)
        self.assertLessEqual(self.key.slot.due, self.now)

    def test_more_keys_than_a_turn_has_places_for_are_served_in_turn(self):
        sks = [Ed25519PrivateKey.generate() for _ in range(40)]
        self.intake = self.make(Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
                                          for n, sk in enumerate(sks)]))
        frames = [item(sk, 1) for sk in sks]
        order = []
        for round_ in range(3):
            for k, f in enumerate(frames):
                self.offer(*[forge(f, 1_000 * round_ + n) for n in range(8)], src=THERE)
                self.offer(forge(f, 50_000 + round_), src=udp(40_000 + k, 2 + round_))
        self.intake.slice.tokens, self.intake.slice.at = 0.0, self.now
        self.intake.checks.tokens, self.intake.checks.at = -1e9, self.now     # so that the queues serve nothing
        for _ in range(100):
            self.now += 2.001 / intake.SLICE_RATE                    # two tokens a turn
            for t in self.intake.take(8):
                if t.budget is self.intake.slice:
                    order.append(t.data[4:12])
                self.intake.settle(t, False, False)
        kids = [f[4:12] for f in frames]
        for n in range(3):
            self.assertEqual(sorted(order[40 * n:40 * n + 40]), sorted(kids), f"round {n} of the keys")

    def test_a_displaced_source_keeps_what_waits_in_the_slot_and_the_rest_is_counted(self):
        """A source that has a place there becomes known by another frame, and is displaced with no room to keep it apart: what
        it had queued is gone and counted, but for what waits in the slot."""
        frames = [item(A, n + 1) for n in range(4)]
        self.offer(*frames, src=HERE)
        with self.intake._lock:
            self.key.know(HERE)
        for n in range(intake.STRANGERS_MAX + 1):                    # every place in the table has something waiting
            self.offer(*[forge(item(A, 1), 100 * n + k) for k in range(2)], src=addr(100 + n))
        before = self.intake.stats()["queued"]
        with self.intake._lock:
            lost = [self.key.know(addr(50 + n)) for n in range(intake.KNOWN_MAX)]
        self.assertEqual((lost, self.waits("tried")), ([0] * (intake.KNOWN_MAX - 1) + [3], [frames[0]]))
        self.assertEqual(self.intake.stats()["queued"], before - 3)
        self.assertNotIn(HERE, (*self.key.known, *self.key.strangers))
        served = []
        for _ in range(20):
            self.now += 1
            served += self.serve(32, verified=lambda t: False)
        self.assertEqual((served.count(frames[0]), self.intake.stats()["queued"]), (1, 0))


HORIZON_S = 60.0        # the newcomer-recovery report's PLAN.md: the lease of a known place


class EchoTest(IntakeCase):
    """Copies of a station's frames that come after its own, from sources that have no key: they take nothing from it."""

    def setUp(self):
        super().setUp()
        self.offer(beacon(A, 1), src=HERE)
        self.accept()
        self.key = self.intake.keys[KID_A]

    def turns(self, frame):
        """Until ``frame`` is accepted. Returns whose copy was."""
        who = None
        for _ in range(100):
            self.now += 0.02
            for t in self.intake.take(32):
                ok = t.data == frame
                if ok:
                    who = t.addr
                    self.intake.remember(t, (KID_A, 5), runner.now_ms() + 60_000)
                self.intake.settle(t, ok, ok)
        return who

    def test_an_echo_right_behind_an_established_stations_frame_displaces_nothing(self):
        for ports in (1, 8, 40):
            for n in range(20):
                self.offer(*[forge(beacon(A, 1), 100 * n + k) for k in range(8)], src=udp(40_000 + n % ports))
                f = beacon(A, 100 * ports + n)
                self.offer(f, src=HERE)
                self.offer(f, src=addr(7, 5_000 + n))          # from a port of its own each time
                self.assertEqual(self.turns(f), HERE)
        self.assertEqual((list(self.key.known), self.intake.stats()["displaced"]), ([HERE], 0))

    def test_nor_one_that_comes_while_the_frame_waits_for_its_stations_rate(self):
        """The station's frame stays in its lane for a while: its copy from elsewhere must not go round it."""
        bucket = self.key.streams[stream_id("chatter")].bucket
        self.offer(*[forge(item(A, 1), k) for k in range(8)], src=THERE)
        f = item(A, 2)
        self.offer(f, src=HERE)
        bucket.tokens, bucket.at = 0.0, self.now
        self.serve(32, verified=lambda t: False)
        self.offer(f, src=addr(7, 5_000))
        self.assertEqual(len(self.key.slot), 0)
        self.now += 1.0
        self.assertEqual(self.turns(f), HERE)

    def test_nor_one_behind_a_newcomers(self):
        for where in ("the slot", "a queue, its relay having a place in the slot", "a lane, the newcomer's frame in another"):
            with self.subTest(where):
                self.offer(*[forge(item(A, 1), k) for k in range(8)], src=THERE)
                f, new, relay = item(A, 2), addr(60), addr(7, 5_000)
                if where.startswith("a queue"):
                    self.offer(forge(f, 99), src=relay)
                elif where.startswith("a lane"):
                    self.offer(forge(f, 99), src=new)
                self.offer(f, src=new)
                self.offer(f, src=relay)
                self.assertEqual(self.turns(f), new)
                self.setUp()

    def test_nor_one_behind_a_newcomers_that_comes_to_a_shorter_queue_while_the_slice_is_spent(self):
        """The newcomer's frame waits in its lane as well, so the echo comes no sooner than it did without the slice."""
        self.offer(*[forge(item(A, 1), k) for k in range(8)], src=THERE)
        f, new, relay = item(A, 2), addr(60), addr(7, 5_000)
        self.offer(forge(f, 99), src=relay)                    # so it has a place in the slot, and its echo has a lane only
        self.offer(f, src=new)
        self.offer(f, src=relay)
        self.intake.slice.tokens, self.intake.slice.at = -100.0, self.now
        self.assertEqual(self.turns(f), new)

    def test_where_both_wait_in_a_turn_the_queues_copy_is_the_one_that_counts(self):
        """An echo ahead of the station's own copy has a place in the slot; the station's lane is served first, as it was."""
        self.offer(*[forge(beacon(A, 1), k) for k in range(8)], src=THERE)
        f = beacon(A, 2)
        self.offer(f, src=addr(7, 5_000))
        self.offer(f, src=HERE)
        self.assertEqual(self.turns(f), HERE)
        self.assertEqual((self.intake.copied, self.intake.slice.tokens), (1, intake.SLICE_BURST))


class LeaseTest(IntakeCase):
    """Who keeps a known place, and how long (🌫's inverse rows on #173). It authenticates nobody: a place is a share of the
    verify work, and the clock is the daemon's own."""

    def accept_from(self, src, *frames):
        self.offer(*frames, src=src)
        self.assertLessEqual(set(frames), set(self.accept()))

    def known(self, after=0.0):
        self.now += after
        getattr(self.intake, "lapse", lambda: None)()         # so that it fails, not errs, on a tree without a lease
        return list(self.intake.keys[KID_A].known)

    def test_a_place_ends_at_the_horizon_after_its_newest_frame(self):
        self.accept_from(HERE, item(A, 1))
        self.assertEqual(self.known(HORIZON_S), [HERE])
        self.assertEqual(self.known(0.01), [])
        self.assertEqual([self.intake.stats().get(k) for k in ("known", "displaced", "lapsed")], [1, 0, 1])

    def test_nothing_waiting_is_not_being_idle_and_a_new_frame_renews(self):
        for n in range(6):
            self.accept_from(HERE, beacon(A, n + 1))
            self.assertEqual(self.known(HORIZON_S - 1), [HERE])

    def test_a_stopped_incumbent_that_replays_one_frame_keeps_its_place_no_longer(self):
        """Row I-b: however often and from the very source, the replays end with the frame's first verification."""
        f = beacon(A, 1)
        self.accept_from(HERE, f)
        for n in range(int(HORIZON_S) * 10 - 1):
            self.offer(f, src=HERE)
            self.assertEqual(self.known(0.1), [HERE])
        self.offer(f, src=HERE)
        self.assertEqual(self.known(0.2), [])
        for n in range(20):
            self.offer(f, src=HERE)
            self.assertEqual((self.known(0.1), self.serve()), ([], []))

    def test_a_repeat_of_a_newer_frame_renews_to_that_frames_age_and_no_further(self):
        """A station whose frames a relay on a faster path is heard with first keeps the place it has, for as long as its
        own copies of new frames come."""
        self.accept_from(HERE, item(A, 1))
        self.now += HORIZON_S - 10
        f = item(A, 2)
        self.accept_from(THERE, f)
        self.now += 5
        self.offer(f, src=HERE)                                # five seconds after f was first verified
        self.assertIn(HERE, self.known(HORIZON_S - 5))
        self.assertNotIn(HERE, self.known(0.01))

    def test_a_copy_that_was_queued_when_the_frame_was_accepted_renews_too(self):
        self.accept_from(HERE, item(A, 1))
        self.now += HORIZON_S - 1
        f = item(A, 2)
        self.offer(f, src=THERE)
        (t,) = self.intake.take(1)
        self.offer(f, src=HERE)                                # waits in its own queue while the relay's copy is verified
        self.intake.remember(t, (KID_A, 5, 0, 2), runner.now_ms() + 60_000)
        self.intake.settle(t, True, True)
        self.assertEqual(self.serve(), [])
        self.assertIn(HERE, self.known(HORIZON_S - 1))

    def test_a_frame_that_was_never_new_renews_nothing(self):
        """What resurfaces after a restart, or is of an earlier epoch, verifies and is kept, and is not new. A stash of such
        frames, each sent twice, must not keep a place."""
        self.accept_from(HERE, item(A, 1))
        for n in range(10):
            self.now += 10
            f = item(A, 100 + n)
            self.offer(f, src=HERE)
            for t in self.intake.take(32):
                self.intake.remember(t, (KID_A, 4, 0, 100 + n), runner.now_ms() + 600_000, fresh=False)
                self.intake.settle(t, True, False)
            self.offer(f, src=HERE)
        self.assertEqual(self.known(), [])

    def test_a_copy_that_waited_in_the_same_turn_as_the_relays_renews_when_it_was_new(self):
        """A relay's copy just ahead of the station's, every second, both in one turn: the station delivered every frame."""
        self.accept_from(HERE, beacon(A, 1))
        self.accept_from(THERE, beacon(A, 2))
        for n in range(int(HORIZON_S) + 30):
            f = beacon(A, n + 10)
            self.offer(f, src=THERE)
            self.offer(f, src=HERE)
            self.assertEqual(len(self.accept()), 1)
            self.assertEqual(set(self.known(1.0)), {HERE, THERE})

    def test_a_repeat_of_an_older_frame_shortens_nothing(self):
        """A carousel sends its older items again and again."""
        old = item(A, 1)
        self.accept_from(HERE, old)
        self.now += HORIZON_S - 1
        self.accept_from(HERE, item(A, 2))
        self.offer(old, src=HERE)
        self.assertEqual(self.known(HORIZON_S - 1), [HERE])

    def test_a_slots_copy_renews_its_source_when_a_queues_stands_for_it(self):
        """A source whose frame waits in the slot has become known by another one meanwhile."""
        self.accept_from(THERE, item(A, 1))
        self.offer(*[forge(item(A, 1), n) for n in range(4)], src=addr(9))
        f = item(A, 3)
        self.offer(f, src=HERE)
        with self.intake._lock:
            self.intake.keys[KID_A].know(HERE)
        self.now += HORIZON_S - 1
        self.offer(f, src=THERE)
        (t,) = [t for t in self.intake.take(32) if t.data == f]
        self.intake.remember(t, (KID_A, 5, 0, 3), runner.now_ms() + 60_000)
        self.intake.settle(t, True, True)
        self.assertEqual((t.addr, set(self.known(HORIZON_S - 1))), (THERE, {HERE, THERE}))

    def test_a_lapse_that_takes_the_last_of_what_waits_leaves_the_key_out_of_the_turns(self):
        self.accept_from(HERE, item(A, 1))
        key = self.intake.keys[KID_A]
        self.offer(*[item(A, n + 2) for n in range(3)], src=HERE)
        self.now += HORIZON_S + 1
        with mock.patch.object(intake, "STRANGERS_MAX", 0):
            self.intake.lapse()
        self.assertEqual((list(key.ready), list(self.intake._ready), self.intake.waiting()), ([], [], False))
        self.assertEqual(self.refused["backlog"], 3)

    def test_and_renews_nothing_when_it_was_not(self):
        self.accept_from(HERE, beacon(A, 1))
        self.accept_from(THERE, beacon(A, 2))
        self.now += HORIZON_S
        f = beacon(A, 5, epoch=4)
        self.offer(f, src=THERE)
        self.offer(f, src=HERE)
        self.serve(32, fresh=False)
        self.assertEqual(self.known(0.01), [])

    def test_a_repeat_never_gives_a_place(self):
        f = item(A, 1)
        self.accept_from(HERE, f)
        self.offer(f, src=THERE)
        self.assertEqual(self.known(), [HERE])
        self.known(HORIZON_S + 1)
        self.offer(f, src=HERE)
        self.assertEqual(self.known(), [])

    def test_a_lapsed_source_queues_on_as_a_stranger(self):
        self.accept_from(HERE, item(A, 1))
        waits = [item(A, n + 2) for n in range(5)]
        self.offer(*waits, src=HERE)
        self.assertEqual((self.known(HORIZON_S + 1), HERE in self.intake.keys[KID_A].strangers), ([], True))
        self.assertEqual(self.serve(), waits)
        self.assertEqual((self.refused, self.known()), ({}, [HERE]))

    def test_with_no_room_for_it_what_a_lapsed_source_had_waiting_is_counted(self):
        self.accept_from(HERE, item(A, 1))
        key = self.intake.keys[KID_A]
        self.now += HORIZON_S
        for n in range(intake.STRANGERS_MAX + 1):
            self.offer(*[forge(item(A, 1), 10 * n + k) for k in range(2)], src=addr(100 + n))
        self.offer(*[item(A, n + 2, "other") for n in range(5)], src=HERE)
        before = self.intake.stats()["queued"]
        self.assertEqual(self.known(0.01), [])
        self.assertEqual((before - self.intake.stats()["queued"], self.refused["backlog"]), (5, 5))
        for _ in range(4):                                     # a stream's bucket holds 48 at once
            self.now += 1
            self.serve(200, verified=lambda t: False)
        self.assertEqual((self.intake.stats()["queued"], self.intake.waiting()), (0, False))

    def test_four_relays_that_were_first_hold_no_place_against_the_station_that_starts(self):
        """Row I-a, a guard (the rule is #173's): four relays have the key's places and go on forwarding valid copies. The
        station's first new frame gives it a place at once, on a new port too, and the copies of it take none away."""
        relays = [addr(7, 5_000 + n) for n in range(intake.KNOWN_MAX)]
        for n, src in enumerate(relays):
            self.accept_from(src, beacon(A, n + 1))
        seq = 100
        for port in (HERE, THERE):
            for _ in range(20):
                seq += 1
                f = beacon(A, seq)
                self.accept_from(port, f)
                for src in relays:
                    self.offer(f, src=src)
                self.assertIn(port, self.known(0.25))
        self.assertEqual(self.intake.stats()["displaced"], 2)
        self.assertEqual(self.known(), [*relays[2:], HERE, THERE])


class ConsistencyTest(IntakeCase):
    """Random traffic from many addresses, random verdicts: after every step the queues, rings, tables and counts
    agree with each other, and the station's buckets and the daemon's hold exactly what the verdicts left them (the
    clock refills nothing). Once it stops, everything is served."""

    def check(self, in_flight=0):
        i, waiting = self.intake, len(self.intake.unlisted.ready)
        self.assertEqual(i.unlisted in i._ready, bool(i.unlisted.ready))
        for key in i.keys.values():
            self.assertEqual(i._ready.count(key), 1 if key.ready else 0)
            queued = Counter()
            for s in key.streams.values():
                self.assertEqual(key.ready.count(s), 1 if s.lanes else 0)
                self.assertEqual({*s.known, *s.strange}, set(s.lanes.values()))
                self.assertEqual(len(s.known) + len(s.strange), len(s.lanes))
                self.assertEqual(s.pool, sum(len(lane.queue) for lane in s.strange))
                for ring, known in ((s.known, True), (s.strange, False)):
                    self.assertTrue(all(lane.queue and lane.source.known is known for lane in ring))
                    self.assertTrue(all(sorted(lane.digests) == sorted(e[1] for e in lane.queue) for lane in ring))
                self.assertEqual(getattr(s, "bytes", None), Counter(e[1] for lane in s.lanes.values() for e in lane.queue))
                for source, lane in s.lanes.items():
                    self.assertIs(lane.source, source)
                    queued[source] += len(lane.queue)
            listed = [*key.known.values(), *key.strangers.values(), *key.crowd]
            self.assertLessEqual(set(queued), set(listed))     # who waits in a lane; a displaced source may still have a place in the slot
            self.assertEqual(i._slots.count(key), 1 if key.slot else 0)
            self.assertEqual(len(set().union(*key.slot.rings)), len(key.slot))
            for ring in key.slot.rings:
                self.assertLessEqual(len(ring), intake.SLOT_MAX)
                for at, c in ring.items():
                    self.assertEqual(at, c.entry[2])
                    self.assertIn(c.stream, key.streams.values())
                    lane = c.stream.lanes.get(c.source)
                    self.assertEqual(c.queued, lane is not None and any(e is c.entry for e in lane.queue))
                    waiting += not c.queued
            self.assertLessEqual(len(key.marks), intake.MARKS_MAX)
            waiting += sum(queued.values())
            self.assertTrue(all(source.queued == queued[source] for source in listed))
            self.assertLessEqual(len(key.known), intake.KNOWN_MAX)
            self.assertLessEqual(len(key.strangers), intake.STRANGERS_MAX)
            self.assertEqual(dict(key.hosts), Counter(a[0] for a in key.strangers))
            self.assertFalse(set(key.known) & set(key.strangers))
            for s in key.streams.values():
                self.assertLessEqual(s.pool, intake.STRANGER_POOL)
                self.assertLessEqual(max((len(lane.queue) for lane in s.known), default=0), intake.STRANGER_POOL)
        self.assertEqual(i.stats()["known"] - i.stats()["displaced"] - i.stats()["lapsed"],
                         sum(len(k.known) for k in i.keys.values()))
        self.assertEqual(i.read, i.repeated + i.copied + i.verified + i.unverified + sum(i.refused.values()) + waiting
                         + in_flight)

    def test_random_traffic(self):
        never = {f"{b}_{k}": v for b in ("KEY", "STREAM", "BEACON", "SOURCE", "CHECK", "UNLISTED", "SLICE", "STRANGE")
                 for k, v in (("RATE", 0.0), ("BURST", 1e6))}
        for seed in range(12):
            r = random.Random(seed)
            good = [item(sk, n, stream) if r.random() < 0.7 else beacon(sk, n)
                    for n in range(1, 50) for sk, stream in [(r.choice((A, B)), r.choice(("chatter", "other", "nowhere")))]]
            bad = [forge(f, n) for n, f in enumerate(good)]
            junk = [b"x", item(Ed25519PrivateKey.generate(), 1)]
            spent: Counter = Counter()
            with mock.patch.multiple(intake, STRANGERS_MAX=10, STRANGERS_PER_HOST=3, STRANGER_POOL=40, CROWD_LANES=6,
                                     KNOWN_DEPTH=5, LEASE_S=8.0, SLOT_MAX=4, MARKS_MAX=20, **never):
                self.intake = self.make()

                def turn(limit, verdict):
                    batch = self.intake.take(limit)
                    self.check(len(batch))
                    if r.random() < 0.3:                                 # the reader goes on while they are being verified
                        offer()
                        self.check(len(batch))
                    for t in batch:
                        verified, fresh = verdict(t)
                        if fresh and r.random() < 0.8:
                            self.intake.remember(t, (t.data[4:12], 5, 0, 1), runner.now_ms() + r.choice((-1, 60_000)))
                        self.intake.settle(t, verified, fresh)
                        if t.key is not None:
                            spent.update([t.stream.bucket] + [t.key.bucket] * (not t.stream.beacon) if fresh else
                                         [self.intake.slice] if t.budget is self.intake.slice else
                                     [self.intake.checks] + [self.intake.strange] * t.strange)
                    self.intake.heard_again()
                    self.check()
                    station = [b for k in self.intake.keys.values()
                               for b in (k.bucket, *(s.bucket for s in k.streams.values()))]
                    for b in (*station, self.intake.checks, self.intake.strange, self.intake.slice):
                        self.assertEqual(1e6 - b.tokens, spent[b])

                def offer():
                    self.intake.offer([(r.choice(r.choice((good, bad, junk))), addr(r.randrange(8), r.randrange(6)))
                                       for _ in range(r.randrange(1, 40))])

                for _ in range(250):
                    self.now += r.choice((0, 0.001, 0.02, 0.2, 3))
                    if r.random() < 0.1:
                        self.intake.lapse()
                        self.check()
                    if r.random() < 0.6:
                        offer()
                        self.check()
                    else:
                        turn(r.choice((1, 4, 32)),
                             lambda t: (v := t.data in good, v and r.random() < 0.7))
                self.now += 1                                        # a key's turns of the slice may be due later
                for _ in range(1_000):
                    r.random = lambda: 1.0                               # nothing more comes
                    turn(32, lambda t: (False, False))
                self.assertEqual((self.intake.stats()["queued"], self.intake.waiting()), (0, False))


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
            self.assertEqual([d for d, _ in got], [d[:intake._SLOT] for d in sent])
            self.assertEqual(len({a for _, a in got}), 1)
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
        """SO_RXQ_OVFL on what is read, SO_MEMINFO now: the same counter (what R5 of test_fair_admission reports)."""
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
            return list(d.intake.repeats), d.intake.keys[wire.key_id(wire.public_key_bytes(SK))].bucket.tokens
        (kept, tokens), _ = self.run_with(scenario)
        self.assertEqual((kept, tokens), ([hashlib.sha256(new).digest()], intake.KEY_BURST))

    def test_a_restart_forgets_the_digests_so_the_first_copy_resurfaces(self):
        f = item(SK, 1)
        async def scenario(d, port):
            c = await self.joined(d)
            self.send(port, f, f)
            await until(lambda: self.frames(c))
            return self.frames(c)[0]["dedup"]
        self.assertEqual([self.run_with(scenario)[0] for _ in range(2)], ["first", "resurfaced"])

    def test_what_resurfaces_after_a_restart_makes_no_address_known(self):
        """Anyone may hold a captured copy of it. The station's next beacon makes its own known."""
        f = item(SK, 1)
        kid = wire.key_id(wire.public_key_bytes(SK))
        async def first(d, port):
            c = await self.joined(d)
            self.send(port, f)
            await until(lambda: self.frames(c))
            return len(d.intake.keys[kid].known)
        async def second(d, port):
            resurfaced = await first(d, port)
            self.assertEqual(d.intake.repeats[hashlib.sha256(f).digest()].at, 0.0)     # nor renews a place by its repeats
            self.send(port, b := beacon(SK, 1))
            await until(lambda: d.intake.keys[kid].known)
            self.assertGreater(d.intake.repeats[hashlib.sha256(b).digest()].at, 0.0)
            return resurfaced
        self.assertEqual([self.run_with(x)[0] for x in (first, second)], [1, 0])

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
                d.intake.offer([(f, HERE) for f in frames])
                await until(lambda: len(self.frames(c)) == 8)
            with mock.patch("canticle.listener.atomic_write_json", side_effect=OSError(28, "No space left on device")):
                d.intake.offer([(item(SK, n + 20), HERE) for n in range(3)])
                await until(lambda: c.eof)
            return len(saves), [r["type"] for r in c.recs[2:]], len(d.intake.repeats)
        (saves, types, kept), code = self.run_with(scenario)
        self.assertEqual((saves, types, kept, code), (1, ["frame"] * 8 + ["fatal"], 8, 1))

    def test_a_known_place_lapses_with_the_daemons_tick_whatever_is_replayed(self):
        """Row I-b through a daemon: a station's own socket replays its one beacon until the lease is over, and after it."""
        b, sock = beacon(SK, 1), socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sock.close)
        async def scenario(d, port):
            c = await self.joined(d)
            stats = []
            started = time.monotonic()
            while time.monotonic() - started < 1.0 or (not stats[-1][2] and time.monotonic() - started < 5.0):
                sock.sendto(b, ("127.0.0.1", port))
                await asyncio.sleep(0.02)
                s = d.intake.stats()
                stats.append((time.monotonic() - started, s["known"], s["lapsed"], s["repeats"]))
            return stats
        with mock.patch.object(intake, "LEASE_S", 0.4):
            stats, _ = self.run_with(scenario, tick_ms=20)
        at = next(t for t, _, lapsed, _ in stats if lapsed)
        self.assertGreaterEqual(at, 0.4)
        self.assertEqual(stats[-1][1:3], (1, 1))
        self.assertGreater(stats[-1][3], 20)

    def test_a_newcomer_whose_lane_forgers_share_is_heard_at_once(self):
        """Through a daemon: 40 ports forge the station's key faster than its strangers' checks, and its first frame is
        heard before it repeats it."""
        socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(40)]
        for s in socks:
            self.addCleanup(s.close)
        f, at = item(SK, 1), item(SK, 2, body=b"a newcomer")
        async def scenario(d, port):
            c, n = await self.joined(d), 0
            key = d.intake.keys[f[4:12]]
            async def flood():
                nonlocal n
                while True:
                    for _ in range(40):
                        n += 1
                        socks[n % 40].sendto(forge(f, n), ("127.0.0.1", port))
                    await asyncio.sleep(0.005)
            task = asyncio.create_task(flood())
            await until(lambda: len(key.marks) == 40)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                while True:                                    # a port that shares a lane with a forger's
                    s.bind(("127.0.0.1", 0))
                    me = udp(s.getsockname()[1])
                    with d.intake._lock:
                        lanes = {id(key.source(udp(x.getsockname()[1]), 0.0)) for x in socks} & {id(x) for x in key.crowd}
                        shared = id(key.source(me, 0.0)) in lanes
                    if shared:
                        break
                    s.close()
                    s.__init__(socket.AF_INET, socket.SOCK_DGRAM)
                sent = time.monotonic()
                s.sendto(at, ("127.0.0.1", port))
                await until(lambda: self.frames(c))
            task.cancel()
            return time.monotonic() - sent, d.intake.stats()["reserved"]
        (took, reserved), _ = self.run_with(scenario)
        self.assertLess(took, 1.0)
        self.assertGreater(reserved, 0)

    def test_health_tells_the_kinds_of_loss_apart(self):
        async def scenario(d, port):
            health = lambda: json.loads(d.receptor.health(runner.now_ms()))
            quiet = health()
            # What claims no listed key is refused without degrading health: no station lost anything by it.
            d.intake.offer([(item(A, n), HERE) for n in range(1, 500)])
            junk = health()
            d.intake.offer([(forge(item(SK, 1), n), THERE) for n in range(500)])
            refused, later = health(), health()
            return quiet, junk, refused, later
        (quiet, junk, refused, later), _ = self.run_with(scenario)
        self.assertEqual((quiet["state"], quiet["records"]["socket_dropped"]), ("ok", 0))
        self.assertEqual(set(quiet["receive"]), {"read", "repeats", "copies", "verified", "unverified", "reserved", "queued",
                                                 "known", "displaced", "lapsed", "refused"})
        self.assertEqual(tuple(quiet["receive"]["refused"]), intake.REFUSED)
        self.assertGreater(junk["receive"]["refused"]["unlisted"], 0)
        self.assertEqual((junk["state"], junk["reasons"]), ("ok", []))
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
