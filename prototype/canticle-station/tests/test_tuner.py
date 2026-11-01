import asyncio
import hashlib
import json
import random
import subprocess
import sys
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import finding, vectors, wire
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig
from canticle.tuner import SECURITY_HEADERS, TunerHttp, TunerView, is_loopback

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
KID = wire.key_id(wire.public_key_bytes(SK))
PRIVATE_PAYLOAD = "PRIVATE-MACHINE-BOY-CONVERSATION-NEVER-FOR-HUMANS"
PRIVATE_STATION = "private-cael"
PRIVATE_STREAM = "private-chatter"
PRIVATE_STATE_KEY = "private-incident-state-key"
PRIVATE_BODY_REF_URL = "https://private.invalid/evidence-ledger"
PRIVATE_BODY_REF_DIGEST = bytes.fromhex("ab" * 32)
PRIVATE_FINDING_SUMMARY = "PRIVATE-FINDING-SUMMARY-NEVER-FOR-HUMANS"
PRIVATE_NOT_PROVED = "PRIVATE-NOT-PROVED-DETAIL-NEVER-FOR-HUMANS"
PRIVATE_BINARY = b"PRIVATE-BINARY-BODY-NEVER-FOR-HUMANS"
PRIVATE_FINDING_BODY = finding.encode({"incident": PRIVATE_STATE_KEY, "subject": PRIVATE_STATION,
                                       "voice": "observer", "status": "open", "severity": "moderate",
                                       "summary": PRIVATE_FINDING_SUMMARY, "not_proved": PRIVATE_NOT_PROVED})


def setup(demo_fixture=False):
    st = Station(SK, [StreamConfig(PRIVATE_STREAM)], epoch=1, rng=random.Random(1), now_ms=T0)
    m = Manifest([StationEntry(PRIVATE_STATION, wire.public_key_bytes(SK),
                               frozenset({1, 2, 4, 5}), (PRIVATE_STREAM,))])
    lst = Listener(m, ephemeral=True, warmup=False)
    return st, lst, TunerView(lst, demo_fixture=demo_fixture)


def feed(st, lst, view):
    st.sing(T0, PRIVATE_STREAM, text=PRIVATE_PAYLOAD, ttl_s=60)
    st.sing(T0, PRIVATE_STREAM, body=PRIVATE_BINARY, ctype=42, ttl_s=60)
    st.sing(T0, PRIVATE_STREAM, cls="finding-ref",
            body_ref=(PRIVATE_BODY_REF_URL, PRIVATE_BODY_REF_DIGEST, 1234), ttl_s=60)
    st.sing(T0, PRIVATE_STREAM, body=PRIVATE_FINDING_BODY, cls="advisory", ctype=finding.CTYPE,
            state_key=PRIVATE_STATE_KEY, ttl_s=60)
    for t in range(T0, T0 + 3_000, 100):
        for frame in st.poll(t):
            for ev in lst.hear(frame, t):
                view.observe(ev, t)
        for ev in lst.tick(t):
            view.observe(ev, t)


