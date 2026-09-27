import random
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, vectors, wire
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig

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

    def test_clock_offset_only_makes_expiry_earlier(self):
        it = wire.Item(epoch=1, stream=1, seq=1, issued_at=T0, expires_at=T0 + 60_000, cls=1, ctype=1, body=b"x")
        self.assertEqual(wire.local_expiry_ms(it, 5_000), T0 + 60_000)
        self.assertEqual(wire.local_expiry_ms(it, -5_000), T0 + 55_000)

    def test_expiry_is_clamped_to_class_max(self):
        it = wire.Item(epoch=1, stream=1, seq=1, issued_at=T0, expires_at=T0 + 10**9, cls=1, ctype=1, body=b"x")
        self.assertEqual(wire.local_expiry_ms(it), T0 + 300_000)


class RobustnessTest(unittest.TestCase):
    def test_garbage_never_escapes(self):
        _, lst = setup()
        for data in (b"", b"BC", b'{"a":1e400}', b"BC\x02\x01" + bytes(8) + b"\xff" * 80, bytes(1300)):
            evs = lst.hear(data, T0)
            self.assertEqual([e.kind for e in evs], ["evidence"])


if __name__ == "__main__":
    unittest.main()
