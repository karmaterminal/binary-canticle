"""Receptor record v1 (RFC-0001 §14.18.3, slice BC-2): the listener's outcomes as records.

``Emitter`` numbers and encodes records: one JSON object per line, non-ASCII escaped,
at most 64 KiB and nesting depth 8 (§14.18.2), each with ``v``, ``type``, ``rec_seq``
(strictly increasing within the run, never reused) and ``run`` (random hex chosen at
process start). It hands each encoded line to a sink; the host daemon (``daemon.py``)
fans the same bytes out to every connection.

``Receptor`` drives a ``Listener`` in receptor mode and maps what it reports onto the
§14.18.3 disposition mapping: ``frame`` for every ITEM or PLUCK verified against a
manifest key (except a benign repeat and an admitted PLUCK), ``retract``,
``landing_state``, ``presence``, ``health`` (fixed counters, the bounded unverified
key-id table of D34), ``hello``, ``fatal`` and ``bye``. It keeps, across restarts,
which tuples it surfaced (so a restart can still retract them) and which keys it
quarantined on equivocation (§10.8).

What is not emitted, and why, is listed in the README ("Record v1").
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from typing import Callable, Optional

from . import wire
from .ids import CLASSES, CTYPES, SCOPES
from .listener import STATE_VERSION, SKEW_MS, Event, Listener

RECORD_V = "canticle-receptor-record/1"
MAX_LINE = 64 * 1024          # bytes per line, newline included (§14.18.2 [PROPOSED DEFAULT])
MAX_DEPTH = 8                 # JSON nesting depth (§14.18.2 [PROPOSED DEFAULT])
RULE_VERSION = "canticle-station/0.1.0+bc2"
RECEPTOR_STATE_VERSION = 1
HEALTH_INTERVAL_MS = 10_000   # §14.18.3 [PROPOSED DEFAULT]
NO_DATAGRAMS_MS = 30_000      # §14.18.3 [PROPOSED DEFAULT]
KEY_TABLE_SIZE = 16           # unverified key ids kept by count (D34)
CLOCK_SKEW_MS = SKEW_MS       # a station offset beyond this marks health `clock_skew`

# Records that a full queue may drop (their rec_seq is then a gap); the rest are never dropped (§14.18.2).
DROPPABLE = frozenset({"frame", "presence", "health"})

# Fixed counter sets: health never grows with what senders choose (§14.18.3, D34).
ADMISSIONS = ("verified", "duplicate", "capability_exceeded", "scope_violation", "hop_limit", "over_quota",
              "pluck_mismatch", "plucked", "superseded", "class_change", "equivocation")
UNVERIFIED = ("unknown_key", "bad_signature", "revoked", "expired", "not_yet_valid", "malformed",
              "crit_unknown", "version")
DISPOSITIONS = ("surface", "ringbuffer_only", "drop", "quarantine_set", "no_op")
RETRACT_REASONS = ("plucked", "superseded", "expired", "revoked", "quarantined", "held_expired",
                   "held_plucked", "held_superseded")
BEACONS = ("verified", "duplicate", "epoch_regression")

# wire.Reject reasons (steps 1-2 of §14.1) -> the §10.9 result they are counted under.
_UNVERIFIED_BY_REJECT = {"unknown-key": "unknown_key", "bad-signature": "bad_signature", "revoked-key": "revoked",
                         "expired": "expired", "not-yet-valid": "not_yet_valid", "crit-unknown": "crit_unknown",
                         "bad-version": "version"}
# Listener evidence for a verified frame (steps 3-4) -> (admission, disposition) of the mapping table.
_REFUSALS = {"capability": ("capability_exceeded", "ringbuffer_only"), "hop-limit": ("hop_limit", "drop"),
             "over-quota": ("over_quota", "drop"), "pluck-mismatch": ("pluck_mismatch", "drop"),
             "plucked": ("plucked", "drop"), "superseded": ("superseded", "drop"),
             "class-change": ("class_change", "drop"), "equivocation": ("equivocation", "quarantine_set")}
_SCOPE_NAMES = {v: k for k, v in SCOPES.items()}
_CTYPE_NAMES = {v: k for k, v in CTYPES.items()}
_SAFE_INT = 2**53 - 1


def _depth(v, d: int = 0) -> int:
    if isinstance(v, dict):
        return max([d + 1] + [_depth(x, d + 1) for x in v.values()])
    if isinstance(v, list):
        return max([d + 1] + [_depth(x, d + 1) for x in v])
    return d


def encode_line(rec: dict) -> bytes:
    """One record as one line (§14.18.2). A record over the limits is a bug here, never sent."""
    line = (json.dumps(rec, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    if len(line) > MAX_LINE or _depth(rec) > MAX_DEPTH:
        raise ValueError(f"{rec.get('type')} record breaks the §14.18.2 framing limits")
    return line


class Emitter:
    """Numbers, encodes and hands out records. ``sink(type, line)`` must not block."""

    def __init__(self, sink: Callable[[str, bytes], None] = lambda t, line: None, run: Optional[str] = None):
        self.run = run or secrets.token_hex(16)
        self.rec_seq = 0
        self.sink = sink

        self._staged: Optional[list] = None

    def emit(self, type_: str, **fields) -> Optional[bytes]:
        """Send a record now, or, inside begin()/commit(), hold it until commit (returns None then)."""
        if self._staged is not None:
            self._staged.append((type_, fields))
            return None
        self.rec_seq += 1
        line = encode_line({"v": RECORD_V, "type": type_, "rec_seq": self.rec_seq, "run": self.run, **fields})
        self.sink(type_, line)
        return line

    # Write-ahead publishing (#79 review): records that a state change implies are held, the state is saved,
    # and only then are they numbered and sent. A discarded batch uses no rec_seq.
    def begin(self) -> None:
        self._staged = []

    def commit(self) -> None:
        staged, self._staged = self._staged or [], None
        for type_, fields in staged:
            self.emit(type_, **fields)

    def discard(self) -> None:
        self._staged = None


class KeyTable:
    """At most ``size`` sender-chosen key ids by count (space-saving, Metwally et al. 2005), plus ``other``.

    A new id takes the slot of the smallest count and inherits it as its ``error``: a listed count
    overestimates by at most ``error``, and any id seen more than total/size times is listed. ``other``
    is what no listed id is known to account for: total - Σ(count - error). Memory is fixed whatever
    the flood (D34)."""

    def __init__(self, size: int = KEY_TABLE_SIZE):
        self.size = size
        self.rows: dict[str, list] = {}  # key id hex -> [count, error]
        self.total = 0

    def add(self, kid_hex: str) -> None:
        self.total += 1
        row = self.rows.get(kid_hex)
        if row is not None:
            row[0] += 1
        elif len(self.rows) < self.size:
            self.rows[kid_hex] = [1, 0]
        else:
            low = min(self.rows, key=lambda k: self.rows[k][0])
            n = self.rows.pop(low)[0]
            self.rows[kid_hex] = [n + 1, n]

    def to_json(self) -> dict:
        rows = sorted(self.rows.items(), key=lambda kv: (-kv[1][0], kv[0]))
        return {"key_ids": [{"key_id": k, "count": c, "error": e} for k, (c, e) in rows],
                "other": self.total - sum(c - e for c, e in self.rows.values())}


def _tuple_json(t: tuple) -> dict:
    kid, epoch, stream, seq = t
    return {"key_id": kid.hex(), "epoch": epoch, "stream_id": stream, "seq": seq if seq <= _SAFE_INT else str(seq)}


def idem(t: tuple) -> str:
    """`canticle:<key_id>:<epoch>:<stream_id>:<seq>` (§14.18.3); stream_id as 8 hex digits, as the
    prototype shows stream ids everywhere else (the RFC leaves the radix open)."""
    kid, epoch, stream, seq = t
    return f"canticle:{kid.hex()}:{epoch}:{stream:08x}:{seq}"


class StateNotDurable(Exception):
    """The safety state could not be saved. The records it implied were not sent; the receptor is unusable
    and its run must end with `fatal` (reason ``state_not_durable``) and a non-zero exit (§14.18.2)."""


class Receptor:
    """The listener's outcomes as record v1 (§14.18.3). Not thread-safe; one event loop drives it."""

    def __init__(self, listener: Listener, emitter: Emitter, *, bind: str, multicast: Optional[str] = None,
                 transport: str = "lan", manifest_sha256: str = "", manifest_label: str = "",
                 now_ms: int = 0, join_snapshot: bool = False):
        if not listener.receptor_mode or listener.tuned is not None:
            raise ValueError("a receptor needs a listener in receptor mode with no tune set (§14.18.1)")
        self.lst, self.em = listener, emitter
        self.bind, self.multicast, self.transport = bind, multicast, transport
        self.manifest_sha256, self.manifest_label = manifest_sha256, manifest_label
        self.started_at = now_ms
        self.join_snapshot = join_snapshot   # hello says so when the transport serves join snapshots (BC-1b)
        self.last_datagram_at: Optional[int] = None
        # identity -> [local_expiry_at, issued_at, state_key, restored]: tuples surfaced and not yet retracted.
        # Each is also a dedup entry of the listener, so the listener's per-key quotas bound it.
        self.surfaced: dict[tuple, list] = {}
        self.restored: set = set()                 # surfaced before this run, not heard since
        self.held_at: dict[tuple, tuple] = {}      # warm-up held identity -> (frame, first hearing, dedup); as listener.held
        self.quarantined: set = set()              # key ids quarantined locally on equivocation (§10.8)
        # Join snapshot state (amendment BC-1b, D36), this run only, never persisted:
        # identity -> fields of the latest deliverable `frame` record this run emitted for a tuple still surfaced
        # (a subset of `surfaced`, so bounded by the same quotas); key id hex -> fields of the station's latest
        # `presence` record (bounded by the manifest).
        self.deliverable: dict[tuple, dict] = {}
        self.presence: dict[str, dict] = {}
        self.landing = {"mute": None, "breaker": "closed", "until": None, "modulation": []}
        self.counters = {"admission": dict.fromkeys(ADMISSIONS, 0), "disposition": dict.fromkeys(DISPOSITIONS, 0),
                         "retract": dict.fromkeys(RETRACT_REASONS, 0), "beacon": dict.fromkeys(BEACONS, 0),
                         "unverified": dict.fromkeys(UNVERIFIED, 0)}
        self.keys = KeyTable()
        self.records_dropped = 0      # set by the transport: records it dropped for some connection
        self.peers_closed = 0         # set by the transport: connections closed for a non-droppable record
        self.snapshots: Optional[dict] = None   # set by a transport that serves join snapshots: its counters
        self._dropped_at_health = 0
        self._dirty = False
        # One state file, one atomic write per datagram: the listener's guards and this receptor's surfaced
        # set and quarantines are saved together (self._save_if_dirty), so a crash cannot persist a PLUCK
        # or a mark without the retract it implies (#79 review). start() reconciles anyway.
        self.failed: Optional[str] = None   # set when a save failed: nothing more is heard or sent
        listener.autosave = False
        listener.extra_state = self._state_json
        if listener.loaded_extra is not None:
            self._load(listener.loaded_extra)

    # ------------------------------------------------------------ lifecycle

    def _batch(self, fn) -> None:
        """Run ``fn``, save the state it changed, then publish the records it emitted (write-ahead). If the
        save fails, nothing from ``fn`` is published and StateNotDurable is raised. Any other exception also
        publishes nothing and propagates: the caller ends the run (fail closed)."""
        if self.failed is not None:
            raise StateNotDurable(self.failed)
        self.em.begin()
        try:
            fn()
            self._save_if_dirty()
        except OSError as e:
            self.em.discard()
            self.failed = f"{type(e).__name__}: {e}"
            raise StateNotDurable(self.failed) from e
        except BaseException:
            self.em.discard()
            self.failed = "internal"
            raise
        self.em.commit()

    def start(self, now_ms: int) -> None:
        """`hello`, then the retracts the persisted state owes (reconcile), then the first `landing_state`
        (§14.18.3), published only once that state is saved. The host daemon serves no connection before
        this returns."""
        self._batch(lambda: self._start(now_ms))

    def _start(self, now_ms: int) -> None:
        extra = {"join_snapshot": True} if self.join_snapshot else {}
        self.em.emit("hello", wire_version=wire.VERSION, record_version=RECORD_V, pid=os.getpid(), bind=self.bind,
                     multicast=self.multicast, transport=self.transport, manifest_sha256=self.manifest_sha256,
                     manifest_label=self.manifest_label, state_version=STATE_VERSION,
                     receptor_state_version=RECEPTOR_STATE_VERSION, rule_version=RULE_VERSION, **extra)
        self._reconcile(now_ms)
        self.em.emit("landing_state", **self.landing)

    def reconcile(self, now_ms: int) -> int:
        n = [0]
        self._batch(lambda: n.__setitem__(0, self._reconcile(now_ms)))
        return n[0]

    def _reconcile(self, now_ms: int) -> int:
        """Retract every surfaced tuple that the persisted guards say is withdrawn: its key revoked or gone
        from the manifest, its key quarantined, a sticky PLUCK on it, a supersession mark newer than it, or
        its local expiry passed. Idempotent: a retracted tuple leaves the surfaced set, so a second call
        emits nothing. Returns the number of retracts."""
        n = 0
        for ident in list(self.surfaced):
            expiry, issued_at, state_key = self.surfaced[ident][:3]
            kid, by = ident[0], None
            entry = self.lst.manifest.entry(kid)
            mark = self.lst.hwm.get((kid, ident[2], state_key)) if state_key is not None else None
            if entry is None or entry.revoked:
                reason = "revoked"
            elif kid in self.quarantined:
                reason = "quarantined"
            elif ident in self.lst.sticky_pluck:
                reason = "plucked"
            elif mark is not None and (issued_at, ident[1], ident[3]) < mark[:3]:
                reason, by = "superseded", (kid, mark[1], ident[2], mark[2])
            elif expiry <= now_ms:
                reason = "expired"
            else:
                continue
            self._retract(ident, reason, by=by)
            n += 1
        return n

    def set_landing(self, **changes) -> bool:
        """Change the landing state and emit it if any part changed. This prototype has no MUTE, circuit
        breaker or regulatory modulation (§10.6, §14.7, §14.8.3), so nothing calls this but tests."""
        new = {**self.landing, **changes}
        if new == self.landing:
            return False
        self.landing = new
        self.em.emit("landing_state", **self.landing)
        return True

    def fatal(self, reason: str, detail: str = "") -> bytes:
        return self.em.emit("fatal", reason=reason, detail=detail[:200])

    def bye(self) -> bytes:
        """Save, then `bye`. A failed save raises StateNotDurable: the run then ends with `fatal`."""
        if self.failed is not None:
            raise StateNotDurable(self.failed)
        try:
            self._save_if_dirty()
        except OSError as e:
            self.failed = f"{type(e).__name__}: {e}"
            raise StateNotDurable(self.failed) from e
        return self.em.emit("bye")

    # ------------------------------------------------------------ hearing

    def hear(self, datagram: bytes, now_ms: int) -> None:
        self._batch(lambda: self._hear(datagram, now_ms))

    def _hear(self, datagram: bytes, now_ms: int) -> None:
        self.last_datagram_at = now_ms
        try:
            events = self.lst.hear(datagram, now_ms)
        except Exception as e:  # the receive path survives any datagram (bug B1 class)
            events = [Event("evidence", "?", "", data={"reason": "internal", "detail": type(e).__name__})]
            self.lst.last_frame = None
        f, dedup = self.lst.last_frame, self.lst.last_dedup
        if f is None:
            self._unverified(datagram, events[0].data.get("reason", "internal") if events else "internal")
        elif f.kind == wire.KIND_BEACON:
            regress = any(ev.kind == "evidence" and ev.data.get("reason") == "epoch-regression" for ev in events)
            self.counters["beacon"]["epoch_regression" if regress else dedup if dedup == "duplicate" else "verified"] += 1
            self._presence_events(events)
        else:
            self._item_or_pluck(f, dedup, events, now_ms)

    def _unverified(self, datagram: bytes, reason: str) -> None:
        """Steps 1-2 of §14.1 failed: counters only, never a record, never attributed (D34)."""
        self.counters["unverified"][_UNVERIFIED_BY_REJECT.get(reason, "malformed")] += 1
        if len(datagram) >= wire.HEADER_LEN and datagram[0:2] == wire.MAGIC:
            self.keys.add(bytes(datagram[4:12]).hex())

    def _item_or_pluck(self, f: wire.Frame, dedup: str, events: list, now_ms: int) -> None:
        ident, body = f.identity, f.body
        refused = pluck_retracted = False
        held = None
        for ev in events:
            if ev.kind == "evidence":
                refused = True
                reason = ev.data.get("reason")
                if reason == "unknown-class":   # verified, ringbuffer_only (§6.2)
                    refused = False
                    self._frame(f, now_ms, "verified", "ringbuffer_only", ["unknown_class"], dedup)
                elif reason == "scope-violation":
                    # Narrower than the binding it arrived on (§4.3) is scope_violation; beyond the key's grant
                    # is capability_exceeded (§10.4). The listener names both `scope-violation`.
                    narrower = body.scope < SCOPES[self.lst.binding]
                    self._frame(f, now_ms, "scope_violation" if narrower else "capability_exceeded",
                                "drop" if narrower else "ringbuffer_only",
                                ["scope_narrower_than_binding" if narrower else "scope_not_granted"], dedup)
                elif reason in _REFUSALS:
                    adm, disp = _REFUSALS[reason]
                    self._frame(f, now_ms, adm, disp, [reason.replace("-", "_")], dedup)
                    if reason == "equivocation":
                        self._quarantine(f.key_id)
            elif ev.kind == "item":
                self._surface_item(f, ev.ident, now_ms, dedup)
            elif ev.kind == "held":
                held = ev.data["reason"]
                if held == "warmup_hold":
                    self.held_at[ev.ident] = (f, self.held_at.get(ev.ident, (f, now_ms))[1], dedup)
                self._frame(f, now_ms, "verified", "ringbuffer_only", [held], dedup)
            elif ev.kind == "held_retract":
                pluck_retracted |= f.kind == wire.KIND_PLUCK
                self._held_retract(ev)
            elif ev.kind in ("superseded", "expired") and ev.ident in self.surfaced:
                self._retract(ev.ident, ev.kind, by=ident if ev.kind == "superseded" else None)
            elif ev.kind == "presence":
                self._presence_events([ev])
        if refused:
            return
        if f.kind == wire.KIND_PLUCK and held is None:
            target = (f.key_id, body.epoch, body.stream, body.target_seq)
            if dedup == "first":
                if not pluck_retracted:
                    self._retract(target, "plucked", by=ident, force=True)
            elif dedup == "resurfaced" and target in self.surfaced:
                self._retract(target, "plucked", by=ident)     # surfaced before the restart (§14.18.3, New)
            else:
                self._count("duplicate", "no_op")
            return
        if dedup == "duplicate" and held is None:
            self._count("duplicate", "no_op")
            return
        if f.kind == wire.KIND_ITEM and body.state_key is not None and held != "epoch_regression":
            self._supersede_restored(f, ident)

    def _surface_item(self, f: wire.Frame, ident: tuple, now_ms: int, dedup: str, heard_at: Optional[int] = None) -> None:
        if ident[0] in self.quarantined:
            self._frame(f, now_ms, "verified", "ringbuffer_only", ["key_quarantined"], dedup, heard_at)
            return
        rec = self._frame(f, now_ms, "verified", "surface", [], dedup, heard_at)
        self.surfaced[ident] = [rec["times"]["local_expiry_at"], f.body.issued_at, f.body.state_key, False]
        self.deliverable[ident] = rec
        self.restored.discard(ident)
        self._dirty = True

    def _supersede_restored(self, f: wire.Frame, ident: tuple) -> None:
        """A keyed item supersedes a value surfaced before the restart, which the listener no longer holds
        as current: retract it (§14.18.3, New). Same key, stream and state_key, older order."""
        it = f.body
        order = (it.issued_at, it.epoch, it.seq)
        for old in [r for r in self.restored if r != ident and r[0] == f.key_id and r[2] == it.stream]:
            row = self.surfaced[old]
            if row[2] == it.state_key and (row[1], old[1], old[3]) < order:
                self._retract(old, "superseded", by=ident)

    def _held_retract(self, ev: Event) -> None:
        self.held_at.pop(ev.ident, None)
        reason, by = ev.data["reason"], ev.data.get("by")
        self.counters["retract"][reason] += 1
        self.em.emit("retract", target=_tuple_json(ev.ident), idem=idem(ev.ident), reason=reason,
                     by=_tuple_json(by) if by else None)

    def _retract(self, target: tuple, reason: str, by: Optional[tuple] = None, force: bool = False) -> None:
        """One `retract`. Supersession, expiry, revocation and quarantine retract only surfaced tuples;
        a valid PLUCK always does (``force``)."""
        self.deliverable.pop(target, None)
        if self.surfaced.pop(target, None) is None and not force:
            return
        self.restored.discard(target)
        self._dirty = True
        self.counters["retract"][reason] += 1
        self.em.emit("retract", target=_tuple_json(target), idem=idem(target), reason=reason,
                     by=_tuple_json(by) if by else None)

    def _quarantine(self, kid: bytes) -> None:
        """Equivocation: quarantine the key locally (§10.8) and retract what it surfaced. No rescind here."""
        if kid not in self.quarantined:
            self.quarantined.add(kid)
            self._dirty = True
        for ident in [i for i in self.surfaced if i[0] == kid]:
            self._retract(ident, "quarantined")

    def _count(self, admission: str, disposition: str) -> None:
        self.counters["admission"][admission] += 1
        self.counters["disposition"][disposition] += 1

    def _frame(self, f: wire.Frame, now_ms: int, admission: str, disposition: str, reasons: list, dedup: str,
               heard_at: Optional[int] = None) -> dict:
        """Emit one `frame` record (§14.18.3 table); returns its fields (without v, type, rec_seq, run)."""
        self._count(admission, disposition)
        kid, b = f.key_id, f.body
        ident = f.identity
        entry = self.lst.manifest.entry(kid)
        st = self.lst.stations.get(kid)
        offset = st.offset_ms if st else 0
        heard = heard_at if heard_at is not None else now_ms
        local_expiry = wire.local_expiry_ms(b, offset, first_heard_ms=heard)
        item = f.kind == wire.KIND_ITEM
        rec = {
            # Only a verified frame reaches the hearer ring (§14.1 step 5); one refused at steps 3-4 has no
            # ring copy, so no receipt pointer: null (#79 review). This spike keeps no ring; for a verified
            # frame these are the hash and size its ring copy would have (the dedup digest).
            "frame": {**_tuple_json(ident), "kind": "item" if item else "pluck",
                      "sha256": hashlib.sha256(f.raw).hexdigest() if admission == "verified" else None,
                      "bytes": len(f.raw) if admission == "verified" else None},
            "idem": idem(ident),
            "station": {"name": entry.name, "principal": None},
            "stream": self.lst._stream_name(kid, b.stream),
            "class": CLASSES[b.cls].name if item and b.cls in CLASSES else None,
            "scope": _SCOPE_NAMES.get(b.scope, b.scope),
            "hop": b.hop if item else None,
            "state_key": b.state_key if item else None,
            "purpose": b.purpose if item else None,
            "intensity": b.intensity if item else None,
            "lens": b.lens if item else None,
            "flags": {"refresh": bool(item and b.flags & wire.Item.REFRESH),
                      "wake_derived": bool(item and b.flags & wire.Item.WAKE_DERIVED),
                      "exercise": bool(item and b.flags & wire.Item.EXERCISE)},
            "lineage": {"derived_from": [_tuple_json(t) for t in b.derived_from] if item else [],
                        "root": _tuple_json(b.root) if item and b.root else None},
            "times": {"issued_at": b.issued_at, "expires_at": b.expires_at, "received_at": now_ms, "heard_at": heard,
                      "offset_ms": offset, "local_expiry_at": local_expiry,
                      "age_ms": max(0, now_ms - b.issued_at - offset)},
            "gap": "unavailable",
            "admission": admission,
            "dedup": "resurfaced" if dedup == "resurfaced" else "first",
            "disposition": disposition,
            "reasons": reasons,
            "versions": {"manifest_sha256": self.manifest_sha256, "manifest_label": self.manifest_label,
                         "rule_version": RULE_VERSION, "state_version": STATE_VERSION},
        }
        if item and admission == "verified" and disposition in ("surface", "ringbuffer_only"):
            if b.body is not None:
                body = {"ctype": _CTYPE_NAMES.get(b.ctype, b.ctype), "size": len(b.body),
                        "sha256": hashlib.sha256(b.body).hexdigest()}
                if b.ctype == CTYPES["text/plain; charset=utf-8"]:
                    body["text"] = b.body.decode("utf-8", "replace")
                else:
                    body["base64"] = base64.b64encode(b.body).decode("ascii")
                rec["body"] = body
            if b.body_ref is not None:
                rec["body_ref"] = {"url": b.body_ref[0], "sha256": b.body_ref[1].hex(), "size": b.body_ref[2]}
        self.em.emit("frame", **rec)
        return rec

    def _presence_events(self, events: list) -> None:
        for ev in events:
            if ev.kind == "presence":
                rec = {"station": {"name": ev.station, "principal": None}, "key_id": ev.key_id,
                       "state": ev.data["state"], "last_beacon_at": ev.data.get("last_beacon_ms")}
                self.presence[ev.key_id] = rec
                self.em.emit("presence", **rec)

    # ------------------------------------------------------------ time

    def tick(self, now_ms: int) -> None:
        self._batch(lambda: self._tick(now_ms))

    def _tick(self, now_ms: int) -> None:
        for ev in self.lst.tick(now_ms):
            if ev.kind == "expired" and ev.ident in self.surfaced:
                self._retract(ev.ident, "expired")
            elif ev.kind == "held_retract":
                self._held_retract(ev)
            elif ev.kind == "item":    # released after warm-up: a second `frame` with the same idem
                held = self.held_at.pop(ev.ident, None)
                if held is not None:
                    self._surface_item(held[0], ev.ident, now_ms, held[2], held[1])
            elif ev.kind == "presence":
                self._presence_events([ev])
        self._expire_restored(now_ms)

    def _expire_restored(self, now_ms: int) -> None:
        for ident in [i for i in self.restored if self.surfaced[i][0] <= now_ms]:
            self._retract(ident, "expired")

    def health(self, now_ms: int) -> bytes:
        if self.failed is not None:
            raise StateNotDurable(self.failed)
        reasons = []
        since = self.last_datagram_at if self.last_datagram_at is not None else self.started_at
        if now_ms - since >= NO_DATAGRAMS_MS:
            reasons.append("no_datagrams")
        if self.records_dropped > self._dropped_at_health:
            reasons.append("records_lost")
        self._dropped_at_health = self.records_dropped
        ages = {}
        for e in self.lst.manifest:
            st = self.lst.stations.get(e.key_id)
            if st is not None and st.last_beacon is not None:
                ages[e.key_id.hex()] = now_ms - st.last_beacon
                if abs(st.offset_ms) > CLOCK_SKEW_MS and "clock_skew" not in reasons:
                    reasons.append("clock_skew")
        return self.em.emit(
            "health", state="degraded" if reasons else "ok", reasons=reasons, last_datagram_at=self.last_datagram_at,
            counters=self.counters, unverified=self.keys.to_json(),
            dedup={"entries": len(self.lst.dedup), "capacity": self.lst.dedup_capacity},
            beacon_age_ms=ages, surfaced=len(self.surfaced), quarantined=sorted(k.hex() for k in self.quarantined),
            records={"emitted": self.em.rec_seq, "dropped": self.records_dropped, "peers_closed": self.peers_closed},
            **({"snapshots": dict(self.snapshots)} if self.snapshots is not None else {}))

    # ------------------------------------------------------------ join snapshot (amendment BC-1b, D36)

    def snapshot_entries(self, now_ms: int) -> list:
        """The run's current state as join-snapshot entries, in truncation order (§14.18.3, *Join snapshot*):
        one `presence` entry per station with a current presence state (by key id), then one `frame` entry per
        tuple this run emitted a deliverable `frame` record for and has not retracted, whose local_expiry_at has
        not passed; alarm class first, then newest heard_at first (idem breaks ties). Each frame entry is that
        record's fields, `dedup` as emitted. Held and other non-deliverable items are never here. Synchronous:
        the caller takes the watermark in the same event-loop step."""
        if self.em._staged is not None:
            raise RuntimeError("snapshot taken inside a record batch")
        out = [{"presence": self.presence[k]} for k in sorted(self.presence)]
        live = [r for r in self.deliverable.values() if r["times"]["local_expiry_at"] > now_ms]
        live.sort(key=lambda r: (r["class"] != "alarm", -r["times"]["heard_at"], r["idem"]))
        return out + [{"frame": r} for r in live]

    # ------------------------------------------------------------ persisted receptor state

    def _save_if_dirty(self) -> None:
        """One atomic write of the listener's and this receptor's state, after this datagram's records."""
        if self._dirty or self.lst._dirty:
            self.lst._save_if_dirty(force=True)
        self._dirty = False

    def _state_json(self) -> dict:
        return {"version": RECEPTOR_STATE_VERSION,
                "surfaced": [[i[0].hex(), i[1], i[2], i[3], r[0], r[1], r[2]] for i, r in self.surfaced.items()],
                "quarantined": sorted(k.hex() for k in self.quarantined)}

    def _load(self, state: dict) -> None:
        if state.get("version") != RECEPTOR_STATE_VERSION:
            raise ValueError(f"receptor state: unsupported version {state.get('version')!r}")
        for kid_hex, epoch, stream, seq, expiry, issued_at, state_key in state["surfaced"]:
            ident = (bytes.fromhex(kid_hex), epoch, stream, seq)
            self.surfaced[ident] = [expiry, issued_at, state_key, True]
            self.restored.add(ident)
        self.quarantined = {bytes.fromhex(k) for k in state["quarantined"]}

