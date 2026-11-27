"""Shared helpers for the four-quantities measurement (RFC-0002 §7.1, frond-ear#116).

Every instrument here reads; none writes to a live file, sings, hushes, tunes or grants. What they write goes
under the report's ``results/`` directory, and only through ``closed()`` and ``label()``:

- ``closed(value, words)`` keeps a value only when it is one of a closed set of words (or matches a closed
  pattern); anything else becomes ``"other"``. Item text, purposes, state keys, digests, key ids, session ids,
  addresses and station or stream names never reach a results file.
- ``label(kind, name)`` turns a station or ``station:stream`` name into a short salted hash. The salt is drawn
  once per process and never written, so the labels count distinct things within one file and name nothing.

RFC-0001 §18.9 and display grants (#137) keep live station activity off human displays without the station's
consent; this report is public, so it carries counts, never which station did what.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from typing import Iterable, Optional

SALT = secrets.token_bytes(16)
WORD = re.compile(r"^[a-z][a-z0-9_:.-]{0,63}$")

HOME = os.path.expanduser("~")
MANIFEST = os.path.join(HOME, ".binary-canticle", "fleet.json")
FROND_EAR_CONFIG = os.path.join(HOME, ".config", "frond-ear", "frond-ear.json")
FROND_EAR_DB = os.path.join(HOME, ".local", "state", "frond-ear", "frond-ear.db")
FROND_EAR_DIR = os.path.join(HOME, "flesh_beast_best_beast", "source", "frond-ear")
OPENCLAW_CONFIG = os.path.join(HOME, ".openclaw", "openclaw.json")
OPENCLAW_CANTICLE = os.path.join(HOME, ".openclaw", "canticle")
DAEMON_SOCKET = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()),
                             "canticle", "daemon.sock")
SEAT_EAR = "frond-scribe"

# The closed words of receptor record v1 at the running SHA (records.py, ids.py, listener.py).
CLASSES = {"chatter", "ambient", "live-state", "advisory", "finding-ref", "regulatory", "alarm", "control", "root"}
ADMISSIONS = {"verified", "duplicate", "capability_exceeded", "scope_violation", "hop_limit", "over_quota",
              "pluck_mismatch", "plucked", "superseded", "class_change", "equivocation"}
DISPOSITIONS = {"surface", "ringbuffer_only", "drop", "quarantine_set", "no_op"}
RETRACTS = {"plucked", "superseded", "expired", "revoked", "quarantined", "held_expired", "held_plucked",
            "held_superseded"}
PRESENCE = {"EQUIPPED_SPEAKING", "EQUIPPED_QUIET", "UNEQUIPPED_PRESENT", "ROOT_UNKNOWN", "UNOBSERVABLE",
            "UNOBSERVABLE:signed_off"}
SCOPES = {"host", "lan", "fleet", "public"}
HEALTH = {"ok", "degraded"}


def closed(value, words: Optional[Iterable[str]] = None) -> Optional[str]:
    """``value`` if it is one of ``words`` (or, with no set, a short lowercase word); else ``"other"``."""
    if value is None:
        return None
    if not isinstance(value, str):
        return "other"
    if words is not None:
        return value if value in words else "other"
    return value if WORD.match(value) else "other"


def label(kind: str, name) -> Optional[str]:
    if name is None:
        return None
    return kind[0] + hashlib.sha256(SALT + kind.encode() + b"\0" + str(name).encode()).hexdigest()[:6]


def now_ms() -> int:
    return int(time.time() * 1000)


def load_json(path: str):
    with open(path, "rb") as fh:
        return json.loads(fh.read())


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def manifest_entries() -> list:
    """(name, key_id, streams, classes, scopes) per manifest station. Held in memory only."""
    m = load_json(MANIFEST)
    return [(e["name"], e["key_id"].lower(), list(e.get("streams") or []), list(e.get("classes") or []),
             list(e.get("scopes") or [])) for e in m["stations"]]


def parse_tune(pattern: str) -> tuple:
    station, _, stream = pattern.partition(":")
    return station, stream


def tune_matches(patterns: Iterable[str], station: Optional[str], stream: Optional[str]) -> bool:
    """frond-ear's and the OpenClaw plugin's tune: ``station:stream``, where the station half may be ``*``."""
    if station is None or stream is None:
        return False
    for p in patterns:
        s, st = parse_tune(p)
        if (s == "*" or s == station) and st == stream:
            return True
    return False


def seat_canticle_config() -> dict:
    return load_json(FROND_EAR_CONFIG).get("canticle") or {}


def openclaw_canticle_config() -> dict:
    c = load_json(OPENCLAW_CONFIG)
    entry = ((c.get("plugins") or {}).get("entries") or {}).get("canticle") or {}
    return {"enabled": entry.get("enabled") is True, "config": entry.get("config") or {}}


def write_jsonl(fh, obj: dict) -> None:
    fh.write(json.dumps(obj, separators=(",", ":"), sort_keys=True) + "\n")
    fh.flush()
