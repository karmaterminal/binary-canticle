#!/usr/bin/env python3
"""Familiar projections: a reference checker for binary-canticle#148. Proposed, not RFC-0001.

It has three parts, all run over synthetic fixtures in fixtures/:

- read_descriptor(): a strict reader for the proposed familiar-projection/1 body.
- Receiver: a reference receiver that keeps claim currency, views, presentation and coverage.
- ProducerCost: what a producer's emissions cost, read from the emissions alone.

    python projection.py                  # every fixture in fixtures/
    python projection.py fixtures/a3-*.json

Standard library only. No clock, network, model or randomness, so a fixture always gives the same
result. README.md is the design note; this file only checks it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DESCRIPTOR = "familiar-projection/1"
FIXTURE = "familiar-projection-fixture/1"

MAX_BODY = 900  # canonical bytes. A keyed item with a 48-byte state_key, ctype 3 and the refresh flag
#                 carries at most 920 inside the 1 100-byte frame (§9.11; test_projection measures it).
MAX_SOURCES = 6  # §17.3's six evidence references
MAX_CLAIMS = 6
MAX_WITHDRAWN = 6
MAX_UNREAD = 6
MAX_TOPICS = 4
MAX_TEXT = 200  # UTF-8 bytes per claim
MAX_LEASE_MS = 900_000  # valid_until - generated_at: §17.4's 900 s aspect horizon

SCOPES = {"host": 0, "lan": 1, "fleet": 2, "public": 3}  # frame key 13 (§9.4)
STANDINGS = ("current", "history")
ORIGINS = ("self", "observed")
AUTHORITIES = ("notice", "record")
BASES = ("report", "state", "interpretation")
WITHDRAW_REASONS = ("withdrawn", "superseded", "revoked")
RETRACT_REASONS = ("plucked", "superseded", "expired", "revoked", "quarantined")  # record v1 (§14.18.3)
LIVE = ("current", "carried")
# §6.3 rule 5: no missing, expired, filtered, plucked or unsupported frame may become one of these.
SILENCE_WORDS = ("quiet", "negative", "absent", "unwell", "offline", "calm", "level 0", "all clear")

KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,47}")
ID_RE = re.compile(r"[a-z0-9]{1,8}")
ACTOR_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}")
TOPIC_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")
REF_RE = re.compile(r"[\x21-\x7e]{1,48}")
KEY_ID_RE = re.compile(r"[0-9a-f]{16}")

TOP = {"v", "key", "standing", "window", "generated_at", "valid_until", "sources", "claims", "withdrawn", "unread"}
TOP_REQUIRED = TOP - {"withdrawn", "unread"}
SOURCE = {"id", "actor", "ref", "rev", "origin", "authority", "audience", "valid_until"}
CLAIM = {"id", "basis", "about", "topics", "src", "text"}
WITHDRAWN = {"actor", "ref", "rev", "reason"}


class Refused(Exception):
    """An unreadable descriptor. A receiver drops it and counts it (fail closed, like typed beacons)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (f": {detail}" if detail else ""))
        self.code = code


class FixtureError(Exception):
    """The fixture itself is malformed. Never a property of the design."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def fmt(ms: int) -> str:
    return f"{ms // 1000}s" if ms % 1000 == 0 else f"{ms // 1000}.{ms % 1000:03d}s"


def stream_id(name: str) -> int:
    """§5.4, as canticle.ids.stream_id: SHA-256("canticle-stream/v2" || 0x00 || name)[0:4]."""
    return int.from_bytes(hashlib.sha256(b"canticle-stream/v2\x00" + name.encode()).digest()[:4], "big")


def idem(key_id: str, epoch: int, stream: str, seq: int) -> str:
    """Receptor record v1's idem (§14.18.3), as canticle.records.idem prints it."""
    return f"canticle:{key_id}:{epoch}:{stream_id(stream):08x}:{seq}"


# ---------------------------------------------------------------------------------------------------
# The descriptor


@dataclass(frozen=True)
class Source:
    id: str
    actor: str
    ref: str
    rev: int
    origin: str
    authority: str
    audience: str
    valid_until: int

    @property
    def triple(self) -> tuple:
        return (self.actor, self.ref, self.rev)


@dataclass(frozen=True)
class Claim:
    id: str
    basis: str
    about: str
    topics: tuple
    src: tuple
    text: str


@dataclass(frozen=True)
class Projection:
    key: str
    standing: str
    window: tuple
    generated_at: int
    valid_until: int
    sources: dict
    claims: tuple
    withdrawn: tuple
    unread: tuple
    digest: str
    size: int

    def cited(self, claim: Claim) -> list:
        return [self.sources[i] for i in claim.src]

    @property
    def basis(self) -> frozenset:
        return frozenset(s.triple for s in self.sources.values())


def _fields(obj, allowed: set, required: set, what: str) -> None:
    if not isinstance(obj, dict):
        raise Refused("shape", f"{what} is not an object")
    if unknown := sorted(set(obj) - allowed):
        raise Refused("unknown-field", f"{what}: {', '.join(unknown)}")
    if missing := sorted(required - set(obj)):
        raise Refused("missing-field", f"{what}: {', '.join(missing)}")


def _int(v, what: str, lo: int = 0) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise Refused("not-integer", what)
    if v < lo:
        raise Refused("range", f"{what} < {lo}")
    return v


