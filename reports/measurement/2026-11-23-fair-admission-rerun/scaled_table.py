"""The scaled rows' table, every run of a row on one line. Usage: scaled_table.py <scaled_rows.py's out.json>
A row passes when every run had every item of the station during the flood, p50 at most 250 ms and none later than
4.5 s (test_fair_admission's bounds), and the daemon reported the kernel's drops, if there were any."""
import json
import sys
from collections import defaultdict
from statistics import median

OUTSIDE = {"spoof-exact-source-100000", "relay-first-then-churn-100000"}


def span(xs, f=",.0f"):
    xs = [x for x in xs if x is not None]
    return "–" if not xs else format(xs[0], f) if min(xs) == max(xs) else f"{min(xs):{f}}–{max(xs):{f}}"


rows = defaultdict(list)
for r in json.load(open(sys.argv[1])):
    rows[r["row"]].append(r)
print("| row | runs | offered /s | sources | that station, items during the flood, per run | latency ms over the runs: p50, p99, max | "
      "its first valid frame, ms | another station | socket drops: kernel (reported) | refused, by reason (median) | "
      "checks that failed (median) | sources that gained a share, lost it | health reasons | verdict |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for name, rs in rows.items():
    s, rc = [r["station"] for r in rs], [r["receive"] for r in rs]
    lat = [x["latency_ms"] for x in s if x["latency_ms"]]
    ok = all(x["during_the_flood"] == x["sung"] and x["latency_ms"]["p50"] <= 250 and x["latency_ms"]["max"] <= 4500 for x in s)
    told = all(r["kernel_drops"] == (r["reported_socket_dropped"] or 0) for r in rs)
    verdict = ("PASS" if ok and told else "**FAIL** (the items pass; the drops are not reported)" if ok else
               "**FAIL — outside the supported guarantee**" if name in OUTSIDE else "**FAIL**")
    other = [r["another_station"] for r in rs if r["another_station"]]
    refused = "–" if rc[0] is None else ", ".join(
        f"{k} {median(c['refused'][k] for c in rc):,.0f}" for k in rc[0]["refused"] if any(c["refused"][k] for c in rc)) or "none"
    print(f"| {name} | {len(rs)} | {span([r['offered_per_s'] for r in rs])} | {span([r['sources'] for r in rs])} | "
          f"{', '.join(str(x['during_the_flood']) for x in s)} of {s[0]['sung']} | "
          f"{span([x['p50'] for x in lat])}, {span([x['p99'] for x in lat])}, {span([x['max'] for x in lat])} | "
          f"{span([r['first_valid_frame_ms'] for r in rs])} | "
          f"{', '.join(str(x['during_the_flood']) for x in other) + ' of ' + str(other[0]['sung']) if other else '–'} | "
          f"{span([r['kernel_drops'] for r in rs])} ({span([r['reported_socket_dropped'] for r in rs])}) | {refused} | "
          f"{median(r['bad_signature'] or 0 for r in rs):,.0f} | "
          f"{'–' if rc[0] is None or rc[0].get('known') is None else span([c['known'] for c in rc]) + ', ' + span([c['displaced'] for c in rc])} | "
          f"{', '.join(sorted({x for r in rs for x in r['health_reasons_seen']})) or 'none'} | {verdict} |")
