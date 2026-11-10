"""Typed beacons (#142): a station's own beacon is versioned, enumerated shape; anything else is unknown.

The reader is checked on a ``TapView`` fed records directly (as in test_tap and test_grant), the CLI by the control
requests it builds, and the whole path by a real station singing through the in-process daemon.
"""

import argparse
import base64
import io
import json
import random
import unittest
from pathlib import Path

from canticle import beacon, cbor, runner, wire
from canticle.__main__ import beacon_requests, parse_until
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig
from canticle.tap import TapView, tap

from test_daemon import SK
from test_join_snapshot import SnapshotCase
from test_tap import bootstrap, frame, rec

KEY = {"cael": "aa" * 8, "rune": "bb" * 8}
NOW = 1_800_000_000_000


def beacon_frame(idem, seq, station="cael", body=None, epoch=1, expiry=10**13, stream=beacon.STREAM,
                 cls=beacon.CLASS, key=beacon.STATE_KEY, **kw):
    r = frame(idem, seq, station=station, stream=stream, expiry=expiry)
    raw = body if body is not None else beacon.encode(**({"state": "working"} | kw))
    r.update({"class": cls, "state_key": key})
    r["frame"] = {**r["frame"], "epoch": epoch, "key_id": KEY.get(station, "00" * 8)}
    r["body"] = {"ctype": beacon.CTYPE_NAME, "size": len(raw), "sha256": "x", "base64": base64.b64encode(raw).decode()}
    return r


def view(*records, complete=True):
    v = TapView([("*", "*")])
    bootstrap(v, join=complete)
    if complete:
        v.apply(rec("snapshot_end", 3, watermark=3, count=0, truncated=False, omitted=0))
    for r in records:
        v.apply(r)
    return v


class CodecTest(unittest.TestCase):
    def test_round_trip(self):
        raw = beacon.encode("blocked", "review", until=NOW + 60_000, refs=["binary-canticle#142", "openclaw/openclaw#129388"])
        self.assertEqual(beacon.decode(raw), {"v": 1, "state": "blocked", "asking": "review", "origin": "reported",
                                              "until": NOW + 60_000, "refs": ("binary-canticle#142", "openclaw/openclaw#129388")})
        self.assertEqual(beacon.decode(beacon.encode("resting")),
                         {"v": 1, "state": "resting", "asking": "none", "origin": "reported", "until": None,
                          "refs": ()})

    def test_encode_refuses(self):
        for kw in ({"state": "fine"}, {"state": "working", "asking": "everyone"}, {"state": ["working"]},
                   {"state": "working", "origin": "rumour"}, {"state": "working", "until": 0},
                   {"state": "working", "until": True}, {"state": "working", "until": 1.5},
                   {"state": "working", "refs": ["r#1", "r#2", "r#3", "r#4", "r#5"]},
                   {"state": "working", "refs": ["see my notes"]}, {"state": "working", "refs": ["r#0"]},
                   {"state": "working", "refs": ["r#7", "r#7"]}, {"state": "working", "refs": ["#7"]},
                   {"state": "working", "refs": ["a/b/c#1"]}, {"state": "working", "refs": ["Openclaw/x#1"]}):
            with self.subTest(kw=kw), self.assertRaises(beacon.BeaconError):
                beacon.encode(**kw)

    def test_decode_refuses_anything_but_exactly_the_known_shape(self):
        good = {"v": 1, "state": "working", "asking": "none", "origin": "reported"}
        bad = [
            b"\xff",                                              # not CBOR
            cbor.encode(["working"]),                             # not a map
            cbor.encode({**good, "text": "hello"}),               # unknown field: no prose rides along
            cbor.encode({**good, 1: "x"}),                        # non-text key
            cbor.encode({**good, "v": 2}),                        # a later shape is not misread as this one
            cbor.encode({**good, "v": True}),                     # True == 1 in Python; a bool is not a version
            cbor.encode({k: v for k, v in good.items() if k != "v"}),
            cbor.encode({k: v for k, v in good.items() if k != "origin"}),
            cbor.encode({**good, "state": []}),                   # unhashable: type is checked first (🌫 on #140)
            cbor.encode({**good, "asking": {"x": 1}}),
            cbor.encode({**good, "until": -5}),
            cbor.encode({**good, "until": 2 ** 53}),
            cbor.encode({**good, "refs": "r#1"}),
            cbor.encode({**good, "refs": [1]}),
            cbor.encode({**good, "refs": ["#1"]}),
            cbor.encode({**good, "until": None}),                 # present but null is not "absent" (🪨 on #143)
            cbor.encode({**good, "refs": None}),
            cbor.encode({**good, "refs": []}),                    # encode never writes an empty list
        ]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(beacon.BeaconError):
                beacon.decode(raw)


