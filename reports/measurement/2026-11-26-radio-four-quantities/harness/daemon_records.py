"""A read-only record v1 client of the live host daemon: what reaches the host's bindings, as closed fields.

One more binding connection on the daemon's unix socket (RFC-0001 §11.1, §14.18.2), like ``canticle tap`` or
frond-ear's record client, except that it prints nothing heard. It asks for the join snapshot (as frond-ear
does) so the window starts from what is live, then follows the live records until ``--duration`` ends. It binds
no UDP port, sends nothing but the one join-snapshot line, writes no state of the daemon's and wakes nothing.

Each record becomes one JSONL line built from a closed list (``project``): types, counters, sizes, ages and
closed words. A frame's body text, purpose, state key, lens, lineage, digests, idem, key ids and names are
dropped; a station or stream becomes a salted label (common.label). Three booleans say whether the frame's
station:stream is on the seat's frond-ear tune, on the OpenClaw binding's tune, and where frond-ear's own
pass-over order (delivery.ts ``#passOver``) would put it: a model, cross-checked against frond-ear's counts.

Observer effect: one of the daemon's 16 connections, one more copy of each record in its fan-out, and one
``snapshots.requested``/``served`` in the daemon's health counters. If this reader stalled past the
connection's 1 024-record queue, the daemon would count ``records.dropped`` (health ``records_lost``), seen by
every binding; it reads continuously, and the summary checks ``records.dropped`` did not move.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

REQ = b'{"op":"join_snapshot","v":"canticle-receptor-record/1"}\n'


class Model:
    """The seat's and the OpenClaw binding's tune and the seat's push boundary, from their live configs."""

    def __init__(self):
        self.entries = C.manifest_entries()
        self.by_name = {e[0]: e for e in self.entries}
        self.by_key = {e[1]: e for e in self.entries}
        can = C.seat_canticle_config()
        self.seat_tune = list((can.get("tune") or {}).get(C.SEAT_EAR) or [])
        self.wake = {}
        for k in can.get("wakeKeys") or []:
            if isinstance(k, str):
                self.wake[k.lower()] = {"alarm"}            # a bare key: alarm only (#176 decision 1)
            else:
                self.wake[str(k.get("key")).lower()] = set(k.get("classes") or ["alarm"])
        d = (can.get("delivery") or {}).get(C.SEAT_EAR) or {}
        self.ceiling = d.get("mode", "off")
        self.station_modes = {str(s).lower(): m for s, m in (d.get("stations") or {}).items()}
        oc = C.openclaw_canticle_config()
        self.oc_tune = list(((oc["config"].get("listen") or {}).get("tune")) or []) if oc["enabled"] else []

    def mode(self, station: str, key: str) -> str:
        ms = [self.station_modes[x] for x in (station.lower(), key) if x in self.station_modes]
        if not ms:
            return self.ceiling
        rank = {"off": 0, "digest": 1, "immediate": 2}
        return min(ms, key=lambda m: rank.get(m, 0))       # where name and key id both have one, the narrower

    def seat_gate(self, station, stream, cls, hop, wake_derived) -> str:
        if not C.tune_matches(self.seat_tune, station, stream):
            return "untuned"
        e = self.by_name.get(station)
        key = e[1] if e else None
        if key not in self.wake:
            return "not_allowlisted"
        if hop != 0:
            return "relayed"
        if wake_derived:
            return "wake_derived"
        if self.mode(station, key) == "off":
            return "off"
        if cls not in set(e[3]):
            return "not_capable"
        if cls not in self.wake[key]:
            return "wake_withheld:" + C.closed(cls, C.CLASSES)
        return "eligible"


