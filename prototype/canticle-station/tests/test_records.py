"""Receptor record v1 (RFC-0001 §14.18.3): the disposition mapping, row by row, and the health bounds."""

import hashlib
import json
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import records, vectors, wire
from canticle.ids import stream_id
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.records import Emitter, KeyTable, Receptor, encode_line
from canticle.station import Station, StreamConfig

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
PUB = wire.public_key_bytes(SK)
KID = wire.key_id(PUB)
CHAT, LIVE, REG = stream_id("chatter"), stream_id("lens.threat"), stream_id("reg")
UNNAMED = stream_id("not.named")
STREAMS = ("chatter", "lens.threat", "reg", "root")


def manifest(classes=(1, 3, 6, 9), scopes=(0, 1), revoked=False):
    return Manifest([StationEntry("cael", PUB, frozenset(classes), STREAMS, revoked=revoked, scopes=frozenset(scopes))])


def item(seq, stream=CHAT, cls=1, t=T0, ttl=60_000, epoch=5, body=b"hello", scope=1, **kw):
    return wire.encode_item(SK, wire.Item(epoch=epoch, stream=stream, seq=seq, issued_at=t, expires_at=t + ttl,
                                          cls=cls, ctype=1, body=body, scope=scope, **kw))


def pluck(seq, target_seq, stream=CHAT, t=T0, expires_at=T0 + 60_000, epoch=5, scope=1):
    return wire.encode_pluck(SK, wire.Pluck(epoch=epoch, stream=stream, seq=seq, issued_at=t, expires_at=expires_at,
                                            scope=scope, target_seq=target_seq))


class Harness:
    def __init__(self, m=None, state_dir=None, warmup=False, **kw):
        self.lines, self.recs = [], []
        self.em = Emitter(self._sink)
        st = os.path.join(state_dir, "listener.json") if state_dir else None
        self.lst = Listener(m or manifest(), state_path=st, ephemeral=state_dir is None, receptor_mode=True,
                            warmup=warmup, **kw)
        self.r = Receptor(self.lst, self.em, bind="127.0.0.1:9999", manifest_sha256="00" * 32, manifest_label="t",
                          state_path=os.path.join(state_dir, "receptor.json") if state_dir else None, now_ms=T0)
        self.r.start(T0)

    def _sink(self, t, line):
        self.lines.append(line)
        self.recs.append(json.loads(line))

    def hear(self, frame, t=T0):
        n = len(self.recs)
        self.r.hear(frame, t)
        return self.recs[n:]

    def tick(self, t):
        n = len(self.recs)
        self.r.tick(t)
        return self.recs[n:]

    def health(self, t=T0):
        return json.loads(self.r.health(t))


def only(recs, type_="frame"):
    got = [r for r in recs if r["type"] == type_]
    assert len(got) == 1, recs
    return got[0]


class EnvelopeTest(unittest.TestCase):
    def test_hello_then_landing_state_then_strictly_increasing(self):
        h = Harness()
        self.assertEqual([r["type"] for r in h.recs], ["hello", "landing_state"])
        hello, landing = h.recs
        self.assertEqual(hello["v"], "canticle-receptor-record/1")
        self.assertRegex(hello["run"], r"^[0-9a-f]{32}$")
        for k in ("wire_version", "record_version", "pid", "bind", "multicast", "transport", "manifest_sha256",
                  "manifest_label", "state_version"):
            self.assertIn(k, hello)
        self.assertEqual((landing["mute"], landing["breaker"], landing["modulation"]), (None, "closed", []))
        for i in range(5):
            h.hear(item(i + 1))
        h.health()
        seqs = [r["rec_seq"] for r in h.recs]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))
        self.assertEqual({r["run"] for r in h.recs}, {hello["run"]})
        for line in h.lines:
            self.assertTrue(line.endswith(b"\n") and line.count(b"\n") == 1 and line.isascii())
            self.assertLessEqual(len(line), records.MAX_LINE)

    def test_two_processes_choose_different_runs(self):
        self.assertNotEqual(Emitter().run, Emitter().run)

    def test_framing_limits_refuse_a_record_rather_than_send_it(self):
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}
        encode_line(deep)                                    # depth 8: allowed
        with self.assertRaises(ValueError):
            encode_line({"z": deep})                         # depth 9
            encode_line(deep)
        with self.assertRaises(ValueError):
            encode_line({"x": "y" * records.MAX_LINE})
        self.assertIn(b"\\u00e9", encode_line({"t": "é"}))   # non-ASCII escaped

    def test_landing_state_only_on_change(self):
        h = Harness()
        self.assertFalse(h.r.set_landing(breaker="closed"))
        self.assertTrue(h.r.set_landing(breaker="open", until=T0 + 1000))
        self.assertEqual(h.recs[-1]["type"], "landing_state")
        self.assertEqual(h.recs[-1]["breaker"], "open")

    def test_bye_and_fatal(self):
        h = Harness()
        h.r.bye()
        h.r.fatal("bind_failed", "x" * 500)
        self.assertEqual([r["type"] for r in h.recs[-2:]], ["bye", "fatal"])
        self.assertEqual(len(h.recs[-1]["detail"]), 200)