class ReadTest(unittest.TestCase):
    def test_a_station_shows_its_own_beacon(self):
        got = beacon.read(view(beacon_frame("c1", 4, asking="review", refs=["binary-canticle#142"])), ["cael", "rune"], NOW)
        self.assertEqual(set(got), {"cael"})
        self.assertEqual({k: got["cael"][k] for k in ("state", "asking", "refs", "generation")},
                         {"state": "working", "asking": "review", "refs": ("binary-canticle#142",), "generation": (1, 4)})

    def test_no_beacon_is_unknown_not_fine(self):
        self.assertEqual(beacon.read(view(), ["cael"], NOW), {})
        self.assertEqual(beacon.read(None, ["cael"], NOW), {})

    def test_the_host_list_is_a_ceiling(self):
        self.assertEqual(beacon.read(view(beacon_frame("r1", 4, station="rune")), ["cael"], NOW), {})

    def test_until_is_an_enforced_expiry(self):
        v = view(beacon_frame("c1", 4, until=NOW + 1_000))
        self.assertIn("cael", beacon.read(v, ["cael"], NOW))
        self.assertEqual(beacon.read(v, ["cael"], NOW + 1_000), {}, "past until, the station is unknown")

    def test_an_expired_item_is_unknown(self):
        self.assertEqual(beacon.read(view(beacon_frame("c1", 4, expiry=NOW - 1)), ["cael"], NOW), {})

    def test_an_inference_cannot_pass_for_testimony(self):
        v = view(beacon_frame("c1", 4, origin="inferred"))
        self.assertEqual(beacon.read(v, ["cael"], NOW), {})

    def test_only_the_beacon_carrier_counts(self):
        body = beacon.encode("working")
        for kw in ({"stream": "chatter"}, {"cls": "chatter"}, {"key": "grant:frond-house@silas"}):
            with self.subTest(kw=kw):
                self.assertEqual(beacon.read(view(beacon_frame("c1", 4, body=body, **kw)), ["cael"], NOW), {})

    def test_a_malformed_signed_beacon_is_refused_not_fatal(self):
        v = view(beacon_frame("c1", 4, body=cbor.encode({"v": 1, "state": [], "asking": "none",
                                                          "origin": "reported"})))
        self.assertEqual(beacon.read(v, ["cael"], NOW), {})

    def test_the_newest_generation_wins(self):
        v = view(beacon_frame("c1", 4, state="working"), beacon_frame("c2", 5, state="resting", epoch=2))
        self.assertEqual(beacon.read(v, ["cael"], NOW)["cael"]["state"], "resting")

    def test_a_view_that_cannot_vouch_shows_nothing(self):
        v = TapView([("*", "*")])
        bootstrap(v, join=True)
        v.apply(beacon_frame("c1", 3))      # mid-snapshot: the item is live, but the view is not ready
        self.assertEqual(len(v.live(NOW)), 1)
        self.assertEqual(beacon.read(v, ["cael"], NOW), {})


