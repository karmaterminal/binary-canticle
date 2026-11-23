"""Run cells given as JSON (a list of parameter dicts) and print a one-line summary of each.

    nice -n 19 ionice -c3 python run_cells.py <out_dir> '<json list>'   (or @file.json)

Refuses to start a cell while the host's 1-minute load average is above nproc (🍃's condition),
waiting up to 5 minutes for it to fall, and records the wait.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from cells import run_cell
from mlib import loadavg, machine


def brief(r: dict) -> dict:
    h = (r.get("daemon_health_last") or {})
    c = h.get("counters", {})
    out = {
        "cell": r["params"]["name"], "offered/s": r.get("offered_rate"), "frame_B": r.get("frame_bytes"),
        "verified/s": r.get("probe_verified_rate_in_window"), "kernel_drops": r.get("kernel_drops"),
        "lat_p50": r.get("latency_send_to_record_ms", {}).get("p50"),
        "lat_p99": r.get("latency_send_to_record_ms", {}).get("p99"),
        "adm": c.get("admission"), "unverified": {k: v for k, v in (c.get("unverified") or {}).items() if v},
        "records": h.get("records"), "dedup": h.get("dedup"),
        "tap_gaps": (r.get("tap") or {}).get("rec_seq_gap_records"),
        "pushes": r.get("pushes"), "quiet": {k: v for k, v in (r.get("quiet") or {}).items()
                                            if k in ("sung", "reached_daemon", "pushed_per_ear")},
        "procs": {k: (v["cpu_mean"], v["rss_max_kb"] // 1024) for k, v in (r.get("processes") or {}).items()},
    }
    return out


def main() -> int:
    out = Path(sys.argv[1])
    spec = sys.argv[2]
    cells = json.loads(Path(spec[1:]).read_text() if spec.startswith("@") else spec)
    out.mkdir(parents=True, exist_ok=True)
    m = machine()
    (out / f"machine-{Path(spec[1:]).stem if spec.startswith('@') else 'inline'}.json").write_text(json.dumps(m, indent=1))
    n = os.cpu_count()
    for p in cells:
        waited = 0
        while loadavg() > n and waited < 300:
            time.sleep(10)
            waited += 10
        p.setdefault("waited_for_load_s", waited)
        r = run_cell(p, out / p["name"])
        print(json.dumps(brief(r), default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
