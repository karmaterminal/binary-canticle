"""Check a synthetic-only web-lanes proof run; print and save summary.json.

    python analyze.py results/<run>

The dashboard lane is not a listener proof. The real listener evidence still comes from
listen-early.jsonl and listen-late.jsonl; the dashboard itself must expose only an explicit fixture.
"""

import json
import statistics
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
TTL_MS = 60_000


def jl(name):
    p = RUN / name
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def num(name):
    return int((RUN / name).read_text().strip())


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def dist(xs):
    return {"n": len(xs), "min": min(xs), "p50": pct(xs, 50), "p95": pct(xs, 95), "max": max(xs)} if xs else {"n": 0}


checks = []


def check(name, ok, detail):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


t0, late_start, emit_stop = num("t0_ms"), num("late_start_ms"), num("emit_stop_ms")
commit = (RUN / "source-commit").read_text().strip() if (RUN / "source-commit").exists() else None
dirty = [l for l in (RUN / "source-dirty").read_text().splitlines() if l.strip() and "results/" not in l] \
    if (RUN / "source-dirty").exists() else ["(not recorded)"]
check("ran from a clean, committed tree", commit and not dirty, {"commit": commit, "dirty": dirty[:5]})

# ---- emission (#58)
emitted = {}
emit_summary = {}
for stream, f in (("hymn", "emit-hymn.jsonl"), ("lens.weather", "emit-weather.jsonl")):
    recs = jl(f)
    if not recs:
        continue
    start, stop = recs[0], recs[-1]
    sings = [r for r in recs if r["event"] == "sing"]
    ticks = [r["t_ms"] for r in recs if r["event"] in ("sing", "breath", "capped", "refused")]
    gaps = [(b - a) / 1000 for a, b in zip(ticks, ticks[1:])]
    emitted[stream] = {r["seq"]: r for r in sings}
    emit_summary[stream] = {"sung": stop["sing"], "breaths": stop["breath"], "capped": stop["capped"],
                            "refused": stop["refused"], "stop_reason": stop["reason"],
                            "model_calls": start["model_calls"] + stop["model_calls"],
                            "tick_gap_s": dist([round(g, 2) for g in gaps]),
                            "distinct_lines": len({r["text"] for r in sings}),
                            "run_s": round((stop["t_ms"] - start["t_ms"]) / 1000, 1)}
    lo, hi = start["gap_s"]
    check(f"{stream}: tick gaps within [{lo}, {hi}] s", gaps and min(gaps) >= lo - 0.05 and max(gaps) <= hi + 0.6,
          emit_summary[stream]["tick_gap_s"])
    check(f"{stream}: zero model calls", emit_summary[stream]["model_calls"] == 0, "fixture source")
    check(f"{stream}: run ended by its bound", stop["reason"] == "duration", stop["reason"])


def hearing(events):
    out = {}
    for s in ("hymn", "lens.weather"):
        first = {}
        for e in events:
            if e.get("event") == "item" and e.get("stream") == s and e["seq"] not in first:
                first[e["seq"]] = e
        tth = [e["t_ms"] - e["issued_at"] for e in first.values()]
        out[s] = {"distinct_items": len(first), "time_to_hear_ms": dist(tth), "first": first}
    return out


early = hearing(jl("listen-early.jsonl"))
late = hearing(jl("listen-late.jsonl"))
for s in ("hymn", "lens.weather"):
    n = len(emitted.get(s, {}))
    check(f"{s}: early listener heard every distinct signed item", early[s]["distinct_items"] == n,
          f"{early[s]['distinct_items']} of {n}")
    first = late[s]["first"]
    gone_before = {q for q, r in emitted.get(s, {}).items() if r["t_ms"] + TTL_MS + 5_000 <= late_start}
    on_air = {q: r for q, r in emitted.get(s, {}).items() if r["t_ms"] <= late_start < r["t_ms"] + TTL_MS}
    after = {q for q, r in emitted.get(s, {}).items() if r["t_ms"] > late_start}
    check(f"{s}: late listener heard nothing that had expired before it started", not (set(first) & gone_before),
          f"{len(gone_before)} items had expired; {len(set(first) & gone_before)} heard")
    check(f"{s}: late listener heard every item sung after it started", after <= set(first),
          f"{len(after & set(first))} of {len(after)}")

