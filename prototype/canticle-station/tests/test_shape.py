"""``canticle shape`` (#133): a shape-only human view over the host daemon.

The projection is checked twice: on a ``TapView`` fed records directly, and end to end against the in-process
daemon (``SnapshotCase``), through the gateway's HTTP port. Station text, purpose and identifiers never appear in
either answer.
"""

import asyncio
import json
import pathlib
import tempfile
import unittest

from canticle import runner
from canticle.shape import (DRUM_BUCKET_MS, DRUM_BUCKETS, DRUM_ROW_MS, DRUM_ROWS, MINUTE_MS, PRESENCE_STATES,
                             RIVER_MAX, STALE_MS, WINDOW_MIN, ShapeView, _StampedView, follow, run_shape)
from canticle.tuner import TunerHttp

from test_join_snapshot import SnapshotCase
from test_tap import EVIL, bootstrap, frame, rec

STATION_KEYS = {"name", "state", "beacon_age_ms", "streams"}
STREAM_KEYS = {"stream", "live", "newest_age_ms"}
TOP_KEYS = {"now_ms", "synthetic", "connected", "daemon", "receive", "stations"}


def presence(seq, name, state="EQUIPPED_SPEAKING", key_id="aa" * 8):
    return rec("presence", seq, key_id=key_id, station={"name": name, "principal": None}, state=state,
               last_beacon_at=1)


def view_with(*records, stations=("cael",), clock=None):
    """A connected view fed ``records``, each applied at ``clock()`` (default: 10 000 ms, the projections' ``now``)."""
    clock = clock or (lambda: 10_000)
    sv = ShapeView(stations, clock=clock)
    tv = _StampedView([("*", "*")], clock, sv.flow)
    bootstrap(tv, join=False)
    for r in records:
        tv.apply(r)
    sv.tap, sv.connected = tv, True
    return sv


def keys_ok(test, out):
    test.assertEqual(set(out), TOP_KEYS)
    for st in out["stations"]:
        test.assertEqual(set(st), STATION_KEYS)
        for s in st["streams"]:
            test.assertEqual(set(s), STREAM_KEYS)


