"""A listener: verify, dedup, pluck, supersede and track presence (RFC-0001 §7.4-§7.8, §8).

This is a receptor-lite for the spike. It surfaces events (a new item, a
withdrawal, a presence change, evidence) and never actuates anything.
Landing into agent sessions (§14) is out of scope here.

With ``state_path`` set, the safety state that must survive a restart (epoch
maxima, dedup digests, sticky PLUCKs, supersession high-water marks; §5.2, §7.4,
§7.7, §7.8) is written atomically after every change and loaded at start.
"""

from __future__ import annotations

import hashlib
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
STATE_VERSION = 1


@dataclass
class Event:
    kind: str       # item | withdrawn | superseded | expired | presence | evidence
    station: str
    key_id: str
    stream: Optional[str] = None
    seq: Optional[int] = None
    data: dict = field(default_factory=dict)

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
    last_stream_item: dict = field(default_factory=dict)  # stream_id -> last time a copy was heard
    presence: str = ""  # nothing reported yet
    first_beacon_at: Optional[int] = None  # first beacon heard since this listener started (warm-up, §7.8)
    stream_loop_max: dict = field(default_factory=dict)  # stream_id -> advertised loop_max_ms

    @property
    def offset_ms(self) -> int:
        return min(self.offsets) if self.offsets else 0


