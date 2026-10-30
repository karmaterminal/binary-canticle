import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("beacon", Path(__file__).with_name("beacon.py"))
beacon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beacon)


class BeaconTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.auth, self.state = (root / name for name in ("fixture.jsonl", "auth.json", "state.json"))
        self.cfg = {"enabled": True, "actor": "alice", "station": "familiar",
                    "source": str(self.source), "audience": "lan", "stream": "wake",
                    "ttl_s": 60, "cadence_s": 30, "inactive_s": 60}
        self.auth.write_text(json.dumps(self.cfg))
        self.sent = []

    def add(self, **kw):
        row = {"actor": "alice", "origin": "actor", "shareable": True,
               "lineage": "local", "kind": "tool", "id": "step1", "topic": "checked tests"}
        row.update(kw)
        with self.source.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def tick(self, now=100):
        return beacon.tick(auth=self.auth, source=self.source, state=self.state,
                           actor="alice", socket_path="fake", now=now,
                           sink=lambda _, req: self.sent.append(req))

    def test_dedupe_restart_and_provenance(self):
        self.add()
        self.add()
        self.assertEqual(self.tick(), "published")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.tick(), "idle")
        self.assertEqual(len(self.sent), 1)
        self.add(id="step1", topic="changed label")
        self.assertEqual(self.tick(now=110), "idle")
        self.assertEqual(len(self.sent), 1)
        req = self.sent[0]
        self.assertEqual((req["stream"], req["class"], req["scope"], req["ttl"]),
                         ("wake", "chatter", "lan", 60))
        self.assertIn("source sha256:", req["text"])
        self.assertIn("row:", req["text"])
        self.assertLessEqual(len(req["text"].encode()), 800)
        self.assertNotIn("fixture.jsonl", req["text"])

    def test_redaction_and_no_echo(self):
        self.add(id="safe", topic="reviewed code")
        self.add(id="secret", topic="token sk-abcdef123456")
        self.add(id="heard", topic="canticle heard text")
        self.add(id="raw", topic="safe label", lineage="canticle")
        self.add(id="other", actor="bob", topic="other work")
        self.tick()
        self.assertIn("reviewed code", self.sent[0]["text"])
        for forbidden in ("sk-abcdef", "canticle heard", "other work", "safe label"):
            self.assertNotIn(forbidden, self.sent[0]["text"])

    def test_bounds_inactivity_and_revocation(self):
        self.add()
        self.tick()
        self.assertEqual(self.tick(now=161), "inactive-stop")
        self.cfg["enabled"] = False
        self.auth.write_text(json.dumps(self.cfg))
        with self.assertRaises(ValueError):
            self.tick(now=162)

    def test_oversize_and_sink_failure_preserve_checkpoint(self):
        self.add(topic="A" * 65)
        self.assertEqual(self.tick(), "idle")
        self.add(id="a", topic="safe")
        with self.assertRaises(RuntimeError):
            beacon.tick(auth=self.auth, source=self.source, state=self.state,
                        actor="alice", socket_path="fake", now=100,
                        sink=lambda *_: (_ for _ in ()).throw(RuntimeError("refused")))
        self.assertEqual(json.loads(self.state.read_text())["offset"], 1)


if __name__ == "__main__":
    unittest.main()