def assert_private_absent(test, value):
    encoded = json.dumps(value)
    for secret in (PRIVATE_PAYLOAD, PRIVATE_STATION, PRIVATE_STREAM, KID.hex(),
                   PRIVATE_STATE_KEY, PRIVATE_BODY_REF_URL, PRIVATE_BODY_REF_DIGEST.hex(),
                   PRIVATE_FINDING_SUMMARY, PRIVATE_NOT_PROVED, PRIVATE_BINARY.decode("ascii"),
                   hashlib.sha256(PRIVATE_PAYLOAD.encode()).hexdigest(),
                   hashlib.sha256(PRIVATE_BINARY).hexdigest(),
                   hashlib.sha256(PRIVATE_FINDING_BODY).hexdigest(),
                   "digest", "payload", "unverified_datagrams", "finding", "body_ref",
                   "state_key", "binary_bytes", "text", "digests", "dedup", "evidence"):
        test.assertNotIn(secret, encoded)
    forbidden_keys = {"text", "finding", "body_ref", "body", "base64", "binary_bytes",
                      "state_key", "sha256", "digests", "dedup", "evidence",
                      "issued_at", "expires_at", "local_expiry", "gap"}
    if isinstance(value, dict):
        def keys(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    test.assertNotIn(k, forbidden_keys)
                    keys(v)
            elif isinstance(obj, list):
                for v in obj:
                    keys(v)
        keys(value)


class TunerViewPrivacyTest(unittest.TestCase):
    def test_default_does_not_enumerate_verified_station_or_hidden_stream(self):
        st, lst, view = setup()
        feed(st, lst, view)
        self.assertIn(KID, lst.stations)  # a real verified observation, not an empty listener
        response = view.stations(T0 + 3_000)
        self.assertEqual(response["stations"], [])
        self.assertFalse(response["synthetic"])
        assert_private_absent(self, response)

    def test_fixture_is_synthetic_and_independent_of_listener(self):
        st, lst, view = setup(demo_fixture=True)
        before = view.stations(T0 + 3_000)
        feed(st, lst, view)
        after = view.stations(T0 + 3_000)
        self.assertEqual(before, after)
        self.assertEqual(len(after["stations"]), 1)
        self.assertEqual(after["stations"][0]["name"], "demo-station")
        self.assertFalse(after["stations"][0]["verified"])
        self.assertTrue(after["stations"][0]["synthetic"])
        assert_private_absent(self, after)


async def http_request(port, method, path, body=None, host=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = b"" if body is None else json.dumps(body).encode()
    req = f"{method} {path} HTTP/1.1\r\nHost: {host or f'127.0.0.1:{port}'}\r\n\r\n"
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


class TunerHttpPrivacyTest(unittest.TestCase):
    def setUp(self):
        self.st, self.lst, self.view = setup()
        feed(self.st, self.lst, self.view)

    def run_http(self, scenario, view=None):
        async def main():
            http = TunerHttp(view or self.view, "127.0.0.1", 0, clock=lambda: T0 + 3_000)
            port = await http.start()
            try:
                return await scenario(port)
            finally:
                await http.close()
        return asyncio.run(main())

    def test_api_is_empty_even_after_verified_live_traffic(self):
        async def scenario(port):
            status, hdrs, body = await http_request(port, "GET", "/api/stations")
            self.assertEqual(status, 200)
            self.assertEqual(hdrs["content-type"], "application/json")
            response = json.loads(body)
            self.assertEqual(response["stations"], [])
            assert_private_absent(self, response)
            for k, v in SECURITY_HEADERS.items():
                self.assertEqual(hdrs[k.lower()], v)
        self.run_http(scenario)

    def test_demo_fixture_http_contains_no_live_metadata(self):
        _, _, view = setup(demo_fixture=True)
        async def scenario(port):
            status, _, body = await http_request(port, "GET", "/api/stations")
            self.assertEqual(status, 200)
            response = json.loads(body)
            self.assertEqual(response["stations"][0]["name"], "demo-station")
            assert_private_absent(self, response)
        self.run_http(scenario, view)

    def test_static_page_and_no_mutation_or_payload_paths(self):
        async def scenario(port):
            status, _, body = await http_request(port, "GET", "/")
            self.assertEqual(status, 200)
            self.assertIn(b"synthetic-only", body)
            assert_private_absent(self, body.decode())
            for path in ("/api/ring", "/api/tune", "/api/leave", "/api/sing",
                         "/api/hush", "/api/journal", "/api/item"):
                status, _, _ = await http_request(port, "GET", path)
                self.assertEqual(status, 404)
            status, _, _ = await http_request(port, "POST", "/api/tune")
            self.assertEqual(status, 405)
        self.run_http(scenario)

    def test_dns_rebinding_and_loopback(self):
        async def scenario(port):
            status, _, _ = await http_request(port, "GET", "/api/stations", host="evil.example")
            self.assertEqual(status, 421)
            status, _, _ = await http_request(port, "GET", "/../etc/passwd")
            self.assertEqual(status, 404)
        self.run_http(scenario)
        self.assertTrue(is_loopback("127.0.0.1") and is_loopback("::1"))
        for host in ("0.0.0.0", "192.168.1.5", "localhost"):
            with self.assertRaises(ValueError):
                TunerHttp(self.view, host, 0)


class TunerCliPrivacyTest(unittest.TestCase):
    def test_tuner_has_no_event_log_option(self):
        result = subprocess.run([sys.executable, "-m", "canticle", "tuner", "--help"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--log", result.stdout)


if __name__ == "__main__":
    unittest.main()
