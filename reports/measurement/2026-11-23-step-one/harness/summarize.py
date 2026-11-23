"""Turn results/<scenario>/<cell>/result.json into the README's §1, §3 and §4 tables (markdown on
stdout) and results/summary.json. Every number in those tables comes from here; --check confirms that
each table it prints appears in the README byte for byte.

    python summarize.py <results dir> [--check <README.md>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FLOOD_SCENARIOS = ("flood", "flood2", "flood3")

# The daemon's own health counter for what each flood mode offers: overload's denominator.
PROCESSED_AS = {"valid": "admission.verified", "dup": "admission.duplicate", "forged": "unverified.bad_signature",
                "unknown": "unverified.unknown_key", "unknown-fixed": "unverified.unknown_key"}


def load(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*/result.json")):
        out.append(json.loads(f.read_text()))
    return out


def mb(kb):
    return f"{kb / 1024:.0f}" if kb is not None else "–"


def num(v, nd=0):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:,.{nd}f}"
    return f"{v:,}"


def proc(r, label):
    return (r.get("processes") or {}).get(label) or {}


def ears_avg(r, key):
    vals = [v[key] for k, v in (r.get("processes") or {}).items() if k.startswith("frond-ear-") and key in v]
    return sum(vals) / len(vals) if vals else None


def ears_max(r, key):
    vals = [v[key] for k, v in (r.get("processes") or {}).items() if k.startswith("frond-ear-") and key in v]
    return max(vals) if vals else None


def health_delta(r):
    """The daemon's counters over the cell: last health record of the probe (the run started at zero)."""
    h = r.get("daemon_health_last") or {}
    c = h.get("counters") or {}
    return h, c


def health_rates(d: Path, r: dict) -> dict:
    """Per-second rates of the daemon's own counters over the producers' window, from its health records
    (1 s apart): what the daemon says it did, as opposed to what was offered."""
    f = d / r["params"]["name"] / "health.jsonl"
    if not f.exists():
        return {}
    t0 = r.get("t_start_mono_ns", 0)
    dur = float(r["params"].get("duration", 30))
    hs = [json.loads(l) for l in open(f) if l.strip()]
    win = [h for h in hs if 2e9 <= h["t_ns"] - t0 <= (dur - 1) * 1e9]
    if len(win) < 2:
        return {}
    a, b = win[0], win[-1]
    dt = (b["t_ns"] - a["t_ns"]) / 1e9
    out = {}
    for group in ("admission", "unverified"):
        for k, v in b["counters"][group].items():
            dv = v - a["counters"][group].get(k, 0)
            if dv:
                out[f"{group}.{k}"] = round(dv / dt, 1)
    out["dedup_entries_end"] = b.get("dedup", {}).get("entries")
    return out


def quiet_split(r: dict) -> dict:
    """Quiet items sung while the flood ran vs after it stopped, and what became of each."""
    items = r.get("quiet_items")
    if not items:
        return {}
    dur = float(r["params"].get("duration", 30))
    during = [i for i in items if i["sung_at_s"] < dur]
    def fate(xs, until):
        return {"sung": len(xs),
                "at_daemon_during_flood": sum(1 for i in xs if i["at_daemon_s"] is not None and i["at_daemon_s"] < until),
                "at_daemon_after_flood": sum(1 for i in xs if i["at_daemon_s"] is not None and i["at_daemon_s"] >= until),
                "pushed_during_flood": sum(1 for i in xs if i["pushed_at_s"] and min(i["pushed_at_s"].values()) < until),
                "pushed_after_flood": sum(1 for i in xs if i["pushed_at_s"] and min(i["pushed_at_s"].values()) >= until)}
    return fate(during, dur)


def cell_order(r: dict) -> tuple:
    """F0, F1, F1b, F2b, F3, F3b, …, F9, F10, F11: by the number in the cell's name, then its suffix."""
    m = re.match(r"[A-Z]+(\d+)([a-z]*)-", r["params"]["name"])
    return (int(m.group(1)), m.group(2)) if m else (sys.maxsize, r["params"]["name"])


