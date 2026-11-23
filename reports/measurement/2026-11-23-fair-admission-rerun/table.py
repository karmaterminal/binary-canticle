"""The rerun's table, from each row's row.json. Usage: table.py <results dir>..."""
import json
import sys
from pathlib import Path


def n(x):
    return "–" if x is None else f"{x:,.0f}"


def d(x, scale=1, f=".0f"):
    return "–" if not x else " / ".join(format(x[k] / scale, f) for k in ("p50", "p90", "p99", "max"))


print("| row | offered /s | quiet at daemon during the flood | pushed | send → record ms, p50 / p90 / p99 / max | "
      "send → push s, p50 / p90 / p99 / max | socket drops: kernel (reported by the daemon) | refused by the daemon, by reason | "
      "repeats, copies (not verified) | verified / checks that failed | health reasons seen | daemon CPU mean, RSS max |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for a in sys.argv[1:]:
    for path in sorted(Path(a).glob("*/row.json")):
        r = json.loads(path.read_text())
        rc, c = r["receive"] or {}, r["daemon_cpu_rss"]
        refused = ", ".join(f"{k} {v:,}" for k, v in (rc.get("refused") or {}).items() if v) or "none"
        print(" | ".join((f"| {r['row']} ({r['duration_s']:.0f} s)", n(r["offered_per_s"]),
                          f"{r['at_daemon_during_flood']}/{r['sung']}", f"{r['pushed']}/{r['sung']}",
                          d(r["send_to_record_ms"]), d(r["send_to_push_ms"], 1000, ".1f"),
                          f"{n(r['kernel_drops'])} ({n(r['reported_socket_dropped'])})", refused if rc else "–",
                          f"{rc['repeats']:,}, {rc['copies']:,}" if rc else "–",
                          f"{rc['verified']:,} / {rc['unverified']:,}" if rc else "–",
                          ", ".join(r["health_reasons_seen"]) or "none",
                          f"{c.get('cpu_mean', 0):.0f} %, {c.get('rss_max_kb', 0) // 1024} MiB |")))
