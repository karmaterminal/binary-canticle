"""Frame v2: fixed header, deterministic CBOR map, Ed25519 trailer (RFC-0001 §9).

``encode_*`` build and sign frames once; loops resend the returned bytes.
``parse`` is the strict admission path. It never raises anything but
``Reject``, whatever the input, so one bad datagram cannot stop a receiver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from . import cbor
from .ids import CLASSES, key_id

MAGIC = b"BC"
VERSION = 2
KIND_ITEM, KIND_BEACON, KIND_PLUCK = 0x01, 0x02, 0x03
HEADER_LEN = 12
SIG_LEN = 64
MAX_DATAGRAM = 1200
MAX_FRAME = 1100
SIGN_DOMAIN = b"binary-canticle/frame/v2\x00"
# Ed25519 group order; signatures with S >= L are rejected (§9.3).
ED25519_L = 2**252 + 27742317777372353535851937790883648493
FUTURE_SKEW_MS = 5_000
MAX_CLAMP_TTL_S = max(c.max_ttl_s for c in CLASSES.values())

KEYED_CLASSES = {c.code for c in CLASSES.values() if c.keyed}
_UNDERSTOOD = {
    KIND_ITEM: set(range(0, 19)),
    KIND_PLUCK: {0, 1, 2, 3, 4, 5, 13, 20, 21},
    KIND_BEACON: set(range(0, 12)),
}


class Reject(Exception):
    """A datagram was not admitted. ``reason`` is the evidence name."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


Tuple = tuple  # (key_id: bytes, epoch: int, stream: int, seq: int)


@dataclass(frozen=True)
class Item:
    epoch: int
    stream: int
    seq: int
    issued_at: int
    expires_at: int
    cls: int
    ctype: int | str
    body: Optional[bytes] = None
    body_ref: Optional[tuple] = None  # (url, sha256, size)
    state_key: Optional[str] = None
    hop: int = 0
    derived_from: tuple = ()
    scope: int = 1
    intensity: Optional[int] = None
    flags: int = 0
    purpose: Optional[str] = None
    root: Optional[tuple] = None
    lens: Optional[int] = None
    extra: dict = field(default_factory=dict, compare=False)

    REFRESH, WAKE_DERIVED, EXERCISE, TRAINING_ELIGIBLE = 1, 2, 4, 8


@dataclass(frozen=True)
class Pluck:
    epoch: int
    stream: int
    seq: int
    issued_at: int
    expires_at: int
    scope: int
    target_seq: int
    reason: Optional[int] = None
    extra: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class StreamEntry:
    stream_id: int
    head_seq: int
    live: int
    loop_ms: int
    loop_max_ms: int
    default_ttl_s: int
    max_ttl_s: int
    b_stream: int
    lens: Optional[int] = None

    def to_cbor(self) -> list:
        out = [self.stream_id, self.head_seq, self.live, self.loop_ms, self.loop_max_ms,
               self.default_ttl_s, self.max_ttl_s, self.b_stream]
        return out + [self.lens] if self.lens is not None else out


@dataclass(frozen=True)
class Beacon:
    epoch: int
    bseq: int
    wallclock: int
    next_beacon_ms: int
    profile: str
    streams: tuple
    b_station: int
    page: Optional[tuple] = None
    catalog_digest: Optional[bytes] = None
    capsid: Optional[dict] = None
    relay: Optional[dict] = None
    extra: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Frame:
    kind: int
    key_id: bytes
    body: Item | Pluck | Beacon
    raw: bytes

    @property
    def identity(self) -> Optional[Tuple]:
        """(key_id, epoch, stream, seq) for ITEM and PLUCK (§5.6)."""
        if self.kind == KIND_BEACON:
            return None
        b = self.body
        return (self.key_id, b.epoch, b.stream, b.seq)


# ---------------------------------------------------------------- encoding

