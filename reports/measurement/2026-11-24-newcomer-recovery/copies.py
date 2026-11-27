"""How many copies a newcomer sends before one is heard, against the lottery the code describes (README.md, the recovery argument).
Usage: copies.py <newcomer_rows.py's out.json>... [name,...]

A run gives one number: the copies (beacons and items, every repeat) sent up to its first valid frame, or all it sent when none was
heard. If each copy is verified independently with chance p, the maximum-likelihood estimate over a cell is heard / copies (in
brackets its exact 95 % interval). The copies are counted to when the client read the frame, not to when it was sent, so the few sent
while it waited count too and p reads a little low. Beside it C/R, C being the checks that came to nothing a second in those runs.
Rows at one rate are pooled over the offsets above 0."""

import json
import sys
from collections import defaultdict
from math import comb
from statistics import median


def interval(k, n, a=0.05):
    cdf = lambda i, p: sum(comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(i + 1))

    def edge(below):
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if below(mid) else (lo, mid)
        return lo
    return (edge(lambda p: 1 - cdf(k - 1, p) < a / 2) if k else 0.0), edge(lambda p: cdf(k, p) > a / 2)


names = next((a.split(",") for a in sys.argv[1:] if not a.endswith(".json")), ["head"])
runs = [r for f in sys.argv[1:] if f.endswith(".json") for r in json.load(open(f)) if r["tree"] in names]
cells = defaultdict(list)
for r in runs:
    kind, ports, rate, off = r["row"].split("-")
    cells[names.index(r["tree"]), kind, int(rate), int(ports), 0, float(off)].append(r)
    if float(off) > 0:
        cells[names.index(r["tree"]), kind, int(rate), int(ports), 1, 0.0].append(r)
print("| tree | flood | R, /s | runs | heard at all | copies sent before the first was heard, per run | p, estimated (95 %) | 1 in | C, checks/s "
      "that failed (median) | C/R | first frame > 1.0 s: seen |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for (t, kind, rate, ports, pooled, off), rs in sorted(cells.items()):
    n = [r["sent_before_first_valid"] if r["first_valid_frame_s"] is not None else r["sent"] for r in rs]
    heard = sum(r["first_valid_frame_s"] is not None for r in rs)
    p, (lo, hi) = heard / sum(n), interval(heard, sum(n))
    c = median(r["unverified"].get("bad_signature", 0) / r["run_s"] for r in rs)
    print(f"| {names[t]} | {kind}-{ports}, {'offsets > 0, pooled' if pooled else f'offset {off:g} s'} | {rate:,} | {len(rs)} | {heard} | "
          f"{', '.join(map(str, n)) if len(n) < 9 else f'{min(n)}–{max(n)}'} | {p:.1%} ({lo:.1%}–{hi:.1%}) | {1 / p if p else float('inf'):.0f} | "
          f"{c:,.0f} | {min(1, c / rate):.1%} | {sum(r['first_miss'] for r in rs)} of {len(rs)} |")
