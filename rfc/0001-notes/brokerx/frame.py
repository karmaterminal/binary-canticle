"""Minimal canticle frame v2 sketch used by the broker control experiment.

magic b"BC" | version 0x02 | det-CBOR map with integer keys | key_id (8 B) | Ed25519 sig (64 B)
The signature covers everything before it. Loops re-send these exact bytes.
"""
import hashlib, time
import cbor2
from nacl.signing import SigningKey, VerifyKey

MAGIC = b"BC\x02"
K_EPOCH, K_STREAM, K_SEQ, K_ISSUED, K_EXPIRES, K_CLASS, K_KEY, K_BODY, K_LOOP = range(1, 10)


def key_id(vk: VerifyKey) -> bytes:
    return hashlib.sha256(bytes(vk)).digest()[:8]


def encode(sk: SigningKey, epoch: int, stream: int, seq: int, ttl_s: float, body: bytes,
           cls: int = 1, key: str | None = None, loop_ms: int = 1000, now_ms: int | None = None) -> bytes:
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    m = {K_EPOCH: epoch, K_STREAM: stream, K_SEQ: seq, K_ISSUED: now_ms,
         K_EXPIRES: now_ms + int(ttl_s * 1000), K_CLASS: cls, K_BODY: body, K_LOOP: loop_ms}
    if key is not None:
        m[K_KEY] = key
    head = MAGIC + cbor2.dumps(m, canonical=True) + key_id(sk.verify_key)
    sig = sk.sign(head).signature
    out = head + sig
    assert len(out) <= 1100, len(out)
    return out


def decode(buf: bytes, trust: dict[bytes, VerifyKey]):
    """Return (key_id, map) or raise. trust maps key_id -> VerifyKey (the allowlist)."""
    if len(buf) < 3 + 8 + 64 or not buf.startswith(MAGIC):
        raise ValueError("bad magic")
    head, sig = buf[:-64], buf[-64:]
    kid = head[-8:]
    vk = trust.get(kid)
    if vk is None:
        raise PermissionError("unknown key")
    vk.verify(head, sig)  # raises BadSignatureError
    return kid, cbor2.loads(head[3:-8])
