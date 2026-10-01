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
from canticle.tuner import (MAX_SUBS, SEEN_WINDOW, SECURITY_HEADERS, TOMBSTONE_MS, Subscriptions, TunerHttp,
                            TunerView, is_loopback)

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
KID = wire.key_id(wire.public_key_bytes(SK))
HYMN, CHAT = stream_id("hymn"), stream_id("chatter")


def setup():
    st = Station(SK, [StreamConfig("hymn", cls="ambient"), StreamConfig("chatter"), StreamConfig("unnamed.here")],
                 epoch=1, rng=random.Random(1), now_ms=T0)
    # The manifest names hymn and chatter only: unnamed.here is heard and verified, never shown (§5.4).
    m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 2}), ("hymn", "chatter"))])
    lst = Listener(m, ephemeral=True, warmup=False)
    return st, lst, TunerView(lst)


def feed(st, lst, view, start, end, step=100, drop=lambda frame: False):
    for t in range(start, end, step):
        for f in st.poll(t):
            if not drop(f):
                for ev in lst.hear(f, t):
                    view.observe(ev, t)
        for ev in lst.tick(t):
            view.observe(ev, t)


class TunerViewTest(unittest.TestCase):
    def test_stations_show_verified_heads_and_only_named_streams_are_tunable(self):
        st, lst, view = setup()
        st.sing(T0, "hymn", text="the lamp is lit", ttl_s=60)
        feed(st, lst, view, T0, T0 + 3_000)
        s = view.stations(T0 + 3_000)
        self.assertEqual(len(s["stations"]), 1)
        cael = s["stations"][0]
        self.assertTrue(cael["verified"])
        self.assertEqual(cael["key_id"], KID.hex())
        streams = {x["stream_id"]: x for x in cael["streams"]}
        self.assertEqual(streams[f"{HYMN:08x}"]["name"], "hymn")
        self.assertEqual(streams[f"{HYMN:08x}"]["head_seq"], 1)
        unnamed = [x for x in cael["streams"] if x["name"] is None]
        self.assertEqual(len(unnamed), 1)
        self.assertFalse(unnamed[0]["tunable"])

    def test_ring_shows_live_items_then_labelled_expiry_never_a_stale_item(self):
        st, lst, view = setup()
        st.sing(T0, "hymn", text="short", ttl_s=20)
        st.sing(T0, "hymn", text="longer", ttl_s=60)
        feed(st, lst, view, T0, T0 + 5_000)
        r = view.ring(KID, HYMN, T0 + 5_000)
        self.assertEqual([i["text"] for i in r["items"]], ["longer", "short"])  # newest first
        self.assertTrue(all(i["remaining_ms"] > 0 for i in r["items"]))
        feed(st, lst, view, T0 + 5_000, T0 + 25_000)
        r = view.ring(KID, HYMN, T0 + 25_000)
        self.assertEqual([i["text"] for i in r["items"]], ["longer"])
        self.assertEqual([(t["seq"], t["reason"]) for t in r["tombstones"]], [(1, "expired")])
        # The tombstone is listed for a short, labelled window, then dropped.
        feed(st, lst, view, T0 + 25_000, T0 + 25_000 + TOMBSTONE_MS + 2_000, step=500)
        r = view.ring(KID, HYMN, T0 + 25_000 + TOMBSTONE_MS + 2_000)
        self.assertEqual(r["items"], [])
        self.assertNotIn(1, [t["seq"] for t in r["tombstones"]])

    def test_withdrawn_items_leave_the_ring(self):
        st, lst, view = setup()
        st.sing(T0, "chatter", text="retract me", ttl_s=60)
        feed(st, lst, view, T0, T0 + 3_000)
        st.hush(T0 + 3_000, "chatter", 1)
        feed(st, lst, view, T0 + 3_000, T0 + 6_000)
        r = view.ring(KID, CHAT, T0 + 6_000)
        self.assertEqual(r["items"], [])
        self.assertEqual([(t["seq"], t["reason"], t["by_seq"]) for t in r["tombstones"]], [(1, "withdrawn", 2)])
        self.assertEqual(r["unheard_seq"], [])  # the PLUCK (seq 2) was heard too

    def test_a_late_view_sees_only_what_is_still_on_air(self):
        st, lst, _ = setup()
        view = TunerView(lst)
        st.sing(T0, "hymn", text="early", ttl_s=20)
        # The listener is not running yet: the first item's copies go unheard, and it expires.
        for t in range(T0, T0 + 25_000, 100):
            st.poll(t)
        st.sing(T0 + 25_000, "hymn", text="now", ttl_s=60)
        feed(st, lst, view, T0 + 25_000, T0 + 30_000)
        r = view.ring(KID, HYMN, T0 + 30_000)
        self.assertEqual([i["text"] for i in r["items"]], ["now"])
        self.assertEqual(r["unheard_seq"], [1])  # honest gap: before this listener, never shown as live

    def test_a_lost_item_shows_as_a_gap_until_its_next_copy(self):
        st, lst, view = setup()
        st.sing(T0, "hymn", text="lost at first", ttl_s=60)
        first = []
        feed(st, lst, view, T0, T0 + 1_500,
             drop=lambda f: f[3] == wire.KIND_ITEM and not first.append(1))  # drop the burst copies
        self.assertEqual(view.ring(KID, HYMN, T0 + 1_500)["unheard_seq"], [1])
        feed(st, lst, view, T0 + 1_500, T0 + 12_000)
        r = view.ring(KID, HYMN, T0 + 12_000)
        self.assertEqual([i["seq"] for i in r["items"]], [1])
        self.assertEqual(r["unheard_seq"], [])

    def test_unknown_streams_and_stations_have_no_ring(self):
        _, _, view = setup()
        self.assertIsNone(view.ring(KID, stream_id("unnamed.here"), T0))
        self.assertIsNone(view.ring(b"\x00" * 8, HYMN, T0))


