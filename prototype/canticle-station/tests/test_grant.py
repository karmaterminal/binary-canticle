"""Display grants (#137): a station appears on a shape display only by its own grant, at the scope granted.

The gateway is checked on a ``_StampedView`` fed records directly, as in test_shape: with a display name, the host's
``--station`` list is only a ceiling; no grant means no row and no trace; a proven narrowing purges what it removed;
an unverifiable moment hides and keeps.
"""

import argparse
import asyncio
import base64
import json
import random
import unittest
from pathlib import Path

from canticle import grant, runner, wire
from canticle.__main__ import grant_requests
from canticle.manifest import Manifest, StationEntry
from canticle.shape import ShapeView, _StampedView, run_shape
from canticle.station import Station, StreamConfig

from test_daemon import SK
from test_join_snapshot import SnapshotCase
from test_shape import http_get
from test_tap import bootstrap, frame, rec

DISPLAY = "frond-house@silas"
KEY = {"cael": "aa" * 8, "rune": "bb" * 8}


def grant_frame(idem, seq, station="cael", scope="river", withheld=False, display=DISPLAY, epoch=1, expiry=10**13,
                body=None, stream=grant.STREAM, cls=grant.CLASS, key=None):
    r = frame(idem, seq, station=station, stream=stream, expiry=expiry)
    raw = body if body is not None else grant.encode(display, scope, withheld)
    r.update({"class": cls, "state_key": key or grant.state_key(display)})
    r["frame"] = {**r["frame"], "epoch": epoch, "key_id": KEY.get(station, "00" * 8)}
    r["body"] = {"ctype": grant.CTYPE_NAME, "size": len(raw), "sha256": "x", "base64": base64.b64encode(raw).decode()}
    return r


def presence(seq, name):
    return rec("presence", seq, key_id=KEY[name], station={"name": name, "principal": None},
               state="EQUIPPED_SPEAKING", last_beacon_at=1)


def health(seq, ages=None):
    return rec("health", seq, state="ok", reasons=[], beacon_age_ms=ages or {})


class Clock:
    def __init__(self, t=10_000):
        self.t = t

    def __call__(self):
        return self.t


def gateway(*records, stations=("cael", "rune"), display=DISPLAY, clock=None, complete=True):
    """A connected gateway whose view joined with a complete (empty) snapshot, then heard ``records``."""
    clock = clock or Clock()
    sv = ShapeView(stations, clock=clock, display=display)
    tv = _StampedView([("*", "*")], clock, sv.flow)
    bootstrap(tv, join=complete)
    if complete:
        tv.apply(rec("snapshot_end", 3, watermark=3, count=0, truncated=False, omitted=0))
    sv.tap, sv.connected = tv, True
    for r in records:
        tv.apply(r)
    return sv, tv


class CodecTest(unittest.TestCase):
    def test_round_trip_and_refusals(self):
        self.assertEqual(grant.decode(grant.encode(DISPLAY, "counts")),
                         {"display": DISPLAY, "scope": "counts", "withheld": False})
        self.assertEqual(grant.decode(grant.encode(DISPLAY, "presence", True))["withheld"], True)
        from canticle import cbor
        for bad in (b"\xff", cbor.encode([1]), cbor.encode({"display": DISPLAY, "scope": "everything"}),
                    cbor.encode({"display": DISPLAY, "scope": "river", "withheld": True}),
                    cbor.encode({"display": DISPLAY, "scope": "river", "text": "hi"}),
                    cbor.encode({"display": "Bad Name", "scope": "river"}),
                    cbor.encode({"display": DISPLAY, "scope": "river", "withheld": 1})):
            with self.assertRaises(grant.GrantError):
                grant.decode(bad)
        with self.assertRaises(grant.GrantError):
            grant.encode(DISPLAY, "counts", withheld=True)


