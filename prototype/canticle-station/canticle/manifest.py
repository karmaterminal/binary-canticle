"""Fleet manifest: the only place a key-id resolves to a public key (RFC-0001 §5.1, §10.3).

Spike limitation: the manifest is an unsigned JSON file. RFC-0001 requires a
manifest signed by an offline 2-of-n root with capability classes, audiences
and a revocation list; this file carries the same fields without the
signature.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ids import CLASS_BY_NAME, SCOPES, check_stream_name, key_id, stream_ids
from .wire import Reject


DEFAULT_SCOPES = frozenset({SCOPES["host"], SCOPES["lan"]})


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
        out = {"name": self.name, "public_key": self.public_key.hex(),
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
            entries.append(StationEntry(
                name=s["name"], public_key=bytes.fromhex(s["public_key"]),
                classes=frozenset(CLASS_BY_NAME[c].code for c in s.get("classes", [])),
                streams=tuple(s.get("streams", [])), revoked=bool(s.get("revoked", False)),
                scopes=frozenset(SCOPES[x] for x in s["scopes"]) if "scopes" in s else DEFAULT_SCOPES))
        return cls(entries)

    def to_json(self) -> dict:
        return {"manifest": "canticle-fleet/spike-0", "signed": False,
                "stations": [e.to_json() for e in self]}

    @classmethod
    def load(cls, path) -> "Manifest":
        return cls.from_json(json.loads(Path(path).read_text()))

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2) + "\n")
