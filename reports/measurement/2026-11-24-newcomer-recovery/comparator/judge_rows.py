"""🌫's acceptance comparator (``oracle.py``, verbatim from #173, issuecomment-7119143235) run on this report's raw runs.

Usage: judge_rows.py <results/*.json of newcomer_rows.py | a full-length run directory of rerun.py>...

``newcomer_rows.py``'s runs: one clock (CLOCK_MONOTONIC), zero at the newcomer's first actual send. Every run is judged twice, and the
two are never substituted for one another: its first valid frame, beacon or item (1.0 s), and its 20 items (2.0 s each). The
expected items are PLAN.md's 20, never what was admitted. The recipient is the local client, the only one these runs
have: nothing here speaks for an ear. An observation after the flood's end is not in the raw file, so it is missing, as it must be.
Before a run is judged it must have run as declared: cryptography 50.0.1, its 20 items sung, and the flood at 95 % of its rate
or more in its lowest whole second. A run that did not is INVALID and passes nothing. So is one whose rate floor is not a finite nonnegative
number, or whose producer sang another number of items than it lists (🌫's hardening, #173 issuecomment-7125278653). An INVALID run
stays in the raw file and in this table; its cell needs the declared number of valid ones (complete.py), and a deadline missed in an invalid
run fails the cell as well: an underdriven flood is the easier one.

``rerun.py``'s: ``result.json``'s ``quiet_items`` are the comparator's own shape. 57 (R) or 30 (F) expected; at the daemon 4.5 s, gate 1's
bound. The push stage has no bound of its own (frond-ear waits 5 s by design): only its missing items are printed.

``established_rows.py`` and ``scaled_rows.py`` keep percentiles and counts per run, not items, so the comparator can't be run on
them. They are gated on their counts (57 of 57 during the flood) and their maximum."""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from oracle import judge

DECLARED = {"slice": 5, "base": 3, "head": 3, "nobudget-177": 5, "nobudget": 3}
LOCKED, FIRST_S, ITEM_S, ITEMS, GATE1_S = "50.0.1", 1.0, 2.0, 20, 4.5


def newcomer(r: dict) -> dict:
    rate = int(r["row"].split("-")[2])
    if r["cryptography"] != LOCKED:
        raise ValueError(f"cryptography {r['cryptography']}")
    low = r["lowest_second"]
    if isinstance(low, bool) or not isinstance(low, (int, float)) or not math.isfinite(low) or low < 0:
        raise ValueError("finite nonnegative lowest_second required")
    if isinstance(r["sung"], bool) or r["sung"] != ITEMS or len(r["items"]) != ITEMS:
        raise ValueError("declared producer count not met")
    if r["lowest_second"] < 0.95 * rate:
        raise ValueError(f"underdriven: {r['lowest_second']} of {rate} in its lowest second")
    expected = [f"item-{i}" for i in range(ITEMS)]
    items = [{"idem": f"item-{i}", "sung_at_s": x["sent_s"],
              "pushed_at_s": None if x["latency_s"] is None else {"client": x["sent_s"] + x["latency_s"]}}
             for i, x in enumerate(r["items"])]
    end = r["items"][-1]["sent_s"] + r["flood_end_after_last_item_sent_s"]
    first = r["first_valid_frame_s"]
    window = dict(stage="push:client", flood_end_s=end, captured_until_s=end)
    return {"first": judge([{"idem": "first-frame", "sung_at_s": 0.0, "pushed_at_s": None if first is None else {"client": first}}],
                           ["first-frame"], budget_s=FIRST_S, **window),
            "items": judge(items, expected, budget_s=ITEM_S, **window)}


def full(path: Path) -> None:
    row, res = json.loads((path / "row.json").read_text()), json.loads((path / "result.json").read_text())
    n, end = (57, 570.0) if path.name.startswith("R") else (30, 300.0)
    try:
        if row["cryptography"] != LOCKED or row["duration_s"] != end:
            raise ValueError("not the pinned runtime, or not the declared length")
        items = res["quiet_items"]
        if len(items) != n:
            raise ValueError(f"{len(items)} sung of {n} declared")
        ids = [x["idem"] for x in items]
        at = judge(items, ids, stage="at_daemon_s", flood_end_s=end, captured_until_s=end + row["drain_s"], budget_s=GATE1_S)
        ear = sum((x["pushed_at_s"] or {}).get("ear0") is None for x in items)
        told = row["kernel_drops"] == (row["reported_socket_dropped"] or 0)
        print(f"| {path.parent.parent.name} | {path.parent.name} | {path.name} | {at['on_time']} of {at['expected']} | {at['late']} | "
              f"{at['missing']} | {at['catchup_after_flood']} | {ear} | {'yes' if told else 'NO'} | "
              f"{'PASS' if at['pass'] and told and not ear else '**FAIL**'} |")
    except ValueError as e:
        print(f"| {path.parent.parent.name} | {path.parent.name} | {path.name} | – | – | – | – | – | – | **INVALID**: {e} |")


def main() -> None:
    files = [Path(a) for a in sys.argv[1:]]
    cells, bad = defaultdict(list), 0
    for f in files:
        if f.is_file():
            for r in json.loads(f.read_text()):
                cells[r["row"], r["tree"]].append(r)
    if cells:
        print("| row | tree | runs judged | first frame: on time / late / missing | items: on time / late / missing, of 20 a run | verdict | the harness's own "
              "verdict |")
        print("|---|---|---|---|---|---|---|")
    key = lambda k: (k[0].split("-")[0], int(k[0].split("-")[2]), int(k[0].split("-")[1]), float(k[0].split("-")[3]), k[1])
    for row, tree in sorted(cells, key=key):
        rs, got, invalid = cells[row, tree], [], []
        for r in rs:
            try:
                got.append(newcomer(r))
            except ValueError as e:
                invalid.append(f"run {r['run']}: {e}")
        s = lambda w, k: sum(g[w][k] for g in got)
        missed = any(not (g["first"]["pass"] and g["items"]["pass"]) for g in got)
        missed_too = any(r["first_miss"] or r["item_misses"] for r in rs)
        short = len(got) < DECLARED.get(tree, 5)
        verdict = "**FAIL**" if missed or missed_too else f"**INVALID**, {len(got)} of {DECLARED.get(tree, 5)} declared" if short else "PASS"
        own = not missed_too
        bad += (verdict == "PASS") != own or short
        print(f"| {row} | {tree} | {len(got)} of {len(rs)} | {s('first', 'on_time')} / {s('first', 'late')} / {s('first', 'missing')} | "
              f"{s('items', 'on_time')} / {s('items', 'late')} / {s('items', 'missing')} | {verdict}"
              f"{' (' + '; '.join(invalid) + ')' if invalid else ''} | {'PASS' if own else 'FAIL'}"
              f"{'' if (verdict == 'PASS') == own else ' **(they differ)**'} |")
    dirs = [d for f in files if f.is_dir() for d in sorted(f.glob("*/row.json"))]
    if dirs:
        print("| tree | run | row | on time (4.5 s) at the daemon, during the flood | late | missing | caught up after the flood | not pushed to the ear | "
              "the kernel's drops reported | verdict |")
        print("|---|---|---|---|---|---|---|---|---|---|")
    for d in dirs:
        full(d.parent)
    sys.exit(f"{bad} cells where the two verdicts differ, or with too few valid runs" if bad else 0)


if __name__ == "__main__":
    main()