def _tok(v, rx: re.Pattern, what: str) -> str:
    if not isinstance(v, str) or not rx.fullmatch(v):
        raise Refused("bad-token", what)
    return v


def _one_of(v, allowed: tuple, what: str) -> str:
    if not isinstance(v, str) or v not in allowed:
        raise Refused("bad-enum", f"{what} {v!r}")
    return v


def _list(v, what: str, hi: int, lo: int = 0) -> list:
    if not isinstance(v, list):
        raise Refused("shape", f"{what} is not a list")
    if not lo <= len(v) <= hi:
        raise Refused("count", f"{what} has {len(v)}, allowed {lo}..{hi}")
    return v


def _text(v) -> str:
    if not isinstance(v, str):
        raise Refused("bad-text", "not a string")
    n = len(v.encode())
    if not 1 <= n <= MAX_TEXT:
        raise Refused("bad-text", f"{n} bytes, allowed 1..{MAX_TEXT}")
    if v != v.strip() or any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in v):
        raise Refused("bad-text", "edge whitespace, or a control, format or line-break character")
    return v


def read_descriptor_bytes(raw: bytes, scope: str) -> Projection:
    """Read a body as it arrives in record v1 (`body.base64`, ctype 3). Only canonical bytes are accepted,
    so record v1's `body.sha256` is the projection's digest and one projection has one lineage root."""
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, FixtureError) as e:
        raise Refused("not-json", str(e)) from None
    proj = read_descriptor(body, scope)
    if canonical(body) != raw:
        raise Refused("not-canonical", "sorted keys, no whitespace, UTF-8, integers only")
    return proj


def _no_constant(name: str):
    raise ValueError(f"{name} is not JSON")


def read_descriptor(body, scope: str) -> Projection:
    """Read one familiar-projection/1 body carried on an item of `scope`. Raises Refused."""
    if not isinstance(body, dict):
        raise Refused("shape", "body is not an object")
    try:
        raw = canonical(body)
    except (TypeError, ValueError) as e:
        raise Refused("not-json", str(e)) from None
    if len(raw) > MAX_BODY:
        raise Refused("too-large", f"{len(raw)} > {MAX_BODY} bytes")
    _fields(body, TOP, TOP_REQUIRED, "projection")
    if body["v"] != DESCRIPTOR:
        raise Refused("version", repr(body["v"]))
    if scope not in SCOPES:
        raise Refused("scope", repr(scope))
    key = _tok(body["key"], KEY_RE, "key")
    standing = _one_of(body["standing"], STANDINGS, "standing")
    w0, w1 = (_int(x, "window") for x in _list(body["window"], "window", 2, 2))
    if w0 > w1:
        raise Refused("window", "from > to")
    gen = _int(body["generated_at"], "generated_at")
    if gen < w1:
        raise Refused("before-window", "generated_at precedes the window's end")
    until = _int(body["valid_until"], "valid_until")
    if until <= gen:
        raise Refused("validity", "valid_until <= generated_at")
    if until - gen > MAX_LEASE_MS:
        raise Refused("lease-too-long", f"{until - gen} ms > {MAX_LEASE_MS} ms")

    sources: dict = {}
    for s in _list(body["sources"], "sources", MAX_SOURCES):
        _fields(s, SOURCE, SOURCE, "source")
        src = Source(
            id=_tok(s["id"], ID_RE, "source id"),
            actor=_tok(s["actor"], ACTOR_RE, "actor"),
            ref=_tok(s["ref"], REF_RE, "ref"),
            rev=_int(s["rev"], "rev", 1),
            origin=_one_of(s["origin"], ORIGINS, "origin"),
            authority=_one_of(s["authority"], AUTHORITIES, "authority"),
            audience=_one_of(s["audience"], tuple(SCOPES), "audience"),
            valid_until=_int(s["valid_until"], "source valid_until"),
        )
        if src.id in sources:
            raise Refused("duplicate-id", f"source {src.id}")
        if any(o.triple == src.triple for o in sources.values()):
            raise Refused("duplicate-source", f"source {src.id}")
        if src.ref.startswith("canticle:"):
            raise Refused("echo-source", f"source {src.id}: a heard canticle item is never a source (#119)")
        if SCOPES[scope] > SCOPES[src.audience]:
            raise Refused("audience", f"source {src.id} is elected for {src.audience}; the item is {scope}")
        if standing == "current" and src.valid_until <= gen:
            raise Refused("lapsed-source", f"source {src.id} lapsed before generated_at")
        sources[src.id] = src

    claims: list = []
    cited: set = set()
    for c in _list(body["claims"], "claims", MAX_CLAIMS):
        _fields(c, CLAIM, CLAIM, "claim")
        cid = _tok(c["id"], ID_RE, "claim id")
        if any(o.id == cid for o in claims):
            raise Refused("duplicate-id", f"claim {cid}")
        topics = [_tok(x, TOPIC_RE, "topic") for x in _list(c["topics"], "topics", MAX_TOPICS, 1)]
        src_ids = [_tok(x, ID_RE, "src") for x in _list(c["src"], "src", MAX_SOURCES, 1)]
        if len(set(topics)) != len(topics) or len(set(src_ids)) != len(src_ids):
            raise Refused("duplicate-id", f"claim {cid} repeats a topic or a source")
        if unknown := [x for x in src_ids if x not in sources]:
            raise Refused("unknown-source", f"claim {cid} cites {', '.join(unknown)}")
        basis = _one_of(c["basis"], BASES, "basis")
        if basis == "state" and any(sources[x].authority != "record" for x in src_ids):
            raise Refused("state-needs-record", f"claim {cid}: a notice cannot carry world state")
        about = _tok(c["about"], ACTOR_RE, "about")
        claims.append(Claim(cid, basis, about, tuple(topics), tuple(src_ids), _text(c["text"])))
        cited.update(src_ids)
    if uncited := sorted(set(sources) - cited):
        raise Refused("uncited-source", ", ".join(uncited))

    withdrawn: list = []
    for w in _list(body.get("withdrawn", []), "withdrawn", MAX_WITHDRAWN):
        _fields(w, WITHDRAWN, WITHDRAWN, "withdrawn")
        entry = (_tok(w["actor"], ACTOR_RE, "actor"), _tok(w["ref"], REF_RE, "ref"), _int(w["rev"], "rev", 1),
                 _one_of(w["reason"], WITHDRAW_REASONS, "reason"))
        if any(e[:3] == entry[:3] for e in withdrawn):
            raise Refused("duplicate-source", "withdrawn twice")
        if any(s.triple == entry[:3] for s in sources.values()):
            raise Refused("cites-withdrawn", f"{entry[0]} {entry[1]} rev {entry[2]}")
        withdrawn.append(entry)
    unread = [_tok(x, ACTOR_RE, "unread") for x in _list(body.get("unread", []), "unread", MAX_UNREAD)]
    if len(set(unread)) != len(unread):
        raise Refused("duplicate-id", "unread")
    if not claims and not withdrawn:
        raise Refused("empty", "no claims and no withdrawals")
    return Projection(key, standing, (w0, w1), gen, until, sources, tuple(claims), tuple(withdrawn),
                      tuple(unread), hashlib.sha256(raw).hexdigest(), len(raw))


