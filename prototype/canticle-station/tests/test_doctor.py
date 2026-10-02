"""`canticle doctor` (RFC-0001 §11.2, §15.7): its checks, its exit status, and what it must not do."""

import argparse
import contextlib
import fcntl
import io
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from canticle import doctor, vectors
from canticle.__main__ import _default_state, _listener_state, main


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def hold(port: int, shared: bool) -> socket.socket:
    """Bind 127.0.0.1:port as another process would; shared sets SO_REUSEADDR, as `canticle listen` does."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if shared:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    return s


def take_lease(path) -> object:
    """Hold a state lease the way `canticle listen` does (`__main__._listener_state`)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, "a")
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return f


class SpySocket(socket.socket):
    """A real socket that records its setsockopt calls (doctor.socket.socket is patched with it). It records a
    group join but never makes it, so no test sends an IGMP report from this host."""
    calls: list = []

    def setsockopt(self, *args):
        SpySocket.calls.append(args)
        if args[:2] == (socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP):
            return None
        return super().setsockopt(*args)


def joins(calls) -> int:
    return sum(c[:2] == (socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP) for c in calls)


def snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in sorted(root.rglob("*"))}


class ChecksTest(unittest.TestCase):
    def test_python(self):
        self.assertEqual(doctor.check_python().status, "ok")
        self.assertEqual(doctor.check_python((3, 11, 0)).status, "ok")
        old = doctor.check_python((3, 10, 14))
        self.assertEqual(old.status, "fail")
        self.assertIn("needs 3.11 or newer", old.detail)

    def test_cryptography(self):
        self.assertIsNone(doctor.ed25519_known_answer())
        self.assertEqual(doctor.check_cryptography().status, "ok")
        self.assertEqual(doctor.check_cryptography("44.0.3", known_answer=lambda: None).status, "fail")
        self.assertEqual(doctor.check_cryptography("46.0.0.dev1", known_answer=lambda: None).status, "ok")
        broken = doctor.check_cryptography("50.0.1", known_answer=lambda: "the signature differs")
        self.assertEqual(broken.status, "fail")
        self.assertIn("does not reproduce RFC 8032 TEST 1: the signature differs", broken.detail)

    def test_the_known_answer_compares(self):
        wrong = "00" * 64
        with mock.patch.object(doctor, "KAT_SIGNATURE", wrong):
            self.assertEqual(doctor.ed25519_known_answer(), "the signature differs")
        with mock.patch.object(doctor, "KAT_PUBLIC", "00" * 32):
            self.assertEqual(doctor.ed25519_known_answer(), "the public key differs")

    def test_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fleet.json"
            self.assertEqual(doctor.check_manifest(p).status, "fail")  # not found
            p.write_text("{")
            self.assertEqual(doctor.check_manifest(p).status, "fail")
            data = vectors.manifest().to_json()
            p.write_text(json.dumps(data))
            ok = doctor.check_manifest(p)
            self.assertEqual((ok.status, ok.data["stations"], ok.data["signed"]), ("ok", 3, False))
            self.assertIn("UNSIGNED", ok.detail)
            data["stations"][0]["key_id"] = "00" * 8
            p.write_text(json.dumps(data))
            bad = doctor.check_manifest(p)
            self.assertEqual(bad.status, "fail")
            self.assertIn("is not SHA-256(public_key)[0:8]", bad.data["problems"][0])
            p.write_text(json.dumps({**data, "stations": []}))
            self.assertIn("no stations", doctor.check_manifest(p).detail)

    def test_bind_free(self):
        port = free_port()
        c = doctor.check_bind(f"127.0.0.1:{port}", {})
        self.assertEqual((c.status, c.data["held_by"]), ("ok", None))

    def test_bind_held_by_another_process(self):
        with tempfile.TemporaryDirectory() as d:
            leases = {"listener": os.path.join(d, "listener.json.lease")}
            for shared in (False, True):
                with self.subTest(shared=shared):
                    port = free_port()
                    with hold(port, shared):
                        c = doctor.check_bind(f"127.0.0.1:{port}", leases)
                    self.assertEqual((c.status, c.data["held_by"]), ("fail", "other"))
                    self.assertIn("is in use, and not by this listener", c.detail)
                    self.assertIn("--ephemeral (which holds no lease)", c.detail)
            self.assertEqual(os.listdir(d), [])  # probing a lease never creates it

    def test_the_bind_probe_never_shares_a_listener_port(self):
        # A probe bound with SO_REUSEADDR would join a running listener's port and could take its unicast datagrams.
        port = free_port()
        SpySocket.calls = []
        with hold(port, shared=True), mock.patch.object(doctor.socket, "socket", SpySocket):
            self.assertEqual(doctor.check_bind(f"127.0.0.1:{port}", {}).status, "fail")
        self.assertNotIn((socket.SOL_SOCKET, socket.SO_REUSEADDR), [c[:2] for c in SpySocket.calls])

    def test_bind_held_by_this_listener(self):
        with tempfile.TemporaryDirectory() as d:
            leases = {"listener": os.path.join(d, "listener.json.lease"), "tuner": os.path.join(d, "tuner.json.lease")}
            for label in ("listener", "tuner"):
                with self.subTest(label):
                    port = free_port()
                    lease = take_lease(leases[label])
                    try:
                        with hold(port, shared=True):
                            c = doctor.check_bind(f"127.0.0.1:{port}", leases)
                    finally:
                        lease.close()
                    self.assertEqual((c.status, c.data["held_by"]), ("ok", label), c.detail)
            # A lease file left behind by a listener that has exited is not held: the port is someone else's.
            port = free_port()
            with hold(port, shared=True):
                self.assertEqual(doctor.check_bind(f"127.0.0.1:{port}", leases).status, "fail")

    def test_bind_malformed(self):
        for bind in ("127.0.0.1:0", "127.0.0.1:x", "127.0.0.1:70000", "203.0.113.7:9999"):  # the last is not ours
            with self.subTest(bind):
                self.assertEqual(doctor.check_bind(bind, {}).status, "fail")

    def test_multicast_is_a_report_whatever_the_probe_finds(self):
        for heard in (True, False):
            with self.subTest(heard=heard):
                c = doctor.multicast_report(False, "0.0.0.0:9999", probe=lambda: (heard, "why"))
                self.assertEqual((c.status, c.data["decided"], c.data["loopback"]), ("report", False, heard))
        c = doctor.multicast_report(True, "127.0.0.1:9999", probe=None)
        self.assertEqual((c.status, c.data["loopback"], c.data["bind_hears_group"]), ("report", None, False))
        self.assertIn("cannot hear 239.255.13.13", c.detail)
        self.assertNotIn("bind_hears_group", doctor.multicast_report(True, "0.0.0.0:9999").data)

    def test_the_loopback_probe_answers(self):
        SpySocket.calls = []
        with mock.patch.object(doctor.socket, "socket", SpySocket):  # the join is recorded, never made
            heard, why = doctor.loopback_probe(timeout_s=0.2)  # either answer is fine here; it must not raise
        self.assertIsInstance(heard, bool)
        self.assertTrue(why)
        self.assertEqual(joins(SpySocket.calls), 1)

    def test_should_probe(self):
        for configured, force, never, want in ((None, False, False, False), (False, False, False, False),
                                               (True, False, False, True), (False, True, False, True),
                                               (True, False, True, False), (None, True, True, False)):
            with self.subTest(configured=configured, force=force, never=never):
                self.assertEqual(doctor.should_probe(configured, force=force, never=never), want)

    def test_the_probe_datagram_never_leaves_this_host(self):
        SpySocket.calls = []
        with mock.patch.object(doctor.socket, "socket", SpySocket):
            doctor.loopback_probe(timeout_s=0.2)
        ttl = [c[2] for c in SpySocket.calls if c[:2] == (socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)]
        self.assertEqual(ttl, [0])

    def test_render(self):
        checks = [doctor.Check("python", "ok", "Python 3.11"),
                  doctor.Check("manifest", "fail", "2 problem(s)", {"problems": ["one", "two"]})]
        text = doctor.render(checks)
        self.assertIn("fail    manifest  2 problem(s)\n                  - one\n", text)
        self.assertTrue(text.endswith("doctor: 1 check(s) failed (exit 1). Multicast is reported, not decided (RFC §11.2)."))


class DoctorCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.conf = self.dir / "home" / ".binary-canticle"
        self.conf.mkdir(parents=True)
        self.state = self.dir / "state"
        env = mock.patch.dict(os.environ, {"HOME": str(self.dir / "home"), "XDG_STATE_HOME": str(self.state)})
        env.start()
        self.addCleanup(env.stop)
        self.port = free_port()
        self.bind = f"127.0.0.1:{self.port}"
        self.fleet = self.conf / "fleet.json"
        self.fleet.write_text(json.dumps(vectors.manifest().to_json()))

    def configure(self, multicast: bool = False) -> None:
        (self.conf / "stations.toml").write_text(
            f'version = 1\n[manifest]\npath = "fleet.json"\n[listen]\nbind = "{self.bind}"\n'
            f"multicast = {'true' if multicast else 'false'}\n")

    def doctor(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["doctor", "--no-probe", "--json", *argv])
        report = json.loads(out.getvalue())
        self.assertEqual(report["ok"], code == 0)
        return code, {c["name"]: c for c in report["checks"]}

    def test_passes_on_a_configured_host(self):
        self.configure()
        code, checks = self.doctor()
        self.assertEqual(code, 0, checks)
        self.assertEqual([c["status"] for c in checks.values()], ["ok"] * 5 + ["report"])
        self.assertEqual(checks["stations"]["path"], str(self.conf / "stations.toml"))
        self.assertEqual((checks["multicast"]["decided"], checks["multicast"]["configured"]), (False, False))

    def test_fails_without_stations_toml(self):
        code, checks = self.doctor()
        self.assertEqual(code, 1)
        self.assertEqual({k: c["status"] for k, c in checks.items()},
                         {"python": "ok", "cryptography": "ok", "stations": "fail", "manifest": "skip", "bind": "skip",
                          "multicast": "report"})
        self.assertIn("pass --manifest", checks["stations"]["detail"])

    def test_a_manifest_flag_needs_no_stations_toml(self):
        (self.conf / "stations.toml").write_text("not toml [")
        code, checks = self.doctor("--manifest", str(self.fleet), "--bind", self.bind)
        self.assertEqual(code, 0, checks)
        self.assertEqual(checks["stations"]["status"], "skip")

    def test_fails_on_a_bad_manifest(self):
        self.configure()
        data = vectors.manifest().to_json()
        data["stations"][1]["key_id"] = data["stations"][0]["key_id"]
        self.fleet.write_text(json.dumps(data))
        code, checks = self.doctor()
        self.assertEqual((code, checks["manifest"]["status"]), (1, "fail"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["doctor", "--no-probe"]), 1)
        self.assertRegex(out.getvalue(), r"\nfail +manifest .*: 1 problem\(s\)\n +- stations\[1\] \(test2\): key_id ")

    def test_fails_when_another_process_holds_the_address(self):
        self.configure()
        with hold(self.port, shared=True):
            code, checks = self.doctor()
        self.assertEqual((code, checks["bind"]["held_by"]), (1, "other"))

    def test_passes_when_this_listener_holds_the_address(self):
        self.configure()
        lease = take_lease(_default_state(str(self.fleet), self.bind) + ".lease")  # where `canticle listen` puts it
        try:
            with hold(self.port, shared=True):
                code, checks = self.doctor()
        finally:
            lease.close()
        self.assertEqual((code, checks["bind"]["status"], checks["bind"]["held_by"]), (0, "ok", "listener"))

    def test_a_listener_with_its_own_state_file(self):
        self.configure()
        state = str(self.dir / "elsewhere" / "listener.json")
        lease = take_lease(state + ".lease")
        try:
            with hold(self.port, shared=True):
                self.assertEqual(self.doctor()[0], 1)                       # not found where the default would be
                self.assertEqual(self.doctor("--state", state)[0], 0)        # found with the listener's --state
        finally:
            lease.close()

    def test_a_lease_probe_never_stops_a_listener_from_starting(self):
        # doctor's lease probe holds a shared lock for a moment. A listener starting then waits; it refuses only
        # when another listener really holds the lease.
        a = argparse.Namespace(ephemeral=False, state=None, manifest=str(self.fleet), bind=self.bind)
        path = _default_state(str(self.fleet), self.bind) + ".lease"
        os.makedirs(os.path.dirname(path))
        probe = open(path, "a")
        fcntl.flock(probe, fcntl.LOCK_SH)
        threading.Timer(0.1, probe.close).start()
        with contextlib.redirect_stderr(io.StringIO()):
            state, lease = _listener_state(a)
            self.assertEqual(state + ".lease", path)
            other = argparse.Namespace(ephemeral=False, state=state, manifest=str(self.fleet), bind=self.bind)
            with self.assertRaises(SystemExit):
                _listener_state(other)  # held for real: refused after the short wait
        lease.close()

    def test_multicast_is_never_decided_and_nothing_is_written(self):
        # §11.2: multicast may be used only after a doctor that runs every step passes. This one does not,
        # so even a probe that loops back must leave multicast off and write nothing.
        self.configure(multicast=False)
        before = snapshot(self.dir)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(doctor, "loopback_probe", lambda: (True, "looped back")):
            code = main(["doctor", "--probe", "--json"])  # forced: multicast is off, so it would be skipped
        m = {c["name"]: c for c in json.loads(out.getvalue())["checks"]}["multicast"]
        self.assertEqual((code, m["status"], m["loopback"], m["decided"], m["configured"]), (0, "report", True, False, False))
        self.assertEqual(snapshot(self.dir), before)  # no stations.toml change, no lease or state file

    def test_a_failed_probe_does_not_fail_the_doctor(self):
        self.configure(multicast=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(doctor, "loopback_probe", lambda: (False, "no route")):
            self.assertEqual(main(["doctor"]), 0)
        self.assertIn("report  multicast     loopback probe failed: no route; listener multicast on", out.getvalue())

    def spied(self, *argv):
        """Run doctor with every socket a spy: (exit code, multicast check, group joins attempted)."""
        SpySocket.calls = []
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(doctor.socket, "socket", SpySocket), \
                mock.patch.object(doctor.loopback_probe, "__defaults__", (doctor.runner.MCAST_GROUP, 0.1)):
            code = main(["doctor", "--json", *argv])
        m = {c["name"]: c for c in json.loads(out.getvalue())["checks"]}["multicast"]
        return code, m, joins(SpySocket.calls)

    def test_no_stations_toml_never_joins_the_group(self):
        # #75: a doctor in an empty HOME joined 239.255.13.13, sending an IGMP report the LAN can see.
        code, m, joined = self.spied()
        self.assertEqual((code, joined, m["status"], m["loopback"]), (1, 0, "report", None))
        self.assertIn("multicast not configured — probe skipped", m["detail"])

    def test_multicast_off_never_joins_the_group(self):
        self.configure(multicast=False)
        code, m, joined = self.spied()
        self.assertEqual((code, joined, m["status"], m["configured"]), (0, 0, "report", False))
        self.assertIn("multicast not configured — probe skipped", m["detail"])
        self.assertEqual(self.spied("--manifest", str(self.fleet), "--bind", self.bind)[::2], (0, 0))

    def test_multicast_on_runs_the_probe(self):
        self.configure(multicast=True)
        code, m, joined = self.spied()
        self.assertEqual((code, joined, m["status"], m["configured"]), (0, 1, "report", True))
        self.assertIsInstance(m["loopback"], bool)
        self.assertEqual(self.spied("--no-multicast")[::2], (0, 0))        # the flag wins over the file
        self.configure(multicast=False)
        self.assertEqual(self.spied("--multicast")[::2], (0, 1))

    def test_probe_and_no_probe_flags(self):
        code, m, joined = self.spied("--probe")                            # forced, even with no stations.toml
        self.assertEqual((code, joined, m["status"], m["configured"]), (1, 1, "report", None))
        self.configure(multicast=True)
        code, m, joined = self.spied("--no-probe")                         # never, even with multicast on
        self.assertEqual((code, joined, m["loopback"]), (0, 0, None))
        self.assertIn("loopback probe skipped (--no-probe)", m["detail"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["doctor", "--probe", "--no-probe"])

    def test_the_multicast_flag_counts_when_stations_toml_does_not_load(self):
        # --multicast configures multicast (README step 3), whether or not a stations.toml loads.
        code, m, joined = self.spied("--multicast")                        # no stations.toml
        self.assertEqual((code, joined, m["configured"]), (1, 1, True))
        (self.conf / "stations.toml").write_text("not toml [")
        code, m, joined = self.spied("--no-multicast")                     # malformed stations.toml
        self.assertEqual((code, joined, m["configured"]), (1, 0, False))
        self.assertIn("listener multicast off", m["detail"])


if __name__ == "__main__":
    unittest.main()
