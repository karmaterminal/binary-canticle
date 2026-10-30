"""Local-only Mirari path: fixture -> station control socket -> signed loopback frame -> listener."""
import asyncio
import importlib.util
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import runner, wire
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig

spec = importlib.util.spec_from_file_location("mirari_beacon", Path(__file__).with_name("beacon.py"))
beacon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beacon)


class MirariLoopbackTest(unittest.TestCase):
    def test_socket_publish_receiver_observation_and_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, auth, state, control = (root / n for n in ("source.jsonl", "auth.json", "state.json", "station.sock"))
            source.write_text(json.dumps({"actor": "alice", "origin": "actor", "shareable": True,
                                          "lineage": "local", "kind": "tool", "id": "step1",
                                          "topic": "checked tests", "raw_body": "PRIVATE BODY NOT FOR WIRE"}) + "\n")
            auth.write_text(json.dumps({"enabled": True, "actor": "alice", "station": "familiar",
                                        "source": str(source), "audience": "lan", "stream": "wake",
                                        "ttl_s": 3, "cadence_s": 30, "inactive_s": 60}))
            key = Ed25519PrivateKey.generate()
            manifest = Manifest([StationEntry("familiar", wire.public_key_bytes(key),
                                              frozenset({1}), ("wake",))])
            station = Station(key, [StreamConfig("wake")], epoch=1, now_ms=runner.now_ms(),
                              grant=manifest.entry(wire.key_id(wire.public_key_bytes(key))))
            listener = Listener(manifest, warmup=False, ephemeral=True)
            events = []
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]

            async def scenario():
                stop_station, stop_listener = asyncio.Event(), asyncio.Event()
                receiver = asyncio.create_task(runner.run_listener(listener, ("127.0.0.1", port), events.append,
                                                                    stop=stop_listener, tick_ms=50))
                sender = asyncio.create_task(runner.run_station(station, [("127.0.0.1", port)], str(control), stop_station))
                try:
                    for _ in range(100):
                        if control.exists():
                            break
                        await asyncio.sleep(0.01)
                    self.assertTrue(control.exists())
                    result = await asyncio.to_thread(beacon.tick, auth=auth, source=source, state=state,
                                                     actor="alice", socket_path=str(control))
                    self.assertEqual(result, "published")
                    for _ in range(100):
                        if any(e.kind == "item" and e.stream == "wake" for e in events):
                            break
                        await asyncio.sleep(0.05)
                    items = [e for e in events if e.kind == "item" and e.stream == "wake"]
                    self.assertEqual(len(items), 1)
                    self.assertIn("checked tests", items[0].data["text"])
                    self.assertNotIn("PRIVATE BODY", items[0].data["text"])
                    self.assertEqual(station.streams["wake"].head_seq, 1)
                    for _ in range(100):
                        if any(e.kind == "expired" and e.stream == "wake" for e in events):
                            break
                        await asyncio.sleep(0.05)
                    self.assertEqual(len([e for e in events if e.kind == "expired" and e.stream == "wake"]), 1)
                    self.assertEqual(listener.on_air(), [])
                    self.assertEqual(station.streams["wake"].head_seq, 1)
                finally:
                    stop_station.set()
                    stop_listener.set()
                    await sender
                    await receiver

            asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
