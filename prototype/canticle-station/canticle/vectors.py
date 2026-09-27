"""Candidate conformance vectors for frame v2 (RFC-0001 §9.13, #27, #48).

These are CANDIDATES: RFC-0001 makes vectors normative only once two
independent implementations generate and cross-check them. This codec does
reproduce the RFC's two illustrative vectors byte for byte (they came from a
separate cbor2-based script), which is the first cross-check.

Keys are RFC 8032 §7.1 test keys, so anyone can re-derive every signature.
"""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import cbor, wire
from .ids import CLASS_BY_NAME, stream_id
from .listener import Listener
from .manifest import Manifest, StationEntry

TEST1 = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"   # RFC 8032 TEST 1
TEST2 = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"   # RFC 8032 TEST 2
TEST3 = "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7"   # RFC 8032 TEST 3
UNKNOWN = hashlib.sha256(b"canticle-vectors/unknown-key").hexdigest()
NOW = 1_790_000_010_000
T0 = 1_790_000_000_000


def _sk(hexseed: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hexseed))


def keys() -> dict:
    out = {}
    for name, seed in (("test1", TEST1), ("test2", TEST2), ("test3-revoked", TEST3), ("unknown", UNKNOWN)):
        pub = wire.public_key_bytes(_sk(seed))
        out[name] = {"secret": seed, "public": pub.hex(), "key_id": wire.key_id(pub).hex()}
    return out


def manifest() -> Manifest:
    allc = frozenset(c.code for c in CLASS_BY_NAME.values() if c.name != "alarm")
    return Manifest([
        StationEntry("test1", wire.public_key_bytes(_sk(TEST1)), allc, ("chatter", "lens.threat", "root")),
        StationEntry("test2", wire.public_key_bytes(_sk(TEST2)), allc, ("chatter",)),
        StationEntry("test3", wire.public_key_bytes(_sk(TEST3)), allc, ("chatter",), revoked=True),
    ])


def _raw(kind: int, sk: Ed25519PrivateKey, map_bytes: bytes, kid: bytes | None = None) -> bytes:
    """Sign arbitrary map bytes, bypassing the encoder's checks (to build invalid frames)."""
    kid = kid if kid is not None else wire.key_id(wire.public_key_bytes(sk))
    unsigned = wire.MAGIC + bytes([wire.VERSION, kind]) + kid + map_bytes
    return unsigned + sk.sign(wire.SIGN_DOMAIN + unsigned)


def _item(kw: dict | None = None) -> dict:
    base = {1: 1, 2: stream_id("chatter"), 3: 1, 4: T0, 5: T0 + 60_000, 6: 1, 7: 1, 8: b"hello, station", 11: 0, 13: 1}
    base.update(kw or {})
    return {k: v for k, v in base.items() if v is not None}