def daemon_reads(r: dict) -> int:
    """Datagrams the daemon read from its socket: the sum of its own admission, beacon and unverified
    counters in its last health record (the run started at zero)."""
    _, c = health_delta(r)
    return sum(sum((c.get(group) or {}).values()) for group in ("admission", "beacon", "unverified"))


def drops_cell(r: dict) -> str:
    """The daemon socket's own kernel drops, with their socket-local share: drops ÷ (drops + the
    datagrams the daemon read), the share of the datagrams that reached that socket."""
    drops = r.get("kernel_drops")
    if not drops:
        return num(drops)
    return f"{num(drops)} ({100 * drops / (drops + daemon_reads(r)):.2f} %)"


def two_figures(x: float) -> str:
    """x to two significant figures, trailing zeros dropped as %g drops them: 4 200, 63, 4.9, 1."""
    v = float(f"{x:.2g}")
    return f"{v:,.0f}".replace(",", " ") if v >= 10 else f"{v:g}"


def offered_rate(r: dict):
    """What the flood offered per second: the producers' sends, or the flooding station's sings."""
    if r.get("offered"):
        return r.get("offered_rate")
    return (r.get("flood_station") or {}).get("rate")


def overload_cell(r: dict) -> str:
    """What the flood offered per second ÷ what the daemon processed of that kind per second, from its
    own health rates (PROCESSED_AS). A flood its socket dropped none of is under 1×."""
    offered = offered_rate(r)
    if not offered:
        return "–"
    if r.get("kernel_drops") == 0:
        return "< 1× (0 socket drops)"
    processed = (r.get("health_rates") or {}).get(PROCESSED_AS[r["params"].get("mode", "valid")])
    return f"≈ {two_figures(offered / processed)}×" if processed else "–"


