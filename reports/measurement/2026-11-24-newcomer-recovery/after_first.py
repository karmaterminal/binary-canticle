"""Whether a late item is late because nothing of the newcomer had been heard yet. Usage: after_first.py <newcomer_rows.py's out.json>... [name,...]
Every item is put on one side of its run's first valid frame by when its first copy was sent. A lost item counts as infinite, and all of
a run's items are before when nothing was heard."""

import json
import sys
from collections import defaultdict
from math import inf
from statistics import median

names = next((a.split(",") for a in sys.argv[1:] if not a.endswith(".json")), None)
sides = defaultdict(lambda: ([], []))
for f in (a for a in sys.argv[1:] if a.endswith(".json")):
    for r in json.load(open(f)):
        if names is None or r["tree"] in names:
            first = r["first_valid_frame_s"]
            for x in r["items"]:
                sides[r["tree"], int(r["row"].split("-")[2])][first is not None and x["sent_s"] > first].append(
                    inf if x["latency_s"] is None else x["latency_s"])
s = lambda x: "lost" if x == inf else f"{x:.3f}"
print("| tree | R, /s | items sung before its first valid frame was heard | later than 2.0 s or lost | items sung after it | latency, s: median, max | "
      "later than 2.0 s or lost |")
print("|---|---|---|---|---|---|---|")
for (tree, rate), (before, after) in sorted(sides.items(), key=lambda kv: (names.index(kv[0][0]) if names else kv[0][0], kv[0][1])):
    print(f"| {tree} | {rate:,} | {len(before)} | {sum(x > 2.0 for x in before)} | {len(after)} | "
          f"{s(median(after)) + ', ' + s(max(after)) if after else '–'} | {sum(x > 2.0 for x in after)} |")
