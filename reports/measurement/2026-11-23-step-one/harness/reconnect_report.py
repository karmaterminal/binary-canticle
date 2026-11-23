"""Read the reconnect-storm cell and say, per restart: how long each binding took to catch up, what each
layer reported, how many items fell into the outage, whether a push said so, and whether anything was
pushed twice. Markdown on stdout; writes reconnect-analysis.json beside the cell.

    python reconnect_report.py <results>/reconnect/R1-reconnect-storm
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sys
from pathlib import Path


def main() -> int:
    d = Path(sys.argv[1])
    r = json.loads((d / "result.json").read_text())
    t0 = r["t_start_mono_ns"]
    actions = json.loads((d / "actions.json").read_text())
    timeline = json.loads((d / "timeline.json").read_text())
    rows = [x for x in timeline if "t_s" in x and "action" not in x]
    ev = [dict(e, t_s=round((e["t_ns"] - t0) / 1e9, 2)) for e in r.get("tap_events", [])]

    # producer send times (every item) and probe arrivals
    sent = []
    sp = d / "blast0.samples.csv.gz"
    if sp.exists():
        with gzip.open(sp, "rt") as f:
            for line in f:
                idem, t = line.strip().split(",")
                sent.append((idem, (int(t) - t0) / 1e9))
    arrived = {}
    fp = d / "tap.frames.csv.gz"
    if fp.exists():
        with gzip.open(fp, "rt") as f:
            rd = csv.reader(f)
            next(rd)
            for t_ns, conn, seq, idem, adm, disp, stream in rd:
                arrived.setdefault(idem, (int(t_ns) - t0) / 1e9)

    # daemon runs seen by the probe: hello times
    hellos = [e["t_s"] for e in ev if e["event"] == "hello"]
    outages = []
    kills = [(t, n) for t, n in actions if n in ("kill_daemon", "term_daemon", "kill_all")]
    for t, n in kills:
        back = next((h for h in hellos if h > t), None)
        lost = [i for i, ts in sent if t <= ts < (back if back is not None else 1e9)]
        reached = [i for i in lost if i in arrived]
        outages.append({"action": n, "at_s": t, "probe_saw_new_run_at_s": back,
                        "probe_outage_s": round(back - t, 2) if back else None,
                        "items_sent_in_outage": len(lost), "of_those_reached_daemon": len(reached)})

    # per ear: state, health and counts at 1 s, around each action
    def ear_track(ear):
        out = []
        for x in rows:
            e = x.get(ear)
            if e:
                out.append((x["t_s"], e.get("state"), e.get("receiveHealth"), tuple(e.get("reasons") or ()),
                            json.dumps(e.get("counts") or {}, sort_keys=True)))
        return out

    ears = sorted(k for k in rows[0] if k.startswith("ear")) if rows else []
    transitions = {}
    for ear in ears:
        tr, last = [], None
        for t, state, health, reasons, counts in ear_track(ear):
            key = (state, health, reasons, counts)
            if key != last:
                tr.append({"t_s": t, "state": state, "receiveHealth": health, "reasons": list(reasons),
                           "counts": json.loads(counts)})
                last = key
        transitions[ear] = tr

    # pushes: lateness and loss lines after each action; anything pushed twice
    pushes = {}
    dup = {}
    for ear in ears:
        p = d / f"session{ear[3:]}.pushes.jsonl"
        rows_p = [json.loads(l) for l in open(p)] if p.exists() else []
        seen = {}
        lst = []
        for x in rows_p:
            if x.get("meta", {}).get("kind") != "canticle":
                lst.append({"t_s": round((x["t_ns"] - t0) / 1e9, 2), "kind": x.get("meta", {}).get("kind")})
                continue
            ts = round((x["t_ns"] - t0) / 1e9, 2)
            for rec in x["records"]:
                k = tuple(rec)
                seen[k] = seen.get(k, 0) + 1
            lst.append({"t_s": ts, "records": len(x["records"]), "late": x.get("late_lines"),
                        "loss": x.get("loss_lines")})
        pushes[ear] = lst
        dup[ear] = sum(1 for v in seen.values() if v > 1)

    analysis = {"outages": outages, "transitions": transitions, "pushes": pushes, "pushed_twice": dup,
                "quiet_items": r.get("quiet_items"), "tap_events": ev}
    (d / "reconnect-analysis.json").write_text(json.dumps(analysis, indent=1))

    print("| restart | at s | probe saw the new run at s (outage) | items the producer sent meanwhile | of those, reached the daemon |")
    print("|---|---|---|---|---|")
    for o in outages:
        print(f"| {o['action']} | {o['at_s']} | {o['probe_saw_new_run_at_s']} ({o['probe_outage_s']} s) | "
              f"{o['items_sent_in_outage']} | {o['of_those_reached_daemon']} |")
    print()
    for ear in ears:
        print(f"**{ear}** transitions:")
        for t in transitions[ear]:
            print(f"- {t['t_s']} s: {t['state']} / {t['receiveHealth']} {t['reasons']} {t['counts']}")
        print(f"pushed twice: {dup[ear]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