def parse_cases() -> list[dict]:
    s1, s2, s3, su = _sk(TEST1), _sk(TEST2), _sk(TEST3), _sk(UNKNOWN)
    k1 = wire.key_id(wire.public_key_bytes(s1))
    rfc_v1 = wire.encode_item(s1, wire.Item(epoch=1, stream=1, seq=1, issued_at=T0, expires_at=T0 + 60_000,
                                            cls=1, ctype=1, body=b"hello, station", hop=0, scope=1))
    rfc_v2 = wire.encode_pluck(s1, wire.Pluck(epoch=1, stream=1, seq=2, issued_at=T0 + 5_000,
                                              expires_at=T0 + 60_000, scope=1, target_seq=1))
    beacon = wire.encode_beacon(s1, wire.Beacon(epoch=1, bseq=1, wallclock=NOW, next_beacon_ms=1000,
                                                profile="canticle-regulation/1", b_station=16000,
                                                streams=(wire.StreamEntry(stream_id("chatter"), 1, 1, 10000, 10000, 60, 300, 4000),)))
    tampered = bytearray(rfc_v1)
    tampered[rfc_v1.index(b"hello")] = ord("j")
    good_map = cbor.encode(_item())
    unsorted = bytes([0xAA]) + b"".join(cbor.encode(k) + cbor.encode(v) for k, v in sorted(_item().items(), reverse=True))
    nonshort = good_map.replace(b"\x01\x01\x02", b"\x01\x18\x01\x02", 1)  # epoch 1 as 0x18 0x01
    sig = rfc_v1[-64:]
    s_int = int.from_bytes(sig[32:], "little") + wire.ED25519_L
    noncanon = rfc_v1[:-32] + s_int.to_bytes(32, "little") if s_int < 2**256 else rfc_v1
    big_body = wire.sign_frame(wire.KIND_ITEM, s1, _item({8: b"x" * 980}))
    pad = 1101 - len(big_body)
    oversize = _raw(wire.KIND_ITEM, s1, cbor.encode(_item({8: b"x" * (980 + pad)})))
    depth_map = bytes([0xAA]) + b"".join(
        cbor.encode(k) + (b"\x81" * 10 + b"\x00" if k == 8 else cbor.encode(v)) for k, v in sorted(_item().items()))
    float_map = bytes([0xAA]) + b"".join(
        cbor.encode(k) + (b"\xf9\x3c\x00" if k == 1 else cbor.encode(v)) for k, v in sorted(_item().items()))
    wrong_key = _raw(wire.KIND_ITEM, s2, good_map, kid=k1)
    cases = [
        ("rfc-vector-1-item", rfc_v1, "accept", "RFC-0001 §9.13 vector 1"),
        ("rfc-vector-2-pluck", rfc_v2, "accept", "RFC-0001 §9.13 vector 2"),
        ("valid-beacon", beacon, "accept", ""),
        ("valid-item-named-stream", wire.sign_frame(wire.KIND_ITEM, s1, _item()), "accept", "stream_id('chatter')"),
        ("unknown-extension-key-ignored", wire.sign_frame(wire.KIND_ITEM, s1, _item({40: "x"})), "accept", "§9.5"),
        ("wrong-key", wrong_key, "bad-signature", "signed by test2 under test1's key-id"),
        ("tampered", bytes(tampered), "bad-signature", "one body byte changed after signing"),
        ("non-canonical-s", noncanon, "bad-signature", "S + L"),
        ("unknown-key", wire.sign_frame(wire.KIND_ITEM, su, _item()), "unknown-key", "key-id not in manifest"),
        ("revoked-key", wire.sign_frame(wire.KIND_ITEM, s3, _item()), "revoked-key", ""),
        ("expired", wire.sign_frame(wire.KIND_ITEM, s1, _item({4: T0 - 120_000, 5: T0 - 60_000})), "expired", ""),
        ("not-yet-valid", wire.sign_frame(wire.KIND_ITEM, s1, _item({4: NOW + 6_000, 5: NOW + 66_000})), "not-yet-valid", "> 5 s ahead"),
        ("ttl-clamped-not-rejected", wire.sign_frame(wire.KIND_ITEM, s1, _item({5: T0 + 10_000_000})), "accept", "receivers clamp to class max TTL"),
        ("non-deterministic-key-order", _raw(wire.KIND_ITEM, s1, unsorted), "non-deterministic", "validly signed, keys unsorted"),
        ("non-deterministic-non-shortest", _raw(wire.KIND_ITEM, s1, nonshort), "non-deterministic", "validly signed"),
        ("crit-unknown", wire.sign_frame(wire.KIND_ITEM, s1, _item({0: [99], 99: 1})), "crit-unknown", "§9.5"),
        ("frame-1101-bytes", oversize, "oversize", f"{len(oversize)} bytes"),
        ("datagram-1201-bytes", b"BC" + bytes(1199), "oversize", ""),
        ("depth-bomb", _raw(wire.KIND_ITEM, s1, depth_map), "bad-cbor", "10 nested arrays"),
        ("float-in-core-key", _raw(wire.KIND_ITEM, s1, float_map), "bad-cbor", "epoch as half-float 1.0"),
        ("missing-state-key", wire.sign_frame(wire.KIND_ITEM, s1, _item({6: 3})), "missing-field", "live-state without state_key"),
        ("bad-version", b"BC\x03" + rfc_v1[3:], "bad-version", ""),
        ("prototype-b1-regression", b'{"a":1e400}', "short", "the 11-byte datagram that killed the prototype"),
    ]
    assert len(oversize) == 1101
    return [{"name": n, "datagram_hex": d.hex(), "expect": e, "note": note} for n, d, e, note in cases]


