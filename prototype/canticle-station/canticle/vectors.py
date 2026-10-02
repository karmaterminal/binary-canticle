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


def _raw_map(entries: dict[bytes, bytes]) -> bytes:
    """Map bytes from pre-encoded {key_bytes: value_bytes}, in RFC 8949 core deterministic order.

    For maps a Python ``dict`` cannot hold, such as one with both ``0`` and ``false`` as keys (#66).
    """
    assert len(entries) < 24
    return bytes([0xA0 + len(entries)]) + b"".join(k + v for k, v in sorted(entries.items()))


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
    # §9.8 post-A1 stream-entry: [stream_id, head_seq, trail_seq, live, loop_ms, loop_max_ms, default_ttl_s,
    # max_ttl_s, b_stream, ? lens]. One item on air (seq 1), so head_seq = trail_seq = 1.
    chat_entry = [stream_id("chatter"), 1, 1, 1, 10000, 10000, 60, 300, 4000]
    bcn = wire.Beacon(epoch=1, bseq=1, wallclock=NOW, next_beacon_ms=1000,
                      profile="canticle-regulation/1", b_station=16000,
                      streams=(wire.StreamEntry(*chat_entry),))
    beacon = wire.encode_beacon(s1, bcn)
    beacon_lens = cbor.encode({**wire.beacon_map(bcn), 6: [chat_entry + [7]]})
    # #70: a pre-A1 8-element entry (no trail_seq). Read as post-A1 it would shift every field after head_seq.
    beacon_pre_a1 = cbor.encode({**wire.beacon_map(bcn), 6: [chat_entry[:2] + chat_entry[3:]]})
    # #66 case 4: b_stream is `uint .size 4` in the §9.8 CDDL, so 2^60 is out of range, not accepted.
    beacon_big_b = cbor.encode({**wire.beacon_map(bcn), 6: [chat_entry[:8] + [2**60]]})
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
    # #66: map keys are integers or text strings at every depth, including extension values. These are
    # validly ordered (0x00 < 0x40 < 0xf4 < 0xf6) and validly signed; only the key type is wrong. A
    # decoder that folds `false` into `0` (Python dict) would reject the first for the wrong reason
    # and accept the third as a frame whose `true` key reads as key 1.
    item_enc = {cbor.encode(k): cbor.encode(v) for k, v in _item().items()}
    ext_bool_key = _raw_map({**item_enc, cbor.encode(19): _raw_map({b"\x00": b"\x00", b"\xf4": b"\x00"})})
    ext_null_key = _raw_map({**item_enc, cbor.encode(19): _raw_map({b"\x00": b"\x00", b"\xf6": b"\x00"})})
    ext_bstr_key = _raw_map({**item_enc, cbor.encode(19): _raw_map({b"\x00": b"\x00", b"\x40": b"\x00"})})
    top_bool_key = _raw_map({**{k: v for k, v in item_enc.items() if k != cbor.encode(1)}, b"\xf5": cbor.encode(1)})
    # #66: an optional key that is present must carry a well-typed value; an explicit null is bad-field.
    null_body = cbor.encode({**_item(), 8: None})
    null_digest = cbor.encode({**wire.beacon_map(bcn), 9: None})
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
        ("extension-map-bool-key", _raw(wire.KIND_ITEM, s1, ext_bool_key), "bad-cbor",
         "#66: key 19 holds {0: 0, false: 0}; keys are int or tstr at every depth (map-key-type, not non-deterministic)"),
        ("extension-map-null-key", _raw(wire.KIND_ITEM, s1, ext_null_key), "bad-cbor", "#66: key 19 holds {0: 0, null: 0}"),
        ("extension-map-bstr-key", _raw(wire.KIND_ITEM, s1, ext_bstr_key), "bad-cbor", "#66: key 19 holds {0: 0, h'': 0}"),
        ("top-level-bool-key", _raw(wire.KIND_ITEM, s1, top_bool_key), "bad-cbor",
         "#66: true where key 1 (epoch) belongs; a bool is never a field key"),
        ("item-null-body", _raw(wire.KIND_ITEM, s1, null_body), "bad-field",
         "#66: 8: null and no 9; an explicit null for an optional key is bad-field, not absence (§9.6 needs a body or a body_ref)"),
        ("beacon-null-catalog-digest", _raw(wire.KIND_BEACON, s1, null_digest), "bad-field", "#66: 9: null; same rule as item-null-body"),
        ("beacon-entry-with-lens", _raw(wire.KIND_BEACON, s1, beacon_lens), "accept",
         "§9.8 (A1): the 10-element stream-entry, lens = 7"),
        ("beacon-pre-a1-8-field-entry", _raw(wire.KIND_BEACON, s1, beacon_pre_a1), "bad-field",
         "#70: an 8-element stream-entry without trail_seq; a stale station fails loudly instead of being read shifted"),
        ("beacon-b-stream-over-u32", _raw(wire.KIND_BEACON, s1, beacon_big_b), "bad-field",
         "#66 case 4: b_stream = 2^60; §9.8 CDDL says uint .size 4"),
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
    # #60: a PLUCK must carry its held target's expires_at (§9.7), and one that claims a later expiry
    # than any class allows holds its dedup slot for at most the largest class max TTL (one day).
    pl_late = wire.sign_frame(wire.KIND_PLUCK, s1, {1: 1, 2: chat, 3: 2, 4: T0 + 5_000, 5: T0 + 3_600_000, 13: 1, 20: 1})
    day = 86_400_000
    pl_far = wire.sign_frame(wire.KIND_PLUCK, s1, {1: 1, 2: chat, 3: 2, 4: T0 + 5_000, 5: T0 + 50 * 365 * day, 13: 1, 20: 1})
    after_day = wire.sign_frame(wire.KIND_ITEM, s1, _item({3: 3, 4: NOW + day + 9_000, 5: NOW + day + 69_000}))
    # #60: supersession marks outlive their dedup entries (§7.8), so they have their own per-key limit:
    # a new state_key waits for a mark, a new value for a marked key does not. k1 is still live at +40 s.
    ks = lambda seq, t, key, ttl=30_000: wire.sign_frame(
        wire.KIND_ITEM, s1, _item({2: threat, 3: seq, 4: t, 5: t + ttl, 6: 3, 10: key}))
    k1, k2 = ks(1, NOW - 1_000, "k1", 60_000), ks(2, NOW - 1_000, "k2")
    k3, k1_new = ks(3, NOW + 39_000, "k3"), ks(4, NOW + 39_500, "k1")
    # §7.8, §23.2 q21: one class per state_key within an epoch, dropped as class-change; a new epoch may change it.
    kc = lambda seq, t, cls, epoch=1: wire.sign_frame(
        wire.KIND_ITEM, s1, _item({1: epoch, 2: threat, 3: seq, 4: t, 5: t + 60_000, 6: cls, 10: "k"}))
    seqs = [
        ("repeat-is-no-op", [v1, v1, v1], ["item"]),
        ("equivocation", [v1, v1_other], ["item", "evidence:equivocation"]),
        ("pluck-after-original", [v1, pl], ["item", "withdrawn"]),
        ("pluck-before-original", [pl, v1], ["evidence:plucked"]),
        ("supersede-by-key", [older, newer], ["item", "superseded", "item"]),
        ("older-after-newer-dropped", [newer, older], ["item", "evidence:superseded"]),
        ("capability-not-granted", [alarm], ["evidence:capability"]),
        ("epoch-regression", [epoch2, v1], ["item", "evidence:epoch-regression"]),
        ("pluck-expiry-mismatch", [v1, pl_late], ["item", "evidence:pluck-mismatch"]),
        ("class-change-in-one-epoch", [kc(1, T0, 3), kc(2, T0 + 1_000, 1)], ["item", "evidence:class-change"]),
        ("class-change-older-in-one-epoch", [kc(2, T0 + 1_000, 3), kc(1, T0, 1)], ["item", "evidence:class-change"]),
        ("class-change-across-epochs", [kc(1, T0, 3), kc(1, T0 + 1_000, 1, epoch=2)], ["item", "superseded", "item"]),
    ]
    out = [{"name": n, "datagrams_hex": [d.hex() for d in ds], "now_ms": NOW, "expect": e} for n, ds, e in seqs]
    # Timed sequences: time advances to at_ms[i] (local expiry applied, its events not listed) before
    # datagram i is heard, with fixed per-key limits for dedup entries and for marks (§7.4).
    timed = [
        ("pluck-expiry-clamped", [pl_far, after_day], [NOW, NOW + day + 10_000], 1, 1, ["item"]),
        ("supersession-marks-have-their-own-key-limit", [k1, k2, k3, k1_new],
         [NOW, NOW, NOW + 40_000, NOW + 40_000], 2, 2, ["item", "item", "evidence:over-quota", "superseded", "item"]),
    ]
    out += [{"name": n, "datagrams_hex": [d.hex() for d in ds], "now_ms": NOW, "at_ms": at,
             "per_key_quota": q, "per_key_mark_quota": mq, "expect": e} for n, ds, at, q, mq, e in timed]
    return out


def run_parse_case(case: dict, m: Manifest) -> str:
    try:
        wire.parse(bytes.fromhex(case["datagram_hex"]), m.resolve, NOW)
        return "accept"
    except wire.Reject as r:
        return r.reason


def run_sequence_case(case: dict, m: Manifest) -> list[str]:
    # Sequence vectors check wire semantics (dedup, pluck, supersession), so the receiver-local
    # warm-up hold (§7.8 rule 4, a timing policy) is off here. Optional fields: at_ms (time advances to
    # at_ms[i], with local expiry applied and its events not listed, before datagram i is heard; default
    # now_ms for every datagram), per_key_quota and per_key_mark_quota (§7.4).
    lst = Listener(m, warmup=False, ephemeral=True, per_key_quota=case.get("per_key_quota"),
                   per_key_mark_quota=case.get("per_key_mark_quota"))
    timed = "at_ms" in case
    at = case["at_ms"] if timed else [case["now_ms"]] * len(case["datagrams_hex"])
    out = []
    for d, t in zip(case["datagrams_hex"], at):
        if timed:
            lst.tick(t)
        for ev in lst.hear(bytes.fromhex(d), t):
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
