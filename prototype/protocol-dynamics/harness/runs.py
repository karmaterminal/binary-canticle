"""Staged, all-or-nothing publication of every experiment's results, with a run manifest.

Layout. Each publication unit (``e1``, ``e2``, ``e3-slow``, ``e3-dead``, ``e4``,
``e5``) owns one directory, ``results/<unit>/``, which holds exactly one
generation::

    results/<unit>/manifest.json     run id, argv, start/finish, git commit, git_dirty, source digest (+ patch)
    results/<unit>/<aggregate>.json  what summarize.py reads; carries the same run_id
    results/<unit>/raw/              per-condition raw files; worker logs (*.log, not in git)

Launch. ``Run()`` snapshots the files the run depends on (the experiment
script, ``harness/*.py``, ``../canticle-station/canticle/*.py``, and for E2
``fanout/*.go`` and ``go.mod``) and compares them with HEAD. If any differ
(modified, added or deleted), the run is refused (``Dirty``) unless
``allow_dirty``; then the manifest embeds the unified diff against HEAD,
content-addressed by its sha256, and the diff is checked to rebuild the working
tree's files exactly from HEAD.

Publication. Workers write into ``results/.staging/<unit>@<run id>/``.
``Run.publish()`` writes the aggregate and the manifest there, fsyncs them,
recomputes the source digest (and refuses if any source file changed since
launch), and swaps the staged directory with ``results/<unit>`` in one
``renameat2(RENAME_EXCHANGE)``. A crash at any point leaves either the whole old
generation or the whole new one in ``results/<unit>``, never a mix. On a
filesystem without RENAME_EXCHANGE the old directory is renamed aside first,
and ``recover()`` (run at every launch and publish) puts it back if the process
died before the new one was in place.

Source digest: sha256 over the lines ``<sha256(file)>  <path>\\n``, one per
source file, path relative to the repository root, sorted bytewise. From the
repository root that is ``sha256sum $(paths | LC_ALL=C sort) | sha256sum``.
``verify()`` recomputes it from ``git show <commit>:<path>``.
"""

from __future__ import annotations

import ctypes
import errno
import fnmatch
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from . import stats

HERE = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(HERE, "results")
CANTICLE = os.path.join(os.path.dirname(HERE), "canticle-station")
STAGING = ".staging"
MANIFEST = "manifest.json"
DIGEST_METHOD = ("sha256 over the lines '<sha256(file)>  <path>\\n', one per source file, path relative to the "
                 "repository root, sorted bytewise (= sha256sum $(paths | LC_ALL=C sort) | sha256sum)")


class RunFailed(Exception):
    """A worker failed, an output is missing, outputs disagree, or provenance does not hold."""


class Dirty(RunFailed):
    """Source files differ from HEAD and ``allow_dirty`` was not given."""


def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}-{os.urandom(2).hex()}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(top: str, *argv: str, check: bool = True, binary: bool = False, env: Optional[dict] = None):
    try:
        p = subprocess.run(["git", "-C", top, *argv], capture_output=True, check=check, text=not binary, env=env)
    except OSError as e:
        raise RunFailed(f"git is needed for provenance: {e}") from e
    except subprocess.CalledProcessError as e:
        raise RunFailed(f"git {' '.join(argv[:3])}: {(e.stderr or '').strip() if not binary else e.stderr}") from e
    return p.stdout


# ---------------------------------------------------------------- sources and digests

@dataclass(frozen=True)
class Sources:
    """The files a run depends on: glob patterns relative to the git work tree ``top``.

    Only the last path component of a pattern may contain wildcards; ``*`` does
    not cross ``/`` and names starting with ``.`` never match.
    """
    top: str
    patterns: tuple[str, ...]

    def match(self, path: str) -> bool:
        d, name = os.path.dirname(path), os.path.basename(path)
        return not name.startswith(".") and any(
            d == os.path.dirname(p) and fnmatch.fnmatchcase(name, os.path.basename(p)) for p in self.patterns)

    def worktree(self) -> dict[str, bytes]:
        """The matching regular files as they are on disk now."""
        out = {}
        for d in sorted({os.path.dirname(p) for p in self.patterns}):
            full = os.path.join(self.top, d)
            if not os.path.isdir(full):
                continue
            for name in os.listdir(full):
                rel = f"{d}/{name}" if d else name
                if self.match(rel) and os.path.isfile(os.path.join(full, name)):
                    with open(os.path.join(full, name), "rb") as f:
                        out[rel] = f.read()
        return out

    def at(self, commit: str) -> dict[str, bytes]:
        """The matching files as ``commit`` has them (``git show <commit>:<path>``)."""
        dirs = sorted({os.path.dirname(p) for p in self.patterns})
        listing = _git(self.top, "ls-tree", "-r", "-z", "--full-tree", commit, "--", *dirs)
        out = {}
        for entry in listing.split("\0"):
            if not entry:
                continue
            meta, path = entry.split("\t", 1)
            if meta.split()[1] == "blob" and self.match(path):
                out[path] = _git(self.top, "show", f"{commit}:{path}", binary=True)
        return out


