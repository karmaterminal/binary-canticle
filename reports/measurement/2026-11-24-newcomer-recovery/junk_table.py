"""Row J's table. Usage: junk_table.py <junk_rows.py's out.json>"""

import json
import sys
from collections import defaultdict

cells = defaultdict(list)
for r in json.load(open(sys.argv[1])):
    cells[r["row"], r["tree"]].append(r)
print("| row | tree | runs | items of each station during the flood, of 57, per run | worst latency, ms | offered /s | drops: kernel (reported) | verdict |")
print("|---|---|---|---|---|---|---|---|")
for (row, tree), rs in sorted(cells.items(), key=lambda kv: (kv[0][0].split("-")[0], int(kv[0][0].split("-")[2]), kv[0][1])):
    per = "; ".join("/".join(str(s["during_the_flood"]) for s in r["stations"].values()) for r in rs)
    worst = max((s["latency_ms"]["max"] for r in rs for s in r["stations"].values() if s["latency_ms"]), default=None)
    ok = sum(r["pass"] and r["told"] and r["driven"] for r in rs)
    print(f"| {row} | {tree} | {len(rs)} | {per} | {worst} | {min(r['offered_per_s'] for r in rs):,} | {max(r['kernel_drops'] for r in rs)} "
          f"({max(r['reported_socket_dropped'] or 0 for r in rs)}) | {'PASS' if ok == len(rs) else '**FAIL**'} ({ok} of {len(rs)} runs) |")
