"""Fleet manifest: the only place a key-id resolves to a public key (RFC-0001 §5.1, §10.3).

Spike limitation: the manifest is an unsigned JSON file. RFC-0001 requires a
manifest signed by an offline 2-of-n root with capability classes, audiences
and a revocation list; this file carries the same fields without the
signature, so nothing authenticates it.

``verify_json`` checks a manifest's structure and keys and reports every
problem it finds (``canticle manifest verify``, ``canticle doctor``). It never
checks a signature: spike-0 has none.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ids import (CLASS_BY_NAME, SCOPES, STATION_NAME_RE, check_public_key, check_stream_name, key_id,
                  stream_ids)
from .wire import Reject


FORMAT = "canticle-fleet/spike-0"
DEFAULT_SCOPES = frozenset({SCOPES["host"], SCOPES["lan"]})
FIELDS = ("manifest", "signed", "stations")
ENTRY_FIELDS = ("name", "public_key", "key_id", "classes", "streams", "scopes", "revoked")
_HEX = {64: re.compile(r"[0-9a-f]{64}"), 16: re.compile(r"[0-9a-f]{16}")}


@dataclass(frozen=True)
class StationEntry:
    name: str
    public_key: bytes
    classes: frozenset          # class codes this key may sign (§10.4)
    streams: tuple = ()         # stream names, so listeners can map ids to names (§5.4)
    revoked: bool = False
    scopes: frozenset = DEFAULT_SCOPES  # scope codes this key may sign (§4.3, §10.3 `scopes`)
    key_id: bytes = field(init=False)
    stream_names: dict = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "key_id", key_id(self.public_key))
        object.__setattr__(self, "stream_names", stream_ids(self.streams))

    def to_json(self) -> dict:
        names = {c.code: c.name for c in CLASS_BY_NAME.values()}
        out = {"name": self.name, "public_key": self.public_key.hex(), "key_id": self.key_id.hex(),
               "classes": sorted(names[c] for c in self.classes), "streams": list(self.streams),
               "scopes": [s for s, c in sorted(SCOPES.items(), key=lambda kv: kv[1]) if c in self.scopes]}
        if self.revoked:
            out["revoked"] = True
        return out


class Manifest:
    def __init__(self, entries=()):
        self._by_kid: dict[bytes, StationEntry] = {}
        self._keys: dict[bytes, Ed25519PublicKey] = {}
        for e in entries:
            self.add(e)

    def add(self, e: StationEntry) -> None:
        try:
            check_public_key(e.public_key)
        except ValueError as err:
            raise ValueError(f"station {e.name!r}: public key {e.public_key.hex()} is {err}; "
                             "the manifest is invalid") from None
        if e.key_id in self._by_kid:
            raise ValueError(f"two keys share key-id {e.key_id.hex()}; the manifest is invalid (§5.1)")
        for s in e.streams:
            check_stream_name(s)
        self._by_kid[e.key_id] = e
        self._keys[e.key_id] = Ed25519PublicKey.from_public_bytes(e.public_key)

    def entry(self, kid: bytes) -> Optional[StationEntry]:
        return self._by_kid.get(kid)

    def resolve(self, kid: bytes) -> Optional[Ed25519PublicKey]:
        e = self._by_kid.get(kid)
        if e is None:
            return None
        if e.revoked:
            raise Reject("revoked-key", kid.hex())
        return self._keys[kid]

    def __iter__(self):
        return iter(self._by_kid.values())

    @classmethod
    def from_json(cls, data: dict) -> "Manifest":
        entries = []
        for s in data.get("stations", []):
            e = StationEntry(
                name=s["name"], public_key=bytes.fromhex(s["public_key"]),
                classes=frozenset(CLASS_BY_NAME[c].code for c in s.get("classes", [])),
                streams=tuple(s.get("streams", [])), revoked=bool(s.get("revoked", False)),
                scopes=frozenset(SCOPES[x] for x in s["scopes"]) if "scopes" in s else DEFAULT_SCOPES)
            # key_id is optional (manifests written before it was added carry none), but one that is
            # present must be SHA-256(public_key)[0:8] (§10.3).
            if "key_id" in s and s["key_id"] != e.key_id.hex():
                raise ValueError(f"station {e.name!r}: key_id {s['key_id']!r} is not SHA-256(public_key)[0:8] = "
                                 f"{e.key_id.hex()}; the manifest is invalid (§10.3)")
            entries.append(e)
        return cls(entries)

    def to_json(self) -> dict:
        return {"manifest": FORMAT, "signed": False,
                "stations": [e.to_json() for e in self]}

    @classmethod
    def load(cls, path) -> "Manifest":
        return cls.from_json(json.loads(Path(path).read_text()))

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2) + "\n")


def verify_json(data) -> list[str]:
    """Every problem with a spike-0 manifest's structure and keys; an empty list when it is sound.

    Stricter than ``Manifest.from_json``, which skips unknown fields: here an unknown field (a misspelt
    ``revoked``, say), non-canonical hex or a station name outside §5.3's grammar is a problem too.
    A manifest with no problems always loads. Signatures are not checked: spike-0 has none.
    """
    if not isinstance(data, dict):
        return ["the manifest is not a JSON object"]
    problems = [f"unknown field {k!r} (spike-0 has {', '.join(FIELDS)})" for k in data if k not in FIELDS]
    if data.get("manifest") != FORMAT:
        problems.append(f"manifest is {data.get('manifest')!r}, not {FORMAT!r}")
    if data.get("signed", False) is not False:
        problems.append("signed must be false: spike-0 manifests carry no signature, and this spike checks none")
    stations = data.get("stations")
    if not isinstance(stations, list):
        return problems + ["stations must be a list"]
    seen: dict[bytes, str] = {}
    for i, s in enumerate(stations):
        at = f"stations[{i}]"
        if not isinstance(s, dict):
            problems.append(f"{at}: not an object")
            continue
        if isinstance(s.get("name"), str):
            at = f"{at} ({s['name']})"
        problems += _entry_problems(s, at, seen)
    if not problems:
        try:
            Manifest.from_json(data)
        except Exception as e:  # a check above is missing; never report a manifest that won't load as sound
            problems.append(f"does not load: {e}")
    return problems


def _entry_problems(s: dict, at: str, seen: dict) -> list[str]:
    out = [f"{at}: unknown field {k!r} (an entry has {', '.join(ENTRY_FIELDS)})" for k in s if k not in ENTRY_FIELDS]
    name = s.get("name")
    if not isinstance(name, str) or not STATION_NAME_RE.match(name):
        out.append(f"{at}: name {name!r} does not match [a-z][a-z0-9-]{{0,30}} (§5.3)")
    pk = s.get("public_key")
    if not isinstance(pk, str) or not _HEX[64].fullmatch(pk):
        out.append(f"{at}: public_key must be 64 lowercase hex characters (32 bytes)")
    else:
        pub = bytes.fromhex(pk)
        try:
            check_public_key(pub)
        except ValueError as e:
            out.append(f"{at}: public_key is {e}")
        kid = key_id(pub)
        if kid in seen:
            out.append(f"{at}: same key as {seen[kid]} (key-id {kid.hex()}); one key is one station (§5.1)")
        seen.setdefault(kid, at)
        if "key_id" in s:
            given = s["key_id"]
            if not isinstance(given, str) or not _HEX[16].fullmatch(given):
                out.append(f"{at}: key_id must be 16 lowercase hex characters")
            elif given != kid.hex():
                out.append(f"{at}: key_id {given} is not SHA-256(public_key)[0:8] = {kid.hex()} (§10.3)")
    out += _names(s, at, "classes", "class", CLASS_BY_NAME)
    out += _names(s, at, "scopes", "scope", SCOPES)
    streams = s.get("streams", [])
    if not isinstance(streams, list) or not all(isinstance(x, str) for x in streams):
        out.append(f"{at}: streams must be a list of stream names")
    else:
        try:
            for x in streams:
                check_stream_name(x)
            stream_ids(streams)
        except ValueError as e:
            out.append(f"{at}: {e}")
    if "revoked" in s and not isinstance(s["revoked"], bool):
        out.append(f"{at}: revoked must be true or false")
    return out


def _names(s: dict, at: str, key: str, noun: str, known: dict) -> list[str]:
    values = s.get(key, [])
    if not isinstance(values, list):
        return [f"{at}: {key} must be a list"]
    return [f"{at}: unknown {noun} {v!r} (known: {', '.join(known)})"
            for v in values if not isinstance(v, str) or v not in known]
