"""Turn results/<scenario>/<cell>/result.json into the report's tables (markdown on stdout) and
results/summary.json. Every number in the README's tables comes from here.

    python summarize.py <results dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


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


def flood_table(rows) -> str:
    out = ["| cell | flood offered/s | kernel drops (share of all datagrams) | daemon verified/s | daemon health says | "
           "quiet sung → at daemon → pushed | pushes (max records/push) | frond-ear says | daemon RSS max / CPU mean | "
           "frond-ear RSS max / CPU mean | load avg max |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["params"]
        h, c = health_delta(r)
        sent = r.get("offered") or 0
        fs = r.get("flood_station") or {}
        q = r.get("quiet") or {}
        drops = r.get("kernel_drops")
        total_in = (r.get("snmp_delta") or {}).get("InDatagrams", 0) + (drops or 0)
        share = f"{100 * drops / total_in:.2f} %" if drops and total_in else "0"
        unv = {k: v for k, v in (c.get("unverified") or {}).items() if v}
        adm = {k: v for k, v in (c.get("admission") or {}).items() if v}
        says = f"state {h.get('state')}, reasons {h.get('reasons')}, records.dropped {(h.get('records') or {}).get('dropped')}"
        if unv:
            says += f", unverified {unv}"
        says += f", admission {adm}"
        fe = (r.get("frond_ear") or {}).get("ear0") or {}
        fe_says = f"{fe.get('receiveHealth')} {fe.get('reasons')} {fe.get('counts')}"
        pushes = (r.get("pushes") or {}).get("ear0") or {}
        load_max = r.get("load_max")
        out.append("| " + " | ".join([
            p["name"], num(r.get("offered_rate"), 0) if sent else (num(fs.get("rate"), 0) + " sings/s" if fs else "0"),
            f"{num(drops)} ({share})", num(r.get("probe_verified_rate_in_window"), 1), says,
            f"{q.get('sung')} → {q.get('reached_daemon')} → {(q.get('pushed_per_ear') or {}).get('ear0')}",
            f"{pushes.get('pushes')} ({pushes.get('records_per_push_max')})", fe_says,
            f"{mb(proc(r, 'canticle-daemon').get('rss_max_kb'))} MiB / {proc(r, 'canticle-daemon').get('cpu_mean')} %",
            f"{mb(proc(r, 'frond-ear-ear0').get('rss_max_kb'))} MiB / {proc(r, 'frond-ear-ear0').get('cpu_mean')} %",
            num(load_max, 1),
        ]) + " |")
    return "\n".join(out)


def ingest_table(rows) -> str:
    out = ["| ears | streams | payload (frame B) | saturated: offered/s → verified/s, kernel drops | 40/s: send→record p50 / p99 ms | "
           "40/s: send→push p50 / p99 ms (n) | daemon CPU % sat / 40 | daemon RSS MiB | frond-ear CPU % / RSS MiB (mean of ears) | "
           "shim RSS MiB | probe gaps | frond-ear counts |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    by = {}
    for r in rows:
        p = r["params"]
        key = (p["ears"], p["streams"], p["payload"])
        by.setdefault(key, {})["sat" if p["name"].startswith("I-sat") else "lat"] = r
    for key in sorted(by, key=lambda k: (k[0], k[1], {"64": 0, "512": 1, "max": 2}[k[2]])):
        s, l = by[key].get("sat", {}), by[key].get("lat", {})
        ls = l.get("latency_send_to_record_ms") or {}
        lp = l.get("latency_send_to_push_ms") or {}
        shim = [v.get("rss_max_kb") for k, v in (s.get("processes") or {}).items() if k.startswith("shim")]
        fe_counts = {}
        for rr in (s, l):
            for ear, v in (rr.get("frond_ear") or {}).items():
                for k2, n in (v.get("counts") or {}).items():
                    if k2 != "joined_late":
                        fe_counts[k2] = fe_counts.get(k2, 0) + n
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
            json.dumps(fe_counts) if fe_counts else "{}",
        ]) + " |")
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
    root = Path(sys.argv[1])
    summary = {}
    for scen in ("flood", "ingest", "admission", "reconnect"):
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
        summary[scen] = rows
        print(f"\n### {scen}\n")
        if scen == "flood":
            print(flood_table(rows))
        elif scen == "ingest":
            print(ingest_table(rows))
        elif scen == "admission":
            print(admission_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
