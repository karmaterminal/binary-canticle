import json
import random
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, vectors, wire
from canticle.ids import stream_id, stream_ids

SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
PK = SK.public_key()
RFC_V1 = ("4243020121fe31dfa154a261aa010102010301041b000001a0c4506c00051b000001a0c451566006010701084e68"
          "656c6c6f2c2073746174696f6e0b000d0142be28e29d744b8c39af187c179f430993f3860f16256da2c310555fd2"
          "d8823b9d40314ea094af3ae24d30dd0775c37db4b094c494398f6770fb7c401b5b2607")
RFC_V2 = ("4243020321fe31dfa154a261a7010102010302041b000001a0c4507f88051b000001a0c45156600d011401fbd962"
          "295d5f8d6274f105d6f0b6d265a613bd54c224781dcdc9a9a764756a73e81365e0003e23413b6504b5f8c9b32986"
          "7db7d2afb80ef584b1fdc4cdff8c05")
VECTORS_FILE = Path(__file__).resolve().parents[1] / "vectors" / "frame-v2-candidates.json"


class CborTest(unittest.TestCase):
    def test_round_trip(self):
        for obj in (0, 23, 24, 255, 256, 2**32, 2**64 - 1, -1, -25, b"", b"\x00" * 30, "é", [], [1, [2]], {1: 2, -1: "x"}, True, None):
            self.assertEqual(cbor.decode(cbor.encode(obj)), obj)

    def test_rejects(self):
        cases = {
            b"\x18\x01": "non-shortest",
            b"\x9f\xff": "indefinite-length",
            b"\xa2\x02\x00\x01\x00": "map-key-order",
            b"\xa2\x01\x00\x01\x00": "map-key-order",  # duplicate key
            b"\xf9\x3c\x00": "float-or-simple",
            b"\xc1\x00": "tag",
            b"\x01\x02": "trailing-bytes",
            b"\x62\xff\xfe": "bad-utf8",
            b"\x81" * 5 + b"\x00": "depth",
            b"\x98\x21" + b"\x00" * 33: "too-many-entries",
            b"\x5a\xff\xff\xff\xff": "truncated",
        }
        for data, reason in cases.items():
            with self.subTest(data=data.hex()):
                with self.assertRaises(cbor.CborError) as cm:
                    cbor.decode(data)
                self.assertEqual(cm.exception.reason, reason)


class WireTest(unittest.TestCase):
    def test_rfc_vectors_byte_exact(self):
        v1 = wire.encode_item(SK, wire.Item(epoch=1, stream=1, seq=1, issued_at=1790000000000, expires_at=1790000060000,
                                            cls=1, ctype=1, body=b"hello, station", hop=0, scope=1))
        v2 = wire.encode_pluck(SK, wire.Pluck(epoch=1, stream=1, seq=2, issued_at=1790000005000,
                                              expires_at=1790000060000, scope=1, target_seq=1))
        self.assertEqual(v1.hex(), RFC_V1)
        self.assertEqual(v2.hex(), RFC_V2)
        self.assertEqual(wire.parse(v1, lambda k: PK).body.body, b"hello, station")

    def test_size_budget_matches_rfc_9_11(self):
        # the parameters rfc/0001-notes/vec/frame_v2_sizes.py measured with (epoch 7, seq 42, a 4-byte stream id)
        base = dict(epoch=7, stream=0x1A2B3C4D, seq=42, issued_at=1790000000000, expires_at=1790000060000,
                    cls=1, hop=0, scope=1)
        self.assertEqual(len(wire.encode_item(SK, wire.Item(ctype="text/plain;charset=utf-8", body=b"x" * 600, **base))), 745)
        self.assertEqual(len(wire.encode_item(SK, wire.Item(ctype=1, body=b"x" * 600, **base))), 720)
        self.assertEqual(len(wire.encode_item(SK, wire.Item(ctype=1, body=b"x" * 980, **base))), 1100)
        with self.assertRaises(ValueError):
            wire.encode_item(SK, wire.Item(ctype=1, body=b"x" * 981, **base))

    def test_stream_ids(self):
        self.assertEqual(stream_id("chatter"), int.from_bytes(__import__("hashlib").sha256(b"canticle-stream/v2\x00chatter").digest()[:4], "big"))
        with self.assertRaises(ValueError):
            stream_id("Chatter")
        with self.assertRaises(ValueError):
            stream_id("a.b.c.d.e")
        self.assertEqual(len(stream_ids(["chatter", "lens.threat", "root"])), 3)

    def test_candidate_vectors(self):
        m = vectors.manifest()
        for case in vectors.parse_cases():
            with self.subTest(case=case["name"]):
                self.assertEqual(vectors.run_parse_case(case, m), case["expect"])
        for case in vectors.sequence_cases():
            with self.subTest(case=case["name"]):
                self.assertEqual(vectors.run_sequence_case(case, m), case["expect"])

    def test_committed_vectors_match_generator(self):
        self.assertEqual(json.loads(VECTORS_FILE.read_text()), json.loads(json.dumps(vectors.build())))

    def test_fuzz_never_raises_anything_but_reject(self):
        rng = random.Random(1)
        m = vectors.manifest()
        seeds = [bytes.fromhex(c["datagram_hex"]) for c in vectors.parse_cases()]
        for i in range(20_000):
            if i % 4 == 0:
                data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 1300)))
            else:
                data = bytearray(rng.choice(seeds))
                for _ in range(rng.randrange(1, 6)):
                    if data:
                        data[rng.randrange(len(data))] = rng.randrange(256)
                data = bytes(data)
            try:
                wire.parse(data, m.resolve, vectors.NOW)
            except wire.Reject as r:
                self.assertNotEqual(r.reason, "internal", data.hex())


if __name__ == "__main__":
    unittest.main()
