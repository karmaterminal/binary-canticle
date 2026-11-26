"""bench_offer.py's log as a table. Usage: bench_table.py <log>   (lines: round tree json; # lines are its header)"""

import json
import statistics
import sys
from collections import defaultdict

runs, trees, header = defaultdict(list), [], []
for line in open(sys.argv[1]):
    if line.startswith("#"):
        header.append(line[1:].strip())
        continue
    _, tree, js = line.split(" ", 2)
    r = json.loads(js)
    runs[r["shape"], tree].append(r["us_per_datagram"])
    if tree not in trees:
        trees.append(tree)
shapes = {"fixed": "40 ports held open", "fixed4": "4 ports held open", "churn": "churned", "replay": "old beacons replayed"}
print("; ".join(header))
print()
print("| flood | " + " | ".join(trees) + " |")
print("|---|" + "---|" * len(trees))
for shape, name in shapes.items():
    print(f"| {name} | " + " | ".join(f"{min(runs[shape, t]):.2f} ({statistics.median(runs[shape, t]):.2f}, {len(runs[shape, t])} runs)"
                                     for t in trees) + " |")