class ShapeViewTest(unittest.TestCase):
    def test_counts_and_ages_for_a_named_station_and_nothing_said(self):
        sv = view_with(presence(3, "cael"),
                       rec("health", 4, state="ok", reasons=[], beacon_age_ms={"aa" * 8: 900}),
                       frame("i1", 5, text=EVIL, heard=1_000), frame("i2", 6, text="second", heard=4_000),
                       frame("i3", 7, stream="lens.threat", heard=2_000))
        out = sv.project(10_000)
        keys_ok(self, out)
        self.assertEqual(out["daemon"], "ok")
        (cael,) = out["stations"]
        self.assertEqual((cael["name"], cael["state"], cael["beacon_age_ms"]), ("cael", "EQUIPPED_SPEAKING", 900))
        self.assertEqual(cael["streams"], [{"stream": "chatter", "live": 2, "newest_age_ms": 6_000},
                                           {"stream": "lens.threat", "live": 1, "newest_age_ms": 8_000}])
        text = json.dumps(out)
        for needle in ("rm -rf", "canticle:heard", "second", "i1", "aa" * 8, "purpose", "lineage", "seq"):
            self.assertNotIn(needle, text)

    def test_only_named_stations_appear(self):
        sv = view_with(presence(3, "cael"), presence(4, "rune", key_id="bb" * 8), frame("i1", 5, station="rune"),
                       stations=())
        self.assertEqual(sv.project(10)["stations"], [])
        sv.allowed = ["rune"]
        (rune,) = sv.project(10)["stations"]
        self.assertEqual((rune["name"], rune["streams"][0]["live"]), ("rune", 1))

    def test_a_named_station_never_heard_reads_not_heard(self):
        out = view_with(stations=("emeric",)).project(10)
        self.assertEqual(out["stations"], [{"name": "emeric", "state": "not_heard", "beacon_age_ms": None,
                                            "streams": []}])

    def test_a_state_word_outside_the_closed_set_is_not_echoed(self):
        sv = view_with(presence(3, "cael", state="<script>alert(1)</script>"),
                       rec("health", 4, state="pwned", reasons=["x"], beacon_age_ms={"aa" * 8: "lots"}))
        out = sv.project(10)
        self.assertEqual(out["stations"][0]["state"], "unknown")
        self.assertIsNone(out["stations"][0]["beacon_age_ms"])
        self.assertEqual(out["daemon"], "unknown")
        self.assertNotIn("script", json.dumps(out))

    def test_every_listener_presence_word_passes(self):
        for state in PRESENCE_STATES:
            self.assertEqual(view_with(presence(3, "cael", state=state)).project(10)["stations"][0]["state"], state)

    def test_disconnected_shows_named_stations_unheard(self):
        sv = view_with(presence(3, "cael"), frame("i1", 4))
        sv.connected = False
        out = sv.project(10)
        keys_ok(self, out)
        self.assertEqual((out["connected"], out["daemon"], out["receive"]), (False, "unknown", "unknown"))
        self.assertEqual(out["stations"][0]["state"], "not_heard")

    def test_a_beacon_age_counts_on_from_its_health_record_until_the_connection_is_stale(self):
        """The daemon's ages are true when its health arrives (every 10 s); between records, and if none comes, the
        answer ages them on the gateway's clock rather than repeating them (🌫 on #134)."""
        clock = [1_000]
        sv = view_with(presence(3, "cael"), rec("health", 4, state="ok", reasons=[], beacon_age_ms={"aa" * 8: 900}),
                       clock=lambda: clock[0])
        self.assertEqual(sv.project(1_000)["stations"][0]["beacon_age_ms"], 900)
        self.assertEqual(sv.project(11_000)["stations"][0]["beacon_age_ms"], 10_900)
        at_bound = sv.project(1_000 + STALE_MS)
        self.assertTrue(at_bound["connected"])
        self.assertEqual(at_bound["stations"][0]["beacon_age_ms"], 900 + STALE_MS)
        stale = sv.project(1_000 + STALE_MS + 1)
        keys_ok(self, stale)
        self.assertEqual((stale["connected"], stale["daemon"], stale["receive"]), (False, "unknown", "unknown"))
        self.assertEqual((stale["stations"][0]["state"], stale["stations"][0]["beacon_age_ms"]), ("not_heard", None))
        clock[0] = 20_000   # a fresh health record re-anchors the ages
        sv.tap.apply(rec("health", 5, state="ok", reasons=[], beacon_age_ms={"aa" * 8: 300}))
        self.assertEqual(sv.project(21_000)["stations"][0]["beacon_age_ms"], 1_300)
        self.assertTrue(sv.project(20_000 + STALE_MS)["connected"])

    def test_a_join_with_no_health_yet_goes_stale_from_the_join(self):
        clock = [5_000]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        self.assertTrue(sv.project(5_000 + STALE_MS)["connected"])
        self.assertIsNone(sv.project(5_000)["stations"][0]["beacon_age_ms"])
        self.assertFalse(sv.project(5_000 + STALE_MS + 1)["connected"])

    def test_a_negative_age_is_not_shown(self):
        sv = view_with(presence(3, "cael"), rec("health", 4, state="ok", reasons=[], beacon_age_ms={"aa" * 8: -5}))
        self.assertIsNone(sv.project(10_000)["stations"][0]["beacon_age_ms"])

    def test_demo_fixture_is_marked_synthetic_and_ignores_the_daemon(self):
        sv = view_with(presence(3, "cael"))
        sv.demo_fixture = True
        out = sv.project(10)
        keys_ok(self, out)
        self.assertTrue(out["synthetic"])
        self.assertTrue(all(s["name"].startswith("demo-") for s in out["stations"]))


FLOW_KEYS = {"now_ms", "since_ms", "minute_ms", "synthetic", "minutes", "stations", "river"}


