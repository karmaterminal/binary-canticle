import json
import random
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, vectors, wire
from canticle.ids import stream_id
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig, next_epoch

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
SK_ID = wire.key_id(wire.public_key_bytes(SK))


def setup():
    st = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=1,
                 rng=random.Random(1), now_ms=T0)
    m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 9}), ("chatter", "root"))])
    return st, Listener(m, ephemeral=True)


def feed(st, lst, start, end, step=100):
    events = []
    for t in range(start, end, step):
        for f in st.poll(t):
            events.extend(lst.hear(f, t))
        events.extend(lst.tick(t))
    return events


class PresenceTest(unittest.TestCase):
    def test_four_states_and_goodbye(self):
        st, lst = setup()
        kinds = lambda evs: [e.data["state"] for e in evs if e.kind == "presence"]
        self.assertEqual(kinds(feed(st, lst, T0, T0 + 2_000)), ["ROOT_UNKNOWN"])
        st.sing(T0 + 2_000, "root", body=cbor.encode({1: "watch the gate"}), ctype=7, state_key="root", ttl_s=600)
        self.assertIn("EQUIPPED_QUIET", kinds(feed(st, lst, T0 + 2_000, T0 + 4_000)))
        st.sing(T0 + 4_000, "chatter", text="hello")
        self.assertIn("EQUIPPED_SPEAKING", kinds(feed(st, lst, T0 + 4_000, T0 + 6_000)))
        st.sing(T0 + 6_000, "root", body=cbor.encode({}), ctype=7, state_key="root", ttl_s=600)  # UNEQUIP
        self.assertIn("UNEQUIPPED_PRESENT", kinds(feed(st, lst, T0 + 6_000, T0 + 8_000)))
        evs = lst.hear(st.goodbye(T0 + 8_000), T0 + 8_000)
        self.assertEqual(kinds(evs), ["UNOBSERVABLE:signed_off"])

    def test_silence_becomes_unobservable_not_offline(self):
        st, lst = setup()
        feed(st, lst, T0, T0 + 2_000)
        evs = []
        for t in range(T0 + 2_000, T0 + 8_000, 100):
            evs.extend(lst.tick(t))  # the station goes quiet: no more polls
        states = [e.data["state"] for e in evs if e.kind == "presence"]
        self.assertEqual(states, ["UNOBSERVABLE"])


class ExpiryTest(unittest.TestCase):
    def test_items_expire_locally_and_are_announced(self):
        st, lst = setup()
        st.sing(T0, "chatter", text="short-lived", ttl_s=10)
        evs = feed(st, lst, T0, T0 + 15_000)
        kinds = [e.kind for e in evs if e.kind in ("item", "expired")]
        self.assertEqual(kinds, ["item", "expired"])
        self.assertEqual(lst.on_air(), [])

    def test_clock_rule_is_rfc_14_6_3(self):
        it = wire.Item(epoch=1, stream=1, seq=1, issued_at=T0, expires_at=T0 + 60_000, cls=1, ctype=1, body=b"x")
        self.assertEqual(wire.local_expiry_ms(it, -5_000), T0 + 55_000)          # receiver behind: earlier
        self.assertEqual(wire.local_expiry_ms(it, 5_000), T0 + 65_000)           # receiver ahead: same instant
        # ... but never more than the full TTL from first hearing
        self.assertEqual(wire.local_expiry_ms(it, 5_000, first_heard_ms=T0 + 1_000), T0 + 61_000)
        self.assertEqual(wire.local_expiry_ms(it, 3_600_000, first_heard_ms=T0 + 1_000), T0 + 61_000)

    def test_station_clock_an_hour_behind(self):
        hour = 3_600_000
        st = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=1,
                     rng=random.Random(1), now_ms=T0 - hour)
        lst = setup()[1]
        for t in range(0, 2_000, 100):                                   # beacons give δ̂ ≈ +1 h
            for f in st.poll(T0 - hour + t):
                lst.hear(f, T0 + t)
        st.sing(T0 - hour + 2_000, "chatter", text="late clock", ttl_s=60)
        evs = [e for f in st.poll(T0 - hour + 2_000) for e in lst.hear(f, T0 + 2_000)]
        self.assertEqual([e.kind for e in evs if e.kind in ("item", "evidence")], ["item"])
        (h,) = lst.current.values()
        self.assertEqual(h.local_expiry, T0 + 62_000)

    def test_expiry_is_clamped_to_class_max(self):
        it = wire.Item(epoch=1, stream=1, seq=1, issued_at=T0, expires_at=T0 + 10**9, cls=1, ctype=1, body=b"x")
        self.assertEqual(wire.local_expiry_ms(it), T0 + 300_000)


