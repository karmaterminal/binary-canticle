"""Focused fixture tests. Real integration uses only ephemeral loopback and Unix sockets."""
import asyncio
import json
from pathlib import Path
import sys
import time
import tempfile
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "canticle-station"))
from fixtures.loopback import Bounds, Fixture, Ledger
from canticle import runner, wire
from canticle.station import Station, StreamConfig
from canticle.manifest import StationEntry
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import run as supervisor


class BoundsTest(unittest.TestCase):
    def test_rejects_unbounded_or_ambiguous_parameters(self):
        for kwargs in ({"items": 0}, {"items": 17}, {"items": True}, {"vus": 3},
                       {"deadline_ms": 499}, {"deadline_ms": 2001},
                       {"pace_ms": 249}, {"pace_ms": 1001}, {"drop_first": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Bounds(**kwargs)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(Bounds(items=2, deadline_ms=500))
        self.key = ("a" * 16, 1, 123, 1)

    def row(self):
        row = self.ledger.offer(0, 0)
        row["identity"] = self.key
        return row

    def test_duplicate_or_invalid_id_never_expands_population(self):
        self.row()
        for value in (0, -1, 2, True, "1"):
            with self.assertRaises(ValueError):
                self.ledger.offer(value, 0)
        self.assertEqual(len(self.ledger.rows), 1)

    def test_known_dropped_offer_remains_in_latency_and_miss_denominator(self):
        row = self.row()
        self.ledger.arrivals[self.key] = (10_000_000, "digest")
        result = self.ledger.result(row, 500_000_000)
        self.assertTrue(result["missed"])
        self.assertIsNone(result["arrival_to_record_ms"])
        self.assertEqual(result["offer_to_record_or_deadline_ms"], 500)
        self.assertEqual(result["arrival_to_record_or_deadline_ms"], 490)
        counts = self.ledger.report(500_000_000)["counts"]
        self.assertEqual((counts["offered"], counts["delivered"], counts["missed"]), (1, 0, 1))

    def test_complete_listener_record_latency_not_submit_ack(self):
        row = self.row()
        self.ledger.arrivals[self.key] = (10_000_000, "digest")
        self.ledger.records[self.key] = (30_000_000, "digest")
        result = self.ledger.result(row, 30_000_000)
        self.assertTrue(result["delivered"])
        self.assertEqual(result["arrival_to_record_ms"], 20)
        self.assertEqual(result["offer_to_record_or_deadline_ms"], 30)

    def test_late_record_does_not_rewrite_failure_as_success(self):
        row = self.row()
        self.ledger.arrivals[self.key] = (10_000_000, "digest")
        self.ledger.records[self.key] = (510_000_000, "digest")
        result = self.ledger.result(row, 600_000_000)
        self.assertTrue(result["late"] and result["missed"])
        self.assertFalse(result["delivered"])
        self.assertEqual(result["arrival_to_record_or_deadline_ms"], 490)

    def test_missing_arrival_or_wrong_hash_is_not_delivery(self):
        row = self.row()
        self.ledger.records[self.key] = (30_000_000, "digest")
        self.assertFalse(self.ledger.result(row, 500_000_000)["delivered"])
        self.ledger.arrivals[self.key] = (10_000_000, "different")
        self.assertFalse(self.ledger.result(row, 500_000_000)["delivered"])

    def test_pending_rejected_and_packet_conservation(self):
        row = self.ledger.offer(0, 0)
        row["submit_error"] = "refused"
        early = self.ledger.report(1)
        self.assertEqual(early["counts"]["pending"], 1)
        self.assertTrue(early["accounting"])
        final = self.ledger.report(500_000_000)
        self.assertTrue(final["accounting"])
        self.assertEqual(final["counts"]["missed"], 1)
        self.ledger.packets["received"] = 1
        self.assertFalse(self.ledger.report(500_000_000)["accounting"])


async def request(fixture, method, path, body=b"", token=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", fixture.ports["http_tcp"])
    try:
        auth = fixture.token if token is None else token
        writer.write((f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                      f"Authorization: Bearer {auth}\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body)
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), 4)
        head, data = raw.split(b"\r\n\r\n", 1)
        return int(head.split()[1]), json.loads(data)
    finally:
        writer.close()
        await writer.wait_closed()


class FixtureTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_record_close_does_not_skip_remaining_cleanup(self):
        f = Fixture(Bounds(items=1))
        await f.__aenter__()
        with patch.object(f.client_writer, "wait_closed", AsyncMock(side_effect=OSError("injected close"))):
            result = await f.close()
        self.assertFalse(result["ok"])
        self.assertTrue(result["tasks_done"] and result["temporary_state_removed"])
        self.assertTrue(all(result["ports_rebindable"].values()))
        self.assertTrue(any("record client close" in e for e in result["errors"]))

    async def test_relay_close_timeout_does_not_skip_remaining_cleanup(self):
        f = Fixture(Bounds(items=1))
        await f.__aenter__()
        with patch.object(f.relay.closed, "wait", AsyncMock(side_effect=TimeoutError("injected close"))):
            result = await f.close()
        self.assertFalse(result["ok"])
        self.assertTrue(result["tasks_done"] and result["temporary_state_removed"])
        self.assertTrue(all(result["ports_rebindable"].values()))
        self.assertTrue(any("relay close" in e for e in result["errors"]))

    async def test_fresh_run_plan_exists_before_submission(self):
        f, g = Fixture(Bounds(items=2)), Fixture(Bounds(items=2))
        self.assertNotEqual(f.run_id, g.run_id)
        self.assertNotEqual(f.token, g.token)
        self.assertEqual(f.expected_ids, [0, 1])
        self.assertEqual(f.ledger.rows, {})

    async def test_supervisor_wall_timeout_reaps_real_k6_and_releases_fixture(self):
        binary = Path("/home/figs/.local/bin/k6")
        if not binary.is_file():
            self.skipTest("optional real-k6 timeout probe needs local binary")
        real_wait = asyncio.wait_for
        async def short_child_wait(aw, timeout):
            return await real_wait(aw, .05 if timeout == 55 else timeout)
        with tempfile.TemporaryDirectory(prefix="canticle-k6-timeout-") as directory:
            out = Path(directory) / "receipt"
            args = SimpleNamespace(out=str(out), k6=str(binary))
            with patch.object(supervisor.asyncio, "wait_for", short_child_wait):
                code = await supervisor.run(args, Bounds(items=16, pace_ms=1000))
            self.assertEqual(code, 1)
            process = json.loads((out / "process.json").read_text())
            cleanup = json.loads((out / "cleanup.json").read_text())
            failure = json.loads((out / "failure.json").read_text())
            self.assertTrue(process["child_started"] and process["child_reaped"])
            self.assertIsNotNone(process["k6_exit_code"])
            self.assertTrue(cleanup["ok"], cleanup)
            self.assertTrue(failure["error"].startswith("TimeoutError"), failure)

    async def test_real_station_daemon_record_client_and_cleanup(self):
        f = Fixture(Bounds(items=2, deadline_ms=500))
        async with f:
            rows = await asyncio.gather(f.offer(0), f.offer(1))
            self.assertTrue(all(r["delivered"] for r in rows), rows)
            report = f.report()
            self.assertTrue(report["accounting"])
            self.assertEqual(report["counts"]["offered"], 2)
            self.assertEqual(report["counts"]["duplicate_surface_records"], 0)
            self.assertTrue(all(r["arrival_to_record_ms"] >= 0 for r in rows))
            self.assertEqual(report["errors"], [])
        self.assertTrue(f.cleanup["ok"], f.cleanup)
        self.assertEqual(await f.close(), f.cleanup)

    async def test_real_negative_drops_all_copies_but_keeps_offered_population(self):
        f = Fixture(Bounds(items=2, deadline_ms=500, drop_first=True))
        async with f:
            dropped = await f.offer(0)
            delivered = await f.offer(1)
            self.assertTrue(dropped["missed"] and dropped["arrived"])
            self.assertTrue(delivered["delivered"])
            # Cross the +1s burst, demonstrating that retransmission is dropped too.
            await asyncio.sleep(.6)
            report = f.report()
            self.assertEqual(report["counts"]["offered"], 2)
            self.assertEqual(report["counts"]["missed"], 1)
            self.assertGreaterEqual(report["packets"]["intentionally_dropped"], 2)
            self.assertTrue(report["accounting"])
        self.assertTrue(f.cleanup["ok"], f.cleanup)

    async def test_http_bounds_auth_and_metrics(self):
        f = Fixture(Bounds(items=1, deadline_ms=500))
        async with f:
            self.assertEqual((await request(f, "POST", "/offer", b'{"id":0}', token="wrong"))[0], 403)
            self.assertEqual((await request(f, "POST", "/offer", b"x"*129))[0], 400)
            self.assertEqual((await request(f, "POST", "/offer", b'{"id":true}'))[0], 400)
            self.assertEqual((await request(f, "GET", "/unknown"))[0], 404)
            status, row = await request(f, "POST", "/offer", b'{"id":0}')
            self.assertEqual(status, 200)
            self.assertTrue(row["delivered"], row)
            self.assertEqual((await request(f, "POST", "/offer", b'{"id":0}'))[0], 400)
            _, stats = await request(f, "GET", "/stats")
            self.assertEqual(stats["counts"]["offered"], 1)
            self.assertEqual(stats["counts"]["delivered"], 1)
            self.assertTrue(stats["accounting"])
        self.assertTrue(f.cleanup["ok"], f.cleanup)

    async def test_exception_and_partial_startup_cleanup(self):
        f = Fixture(Bounds(items=1))
        with self.assertRaisesRegex(RuntimeError, "scenario failed"):
            async with f:
                raise RuntimeError("scenario failed")
        self.assertTrue(f.cleanup["ok"], f.cleanup)
        original = Fixture.start
        async def broken(fixture):
            await original(fixture)
            raise RuntimeError("startup failed")
        g = Fixture(Bounds(items=1))
        with patch.object(Fixture, "start", broken):
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                async with g:
                    self.fail("unreachable")
        self.assertTrue(g.cleanup["ok"], g.cleanup)

    async def test_submission_failure_is_a_deadline_miss_not_removed(self):
        f = Fixture(Bounds(items=1, deadline_ms=500))
        async with f:
            f.control = str(f.root / "absent.sock")
            row = await f.offer(0)
            self.assertTrue(row["missed"])
            self.assertFalse(row["accepted"])
            self.assertEqual(f.report()["counts"]["offered"], 1)
            self.assertTrue(f.report()["accounting"])
        self.assertTrue(f.cleanup["ok"], f.cleanup)


class StationStartupTest(unittest.IsolatedAsyncioTestCase):
    async def probe(self, cancel=False):
        key = Ed25519PrivateKey.generate()
        grant = StationEntry("startup-test", wire.public_key_bytes(key), frozenset({1}), ("chatter",))
        station = Station(key, [StreamConfig("chatter")], epoch=1, now_ms=runner.now_ms(), grant=grant)
        sockets = []
        reached = asyncio.Event()
        class TrackedSockets:
            def __getattr__(self, name):
                return getattr(socket, name)
            def socket(self, *args, **kwargs):
                sock = socket.socket(*args, **kwargs)
                sockets.append(sock)
                return sock
        async def failed_server(*args, **kwargs):
            reached.set()
            if cancel:
                await asyncio.Event().wait()
            raise OSError("injected intermediate control startup failure")
        try:
            with tempfile.TemporaryDirectory(prefix="canticle-station-startup-") as directory:
                with patch.object(runner, "socket", TrackedSockets()), patch.object(runner.asyncio, "start_unix_server", failed_server):
                    task = asyncio.create_task(runner.run_station(station, [], str(Path(directory)/"control.sock")))
                    if cancel:
                        await asyncio.wait_for(reached.wait(), 1)
                        task.cancel()
                    with self.assertRaises(asyncio.CancelledError if cancel else OSError):
                        await task
            self.assertTrue(sockets)
            self.assertTrue(all(s.fileno() == -1 for s in sockets), "station UDP socket leaked before control startup")
        finally:
            for sock in sockets:
                sock.close()  # failed RED probes must not leak into the test runner

    async def test_intermediate_startup_failure_closes_station_udp(self):
        await self.probe()

    async def test_intermediate_startup_cancellation_closes_station_udp(self):
        await self.probe(cancel=True)

if __name__ == "__main__":
    unittest.main()
