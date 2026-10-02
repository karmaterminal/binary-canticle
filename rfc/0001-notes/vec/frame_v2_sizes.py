"""Illustrative size/test-vector calculator for RFC-0001 frame v2 (non-normative).

Layout: magic "BC" | version 0x02 | kind | key_id(8) | det-CBOR map (int keys) | Ed25519 sig(64)
Signed bytes: b"binary-canticle/frame/v2\x00" || header || cbor
"""
import hashlib
import cbor2
from nacl.signing import SigningKey

DOMAIN = b"binary-canticle/frame/v2\x00"
MAGIC = b"BC\x02"
KIND_ITEM, KIND_BEACON, KIND_PLUCK = 0x01, 0x02, 0x03

# RFC 8032 section 7.1 TEST 1 secret key (public, well-known test key)
SK = SigningKey(bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"))
PK = bytes(SK.verify_key)
KID = hashlib.sha256(PK).digest()[:8]


def det(m):
    return cbor2.dumps(m, canonical=True)


def frame(kind, m):
    head = MAGIC + bytes([kind]) + KID
    body = det(m)
    sig = SK.sign(DOMAIN + head + body).signature
    return head + body + sig, len(head), len(body)


def item(body: bytes, ctype, extra=None):
    m = {1: 7, 2: 0x1A2B3C4D, 3: 42, 4: 1_790_000_000_000, 5: 1_790_000_060_000,
         6: 1, 7: ctype, 8: body, 11: 0, 13: 1}
    if extra:
        m.update(extra)
    return frame(KIND_ITEM, m)


if __name__ == "__main__":
    print("public key", PK.hex())
    print("key_id    ", KID.hex())
    f, h, b = item(b"x" * 600, "text/plain;charset=utf-8")
    print("600B body, text ctype: total", len(f), "header", h, "cbor", b, "sig 64")
    f, h, b = item(b"x" * 600, 1)
    print("600B body, registered ctype=1: total", len(f))
    lineage = {12: [[KID, 7, 0x1A2B3C4D, 40]] * 4, 17: [KID, 7, 0x1A2B3C4D, 1], 10: "now", 16: "p" * 64}
    for n in range(800, 1100):
        f, _, _ = item(b"x" * n, "text/plain;charset=utf-8", lineage)
        if len(f) > 1100:
            print("max body with 4 lineage tuples + root + state_key + 64B purpose + text ctype:", n - 1)
            break
    for n in range(900, 1100):
        f, _, _ = item(b"x" * n, 1)
        if len(f) > 1100:
            print("max body minimal fields, registered ctype:", n - 1)
            break
    # stream-entry per RFC-0001 section 9.8 (trail_seq added by amendment A1):
    # [stream_id, head_seq, trail_seq, live, loop_ms, loop_max_ms, default_ttl_s, max_ttl_s, b_stream, ?lens]
    streams = [[0x1A2B3C00 + i, 100 + i, 98 + i, 3, 5000, 5000, 60, 300, 4000] for i in range(5)]
    bm = {1: 7, 2: 123456, 3: 1_790_000_000_000, 4: 1000, 5: "canticle-regulation/1", 6: streams, 8: 16000}
    f, h, b = frame(KIND_BEACON, bm)
    print("beacon 5 streams:", len(f), "per-stream entry bytes ~", len(det(streams[0])))
    # Worst case at the bounds the section 9.8 CDDL allows: u64 bseq, wallclock, head_seq and trail_seq;
    # u32 everywhere else; a 32-byte profile; paging on. This is the A1 size proof.
    U32, U64 = 2**32 - 1, 2**64 - 1
    entry = [U32, U64, U64, U32, U32, U32, U32, U32, U32]
    fixed = {1: U32, 2: U64, 3: U64, 4: U32, 5: "p" * 32, 7: [7, 8], 8: U32, 9: b"\x00" * 8}
    # capsid in the suggested shape of section 8.7, every field at its largest, 32 buckets (section 9.4 cap)
    capsid = {1: U32, 2: U32, 3: {U32 - i: 3 for i in range(32)}, 4: b"\x00" * 32, 5: b"\x00" * 16}
    relay = {1: 2, 2: 2, 3: [[KID, U32]] * 32, 4: U32}

    def per_page(extra, e):
        n = 0
        while n < 32 and len(frame(KIND_BEACON, {**fixed, **extra, 6: [e] * (n + 1)})[0]) <= 1100:
            n += 1
        return n

    print("beacon worst case, no streams:", len(frame(KIND_BEACON, {**fixed, 6: []})[0]),
          "entry bytes", len(det(entry)), "with lens", len(det(entry + [U32])))
    for label, extra in (("no capsid", {}), ("worst capsid", {10: capsid})):
        a, b2 = per_page(extra, entry), per_page(extra, entry + [U32])
        print(f"beacon worst case, {label}: entries per page {a} (with lens {b2});"
              f" 8-page catalog floor {8 * a} ({8 * b2})")
    print("relay beacon worst case (32 relay entries, no streams):",
          len(frame(KIND_BEACON, {**fixed, 6: [], 11: relay})[0]))
    # aspect item (bio note section 6.2 CDDL), synthesis 512 B, 6 evidence refs
    ev=[[KID, 7, 0x1A2B3C4D, 1000+i] for i in range(6)]
    aspect={1:1,2:2,3:2,4:1,5:"s"*512,6:ev,7:{1:1_790_000_000_000,2:1_790_000_300_000,3:4,4:6},8:b"\x11"*32,9:3}
    ab=det(aspect)
    f,_,_=item(ab,4,{6:3,10:"now",12:[[KID,7,0x1A2B3C4D,40]],13:2,17:[KID,7,0x1A2B3C4D,1],18:1})
    print("aspect body", len(ab), "aspect frame", len(f))
    # tiny illustrative vector
    f, h, b = frame(KIND_ITEM, {1: 1, 2: 1, 3: 1, 4: 1_790_000_000_000, 5: 1_790_000_060_000,
                                6: 1, 7: 1, 8: b"hello, station", 11: 0, 13: 1})
    print("vector1 len", len(f))
    print("vector1 hex", f.hex())
    pl, _, _ = frame(KIND_PLUCK, {1: 1, 2: 1, 3: 2, 4: 1_790_000_005_000, 5: 1_790_000_060_000, 13: 1, 20: 1})
    print("pluck len", len(pl))
    print("pluck hex", pl.hex())
