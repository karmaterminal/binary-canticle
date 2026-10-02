"""The README's onboarding, end to end: keygen, stations.toml, doctor, then `canticle listen` with no flags
hearing a station over loopback UDP while doctor recognises it holding the address."""

import contextlib
import io
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from canticle import runner, wire
from canticle.__main__ import _load_key, main
from canticle.manifest import Manifest
from canticle.station import Station, StreamConfig

PACKAGE = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def lines(stream, q: queue.Queue) -> None:
    for line in stream:
        q.put(line)


def wait_for(q: queue.Queue, pred, timeout_s: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_s
    seen = []
    while (left := deadline - time.monotonic()) > 0:
        try:
            line = q.get(timeout=left)
        except queue.Empty:
            break
        seen.append(line)
        if pred(line):
            return line
    raise AssertionError(f"timed out; saw {seen!r}")


class OnboardingTest(unittest.TestCase):
    def test_keygen_stations_toml_doctor_listen(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        home, conf = root / "home", root / "home" / ".binary-canticle"
        conf.mkdir(parents=True)
        env = {"HOME": str(home), "XDG_STATE_HOME": str(root / "state")}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        port = free_port()

        def run(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = main(list(argv))
            return code, out.getvalue()

        code, out = run("keygen", "--out", str(conf / "cael.key"), "--manifest", str(conf / "fleet.json"),
                        "--name", "cael", "--classes", "chatter", "--streams", "chatter")
        self.assertEqual(code, 0)
        kid = json.loads(out)["key_id"]
        (conf / "stations.toml").write_text(f'version = 1\n\n[manifest]\npath = "fleet.json"\n\n'
                                            f'[listen]\nbind = "127.0.0.1:{port}"\n')
        code, out = run("doctor", "--no-probe", "--json")
        self.assertEqual(code, 0, out)

        proc = subprocess.Popen([sys.executable, "-m", "canticle", "listen"], cwd=root, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, **env, "PYTHONPATH": str(PACKAGE)})
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        out_q, err_q = queue.Queue(), queue.Queue()
        readers = [threading.Thread(target=lines, args=(stream, q), daemon=True)
                   for stream, q in ((proc.stdout, out_q), (proc.stderr, err_q))]
        for r in readers:
            r.start()
        started = json.loads(wait_for(err_q, lambda line: '"stations"' in line))
        self.assertEqual(started, {"stations": str(conf / "stations.toml"), "manifest": str(conf / "fleet.json"),
                                   "bind": f"127.0.0.1:{port}", "multicast": False})
        wait_for(err_q, lambda line: "listener_state" in line)

        def bind_check() -> dict:
            return next(c for c in json.loads(run("doctor", "--no-probe", "--json")[1])["checks"] if c["name"] == "bind")

        deadline = time.monotonic() + 10
        while not (check := bind_check())["held_by"] and time.monotonic() < deadline:
            time.sleep(0.05)  # the listener prints its state path just before it binds
        self.assertEqual((check["status"], check["held_by"]), ("ok", "listener"), check)

        sk = _load_key(conf / "cael.key")
        now = runner.now_ms()
        st = Station(sk, [StreamConfig("chatter")], epoch=1, now_ms=now,
                     grant=Manifest.load(conf / "fleet.json").entry(wire.key_id(wire.public_key_bytes(sk))))
        st.sing(now, "chatter", text="onboarded", ttl_s=30)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tx:
            for frame in st.poll(now):
                tx.sendto(frame, ("127.0.0.1", port))
        item = json.loads(wait_for(out_q, lambda line: '"item"' in line))
        self.assertEqual((item["key_id"], item["stream"], item["text"]), (kid, "chatter", "onboarded"))

        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(timeout=10), 0)
        for r in readers:
            r.join(timeout=5)
        proc.stdout.close()
        proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