def evidence_id(triples) -> str:
    """One id per evidence basis: the sorted (actor, ref, rev) triples. Wording and producer play no part."""
    return hashlib.sha256(canonical(sorted([a, r, v] for a, r, v in triples))).hexdigest()[:16]


def label_of(proj: Projection, claim: Claim) -> str:
    """The signer is always the speaker (§6.7); the label says what kind of statement it makes."""
    if claim.basis == "state":
        return "record"
    if claim.basis == "interpretation":
        return "interpretation"
    if all(s.origin == "self" and s.actor == claim.about for s in proj.cited(claim)):
        return "self-report"
    return "observation"


def support_of(proj: Projection, claim: Claim) -> int:
    """Distinct source actors a claim stands on (R-INT-4). Never producers, copies or wordings."""
    return len({s.actor for s in proj.cited(claim)})


def presentation_key(proj: Projection, claim: Claim) -> tuple:
    """What presentation dedupes on: the same kind of statement over the same evidence is shown once."""
    return (label_of(proj, claim), evidence_id(s.triple for s in proj.cited(claim)))


def resolved(proj: Projection, claim: Claim) -> tuple:
    return (claim.basis, claim.about, claim.topics, claim.text, tuple(sorted(s.triple for s in proj.cited(claim))))


# ---------------------------------------------------------------------------------------------------
# Producer cost


class ProducerCost:
    """Classifies each emission per station key and projection key, from the bodies alone.

    repeat: the same body again (a refresh re-issue or an at-least-once retry); no model call.
    mechanical: every claim already appeared, resolved, in the key's last body (a re-stamp, or claims
        dropped after a withdrawal or lapse); a deterministic re-check, no model call.
    synthesis: anything else; it needs a model call. no_new_evidence counts the syntheses whose
        sources this producer had all cited before (a rephrase of known evidence).
    """

    FIELDS = ("synthesis", "no_new_evidence", "mechanical", "repeats", "refused")

    def __init__(self) -> None:
        self.counts: dict = {}
        self._last: dict = {}
        self._seen: dict = {}
        self._idems: set = set()

    def emit(self, key_id: str, ident: str, body, scope: str) -> str:
        if ident in self._idems:
            return "duplicate"  # the carousel looping one signed frame is not an emission
        self._idems.add(ident)
        n = self.counts.setdefault(key_id, dict.fromkeys(self.FIELDS, 0))
        try:
            proj = read_descriptor(body, scope)
        except Refused:
            n["refused"] += 1
            return "refused"
        last = self._last.get((key_id, proj.key))
        if last and last[0] == proj.digest:
            n["repeats"] += 1
            return "repeat"
        claims = frozenset(resolved(proj, c) for c in proj.claims)
        seen = self._seen.setdefault(key_id, set())
        if claims <= (last[1] if last else frozenset()):
            n["mechanical"] += 1
            kind = "mechanical"
        else:
            n["synthesis"] += 1
            kind = "synthesis"
            if proj.basis <= seen:
                n["no_new_evidence"] += 1
                kind = "no-new-evidence"
        seen |= proj.basis
        self._last[(key_id, proj.key)] = (proj.digest, claims)
        return kind


# ---------------------------------------------------------------------------------------------------
# The receiver


@dataclass
class Frame:
    name: str
    body: object
    key_id: str
    station: str
    stream: str
    scope: str
    epoch: int
    seq: int
    expires_at: int  # receiver-local expiry (§14.6.3)

    @property
    def idem(self) -> str:
        return idem(self.key_id, self.epoch, self.stream, self.seq)


