"""Operator-started, one-actor Mirari's Wake fixture worker. No model or transcript access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import time
from pathlib import Path

MAX_LINE = 4096
MAX_ROWS = 16
MAX_ITEM = 800
KINDS = {"event", "tool", "file", "summary"}
SAFE_TOPIC = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.,:/#-]{0,63}$")
SECRET = re.compile(r"(?i)(?:api[_-]?key|token|password|secret|authorization|bearer|private[_-]?key|sk-[a-z0-9]|gh[pousr]_[a-z0-9]|AKIA[0-9A-Z]{16})")
HEARD = re.compile(r"(?i)(?:canticle|heard|receiver|receptor|wake|beacon)")
ID = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")


def _check_file(path: Path) -> None:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise ValueError("source must be a regular non-symlink file")


def _load_json(path: Path) -> dict:
    _check_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        os.chmod(tmp, 0o600)
        json.dump(obj, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def authorization(path: Path, source: Path, actor: str) -> dict:
    cfg = _load_json(path)
    if cfg.get("enabled") is not True or cfg.get("actor") != actor:
        raise ValueError("source authorization disabled or actor mismatch")
    if not ID.fullmatch(actor) or not ID.fullmatch(cfg.get("station", "")):
        raise ValueError("invalid actor/station")
    if cfg.get("source") != str(source.resolve()) or cfg.get("audience") != "lan":
        raise ValueError("source and LAN audience must be explicit")
    if cfg.get("stream") != "wake" or not 1 <= cfg.get("ttl_s", 0) <= 300:
        raise ValueError("wake stream and TTL <=300 required")
    if not 30 <= cfg.get("cadence_s", 0) <= 3600 or not 30 <= cfg.get("inactive_s", 0) <= 86400:
        raise ValueError("cadence/inactivity outside bounded range")
    return cfg


def read_rows(source: Path, actor: str, after: int, seen: set[str]) -> tuple[list[dict], int]:
    _check_file(source)
    if source.stat().st_size > 1_048_576:
        raise ValueError("source exceeds 1 MiB fixture bound")
    rows = []
    with source.open("rb") as inp:
        for n, raw in enumerate(inp, 1):
            if n <= after:
                continue
            if len(raw) > MAX_LINE:
                raise ValueError("oversized source row")
            row = json.loads(raw)
            if row.get("actor") != actor or row.get("kind") not in KINDS:
                continue
            # Only actor-authored, explicitly shareable metadata; no tool result or log body.
            if row.get("origin") != "actor" or row.get("shareable") is not True:
                continue
            if row.get("lineage") != "local" or row.get("kind") == "summary" and row.get("from_canticle"):
                continue
            topic = row.get("topic")
            if not isinstance(topic, str) or not SAFE_TOPIC.fullmatch(topic) or SECRET.search(topic) or HEARD.search(topic):
                continue
            event_id = row.get("id")
            if not isinstance(event_id, str) or not ID.fullmatch(event_id) or event_id in seen:
                continue
            rows.append({"id": event_id, "kind": row["kind"], "topic": topic})
            if len(rows) >= MAX_ROWS:
                return rows, n
        return rows, n if 'n' in locals() else 0


def summarize(actor: str, station: str, rows: list[dict], source: Path) -> tuple[str, str]:
    unique = list({r["id"]: r for r in rows}.values())
    lineage = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    identity = hashlib.sha256(json.dumps([actor, lineage, sorted(r["id"] for r in unique)]).encode()).hexdigest()[:16]
    labels = list(dict.fromkeys(r["topic"] for r in unique))[:5]
    text = f"actor {actor}; observed {len(unique)} shareable actions: {', '.join(labels)}; source sha256:{lineage}; row:{identity}"
    if SECRET.search(text) or len(text.encode()) > MAX_ITEM:
        raise ValueError("unsafe or oversized beacon")
    return text, identity


def station_sink(path: str, req: dict) -> dict:
    # This is the station control socket, not the receptor-only host daemon socket.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(path)
        sock.sendall((json.dumps(req) + "\n").encode())
        response = b""
        while not response.endswith(b"\n"):
            part = sock.recv(4096)
            if not part or len(response) + len(part) > 4096:
                raise RuntimeError("invalid station response")
            response += part
    result = json.loads(response)
    if result.get("ok") is not True:
        raise RuntimeError("station refused publish")
    return result


def tick(*, auth: Path, source: Path, state: Path, actor: str, socket_path: str, sink=station_sink, now=None) -> str:
    now = time.time() if now is None else now
    cfg = authorization(auth, source, actor)  # re-check revocation every cadence
    old = _load_json(state) if state.exists() else {}
    if old and (old.get("actor") != actor or old.get("source") != str(source.resolve())):
        raise ValueError("state bound to a different source")
    seen = set(old.get("seen", []))
    rows, end = read_rows(source, actor, old.get("offset", 0), seen)
    if end < old.get("offset", 0):
        raise ValueError("source shrank; operator must inspect before resetting state")
    if not rows:
        if now - old.get("last_activity", now) >= cfg["inactive_s"]:
            return "inactive-stop"
        _save(state, {**old, "actor": actor, "source": str(source.resolve()),
                      "offset": end, "last_activity": old.get("last_activity", now)})
        return "idle"
    text, identity = summarize(actor, cfg["station"], rows, source)
    if identity != old.get("identity"):
        req = {"op": "sing", "stream": "wake", "class": "chatter", "scope": "lan",
               "ttl": cfg["ttl_s"], "text": text, "state_key": f"wake-{identity}"}
        sink(socket_path, req)
    seen.update(r["id"] for r in rows)
    _save(state, {"actor": actor, "source": str(source.resolve()), "offset": end,
                  "identity": identity, "last_activity": now, "seen": sorted(seen)})
    return "published"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--auth", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--station-socket", required=True)
    a = p.parse_args()
    while True:
        cfg = authorization(a.auth, a.source, a.actor)
        result = tick(auth=a.auth, source=a.source, state=a.state, actor=a.actor,
                      socket_path=a.station_socket)
        if result == "inactive-stop":
            return
        time.sleep(cfg["cadence_s"])


if __name__ == "__main__":
    main()
