"""A listener: verify, dedup, pluck, supersede and track presence (RFC-0001 §7.4-§7.8, §8).

This is a receptor-lite for the spike. It surfaces events (a new item, a
withdrawal, a presence change, evidence) and never actuates anything.
Landing into agent sessions (§14) is out of scope here.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from . import cbor, wire
from .ids import CLASSES, CTYPES
from .manifest import Manifest

SKEW_MS = 5_000
OFFSET_SAMPLES = 16


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

    @property
    def offset_ms(self) -> int:
        return min(self.offsets) if self.offsets else 0


class Listener:
    def __init__(self, manifest: Manifest, tuned: Optional[set] = None, dedup_capacity: int = 100_000):
        self.manifest = manifest
        self.tuned = tuned                    # stream names to surface; None = every named stream
        self.dedup_capacity = dedup_capacity
        self.dedup: dict[tuple, tuple] = {}   # identity -> (sha256(frame), retain_until)
        self.sticky_pluck: dict[tuple, int] = {}
        self.hwm: dict[tuple, tuple] = {}     # (kid, stream, state_key) -> (issued_at, epoch, seq, retain_until)
        self.current: dict[tuple, _Heard] = {}  # identity -> heard item (on air, from this listener's view)
        self.stations: dict[bytes, _StationState] = {}
        self.evidence_counts: dict[str, int] = {}

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
        if f.kind == wire.KIND_BEACON:
            return self._beacon(f, now_ms)
        return self._item_or_pluck(f, now_ms)

    def _epoch_ok(self, kid: bytes, epoch: int, now_ms: int, events: list) -> bool:
        st = self._st(kid)
        if epoch < st.epoch_hwm:
            events.append(self._evidence("epoch-regression", kid, f"{epoch} < {st.epoch_hwm}"))
            return False
        if epoch > st.epoch_hwm:
            st.epoch_hwm, st.epoch_seen_at = epoch, now_ms
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
        for e in b.streams:
            st.stream_loops[e.stream_id] = e.loop_ms
        events.extend(self._presence(f.key_id, now_ms))
        return events

    def _item_or_pluck(self, f: wire.Frame, now_ms: int) -> list[Event]:
        events: list[Event] = []
        body = f.body
        kid = f.key_id
        if not self._epoch_ok(kid, body.epoch, now_ms, events):
            return events
        ident = f.identity
        digest = hashlib.sha256(f.raw).digest()
        seen = self.dedup.get(ident)
        st = self._st(kid)
        st.last_stream_item[body.stream] = now_ms
        if seen is not None:
            if seen[0] != digest:
                events.append(self._evidence("equivocation", kid, f"two frames for {ident[1:]}",
                                             stream=self._stream_name(kid, body.stream), seq=body.seq))
            elif ident in self.current:
                h = self.current[ident]
                h.copies += 1
                h.last_heard = now_ms
            return events  # a repeat is a benign no-op (§7.4)
        retain = wire.local_expiry_ms(body, st.offset_ms) + SKEW_MS
        self._remember(ident, digest, retain)
        name = self._stream_name(kid, body.stream)
        if f.kind == wire.KIND_PLUCK:
            target = (kid, body.epoch, body.stream, body.target_seq)
            self.sticky_pluck[target] = retain
            if target in self.current:
                del self.current[target]
                events.append(Event("withdrawn", self._name(kid), kid.hex(), name, body.target_seq,
                                    {"by_seq": body.seq, "reason": body.reason}))
            return events
        it: wire.Item = body
        entry = self.manifest.entry(kid)
        if it.cls not in entry.classes:
            events.append(self._evidence("capability", kid, f"class {it.cls} not granted", stream=name, seq=it.seq))
            return events
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
            if prev is not None and order <= prev[:3]:
                events.append(self._evidence("superseded", kid, "older than the high-water mark", stream=name, seq=it.seq))
                return events
            class_max_ms = CLASSES[it.cls].max_ttl_s * 1000
            self.hwm[hkey] = (*order, retain + class_max_ms)
            for other_ident, h in list(self.current.items()):
                if other_ident[0] == kid and h.item.stream == it.stream and h.item.state_key == it.state_key:
                    del self.current[other_ident]
                    events.append(Event("superseded", self._name(kid), kid.hex(), name, h.item.seq, {"by_seq": it.seq}))
        if name is None or (self.tuned is not None and name not in self.tuned):
            return events  # untuned or unnamed streams are held, not surfaced (§5.4)
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

    def _remember(self, ident: tuple, digest: bytes, retain: int) -> None:
        if len(self.dedup) >= self.dedup_capacity:  # evict oldest first; never fail closed (§7.4)
            for k, _ in sorted(self.dedup.items(), key=lambda kv: kv[1][1])[: max(1, self.dedup_capacity // 10)]:
                del self.dedup[k]
        self.dedup[ident] = (digest, retain)

    # ------------------------------------------------------------ time

    def tick(self, now_ms: int) -> list[Event]:
        events: list[Event] = []
        for ident, h in list(self.current.items()):
            if now_ms >= h.local_expiry:
                del self.current[ident]
                events.append(Event("expired", self._name(ident[0]), ident[0].hex(),
                                    self._stream_name(ident[0], ident[2]), ident[3]))
        for d in (self.dedup,):
            for k in [k for k, v in d.items() if v[1] <= now_ms]:
                del d[k]
        for k in [k for k, v in self.sticky_pluck.items() if v <= now_ms]:
            del self.sticky_pluck[k]
        for k in [k for k, v in self.hwm.items() if v[3] <= now_ms]:
            del self.hwm[k]
        for kid in list(self.stations):
            events.extend(self._presence(kid, now_ms))
        return events

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
