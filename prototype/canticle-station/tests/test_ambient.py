import random
import tempfile
import unittest
from pathlib import Path

from canticle.ambient import MAX_DURATION_S, AmbientConfig, FixtureError, load_fixture, run

LINES = ("the lamp is lit", "breathe", "the lamp is lit", "quiet on the hill")


class Clock:
    """A virtual clock: sleep advances it, so a ten-minute run takes no real time."""

    def __init__(self):
        self.t = 1000.0

    def now(self) -> float:
        return self.t

    def wall_ms(self) -> int:
        return int(self.t * 1000)

    def sleep(self, s: float) -> None:
        self.t += max(s, 0.001)


def simulate(cfg: AmbientConfig, seed: int = 7, respond=None, stop_at=None):
    clock, records, sent = Clock(), [], []

    def send(req):
        sent.append((clock.now(), req))
        return respond(req) if respond else {"ok": True, "seq": len(sent), "size": 90, "ttl_s": req["ttl"],
                                             "loop_ms": 10_000, "clamp": "class_min"}

    stop = (lambda: clock.now() >= stop_at) if stop_at else (lambda: False)
    summary = run(cfg, send, records.append, stop=stop, rng=random.Random(seed),
                  clock=clock.now, wall_ms=clock.wall_ms, sleep=clock.sleep)
    return summary, records, sent


class AmbientScheduleTest(unittest.TestCase):
    def test_ticks_stay_within_the_gap_and_the_run_ends_on_time(self):
        cfg = AmbientConfig("hymn", LINES, duration_s=600)
        summary, records, _ = simulate(cfg)
        ticks = [r["t_ms"] for r in records if r["event"] in ("sing", "breath", "capped")]
        gaps = [(b - a) / 1000 for a, b in zip(ticks, ticks[1:])]
        self.assertTrue(all(2.0 - 0.01 <= g <= 10.0 + 0.51 for g in gaps), (min(gaps), max(gaps)))
        self.assertEqual(summary["reason"], "duration")
        self.assertLessEqual((records[-1]["t_ms"] - records[0]["t_ms"]) / 1000, 600.5)
        self.assertEqual(summary["model_calls"], 0)

    def test_breaths_and_repetition_happen(self):
        summary, records, _ = simulate(AmbientConfig("hymn", LINES, breath=0.3, duration_s=900))
        self.assertGreater(summary["breath"], 0)
        texts = [r["text"] for r in records if r["event"] == "sing"]
        self.assertLess(len(set(texts)), len(texts))  # lines repeat; each repeat is a new item

    def test_every_sing_carries_the_ttl_and_class_and_nothing_else_is_asked(self):
        _, _, sent = simulate(AmbientConfig("hymn", LINES, ttl_s=60, duration_s=120))
        for _, req in sent:
            self.assertEqual(set(req), {"op", "stream", "class", "text", "ttl"})
            self.assertEqual((req["op"], req["class"], req["ttl"]), ("sing", "ambient", 60))

    def test_per_minute_cap(self):
        cfg = AmbientConfig("hymn", LINES, min_gap_s=1, max_gap_s=1, breath=0, max_per_minute=5, duration_s=180)
        summary, _, sent = simulate(cfg)
        times = [t for t, _ in sent]
        for t in times:
            self.assertLessEqual(sum(1 for u in times if t - 60 < u <= t), 5)
        self.assertGreater(summary["capped"], 0)

    def test_stop_signal_ends_the_run_early(self):
        summary, records, _ = simulate(AmbientConfig("hymn", LINES, duration_s=600), stop_at=1030)
        self.assertEqual(summary["reason"], "signal")
        self.assertLess(records[-1]["t_ms"] / 1000, 1031)

    def test_refusals_are_logged_and_the_run_continues(self):
        summary, records, _ = simulate(AmbientConfig("hymn", LINES, breath=0, duration_s=60),
                                       respond=lambda req: {"ok": False, "error": "BUDGET_EXHAUSTED"})
        self.assertEqual(summary["reason"], "duration")
        self.assertGreater(summary["refused"], 3)
        self.assertEqual(summary["sing"], 0)

    def test_an_unreachable_station_stops_the_run(self):
        def gone(req):
            raise FileNotFoundError("no socket")
        summary, _, sent = simulate(AmbientConfig("hymn", LINES, breath=0, duration_s=600), respond=gone)
        self.assertEqual(summary["reason"], "station-unreachable")
        self.assertEqual(len(sent), 3)


class AmbientBoundsTest(unittest.TestCase):
    def test_bounds_are_enforced(self):
        for bad in ({"duration_s": MAX_DURATION_S + 1}, {"min_gap_s": 0.5}, {"min_gap_s": 5, "max_gap_s": 4},
                    {"breath": 1.0}, {"cls": "alarm"}, {"cls": "live-state"}, {"max_per_minute": 0}):
            with self.assertRaises(ValueError, msg=bad):
                AmbientConfig("hymn", LINES, **bad)

    def test_fixture_loading(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hymn.txt"
            p.write_text("# a comment\n\nfirst line\n  second line  \n")
            self.assertEqual(load_fixture(p, 64), ("first line", "second line"))
            p.write_text("x" * 65 + "\n")
            with self.assertRaises(FixtureError):
                load_fixture(p, 64)
            p.write_text("# only comments\n")
            with self.assertRaises(FixtureError):
                load_fixture(p, 64)


if __name__ == "__main__":
    unittest.main()
