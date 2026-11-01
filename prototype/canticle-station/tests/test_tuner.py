import asyncio
import json
import random
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import vectors, wire
from canticle.ids import stream_id
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig
from canticle.tuner import SECURITY_HEADERS, TunerHttp, TunerView, is_loopback

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
KID = wire.key_id(wire.public_key_bytes(SK))
HYMN, CHAT = stream_id("hymn"), stream_id("chatter")
PRIVATE_PAYLOAD = "PRIVATE-MACHINE-BOY-CONVERSATION-NEVER-FOR-HUMANS"


def setup():
    st = Station(SK, [StreamConfig("hymn", cls="ambient"), StreamConfig("chatter")],
                 epoch=1, rng=random.Random(1), now_ms=T0)
    m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 2}), ("hymn", "chatter"))])
    lst = Listener(m, ephemeral=True, warmup=False)
    return st, lst, TunerView(lst)


def feed(st, lst, view, start, end, step=100):
    for t in range(start, end, step):
        for f in st.poll(t):
            for ev in lst.hear(f, t):
                view.observe(ev, t)
        for ev in lst.tick(t):
            view.observe(ev, t)


class TunerViewMetadataTest(unittest.TestCase):
    def test_public_metadata_only_and_private_stream_is_omitted(self):
        st, lst, view = setup()
        st.sing(T0, "hymn", text=PRIVATE_PAYLOAD, ttl_s=60)
        st.sing(T0, "chatter", text="also-private", ttl_s=60)
        feed(st, lst, view, T0, T0 + 3_000)

        s = view.stations(T0 + 3_000)
        self.assertEqual(len(s["stations"]), 1)
        cael = s["stations"][0]
        self.assertEqual(cael["key_id"], KID.hex())
        self.assertEqual(cael["name"], "cael")
        self.assertTrue(cael["verified"])
        self.assertTrue(cael["beacon_active"])
        self.assertTrue(cael["lease_active"])
        self.assertIn("beacon", cael)
        self.assertIn("presence", cael)

        streams = {x["name"]: x for x in cael["streams"]}
        self.assertEqual(set(streams), {"hymn", "chatter"})
        self.assertEqual(streams["hymn"]["health"], "active")
        self.assertTrue(streams["hymn"]["lease_active"])
        self.assertEqual(streams["hymn"]["ttl_s"], streams["hymn"]["default_ttl_s"])
        self.assertIn("max_ttl_s", streams["hymn"])

        forbidden = ("text", "body", "summary", "finding", "purpose", "state_key", "tombstones",
                     "unheard_seq", "items", "seq", "copies", "issued_at", "expires_at")
        encoded = json.dumps(s)
        self.assertNotIn(PRIVATE_PAYLOAD, encoded)
        self.assertNotIn("also-private", encoded)
        def keys(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    yield key
                    yield from keys(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from keys(value)
        actual_keys = set(keys(s))
        self.assertFalse(actual_keys.intersection(forbidden))

    def test_unnamed_stream_never_enters_human_projection(self):
        st = Station(SK, [StreamConfig("hymn", cls="ambient"), StreamConfig("unnamed.here")],
                     epoch=1, rng=random.Random(1), now_ms=T0)
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 2}), ("hymn",))])
        lst = Listener(m, ephemeral=True, warmup=False)
        view = TunerView(lst)
        st.sing(T0, "unnamed.here", text="must-not-be-a-public-stream-name", ttl_s=60)
        feed(st, lst, view, T0, T0 + 3_000)

        cael = view.stations(T0 + 3_000)["stations"][0]
        self.assertEqual([x["name"] for x in cael["streams"]], ["hymn"])
        self.assertNotIn("unnamed.here", json.dumps(cael))
        self.assertNotIn("must-not-be-a-public-stream-name", json.dumps(cael))


async def http_request(port: int, method: str, path: str, body=None, host=None, headers=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = b"" if body is None else json.dumps(body).encode()
    hdrs = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    if data:
        hdrs.setdefault("Content-Length", str(len(data)))
    req = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n"
    writer.write(req.encode() + data)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    head, _, payload = raw.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    status = int(lines[0].split()[1])
    got = {k.lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
    return status, got, payload


class TunerHttpMetadataTest(unittest.TestCase):
    def setUp(self):
        self.st, self.lst, self.view = setup()
        self.st.sing(T0, "hymn", text=PRIVATE_PAYLOAD, ttl_s=60)
        feed(self.st, self.lst, self.view, T0, T0 + 3_000)

    def run_http(self, scenario):
        async def main():
            http = TunerHttp(self.view, "127.0.0.1", 0, clock=lambda: T0 + 3_000)
            port = await http.start()
            try:
                return await scenario(port)
            finally:
                await http.close()
        return asyncio.run(main())

    def test_page_and_metadata_api_have_no_payload(self):
        async def scenario(port):
            status, hdrs, body = await http_request(port, "GET", "/")
            self.assertEqual(status, 200)
            self.assertIn(b"Canticle dashboard", body)
            self.assertNotIn(PRIVATE_PAYLOAD.encode(), body)
            for k, v in SECURITY_HEADERS.items():
                self.assertEqual(hdrs[k.lower()], v)

            status, hdrs, body = await http_request(port, "GET", "/api/stations")
            self.assertEqual(status, 200)
            self.assertEqual(hdrs["content-type"], "application/json")
            s = json.loads(body)
            encoded = json.dumps(s)
            self.assertIn("beacon_active", encoded)
            self.assertIn("lease_active", encoded)
            self.assertIn("ttl_s", encoded)
            self.assertNotIn(PRIVATE_PAYLOAD, encoded)
        self.run_http(scenario)

    def test_no_ring_tune_leave_or_mutation_api_path_exists(self):
        async def scenario(port):
            for path in ("/api/ring", "/api/ring?sub=body", "/api/tune", "/api/leave",
                         "/api/sing", "/api/hush", "/api/journal", "/api/item"):
                status, _, _ = await http_request(port, "GET", path)
                self.assertEqual(status, 404)
            status, _, _ = await http_request(port, "POST", "/api/tune", {"station": KID.hex(), "stream": "0"})
            self.assertEqual(status, 405)
        self.run_http(scenario)

    def test_dns_rebinding_loopback_and_static_boundaries(self):
        async def scenario(port):
            status, _, _ = await http_request(port, "GET", "/api/stations", host="evil.example")
            self.assertEqual(status, 421)
            status, _, _ = await http_request(port, "GET", "/../etc/passwd")
            self.assertEqual(status, 404)
            status, _, _ = await http_request(port, "PUT", "/api/stations")
            self.assertEqual(status, 405)
        self.run_http(scenario)

    def test_loopback_only(self):
        st, lst, view = setup()
        self.assertTrue(is_loopback("127.0.0.1") and is_loopback("::1"))
        for host in ("0.0.0.0", "192.168.1.5", "localhost"):
            with self.assertRaises(ValueError):
                TunerHttp(view, host, 0)


if __name__ == "__main__":
    unittest.main()
