"""Station identity, stream ids and the class registry (RFC-0001 §5, §6.2)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_SEGMENT = r"[a-z][a-z0-9-]{0,30}"
STATION_NAME_RE = re.compile(rf"^{_SEGMENT}$")
STREAM_NAME_RE = re.compile(rf"^{_SEGMENT}(\.{_SEGMENT}){{0,3}}$")


def key_id(public_key: bytes) -> bytes:
    """SHA-256(public key)[0:8] (§5.1)."""
    if len(public_key) != 32:
        raise ValueError("Ed25519 public keys are 32 bytes")
    return hashlib.sha256(public_key).digest()[:8]


# edwards25519 (RFC 8032 §5.1): field prime, curve constant d, and sqrt(-1).
_P = 2**255 - 19
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _ed_add(a: tuple, b: tuple) -> tuple:
    (x1, y1), (x2, y2) = a, b
    t = _D * x1 * x2 * y1 * y2 % _P
    return ((x1 * y2 + x2 * y1) * pow(1 + t, _P - 2, _P) % _P,
            (y1 * y2 + x1 * x2) * pow(1 - t, _P - 2, _P) % _P)


def check_public_key(public_key: bytes) -> bytes:
    """Refuse an Ed25519 public key that is not a canonical encoding of a curve point, or that is
    a small-order point (§9.3: verifiers SHOULD refuse small-order keys when loading the manifest).

    Under a small-order key, a forged signature verifies for a fraction of messages, so anyone could
    sign as that key-id. Decoding follows RFC 8032 §5.1.3; the order test is [8]A = identity.
    """
    if len(public_key) != 32:
        raise ValueError("an Ed25519 public key is 32 bytes")
    y = int.from_bytes(public_key, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    if y >= _P:
        raise ValueError("not a canonical encoding (y >= p)")
    u, v = (y * y - 1) % _P, (_D * y * y + 1) % _P
    x = u * pow(v, 3, _P) * pow(u * pow(v, 7, _P), (_P - 5) // 8, _P) % _P
    if v * x * x % _P == (-u) % _P:
        x = x * _SQRT_M1 % _P
    elif v * x * x % _P != u:
        raise ValueError("not a point on edwards25519")
    if x == 0 and sign:
        raise ValueError("not a valid encoding (x = 0 with the sign bit set)")
    # The sign bit only picks x or -x, and [8](-A) = -[8]A, so the order test does not need it applied.
    pt = (x, y)
    for _ in range(3):
        pt = _ed_add(pt, pt)
    if pt == (0, 1):
        raise ValueError("a small-order point: forged signatures can verify under it (§9.3)")
    return public_key


def check_stream_name(name: str) -> str:
    if len(name.encode()) > 64 or not STREAM_NAME_RE.match(name):
        raise ValueError(f"invalid stream name {name!r}: up to 4 dot-joined segments of [a-z][a-z0-9-]{{0,30}}, 64 bytes max")
    return name


def stream_id(name: str) -> int:
    """First 4 bytes, big-endian, of SHA-256("canticle-stream/v2" || 0x00 || name) (§5.4)."""
    check_stream_name(name)
    digest = hashlib.sha256(b"canticle-stream/v2\x00" + name.encode()).digest()
    return int.from_bytes(digest[:4], "big")


def stream_ids(names) -> dict[int, str]:
    """Map names to ids, refusing collisions (§5.4, closes #38): rename, never rehash."""
    out: dict[int, str] = {}
    for name in names:
        sid = stream_id(name)
        if sid in out and out[sid] != name:
            raise ValueError(f"stream_id collision: {out[sid]!r} and {name!r} both map to {sid:#010x}; rename one")
        out[sid] = name
    return out


@dataclass(frozen=True)
class ClassSpec:
    code: int
    name: str
    default_ttl_s: int
    max_ttl_s: int
    loop_floor_ms: int
    hop_limit: int
    keyed: bool          # state_key REQUIRED
    wake_eligible: bool  # v1: alarm only, and gated (§14.10)


CLASSES: dict[int, ClassSpec] = {
    c.code: c
    for c in (
        ClassSpec(1, "chatter", 60, 300, 5_000, 2, False, False),
        ClassSpec(2, "ambient", 300, 3_600, 10_000, 2, False, False),
        ClassSpec(3, "live-state", 180, 900, 5_000, 2, True, False),
        ClassSpec(4, "advisory", 900, 3_600, 5_000, 1, False, False),
        ClassSpec(5, "finding-ref", 900, 86_400, 10_000, 1, False, False),
        ClassSpec(6, "regulatory", 600, 3_600, 5_000, 0, True, False),
        ClassSpec(7, "alarm", 900, 3_600, 2_000, 0, True, True),
        ClassSpec(8, "control", 600, 3_600, 1_000, 0, True, False),
        ClassSpec(9, "root", 3_600, 3_600, 30_000, 0, True, False),
    )
}
CLASS_BY_NAME = {c.name: c for c in CLASSES.values()}

# B_station overflow priority (§7.5): earlier scales down last.
CLASS_PRIORITY = ["control", "alarm", "live-state", "regulatory", "advisory", "finding-ref", "ambient", "chatter", "root"]

SCOPES = {"host": 0, "lan": 1, "fleet": 2, "public": 3}

# Content-type registry (§9.9).
CTYPES = {
    "text/plain; charset=utf-8": 1,
    "application/cbor": 2,
    "application/json": 3,
    "application/vnd.canticle.aspect+cbor": 4,
    "application/vnd.canticle.alarm+cbor": 5,
    "application/vnd.canticle.regulatory+cbor": 6,
    "application/vnd.canticle.root+cbor": 7,
    "application/vnd.canticle.digest-ref+cbor": 8,
    "application/vnd.canticle.disposition+cbor": 9,
    "application/vnd.canticle.control+cbor": 10,
}