def repo_top() -> str:
    return os.path.realpath(_git(HERE, "rev-parse", "--show-toplevel").strip())


def default_sources(script: str, extra: Iterable[str] = ()) -> Sources:
    """The experiment ``script``, harness/*.py, ../canticle-station/canticle/*.py and ``extra`` (under HERE)."""
    top = repo_top()

    def rel(p: str) -> str:
        return os.path.relpath(os.path.realpath(p) if "*" not in p else p, top).replace(os.sep, "/")

    return Sources(top, (rel(script), rel(os.path.join(HERE, "harness", "*.py")),
                         rel(os.path.join(os.path.realpath(CANTICLE), "canticle", "*.py")),
                         *(rel(os.path.join(HERE, e)) for e in extra)))


def file_digests(files: dict[str, bytes]) -> dict[str, str]:
    return {p: _sha(b) for p, b in sorted(files.items())}


def digest(shas: dict[str, str]) -> str:
    """The source digest of {path: sha256} (see the module docstring)."""
    return _sha("".join(f"{shas[p]}  {p}\n" for p in sorted(shas, key=lambda s: s.encode())).encode())


def unified_diff(src: Sources, commit: str, paths: list[str], at_commit: dict) -> str:
    """``git diff`` from ``commit`` to the working tree for ``paths``; files not in ``commit`` as new files."""
    opts = ["-c", "core.quotepath=off", "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
            "--binary", "--full-index", "--src-prefix=a/", "--dst-prefix=b/"]
    old = [p for p in paths if p in at_commit]
    out = _git(src.top, *opts, commit, "--", *old) if old else ""
    for p in paths:
        if p not in at_commit:          # untracked (or only in the index): diff against nothing
            out += _git(src.top, *opts, "--no-index", "--", "/dev/null", p, check=False)
    return out


