"""The inverse rows' table. Usage: inverse_table.py <inverse_rows.py's out.json>..."""

import json
import sys
from collections import defaultdict

cells = defaultdict(list)
for f in sys.argv[1:]:
    for r in json.load(open(f)):
        cells[r["row"], r["tree"]].append(r)
print("| row | tree | runs | what | passed |")
print("|---|---|---|---|---|")
for (row, tree), rs in sorted(cells.items()):
    if row == "I-b":
        what = "lease ended after " + ", ".join("never" if r["lapsed_after_s"] is None else f"{r['lapsed_after_s']:.2f} s" for r in rs)
    else:
        what = "; ".join("place after " + " / ".join("never" if s["known_after_s"] is None else f"{s['known_after_s']:.2f} s" for s in r["starts"])
                         + ", item misses " + " / ".join(str(s["item_misses"]) for s in r["starts"])
                         + f", displaced {r['receive'].get('displaced')}" for r in rs)
    print(f"| {row} | {tree} | {len(rs)} | {what} | {sum(r['pass'] for r in rs)} of {len(rs)} |")
