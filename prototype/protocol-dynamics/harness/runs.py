"""Run staging and provenance for the experiments that write one raw file per condition (E1, E4).

Each invocation writes into a fresh staging directory. Only when every worker
exited 0 and every expected output exists and agrees on its provenance are the
raw files moved into ``results/raw/`` and the aggregate written (atomically).
Otherwise nothing under ``results/`` changes and the caller exits nonzero.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Iterable, Optional

from . import stats

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")
CANTICLE = os.path.join(os.path.dirname(HERE), "canticle-station")


class RunFailed(Exception):
    """A worker failed, an output is missing, or outputs disagree on provenance."""


def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}-{os.urandom(2).hex()}"


def stage_dir(results: str, experiment: str, run_id: str) -> str:
    """A fresh directory on the same filesystem as ``results`` (so publishing is a rename)."""
    path = os.path.join(results, ".staging", f"{experiment}-{run_id}")
    os.makedirs(path)
    return path


def _git(*argv: str) -> Optional[str]:
    try:
        return subprocess.run(["git", "-C", HERE, *argv], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def source_digest(paths: Iterable[str]) -> str:
    """sha256 over the named files' paths and contents, so a dirty tree is still identifiable."""
    h = hashlib.sha256()
    for p in sorted(set(paths)):
        h.update(os.path.relpath(p, os.path.dirname(HERE)).encode() + b"\0")
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def manifest(experiment: str, run_id: str, conditions: list[str], config: dict, script: str) -> dict:
    """What produced an aggregate: code, time, host and the exact condition list."""
    sources = [script, *glob.glob(os.path.join(HERE, "harness", "*.py")),
               *glob.glob(os.path.join(CANTICLE, "canticle", "*.py"))]
    dirty = _git("status", "--porcelain", "--", HERE, CANTICLE)
    return {"experiment": experiment, "run_id": run_id, "argv": sys.argv,
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": None if dirty is None else bool(dirty),
            "source_sha256": source_digest(sources), "config": config, "conditions": conditions,
            "env": stats.env()}


def check_consistent(docs: dict[str, dict], keys: Iterable[str], expect: Optional[dict] = None) -> None:
    """Every doc must carry ``keys`` with one common value (and ``expect``'s value where given)."""
    for k in keys:
        vals = {name: d.get(k) for name, d in docs.items()}
        if any(v is None for v in vals.values()):
            raise RunFailed(f"{k} missing in {sorted(n for n, v in vals.items() if v is None)}")
        distinct = {json.dumps(v, sort_keys=True) for v in vals.values()}
        if len(distinct) > 1:
            raise RunFailed(f"mixed {k} across raw files: {vals}")
        if expect and k in expect and next(iter(vals.values())) != expect[k]:
            raise RunFailed(f"{k} is {next(iter(vals.values()))!r}, expected {expect[k]!r}")


def wait_all(procs: list[tuple[str, str, "subprocess.Popen"]]) -> None:
    """Wait for (tag, output path, process) workers; raise unless all exited 0 and wrote their output."""
    codes = {tag: p.wait() for tag, _, p in procs}
    failed = {tag: c for tag, c in codes.items() if c != 0}
    missing = [tag for tag, out, _ in procs if codes[tag] == 0 and not os.path.exists(out)]
    if failed or missing:
        raise RunFailed(f"failed workers (exit codes) {failed}; missing outputs {missing}")


def publish(stage: str, raw: str, aggregate_path: str, aggregate: dict) -> list[str]:
    """Move the staged raw files into ``raw`` and write the aggregate atomically; remove the stage."""
    os.makedirs(raw, exist_ok=True)
    moved = []
    for name in sorted(os.listdir(stage)):
        os.replace(os.path.join(stage, name), os.path.join(raw, name))
        moved.append(name)
    tmp = aggregate_path + f".tmp-{os.getpid()}"
    stats.write_json(tmp, aggregate)
    os.replace(tmp, aggregate_path)
    os.rmdir(stage)
    try:
        os.rmdir(os.path.dirname(stage))         # .staging/, if no other run is using it
    except OSError:
        pass
    return moved
