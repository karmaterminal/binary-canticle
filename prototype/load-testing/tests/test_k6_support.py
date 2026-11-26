"""Portable discovery and explicit required-k6 admission controls."""
import unittest
from unittest.mock import patch

from k6_support import k6_binary


class K6DiscoveryTest(unittest.TestCase):
    def test_path_discovery(self):
        with patch.dict("os.environ", {}, clear=True), patch("k6_support.shutil.which", return_value="/bin/k6") as which:
            self.assertEqual(k6_binary(self), "/bin/k6")
            which.assert_called_once_with("k6")

    def test_explicit_binary_wins_over_path(self):
        with patch.dict("os.environ", {"CANTICLE_K6": "/custom/k6"}, clear=True), patch("k6_support.shutil.which", return_value="/custom/k6") as which:
            self.assertEqual(k6_binary(self), "/custom/k6")
            which.assert_called_once_with("/custom/k6")

    def test_absent_optional_binary_skips(self):
        with patch.dict("os.environ", {}, clear=True), patch("k6_support.shutil.which", return_value=None):
            with self.assertRaises(unittest.SkipTest):
                k6_binary(self)

    def test_absent_required_binary_fails_not_skips(self):
        with patch.dict("os.environ", {"CANTICLE_K6": "/missing/k6", "CANTICLE_REQUIRE_K6": "1"}, clear=True), patch("k6_support.shutil.which", return_value=None):
            with self.assertRaises(AssertionError):
                k6_binary(self)