def health(seq, age, key_id="aa" * 8):
    return rec("health", seq, state="ok", reasons=[], beacon_age_ms={key_id: age})


class FlowTest(unittest.TestCase):
    """``/api/flow`` (#135): the last hour minute by minute, and the last arrivals, with nothing said."""

    def test_a_minute_records_observation_beacon_arrivals_and_state_and_nothing_said(self):
        clock = [5 * MINUTE_MS + 1_000]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(health(4, 900))
        sv.tap.apply(frame("i1", 5, text=EVIL, heard=clock[0]))
        sv.tap.apply(frame("i2", 6, text="second", heard=clock[0]))
        sv.tap.apply(frame("i3", 7, stream="lens.threat", text="third", heard=clock[0]))
        clock[0] = 7 * MINUTE_MS + 30_000
        sv.tap.apply(frame("i4", 8, text="later", heard=clock[0]))
        out = sv.flow.project(clock[0])
        self.assertEqual(set(out), FLOW_KEYS)
        self.assertEqual(len(out["minutes"]), WINDOW_MIN)
        self.assertEqual(out["minutes"][-1]["t"], 7 * MINUTE_MS)
        by_t = {m["t"]: i for i, m in enumerate(out["minutes"])}
        five, six, seven = (out["stations"][0]["minutes"][by_t[m * MINUTE_MS]] for m in (5, 6, 7))
        self.assertEqual(five, {"beacon": True, "state": "EQUIPPED_SPEAKING",
                                "arrivals": [{"stream": "chatter", "n": 2}, {"stream": "lens.threat", "n": 1}]})
        self.assertEqual(six, {"beacon": False, "state": None, "arrivals": []})
        self.assertEqual(seven["arrivals"], [{"stream": "chatter", "n": 1}])
        self.assertFalse(seven["beacon"], "no health record reported a beacon in that minute")
        self.assertEqual([out["minutes"][by_t[m * MINUTE_MS]]["observed"] for m in (5, 6, 7)], [True, False, False])
        self.assertEqual(out["river"][0], {"at_ms": 7 * MINUTE_MS + 30_000, "station": "cael", "stream": "chatter"})
        self.assertEqual(len(out["river"]), 4)
        text = json.dumps(out)
        for needle in ("rm -rf", "canticle:heard", "second", "third", "later", "i1", "aa" * 8, "purpose", "seq"):
            self.assertNotIn(needle, text)

    def test_a_replay_is_not_a_new_arrival(self):
        """🌫 on #136: a daemon restart re-surfaces a still-live item (`dedup: resurfaced`), and the same item can
        reach the gateway twice; neither is a new emission."""
        clock = [MINUTE_MS]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(frame("i1", 4, heard=clock[0]))
        again = frame("i1", 5, heard=clock[0] + 5)
        sv.tap.apply(again)
        resurfaced = {**frame("i2", 6, heard=clock[0]), "dedup": "resurfaced"}
        sv.tap.apply(resurfaced)
        sv.tap.apply({**frame("i3", 7, heard=clock[0]), "dedup": "first"})
        out = sv.flow.project(clock[0])
        self.assertEqual(out["stations"][0]["minutes"][-1]["arrivals"], [{"stream": "chatter", "n": 2}])
        self.assertEqual(len(out["river"]), 2)
        self.assertNotIn("i1", json.dumps(out), "remembered identities are never served")

    def test_an_item_already_expired_when_consumed_is_not_an_arrival(self):
        clock = [10 * MINUTE_MS]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(frame("i1", 4, heard=clock[0] - 5_000, expiry=clock[0]))
        sv.tap.apply(frame("i2", 5, heard=clock[0] - 5_000, expiry=clock[0] - 1))
        self.assertEqual(sv.flow.project(clock[0])["river"], [])

    def test_an_arrival_is_placed_at_its_heard_time(self):
        """A live item the gateway consumes late lands in the minute the daemon heard it, not the gateway's minute."""
        clock = [10 * MINUTE_MS + 5_000]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(frame("i1", 4, heard=9 * MINUTE_MS + 50_000))
        out = sv.flow.project(clock[0])
        row = out["stations"][0]["minutes"]
        self.assertEqual((row[-2]["arrivals"], row[-1]["arrivals"]), ([{"stream": "chatter", "n": 1}], []))
        self.assertEqual(out["river"][0]["at_ms"], 9 * MINUTE_MS + 50_000)

    def test_the_river_is_newest_heard_first_whatever_order_it_was_consumed_in(self):
        clock = [10 * MINUTE_MS]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(frame("i1", 4, heard=clock[0] - 1_000))
        sv.tap.apply(frame("i2", 5, heard=clock[0] - 3_000, stream="lens.threat"))
        sv.tap.apply(frame("i3", 6, heard=clock[0] - 2_000))
        self.assertEqual([r["at_ms"] for r in sv.flow.project(clock[0])["river"]],
                         [clock[0] - 1_000, clock[0] - 2_000, clock[0] - 3_000])

    def test_only_named_stations_are_kept(self):
        sv = view_with(presence(3, "cael"), presence(4, "rune", key_id="bb" * 8), stations=("cael",))
        sv.tap.apply(frame("i1", 5, station="rune"))
        sv.tap.apply(health(6, 100, key_id="bb" * 8))
        out = sv.flow.project(10_000)
        self.assertEqual([s["name"] for s in out["stations"]], ["cael"])
        self.assertEqual(out["river"], [])
        self.assertNotIn("rune", json.dumps(out))

    def test_the_window_is_an_hour_and_the_river_is_bounded(self):
        clock = [0]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        seq = 4
        for i in range(RIVER_MAX + 5):
            sv.tap.apply(frame(f"i{i}", seq))
            seq += 1
        self.assertEqual(len(sv.flow.river), RIVER_MAX)
        clock[0] = WINDOW_MIN * MINUTE_MS   # minute 0 has just left the window
        sv.tap.apply(health(seq, 10))
        out = sv.flow.project(clock[0])
        self.assertEqual(out["minutes"][0]["t"], MINUTE_MS)
        self.assertTrue(all(not m["arrivals"] for m in out["stations"][0]["minutes"]))
        self.assertEqual(out["river"], [], "arrivals older than the window are not shown")
        self.assertNotIn(0, sv.flow.minutes["cael"], "minute 0's arrivals were pruned")
        self.assertTrue(out["stations"][0]["minutes"][-2]["beacon"], "a beacon 10 ms before minute 60 is minute 59's")

    def test_a_state_outside_the_closed_set_is_not_echoed_and_a_wild_age_marks_no_beacon(self):
        clock = [MINUTE_MS * 3]
        sv = view_with(presence(3, "cael", state="<script>"), clock=lambda: clock[0])
        sv.tap.apply(health(4, 10 * MINUTE_MS))
        row = sv.flow.project(clock[0])["stations"][0]["minutes"]
        self.assertEqual(row[-1]["state"], "unknown")
        self.assertFalse(any(m["beacon"] for m in row))
        self.assertNotIn("script", json.dumps(sv.flow.project(clock[0])))

    def test_demo_flow_is_marked_synthetic(self):
        sv = view_with(presence(3, "cael"))
        sv.demo_fixture = True
        out = sv.flow_project(10 * MINUTE_MS)
        self.assertEqual(set(out), FLOW_KEYS)
        self.assertTrue(out["synthetic"])
        self.assertTrue(all(s["name"].startswith("demo-") for s in out["stations"]))


