#!/usr/bin/env python3
"""Own the short-lived fixture and k6 child; never start a persistent service."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time
from dataclasses import asdict

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "prototype" / "canticle-station"))
from fixtures.loopback import Bounds, Fixture  # noqa: E402


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def child_limits():
    # No hard address-space cap: Go reserves a large virtual arena. RSS is not
    # claimed bounded by GOMEMLIMIT; the test population and lifetime ARE bounded.
    for kind, maximum in ((resource.RLIMIT_NOFILE, 128),
                          (resource.RLIMIT_FSIZE, 8 * 1024 * 1024),
                          (resource.RLIMIT_CPU, 30)):
        _, hard = resource.getrlimit(kind)
        cap = maximum if hard == resource.RLIM_INFINITY else min(maximum, hard)
        resource.setrlimit(kind, (cap, cap))


async def stop_child(child):
    if child is None:
        return True
    if child.returncode is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(child.wait(), 2)
        except TimeoutError:
            os.killpg(child.pid, signal.SIGKILL)
            await asyncio.wait_for(child.wait(), 2)
    return child.returncode is not None


async def run(args, bounds):
    out = Path(args.out).resolve()
    if out.is_relative_to(REPO):
        raise ValueError("artifacts/state must be outside this repository")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    binary = shutil.which(args.k6)
    if binary is None:
        raise ValueError("k6 executable not found")
    loop = asyncio.get_running_loop()
    owner = asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, owner.cancel)
    fixture = Fixture(bounds)
    child = None
    code = 1
    failure = None
    report = None
    try:
        async with fixture:
            # Deliberately do not inherit proxies, credentials, cloud outputs or
            # arbitrary K6_* settings. No k6 telemetry or externally bound API.
            env = dict(PATH="/usr/bin:/bin", HOME=str(fixture.root),
                       FIXTURE_URL=fixture.url, FIXTURE_TOKEN=fixture.token,
                       ITEMS=str(bounds.items), VUS=str(bounds.vus),
                       PACE_MS=str(bounds.pace_ms),
                       SUMMARY_PATH=str(out / "k6-summary.json"),
                       K6_NO_USAGE_REPORT="true", K6_WEB_DASHBOARD="false",
                       GOMAXPROCS="2", GOMEMLIMIT="128MiB", NO_PROXY="*")
            command = [binary, "run", "--address", "127.0.0.1:0", "--no-usage-report",
                       str(HERE / "scenarios" / "smoke.js")]
            dump(out / "run.json", dict(bounds=asdict(bounds), command=command,
                 latency_boundary="first relay UDP arrival to complete record-v1 newline; not model heard",
                 shared_process=True, hard_caps=dict(child_cpu_seconds=30, child_fds=128,
                 child_file_bytes=8*1024*1024, child_wall_seconds=55)))
            with (out / "k6.log").open("wb") as log:
                child = await asyncio.create_subprocess_exec(*command, env=env, cwd=fixture.root,
                    stdout=log, stderr=asyncio.subprocess.STDOUT,
                    start_new_session=True, preexec_fn=child_limits)
                code = await asyncio.wait_for(child.wait(), 55)
            report = fixture.report()
            if not report["accounting"] or report["errors"] or not report["production_tasks_alive"]:
                code = code or 1
    except (Exception, asyncio.CancelledError) as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:200]
        code = 1
    finally:
        child_reaped = await stop_child(child)
        cleanup = await fixture.close()
        cleanup["k6_child_reaped"] = child_reaped
        cleanup["ok"] = cleanup["ok"] and child_reaped
        dump(out / "process.json", dict(k6_exit_code=child.returncode if child else None,
             supervisor_exit_code=code if cleanup["ok"] else (code or 1),
             child_started=child is not None, child_reaped=child_reaped))
        dump(out / "cleanup.json", cleanup)
        dump(out / "fixture-report.json", report or fixture.ledger.report(time.monotonic_ns()))
        if failure:
            dump(out / "failure.json", dict(error=failure))
        if not cleanup["ok"]:
            code = code or 1
    print(json.dumps(dict(exit_code=code, artifacts=str(out), cleanup_ok=cleanup["ok"], failure=failure)))
    return code if 0 <= code <= 255 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="NEW artifact directory outside the repository")
    parser.add_argument("--k6", default="k6", help="path to local k6 executable")
    parser.add_argument("--items", type=int, default=6)
    parser.add_argument("--vus", type=int, default=1)
    parser.add_argument("--deadline-ms", type=int, default=1000)
    parser.add_argument("--pace-ms", type=int, default=250)
    parser.add_argument("--drop-first", action="store_true", help="negative control: MUST fail k6 thresholds")
    args = parser.parse_args()
    try:
        bounds = Bounds(args.items, args.vus, args.deadline_ms, args.pace_ms, args.drop_first)
        return asyncio.run(run(args, bounds))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