@dataclass
class Held:
    name: str
    frame: Frame
    proj: Projection
    idem: str
    item_until: int
    pkeys: dict
    aliases: set = field(default_factory=set)
    retracted: str | None = None
    superseded_by: str | None = None

    @property
    def key_id(self) -> str:
        return self.frame.key_id


@dataclass
class SourceMark:
    """What one producer has said about one source (per station key; never across producers)."""

    max_rev: int
    until: dict = field(default_factory=dict)  # rev -> the earliest valid_until it ever stated
    withdrawn: dict = field(default_factory=dict)  # rev -> (reason, t); sticky


@dataclass
class Pending:
    pkey: tuple
    first_ref: str
    due: int
    why: str


@dataclass
class Kept:
    """A separately elected, binding-local history entry: attributed, never current, never support."""

    ref: str
    key_id: str
    station: str
    about: str
    topics: tuple
    window: tuple
    generated_at: int
    text: str
    triples: tuple
    kept_at: int
    by: str


def _terms(topics, about: str, text: str) -> set:
    """Lexical index terms. Matching and search read these; neither needs a model."""
    return set(topics) | {about} | set(re.findall(r"[a-z0-9]+", text.lower()))


def stated_until(earlier: int | None, stated: int) -> int:
    """A later body can shorten a source revision's validity, never extend it (I-3, AC3). Extending
    a source takes a new revision, which is new evidence."""
    return stated if earlier is None else min(earlier, stated)


def evidence_state(rx: "Receiver", held: Held, claim: Claim, t: int) -> str | None:
    """Claim-level dependency: the worst state among the sources this claim cites, from the ledger."""
    found = set()
    for s in held.proj.cited(claim):
        mark = rx.marks[(held.key_id, s.actor, s.ref)]
        if w := mark.withdrawn.get(s.rev):
            found.add("source-superseded" if w[0] == "superseded" else "withdrawn")
        if s.rev < mark.max_rev:
            found.add("source-superseded")
        if t >= mark.until[s.rev]:
            found.add("source-lapsed")
    return next((st for st in ("withdrawn", "source-superseded", "source-lapsed") if st in found), None)


def claim_status(rx: "Receiver", held: Held, claim: Claim, t: int) -> str:
    """Every rule here can only end currency, never extend it."""
    ev = evidence_state(rx, held, claim, t)
    history = held.proj.standing == "history"
    if ev in ("withdrawn", "source-superseded") and not history:
        return ev
    if held.retracted:
        return "retracted"
    if held.superseded_by:
        return "superseded"
    if t >= min(held.item_until, held.proj.valid_until):
        return "lapsed"
    if history:
        return "history"
    if ev:
        return ev
    if rx.coverage[0] != "complete":
        return "carried"
    return "current"


def claim_until(rx: "Receiver", held: Held, claim: Claim) -> int:
    marks = [rx.marks[(held.key_id, s.actor, s.ref)].until[s.rev] for s in held.proj.cited(claim)]
    return min([held.item_until, held.proj.valid_until] + marks)


