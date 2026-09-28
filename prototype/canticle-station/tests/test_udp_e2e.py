"""End to end over real loopback UDP and the unix control socket."""

import asyncio
import os
import socket
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import runner, wire
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class UdpEndToEndTest(unittest.TestCase):
    def test_sing_listen_hush_over_loopback(self):
        sk = Ed25519PrivateKey.generate()
        m = Manifest([StationEntry("cael", wire.public_key_bytes(sk), frozenset({1, 3}), ("chatter", "lens.threat"))])
        st = Station(sk, [StreamConfig("chatter"), StreamConfig("lens.threat", cls="live-state")], epoch=1,
                     now_ms=runner.now_ms(), grant=m.entry(wire.key_id(wire.public_key_bytes(sk))))
        port = free_port()
        control = os.path.join(tempfile.mkdtemp(), "station.sock")
        events = []

        async def scenario():
            stop_listener, stop_station = asyncio.Event(), asyncio.Event()
            lst_task = asyncio.create_task(runner.run_listener(Listener(m, warmup=False, ephemeral=True), ("127.0.0.1", port), events.append, stop=stop_listener))
            st_task = asyncio.create_task(runner.run_station(st, [("127.0.0.1", port)], control, stop_station))
            while not os.path.exists(control):
                await asyncio.sleep(0.02)
            loop = asyncio.get_running_loop()
            ask = lambda req: loop.run_in_executor(None, runner.control_request, control, req)
            r1 = await ask({"op": "sing", "stream": "chatter", "text": "port-scan burst from 10.0.0.7", "ttl": 30})
            r2 = await ask({"op": "sing", "stream": "lens.threat", "text": "threat: elevated", "state_key": "now"})
            await asyncio.sleep(2.3)  # immediate copy + burst at +1 s and +2 s
            r3 = await ask({"op": "hush", "stream": "chatter", "seq": r1["seq"]})
            status = await ask({"op": "status"})
            await asyncio.sleep(1.2)
            stop_station.set()          # the station sends its goodbye beacon on the way out
            await st_task
            await asyncio.sleep(0.3)
            stop_listener.set()
            await lst_task
            return r1, r2, r3, status

        r1, r2, r3, status = asyncio.run(scenario())
        self.assertTrue(r1["ok"] and r2["ok"] and r3["ok"], (r1, r2, r3))
        items = [e for e in events if e.kind == "item"]
        self.assertEqual(sorted((e.stream, e.seq) for e in items), [("chatter", 1), ("lens.threat", 1)])  # once each
        self.assertEqual({e.data.get("text") for e in items}, {"port-scan burst from 10.0.0.7", "threat: elevated"})
        self.assertIn("withdrawn", [e.kind for e in events])
        presence = [e.data["state"] for e in events if e.kind == "presence"]
        self.assertEqual(presence[0], "ROOT_UNKNOWN")
        self.assertEqual(presence[-1], "UNOBSERVABLE:signed_off")  # goodbye on shutdown
        self.assertEqual([x["kind"] for x in status["streams"]["chatter"]["on_air"]], ["pluck"])
        self.assertFalse(os.path.exists(control))  # removed on shutdown


if __name__ == "__main__":
    unittest.main()