class RestartTest(unittest.TestCase):
    def restarted(self, epoch, now_ms):
        return Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=epoch,
                       rng=random.Random(epoch), now_ms=now_ms)

    def test_higher_epoch_beacons_count_from_one_again(self):
        st, lst = setup()
        feed(st, lst, T0, T0 + 4_500)  # epoch 1 reaches bseq 5
        s = lst.stations[st.key_id]
        self.assertEqual((s.epoch_hwm, s.bseq), (1, 5))
        evs = lst.hear(st.goodbye(T0 + 4_600), T0 + 4_600)
        self.assertEqual([e.data["state"] for e in evs if e.kind == "presence"], ["UNOBSERVABLE:signed_off"])
        st2 = self.restarted(2, T0 + 5_000)
        evs = [e for f in st2.poll(T0 + 5_000) for e in lst.hear(f, T0 + 5_000)]  # epoch 2, bseq 1
        self.assertEqual((s.epoch_hwm, s.bseq, s.last_beacon, s.signed_off), (2, 1, T0 + 5_000, False))
        self.assertEqual([e.data["state"] for e in evs if e.kind == "presence"], ["ROOT_UNKNOWN"])

    def test_new_epoch_item_before_its_first_beacon(self):
        st, lst = setup()
        feed(st, lst, T0, T0 + 4_500)
        st2 = self.restarted(2, T0 + 5_000)
        st2.sing(T0 + 5_000, "chatter", text="back")
        frames = st2.poll(T0 + 5_000)
        kinds = [wire.parse(f, lst.manifest.resolve, T0 + 5_000).kind for f in frames]
        order = sorted(range(len(frames)), key=lambda i: kinds[i] == wire.KIND_BEACON)  # items first
        for i in order:
            lst.hear(frames[i], T0 + 5_000)
        s = lst.stations[st.key_id]
        self.assertEqual((s.epoch_hwm, s.bseq, s.last_beacon), (2, 1, T0 + 5_000))

    def test_two_immediate_restarts_never_reuse_an_identity(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cael.key.epoch"
            _, lst = setup()
            now_s = T0 // 1000
            for i in range(2):  # two starts within the same second
                st = self.restarted(next_epoch(path, now_s=now_s), T0 + i)
                st.sing(T0 + i, "chatter", text=f"start {i}")  # seq 1 both times
                for f in st.poll(T0 + i):
                    lst.hear(f, T0 + i)
            self.assertEqual(lst.stations[st.key_id].epoch_hwm, now_s + 1)
            self.assertNotIn("equivocation", lst.evidence_counts)
            self.assertEqual(sorted(h["seq"] for h in lst.on_air()), [1, 1])


class AdmissionTest(unittest.TestCase):
    def test_capability_rejected_frames_are_state_neutral(self):
        st, lst = setup()
        feed(st, lst, T0, T0 + 1_500)
        rogue = Station(SK, [StreamConfig("chatter")], epoch=99, rng=random.Random(9), now_ms=T0 + 2_000)
        rogue.sing(T0 + 2_000, "chatter", cls="advisory", text="not granted")   # class 4: not in the manifest
        s = lst.stations[st.key_id]
        before = (s.epoch_hwm, s.bseq, dict(s.last_stream_item), dict(lst.dedup))
        items_only = [f for f in rogue.poll(T0 + 2_000)
                      if wire.parse(f, lst.manifest.resolve, T0 + 2_000).kind == wire.KIND_ITEM]
        evs = [e for f in items_only for e in lst.hear(f, T0 + 2_000)]
        self.assertEqual([e.data["reason"] for e in evs], ["capability"])
        self.assertEqual((s.epoch_hwm, s.bseq, dict(s.last_stream_item), dict(lst.dedup)), before)
        st2 = Station(SK, [StreamConfig("chatter")], epoch=2, rng=random.Random(2), now_ms=T0 + 3_000)
        st2.sing(T0 + 3_000, "chatter", text="authorised")
        evs = [e for f in st2.poll(T0 + 3_000) for e in lst.hear(f, T0 + 3_000)]
        self.assertIn("item", [e.kind for e in evs])
        self.assertNotIn("epoch-regression", lst.evidence_counts)

    def test_quota_refuses_new_tuples_and_keeps_live_ones(self):
        sk2 = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST2))
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 9}), ("chatter", "root")),
                      StationEntry("silas", wire.public_key_bytes(sk2), frozenset({1}), ("chatter",))])
        lst = Listener(m, dedup_capacity=6, ephemeral=True)                              # 3 tuples per key
        loud = Station(SK, [StreamConfig("chatter")], epoch=1, rng=random.Random(1), now_ms=T0)
        quiet = Station(sk2, [StreamConfig("chatter")], epoch=1, rng=random.Random(2), now_ms=T0)
        for i in range(5):
            loud.sing(T0, "chatter", text=f"flood {i}", ttl_s=30)
        quiet.sing(T0, "chatter", text="still heard", ttl_s=30)
        evs = [e for f in loud.poll(T0) + quiet.poll(T0) for e in lst.hear(f, T0)]
        heard = [(e.station, e.seq) for e in evs if e.kind == "item"]
        self.assertEqual(heard, [("cael", 1), ("cael", 2), ("cael", 3), ("silas", 1)])
        self.assertEqual(lst.evidence_counts.get("over-quota"), 2)
        again = [e for f in loud.poll(T0 + 1_000) for e in lst.hear(f, T0 + 1_000)]  # burst repeats
        self.assertNotIn("item", [e.kind for e in again if e.seq in (1, 2, 3)])   # live entries kept: still no-ops
        lst.tick(T0 + 40_000)                                                     # expired: room again
        self.assertEqual(lst.dedup_per_key, {loud.key_id: 0, quiet.key_id: 0})


