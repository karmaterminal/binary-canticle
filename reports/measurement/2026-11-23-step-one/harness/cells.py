"""One measurement cell: a throwaway lab, producers, ears, a probe, a sampler; then the numbers.

A cell is a dict of parameters (see `run_cell`). It builds a fresh lab (so no cell inherits another's
dedup state), starts the host daemon, `ears` frond-ear daemons each with a fake session, the probe
tap, optionally a real quiet station singing every `quiet_interval` seconds, and the producers; runs
for `duration` seconds plus a drain; and returns one summary dict. Raw per-cell files (sampler CSV,
health JSONL, pushes JSONL, latency samples) are copied to `out_dir`.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import signal
import time
from pathlib import Path
from typing import Optional

from mlib import (FROND_EAR, HERE, NODE_SHIM, PYTHON, Lab, Sampler, frond_ear_status, key_id_hex, loadavg, mono_ns,
                  percentile, stream_names, summarize_samples, udp_snmp, udp_socket_drops)

DEFAULT_DELIVERY = {"mode": "off", "stations": {}}   # the live seat's shape: off, per-station immediate


def ear_block(status: Optional[dict], ear: str) -> dict:
    if not status:
        return {}
    for e in status.get("ears", []):
        if e.get("name") == ear:
            return {"canticleDelivery": e.get("canticleDelivery"), "canticleCustody": e.get("canticleCustody"),
                    "attached": e.get("attached")}
    return {}


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def run_cell(p: dict, out_dir: Path, keep_lab: bool = False, actions=None) -> dict:
    """Parameters (defaults in brackets):
      name; duration [30]; drain [8]
      streams [1]; payload ["64"|"512"|"max"]; producers [1] (processes, one key between them);
      rate [0 = max, per process]; mode ["valid"]; ttl [60]; prod_keys [1] (separate keys, one process each,
      instead of `producers`); copies of none (dup mode is its own mode)
      ears [1]; ear_tune ["stream0"|"all"|"none"]; prod_wake [True] (producer key on wakeKeys + immediate)
      quiet_interval [None]; quiet_in_flood_station [False]
      flood_station_rate [None] (a real station flooded through its control socket instead of blasters)
      tap [True]; health_s [1.0]; sample_period [0.5]
    `actions`: optional list of (t_offset_s, callable(lab)) run during the cell (restart storms)."""
    name = p["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    lab = Lab(name)
    result: dict = {"params": p, "lab": str(lab.dir)}
    try:
        n_streams = int(p.get("streams", 1))
        prod_keys = int(p.get("prod_keys", 1))
        producers = int(p.get("producers", 1)) if prod_keys == 1 else prod_keys
        names = stream_names("s", n_streams)
        (lab.dir / "streams.txt").write_text("\n".join(names))
        keys = []
        for k in range(prod_keys):
            keys.append(lab.add_station(f"prod{k}" if prod_keys > 1 else "prod", names))
        quiet_sk = None
        qi = p.get("quiet_interval")
        in_flood = bool(p.get("quiet_in_flood_station"))
        fsr = p.get("flood_station_rate")
        if qi and not in_flood:
            quiet_sk = lab.add_station("quiet", ["quiet"])
        if fsr is not None or in_flood:
            # a real station carrying the flood stream (and, in_flood, the quiet stream too)
            fs_streams = ["flood"] + (["quiet"] if in_flood else [])
            flood_sk = lab.add_station("floodst", fs_streams)
            if in_flood:
                quiet_sk = flood_sk
        lab.write_manifest()
        sampler = Sampler(out_dir / "samples.csv", period=float(p.get("sample_period", 0.5)))
        lab.sampler = sampler
        drops0 = udp_socket_drops(lab.port)  # None before bind
        snmp0 = udp_snmp()
        lab.start_daemon(health_s=float(p.get("health_s", 1.0)))
        drops0 = udp_socket_drops(lab.port)

        # ears: frond-ear daemons, each one ear, each with a fake session
        n_ears = int(p.get("ears", 1))
        tune_mode = p.get("ear_tune", "stream0")
        wake = []
        stations_delivery = {}
        tune: list[str] = []
        prod_names = [f"prod{k}" if prod_keys > 1 else "prod" for k in range(prod_keys)]
        if p.get("prod_wake", True):
            wake += [key_id_hex(k) for k in keys]
            stations_delivery.update({n: "immediate" for n in prod_names})
        if tune_mode == "stream0":
            tune += [f"{n}:{names[0]}" for n in prod_names]
        elif tune_mode == "all":
            tune += [f"{n}:{s}" for n in prod_names for s in names]
        if quiet_sk is not None:
            qname = "floodst" if in_flood else "quiet"
            tune.append(f"{qname}:quiet")
            wake.append(key_id_hex(quiet_sk))
            stations_delivery[qname] = "immediate"
        delivery = dict(DEFAULT_DELIVERY, stations=stations_delivery)
        duration = float(p.get("duration", 30))
        drain = float(p.get("drain", 8))
        settle = 4.0
        total = settle + duration + drain
        for e in range(n_ears):
            ear = f"ear{e}"
            cfg = lab.frond_ear_config(ear, tune, wake, delivery)
            lab.start_frond_ear(ear, cfg)
            lab.spawn(f"session{e}", [PYTHON, HERE / "fake_session.py", "--frond-ear", FROND_EAR, "--node", NODE_SHIM,
                                      "--socket", lab.frond_ear_sock(ear), "--ear", ear, "--out", lab.logs / f"session{e}",
                                      "--duration", total + 2])
            # the shim is the session's child process: sample it too
        if p.get("tap", True):
            lab.spawn("tap", [PYTHON, HERE / "tap.py", "--socket", lab.daemon_sock, "--out", lab.logs / "tap",
                              "--duration", total + 1])
        time.sleep(settle)
        for e in range(n_ears):
            # the shim the fake session spawned (its only child)
            sess = lab.procs[f"session{e}"].pid
            try:
                kids = Path(f"/proc/{sess}/task/{sess}/children").read_text().split()
                if kids:
                    sampler.track(f"shim{e}", int(kids[0]))
            except OSError:
                pass

        stations = []
        if qi and not in_flood:
            lab.start_station("quiet", ["quiet:chatter"])
            stations.append("quiet")
        if fsr is not None or in_flood:
            specs = ["flood:chatter"] + (["quiet:chatter"] if in_flood else [])
            lab.start_station("floodst", specs)
            stations.append("floodst")

        t_start = time.monotonic() + 1.0
        result["t_start_mono_ns"] = int(t_start * 1e9)
        epoch = int(time.time())
        mode = p.get("mode", "valid")
        sample_every = int(p.get("sample_every", 1))
        for i in range(producers):
            key_file = lab.dir / (f"prod{i}.key" if prod_keys > 1 else "prod.key")
            lab.spawn(f"blast{i}", [PYTHON, HERE / "blast.py", "--target", f"127.0.0.1:{lab.port}", "--key", key_file,
                                    "--streams", f"@{lab.dir / 'streams.txt'}", "--mode", mode,
                                    "--payload", p.get("payload", "64"), "--rate", p.get("rate", 0),
                                    "--duration", duration, "--ttl", p.get("ttl", 60), "--epoch", epoch,
                                    "--proc-index", 0 if prod_keys > 1 else i,
                                    "--proc-count", 1 if prod_keys > 1 else producers,
                                    "--sample-every", sample_every if i == 0 or prod_keys > 1 else 0,
                                    "--sample-log", lab.logs / f"blast{i}.samples.csv",
                                    "--summary", lab.logs / f"blast{i}.json", "--start-at", t_start])
        for extra_mode, count in (p.get("extra_floods") or {}).items():
            # additional producers of another kind (forged / unknown / dup), on prod key 0
            for j in range(int(count)):
                lab.spawn(f"x{extra_mode}{j}", [PYTHON, HERE / "blast.py", "--target", f"127.0.0.1:{lab.port}",
                                                "--key", lab.dir / ("prod0.key" if prod_keys > 1 else "prod.key"),
                                                "--streams", f"@{lab.dir / 'streams.txt'}", "--mode", extra_mode,
                                                "--payload", p.get("payload", "64"), "--rate", 0,
                                                "--duration", duration, "--epoch", epoch,
                                                "--summary", lab.logs / f"x{extra_mode}{j}.json", "--start-at", t_start])
        if fsr is not None:
            lab.spawn("floodsinger", [PYTHON, HERE / "singer.py", "--control", lab.run / "station-floodst.sock",
                                      "--stream", "flood", "--key-id", key_id_hex(lab.keys["floodst"]),
                                      "--rate", fsr, "--duration", duration, "--payload", p.get("payload", "64"),
                                      "--tag", "flood", "--out", lab.logs / "floodsinger",
                                      "--first-at", max(0.0, t_start - time.monotonic())])
        if qi:
            ctl = lab.run / ("station-floodst.sock" if in_flood else "station-quiet.sock")
            lab.spawn("quietsinger", [PYTHON, HERE / "singer.py", "--control", ctl, "--stream", "quiet",
                                      "--key-id", key_id_hex(quiet_sk), "--interval", qi,
                                      "--duration", duration, "--tag", "quiet", "--out", lab.logs / "quiet",
                                      "--first-at", max(0.0, t_start - time.monotonic()) + float(p.get("quiet_offset", 2.0))])

        # watch: kernel drops, frond-ear status and load, every 5 s; scheduled actions
        timeline = []
        actions = sorted(actions or [], key=lambda a: a[0])
        while time.monotonic() < t_start + duration + drain:
            now = time.monotonic()
            while actions and now - t_start >= actions[0][0]:
                t_off, fn = actions.pop(0)
                timeline.append({"t_s": round(now - t_start, 2), "action": fn.__name__})
                fn(lab)
            row = {"t_s": round(now - t_start, 2), "loadavg1": loadavg(), "udp": udp_socket_drops(lab.port)}
            if int(now - t_start) % 5 == 0 or not timeline:
                for e in range(n_ears):
                    st = frond_ear_status(lab.frond_ear_sock(f"ear{e}"), timeout=2)
                    if st:
                        c = st.get("canticle", {})
                        row[f"ear{e}"] = {"receiveHealth": c.get("receiveHealth"), "reasons": c.get("reasons"),
                                          "counts": c.get("counts"), "state": c.get("state"),
                                          "delivery": (ear_block(st, f"ear{e}").get("canticleDelivery") or {})}
            timeline.append(row)
            time.sleep(1.0)
        drops1 = udp_socket_drops(lab.port)
        snmp1 = udp_snmp()
        statuses = {f"ear{e}": frond_ear_status(lab.frond_ear_sock(f"ear{e}")) for e in range(n_ears)}
        # let the probes finish and write
        for label in list(lab.procs):
            if label.startswith(("tap", "session")):
                try:
                    lab.procs[label].wait(15)
                except Exception:
                    lab.stop(label)
        lab.close()
        result.update(collect(lab, p, out_dir, drops0, drops1, snmp0, snmp1, statuses, timeline, n_ears,
                              producers, quiet_sk is not None, t_start, duration))
    finally:
        lab.close()
        if not keep_lab:
            lab.remove()
    (out_dir / "result.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def collect(lab: Lab, p, out_dir, drops0, drops1, snmp0, snmp1, statuses, timeline, n_ears, producers, has_quiet,
            t_start, duration) -> dict:
    logs = lab.logs
    r: dict = {}
    # producers
    blasts = [json.loads((logs / f).read_text()) for f in sorted(os.listdir(logs))
              if (f.startswith("blast") or f.startswith("x")) and f.endswith(".json")]
    r["producers"] = blasts
    r["offered"] = sum(b["sent"] for b in blasts)
    r["offered_rate"] = round(sum(b["rate_achieved"] or 0 for b in blasts), 1)
    r["frame_bytes"] = max((b["frame_bytes"] for b in blasts), default=None)
    # kernel
    r["kernel_drops"] = (drops1 or {}).get("drops", 0) - (drops0 or {}).get("drops", 0) if drops1 else None
    r["snmp_delta"] = {k: snmp1[k] - snmp0.get(k, 0) for k in snmp1 if snmp1[k] != snmp0.get(k, 0)}
    # the daemon's own health (last record) and the probe
    health = read_jsonl(logs / "tap.health.jsonl")
    r["daemon_health_last"] = health[-1] if health else None
    (out_dir / "health.jsonl").write_text("".join(json.dumps(h) + "\n" for h in health))
    tap = json.loads((logs / "tap.json").read_text()) if (logs / "tap.json").exists() else {}
    r["tap"] = {k: tap.get(k) for k in ("connections", "lines", "bytes", "counts", "rec_seq_gaps",
                                        "rec_seq_gap_records", "rec_seq_regressions")}
    r["tap_events"] = tap.get("events", [])
    # throughput: verified frame records per second through the daemon (as the probe received them)
    t0 = int(t_start * 1e9)
    send_t: dict[str, int] = {}
    for i in range(producers):
        f = logs / f"blast{i}.samples.csv"
        if f.exists():
            for line in open(f):
                idem, t = line.strip().split(",")
                send_t[idem] = int(t)
    quiet_rows = read_jsonl(logs / "quiet.jsonl")
    quiet_t = {q["idem"]: q["t_ok_ns"] for q in quiet_rows if "idem" in q}
    lat, quiet_lat = [], {}
    per_sec: dict[int, int] = {}
    adm: dict[str, int] = {}
    first_t = last_t = None
    frames_csv = logs / "tap.frames.csv"
    if frames_csv.exists():
        with open(frames_csv) as f:
            rd = csv.reader(f)
            next(rd)
            for t_ns, conn, seq, idem, a_, d_, stream in rd:
                t_ns = int(t_ns)
                adm[f"{a_}/{d_}"] = adm.get(f"{a_}/{d_}", 0) + 1
                if a_ == "verified":
                    s = (t_ns - t0) // 1_000_000_000
                    per_sec[s] = per_sec.get(s, 0) + 1
                    first_t = t_ns if first_t is None else first_t
                    last_t = t_ns
                ts = send_t.get(idem)
                if ts is not None:
                    lat.append((t_ns - ts) / 1e6)
                qt = quiet_t.get(idem)
                if qt is not None and idem not in quiet_lat:
                    quiet_lat[idem] = (t_ns - qt) / 1e6
    r["probe_frames_by_admission"] = adm
    verified = sum(v for k, v in adm.items() if k.startswith("verified/"))
    in_window = sum(v for s, v in per_sec.items() if 0 <= s < duration)
    r["probe_verified_frames"] = verified
    r["probe_verified_rate_in_window"] = round(in_window / duration, 1)
    r["probe_verified_per_s"] = [per_sec.get(s, 0) for s in range(-1, int(duration) + 8)]
    r["latency_send_to_record_ms"] = {"n": len(lat), "p50": percentile(lat, 50), "p90": percentile(lat, 90),
                                      "p99": percentile(lat, 99), "max": max(lat) if lat else None}
    with open(out_dir / "latency_send_to_record.csv", "w") as f:
        f.write("latency_ms\n")
        step = max(1, len(lat) // 20000)
        for x in lat[::step]:
            f.write(f"{x:.3f}\n")
    # pushes, per ear
    pushes_all = {}
    e2e, quiet_push = [], {}
    for e in range(n_ears):
        rows = read_jsonl(logs / f"session{e}.pushes.jsonl")
        shutil.copy(logs / f"session{e}.pushes.jsonl", out_dir / f"session{e}.pushes.jsonl") if rows else None
        recs = 0
        canticle_pushes = [x for x in rows if x.get("meta", {}).get("kind") == "canticle"]
        per_push = [len(x["records"]) for x in canticle_pushes]
        for x in canticle_pushes:
            for st, key, stream, ep, seq in x["records"]:
                from canticle.ids import stream_id
                idem = f"canticle:{key}:{ep}:{stream_id(stream):08x}:{seq}"
                if idem in send_t:
                    e2e.append((x["t_ns"] - send_t[idem]) / 1e6)
                if idem in quiet_t:
                    quiet_push.setdefault(idem, {})[f"ear{e}"] = (x["t_ns"] - quiet_t[idem]) / 1e6
                recs += 1
        pushes_all[f"ear{e}"] = {"pushes": len(canticle_pushes), "records": recs,
                                 "records_per_push_max": max(per_push) if per_push else 0,
                                 "late_lines": sum(len(x.get("late_lines", [])) for x in canticle_pushes),
                                 "loss_lines": sum(len(x.get("loss_lines", [])) for x in canticle_pushes),
                                 "other_events": len(rows) - len(canticle_pushes)}
    r["pushes"] = pushes_all
    r["latency_send_to_push_ms"] = {"n": len(e2e), "p50": percentile(e2e, 50), "p99": percentile(e2e, 99),
                                    "max": max(e2e) if e2e else None}
    if has_quiet:
        r["quiet"] = {"sung": len(quiet_t), "sing_errors": sum(1 for q in quiet_rows if "idem" not in q),
                      "reached_daemon": len(quiet_lat),
                      "pushed_per_ear": {f"ear{e}": sum(1 for v in quiet_push.values() if f"ear{e}" in v)
                                         for e in range(n_ears)},
                      "send_to_record_ms": sorted(quiet_lat.values()),
                      "send_to_push_ms": {k: v for k, v in quiet_push.items()},
                      "missing_at_daemon": [i for i in quiet_t if i not in quiet_lat],
                      "missing_in_push": [i for i in quiet_t if i not in quiet_push]}
    # frond-ear's own view, per ear
    r["frond_ear"] = {}
    for ear, st in statuses.items():
        c = (st or {}).get("canticle", {})
        r["frond_ear"][ear] = {"receiveHealth": c.get("receiveHealth"), "reasons": c.get("reasons"),
                               "counts": c.get("counts"), "joinSnapshot": c.get("joinSnapshot"),
                               **ear_block(st, ear)}
    # processes
    sampler_csv = out_dir / "samples.csv"
    r["processes"] = summarize_samples(sampler_csv) if sampler_csv.exists() else {}
    (out_dir / "timeline.json").write_text(json.dumps(timeline, default=str))
    for f in ("quiet.jsonl", "floodsinger.json", "quiet.json"):
        if (logs / f).exists():
            shutil.copy(logs / f, out_dir / f)
    # error tails of every process, for the record
    errs = {}
    for f in sorted(os.listdir(logs)):
        if f.endswith(".err"):
            txt = (logs / f).read_text(errors="replace")
            lines = [l for l in txt.splitlines() if l.strip()]
            errs[f] = {"lines": len(lines), "tail": lines[-3:]}
    r["stderr"] = errs
    return r