class Receiver:
    """A reference receiver. It reads what producers said; it never calls a model."""

    CONFIG = {"topics", "actors", "window_ms", "min_support"}

    def __init__(self, name: str, cfg: dict):
        if not isinstance(cfg, dict) or set(cfg) - self.CONFIG:
            raise FixtureError(f"receiver {name}: config keys are {sorted(self.CONFIG)}")
        self.name = name
        self.topics = frozenset(cfg.get("topics", ()))
        self.actors = frozenset(cfg.get("actors", ()))
        self.window_ms = cfg.get("window_ms", 30_000)
        self.min_support = cfg.get("min_support", 1)
        self.override: tuple | None = None  # (topics, until) from a temporary retune
        self.coverage: tuple = ("complete", None, None)  # (state, since, reason)
        self.held: dict = {}
        self.latest: dict = {}  # (key_id, projection key) -> held name
        self.marks: dict = {}  # (key_id, actor, ref) -> SourceMark
        self.idems: set = set()
        self.sticky: dict = {}  # retracted before heard: idem -> reason (§7.7)
        self.pending: dict = {}  # pkey -> Pending
        self.presented: dict = {}  # pkey -> ref
        self.noted: set = set()
        self.kept: dict = {}
        self.refused: list = []
        self.repeats = 0
        self.model_calls = 0

    # -- intake ------------------------------------------------------------------------------------

    def frame(self, f: Frame, t: int) -> str:
        if f.expires_at <= t:
            raise FixtureError(f"{f.name}: a frame that expired before it was heard is never delivered")
        if f.idem in self.idems:
            return "duplicate"  # R-INT-1
        self.idems.add(f.idem)
        if f.idem in self.sticky:
            return "plucked"
        try:
            proj = read_descriptor(f.body, f.scope)
        except Refused as e:
            self.refused.append([f.name, e.code])
            return e.code
        cur = self.held.get(self.latest.get((f.key_id, proj.key)))
        if cur is not None:
            if proj.generated_at < cur.proj.generated_at:
                self.refused.append([f.name, "stale"])
                return "stale"  # a restarted producer cannot roll a key back
            if proj.generated_at == cur.proj.generated_at:
                if proj.digest != cur.proj.digest:
                    self.refused.append([f.name, "conflict"])
                    return "conflict"
                cur.aliases.add(cur.idem)  # R-INT-2: one lineage root; the new copy supersedes the old
                cur.idem, cur.item_until = f.idem, f.expires_at
                self.repeats += 1
                return "repeat"
            cur.superseded_by = f.name
        if f.name in self.held:
            raise FixtureError(f"body {f.name} admitted twice as two projections")
        held = Held(f.name, f, proj, f.idem, f.expires_at, {c.id: presentation_key(proj, c) for c in proj.claims})
        self.held[f.name] = held
        self.latest[(f.key_id, proj.key)] = f.name
        self._mark(f.key_id, proj, t)
        self._enqueue(held, t)
        return "admitted"

    def _mark(self, key_id: str, proj: Projection, t: int) -> None:
        for s in proj.sources.values():
            mark = self.marks.setdefault((key_id, s.actor, s.ref), SourceMark(s.rev))
            mark.max_rev = max(mark.max_rev, s.rev)
            mark.until[s.rev] = stated_until(mark.until.get(s.rev), s.valid_until)
        for actor, ref, rev, reason in proj.withdrawn:
            mark = self.marks.setdefault((key_id, actor, ref), SourceMark(rev))
            mark.max_rev = max(mark.max_rev, rev)
            mark.withdrawn.setdefault(rev, (reason, t))

    def retract(self, ident: str, reason: str, t: int) -> str:
        for held in self.held.values():
            if ident in held.aliases:
                return "old copy"
            if ident == held.idem:
                if reason == "expired":
                    held.item_until = min(held.item_until, t)
                elif not held.retracted:
                    held.retracted = reason
                return "applied"
        self.sticky[ident] = reason
        return "sticky"

    def health(self, t: int, reason: str) -> None:
        if self.coverage[0] == "complete":
            self.coverage = ("unknown", t, reason)

    def snapshot(self, t: int, frames: list, complete: bool) -> list:
        results = [self.frame(f, t) for f in frames]
        if complete:
            listed = {f.idem for f in frames}
            for held in self.held.values():
                if held.idem not in listed and held.item_until > t and not held.retracted:
                    held.retracted = "off air"
            self.coverage = ("complete", None, None)
        return results

    def restart(self, t: int) -> list:
        """The journal, ledger, pending and presented sets persist; coverage does not."""
        self.coverage = ("unknown", t, "restart")
        settled = []
        for pkey, p in sorted(self.pending.items(), key=lambda kv: (kv[1].due, kv[1].first_ref)):
            if self._resolve(pkey, t) is None:
                settled.append(p.first_ref)
                del self.pending[pkey]
        return settled

    def retune(self, t: int, topics, until: int) -> None:
        self.override = (frozenset(topics), until)
        for held in self.held.values():
            self._enqueue(held, t)

    def retain(self, t: int, ref: str, by: str) -> str:
        if by not in ("principal", "human"):
            return "refused"  # §6.4 and I-10: a session never keeps what it heard
        held, claim = self.claim(ref)
        if claim_status(self, held, claim, t) not in LIVE + ("history",):
            return "refused"
        self.kept["kept:" + ref] = Kept(ref, held.key_id, held.frame.station, claim.about, claim.topics,
                                         held.proj.window, held.proj.generated_at, claim.text,
                                         tuple(s.triple for s in held.proj.cited(claim)), t, by)
        return "kept"

    # -- matching and presentation -----------------------------------------------------------------

    def interest(self, t: int) -> tuple:
        if self.override and t < self.override[1]:
            return self.override[0], f"retune until {fmt(self.override[1])}"
        return self.topics, None

    def matches(self, claim: Claim, t: int) -> str | None:
        topics, via = self.interest(t)
        if hit := [x for x in claim.topics if x in topics]:
            return f"topic {hit[0]}" + (f", {via}" if via else "")
        if claim.about in self.actors:
            return f"actor {claim.about}"
        return None

    def _enqueue(self, held: Held, t: int) -> None:
        for c in held.proj.claims:
            pkey = held.pkeys[c.id]
            if pkey in self.presented or pkey in self.pending:
                continue
            if claim_status(self, held, c, t) not in LIVE or support_of(held.proj, c) < self.min_support:
                continue
            if why := self.matches(c, t):
                self.pending[pkey] = Pending(pkey, f"{held.name}#{c.id}", t + self.window_ms, why)

    def _resolve(self, pkey: tuple, t: int):
        """The newest live claim with this presentation key, or None."""
        best = None
        for held, c in self.claims():
            if held.pkeys[c.id] == pkey and claim_status(self, held, c, t) in LIVE:
                best = (held, c)
        return best

    def present(self, t: int) -> dict:
        presented, settled, notes = [], [], []
        keep = {}
        for p in sorted(self.pending.values(), key=lambda p: (p.due, p.first_ref)):
            hit = self._resolve(p.pkey, t)
            if hit is None:
                settled.append(p.first_ref)
                continue
            held, claim = hit
            if p.due > t or claim_status(self, held, claim, t) == "carried":
                keep[p.pkey] = p
            elif self.matches(claim, t) and support_of(held.proj, claim) >= self.min_support:
                presented.append(f"{held.name}#{claim.id}")
                self.presented[p.pkey] = presented[-1]
            else:
                settled.append(p.first_ref)
        self.pending = keep
        for pkey, ref in self.presented.items():
            if pkey not in self.noted and self._resolve(pkey, t) is None:
                held, claim = self._newest(pkey)
                notes.append(f"{ref}: no longer current ({claim_status(self, held, claim, t)})")
                self.noted.add(pkey)
        return {"presented": presented, "settled": settled, "notes": notes}

    def _newest(self, pkey: tuple):
        return [(h, c) for h, c in self.claims() if h.pkeys[c.id] == pkey][-1]

    # -- reading -----------------------------------------------------------------------------------

    def claims(self):
        for held in self.held.values():
            for c in held.proj.claims:
                yield held, c

    def claim(self, ref: str):
        name, _, cid = ref.partition("#")
        held = self.held.get(name)
        found = [c for c in held.proj.claims if c.id == cid] if held else []
        if not found:
            raise FixtureError(f"{self.name} holds no claim {ref}")
        return held, found[0]

    def status(self, ref: str, t: int) -> str:
        return claim_status(self, *self.claim(ref), t)

    def topic_support(self, topic: str, t: int) -> int:
        actors = set()
        for held, c in self.claims():
            if topic in c.topics and claim_status(self, held, c, t) == "current":
                actors |= {s.actor for s in held.proj.cited(c)}
        return len(actors)

    def view(self, t: int, name: str, q: str | None = None, history: bool = False, interest: bool = False) -> list:
        refs = []
        if name == "pending":
            for p in sorted(self.pending.values(), key=lambda p: (p.due, p.first_ref)):
                if hit := self._resolve(p.pkey, t):
                    refs.append(f"{hit[0].name}#{hit[1].id}")
            return refs
        if name not in ("current", "search", "history"):
            raise FixtureError(f"unknown view {name!r}")
        words = set(q.lower().split()) if q else set()
        for held, c in self.claims():
            st = claim_status(self, held, c, t)
            if name == "history":
                wanted = st == "history"
            else:  # current and search show live claims; search shows history only when asked
                wanted = st in LIVE or (name == "search" and history and st == "history")
            if not wanted or (interest and not self.matches(c, t)):
                continue
            if name == "search" and not words & _terms(c.topics, c.about, c.text):
                continue
            refs.append(f"{held.name}#{c.id}")
        if name == "history" or (name == "search" and history):
            refs += [ref for ref, k in self.kept.items()
                     if name == "history" or words & _terms(k.topics, k.about, k.text)]
        return refs

    def why(self, ref: str, t: int, view: str) -> str | None:
        if view == "pending":
            held, claim = self.claim(ref)
            p = self.pending.get(held.pkeys[claim.id])
            return p.why if p else None
        return self.matches(self.claim(ref)[1], t)

    def unknown(self, t: int) -> list:
        """Actors a live projection says its producer could not read: unknown, never quiet."""
        out = []
        for held in self.held.values():
            if held.proj.standing == "current" and not held.retracted and not held.superseded_by \
                    and t < min(held.item_until, held.proj.valid_until):
                out += [(a, held) for a in held.proj.unread]
        return out

    def withdrawn_at(self, key_id: str, triples) -> int | None:
        times = [m.withdrawn[r][1] for a, ref, r in triples
                 if (m := self.marks.get((key_id, a, ref))) and r in m.withdrawn]
        return min(times) if times else None

    def render(self, t: int, name: str, refs: list) -> list:
        """Host-written lines. Claim text only ever appears quoted (`> `), as data (I-6)."""
        state, since, reason = self.coverage
        head = f"{name} view at {fmt(t)}; coverage {state}"
        if since is not None:
            head += f" since {fmt(since)} ({reason}); live claims are carried, not confirmed"
        lines = [head]
        for ref in refs:
            if ref in self.kept:
                k = self.kept[ref]
                line = (f"- [history] about {k.about}, from {k.station} {k.key_id}, window {fmt(k.window[0])}-"
                        f"{fmt(k.window[1])}, generated {fmt(k.generated_at)}, kept at {fmt(k.kept_at)} by {k.by}")
                if (w := self.withdrawn_at(k.key_id, k.triples)) is not None:
                    line += f"; source withdrawn at {fmt(w)}"
                lines += [line, "> " + k.text]
                continue
            held, c = self.claim(ref)
            st = claim_status(self, held, c, t)
            line = (f"- [{label_of(held.proj, c)}] about {c.about}, from {held.frame.station} {held.key_id}, "
                    f"window {fmt(held.proj.window[0])}-{fmt(held.proj.window[1])}, generated "
                    f"{fmt(held.proj.generated_at)}, {st}")
            if st in LIVE:
                line += f", support {support_of(held.proj, c)}, until {fmt(claim_until(self, held, c))}"
            elif st == "history":
                line += ", historical"
                if (w := self.withdrawn_at(held.key_id, [s.triple for s in held.proj.cited(c)])) is not None:
                    line += f"; source withdrawn at {fmt(w)}"
            lines += [line, "> " + c.text]
        if name == "current":
            for actor, held in self.unknown(t):
                lines.append(f"- {actor}: unknown; {held.frame.station} {held.key_id} did not read it for window "
                             f"{fmt(held.proj.window[0])}-{fmt(held.proj.window[1])}")
        if not refs:
            lines.append("- no claims in this view; that says nothing about any source")
        return lines