class FrameRecordTest(unittest.TestCase):
    def test_new_item_on_a_named_stream_surfaces(self):
        h = Harness()
        raw = item(1, purpose="test", intensity=3)
        f = only(h.hear(raw, T0 + 100))
        self.assertEqual((f["admission"], f["disposition"], f["dedup"], f["reasons"]), ("verified", "surface", "first", []))
        self.assertEqual(f["frame"], {"key_id": KID.hex(), "epoch": 5, "stream_id": CHAT, "seq": 1, "kind": "item",
                                      "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.assertEqual(f["idem"], f"canticle:{KID.hex()}:5:{CHAT:08x}:1")
        self.assertEqual(f["station"], {"name": "cael", "principal": None})
        self.assertEqual((f["stream"], f["class"], f["scope"], f["hop"], f["purpose"], f["intensity"]),
                         ("chatter", "chatter", "lan", 0, "test", 3))
        self.assertEqual(f["body"]["text"], "hello")
        self.assertEqual(f["body"]["sha256"], hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(f["gap"], "unavailable")
        t = f["times"]
        self.assertEqual((t["issued_at"], t["received_at"], t["heard_at"], t["local_expiry_at"], t["age_ms"]),
                         (T0, T0 + 100, T0 + 100, T0 + 60_000, 100))
        self.assertEqual(f["flags"], {"refresh": False, "wake_derived": False, "exercise": False})
        self.assertEqual(f["lineage"], {"derived_from": [], "root": None})

    def test_repeat_is_a_health_counter_only(self):
        h = Harness()
        h.hear(item(1))
        self.assertEqual(h.hear(item(1), T0 + 5), [])
        c = h.health()["counters"]
        self.assertEqual((c["admission"]["duplicate"], c["disposition"]["no_op"]), (1, 1))

    def test_unnamed_stream_is_ringbuffer_only(self):
        f = only(Harness().hear(item(1, stream=UNNAMED)))
        self.assertEqual((f["admission"], f["disposition"], f["reasons"], f["stream"]),
                         ("verified", "ringbuffer_only", ["unnamed_stream"], None))
        self.assertIn("body", f)

    def test_unknown_class_is_verified_ringbuffer_only(self):
        f = only(Harness(manifest(classes=(1, 42))).hear(item(1, cls=42)))
        self.assertEqual((f["admission"], f["disposition"], f["reasons"], f["class"]),
                         ("verified", "ringbuffer_only", ["unknown_class"], None))
        self.assertIn("body", f)

    def _refused(self, h, raw, admission, disposition):
        f = only(h.hear(raw))
        self.assertEqual((f["admission"], f["disposition"]), (admission, disposition))
        self.assertNotIn("body", f)
        self.assertNotIn("body_ref", f)
        return f

    def test_capability_exceeded_class_and_scope(self):
        h = Harness(manifest(classes=(1,), scopes=(1,)))
        self._refused(h, item(1, cls=2), "capability_exceeded", "ringbuffer_only")       # ambient not granted
        f = self._refused(h, item(2, scope=2), "capability_exceeded", "ringbuffer_only")  # fleet not granted
        self.assertEqual(f["reasons"], ["scope_not_granted"])

    def test_scope_narrower_than_the_binding_is_scope_violation(self):
        f = self._refused(Harness(), item(1, scope=0), "scope_violation", "drop")   # a host frame heard over UDP
        self.assertEqual(f["reasons"], ["scope_narrower_than_binding"])

    def test_hop_limit(self):
        self._refused(Harness(), item(1, hop=3), "hop_limit", "drop")

    def test_over_quota(self):
        h = Harness(per_key_quota=1)
        h.hear(item(1))
        self._refused(h, item(2), "over_quota", "drop")

    def test_pluck_mismatch(self):
        h = Harness()
        h.hear(item(1))
        f = self._refused(h, pluck(2, 1, expires_at=T0 + 1), "pluck_mismatch", "drop")
        self.assertEqual(f["frame"]["kind"], "pluck")

    def test_item_after_its_pluck_is_plucked(self):
        h = Harness()
        r = only(h.hear(pluck(2, 1)), "retract")   # a valid PLUCK always retracts, held target or not
        self.assertEqual((r["reason"], r["idem"], r["by"]["seq"]), ("plucked", f"canticle:{KID.hex()}:5:{CHAT:08x}:1", 2))
        self._refused(h, item(1), "plucked", "drop")

    def test_supersession_retracts_the_surfaced_value_and_drops_an_older_one(self):
        h = Harness()
        h.hear(item(1, stream=LIVE, cls=3, state_key="k"))
        out = h.hear(item(2, stream=LIVE, cls=3, state_key="k", t=T0 + 10), T0 + 10)
        r = only(out, "retract")
        self.assertEqual((r["reason"], r["target"]["seq"], r["by"]["seq"]), ("superseded", 1, 2))
        self.assertEqual(only(out)["disposition"], "surface")
        self._refused(h, item(3, stream=LIVE, cls=3, state_key="k", t=T0 + 5), "superseded", "drop")

    def test_class_change(self):
        h = Harness()
        h.hear(item(1, stream=LIVE, cls=3, state_key="k"))
        self._refused(h, item(2, stream=LIVE, cls=6, state_key="k", t=T0 + 10), "class_change", "drop")

    def test_equivocation_quarantines_the_key_and_retracts_what_it_surfaced(self):
        h = Harness()
        h.hear(item(1))
        h.hear(item(2))
        out = h.hear(item(1, body=b"other"))
        f = only(out)
        self.assertEqual((f["admission"], f["disposition"]), ("equivocation", "quarantine_set"))
        self.assertNotIn("body", f)
        self.assertEqual(sorted((r["reason"], r["target"]["seq"]) for r in out if r["type"] == "retract"),
                         [("quarantined", 1), ("quarantined", 2)])
        later = only(h.hear(item(3)))
        self.assertEqual((later["admission"], later["disposition"], later["reasons"]),
                         ("verified", "ringbuffer_only", ["key_quarantined"]))
        self.assertEqual(h.health()["quarantined"], [KID.hex()])

    def test_lower_epoch_new_tuple_is_ringbuffer_only_and_a_repeat_is_duplicate(self):
        h = Harness()
        h.hear(item(1, epoch=5))
        f = only(h.hear(item(1, epoch=4)))
        self.assertEqual((f["admission"], f["disposition"], f["reasons"]), ("verified", "ringbuffer_only", ["epoch_regression"]))
        self.assertEqual(h.lst.stations[KID].epoch_hwm, 5)
        self.assertEqual(h.hear(item(1, epoch=4)), [])
        self.assertEqual(h.health()["counters"]["admission"]["duplicate"], 1)
        # it supersedes nothing: a keyed lower-epoch value leaves the surfaced one alone
        h.hear(item(2, stream=LIVE, cls=3, state_key="k", t=T0 + 10))
        out = h.hear(item(9, stream=LIVE, cls=3, state_key="k", epoch=4, t=T0 + 20))
        self.assertEqual([r["type"] for r in out], ["frame"])
        self.assertEqual(out[0]["reasons"], ["epoch_regression"])

    def test_retract_on_local_expiry(self):
        h = Harness()
        h.hear(item(1, ttl=10_000))
        r = only(h.tick(T0 + 10_000), "retract")
        self.assertEqual((r["reason"], r["by"]), ("expired", None))
        self.assertEqual(h.tick(T0 + 20_000), [])


class WarmupTest(unittest.TestCase):
    def setUp(self):
        self.st = Station(SK, [StreamConfig("lens.threat", cls="live-state"), StreamConfig("chatter")], epoch=7,
                          rng=random.Random(1), now_ms=T0)
        self.h = Harness(m=manifest(), warmup=True)

    def feed(self, start, end, step=100):
        out = []
        for t in range(start, end, step):
            for f in self.st.poll(t):
                out.extend(self.h.hear(f, t))
            out.extend(self.h.tick(t))
        return out

    def test_held_then_released_with_the_same_idem(self):
        self.st.sing(T0, "lens.threat", text="threat: elevated", state_key="now", ttl_s=120)
        out = self.feed(T0, T0 + 30_000)
        frames = [r for r in out if r["type"] == "frame"]
        self.assertEqual([(f["disposition"], f["reasons"]) for f in frames],
                         [("ringbuffer_only", ["warmup_hold"]), ("surface", [])])
        self.assertEqual(frames[0]["idem"], frames[1]["idem"])
        self.assertEqual(frames[1]["times"]["heard_at"], frames[0]["times"]["heard_at"])
        self.assertEqual(frames[1]["frame"]["sha256"], frames[0]["frame"]["sha256"])

    def test_held_expired(self):
        lst = self.h.lst
        raw = item(1, stream=LIVE, cls=3, state_key="k", ttl=2_000)
        only(self.h.hear(raw))
        r = only(self.h.tick(T0 + 2_000), "retract")
        self.assertEqual(r["reason"], "held_expired")
        self.assertEqual(lst.held, {})

    def test_held_plucked_is_one_retract(self):
        self.h.hear(item(1, stream=LIVE, cls=3, state_key="k"))
        out = self.h.hear(pluck(2, 1, stream=LIVE))
        r = only(out, "retract")
        self.assertEqual((r["reason"], r["by"]["seq"]), ("held_plucked", 2))

    def test_held_superseded(self):
        self.h.hear(item(1, stream=LIVE, cls=3, state_key="k"))
        out = self.h.hear(item(2, stream=LIVE, cls=3, state_key="k", t=T0 + 10), T0 + 10)
        r = only(out, "retract")
        self.assertEqual((r["reason"], r["target"]["seq"]), ("held_superseded", 1))
        self.assertEqual(only(out)["reasons"], ["warmup_hold"])


class RestartTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_resurfaced_after_restart(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1))
        b = Harness(state_dir=self.dir)
        self.assertNotEqual(a.em.run, b.em.run)
        f = only(b.hear(item(1), T0 + 50), "frame")
        self.assertEqual((f["admission"], f["dedup"], f["disposition"]), ("verified", "resurfaced", "surface"))
        self.assertEqual(b.hear(item(1), T0 + 60), [])   # then an ordinary repeat

    def test_surfaced_before_restart_expires_without_being_heard(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1, ttl=10_000))
        b = Harness(state_dir=self.dir)
        r = only(b.tick(T0 + 10_000), "retract")
        self.assertEqual((r["reason"], r["target"]["seq"]), ("expired", 1))
        self.assertEqual(b.tick(T0 + 20_000), [])

    def test_revoked_key_retracts_at_start(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1))
        b = Harness(m=manifest(revoked=True), state_dir=self.dir)
        self.assertEqual([r["type"] for r in b.recs], ["hello", "landing_state", "retract"])
        self.assertEqual(b.recs[-1]["reason"], "revoked")

    def test_superseding_item_after_restart_retracts_the_old_value(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1, stream=LIVE, cls=3, state_key="k"))
        b = Harness(state_dir=self.dir)
        out = b.hear(item(2, stream=LIVE, cls=3, state_key="k", t=T0 + 10), T0 + 10)
        r = only(out, "retract")
        self.assertEqual((r["reason"], r["target"]["seq"], r["by"]["seq"]), ("superseded", 1, 2))

    def test_pluck_reheard_after_restart(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1))
        state = Path(self.dir, "receptor.json")
        snapshot = state.read_text()
        a.hear(pluck(2, 1))
        # The run ended after the listener kept the PLUCK and before the receptor recorded its retract.
        state.write_text(snapshot)
        b = Harness(state_dir=self.dir)
        r = only(b.hear(pluck(2, 1), T0 + 50), "retract")
        self.assertEqual((r["reason"], r["target"]["seq"]), ("plucked", 1))
        c = Harness(state_dir=self.dir)    # the target is no longer surfaced: a counter only
        self.assertEqual(c.hear(pluck(2, 1), T0 + 60), [])
        self.assertEqual(c.health(T0 + 60)["counters"]["admission"]["duplicate"], 1)

    def test_quarantine_survives_restart(self):
        a = Harness(state_dir=self.dir)
        a.hear(item(1))
        a.hear(item(1, body=b"other"))
        b = Harness(state_dir=self.dir)
        self.assertEqual(only(b.hear(item(5)))["reasons"], ["key_quarantined"])


