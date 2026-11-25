"""Complete the cells whose runs were underdriven (PLAN.md, "Added ... underdriven runs"). Usage: complete.py <newcomer_rows.py's out.json> <name=tree:declared,...>

A run whose flood fell under 95 % of its rate in its lowest whole second is no evidence of the workload (🌫's comparator calls it INVALID), however it ended. It
stays in the raw file. Its cell gets another run, with the next number, under the same harness, until it has the declared number of valid ones, at most as many
again as were declared. Which cells are run again depends on the flood's rate alone, never on what the newcomer met."""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
out, trees = Path(sys.argv[1]), [t.split("=") for t in sys.argv[2].split(",")]


def valid(r):
    return r["cryptography"] == "50.0.1" and r["lowest_second"] >= 0.95 * int(r["row"].split("-")[2])


def lacking():
    cells = defaultdict(list)
    for r in json.loads(out.read_text()):
        cells[r["tree"], r["row"]].append(r)
    for name, spec in trees:
        tree, declared = spec.rsplit(":", 1)
        for (t, row), rs in sorted(cells.items()):
            if t == name and sum(map(valid, rs)) < int(declared) and len(rs) < 2 * int(declared):
                yield name, tree, row, max(r["run"] for r in rs) + 2


while (todo := list(lacking())):
    for name, tree, row, runs in todo:
        print("completing", name, row, "run", runs - 1, flush=True)
        subprocess.run([sys.executable, str(HERE / "newcomer_rows.py"), str(out), f"{name}={tree}:{runs}", row], check=True)
