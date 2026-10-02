"""The station: a per-stream ring of live items looped until expiry (RFC-0001 §7, §8).

Time is explicit (``now_ms``) so the carousel is deterministic under test; the
asyncio runner in ``runner.py`` drives it with the real clock.
"""

from __future__ import annotations

import fcntl
import hashlib
import heapq
import os
import random
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import cbor, wire
from .ids import CLASS_BY_NAME, CLASS_PRIORITY, CLASSES, CTYPES, SCOPES, key_id, stream_ids

STOP_BEFORE_EXPIRY_MS = 100      # §7.3
KEY_CLASS_MARGIN_MS = 10_000     # §7.8: receiver skew (5 s) plus transit, past a key's last possible mark
BURST_OFFSETS_MS = (1_000, 2_000, 4_000)  # §7.6
K_AVAIL = 3                      # §7.5
CLASS_MAX_LOOP_MS = 300_000      # §7.5
DEFAULT_DEPTH = 256              # §7.1
DEFAULT_B_STREAM = 4_000         # bit/s, §7.5
DEFAULT_B_STATION = 16_000       # bit/s, §7.5
STATION_HARD_CAP_S = 86_400      # D3
DEFAULT_STREAM_MAX_TTL_S = 300   # D3
BEACON_ENTRIES_PER_PAGE = 24     # §8.4 (worst case ~26-27 fit in 1 100 B)
MAX_PAGES = 8
PROFILE = "canticle-regulation/1"
NEVER_SHED = {"control", "alarm"}


@dataclass
class StreamConfig:
    name: str
    cls: str = "chatter"                  # default class for items on this stream
    default_ttl_s: Optional[int] = None   # None: the class default, capped by max_ttl_s
    max_ttl_s: int = DEFAULT_STREAM_MAX_TTL_S
    b_stream: int = DEFAULT_B_STREAM
    lens: Optional[int] = None


@dataclass
class SingResult:
    stream: str
    seq: int
    epoch: int
    issued_at: int
    expires_at: int
    ttl_s: float
    loop_ms: int
    clamp: str              # class_min | fair_share | budget | degraded | none
    size: int
    superseded_seq: Optional[int] = None
    kind: str = "item"

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class _OnAir:
    frame: bytes
    kind: int
    seq: int
    cls: int
    expires_at: int
    req_loop_ms: int
    scope: int
    state_key: Optional[str] = None
    burst: list = field(default_factory=list)   # absolute send times still pending
    next_at: Optional[int] = None
    u: float = 1.0                              # jitter factor for the current interval
    last_sent: Optional[int] = None
    loop_ms: int = 0
    clamp: str = "none"
    shed: bool = False                          # degraded and sheddable: no repeats after the burst
    # refresh re-issue (§7.9)
    refresh_at: Optional[int] = None
    horizon: Optional[int] = None
    reissue: Optional[dict] = None


@dataclass
class _Stream:
    cfg: StreamConfig
    sid: int
    head_seq: int = 0
    ring: dict = field(default_factory=dict)  # seq -> _OnAir, in seq order
    # state_key -> [class code, forget_at]. One class per state_key within an epoch while a receiver may
    # still hold a mark for the key (§7.8, §23.2 q21); after forget_at the entry is dropped, so the table
    # holds only keys sung within about one TTL + class max TTL, not every key of the epoch.
    key_classes: dict = field(default_factory=dict)