def project_frame(rec: dict, model: Model, source: str) -> dict:
    st = rec.get("station") or {}
    name, stream = st.get("name"), rec.get("stream")
    fr = rec.get("frame") or {}
    times = rec.get("times") or {}
    flags = rec.get("flags") or {}
    body = rec.get("body") or {}
    cls = rec.get("class")
    hop = rec.get("hop")
    out = {
        "source": source,
        "station": C.label("station", name),
        "stream": C.label("stream", f"{name}:{stream}"),
        "class": C.closed(cls, C.CLASSES),
        "kind": C.closed(fr.get("kind"), {"item", "pluck"}),
        "frame_bytes": fr.get("bytes") if isinstance(fr.get("bytes"), int) else None,
        "admission": C.closed(rec.get("admission"), C.ADMISSIONS),
        "disposition": C.closed(rec.get("disposition"), C.DISPOSITIONS),
        "dedup": C.closed(rec.get("dedup"), {"first", "resurfaced"}),
        "reasons": [C.closed(r) for r in (rec.get("reasons") or [])][:8],
        "scope": C.closed(rec.get("scope"), C.SCOPES),
        "hop": hop if isinstance(hop, int) else None,
        "refresh": bool(flags.get("refresh")),
        "wake_derived": bool(flags.get("wake_derived")),
        "age_ms": times.get("age_ms") if isinstance(times.get("age_ms"), int) else None,
        "ttl_left_ms": (times["local_expiry_at"] - times["received_at"])
        if isinstance(times.get("local_expiry_at"), int) and isinstance(times.get("received_at"), int) else None,
        "body_size": body.get("size") if isinstance(body.get("size"), int) else None,
        "body_ctype": C.closed(body.get("ctype"), {"text/plain; charset=utf-8", "application/cbor", "other"})
        if body else None,
        "body_ref": "body_ref" in rec,
        "tuned_seat": C.tune_matches(model.seat_tune, name, stream),
        "tuned_openclaw": C.tune_matches(model.oc_tune, name, stream),
        "seat_gate_model": model.seat_gate(name, stream, cls, hop, bool(flags.get("wake_derived"))),
    }
    return out


def project_health(rec: dict) -> dict:
    ages = rec.get("beacon_age_ms") or {}
    ages = sorted(int(v) for v in ages.values() if isinstance(v, (int, float)))
    unv = rec.get("unverified") or {}
    counters = rec.get("counters") or {}
    return {
        "state": C.closed(rec.get("state"), C.HEALTH),
        "reasons": [C.closed(r) for r in (rec.get("reasons") or [])][:8],
        "counters": {g: {k: v for k, v in (counters.get(g) or {}).items() if isinstance(v, int) and C.WORD.match(k)}
                     for g in ("admission", "disposition", "retract", "beacon", "unverified")},
        # The D34 table of unverified key ids: how many ids and datagrams, never the ids.
        "unverified_keys": {"ids": len(unv.get("key_ids") or []),
                            "counted": sum(int(r.get("count", 0)) for r in (unv.get("key_ids") or [])),
                            "other": unv.get("other") if isinstance(unv.get("other"), int) else None}
        if isinstance(unv, dict) else None,
        "dedup": {k: v for k, v in (rec.get("dedup") or {}).items() if isinstance(v, int)},
        "beacon_ages_ms": ages,
        "surfaced": rec.get("surfaced") if isinstance(rec.get("surfaced"), int) else None,
        "quarantined": len(rec.get("quarantined") or []),
        "records": {k: v for k, v in (rec.get("records") or {}).items() if isinstance(v, int)},
        "snapshots": {k: v for k, v in (rec.get("snapshots") or {}).items() if isinstance(v, int)},
        "last_datagram_at": rec.get("last_datagram_at") if isinstance(rec.get("last_datagram_at"), int) else None,
    }


