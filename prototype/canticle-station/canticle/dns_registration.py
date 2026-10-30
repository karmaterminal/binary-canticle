"""Station-owned, opt-in unicast DNS-SD lease planning (§13).

No DNS transport is implemented here. A provider receives an immutable record set and
returns an opaque ownership handle; a future authenticated SRP/UPDATE adapter must
prove that it owns the lease before changing a zone. DNS data never grants trust.
"""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\Z")


def _domain(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("DNS name must be a string")
    name = value.rstrip(".").lower()
    if (not name or len(name) > 253 or any(not _NAME.fullmatch(x) for x in name.split("."))
            or name == "local" or name.endswith(".local")):
        raise ValueError("registration requires a valid unicast DNS name, not .local")
    return name + "."


@dataclass(frozen=True)
class Record:
    owner: str
    kind: str
    ttl: int
    value: object


@dataclass(frozen=True)
class Publication:
    station: str
    zone: str
    records: tuple[Record, ...]


class Registration:
    """One station's DNS lease. Methods are explicit; no background or session refresh.

    Provider contract: publish(publication, lease_seconds) -> opaque handle;
    renew(handle, publication, lease_seconds); withdraw(handle). A failed call must
    raise, leaving the prior lease unchanged. Providers must enforce handle ownership.
    """

    def __init__(self, station, manifest, provider, *, enabled: bool = False,
                 zone: str, target: str, port: int, lease_seconds: int = 3600,
                 clock=time.monotonic):
        if not enabled:
            raise ValueError("DNS registration requires explicit opt-in")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 3600 <= lease_seconds <= 7200:
            raise ValueError("DNS lease must be 3600–7200 seconds (§13.4)")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("SRV port must be 1–65535")
        zone, target = _domain(zone), _domain(target)
        if not target.endswith("." + zone):
            raise ValueError("SRV target must be inside the explicit zone")
        grant = station.grant
        if grant is None or grant.revoked or grant.key_id != station.key_id:
            raise ValueError("station needs its own active manifest grant")
        if manifest.entry(station.key_id) != grant:
            raise ValueError("station grant must match the supplied local manifest")
        if len([e for e in manifest if e.name == grant.name and not e.revoked]) != 1:
            raise ValueError("station name must have one active manifest key")
        if not grant.public_streams:
            raise ValueError("station has no explicitly public streams")
        if len(grant.public_streams) > 32:
            raise ValueError("public stream list exceeds DNS publication bound")
        if not set(grant.public_streams).issubset(station.streams):
            raise ValueError("public streams must be configured on this station")
        instance = f"{grant.name}._canticle._udp.{zone}"
        service = f"_canticle._udp.{zone}"
        txt = ("txtvers=1", f"sid={grant.key_id.hex()}",
               "k=ed25519:" + base64.b64encode(grant.public_key).decode("ascii"),
               "mode=lease", "streams=" + ",".join(grant.public_streams))
        if any(len(item.encode("utf-8")) > 255 for item in txt) or sum(len(x.encode("utf-8")) + 1 for x in txt) > 200:
            raise ValueError("DNS TXT record exceeds publication bound")
        self.publication = Publication(grant.name, zone, (
            Record(service, "PTR", 300, instance),
            Record(instance, "SRV", 120, (0, 0, port, target)),
            Record(instance, "TXT", 120, txt),
        ))
        self.provider, self.clock, self.lease_seconds = provider, clock, lease_seconds
        self.station, self.manifest, self.grant = station, manifest, grant
        self._handle = None
        self._expires_at = None

    def _check_grant(self):
        current = self.manifest.entry(self.station.key_id)
        if current != self.grant or current.revoked or self.station.grant != current:
            raise RuntimeError("station manifest grant changed; refuse DNS publication")

    @property
    def expires_at(self):
        return self._expires_at

    def publish(self):
        self._check_grant()
        if self._handle is not None and self.clock() < self._expires_at:
            raise RuntimeError("lease already active; renew it")
        # Expired handles are never reused or withdrawn: a new owner may now hold the name.
        now = self.clock()
        handle = self.provider.publish(self.publication, self.lease_seconds)
        if handle is None:
            raise RuntimeError("provider did not return a lease handle")
        self._handle = handle
        self._expires_at = now + self.lease_seconds

    def renew(self):
        self._check_grant()
        if self._handle is None or self.clock() >= self._expires_at:
            raise RuntimeError("no live lease to renew")
        now = self.clock()
        self.provider.renew(self._handle, self.publication, self.lease_seconds)
        self._expires_at = now + self.lease_seconds

    def withdraw(self):
        if self._handle is None:
            return
        if self.clock() < self._expires_at:
            self.provider.withdraw(self._handle)
        self._handle = None
        self._expires_at = None
