"""AB's runs (rerun.py's row.json, 60 s flat out) as a table. Usage: ab_table.py <dir of <tree>/run<n>/<row>/row.json>

The producers run flat out, so what they offer differs from run to run, and the share dropped at the socket with it. What the reader
read a second is the reader's own rate: the two trees are compared by it. Each run is one line, in the order the trees ran."""

import json
import sys
from pathlib import Path

print("| row | run | tree | offered /s | read by the daemon /s | dropped at the socket | quiet items on time | daemon CPU % | load before |")
print("|---|---|---|---|---|---|---|---|---|")
rows = sorted(Path(sys.argv[1]).glob("*/run*/*/row.json"), key=lambda p: (p.parts[-2], p.parts[-3], p.parts[-4] != "new"))
for p in rows:
    r = json.loads(p.read_text())
    d = r["duration_s"]
    offered = r["offered_per_s"] * d
    print(f"| {p.parts[-2][:3].rstrip('-')} | {p.parts[-3][3:]} | {p.parts[-4]} | {r['offered_per_s']:,.0f} | {r['receive']['read'] / d:,.0f} | "
          f"{100 * r['kernel_drops'] / offered:.1f} % | {r['at_daemon_during_flood']} of {r['sung']} | {r['daemon_cpu_rss'].get('cpu_mean')} | "
          f"{r['load_at_start']:.1f} |")