class PresenceAndBeaconTest(unittest.TestCase):
    def test_presence_record_and_beacon_counters(self):
        st = Station(SK, [StreamConfig("chatter")], epoch=7, rng=random.Random(1), now_ms=T0)
        h = Harness()
        out = []
        beacons = []
        for t in range(T0, T0 + 3_000, 100):
            for f in st.poll(t):
                if f[3] == wire.KIND_BEACON:
                    beacons.append(f)
                out.extend(h.hear(f, t))
        p = only(out, "presence")
        self.assertEqual((p["station"], p["key_id"], p["state"]), ({"name": "cael", "principal": None}, KID.hex(), "ROOT_UNKNOWN"))
        self.assertEqual(h.hear(beacons[0], T0 + 3_000), [])          # an older beacon: a counter
        c = h.health(T0 + 3_000)
        self.assertEqual(c["counters"]["beacon"]["duplicate"], 1)
        self.assertIn(KID.hex(), c["beacon_age_ms"])


class UnverifiedTest(unittest.TestCase):
    def test_unverified_datagrams_are_counters_only_and_never_attributed(self):
        h = Harness()
        other = Ed25519PrivateKey.generate()
        stranger = wire.encode_item(other, wire.Item(epoch=1, stream=CHAT, seq=1, issued_at=T0, expires_at=T0 + 60_000,
                                                     cls=1, ctype=1, body=b"x"))
        tampered = bytearray(item(1))
        tampered[-1] ^= 1
        for d in (stranger, bytes(tampered), b"\x00" * 11, b"BC\x09" + b"\x00" * 100, item(2, t=T0 - 3_600_000)):
            self.assertEqual(h.hear(d), [])
        u = h.health()
        self.assertEqual({k: v for k, v in u["counters"]["unverified"].items() if v},
                         {"unknown_key": 1, "bad_signature": 1, "malformed": 1, "version": 1, "expired": 1})
        listed = {r["key_id"] for r in u["unverified"]["key_ids"]}
        self.assertIn(wire.key_id(wire.public_key_bytes(other)).hex(), listed)
        self.assertNotIn("cael", json.dumps(u["unverified"]))   # a key id, never a name (D34)
        self.assertEqual(u["last_datagram_at"], T0)

    def test_key_id_table_is_bounded_under_a_flood(self):
        h = Harness()
        heavy = os.urandom(8)
        sizes = []
        for i in range(2_000):
            kid = heavy if i % 3 == 0 else os.urandom(8)
            h.hear(b"BC\x02\x01" + kid + b"\x00" * 80)
            if i % 500 == 499:
                sizes.append(len(h.r.health(T0)))
        u = json.loads(h.r.health(T0))["unverified"]
        self.assertEqual(len(u["key_ids"]), 16)
        self.assertEqual(len(h.r.keys.rows), 16)
        self.assertEqual(u["key_ids"][0]["key_id"], heavy.hex())       # a heavy hitter stays listed
        self.assertEqual(u["other"], 2_000 - sum(r["count"] - r["error"] for r in u["key_ids"]))
        self.assertLess(max(sizes) - min(sizes), 64)                    # the record does not grow with the flood

    def test_space_saving_guarantee(self):
        t = KeyTable(4)
        for k in "aaaaabbbcde" * 3 + "fghij":
            t.add(k)
        rows = {r["key_id"]: r for r in t.to_json()["key_ids"]}
        self.assertIn("a", rows)
        self.assertGreaterEqual(rows["a"]["count"] - rows["a"]["error"], 0)
        self.assertGreaterEqual(rows["a"]["count"], 15)


class HealthTest(unittest.TestCase):
    def test_states_and_reasons(self):
        h = Harness()
        self.assertEqual((h.health(T0 + 1_000)["state"], h.health(T0 + 1_000)["reasons"]), ("ok", []))
        g = h.health(T0 + 30_000)
        self.assertEqual((g["state"], g["reasons"], g["last_datagram_at"]), ("degraded", ["no_datagrams"], None))
        h.hear(item(1), T0 + 30_000)
        h.r.records_dropped += 3
        g = h.health(T0 + 30_001)
        self.assertEqual(g["reasons"], ["records_lost"])
        self.assertEqual(g["records"]["dropped"], 3)
        self.assertEqual(h.health(T0 + 30_002)["reasons"], [])   # reported once per drop, not forever
        self.assertEqual(g["dedup"]["entries"], 1)
        for section, names in (("admission", records.ADMISSIONS), ("disposition", records.DISPOSITIONS),
                               ("retract", records.RETRACT_REASONS), ("unverified", records.UNVERIFIED)):
            self.assertEqual(tuple(g["counters"][section]), names)


if __name__ == "__main__":
    unittest.main()
