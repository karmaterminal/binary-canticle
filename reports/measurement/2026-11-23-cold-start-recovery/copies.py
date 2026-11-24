"""How many copies a newcomer sends before one is heard, against the lottery the code describes (README.md, the recovery argument).
Usage: copies.py <newcomer_rows.py's out.json>... [name,...]

A run gives one number: the copies (beacons and items, every repeat) sent up to its first valid frame, or all it sent when none was
heard. If each copy is verified independently with chance p, the maximum-likelihood estimate over a cell is heard / copies. (The
copies are counted to when the client read the frame, not to when it was sent, so the few sent while it waited count too
and p reads a little low.) Beside it, C/R with the head's C = 1 000/s. Rows at one rate are pooled over the offsets above 0."""

import json
import sys
from collections import defaultdict

names = next((a.split(",") for a in sys.argv[1:] if not a.endswith(".json")), ["head"])
runs = [r for f in sys.argv[1:] if f.endswith(".json") for r in json.load(open(f)) if r["tree"] in names]
cells = defaultdict(list)
for r in runs:
    kind, ports, rate, off = r["row"].split("-")
    cells[r["tree"], kind, int(rate), int(ports), f"offset {off} s"].append(r)
    if float(off) > 0:
        cells[r["tree"], kind, int(rate), int(ports), "offsets > 0, pooled"].append(r)
print("| tree | flood | R, /s | runs | heard at all | copies sent before the first was heard, per run | p, estimated | 1 in | C/R, C = 1 000/s | first "
      "frame > 1.0 s: seen |")
print("|---|---|---|---|---|---|---|---|---|---|")
for (tree, kind, rate, ports, off), rs in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3], "pooled" in kv[0][4],
                                                                              float(kv[0][4].split()[1].strip(",s>") or 0) if "pooled" not in kv[0][4] else 0)):
    n = [r["sent_before_first_valid"] if r["first_valid_frame_s"] is not None else r["sent"] for r in rs]
    heard = sum(r["first_valid_frame_s"] is not None for r in rs)
    p = heard / sum(n)
    print(f"| {tree} | {kind}-{ports}, {off} | {rate:,} | {len(rs)} | {heard} | {', '.join(map(str, n)) if len(n) < 9 else f'{min(n)}–{max(n)}'} | {p:.1%} | "
          f"{1 / p if p else float('inf'):.0f} | {min(1, 1_000 / rate):.1%} | {sum(r['first_miss'] for r in rs)} of {len(rs)} |")