def project(rec: dict, model: Model, manifest_sha: str, source: str = "live") -> dict:
    t = C.closed(rec.get("type"), {"hello", "landing_state", "presence", "frame", "retract", "health", "snapshot",
                                    "snapshot_end", "fatal", "bye"})
    out: dict = {"type": t, "rec_seq": rec.get("rec_seq") if isinstance(rec.get("rec_seq"), int) else None,
                 "run": str(rec.get("run") or "")[:8]}
    if t == "hello":
        out.update(wire_version=rec.get("wire_version"), transport=C.closed(rec.get("transport")),
                   multicast=rec.get("multicast") is not None, join_snapshot=rec.get("join_snapshot") is True,
                   manifest_matches_local_file=rec.get("manifest_sha256") == manifest_sha,
                   rule_version=C.closed(rec.get("rule_version"), {"canticle-station/0.1.0+bc2"}))
    elif t == "landing_state":
        out.update(muted=rec.get("mute") is not None, breaker=C.closed(rec.get("breaker"), {"closed", "open", "half_open"}),
                   modulation=len(rec.get("modulation") or []))
    elif t == "presence":
        st = rec.get("station") or {}
        out.update(source=source, station=C.label("station", st.get("name")),
                   state=C.closed(rec.get("state"), C.PRESENCE))
    elif t == "frame":
        out.update(project_frame(rec, model, source))
    elif t == "retract":
        tgt = rec.get("target") or {}
        e = model.by_key.get(str(tgt.get("key_id", "")).lower())
        out.update(reason=C.closed(rec.get("reason"), C.RETRACTS), station=C.label("station", e[0] if e else None))
    elif t == "health":
        out.update(project_health(rec))
    elif t == "snapshot":
        # An entry is {"presence": <presence record fields>} or {"frame": <frame record fields>} (records.py).
        entry = rec.get("entry") or {}
        kind = "presence" if "presence" in entry else "frame" if "frame" in entry else None
        inner = project({**(entry.get(kind) or {}), "type": kind, "rec_seq": rec.get("rec_seq"), "run": rec.get("run")},
                        model, manifest_sha, source="snapshot") if kind else {"type": "other"}
        out.update(snap_seq=rec.get("snap_seq"), entry=inner)
    elif t == "snapshot_end":
        out.update(count=rec.get("count"), truncated=rec.get("truncated") is True, omitted=rec.get("omitted"))
    elif t in ("fatal", "bye"):
        out.update(reason=C.closed(rec.get("reason")))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--socket", default=C.DAEMON_SOCKET)
    p.add_argument("--out", required=True, help="JSONL file of projected records")
    p.add_argument("--duration", type=float, required=True, help="seconds")
    a = p.parse_args()

    model = Model()
    manifest_sha = C.sha256_file(C.MANIFEST)
    deadline = time.monotonic() + a.duration
    attempt = 0
    with open(a.out, "w") as out:
        C.write_jsonl(out, {"type": "_probe", "event": "start", "t": C.now_ms(), "duration_s": a.duration})
        while time.monotonic() < deadline:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(a.socket)
            except OSError as e:
                C.write_jsonl(out, {"type": "_probe", "event": "connect_failed", "t": C.now_ms(),
                                    "errno": getattr(e, "errno", None)})
                s.close()
                time.sleep(min(30.0, 2.0 ** attempt))
                attempt += 1
                continue
            attempt = 0
            C.write_jsonl(out, {"type": "_probe", "event": "connected", "t": C.now_ms()})
            s.sendall(REQ)
            s.settimeout(1.0)
            buf = b""
            ended = None
            while time.monotonic() < deadline:
                try:
                    data = s.recv(65536)
                except socket.timeout:
                    continue
                except OSError as e:
                    ended = f"error:{getattr(e, 'errno', None)}"
                    break
                if not data:
                    ended = "eof"
                    break
                buf += data
                while True:
                    nl = buf.find(b"\n")
                    if nl < 0:
                        break
                    line, buf = buf[:nl], buf[nl + 1:]
                    t, tm = C.now_ms(), time.monotonic_ns()
                    try:
                        rec = json.loads(line)
                        obj = project(rec, model, manifest_sha) if isinstance(rec, dict) else {"type": "other"}
                    except ValueError:
                        obj = {"type": "_unparsed"}
                    obj.update(t=t, tm=tm, line_bytes=len(line) + 1)
                    C.write_jsonl(out, obj)
            s.close()
            C.write_jsonl(out, {"type": "_probe", "event": "disconnected", "t": C.now_ms(), "why": ended or "deadline"})
        C.write_jsonl(out, {"type": "_probe", "event": "end", "t": C.now_ms()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
