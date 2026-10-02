"""A listener: verify, dedup, pluck, supersede and track presence (RFC-0001 §7.4-§7.8, §8).

This is a receptor-lite for the spike. It surfaces events (a new item, a
withdrawal, a presence change, evidence) and never actuates anything.
Landing into agent sessions (§14) is out of scope here.

With ``state_path`` set, the safety state that must survive a restart (epoch
maxima, dedup digests, sticky PLUCKs, supersession high-water marks; §5.2, §7.4,
§7.7, §7.8) is written atomically after every change and loaded at start.

``receptor_mode=True`` is the BC-2 behaviour the record v1 emitter needs
(``records.py``, RFC §14.18.3): it reports the outcomes this listener is otherwise
silent on (``held`` events for `unnamed_stream`, `warmup_hold` and a lower epoch's
new tuple, which it admits as `ringbuffer_only` instead of dropping; ``held_retract``
events when a held item is dropped before release). ``last_frame`` and
``last_dedup`` describe the most recent datagram. Without it, events are as before.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import os
import tempfile
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from . import cbor, wire
from .ids import CLASS_BY_NAME, CLASSES, CTYPES, SCOPES
from .manifest import Manifest

SKEW_MS = 5_000
OFFSET_SAMPLES = 16
SCOPE_NAMES = {v: k for k, v in SCOPES.items()}
LIVE_STATE = CLASS_BY_NAME["live-state"].code
STATE_VERSION = 3  # 2: dedup rows carry (expires_at, scope) for the §9.7 PLUCK check (#60); 3: marks carry their class (§23.2 q21)


@dataclass
class Event:
    kind: str       # item | withdrawn | superseded | expired | presence | evidence
    station: str
    key_id: str
    stream: Optional[str] = None
    seq: Optional[int] = None
    data: dict = field(default_factory=dict)
    # The identity tuple the event is about (not printed): the record emitter needs it (§14.18.3).
    ident: Optional[tuple] = field(default=None, compare=False)

    def to_json(self) -> dict:
        out = {"event": self.kind, "station": self.station, "key_id": self.key_id}
        if self.stream is not None:
            out["stream"] = self.stream
        if self.seq is not None:
            out["seq"] = self.seq
        out.update(self.data)
        return out


@dataclass
class _Heard:
    item: wire.Item
    tuple: tuple
    local_expiry: int
    first_heard: int
    last_heard: int
    copies: int = 1


@dataclass
class _StationState:
    epoch_hwm: int = 0
    epoch_seen_at: int = 0
    bseq: int = 0
    last_beacon: Optional[int] = None
    period_ms: int = 0
    signed_off: bool = False
    offsets: deque = field(default_factory=lambda: deque(maxlen=OFFSET_SAMPLES))
    stream_loops: dict = field(default_factory=dict)  # stream_id -> advertised loop_ms
    last_stream_item: dict = field(default_factory=dict)  # stream_id -> last admitted copy, oldest first (#60)
    presence: str = ""  # nothing reported yet
    first_beacon_at: Optional[int] = None  # first beacon heard since this listener started (warm-up, §7.8)
    stream_loop_max: dict = field(default_factory=dict)  # stream_id -> advertised loop_max_ms
    stream_entries: dict = field(default_factory=dict)  # stream_id -> latest beacon StreamEntry (heads, live)
    # page index -> (bseq heard at, that page's stream entries). The three stream maps above are rebuilt
    # from these, so they hold one advertised catalog (at most 8 pages, §8.4), not every stream id ever
    # beaconed (#60). A stream on two held pages takes its entry from the more recent beacon.
    catalog_pages: dict = field(default_factory=dict)

    @property
    def offset_ms(self) -> int:
        return min(self.offsets) if self.offsets else 0


def atomic_write_json(path, obj) -> None:
    """Write ``obj`` as JSON beside ``path``, fsync it, rename it into place and fsync the directory."""
    path = os.fspath(path)
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    dfd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


class _Expiries:
    """Min-heap of (time, key) over one table whose entries expire (#60 review). Purging pops only what
    is due, rather than scanning the table, so a key held at its limit cannot make every refusal or
    tick cost a full scan. Deletion is lazy: the table is the truth, and a popped entry whose table
    row has gone or moved later is skipped."""

    def __init__(self):
        self.heap: list = []

    def push(self, t: int, key) -> None:
        heapq.heappush(self.heap, (t, key))

    def due(self, now_ms: int):
        while self.heap and self.heap[0][0] <= now_ms:
            yield heapq.heappop(self.heap)

    def compact(self, live: int, rows) -> None:
        """Rebuild from the live (time, key) rows (a callable) once stale entries outnumber them."""
        if len(self.heap) > 2 * live + 1024:
            self.heap = list(rows())
            heapq.heapify(self.heap)


class Listener:
    def __init__(self, manifest: Manifest, tuned: Optional[set] = None, dedup_capacity: int = 100_000,
                 binding: str = "lan", state_path=None, warmup: bool = True, ephemeral: bool = False,
                 per_key_quota: Optional[int] = None, per_key_mark_quota: Optional[int] = None,
                 receptor_mode: bool = False):
        # Restart safety is the default: without state_path a restarted listener could surface a
        # stale or withdrawn item (§7.4-§7.8). Tests and experiments must opt out explicitly.
        if state_path is None and not ephemeral:
            raise ValueError("a listener needs state_path for restart safety (§7.4-§7.8), "
                             "or ephemeral=True where restarts are not under test")
        self.manifest = manifest
        # binding: where frames reach this listener. A frame whose scope is narrower than the
        # binding (a `host` frame heard over UDP) is a scope violation (§4.3, §10.9).
        if binding not in SCOPES:
            raise ValueError(f"unknown binding {binding!r}")
        self.binding = binding
        self.state_path = state_path
        self.warmup = warmup  # hold live-state keys until warm-up completes (§7.8 rule 4)
        self._dirty = False
        self._restored: set = set()   # identities loaded from state, not yet re-surfaced here
        self.held: dict[tuple, tuple] = {}  # (kid, stream, state_key) -> (ident, item, retain) during warm-up
        self.tuned = tuned                    # stream names to surface; None = every named stream
        self.dedup_capacity = dedup_capacity
        self.per_key_quota = per_key_quota    # fixed per-key share; None = an equal share of dedup_capacity
        self.per_key_mark_quota = per_key_mark_quota  # fixed per-key mark limit; None = derived (_mark_quota)
        self.dedup: dict[tuple, tuple] = {}   # identity -> (sha256(frame), retain_until, (expires_at, scope) | None)
        self.dedup_per_key: dict[bytes, int] = {}
        self.sticky_pluck: dict[tuple, int] = {}
        self.hwm: dict[tuple, tuple] = {}     # (kid, stream, state_key) -> (issued_at, epoch, seq, retain_until, class)
        self.hwm_per_key: dict[bytes, int] = {}
        self._dedup_due, self._sticky_due, self._hwm_due = _Expiries(), _Expiries(), _Expiries()
        self.current: dict[tuple, _Heard] = {}  # identity -> heard item (on air, from this listener's view)
        self.stations: dict[bytes, _StationState] = {}
        self.evidence_counts: dict[str, int] = {}
        self.receptor_mode = receptor_mode
        # The last datagram's parsed frame (None when wire.parse rejected it) and its dedup outcome:
        # "first", "duplicate" (a benign repeat, or an older/repeated beacon) or "resurfaced" (§14.18.3).
        self.last_frame: Optional[wire.Frame] = None
        self.last_dedup: Optional[str] = None
        if state_path is not None and os.path.exists(state_path):
            self._load(state_path)

    # ------------------------------------------------------------ helpers

    def _name(self, kid: bytes) -> str:
        e = self.manifest.entry(kid)
        return e.name if e else kid.hex()

    def _stream_name(self, kid: bytes, sid: int) -> Optional[str]:
        e = self.manifest.entry(kid)
        return e.stream_names.get(sid) if e else None

    def _evidence(self, kind: str, kid: bytes, detail: str = "", **data) -> Event:
        self.evidence_counts[kind] = self.evidence_counts.get(kind, 0) + 1
        return Event("evidence", self._name(kid) if kid else "?", kid.hex() if kid else "",
                     data={"reason": kind, "detail": detail, **data})

    def _st(self, kid: bytes) -> _StationState:
        return self.stations.setdefault(kid, _StationState())

    # ------------------------------------------------------------ hearing

    def hear(self, datagram: bytes, now_ms: int) -> list[Event]:
        kid = bytes(datagram[4:12]) if len(datagram) >= 12 else b""
        st = self.stations.get(kid)
        self.last_frame, self.last_dedup = None, None
        try:
            f = wire.parse(datagram, self.manifest.resolve, now_ms, st.offset_ms if st else 0)
        except wire.Reject as r:
            known = kid and self.manifest.entry(kid) is not None
            return [self._evidence(r.reason, kid if known else b"", r.detail)]
        self.last_frame, self.last_dedup = f, "first"
        events = self._beacon(f, now_ms) if f.kind == wire.KIND_BEACON else self._item_or_pluck(f, now_ms)
        self._save_if_dirty()
        return events

    def _epoch_ok(self, kid: bytes, epoch: int, now_ms: int, events: list, advance: bool = True) -> bool:
        st = self._st(kid)
        if epoch < st.epoch_hwm:
            events.append(self._evidence("epoch-regression", kid, f"{epoch} < {st.epoch_hwm}"))
            return False
        if advance and epoch > st.epoch_hwm:
            st.epoch_hwm, st.epoch_seen_at = epoch, now_ms
            self._dirty = True
            # bseq, the advertised catalog and the per-stream hearing times belong to the previous
            # epoch (§9.8): a restarted station counts beacons from 1 again and may loop different streams.
            st.bseq = 0
            st.catalog_pages.clear()
            st.stream_loops.clear()
            st.stream_loop_max.clear()
            st.stream_entries.clear()
            st.last_stream_item.clear()
        return True

    def _beacon(self, f: wire.Frame, now_ms: int) -> list[Event]:
        b: wire.Beacon = f.body
        events: list[Event] = []
        if not self._epoch_ok(f.key_id, b.epoch, now_ms, events):
            return events
        st = self._st(f.key_id)
        if b.epoch == st.epoch_hwm and b.bseq <= st.bseq and st.last_beacon is not None:
            self.last_dedup = "duplicate"
            return events  # older or repeated beacon
        st.bseq = b.bseq
        st.offsets.append(now_ms - b.wallclock)
        st.last_beacon = now_ms
        st.signed_off = b.next_beacon_ms == 0
        st.period_ms = b.next_beacon_ms or st.period_ms
        if st.first_beacon_at is None:
            st.first_beacon_at = now_ms
        # A beacon carries one page of the station's catalog (§8.4): it replaces that page and drops
        # pages past the advertised count. Rebuilding the stream maps from the pages bounds them by
        # what one catalog can advertise, however many beacons (or stream ids) a key sends (#60).
        index, count = b.page or (0, 1)
        for p in [p for p in st.catalog_pages if p >= count]:
            del st.catalog_pages[p]
        st.catalog_pages[index] = (b.bseq, b.streams)
        st.stream_loops.clear()
        st.stream_loop_max.clear()
        st.stream_entries.clear()
        # bseq order, so the newest copy wins: §8.4 lets a changed stream ride the next beacon, whatever
        # its page. bseq only rises within an epoch, and an epoch advance clears the pages.
        for _, entries in sorted(st.catalog_pages.values(), key=lambda v: v[0]):
            for e in entries:
                st.stream_loops[e.stream_id] = e.loop_ms
                st.stream_loop_max[e.stream_id] = e.loop_max_ms
                st.stream_entries[e.stream_id] = e
        events.extend(self._presence(f.key_id, now_ms))
        return events

    def _item_or_pluck(self, f: wire.Frame, now_ms: int) -> list[Event]:
        events: list[Event] = []
        body = f.body
        kid = f.key_id
        # Authorise before touching any state: a rejected frame must leave epoch, dedup,
        # presence, sticky-pluck and high-water marks exactly as they were (§10.9).
        entry = self.manifest.entry(kid)
        sname = self._stream_name(kid, body.stream)
        if f.kind == wire.KIND_ITEM and body.cls not in entry.classes:
            events.append(self._evidence("capability", kid, f"class {body.cls} not granted", stream=sname, seq=body.seq))
            return events
        if body.scope < SCOPES[self.binding]:
            events.append(self._evidence("scope-violation", kid, f"{SCOPE_NAMES.get(body.scope, body.scope)} frame "
                                         f"heard on a {self.binding} binding", stream=sname, seq=body.seq))
            return events
        if body.scope not in entry.scopes:
            events.append(self._evidence("scope-violation", kid, f"scope {SCOPE_NAMES.get(body.scope, body.scope)} "
                                         "not granted", stream=sname, seq=body.seq))
            return events
        if f.kind == wire.KIND_ITEM and body.cls in CLASSES and body.hop > CLASSES[body.cls].hop_limit:
            events.append(self._evidence("hop-limit", kid, f"hop {body.hop} > {CLASSES[body.cls].hop_limit} for "
                                         f"{CLASSES[body.cls].name}", stream=sname, seq=body.seq))
            return events
        # Regression is checked now; a higher epoch is adopted only once the frame is admitted, so an
        # over-quota or mismatched frame cannot advance it (§10.9: refusals are state-neutral).
        if self.receptor_mode and body.epoch < self._st(kid).epoch_hwm:
            return self._lower_epoch(f, now_ms)
        if not self._epoch_ok(kid, body.epoch, now_ms, events, advance=False):
            return events
        ident = f.identity
        digest = hashlib.sha256(f.raw).digest()
        seen = self.dedup.get(ident)
        st = self._st(kid)
        resurface = False
        if seen is not None:
            if seen[0] != digest:
                events.append(self._evidence("equivocation", kid, f"two frames for {ident[1:]}",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            if ident in self.current:
                h = self.current[ident]
                h.copies += 1
                h.last_heard = now_ms
            if ident not in self._restored:
                self._heard_on(st, body.stream, now_ms)
                self.last_dedup = "duplicate"
                return events  # a repeat is a benign no-op (§7.4)
            # Accepted before a restart: its dedup, pluck and supersession state was kept, but this
            # process has not surfaced it yet. Surface it once, through the same checks.
            if self._needs_hwm_slot(f, ident) and not self._hwm_room(kid, now_ms):
                events.append(self._evidence("over-quota", kid, "per-key supersession mark limit full; live "
                                             "marks kept", stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            self._heard_on(st, body.stream, now_ms)
            self._restored.discard(ident)
            self.last_dedup = "resurfaced"
            resurface = True
            retain = seen[1]
        else:
            target = None
            if f.kind == wire.KIND_PLUCK:
                # §9.7: a PLUCK carries its target's expires_at and scope. Checkable while the target's
                # dedup entry is held; a PLUCK for a target never heard is still recorded (§7.7).
                target = self.dedup.get((kid, body.epoch, body.stream, body.target_seq))
                if target is not None and target[2] is not None and target[2] != (body.expires_at, body.scope):
                    events.append(self._evidence("pluck-mismatch", kid, "expires_at or scope differs from the "
                                                 "target's (§9.7)", stream=self._stream_name(kid, body.stream),
                                                 seq=body.seq))
                    return events
            if not self._room_for(kid, now_ms):
                events.append(self._evidence("over-quota", kid, "per-key dedup quota full; live entries kept",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            if self._needs_hwm_slot(f, ident) and not self._hwm_room(kid, now_ms):
                events.append(self._evidence("over-quota", kid, "per-key supersession mark limit full; live "
                                             "marks kept", stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            self._epoch_ok(kid, body.epoch, now_ms, events)
            retain = wire.local_expiry_ms(body, st.offset_ms, first_heard_ms=now_ms) + SKEW_MS
            self._remember(ident, digest, retain,
                           (body.expires_at, body.scope) if f.kind == wire.KIND_ITEM else None)
            self._heard_on(st, body.stream, now_ms)
        name = self._stream_name(kid, body.stream)
        if f.kind == wire.KIND_PLUCK:
            if resurface:
                return events  # its sticky mark was kept across the restart
            target = (kid, body.epoch, body.stream, body.target_seq)
            self.sticky_pluck[target] = retain
            self._sticky_due.push(retain, target)
            self._dirty = True
            for k, (hid, _, _) in list(self.held.items()):
                if hid == target:
                    del self.held[k]
                    self._held_retract(hid, "held_plucked", by=ident, events=events)
            if target in self.current:
                del self.current[target]
                events.append(Event("withdrawn", self._name(kid), kid.hex(), name, body.target_seq,
                                    {"by_seq": body.seq, "reason": body.reason}, ident=target))
            return events
        it: wire.Item = body
        # A keyed item that arrives after its own PLUCK still superseded what came before it at the
        # station (§7.8, whatever the arrival order), so it moves the mark before it is dropped.
        plucked = ident in self.sticky_pluck
        if plucked and (it.state_key is None or it.cls not in CLASSES):
            events.append(self._evidence("plucked", kid, "item arrived after its pluck", stream=name, seq=it.seq))
            return events
        if it.cls not in CLASSES:
            events.append(self._evidence("unknown-class", kid, str(it.cls), stream=name, seq=it.seq))
            return events  # ringbuffer_only: kept for dedup, never surfaced (§6.2)
        if it.state_key is not None:
            hkey = (kid, it.stream, it.state_key)
            order = (it.issued_at, it.epoch, it.seq)
            prev = self.hwm.get(hkey)
            # A mark must outlive every older item for its key (§7.8). Its horizon is the latest of
            # (local expiry + skew + class max TTL) over the items admitted for the key while it is held,
            # so it never goes down (#60 review: a newer value of a shorter-lived class must not shorten
            # it). Each term is bounded when it is set (local expiry is at most first hearing + TTL), so
            # no clock offset can push a horizon past now + TTL + class max + skew. Refused older items
            # do not move it. A mark whose horizon has passed is dropped first, as tick() would, so the
            # outcome does not depend on tick cadence.
            if prev is not None and prev[3] <= now_ms:
                del self.hwm[hkey]
                self.hwm_per_key[kid] -= 1
                self._dirty = True
                prev = None
            # One class per state_key within an epoch (§7.8, §23.2 q21): a change of class in the mark's
            # epoch is dropped and does not move the mark. A new epoch may change it.
            if prev is not None and prev[4] is not None and it.epoch == prev[1] and it.cls != prev[4]:
                reason = "plucked" if plucked else "class-change"   # §7.7: a plucked tuple reports plucked
                events.append(self._evidence(reason, kid, f"class {it.cls} for a key marked with class {prev[4]} "
                                             f"in epoch {prev[1]}" if reason == "class-change"
                                             else "item arrived after its pluck", stream=name, seq=it.seq))
                return events
            # Equal order is only possible for the same identity, i.e. a re-surface after restart.
            if prev is not None and (order < prev[:3] or (order == prev[:3] and not resurface)):
                reason = "plucked" if plucked else "superseded"   # §7.7: a plucked tuple reports plucked
                events.append(self._evidence(reason, kid, "older than the high-water mark" if reason == "superseded"
                                             else "item arrived after its pluck", stream=name, seq=it.seq))
                return events
            if prev is not None and resurface and order == prev[:3] and prev[4] is None:
                self.hwm[hkey] = (*prev[:4], it.cls)   # a mark loaded from v1/v2 state learns its class
                self._dirty = True
            if prev is None or order > prev[:3]:
                until = retain + CLASSES[it.cls].max_ttl_s * 1000
                if prev is None:
                    self.hwm_per_key[kid] = self.hwm_per_key.get(kid, 0) + 1
                else:
                    until = max(until, prev[3])
                self.hwm[hkey] = (*order, until, it.cls)
                self._hwm_due.push(until, hkey)
                self._dirty = True
            for other_ident, h in list(self.current.items()):
                if other_ident[0] == kid and h.item.stream == it.stream and h.item.state_key == it.state_key:
                    del self.current[other_ident]
                    events.append(Event("superseded", self._name(kid), kid.hex(), name, h.item.seq, {"by_seq": it.seq},
                                        ident=other_ident))
        if plucked:
            events.append(self._evidence("plucked", kid, "item arrived after its pluck", stream=name, seq=it.seq))
            return events
        if name is None or (self.tuned is not None and name not in self.tuned):
            if self.receptor_mode and name is None:
                events.append(Event("held", self._name(kid), kid.hex(), None, it.seq,
                                    {"reason": "unnamed_stream"}, ident=ident))
            return events  # untuned or unnamed streams are held, not surfaced (§5.4)
        if it.cls == LIVE_STATE and self.warmup and not self._warm(kid, it.stream, now_ms):
            hkey = (kid, it.stream, it.state_key)
            prev_held = self.held.get(hkey)
            if prev_held is not None and prev_held[0] != ident:
                self._held_retract(prev_held[0], "held_superseded", by=ident, events=events)
            self.held[hkey] = (ident, it, retain)
            if self.receptor_mode:
                events.append(Event("held", self._name(kid), kid.hex(), name, it.seq,
                                    {"reason": "warmup_hold"}, ident=ident))
            return events  # §7.8 rule 4: UNKNOWN until warm-up; released by tick()
        self.current[ident] = _Heard(it, ident, retain - SKEW_MS, now_ms, now_ms)
        events.append(Event("item", self._name(kid), kid.hex(), name, it.seq, self._item_data(it, now_ms, st),
                            ident=ident))
        if name == "root":
            events.extend(self._presence(kid, now_ms))
        return events

    def _item_data(self, it: wire.Item, now_ms: int, st: _StationState) -> dict:
        d = {"class": CLASSES[it.cls].name, "epoch": it.epoch, "issued_at": it.issued_at,
             "expires_at": it.expires_at, "age_ms": max(0, now_ms - it.issued_at - st.offset_ms),
             "hop": it.hop, "scope": it.scope}
        if it.state_key is not None:
            d["state_key"] = it.state_key
        if it.flags & wire.Item.REFRESH:
            d["refresh"] = True
        if it.purpose is not None:
            d["purpose"] = it.purpose
        if it.intensity is not None:
            d["intensity"] = it.intensity
        if it.body is not None:
            if it.ctype == CTYPES["text/plain; charset=utf-8"]:
                d["text"] = it.body.decode("utf-8", "replace")
            else:
                d["body_hex"] = it.body.hex()
            d["ctype"] = it.ctype
        if it.body_ref is not None:
            d["body_ref"] = {"url": it.body_ref[0], "sha256": it.body_ref[1].hex(), "size": it.body_ref[2]}
        return d

    def _quota(self) -> int:
        """Per-key share of the dedup store (§7.4). A key that floods only fills its own share."""
        if self.per_key_quota is not None:
            return max(1, self.per_key_quota)
        return max(1, self.dedup_capacity // max(1, sum(1 for _ in self.manifest)))

    def _room_for(self, kid: bytes, now_ms: int) -> bool:
        if self.dedup_per_key.get(kid, 0) < self._quota():
            return True
        self._purge_dedup(now_ms)
        return self.dedup_per_key.get(kid, 0) < self._quota()

    def _needs_hwm_slot(self, f: wire.Frame, ident: tuple) -> bool:
        """Would admitting this frame add a supersession mark? (the conditions of the hwm step below)"""
        it = f.body
        return (f.kind == wire.KIND_ITEM and it.state_key is not None and it.cls in CLASSES
                and (f.key_id, it.stream, it.state_key) not in self.hwm)

    def _mark_quota(self, kid: bytes) -> int:
        """Per-key limit on supersession marks, counted apart from dedup entries (§7.4). A dedup entry
        lasts about one TTL; a mark lasts that TTL + skew + the class max TTL (§7.8). So the limit is the
        dedup share scaled by the largest ⌈(default TTL + max TTL + skew) / default TTL⌉ among the key's
        granted classes: a key churning state_keys at its class default TTLs within its share fits."""
        if self.per_key_mark_quota is not None:
            return max(1, self.per_key_mark_quota)
        entry = self.manifest.entry(kid)
        specs = [CLASSES[c] for c in (entry.classes if entry else ()) if c in CLASSES] or list(CLASSES.values())
        factor = max(-(-((c.default_ttl_s + c.max_ttl_s) * 1000 + SKEW_MS) // (c.default_ttl_s * 1000)) for c in specs)
        return self._quota() * factor

    def _hwm_room(self, kid: bytes, now_ms: int) -> bool:
        """Marks outlive dedup entries, so they have their own per-key limit, checked at admission and
        never met by evicting a live mark (§7.4, #60)."""
        if self.hwm_per_key.get(kid, 0) < self._mark_quota(kid):
            return True
        self._purge_hwm(now_ms)
        return self.hwm_per_key.get(kid, 0) < self._mark_quota(kid)

    def _heard_on(self, st: _StationState, stream: int, now_ms: int) -> None:
        """Note an admitted copy on a stream, for presence (§8.6). Capped at the key's share, oldest
        dropped first: presence only asks whether some stream was heard within its loops (#60)."""
        st.last_stream_item.pop(stream, None)
        st.last_stream_item[stream] = now_ms
        while len(st.last_stream_item) > self._quota():
            del st.last_stream_item[next(iter(st.last_stream_item))]

    def _warm(self, kid: bytes, stream: int, now_ms: int) -> bool:
        """Warm-up is over for a stream once a beacon has been heard since start and one
        advertised loop period of the stream has passed after it (§7.8 rule 4)."""
        st = self.stations.get(kid)
        if st is None or st.first_beacon_at is None:
            return False
        loop = st.stream_loop_max.get(stream) or CLASSES[LIVE_STATE].loop_floor_ms * 4 // 3
        return now_ms >= st.first_beacon_at + loop

    def _held_retract(self, ident: tuple, reason: str, by: Optional[tuple] = None, events: Optional[list] = None) -> None:
        """A held item dropped before release (§14.18.3 `held_*`), reported only in receptor mode."""
        if self.receptor_mode and events is not None:
            events.append(Event("held_retract", self._name(ident[0]), ident[0].hex(),
                                self._stream_name(ident[0], ident[2]), ident[3], {"reason": reason, "by": by},
                                ident=ident))

    def _lower_epoch(self, f: wire.Frame, now_ms: int) -> list[Event]:
        """Receptor mode: a frame whose epoch is below the key's highest (§5.2, §10.9 amendment BC-1). A
        repeat of an accepted tuple is `duplicate`; a new tuple is admitted to dedup only, as `verified`
        with reason `epoch_regression` and disposition `ringbuffer_only`: it supersedes, plucks and
        surfaces nothing and advances no epoch. It still records evidence `epoch-regression`."""
        kid, body, ident = f.key_id, f.body, f.identity
        events: list[Event] = []
        digest = hashlib.sha256(f.raw).digest()
        seen = self.dedup.get(ident)
        st = self._st(kid)
        if seen is not None:
            if seen[0] != digest:
                events.append(self._evidence("equivocation", kid, f"two frames for {ident[1:]}",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            if ident not in self._restored:
                self.last_dedup = "duplicate"
                return events
            self._restored.discard(ident)
            self.last_dedup = "resurfaced"
        else:
            if not self._room_for(kid, now_ms):
                events.append(self._evidence("over-quota", kid, "per-key dedup quota full; live entries kept",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            retain = wire.local_expiry_ms(body, st.offset_ms, first_heard_ms=now_ms) + SKEW_MS
            self._remember(ident, digest, retain,
                           (body.expires_at, body.scope) if f.kind == wire.KIND_ITEM else None)
        self.evidence_counts["epoch-regression"] = self.evidence_counts.get("epoch-regression", 0) + 1
        events.append(Event("held", self._name(kid), kid.hex(), self._stream_name(kid, body.stream), body.seq,
                            {"reason": "epoch_regression"}, ident=ident))
        return events

    def _release_held(self, now_ms: int) -> list[Event]:
        events: list[Event] = []
        for hkey, (ident, it, retain) in list(self.held.items()):
            kid = ident[0]
            if now_ms >= retain - SKEW_MS or ident in self.sticky_pluck:
                del self.held[hkey]
                self._held_retract(ident, "held_expired" if ident not in self.sticky_pluck else "held_plucked",
                                   events=events)
                continue
            if not self._warm(kid, it.stream, now_ms):
                continue
            del self.held[hkey]
            prev = self.hwm.get(hkey)
            if prev is not None and (it.issued_at, it.epoch, it.seq) < prev[:3]:
                self._held_retract(ident, "held_superseded", events=events)
                continue  # a newer value was heard meanwhile
            st = self._st(kid)
            self.current[ident] = _Heard(it, ident, retain - SKEW_MS, now_ms, now_ms)
            events.append(Event("item", self._name(kid), kid.hex(), self._stream_name(kid, it.stream), it.seq,
                                self._item_data(it, now_ms, st), ident=ident))
        return events

    def _remember(self, ident: tuple, digest: bytes, retain: int, meta: Optional[tuple] = None) -> None:
        # Live entries are never evicted: they hold the equivocation evidence (§10.8) and stop a
        # repeat from counting as new. New tuples are refused per key instead (_room_for).
        # meta is an ITEM's (expires_at, scope), which a later PLUCK must match (§9.7).
        self.dedup[ident] = (digest, retain, meta)
        self.dedup_per_key[ident[0]] = self.dedup_per_key.get(ident[0], 0) + 1
        self._dedup_due.push(retain, ident)
        self._dirty = True

    def _purge_dedup(self, now_ms: int) -> None:
        for _, k in self._dedup_due.due(now_ms):
            v = self.dedup.get(k)
            if v is not None and v[1] <= now_ms:
                del self.dedup[k]
                self.dedup_per_key[k[0]] -= 1
                self._restored.discard(k)
                self._dirty = True
        # A sticky-pluck mark has its PLUCK's retention (§7.7): purging them together keeps the marks
        # within the dedup quota between ticks too (#60).
        for _, k in self._sticky_due.due(now_ms):
            v = self.sticky_pluck.get(k)
            if v is not None and v <= now_ms:
                del self.sticky_pluck[k]
                self._dirty = True
        self._dedup_due.compact(len(self.dedup), lambda: ((v[1], k) for k, v in self.dedup.items()))
        self._sticky_due.compact(len(self.sticky_pluck), lambda: ((v, k) for k, v in self.sticky_pluck.items()))

    def _purge_hwm(self, now_ms: int) -> None:
        for _, k in self._hwm_due.due(now_ms):
            v = self.hwm.get(k)
            if v is not None and v[3] <= now_ms:
                del self.hwm[k]
                self.hwm_per_key[k[0]] -= 1
                self._dirty = True
        self._hwm_due.compact(len(self.hwm), lambda: ((v[3], k) for k, v in self.hwm.items()))

    # ------------------------------------------------------------ time

    def tick(self, now_ms: int) -> list[Event]:
        events: list[Event] = []
        for ident, h in list(self.current.items()):
            if now_ms >= h.local_expiry:
                del self.current[ident]
                events.append(Event("expired", self._name(ident[0]), ident[0].hex(),
                                    self._stream_name(ident[0], ident[2]), ident[3], ident=ident))
        self._purge_dedup(now_ms)
        self._purge_hwm(now_ms)
        events.extend(self._release_held(now_ms))
        self._save_if_dirty()
        for kid in list(self.stations):
            events.extend(self._presence(kid, now_ms))
        return events

    # ------------------------------------------------------------ persisted safety state

    def _save_if_dirty(self) -> None:
        if self.state_path is None or not self._dirty:
            return
        state = {
            "version": STATE_VERSION,
            "epochs": {k.hex(): [s.epoch_hwm, s.epoch_seen_at] for k, s in self.stations.items() if s.epoch_hwm},
            "dedup": [[i[0].hex(), i[1], i[2], i[3], d.hex(), r, *(m or (None, None))]
                      for i, (d, r, m) in self.dedup.items()],
            "sticky_pluck": [[i[0].hex(), i[1], i[2], i[3], r] for i, r in self.sticky_pluck.items()],
            "hwm": [[k[0].hex(), k[1], k[2], *v] for k, v in self.hwm.items()],
        }
        atomic_write_json(self.state_path, state)
        self._dirty = False

    def _load(self, path) -> None:
        with open(path) as f:
            state = json.load(f)
        version = state.get("version")
        if version not in (1, 2, STATE_VERSION):
            raise ValueError(f"listener state {path}: unsupported version {version!r}")
        for kid_hex, (epoch, seen_at) in state["epochs"].items():
            st = self._st(bytes.fromhex(kid_hex))
            st.epoch_hwm, st.epoch_seen_at = epoch, seen_at
        for row in state["dedup"]:
            # version 1 rows have no (expires_at, scope): those targets skip the §9.7 PLUCK check
            kid_hex, epoch, stream, seq, digest, retain = row[:6]
            meta = tuple(row[6:8]) if len(row) >= 8 and row[6] is not None else None
            ident = (bytes.fromhex(kid_hex), epoch, stream, seq)
            self.dedup[ident] = (bytes.fromhex(digest), retain, meta)
            self.dedup_per_key[ident[0]] = self.dedup_per_key.get(ident[0], 0) + 1
            self._dedup_due.push(retain, ident)
            self._restored.add(ident)
        for kid_hex, epoch, stream, seq, retain in state["sticky_pluck"]:
            target = (bytes.fromhex(kid_hex), epoch, stream, seq)
            self.sticky_pluck[target] = retain
            self._sticky_due.push(retain, target)
        for row in state["hwm"]:
            # rows before version 3 have no class: those marks skip the class-change check
            kid_hex, stream, state_key, issued_at, epoch, seq, retain = row[:7]
            kid = bytes.fromhex(kid_hex)
            self.hwm[(kid, stream, state_key)] = (issued_at, epoch, seq, retain, row[7] if len(row) > 7 else None)
            self._hwm_due.push(retain, (kid, stream, state_key))
            self.hwm_per_key[kid] = self.hwm_per_key.get(kid, 0) + 1

    # ------------------------------------------------------------ presence (§8.6)

    def _root_state(self, kid: bytes) -> Optional[bool]:
        for h in self.current.values():
            if h.tuple[0] == kid and h.item.state_key == "root" and self._stream_name(kid, h.item.stream) == "root":
                try:
                    body = cbor.decode(h.item.body) if h.item.body is not None else {}
                except cbor.CborError:
                    return None
                return isinstance(body, dict) and 1 in body
        return None

    def presence_state(self, kid: bytes, now_ms: int) -> str:
        st = self.stations.get(kid)
        if st is None or st.last_beacon is None:
            return "UNOBSERVABLE"
        if st.signed_off:
            return "UNOBSERVABLE:signed_off"
        period = st.period_ms or 1_000
        if now_ms - st.last_beacon > 3 * period:
            return "UNOBSERVABLE"
        root = self._root_state(kid)
        if root is None:
            return "ROOT_UNKNOWN"
        if root is False:
            return "UNEQUIPPED_PRESENT"
        for sid, last in st.last_stream_item.items():
            loop = st.stream_loops.get(sid) or 0
            if loop and now_ms - last <= 5 * loop and self._stream_name(kid, sid) != "root":
                return "EQUIPPED_SPEAKING"
        return "EQUIPPED_QUIET"

    def _presence(self, kid: bytes, now_ms: int) -> list[Event]:
        st = self._st(kid)
        state = self.presence_state(kid, now_ms)
        if state == st.presence:
            return []
        st.presence = state
        since = st.last_beacon
        return [Event("presence", self._name(kid), kid.hex(), data={"state": state, "last_beacon_ms": since})]

    def on_air(self) -> list[dict]:
        """What this listener currently holds as live (its view, not the station's)."""
        return [{"station": self._name(h.tuple[0]), "stream": self._stream_name(h.tuple[0], h.item.stream),
                 "seq": h.item.seq, "copies": h.copies, "state_key": h.item.state_key}
                for h in self.current.values()]