class TunerBoundsTest(unittest.TestCase):
    """The gateway's per-channel memory stays bounded however long a stream runs (Silas, #59)."""

    def test_long_stream_keeps_a_bounded_seq_window_and_honest_recent_gaps(self):
        st, lst, view = setup()
        n, dropped, peak, t = 600, {}, 0, T0
        for i in range(1, n + 1):
            r = st.sing(t, "chatter", text=f"line {i}", ttl_s=20, loop="fast")
            if i == n - 5:   # lose every copy of one recent item: it must show as a gap, and only it
                dropped[r.seq] = st.streams["chatter"].ring[r.seq].frame
            feed(st, lst, view, t, t + 1_000, drop=lambda f: f in dropped.values())
            peak = max(peak, len(view.channels[(KID, CHAT)].seen))
            t += 1_000
        feed(st, lst, view, t, t + 25_000, drop=lambda f: f in dropped.values())   # everything expires
        self.assertLessEqual(peak, SEEN_WINDOW)
        r = view.ring(KID, CHAT, t + 25_000)
        self.assertEqual(r["head_seq"], n)
        self.assertEqual(r["unheard_seq"], list(dropped))
        self.assertLessEqual(len(view.channels[(KID, CHAT)].seen), SEEN_WINDOW)

    def test_a_new_epoch_starts_a_fresh_window(self):
        st, lst, view = setup()
        for i in range(5):
            st.sing(T0 + i * 1_000, "chatter", text=f"a{i}", ttl_s=30)
            feed(st, lst, view, T0 + i * 1_000, T0 + (i + 1) * 1_000)
        t1 = T0 + 10_000
        st2 = Station(SK, [StreamConfig("hymn", cls="ambient"), StreamConfig("chatter")], epoch=2,
                      rng=random.Random(2), now_ms=t1)
        st2.sing(t1, "chatter", text="after restart", ttl_s=30)
        feed(st2, lst, view, t1, t1 + 3_000)
        ch = view.channels[(KID, CHAT)]
        self.assertEqual((ch.epoch, ch.seen), (2, {1}))
        self.assertEqual(view.ring(KID, CHAT, t1 + 3_000)["unheard_seq"], [])


class SubscriptionsTest(unittest.TestCase):
    def test_tune_leave_retune_and_limits(self):
        _, _, view = setup()
        subs = Subscriptions(view)
        a = subs.tune(KID, HYMN, T0)
        self.assertTrue(subs.leave(a))
        self.assertFalse(subs.leave(a))
        b = subs.tune(KID, CHAT, T0)
        self.assertIsNotNone(subs.get(b, T0 + 1_000))
        self.assertIsNone(subs.get(b, T0 + 1_000 + 31_000))  # idle subscriptions lapse
        with self.assertRaises(LookupError):
            subs.tune(KID, stream_id("unnamed.here"), T0)
        for _ in range(MAX_SUBS):
            subs.tune(KID, HYMN, T0 + 40_000)
        with self.assertRaises(OverflowError):
            subs.tune(KID, HYMN, T0 + 40_000)


