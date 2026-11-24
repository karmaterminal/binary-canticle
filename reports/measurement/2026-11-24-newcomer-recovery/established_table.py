"""Gate 1's table, every run of a row on one line. Usage: established_table.py <established_rows.py's out.json>... [name,...]
A run passes as established_rows.py says: 57 of 57 during the flood, p50 at most 250 ms, none later than 4.5 s, and the kernel's
drops, if there were any, reported. One run that misses fails its row. ``name,...`` picks trees and their order."""

import json
import sys
from collections import defaultdict
from statistics import median

names = next((a.split(",") for a in sys.argv[1:] if not a.endswith(".json")), None)
rows = defaultdict(list)
for f in (a for a in sys.argv[1:] if a.endswith(".json")):
    for r in json.load(open(f)):
        rows[r["row"], r["tree"]].append(r)


def span(xs):
    return f"{min(xs):,.0f}–{max(xs):,.0f}" if min(xs) != max(xs) else f"{xs[0]:,.0f}"


print("| row | tree | runs | quiet items during the flood, per run, of 57 | latency ms over the runs: p50, max | offered /s | socket drops: kernel "
      "(reported) | refused, by reason (median) | checks that failed (median) | verdict |")
print("|---|---|---|---|---|---|---|---|---|---|")
for row, tree in sorted((k for k in rows if names is None or k[1] in names), key=lambda k: (k[0], names.index(k[1]) if names else k[1])):
    rs = rows[row, tree]
    assert {r["cryptography"] for r in rs} == {"50.0.1"} and {r["sung"] for r in rs} == {57}, (row, tree)
    lat = [r["latency_ms"] for r in rs if r["latency_ms"]]
    rc = [r["receive"] for r in rs if r["receive"]]
    reasons = [k for k in (rc[0]["refused"] if rc else ()) if any(c["refused"][k] for c in rc)]
    refused = ", ".join(f"{k} {median(c['refused'][k] for c in rc):,.0f}" for k in reasons) or "none" if rc else "–"
    rep = [r["reported_socket_dropped"] for r in rs]
    print(f"| {row} | {tree} | {len(rs)} | {', '.join(str(r['during_the_flood']) for r in rs)} | "
          f"{span([x['p50'] for x in lat]) + ', ' + span([x['max'] for x in lat]) if lat else '–'} | {span([r['offered_per_s'] for r in rs])} | "
          f"{span([r['kernel_drops'] for r in rs])} ({'–' if rep[0] is None else span(rep)}) | {refused} | "
          f"{median(r['unverified'].get('bad_signature', 0) for r in rs):,.0f} | "
          f"{'PASS' if all(r['pass'] and r['told'] for r in rs) else '**FAIL**'} ({sum(r['pass'] and r['told'] for r in rs)} of {len(rs)} runs) |")
