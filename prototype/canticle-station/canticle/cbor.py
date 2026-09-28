"""Strict, bounded, deterministic CBOR for frame v2 (RFC-0001 §9.4).

Only the subset frame v2 needs is supported: unsigned and negative integers,
byte strings, UTF-8 text strings, arrays, maps, false, true and null. The
encoder emits RFC 8949 §4.2.1 core deterministic encoding. The decoder
accepts nothing else: definite lengths only, shortest-form heads, map keys in
strictly increasing bytewise order of their encodings (so no duplicates), no
floats, no tags, bounded depth and entry counts, and no trailing bytes.

The spike rejects floats and tags everywhere. RFC-0001 only forbids them
under core keys 1-31, so this is stricter than the RFC.
"""

from __future__ import annotations

MAX_DEPTH = 4
MAX_ENTRIES = 32


class CborError(ValueError):
    """Input is not strict deterministic CBOR within the frame v2 subset."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 0x100:
        return bytes([(major << 5) | 24, value])
    if value < 0x10000:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value < 0x100000000:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    if value < 0x10000000000000000:
        return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")
    raise CborError("int-range")


def encode(obj) -> bytes:
    if obj is False:
        return b"\xf4"
    if obj is True:
        return b"\xf5"
    if obj is None:
        return b"\xf6"
    if isinstance(obj, int):
        return _head(0, obj) if obj >= 0 else _head(1, -1 - obj)
    if isinstance(obj, (bytes, bytearray)):
        return _head(2, len(obj)) + bytes(obj)
    if isinstance(obj, str):
        raw = obj.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(obj, (list, tuple)):
        return _head(4, len(obj)) + b"".join(encode(x) for x in obj)
    if isinstance(obj, dict):
        items = sorted(((encode(k), encode(v)) for k, v in obj.items()), reverse=True)  # CI proof: deliberately wrong map-key order; reverted by the next commit
        for a, b in zip(items, items[1:]):
            if a[0] == b[0]:
                raise CborError("duplicate-key")
        return _head(5, len(items)) + b"".join(k + v for k, v in items)
    raise CborError(f"unsupported-type:{type(obj).__name__}")


class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0

    def take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.buf):
            raise CborError("truncated")
        out = self.buf[self.pos:end]
        self.pos = end
        return out

    def head(self) -> tuple[int, int, int]:
        start = self.pos
        ib = self.take(1)[0]
        major, ai = ib >> 5, ib & 0x1F
        if major == 7:
            if ai in (20, 21, 22):
                return major, ai, start
            raise CborError("float-or-simple")
        if major == 6:
            raise CborError("tag")
        if ai < 24:
            return major, ai, start
        if ai == 31:
            raise CborError("indefinite-length")
        if ai > 27:
            raise CborError("reserved-additional-info")
        size = 1 << (ai - 24)
        value = int.from_bytes(self.take(size), "big")
        minimum = 24 if size == 1 else 1 << (8 * size // 2)
        if value < minimum:
            raise CborError("non-shortest")
        return major, value, start


def _decode(r: _Reader, depth: int):
    major, value, start = r.head()
    if major == 0:
        return value
    if major == 1:
        return -1 - value
    if major == 2:
        return r.take(value)
    if major == 3:
        try:
            return r.take(value).decode("utf-8")
        except UnicodeDecodeError:
            raise CborError("bad-utf8") from None
    if major == 7:
        return {20: False, 21: True, 22: None}[value]
    if depth >= MAX_DEPTH:
        raise CborError("depth")
    if value > MAX_ENTRIES:
        raise CborError("too-many-entries")
    if major == 4:
        return [_decode(r, depth + 1) for _ in range(value)]
    out = {}
    prev = None
    for _ in range(value):
        kstart = r.pos
        key = _decode(r, depth + 1)
        kbytes = r.buf[kstart:r.pos]
        if prev is not None and kbytes <= prev:
            raise CborError("map-key-order")
        prev = kbytes
        if isinstance(key, (list, dict)):
            raise CborError("complex-key")
        out[key] = _decode(r, depth + 1)
    return out


def decode(buf: bytes):
    """Decode exactly one strict deterministic CBOR item filling ``buf``."""
    r = _Reader(bytes(buf))
    obj = _decode(r, 0)
    if r.pos != len(r.buf):
        raise CborError("trailing-bytes")
    return obj
