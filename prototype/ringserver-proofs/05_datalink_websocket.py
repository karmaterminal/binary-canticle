"""Proof 05: a JSON TTL item written over DataLink/TCP is readable by a browser-style
DataLink-over-WebSocket client at ws://<ring>:<SLPORT>/datalink.

Note: ringserver never serves */JSON packets over SeedLink (only */MSEED and */MSEED3),
so JSON items are a DataLink-only lane for custom consoles.
"""

import asyncio
import time

import simpledali

from _env import DLPORT, HOST, SLPORT


async def main():
    now = time.time()
    async with simpledali.SocketDataLink(HOST, DLPORT) as d:
        await d.id("canticle-publisher", "local", 0, "py")
        item = {"station": "XX_CANT", "lens": "healing", "text": "patch 4.2 rolled", "ttl": 60, "loop_hz": 0.1}
        r = await d.writeJSON("XX_CANT_LENS_HEALING/JSON", int(now * 1e6), int((now + 60) * 1e6), item)
        print("write:", r.type, r.value)
    async with simpledali.WebSocketDataLink(f"ws://{HOST}:{SLPORT}/datalink") as w:
        await w.id("browser-like", "local", 0, "py")
        await w.match(".*/JSON")
        p = await w.positionEarliest()
        print("position earliest:", p.type, p.value)
        pid = int(p.value)
        while True:
            pk = await w.read(pid)
            pid += 1
            if pk.streamId == "XX_CANT_LENS_HEALING/JSON":
                print("ws read:", pk.type, pk.streamId, pk.packetId, pk.data.decode()[:120])
                break


if __name__ == "__main__":
    asyncio.run(main())