# ---------------------------------------------------------------------------------------------------
# Fixtures

STEP_KEYS = {
    "frame": {"body", "seq", "expires_at", "to", "key_id", "station", "stream", "scope", "epoch", "refresh", "expect"},
    "retract": {"seq", "reason", "to", "key_id", "stream", "epoch", "expect"},
    "health": {"at", "records_lost", "no_datagrams"},
    "snapshot": {"at", "frames", "complete", "expect"},
    "restart": {"at", "expect"},
    "retune": {"at", "topics", "until"},
    "retain": {"at", "claim", "by", "expect"},
    "read": {"at", "view", "q", "history", "interest", "expect"},
    "present": {"at", "expect"},
    "descriptor": {"body", "scope", "expect"},
}
READ_EXPECT = {"claims", "status", "labels", "support", "topic_support", "same_evidence", "coverage", "unknown",
               "why", "until", "render_includes", "render_excludes"}
FIXTURE_KEYS = {"v", "name", "case", "synthetic", "about", "defaults", "receivers", "bodies", "steps", "expect_end"}


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise FixtureError(f"duplicate JSON key {k!r}")
        out[k] = v
    return out


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_no_dupes)


def host_lines(lines: list) -> list:
    return [x for x in lines if not x.startswith("> ")]


def _has_word(line: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", line.lower()) is not None


class Run:
    def __init__(self, fx: dict, name: str):
        if set(fx) - FIXTURE_KEYS or fx.get("v") != FIXTURE:
            raise FixtureError(f"{name}: top-level keys are {sorted(FIXTURE_KEYS)}, v {FIXTURE}")
        if fx.get("synthetic") is not True:
            raise FixtureError(f"{name}: every fixture here is synthetic and says so")
        if fx.get("name") != name:
            raise FixtureError(f"{name}: name {fx.get('name')!r} does not match the file")
        self.fx = fx
        self.defaults = {"station": "familiar", "stream": "wake", "scope": "lan", "epoch": 1, **fx.get("defaults", {})}
        self.bodies = fx.get("bodies", {})
        self.rx = {n: Receiver(n, cfg) for n, cfg in fx.get("receivers", {}).items()}
        self.cost = ProducerCost()
        self.owner: dict = {}
        self.failures: list = []
        self.reads = 0

    def fail(self, i: int, step: dict, msg: str) -> None:
        self.failures.append(f"step {i} (t={step.get('t')}, {step.get('op')}): {msg}")

    def frame_of(self, spec: dict) -> Frame:
        d = {**self.defaults, **spec}
        name = d["body"]
        if name not in self.bodies:
            raise FixtureError(f"no body named {name!r}")
        if not KEY_ID_RE.fullmatch(d.get("key_id", "")):
            raise FixtureError(f"{name}: key_id must be 16 hex digits")
        if self.owner.setdefault(name, d["key_id"]) != d["key_id"]:
            raise FixtureError(f"body {name} is sent by two station keys; give each producer its own bodies")
        return Frame(name, self.bodies[name], d["key_id"], d["station"], d["stream"], d["scope"], d["epoch"],
                     d["seq"], d["expires_at"])

    def targets(self, step: dict) -> list:
        names = step.get("to", list(self.rx))
        if isinstance(names, str):
            names = [names]
        if unknown := [n for n in names if n not in self.rx]:
            raise FixtureError(f"unknown receivers {unknown}")
        return [self.rx[n] for n in names]

    def run(self) -> list:
        last_t = -1
        for i, step in enumerate(self.fx.get("steps", [])):
            op = step.get("op")
            if op not in STEP_KEYS or set(step) - STEP_KEYS[op] - {"t", "op"}:
                raise FixtureError(f"step {i}: op {op!r} takes {sorted(STEP_KEYS.get(op, ()))}")
            t = step.get("t", last_t)
            if op != "descriptor" and (not isinstance(t, int) or isinstance(t, bool) or t < max(last_t, 0)):
                raise FixtureError(f"step {i}: t must be a non-negative integer that never goes back")
            last_t = t
            getattr(self, "op_" + op)(i, step, t)
        self.check_end()
        return self.failures

    def expect(self, i: int, step: dict, what: str, got, want) -> None:
        if isinstance(want, list) and isinstance(got, list):
            got, want = sorted(got, key=json.dumps), sorted(want, key=json.dumps)
        if got != want:
            self.fail(i, step, f"{what}: expected {want!r}, got {got!r}")

    def op_descriptor(self, i: int, step: dict, t) -> None:
        try:
            read_descriptor(self.bodies[step["body"]], step.get("scope", "lan"))
            got = "ok"
        except Refused as e:
            got = e.code
        self.expect(i, step, f"descriptor {step['body']}", got, step["expect"])

    def op_frame(self, i: int, step: dict, t: int) -> None:
        f = self.frame_of(step)
        self.cost.emit(f.key_id, f.idem, f.body, f.scope)
        want = step.get("expect", {}).get("admit")
        for rx in self.targets(step):
            got = rx.frame(f, t)
            if want is not None:
                self.expect(i, step, f"{rx.name} admit {f.name}", got,
                            want[rx.name] if isinstance(want, dict) else want)

    def op_retract(self, i: int, step: dict, t: int) -> None:
        d = {**self.defaults, **step}
        if d["reason"] not in RETRACT_REASONS:
            raise FixtureError(f"retract reason {d['reason']!r}")
        ident = idem(d["key_id"], d["epoch"], d["stream"], d["seq"])
        for rx in self.targets(step):
            got = rx.retract(ident, d["reason"], t)
            if "expect" in step:
                self.expect(i, step, f"{rx.name} retract", got, step["expect"])

    def op_health(self, i: int, step: dict, t: int) -> None:
        if step.get("records_lost"):
            reason = f"{step['records_lost']} records lost"
        elif step.get("no_datagrams") is True:
            reason = "no datagrams heard"
        else:
            raise FixtureError("health needs records_lost or no_datagrams")
        self.rx[step["at"]].health(t, reason)

    def op_snapshot(self, i: int, step: dict, t: int) -> None:
        rx = self.rx[step["at"]]
        got = rx.snapshot(t, [self.frame_of(s) for s in step.get("frames", [])], step.get("complete") is True)
        if "expect" in step:
            self.expect(i, step, f"{rx.name} snapshot", got, step["expect"])

    def op_restart(self, i: int, step: dict, t: int) -> None:
        rx = self.rx[step["at"]]
        got = rx.restart(t)
        if "expect" in step:
            self.expect(i, step, f"{rx.name} settled at restart", got, step["expect"].get("settled", []))

    def op_retune(self, i: int, step: dict, t: int) -> None:
        if not isinstance(step.get("until"), int) or step["until"] <= t:
            raise FixtureError("a temporary retune needs an absolute until after t")
        self.rx[step["at"]].retune(t, step["topics"], step["until"])

    def op_retain(self, i: int, step: dict, t: int) -> None:
        rx = self.rx[step["at"]]
        got = rx.retain(t, step["claim"], step["by"])
        self.expect(i, step, f"{rx.name} retain {step['claim']}", got, step["expect"])

    def op_present(self, i: int, step: dict, t: int) -> None:
        rx = self.rx[step["at"]]
        got = rx.present(t)
        for k, want in step.get("expect", {}).items():
            if k not in got:
                raise FixtureError(f"present expects only {sorted(got)}")
            self.expect(i, step, f"{rx.name} {k}", got[k], want)

    def op_read(self, i: int, step: dict, t: int) -> None:
        rx = self.rx[step["at"]]
        view = step.get("view", "current")
        refs = rx.view(t, view, q=step.get("q"), history=step.get("history", False),
                       interest=step.get("interest", False))
        if len(set(refs)) != len(refs):
            self.fail(i, step, f"view lists a claim twice: {refs}")
        lines = rx.render(t, view, refs)
        self.reads += 1
        for line in host_lines(lines):
            for word in SILENCE_WORDS:
                if _has_word(line, word):
                    self.fail(i, step, f"host line says {word!r} (§6.3 rule 5): {line}")
        exp = step.get("expect", {})
        if unknown := set(exp) - READ_EXPECT:
            raise FixtureError(f"read expectations are {sorted(READ_EXPECT)}; not {sorted(unknown)}")
        for k, want in exp.items():
            if k == "claims":
                self.expect(i, step, "claims", refs, want)
            elif k == "coverage":
                self.expect(i, step, "coverage", rx.coverage[0], want)
            elif k == "unknown":
                self.expect(i, step, "unknown", [a for a, _ in rx.unknown(t)], want)
            elif k == "same_evidence":
                for group in want:
                    ids = {rx.claim(r)[0].pkeys[rx.claim(r)[1].id][1] for r in group}
                    if len(ids) != 1:
                        self.fail(i, step, f"evidence differs across {group}")
            elif k == "render_includes":
                for s in want:
                    if s not in "\n".join(lines):
                        self.fail(i, step, f"render lacks {s!r}:\n" + "\n".join(lines))
            elif k == "render_excludes":
                for s in want:
                    if any(_has_word(x, s) for x in host_lines(lines)):
                        self.fail(i, step, f"a host line says {s!r}:\n" + "\n".join(lines))
            else:
                for key, w in want.items():
                    if k == "topic_support":
                        got = rx.topic_support(key, t)
                    elif k == "why":
                        got = rx.why(key, t, view)
                    else:
                        held, claim = rx.claim(key)
                        got = {"status": lambda: claim_status(rx, held, claim, t),
                               "labels": lambda: label_of(held.proj, claim),
                               "support": lambda: support_of(held.proj, claim),
                               "until": lambda: claim_until(rx, held, claim)}[k]()
                    self.expect(i, step, f"{k} {key}", got, w)

    def check_end(self) -> None:
        end = self.fx.get("expect_end", {})
        step = {"t": "end", "op": "expect_end"}
        for key_id, want in end.get("producers", {}).items():
            got = self.cost.counts.get(key_id, dict.fromkeys(ProducerCost.FIELDS, 0))
            for k, w in want.items():
                self.expect(-1, step, f"producer {key_id} {k}", got[k], w)
        for name, want in end.get("receivers", {}).items():
            rx = self.rx[name]
            for k, w in want.items():
                got = {"model_calls": rx.model_calls, "repeats": rx.repeats, "refused": rx.refused}[k]
                self.expect(-1, step, f"receiver {name} {k}", got, w)


def run_fixture(path) -> list:
    """Run one fixture file; return its failures (empty when it passes)."""
    path = Path(path)
    return Run(load(path), path.stem).run()


def main(argv: list) -> int:
    here = Path(__file__).resolve().parent
    paths = [Path(p) for p in argv] or sorted((here / "fixtures").glob("*.json"))
    bad = 0
    for path in paths:
        fx = load(path)
        failures = run_fixture(path)
        print(f"{'ok  ' if not failures else 'FAIL'} {path.stem} ({fx.get('case')})")
        for f in failures:
            print("     " + f)
        bad += bool(failures)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
