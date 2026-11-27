"""Bounded, read-only DNS-SD locator browse (§13); never an authority or liveness source.

The resolver boundary returns (records, TTL). Empty answers use the resolver's negative
TTL (SOA minimum when available). No discovered address is opened or joined here.
find() is the browse filtered by predicates on the TXT keys the browse cross-checks.
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
MAX_WHERE = 8
AUTHORITY = "local unsigned spike manifest; DNS is locator only"
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
# Stream-name characters (ids.STREAM_NAME_RE) plus the two wildcards; 64 bytes, as a stream name.
_GLOB = re.compile(r"[a-z0-9.*?-]{1,64}")
_SID = re.compile(r"[0-9a-f]{16}")


@dataclass(frozen=True)
class Answer:
    records: tuple
    ttl: int


def _key_hint(grant) -> str:
    """The §13.2 `k` value for a grant's public key."""
    return "ed25519:" + base64.b64encode(grant.public_key).decode()


def _glob(pattern: str, name: str) -> bool:
    """`*` any run, `?` one character, anything else itself. Never backtracks: a regex would, and
    a 30-star glob that cannot match would then run for hours, before any DNS timeout applies."""
    p = n = 0
    star, resume = -1, 0
    while n < len(name):
        if p < len(pattern) and pattern[p] == "*":
            star, resume = p, n
            p += 1
        elif p < len(pattern) and pattern[p] in ("?", name[n]):
            p += 1
            n += 1
        elif star >= 0:
            # Let the last star take one more character, and retry what follows it.
            resume += 1
            p, n = star + 1, resume
        else:
            return False
    return pattern[p:].strip("*") == ""


@dataclass(frozen=True)
class Where:
    """One `KEY=PATTERN` predicate on a §13.2 TXT key the browse checks against the manifest.

    `streams` takes a glob (`*` any run, `?` one character) over the grant's public stream names;
    `sid` and `k` take one exact value. Both parts are US-ASCII. The key is case-insensitive
    (RFC 6763 §6.4); values are exact, except that a key id is hex. Other §13.2 keys are not
    cross-checked, so they cannot be searched: matching them would let an unverified TXT decide a
    hit. Every Where is checked when it is made, by `parse` or directly.
    """
    key: str
    pattern: str

    def __post_init__(self):
        key, pattern = self.key, self.pattern
        if not (isinstance(key, str) and isinstance(pattern, str) and key.isascii() and pattern.isascii()):
            raise ValueError(f"a predicate is US-ASCII KEY=PATTERN, not {key!r}={pattern!r}")
        key = key.lower()
        if key == "streams":
            if not _GLOB.fullmatch(pattern):
                raise ValueError(f"streams={pattern!r}: a glob of up to 64 stream-name characters, * and ?")
        elif key == "sid":
            pattern = pattern.lower()
            if not _SID.fullmatch(pattern):
                raise ValueError(f"sid={pattern!r}: a key id is 16 hex characters")
        elif key == "k":
            raw = b""
            if pattern.startswith("ed25519:"):
                try:
                    raw = base64.b64decode(pattern[8:], validate=True)
                except ValueError:
                    pass
            # Canonical only: the comparison is of strings, so another spelling of the key never matches.
            if len(raw) != 32 or base64.b64encode(raw).decode() != pattern[8:]:
                raise ValueError(f"k={pattern!r}: ed25519:<canonical base64 of a 32-byte public key>")
        else:
            raise ValueError(f"cannot search on {key!r}: the keys are streams, sid and k")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "pattern", pattern)

    @classmethod
    def parse(cls, text) -> "Where":
        if not isinstance(text, str) or "=" not in text:
            raise ValueError(f"a predicate is KEY=PATTERN, not {text!r}")
        return cls(*text.split("=", 1))

    def values(self, grant) -> list:
        """The grant's values that satisfy this predicate, in manifest order; empty if none."""
        if self.key == "streams":
            return [name for name in grant.public_streams if _glob(self.pattern, name)]
        value = grant.key_id.hex() if self.key == "sid" else _key_hint(grant)
        return [value] if value == self.pattern else []