# ---- synthetic dashboard snapshots and browser
snaps = jl("dashboard-snapshots.jsonl")
check("dashboard snapshots are synthetic only", snaps and all(s.get("synthetic") is True and s.get("all_synthetic") is True
      and s.get("station_count", 0) == 1 for s in snaps),
      {"snapshots": len(snaps), "first": snaps[0] if snaps else None})

steps = jl("browser.jsonl")
by = lambda step: [s for s in steps if s["step"] == step]
loaded = by("loaded")
verified = by("verified")
check("browser renders the synthetic fixture station", loaded and loaded[0]["dashboard"]["stations"] ==
      [{"name": "demo-station", "synthetic": True}],
      loaded[0]["dashboard"] if loaded else None)
check("browser renders the synthetic demo stream", loaded and loaded[0]["dashboard"]["streams"] == ["demo-stream"],
      loaded[0]["dashboard"] if loaded else None)
check("browser has no item/ring/tune DOM", loaded and loaded[0]["dashboard"]["payloadElements"] == 0,
      loaded[0]["dashboard"] if loaded else None)
check("browser stays synthetic in every phase", all(s["dashboard"]["stations"][0]["synthetic"]
      and s["dashboard"]["payloadElements"] == 0 for s in loaded + verified),
      {"steps": len(loaded + verified)})
errs = [e for s in by("done") for e in s["console_errors"]]
check("no browser console errors", not errs, errs)
check("browser runs completed", not [s for s in steps if s["step"] == "error"], "")

tl = (RUN / "timeline.txt").read_text()
check("the station was never restarted", "still the same process at the end" in tl, "same PID start to end")

# ---- sender tracks nobody; resources
def counter(name, comment):
    for o in json.loads((RUN / name).read_text())["nftables"]:
        r = o.get("rule")
        if r and r.get("comment") == comment:
            return next(e["counter"] for e in r["expr"] if "counter" in e)


into_station = counter("nft-station-host.json", "udp-into-station-host")
into_listener = counter("nft-listener-host.json", "canticle-into-listener-host")
check("no UDP datagram reached the station host: no subscriber table, no acknowledgements", into_station["packets"] == 0,
      into_station)
span_s = (emit_stop + TTL_MS - t0) / 1000
summary = {
    "label": "same-host: two network namespaces on one kernel, veth + LAN multicast; not a second host",
    "source_commit": commit,
    "emission": emit_summary,
    "hearing": {who: {s: {k: v for k, v in d.items() if k != "first"} for s, d in h.items()}
                for who, h in (("early_listener", early), ("late_listener", late))},
    "dashboard": {"synthetic_only": True, "snapshots": len(snaps), "browser_steps": len(steps)},
    "late_listener_started_s_after_t0": round((late_start - t0) / 1000, 1),
    "network": {"udp_into_station_host": into_station, "canticle_udp_into_listener_host": into_listener,
                "mean_kbit_s_into_listener_host": round(into_listener["bytes"] * 8 / span_s / 1000, 2)},
    "cpu_s": {r["process"]: r["cpu_s"] for r in jl("cpu.jsonl")},
    "checks": checks,
}
(RUN / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
for c in checks:
    print(("PASS " if c["ok"] else "FAIL ") + c["check"] + " — " + json.dumps(c["detail"]))
print(json.dumps({k: summary[k] for k in ("hearing", "dashboard", "network", "cpu_s")}, indent=1))
sys.exit(0 if all(c["ok"] for c in checks) else 1)
