"""Manifest checks (RFC-0001 §9.3, §10.3), `canticle manifest verify|show` and `canticle keygen`."""

import contextlib
import errno
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from canticle import vectors, wire
from canticle.__main__ import main
from canticle.ids import check_public_key, check_stream_name, stream_id
from canticle.manifest import Manifest, StationEntry, verify_json

# The eight small-order points of edwards25519: the identity, the point of order 2, two of order 4
# and four of order 8. A manifest that lists one lets anyone forge signatures as its key-id (§9.3).
SMALL_ORDER = [
    "0100000000000000000000000000000000000000000000000000000000000000",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000080",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
]
NOT_ON_CURVE = "02" + "00" * 31          # y = 2: (y^2 - 1) / (d y^2 + 1) has no square root
NON_CANONICAL = "ed" + "ff" * 30 + "7f"  # y = p


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def good() -> dict:
    return vectors.manifest().to_json()  # test1, test2, test3 (revoked)


class KeyCheckTest(unittest.TestCase):
    def test_generated_and_rfc8032_keys_pass(self):
        for name, k in vectors.keys().items():
            with self.subTest(name):
                check_public_key(bytes.fromhex(k["public"]))

    def test_small_order_keys_are_refused(self):
        for h in SMALL_ORDER:
            with self.subTest(key=h):
                with self.assertRaisesRegex(ValueError, "small-order"):
                    check_public_key(bytes.fromhex(h))

    def test_malformed_encodings_are_refused(self):
        for h, why in ((NOT_ON_CURVE, "not a point"), (NON_CANONICAL, "not a canonical encoding"),
                       ("01" + "00" * 30 + "80", "x = 0 with the sign bit set"), ("00" * 31, "32 bytes")):
            with self.subTest(key=h), self.assertRaisesRegex(ValueError, why):
                check_public_key(bytes.fromhex(h))

    def test_the_manifest_refuses_a_small_order_key(self):
        # §9.3: refuse small-order keys when loading the manifest, so the listener never resolves one.
        for h in SMALL_ORDER:
            with self.subTest(key=h):
                with self.assertRaisesRegex(ValueError, "small-order"):
                    Manifest([StationEntry("evil", bytes.fromhex(h), frozenset({1}))])
                data = good()
                data["stations"][0].update(public_key=h, key_id=wire.key_id(bytes.fromhex(h)).hex())
                with self.assertRaisesRegex(ValueError, "small-order"):
                    Manifest.from_json(data)


