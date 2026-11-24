#!/usr/bin/env python3
"""Check RFC-0002's claim tags (stdlib only).

Every unit of Markdown that contains a BCP 14 key word in capitals (MUST, MUST NOT, SHOULD,
SHOULD NOT, SHALL, REQUIRED) has to carry a status tag in the same unit. A unit is one list item
with its continuation lines, one paragraph, one table row or one heading. Fenced code is skipped,
and so is text between `<!-- claim-check: off -->` and `<!-- claim-check: on -->` (the excluded
lines are counted and printed, so nothing is skipped silently).

The tags (RFC-0002 §0.3):

    [built+tested: <repo>@<sha>:<path>:<line> | <test>]
    [built: <repo>@<sha>:<path>:<line>]
    [proposed: <issue/PR>]
    [open: <issue/PR or §n>]

A malformed tag fails anywhere in the file, keyword or not.

With --verify NAME=PATH, each built pointer into repository NAME is checked in the git
repository at PATH: the commit must exist, the file must exist at that commit, and it must have
at least that many lines. A test named as <path>:<line> is checked the same way at the same
commit, and one named as Class.method must find both names at that commit. binary-canticle is verified against this script's own repository by
default. Pointers into a repository with no PATH are counted as unverified, not failed.

Usage:
    python3 rfc/tools/check-claim-tags.py [--verify frond-ear=../frond-ear] [FILE ...]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

KEYWORD = re.compile(r"\b(MUST|SHOULD|SHALL|REQUIRED)\b")
TAG = re.compile(r"\[(built\+tested|built|proposed|open):\s*([^\]]*)\]")
TAG_START = re.compile(r"\[(built\+tested|built|proposed|open)\b")
POINTER = re.compile(r"^(?P<repo>[A-Za-z0-9_.-]+)@(?P<sha>[0-9a-f]{7,40}):(?P<path>[^:\s|]+):(?P<line>\d+)$")
REFERENCE = re.compile(r"(#\d+|§\d)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
FENCE = re.compile(r"^\s*(```|~~~)")
OFF, ON = "<!-- claim-check: off -->", "<!-- claim-check: on -->"
DEFAULT_FILES = ("rfc/0002-binary-canticle-sense-organ.md",)


def units(text: str):
    """Yield (first line number, [lines]) for each unit, and count the excluded lines."""
    unit: list[str] = []
    start = 0
    fenced = off = False
    excluded = 0

    def flush():
        nonlocal unit
        if unit:
            yield start, unit
        unit = []

    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped == OFF:
            yield from flush()
            off = True
            continue
        if stripped == ON:
            off = False
            continue
        if off:
            excluded += 1
            continue
        if FENCE.match(line):
            yield from flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        body = re.sub(r"^\s*>\s?", "", line) if line.lstrip().startswith(">") else line
        if not body.strip():
            yield from flush()
            continue
        if body.lstrip().startswith("|") or body.lstrip().startswith("#"):
            yield from flush()
            yield n, [body]
            continue
        if LIST_ITEM.match(body):
            yield from flush()
        if not unit:
            start = n
        unit.append(body)
    yield from flush()
    units.excluded = excluded


def check_tag(kind: str, value: str) -> tuple[str | None, list[re.Match]]:
    """Return (problem or None, pointer matches) for one tag."""
    value = value.strip()
    if kind in ("proposed", "open"):
        return (None if REFERENCE.search(value) else f"{kind} tag names no issue, PR or §: {value!r}"), []
    parts = re.split(r"\s*\\?\|\s*", value, maxsplit=1)
    pointer = POINTER.match(parts[0].strip())
    if pointer is None:
        return f"{kind} tag has no <repo>@<sha>:<path>:<line> pointer: {value!r}", []
    if kind == "built+tested" and (len(parts) < 2 or not parts[1].strip()):
        return f"built+tested tag names no test: {value!r}", [pointer]
    if kind == "built" and len(parts) > 1:
        return f"built tag carries a test; use built+tested: {value!r}", [pointer]
    if kind == "built+tested":
        return None, [pointer, parts[1].strip()]
    return None, [pointer]


def verify_test(pointer: re.Match, test: str, repos: dict[str, Path], cache: dict) -> str | None:
    """Check a test named as <path>:<line> or Class.method at the pointer's repo and SHA.

    Anything else (a measurement cell, say) is left to the reader: None.
    """
    repo = repos.get(pointer["repo"])
    if repo is None:
        return "unverified"
    at = re.fullmatch(r"([^:\s]+):(\d+)", test)
    if at:
        fake = POINTER.match(f"{pointer['repo']}@{pointer['sha']}:{at[1]}:{at[2]}")
        return verify(fake, repos, cache)
    named = re.fullmatch(r"([A-Za-z_]\w*)\.(test_\w+)", test)
    if named:
        for needle in (f"class {named[1]}", f"def {named[2]}"):
            r = subprocess.run(["git", "-C", str(repo), "grep", "-q", "-F", needle, pointer["sha"], "--"],
                               capture_output=True)
            if r.returncode != 0:
                return f"no {needle!r} at {pointer['repo']}@{pointer['sha']}"
    return None


def verify(pointer: re.Match, repos: dict[str, Path], cache: dict) -> str | None:
    """None if the pointer resolves, a problem string if not, 'unverified' if no repo path."""
    repo = repos.get(pointer["repo"])
    if repo is None:
        return "unverified"
    key = (pointer["repo"], pointer["sha"], pointer["path"])
    if key not in cache:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{pointer['sha']}:{pointer['path']}"],
                           capture_output=True, text=True)
        cache[key] = r.stdout.count("\n") + (0 if r.stdout.endswith("\n") or not r.stdout else 1) \
            if r.returncode == 0 else None
    lines = cache[key]
    if lines is None:
        return f"{pointer['path']} does not exist at {pointer['repo']}@{pointer['sha']}"
    if int(pointer["line"]) > lines:
        return f"{pointer['path']} has {lines} lines at {pointer['sha']}, not {pointer['line']}"
    return None


def main() -> int:
    here = Path(__file__).resolve().parent
    top = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True).stdout.strip()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", help=f"default: {' '.join(DEFAULT_FILES)}")
    ap.add_argument("--verify", action="append", default=[], metavar="NAME=PATH",
                    help="check built pointers into repository NAME in the git repository at PATH")
    args = ap.parse_args()
    repos = {"binary-canticle": Path(top)} if top else {}
    for spec in args.verify:
        name, _, path = spec.partition("=")
        if not path:
            ap.error(f"--verify wants NAME=PATH, not {spec!r}")
        ok = subprocess.run(["git", "-C", path, "rev-parse", "--git-dir"], capture_output=True).returncode == 0
        if not ok:
            ap.error(f"--verify {name}={path}: {path} is not a git repository")
        repos[name] = Path(path)
    files = [Path(f) for f in args.files] or [Path(top or ".") / f for f in DEFAULT_FILES]

    failures: list[str] = []
    tags: Counter = Counter()
    pointers: Counter = Counter()
    cache: dict = {}
    keyword_units = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        units.excluded = 0
        for start, lines in units(text):
            joined = " ".join(lines)
            found = list(TAG.finditer(joined))
            if len(TAG_START.findall(joined)) != len(found):
                failures.append(f"{path}:{start}: a tag is not closed or not of the form [kind: value]")
            for t in found:
                tags[t[1]] += 1
                problem, matched = check_tag(t[1], t[2])
                if problem:
                    failures.append(f"{path}:{start}: {problem}")
                for p in matched[:1]:
                    results = [verify(p, repos, cache)]
                    if len(matched) > 1:
                        results.append(verify_test(p, matched[1], repos, cache))
                    real = [r for r in results if r and r != "unverified"]
                    result = real[0] if real else results[0]
                    if result == "unverified":
                        pointers["unverified"] += 1
                    elif result:
                        pointers["broken"] += 1
                        failures.append(f"{path}:{start}: {result}")
                    else:
                        pointers["verified"] += 1
            if KEYWORD.search(joined):
                keyword_units += 1
                if not found:
                    word = KEYWORD.search(joined)[1]
                    failures.append(f"{path}:{start}: {word} with no status tag in its unit: "
                                    f"{joined.strip()[:100]!r}")
        print(f"{path}: {keyword_units} units with a key word; tags: "
              + ", ".join(f"{k} {tags[k]}" for k in ("built+tested", "built", "proposed", "open"))
              + f"; pointers: {pointers['verified']} verified, {pointers['unverified']} unverified"
              + f" (no --verify path), {pointers['broken']} broken; {units.excluded} lines excluded by"
              + " claim-check: off")
    for f in failures:
        print(f"FAIL {f}")
    print("FAIL" if failures else "PASS", f"({len(failures)} problem{'s' if len(failures) != 1 else ''})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
