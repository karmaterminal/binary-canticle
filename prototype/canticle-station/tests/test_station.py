import random
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, runner, vectors, wire
from canticle.ids import stream_id
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import NotGranted, Station, StreamConfig, next_epoch

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
PK = SK.public_key()


def station(*streams, **kw) -> Station:
    streams = streams or (StreamConfig("chatter"), StreamConfig("lens.threat", cls="live-state"), StreamConfig("root", cls="root"))
    return Station(SK, streams, epoch=7, rng=random.Random(3), now_ms=T0, **kw)


def run(st: Station, start: int, end: int, step: int = 50) -> list[tuple[int, bytes]]:
    """Poll the station on a virtual clock and collect (time, frame) pairs."""
    out = []
    for t in range(start, end, step):
        out.extend((t, f) for f in st.poll(t))
    return out


def items(sent, seq=None, kind=wire.KIND_ITEM):
    return [(t, f) for t, f in sent if f[3] == kind and (seq is None or wire.parse(f, lambda k: PK).body.seq == seq)]


class CarouselTest(unittest.TestCase):
    def test_burst_then_loop_byte_identical_until_expiry(self):
        st = station()
        r = st.sing(T0, "chatter", text="port-scan burst from 10.0.0.7", ttl_s=60)
        self.assertEqual((r.seq, r.ttl_s, r.loop_ms, r.clamp), (1, 60.0, 10_000, "none"))  # normal = 2 x 5 s floor
        sent = items(run(st, T0, T0 + 70_000))
        times = [t - T0 for t, _ in sent]
        self.assertEqual(times[:4], [0, 1_000, 2_000, 4_000])                   # burst (§7.6)
        self.assertEqual(len({f for _, f in sent}), 1)                          # signed once, byte-identical (§7.2)
        gaps = [b - a for a, b in zip(times[3:], times[4:])]
        self.assertTrue(all(10_000 * 2 / 3 - 50 <= g <= 10_000 * 4 / 3 + 50 for g in gaps), gaps)  # U(2/3, 4/3)
        self.assertLess(times[-1], 60_000 - 100 + 50)                           # stop before expiry (§7.3)
        self.assertGreater(times[-1], 60_000 - 10_000 * 4 / 3 - 100)            # ...but keep looping to the end
        self.assertEqual(wire.parse(sent[-1][1], lambda k: PK).body.expires_at, T0 + 60_000)  # absolute, unchanged

    def test_regulator_fair_share_and_class_floor(self):
        st = station(StreamConfig("chatter", default_ttl_s=300, max_ttl_s=300))
        for i in range(12):
            r = st.sing(T0, "chatter", body=b"x" * 530, ctype=2, loop="fast")
        # 12 items of ~600 B in a 4 kbit/s stream: fair share ~14.4 s beats a 5 s 'fast' request (RFC-0001 §7.5 table)
        self.assertEqual(r.clamp, "fair_share")
        self.assertAlmostEqual(r.loop_ms, 1000 * 8 * r.size * 12 / 4000, delta=1)
        one = station().sing(T0, "lens.threat", text="threat: low", state_key="now", loop="fast")
        self.assertEqual((one.loop_ms, one.clamp), (5_000, "none"))  # fast == the live-state floor
        slow_req = station().sing(T0, "lens.threat", text="x", state_key="now", loop=1_000)
        self.assertEqual((slow_req.loop_ms, slow_req.clamp), (5_000, "class_min"))

    def test_ttl_is_capped_by_stream_default(self):
        st = station(StreamConfig("chatter"))  # chatter default 60 s
        self.assertEqual(st.sing(T0, "chatter", text="x", ttl_s=10_000).ttl_s, 60.0)
        self.assertEqual(st.sing(T0, "chatter", text="x", ttl_s=5).ttl_s, 5.0)

    def test_supersede_stops_the_old_loop(self):
        st = station()
        a = st.sing(T0, "lens.threat", text="threat: low", state_key="now")
        run(st, T0, T0 + 5_000)
        b = st.sing(T0 + 5_000, "lens.threat", text="threat: high", state_key="now")
        self.assertEqual(b.superseded_seq, a.seq)
        later = run(st, T0 + 5_000, T0 + 60_000)
        self.assertFalse(items(later, seq=a.seq))
        self.assertTrue(items(later, seq=b.seq))

    def test_one_class_per_state_key_within_an_epoch(self):
        # §7.8, §23.2 q21: a state_key keeps its class for the epoch; a new epoch may change it.
        st = Station(SK, [StreamConfig("chatter")], epoch=1, rng=random.Random(1), now_ms=T0)
        st.sing(T0, "chatter", text="a", cls="live-state", state_key="k")
        head = st.streams["chatter"].head_seq
        with self.assertRaises(ValueError):
            st.sing(T0 + 1, "chatter", text="b", cls="chatter", state_key="k")
        self.assertEqual(st.streams["chatter"].head_seq, head)                    # refused before a seq is used
        st.sing(T0 + 2, "chatter", text="c", cls="live-state", state_key="k")     # same class: fine
        st.sing(T0 + 3, "chatter", text="d", cls="chatter", state_key="other")    # keys are independent
        later = Station(SK, [StreamConfig("chatter")], epoch=2, rng=random.Random(2), now_ms=T0 + 4)
        later.sing(T0 + 4, "chatter", text="e", cls="chatter", state_key="k")     # a new epoch may change it

    def test_key_classes_are_forgotten_once_no_mark_can_hold_them(self):
        # The q21 review: the table must not grow with every key of the epoch. A key is forgotten once its
        # last item's expiry + TTL + class max TTL + margin has passed; then a class change is allowed.
        st = Station(SK, [StreamConfig("chatter")], epoch=1, rng=random.Random(1), now_ms=T0)
        st.sing(T0, "chatter", text="a", cls="live-state", state_key="k", ttl_s=60)
        t = T0 + 60_000 + 60_000 + 900_000 + 10_000 - 1
        st.poll(t)
        with self.assertRaises(ValueError):                                       # a mark may still be held
            st.sing(t, "chatter", text="b", cls="chatter", state_key="k")
        st.poll(t + 1)
        self.assertEqual(st.streams["chatter"].key_classes, {})
        st.sing(t + 1, "chatter", text="c", cls="chatter", state_key="k")         # no mark can hold it now
        churn = Station(SK, [StreamConfig("chatter")], epoch=2, rng=random.Random(2), now_ms=T0)
        for i in range(2_000):                                                    # a new key every second
            t = T0 + i * 1_000
            churn.sing(t, "chatter", text="x", state_key=f"k{i}", ttl_s=30)
            churn.poll(t)
        self.assertLessEqual(len(churn.streams["chatter"].key_classes), 30 + 30 + 300 + 10 + 1)

    def test_pluck_stops_target_and_loops_until_target_expiry(self):
        st = station()
        a = st.sing(T0, "chatter", text="oops", ttl_s=60)
        run(st, T0, T0 + 3_000)
        p = st.hush(T0 + 3_000, "chatter", a.seq)
        self.assertEqual((p.kind, p.seq, p.expires_at), ("pluck", 2, a.expires_at))
        later = run(st, T0 + 3_000, T0 + 70_000)
        self.assertFalse(items(later, seq=a.seq))
        plucks = items(later, kind=wire.KIND_PLUCK)
        self.assertGreater(len(plucks), 4)
        self.assertLess(plucks[-1][0], a.expires_at)
        self.assertEqual(wire.parse(plucks[0][1], lambda k: PK).body.target_seq, a.seq)

    def test_refused_hush_leaves_the_carousel_unchanged(self):
        st = station()
        a = st.sing(T0, "chatter", text="oops", ttl_s=60)
        s = st.streams["chatter"]
        before = (dict(s.ring), s.head_seq)
        with self.assertRaises(ValueError):
            st.hush(a.expires_at - 50, "chatter", a.seq)  # inside the stop-before-expiry margin
        self.assertEqual((dict(s.ring), s.head_seq), before)
        with self.assertRaises(ValueError):
            st.hush(T0 + 1_000, "chatter", a.seq + 5)  # no such item
        self.assertEqual((dict(s.ring), s.head_seq), before)

    def test_late_pluck_is_never_shed(self):
        st = station()
        a = st.sing(T0, "chatter", text="oops", ttl_s=60)
        run(st, T0, T0 + 40_000)
        st.hush(T0 + 40_000, "chatter", a.seq)  # 20 s left: fewer than k_avail loops remain
        plucks = items(run(st, T0 + 40_000, T0 + 70_000), kind=wire.KIND_PLUCK)
        self.assertGreater(len(plucks), 4)  # more than the burst
        self.assertGreater(plucks[-1][0], a.expires_at - 10_000 * 4 / 3 - 100)

    def test_degraded_chatter_is_shed_after_its_burst(self):
        st = station(StreamConfig("chatter"))
        for i in range(100):
            r = st.sing(T0, "chatter", body=b"x" * 530, ctype=2)
        self.assertEqual(r.clamp, "degraded")  # §7.5 table: 100 x 600 B chatter exceeds hi = TTL/3
        sent = items(run(st, T0, T0 + 60_000), seq=r.seq)
        self.assertEqual([t - T0 for t, _ in sent], [0, 1_000, 2_000, 4_000])

    def test_refresh_reissue_keeps_a_keyed_item_on_air(self):
        st = station()
        r = st.sing(T0, "root", body=cbor.encode({1: "tend the garden"}), ctype=7, state_key="root",
                    ttl_s=90, keep_on_air_s=300)
        sent = items(run(st, T0, T0 + 300_000, step=250))
        seqs = sorted({wire.parse(f, lambda k: PK).body.seq for _, f in sent})
        self.assertGreaterEqual(len(seqs), 4)                    # re-issued every ~2/3 TTL
        refreshed = [wire.parse(f, lambda k: PK).body for _, f in sent if wire.parse(f, lambda k: PK).body.seq > r.seq]
        self.assertTrue(all(b.flags & wire.Item.REFRESH and b.state_key == "root" for b in refreshed))
        self.assertLessEqual(max(b.issued_at for b in refreshed), T0 + 300_000)

    def test_refresh_keeps_provenance_flags(self):
        st = station()
        r = st.sing(T0, "root", body=cbor.encode({1: "hold"}), ctype=7, state_key="root", ttl_s=90,
                    keep_on_air_s=300, flags=wire.Item.WAKE_DERIVED)
        sent = items(run(st, T0, T0 + 200_000, step=250))
        refreshed = {b.seq: b for b in (wire.parse(f, lambda k: PK).body for _, f in sent) if b.seq > r.seq}
        self.assertTrue(refreshed)
        for b in refreshed.values():
            self.assertEqual(b.flags, wire.Item.WAKE_DERIVED | wire.Item.REFRESH)

    def test_depth_never_evicts_a_pluck(self):
        st = station(depth=1)
        a = st.sing(T0, "chatter", text="oops", ttl_s=60)
        p = st.hush(T0 + 1_000, "chatter", a.seq)
        st.sing(T0 + 2_000, "chatter", text="b")
        c = st.sing(T0 + 3_000, "chatter", text="c")                 # depth 1 pushes out b, not the pluck
        s = st.streams["chatter"]
        self.assertEqual(sorted(s.ring), [p.seq, c.seq])
        before = (dict(s.ring), s.head_seq)
        with self.assertRaises(ValueError):
            st.hush(T0 + 4_000, "chatter", c.seq)                     # a second live PLUCK exceeds depth 1
        self.assertEqual((dict(s.ring), s.head_seq), before)
        plucks = items(run(st, T0 + 3_000, T0 + 70_000), kind=wire.KIND_PLUCK)
        self.assertGreater(plucks[-1][0], a.expires_at - 20_000)      # still looping near the target's expiry
        self.assertLess(plucks[-1][0], a.expires_at)

    def test_depth_pushes_out_oldest(self):
        st = station(depth=3)
        for i in range(5):
            st.sing(T0, "chatter", text=f"m{i}")
        self.assertEqual([x["seq"] for x in st.status(T0)["streams"]["chatter"]["on_air"]], [3, 4, 5])

    def test_stream_id_collision_is_refused(self):
        import canticle.ids as ids
        real = ids.stream_id
        try:
            ids.stream_id = lambda name: 42
            with self.assertRaises(ValueError):
                ids.stream_ids(["a", "b"])
        finally:
            ids.stream_id = real

    def test_beacon_contents_and_goodbye(self):
        st = station()
        st.sing(T0, "chatter", text="x")
        b = wire.parse(run(st, T0, T0 + 50)[0][1], lambda k: PK).body
        self.assertIsInstance(b, wire.Beacon)
        self.assertEqual((b.epoch, b.bseq, b.profile), (7, 1, "canticle-regulation/1"))
        self.assertTrue(900 <= b.next_beacon_ms <= 1100)
        entry = {e.stream_id: e for e in b.streams}[stream_id("chatter")]
        self.assertEqual((entry.head_seq, entry.trail_seq, entry.live, entry.loop_ms, entry.default_ttl_s),
                         (1, 1, 1, 10_000, 60))
        bye = wire.parse(st.goodbye(T0 + 100), lambda k: PK).body
        self.assertEqual(bye.next_beacon_ms, 0)

    def test_trail_seq_tracks_the_on_air_set(self):
        # F-PD A1 (§22.3, §9.8): trail_seq is the lowest seq of any ITEM or PLUCK still on air, head_seq + 1
        # when nothing is, and it stays right through expiry, supersession, pluck and depth eviction.
        st = station(StreamConfig("chatter", default_ttl_s=300, max_ttl_s=300),
                     StreamConfig("lens.threat", cls="live-state"), depth=3)
        ent = lambda name: {e.stream_id: e for e in st._entries()}[stream_id(name)]
        self.assertEqual((ent("chatter").head_seq, ent("chatter").trail_seq, ent("chatter").live), (0, 1, 0))
        st.sing(T0, "chatter", text="a", ttl_s=10)                                  # seq 1, off air at T0 + 9.9 s
        st.sing(T0, "chatter", text="b", ttl_s=300)                                 # seq 2
        st.sing(T0, "chatter", text="c", ttl_s=300)                                 # seq 3
        self.assertEqual((ent("chatter").head_seq, ent("chatter").trail_seq, ent("chatter").live), (3, 1, 3))
        b = wire.parse(st._beacon(T0 + 9_950), lambda k: PK).body                  # expiry: the beacon sweeps first
        e = {e.stream_id: e for e in b.streams}[stream_id("chatter")]
        self.assertEqual((e.head_seq, e.trail_seq, e.live), (3, 2, 2))
        st.hush(T0 + 11_000, "chatter", 2)                                          # pluck: item 2 off, PLUCK seq 4 on
        self.assertEqual((ent("chatter").head_seq, ent("chatter").trail_seq, ent("chatter").live), (4, 3, 2))
        for text in ("d", "e", "f"):                                                # depth 3: item 3 is evicted by seq 7
            st.sing(T0 + 12_000, "chatter", text=text, ttl_s=300)
        self.assertEqual((ent("chatter").head_seq, ent("chatter").trail_seq, ent("chatter").live), (7, 4, 4))
        st.sing(T0, "lens.threat", text="low", state_key="now")                     # supersession: seq 1 then 2
        st.sing(T0 + 1_000, "lens.threat", text="high", state_key="now")
        self.assertEqual((ent("lens.threat").head_seq, ent("lens.threat").trail_seq, ent("lens.threat").live), (2, 2, 1))
        st.poll(T0 + 400_000)                                                       # everything has expired
        self.assertEqual((ent("chatter").head_seq, ent("chatter").trail_seq, ent("chatter").live), (7, 8, 0))
        self.assertEqual(st.status(T0 + 400_000)["streams"]["chatter"]["trail_seq"], 8)

    def test_beacon_pages_rotate_with_a_catalog_digest(self):
        st = station(*[StreamConfig(f"s{i}", b_stream=500) for i in range(120)], b_station=60_000)
        first = wire.parse(st._beacon(T0), lambda k: PK).body
        count = first.page[1]
        self.assertGreater(count, 1)
        pages = [first] + [wire.parse(st._beacon(T0 + i), lambda k: PK).body for i in range(1, count)]
        self.assertEqual([p.page for p in pages], [(i, count) for i in range(count)])
        self.assertEqual(len({p.catalog_digest for p in pages}), 1)
        self.assertEqual(sorted(e.stream_id for p in pages for e in p.streams), sorted(s.sid for s in st.streams.values()))
        self.assertTrue(all(len(st._beacon(T0)) <= wire.MAX_FRAME for _ in range(count)))
        small = station(*[StreamConfig(f"s{i}", b_stream=500) for i in range(30)], b_station=16_000)
        self.assertIsNone(wire.parse(small._beacon(T0), lambda k: PK).body.page)     # fits one beacon: not paged

    def test_beacon_paging_bound_matches_rfc_8_4(self):
        # §8.4 paging bound (A1): with every entry field at its CDDL maximum, 17 entries fit a page (54 B each),
        # so a catalog of 136 streams fits 8 pages and 137 does not. With lens (59 B) the RFC's 32-byte profile
        # gives 15 per page; this station's 21-byte profile leaves room for 16, so its floor is 128.
        cfg = lambda n, **kw: [StreamConfig(f"s{i}", b_stream=500, **kw) for i in range(n)]
        st = station(*cfg(136), b_station=100_000)
        worst = [wire.StreamEntry(*wire.StreamEntry.MAXIMA[:9]) for _ in range(136)]
        pages = st._pages(worst)
        self.assertEqual([len(p) for p in pages], [17] * 8)
        for p in pages:                                                             # each worst-case page encodes within the limit
            b = wire.Beacon(epoch=st.epoch, bseq=wire.U64, wallclock=wire.U64, next_beacon_ms=wire.U32,
                            profile="canticle-regulation/1", streams=tuple(p), b_station=100_000,
                            page=(7, 8), catalog_digest=bytes(8))
            self.assertLessEqual(len(wire.encode_beacon(SK, b)), wire.MAX_FRAME)
        with self.assertRaises(ValueError):
            station(*cfg(137), b_station=100_000)
        self.assertEqual(len(station(*cfg(128, lens=1), b_station=100_000)._pages(
            [wire.StreamEntry(*wire.StreamEntry.MAXIMA[:9], lens=wire.U32) for _ in range(128)])), 8)
        with self.assertRaises(ValueError):
            station(*cfg(129, lens=1), b_station=100_000)