class VerifyTest(unittest.TestCase):
    def test_a_written_manifest_verifies_and_lists_key_ids(self):
        data = good()
        self.assertEqual(verify_json(data), [])
        for s in data["stations"]:
            self.assertEqual(s["key_id"], wire.key_id(bytes.fromhex(s["public_key"])).hex())

    def test_key_id_is_optional(self):
        data = good()  # a manifest written before entries carried key_id
        for s in data["stations"]:
            del s["key_id"]
        self.assertEqual(verify_json(data), [])
        self.assertEqual(len(list(Manifest.from_json(data))), 3)

    def test_a_mismatched_key_id_is_refused_by_verify_and_by_the_listener(self):
        data = good()
        data["stations"][1]["key_id"] = data["stations"][0]["key_id"]  # test2 claims test1's key-id
        problems = verify_json(data)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("stations[1] (test2): key_id", problems[0])
        self.assertIn("is not SHA-256(public_key)[0:8]", problems[0])
        with self.assertRaisesRegex(ValueError, r"'test2'.*is not SHA-256\(public_key\)\[0:8\]"):
            Manifest.from_json(data)  # what `canticle listen` loads

    def test_every_problem_is_reported(self):
        def entry(**kw):
            return lambda d: d["stations"][0].update(kw)

        cases = [
            (lambda d: d.update(extra=1), "unknown field 'extra'"),
            (lambda d: d.update(manifest="canticle-fleet/v1"), "not 'canticle-fleet/spike-0'"),
            (lambda d: d.update(signed=True), "signed must be false"),
            (lambda d: d.update(stations={}), "stations must be a list"),
            (lambda d: d["stations"].append("cael"), "stations[3]: not an object"),
            (entry(revokd=True), "unknown field 'revokd'"),
            (entry(name="Cael"), "name 'Cael' does not match"),
            (entry(name="test1\n"), "name 'test1\\n' does not match"),
            (entry(streams=["chatter\n"]), "invalid stream name 'chatter\\n'"),
            (entry(public_key=good()["stations"][0]["public_key"].upper()), "64 lowercase hex"),
            (entry(public_key="d75a98"), "64 lowercase hex"),
            (entry(public_key=NOT_ON_CURVE), "not a point on edwards25519"),
            (entry(public_key=NON_CANONICAL), "not a canonical encoding"),
            (entry(public_key=SMALL_ORDER[4]), "small-order"),
            (entry(key_id="D75A980182B10AB7"), "key_id must be 16 lowercase hex"),
            (entry(classes=["chatter", "gossip"]), "unknown class 'gossip'"),
            (entry(classes="chatter"), "classes must be a list"),
            (entry(scopes=["mars"]), "unknown scope 'mars'"),
            (entry(streams=["Chatter"]), "invalid stream name 'Chatter'"),
            (entry(streams="chatter"), "streams must be a list of stream names"),
            (entry(revoked="yes"), "revoked must be true or false"),
            (lambda d: d["stations"].append(dict(d["stations"][0], name="twin")), "same key as stations[0] (test1)"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected):
                data = good()
                mutate(data)
                problems = verify_json(data)
                self.assertTrue(any(expected in p for p in problems), problems)
        self.assertEqual(verify_json(["not", "an", "object"]), ["the manifest is not a JSON object"])

    def test_a_name_with_a_trailing_newline_is_refused(self):
        # With re.match, `$` also matches before a final newline: "chatter\n" would hash to its own stream_id.
        with self.assertRaisesRegex(ValueError, "invalid stream name"):
            check_stream_name("chatter\n")
        with self.assertRaisesRegex(ValueError, "invalid stream name"):
            Manifest([StationEntry("cael", bytes.fromhex(good()["stations"][0]["public_key"]), frozenset({1}),
                                   ("chatter\n",))])

    def test_a_manifest_without_problems_loads(self):
        data = good()
        data["stations"][0]["streams"] = ["chatter", "lens.threat.now"]
        self.assertEqual(verify_json(data), [])
        Manifest.from_json(data)


class ManifestCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        env = mock.patch.dict(os.environ, {"HOME": str(self.dir / "home"), "XDG_STATE_HOME": str(self.dir / "state")})
        env.start()
        self.addCleanup(env.stop)

    def write(self, data, name="fleet.json") -> str:
        p = self.dir / name
        p.write_text(data if isinstance(data, str) else json.dumps(data))
        return str(p)

    def test_verify_good(self):
        path = self.write(good())
        code, out, _ = run("manifest", "verify", path)
        self.assertEqual(code, 0, out)
        for s in good()["stations"]:
            self.assertIn(f"{s['name']:<16} {s['key_id']}  matches its public key", out)
        self.assertIn("REVOKED", out)
        self.assertIn("UNSIGNED", out)
        self.assertIn("verify: ok (structure, keys and key ids; no signature checked)", out)
        code, out, _ = run("manifest", "verify", path, "--json")
        report = json.loads(out)
        self.assertEqual((code, report["ok"], report["signed"], report["problems"]), (0, True, False, []))
        self.assertEqual([r["key_id_listed"] for r in report["stations"]], [True, True, True])

    def test_verify_mismatched_key_id(self):
        data = good()
        data["stations"][2]["key_id"] = "00" * 8
        code, out, _ = run("manifest", "verify", self.write(data))
        self.assertEqual(code, 1, out)
        self.assertIn("stations[2] (test3): key_id 0000000000000000 is not SHA-256(public_key)[0:8]", out)
        self.assertIn("UNSIGNED", out)
        self.assertIn("verify: FAILED", out)
        report = json.loads(run("manifest", "verify", self.write(data), "--json")[1])
        self.assertEqual((report["ok"], len(report["problems"]), report["stations"]), (False, 1, []))

    def test_show(self):
        path = self.write(good())
        code, out, _ = run("manifest", "show", path)
        self.assertEqual(code, 0, out)
        self.assertIn("UNSIGNED", out)
        self.assertIn(f"lens.threat ({stream_id('lens.threat'):08x})", out)
        rows = json.loads(run("manifest", "show", path, "--json")[1])["stations"]
        self.assertEqual([r["name"] for r in rows], ["test1", "test2", "test3"])
        self.assertEqual(rows[0]["streams"][0], {"name": "chatter", "stream_id": f"{stream_id('chatter'):08x}"})
        self.assertTrue(rows[2]["revoked"])

    def test_show_exits_1_when_verify_finds_problems(self):
        data = good()
        data.update(manifest="canticle-fleet/v9", signed=True)
        code, out, _ = run("manifest", "show", self.write(data))
        self.assertEqual(code, 1, out)
        self.assertIn(": canticle-fleet/v9, 3 station(s), UNSIGNED", out)
        self.assertIn("verify: 2 problem(s)", out)
        self.assertEqual(run("manifest", "show", self.write(data), "--json")[0], 1)

    def test_show_refuses_what_the_listener_would_refuse(self):
        data = good()
        data["stations"][0]["key_id"] = "11" * 8
        code, out, err = run("manifest", "show", self.write(data))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("does not load", err)

    def test_unreadable_input(self):
        self.assertEqual(run("manifest", "verify", self.write("{not json"))[0], 1)
        self.assertEqual(run("manifest", "verify", str(self.dir / "absent.json"))[0], 1)

    def test_default_path_comes_from_stations_toml(self):
        code, _, err = run("manifest", "verify")
        self.assertEqual(code, 1)
        self.assertIn("stations.toml: not found", err)
        self.assertIn("canticle manifest verify PATH", err)
        conf = self.dir / "home" / ".binary-canticle"
        conf.mkdir(parents=True)
        (conf / "fleet.json").write_text(json.dumps(good()))
        (conf / "stations.toml").write_text('version = 1\n[manifest]\npath = "fleet.json"\n')
        code, out, _ = run("manifest", "verify")
        self.assertEqual(code, 0, out)
        self.assertIn(str(conf / "fleet.json"), out)


class KeygenTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.key, self.fleet = self.dir / "cael.key", self.dir / "fleet.json"

    def keygen(self, *extra, key=None):
        return run("keygen", "--out", str(key or self.key), "--manifest", str(self.fleet), *extra)

    def test_keygen_writes_a_private_key_and_a_verifiable_manifest(self):
        code, out, err = self.keygen("--name", "cael", "--classes", "chatter,live-state", "--streams", "chatter,lens.threat")
        self.assertEqual(code, 0, err)
        info = json.loads(out)
        self.assertEqual(stat.S_IMODE(self.key.stat().st_mode), 0o600)
        data = json.loads(self.fleet.read_text())
        self.assertEqual(data["stations"][0]["key_id"], info["key_id"])
        self.assertEqual(verify_json(data), [])
        code, _, err = self.keygen("--name", "ronan", key=self.dir / "ronan.key")
        self.assertEqual(code, 0, err)
        self.assertEqual([s["name"] for s in json.loads(self.fleet.read_text())["stations"]], ["cael", "ronan"])

    def test_a_refused_keygen_writes_no_key(self):
        # Each of these used to write the key and then fail, leaving a key that is in no manifest and that
        # makes the corrected command fail with "exists; refusing to overwrite".
        bad = good()
        bad["stations"][0]["key_id"] = "00" * 8
        cases = [
            ((), None, "--manifest needs --name"),
            (("--name", "Cael"), None, "--manifest needs --name"),
            (("--name", "cael\n"), None, "--manifest needs --name"),
            (("--name", "cael", "--classes", "chatter,gossip"), None, "unknown class 'gossip'"),
            (("--name", "cael", "--scopes", "host,mars"), None, "unknown scope 'mars'"),
            (("--name", "cael", "--streams", "Chatter"), None, "invalid stream name"),
            (("--name", "cael"), json.dumps(bad), "is not SHA-256(public_key)[0:8]"),
            (("--name", "cael"), "{not json", "no key written"),
        ]
        for extra, manifest, expected in cases:
            with self.subTest(extra=extra, manifest=(manifest or "")[:20]):
                for p in (self.key, self.fleet):
                    p.unlink(missing_ok=True)
                if manifest is not None:
                    self.fleet.write_text(manifest)
                code, _, err = self.keygen(*extra)
                self.assertEqual(code, 1)
                self.assertIn(expected, err)
                self.assertIn("no key written", err)
                self.assertFalse(self.key.exists())
                if manifest is None:
                    self.assertFalse(self.fleet.exists())
                else:
                    self.assertEqual(self.fleet.read_text(), manifest)

    def test_a_failed_manifest_write_leaves_no_key(self):
        # The manifest is written beside the old one and moved into place only after the key is on disk; if
        # either step fails, the key is removed and the old manifest is left as it was.
        self.fleet.write_text(json.dumps(good()))
        before = self.fleet.read_text()
        for target, fault in (("os.replace", OSError(errno.EROFS, "Read-only file system")),
                              ("canticle.manifest.Manifest.stage", OSError(errno.ENOSPC, "No space left on device"))):
            with self.subTest(target):
                with mock.patch(target, side_effect=fault):
                    code, _, err = self.keygen("--name", "cael")
                self.assertEqual(code, 1)
                self.assertIn("no key written", err)
                self.assertFalse(self.key.exists())
                self.assertEqual(self.fleet.read_text(), before)
                self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["fleet.json"])  # no temporary file left

    def test_keygen_refuses_one_file_for_key_and_manifest(self):
        code, _, err = self.keygen("--name", "cael", key=self.fleet)
        self.assertEqual(code, 1)
        self.assertIn("name the same file", err)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_a_second_key_under_one_name_is_a_rotation(self):
        # §10.3 rotation lists the old and new key side by side, so a name may have two keys; keygen says so.
        self.assertEqual(self.keygen("--name", "cael")[0], 0)
        code, _, err = self.keygen("--name", "cael", key=self.dir / "cael-2.key")
        self.assertEqual(code, 0, err)
        self.assertIn("cael already has key-id", err)
        self.assertEqual(verify_json(json.loads(self.fleet.read_text())), [])

    def test_the_manifest_keeps_its_mode_and_its_symlink(self):
        real = self.dir / "conf"
        real.mkdir()
        (real / "fleet.json").write_text(json.dumps(good()))
        os.chmod(real / "fleet.json", 0o640)
        self.fleet.symlink_to(real / "fleet.json")
        self.assertEqual(self.keygen("--name", "cael")[0], 0)
        self.assertTrue(self.fleet.is_symlink())
        self.assertEqual(stat.S_IMODE((real / "fleet.json").stat().st_mode), 0o640)
        self.assertEqual(len(json.loads((real / "fleet.json").read_text())["stations"]), 4)
        self.assertEqual(sorted(p.name for p in real.iterdir()), ["fleet.json"])

    def test_missing_directories_are_refused_before_the_key_is_written(self):
        code, _, err = self.keygen("--name", "cael", key=self.dir / "nowhere" / "cael.key")
        self.assertEqual(code, 1)
        self.assertIn("no such directory", err)
        self.fleet = self.dir / "nowhere" / "fleet.json"
        code, _, err = self.keygen("--name", "cael")
        self.assertEqual(code, 1)
        self.assertFalse(self.key.exists())


if __name__ == "__main__":
    unittest.main()
