"""The commissioning inventory must not promote source bytes to a live proof."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "proofs/lesson-x/inventory.py"
spec = importlib.util.spec_from_file_location("lesson_x_inventory", SOURCE)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for name in inventory.PATHS["canticle"]:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("reviewed source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)

    def test_clean_source_is_never_a_runtime_or_release_receipt(self):
        result = inventory.report({"canticle": self.repo})
        self.assertTrue(result["repositories"]["canticle"]["selected_sources_match_head"])
        self.assertFalse(result["runtime_installation_verified"])
        self.assertFalse(result["live_session_encounter_proved"])
        self.assertFalse(result["policy_adoption_verified"])
        self.assertEqual(result["lesson_release"], "not_evaluated")

    def test_changed_source_is_distinguished_without_printing_its_contents(self):
        (self.repo / inventory.PATHS["canticle"][0]).write_text("PRIVATE SENTINEL")
        result = inventory.report({"canticle": self.repo})
        self.assertFalse(result["repositories"]["canticle"]["selected_sources_match_head"])
        self.assertNotIn("PRIVATE SENTINEL", json.dumps(result))

    def test_outside_symlink_is_not_read_and_output_is_not_overwritten(self):
        outside = self.root / "private"
        outside.write_text("PRIVATE SENTINEL")
        selected = self.repo / inventory.PATHS["canticle"][0]
        selected.unlink()
        selected.symlink_to(outside)
        result = inventory.report({"canticle": self.repo})
        self.assertEqual(result["repositories"]["canticle"]["files"][0]["error"],
                         "source_unavailable_or_unsafe")
        self.assertNotIn("PRIVATE SENTINEL", json.dumps(result))
        output = self.root / "existing.json"
        output.write_text("keep me")
        self.assertEqual(inventory.main(["--canticle", str(self.repo), "--output", str(output)]), 2)
        self.assertEqual(output.read_text(), "keep me")

    def test_missing_checkout_is_reported_without_environment_details(self):
        result = inventory.report({"canticle": self.root / "missing"})
        self.assertEqual(result["repositories"]["canticle"],
                         {"error": "checkout_unavailable_or_unsafe"})
        self.assertNotIn(str(self.root), json.dumps(result))
