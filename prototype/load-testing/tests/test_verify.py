"""Verifier negative controls over committed, real-run receipts; no live load."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from verify import verify

class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="canticle-verify-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "negative"
        shutil.copytree(HERE / "evidence/2026-11-23-smoke/negative", self.root)

    def mutate(self, name, change):
        path = self.root / name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_real_receipt_controls(self):
        self.assertTrue(verify(self.root, negative=True)["verified"])
        self.assertTrue(verify(HERE / "evidence/2026-11-23-smoke/smoke")["verified"])

    def test_negative_json_cannot_hide_successful_process_exit(self):
        self.mutate("process.json", lambda p: p.update(k6_exit_code=0, supervisor_exit_code=0))
        with self.assertRaises(AssertionError): verify(self.root, negative=True)

    def test_missing_item_cannot_be_deleted_from_expected_plan(self):
        self.mutate("fixture-report.json", lambda p: p["expected_ids"].pop())
        with self.assertRaises(AssertionError): verify(self.root, negative=True)

    def test_missing_row_cannot_hide_in_aggregate_counts(self):
        self.mutate("fixture-report.json", lambda p: p["rows"].pop())
        with self.assertRaises(AssertionError): verify(self.root, negative=True)

    def test_success_verifier_rejects_negative_control(self):
        with self.assertRaises(AssertionError): verify(self.root)

    def test_unreaped_child_cannot_pass(self):
        self.mutate("process.json", lambda p: p.update(child_reaped=False))
        with self.assertRaises(AssertionError): verify(self.root, negative=True)

if __name__ == "__main__": unittest.main()
