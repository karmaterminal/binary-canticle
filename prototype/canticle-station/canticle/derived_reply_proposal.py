"""Default-closed #146 review primitive. Not registered with the CLI, control socket or any agent tool.

The default is closed. All mutators below are trusted-host operations, not model-callable APIs.
This exercises a candidate capability representation; it does not authorize deployment, implement
the host's exposure/egress controls. The separate unregistered station adapter proves an effect boundary.
This primitive alone does not claim station acceptance. See the accompanying review note.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import wire
from .ids import CLASS_BY_NAME, CTYPES, SCOPES, check_stream_name, key_id, stream_id

VERSION = "canticle-derived-reply-proposal/2"
DOMAIN = b"canticle-derived-reply-proposal\x00"
MAX_EXPOSURES = 256  # overflow refuses; never truncate the causal ledger to make a reply fit
MAX_CAPSULE_BYTES = 8192


class Refused(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class _ObservedExpiry(Refused):
    """Commit a terminal deadline observation without releasing the transaction lock first."""
    def __init__(self, election_id: str):
        self.election_id = election_id
        super().__init__("expired")


def _require(value: bool, reason: str) -> None:
    if not value:
        raise Refused(reason)


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _name(value: str, limit: int = 128) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= limit
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]*", value) is not None)


def _uint(value: int, maximum: int = 2**53 - 1) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _tuple(value: tuple) -> bool:
    return (type(value) is tuple and len(value) == 4 and isinstance(value[0], str)
            and re.fullmatch(r"[0-9a-f]{16}", value[0]) is not None
            and _uint(value[1], 2**64 - 1) and _uint(value[2], 2**32 - 1)
            and _uint(value[3], 2**64 - 1) and value[3] > 0)


@dataclass(frozen=True)
class Reader:
    principal: str
    session_key: str
    session_id: str
    lifecycle_revision: str

    def __post_init__(self):
        _require(all(_name(x) for x in (self.principal, self.session_id, self.lifecycle_revision)), "reader_identity")
        _require(isinstance(self.session_key, str)
                 and re.fullmatch(r"agent:[a-z][a-z0-9_-]*:subagent:[a-z0-9_-]+(?::[a-z0-9_-]+){0,4}", self.session_key) is not None,
                 "reader_identity")

    @property
    def generation(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class Exposure:
    receipt_id: str
    binding: str
    reader_decision: str
    item: tuple
    root: tuple | None
    hop: int
    drained_at: int
    expires_at: int
    source_class: str = "chatter"
    wake_derived: bool | None = False
    scope: str | None = None  # F1: the heard source's own scope; None (unrecorded) refuses every reply

    def __post_init__(self):
        _require(all(_name(x) for x in (self.receipt_id, self.binding, self.reader_decision)), "exposure_receipt")
        _require(_tuple(self.item) and (self.root is None or _tuple(self.root)), "source_identity")
        _require(_uint(self.hop, 15) and _uint(self.drained_at) and _uint(self.expires_at)
                 and self.drained_at < self.expires_at, "source_bounds")
        _require(self.source_class in CLASS_BY_NAME and
                 (self.wake_derived is None or type(self.wake_derived) is bool)
                 and (self.scope is None or self.scope in SCOPES), "source_class")


def exposure_record(exposure: Exposure) -> dict:
    """Candidate canonical receipt: counters are decimal strings, avoiding JSON/JS uint64 rounding."""
    value = asdict(exposure)
    value["item"] = [exposure.item[0], *(str(x) for x in exposure.item[1:])]
    value["root"] = None if exposure.root is None else [exposure.root[0], *(str(x) for x in exposure.root[1:])]
    return value


@dataclass(frozen=True)
class HistoryOrigin:
    """Trusted host proof of a complete initial prefix, not a taint Boolean or operator guess."""
    receipt_id: str
    kind: str
    count: int
    digest: str

    def __post_init__(self):
        _require(_name(self.receipt_id) and self.kind in ("observed_session_birth", "verified_full_history")
                 and _uint(self.count, MAX_EXPOSURES)
                 and re.fullmatch(r"[0-9a-f]{64}", self.digest or "") is not None, "history_attestation")


@dataclass(frozen=True)
class Intent:
    publisher: str
    station: str
    key_id: str
    stream: str
    audience: tuple[Reader, ...]
    public_key: str
    ttl_ms: int = 60_000
    cls: str = "chatter"
    scope: str = "lan"

    def __post_init__(self):
        _require(_name(self.publisher) and _name(self.station, 31), "publisher_identity")
        _require(re.fullmatch(r"[0-9a-f]{16}", self.key_id or "") is not None, "publisher_identity")
        _require(re.fullmatch(r"[0-9a-f]{64}", self.public_key or "") is not None
                 and key_id(bytes.fromhex(self.public_key)).hex() == self.key_id, "publisher_identity")
        check_stream_name(self.stream)
        _require(type(self.audience) is tuple and 1 <= len(self.audience) <= 16
                 and all(isinstance(x, Reader) for x in self.audience)
                 and len({x.session_key for x in self.audience}) == len(self.audience), "audience")
        _require(_uint(self.ttl_ms) and self.ttl_ms > 100, "ttl")


@dataclass(frozen=True)
class Grant:
    """Owner-supplied fixture policy, not a replacement for the real station manifest/host policy."""
    publisher: str
    station: str
    key_id: str
    stream: str
    authors: tuple[str, ...]
    audience_principals: tuple[str, ...]
    public_key: str
    scope: str = "lan"
    max_ttl_ms: int = 60_000
    max_bytes: int = 600
    per_turn: int = 5
    per_hour: int = 60
    capability_ms: int = 30_000

    def __post_init__(self):
        _require(re.fullmatch(r"[0-9a-f]{64}", self.public_key or "") is not None
                 and key_id(bytes.fromhex(self.public_key)).hex() == self.key_id, "grant")
        # An empty authors or audience tuple is a revocation: nobody passes the membership checks (closed).
        _require(self.scope in ("host", "lan") and type(self.authors) is tuple
                 and type(self.audience_principals) is tuple, "grant")
        _require(all(_name(x) and "*" not in x for x in (*self.authors, *self.audience_principals)), "grant")
        _require(_uint(self.max_ttl_ms, 300_000) and self.max_ttl_ms > 100
                 and _uint(self.max_bytes, 800) and self.max_bytes > 0
                 and _uint(self.per_turn, 5) and self.per_turn > 0
                 and _uint(self.per_hour, 60) and self.per_hour > 0
                 and _uint(self.capability_ms, 30_000) and self.capability_ms > 0, "grant_bounds")


def _stored_grant(value: dict) -> Grant:
    """JSON stores tuples as lists; restore them so the stored grant passes the same validation."""
    return Grant(**{**value, "authors": tuple(value["authors"]),
                    "audience_principals": tuple(value["audience_principals"])})


def narrower_grant(stored: Grant, given: Grant) -> Grant:
    """The intersection of two grants for one publisher identity; refuses rather than choosing between identities."""
    identity = ("publisher", "station", "key_id", "stream", "public_key")
    _require(all(getattr(stored, f) == getattr(given, f) for f in identity), "grant_conflict")
    authors = tuple(x for x in given.authors if x in stored.authors)
    audience = tuple(x for x in given.audience_principals if x in stored.audience_principals)
    bounds = ("max_ttl_ms", "max_bytes", "per_turn", "per_hour", "capability_ms")
    return Grant(**{**{f: getattr(given, f) for f in identity}, "authors": authors, "audience_principals": audience,
                    "scope": min(stored.scope, given.scope, key=SCOPES.__getitem__),
                    **{f: min(getattr(stored, f), getattr(given, f)) for f in bounds}})


@dataclass(frozen=True)
class Admission:
    """A consumed proposal permission. This is not an on-air or received-item receipt."""
    election_id: str
    envelope: bytes


class ReplyProposal:
    def __init__(self, path: Path, *, enabled: bool = False, issuer_public: bytes | None = None,
                 issuer_key: Ed25519PrivateKey | None = None,
                 issuer: str = "fixture-host", grant: Grant | None = None,
                 content_allowed: Callable[[bytes], bool] | None = None,
                 clock: Callable[[], int] = lambda: time.time_ns() // 1_000_000):
        # F3 (#162 review): the issuer signs capsules with its private key; a station verifies with the
        # public key alone. Construct the station side WITHOUT issuer_key: it can admit, never mint.
        # This separates roles in code only. Holding the private key where the ear's uid cannot read
        # or command it is a deployment boundary (binary-canticle#99, rfc/0002 §4.2).
        self.path, self.enabled, self.issuer_key = Path(path), enabled, issuer_key
        self.issuer_public = issuer_public
        self.issuer, self.grant, self.content_allowed, self.clock = issuer, grant, content_allowed, clock
        if not enabled:
            return  # default-closed construction creates no state, key or process
        _require(type(issuer_public) is bytes and len(issuer_public) == 32 and _name(issuer)
                 and grant is not None and callable(content_allowed), "authority_missing")
        _require(issuer_key is None or (isinstance(issuer_key, Ed25519PrivateKey)
                                        and wire.public_key_bytes(issuer_key) == issuer_public), "issuer_key_mismatch")
        self._verify_key = Ed25519PublicKey.from_public_bytes(issuer_public)
        # The caller owns the private directory; reject a symlink or broadly accessible existing DB.
        if self.path.exists() or self.path.is_symlink():
            st = self.path.lstat()
            _require(self.path.is_file() and not self.path.is_symlink() and not (st.st_mode & 0o077), "state_permissions")
        else:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        db = self._db()
        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS readers (session_key TEXT PRIMARY KEY, generation TEXT NOT NULL, reader TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reader_history (session_key TEXT NOT NULL, generation TEXT NOT NULL,
                    PRIMARY KEY(session_key, generation));
                CREATE TABLE IF NOT EXISTS origins (generation TEXT PRIMARY KEY, receipt TEXT NOT NULL,
                    kind TEXT NOT NULL, complete INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK (id=1), enabled INTEGER NOT NULL,
                    grant_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS exposures (
                    ordinal INTEGER PRIMARY KEY AUTOINCREMENT, generation TEXT NOT NULL, receipt_id TEXT NOT NULL,
                    record TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, UNIQUE(generation, receipt_id));
                CREATE TABLE IF NOT EXISTS pending_exposures (
                    id TEXT PRIMARY KEY, generation TEXT NOT NULL, receipt_id TEXT NOT NULL, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS withdrawn_receipts (
                    generation TEXT NOT NULL, receipt_id TEXT NOT NULL, PRIMARY KEY(generation, receipt_id));
                CREATE TABLE IF NOT EXISTS elections (
                    id TEXT PRIMARY KEY, generation TEXT NOT NULL, choice_id TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
                    reader TEXT NOT NULL, turn_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL, intent TEXT NOT NULL,
                    snapshot TEXT NOT NULL, citation TEXT NOT NULL, wake_derived INTEGER NOT NULL,
                    issued_at INTEGER NOT NULL, valid_until INTEGER NOT NULL, item_expires_at INTEGER NOT NULL,
                    state TEXT NOT NULL, claimed_at INTEGER, envelope TEXT,
                    UNIQUE(generation, choice_id));
                CREATE TABLE IF NOT EXISTS station_effects (
                    election_id TEXT PRIMARY KEY, state TEXT NOT NULL, receipt TEXT);
                CREATE TABLE IF NOT EXISTS outcomes (
                    election_id TEXT NOT NULL, kind TEXT NOT NULL, receipt TEXT NOT NULL,
                    PRIMARY KEY(election_id, kind, receipt));
            """)
            # F2: neither the persisted grant nor the constructor's is authority alone. The effective grant
            # is the narrower of the two, so an owner's narrowing (by config or replace_grant) governs every
            # check after a restart, and widening needs an explicit replace_grant. Identity disagreement refuses.
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT grant_json FROM policy WHERE id=1").fetchone()
                effective = grant if row is None else narrower_grant(_stored_grant(json.loads(row[0])), grant)
                db.execute("INSERT INTO policy VALUES (1,1,?) ON CONFLICT(id) DO UPDATE SET grant_json=excluded.grant_json",
                           (_json(asdict(effective)).decode(),))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        finally:
            db.close()

    def _db(self) -> sqlite3.Connection:
        _require(self.enabled, "disabled")
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def _tx(self, *, gated: bool = True) -> Iterator[sqlite3.Connection]:
        db = self._db()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("SAVEPOINT operation")
            if gated:
                _require(db.execute("SELECT enabled FROM policy WHERE id=1").fetchone()[0] == 1, "disabled")
            yield db
            db.execute("RELEASE operation")
            db.commit()
        except _ObservedExpiry as expired:
            # Roll back only the attempted operation, retaining the writer lock until the deadline
            # observation is durable. Another instance cannot revive it in a rollback/reacquire gap.
            try:
                db.execute("ROLLBACK TO operation")
                db.execute("RELEASE operation")
                db.execute("UPDATE elections SET state='expired' WHERE id=? AND state IN ('elected','claimed_unknown')",
                           (expired.election_id,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
            raise Refused("expired") from None
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _now(self) -> int:
        now = self.clock()
        _require(_uint(now), "clock")
        return now

    def _current(self, db: sqlite3.Connection, reader: Reader) -> None:
        row = db.execute("SELECT generation FROM readers WHERE session_key=?", (reader.session_key,)).fetchone()
        _require(row is not None and row["generation"] == reader.generation, "reader_generation")

    def set_current_reader(self, reader: Reader) -> None:
        """Trusted host observation of an incarnation; never resets an actual session or deletes history."""
        with self._tx(gated=False) as db:
            old = db.execute("SELECT generation FROM readers WHERE session_key=?", (reader.session_key,)).fetchone()
            if old is not None and old["generation"] != reader.generation:
                _require(db.execute("SELECT 1 FROM reader_history WHERE session_key=? AND generation=?",
                                    (reader.session_key, reader.generation)).fetchone() is None, "generation_reuse")
            db.execute("INSERT OR IGNORE INTO reader_history VALUES (?,?)", (reader.session_key, reader.generation))
            db.execute("INSERT INTO readers VALUES (?,?,?) ON CONFLICT(session_key) DO UPDATE SET generation=excluded.generation,reader=excluded.reader",
                       (reader.session_key, reader.generation, _json(asdict(reader)).decode()))

    def set_publication_enabled(self, enabled: bool) -> None:
        """Trusted owner fixture gate; closing it is durable and fences all instances' later claims."""
        _require(type(enabled) is bool, "gate")
        with self._tx(gated=False) as db:
            db.execute("UPDATE policy SET enabled=? WHERE id=1", (int(enabled),))

    def replace_grant(self, grant: Grant) -> None:
        """Trusted policy revision, serialized with claim/admission; never model input."""
        with self._tx(gated=False) as db:
            db.execute("UPDATE policy SET grant_json=? WHERE id=1", (_json(asdict(grant)).decode(),))

    def attest_history(self, reader: Reader, origin: HistoryOrigin) -> None:
        """Only a verified complete host receipt can initialize/restore the lifetime source ledger."""
        _require(isinstance(origin, HistoryOrigin), "history_attestation")
        with self._tx(gated=False) as db:
            self._current(db, reader)
            _require(db.execute("SELECT 1 FROM pending_exposures WHERE generation=? LIMIT 1",
                                (reader.generation,)).fetchone() is None, "history_unknown")
            records = [json.loads(x[0]) for x in db.execute(
                "SELECT record FROM exposures WHERE generation=? ORDER BY ordinal", (reader.generation,))]
            _require(origin.count == len(records) and origin.digest == _digest(records), "history_attestation")
            prior = db.execute("SELECT complete FROM origins WHERE generation=?", (reader.generation,)).fetchone()
            if origin.kind == "observed_session_birth":
                _require(not records and prior is None, "history_attestation")
            db.execute("INSERT INTO origins VALUES (?,?,?,1) ON CONFLICT(generation) DO UPDATE SET "
                       "receipt=excluded.receipt,kind=excluded.kind,complete=1",
                       (reader.generation, origin.receipt_id, origin.kind))

    def mark_history_gap(self, reader: Reader, receipt_id: str) -> None:
        _require(_name(receipt_id), "history_attestation")
        with self._tx(gated=False) as db:
            self._current(db, reader)
            db.execute("INSERT INTO origins VALUES (?,?,?,0) ON CONFLICT(generation) DO UPDATE SET "
                       "receipt=excluded.receipt,kind=excluded.kind,complete=0",
                       (reader.generation, receipt_id, "gap"))

    def record_exposure(self, reader: Reader, exposure: Exposure) -> None:
        """Synthetic convenience. Real adapters must fence BEFORE handoff, then confirm its actual receipt."""
        fence = self.begin_exposure(reader, exposure)
        if fence is not None:
            self.confirm_exposure(reader, fence)

    def begin_exposure(self, reader: Reader, exposure: Exposure) -> str | None:
        """Persist a fence before releasing any payload to the session. Failure means DO NOT expose."""
        record = _json(exposure_record(exposure)).decode()
        with self._tx(gated=False) as db:
            self._current(db, reader)
            prior = db.execute("SELECT record FROM exposures WHERE generation=? AND receipt_id=?",
                               (reader.generation, exposure.receipt_id)).fetchone()
            if prior is not None and prior["record"] == record:
                return None
            pending = db.execute("SELECT COUNT(*) FROM pending_exposures WHERE generation=?", (reader.generation,)).fetchone()[0]
            _require(pending < 64, "pending_full")
            fence = secrets.token_hex(16)
            db.execute("INSERT INTO pending_exposures VALUES (?,?,?,?)",
                       (fence, reader.generation, exposure.receipt_id, record))
        return fence  # until confirmation, another instance/restart must treat the whole history as unknown

    def confirm_exposure(self, reader: Reader, fence: str) -> None:
        """Trusted actual-delivery receipt only. Failure retains the durable fence; never retry the delivery."""
        with self._tx(gated=False) as db:
            self._current(db, reader)
            pending = db.execute("SELECT * FROM pending_exposures WHERE id=? AND generation=?",
                                 (fence, reader.generation)).fetchone()
            _require(pending is not None, "exposure_fence")
            value, record = json.loads(pending["record"]), pending["record"]
            _require(value["drained_at"] <= self._now(), "receipt_time")
            prior = db.execute("SELECT record FROM exposures WHERE generation=? AND receipt_id=?",
                               (reader.generation, pending["receipt_id"])).fetchone()
            if prior is not None:
                _require(prior["record"] == record, "receipt_reuse")
                db.execute("DELETE FROM pending_exposures WHERE id=?", (fence,))
                return
            count = db.execute("SELECT COUNT(*) FROM exposures WHERE generation=?", (reader.generation,)).fetchone()[0]
            _require(count < MAX_EXPOSURES, "ledger_full")
            last = db.execute("SELECT record FROM exposures WHERE generation=? ORDER BY ordinal DESC LIMIT 1",
                              (reader.generation,)).fetchone()
            _require(last is None or json.loads(last["record"])["drained_at"] <= value["drained_at"], "receipt_order")
            withdrawn = db.execute("SELECT 1 FROM withdrawn_receipts WHERE generation=? AND receipt_id=?",
                                   (reader.generation, pending["receipt_id"])).fetchone() is not None
            db.execute("INSERT INTO exposures (generation,receipt_id,record,active) VALUES (?,?,?,?)",
                       (reader.generation, pending["receipt_id"], record, int(not withdrawn)))
            db.execute("DELETE FROM pending_exposures WHERE id=?", (fence,))

    def pending_exposures(self, reader: Reader) -> list[dict]:
        """Host recovery metadata only. A pending entry is not evidence that a session received it."""
        with self._tx(gated=False) as db:
            self._current(db, reader)
            return [dict(x) for x in db.execute(
                "SELECT id,receipt_id,record FROM pending_exposures WHERE generation=? ORDER BY id", (reader.generation,))]

    def withdraw_or_mute(self, reader: Reader, receipt_id: str) -> None:
        """Stop future use; the exposure and its causal taint remain in the ledger."""
        with self._tx(gated=False) as db:
            self._current(db, reader)
            known = db.execute("SELECT 1 FROM exposures WHERE generation=? AND receipt_id=? UNION ALL "
                               "SELECT 1 FROM pending_exposures WHERE generation=? AND receipt_id=? LIMIT 1",
                               (reader.generation, receipt_id, reader.generation, receipt_id)).fetchone()
            _require(known is not None, "receipt_missing")
            db.execute("INSERT OR IGNORE INTO withdrawn_receipts VALUES (?,?)", (reader.generation, receipt_id))
            db.execute("UPDATE exposures SET active=0 WHERE generation=? AND receipt_id=?",
                       (reader.generation, receipt_id))

    def _snapshot(self, db: sqlite3.Connection, reader: Reader, now: int) -> dict:
        origin = db.execute("SELECT receipt,complete FROM origins WHERE generation=?", (reader.generation,)).fetchone()
        _require(origin is not None and origin["complete"] == 1, "history_unknown")
        _require(db.execute("SELECT 1 FROM pending_exposures WHERE generation=? LIMIT 1",
                            (reader.generation,)).fetchone() is None, "history_unknown")
        rows = db.execute("SELECT record,active FROM exposures WHERE generation=? ORDER BY ordinal", (reader.generation,)).fetchall()
        _require(bool(rows), "exposure_missing")
        records = [json.loads(row["record"]) for row in rows]
        # Deliberately conservative candidate rule: every causal source must still be eligible.
        # Owners must settle historical-source use separately; this code never drops stale causal entries.
        _require(all(row["active"] and r["expires_at"] > now for row, r in zip(rows, records)), "source_unavailable")
        return {"history_receipt": origin["receipt"], "count": len(records), "digest": _digest(records), "max_hop": max(r["hop"] for r in records),
                "tail": records[-4:], "source_classes": sorted({r["source_class"] for r in records}),
                "wake_derived": any(r["wake_derived"] is not False for r in records),
                # F1: the narrowest scope any causal source was heard at; None if any is unrecorded.
                "scope": None if any(r.get("scope") is None for r in records)
                         else min((r["scope"] for r in records), key=SCOPES.__getitem__),
                "expires_at": min(r["expires_at"] for r in records)}

    def _policy(self, db: sqlite3.Connection, reader: Reader, intent: dict, payload: bytes, snapshot: dict) -> Grant:
        grant = _stored_grant(json.loads(db.execute("SELECT grant_json FROM policy WHERE id=1").fetchone()[0]))
        _require(grant is not None and callable(self.content_allowed), "authority_missing")
        _require(reader.principal in grant.authors and
                 (intent["publisher"], intent["station"], intent["key_id"], intent["stream"], intent["public_key"])
                 == (grant.publisher, grant.station, grant.key_id, grant.stream, grant.public_key), "publisher_not_allowed")
        _require(intent["cls"] == "chatter" and snapshot["source_classes"] == ["chatter"]
                 and intent["scope"] in ("host", "lan") and SCOPES[intent["scope"]] <= SCOPES[grant.scope], "class_scope")
        # F1: the derived audience may never be wider than the narrowest source the reader was exposed to.
        _require(snapshot["scope"] is not None and SCOPES[intent["scope"]] <= SCOPES[snapshot["scope"]], "source_scope")
        _require(1 + snapshot["max_hop"] <= CLASS_BY_NAME["chatter"].hop_limit, "hop_limit")
        _require(type(payload) is bytes and bool(payload), "content_bounds")
        _require(100 < intent["ttl_ms"] <= grant.max_ttl_ms and len(payload) <= grant.max_bytes, "content_bounds")
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("content_encoding") from None
        _require(self.content_allowed(payload) is True, "content_policy")
        for value in intent["audience"]:
            recipient = Reader(**value)
            _require(recipient.principal in grant.audience_principals, "audience_not_allowed")
            self._current(db, recipient)
        return grant

    def elect(self, reader: Reader, *, author: str, turn_id: str, choice_id: str,
              exposure_receipt: str, payload: bytes, intent: Intent, turn_woken: bool = False) -> str:
        """An explicit fresh-text election. Quiet is represented by not calling this method."""
        _require(author == reader.principal and _name(turn_id) and _name(choice_id)
                 and type(turn_woken) is bool, "election_authority")
        with self._tx() as db:
            now = self._now()  # the database lock may have waited; never cache time before admission
            self._current(db, reader)
            snapshot = self._snapshot(db, reader, now)
            citation = db.execute("SELECT 1 FROM exposures WHERE generation=? AND receipt_id=?",
                                  (reader.generation, exposure_receipt)).fetchone()
            _require(citation is not None, "exposure_missing")
            value = asdict(intent)
            grant = self._policy(db, reader, value, payload, snapshot)
            payload_hash = hashlib.sha256(payload).hexdigest()
            fingerprint = _digest([reader.generation, payload_hash, value])
            prior = db.execute("SELECT id,fingerprint FROM elections WHERE generation=? AND choice_id=?",
                               (reader.generation, choice_id)).fetchone()
            if prior is not None:
                _require(prior["fingerprint"] == fingerprint, "choice_reuse")
                return prior["id"]  # immutable expiry/snapshot; a retry does not elect again
            _require(db.execute("SELECT 1 FROM elections WHERE fingerprint=?", (fingerprint,)).fetchone() is None,
                     "existing_election")  # fresh ID cannot launder an ambiguous prior send
            now = self._now()
            expiry = min(now + intent.ttl_ms, snapshot["expires_at"])
            valid_until = min(now + grant.capability_ms, expiry - 100)
            _require(valid_until > now, "expired")
            election_id = secrets.token_hex(16)
            db.execute("INSERT INTO elections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (election_id, reader.generation, choice_id, fingerprint, _json(asdict(reader)).decode(),
                        turn_id, payload_hash, _json(value).decode(), _json(snapshot).decode(), exposure_receipt,
                        int(turn_woken or snapshot["wake_derived"]), now, valid_until, expiry, "elected", None, None))
            return election_id

    def _check_election(self, db: sqlite3.Connection, row: sqlite3.Row, payload: bytes, now: int) -> tuple[Reader, dict, dict, Grant]:
        self._window(row, now)
        _require(hashlib.sha256(payload).hexdigest() == row["payload_sha256"], "payload_changed")
        reader, intent, frozen = Reader(**json.loads(row["reader"])), json.loads(row["intent"]), json.loads(row["snapshot"])
        self._current(db, reader)
        current = self._snapshot(db, reader, now)
        _require(current == frozen, "ledger_changed")
        grant = self._policy(db, reader, intent, payload, current)
        self._window(row, self._now())  # a content-policy check may take time
        return reader, intent, frozen, grant

    @staticmethod
    def _window(row: sqlite3.Row, now: int) -> None:
        if now >= row["valid_until"] or now >= row["item_expires_at"] - 100:
            raise _ObservedExpiry(row["id"])
        _require(row["issued_at"] <= now, "expired")

    def claim(self, election_id: str, payload: bytes) -> bytes:
        """Durably burn the one-use host claim before returning an authenticated station envelope."""
        _require(self.issuer_key is not None, "issuer_key_missing")  # a verify-only instance cannot mint
        with self._tx() as db:
            now = self._now()
            row = db.execute("SELECT * FROM elections WHERE id=?", (election_id,)).fetchone()
            _require(row is not None and row["state"] == "elected", "not_elected")
            reader, intent, snapshot, grant = self._check_election(db, row, payload, now)
            used = db.execute("SELECT turn_id,claimed_at FROM elections WHERE claimed_at IS NOT NULL AND generation=?",
                              (reader.generation,)).fetchall()
            _require(sum(x["turn_id"] == row["turn_id"] for x in used) < grant.per_turn
                     and sum(x["claimed_at"] > now - 3_600_000 for x in used) < grant.per_hour, "budget")
            envelope = {"v": VERSION, "issuer": self.issuer, "election_id": election_id,
                        "claim_nonce": secrets.token_hex(32), "reader": asdict(reader), "intent": intent,
                        "payload_sha256": row["payload_sha256"], "snapshot": snapshot,
                        "exposure_receipt": row["citation"], "wake_derived": bool(row["wake_derived"]),
                        "issued_at": row["issued_at"], "valid_until": row["valid_until"],
                        "item_expires_at": row["item_expires_at"]}
            encoded = _json(envelope)
            sig = self.issuer_key.sign(DOMAIN + encoded).hex()
            capsule = _json({"envelope": envelope, "sig": sig})
            _require(len(capsule) <= MAX_CAPSULE_BYTES, "capability_size")
            now = self._now()
            self._window(row, now)
            db.execute("UPDATE elections SET state='claimed_unknown',claimed_at=?,envelope=? WHERE id=?",
                       (now, encoded.decode(), election_id))
        return capsule  # a crash/lost result after the commit never permits another claim

    @staticmethod
    def _redemption_budget(db: sqlite3.Connection, row: sqlite3.Row, grant: Grant, now: int) -> None:
        """A claimed reservation remains spent; a tighter current grant can still refuse its effect."""
        used = db.execute("SELECT turn_id,claimed_at FROM elections WHERE claimed_at IS NOT NULL AND generation=?",
                          (row["generation"],)).fetchall()
        _require(sum(x["turn_id"] == row["turn_id"] for x in used) <= grant.per_turn
                 and sum(x["claimed_at"] > now - 3_600_000 for x in used) <= grant.per_hour, "budget")

    def station_admit(self, capsule: bytes, payload: bytes, *, station: str, key_id: str, public_key: str) -> Admission:
        """Authenticate and consume the candidate permission; does not call Station.sing or emit a frame."""
        _require(self.enabled, "disabled")
        _require(type(capsule) is bytes and len(capsule) <= MAX_CAPSULE_BYTES, "capability_format")
        try:
            outer = json.loads(capsule)
            _require(type(outer) is dict and set(outer) == {"envelope", "sig"} and _json(outer) == capsule, "capability_format")
            envelope, sig = outer["envelope"], outer["sig"]
            encoded = _json(envelope)
            _require(type(sig) is str and re.fullmatch(r"[0-9a-f]{128}", sig) is not None, "capability_auth")
            try:
                self._verify_key.verify(bytes.fromhex(sig), DOMAIN + encoded)
            except InvalidSignature:
                raise Refused("capability_auth") from None
            _require(envelope["v"] == VERSION and envelope["issuer"] == self.issuer, "capability_auth")
        except Refused:
            raise
        except (KeyError, TypeError, ValueError, RecursionError):
            raise Refused("capability_format") from None
        with self._tx() as db:
            now = self._now()
            row = db.execute("SELECT * FROM elections WHERE id=?", (envelope["election_id"],)).fetchone()
            _require(row is not None and row["state"] == "claimed_unknown", "claim_consumed")
            _require(row["envelope"] == encoded.decode(), "capability_mismatch")
            _, intent, _, grant = self._check_election(db, row, payload, now)
            self._redemption_budget(db, row, grant, self._now())
            _require((station, key_id, public_key) == (intent["station"], intent["key_id"], intent["public_key"]), "wrong_station")
            self._window(row, self._now())
            db.execute("UPDATE elections SET state='admitted_unknown' WHERE id=?", (row["id"],))
            db.execute("INSERT INTO station_effects VALUES (?,'claimed_unknown',NULL)", (row["id"],))
        return Admission(row["id"], encoded)

    def cancel(self, election_id: str) -> None:
        with self._tx(gated=False) as db:
            row = db.execute("SELECT state FROM elections WHERE id=?", (election_id,)).fetchone()
            _require(row is not None and row["state"] in ("elected", "claimed_unknown"), "not_cancellable")
            db.execute("UPDATE elections SET state='cancelled' WHERE id=?", (election_id,))
            # An admitted permission cannot be cancelled locally as if its effect never happened.

    def record_outcome(self, election_id: str, kind: str, receipt: str) -> None:
        """Trusted adapters supply separately verified receipts; one kind never implies another."""
        _require(kind in ("station_acceptance", "host_reception", "session_exposure", "elected_response")
                 and _name(receipt, 256), "outcome")
        with self._tx(gated=False) as db:
            row = db.execute("SELECT state FROM elections WHERE id=?", (election_id,)).fetchone()
            _require(row is not None and row["state"] == "admitted_unknown", "not_admitted")
            db.execute("INSERT OR IGNORE INTO outcomes VALUES (?,?,?)", (election_id, kind, receipt))

    def inspect(self, election_id: str) -> dict:
        db = self._db()
        try:
            row = db.execute("SELECT id,state,payload_sha256,valid_until,item_expires_at FROM elections WHERE id=?",
                             (election_id,)).fetchone()
            _require(row is not None, "election_missing")
            return {**dict(row), "outcomes": [dict(x) for x in db.execute(
                "SELECT kind,receipt FROM outcomes WHERE election_id=? ORDER BY kind,receipt", (election_id,))]}
        finally:
            db.close()


def proposed_item(admission: Admission, payload: bytes, *, epoch: int, seq: int, now: int) -> wire.Item:
    """Pure wire projection for tests/review. It neither signs, assigns seq nor authorizes a real station."""
    envelope = json.loads(admission.envelope)
    _require(envelope["issued_at"] <= now < envelope["valid_until"] and now < envelope["item_expires_at"] - 100, "expired")
    _require(hashlib.sha256(payload).hexdigest() == envelope["payload_sha256"], "payload_changed")
    snapshot, intent = envelope["snapshot"], envelope["intent"]
    tail = snapshot["tail"]
    def item_tuple(value: list) -> tuple:
        return (bytes.fromhex(value[0]), *(int(x) for x in value[1:]))
    return wire.Item(epoch=epoch, stream=stream_id(intent["stream"]), seq=seq, issued_at=now,
                     expires_at=envelope["item_expires_at"], cls=CLASS_BY_NAME["chatter"].code,
                     ctype=CTYPES["text/plain; charset=utf-8"], body=payload,
                     hop=1 + snapshot["max_hop"], derived_from=tuple(item_tuple(x["item"]) for x in tail),
                     root=item_tuple(tail[0]["root"] or tail[0]["item"]), scope=SCOPES[intent["scope"]],
                     flags=wire.Item.WAKE_DERIVED if envelope["wake_derived"] else 0)
