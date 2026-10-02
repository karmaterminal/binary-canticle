"""stations.toml, the static locator file (RFC-0001 §13.6), and how `canticle listen` uses it."""

import argparse
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from canticle import stations
from canticle.__main__ import _locators, main

FULL = """\
version = 1

[manifest]
path = "fleet.json"

[listen]
bind = "127.0.0.1:9998"
multicast = true
"""


def locator_args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**{"manifest": None, "stations": None, "bind": None, "multicast": None, **kw})


class StationsTomlTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        env = mock.patch.dict(os.environ, {"HOME": str(self.dir / "home")})
        env.start()
        self.addCleanup(env.stop)

    def write(self, text: str, name: str = "stations.toml") -> Path:
        p = self.dir / name
        p.write_text(text)
        return p

    def test_a_full_file(self):
        p = self.write(FULL)
        s = stations.load(p)
        self.assertEqual(s.path, p)
        self.assertEqual(s.manifest, self.dir / "fleet.json")  # relative to the file, not the working directory
        self.assertEqual((s.bind, s.multicast), ("127.0.0.1:9998", True))

    def test_a_minimal_file_takes_the_defaults(self):
        s = stations.load(self.write('version = 1\n[manifest]\npath = "/etc/canticle/fleet.json"\n'))
        self.assertEqual(s.manifest, Path("/etc/canticle/fleet.json"))
        self.assertEqual((s.bind, s.multicast), ("0.0.0.0:9999", False))  # multicast stays off unless asked for

    def test_a_home_relative_manifest(self):
        s = stations.load(self.write('version = 1\n[manifest]\npath = "~/.binary-canticle/fleet.json"\n'))
        self.assertEqual(s.manifest, self.dir / "home" / ".binary-canticle" / "fleet.json")

    def test_the_default_path(self):
        self.assertEqual(stations.default_path(), self.dir / "home" / ".binary-canticle" / "stations.toml")
        conf = self.dir / "home" / ".binary-canticle"
        conf.mkdir(parents=True)
        (conf / "stations.toml").write_text(FULL)
        self.assertEqual(stations.load().manifest, conf / "fleet.json")

    def test_a_missing_file(self):
        with self.assertRaises(stations.StationsMissing) as cm:
            stations.load(self.dir / "absent.toml")
        self.assertIn("absent.toml: not found", str(cm.exception))

    def test_malformed_toml(self):
        with self.assertRaises(stations.StationsError) as cm:
            stations.load(self.write('version = 1\n[manifest\npath = "fleet.json"\n'))
        self.assertNotIsInstance(cm.exception, stations.StationsMissing)
        self.assertIn("not valid TOML", str(cm.exception))

    def test_invalid_values(self):
        head = 'version = 1\n[manifest]\npath = "fleet.json"\n'
        cases = [
            ('[manifest]\npath = "fleet.json"\n', "version = 1 is required"),
            ('version = "1"\n[manifest]\npath = "fleet.json"\n', "version must be 1, not '1'"),
            ('version = 2\n[manifest]\npath = "fleet.json"\n', "version must be 1, not 2"),
            ("version = 1\n", "a [manifest] table"),
            ('version = 1\nmanifest = "fleet.json"\n', "a [manifest] table"),
            ('version = 1\n[manifest]\npath = ""\n', "manifest.path must be a non-empty string"),
            ('version = 1\nlisten = "0.0.0.0:9999"\n[manifest]\npath = "fleet.json"\n', "listen must be a table"),
            (head + '[listen]\nmulticast = "yes"\n', "listen.multicast must be true or false"),
            (head + "[listen]\nmulticast = 1\n", "listen.multicast must be true or false"),
            (head + "[listen]\nbind = 9999\n", "must be a string"),
            (head + '[listen]\nbind = "0.0.0.0"\n', "must be IPv4-address:port"),
            (head + '[listen]\nbind = "0.0.0.0:0"\n', "port from 1 to 65535"),
            (head + '[listen]\nbind = "0.0.0.0:65536"\n', "port from 1 to 65535"),
            (head + '[listen]\nbind = "0.0.0.0:+999"\n', "port from 1 to 65535"),
            (head + '[listen]\nbind = "localhost:9999"\n', "'localhost' is not an IPv4 address"),
            (head + '[listen]\nbind = "[::]:9999"\n', "is not an IPv4 address"),
        ]
        for text, expected in cases:
            with self.subTest(expected):
                with self.assertRaises(stations.StationsError) as cm:
                    stations.load(self.write(text))
                self.assertIn(expected, str(cm.exception))
                self.assertIn("stations.toml", str(cm.exception))  # names the file

    def test_unknown_keys_are_errors(self):
        # A misspelt key must fail, not leave its default in place (multicast silently off, say).
        head = 'version = 1\n[manifest]\npath = "fleet.json"\n'
        for text, expected in (
            (head + "[listen]\nmulticats = true\n", "unknown key listen.multicats"),
            (head.replace("path =", "file ="), "unknown key manifest.file"),
            ("verison = 1\n" + head, "unknown key verison"),
        ):
            with self.subTest(expected):
                with self.assertRaisesRegex(stations.StationsError, expected):
                    stations.load(self.write(text))

    def test_a_trust_table_is_refused(self):
        text = FULL + '\n[trust]\ngenesis = "sha256:00"\n'
        with self.assertRaisesRegex(stations.StationsError, r"\[trust\].*not supported.*unsigned"):
            stations.load(self.write(text))


class ListenLocatorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.conf = self.dir / "home" / ".binary-canticle"
        self.conf.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {"HOME": str(self.dir / "home"), "XDG_STATE_HOME": str(self.dir / "state")})
        env.start()
        self.addCleanup(env.stop)

    def test_without_a_manifest_listen_reads_stations_toml(self):
        (self.conf / "stations.toml").write_text(FULL)
        manifest, bind, multicast, source = _locators(locator_args())
        self.assertEqual((manifest, bind, multicast, source),
                         (str(self.conf / "fleet.json"), "127.0.0.1:9998", True, self.conf / "stations.toml"))

    def test_flags_win_over_the_file(self):
        p = self.dir / "elsewhere.toml"
        p.write_text(FULL)
        manifest, bind, multicast, source = _locators(locator_args(stations=str(p), bind="0.0.0.0:7777", multicast=False))
        self.assertEqual((manifest, bind, multicast, source), (str(self.dir / "fleet.json"), "0.0.0.0:7777", False, p))

    def test_a_manifest_flag_skips_the_file(self):
        (self.conf / "stations.toml").write_text("not toml at all [")
        self.assertEqual(_locators(locator_args(manifest="fleet.json")), ("fleet.json", "0.0.0.0:9999", False, None))
        self.assertEqual(_locators(locator_args(manifest="fleet.json", bind="127.0.0.1:1", multicast=True)),
                         ("fleet.json", "127.0.0.1:1", True, None))

    def test_listen_without_any_locator(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(["listen"]), 1)
        self.assertIn("stations.toml: not found", err.getvalue())
        self.assertIn("pass --manifest", err.getvalue())
        self.assertFalse((self.dir / "state").exists())  # refused before any listener state is created

    def test_listen_with_a_broken_stations_toml(self):
        (self.conf / "stations.toml").write_text('version = 1\n[manifest]\npath = "fleet.json"\n[listen]\nmulticats = true\n')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(["listen"]), 1)
        self.assertIn("unknown key listen.multicats", err.getvalue())

    def test_listen_with_an_unloadable_manifest(self):
        (self.conf / "stations.toml").write_text(FULL)
        (self.conf / "fleet.json").write_text('{"manifest": "canticle-fleet/spike-0", "stations": [{"name": "x"}]}')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(["listen"]), 1)
        self.assertIn("canticle manifest verify lists every problem", err.getvalue())
        self.assertFalse((self.dir / "state").exists())

    def test_manifest_and_stations_are_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["listen", "--manifest", "fleet.json", "--stations", "stations.toml"])


if __name__ == "__main__":
    unittest.main()
