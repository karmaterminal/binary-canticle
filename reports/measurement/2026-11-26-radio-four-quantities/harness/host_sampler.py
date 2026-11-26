"""Samples the host's counters through the window, read-only.

Every ``--fast`` seconds (default 10): the host daemon's UDP socket row in ``/proc/net/udp`` (its receive queue
and its kernel ``drops``, the loss no record reports; step one, #171), and the daemon process's CPU ticks and
resident memory.

Every ``--slow`` seconds (default 120):

- ``frond-ear status`` (the CLI's own read of the frond-ear daemon), reduced to closed numeric fields of the
  canticle source, the seat ear's canticle delivery and custody, and the store's ``canticle_*`` counters;
- frond-ear's ``canticle_custody`` table, opened read-only: rows by path, mode and how far each got;
- the OpenClaw canticle binding's state file: how many session checkpoints and heard-text taint marks it holds,
  and how many are newer than the window's start. Never a session key.

Nothing here writes a live file. ``frond-ear status`` is one CLI client connection to the frond-ear daemon per
sample; SQLite opens the store read-only (``mode=ro``), as ``frond-ear exposure`` does.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

CLK = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")
NODE = os.path.join(C.HOME, ".local", "bin", "node")   # the frond-ear unit's node


def daemon_pid() -> int | None:
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv = fh.read().split(b"\0")
        except OSError:
            continue
        if len(argv) > 2 and argv[1].endswith(b"/canticle") and argv[2] == b"daemon":
            return int(pid)
    return None


def socket_inodes(pid: int) -> set:
    out = set()
    try:
        for fd in os.listdir(f"/proc/{pid}/fd"):
            try:
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
            except OSError:
                continue
            if target.startswith("socket:["):
                out.add(target[8:-1])
    except OSError:
        pass
    return out


def udp_row(pid: int) -> dict | None:
    """The daemon's UDP socket in /proc/net/udp, matched by inode: rx_queue (bytes queued) and drops."""
    inodes = socket_inodes(pid)
    with open("/proc/net/udp") as fh:
        next(fh)
        for line in fh:
            f = line.split()
            if f[9] in inodes:
                tx, rx = f[4].split(":")
                return {"rx_queue": int(rx, 16), "tx_queue": int(tx, 16), "drops": int(f[12]),
                        "port": int(f[1].split(":")[1], 16)}
    return None


def proc_stat(pid: int) -> dict:
    with open(f"/proc/{pid}/stat") as fh:
        f = fh.read().rsplit(")", 1)[1].split()
    with open(f"/proc/{pid}/statm") as fh:
        rss_pages = int(fh.read().split()[1])
    return {"cpu_s": (int(f[11]) + int(f[12])) / CLK, "rss_kib": rss_pages * PAGE // 1024,
            "start_ticks": int(f[19])}


def ints(d) -> dict:
    return {k: v for k, v in (d or {}).items() if isinstance(v, int) and isinstance(k, str) and C.WORD.match(k)}