class ScopeAndHopTest(unittest.TestCase):
    def test_host_frame_over_udp_is_a_state_neutral_scope_violation(self):
        _, lst = setup()
        st = Station(SK, [StreamConfig("chatter")], epoch=5, rng=random.Random(1), now_ms=T0, host_binding=True)
        st.sing(T0, "chatter", text="stay home", scope="host")
        frames = [f for f in st.poll(T0) if wire.parse(f, lst.manifest.resolve, T0).kind == wire.KIND_ITEM]
        evs = [e for f in frames for e in lst.hear(f, T0)]
        self.assertEqual({e.data["reason"] for e in evs}, {"scope-violation"})
        self.assertEqual((lst.stations, lst.dedup), ({}, {}))

    def test_scope_must_be_granted(self):
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1}), ("chatter",), scopes=frozenset({1}))])
        lst = Listener(m, ephemeral=True)
        st = Station(SK, [StreamConfig("chatter")], epoch=5, rng=random.Random(1), now_ms=T0)
        st.sing(T0, "chatter", text="to everyone", scope="public")
        evs = [e for f in st.poll(T0) for e in lst.hear(f, T0) if e.kind == "evidence"]
        self.assertEqual([e.data["reason"] for e in evs], ["scope-violation"])

    def test_hop_limit_boundaries(self):
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 7}), ("chatter", "alarm"))])
        lst = Listener(m, ephemeral=True)
        st = Station(SK, [StreamConfig("chatter"), StreamConfig("alarm", cls="alarm")], epoch=5,
                     rng=random.Random(1), now_ms=T0)
        st.sing(T0, "chatter", text="hop 2", hop=2)            # chatter allows 2
        st.sing(T0, "chatter", text="hop 3", hop=3)
        st.sing(T0, "alarm", text="relayed alarm", state_key="a", hop=1)  # alarm allows 0
        evs = [e for f in st.poll(T0) for e in lst.hear(f, T0) if e.kind in ("item", "evidence")]
        self.assertEqual([(e.kind, e.seq if e.kind == "item" else e.data["reason"]) for e in evs],
                         [("item", 1), ("evidence", "hop-limit"), ("evidence", "hop-limit")])
        self.assertEqual(len(lst.dedup), 1)                     # rejected frames left no dedup state


