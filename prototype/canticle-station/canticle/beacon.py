"""Typed beacons (#142): what a station says about itself, as shape a display can draw and a familiar can count.

A beacon is a keyed ``live-state`` item that a station sings on its own stream ``beacon`` with ``state_key`` ``beacon``.
Its body is a versioned CBOR map of enumerated fields, never prose:

- ``v``: 1, the only version this code reads; any other is refused, so a later shape cannot be misread as this one;
- ``state``: ``working``, ``resting``, ``blocked`` or ``away``;
- ``asking``: ``none``, ``review``, ``peer`` or ``human``;
- ``origin``: ``reported`` (the station says it about itself) or ``inferred`` (a familiar's conclusion). On a station's
  own ``beacon`` stream only ``reported`` is read: an inference cannot pass for testimony (🩸 on #142);
- ``until`` (optional): epoch milliseconds after which the beacon no longer stands. It is enforced: past it, a reader
  shows the station as unknown even while the item is still on air (🌫 on #142);
- ``refs`` (optional): at most four pointers like ``binary-canticle#142`` or ``#142``, never text.

Who sang a beacon comes only from the verified record's station, never from a field in the body. ``asking`` is
descriptive: it says what the station would welcome, and nothing that reads a beacon acts on it. ``refs`` are inert
pointers. A beacon is something to look at, never an order.

The carrier gives the rest, as for display grants (#137): only the station's key can sing it and the daemon admits it
only after verifying that key (own-key-only); the listener's high-water mark per (key, stream, state_key) keeps an
older beacon from coming back over a newer one or over a pluck; the TTL (at most 900 s, the class maximum) bounds how
long a silent station's last beacon stands. A reader treats a missing or expired beacon as "unknown", never as "fine".
"""

from __future__ import annotations

import base64
import re
from typing import Optional

from . import cbor

STREAM = "beacon"
CLASS = "live-state"
STATE_KEY = "beacon"
CTYPE = 2                       # application/cbor
CTYPE_NAME = "application/cbor"
VERSION = 1
MAX_TTL_S = 900                 # the live-state class maximum
STATES = ("working", "resting", "blocked", "away")
ASKING = ("none", "review", "peer", "human")
ORIGINS = ("reported", "inferred")
MAX_REFS = 4
REF_RE = re.compile(r"^(?:[a-z0-9][a-z0-9._-]{0,39})?#[1-9][0-9]{0,6}$")
MAX_UNTIL_MS = 2 ** 53          # the largest integer a JSON reader keeps exactly
FIELDS = frozenset({"v", "state", "asking", "origin", "until", "refs"})


class BeaconError(ValueError):
    pass


def _enum(name: str, value, allowed: tuple) -> str:
    if not isinstance(value, str) or value not in allowed:   # type first: a list or map is unhashable (🌫 on #140)
        raise BeaconError(f"{name} must be one of {', '.join(allowed)}")
    return value


def _until(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < MAX_UNTIL_MS:
        raise BeaconError("until must be a positive integer of epoch milliseconds")
    return value


def _refs(value) -> tuple:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > MAX_REFS:
        raise BeaconError(f"refs must be a list of at most {MAX_REFS}")
    for r in value:
        if not isinstance(r, str) or not REF_RE.match(r):
            raise BeaconError(f"a ref must match {REF_RE.pattern}")
    if len(set(value)) != len(value):
        raise BeaconError("refs repeat")
    return tuple(value)


def encode(state: str, asking: str = "none", until: Optional[int] = None, refs=(), origin: str = "reported") -> bytes:
    body = {"v": VERSION, "state": _enum("state", state, STATES), "asking": _enum("asking", asking, ASKING),
            "origin": _enum("origin", origin, ORIGINS)}
    if _until(until) is not None:
        body["until"] = until
    refs = _refs(list(refs) if refs else None)
    if refs:
        body["refs"] = list(refs)
    return cbor.encode(body)


def decode(raw: bytes) -> dict:
    """The beacon in ``raw``, or BeaconError. Anything but exactly the known fields, with known values, is refused."""
    try:
        body = cbor.decode(raw)
    except Exception as e:  # the codec's own errors are not part of this module's contract
        raise BeaconError(f"not CBOR: {e}") from None
    if not isinstance(body, dict) or not all(isinstance(k, str) for k in body) or not set(body) <= FIELDS:
        raise BeaconError("not a beacon map")
    v = body.get("v")
    if isinstance(v, bool) or v != VERSION:   # True == 1 in Python: a bool is not a version
        raise BeaconError(f"unknown beacon version {v!r}")
    for required in ("state", "asking", "origin"):
        if required not in body:
            raise BeaconError(f"{required} is missing")
    return {"v": VERSION, "state": _enum("state", body["state"], STATES),
            "asking": _enum("asking", body["asking"], ASKING), "origin": _enum("origin", body["origin"], ORIGINS),
            "until": _until(body.get("until")), "refs": _refs(body.get("refs"))}


def names(r: dict) -> bool:
    """Whether frame record ``r`` is a beacon item by its carrier: stream, class and state key."""
    return r.get("stream") == STREAM and r.get("class") == CLASS and r.get("state_key") == STATE_KEY


def _from_record(r: dict) -> Optional[dict]:
    if not names(r):
        return None
    body = r.get("body")
    if not isinstance(body, dict) or body.get("ctype") not in (CTYPE, CTYPE_NAME) \
            or not isinstance(body.get("base64"), str):
        return None
    try:
        b = decode(base64.b64decode(body["base64"], validate=True))
    except (BeaconError, ValueError, TypeError):   # a signature authenticates the sender, not this body
        return None
    return b if b["origin"] == "reported" else None   # a station's own stream carries testimony only


def read(view, allowed, now_ms: int) -> dict:
    """Each station in ``allowed`` that has a live, verified, well-formed beacon, mapped to
    ``{"state", "asking", "until", "refs", "generation", "issued_at"}``. ``generation`` is the item's (epoch, seq).

    A station absent from the result is **unknown**: no beacon, an expired one (by TTL or by ``until``), one this code
    cannot read, or a view
    that cannot vouch for what it holds (not ready, or carried across a gap; ``view.live`` leaves those out)."""
    allowed = set(allowed)
    out: dict = {}
    if view is None or not view.ready:
        return out
    for r in view.live(now_ms):   # surfaced, verified, unexpired, not carried across a gap
        name = (r.get("station") or {}).get("name")
        if name not in allowed:
            continue
        b = _from_record(r)
        if b is None or (b["until"] is not None and now_ms >= b["until"]):   # until is an expiry, not a hint
            continue
        f = r.get("frame") or {}
        gen = (int(f.get("epoch") or 0), int(f.get("seq") or 0))
        if name not in out or gen > out[name]["generation"]:
            out[name] = {"state": b["state"], "asking": b["asking"], "until": b["until"], "refs": b["refs"],
                         "generation": gen, "issued_at": (r.get("times") or {}).get("issued_at")}
    return out