async def http_request(port: int, method: str, path: str, body=None, host=None, headers=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = b"" if body is None else json.dumps(body).encode()
    hdrs = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
        hdrs["Content-Length"] = str(len(data))
    req = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n"
    writer.write(req.encode() + data)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    head, _, payload = raw.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    status = int(lines[0].split()[1])
    got = {k.lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
    return status, got, payload


class TunerHttpTest(unittest.TestCase):
    def setUp(self):
        self.st, self.lst, self.view = setup()
        self.st.sing(T0, "hymn", text="<b>not markup</b>", ttl_s=60)
        feed(self.st, self.lst, self.view, T0, T0 + 3_000)
        self.now = [T0 + 3_000]

    def run_http(self, scenario):
        async def main():
            http = TunerHttp(self.view, Subscriptions(self.view), "127.0.0.1", 0, clock=lambda: self.now[0])
            port = await http.start()
            try:
                return await scenario(port)
            finally:
                await http.close()
        return asyncio.run(main())

    def test_page_and_headers(self):
        async def scenario(port):
            status, hdrs, body = await http_request(port, "GET", "/")
            self.assertEqual(status, 200)
            self.assertIn(b"Canticle tuner", body)
            for k, v in SECURITY_HEADERS.items():
                self.assertEqual(hdrs[k.lower()], v)
            self.assertIn("script-src 'self'", hdrs["content-security-policy"])
            status, hdrs, _ = await http_request(port, "GET", "/tuner.js")
            self.assertEqual((status, hdrs["content-type"]), (200, "text/javascript; charset=utf-8"))
        self.run_http(scenario)

    def test_tune_ring_leave_retune(self):
        async def scenario(port):
            status, _, body = await http_request(port, "GET", "/api/stations")
            stations = json.loads(body)["stations"]
            self.assertEqual(stations[0]["name"], "cael")
            status, _, body = await http_request(port, "POST", "/api/tune",
                                                 {"station": KID.hex(), "stream": f"{HYMN:08x}"})
            self.assertEqual(status, 200)
            sub = json.loads(body)["sub"]
            status, _, body = await http_request(port, "GET", f"/api/ring?sub={sub}")
            ring = json.loads(body)
            self.assertEqual((ring["station"], ring["stream"]), ("cael", "hymn"))
            self.assertEqual(ring["items"][0]["text"], "<b>not markup</b>")  # data, rendered as text by the page
            self.now[0] += 100
            status, _, _ = await http_request(port, "GET", f"/api/ring?sub={sub}")
            self.assertEqual(status, 429)  # polls are rate-limited per subscription
            status, _, body = await http_request(port, "POST", "/api/leave", {"sub": sub})
            self.assertEqual(json.loads(body), {"left": True})
            self.now[0] += 1_000
            status, _, _ = await http_request(port, "GET", f"/api/ring?sub={sub}")
            self.assertEqual(status, 404)
            status, _, body = await http_request(port, "POST", "/api/tune",
                                                 {"station": KID.hex(), "stream": f"{CHAT:08x}"})
            self.assertEqual(status, 200)  # retuned without touching the station
        self.run_http(scenario)

    def test_boundary_checks(self):
        async def scenario(port):
            status, _, _ = await http_request(port, "GET", "/api/stations", host="evil.example")
            self.assertEqual(status, 421)  # DNS rebinding
            status, _, _ = await http_request(port, "POST", "/api/tune", {"station": KID.hex(), "stream": "0"},
                                              headers={"Origin": "http://evil.example"})
            self.assertEqual(status, 403)
            status, _, _ = await http_request(port, "POST", "/api/tune", {"station": KID.hex()},
                                              headers={"Content-Type": "text/plain"})
            self.assertEqual(status, 415)
            status, _, _ = await http_request(port, "POST", "/api/tune", {"station": "zz", "stream": "1"})
            self.assertEqual(status, 400)
            status, _, _ = await http_request(port, "POST", "/api/tune",
                                              {"station": KID.hex(), "stream": f"{stream_id('unnamed.here'):08x}"})
            self.assertEqual(status, 404)
            for method in ("PUT", "DELETE", "PATCH"):
                status, _, _ = await http_request(port, method, "/api/tune")
                self.assertEqual(status, 405)
            for path in ("/api/sing", "/api/hush", "/../etc/passwd", "/web/index.html"):
                status, _, _ = await http_request(port, "GET", path)
                self.assertEqual(status, 404)
        self.run_http(scenario)

    def test_loopback_only(self):
        self.assertTrue(is_loopback("127.0.0.1") and is_loopback("::1"))
        for host in ("0.0.0.0", "192.168.1.5", "localhost"):
            with self.assertRaises(ValueError):
                TunerHttp(self.view, Subscriptions(self.view), host, 0)


if __name__ == "__main__":
    unittest.main()