def frond_ear_status() -> dict:
    try:
        p = subprocess.run([NODE, "src/cli.ts", "status"], cwd=C.FROND_EAR_DIR, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": type(e).__name__}
    if p.returncode != 0:
        return {"error": f"exit {p.returncode}"}
    try:
        s = json.loads(p.stdout)
    except ValueError:
        return {"error": "unparsed"}
    can = s.get("canticle") or {}
    live = can.get("liveSet") or {}
    omitted = live.get("omitted") or {}
    out = {
        "canticle": {
            "source": C.closed(can.get("source")), "state": C.closed(can.get("state")),
            "receive_health": C.closed(can.get("receiveHealth")),
            "reasons": [C.closed(r) for r in (can.get("reasons") or [])][:8],
            "join_snapshot": C.closed(can.get("joinSnapshot")),
            "breaker": C.closed(can.get("breaker")),
            "counts": ints(can.get("counts")),
            "live_set": {"size": live.get("size"), "max": live.get("max"),
                         "streams": len(live.get("shares") or {}),
                         "omitted_now": sum(int(o.get("count", 0)) for o in omitted.values()),
                         "omitted_total": sum(int(o.get("total", 0)) for o in omitted.values())},
            "stations_by_state": {},
        },
        "counters": {k: v for k, v in ints(s.get("counters")).items() if k.startswith("canticle")},
    }
    for st in (can.get("stations") or {}).values():   # name -> presence state word (frond-ear records.ts)
        w = C.closed(st.get("state") if isinstance(st, dict) else st, C.PRESENCE)
        out["canticle"]["stations_by_state"][w] = out["canticle"]["stations_by_state"].get(w, 0) + 1
    for ear in s.get("ears") or []:
        if ear.get("name") != C.SEAT_EAR:
            continue
        d = ear.get("canticleDelivery") or {}
        cu = ear.get("canticleCustody") or {}
        ex = ear.get("canticleExposure")
        out["ear"] = {
            "attached": ear.get("attached") is True, "registered": ear.get("registered") is True,
            "delivery": {
                "ceiling": C.closed(d.get("ceiling")), "mode": C.closed(d.get("mode")),
                "station_modes": sorted(C.closed((v or {}).get("mode")) for v in (d.get("stations") or {}).values()),
                "choices": len(d.get("choices") or []), "wake_keys": d.get("wakeKeys"),
                "wake_grants": len(d.get("wakeGrants") or []) if isinstance(d.get("wakeGrants"), list) else None,
                "window_ms": d.get("windowMs"), "debounce_ms": d.get("debounceMs"), "max_age_ms": d.get("maxAgeMs"),
                "waiting": d.get("waiting"), "held": C.closed(d.get("held")),
                "pushes_last_hour": d.get("pushesLastHour"), "max_pushes_per_hour": d.get("maxPushesPerHour"),
                "counts": ints(d.get("counts")),
            },
            "custody": {"window_ms": cu.get("windowMs"), "history": C.closed(cu.get("history")),
                        "counts": ints(cu.get("counts"))},
            "exposure_enabled": ex is not None,
        }
    return out


def custody_counts() -> dict:
    con = sqlite3.connect(f"file:{C.FROND_EAR_DB}?mode=ro", uri=True, timeout=5)
    try:
        rows = con.execute(
            "SELECT path, mode, shown, COUNT(*), SUM(offered_at IS NOT NULL), SUM(echoed_at IS NOT NULL), "
            "MAX(claimed_at) FROM canticle_custody WHERE ear = ? GROUP BY 1, 2, 3", (C.SEAT_EAR,)).fetchall()
        counters = dict(con.execute("SELECT name, value FROM counters WHERE name LIKE 'canticle%'").fetchall())
        exposure = con.execute("SELECT COUNT(*) FROM canticle_exposure").fetchone()[0]
    finally:
        con.close()
    return {"rows": [{"path": C.closed(r[0], {"immediate", "report", "hear"}), "mode": C.closed(r[1]),
                      "shown": C.closed(r[2], {"whole", "cut", "none"}), "n": r[3], "offered": r[4], "echoed": r[5],
                      "last_claimed_at": r[6]} for r in rows],
            "counters": {k: v for k, v in counters.items() if C.WORD.match(k)}, "exposure_rows": exposure}


def openclaw_state(t0: int) -> dict:
    out = {}
    try:
        names = sorted(os.listdir(C.OPENCLAW_CANTICLE))
    except OSError:
        return {"error": "no state dir"}
    for b in names:
        path = os.path.join(C.OPENCLAW_CANTICLE, b, "state.json")
        try:
            s = C.load_json(path)
        except (OSError, ValueError):
            continue
        cp, taint = s.get("checkpoints") or {}, s.get("taint") or {}
        out[C.label("binding", b)] = {
            "checkpoints": len(cp), "checkpoints_since_t0": sum(1 for v in cp.values() if v.get("at", 0) >= t0),
            "taint": len(taint), "taint_since_t0": sum(1 for v in taint.values() if v.get("at", 0) >= t0),
            "taint_overflow": s.get("taint_overflow") is not None, "mutes": len(s.get("mutes") or []),
            "state_mtime_ms": int(os.stat(path).st_mtime * 1000)}
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--fast", type=float, default=10.0)
    p.add_argument("--slow", type=float, default=120.0)
    p.add_argument("--t0", type=int, required=True, help="window start, epoch ms")
    a = p.parse_args()
    start = time.monotonic()
    deadline = start + a.duration
    next_slow = start
    with open(a.out, "w") as out:
        while True:
            now = time.monotonic()
            pid = daemon_pid()
            row = {"kind": "fast", "t": C.now_ms(), "daemon_pid_seen": pid is not None}
            if pid is not None:
                try:
                    row["udp"] = udp_row(pid)
                    row["proc"] = proc_stat(pid)
                except OSError as e:
                    row["error"] = type(e).__name__
            C.write_jsonl(out, row)
            if now >= next_slow or now >= deadline:
                slow = {"kind": "slow", "t": C.now_ms()}
                for name, fn in (("frond_ear", frond_ear_status), ("custody", custody_counts),
                                 ("openclaw", lambda: openclaw_state(a.t0))):
                    try:
                        slow[name] = fn()
                    except Exception as e:   # one failed read is a gap in that series, never a stop
                        slow[name] = {"error": type(e).__name__}
                C.write_jsonl(out, slow)
                next_slow += a.slow
            if now >= deadline:
                break
            time.sleep(max(0.0, min(a.fast, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