def reconstruct(src: Sources, commit: str, patch: str) -> dict[str, bytes]:
    """The source files that ``commit`` plus ``patch`` give."""
    with tempfile.TemporaryDirectory(prefix="pd-src-") as tmp:
        for path, data in src.at(commit).items():
            os.makedirs(os.path.join(tmp, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(tmp, path), "wb") as f:
                f.write(data)
        if patch:
            env = {**os.environ, "GIT_CEILING_DIRECTORIES": os.path.dirname(tmp)}   # never find an outer repo
            env.pop("GIT_DIR", None)
            p = subprocess.run(["git", "apply", "-"], cwd=tmp, input=patch, text=True, capture_output=True, env=env)
            if p.returncode:
                raise RunFailed(f"patch does not apply to {commit}: {p.stderr.strip()}")
        return Sources(tmp, src.patterns).worktree()


def source_state(src: Sources, allow_dirty: bool) -> dict:
    """Commit, per-file digests and source digest of the working tree; refuses a dirty tree unless allowed."""
    commit = _git(src.top, "rev-parse", "--verify", "HEAD^{commit}").strip()
    work = src.worktree()
    head = src.at(commit)
    shas, head_shas = file_digests(work), file_digests(head)
    dirty = sorted(p for p in set(shas) | set(head_shas) if shas.get(p) != head_shas.get(p))
    if not shas:
        raise RunFailed(f"no source files match {src.patterns}")
    state = {"digest": digest(shas), "method": DIGEST_METHOD, "patterns": list(src.patterns), "files": shas,
             "git_commit": commit, "git_dirty": bool(dirty), "dirty_files": dirty, "patch": None}
    if dirty:
        if not allow_dirty:
            raise Dirty(f"uncommitted changes to source files {dirty}. Commit them, or pass --allow-dirty to run "
                        "anyway and record the diff in the manifest")
        text = unified_diff(src, commit, dirty, head)
        if file_digests(reconstruct(src, commit, text)) != shas:
            raise RunFailed("the recorded diff does not rebuild the working tree's source files from HEAD")
        state["patch"] = {"base": commit, "sha256": _sha(text.encode()), "unified_diff": text}
    return state


# ---------------------------------------------------------------- one run

class Run:
    """One invocation of an experiment: provenance at launch, a staging directory, atomic publication.

    ``unit`` names the directory under ``results/`` (``e1``, ``e3-slow``, ...).
    Construction refuses a dirty tree (``Dirty``) unless ``allow_dirty``.
    """

    def __init__(self, unit: str, experiment: str, script: str, config: dict, *, results_dir: str = RESULTS,
                 allow_dirty: bool = False, extra_sources: Iterable[str] = (), conditions: Optional[list] = None):
        self.unit, self.experiment = unit, experiment
        self.results = os.path.abspath(results_dir)
        self.target = os.path.join(self.results, unit)
        self.sources = default_sources(script, extra_sources)
        self.id = new_run_id()
        started = _now()
        self.source = source_state(self.sources, allow_dirty)
        canticle = _imported_from("canticle")
        if canticle and not canticle.startswith(os.path.realpath(CANTICLE) + os.sep):
            raise RunFailed(f"canticle is imported from {canticle}, not from the digested {CANTICLE}")
        os.makedirs(os.path.join(self.results, STAGING), exist_ok=True)
        recover(self.results, unit)
        self.stage = os.path.join(self.results, STAGING, f"{unit}@{self.id}")
        os.makedirs(os.path.join(self.stage, "raw"))
        src = self.source
        self.manifest = {
            "experiment": experiment, "unit": unit, "run_id": self.id, "argv": list(sys.argv),
            "python": sys.executable, "started": started, "finished": None,
            "git_commit": src["git_commit"], "git_dirty": src["git_dirty"], "allow_dirty": allow_dirty,
            "source_sha256": src["digest"],
            "source": {k: src[k] for k in ("method", "patterns", "files", "dirty_files", "patch")},
            "canticle_imported_from": canticle, "config": config, "conditions": conditions, "env": stats.env()}

    def raw(self, name: str) -> str:
        """Path of a raw output file inside the stage."""
        return os.path.join(self.stage, "raw", name)

    def publish(self, aggregate_name: str, aggregate: dict, **manifest_extra) -> str:
        """Write the aggregate and manifest into the stage and swap it into ``results/<unit>``.

        Raises ``RunFailed`` and publishes nothing if a source file changed
        since launch; the stage is kept for inspection.
        """
        stats.write_json(os.path.join(self.stage, aggregate_name), {"run_id": self.id, **aggregate})
        self.manifest.update(manifest_extra, finished=_now(), aggregate=aggregate_name)
        self.manifest["outputs"] = outputs(self.stage)
        stats.write_json(os.path.join(self.stage, MANIFEST), self.manifest)
        _fsync_tree(self.stage)
        now = file_digests(self.sources.worktree())
        if now != self.source["files"]:
            changed = sorted(p for p in set(now) | set(self.source["files"]) if now.get(p) != self.source["files"].get(p))
            raise RunFailed(f"source files changed during the run: {changed}. Nothing was published; the staged "
                            f"output is in {self.stage}")
        recover(self.results, self.unit)
        swap_in(self.stage, self.target)
        return self.target


def _imported_from(module: str) -> Optional[str]:
    m = sys.modules.get(module)
    return os.path.realpath(m.__file__) if m is not None and getattr(m, "__file__", None) else None


# ---------------------------------------------------------------- generations

def outputs(gen: str) -> dict[str, str]:
    """sha256 of every file in a generation except the manifest and worker logs (logs are not in git)."""
    out = {}
    for root, _, files in os.walk(gen):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), gen).replace(os.sep, "/")
            if rel == MANIFEST or name.endswith(".log"):
                continue
            with open(os.path.join(root, name), "rb") as f:
                out[rel] = _sha(f.read())
    return dict(sorted(out.items()))


def load_manifest(gen: str) -> Optional[dict]:
    path = os.path.join(gen, MANIFEST)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def check_generation(gen: str) -> dict:
    """The manifest of a complete, unmixed generation; raises ``RunFailed`` otherwise."""
    m = load_manifest(gen)
    if m is None:
        raise RunFailed(f"{gen}: no {MANIFEST}")
    have = outputs(gen)
    want = m.get("outputs") or {}
    bad = sorted(p for p in set(have) | set(want) if have.get(p) != want.get(p))
    if bad:
        raise RunFailed(f"{gen}: files differ from the manifest of run {m.get('run_id')}: {bad}")
    with open(os.path.join(gen, m["aggregate"])) as f:
        if json.load(f).get("run_id") != m["run_id"]:
            raise RunFailed(f"{gen}: aggregate and manifest name different runs")
    return m