def sequence_cases() -> list[dict]:
    s1 = _sk(TEST1)
    chat = stream_id("chatter")
    threat = stream_id("lens.threat")
    v1 = wire.sign_frame(wire.KIND_ITEM, s1, _item())
    v1_other = wire.sign_frame(wire.KIND_ITEM, s1, _item({8: b"a different body"}))
    pl = wire.sign_frame(wire.KIND_PLUCK, s1, {1: 1, 2: chat, 3: 2, 4: T0 + 5_000, 5: T0 + 60_000, 13: 1, 20: 1})
    ls = lambda seq, t, text: wire.sign_frame(wire.KIND_ITEM, s1, _item({2: threat, 3: seq, 4: t, 5: t + 120_000, 6: 3, 10: "now", 8: text}))
    newer, older = ls(2, T0 + 1_000, b"threat: high"), ls(1, T0, b"threat: low")
    alarm = wire.sign_frame(wire.KIND_ITEM, s1, _item({6: 7, 10: "a-1"}))
    epoch2 = wire.sign_frame(wire.KIND_ITEM, s1, _item({1: 2}))
    seqs = [
        ("repeat-is-no-op", [v1, v1, v1], ["item"]),
        ("equivocation", [v1, v1_other], ["item", "evidence:equivocation"]),
        ("pluck-after-original", [v1, pl], ["item", "withdrawn"]),
        ("pluck-before-original", [pl, v1], ["evidence:plucked"]),
        ("supersede-by-key", [older, newer], ["item", "superseded", "item"]),
        ("older-after-newer-dropped", [newer, older], ["item", "evidence:superseded"]),
        ("capability-not-granted", [alarm], ["evidence:capability"]),
        ("epoch-regression", [epoch2, v1], ["item", "evidence:epoch-regression"]),
    ]
    return [{"name": n, "datagrams_hex": [d.hex() for d in ds], "now_ms": NOW, "expect": e} for n, ds, e in seqs]


def run_parse_case(case: dict, m: Manifest) -> str:
    try:
        wire.parse(bytes.fromhex(case["datagram_hex"]), m.resolve, NOW)
        return "accept"
    except wire.Reject as r:
        return r.reason


def run_sequence_case(case: dict, m: Manifest) -> list[str]:
    # Sequence vectors check wire semantics (dedup, pluck, supersession) at one instant, so the
    # receiver-local warm-up hold (§7.8 rule 4, a timing policy) is off here.
    lst = Listener(m, warmup=False)
    out = []
    for d in case["datagrams_hex"]:
        for ev in lst.hear(bytes.fromhex(d), case["now_ms"]):
            if ev.kind == "presence":
                continue
            out.append(f"evidence:{ev.data['reason']}" if ev.kind == "evidence" else ev.kind)
    return out


def build() -> dict:
    return {
        "about": "Candidate frame v2 conformance vectors (RFC-0001 §9.13). Not normative until a second, "
                 "independent implementation reproduces them. Keys are RFC 8032 §7.1 test keys.",
        "now_ms": NOW,
        "keys": keys(),
        "manifest": manifest().to_json(),
        "parse": parse_cases(),
        "sequences": sequence_cases(),
    }
