"""Real, bounded loopback process fixtures; no live config, keys or services."""
import asyncio
import os
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import AsyncMock, patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "canticle-station"))
from fixtures.loopback import Bounds
from fixtures.processes import ProcessFixture


async def wait_dead(child):
    async with asyncio.timeout(2):
        while child.is_alive():
            await asyncio.sleep(.01)


@unittest.skipUnless(sys.platform == "linux", "production sockets and SIGTERM fixture require Linux")
class ProcessFixtureTest(unittest.IsolatedAsyncioTestCase):
    def assert_resources_removed(self, fixture):
        cleanup = fixture.cleanup
        self.assertTrue(cleanup["tasks_done"], cleanup)
        self.assertTrue(cleanup["processes_reaped"], cleanup)
        self.assertTrue(cleanup["unix_sockets_removed"], cleanup)
        self.assertTrue(cleanup["temporary_state_removed"], cleanup)
        self.assertTrue(all(cleanup["ports_rebindable"].values()), cleanup)
        for role, receipt in cleanup["processes"].items():
            self.assertFalse(receipt["alive"], role)
            self.assertIsNotNone(receipt["exit_code"], role)
            self.assertIsNotNone(receipt["exit_observed_ns"], role)
            self.assertTrue(receipt["reaped"] and receipt["handle_closed"], cleanup)
            # Receipt flags alone do not prove the OS pid was actually reaped.
            with self.assertRaises(ChildProcessError):
                os.waitpid(receipt["pid"], os.WNOHANG)

    async def test_distinct_real_processes_delivery_and_ordered_reap(self):
        f = ProcessFixture(Bounds(items=2, deadline_ms=1000))
        async with f:
            before = f.report()
            self.assertEqual(before["fixture_mode"], "processes")
            self.assertIs(before["process_mode"], True)
            self.assertEqual(before["parent_pid"], os.getpid())
            children = before["processes"]
            self.assertEqual(set(children), {"station", "daemon"})
            self.assertEqual(len({os.getpid(), *(r["pid"] for r in children.values())}), 3)
            self.assertTrue(before["production_tasks_alive"], before)
            for receipt in children.values():
                self.assertTrue(receipt["started"] and receipt["ready"] and receipt["alive"])
                self.assertLessEqual(receipt["started_ns"], receipt["child_started_ns"])
                self.assertLessEqual(receipt["child_started_ns"], receipt["ready_ns"])
            self.assertEqual(f.root.stat().st_mode & 0o777, 0o700)
            self.assertFalse(list(f.root.rglob("*.key")))
            rows = await asyncio.gather(f.offer(0), f.offer(1))
            self.assertTrue(all(r["delivered"] for r in rows), rows)
            self.assertTrue(all(r["frame_sha256"] == r["record_frame_sha256"] for r in rows))
            report = f.report()
            self.assertTrue(report["production_tasks_alive"] and report["accounting"], report)
            self.assertEqual(report["counts"]["offered"], 2)
            self.assertEqual(report["counts"]["delivered"], 2)
            self.assertEqual(report["counts"]["duplicate_surface_records"], 0)
            self.assertEqual(report["errors"], [])
        self.assert_resources_removed(f)
        self.assertTrue(f.cleanup["ok"], f.cleanup)
        self.assertEqual(list(f.ledger.errors), [])
        receipts = f.cleanup["processes"]
        for receipt in receipts.values():
            self.assertEqual(receipt["exit_code"], 0)
            self.assertTrue(receipt["term_sent"])
            self.assertFalse(receipt["kill_sent"])
        self.assertLessEqual(receipts["station"]["reaped_ns"], receipts["daemon"]["reaped_ns"])
        self.assertIs(await f.close(), f.cleanup)

    async def test_mandatory_sequence_one_drop_preserves_failure_denominator(self):
        f = ProcessFixture(Bounds(items=2, deadline_ms=1500, drop_first=True))
        async with f:
            dropped = await f.offer(0)
            delivered = await f.offer(1)
            self.assertEqual(dropped["identity"][3], 1)
            self.assertTrue(dropped["accepted"] and dropped["arrived"] and dropped["missed"])
            self.assertFalse(dropped["delivered"])
            self.assertIsNone(dropped["complete_record_ns"])
            self.assertIsNone(dropped["arrival_to_record_ms"])
            self.assertIsNotNone(dropped["arrival_to_record_or_deadline_ms"])
            self.assertTrue(delivered["delivered"], delivered)
            report = f.report()
            self.assertTrue(report["accounting"] and report["production_tasks_alive"], report)
            self.assertEqual({k: report["counts"][k] for k in
                ("offered", "accepted", "arrived", "delivered", "missed", "pending")},
                dict(offered=2, accepted=2, arrived=2, delivered=1, missed=1, pending=0))
            # A full deadline spans repeated carousel copies, all still dropped.
            self.assertGreater(report["packets"]["intentionally_dropped"], 1)
        self.assert_resources_removed(f)
        self.assertTrue(f.cleanup["ok"], f.cleanup)

    async def test_station_early_death_cannot_make_report_green(self):
        f = ProcessFixture(Bounds(items=2, deadline_ms=500))
        async with f:
            self.assertTrue((await f.offer(0))["delivered"])
            f.children["station"].kill()
            await wait_dead(f.children["station"])
            # report observes liveness synchronously even without the monitor tick.
            report = f.report()
            self.assertFalse(report["production_tasks_alive"], report)
            self.assertTrue(any("station child exited" in e for e in report["errors"]))
            missed = await f.offer(1)
            self.assertFalse(missed["delivered"])
            self.assertTrue(missed["missed"])
        self.assert_resources_removed(f)
        self.assertFalse(f.cleanup["ok"], f.cleanup)
        self.assertEqual(f.cleanup["processes"]["station"]["exit_code"], -signal.SIGKILL)

    async def test_daemon_early_death_records_eof_and_cannot_green(self):
        f = ProcessFixture(Bounds(items=1, deadline_ms=500))
        async with f:
            f.children["daemon"].kill()
            await wait_dead(f.children["daemon"])
            row = await f.offer(0)
            self.assertTrue(row["missed"] and row["arrived"], row)
            report = f.report()
            self.assertFalse(report["production_tasks_alive"], report)
            self.assertIn("record client EOF before cleanup", report["errors"])
        self.assert_resources_removed(f)
        self.assertFalse(f.cleanup["ok"], f.cleanup)

    async def test_partial_start_actual_station_failure_reaps_daemon_and_station(self):
        f = ProcessFixture(Bounds(items=1))
        launch = f._start_child

        async def fail_station_control(role, payload):
            if role == "station":
                # Actual production start_unix_server fails: parent directory absent.
                payload["control"] = str(f.root / "absent" / "station.sock")
            return await launch(role, payload)

        with patch.object(f, "_start_child", side_effect=fail_station_control):
            with self.assertRaisesRegex(RuntimeError, "station.*readiness"):
                await f.__aenter__()
        self.assert_resources_removed(f)
        self.assertFalse(f.cleanup["ok"], f.cleanup)
        self.assertTrue(f.cleanup["processes"]["daemon"]["ready"])
        self.assertFalse(f.cleanup["processes"]["station"]["ready"])
        self.assertEqual(f.cleanup["processes"]["daemon"]["exit_code"], 0)
        self.assertNotEqual(f.cleanup["processes"]["station"]["exit_code"], 0)

    async def test_failure_after_both_ready_still_cleans_every_resource(self):
        f = ProcessFixture(Bounds(items=1))
        with patch("fixtures.processes.asyncio.start_server",
                   AsyncMock(side_effect=OSError("injected HTTP bind failure"))):
            with self.assertRaisesRegex(OSError, "injected HTTP"):
                await f.__aenter__()
        self.assert_resources_removed(f)
        self.assertTrue(f.cleanup["ok"], f.cleanup)
        self.assertTrue(all(r["ready"] for r in f.cleanup["processes"].values()))

    async def test_process_start_exception_closes_unstarted_handle(self):
        f = ProcessFixture(Bounds(items=1))
        with patch("multiprocessing.process.BaseProcess.start", side_effect=OSError("injected spawn failure")):
            with self.assertRaisesRegex(OSError, "injected spawn"):
                await f.__aenter__()
        self.assertTrue(f.cleanup["tasks_done"] and f.cleanup["temporary_state_removed"], f.cleanup)
        self.assertTrue(f.cleanup["processes_reaped"], f.cleanup)
        self.assertFalse(f.cleanup["processes"]["daemon"]["started"])
        self.assertTrue(f.cleanup["processes"]["daemon"]["handle_closed"])

    async def test_readiness_timeout_reaps_started_child(self):
        f = ProcessFixture(Bounds(items=1))
        with patch("fixtures.processes.STARTUP_SECONDS", 0):
            with self.assertRaises(TimeoutError):
                await f.__aenter__()
        self.assert_resources_removed(f)
        self.assertTrue(f.cleanup["processes"]["daemon"]["started"])
        self.assertFalse(f.cleanup["processes"]["daemon"]["ready"])

    async def test_stopped_child_requires_kill_is_reaped_and_reports_failure(self):
        f = ProcessFixture(Bounds(items=1))
        await f.__aenter__()
        try:
            os.kill(f.children["station"].pid, signal.SIGSTOP)
            # Stop delivery is asynchronous; waitpid WUNTRACED proves the stop.
            async with asyncio.timeout(1):
                while True:
                    pid, status = os.waitpid(f.children["station"].pid,
                                            os.WNOHANG | os.WUNTRACED)
                    if pid and os.WIFSTOPPED(status):
                        break
                    await asyncio.sleep(.01)
            with patch("fixtures.processes.TERM_SECONDS", .05):
                await f.close()
        finally:
            await f.close()
        self.assert_resources_removed(f)
        self.assertFalse(f.cleanup["ok"], f.cleanup)
        self.assertTrue(f.cleanup["processes"]["station"]["kill_sent"])
        self.assertEqual(f.cleanup["processes"]["daemon"]["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
