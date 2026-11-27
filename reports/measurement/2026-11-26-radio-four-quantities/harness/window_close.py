"""Reads, once the window has closed, what the receivers kept about it. Read-only, counts only.

- frond-ear's ``canticle_custody`` rows (one per record exposed to the seat ear's session, frond-ear#112/#161):
  those claimed inside the window, and, for context, every row since ``canticle.custody.since`` (custody is whole
  from then), by path (``immediate``/``report`` pushes, ``hear`` reads), mode and how far each got (claimed,
  offered by the host, echoed by the session). The store is opened read-only. No identity, digest or session.
- frond-ear's journal (``journalctl --user -u frond-ear.service``) inside the window: its structured log lines
  counted by ``event`` name. Nothing else of a line is kept.
- The host daemon's journal inside the window: its lines counted by record type (it logs only hello, fatal, bye).
- The OpenClaw canticle binding's heard journal (#97), inside the window and over all it retains: entries by kind;
  heard entries by disposition, source, class and whether the binding's tune names the stream. Never a payload,
  purpose, state key, idem or name.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

DAY = 86_400_000


def state(row: tuple) -> str:
    offered_at, echoed_at = row
    return "echoed" if echoed_at is not None else "offered" if offered_at is not None else "claimed"


def custody(t0: int, t1: int) -> dict:
    con = sqlite3.connect(f"file:{C.FROND_EAR_DB}?mode=ro", uri=True, timeout=5)
    try:
        since = con.execute("SELECT value FROM runtime_state WHERE name = 'canticle.custody.since'").fetchone()
        rows = con.execute("SELECT path, mode, shown, claimed_at, offered_at, echoed_at, echo_kind "
                           "FROM canticle_custody WHERE ear = ? ORDER BY claimed_at", (C.SEAT_EAR,)).fetchall()
        exposure = con.execute("SELECT COUNT(*) FROM canticle_exposure").fetchone()[0]
        batches = con.execute("SELECT COUNT(DISTINCT batch_id) FROM canticle_custody WHERE ear = ? AND batch_id "
                              "IS NOT NULL AND claimed_at BETWEEN ? AND ?", (C.SEAT_EAR, t0, t1)).fetchone()[0]
    finally:
        con.close()

    def tally(sel):
        out: dict = {}
        for path, mode, shown, _c, off, ech, kind in sel:
            k = "|".join([C.closed(path, {"immediate", "report", "hear"}), C.closed(mode), C.closed(shown),
                          state((off, ech)), C.closed(kind) or "-"])
            out[k] = out.get(k, 0) + 1
        return out

    inside = [r for r in rows if t0 <= r[3] <= t1]
    days: dict = {}
    for r in rows:
        d = datetime.datetime.fromtimestamp(r[3] / 1000, datetime.timezone.utc).date().isoformat()
        days[d] = days.get(d, 0) + 1
    return {
        "custody_since_ms": int(since[0]) if since else None,
        "window": {"rows": len(inside), "batches": batches, "by": tally(inside)},
        "all_retained": {"rows": len(rows), "first_claimed_at": rows[0][3] if rows else None,
                         "last_claimed_at": rows[-1][3] if rows else None, "by": tally(rows), "by_day_utc": days},
        "exposure_rows": exposure,
    }


def journal_events(unit: str, t0: int, t1: int, field: str) -> dict:
    p = subprocess.run(["journalctl", "--user", "-u", unit, "--since", f"@{t0 // 1000}", "--until",
                        f"@{-(-t1 // 1000)}", "-o", "cat", "--no-pager"], capture_output=True, timeout=120)
    counts: dict = {}
    lines = unparsed = 0
    for raw in p.stdout.splitlines():
        lines += 1
        try:
            obj = json.loads(raw)
            name = C.closed(obj.get(field)) if isinstance(obj, dict) else None
        except ValueError:
            name = None
        if name is None:
            unparsed += 1
            continue
        counts[name] = counts.get(name, 0) + 1
    return {"unit": unit, "lines": lines, "unparsed": unparsed, "by_" + field: dict(sorted(counts.items()))}


SEG = re.compile(r"^\d{12}\.jsonl$")


def openclaw_journal(t0: int, t1: int) -> dict:
    oc = C.openclaw_canticle_config()
    tune = list(((oc["config"].get("listen") or {}).get("tune")) or [])
    out = {}
    for b in sorted(os.listdir(C.OPENCLAW_CANTICLE)):
        jdir = os.path.join(C.OPENCLAW_CANTICLE, b, "journal")
        if not os.path.isdir(jdir):
            continue
        win: dict = {"by_kind": {}, "heard": {}, "heard_streams": set(), "heard_stations": set()}
        allr: dict = {"by_kind": {}, "first_at": None, "last_at": None, "entries": 0}
        bad = 0
        for name in sorted(f for f in os.listdir(jdir) if SEG.match(f)):
            with open(os.path.join(jdir, name), "rb") as fh:
                for raw in fh:
                    try:
                        e = json.loads(raw)
                    except ValueError:
                        bad += 1
                        continue
                    at, kind = e.get("at"), C.closed(e.get("kind"), {"heard", "withdrawn", "presence", "note"})
                    if not isinstance(at, int):
                        bad += 1
                        continue
                    allr["entries"] += 1
                    allr["by_kind"][kind] = allr["by_kind"].get(kind, 0) + 1
                    allr["first_at"] = at if allr["first_at"] is None else min(allr["first_at"], at)
                    allr["last_at"] = at if allr["last_at"] is None else max(allr["last_at"], at)
                    if not t0 <= at <= t1:
                        continue
                    win["by_kind"][kind] = win["by_kind"].get(kind, 0) + 1
                    if kind == "heard":
                        f = e.get("frame") or {}
                        k = "|".join([C.closed(e.get("disposition"), {"held", "muted", "self"}),
                                      C.closed(e.get("source"), {"live", "snapshot"}),
                                      C.closed(f.get("class"), C.CLASSES),
                                      "tuned" if C.tune_matches(tune, f.get("station"), f.get("stream")) else "untuned"])
                        win["heard"][k] = win["heard"].get(k, 0) + 1
                        win["heard_streams"].add(C.label("stream", f"{f.get('station')}:{f.get('stream')}"))
                        win["heard_stations"].add(C.label("station", f.get("station")))
                    elif kind == "note":
                        n = e.get("note") or {}
                        nk = "note:" + (C.closed(n.get("kind")) or "none")
                        win["by_kind"][nk] = win["by_kind"].get(nk, 0) + 1
        win["heard_streams"] = len(win["heard_streams"])
        win["heard_stations"] = len(win["heard_stations"])
        out[C.label("binding", b)] = {"window": win, "all_retained": allr, "bad_lines": bad}
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--t0", type=int, required=True)
    p.add_argument("--t1", type=int, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    res = {"t0": a.t0, "t1": a.t1}
    for name, fn in (("custody", lambda: custody(a.t0, a.t1)),
                     ("frond_ear_journal", lambda: journal_events("frond-ear.service", a.t0, a.t1, "event")),
                     ("daemon_journal", lambda: journal_events("canticle-daemon.service", a.t0, a.t1, "type")),
                     ("openclaw_journal", lambda: openclaw_journal(a.t0, a.t1))):
        try:
            res[name] = fn()
        except Exception as e:
            res[name] = {"error": type(e).__name__}
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
