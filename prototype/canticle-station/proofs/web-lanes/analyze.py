"""Check a web-lanes proof run against the #57 and #58 acceptance items; print and save summary.json.

    python analyze.py results/<run>

Every figure here comes from the run's own logs. All processes shared one kernel clock, so
emission, issue and hearing times are directly comparable (same-host evidence, see run.sh).
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


# ---- hearing: distinct signed items and time-to-hear (Silas's receipt)
def hearing(events, since_ms=None):
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
tuner = hearing(jl("tuner-events.jsonl"))
late = hearing(jl("listen-late.jsonl"))
for s in ("hymn", "lens.weather"):
    n = len(emitted[s])
    check(f"{s}: early listener heard every distinct signed item", early[s]["distinct_items"] == n,
          f"{early[s]['distinct_items']} of {n}")
    check(f"{s}: tuner gateway heard every distinct signed item", tuner[s]["distinct_items"] == n,
          f"{tuner[s]['distinct_items']} of {n}")
    # Late join. Items that expired before it started must never be heard. Items on air at its start
    # are heard from the carousel within one loop (x 4/3 jitter), unless they expire before their next
    # copy; items sung after its start are heard like any other.
    first = late[s]["first"]
    gone_before = {q for q, r in emitted[s].items() if r["t_ms"] + TTL_MS + 5_000 <= late_start}
    on_air = {q: r for q, r in emitted[s].items() if r["t_ms"] <= late_start < r["t_ms"] + TTL_MS}
    after = {q for q, r in emitted[s].items() if r["t_ms"] > late_start}
    bound = {q: r["loop_ms"] * 4 / 3 for q, r in on_air.items()}
    must = {q for q, r in on_air.items() if r["t_ms"] + TTL_MS - late_start > bound[q]}
    catch = {q: first[q]["t_ms"] - late_start for q in on_air if q in first}
    missed = {q: round((r["t_ms"] + TTL_MS - late_start) / 1000, 1) for q, r in on_air.items() if q not in first}
    late[s].update({"on_air_at_start": len(on_air), "heard_of_on_air": len(catch), "catch_up_ms": dist(list(catch.values())),
                    "missed_with_remaining_life_s": missed,
                    "time_to_hear_ms": dist([first[q]["t_ms"] - first[q]["issued_at"] for q in after if q in first]),
                    "sung_after_start": len(after), "heard_of_sung_after": len(after & set(first))})
    check(f"{s}: late listener heard nothing that had expired before it started", not (set(first) & gone_before),
          f"{len(gone_before)} items had expired; {len(set(first) & gone_before)} heard")
    check(f"{s}: late listener caught up on every on-air item with more than one loop of life left, within loop x 4/3",
          must <= set(catch) and all(catch[q] <= bound[q] + 1_000 for q in catch),
          {"on_air": len(on_air), "heard": len(catch), "catch_up_ms": late[s]["catch_up_ms"],
           "missed (remaining life at start, s)": missed})
    check(f"{s}: late listener heard every item sung after it started", after <= set(first),
          f"{len(after & set(first))} of {len(after)}")

# ---- natural expiry, from the gateway's timed events
exp = [e for e in jl("tuner-events.jsonl") if e.get("event") == "expired"]
signed = {(e["stream"], e["seq"]): e["expires_at"] for e in jl("tuner-events.jsonl") if e.get("event") == "item"}
lag = [e["t_ms"] - signed[(e["stream"], e["seq"])] for e in exp if (e["stream"], e["seq"]) in signed]
n_items = sum(len(v) for v in emitted.values())
check("every item expired naturally, at its signed expiry", len(lag) == n_items and max(lag) <= 500 and min(lag) >= -5_100,
      {"expired": len(lag), "items": n_items, "event_minus_expires_at_ms": dist(lag)})

# ---- ring snapshots: nothing shown past its signed expiry; empty after the drain
snaps = [s for s in jl("ring-snapshots.jsonl") if "items" in s]
late_shown = [(s["t_ms"], it[0]) for s in snaps for it in s["items"] if it[1] + TTL_MS < s["t_ms"] - 1_000]
check("ring snapshots never show an item past its TTL", not late_shown, f"{len(snaps)} snapshots; {len(late_shown)} violations")
after = [s for s in snaps if s["t_ms"] > emit_stop + TTL_MS + 2_000]
check("rings are empty once every item has expired", after and all(not s["items"] for s in after),
      f"{len(after)} snapshots after emit stop + TTL")

# ---- browser (#57)
steps = jl("browser.jsonl")
by = lambda phase, step, stream=None: [s for s in steps if s["phase"] == phase and s["step"] == step and
                                       (stream is None or s.get("stream") == stream)]
weather_lines = {l.strip() for l in (RUN / "weather.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
hymn_lines = {l.strip() for l in (RUN / "hymn.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
tuned_h = by("early", "tuned", "hymn")
left = by("early", "left")
tuned_w = by("early", "tuned", "lens.weather")
check("browser tuned hymn and saw its ring", tuned_h and tuned_h[0]["ring"]["items"] and
      all(i["text"] in hymn_lines for i in tuned_h[0]["ring"]["items"]),
      [i["seq"] for i in tuned_h[0]["ring"]["items"]] if tuned_h else None)
check("browser left: no channel shown", left and left[0]["ring"]["notTuned"], "not tuned")
check("browser retuned to lens.weather and saw only weather items", tuned_w and tuned_w[0]["ring"]["items"] and
      all(i["text"] in weather_lines for i in tuned_w[0]["ring"]["items"]),
      [i["seq"] for i in tuned_w[0]["ring"]["items"]] if tuned_w else None)
check("browser retuned back to hymn", len(tuned_h) >= 2, f"{len(tuned_h)} hymn tunes")
lv = by("late", "late-view", "hymn")
if lv:
    t = lv[0]["t_ms"]
    shown = [i["seq"] for i in lv[0]["ring"]["items"]]
    live = sorted(q for q, r in emitted["hymn"].items() if r["t_ms"] <= t and r["t_ms"] + TTL_MS > t + 1_000)
    stale = [q for q in shown if emitted["hymn"][q]["t_ms"] + TTL_MS < t - 1_000]
    check("late page shows the live ring and nothing expired", set(live) <= set(shown) and not stale,
          {"shown": shown, "live_per_emit_log": live, "expired_shown": stale})
dr = by("drain", "after-stop", "hymn")
check("after the drain the page shows no live items, only labelled expiries", dr and not dr[0]["ring"]["items"],
      {"items": len(dr[0]["ring"]["items"]) if dr else None, "tombstones": dr[0]["ring"]["tombstones"][:3] if dr else None})
errs = [e for s in by("early", "done") + by("late", "done") + by("drain", "done") for e in s["console_errors"]]
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
                for who, h in (("early_listener", early), ("tuner_gateway", tuner), ("late_listener", late))},
    "late_listener_started_s_after_t0": round((late_start - t0) / 1000, 1),
    "network": {"udp_into_station_host": into_station, "canticle_udp_into_listener_host": into_listener,
                "mean_kbit_s_into_listener_host": round(into_listener["bytes"] * 8 / span_s / 1000, 2)},
    "cpu_s": {r["process"]: r["cpu_s"] for r in jl("cpu.jsonl")},
    "checks": checks,
}
(RUN / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
for c in checks:
    print(("PASS " if c["ok"] else "FAIL ") + c["check"] + " — " + json.dumps(c["detail"]))
print(json.dumps({k: summary[k] for k in ("hearing", "network", "cpu_s")}, indent=1))
sys.exit(0 if all(c["ok"] for c in checks) else 1)
