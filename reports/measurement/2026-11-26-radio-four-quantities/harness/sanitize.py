"""Builds the published ``results/`` from the instruments' raw files, which stay on the seat.

    python3 harness/sanitize.py <raw-dir> <results-dir>

Added after the window, from an independent review of the harness. The window's instruments (``run.sh`` at
``a3768b1``) wrote no heard text, name, key id, address or session id. But two things they wrote should not be
public as they are:

- **Per-frame records.** Each carries a salted station label, a class and an arrival time. The classes a manifest
  licenses can single a station out (one station holds ``ambient``), so a label plus times is that station's
  timeline: the "river" tier that display grants (#137) leave to the station's own consent. Frames are therefore
  published only as counts over the window (``frames.json``), and their records stay in the raw directory on the
  seat. The sequential ``daemon-records.jsonl`` keeps every other record (health, presence, hello, landing state,
  snapshot ends, the probe's own events) with frames removed.
- **Strings that pass as words without being closed.** The daemon's run id becomes a label, store counter names keep
  only the part before a ``.`` (frond-ear names some per ear), class names must be classes, and the manifest's
  digest prefix is dropped (``hello`` already says whether the daemon's manifest matches the file).

What frames.json counts, inside [t0, t1]: the join snapshot's frame entries from the probe's first connection
(what was live at t0) and every live ``frame`` record that arrived in the window.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

COPY = ("window.json", "beacon-sizes.json", "code-bounds.json", "window-close.json")


def jsonl(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def split_keys(d: dict) -> dict:
    out: dict = {}
    for k, v in (d or {}).items():
        base = k.split(".", 1)[0]
        out[base] = out.get(base, 0) + v
    return out


def tally(rows, key):
    out: dict = {}
    for r in rows:
        k = key(r)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def frames_summary(recs: list, t0: int, t1: int) -> dict:
    # The join snapshot of the probe's first connection: what was live at t0.
    first_conn, snap, live = None, [], []
    for r in recs:
        if r["type"] == "_probe" and r.get("event") == "connected":
            first_conn = 1 if first_conn is None else 2
        elif r["type"] == "snapshot" and first_conn == 1 and r["entry"].get("type") == "frame":
            snap.append(r["entry"])
        elif r["type"] == "frame" and t0 <= r["t"] <= t1:
            live.append(r)
    frames = snap + live
    surfaced = [f for f in frames if f["admission"] == "verified" and f["disposition"] == "surface"]
    first = [f for f in live if f["admission"] == "verified" and f["dedup"] == "first" and f["kind"] == "item"]
    live_items = [f for f in snap if f["kind"] == "item"] + first
    fb = [f["frame_bytes"] for f in first if f.get("frame_bytes")]
    lb = [f["frame_bytes"] for f in live_items if f.get("frame_bytes")]

    def distinct(rows, field):
        return len({f[field] for f in rows})

    return {
        "t0": t0, "t1": t1,
        "records": {"snapshot_entries": len(snap), "live_in_window": len(live)},
        "by": tally(frames, lambda f: "|".join(str(f.get(k)) for k in (
            "source", "kind", "admission", "disposition", "dedup", "class", "tuned_seat", "tuned_openclaw"))),
        "reasons": tally([x for f in frames for x in f.get("reasons") or []], lambda x: x),
        "distinct": {
            "stations": distinct(frames, "station"), "streams": distinct(frames, "stream"),
            "streams_tuned_seat": len({f["stream"] for f in frames if f["tuned_seat"]}),
            "streams_tuned_openclaw": len({f["stream"] for f in frames if f["tuned_openclaw"]}),
            "stations_tuned_seat": len({f["station"] for f in frames if f["tuned_seat"]}),
            "streams_surfaced": distinct(surfaced, "stream"),
            "streams_surfaced_tuned_seat": len({f["stream"] for f in surfaced if f["tuned_seat"]}),
        },
        # What frond-ear's #passOver sees: verified records it surfaced (delivery.ts reads the hear view).
        "seat_gate_model_surfaced": tally(surfaced, lambda f: f["seat_gate_model"]),
        "surfaced_by_class": tally(surfaced, lambda f: f["class"]),
        "surfaced_by_tuned_seat": tally(surfaced, lambda f: str(f["tuned_seat"])),
        "first_copies": {"items": len(first), "bytes": sum(fb), "bytes_min": min(fb) if fb else None,
                         "bytes_max": max(fb) if fb else None,
                         "bytes_mean": statistics.mean(fb) if fb else None,
                         "refresh": sum(1 for f in first if f.get("refresh")),
                         "hop_nonzero": sum(1 for f in first if f.get("hop")),
                         "wake_derived": sum(1 for f in first if f.get("wake_derived"))},
        "plucks": sum(1 for f in live if f["kind"] == "pluck"),
        "warmup_held": sum(1 for f in frames if "warmup_hold" in (f.get("reasons") or [])),
        "live_items": {"n": len(live_items), "bytes_min": min(lb) if lb else None,
                       "bytes_max": max(lb) if lb else None, "bytes_mean": statistics.mean(lb) if lb else None},
        "body_bytes": {"n": sum(1 for f in live_items if f.get("body_size") is not None),
                       "min": min((f["body_size"] for f in live_items if f.get("body_size") is not None), default=None),
                       "max": max((f["body_size"] for f in live_items if f.get("body_size") is not None), default=None)},
    }


def main() -> int:
    raw, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name in COPY:
        shutil.copyfile(os.path.join(raw, name), os.path.join(out, name))
    win = C.load_json(os.path.join(raw, "window.json"))

    cat = C.load_json(os.path.join(raw, "catalog.json"))
    m = cat["manifest"]
    m.pop("sha256_prefix", None)
    m["stations_per_class"] = {C.closed(k, C.CLASSES): v for k, v in m["stations_per_class"].items()}
    for p in cat["seat_frond_ear"]["patterns"]:
        for pair in p["pairs"]:
            for k in ("licensed_classes", "wake_classes_x_licensed"):
                pair[k] = sorted(C.closed(c, C.CLASSES) for c in pair[k])
    with open(os.path.join(out, "catalog.json"), "w") as fh:
        json.dump(cat, fh, indent=1, sort_keys=True)
        fh.write("\n")

    recs = jsonl(os.path.join(raw, "daemon-records.jsonl"))
    with open(os.path.join(out, "frames.json"), "w") as fh:
        json.dump(frames_summary(recs, win["t0"], win["t1"]), fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(out, "daemon-records.jsonl"), "w") as fh:
        for r in recs:
            if r["type"] == "frame":
                continue
            if r["type"] == "snapshot":
                kind = r["entry"].get("type")
                r["entry"] = r["entry"] if kind == "presence" else {"type": kind}
                if "run" in r["entry"]:
                    r["entry"]["run"] = C.label("run", r["entry"]["run"])
            if r.get("run"):
                r["run"] = C.label("run", r["run"])
            C.write_jsonl(fh, r)

    with open(os.path.join(out, "host-samples.jsonl"), "w") as fh:
        for r in jsonl(os.path.join(raw, "host-samples.jsonl")):
            if r["kind"] == "slow":
                fe, cu = r.get("frond_ear") or {}, r.get("custody") or {}
                if "counters" in fe:
                    fe["counters"] = split_keys(fe["counters"])
                if "counters" in cu:
                    cu["counters"] = split_keys(cu["counters"])
            C.write_jsonl(fh, r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