def parse_where(predicates) -> tuple:
    """1 to MAX_WHERE predicates, as KEY=PATTERN strings or Where; ValueError before any query."""
    if isinstance(predicates, str):
        raise ValueError("predicates are a list of KEY=PATTERN strings, not one string")
    predicates = list(predicates)
    if not 1 <= len(predicates) <= MAX_WHERE:
        raise ValueError(f"between 1 and {MAX_WHERE} predicates, not {len(predicates)}")
    return tuple(p if isinstance(p, Where) else Where.parse(p) for p in predicates)


def find(domain: str, predicates, *, manifest, query, clock=time.monotonic) -> dict:
    """Browse `domain` and keep the stations whose manifest grant satisfies every predicate (AND).

    The only I/O is `query(name, kind) -> Answer`, the resolver boundary, so a caller (a tool, a
    test) supplies its own. Read-only, bounded, and never an authority or liveness answer: a hit
    is a place to listen, as the local manifest grants it.
    """
    return Browser(_Query(query), manifest, domain, clock).find(predicates)


class _Query:
    def __init__(self, query):
        self.resolve = query


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

    def _candidates(self):
        """The PTR answer, and each in-zone instance's one unrevoked grant with a public catalog."""
        service = "_canticle._udp." + self.domain
        ptr = self._query(service, "PTR")
        candidates = []
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
            candidates.append((instance, grant))
        return ptr, candidates

    def browse(self):
        ptr, candidates = self._candidates()
        rows = [self._row(instance, grant, ptr) for instance, grant in candidates]
        return {"domain": self.domain, "stations": rows, "truncated": len(ptr.records) > MAX_INSTANCES,
                "authority": AUTHORITY}

    def find(self, predicates):
        """The browse rows whose grant satisfies every predicate, each with what it matched on.

        Predicates are evaluated on the manifest grant only, before SRV or TXT is asked for, so DNS
        never makes a station match. A matching station whose TXT is malformed is refused, not a hit.
        """
        where = parse_where(predicates)
        ptr, candidates = self._candidates()
        hits, refused = [], []
        for instance, grant in candidates:
            matched = []
            for w in where:
                values = w.values(grant)
                if not values:
                    break
                matched.append({"key": w.key, "pattern": w.pattern, "values": values[:MAX_PUBLIC_STREAMS],
                                "values_truncated": len(values) > MAX_PUBLIC_STREAMS})
            else:
                row = self._row(instance, grant, ptr)
                if "txt-invalid" in row["mismatches"]:
                    refused.append({"station": row["station"], "key_id": row["key_id"], "reason": "txt-invalid"})
                else:
                    hits.append({**row, "matched_on": matched})
        return {"domain": self.domain, "where": [{"key": w.key, "pattern": w.pattern} for w in where],
                "stations": hits, "refused": refused, "truncated": len(ptr.records) > MAX_INSTANCES,
                "authority": AUTHORITY}

    def _row(self, instance, grant, ptr):
        srv = self._query(instance, "SRV")
        txt = self._query(instance, "TXT")
        hints = {}
        # A repeated key has no usable value, even if it appears again later.
        duplicate_keys = set()
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
                    k = k.lower()  # DNS-SD TXT keys are case-insensitive.
                    if k in hints or k in duplicate_keys:
                        hints.pop(k, None)
                        duplicate_keys.add(k)
                        txt_invalid = True
                    else:
                        hints[k] = v
        mismatches = []
        if txt_invalid:
            mismatches.append("txt-invalid")
        if "sid" in hints and hints["sid"].lower() != grant.key_id.hex():
            mismatches.append("sid")
        if "k" in hints and hints["k"] != _key_hint(grant):
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
        return {"station": grant.name, "key_id": grant.key_id.hex(),
                "public_streams": list(grant.public_streams[:MAX_PUBLIC_STREAMS]),
                "public_streams_truncated": len(grant.public_streams) > MAX_PUBLIC_STREAMS,
                "locators": endpoints,
                "mismatches": sorted(set(mismatches)),
                "ttl": min(ptr.ttl, srv.ttl, txt.ttl)}
