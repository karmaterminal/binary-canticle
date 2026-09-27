"""Regression tests for the harness that need no root and no network namespaces.

    cd prototype/protocol-dynamics
    PYTHONPATH=../canticle-station python -m unittest discover -s tests -v

Provenance tests build a throwaway git repository (git must be installed) and
point the runners at it, so they do not depend on the state of this checkout.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import hashlib
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "canticle-station"))

import e1_freshness as e1  # noqa: E402
import e2_fanout as e2  # noqa: E402
import e4_late_joiner as e4  # noqa: E402
from harness import netns, runs, stats  # noqa: E402

# A stand-in for one condition's worker: reads the runner's argv, writes a minimal raw file.
FAKE_WORKER = r"""
import json, sys
argv = sys.argv[1:]
kv = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
exp, code, dur = sys.argv[1], int(sys.argv[2]), sys.argv[3]
if dur == "nofile":         # exits 0 but writes nothing
    sys.exit(0)
if code == 0:
    doc = {"run_id": kv["--run-id"], "tag": kv["--tag"], "duration_s": float(dur if dur != "-" else kv["--duration"])}
    if exp == "e1":
        doc.update(update_s=float(kv["--update-s"]), loss_permille=int(kv.get("--loss", 0)), loss_direction="both",
                   outage_s=0, receivers=int(kv["--receivers"]), warmup_s=5, drain_s=20, body_bytes=200,
                   nft={"measured_loss": 0.0}, arms={"udp-live": {"samples": 1}})
    else:
        doc.update(loss_permille=int(kv["--loss"]), items=20, slots_per_arm=10, trial_timeout_s=120,
                   granted_bps=32000, arms={})
    with open(kv["--out"], "w") as f:
        json.dump(doc, f)
sys.exit(code)
"""


def fake_spawn(exp: str, exit_code: int = 0, duration: str = "-", calls: list = None):
    """Replace ``_spawn``: run FAKE_WORKER with the runner's argv instead of the real condition."""
    def spawn(ns, argv, log_path):
        if calls is not None:
            calls.append(argv)
        with open(log_path, "w") as log:
            return subprocess.Popen([sys.executable, "-c", FAKE_WORKER, exp, str(exit_code), duration, *argv[2:]],
                                    stdout=log, stderr=subprocess.STDOUT)
    return spawn


@contextlib.contextmanager
def no_netns(name):
    yield name


