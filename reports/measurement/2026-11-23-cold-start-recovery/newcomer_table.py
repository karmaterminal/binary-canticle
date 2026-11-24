"""The newcomer rows' table, every run of a cell on one line. Usage: newcomer_table.py <newcomer_rows.py's out.json>... [name,...]
A cell passes when no run missed a deadline (PLAN.md): its first valid frame within 1.0 s, every item within 2.0 s. A lost item
counts as infinite in the distribution. ``name,...`` picks trees and their order."""

import json
import sys
from collections import defaultdict
from math import inf
from statistics import median

FIRST_S, ITEM_S = 1.0, 2.0


def s(x):
    return "lost" if x == inf else f"{x:.2f}"


def pct(xs, p):
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


files = [a for a in sys.argv[1:] if a.endswith(".json")]
names = next((a.split(",") for a in sys.argv[1:] if not a.endswith(".json")), None)
cells = defaultdict(list)
for f in files:
    for r in json.load(open(f)):
        cells[r["tree"], r["row"]].append(r)
order = lambda k: (lambda kind, ports, rate, off: (kind, int(rate), int(ports), float(off)))(*k[1].split("-"))
print("| row (sources-ports-rate-offset) | tree | runs | first valid frame, s, per run | first-frame misses (> 1.0 s) | item latency, s: "
      "min / median / p95 / max | item misses (> 2.0 s or lost) | > 10 s late | lost | socket drops: kernel (reported) | refused, by "
      "reason (median) | checks that failed, /s (median) | lowest second of the flood | verdict |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for tree, row in sorted((k for k in cells if names is None or k[0] in names),
                        key=lambda k: (order(k), names.index(k[0]) if names else k[0])):
    rs = cells[tree, row]
    lat = sorted(inf if x["latency_s"] is None else x["latency_s"] for r in rs for x in r["items"])
    first, miss = sum(r["first_miss"] for r in rs), sum(r["item_misses"] for r in rs)
    drops, rep = [r["kernel_drops"] for r in rs], [r["reported_socket_dropped"] for r in rs]
    rc = [r["receive"] for r in rs if r["receive"]]
    reasons = {k for c in rc for k, v in c["refused"].items() if v}
    refused = ", ".join(f"{k} {median(c['refused'][k] for c in rc):,.0f}" for k in rc[0]["refused"] if k in reasons) or "none" if rc else "–"
    assert all(r["flood_end_after_last_deadline_s"] > 0 and r["sung"] == len(r["items"]) == 20 for r in rs), (tree, row)
    print(f"| {row} | {tree} | {len(rs)} | {', '.join(s(inf if r['first_valid_frame_s'] is None else r['first_valid_frame_s']) for r in rs)} | "
          f"{first} of {len(rs)} | {s(lat[0])} / {s(pct(lat, 50))} / {s(pct(lat, 95))} / {s(lat[-1])} | {miss} of {20 * len(rs)} | "
          f"{sum(r['items_more_than_one_loop_late'] for r in rs)} | {sum(r['items_lost'] for r in rs)} | "
          f"{median(drops):,.0f} ({'–' if rep[0] is None else format(median(rep), ',.0f')}) | {refused} | "
          f"{median(r['unverified'].get('bad_signature', 0) / r['run_s'] for r in rs):,.0f} | {min(r['lowest_second'] for r in rs):,} | "
          f"{'PASS' if first == miss == 0 else '**FAIL**'} |")