DRUM_KEYS = {"now_ms", "since_ms", "synthetic", "start_ms", "bucket_ms", "row_ms", "rows", "observed", "streams",
             "stations"}


class DrumTest(unittest.TestCase):
    """``/api/drum``: a helicorder day in 10 s buckets, sparse, with the same arrival gate as ``/api/flow``."""

    def test_buckets_index_from_the_first_row_and_nothing_is_said(self):
        now = 200 * DRUM_ROW_MS + 7 * MINUTE_MS + 25_000          # 7m25s into a row
        clock = [now - 30_000]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(health(4, 2_000))                             # observed at now-30 s; beacon heard at now-32 s
        clock[0] = now - 20_000
        sv.tap.apply(health(5, 1_000))                             # the next 10 s bucket: one observed range
        clock[0] = now - 10_000                                    # consumed 5 s after the daemon heard them
        sv.tap.apply(frame("i1", 6, text=EVIL, heard=now - 15_000))
        sv.tap.apply(frame("i2", 7, stream="lens.threat", text="second", heard=now - 15_000))
        sv.tap.apply(frame("i1", 8, text=EVIL, heard=now - 14_000))   # the same item again: not counted
        out = sv.flow.project_drum(now)
        self.assertEqual(set(out), DRUM_KEYS)
        self.assertEqual(out["start_ms"], (200 - DRUM_ROWS + 1) * DRUM_ROW_MS)
        self.assertEqual((out["rows"], out["row_ms"], out["bucket_ms"]), (DRUM_ROWS, DRUM_ROW_MS, DRUM_BUCKET_MS))
        idx = lambda t: (t - out["start_ms"]) // DRUM_BUCKET_MS
        self.assertEqual(out["observed"], [[idx(now - 30_000), idx(now - 20_000) + 1]])
        self.assertEqual(out["streams"], ["chatter", "lens.threat"])
        (cael,) = out["stations"]
        self.assertEqual(cael["beacons"], [idx(now - 32_000), idx(now - 21_000)])
        self.assertEqual(cael["arrivals"], [[idx(now - 15_000), 0, 1], [idx(now - 15_000), 1, 1]])
        self.assertLess(max(i for i, _, _ in cael["arrivals"]), DRUM_BUCKETS)
        text = json.dumps(out)
        for needle in ("rm -rf", "canticle:heard", "second", "i1", "aa" * 8, "purpose", "seq"):
            self.assertNotIn(needle, text)

    def test_a_day_is_kept_and_no_more(self):
        clock = [5 * DRUM_ROW_MS]
        sv = view_with(presence(3, "cael"), clock=lambda: clock[0])
        sv.tap.apply(health(4, 10))
        sv.tap.apply(frame("i1", 5, heard=clock[0]))
        clock[0] += DRUM_ROWS * DRUM_ROW_MS + DRUM_BUCKET_MS       # a day and a bucket later
        sv.tap.apply(health(6, 10))
        out = sv.flow.project_drum(clock[0])
        self.assertEqual(out["stations"][0]["arrivals"], [])
        self.assertEqual(len(out["observed"]), 1, "only the new health record's bucket is still in the day")
        self.assertFalse(sv.flow.drum_arrivals["cael"])

    def test_only_named_stations_and_a_marked_demo(self):
        sv = view_with(presence(3, "cael"), presence(4, "rune", key_id="bb" * 8), stations=("cael",))
        sv.tap.apply(frame("i1", 5, station="rune", heard=10_000))
        out = sv.flow.project_drum(10_000)
        self.assertEqual([s["name"] for s in out["stations"]], ["cael"])
        self.assertNotIn("rune", json.dumps(out))
        sv.demo_fixture = True
        demo = sv.drum_project(10 * DRUM_ROW_MS)
        self.assertEqual(set(demo), DRUM_KEYS)
        self.assertTrue(demo["synthetic"])
        self.assertTrue(all(s["name"].startswith("demo-") for s in demo["stations"]))
        self.assertTrue(all(0 <= i < DRUM_BUCKETS for s in demo["stations"] for i, _, _ in s["arrivals"]))