class Listener:
    def __init__(self, manifest: Manifest, tuned: Optional[set] = None, dedup_capacity: int = 100_000,
                 binding: str = "lan", state_path=None, warmup: bool = True, ephemeral: bool = False):
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
        self.dedup: dict[tuple, tuple] = {}   # identity -> (sha256(frame), retain_until)
        self.dedup_per_key: dict[bytes, int] = {}
        self.sticky_pluck: dict[tuple, int] = {}
        self.hwm: dict[tuple, tuple] = {}     # (kid, stream, state_key) -> (issued_at, epoch, seq, retain_until)
        self.current: dict[tuple, _Heard] = {}  # identity -> heard item (on air, from this listener's view)
        self.stations: dict[bytes, _StationState] = {}
        self.evidence_counts: dict[str, int] = {}
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
        try:
            f = wire.parse(datagram, self.manifest.resolve, now_ms, st.offset_ms if st else 0)
        except wire.Reject as r:
            known = kid and self.manifest.entry(kid) is not None
            return [self._evidence(r.reason, kid if known else b"", r.detail)]
        events = self._beacon(f, now_ms) if f.kind == wire.KIND_BEACON else self._item_or_pluck(f, now_ms)
        self._save_if_dirty()
        return events

    def _epoch_ok(self, kid: bytes, epoch: int, now_ms: int, events: list) -> bool:
        st = self._st(kid)
        if epoch < st.epoch_hwm:
            events.append(self._evidence("epoch-regression", kid, f"{epoch} < {st.epoch_hwm}"))
            return False
        if epoch > st.epoch_hwm:
            st.epoch_hwm, st.epoch_seen_at = epoch, now_ms
            self._dirty = True
            # bseq and the advertised loops belong to the previous epoch (§9.8): a restarted
            # station counts beacons from 1 again and may loop different streams.
            st.bseq = 0
            st.stream_loops.clear()
        return True

    def _beacon(self, f: wire.Frame, now_ms: int) -> list[Event]:
        b: wire.Beacon = f.body
        events: list[Event] = []
        if not self._epoch_ok(f.key_id, b.epoch, now_ms, events):
            return events
        st = self._st(f.key_id)
        if b.epoch == st.epoch_hwm and b.bseq <= st.bseq and st.last_beacon is not None:
            return events  # older or repeated beacon
        st.bseq = b.bseq
        st.offsets.append(now_ms - b.wallclock)
        st.last_beacon = now_ms
        st.signed_off = b.next_beacon_ms == 0
        st.period_ms = b.next_beacon_ms or st.period_ms
        if st.first_beacon_at is None:
            st.first_beacon_at = now_ms
        for e in b.streams:
            st.stream_loops[e.stream_id] = e.loop_ms
            st.stream_loop_max[e.stream_id] = e.loop_max_ms
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
        if not self._epoch_ok(kid, body.epoch, now_ms, events):
            return events
        ident = f.identity
        digest = hashlib.sha256(f.raw).digest()
        seen = self.dedup.get(ident)
        st = self._st(kid)
        st.last_stream_item[body.stream] = now_ms
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
                return events  # a repeat is a benign no-op (§7.4)
            # Accepted before a restart: its dedup, pluck and supersession state was kept, but this
            # process has not surfaced it yet. Surface it once, through the same checks.
            self._restored.discard(ident)
            resurface = True
            retain = seen[1]
        else:
            if not self._room_for(kid, now_ms):
                events.append(self._evidence("over-quota", kid, "per-key dedup quota full; live entries kept",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
                return events
            retain = wire.local_expiry_ms(body, st.offset_ms, first_heard_ms=now_ms) + SKEW_MS
            self._remember(ident, digest, retain)
        name = self._stream_name(kid, body.stream)
        if f.kind == wire.KIND_PLUCK:
            if resurface:
                return events  # its sticky mark was kept across the restart
            target = (kid, body.epoch, body.stream, body.target_seq)
            self.sticky_pluck[target] = retain
            self._dirty = True
            for k, (hid, _, _) in list(self.held.items()):
                if hid == target:
                    del self.held[k]
            if target in self.current:
                del self.current[target]
                events.append(Event("withdrawn", self._name(kid), kid.hex(), name, body.target_seq,
                                    {"by_seq": body.seq, "reason": body.reason}))
            return events
        it: wire.Item = body
        if ident in self.sticky_pluck:
            events.append(self._evidence("plucked", kid, "item arrived after its pluck", stream=name, seq=it.seq))
            return events
        if it.cls not in CLASSES:
            events.append(self._evidence("unknown-class", kid, str(it.cls), stream=name, seq=it.seq))
            return events  # ringbuffer_only: kept for dedup, never surfaced (§6.2)
        if it.state_key is not None:
            hkey = (kid, it.stream, it.state_key)
            order = (it.issued_at, it.epoch, it.seq)
            prev = self.hwm.get(hkey)
            # Equal order is only possible for the same identity, i.e. a re-surface after restart.
            if prev is not None and (order < prev[:3] or (order == prev[:3] and not resurface)):
                events.append(self._evidence("superseded", kid, "older than the high-water mark", stream=name, seq=it.seq))
                return events
            if prev is None or order > prev[:3]:
                class_max_ms = CLASSES[it.cls].max_ttl_s * 1000
                self.hwm[hkey] = (*order, retain + class_max_ms)
                self._dirty = True
            for other_ident, h in list(self.current.items()):
                if other_ident[0] == kid and h.item.stream == it.stream and h.item.state_key == it.state_key:
                    del self.current[other_ident]
                    events.append(Event("superseded", self._name(kid), kid.hex(), name, h.item.seq, {"by_seq": it.seq}))
        if name is None or (self.tuned is not None and name not in self.tuned):
            return events  # untuned or unnamed streams are held, not surfaced (§5.4)
        if it.cls == LIVE_STATE and self.warmup and not self._warm(kid, it.stream, now_ms):
            self.held[(kid, it.stream, it.state_key)] = (ident, it, retain)
            return events  # §7.8 rule 4: UNKNOWN until warm-up; released by tick()
        self.current[ident] = _Heard(it, ident, retain - SKEW_MS, now_ms, now_ms)
        events.append(Event("item", self._name(kid), kid.hex(), name, it.seq, self._item_data(it, now_ms, st)))
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
        return max(1, self.dedup_capacity // max(1, sum(1 for _ in self.manifest)))

    def _room_for(self, kid: bytes, now_ms: int) -> bool:
        if self.dedup_per_key.get(kid, 0) < self._quota():
            return True
        self._purge_dedup(now_ms)
        return self.dedup_per_key.get(kid, 0) < self._quota()

    def _warm(self, kid: bytes, stream: int, now_ms: int) -> bool:
        """Warm-up is over for a stream once a beacon has been heard since start and one
        advertised loop period of the stream has passed after it (§7.8 rule 4)."""
        st = self.stations.get(kid)
        if st is None or st.first_beacon_at is None:
            return False
        loop = st.stream_loop_max.get(stream) or CLASSES[LIVE_STATE].loop_floor_ms * 4 // 3
        return now_ms >= st.first_beacon_at + loop

    def _release_held(self, now_ms: int) -> list[Event]:
        events: list[Event] = []
        for hkey, (ident, it, retain) in list(self.held.items()):
            kid = ident[0]
            if now_ms >= retain - SKEW_MS or ident in self.sticky_pluck:
                del self.held[hkey]
                continue
            if not self._warm(kid, it.stream, now_ms):
                continue
            del self.held[hkey]
            prev = self.hwm.get(hkey)
            if prev is not None and (it.issued_at, it.epoch, it.seq) < prev[:3]:
                continue  # a newer value was heard meanwhile
            st = self._st(kid)
            self.current[ident] = _Heard(it, ident, retain - SKEW_MS, now_ms, now_ms)
            events.append(Event("item", self._name(kid), kid.hex(), self._stream_name(kid, it.stream), it.seq,
                                self._item_data(it, now_ms, st)))
        return events

    def _remember(self, ident: tuple, digest: bytes, retain: int) -> None:
        # Live entries are never evicted: they hold the equivocation evidence (§10.8) and stop a
        # repeat from counting as new. New tuples are refused per key instead (_room_for).
        self.dedup[ident] = (digest, retain)
        self.dedup_per_key[ident[0]] = self.dedup_per_key.get(ident[0], 0) + 1
        self._dirty = True

    def _purge_dedup(self, now_ms: int) -> None:
        for k in [k for k, v in self.dedup.items() if v[1] <= now_ms]:
            del self.dedup[k]
            self.dedup_per_key[k[0]] -= 1
            self._restored.discard(k)
            self._dirty = True

    # ------------------------------------------------------------ time

    def tick(self, now_ms: int) -> list[Event]:
        events: list[Event] = []
        for ident, h in list(self.current.items()):
            if now_ms >= h.local_expiry:
                del self.current[ident]
                events.append(Event("expired", self._name(ident[0]), ident[0].hex(),
                                    self._stream_name(ident[0], ident[2]), ident[3]))
        self._purge_dedup(now_ms)
        for k in [k for k, v in self.sticky_pluck.items() if v <= now_ms]:
            del self.sticky_pluck[k]
            self._dirty = True
        for k in [k for k, v in self.hwm.items() if v[3] <= now_ms]:
            del self.hwm[k]
            self._dirty = True
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
            "dedup": [[i[0].hex(), i[1], i[2], i[3], d.hex(), r] for i, (d, r) in self.dedup.items()],
            "sticky_pluck": [[i[0].hex(), i[1], i[2], i[3], r] for i, r in self.sticky_pluck.items()],
            "hwm": [[k[0].hex(), k[1], k[2], *v] for k, v in self.hwm.items()],
        }
        path = os.fspath(self.state_path)
        d = os.path.dirname(path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=os.path.basename(path) + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, separators=(",", ":"))
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
        self._dirty = False

    def _load(self, path) -> None:
        with open(path) as f:
            state = json.load(f)
        if state.get("version") != STATE_VERSION:
            raise ValueError(f"listener state {path}: unsupported version {state.get('version')!r}")
        for kid_hex, (epoch, seen_at) in state["epochs"].items():
            st = self._st(bytes.fromhex(kid_hex))
            st.epoch_hwm, st.epoch_seen_at = epoch, seen_at
        for kid_hex, epoch, stream, seq, digest, retain in state["dedup"]:
            ident = (bytes.fromhex(kid_hex), epoch, stream, seq)
            self.dedup[ident] = (bytes.fromhex(digest), retain)
            self.dedup_per_key[ident[0]] = self.dedup_per_key.get(ident[0], 0) + 1
            self._restored.add(ident)
        for kid_hex, epoch, stream, seq, retain in state["sticky_pluck"]:
            self.sticky_pluck[(bytes.fromhex(kid_hex), epoch, stream, seq)] = retain
        for kid_hex, stream, state_key, issued_at, epoch, seq, retain in state["hwm"]:
            self.hwm[(bytes.fromhex(kid_hex), stream, state_key)] = (issued_at, epoch, seq, retain)

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
