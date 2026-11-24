"""Gate 2 (or any of the newcomer rows) as a matrix: a line per cell, a column per tree. Usage: verdict_table.py <newcomer_rows.py's out.json>...
<name,...>. In a cell of the matrix: the verdict; the first valid frame, s, worst of the runs; first-frame misses (> 1.0 s); item misses
(> 2.0 s or lost); of these, lost, and more than one loop (10 s) late, a label only. newcomer_table.py has the rest."""

import json
import sys
from collections import defaultdict
from math import inf

names = sys.argv[-1].split(",")
cells = defaultdict(list)
for f in sys.argv[1:-1]:
    for r in json.load(open(f)):
        cells[r["row"], r["tree"]].append(r)
rows = sorted({k[0] for k in cells}, key=lambda row: (lambda kind, ports, rate, off: (kind, int(rate), int(ports), float(off)))(*row.split("-")))
print("| row (sources-ports-rate-offset) | " + " | ".join(names) + " |")
print("|---" * (len(names) + 1) + "|")
passed = dict.fromkeys(names, 0)
for row in rows:
    out = []
    for n in names:
        rs = cells.get((row, n))
        if not rs:
            out.append("–")
            continue
        assert {r["cryptography"] for r in rs} == {"50.0.1"}, (row, n)
        firsts = [inf if r["first_valid_frame_s"] is None else r["first_valid_frame_s"] for r in rs]
        fm, im = sum(r["first_miss"] for r in rs), sum(r["item_misses"] for r in rs)
        lost, loop = sum(r["items_lost"] for r in rs), sum(r["items_more_than_one_loop_late"] for r in rs)
        ok = not fm and not im
        passed[n] += ok
        worst = "lost" if max(firsts) == inf else f"{max(firsts):.2f} s"
        out.append(f"{'PASS' if ok else '**FAIL**'}: worst first {worst}; first {fm}/{len(rs)}, items {im}/{20 * len(rs)}"
                   + (f" (lost {lost}, > 10 s {loop})" if lost or loop else ""))
    print(f"| {row} | " + " | ".join(out) + " |")
print("| **cells passed** | " + " | ".join(f"**{passed[n]} of {sum(1 for r in rows if cells.get((r, n)))}**" for n in names) + " |")
