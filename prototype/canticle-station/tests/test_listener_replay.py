"""#175: what a receiver keeps across a restart, so a captured old stream can't come back as fresh,
and why a rise in δ̂ can't re-admit an item it already heard."""
import random
import tempfile
import unittest
from pathlib import Path

from canticle import wire
from canticle import listener
from canticle.listener import Listener
from canticle.station import Station, StreamConfig

from test_listener import SK, T0, setup

HOUR = 3_600_000


def kind(lst, frame, now):
    return wire.parse(frame, lst.manifest.resolve, now, 0).kind


class RestartReplayTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = Path(d.name) / "listener.json"
        self.st, eph = setup()
        self.manifest = eph.manifest

    def listener(self):
        return Listener(self.manifest, state_path=self.path)

    def heard_then_quiet(self, lst, frames, start):
        """Hear ``frames`` at ``start``, then two quiet minutes, then stop (the state is saved)."""
        events = [e.kind for f in frames for e in lst.hear(f, start)]
        for t in range(start, start + 120_000, 1_000):
            lst.tick(t)
        lst._save_if_dirty(force=True)
        return events

    def test_a_captured_beacon_and_item_do_not_land_fresh_after_a_restart(self):
        self.st.sing(T0, "chatter", text="an hour old", ttl_s=60)
        captured = self.st.poll(T0)
        lst = self.listener()
        self.assertIn("item", self.heard_then_quiet(lst, captured, T0))
        before = lst.stations[SK_ID()].offset_ms
        fresh = self.listener()                                      # restart
        evs = [e for f in captured for e in fresh.hear(f, T0 + HOUR)]
        self.assertNotIn("item", [e.kind for e in evs])
        self.assertEqual(fresh.stations[SK_ID()].offset_ms, before)  # the replay did not move δ̂

    def test_a_restart_keeps_the_beacon_mark(self):
        captured = self.st.poll(T0)
        self.assertEqual([kind(self.listener(), f, T0) for f in captured], [wire.KIND_BEACON])
        lst = self.listener()
        self.heard_then_quiet(lst, captured, T0)
        fresh = self.listener()
        self.assertEqual(fresh.stations[SK_ID()].bseq, lst.stations[SK_ID()].bseq)
        fresh.hear(captured[0], T0 + HOUR)
        self.assertEqual(fresh.last_dedup, "duplicate")              # the same beacon again, not a new one
        self.assertIsNone(fresh.stations[SK_ID()].last_beacon)       # and it does not make the station present

    def test_a_beacon_of_an_epoch_it_missed_cannot_raise_the_offset(self):
        lst = self.listener()
        self.heard_then_quiet(lst, self.st.poll(T0), T0)
        floor = lst.stations[SK_ID()].offset_ms
        # The station restarts while the receiver is down; what it sang then is captured, not heard.
        later = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=2,
                        rng=random.Random(2), now_ms=T0 + 200_000)
        later.sing(T0 + 200_000, "chatter", text="from an epoch it missed", ttl_s=60)
        captured = later.poll(T0 + 200_000)
        fresh = self.listener()
        evs = [e for f in captured for e in fresh.hear(f, T0 + HOUR)]
        self.assertNotIn("item", [e.kind for e in evs])
        self.assertEqual(fresh.stations[SK_ID()].offset_ms, floor)

    def test_honest_beacons_after_a_restart_still_count(self):
        lst = self.listener()
        self.heard_then_quiet(lst, self.st.poll(T0), T0)
        fresh = self.listener()
        t = T0 + 130_000
        self.st.sing(t, "chatter", text="after the restart", ttl_s=60)
        evs = [e.kind for f in self.st.poll(t) for e in fresh.hear(f, t)]
        self.assertIn("item", evs)
        self.assertIsNotNone(fresh.stations[SK_ID()].last_beacon)


    def test_residual_a_full_run_of_a_missed_epoch_rolls_the_floor_out(self):
        """🪨 on #175: what this does not close. δ̂ is the minimum of the last 16 samples, so 16 captured beacons
        of an epoch the receiver never heard push the honest floor out, and with no skew bound an old item
        then lands. The same as a first join; `max_skew_s` is the bound for that. If this ever fails, the
        residual is closed: say so on #175."""
        lst = self.listener()
        self.heard_then_quiet(lst, self.st.poll(T0), T0)
        later = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=2,
                        rng=random.Random(2), now_ms=T0 + 200_000)
        start = T0 + 200_000
        later.sing(start + 20_000, "chatter", text="after a full run", ttl_s=60)
        captured = []
        for t in range(start, start + 20_001, 100):
            captured += later.poll(t)
        beacons = [f for f in captured if kind(lst, f, t) == wire.KIND_BEACON]
        self.assertGreaterEqual(len(beacons), 17)
        fresh = self.listener()
        evs = [e for f in captured for e in fresh.hear(f, T0 + HOUR)]
        self.assertIn("item", [e.kind for e in evs])
        self.assertGreater(fresh.stations[SK_ID()].offset_ms, HOUR - 300_000)

    def test_a_crash_loses_at_most_the_last_beacons_of_the_mark(self):
        lst = self.listener()
        beacons = []
        for t in range(T0, T0 + 30_000, 100):
            for f in self.st.poll(t):
                if kind(lst, f, t) == wire.KIND_BEACON:
                    beacons.append((t, f))
                lst.hear(f, t)
            lst.tick(t)
        # no clean save: a crash
        fresh = self.listener()
        old = [f for t, f in beacons if t <= T0 + 30_000 - listener.MARK_SAVE_MS - 1_000]
        self.assertTrue(old)
        for f in old:
            fresh.hear(f, T0 + HOUR)
            self.assertEqual(fresh.last_dedup, "duplicate")

    def test_a_state_file_without_marks_still_loads_and_says_so(self):
        lst = self.listener()
        self.heard_then_quiet(lst, self.st.poll(T0), T0)
        import json
        state = json.loads(self.path.read_text())
        state["version"] = 3
        del state["beacons"]
        self.path.write_text(json.dumps(state))
        fresh = self.listener()
        self.assertTrue(fresh.loaded_without_marks)
        self.assertEqual(fresh.stations[SK_ID()].bseq, 0)


