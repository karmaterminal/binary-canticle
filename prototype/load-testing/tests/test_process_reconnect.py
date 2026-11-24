"""A real client reconnect, not daemon recovery or host custody acceptance."""
import asyncio
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "canticle-station"))
from fixtures.loopback import Bounds
from fixtures.processes import ProcessFixture
from canticle.records import MAX_LINE, RECORD_V


@unittest.skipUnless(sys.platform == "linux", "local process fixture requires Linux")
class RecordReconnectTest(unittest.IsolatedAsyncioTestCase):
    async def test_new_offer_after_client_reconnect_keeps_identity_boundary(self):
        f = ProcessFixture(Bounds(items=2))
        async with f:
            first = await f.offer(0)
            self.assertTrue(first["delivered"], first)
            before = f.report()
            old_task = next(t for t in f.tasks if t.get_name() == "record-v1-listener")
            old_task.cancel()
            await asyncio.gather(old_task, return_exceptions=True)
            f.tasks.remove(old_task)
            f.client_writer.close()
            await f.client_writer.wait_closed()
            async with asyncio.timeout(2):
                reader, f.client_writer = await asyncio.open_unix_connection(
                    str(f.root / "run" / "daemon.sock"), limit=MAX_LINE)
                records = [json.loads(await reader.readline()) for _ in range(2)]
            self.assertEqual([r["type"] for r in records], ["hello", "landing_state"])
            self.assertTrue(all(r["v"] == RECORD_V for r in records))
            self.assertEqual(records[-1]["run"], f.record_run)
            f.record_run, f.rec_seq = records[-1]["run"], records[-1]["rec_seq"]
            f.task(f.read_records(reader), "record-v1-listener")
            second = await f.offer(1)
            self.assertTrue(second["delivered"], second)
            self.assertNotEqual(first["identity"], second["identity"])
            self.assertEqual(second["frame_sha256"], second["record_frame_sha256"])
            self.assertLessEqual(second["first_arrival_ns"], second["complete_record_ns"])
            after = f.report()
            self.assertEqual({k:v["pid"] for k,v in before["processes"].items()},
                             {k:v["pid"] for k,v in after["processes"].items()})
            self.assertTrue(after["production_tasks_alive"] and after["accounting"], after)
            self.assertEqual(after["counts"]["delivered"], 2)
            self.assertEqual(after["counts"]["missed"], 0)
            self.assertEqual(after["counts"]["duplicate_surface_records"], 0)
            self.assertEqual(after["errors"], [])
        self.assertTrue(f.cleanup["ok"] and f.cleanup["processes_reaped"], f.cleanup)


if __name__ == "__main__":
    unittest.main()