class PersistenceTest(unittest.TestCase):
    def test_state_is_required_unless_explicitly_ephemeral(self):
        with self.assertRaises(ValueError):
            Listener(setup()[1].manifest)
        with tempfile.TemporaryDirectory() as d:
            Listener(setup()[1].manifest, state_path=Path(d) / "s.json")

    def keyed(self, st, t, text):
        return st.sing(t, "root", body=cbor.encode({1: text}), ctype=7, state_key="root", ttl_s=600)

    def test_restart_keeps_supersession_pluck_and_epoch(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "listener.json"
            st, _ = setup()
            lst = Listener(setup()[1].manifest, state_path=path)
            old = self.keyed(st, T0, "old")
            old_frames = st.poll(T0)
            for f in old_frames:
                lst.hear(f, T0)
            self.keyed(st, T0 + 1_000, "new")
            chat = st.sing(T0 + 1_000, "chatter", text="withdrawn later", ttl_s=60)
            later = st.poll(T0 + 1_000)
            for f in later:
                lst.hear(f, T0 + 1_000)
            st.hush(T0 + 2_000, "chatter", chat.seq)
            for f in st.poll(T0 + 2_000):
                lst.hear(f, T0 + 2_000)

            fresh = Listener(lst.manifest, state_path=path)          # restart
            evs = [e for f in old_frames for e in fresh.hear(f, T0 + 3_000)]
            self.assertNotIn("item", [e.kind for e in evs])            # the stale value does not come back
            evs = [e for f in later for e in fresh.hear(f, T0 + 3_000)]
            items = [(e.stream, e.seq) for e in evs if e.kind == "item"]
            self.assertEqual(items, [("root", old.seq + 1)])           # current value re-surfaces; plucked one does not
            self.assertEqual(fresh.stations[st.key_id].epoch_hwm, 1)
            again = [e for f in later for e in fresh.hear(f, T0 + 3_100)]
            self.assertNotIn("item", [e.kind for e in again])          # and only once

    def test_live_state_waits_for_warm_up(self):
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({3}), ("lens.threat",))])
        lst = Listener(m, ephemeral=True)
        st = Station(SK, [StreamConfig("lens.threat", cls="live-state")], epoch=1, rng=random.Random(1), now_ms=T0)
        st.sing(T0, "lens.threat", text="elevated", state_key="now", ttl_s=120)
        evs = []
        for t in range(T0, T0 + 30_000, 100):
            for f in st.poll(t):
                evs.extend((t, e) for e in lst.hear(f, t))
            evs.extend((t, e) for e in lst.tick(t))
        items = [(t, e) for t, e in evs if e.kind == "item"]
        self.assertEqual(len(items), 1)
        loop = lst.stations[st.key_id].stream_loop_max[st.streams["lens.threat"].sid]
        self.assertGreaterEqual(items[0][0], T0 + loop)                # not before one advertised loop

    def test_warm_up_never_lands_an_older_value(self):
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({3}), ("lens.threat",))])
        lst = Listener(m, ephemeral=True)
        st = Station(SK, [StreamConfig("lens.threat", cls="live-state")], epoch=1, rng=random.Random(1), now_ms=T0)
        st.sing(T0, "lens.threat", text="old", state_key="now", ttl_s=120)
        old = st.poll(T0)
        st.sing(T0 + 500, "lens.threat", text="new", state_key="now", ttl_s=120)
        new = st.poll(T0 + 500)
        for f in new + old:                                             # newer first, then the stale copy
            lst.hear(f, T0 + 600)
        evs = [e for t in range(T0 + 600, T0 + 30_000, 250) for e in lst.tick(t)]
        self.assertEqual([e.data.get("text") for e in evs if e.kind == "item"], ["new"])