def public_key_bytes(sk: Ed25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def item_map(it: Item) -> dict:
    m = {1: it.epoch, 2: it.stream, 3: it.seq, 4: it.issued_at, 5: it.expires_at,
         6: it.cls, 7: it.ctype, 11: it.hop, 13: it.scope}
    if it.body is not None:
        m[8] = it.body
    if it.body_ref is not None:
        m[9] = list(it.body_ref)
    if it.state_key is not None:
        m[10] = it.state_key
    if it.derived_from:
        m[12] = [list(t) for t in it.derived_from]
    if it.intensity is not None:
        m[14] = it.intensity
    if it.flags:
        m[15] = it.flags
    if it.purpose is not None:
        m[16] = it.purpose
    if it.root is not None:
        m[17] = list(it.root)
    if it.lens is not None:
        m[18] = it.lens
    m.update(it.extra)
    return m


def pluck_map(p: Pluck) -> dict:
    m = {1: p.epoch, 2: p.stream, 3: p.seq, 4: p.issued_at, 5: p.expires_at, 13: p.scope, 20: p.target_seq}
    if p.reason is not None:
        m[21] = p.reason
    m.update(p.extra)
    return m


def beacon_map(b: Beacon) -> dict:
    m = {1: b.epoch, 2: b.bseq, 3: b.wallclock, 4: b.next_beacon_ms, 5: b.profile,
         6: [s.to_cbor() for s in b.streams], 8: b.b_station}
    if b.page is not None:
        m[7] = list(b.page)
    if b.catalog_digest is not None:
        m[9] = b.catalog_digest
    if b.capsid is not None:
        m[10] = b.capsid
    if b.relay is not None:
        m[11] = b.relay
    m.update(b.extra)
    return m


def sign_frame(kind: int, sk: Ed25519PrivateKey, fields: dict) -> bytes:
    """Encode and sign once (§7.2, §9.3). Raises ValueError above 1 100 bytes."""
    unsigned = MAGIC + bytes([VERSION, kind]) + key_id(public_key_bytes(sk)) + cbor.encode(fields)
    frame = unsigned + sk.sign(SIGN_DOMAIN + unsigned)
    if len(frame) > MAX_FRAME:
        raise ValueError(f"frame is {len(frame)} bytes; the canonical limit is {MAX_FRAME}")
    return frame


def encode_item(sk: Ed25519PrivateKey, it: Item) -> bytes:
    return sign_frame(KIND_ITEM, sk, item_map(it))


def encode_pluck(sk: Ed25519PrivateKey, p: Pluck) -> bytes:
    return sign_frame(KIND_PLUCK, sk, pluck_map(p))


def encode_beacon(sk: Ed25519PrivateKey, b: Beacon) -> bytes:
    return sign_frame(KIND_BEACON, sk, beacon_map(b))


# ---------------------------------------------------------------- parsing

def _uint(v, name, maximum=2**64 - 1):
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= maximum:
        raise Reject("bad-field", name)
    return v


def _tstr(v, name, lo=0, hi=None):
    if not isinstance(v, str) or not lo <= len(v.encode()) <= (hi if hi is not None else 1 << 20):
        raise Reject("bad-field", name)
    return v


def _tuple(v, name):
    if (not isinstance(v, list) or len(v) != 4 or not isinstance(v[0], bytes) or len(v[0]) != 8):
        raise Reject("bad-field", name)
    return (v[0], _uint(v[1], name, 2**32 - 1), _uint(v[2], name, 2**32 - 1), _uint(v[3], name))


def _require(m, keys, kind_name):
    missing = [k for k in keys if k not in m]
    if missing:
        raise Reject("missing-field", f"{kind_name} keys {missing}")


def _item(m: dict) -> Item:
    _require(m, (1, 2, 3, 4, 5, 6, 7, 11, 13), "ITEM")
    if 8 not in m and 9 not in m:
        raise Reject("missing-field", "ITEM needs body (8) or body_ref (9)")
    ctype = m[7]
    if isinstance(ctype, str):
        _tstr(ctype, "ctype", 1, 64)
    else:
        _uint(ctype, "ctype", 0xFFFF)
    body = m.get(8)
    if body is not None and not isinstance(body, bytes):
        raise Reject("bad-field", "body")
    body_ref = None
    if 9 in m:
        br = m[9]
        if not (isinstance(br, list) and len(br) == 3 and isinstance(br[1], bytes) and len(br[1]) == 32):
            raise Reject("bad-field", "body_ref")
        body_ref = (_tstr(br[0], "body_ref.url", 1, 200), br[1], _uint(br[2], "body_ref.size"))
    cls = _uint(m[6], "class", 0xFFFF)
    state_key = _tstr(m[10], "state_key", 1, 32) if 10 in m else None
    if cls in KEYED_CLASSES and state_key is None:
        raise Reject("missing-field", "state_key required for keyed classes")
    derived = ()
    if 12 in m:
        if not isinstance(m[12], list) or len(m[12]) > 4:
            raise Reject("bad-field", "derived_from")
        derived = tuple(_tuple(t, "derived_from") for t in m[12])
        if 17 not in m:
            raise Reject("missing-field", "root required with derived_from")
    flags = _uint(m.get(15, 0), "flags", 0xFFFF)
    if flags >> 4:
        raise Reject("bad-field", "flags bits 4-15 must be 0")
    it = Item(
        epoch=_uint(m[1], "epoch", 2**32 - 1), stream=_uint(m[2], "stream", 2**32 - 1),
        seq=_uint(m[3], "seq"), issued_at=_uint(m[4], "issued_at"), expires_at=_uint(m[5], "expires_at"),
        cls=cls, ctype=ctype, body=body, body_ref=body_ref, state_key=state_key,
        hop=_uint(m[11], "hop", 15), derived_from=derived, scope=_uint(m[13], "scope", 3),
        intensity=_uint(m[14], "intensity", 255) if 14 in m else None, flags=flags,
        purpose=_tstr(m[16], "purpose", 0, 128) if 16 in m else None,
        root=_tuple(m[17], "root") if 17 in m else None,
        lens=_uint(m[18], "lens", 0xFFFF) if 18 in m else None,
        extra={k: v for k, v in m.items() if k not in _UNDERSTOOD[KIND_ITEM]},
    )
    if it.expires_at <= it.issued_at:
        raise Reject("bad-field", "expires_at must be after issued_at")
    return it


def _pluck(m: dict) -> Pluck:
    _require(m, (1, 2, 3, 4, 5, 13, 20), "PLUCK")
    p = Pluck(
        epoch=_uint(m[1], "epoch", 2**32 - 1), stream=_uint(m[2], "stream", 2**32 - 1),
        seq=_uint(m[3], "seq"), issued_at=_uint(m[4], "issued_at"), expires_at=_uint(m[5], "expires_at"),
        scope=_uint(m[13], "scope", 3), target_seq=_uint(m[20], "target_seq"),
        reason=_uint(m[21], "reason", 2) if 21 in m else None,
        extra={k: v for k, v in m.items() if k not in _UNDERSTOOD[KIND_PLUCK]},
    )
    if p.expires_at <= p.issued_at or p.target_seq >= p.seq:
        raise Reject("bad-field", "pluck times or target")
    return p


def _beacon(m: dict) -> Beacon:
    _require(m, (1, 2, 3, 4, 5, 6, 8), "BEACON")
    if not isinstance(m[6], list):
        raise Reject("bad-field", "streams")
    entries = []
    for e in m[6]:
        if not isinstance(e, list) or len(e) not in (8, 9):
            raise Reject("bad-field", "stream-entry")
        vals = [_uint(v, "stream-entry") for v in e]
        entries.append(StreamEntry(*vals))
    page = None
    if 7 in m:
        pg = m[7]
        if not (isinstance(pg, list) and len(pg) == 2):
            raise Reject("bad-field", "page")
        page = (_uint(pg[0], "page"), _uint(pg[1], "page", 8))
        if page[0] >= page[1]:
            raise Reject("bad-field", "page index")
    digest = m.get(9)
    if digest is not None and not (isinstance(digest, bytes) and len(digest) == 8):
        raise Reject("bad-field", "catalog_digest")
    for k in (10, 11):
        if k in m and not isinstance(m[k], dict):
            raise Reject("bad-field", "capsid" if k == 10 else "relay")
    return Beacon(
        epoch=_uint(m[1], "epoch", 2**32 - 1), bseq=_uint(m[2], "bseq"), wallclock=_uint(m[3], "wallclock"),
        next_beacon_ms=_uint(m[4], "next_beacon_ms"), profile=_tstr(m[5], "profile", 1, 32),
        streams=tuple(entries), b_station=_uint(m[8], "b_station"), page=page, catalog_digest=digest,
        capsid=m.get(10), relay=m.get(11),
        extra={k: v for k, v in m.items() if k not in _UNDERSTOOD[KIND_BEACON]},
    )


def local_expiry_ms(it: Item | Pluck, clock_offset_ms: int = 0, first_heard_ms: Optional[int] = None) -> int:
    """Receiver-clock expiry (§14.6.3):
    ``min(expires_eff + δ̂, first_heard + (expires_eff − issued_at))``.

    ``expires_eff`` clamps to the class max TTL (§6.2). δ̂ (receiver minus station clock, §8.2)
    moves the station's expiry onto the receiver clock, and the TTL counted from first hearing caps
    it, so a wrong or lying station clock can never keep an item longer than its full TTL.

    A PLUCK does not carry its target's class, so it clamps to the largest class max TTL: its
    ``expires_at`` must equal its target's (§9.7), which cannot be later than that (#60).
    """
    if isinstance(it, Item):
        spec = CLASSES.get(it.cls)
        max_ttl_s = spec.max_ttl_s if spec else MAX_CLAMP_TTL_S
    else:
        max_ttl_s = MAX_CLAMP_TTL_S
    exp = min(it.expires_at, it.issued_at + max_ttl_s * 1000)
    local = exp + clock_offset_ms
    if first_heard_ms is not None:
        local = min(local, first_heard_ms + (exp - it.issued_at))
    return local


def parse(
    datagram: bytes,
    resolve: Callable[[bytes], Optional[Ed25519PublicKey]],
    now_ms: Optional[int] = None,
    clock_offset_ms: int = 0,
) -> Frame:
    """Admit one datagram or raise ``Reject``: size, header, key, CBOR, fields,
    time window, then signature (cheap checks first, §12.2)."""
    try:
        return _parse(bytes(datagram), resolve, now_ms, clock_offset_ms)
    except Reject:
        raise
    except Exception as e:  # defence in depth: nothing else may escape
        raise Reject("internal", type(e).__name__) from None


def _parse(buf, resolve, now_ms, clock_offset_ms):
    if len(buf) > MAX_DATAGRAM:
        raise Reject("oversize", f"{len(buf)} bytes")
    if len(buf) < HEADER_LEN + 1 + SIG_LEN:
        raise Reject("short")
    if buf[0:2] != MAGIC:
        raise Reject("bad-magic")
    if buf[2] != VERSION:
        raise Reject("bad-version", str(buf[2]))
    kind = buf[3]
    if kind not in _UNDERSTOOD:
        raise Reject("unsupported-kind", f"{kind:#04x}")
    if len(buf) > MAX_FRAME:
        raise Reject("oversize", f"frame {len(buf)} > {MAX_FRAME}")
    kid = buf[4:12]
    public_key = resolve(kid)
    if public_key is None:
        raise Reject("unknown-key", kid.hex())
    raw_map = buf[HEADER_LEN:-SIG_LEN]
    try:
        m = cbor.decode(raw_map)
    except cbor.CborError as e:
        if e.reason in ("map-key-order", "non-shortest", "indefinite-length", "duplicate-key"):
            raise Reject("non-deterministic", e.reason) from None
        raise Reject("bad-cbor", e.reason) from None
    if not isinstance(m, dict) or not all(isinstance(k, int) for k in m):
        raise Reject("bad-cbor", "top level must be an integer-keyed map")
    if cbor.encode(m) != raw_map:
        raise Reject("non-deterministic")
    if 0 in m:
        crit = m[0]
        if not isinstance(crit, list) or not all(isinstance(k, int) and not isinstance(k, bool) for k in crit):
            raise Reject("bad-field", "crit")
        unknown = [k for k in crit if k not in _UNDERSTOOD[kind]]
        if unknown:
            raise Reject("crit-unknown", str(unknown))
    body = {KIND_ITEM: _item, KIND_PLUCK: _pluck, KIND_BEACON: _beacon}[kind](m)
    if now_ms is not None and kind != KIND_BEACON:
        if body.issued_at > now_ms - clock_offset_ms + FUTURE_SKEW_MS:
            raise Reject("not-yet-valid")
        if local_expiry_ms(body, clock_offset_ms) <= now_ms:
            raise Reject("expired")
    sig = buf[-SIG_LEN:]
    if int.from_bytes(sig[32:], "little") >= ED25519_L:
        raise Reject("bad-signature", "non-canonical S")
    try:
        public_key.verify(sig, SIGN_DOMAIN + buf[:-SIG_LEN])
    except InvalidSignature:
        raise Reject("bad-signature") from None
    return Frame(kind=kind, key_id=kid, body=body, raw=buf)