class BeaconCliTest(unittest.TestCase):
    def args(self, **kw):
        base = {"state": None, "asking": None, "until": None, "ref": None, "ttl": 300, "hours": 12, "pluck": False}
        return argparse.Namespace(**{**base, **kw})

    def test_a_beacon_is_one_keyed_live_state_sing(self):
        (req,) = beacon_requests(self.args(state="blocked", asking="review", until="+30m", ref=["openclaw/openclaw#129388"]), now_ms=NOW)
        self.assertEqual({k: req[k] for k in ("op", "stream", "class", "state_key", "ctype", "ttl", "keep_on_air")},
                         {"op": "sing", "stream": "beacon", "class": "live-state", "state_key": "beacon",
                          "ctype": 2, "ttl": 300, "keep_on_air": 43_200})
        self.assertEqual(beacon.decode(bytes.fromhex(req["body_hex"])),
                         {"v": 1, "state": "blocked", "asking": "review", "origin": "reported",
                          "until": NOW + 1_800_000, "refs": ("openclaw/openclaw#129388",)})

    def test_the_cli_cannot_sing_an_inference(self):
        (req,) = beacon_requests(self.args(state="working"), now_ms=NOW)
        self.assertEqual(beacon.decode(bytes.fromhex(req["body_hex"]))["origin"], "reported")

    def test_pluck_hushes_each_beacon_on_air(self):
        status = {"streams": {"beacon": {"on_air": [{"seq": 3, "kind": "item", "state_key": "beacon"},
                                                    {"seq": 4, "kind": "item", "state_key": "other"},
                                                    {"seq": 5, "kind": "pluck", "state_key": None}]}}}
        self.assertEqual(beacon_requests(self.args(pluck=True), status),
                         [{"op": "hush", "stream": "beacon", "seq": 3}])

    def test_until_forms(self):
        self.assertEqual(parse_until("+90s", NOW), NOW + 90_000)
        self.assertEqual(parse_until("+2h", NOW), NOW + 7_200_000)
        self.assertEqual(parse_until("2026-11-10T07:07Z", 0), 1_794_294_420_000)
        self.assertEqual(parse_until("2026-11-10T07:07:30Z", 0), 1_794_294_450_000)

    def test_usage_mistakes(self):
        for kw, status in (({}, None), ({"state": "working", "ttl": 901}, None),
                           ({"state": "working", "hours": 25}, None), ({"pluck": True, "state": "working"}, {}),
                           ({"pluck": True}, {"streams": {}}), ({"state": "working", "until": "tomorrow"}, None),
                           ({"state": "working", "until": "2020-01-01T00:00Z"}, None),
                           ({"state": "working", "ref": ["not a ref"]}, None),
                           ({"state": "working", "until": "+13h"}, None),            # past the default 12 h on air
                           ({"state": "working", "until": "+2h", "hours": 1}, None)):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                beacon_requests(self.args(**kw), status, now_ms=NOW)


class BeaconDaemonTest(SnapshotCase):
    """A beacon sung by a real station through the in-process daemon reads back as typed shape, and a pluck makes the
    station unknown again."""

    def setUp(self):
        super().setUp()
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3}), ("chatter", "beacon"))])
        Path(self.manifest).write_text(json.dumps(m.to_json()))

    def station(self):
        return Station(SK, [StreamConfig("chatter"), StreamConfig("beacon", cls="live-state")], epoch=1,
                       rng=random.Random(3), now_ms=runner.now_ms())

    def test_sung_read_back_then_plucked(self):
        async def read_now(d, now):
            v = TapView([("*", "*")])
            await tap(d.cfg.socket_path, v, io.StringIO(), as_json=True, timeout_s=3, now_ms=lambda: now)
            return beacon.read(v, ["cael"], now)

        async def scenario(d, port):
            st = self.station()
            now = runner.now_ms()
            self.beacon(d, st, now)
            now += 120_000   # past the live-state warm-up (one beacon, then a loop period)
            res = st.sing(now, "beacon", body=beacon.encode("blocked", "human", refs=["binary-canticle#142"]), ctype=beacon.CTYPE,
                          cls=beacon.CLASS, state_key=beacon.STATE_KEY, ttl_s=300)
            self.feed(d, st.poll(now), now)
            sung = await read_now(d, now)
            st.hush(now + 1, "beacon", res.seq)
            self.feed(d, st.poll(now + 1), now + 1)
            plucked = await read_now(d, now + 1)
            return sung, plucked

        (sung, plucked), _ = self.run_with(scenario)
        self.assertEqual(set(sung), {"cael"})
        self.assertEqual((sung["cael"]["state"], sung["cael"]["asking"], sung["cael"]["refs"]),
                         ("blocked", "human", ("binary-canticle#142",)))
        self.assertEqual(plucked, {}, "a pluck makes the station unknown")


if __name__ == "__main__":
    unittest.main()