def digest_tree(path: str) -> dict:
    out = {}
    for root, _, files in os.walk(path):
        if ".staging" in root:
            continue
        for f in files:
            with open(os.path.join(root, f), "rb") as fh:
                out[os.path.relpath(os.path.join(root, f), path)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def git(top: str, *argv: str) -> str:
    return subprocess.run(["git", "-C", top, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", *argv], check=True, capture_output=True, text=True).stdout


class Repo:
    """A throwaway git repository shaped like this one: an experiment script, harness/, canticle/."""

    PATTERNS = ("prototype/protocol-dynamics/exp.py", "prototype/protocol-dynamics/harness/*.py",
                "prototype/canticle-station/canticle/*.py")
    FILES = {"prototype/protocol-dynamics/exp.py": "print('experiment')\n",
             "prototype/protocol-dynamics/harness/a.py": "A = 1\n",
             "prototype/protocol-dynamics/harness/b.py": "B = 2\n",
             "prototype/protocol-dynamics/harness/notes.txt": "not a source file\n",
             "prototype/canticle-station/canticle/c.py": "C = 3\n"}

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pd-repo-")
        self.top = os.path.realpath(self.tmp.name)
        git(self.top, "init", "-q")
        for p, text in self.FILES.items():
            self.write(p, text)
        self.commit("init")
        self.sources = runs.Sources(self.top, self.PATTERNS)

    def write(self, rel: str, text: str) -> None:
        os.makedirs(os.path.dirname(os.path.join(self.top, rel)), exist_ok=True)
        with open(os.path.join(self.top, rel), "w") as f:
            f.write(text)

    def commit(self, msg: str) -> str:
        git(self.top, "add", "-A")
        git(self.top, "commit", "-q", "-m", msg)
        return git(self.top, "rev-parse", "HEAD").strip()

    def use(self):
        """Point every Run at this repository's sources."""
        return mock.patch.object(runs, "default_sources", lambda script, extra=(): self.sources)

    def cleanup(self):
        self.tmp.cleanup()


def publish_generation(results: str, unit: str = "e1", raw: int = 2, **kw) -> str:
    """A complete generation of ``unit`` with ``raw`` raw files; returns its run id."""
    run = runs.Run(unit, "test", "exp.py", {"k": 1}, results_dir=results, **kw)
    for i in range(raw):
        stats.write_json(run.raw(f"r{i}.json"), {"run_id": run.id, "i": i})
    run.publish("agg.json", {"rows": [run.id]})
    return run.id


class KaplanMeier(unittest.TestCase):
    def test_selfcheck(self):
        stats.km_selfcheck()

    def test_all_censored_has_no_quantiles(self):
        r = stats.km([10, 20, 30], [False, False, False])
        self.assertEqual((r["median"], r["p99"], r["censored_beyond_ms"], r["max_event"]), (None, None, 30, None))


class E1Analysis(unittest.TestCase):
    def test_undelivered_updates_are_censored_not_latencies(self):
        issue = {k: float(k) for k in range(1, 11)}                  # update k issued at t = k s
        fast = [(k + 0.1, k) for k in range(1, 11)]                  # every update after 100 ms
        stuck = [(1.2, 1), (2.2, 2)]                                 # nothing after update 2
        r = e1.analyze(issue, [fast, stuck], w0=1.0, w1=10.0, t_end=30.0, outages=[])
        self.assertEqual((r["samples"], r["delivered"], r["censored"]), (20, 12, 8))
        self.assertAlmostEqual(r["delivered_fraction"], 0.6)
        km = r["update_latency_km_ms"]
        self.assertEqual((km["events"], km["censored"]), (12, 8))
        self.assertEqual(km["median"], 100.0)                        # 10 of 20 at 100 ms: S = 0.5
        self.assertIsNone(km["p90"])                                 # 40% never delivered
        self.assertEqual(km["censored_beyond_ms"], 27000.0)          # t_end - t_issue of update 3
        self.assertEqual(r["delivered_latency_ms"]["max"], 200.0)    # observed only
        self.assertNotIn("update_latency_ms", r)

    def test_outage_recovery_censored(self):
        issue = {k: float(k) for k in range(1, 11)}
        ok = [(k + 0.1, k) for k in range(1, 11)]
        stuck = [(1.1, 1), (2.1, 2), (3.1, 3)]
        r = e1.analyze(issue, [ok, stuck], w0=1.0, w1=10.0, t_end=30.0, outages=[(4.5, 5.5)])
        self.assertEqual(r["outage_recovery_censored"], 1)
        self.assertEqual(r["outage_recovery_km_ms"]["censored"], 1)
        self.assertEqual(r["updates_issued_in_outage_censored"], 1)
        self.assertNotIn("outage_recovery_ms", r)


class E1Runner(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.tmp = tempfile.TemporaryDirectory()
        self.res = self.tmp.name
        self.gen = os.path.join(self.res, "e1")
        os.makedirs(os.path.join(self.gen, "raw"))
        # an older run's files: one of the conditions we rerun, one we do not
        for tag in ("u2-loss50", "u10-loss0"):
            with open(os.path.join(self.gen, "raw", f"e1-{tag}.json"), "w") as f:
                json.dump({"run_id": "old", "tag": tag, "duration_s": 900}, f)
        with open(os.path.join(self.gen, "e1_freshness.json"), "w") as f:
            f.write('{"experiment": "e1_freshness", "rows": ["old aggregate"]}\n')
        self.args = types.SimpleNamespace(duration=30.0, receivers=2, update_values=[2.0], allow_dirty=False,
                                          only=["u2-loss0", "u2-loss50"], results_dir=self.res)
        self.patches = [mock.patch.object(e1.netns, "netns", no_netns), self.repo.use()]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()
        self.repo.cleanup()

    def test_failed_worker_fails_and_publishes_nothing(self):
        before = digest_tree(self.res)
        with mock.patch.object(e1, "_spawn", fake_spawn("e1", exit_code=9)):
            self.assertEqual(e1.run_all(self.args), 1)
        self.assertEqual(digest_tree(self.res), before)

    def test_missing_output_fails(self):
        before = digest_tree(self.res)
        with mock.patch.object(e1, "_spawn", fake_spawn("e1", exit_code=0, duration="nofile")):
            self.assertEqual(e1.run_all(self.args), 1)
        self.assertEqual(digest_tree(self.res), before)

    def test_mismatched_duration_is_refused(self):
        before = digest_tree(self.res)
        with mock.patch.object(e1, "_spawn", fake_spawn("e1", exit_code=0, duration="900")):
            self.assertEqual(e1.run_all(self.args), 1)
        self.assertEqual(digest_tree(self.res), before)

    def test_dirty_tree_is_refused_before_any_worker(self):
        self.repo.write("prototype/protocol-dynamics/harness/a.py", "A = 2\n")
        before, calls = digest_tree(self.res), []
        with mock.patch.object(e1, "_spawn", fake_spawn("e1", calls=calls)):
            self.assertEqual(e1.run_all(self.args), 1)
        self.assertEqual((digest_tree(self.res), calls), (before, []))

    def test_collate_refuses_mixed_duration(self):
        a = os.path.join(self.res, "a.json")
        b = os.path.join(self.res, "b.json")
        base = {"run_id": "r", "receivers": 20, "warmup_s": 5, "drain_s": 20, "body_bytes": 200, "arms": {}}
        for path, tag, dur in ((a, "x", 900), (b, "y", 120)):
            with open(path, "w") as f:
                json.dump({**base, "tag": tag, "duration_s": dur}, f)
        with self.assertRaisesRegex(runs.RunFailed, "mixed duration_s"):
            e1.collate([a, b])

    def test_success_publishes_only_this_run(self):
        with mock.patch.object(e1, "_spawn", fake_spawn("e1")):
            self.assertEqual(e1.run_all(self.args), 0)
        m = runs.check_generation(self.gen)
        with open(os.path.join(self.gen, "e1_freshness.json")) as f:
            agg = json.load(f)
        self.assertEqual(agg["run_id"], m["run_id"])
        self.assertEqual(m["conditions"], ["u2-loss0", "u2-loss50"])
        self.assertEqual(sorted(r["tag"] for r in agg["rows"]), ["u2-loss0", "u2-loss50"])
        self.assertTrue(all(r["run_id"] == m["run_id"] and r["duration_s"] == 30.0 and r["receivers"] == 2
                            for r in agg["rows"]))
        for key in ("run_id", "argv", "started", "finished", "git_commit", "git_dirty", "source_sha256", "source",
                    "config", "env", "outputs"):
            self.assertIn(key, m)
        self.assertFalse(m["git_dirty"])
        # the whole directory is the new generation: the old run's u10-loss0 file is gone, not mixed in
        self.assertEqual(sorted(os.listdir(os.path.join(self.gen, "raw"))),
                         ["e1-u2-loss0.json", "e1-u2-loss0.log", "e1-u2-loss50.json", "e1-u2-loss50.log"])
        self.assertEqual(os.listdir(os.path.join(self.res, ".staging")), [])                  # stage removed

    def test_only_refuses_default_results(self):
        self.args.results_dir = runs.RESULTS
        with self.assertRaises(SystemExit):
            e1.run_all(self.args)


class E4Runner(unittest.TestCase):
    def test_failed_worker_fails_and_publishes_nothing(self):
        repo = Repo()
        with tempfile.TemporaryDirectory() as res, repo.use():
            os.makedirs(os.path.join(res, "e4", "raw"))
            with open(os.path.join(res, "e4", "raw", "e4-loss50.json"), "w") as f:
                f.write('{"old": true}\n')
            with open(os.path.join(res, "e4", "e4_late_joiner.json"), "w") as f:
                f.write('{"old": true}\n')
            before = digest_tree(res)
            a = types.SimpleNamespace(duration=30.0, losses=[0, 50], results_dir=res, allow_dirty=False)
            with mock.patch.object(e4.netns, "netns", no_netns), \
                    mock.patch.object(e4, "_spawn", fake_spawn("e4", exit_code=9)):
                self.assertEqual(e4.run_all(a), 1)
            self.assertEqual(digest_tree(res), before)
            with mock.patch.object(e4.netns, "netns", no_netns), mock.patch.object(e4, "_spawn", fake_spawn("e4")):
                self.assertEqual(e4.run_all(a), 0)
            m = runs.check_generation(os.path.join(res, "e4"))
            with open(os.path.join(res, "e4", "e4_late_joiner.json")) as f:
                agg = json.load(f)
            self.assertEqual([c["loss_permille"] for c in agg["conditions"]], [0, 50])
            self.assertEqual({c["run_id"] for c in agg["conditions"]}, {agg["run_id"]}, {m["run_id"]})
        repo.cleanup()


class Provenance(unittest.TestCase):
    """Launch refuses a dirty tree; --allow-dirty embeds a diff that rebuilds it; sources must not change."""

    def setUp(self):
        self.repo = Repo()
        self.tmp = tempfile.TemporaryDirectory()
        self.res = self.tmp.name
        self.use = self.repo.use()
        self.use.start()

    def tearDown(self):
        self.use.stop()
        self.tmp.cleanup()
        self.repo.cleanup()

    def test_clean_digest_is_sha256sum_of_sha256sum(self):
        gen = os.path.join(self.res, "e1")
        publish_generation(self.res)
        m = runs.check_generation(gen)
        files = sorted(m["source"]["files"])
        self.assertEqual(files, sorted(p for p in Repo.FILES if p.endswith(".py")))     # notes.txt is not a source
        listing = subprocess.run(["sha256sum", *files], cwd=self.repo.top, capture_output=True, check=True).stdout
        self.assertEqual(m["source_sha256"], hashlib.sha256(listing).hexdigest())
        self.assertEqual((m["git_dirty"], m["source"]["patch"]), (False, None))

    def test_dirty_tree_is_refused(self):
        for change in (lambda: self.repo.write("prototype/protocol-dynamics/harness/a.py", "A = 9\n"),
                       lambda: self.repo.write("prototype/canticle-station/canticle/new.py", "N = 1\n"),
                       lambda: os.unlink(os.path.join(self.repo.top, "prototype/protocol-dynamics/harness/b.py"))):
            git(self.repo.top, "checkout", "-q", "--", ".")
            git(self.repo.top, "clean", "-qfd")
            change()
            with self.assertRaises(runs.Dirty):
                runs.Run("e1", "test", "exp.py", {}, results_dir=self.res)
            self.assertFalse(os.path.exists(os.path.join(self.res, "e1")))

    def test_edit_outside_sources_is_not_dirty(self):
        self.repo.write("prototype/protocol-dynamics/harness/notes.txt", "edited\n")
        self.repo.write("prototype/protocol-dynamics/README.md", "new\n")
        runs.Run("e1", "test", "exp.py", {}, results_dir=self.res)

    def test_allow_dirty_embeds_a_patch_that_rebuilds_the_tree(self):
        base = git(self.repo.top, "rev-parse", "HEAD").strip()
        self.repo.write("prototype/protocol-dynamics/harness/a.py", "A = 9")                  # no final newline
        self.repo.write("prototype/canticle-station/canticle/new.py", "N = 1\n")              # untracked
        os.unlink(os.path.join(self.repo.top, "prototype/protocol-dynamics/harness/b.py"))    # deleted
        publish_generation(self.res, allow_dirty=True)
        gen = os.path.join(self.res, "e1")
        m = runs.check_generation(gen)
        patch = m["source"]["patch"]
        self.assertTrue(m["git_dirty"] and m["allow_dirty"])
        self.assertEqual(m["source"]["dirty_files"], ["prototype/canticle-station/canticle/new.py",
                                                      "prototype/protocol-dynamics/harness/a.py",
                                                      "prototype/protocol-dynamics/harness/b.py"])
        self.assertEqual(patch["base"], base)
        self.assertEqual(patch["sha256"], hashlib.sha256(patch["unified_diff"].encode()).hexdigest())
        rebuilt = runs.file_digests(runs.reconstruct(self.repo.sources, base, patch["unified_diff"]))
        self.assertEqual(rebuilt, m["source"]["files"])
        self.assertEqual(runs.digest(rebuilt), m["source_sha256"])
        v = runs.verify(gen, base, top=self.repo.top)
        self.assertEqual((v["match"], v["patch_sha256_ok"], v["match_with_patch"]), (False, True, True))
        self.assertEqual(v["differ"], m["source"]["dirty_files"])

    def test_source_change_during_run_refuses_publication(self):
        old = publish_generation(self.res)
        gen = os.path.join(self.res, "e1")
        before = digest_tree(gen)
        run = runs.Run("e1", "test", "exp.py", {}, results_dir=self.res)
        stats.write_json(run.raw("r0.json"), {"run_id": run.id})
        self.repo.write("prototype/canticle-station/canticle/c.py", "C = 4\n")               # edited mid-run
        with self.assertRaisesRegex(runs.RunFailed, "changed during the run.*canticle/c.py"):
            run.publish("agg.json", {"rows": []})
        self.assertEqual(digest_tree(gen), before)
        self.assertEqual(runs.check_generation(gen)["run_id"], old)
        self.assertTrue(os.path.isdir(run.stage))                                            # kept to inspect

    def test_verify_against_commits(self):
        publish_generation(self.res)
        gen = os.path.join(self.res, "e1")
        first = git(self.repo.top, "rev-parse", "HEAD").strip()
        self.assertTrue(runs.verify(gen, top=self.repo.top)["match"])                         # its own commit
        self.repo.write("prototype/protocol-dynamics/harness/a.py", "A = 5\n")
        self.repo.write("prototype/protocol-dynamics/README.md", "docs\n")
        later = self.repo.commit("change a source")
        v = runs.verify(gen, later, top=self.repo.top)
        self.assertEqual((v["match"], v["differ"]), (False, ["prototype/protocol-dynamics/harness/a.py"]))
        self.assertTrue(runs.verify(gen, first, top=self.repo.top)["match"])

    def test_verify_detects_a_tampered_generation(self):
        publish_generation(self.res)
        with open(os.path.join(self.res, "e1", "raw", "r1.json"), "w") as f:
            f.write('{"run_id": "someone else"}\n')
        with self.assertRaisesRegex(runs.RunFailed, "raw/r1.json"):
            runs.verify(os.path.join(self.res, "e1"), top=self.repo.top)


class SimulatedCrash(BaseException):
    """Stands for the process dying: nothing after it runs, no exception handler sees it."""


class CrashDuringPublish(unittest.TestCase):
    """Kill publication at every filesystem step: results/e1 is always one whole generation, old or new."""

    def setUp(self):
        self.repo = Repo()
        self.use = self.repo.use()
        self.use.start()

    def tearDown(self):
        self.use.stop()
        self.repo.cleanup()

    def crash_at(self, k: int, exchange: bool) -> tuple[str, str, str, dict, bool]:
        """Publish an old generation, then a new one that dies at filesystem step ``k``; recover as a new run would."""
        res = tempfile.mkdtemp(prefix="pd-crash-")
        self.addCleanup(shutil.rmtree, res)
        gen = os.path.join(res, "e1")
        old = publish_generation(res, raw=3)
        old_tree = digest_tree(gen)
        run = runs.Run("e1", "test", "exp.py", {}, results_dir=res)
        for i in range(2):                                     # a different set of raw files than the old run
            stats.write_json(run.raw(f"n{i}.json"), {"run_id": run.id})
        steps = [0]

        def step(fn):
            def wrapped(*a, **kw):
                steps[0] += 1
                if steps[0] == k:
                    raise SimulatedCrash
                return fn(*a, **kw)
            return wrapped

        def no_exchange(src, dst, flags):
            raise OSError(errno.EINVAL, "RENAME_EXCHANGE not supported here")

        crashed = False
        with mock.patch.object(runs.os, "rename", step(os.rename)), mock.patch.object(runs.os, "fsync", step(os.fsync)), \
                mock.patch.object(runs.shutil, "rmtree", step(shutil.rmtree)), \
                mock.patch.object(runs.stats, "write_json", step(stats.write_json)), \
                mock.patch.object(runs, "_renameat2", step(runs._renameat2 if exchange else no_exchange)):
            try:
                run.publish("agg.json", {"rows": [run.id]})
            except SimulatedCrash:
                crashed = True
        runs.recover(res, "e1")                                 # what the next Run does first
        m = runs.check_generation(gen)                          # a whole generation, whichever it is
        return old, run.id, m["run_id"], {"old": old_tree == digest_tree(gen)}, crashed

    def check_every_step(self, exchange: bool) -> None:
        seen = []
        for k in range(1, 100):
            old, new, now, same, crashed = self.crash_at(k, exchange)
            self.assertIn(now, (old, new), k)
            if now == old:
                self.assertTrue(same["old"], f"step {k}: old generation not byte-identical")
            seen.append(now == new)
            if not crashed:
                break
        self.assertTrue(seen[-1], "publication without a crash must publish the new generation")
        self.assertIn(False, seen)                              # some crashes kept the old one ...
        self.assertEqual(seen, sorted(seen))                    # ... and once new, always new
        self.assertGreater(len(seen), 5)

    def test_every_step_with_rename_exchange(self):
        self.check_every_step(exchange=True)

    def test_every_step_without_rename_exchange(self):
        self.check_every_step(exchange=False)


class E2Cost(unittest.TestCase):
    """Per-listener cost from matched idle controls is never negative: it is reported only when resolved."""

    @staticmethod
    def doc(loaded: dict, idle: dict, rate: float = 10, window: float = 20) -> dict:
        rows = [{"mode": m, "n": n, "repeat": r, "rate": rate, "measure_s": window, "sender_host_cpu0_busy_s_per_s": v}
                for (m, n), vs in loaded.items() for r, v in enumerate(vs)]
        rows += [{"mode": "idle", "n": n, "repeat": r, "rate": rate, "measure_s": window,
                  "sender_host_cpu0_busy_s_per_s": v} for n, vs in idle.items() for r, v in enumerate(vs)]
        return {"rows": rows}

    def test_below_idle_is_not_resolved(self):
        c = {(x["mode"], x["n"]): x for x in e2.cost(self.doc(
            {("udp", 100): [0.0040, 0.0075, 0.0060], ("tcp", 5000): [0.605, 0.611, 0.608]},
            {100: [0.0085, 0.0070, 0.0090], 5000: [0.0080, 0.0095, 0.0085]}))}
        low, high = c[("udp", 100)], c[("tcp", 5000)]
        self.assertFalse(low["resolved"])
        self.assertIsNone(low["us_per_listener_frame"])
        self.assertGreater(low["resolution_us"], 0)
        self.assertTrue(high["resolved"])
        self.assertAlmostEqual(high["us_per_listener_frame"]["mean"], 11.99, places=2)
        self.assertGreater(high["us_per_listener_frame"]["ci95"][0], 0)
        self.assertTrue(high["idle_matched"])

    def test_never_negative_on_noise(self):
        rng = random.Random(7)
        for _ in range(300):
            n = rng.choice([10, 100, 1000, 5000])
            true = rng.choice([0.0, 0.5e-6, 4e-6, 12e-6]) * n * 10          # CPU s/s the listeners really cost
            reps = rng.randint(1, 5)
            idle = [max(0.0, rng.gauss(0.009, 0.003)) for _ in range(reps)]
            loaded = [max(0.0, i + true + rng.gauss(0, 0.004)) for i in idle]
            for c in e2.cost(self.doc({("tcp", n): loaded}, {n: idle})):
                if c["resolved"]:
                    self.assertGreater(c["us_per_listener_frame"]["mean"], 0)
                    self.assertGreater(c["us_per_listener_frame"]["ci95"][0], 0)
                else:
                    self.assertIsNone(c["us_per_listener_frame"])
                    self.assertTrue(c["resolution_us"] is None or c["resolution_us"] >= 0)

    def test_identical_tick_quantised_repeats_are_not_resolved(self):
        # two repeats that each differ from idle by one 1/100 s accounting tick in a 4 s window: zero spread,
        # but one tick is quantisation, not a measured cost (and minus one tick is not a negative one)
        tick = 0.01 / 4
        for sign in (1, -1):
            (c,) = e2.cost(self.doc({("udp", 10): [0.005 + sign * tick] * 2}, {10: [0.005] * 2}, window=4))
            self.assertFalse(c["resolved"])
            self.assertEqual(c["resolution_us"], c["accounting_quantum_us"])
            self.assertEqual(c["accounting_quantum_us"], 50.0)          # 2 ticks / 4 s / (10 × 10) = 50 µs

    def test_one_repeat_is_not_resolved(self):
        (c,) = e2.cost(self.doc({("tcp", 5000): [0.6]}, {5000: [0.01]}))
        self.assertEqual((c["resolved"], c["resolution_us"]), (False, None))

    def test_legacy_run_uses_its_one_idle_sample_and_says_so(self):
        d = self.doc({("udp", 100): [0.0045, 0.0060, 0.0075]}, {})
        d["idle_baseline"] = {"cpu0": 0.0085}
        (c,) = e2.cost(d)
        self.assertEqual((c["idle_matched"], c["resolved"], c["us_per_listener_frame"]), (False, False, None))


class E4RelayLeases(unittest.TestCase):
    """Leases are keyed by session (address + client nonce), not by address."""

    def test_new_session_from_same_socket_gets_snapshot(self):
        asyncio.run(self._run())

    async def _run(self):
        from canticle.manifest import Manifest
        from canticle.station import StreamConfig
        from harness.arms import frame_for, make_station

        station, entry = make_station("slow", [StreamConfig("lens.state", cls="live-state")])
        relay = e4.Relay(Manifest([entry]))
        relay.frames = {1: b"snap-1", 2: b"snap-2"}
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.bind(("127.0.0.1", 0))
        c.setblocking(False)
        loop = asyncio.get_running_loop()
        dst = ("127.0.0.1", relay.port)

        async def drain(wait=0.15):
            await asyncio.sleep(wait)
            got = []
            while True:
                try:
                    got.append(c.recv(2048))
                except BlockingIOError:
                    return got

        async def session(nonce):
            c.sendto(e4.lease_msg(e4.HELLO, nonce, pad_to=256), dst)
            cookie = [m for m in await drain() if m[3] == e4.COOKIE][0][20:36]
            c.sendto(e4.lease_msg(e4.LISTEN, nonce, cookie, bytes(28)), dst)
            return cookie, await drain()

        n1, n2 = os.urandom(16), os.urandom(16)
        cookie1, got = await session(n1)
        self.assertEqual((relay.snapshots, got.count(b"snap-1")), (1, 1))
        c.sendto(e4.lease_msg(e4.LISTEN, n1, cookie1, bytes(28)), dst)         # LISTEN retransmit: same lease
        await drain()
        self.assertEqual(relay.snapshots, 1)
        _, got = await session(n2)                                             # BYE for n1 was "lost"
        self.assertEqual((relay.snapshots, got.count(b"snap-1")), (2, 1))
        self.assertEqual(len(relay.leases), 2)
        frame = frame_for(station, "lens.state", 1, 50, state_key="k00", loop="fast")
        ing = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ing.sendto(frame, ("127.0.0.1", relay.port_ingress))
        self.assertEqual((await drain()).count(frame), 1)                      # once per address
        c.sendto(e4.lease_msg(e4.BYE, n1, bytes(16)), dst)                     # wrong cookie: ignored
        await drain(0.05)
        self.assertEqual(len(relay.leases), 2)
        c.sendto(e4.lease_msg(e4.BYE, n1, cookie1), dst)
        await drain(0.05)
        self.assertEqual(len(relay.leases), 1)
        for s in (c, ing, relay.sock, relay.ingress):
            loop.remove_reader(s) if s in (relay.sock, relay.ingress) else None
            s.close()


class Namespaces(unittest.TestCase):
    def test_only_own_namespaces_are_deleted(self):
        calls = []
        with tempfile.NamedTemporaryFile("r") as track, \
                mock.patch.object(netns, "run", lambda *a, **k: calls.append(a) or ""), \
                mock.patch.object(netns, "TRACK", track.name):
            netns.delete(netns.PREFIX + "someone-else")
            self.assertEqual(calls, [])
            netns.add(netns.name("mine"))
            netns.delete(netns.name("mine"))
            self.assertEqual(calls, [("ip", "netns", "add", netns.PREFIX + "mine"),
                                     ("ip", "netns", "del", netns.PREFIX + "mine")])
            self.assertEqual(track.read().split(), [netns.PREFIX + "mine"])

    def test_prefix_is_per_run(self):
        self.assertTrue(netns.PREFIX.startswith("pd") and netns.PREFIX != "pd-")


if __name__ == "__main__":
    unittest.main()