def next_epoch(path, now_s: Optional[int] = None) -> int:
    """Take the next epoch from a counter persisted at ``path`` (§5.2), storing it before returning it.

    The epoch is ``max(previous + 1, floor(unix seconds))``. It strictly increases across restarts
    however close together, and across a clock that steps back, and it never falls below the epoch
    a time-based start would have used, so listeners that heard one don't see a regression. The
    file is replaced atomically, so a crash leaves the old value or the new one, never neither.
    A missing file starts the counter; an unreadable one raises rather than guessing.
    """
    p = Path(path)
    now_s = int(time.time()) if now_s is None else now_s
    # One lock across read, increment and durable replace: two concurrent starts must never
    # read the same previous value. The temporary file is unique per call.
    with open(p.with_name(p.name + ".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prev = int(p.read_text()) if p.exists() else 0
        n = max(prev + 1, now_s)
        if n > 2**32 - 1:
            raise ValueError("epoch space exhausted (u32, §5.2)")
        fd, tmp = tempfile.mkstemp(dir=p.parent or ".", prefix=p.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(f"{n}\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        dfd = os.open(p.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    return n


class NotGranted(ValueError):
    """The station's manifest entry does not grant this class, scope or stream (§10.4)."""


class Station:
    def __init__(self, sk: Ed25519PrivateKey, streams, *, epoch: Optional[int] = None,
                 b_station: int = DEFAULT_B_STATION, beacon_period_ms: int = 1_000,
                 depth: int = DEFAULT_DEPTH, rng: Optional[random.Random] = None, now_ms: Optional[int] = None,
                 grant=None, host_binding: bool = False):
        self.sk = sk
        self.key_id = key_id(wire.public_key_bytes(sk))
        # grant: this key's manifest entry (manifest.StationEntry). When set, sing() refuses any
        # class, scope or stream it does not grant, before a seq is allocated or anything signed.
        # A station behind an agent-facing socket must have one (runner.run_station checks).
        if grant is not None and grant.key_id != self.key_id:
            raise ValueError("grant is for a different key")
        self.grant = grant
        # host_binding: whether this station has a host-local binding (§11.1). Without one it only
        # speaks UDP, and a host-scoped frame must never leave the host (§4.3), so sing() refuses it.
        self.host_binding = host_binding
        # epoch=None falls back to floor(unix seconds): only safe if starts are >= 1 s apart and the
        # clock never steps back. Anything that can restart should pass next_epoch(path) (§5.2).
        self.epoch = int(time.time()) if epoch is None else epoch
        self.rng = rng or random.Random()
        self.depth = depth
        self.beacon_period_ms = beacon_period_ms
        self.b_station = b_station
        configs = list(streams)
        ids = stream_ids(c.name for c in configs)  # refuses collisions (§5.4)
        by_name = {v: k for k, v in ids.items()}
        if len(configs) > BEACON_ENTRIES_PER_PAGE * MAX_PAGES:
            raise ValueError("too many streams for beacon rotation (§8.4)")
        self.streams: dict[str, _Stream] = {}
        self._key_due: list = []  # heap of (forget_at, stream name, state_key), lazily invalidated
        for c in configs:
            if c.cls not in CLASS_BY_NAME:
                raise ValueError(f"unknown class {c.cls!r}")
            spec = CLASS_BY_NAME[c.cls]
            c.max_ttl_s = min(c.max_ttl_s, spec.max_ttl_s, STATION_HARD_CAP_S)
            c.default_ttl_s = min(c.default_ttl_s or spec.default_ttl_s, c.max_ttl_s)
            self.streams[c.name] = _Stream(cfg=c, sid=by_name[c.name])
        self._fit_budget()
        self.bseq = 0
        now = _now() if now_ms is None else now_ms
        self.next_beacon_at = now
        self._next_beacon_ms = beacon_period_ms
        self.page_index = 0

    # ------------------------------------------------------------ budget

    def _fit_budget(self) -> None:
        """Scale stream budgets down, lowest class priority first, to fit B_station (§7.5)."""
        total = sum(s.cfg.b_stream for s in self.streams.values())
        order = sorted(self.streams.values(), key=lambda s: -CLASS_PRIORITY.index(s.cfg.cls))
        for s in order:
            if total <= self.b_station:
                break
            cut = min(s.cfg.b_stream - 500, total - self.b_station)
            if cut > 0:
                s.cfg.b_stream -= cut
                total -= cut
        if total > self.b_station:
            raise ValueError("stream budgets cannot fit B_station")

    # ------------------------------------------------------------ regulator

    def _loop(self, st: _Stream, oa: _OnAir, now: int, admission: bool = False) -> tuple[int, str]:
        """Effective loop and clamp reason (§7.5). The availability ceiling ``hi`` is
        checked at admission: an item that cannot get k_avail repeats in its life is
        DEGRADED and, if sheddable, sent as first copy and burst only. Rechecking it
        at every reconsideration would shed every item in the last third of its life."""
        n = max(1, len(st.ring))
        fair = int(1000 * 8 * len(oa.frame) * n / st.cfg.b_stream)
        lo = CLASSES[oa.cls].loop_floor_ms
        loop = max(oa.req_loop_ms, lo, fair)
        if admission:
            hi = min(CLASS_MAX_LOOP_MS, (oa.expires_at - now) // K_AVAIL)
            if loop > hi:
                return loop, "degraded"
        if loop == fair and fair > max(oa.req_loop_ms, lo):
            return loop, "fair_share"
        if loop == lo and lo > oa.req_loop_ms:
            return loop, "class_min"
        return loop, "none"

    @staticmethod
    def _req_loop(loop, cls: int) -> int:
        lo = CLASSES[cls].loop_floor_ms
        if isinstance(loop, int):
            return loop
        return {"fast": lo, "normal": 2 * lo, "slow": 6 * lo}[loop]

    # ------------------------------------------------------------ publishing

    def _stream(self, name: str) -> _Stream:
        try:
            return self.streams[name]
        except KeyError:
            raise ValueError(f"station has no stream {name!r}") from None

    def sing(self, now_ms: int, stream: str, *, body: Optional[bytes] = None, text: Optional[str] = None,
             body_ref=None, cls: Optional[str] = None, ctype=None, ttl_s: Optional[float] = None,
             state_key: Optional[str] = None, loop="normal", scope: str = "lan",
             purpose: Optional[str] = None, intensity: Optional[int] = None,
             keep_on_air_s: Optional[int] = None, hop: int = 0, flags: int = 0) -> SingResult:
        """Accept an item: assign epoch/seq/times, sign once, schedule burst and loop (§7.2)."""
        st = self._stream(stream)
        spec = CLASS_BY_NAME[cls or st.cfg.cls]
        if scope not in SCOPES:
            raise ValueError(f"unknown scope {scope!r}")
        if self.grant is not None:
            if spec.code not in self.grant.classes:
                raise NotGranted(f"class {spec.name} is not granted to this key (§10.4)")
            if SCOPES[scope] not in self.grant.scopes:
                raise NotGranted(f"scope {scope} is not granted to this key (§4.3)")
            if self.grant.streams and stream not in self.grant.streams:
                raise NotGranted(f"stream {stream} is not granted to this key (§10.3)")
        if scope == "host" and not self.host_binding:
            raise ValueError("host scope needs a host-local binding; this station only sends UDP (§4.3)")
        if text is not None:
            body, ctype = text.encode("utf-8"), CTYPES["text/plain; charset=utf-8"] if ctype is None else ctype
        if body is None and body_ref is None:
            raise ValueError("an item needs a body or a body_ref")
        if ctype is None:
            if body is not None:
                raise ValueError("ctype is required for a bytes body (§9.9)")
            ctype = CTYPES["application/vnd.canticle.digest-ref+cbor"]  # a doorbell (§9.12)
        if spec.keyed and not state_key:
            raise ValueError(f"class {spec.name} requires a state_key")
        if keep_on_air_s and not state_key:
            raise ValueError("only keyed items can be kept on air by refresh (§7.9)")
        self._forget_keys(now_ms)
        held = st.key_classes.get(state_key) if state_key is not None else None
        if held is not None and held[0] != spec.code:
            raise ValueError(f"state_key {state_key!r} still carries class {CLASSES[held[0]].name} in this "
                             "epoch; a class change waits until no receiver can hold its mark, or a new "
                             "epoch (§7.8)")
        ttl_ms = int(min(ttl_s if ttl_s is not None else st.cfg.default_ttl_s, st.cfg.default_ttl_s) * 1000)
        if ttl_ms <= STOP_BEFORE_EXPIRY_MS:
            raise ValueError("ttl too short")
        st.head_seq += 1
        it = wire.Item(epoch=self.epoch, stream=st.sid, seq=st.head_seq, issued_at=now_ms,
                       expires_at=now_ms + ttl_ms, cls=spec.code, ctype=ctype,
                       body=body, body_ref=body_ref, state_key=state_key, hop=hop, scope=SCOPES[scope],
                       intensity=intensity, flags=flags, purpose=purpose, lens=st.cfg.lens)
        frame = wire.encode_item(self.sk, it)
        superseded = None
        if state_key is not None:
            for seq, other in list(st.ring.items()):
                if other.kind == wire.KIND_ITEM and other.state_key == state_key:
                    del st.ring[seq]  # §7.8: stop the superseded loop at once
                    superseded = seq
        oa = _OnAir(frame=frame, kind=wire.KIND_ITEM, seq=it.seq, cls=spec.code, expires_at=it.expires_at,
                    req_loop_ms=self._req_loop(loop, spec.code), scope=it.scope, state_key=state_key)
        if keep_on_air_s:
            oa.horizon = now_ms + int(min(keep_on_air_s, STATION_HARD_CAP_S) * 1000)  # D3: 24 h ceiling
            oa.refresh_at = now_ms + (2 * ttl_ms) // 3
            oa.reissue = dict(stream=stream, body=body, body_ref=body_ref, cls=spec.name, ctype=it.ctype,
                              ttl_s=ttl_ms / 1000, state_key=state_key, loop=loop, scope=scope,
                              purpose=purpose, intensity=intensity, hop=hop, flags=flags)
        if state_key is not None:
            # A receiver's mark lasts its local expiry (at most first hearing + TTL) + 5 s + class max TTL
            # (§7.8); first hearing is at most this item's expiry plus transit.
            forget_at = it.expires_at + ttl_ms + spec.max_ttl_s * 1000 + KEY_CLASS_MARGIN_MS
            held = st.key_classes.get(state_key)
            if held is None or forget_at > held[1]:
                st.key_classes[state_key] = [spec.code, max(forget_at, held[1] if held else 0)]
                heapq.heappush(self._key_due, (forget_at, stream, state_key))
        self._admit(st, oa, now_ms)
        return SingResult(stream=stream, seq=it.seq, epoch=self.epoch, issued_at=it.issued_at,
                          expires_at=it.expires_at, ttl_s=ttl_ms / 1000, loop_ms=oa.loop_ms, clamp=oa.clamp,
                          size=len(frame), superseded_seq=superseded)

    def hush(self, now_ms: int, stream: str, seq: int, reason: int = 0) -> SingResult:
        """Pluck a live item: stop its loop, then loop a PLUCK until its expiry (§7.7)."""
        st = self._stream(stream)
        target = st.ring.get(seq)
        if target is None or target.kind != wire.KIND_ITEM:
            raise ValueError(f"no live item {stream}#{seq} to pluck")
        if target.expires_at - now_ms < STOP_BEFORE_EXPIRY_MS:
            raise ValueError("target already expiring")
        if sum(1 for oa in st.ring.values() if oa.kind == wire.KIND_PLUCK) >= self.depth:
            raise ValueError("pluck capacity full: the stream already holds depth live PLUCKs (§7.1)")
        # Build and sign the PLUCK before touching the carousel, so a refused hush changes nothing.
        p = wire.Pluck(epoch=self.epoch, stream=st.sid, seq=st.head_seq + 1, issued_at=now_ms,
                       expires_at=target.expires_at, scope=target.scope, target_seq=seq, reason=reason)
        frame = wire.encode_pluck(self.sk, p)
        del st.ring[seq]
        st.head_seq = p.seq
        oa = _OnAir(frame=frame, kind=wire.KIND_PLUCK, seq=p.seq, cls=target.cls, expires_at=p.expires_at,
                    req_loop_ms=target.req_loop_ms, scope=p.scope)
        self._admit(st, oa, now_ms)
        return SingResult(stream=stream, seq=p.seq, epoch=self.epoch, issued_at=now_ms, expires_at=p.expires_at,
                          ttl_s=(p.expires_at - now_ms) / 1000, loop_ms=oa.loop_ms, clamp=oa.clamp,
                          size=len(frame), kind="pluck")

    def _admit(self, st: _Stream, oa: _OnAir, now: int) -> None:
        # §7.1: depth counts ITEMs and pushes out the oldest one (an honest gap). PLUCKs are
        # tombstones: never evicted before their target's expiry, capped separately in hush().
        if oa.kind == wire.KIND_ITEM:
            items = [s for s, o in st.ring.items() if o.kind == wire.KIND_ITEM]
            while len(items) >= self.depth:
                del st.ring[items.pop(0)]
        st.ring[oa.seq] = oa
        oa.loop_ms, oa.clamp = self._loop(st, oa, now, admission=True)
        # never shed: plucks, control and alarm frames (§12.3 never-shed rules)
        oa.shed = oa.clamp == "degraded" and oa.kind == wire.KIND_ITEM and CLASSES[oa.cls].name not in NEVER_SHED
        oa.burst = [now] + [now + d for d in BURST_OFFSETS_MS if now + d < oa.expires_at - STOP_BEFORE_EXPIRY_MS]

    # ------------------------------------------------------------ carousel

    def _forget_keys(self, now_ms: int) -> None:
        """Drop class entries no receiver can still hold a mark for (§7.8). Cost follows what expires."""
        while self._key_due and self._key_due[0][0] <= now_ms:
            forget_at, stream, key = heapq.heappop(self._key_due)
            held = self.streams[stream].key_classes.get(key)
            if held is not None and held[1] <= now_ms:
                del self.streams[stream].key_classes[key]

    def poll(self, now_ms: int) -> list[bytes]:
        """Frames due at ``now_ms``: beacons, bursts and loop repeats, in that order."""
        self._forget_keys(now_ms)
        out: list[bytes] = []
        if now_ms >= self.next_beacon_at:
            out.append(self._beacon(now_ms))
        for st in self.streams.values():
            for seq, oa in list(st.ring.items()):
                if oa.expires_at - now_ms < STOP_BEFORE_EXPIRY_MS:
                    del st.ring[seq]
                    continue
                if oa.refresh_at is not None and now_ms >= oa.refresh_at:
                    if now_ms < oa.horizon:
                        # keep provenance flags (WAKE_DERIVED above all) and add REFRESH (§7.9)
                        self.sing(now_ms, **{**oa.reissue, "flags": oa.reissue["flags"] | wire.Item.REFRESH},
                                  keep_on_air_s=(oa.horizon - now_ms) / 1000)
                        continue  # the refresh superseded this entry
                    oa.refresh_at = None
                if oa.burst and now_ms >= oa.burst[0]:
                    while oa.burst and now_ms >= oa.burst[0]:
                        oa.burst.pop(0)
                    self._send(st, oa, now_ms, out)
                    continue
                if oa.burst:
                    continue
                if oa.next_at is None:
                    self._schedule(st, oa, now_ms)
                if now_ms >= oa.next_at:
                    # reconsideration (RFC 2974 §3.1): recompute with the current live set
                    if oa.shed:
                        oa.next_at = oa.expires_at  # attenuation: stop repeating (§12.3 ladder, simplified)
                        continue
                    oa.loop_ms, _ = self._loop(st, oa, now_ms)
                    due = oa.last_sent + int(oa.loop_ms * oa.u)
                    if due <= now_ms:
                        self._send(st, oa, now_ms, out)
                    else:
                        oa.next_at = due
        return out

    def _send(self, st: _Stream, oa: _OnAir, now: int, out: list) -> None:
        out.append(oa.frame)
        oa.last_sent = now
        oa.next_at = None
        if not oa.burst:
            self._schedule(st, oa, now)

    def _schedule(self, st: _Stream, oa: _OnAir, now: int) -> None:
        oa.loop_ms, _ = self._loop(st, oa, now)
        oa.u = self.rng.uniform(2 / 3, 4 / 3)
        base = oa.last_sent if oa.last_sent is not None else now
        oa.next_at = base + int(oa.loop_ms * oa.u)

    def next_due(self) -> int:
        """Earliest time ``poll`` has work (callers may poll earlier)."""
        t = self.next_beacon_at
        for st in self.streams.values():
            for oa in st.ring.values():
                cands = [oa.expires_at - STOP_BEFORE_EXPIRY_MS]
                if oa.burst:
                    cands.append(oa.burst[0])
                elif oa.next_at is not None:
                    cands.append(oa.next_at)
                if oa.refresh_at is not None:
                    cands.append(oa.refresh_at)
                t = min(t, *cands)
        return t

    # ------------------------------------------------------------ beacon

    def _entries(self) -> list[wire.StreamEntry]:
        out = []
        for st in self.streams.values():
            loops = [oa.loop_ms for oa in st.ring.values()]
            out.append(wire.StreamEntry(
                stream_id=st.sid, head_seq=st.head_seq, live=len(st.ring),
                loop_ms=int(statistics.median(loops)) if loops else 0, loop_max_ms=max(loops) if loops else 0,
                default_ttl_s=int(st.cfg.default_ttl_s), max_ttl_s=int(st.cfg.max_ttl_s),
                b_stream=st.cfg.b_stream, lens=st.cfg.lens))
        return out

    def catalog_digest(self) -> bytes:
        cat = [[st.sid, int(st.cfg.default_ttl_s), int(st.cfg.max_ttl_s), st.cfg.b_stream]
               for st in self.streams.values()]
        return hashlib.sha256(cbor.encode(cat)).digest()[:8]

    def _beacon(self, now_ms: int, goodbye: bool = False) -> bytes:
        self.bseq += 1
        nxt = 0 if goodbye else int(self.beacon_period_ms * self.rng.uniform(0.9, 1.1))
        entries = self._entries()
        page = digest = None
        if len(entries) > BEACON_ENTRIES_PER_PAGE:
            pages = [entries[i:i + BEACON_ENTRIES_PER_PAGE] for i in range(0, len(entries), BEACON_ENTRIES_PER_PAGE)]
            idx = self.page_index % len(pages)
            self.page_index += 1
            page, digest, entries = (idx, len(pages)), self.catalog_digest(), pages[idx]
        b = wire.Beacon(epoch=self.epoch, bseq=self.bseq, wallclock=now_ms, next_beacon_ms=nxt, profile=PROFILE,
                        streams=tuple(entries), b_station=self.b_station, page=page, catalog_digest=digest)
        self.next_beacon_at = now_ms + nxt
        self._next_beacon_ms = nxt
        return wire.encode_beacon(self.sk, b)

    def goodbye(self, now_ms: int) -> bytes:
        """A final beacon with next_beacon_ms = 0 (§8.3)."""
        return self._beacon(now_ms, goodbye=True)

    # ------------------------------------------------------------ status

    def status(self, now_ms: int) -> dict:
        return {
            "key_id": self.key_id.hex(), "epoch": self.epoch, "b_station": self.b_station,
            "streams": {
                name: {"stream_id": f"{st.sid:08x}", "head_seq": st.head_seq, "b_stream": st.cfg.b_stream,
                       "default_ttl_s": st.cfg.default_ttl_s, "max_ttl_s": st.cfg.max_ttl_s,
                       "on_air": [{"seq": oa.seq, "kind": "pluck" if oa.kind == wire.KIND_PLUCK else "item",
                                   "state_key": oa.state_key, "remaining_s": round((oa.expires_at - now_ms) / 1000, 1),
                                   "loop_ms": oa.loop_ms, "clamp": oa.clamp, "size": len(oa.frame)}
                                  for oa in st.ring.values()]}
                for name, st in self.streams.items()},
        }


def _now() -> int:
    return time.time_ns() // 1_000_000