class PerKeyBoundsTest(unittest.TestCase):
    """#60: every per-key structure stays within the key's share, whatever a granted key sends."""

    CHAT = stream_id("chatter")

    def lst(self, quota=10, scopes=None, **kw):
        entry = StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3, 9}), ("chatter", "root"),
                             **({"scopes": scopes} if scopes else {}))
        return Listener(Manifest([entry]), ephemeral=True, per_key_quota=quota, **kw)

    def item(self, seq, t, stream=None, cls=1, ttl=30_000, extra=None):
        m = {1: 1, 2: stream or self.CHAT, 3: seq, 4: t, 5: t + ttl, 6: cls, 7: 1, 8: b"x", 11: 0, 13: 1}
        m.update(extra or {})
        return wire.sign_frame(wire.KIND_ITEM, SK, m)

    def pluck(self, seq, target, t, expires, scope=1):
        return wire.sign_frame(wire.KIND_PLUCK, SK, {1: 1, 2: self.CHAT, 3: seq, 4: t, 5: expires, 13: scope, 20: target})

    def beacon(self, bseq, streams, page=None, epoch=1):
        m = {1: epoch, 2: bseq, 3: T0, 4: 1000, 5: "p", 6: streams, 8: 16000}
        if page:
            m[7] = list(page)
        return wire.sign_frame(wire.KIND_BEACON, SK, m)

    def test_stream_hearing_is_admitted_frames_only_and_capped(self):
        lst = self.lst()
        for i in range(2000):  # distinct stream ids: 10 admitted, 1 990 over quota
            lst.hear(self.item(1, T0, stream=0x10000 + i), T0)
        st = lst.stations[SK_ID]
        self.assertEqual(len(lst.dedup), 10)
        self.assertEqual(len(st.last_stream_item), 10)
        st.last_stream_item.clear()
        evs = lst.hear(self.item(1, T0, stream=0x10000, extra={8: b"other bytes"}), T0)  # equivocation
        self.assertEqual([e.data["reason"] for e in evs], ["equivocation"])
        self.assertEqual(st.last_stream_item, {})
        lst.hear(self.item(1, T0, stream=0x10000), T0)                               # a benign repeat counts
        self.assertEqual(list(st.last_stream_item), [0x10000])

    def test_over_quota_frames_do_not_make_a_station_speak(self):
        lst = self.lst(quota=2)
        lst.hear(self.beacon(1, [[self.CHAT, 1, 1, 5000, 5000, 60, 300, 4000]]), T0)
        root = wire.sign_frame(wire.KIND_ITEM, SK, {1: 1, 2: stream_id("root"), 3: 1, 4: T0, 5: T0 + 600_000, 6: 9,
                                                    7: 7, 8: cbor.encode({1: "watch"}), 10: "root", 11: 0, 13: 1})
        lst.hear(root, T0)
        lst.hear(self.item(1, T0, stream=0x99), T0)                                  # fills the share
        self.assertEqual(lst.presence_state(SK_ID, T0), "EQUIPPED_QUIET")
        evs = lst.hear(self.item(2, T0), T0)                                         # refused on chatter
        self.assertEqual([e.data["reason"] for e in evs if e.kind == "evidence"], ["over-quota"])
        self.assertEqual(lst.presence_state(SK_ID, T0), "EQUIPPED_QUIET")

    def test_beacon_maps_hold_one_catalog(self):
        lst = self.lst()
        entry = lambda sid: [sid, 1, 1, 5000, 5000, 60, 300, 4000]
        for b in range(1, 201):                                                      # unpaged: each is the whole catalog
            lst.hear(self.beacon(b, [entry(0x20000 + b * 32 + j) for j in range(32)]), T0)
        st = lst.stations[SK_ID]
        self.assertEqual([len(st.stream_loops), len(st.stream_loop_max), len(st.stream_entries)], [32, 32, 32])
        self.assertIn(0x20000 + 200 * 32, st.stream_loops)                           # the latest catalog
        for p in range(4):                                                           # four pages of 32
            lst.hear(self.beacon(201 + p, [entry(0x30000 + p * 32 + j) for j in range(32)], page=(p, 4)), T0)
        self.assertEqual(len(st.stream_loop_max), 128)
        lst.hear(self.beacon(205, [entry(0x40000 + j) for j in range(32)], page=(0, 2)), T0)  # catalog shrinks
        self.assertEqual(sorted(st.catalog_pages), [0, 1])
        self.assertEqual(len(st.stream_loop_max), 64)
        lst.hear(self.item(1, T0, extra={1: 2}), T0)                                 # epoch advance clears all of it
        self.assertEqual([len(st.catalog_pages), len(st.stream_loops), len(st.stream_loop_max),
                          len(st.stream_entries)], [0, 0, 0, 0])
        self.assertEqual(list(st.last_stream_item), [self.CHAT])                     # only the new epoch's item

    def test_supersession_marks_count_against_the_key_share(self):
        lst = self.lst(warmup=False)
        refused = 0
        for i in range(500):                                                         # new state_key every 3.5 s
            t = T0 + i * 3_500
            evs = lst.hear(self.item(i + 1, t, cls=3, extra={10: f"k{i}"}), t)
            refused += sum(e.kind == "evidence" and e.data["reason"] == "over-quota" for e in evs)
            self.assertLessEqual(len(lst.hwm), 10)
            self.assertEqual(sum(lst.hwm_per_key.values()), len(lst.hwm))
        self.assertGreater(refused, 0)
        # Marks are never evicted early (§7.4, §7.8): the first ten were kept until they expired.
        lst = self.lst(quota=3, warmup=False)
        for i, key in enumerate(("a", "b", "c")):
            lst.hear(self.item(i + 1, T0, cls=3, extra={10: key}), T0)
        t = T0 + 40_000                                                              # dedup slots expired, marks live
        evs = lst.hear(self.item(4, t, cls=3, extra={10: "d"}), t)
        self.assertEqual([e.data["reason"] for e in evs if e.kind == "evidence"], ["over-quota"])
        self.assertEqual(sorted(k[2] for k in lst.hwm), ["a", "b", "c"])
        evs = lst.hear(self.item(5, t, cls=3, extra={10: "a"}), t)                   # a held key needs no new mark
        self.assertIn("item", [e.kind for e in evs])
        self.assertNotIn((SK_ID, 1, self.CHAT, 4), lst.dedup)                       # the refused frame left no slot
        later = max(v[3] for v in lst.hwm.values()) + 1
        evs = lst.hear(self.item(6, later, cls=3, extra={10: "d"}), later)           # room again once marks expire
        self.assertIn("item", [e.kind for e in evs])

    def test_pluck_expiry_is_clamped(self):
        lst = self.lst(quota=1)
        lst.hear(self.pluck(2, 1, T0, T0 + 50 * 365 * 86_400_000), T0)               # a far-future PLUCK
        day = 86_400_000
        self.assertEqual(max(lst.sticky_pluck.values()), T0 + day + 5_000)
        self.assertEqual(max(v[1] for v in lst.dedup.values()), T0 + day + 5_000)
        t = T0 + day + 5_001
        evs = lst.hear(self.item(3, t), t)                                            # its slot is free after one day
        self.assertIn("item", [e.kind for e in evs])

    def test_pluck_must_match_a_held_target(self):
        lst = self.lst(scopes=frozenset({1, 2}))
        lst.hear(self.item(1, T0, ttl=60_000), T0)
        before = (dict(lst.dedup), dict(lst.sticky_pluck))
        for bad in (self.pluck(2, 1, T0 + 1, T0 + 3_600_000), self.pluck(2, 1, T0 + 1, T0 + 60_000, scope=2)):
            evs = lst.hear(bad, T0 + 1)
            self.assertEqual([e.data["reason"] for e in evs if e.kind == "evidence"], ["pluck-mismatch"])
            self.assertEqual((dict(lst.dedup), dict(lst.sticky_pluck)), before)     # state-neutral
        self.assertEqual(len(lst.current), 1)
        evs = lst.hear(self.pluck(2, 1, T0 + 1, T0 + 60_000), T0 + 1)
        self.assertEqual([e.kind for e in evs], ["withdrawn"])
        self.assertEqual(lst.sticky_pluck[(SK_ID, 1, self.CHAT, 1)], lst.dedup[(SK_ID, 1, self.CHAT, 1)][1])

    def test_state_v2_round_trip_and_v1_still_loads(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "listener.json"
            entry = StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3}), ("chatter",))
            lst = Listener(Manifest([entry]), state_path=path, warmup=False)
            lst.hear(self.item(1, T0, ttl=60_000), T0)
            lst.hear(self.item(2, T0, cls=3, extra={10: "k"}), T0)
            fresh = Listener(Manifest([entry]), state_path=path, warmup=False)
            self.assertEqual(fresh.dedup, lst.dedup)
            self.assertEqual(fresh.hwm_per_key, {SK_ID: 1})
            evs = fresh.hear(self.pluck(3, 1, T0 + 1, T0 + 3_600_000), T0 + 1)        # the check survives restart
            self.assertEqual([e.data["reason"] for e in evs if e.kind == "evidence"], ["pluck-mismatch"])
            state = json.loads(path.read_text())
            state["version"] = 1
            state["dedup"] = [row[:6] for row in state["dedup"]]
            path.write_text(json.dumps(state))
            old = Listener(Manifest([entry]), state_path=path, warmup=False)
            self.assertEqual({v[2] for v in old.dedup.values()}, {None})              # v1 rows: no target check
            evs = old.hear(self.pluck(3, 1, T0 + 1, T0 + 3_600_000), T0 + 1)
            self.assertNotIn("evidence", [e.kind for e in evs])


class RobustnessTest(unittest.TestCase):
    def test_garbage_never_escapes(self):
        _, lst = setup()
        for data in (b"", b"BC", b'{"a":1e400}', b"BC\x02\x01" + bytes(8) + b"\xff" * 80, bytes(1300)):
            evs = lst.hear(data, T0)
            self.assertEqual([e.kind for e in evs], ["evidence"])


if __name__ == "__main__":
    unittest.main()
