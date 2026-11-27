"""Computes every number REPORT.md gives, from the published ``results/`` alone, by METHOD.md's formulas.

    python3 harness/summarize.py results/ > /dev/null   (writes results/summary.json, and prints it)

``Δ`` is a counter's value at the last sample inside [t0, t1] minus its value at the first; a rate divides it by the
seconds between those two samples. Corrections from the post-window review of the harness (REPORT.md, "How the
numbers were checked"):

- a verified first copy of a PLUCK emits a ``retract`` and no admission count (``records.py:373-377``), so plucks
  are counted from ``Δ retract.plucked`` and ``Δ retract.held_plucked``;
- a warm-up hold released later emits a second ``frame`` and a second admission count for one datagram; the count
  of such holds is subtracted (``frames.json`` ``warmup_held``);
- the size of repeats uses the plain mean of the items live in the window (a snapshot entry's remaining life
  is not in the projected record, so no time weighting);
- the seat's pass-over model is compared over verified, surfaced records only, which is what frond-ear reads;
- every delta is checked for a restart in between (a counter going down, a new daemon run or process).
"""

from __future__ import annotations

import json
import os
import statistics
import sys

ON_AIR = {"ROOT_UNKNOWN", "UNEQUIPPED_PRESENT", "EQUIPPED_SPEAKING", "EQUIPPED_QUIET"}


def load(path):
    with open(path) as fh:
        return json.load(fh)


