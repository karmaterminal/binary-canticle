"""The finding body of the fleet probe profile (RFC-0001 §6.7, amendment FP-1, #112).

A probe or a watcher sings a finding as an ``advisory`` item with content type 11, keyed by incident: the
item's ``state_key`` is the body's ``incident``. The body is a CBOR map with small integer keys; ``FIELDS``
names them for the JSON projection (§9.10).

- ``check`` validates a finding given by name (what ``canticle sing --finding`` and the control socket take).
- ``encode`` returns its deterministic CBOR. It signs nothing; the station does that.
- ``decode`` and ``from_item`` are the strict readers a receiver uses. Anything they refuse is not a finding:
  a receiver shows it as an opaque body, never with a status or severity (unknown schema fails quiet, §6.2).
- ``attribute`` says how a receiver may attribute a finding. The signer is always the speaker; ``subject`` and
  ``voice`` are what the signer says, never trust inputs (I-11).

Stream names, incident keys, the receipt and the lifecycle are in ``rfc/0001-notes/probe-profile.md``.
"""

from __future__ import annotations

import base64
import binascii
import unicodedata
from typing import Optional

from . import cbor
from .ids import CTYPES

MEDIA_TYPE = "application/vnd.canticle.finding+cbor"
CTYPE = CTYPES[MEDIA_TYPE]
CLASS = "advisory"
FIELDS = {1: "incident", 2: "subject", 3: "voice", 4: "status", 5: "severity", 6: "summary", 7: "not_proved"}
KEYS = {name: key for key, name in FIELDS.items()}
VOICES = ("self", "observer")
STATUSES = ("open", "resolved", "ended")
SEVERITIES = ("extreme", "severe", "moderate", "minor", "unknown")   # the words of CAP's severity, lowercased
WORDS = {"voice": VOICES, "status": STATUSES, "severity": SEVERITIES}
TEXT = {"incident": 32, "subject": 64, "summary": 280, "not_proved": 160}   # most UTF-8 bytes each
REQUIRED = ("incident", "subject", "voice", "status", "summary", "not_proved")


class FindingError(ValueError):
    """Not a finding this profile can write or read. On the read path ``reason`` is fixed text: it never quotes
    what a station sent."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def one_line(text: str) -> bool:
    """No control character (Unicode Cc, which includes NEL) and no line or paragraph separator."""
    return not any(unicodedata.category(c) == "Cc" or c in "  " for c in text)


def _valid(f: dict) -> dict:
    for name in REQUIRED:
        if name not in f:
            raise FindingError(f"{name} is required")
    for name, most in TEXT.items():
        v = f[name]
        if not isinstance(v, str) or not 1 <= len(v.encode("utf-8")) <= most:
            raise FindingError(f"{name} is text of 1-{most} bytes")
        if not one_line(v):
            raise FindingError(f"{name} is one line, with no control characters")
    for name, words in WORDS.items():
        if name in f and f[name] not in words:
            raise FindingError(f"{name} is one of {', '.join(words)}")
    if f["status"] == "open" and "severity" not in f:
        raise FindingError("severity is required when status is open")
    if f["status"] != "open" and "severity" in f:
        raise FindingError("severity is given only when status is open")
    return f


def check(finding) -> dict:
    """A finding given by its JSON-projection names, validated; returns a copy."""
    if not isinstance(finding, dict):
        raise FindingError("a finding is an object of named fields")
    unknown = sorted(set(finding) - set(KEYS))
    if unknown:
        raise FindingError(f"unknown field(s): {', '.join(map(str, unknown))}")
    return _valid(dict(finding))


def encode(finding) -> bytes:
    f = check(finding)
    return cbor.encode({KEYS[name]: v for name, v in f.items()})


def decode(body: bytes) -> dict:
    """The JSON projection of a finding body. Unsigned integer keys other than 1-7 are ignored; a change that
    old receivers must not misread takes a new content type (§6.7)."""
    try:
        m = cbor.decode(body)
    except cbor.CborError as e:
        raise FindingError(f"not strict CBOR ({e.reason})") from None
    if not isinstance(m, dict):
        raise FindingError("not a CBOR map")
    out = {}
    for k, v in m.items():
        if not isinstance(k, int) or k < 0:
            raise FindingError("map keys are unsigned integers")
        if k in FIELDS:
            out[FIELDS[k]] = v
    return _valid(out)


def from_item(cls: Optional[str], ctype, state_key: Optional[str], body: Optional[bytes]) -> dict:
    """The finding an item carries: class ``advisory``, content type 11, a body that decodes, and an incident equal
    to the item's ``state_key``. ``cls`` is the class name; ``ctype`` the registered id or its media type."""
    if ctype not in (CTYPE, MEDIA_TYPE):
        raise FindingError("not content type 11")
    if cls != CLASS:
        raise FindingError("a finding rides class advisory only")
    if body is None:
        raise FindingError("no body")
    f = decode(body)
    if f["incident"] != state_key:
        raise FindingError("incident is not the item's state_key")
    return f


def from_record(rec: dict) -> Optional[dict]:
    """The finding of a record v1 ``frame`` (§14.18.3): None when its body is not content type 11, FindingError when
    it is one but not a finding."""
    body = rec.get("body")
    if body is None or body.get("ctype") not in (CTYPE, MEDIA_TYPE):
        return None
    try:
        raw = base64.b64decode(body.get("base64") or "", validate=True) if "base64" in body else None
    except (binascii.Error, ValueError):
        raise FindingError("body is not base64") from None
    return from_item(rec.get("class"), CTYPE, rec.get("state_key"), raw)


def attribute(finding: dict, signer: Optional[str]) -> str:
    """How a receiver attributes a finding signed by the station named ``signer`` (its manifest name):

    - ``observer``: the signer's observation of the subject it names;
    - ``self``: the signer about itself, only when the body says ``self`` and names the signer;
    - ``self-unmatched``: the body says ``self`` but names another subject. It is the signer's observation of that
      subject, never that subject's own voice.
    """
    if finding["voice"] == "observer":
        return "observer"
    return "self" if signer is not None and finding["subject"] == signer else "self-unmatched"
