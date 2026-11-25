"""Row J's table. Usage: junk_table.py <junk_rows.py's out.json>...
A run whose flood fell under 95 % of its rate in its lowest whole second is INVALID (PLAN.md): it passes nothing, stays in the table, and fails its cell when a
deadline was missed in it. A cell needs its declared number of valid runs."""

import json
import sys
from collections import defaultdict

cells = defaultdict(list)
for f in sys.argv[1:]:
    for r in json.load(open(f)):
        cells[r["row"], r["tree"]].append(r)
DECLARED = {"new": 5, "slice": 5, "head": 3, "base": 3}
print("| row | tree | runs | items of each station during the flood, of 57, per run | worst latency, ms | offered /s | drops: kernel (reported) | verdict |")
print("|---|---|---|---|---|---|---|---|")
for (row, tree), rs in sorted(cells.items(), key=lambda kv: (kv[0][0].split("-")[0], int(kv[0][0].split("-")[2]), kv[0][1])):
    per = "; ".join("/".join(str(s["during_the_flood"]) for s in r["stations"].values()) for r in rs)
    worst = max((s["latency_ms"]["max"] for r in rs for s in r["stations"].values() if s["latency_ms"]), default=None)
    valid = [r for r in rs if r["driven"]]
    bad = [r for r in rs if not (r["pass"] and r["told"])]
    short = len(valid) < DECLARED[tree]
    verdict = "**FAIL**" if bad else f"**INVALID**, {len(valid)} of {DECLARED[tree]} declared" if short else "PASS"
    under = "; ".join(f"run {r['run']} underdriven: {r['lowest_second']:,}" for r in rs if not r["driven"])
    print(f"| {row} | {tree} | {len(rs)} | {per} | {worst} | {min(r['offered_per_s'] for r in rs):,} | {max(r['kernel_drops'] for r in rs)} "
          f"({max(r['reported_socket_dropped'] or 0 for r in rs)}) | {verdict}{' (' + under + ')' if under else ''} |")