def flood_tables(rows) -> list[str]:
    a = ["| cell | offered | daemon's own rates (per s, from its health) | daemon CPU mean | kernel drops at the daemon's socket, its own `drops` (share of the datagrams that reached the socket) | "
         "what the daemon's health said | what frond-ear said | load avg max |",
         "|---|---|---|---|---|---|---|---|"]
    b = ["| cell | overload | quiet items sung while the flood ran | of those, reached the daemon during / after the flood | of those, pushed during / after the flood | "
         "pushes in all (max records per push) | daemon RSS max (MiB) | frond-ear RSS start → max (MiB) | shim RSS max (MiB) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["params"]
        h, c = health_delta(r)
        fs = r.get("flood_station") or {}
        if r.get("offered"):
            offered = f"{num(r.get('offered_rate'), 0)} {p.get('mode', 'valid')} items/s ({r.get('frame_bytes')} B)"
        elif fs:
            offered = f"real station, {num(fs.get('rate'), 0)} sings/s"
        else:
            offered = "none"
        rates = r.get("health_rates") or {}
        rate_s = ", ".join(f"{k.split('.', 1)[1]} {num(v, 1)}" for k, v in rates.items() if k != "dedup_entries_end")
        says = f"`{h.get('state')}`, reasons {h.get('reasons')}, records dropped {(h.get('records') or {}).get('dropped')}"
        fe = (r.get("frond_ear") or {}).get("ear0") or {}
        fe_counts = {k: v for k, v in (fe.get("counts") or {}).items() if k != "joined_late"}
        fe_says = f"`{fe.get('receiveHealth')}` {fe.get('reasons')} {fe_counts or ''}".strip()
        dcounts = ((fe.get("canticleDelivery") or {}).get("counts")) or {}
        if dcounts:
            fe_says += f"; delivery {dcounts}"
        a.append("| " + " | ".join([p["name"], offered, rate_s or "–", f"{proc(r, 'canticle-daemon').get('cpu_mean')} %",
                                    drops_cell(r), says, fe_says, num(r.get("load_max"), 1)]) + " |")
        q = r.get("quiet_split") or {}
        qq = r.get("quiet") or {}
        if q:
            sung = str(q["sung"])
            reach = f"{q['at_daemon_during_flood']} / {q['at_daemon_after_flood']}"
            pushed = f"{q['pushed_during_flood']} / {q['pushed_after_flood']}"
        else:
            sung = f"{qq.get('sung')} (whole run)"
            reach = f"{qq.get('reached_daemon')} in all (no per-item timing in this cell)"
            pushed = str((qq.get("pushed_per_ear") or {}).get("ear0"))
        pu = (r.get("pushes") or {}).get("ear0") or {}
        fe_p = proc(r, "frond-ear-ear0")
        b.append("| " + " | ".join([p["name"], overload_cell(r), sung, reach, pushed,
                                    f"{pu.get('pushes')} ({pu.get('records_per_push_max')})",
                                    mb(proc(r, 'canticle-daemon').get('rss_max_kb')),
                                    f"{mb(fe_p.get('rss_first_kb'))} → {mb(fe_p.get('rss_max_kb'))}",
                                    mb(proc(r, 'shim0').get('rss_max_kb'))]) + " |")
    return ["\n".join(a), "\n".join(b)]


def ingest_table(rows) -> str:
    out = ["| ears | streams | payload (frame B) | saturated: offered/s → verified/s, kernel drops (the daemon socket's own `drops`) | "
           "40/s: send→record p50 / p99 ms | 40/s: send→push p50 / p99 ms (n) | daemon CPU % sat / 40 | daemon RSS MiB | "
           "frond-ear CPU % (mean of ears) / RSS MiB (max of ears), saturated cell | shim RSS MiB | probe gaps sat / 40 | "
           "frond-ear loss counts: receive side (all ears, both cells); delivery (ear0, 40/s cell) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    by = {}
    for r in rows:
        p = r["params"]
        if not p["name"].startswith("I-"):
            continue
        key = (p["ears"], p["streams"], p["payload"])
        by.setdefault(key, {})["sat" if p["name"].startswith("I-sat") else "lat"] = r
    for key in sorted(by, key=lambda k: (k[0], k[1], {"64": 0, "512": 1, "max": 2}[k[2]])):
        s, l = by[key].get("sat", {}), by[key].get("lat", {})
        ls = l.get("latency_send_to_record_ms") or {}
        lp = l.get("latency_send_to_push_ms") or {}
        shim = [v.get("rss_max_kb") for k, v in (s.get("processes") or {}).items() if k.startswith("shim")]
        recv = {}
        for rr in (s, l):
            for ear, v in (rr.get("frond_ear") or {}).items():
                for k2, n in (v.get("counts") or {}).items():
                    if k2 != "joined_late":
                        recv[k2] = recv.get(k2, 0) + n
        dl = ((((l.get("frond_ear") or {}).get("ear0") or {}).get("canticleDelivery") or {}).get("counts") or {})
        fe_counts = f"receive {json.dumps(recv) if recv else 'none'}; 40/s delivery: pushed {dl.get('records_pushed', 0)}, " \
                    f"dropped {dl.get('dropped', 0)}, late {dl.get('routed_late', 0)}"
        out.append("| " + " | ".join([
            str(key[0]), num(key[1]), f"{key[2]} ({s.get('frame_bytes')})",
            f"{num(s.get('offered_rate'), 0)} → {num(s.get('probe_verified_rate_in_window'), 1)}, {num(s.get('kernel_drops'))}",
            f"{num(ls.get('p50'), 1)} / {num(ls.get('p99'), 1)}",
            f"{num(lp.get('p50'), 0)} / {num(lp.get('p99'), 0)} ({lp.get('n')})",
            f"{proc(s, 'canticle-daemon').get('cpu_mean')} / {proc(l, 'canticle-daemon').get('cpu_mean')}",
            mb(max(proc(s, 'canticle-daemon').get('rss_max_kb') or 0, proc(l, 'canticle-daemon').get('rss_max_kb') or 0)),
            f"{num(ears_avg(s, 'cpu_mean'), 1)} / {mb(ears_max(s, 'rss_max_kb'))}",
            mb(max(shim) if shim else None),
            f"{(s.get('tap') or {}).get('rec_seq_gap_records')} / {(l.get('tap') or {}).get('rec_seq_gap_records')}",
            fe_counts,
        ]) + " |")
    return "\n".join(out)


def tune_table(rows) -> str:
    out = ["| tuned streams (all of the producer's) | offered/s | verified/s | send→push p50 / p99 ms (n) | pushes (records) | "
           "frond-ear CPU % mean / max | frond-ear RSS MiB | delivery counts |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["params"]
        if not p["name"].startswith("T-"):
            continue
        lp = r.get("latency_send_to_push_ms") or {}
        fe = proc(r, "frond-ear-ear0")
        pu = (r.get("pushes") or {}).get("ear0") or {}
        dc = (((r.get("frond_ear") or {}).get("ear0") or {}).get("canticleDelivery") or {}).get("counts")
        out.append("| " + " | ".join([num(p["streams"]), num(r.get("offered_rate"), 1),
                                      num(r.get("probe_verified_rate_in_window"), 1),
                                      f"{num(lp.get('p50'), 0)} / {num(lp.get('p99'), 0)} ({lp.get('n')})",
                                      f"{pu.get('pushes')} ({pu.get('records')})",
                                      f"{fe.get('cpu_mean')} / {fe.get('cpu_max')}", mb(fe.get("rss_max_kb")),
                                      json.dumps(dc)]) + " |")
    return "\n".join(out)


def admission_table(rows) -> str:
    out = ["| cell | duration s | offered items | reached the ear (verified records) | pushes | records pushed | max records/push | "
           "pushes/hour cap | held at end | delivery counts |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["params"]
        fe = ((r.get("frond_ear") or {}).get("ear0") or {}).get("canticleDelivery") or {}
        pu = (r.get("pushes") or {}).get("ear0") or {}
        out.append("| " + " | ".join([
            p["name"], str(p["duration"]), num(r.get("offered")), num(r.get("probe_verified_frames")),
            str(pu.get("pushes")), str(pu.get("records")), str(pu.get("records_per_push_max")),
            str(fe.get("maxPushesPerHour")), str(fe.get("held")), json.dumps(fe.get("counts")),
        ]) + " |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--check", type=Path, metavar="README",
                    help="exit 1 unless every table printed appears in this file byte for byte")
    args = ap.parse_args()
    root = args.results
    summary = {}
    for scen in ("flood", "flood2", "flood3", "ingest", "admission", "reconnect"):
        d = root / scen
        if not d.exists():
            continue
        rows = load(d)
        for r in rows:
            # load average over the cell, from the sampler
            s = d / r["params"]["name"] / "samples.csv"
            if s.exists():
                las = [float(l.rsplit(",", 1)[1]) for l in open(s).readlines()[1:] if l.strip()]
                r["load_max"] = max(las) if las else None
            fsj = d / r["params"]["name"] / "floodsinger.json"
            if fsj.exists():
                r["flood_station"] = json.loads(fsj.read_text())
            r["health_rates"] = health_rates(d, r)
            r["quiet_split"] = quiet_split(r)
        summary[scen] = rows
    sections = []
    floods = [s for s in FLOOD_SCENARIOS if s in summary]
    if floods:
        # §1 is one table pair for the three flood runs (see the README's *Run history*), in cell order.
        sections.append((f"§1 flood test ({', '.join(floods)})",
                         flood_tables(sorted((r for s in floods for r in summary[s]), key=cell_order))))
    if "ingest" in summary:
        sections.append(("§3 ingest", [ingest_table(summary["ingest"]), tune_table(summary["ingest"])]))
    if "admission" in summary:
        sections.append(("§4 admission", [admission_table(summary["admission"])]))
    for title, tables in sections:
        print(f"\n### {title}\n")
        print("\n\n".join(tables))
    (root / "summary.json").write_text(json.dumps(
        {k: [{kk: vv for kk, vv in r.items() if kk not in ("tap_events", "stderr")} for r in v] for k, v in summary.items()},
        indent=1, default=str))
    if args.check:
        readme = "\n" + args.check.read_text() + "\n"
        missing = [t.split("\n", 1)[0][:100] for _, tables in sections for t in tables if f"\n{t}\n" not in readme]
        for header in missing:
            print(f"not in {args.check} byte for byte: {header}…", file=sys.stderr)
        if missing:
            return 1
        print(f"\nall {sum(len(t) for _, t in sections)} tables appear in {args.check} byte for byte", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
