"""The full-length rows (#171's harness, rerun.py) as a matrix, judged by 🌫's comparator: a line per row, a column per tree.
Usage: full_table.py <results/full> <tree,...>   reads <dir>/<tree>/run<n>/<row>/{row,result}.json
In a cell: runs that passed of runs, and, over the runs, items on time (4.5 s) of 57 (R) or 30 (F). A run passes when every item was at the
daemon in time during the flood, the kernel's drops were reported, and every item was pushed to the ear (the push stage has no bound of its own:
only its missing items count). A run on another cryptography, or not of the declared length, is INVALID."""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "comparator"))
from oracle import judge        # noqa: E402

LOCKED, GATE1_S = "50.0.1", 4.5
root, trees = Path(sys.argv[1]), sys.argv[2].split(",")
cells = defaultdict(list)
for t in trees:
    for path in sorted(root.glob(f"{t}/run*/*/row.json")):
        row, res = json.loads(path.read_text()), json.loads((path.parent / "result.json").read_text())
        n, end = (57, 570.0) if path.parent.name.startswith("R") else (30, 300.0)
        items = res["quiet_items"]
        if row["cryptography"] != LOCKED or row["duration_s"] != end or len(items) != n:
            cells[path.parent.name, t].append(None)
            continue
        at = judge(items, [x["idem"] for x in items], stage="at_daemon_s", flood_end_s=end, captured_until_s=end + row["drain_s"], budget_s=GATE1_S)
        told = row["kernel_drops"] == (row["reported_socket_dropped"] or 0)
        unpushed = sum((x["pushed_at_s"] or {}).get("ear0") is None for x in items)
        cells[path.parent.name, t].append((at["pass"] and told and not unpushed, at["on_time"], n))
order = lambda name: (0 if name.startswith("R") else 1, name)
print("| row | " + " | ".join(trees) + " |")
print("|---" * (len(trees) + 1) + "|")
passed = {t: [0, 0] for t in trees}
for name in sorted({k[0] for k in cells}, key=order):
    out = []
    for t in trees:
        rs = cells.get((name, t))
        if not rs:
            out.append("–")
            continue
        ok = sum(r is not None and r[0] for r in rs)
        passed[t][0] += ok == len(rs)
        passed[t][1] += 1
        out.append(f"{'PASS' if ok == len(rs) else '**FAIL**'}: {ok} of {len(rs)} runs; on time {', '.join('invalid' if r is None else f'{r[1]} of {r[2]}' for r in rs)}")
    print(f"| {name} | " + " | ".join(out) + " |")
print("| **rows passed** | " + " | ".join(f"**{passed[t][0]} of {passed[t][1]}**" for t in trees) + " |")
