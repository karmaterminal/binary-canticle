"""Structural fail-closed controls; synthetic process fields are NOT run evidence."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from verify import verify


class ProcessReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="canticle-process-verify-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "receipt"
        shutil.copytree(HERE / "evidence/2026-11-23-smoke/smoke", self.root)
        self.change("run.json", lambda r: r.update(shared_process=False))
        children = {role: dict(pid=pid, alive=True, started=True, ready=True,
            started_ns=1, child_started_ns=2, ready_ns=3, exit_code=None)
            for role, pid in (("station", 101), ("daemon", 102))}
        self.change("fixture-report.json", lambda r: r.update(process_mode=True,
            parent_pid=100, processes=children))
        cleaned = {role: dict(receipt, alive=False, reaped=True, exit_code=0,
            handle_closed=True, term_sent=True, kill_sent=False,
            exit_observed_ns=4 if role == "station" else 5,
            reaped_ns=4 if role == "station" else 5) for role, receipt in children.items()}
        self.change("cleanup.json", lambda r: r.update(processes_reaped=True, processes=cleaned))

    def change(self, filename, mutate):
        path = self.root / filename
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))

    def rejects(self, filename, mutate):
        self.change(filename, mutate)
        with self.assertRaises(AssertionError):
            verify(self.root)

    def test_structural_control_only_not_process_evidence(self):
        self.assertTrue(verify(self.root)["verified"])

    def test_same_process_cannot_masquerade_as_two_children(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["station"].update(pid=102))

    def test_parent_cannot_masquerade_as_child(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["station"].update(pid=100))

    def test_dead_child_cannot_pass(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["daemon"].update(alive=False))

    def test_missing_reap_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(reaped=False))

    def test_failed_exit_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(exit_code=1))

    def test_unready_child_cannot_pass(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["station"].update(ready=False))

    def test_forced_kill_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(kill_sent=True))

    def test_daemon_first_shutdown_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(reaped_ns=6))

    def test_missing_readiness_cannot_pass(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["station"].pop("ready"))

    def test_impossible_start_order_cannot_pass(self):
        self.rejects("fixture-report.json", lambda r: r["processes"]["station"].update(child_started_ns=4))

    def test_cleanup_alive_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(alive=True))

    def test_open_handle_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(handle_closed=False))

    def test_changed_startup_receipt_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(child_started_ns=3))

    def test_wrong_reaped_pid_cannot_pass(self):
        self.rejects("cleanup.json", lambda r: r["processes"]["station"].update(pid=999))


if __name__ == "__main__":
    unittest.main()