def jsonl(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def flat(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[prefix + k] = v
    return out


def delta(first, last):
    a, b = flat(first), flat(last)
    return {k: b.get(k, 0) - a.get(k, 0) for k in sorted(set(a) | set(b)) if b.get(k, 0) != a.get(k, 0)}


def monotonic(series) -> bool:
    """Every counter in a series of dicts never goes down (no restart reset it in between)."""
    prev: dict = {}
    for d in series:
        cur = flat(d)
        if any(cur.get(k, 0) < v for k, v in prev.items()):
            return False
        prev = cur
    return True


def main() -> int:
    res = sys.argv[1] if len(sys.argv) > 1 else "results"
    win = load(os.path.join(res, "window.json"))
    t0, t1 = win["t0"], win["t1"]
    cat = load(os.path.join(res, "catalog.json"))
    sizes = load(os.path.join(res, "beacon-sizes.json"))
    bounds = load(os.path.join(res, "code-bounds.json"))
    fr = load(os.path.join(res, "frames.json"))
    recs = jsonl(os.path.join(res, "daemon-records.jsonl"))
    host = jsonl(os.path.join(res, "host-samples.jsonl"))
    close = load(os.path.join(res, "window-close.json"))
    S: dict = {"window": {"t0": t0, "t1": t1, "seconds": (t1 - t0) / 1000}}

    # ---- integrity: one probe connection, one daemon run, no restart, nothing dropped for any binding
    probes = [r for r in recs if r["type"] == "_probe"]
    health = [r for r in recs if r["type"] == "health" and t0 <= r["t"] <= t1]
    fast = [r for r in host if r["kind"] == "fast" and r.get("udp") and t0 <= r["t"] <= t1]
    slow = [r for r in host if r["kind"] == "slow" and isinstance(r.get("frond_ear"), dict)
            and "ear" in r["frond_ear"] and "error" not in r.get("custody", {"error": 1})]
    S["integrity"] = {
        "probe_events": [p["event"] + (":" + p["why"] if "why" in p else "") for p in probes],
        "daemon_runs_seen": len({r["run"] for r in recs if r.get("run")}),
        "daemon_process_starts_seen": len({r["proc"]["start_ticks"] for r in fast if r.get("proc")}),
        "hello_manifest_matches_local_file": [h.get("manifest_matches_local_file") for h in recs if h["type"] == "hello"],
        "health_records": len(health),
        "health_counters_monotonic": monotonic([h["counters"] for h in health]),
        "udp_drops_monotonic": monotonic([{"d": r["udp"]["drops"]} for r in fast]),
        "frond_ear_samples": len(slow),
        "frond_ear_counts_monotonic": monotonic([r["frond_ear"]["ear"]["delivery"]["counts"] for r in slow])
        and monotonic([r["custody"]["counters"] for r in slow]),
        "records_dropped_delta": health[-1]["records"]["dropped"] - health[0]["records"]["dropped"],
        "peers_closed_delta": health[-1]["records"]["peers_closed"] - health[0]["records"]["peers_closed"],
        "health_states": sorted({h["state"] for h in health}),
        "health_reasons": sorted({r for h in health for r in h["reasons"]}),
        "fast_samples": len(fast),
    }

    # ---- 1. catalog
    m = cat["manifest"]
    fresh5 = [sum(1 for a in h["beacon_ages_ms"] if a <= 5_000) for h in health]
    fresh30 = [sum(1 for a in h["beacon_ages_ms"] if a <= 30_000) for h in health]
    pres, changes = {}, 0
    for r in recs:
        p = r["entry"] if r["type"] == "snapshot" else r
        if p.get("type") == "presence" and (r["type"] == "snapshot" or t0 <= r["t"] <= t1):
            if r["type"] != "snapshot":
                changes += 1
            pres[p["station"]] = p["state"]
    by_state: dict = {}
    for s in pres.values():
        by_state[s] = by_state.get(s, 0) + 1
    S["q1_catalog"] = {
        "licensed_stations": m["stations"], "licensed_pairs": m["licensed_pairs"],
        "streams_per_station": m["streams_per_station"], "distinct_stream_names": m["distinct_stream_names"],
        "stations_per_class": m["stations_per_class"], "signed": m["signed"], "public_streams": m["public_streams"],
        "stations_with_a_beacon_this_run": max(len(h["beacon_ages_ms"]) for h in health),
        "beacon_age_le_5s": {"min": min(fresh5), "median": statistics.median(fresh5), "max": max(fresh5)},
        "beacon_age_le_30s": {"min": min(fresh30), "median": statistics.median(fresh30), "max": max(fresh30)},
        "presence_at_end_by_state": dict(sorted(by_state.items())),
        "on_air_at_end": sum(v for k, v in by_state.items() if k in ON_AIR),
        "presence_changes_in_window": changes,
        "stations_with_items_in_window": fr["distinct"]["stations"],
        "streams_with_items_in_window": fr["distinct"]["streams"],
        "local_stations": [{"streams": p["streams"], "peers": p["peers"], "beacon_ms": p["beacon_ms"]}
                           for p in cat["processes"] if p["role"] == "canticle station"],
        "code": {"max_streams_per_station": bounds["max_streams_per_station"],
                 "beacon_catalog_bound": sizes["max_streams_per_station"],
                 "dedup_quota_per_key": bounds["dedup_quota_per_key"]},
    }

    # ---- 2. traffic at the host daemon
    h0, h1 = health[0], health[-1]
    secs = (h1["t"] - h0["t"]) / 1000
    dc = delta(h0["counters"], h1["counters"])
    beacons = sum(v for k, v in dc.items() if k.startswith("beacon."))
    plucks = dc.get("retract.plucked", 0) + dc.get("retract.held_plucked", 0)
    items = sum(v for k, v in dc.items() if k.startswith("admission.")) - fr["warmup_held"]
    unverified = sum(v for k, v in dc.items() if k.startswith("unverified."))
    drops = fast[-1]["udp"]["drops"] - fast[0]["udp"]["drops"]
    total = beacons + items + plucks + unverified + drops
    daemon_start = min(p["started_at_ms"] for p in cat["processes"] if p["role"] == "canticle daemon")
    up = (h1["t"] - daemon_start) / 1000
    rc = flat(h1["counters"])
    run = {"beacons": sum(v for k, v in rc.items() if k.startswith("beacon.")),
           "items": sum(v for k, v in rc.items() if k.startswith("admission.")),
           "first_copies": rc.get("admission.verified", 0), "repeats": rc.get("admission.duplicate", 0),
           "plucks": rc.get("retract.plucked", 0) + rc.get("retract.held_plucked", 0),
           "unverified": sum(v for k, v in rc.items() if k.startswith("unverified."))}
    fc, li = fr["first_copies"], fr["live_items"]
    dup = dc.get("admission.duplicate", 0)
    typ, idle = sizes["typical"], sizes["idle"]
    kbar = round(m["licensed_pairs"] / m["stations"])
    maxk = min(max(m["streams_per_station"]), max(int(k) for k in typ))
    rep = {"datagrams": dup, "mean_bytes": li["bytes_mean"],
           "bytes": dup * li["bytes_mean"] if li["bytes_mean"] else 0,
           "bytes_low": dup * li["bytes_min"] if li["bytes_min"] else 0,
           "bytes_high": dup * li["bytes_max"] if li["bytes_max"] else 0}
    bea = {"datagrams": beacons, "streams_per_beacon_assumed": kbar, "size": typ[str(kbar)],
           "size_low": idle["1"], "size_high": typ[str(maxk)], "bytes": beacons * typ[str(kbar)],
           "bytes_low": beacons * idle["1"], "bytes_high": beacons * typ[str(maxk)]}
    rec_live = [r for r in recs if r["type"] in ("presence", "health", "retract", "landing_state")
                and t0 <= r["t"] <= t1]
    S["q2_traffic"] = {
        "seconds": secs,
        "datagrams": {"beacon": beacons, "item": items, "pluck": plucks, "unverified": unverified,
                      "kernel_dropped": drops, "total": total},
        "per_s": {"beacon": beacons / secs, "item": items / secs, "pluck": plucks / secs,
                  "unverified": unverified / secs, "kernel_dropped": drops / secs, "total": total / secs},
        "share_beacon": beacons / total if total else None,
        "items_split": {"first_copies_counter": dc.get("admission.verified", 0), "repeats": dup,
                        "first_copies_records": fc["items"], "warmup_held": fr["warmup_held"]},
        "counter_deltas": dc,
        "rx_queue_max_bytes": max(r["udp"]["rx_queue"] for r in fast),
        "kernel_drops_this_socket_total": fast[-1]["udp"]["drops"],
        "whole_run": {"seconds": up, **run, "per_s": {k: v / up for k, v in run.items()}},
        "first_copies": fc,
        "live_items": li,
        "derived_bytes": {"repeats": rep, "beacons": bea},
        "bytes_per_s": {"observed_first_copies": fc["bytes"] / secs,
                        "estimate_low": (fc["bytes"] + rep["bytes_low"] + bea["bytes_low"]) / secs,
                        "estimate": (fc["bytes"] + rep["bytes"] + bea["bytes"]) / secs,
                        "estimate_high": (fc["bytes"] + rep["bytes_high"] + bea["bytes_high"]) / secs},
        "record_v1": {"records_emitted": h1["records"]["emitted"] - h0["records"]["emitted"],
                      "per_s": (h1["records"]["emitted"] - h0["records"]["emitted"]) / secs,
                      "non_frame_records_to_probe": {t: sum(1 for r in rec_live if r["type"] == t)
                                                     for t in sorted({r["type"] for r in rec_live})},
                      "frame_records_to_probe": fr["records"]["live_in_window"],
                      "bytes_to_probe_excl_frames": sum(r["line_bytes"] for r in rec_live)},
    }
    procs = [r for r in fast if r.get("proc")]
    if procs:
        S["q2_traffic"]["daemon"] = {"cpu_s": round(procs[-1]["proc"]["cpu_s"] - procs[0]["proc"]["cpu_s"], 2),
                                     "rss_kib_max": max(r["proc"]["rss_kib"] for r in procs)}

    # ---- 3. tuned
    w0, w1 = slow[0], slow[-1]
    fe0, fe1 = w0["frond_ear"], w1["frond_ear"]
    S["q3_tuned"] = {
        "seat": cat["seat_frond_ear"],
        "frames": {"records": fr["records"], "by": fr["by"], "distinct": fr["distinct"],
                   "surfaced_by_tuned_seat": fr["surfaced_by_tuned_seat"],
                   "surfaced_by_class": fr["surfaced_by_class"]},
        "seat_gate_model_surfaced": fr["seat_gate_model_surfaced"],
        "frond_ear_samples": {"first_t": w0["t"], "last_t": w1["t"], "n": len(slow)},
        "frond_ear_delivery_counts_delta": delta(fe0["ear"]["delivery"]["counts"], fe1["ear"]["delivery"]["counts"]),
        "frond_ear_delivery_counts_end": fe1["ear"]["delivery"]["counts"],
        "frond_ear_canticle_counts_delta": delta(fe0["canticle"]["counts"], fe1["canticle"]["counts"]),
        "frond_ear_live_set": {"size_min": min(r["frond_ear"]["canticle"]["live_set"]["size"] for r in slow),
                               "size_max": max(r["frond_ear"]["canticle"]["live_set"]["size"] for r in slow),
                               "streams_max": max(r["frond_ear"]["canticle"]["live_set"]["streams"] for r in slow),
                               "max": fe1["canticle"]["live_set"]["max"],
                               "omitted_total_delta": fe1["canticle"]["live_set"]["omitted_total"]
                               - fe0["canticle"]["live_set"]["omitted_total"]},
        "frond_ear_receive": sorted({f'{r["frond_ear"]["canticle"]["receive_health"]}/{r["frond_ear"]["canticle"]["state"]}'
                                     for r in slow}),
        "frond_ear_stations_by_state_end": fe1["canticle"]["stations_by_state"],
        "openclaw_binding": {k: v for k, v in cat["openclaw_binding"].items() if k != "extension_digest"},
        "openclaw_journal": close["openclaw_journal"],
    }

    # ---- 4. admitted to a turn
    S["q4_admitted"] = {
        "custody_window": close["custody"]["window"],
        "custody_all_retained": close["custody"]["all_retained"],
        "custody_since_ms": close["custody"]["custody_since_ms"],
        "store_counters_delta": delta(w0["custody"]["counters"], w1["custody"]["counters"]),
        "store_counters_end": w1["custody"]["counters"],
        "ear_delivery_end": {k: fe1["ear"]["delivery"][k] for k in (
            "ceiling", "mode", "station_modes", "wake_keys", "max_pushes_per_hour", "debounce_ms", "window_ms",
            "max_age_ms")},
        "pushes_last_hour_max": max(r["frond_ear"]["ear"]["delivery"]["pushes_last_hour"] for r in slow),
        "waiting_max": max(r["frond_ear"]["ear"]["delivery"]["waiting"] for r in slow),
        "held_words": sorted({str(r["frond_ear"]["ear"]["delivery"]["held"]) for r in slow}),
        "ear_custody_end": fe1["ear"]["custody"],
        "ear_attached_all_samples": all(r["frond_ear"]["ear"]["attached"] for r in slow),
        "exposure_enabled": cat["seat_frond_ear"]["exposure_enabled"],
        "exposure_rows": close["custody"]["exposure_rows"],
        "openclaw_state_end": slow[-1]["openclaw"],
        "frond_ear_journal": close["frond_ear_journal"],
        "daemon_journal": close["daemon_journal"],
    }

    with open(os.path.join(res, "summary.json"), "w") as fh:
        json.dump(S, fh, indent=1, sort_keys=True)
        fh.write("\n")
    json.dump(S, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
