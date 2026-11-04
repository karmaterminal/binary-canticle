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
from canticle.shape import PRESENCE_STATES, STALE_MS, ShapeView, _StampedView, follow, run_shape
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
    tv = _StampedView([("*", "*")], clock)
    bootstrap(tv, join=False)
    for r in records:
        tv.apply(r)
    sv = ShapeView(stations, clock=clock)
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
            got = {"api": (status, body),
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