class GrantedRowsTest(unittest.TestCase):
    def test_no_grant_no_row(self):
        sv, _ = gateway(presence(4, "cael"), health(5, {KEY["cael"]: 100}), frame("c1", 6, heard=9_000))
        out = sv.project(10_000)
        self.assertEqual(out["stations"], [])
        self.assertEqual(out["display"], DISPLAY)
        self.assertEqual(sv.flow_project(10_000)["stations"], [])
        self.assertEqual(sv.flow_project(10_000)["river"], [])
        drum = sv.drum_project(10_000)
        self.assertEqual((drum["stations"], drum["streams"]), ([], []))

    def test_each_scope_shows_only_its_fields(self):
        expect = {"presence": (None, []), "beacon": (100, []),
                  "counts": (100, [{"stream": "chatter", "live": 1, "newest_age_ms": 1_000}]),
                  "river": (100, [{"stream": "chatter", "live": 1, "newest_age_ms": 1_000}])}
        for scope, (age, streams) in expect.items():
            with self.subTest(scope=scope):
                sv, _ = gateway(grant_frame("g", 4, scope=scope), presence(5, "cael"),
                                health(6, {KEY["cael"]: 100}), frame("c1", 7, heard=9_000))
                (row,) = sv.project(10_000)["stations"]
                self.assertEqual((row["name"], row["state"], row["beacon_age_ms"], row["streams"], row["withheld"]),
                                 ("cael", "EQUIPPED_SPEAKING", age, streams, False))
                flow = sv.flow_project(10_000)
                minute = flow["stations"][0]["minutes"][-1]
                self.assertEqual(bool(minute["arrivals"]), scope in ("counts", "river"))
                self.assertEqual(bool(minute["beacon"]), scope != "presence")
                self.assertEqual(len(flow["river"]), 1 if scope == "river" else 0)

    def test_withheld_only_when_granted(self):
        sv, _ = gateway(grant_frame("g", 4, scope="presence", withheld=True), presence(5, "cael"))
        self.assertTrue(sv.project(10_000)["stations"][0]["withheld"])

    def test_the_host_list_is_a_ceiling(self):
        sv, _ = gateway(grant_frame("g", 4, station="rune"), presence(5, "rune"), stations=("cael",))
        self.assertEqual(sv.project(10_000)["stations"], [])

    def test_only_a_grant_for_this_display_on_the_display_stream(self):
        for bad in (grant_frame("g", 4, display="other@host"),
                    grant_frame("g", 4, display="other@host", key=grant.state_key(DISPLAY)),
                    grant_frame("g", 4, stream="chatter"),
                    grant_frame("g", 4, cls="chatter"),
                    grant_frame("g", 4, key="grant:other@host"),
                    grant_frame("g", 4, body=b"\x00not cbor")):
            with self.subTest(bad=(bad["stream"], bad["class"], bad["state_key"])):
                sv, _ = gateway(bad, presence(5, "cael"))
                self.assertEqual(sv.project(10_000)["stations"], [])

    def test_an_expired_grant_shows_nothing(self):
        sv, _ = gateway(grant_frame("g", 4, expiry=9_000), presence(5, "cael"))
        self.assertEqual(sv.project(10_000)["stations"], [])

    def test_the_newest_generation_wins(self):
        sv, _ = gateway(grant_frame("g1", 4, scope="river"), grant_frame("g2", 5, scope="presence"),
                        presence(6, "cael"))
        self.assertEqual(sv.grants(10_000)["cael"]["scope"], "presence")
        sv, _ = gateway(grant_frame("g1", 4, scope="river", epoch=2), grant_frame("g2", 5, scope="presence"),
                        presence(6, "cael"))
        self.assertEqual(sv.grants(10_000)["cael"]["scope"], "river")

    def test_the_grant_carrier_is_not_telemetry(self):
        sv, _ = gateway(grant_frame("g", 4, scope="river", expiry=10**13), presence(5, "cael"),
                        grant_frame("g2", 6, scope="river"))
        row = sv.project(10_000)["stations"][0]
        self.assertEqual(row["streams"], [])
        self.assertEqual(sv.flow_project(10_000)["river"], [])
        self.assertEqual(sv.drum_project(10_000)["streams"], [])

    def test_an_ungranted_station_leaves_no_trace(self):
        """Its arrivals change no count, list or stream name another station shows."""
        sv, _ = gateway(grant_frame("g", 4, scope="river"), presence(5, "cael"), presence(6, "rune"),
                        health(7, {KEY["cael"]: 100, KEY["rune"]: 100}),
                        frame("r1", 8, station="rune", stream="lens.threat", heard=9_000))
        text = json.dumps([sv.project(10_000), sv.flow_project(10_000), sv.drum_project(10_000)])
        self.assertNotIn("rune", text)
        self.assertNotIn("lens.threat", text)

    def test_a_dead_connection_shows_nothing(self):
        sv, _ = gateway(grant_frame("g", 4), presence(5, "cael"))
        sv.connected = False
        self.assertEqual(sv.project(10_000)["stations"], [])
        self.assertEqual(sv.flow_project(10_000)["stations"], [])


