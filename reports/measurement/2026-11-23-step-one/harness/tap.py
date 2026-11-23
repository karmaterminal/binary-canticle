"""A record v1 probe on the host daemon's socket (RFC §14.18.2-§14.18.3): the measurement's own
binding, beside the frond-ear ears.

It asks for a join snapshot (as frond-ear does), timestamps every line on arrival with
CLOCK_MONOTONIC, and keeps, per connection: record counts by type, `rec_seq` gaps (records the
daemon dropped for this connection, or lost across a reconnect), every `frame` record's idem and
arrival time (for latency, joined later against the producers' send logs) with its admission
and disposition, and every `health` record whole. It reconnects on the frond-ear curve
(1 s·2^n ≤ 30 s) when the daemon goes away, so a restart storm is observed, not survived by luck.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

REQ = b'{"op":"join_snapshot","v":"canticle-receptor-record/1"}\n'


def field(line: bytes, key: bytes) -> bytes | None:
    i = line.find(key)
    if i < 0:
        return None
    i += len(key)
    if line[i:i + 1] == b'"':
        j = line.find(b'"', i + 1)
        return line[i + 1:j]
    j = i
    while j < len(line) and line[j:j + 1] not in (b",", b"}"):
        j += 1
    return line[i:j]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--socket", required=True)
    p.add_argument("--out", required=True, help="prefix for <out>.frames.csv, <out>.health.jsonl, <out>.json")
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--no-snapshot", action="store_true")
    a = p.parse_args()

    deadline = time.monotonic() + a.duration
    frames = open(a.out + ".frames.csv", "w")
    frames.write("t_ns,conn,rec_seq,idem,admission,disposition,stream\n")
    health = open(a.out + ".health.jsonl", "w")
    events = []
    counts: dict[str, int] = {}
    conn = 0
    gaps = gap_records = regressions = 0
    lines = nbytes = 0
    attempt = 0
    while time.monotonic() < deadline:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(a.socket)
        except OSError as e:
            s.close()
            delay = min(30.0, 1.0 * 2 ** min(attempt, 5))
            attempt += 1
            events.append({"t_ns": time.monotonic_ns(), "event": "connect_failed", "error": e.strerror})
            time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
            continue
        attempt = 0
        conn += 1
        events.append({"t_ns": time.monotonic_ns(), "event": "connected", "conn": conn})
        if not a.no_snapshot:
            s.sendall(REQ)
        s.settimeout(0.5)
        buf = b""
        last_seq = None
        boot = 0          # hello and landing_state carry their original rec_seq (§14.18.3 "Joining a run")
        while time.monotonic() < deadline:
            try:
                chunk = s.recv(1 << 20)
            except socket.timeout:
                continue
            except OSError as e:
                events.append({"t_ns": time.monotonic_ns(), "event": "recv_error", "error": str(e)})
                break
            if not chunk:
                events.append({"t_ns": time.monotonic_ns(), "event": "eof", "conn": conn})
                break
            t = time.monotonic_ns()
            nbytes += len(chunk)
            buf += chunk
            *whole, buf = buf.split(b"\n")
            for line in whole:
                if not line:
                    continue
                lines += 1
                typ = (field(line, b'"type":') or b"?").decode()
                counts[typ] = counts.get(typ, 0) + 1
                seq_b = field(line, b'"rec_seq":')
                seq = int(seq_b) if seq_b else None
                if typ in ("snapshot", "snapshot_end"):
                    if typ == "snapshot_end":
                        rec = json.loads(line)
                        events.append({"t_ns": t, "event": "snapshot_end", "conn": conn,
                                       **{k: rec.get(k) for k in ("watermark", "count", "truncated", "omitted")}})
                    continue
                if boot < 2 and typ in ("hello", "landing_state"):
                    boot += 1
                    if typ == "hello":
                        rec = json.loads(line)
                        events.append({"t_ns": t, "event": "hello", "conn": conn, "run": rec.get("run"),
                                       "pid": rec.get("pid")})
                    last_seq = None      # §14.18.3 step 2: the skip to the first live record is never a gap
                    continue
                if seq is not None and last_seq is not None:
                    if seq > last_seq + 1:
                        gaps += 1
                        gap_records += seq - last_seq - 1
                    elif seq <= last_seq:
                        regressions += 1
                if seq is not None:
                    last_seq = seq
                if typ == "frame":
                    idem = (field(line, b'"idem":') or b"").decode()
                    adm = (field(line, b'"admission":') or b"").decode()
                    disp = (field(line, b'"disposition":') or b"").decode()
                    stream = (field(line, b'"stream":') or b"").decode()
                    frames.write(f"{t},{conn},{seq},{idem},{adm},{disp},{stream}\n")
                elif typ == "health":
                    rec = json.loads(line)
                    rec["t_ns"] = t
                    rec["conn"] = conn
                    health.write(json.dumps(rec) + "\n")
                elif typ in ("bye", "fatal", "hello"):
                    rec = json.loads(line)
                    events.append({"t_ns": t, "event": typ, "conn": conn,
                                   **({"reason": rec.get("reason")} if typ == "fatal" else {})})
        s.close()
    frames.close()
    health.close()
    with open(a.out + ".json", "w") as f:
        json.dump({"connections": conn, "lines": lines, "bytes": nbytes, "counts": counts,
                   "rec_seq_gaps": gaps, "rec_seq_gap_records": gap_records, "rec_seq_regressions": regressions,
                   "events": events}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
