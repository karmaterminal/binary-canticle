#!/usr/bin/env python3
"""Read source identity only. This is never a launch or live-session receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PATHS = {
    "canticle": (
        "prototype/openclaw-canticle/index.ts",
        "prototype/openclaw-canticle/src/binding.ts",
        "prototype/openclaw-canticle/src/tools.ts",
        "prototype/canticle-station/canticle/station.py",
    ),
    "openclaw": (
        "src/plugins/local-session-route.ts",
        "src/plugins/tool-types.ts",
        "src/agents/agent-tools.before-tool-call.policy.ts",
        "src/agents/agent-tools.caller.ts",
        "src/auto-reply/reply/reply-dispatch-before-deliver.ts",
        "src/agents/subagents/announce/subagent-announce-handoff.ts",
        "src/agents/subagents/announce/subagent-announce-direct-delivery.ts",
        "src/agents/subagents/completion/subagent-completion-delivery.ts",
    ),
    "frond_ear": (
        "src/canticle/hear.ts",
        "src/canticle/delivery.ts",
        "docs/runbook.md",
    ),
}


def git(root: Path, *args: str) -> bytes:
    # No shell, network operation, user-supplied Git subcommand or config output.
    return subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        check=True, capture_output=True, timeout=15,
    ).stdout


def inventory(kind: str, root: Path) -> dict:
    root = root.resolve(strict=True)
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise ValueError("unsupported Git object ID")
    result = {"head": head, "files": []}
    for relative in PATHS[kind]:
        entry = {"path": relative}
        try:
            path = root / relative
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
                raise ValueError("source path is a symlink or leaves the checkout")
            if path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError("source file exceeds inventory limit")
            working = path.read_bytes()
            committed = git(root, "show", f"{head}:{relative}")
            entry.update(
                sha256=hashlib.sha256(working).hexdigest(),
                head_sha256=hashlib.sha256(committed).hexdigest(),
                matches_head=working == committed,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            # Do not print Git stderr, file contents or local paths into a receipt.
            entry["error"] = "source_unavailable_or_unsafe"
        result["files"].append(entry)
    result["selected_sources_match_head"] = all(
        f.get("matches_head") is True for f in result["files"]
    )
    return result


def report(checkouts: dict[str, Path]) -> dict:
    repositories = {}
    for name, path in checkouts.items():
        try:
            repositories[name] = inventory(name, path)
        except (OSError, ValueError, subprocess.SubprocessError):
            repositories[name] = {"error": "checkout_unavailable_or_unsafe"}
    return {
        "schema": "canticle-lesson-x-source-inventory/1",
        "scope": "selected source files in operator-supplied checkouts",
        "runtime_installation_verified": False,
        "live_session_encounter_proved": False,
        "policy_adoption_verified": False,
        "lesson_release": "not_evaluated",
        "repositories": repositories,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canticle", type=Path, required=True)
    parser.add_argument("--openclaw", type=Path)
    parser.add_argument("--frond-ear", type=Path)
    parser.add_argument("--output", type=Path, required=True,
                        help="new JSON file; refuses to overwrite an existing file")
    args = parser.parse_args(argv)
    checkouts = {name: getattr(args, name) for name in PATHS if getattr(args, name)}
    receipt = report(checkouts)
    try:
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(receipt, output, indent=2)
            output.write("\n")
    except OSError:
        print("inventory output could not be created; existing files are never replaced", file=sys.stderr)
        return 2
    clean = all(r.get("selected_sources_match_head") is True
                for r in receipt["repositories"].values())
    print("Source inventory written; no live-session or release proof was performed.")
    return 0 if clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
