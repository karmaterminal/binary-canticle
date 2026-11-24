"""Pass 2's rows (cold start, exact-source spoof, relay-first, churn-established) as a matrix, a column per tree. Usage: scaled_compare.py <dir> <name,...>
reads <dir>/scaled-<name>.json of pass 2's scaled_rows.py. In a cell: the verdict by that script's own bounds (20 of 20 or 57 of 57 during the flood, p50
at most 250 ms, none later than 4.5 s, the kernel's drops reported; ``outside`` for the two rows pass 2 says are outside the guarantee), the items over
the runs, and the first valid frame, ms. Pass 3's 1.0 s / 2.0 s deadline is not this bound."""

import json
import sys
from collections import defaultdict

OUTSIDE = {"spoof-exact-source-100000", "relay-first-then-churn-100000"}
d, names = sys.argv[1], sys.argv[2].split(",")
rows, order = defaultdict(list), []
for n in names:
    for r in json.load(open(f"{d}/scaled-{n}.json")):
        assert r["cryptography"] == "50.0.1", (n, r["row"])
        rows[r["row"], n].append(r)
        if r["row"] not in order:
            order.append(r["row"])
print("| row | " + " | ".join(names) + " |")
print("|---" * (len(names) + 1) + "|")
for row in order:
    out = []
    for n in names:
        rs = rows[row, n]
        s = [r["station"] for r in rs]
        ok = all(x["during_the_flood"] == x["sung"] and x["latency_ms"]["p50"] <= 250 and x["latency_ms"]["max"] <= 4500 for x in s)
        told = all(r["kernel_drops"] == (r["reported_socket_dropped"] or 0) for r in rs)
        first = [r["first_valid_frame_ms"] for r in rs if r["first_valid_frame_ms"] is not None]
        late = max((x["latency_ms"]["max"] if x["latency_ms"] else 0) for x in s)
        items = ", ".join(str(x["during_the_flood"]) for x in s)
        v = "PASS" if ok and told else "**FAIL** (outside the supported guarantee)" if not ok and row in OUTSIDE else "**FAIL**"
        out.append(f"{v}; {items} of {s[0]['sung']}; max {late:,.0f} ms" + (f"; first {min(first):,.0f}-{max(first):,.0f} ms" if first else ""))
    print(f"| {row} | " + " | ".join(out) + " |")