class PurgeTest(unittest.TestCase):
    def history(self, sv, now=10_000):
        flow, drum = sv.flow_project(now), sv.drum_project(now)
        return {"river": len(flow["river"]),
                "arrivals": sum(len(m["arrivals"]) for s in flow["stations"] for m in s["minutes"]),
                "drum_arrivals": sum(len(s["arrivals"]) for s in drum["stations"])}

    def test_a_downgrade_purges_what_it_removed_and_a_regrant_does_not_bring_it_back(self):
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        self.assertEqual(self.history(sv), {"river": 1, "arrivals": 1, "drum_arrivals": 1})
        tv.apply(grant_frame("g2", 7, scope="counts"))
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 1, "drum_arrivals": 1})
        tv.apply(grant_frame("g3", 8, scope="presence"))
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})
        tv.apply(grant_frame("g4", 9, scope="river"))
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})

    def test_a_pluck_purges_everything(self):
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        tv.apply(rec("retract", 7, idem="g1", reason="plucked"))
        self.assertEqual(sv.project(10_000)["stations"], [])
        self.assertEqual(sv.flow.minutes["cael"], {})
        tv.apply(grant_frame("g2", 8, scope="river"))
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})

    def test_expiry_purges_at_the_next_record(self):
        clock = Clock()
        sv, tv = gateway(grant_frame("g1", 4, scope="river", expiry=20_000), presence(5, "cael"),
                         frame("c1", 6, heard=9_000), clock=clock)
        clock.t = 21_000
        tv.apply(health(7))
        self.assertEqual(sv.flow.minutes["cael"], {})

    def test_a_gap_hides_and_keeps(self):
        """After a live rec_seq gap the grant is carried, not verified: hidden, history kept, nothing new recorded."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        tv.apply(frame("c2", 9, heard=9_500))   # 7 and 8 lost
        self.assertEqual(sv.project(10_000)["stations"], [])
        self.assertEqual(len(sv.flow.river), 1, "kept, not purged")
        self.assertEqual(sum(sum(b["arrivals"].values()) for b in sv.flow.minutes["cael"].values()), 1,
                         "c2 is not recorded while the grant is unverified")

    def test_a_seen_pluck_purges_without_a_complete_snapshot(self):
        """A withdrawal of the station's own grant item is proof for that station, whatever the snapshot."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000),
                         complete=False)
        tv.apply(rec("retract", 7, idem="g1", reason="plucked"))
        self.assertEqual(sv.project(10_000)["stations"], [])
        self.assertEqual(len(sv.flow.river), 0)

    def test_observed_pluck_after_a_gap_then_regrant(self):
        """🌿's probe on #140: records_lost makes the view's absence unproven, but the seen pluck still purges."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        tv.apply(frame("c2", 9, heard=9_500))                     # 7, 8 lost: records_lost > 0
        tv.apply(rec("retract", 10, idem="g1", reason="plucked"))  # the pluck arrives and is seen
        tv.apply(grant_frame("g2", 11, scope="river"))             # the station grants again
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})

    def test_a_pluck_lost_in_a_gap_then_regrant_does_not_resurrect(self):
        """The grant was carried across a gap (its pluck may be among the lost records), so the next verified grant
        purges before recording resumes."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        tv.apply(frame("c2", 9, heard=9_500))                     # 7, 8 lost: g1 carried, absence unproven
        self.assertEqual(len(sv.flow.river), 1, "hidden and kept while unproven")
        tv.apply(grant_frame("g3", 10, scope="river"))
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})

    def test_a_new_connection_does_not_resurrect(self):
        """Anything may have happened while the gateway was away: a grant verified on a new connection starts clean."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        self.assertEqual(self.history(sv)["river"], 1)
        tv2 = _StampedView([("*", "*")], sv.clock, sv.flow)
        bootstrap(tv2, join=True)
        entry = {k: v for k, v in grant_frame("g9", 3, scope="river").items() if k not in ("v", "type", "rec_seq", "run")}
        tv2.apply(rec("snapshot", 3, snap_seq=1, entry={"frame": entry}))
        tv2.apply(rec("snapshot_end", 3, watermark=3, count=1, truncated=False, omitted=0))
        sv.tap = tv2
        tv2.apply(health(4))
        self.assertEqual(len(sv.project(10_000)["stations"]), 1)
        self.assertEqual(self.history(sv), {"river": 0, "arrivals": 0, "drum_arrivals": 0})

    def test_a_refresh_of_the_same_grant_keeps_history(self):
        """The station re-sings its grant by refresh (a new seq, same scope): continuity on one connection, no purge."""
        sv, tv = gateway(grant_frame("g1", 4, scope="river"), presence(5, "cael"), frame("c1", 6, heard=9_000))
        tv.apply(grant_frame("g2", 7, scope="river"))
        tv.apply(rec("retract", 8, idem="g1", reason="superseded"))
        self.assertEqual(self.history(sv), {"river": 1, "arrivals": 1, "drum_arrivals": 1})


class GrantCliTest(unittest.TestCase):
    def args(self, **kw):
        base = {"display": DISPLAY, "scope": None, "withheld": False, "ttl": 900, "hours": 24, "pluck": False}
        return argparse.Namespace(**{**base, **kw})

    def test_a_grant_is_one_keyed_live_state_sing(self):
        (req,) = grant_requests(self.args(scope="beacon"))
        self.assertEqual({k: req[k] for k in ("op", "stream", "class", "state_key", "ctype", "ttl", "keep_on_air")},
                         {"op": "sing", "stream": "display", "class": "live-state", "state_key": f"grant:{DISPLAY}",
                          "ctype": 2, "ttl": 900, "keep_on_air": 86_400})
        self.assertEqual(grant.decode(bytes.fromhex(req["body_hex"]))["scope"], "beacon")

    def test_pluck_hushes_each_grant_on_air(self):
        status = {"streams": {"display": {"on_air": [
            {"seq": 3, "kind": "item", "state_key": f"grant:{DISPLAY}"},
            {"seq": 4, "kind": "item", "state_key": "grant:other@host"},
            {"seq": 5, "kind": "pluck", "state_key": None}]}}}
        self.assertEqual(grant_requests(self.args(pluck=True), status),
                         [{"op": "hush", "stream": "display", "seq": 3}])

    def test_usage_mistakes(self):
        for kw, status in (({}, None), ({"scope": "river", "ttl": 901}, None), ({"scope": "river", "hours": 25}, None),
                           ({"pluck": True, "scope": "river"}, {}), ({"pluck": True}, {"streams": {}}),
                           ({"scope": "counts", "withheld": True}, None), ({"display": "Nope!", "scope": "river"}, None)):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                grant_requests(self.args(**kw), status)


class GrantDaemonTest(SnapshotCase):
    """A grant sung by a real station through the in-process daemon: the gateway shows the station only while it
    holds the grant, and only at its scope."""

    def setUp(self):
        super().setUp()
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3}), ("chatter", "display"))])
        Path(self.manifest).write_text(json.dumps(m.to_json()))

    def station(self):
        return Station(SK, [StreamConfig("chatter"), StreamConfig("display", cls="live-state")], epoch=1,
                       rng=random.Random(3), now_ms=runner.now_ms())

    def test_a_station_appears_by_its_own_grant_and_leaves_by_its_pluck(self):
        async def scenario(d, port):
            st = self.station()
            now = runner.now_ms()
            self.beacon(d, st, now)
            now += 120_000   # past the live-state warm-up (one beacon, then a loop period)
            res = st.sing(now, "display", body=grant.encode(DISPLAY, "counts"), ctype=grant.CTYPE, cls=grant.CLASS,
                          state_key=grant.state_key(DISPLAY), ttl_s=900)
            self.feed(d, st.poll(now), now)
            self.sing(d, st, text="a secret line", now=now)
            stop, ports = asyncio.Event(), []
            task = asyncio.ensure_future(run_shape(d.cfg.socket_path, ["cael", "rune"], "127.0.0.1", 0, stop,
                                                   ready=ports.append, display=DISPLAY))
            granted = None
            for _ in range(100):
                await asyncio.sleep(0.05)
                if ports:
                    granted = json.loads((await http_get(ports[0]))[1])
                    if granted["connected"] and granted["stations"]:
                        break
            st.hush(now + 1, "display", res.seq)
            self.feed(d, st.poll(now + 1), now + 1)
            revoked = None
            for _ in range(100):
                await asyncio.sleep(0.05)
                revoked = await http_get(ports[0])
                if not json.loads(revoked[1])["stations"]:
                    break
            stop.set()
            await asyncio.wait_for(task, 5)
            return granted, revoked

        (granted, revoked), _ = self.run_with(scenario)
        self.assertEqual(granted["display"], DISPLAY)
        (cael,) = granted["stations"]
        self.assertEqual((cael["name"], cael["withheld"]), ("cael", False))
        self.assertEqual([s["stream"] for s in cael["streams"]], ["chatter"], "the grant's own carrier is not shown")
        self.assertEqual(json.loads(revoked[1])["stations"], [], "a pluck removes the row")
        self.assertNotIn(b"secret", revoked[1])


if __name__ == "__main__":
    unittest.main()