class LateJoinerTest(unittest.TestCase):
    def test_late_listener_hears_every_live_item_within_one_loop(self):
        st = station(StreamConfig("chatter", default_ttl_s=300, max_ttl_s=300))
        for i in range(5):
            st.sing(T0, "chatter", text=f"item {i}", ttl_s=300)
        run(st, T0, T0 + 30_000)
        m = Manifest([StationEntry("test1", wire.public_key_bytes(SK), frozenset({1}), ("chatter",))])
        lst = Listener(m, ephemeral=True)
        heard, first = set(), None
        for t, f in run(st, T0 + 30_000, T0 + 60_000):
            for ev in lst.hear(f, t):
                if ev.kind == "item":
                    heard.add(ev.seq)
                    if len(heard) == 5 and first is None:
                        first = t - (T0 + 30_000)
        self.assertEqual(heard, {1, 2, 3, 4, 5})
        self.assertLessEqual(first, 10_000 * 4 / 3 + 100)  # within loop_ms x 4/3 (§7.10)


class EpochTest(unittest.TestCase):
    def test_persisted_epoch_strictly_increases(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "k.epoch"
            now = 1_790_000_000
            self.assertEqual(next_epoch(path, now_s=now), now)          # first start: not below time-based epochs
            self.assertEqual(next_epoch(path, now_s=now), now + 1)      # same second
            self.assertEqual(next_epoch(path, now_s=now - 3600), now + 2)  # clock stepped back
            self.assertEqual(next_epoch(path, now_s=now + 60), now + 60)
            self.assertEqual(path.read_text(), f"{now + 60}\n")
            self.assertEqual(sorted(x.name for x in Path(d).iterdir()), ["k.epoch", "k.epoch.lock"])

    def test_unreadable_counter_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "k.epoch"
            path.write_text("not a number\n")
            with self.assertRaises(ValueError):
                next_epoch(path, now_s=1)
            path.write_text(f"{2**32 - 1}\n")
            with self.assertRaises(ValueError):
                next_epoch(path, now_s=1)


class GrantTest(unittest.TestCase):
    def granted(self, classes=frozenset({1}), scopes=frozenset({1}), streams=("chatter",)):
        entry = StationEntry("cael", wire.public_key_bytes(SK), classes, streams, scopes=scopes)
        return Station(SK, (StreamConfig("chatter"), StreamConfig("root", cls="root")), epoch=7,
                       rng=random.Random(3), now_ms=T0, grant=entry)

    def test_ungranted_class_scope_or_stream_is_refused_before_signing(self):
        st = self.granted()
        s = st.streams["chatter"]
        for kw in ({"cls": "control", "state_key": "k"}, {"scope": "public"}, {"scope": "fleet"}):
            with self.assertRaises(NotGranted):
                st.sing(T0, "chatter", text="x", **kw)
        with self.assertRaises(NotGranted):
            st.sing(T0, "root", body=cbor.encode({1: "x"}), ctype=7, state_key="root")  # stream not granted
        self.assertEqual((s.head_seq, dict(s.ring)), (0, {}))
        self.assertEqual(st.sing(T0, "chatter", text="ok").seq, 1)

    def test_host_scope_never_goes_to_udp(self):
        st = self.granted(scopes=frozenset({0, 1}))
        with self.assertRaises(ValueError):
            st.sing(T0, "chatter", text="stay home", scope="host")
        self.assertEqual(st.streams["chatter"].head_seq, 0)

    def test_run_station_needs_a_grant_and_no_host_binding(self):
        import asyncio
        bare = station()
        with self.assertRaises(ValueError):
            asyncio.run(runner.run_station(bare, []))
        hosted = Station(SK, (StreamConfig("chatter"),), epoch=7, now_ms=T0, host_binding=True,
                         grant=StationEntry("cael", wire.public_key_bytes(SK), frozenset({1}), ("chatter",)))
        with self.assertRaises(ValueError):
            asyncio.run(runner.run_station(hosted, []))


class SocketGrantTest(unittest.TestCase):
    def station(self):
        entry = StationEntry("keeper", wire.public_key_bytes(SK), frozenset({1, 6, 7, 8}),
                             ("chatter", "alarm", "reg"), scopes=frozenset({1}))
        return Station(SK, (StreamConfig("chatter"), StreamConfig("alarm", cls="alarm"),
                            StreamConfig("reg", cls="regulatory")), epoch=7, now_ms=T0, grant=entry)

    def test_socket_never_takes_regulatory_alarm_or_control(self):
        st = self.station()
        self.assertEqual(runner.socket_grant(st), frozenset({"chatter"}))
        for cls in ("control", "alarm", "regulatory"):
            with self.assertRaises(ValueError):
                runner.socket_grant(st, [cls])     # even when the key holds it
        with self.assertRaises(ValueError):
            runner.socket_grant(st, ["advisory"])  # not granted to the key at all

    def test_dispatch_refuses_before_signing(self):
        st = self.station()
        allowed = runner.socket_grant(st)
        for req in ({"op": "sing", "stream": "alarm", "text": "x", "state_key": "a"},
                    {"op": "sing", "stream": "reg", "text": "quarantine-vote", "state_key": "q"},
                    {"op": "sing", "stream": "chatter", "text": "x", "class": "control", "state_key": "c"}):
            self.assertFalse(runner._dispatch(st, req, allowed)["ok"])
        self.assertEqual({n: s.head_seq for n, s in st.streams.items()}, {"chatter": 0, "alarm": 0, "reg": 0})
        self.assertTrue(runner._dispatch(st, {"op": "sing", "stream": "chatter", "text": "ok"}, allowed)["ok"])


def _next_epoch_worker(args):
    path, barrier_path, now_s = args
    import time as _t
    while not Path(barrier_path).exists():
        _t.sleep(0.001)
    return next_epoch(path, now_s=now_s)


class EpochConcurrencyTest(unittest.TestCase):
    def test_concurrent_starts_get_distinct_epochs(self):
        import multiprocessing as mp
        with tempfile.TemporaryDirectory() as d:
            path, barrier = str(Path(d) / "k.epoch"), str(Path(d) / "go")
            with mp.get_context("fork").Pool(8) as pool:
                res = pool.map_async(_next_epoch_worker, [(path, barrier, 1_000)] * 16)
                Path(barrier).touch()
                epochs = res.get(timeout=30)
            self.assertEqual(sorted(epochs), list(range(1_000, 1_016)))
            self.assertEqual(Path(path).read_text(), "1015\n")
            self.assertFalse([x for x in Path(d).iterdir() if x.suffix == ".tmp"])


if __name__ == "__main__":
    unittest.main()
