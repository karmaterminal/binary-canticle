"""The #171 rerun rows, on #171's own harness (read only, at 7d46e4f2). Usage: rerun.py <harness dir> <out dir> <row,row|all> <duration> <drain>
The canticle under test is <harness>/../../../../prototype/canticle-station."""
import json, os, sys, time
from pathlib import Path
harness, out, rows, duration, drain = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
sys.path.insert(0, str(harness))
import cells, mlib
from mlib import PYTHON, Lab, free_udp_port, key_id_hex, loadavg, machine, percentile
HERE = Path(__file__).resolve().parent
base = dict(payload="64", prod_wake=False, ear_tune="none", quiet_interval=10, duration=duration, drain=drain, status_every=5, sample_every=0)
ROWS = {
    "F0-quiet-only": dict(producers=0),
    "R1-valid-other-key-4x-max": dict(prod_keys=4, mode="valid", rate=0, sample_every=1000),
    "R2-same-station": dict(producers=0, flood_station_rate=0, quiet_in_flood_station=True),
    "R3-forged-claiming-quiet-2x-max": dict(producers=0, custom="forged", custom_n=2),
    "R4a-replay-earlier-frames-2x-max": dict(producers=0, custom="earlier", custom_n=2),
    "R4b-replay-latest-item-2x-max": dict(producers=0, custom="latest", custom_n=2),
    "F2b-forged-own-key-2x-max": dict(prod_keys=2, mode="forged", rate=0),
    "F3b-unknown-key-2x-max": dict(prod_keys=2, mode="unknown-fixed", rate=0),
    "F4-replay-other-key-2x-max": dict(prod_keys=2, mode="dup", rate=0),
    "F5-real-station-flood": dict(producers=0, flood_station_rate=0),
    "F11-valid-1000ps": dict(producers=1, mode="valid", rate=1000, sample_every=1),
}
spawn = Lab.spawn
def patched(self, label, argv, **kw):
    if label == "station-quiet" and getattr(self, "captures", None):
        argv = list(argv) + [x for c in self.captures for x in ("--to", f"127.0.0.1:{c}")]
    return spawn(self, label, argv, **kw)
Lab.spawn = patched
out.mkdir(parents=True, exist_ok=True)
(out / "machine.json").write_text(json.dumps(machine(), indent=1))
for name, p in ROWS.items():
    if rows != "all" and not any(name.startswith(r) for r in rows.split(",")):
        continue
    p = {**base, "name": name, **p}
    custom, n = p.pop("custom", None), p.pop("custom_n", 0)
    captures = [free_udp_port() for _ in range(n)] if custom in ("earlier", "latest") else []
    init = Lab.__init__
    def patched_init(self, *a, **kw):
        init(self, *a, **kw); self.captures = captures
    cells.Lab.__init__ = patched_init
    def start_floods(lab):
        for i in range(n):
            argv = [PYTHON, HERE / "flood_rows.py", custom, "--target", f"127.0.0.1:{lab.port}", "--kid", key_id_hex(lab.keys["quiet"]),
                    "--epoch", int(time.time()), "--duration", duration - 0.1, "--index", i, "--summary", lab.logs / f"x{custom}{i}.json"]
            if captures:
                argv += ["--capture", captures[i]]
            lab.spawn(f"x{custom}{i}", argv)
    waited = 0
    while loadavg() > os.cpu_count() and waited < 300:
        time.sleep(10); waited += 10
    p["waited_for_load_s"] = waited
    load0 = loadavg()
    try:
        r = cells.run_cell(p, out / name, actions=[(0.0, start_floods)] if custom else None)
    finally:
        cells.Lab.__init__ = init
    h = r.get("daemon_health_last") or {}
    healths = cells.read_jsonl(out / name / "health.jsonl")
    q = r.get("quiet") or {}
    lat = q.get("send_to_record_ms") or []
    push = [v["ear0"] for v in (q.get("send_to_push_ms") or {}).values() if "ear0" in v]
    during = [x for x in r.get("quiet_items", []) if x["at_daemon_s"] is not None and x["at_daemon_s"] <= duration]
    def dist(xs):
        return {k: round(percentile(xs, v), 1) for k, v in (("p50", 50), ("p90", 90), ("p99", 99), ("max", 100))} if xs else None
    row = {"row": name, "offered_per_s": r.get("offered_rate") or (r.get("flood_station") or {}).get("rate"), "sung": q.get("sung"),
           "at_daemon": len(lat), "at_daemon_during_flood": len(during), "pushed": (q.get("pushed_per_ear") or {}).get("ear0"),
           "send_to_record_ms": dist(lat), "send_to_push_ms": dist(push), "kernel_drops": r.get("kernel_drops"),
           "reported_socket_dropped": (h.get("records") or {}).get("socket_dropped"), "receive": h.get("receive"),
           "health_reasons_seen": sorted({x for g in healths for x in g.get("reasons", [])}),
           "admission": {k: v for k, v in h.get("counters", {}).get("admission", {}).items() if v},
           "unverified": {k: v for k, v in h.get("counters", {}).get("unverified", {}).items() if v},
           "ear_live_overflow": ((r.get("frond_ear", {}).get("ear0") or {}).get("counts") or {}).get("live_overflow"),
           "daemon_cpu_rss": {k: v for k, v in (r.get("processes", {}).get("canticle-daemon") or {}).items() if k in ("cpu_mean", "cpu_max", "rss_max_kb")},
           "load_at_start": load0, "duration_s": duration, "drain_s": drain}
    (out / name / "row.json").write_text(json.dumps(row, indent=1))
    print(json.dumps(row), flush=True)
