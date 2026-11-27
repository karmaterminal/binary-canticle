"""What the host is configured to carry and to tune, read once at the window's start. Counts, no names.

- the fleet manifest the host daemon loaded (``~/.binary-canticle/fleet.json``; the daemon's ``hello`` carries its
  SHA-256, which ``daemon_records.py`` compares): stations, licensed ``station:stream`` pairs, classes and scopes;
- the stations running on this host (their ``canticle station`` command lines): how many streams each sings and to
  how many peers (never an address);
- the seat's frond-ear tune (``canticle.tune.frond-scribe``), resolved against the manifest, with what frond-ear's
  push boundary does with each resolved pair (``wakeKeys``, delivery mode, wake classes);
- the OpenClaw canticle binding's tune and delivery;
- the code each running process loaded: the git HEADs of the clones they run from, and their start times.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

BC_CLONE = os.path.join(C.HOME, "flesh_beast_best_beast", "source", "binary-canticle")
OC_EXT = os.path.join(C.HOME, ".openclaw", "extensions", "canticle")


def git_head(path: str) -> str | None:
    p = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", path, "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    return (p.stdout.strip() + ("+dirty" if dirty else "")) if p.returncode == 0 else None


def boot_ms() -> int:
    with open("/proc/stat") as fh:
        for line in fh:
            if line.startswith("btime "):
                return int(line.split()[1]) * 1000
    raise RuntimeError("no btime")


def processes() -> list:
    clk, boot = os.sysconf("SC_CLK_TCK"), boot_ms()
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv = [x.decode(errors="replace") for x in fh.read().split(b"\0") if x]
            with open(f"/proc/{pid}/stat") as fh:
                start = int(fh.read().rsplit(")", 1)[1].split()[19])
        except OSError:
            continue
        role = None
        if len(argv) > 2 and argv[1].endswith("/canticle") and argv[2] in ("daemon", "station"):
            role = "canticle " + argv[2]
        elif len(argv) > 2 and argv[1] == "src/cli.ts" and argv[2] == "daemon":
            role = "frond-ear daemon"
        elif any(x.endswith("openclaw/dist/index.js") for x in argv) and "gateway" in argv:
            role = "openclaw gateway"
        if role is None:
            continue
        row = {"role": role, "started_at_ms": boot + start * 1000 // clk}
        if role == "canticle station":
            row["streams"] = argv.count("--stream")
            row["peers"] = argv.count("--to")
            row["beacon_ms"] = int(argv[argv.index("--beacon-ms") + 1]) if "--beacon-ms" in argv else 1000
        if role == "canticle daemon":
            row["multicast"] = "--no-multicast" not in argv
        out.append(row)
    return sorted(out, key=lambda r: (r["role"], r["started_at_ms"]))


def ext_digest() -> dict:
    """SHA-256 over the OpenClaw extension's src/*.ts and index.ts, to name the prototype commit it was copied from."""
    files = sorted(os.listdir(os.path.join(OC_EXT, "src")))
    h = hashlib.sha256()
    per = {}
    for f in ["index.ts"] + [os.path.join("src", x) for x in files]:
        with open(os.path.join(OC_EXT, f), "rb") as fh:
            b = fh.read()
        per[f] = hashlib.sha256(b).hexdigest()
        h.update(f.encode() + b"\0" + b)
    return {"files": per, "all": h.hexdigest()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    a = p.parse_args()

    m = C.load_json(C.MANIFEST)
    entries = C.manifest_entries()
    classes: dict = {}
    for _n, _k, _s, cl, _sc in entries:
        for c in cl:
            classes[c] = classes.get(c, 0) + 1
    manifest = {
        "format": C.closed(m.get("manifest"), {"canticle-fleet/spike-0"}), "signed": m.get("signed") is True, "stations": len(entries),
        "licensed_pairs": sum(len(e[2]) for e in entries),
        "streams_per_station": sorted((len(e[2]) for e in entries), reverse=True),
        "distinct_stream_names": len({s for e in entries for s in e[2]}),
        "stations_per_class": dict(sorted(classes.items())),
        "scopes_per_station": sorted(len(e[4]) for e in entries),
        "revoked": sum(1 for e in m["stations"] if e.get("revoked")),
        "public_streams": sum(len(e.get("public_streams") or []) for e in m["stations"]),
        "sha256_prefix": C.sha256_file(C.MANIFEST)[:12],
        "mtime_ms": int(os.stat(C.MANIFEST).st_mtime * 1000),
    }

    can = C.seat_canticle_config()
    tune = list((can.get("tune") or {}).get(C.SEAT_EAR) or [])
    wake = {}
    for k in can.get("wakeKeys") or []:
        wake.update({k.lower(): ["alarm"]} if isinstance(k, str) else {str(k["key"]).lower(): list(k.get("classes") or ["alarm"])})
    deliv = (can.get("delivery") or {}).get(C.SEAT_EAR) or {}
    smodes = {str(s).lower(): v for s, v in (deliv.get("stations") or {}).items()}
    patterns = []
    for i, pat in enumerate(tune, 1):
        s, st = C.parse_tune(pat)
        pairs = [(e, st) for e in entries if (s == "*" or s == e[0]) and st in e[2]]
        rows = []
        for e, stream in pairs:
            modes = [smodes[x] for x in (e[0].lower(), e[1]) if x in smodes]
            mode = min(modes, key=lambda x: {"off": 0, "digest": 1, "immediate": 2}.get(x, 0)) if modes \
                else deliv.get("mode", "off")
            rows.append({"allowlisted": e[1] in wake, "mode": C.closed(mode),
                         "wake_classes_x_licensed": sorted(set(wake.get(e[1], [])) & set(e[3])),
                         "licensed_classes": sorted(e[3])})
        patterns.append({"pattern": f"P{i}", "station_wildcard": s == "*", "matches": len(pairs), "pairs": rows})
    seat = {
        "enabled": can.get("enabled") is True, "source": C.closed(can.get("source")),
        "binding": C.closed(can.get("binding"), C.SCOPES), "patterns": patterns,
        "resolved_pairs": sum(p["matches"] for p in patterns),
        "resolved_stations": len({e[0] for pat in tune for e in entries
                                  if (C.parse_tune(pat)[0] in ("*", e[0])) and C.parse_tune(pat)[1] in e[2]}),
        "wake_keys": len(wake), "wake_keys_bare": sum(1 for k in can.get("wakeKeys") or [] if isinstance(k, str)),
        "delivery_ceiling": C.closed(deliv.get("mode", "off")),
        "delivery_station_entries": len(smodes),
        "exposure_enabled": (can.get("exposure") or {}).get("enabled") is True,
        "muted": can.get("muted") is True,
        "config_mtime_ms": int(os.stat(C.FROND_EAR_CONFIG).st_mtime * 1000),
    }

    oc = C.openclaw_canticle_config()
    occ = oc["config"]
    oc_tune = list(((occ.get("listen") or {}).get("tune")) or [])
    openclaw = {
        "enabled": oc["enabled"], "tune_patterns": len(oc_tune),
        "resolved_pairs": sum(1 for pat in oc_tune for e in entries
                              if C.parse_tune(pat)[0] in ("*", e[0]) and C.parse_tune(pat)[1] in e[2]),
        "payload_sessions": len(((occ.get("listen") or {}).get("payloadSessions")) or []),
        "include_self": ((occ.get("listen") or {}).get("includeSelf")) is True,
        "delivery_mode": C.closed((occ.get("delivery") or {}).get("mode")),
        "publish_enabled": ((occ.get("publish") or {}).get("enabled")) is True,
        "extension_digest": ext_digest(),
    }

    res = {
        "t": C.now_ms(), "manifest": manifest, "seat_frond_ear": seat, "openclaw_binding": openclaw,
        "processes": processes(),
        "code": {"binary_canticle_clone": git_head(BC_CLONE), "frond_ear_clone": git_head(C.FROND_EAR_DIR)},
        "host": {"uname": " ".join(os.uname()[i] for i in (0, 2, 4)), "nproc": os.cpu_count()},
    }
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
