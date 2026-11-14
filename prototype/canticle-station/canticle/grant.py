"""Display grants (#137): the prince, not the host, says yes to the shape display.

A grant is a keyed ``live-state`` item that a station sings on stream ``display`` with ``state_key``
``grant:<display>``.  Its body is a CBOR map ``{"display": <name>, "scope": <tier>}``, plus ``"withheld": true`` when
the prince chooses to show that further telemetry is withheld (only beside ``presence``).

The carrier already gives what a grant needs:
- only the holder of the station's key can sing it, and the daemon admits it only after verifying that key;
- the listener keeps a high-water mark per (key, stream, state_key), so an older grant cannot come back over a newer
  one or over a pluck;
- its TTL is the lease (the ``live-state`` class allows at most 900 s), so a display cut off from the network loses
  the grant within that bound;
- a pluck, signed with the same key, revokes it wherever it arrives.

Tiers are cumulative, smallest first: ``presence`` (that the station exists and its presence state), ``beacon``
(carrier age and beacon history), ``counts`` (arrivals per stream per minute, live counts and their ages), ``river``
(each arrival as a time and a stream).  A grant means only what the station's key means: a key kept on a host the
prince does not control lets that host say yes for the prince.
"""

from __future__ import annotations

import base64
import re
from typing import Optional

from . import cbor

STREAM = "display"
CLASS = "live-state"
CTYPE = 2                       # application/cbor
CTYPE_NAME = "application/cbor"
TIERS = ("presence", "beacon", "counts", "river")
RANK = {t: i for i, t in enumerate(TIERS)}
MAX_TTL_S = 900                 # the live-state class maximum: the lease
DISPLAY_RE = re.compile(r"^[a-z0-9][a-z0-9._@-]{0,63}$")


class GrantError(ValueError):
    pass


def state_key(display: str) -> str:
    return f"grant:{display}"


def check_display(display: str) -> str:
    if not isinstance(display, str) or not DISPLAY_RE.match(display):
        raise GrantError(f"display name must match {DISPLAY_RE.pattern}")
    return display


def encode(display: str, scope: str, withheld: bool = False) -> bytes:
    check_display(display)
    if scope not in RANK:
        raise GrantError(f"scope must be one of {', '.join(TIERS)}")
    if withheld and scope != "presence":
        raise GrantError("withheld goes only with scope presence")
    body = {"display": display, "scope": scope}
    if withheld:
        body["withheld"] = True
    return cbor.encode(body)


def decode(raw: bytes) -> dict:
    """The grant in ``raw``, or GrantError.  Anything but exactly the known fields, with known values, is refused."""
    try:
        body = cbor.decode(raw)
    except Exception as e:  # the codec's own errors are not part of this module's contract
        raise GrantError(f"not CBOR: {e}") from None
    if not isinstance(body, dict) or not all(isinstance(k, str) for k in body) \
            or not set(body) <= {"display", "scope", "withheld"}:
        raise GrantError("not a grant map")
    display, scope, withheld = body.get("display"), body.get("scope"), body.get("withheld", False)
    check_display(display)
    if not isinstance(scope, str) or scope not in RANK:   # type first: a list or map is unhashable (🌫 on #140)
        raise GrantError("unknown scope")
    if withheld is not True and withheld is not False:
        raise GrantError("withheld is not a boolean")
    if withheld and scope != "presence":
        raise GrantError("withheld goes only with scope presence")
    return {"display": display, "scope": scope, "withheld": withheld}


def names(r: dict, display: str) -> bool:
    """Whether frame record ``r`` is a grant item for ``display`` by its carrier: stream, class and state key."""
    return r.get("stream") == STREAM and r.get("class") == CLASS and r.get("state_key") == state_key(display)


def _from_record(r: dict, display: str) -> Optional[dict]:
    if not names(r, display):
        return None
    body = r.get("body")
    if not isinstance(body, dict) or body.get("ctype") not in (CTYPE, CTYPE_NAME) \
            or not isinstance(body.get("base64"), str):
        return None
    try:
        g = decode(base64.b64decode(body["base64"], validate=True))
    except (GrantError, ValueError, TypeError):   # a signature authenticates the sender, not this body
        return None
    return g if g["display"] == display else None


def read(view, display: str, allowed, now_ms: int) -> tuple:
    """(grants, proof) from a connection's view.

    ``grants`` maps each station in ``allowed`` (the host's ceiling) that holds a live, verified grant for ``display``
    to ``{"scope", "withheld", "generation"}``.  ``generation`` is the item's (epoch, seq): a new one is a new grant.

    ``proof`` says whether a station's absence from ``grants`` proves it holds none: only a ready view with a complete
    join snapshot and no records lost can say so.  Without proof the caller hides the station and keeps what it holds;
    with proof it purges."""
    allowed = set(allowed)
    grants: dict = {}
    if view is None or not view.ready:
        return grants, False
    for r in view.live(now_ms):   # surfaced, verified, unexpired, not carried across a gap
        name = (r.get("station") or {}).get("name")
        if name not in allowed:
            continue
        g = _from_record(r, display)
        if g is None:
            continue
        f = r.get("frame") or {}
        gen = (int(f.get("epoch") or 0), int(f.get("seq") or 0))
        if name not in grants or gen > grants[name]["generation"]:
            grants[name] = {"scope": g["scope"], "withheld": g["withheld"], "generation": gen}
    proof = view.snapshot == "complete" and not view.records_lost
    return grants, proof


def at_least(grant: Optional[dict], tier: str) -> bool:
    return grant is not None and RANK[grant["scope"]] >= RANK[tier]
