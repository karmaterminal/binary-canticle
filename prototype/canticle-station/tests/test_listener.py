import random
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, vectors, wire
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig, next_epoch

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))


def setup():
    st = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=1,
                 rng=random.Random(1), now_ms=T0)
    m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 9}), ("chatter", "root"))])
    return st, Listener(m)


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
        lst = Listener(m, dedup_capacity=6)                              # 3 tuples per key
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


class RobustnessTest(unittest.TestCase):
    def test_garbage_never_escapes(self):
        _, lst = setup()
        for data in (b"", b"BC", b'{"a":1e400}', b"BC\x02\x01" + bytes(8) + b"\xff" * 80, bytes(1300)):
            evs = lst.hear(data, T0)
            self.assertEqual([e.kind for e in evs], ["evidence"])


if __name__ == "__main__":
    unittest.main()