async def http_get(port, path="/api/shape", host=None, method="GET"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{method} {path} HTTP/1.1\r\nHost: {host or f'127.0.0.1:{port}'}\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    return int(head.split()[1]), body


class ShapeDaemonTest(SnapshotCase):
    def test_gateway_serves_shape_from_the_daemon_and_nothing_else(self):
        async def scenario(d, port):
            st = self.station()
            self.beacon(d, st)
            self.sing(d, st, text=EVIL, purpose="steal the keys")
            self.sing(d, st, text="a second chatter line")
            self.sing(d, st, stream="lens.threat", text="a live-state fact", state_key="k1")  # warm-up hold
            stop, ports = asyncio.Event(), []
            task = asyncio.ensure_future(run_shape(d.cfg.socket_path, ["cael", "rune"], "127.0.0.1", 0, stop,
                                                   ready=ports.append))
            for _ in range(100):
                await asyncio.sleep(0.05)
                if ports:
                    status, body = await http_get(ports[0])
                    if json.loads(body)["connected"]:
                        break
            flow_before = await http_get(ports[0], "/api/flow")
            self.sing(d, st, text="sung after the join")
            await asyncio.sleep(0.5)
            got = {"api": (status, body),
                   "flow_before": flow_before,
                   "flow": await http_get(ports[0], "/api/flow"),
                   "drum": await http_get(ports[0], "/api/drum"),
                   "root": await http_get(ports[0], "/"),
                   "tuner_api": await http_get(ports[0], "/api/stations"),
                   "rebind": await http_get(ports[0], host="evil.example:80"),
                   "post": await http_get(ports[0], method="POST")}
            stop.set()
            await asyncio.wait_for(task, 5)
            return got

        got, _ = self.run_with(scenario)
        status, body = got["api"]
        self.assertEqual(status, 200)
        out = json.loads(body)
        keys_ok(self, out)
        self.assertTrue(out["connected"])
        cael, rune = out["stations"]
        self.assertEqual(cael["name"], "cael")
        self.assertNotEqual(cael["state"], "not_heard")
        self.assertEqual({s["stream"]: s["live"] for s in cael["streams"]}, {"chatter": 2}, "a live-state warm-up hold is not surfaced, so not counted")
        self.assertEqual(rune["state"], "not_heard")
        for needle in (b"rm -rf", b"steal", b"live-state fact", b"second chatter", b"canticle:heard"):
            self.assertNotIn(needle, body)
        def arrivals(flow):
            return sum(a["n"] for m in flow["stations"][0]["minutes"] for a in m["arrivals"])

        before, after = (json.loads(got[k][1]) for k in ("flow_before", "flow"))
        self.assertEqual(got["flow"][0], 200)
        self.assertEqual(set(after), FLOW_KEYS)
        self.assertEqual(arrivals(before), 0, "items sung before the gateway joined come in the snapshot, not as arrivals")
        self.assertEqual(arrivals(after), 1, "the item sung after the join is one arrival")
        self.assertEqual([(r["station"], r["stream"]) for r in after["river"]], [("cael", "chatter")])
        for needle in (b"rm -rf", b"steal", b"live-state fact", b"second chatter", b"after the join", b"canticle:heard"):
            self.assertNotIn(needle, got["flow"][1])
            self.assertNotIn(needle, got["drum"][1])
        drum = json.loads(got["drum"][1])
        self.assertEqual((got["drum"][0], set(drum)), (200, DRUM_KEYS))
        self.assertEqual(sum(n for _, _, n in drum["stations"][0]["arrivals"]), 1, "the post-join sing, once")
        self.assertEqual(got["root"][0], 404)
        self.assertEqual(got["tuner_api"][0], 404)
        self.assertEqual(got["rebind"][0], 421)
        self.assertEqual(got["post"][0], 405)

    def test_http_ages_on_its_own_clock_and_reads_disconnected_once_stale(self):
        """🌫's probe on #134: polls at 1 000 and 41 000 ms both said 900 ms and connected."""
        async def scenario():
            clock = [1_000]
            sv = view_with(presence(3, "cael"), rec("health", 4, state="ok", reasons=[], beacon_age_ms={"aa" * 8: 900}),
                           clock=lambda: clock[0])
            http = TunerHttp(sv, "127.0.0.1", 0, clock=lambda: clock[0], api_path="/api/shape", static=False)
            port = await http.start()
            try:
                out = []
                for at in (1_000, 9_000, 41_000):
                    clock[0] = at
                    out.append(json.loads((await http_get(port))[1]))
                return out
            finally:
                await http.close()

        first, later, stale = asyncio.run(scenario())
        self.assertEqual([s["stations"][0]["beacon_age_ms"] for s in (first, later)], [900, 8_900])
        self.assertTrue(later["connected"])
        self.assertEqual((stale["connected"], stale["stations"][0]["state"]), (False, "not_heard"))

    def test_follow_drops_an_open_but_silent_daemon_and_joins_again(self):
        """A daemon that completes the join, reports health once, then holds its socket open saying nothing: once no
        health has come for STALE_MS the view reads disconnected and follow joins again (🌫 on #134)."""
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                sock = str(pathlib.Path(tmp) / "sock")
                clock, joins, release = [1_000], [], asyncio.Event()

                async def peer(reader, writer):
                    joins.append(clock[0])
                    try:
                        await reader.readline()
                        p = presence(3, "cael")
                        fields = {k: v for k, v in p.items() if k not in ("v", "type", "rec_seq", "run")}
                        records = [rec("hello", 1, join_snapshot=True), rec("landing_state", 2),
                                   rec("snapshot", 3, snap_seq=1, entry={"presence": fields}),
                                   rec("snapshot_end", 3, watermark=3, count=1, truncated=False, omitted=0),
                                   rec("health", 4, state="ok", reasons=[], beacon_age_ms={"aa" * 8: 900})]
                        writer.write("".join(json.dumps(r) + "\n" for r in records).encode())
                        await writer.drain()
                        await release.wait()
                    finally:
                        writer.close()

                server = await asyncio.start_unix_server(peer, sock)
                sv, stop, sleeps = ShapeView(["cael"], clock=lambda: clock[0]), asyncio.Event(), []

                async def sleep(s):
                    sleeps.append(s)
                    if len(joins) >= 2:
                        stop.set()

                task = asyncio.ensure_future(follow(sock, sv, stop, sleep=sleep))
                try:
                    for _ in range(100):
                        await asyncio.sleep(0.02)
                        if sv.connected and sv.tap.health:
                            break
                    fresh = sv.project(clock[0])
                    clock[0] += STALE_MS + 1   # the daemon stays open and silent past the bound
                    stale = sv.project(clock[0])
                    for _ in range(100):
                        await asyncio.sleep(0.02)
                        if len(joins) >= 2:
                            break
                    return fresh, stale, list(joins), sleeps
                finally:
                    stop.set()
                    release.set()
                    await asyncio.wait_for(task, 5)
                    server.close()
                    await server.wait_closed()

        fresh, stale, joins, sleeps = asyncio.run(scenario())
        self.assertEqual((fresh["connected"], fresh["stations"][0]["beacon_age_ms"]), (True, 900))
        self.assertEqual((stale["connected"], stale["stations"][0]["state"]), (False, "not_heard"))
        self.assertEqual(len(joins), 2, "follow joined again after the stale connection")
        self.assertEqual(sleeps[0], 1, "backoff restarts at the first step after a connection that was up")

    def test_follow_reconnects_after_the_daemon_is_gone(self):
        """No daemon: follow backs off and retries instead of ending; the view stays disconnected."""
        async def scenario():
            sv, stop, sleeps = ShapeView(["cael"]), asyncio.Event(), []

            async def sleep(s):
                sleeps.append(s)
                if len(sleeps) >= 3:
                    stop.set()

            await asyncio.wait_for(follow("/nonexistent/canticle.sock", sv, stop, timeout_s=0.2, sleep=sleep), 5)
            return sv, sleeps

        sv, sleeps = asyncio.run(scenario())
        self.assertEqual(sleeps, [1, 2, 5])
        self.assertFalse(sv.connected)
        self.assertEqual(sv.project(runner.now_ms())["stations"][0]["state"], "not_heard")


if __name__ == "__main__":
    unittest.main()