RENAME_NOREPLACE, RENAME_EXCHANGE = 1, 2
_AT_FDCWD = -100


def _renameat2(src: str, dst: str, flags: int) -> None:
    fn = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if fn is None:
        raise OSError(errno.ENOSYS, "renameat2 is not available")
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    if fn(_AT_FDCWD, os.fsencode(src), _AT_FDCWD, os.fsencode(dst), flags) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), src, None, dst)


_UNSUPPORTED = (errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP)


def swap_in(stage: str, target: str) -> None:
    """Make the complete directory ``stage`` the generation at ``target``, atomically; drop the old one."""
    parent = os.path.dirname(target)
    if not os.path.lexists(target):
        try:
            _renameat2(stage, target, RENAME_NOREPLACE)
        except OSError as e:
            if e.errno not in _UNSUPPORTED:
                raise
            os.rename(stage, target)
        _fsync_dir(parent)
        return
    try:
        _renameat2(stage, target, RENAME_EXCHANGE)       # one step: target is now new, stage holds the old
    except OSError as e:
        if e.errno not in _UNSUPPORTED:
            raise
        aside = stage + ".previous"                     # recover() restores this if we die before the next rename
        os.rename(target, aside)
        _fsync_dir(parent)
        _fsync_dir(os.path.dirname(aside))
        os.rename(stage, target)
        _fsync_dir(parent)
        shutil.rmtree(aside)
        return
    _fsync_dir(parent)
    _fsync_dir(os.path.dirname(stage))
    shutil.rmtree(stage)


def recover(results: str, unit: str) -> None:
    """Finish or roll back a publication that died between its two renames (no RENAME_EXCHANGE)."""
    target = os.path.join(results, unit)
    for aside in sorted(glob.glob(os.path.join(results, STAGING, glob.escape(unit) + "@*.previous"))):
        if os.path.lexists(target):
            shutil.rmtree(aside)            # the new generation made it in; this is the old one
        else:
            os.rename(aside, target)        # died between the renames: put the old generation back
            _fsync_dir(results)


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_tree(path: str) -> None:
    for root, _, files in os.walk(path, topdown=False):
        for name in files:
            fd = os.open(os.path.join(root, name), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        _fsync_dir(root)


# ---------------------------------------------------------------- checks used by the runners

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


# ---------------------------------------------------------------- verification

def verify(gen: str, commit: Optional[str] = None, top: Optional[str] = None) -> dict:
    """Check a published generation: its files against its manifest, its source digest against ``commit``.

    ``commit`` defaults to the one the manifest names. The digest is recomputed
    from ``git show <commit>:<path>`` over the manifest's source patterns. If the
    manifest embeds a patch, the digest of ``commit`` plus that patch is checked too.
    """
    m = check_generation(gen)
    top = top or repo_top()
    rev = _git(top, "rev-parse", "--verify", f"{commit or m['git_commit']}^{{commit}}").strip()
    src = Sources(top, tuple(m["source"]["patterns"]))
    at = file_digests(src.at(rev))
    rec = m["source"]["files"]
    out = {"unit": m.get("unit"), "run_id": m["run_id"], "commit": rev, "recorded_commit": m["git_commit"],
           "recorded_digest": m["source_sha256"], "digest_at_commit": digest(at),
           "match": digest(at) == m["source_sha256"] and at == rec,
           "differ": sorted(p for p in set(at) | set(rec) if at.get(p) != rec.get(p))}
    if digest(rec) != m["source_sha256"]:
        out["match"] = False
        out["manifest_inconsistent"] = "per-file digests do not give the recorded source digest"
    patch = m["source"].get("patch")
    if patch:
        text = patch["unified_diff"]
        out["patch_sha256_ok"] = _sha(text.encode()) == patch["sha256"]
        try:
            rebuilt = file_digests(reconstruct(src, rev, text))
            out["match_with_patch"] = out["patch_sha256_ok"] and digest(rebuilt) == m["source_sha256"]
        except RunFailed as e:
            out["match_with_patch"] = False
            out["patch_error"] = str(e)
    return out