class SkewBoundTest(unittest.TestCase):
    """The opt-in bound (#175): what it refuses, and that a refusal leaves no trace."""

    def setUp(self):
        self.st, eph = setup()
        self.manifest = eph.manifest

    def test_off_by_default_so_a_clock_an_hour_wrong_still_delivers(self):
        lst = Listener(self.manifest, ephemeral=True)
        self.st.sing(T0, "chatter", text="from a slow clock", ttl_s=60)
        evs = [e.kind for f in self.st.poll(T0) for e in lst.hear(f, T0 + HOUR)]
        self.assertIn("item", evs)

    def test_a_first_join_refuses_a_stream_older_than_the_bound(self):
        lst = Listener(self.manifest, ephemeral=True, max_skew_ms=300_000)
        self.st.sing(T0, "chatter", text="an hour old", ttl_s=60)
        evs = [e for f in self.st.poll(T0) for e in lst.hear(f, T0 + HOUR)]
        self.assertNotIn("item", [e.kind for e in evs])
        self.assertIn("clock-skew", [e.data.get("reason") for e in evs if e.kind == "evidence"])
        st = lst.stations.get(SK_ID())                       # nothing was kept about the station at all
        self.assertTrue(st is None or (st.epoch_hwm, st.bseq, list(st.offsets), st.last_beacon) == (0, 0, [], None))

    def test_inside_the_bound_a_skewed_clock_still_delivers(self):
        lst = Listener(self.manifest, ephemeral=True, max_skew_ms=300_000)
        self.st.sing(T0, "chatter", text="two minutes slow", ttl_s=60)
        evs = [e.kind for f in self.st.poll(T0) for e in lst.hear(f, T0 + 120_000)]
        self.assertIn("item", evs)
        self.assertEqual(lst.stations[SK_ID()].offset_ms, 120_000)

    def test_a_negative_bound_is_refused(self):
        with self.assertRaises(ValueError):
            Listener(self.manifest, ephemeral=True, max_skew_ms=-1)


class OffsetRiseTest(unittest.TestCase):
    """🌿's case on #175: a station clock 20 s behind, its item heard before any beacon."""

    def test_a_rise_in_the_offset_does_not_readmit_an_item_it_heard(self):
        behind = 20_000
        st, lst = setup()
        st.sing(T0, "chatter", text="once", ttl_s=60)
        frames = st.poll(T0)
        beacons = [f for f in frames if kind(lst, f, T0 + behind) == wire.KIND_BEACON]
        items = [f for f in frames if kind(lst, f, T0 + behind) == wire.KIND_ITEM]
        self.assertEqual((len(beacons), len(items)), (1, 1))
        first = [e.kind for e in lst.hear(items[0], T0 + behind)]   # δ̂ is 0: it expires 20 s early here
        self.assertEqual(first, ["item"])
        lst.hear(beacons[0], T0 + behind + 1_000)                   # δ̂ rises to 20 s
        self.assertGreaterEqual(lst.stations[SK_ID()].offset_ms, behind)
        evs = []
        for t in range(T0 + behind + 1_000, T0 + behind + 55_000, 1_000):
            evs.extend(lst.tick(t))
        self.assertIn("expired", [e.kind for e in evs])
        again = [e.kind for e in lst.hear(items[0], T0 + behind + 50_000)]   # its ordinary loop, still in its life
        self.assertNotIn("item", again)


def SK_ID():
    return wire.key_id(wire.public_key_bytes(SK))


if __name__ == "__main__":
    unittest.main()
