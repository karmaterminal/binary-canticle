"""The k6 supervisor timeout must reap production children, not just k6."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "canticle-station"))
import run as supervisor


@unittest.skipUnless(sys.platform == "linux", "local process fixture requires Linux")
class ProcessSupervisorTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_k6_timeout_reaps_all_three_children(self):
        binary = Path("/home/figs/.local/bin/k6")
        if not binary.is_file():
            self.skipTest("optional local k6 executable absent")
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


if __name__ == "__main__":
    unittest.main()
