"""The host daemon's intake (``canticle/intake.py``, #171): what may be skipped before verify, who pays, what is bounded.

Two kinds of test. ``IntakeCase`` drives an ``Intake`` with no thread and no socket traffic: ``offer`` places datagrams,
``take`` and ``settle`` are the event loop's half. ``DaemonIntakeTest`` sends real frames to a real in-process daemon
over loopback UDP. The floods are in ``test_fair_admission``.
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
from collections import Counter
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import intake, listener, runner, wire
from canticle.ids import stream_id
from canticle.intake import BEACON, OTHER, Intake, peek_stream
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
        self.assertEqual(self.serve(4).index(quiet), 1)

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
        self.assertEqual(self.intake.stats()["queued"], intake.STRANGER_POOL)
        self.assertEqual(self.intake.stats()["queued"] + sum(self.refused.values()), 5_000)

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
        self.offer(quiet, src=HERE)
        lanes = intake.STRANGERS_PER_HOST + intake.CROWD_LANES + 1
        served = [d for _ in range(lanes // 16 + 1) for d in self.serve(16, verified=lambda t: t.data == quiet)]
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
        self.assertIn(f, served[:len(mine) + 1])

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
        self.assertEqual([d for d in served if d in quiet], quiet)

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
        self.assertLessEqual(before - self.intake.stats()["queued"], 8 * intake.TURN)

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
        self.serve(200, verified=lambda t: False)
        self.assertEqual((self.intake.stats()["queued"], self.intake.waiting()), (0, False))
        self.assertEqual([(s.pool, s.lanes) for s in key.streams.values()], [(0, {})] * len(key.streams))

    def test_the_unlisted_queue_is_examined_on_a_budget(self):
        unknown = Ed25519PrivateKey.generate()
        for n in range(2_000):
            self.offer(item(unknown, n + 1))
            self.serve(verified=lambda t: False)
        self.assertLessEqual(self.intake.unverified, intake.UNLISTED_BURST)


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
                for source, lane in s.lanes.items():
                    self.assertIs(lane.source, source)
                    queued[source] += len(lane.queue)
            waiting += sum(queued.values())
            listed = [*key.known.values(), *key.strangers.values(), *key.crowd]
            self.assertLessEqual(set(queued), set(listed))
            self.assertTrue(all(source.queued == queued[source] for source in listed))
            self.assertLessEqual(len(key.known), intake.KNOWN_MAX)
            self.assertLessEqual(len(key.strangers), intake.STRANGERS_MAX)
            self.assertEqual(dict(key.hosts), Counter(a[0] for a in key.strangers))
            self.assertFalse(set(key.known) & set(key.strangers))
        self.assertEqual(i.read, i.repeated + i.copied + i.verified + i.unverified + sum(i.refused.values()) + waiting
                         + in_flight)

    def test_random_traffic(self):
        never = {f"{b}_{k}": v for b in ("KEY", "STREAM", "BEACON", "SOURCE", "CHECK", "UNLISTED")
                 for k, v in (("RATE", 0.0), ("BURST", 1e6))}
        for seed in range(12):
            r = random.Random(seed)
            good = [item(sk, n, stream) if r.random() < 0.7 else beacon(sk, n)
                    for n in range(1, 50) for sk, stream in [(r.choice((A, B)), r.choice(("chatter", "other", "nowhere")))]]
            bad = [forge(f, n) for n, f in enumerate(good)]
            junk = [b"x", item(Ed25519PrivateKey.generate(), 1)]
            spent: Counter = Counter()
            with mock.patch.multiple(intake, STRANGERS_MAX=10, STRANGERS_PER_HOST=3, STRANGER_POOL=40, CROWD_LANES=6,
                                     KNOWN_DEPTH=5, **never):
                self.intake = self.make()

                def turn(limit, verdict):
                    batch = self.intake.take(limit)
                    self.check(len(batch))
                    for t in batch:
                        verified, fresh = verdict(t)
                        if fresh and r.random() < 0.8:
                            self.intake.remember(t, (t.data[4:12], 5, 0, 1), runner.now_ms() + r.choice((-1, 60_000)))
                        self.intake.settle(t, verified, fresh)
                        if t.key is not None:
                            spent.update([t.stream.bucket] + [t.key.bucket] * (not t.stream.beacon) if fresh else
                                         [self.intake.checks])
                    self.intake.heard_again()
                    self.check()
                    station = [b for k in self.intake.keys.values()
                               for b in (k.bucket, *(s.bucket for s in k.streams.values()))]
                    for b in (*station, self.intake.checks):
                        self.assertEqual(1e6 - b.tokens, spent[b])

                for _ in range(250):
                    self.now += r.choice((0, 0.001, 0.02, 0.2, 3))
                    if r.random() < 0.6:
                        self.intake.offer([(r.choice(r.choice((good, bad, junk))), addr(r.randrange(8), r.randrange(6)))
                                           for _ in range(r.randrange(1, 40))])
                        self.check()
                    else:
                        turn(r.choice((1, 4, 32)),
                             lambda t: (v := t.data in good, v and r.random() < 0.7))
                for _ in range(1_000):
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
            self.send(port, beacon(SK, 1))
            await until(lambda: d.intake.keys[kid].known)
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
        self.assertEqual(set(quiet["receive"]), {"read", "repeats", "copies", "verified", "unverified", "queued",
                                                 "refused"})
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
