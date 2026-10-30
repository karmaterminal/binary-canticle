"""Bounded, read-only DNS-SD locator browse (§13); never an authority or liveness source.

The resolver boundary returns (records, TTL). Empty answers use the resolver's negative
TTL (SOA minimum when available). No discovered address is opened or joined here.
"""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass

MAX_INSTANCES = 32
MAX_PUBLIC_STREAMS = 32
MAX_RECORDS = 8
MAX_TXT_STRINGS = 32
MAX_TXT_BYTES = 4096
MAX_CACHE = 128
MAX_TTL = 300
NEGATIVE_TTL = 60
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")


@dataclass(frozen=True)
class Answer:
    records: tuple
    ttl: int


class DnsPythonResolver:
    """Optional dnspython backend; no new station runtime dependency."""

    def __init__(self):
        try:
            import dns.resolver
        except ImportError as exc:
            raise RuntimeError("DNS browse needs dnspython installed separately") from exc
        self.resolver = dns.resolver.Resolver()

    def resolve(self, name: str, kind: str) -> Answer:
        import dns.exception
        import dns.resolver
        import dns.rdatatype
        try:
            reply = self.resolver.resolve(name, kind, lifetime=2.0)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer) as exc:
            responses = exc.responses().values() if isinstance(exc, dns.resolver.NXDOMAIN) else [exc.response()]
            ttls = [min(int(rrset.ttl), int(soa.minimum)) for response in responses if response
                    for rrset in response.authority if rrset.rdtype == dns.rdatatype.SOA for soa in rrset]
            return Answer((), min(ttls, default=NEGATIVE_TTL))
        except dns.exception.DNSException as exc:
            raise RuntimeError(f"DNS {kind} {name}: {exc}") from exc
        if kind == "PTR":
            rows = tuple(str(r.target) for r in reply)
        elif kind == "SRV":
            rows = tuple((int(r.priority), int(r.weight), int(r.port), str(r.target)) for r in reply)
        else:
            rows = tuple(tuple(bytes(s).decode("utf-8", "replace") for s in r.strings)
                         for r in reply[:MAX_RECORDS])
        return Answer(rows, int(reply.rrset.ttl))


class Browser:
    def __init__(self, resolver, manifest, domain: str, clock=time.monotonic):
        domain = domain.rstrip(".").lower()
        if (not domain or len(domain) > 253 or any(not _NAME.fullmatch(x) for x in domain.split("."))):
            raise ValueError("one explicit DNS domain is required")
        if domain == "local" or domain.endswith(".local"):
            raise ValueError(".local requires mDNS; this slice browses unicast DNS only")
        self.domain, self.resolver, self.manifest, self.clock = domain + ".", resolver, manifest, clock
        self.cache = {}

    def _query(self, name, kind):
        key = (name.lower(), kind)
        now = self.clock()
        cached = self.cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        answer = self.resolver.resolve(name, kind)
        if not isinstance(answer, Answer):
            raise ValueError("resolver must return Answer")
        records = answer.records[:MAX_RECORDS] if kind != "PTR" else answer.records[:MAX_INSTANCES + 1]
        ttl = max(1, min(MAX_TTL, int(answer.ttl if records else min(answer.ttl, NEGATIVE_TTL))))
        result = Answer(tuple(records), ttl)
        if len(self.cache) >= MAX_CACHE:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = (now + ttl, result)
        return result

    def browse(self):
        service = "_canticle._udp." + self.domain
        ptr = self._query(service, "PTR")
        rows = []
        seen = set()
        for raw in ptr.records[:MAX_INSTANCES]:
            instance = str(raw).lower().rstrip(".") + "."
            if instance in seen or not instance.endswith("." + service):
                continue
            seen.add(instance)
            label = instance[:-(len(service) + 1)]
            # Manifest name is authoritative; instance is only a candidate locator.
            grants = [e for e in self.manifest if e.name == label and not e.revoked]
            if len(grants) != 1:
                continue
            grant = grants[0]
            if not grant.public_streams:
                continue
            srv = self._query(instance, "SRV")
            txt = self._query(instance, "TXT")
            hints = {}
            txt_invalid = False
            for strings in txt.records:
                if (not isinstance(strings, tuple) or len(strings) > MAX_TXT_STRINGS
                        or sum(len(item.encode("utf-8")) for item in strings if isinstance(item, str)) > MAX_TXT_BYTES
                        or any(not isinstance(item, str) or "\ufffd" in item for item in strings)):
                    txt_invalid = True
                    continue
                for item in strings:
                    if "=" in item:
                        k, v = item.split("=", 1)
                        if k not in hints:
                            hints[k] = v
            mismatches = []
            if txt_invalid:
                mismatches.append("txt-invalid")
            if "sid" in hints and hints["sid"].lower() != grant.key_id.hex():
                mismatches.append("sid")
            if "k" in hints:
                expected = "ed25519:" + base64.b64encode(grant.public_key).decode()
                if hints["k"] != expected:
                    mismatches.append("k")
            if "streams" in hints and set(hints["streams"].split(",")) != set(grant.public_streams):
                mismatches.append("streams")
            endpoints = []
            for priority, weight, port, target in srv.records:
                target = str(target).lower().rstrip(".") + "."
                if not 1 <= port <= 65535 or not target.endswith("." + self.domain):
                    mismatches.append("srv-target")
                    continue
                endpoints.append({"target": target, "port": port, "priority": priority, "weight": weight})
            rows.append({"station": grant.name, "key_id": grant.key_id.hex(),
                         "public_streams": list(grant.public_streams[:MAX_PUBLIC_STREAMS]),
                         "public_streams_truncated": len(grant.public_streams) > MAX_PUBLIC_STREAMS,
                         "locators": endpoints,
                         "mismatches": sorted(set(mismatches)),
                         "ttl": min(ptr.ttl, srv.ttl, txt.ttl)})
        return {"domain": self.domain, "stations": rows, "truncated": len(ptr.records) > MAX_INSTANCES,
                "authority": "local unsigned spike manifest; DNS is locator only"}
