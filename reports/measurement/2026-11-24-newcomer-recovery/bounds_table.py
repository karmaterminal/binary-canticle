"""Each cell's worst first valid frame beside the bound PLAN.md declared for it (its "Added ... what changed in the slice" section), by kind:
churn (own key): none; fixed (own key): 0.33 s at offset 0, else 0.17 s; xchurn and xfixed (other keys): 0.22 s; afixed (every key): 0.23 s.
Usage: bounds_table.py <newcomer_rows.py's out.json>... <name,...>"""

import json
import sys
from collections import defaultdict
from math import inf

names = sys.argv[-1].split(",")


def bound(kind, offset):
    return {"churn": None, "xchurn": 0.22, "xfixed": 0.22, "afixed": 0.23, "fixed": 0.33 if offset == 0 else 0.17}[kind]


cells = defaultdict(list)
for f in sys.argv[1:-1]:
    for r in json.load(open(f)):
        cells[r["row"], r["tree"]].append(r)
print("| row | bound, s | " + " | ".join(f"{n}: worst first frame, s; runs inside" for n in names) + " |")
print("|---" * (2 + len(names)) + "|")
key = lambda row: (lambda k, p, r, o: (k, int(r), int(p), float(o)))(*row.split("-"))
for row in sorted({k[0] for k in cells}, key=key):
    kind, _, _, offset = row.split("-")
    b, out = bound(kind, float(offset)), []
    for n in names:
        firsts = [inf if r["first_valid_frame_s"] is None else r["first_valid_frame_s"] for r in cells.get((row, n), [])]
        if not firsts:
            out.append("–")
            continue
        worst = "lost" if max(firsts) == inf else f"{max(firsts):.3f}"
        inside = "" if b is None else f"; {sum(x <= b for x in firsts)} of {len(firsts)}" + ("" if max(firsts) <= b else " **OUTSIDE**")
        out.append(worst + inside)
    print(f"| {row} | {'none' if b is None else b} | " + " | ".join(out) + " |")
