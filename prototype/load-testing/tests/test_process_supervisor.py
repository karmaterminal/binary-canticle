"""The k6 supervisor timeout must reap production children, not just k6."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "canticle-station"))
import run as supervisor
from k6_support import k6_binary


@unittest.skipUnless(sys.platform == "linux", "local process fixture requires Linux")
class ProcessSupervisorTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_k6_timeout_reaps_all_three_children(self):
        binary = k6_binary(self)
        real_wait = asyncio.wait_for

        async def accelerated(aw, timeout):
            return await real_wait(aw, .05 if timeout == 55 else timeout)

        with tempfile.TemporaryDirectory(prefix="canticle-process-timeout-") as t:
            out = Path(t) / "receipt"
            args = SimpleNamespace(out=str(out), k6=str(binary), processes=True)
            with patch.object(supervisor.asyncio, "wait_for", accelerated):
                code = await supervisor.run(args, supervisor.Bounds(items=16, pace_ms=1000))
            self.assertEqual(code, 1)
            cleanup = json.loads((out / "cleanup.json").read_text())
            process = json.loads((out / "process.json").read_text())
            failure = json.loads((out / "failure.json").read_text())
            self.assertTrue(failure["error"].startswith("TimeoutError"), failure)
            self.assertTrue(process["child_started"] and process["child_reaped"], process)
            self.assertTrue(cleanup["ok"] and cleanup["processes_reaped"], cleanup)
            self.assertEqual(set(cleanup["processes"]), {"station", "daemon"})
            self.assertTrue(all(r["reaped"] and r["exit_code"] == 0
                                for r in cleanup["processes"].values()), cleanup)

    async def test_group_exiting_between_term_timeout_and_kill_is_reaped(self):
        child = SimpleNamespace(pid=12345, returncode=None)
        original_wait = AsyncMock(side_effect=[TimeoutError(), -15])
        async def wait_for_exit():
            try:
                return await original_wait()
            finally:
                if original_wait.await_count == 2:
                    child.returncode = -15
        child.wait = wait_for_exit
        with patch.object(supervisor.os, "killpg", side_effect=[None, ProcessLookupError()]) as kill:
            self.assertTrue(await supervisor.stop_child(child))
        self.assertEqual(kill.call_count, 2)
        self.assertEqual(original_wait.await_count, 2)


if __name__ == "__main__":
    unittest.main()
