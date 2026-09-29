"""Proof 04: SeedLink v4 `DATA ALL <now>` acts as a TTL filter when a record's end time == expiry.

Three miniSEED3 text items are written with TTL encoded as the record span
(sampleRate = nbytes / ttl, so end_time = issued + ttl): two already expired, one live.
A v4 client asking for data with end time after <now> should get only the live one:
the "on-air set" catch-up query for late joiners on the TCP replay tier.
"""

import asyncio
import socket
import struct
from datetime import datetime, timedelta, timezone

import simpledali
import simplemseed

from _env import DLPORT, HOST, SLPORT

STATION = "XX_TTL"


async def put(label, issued, ttl):
    h = simplemseed.MSeed3Header()
    h.starttime = issued
    h.encoding = 0
    txt = f'{{"item":"{label}","ttl":{ttl}}}'.encode()
    h.numSamples = len(txt)
    h.sampleRatePeriod = len(txt) / ttl  # span = N / rate = ttl seconds -> end_time = expiry
    ms3 = simplemseed.MSeed3Record(h, f"FDSN:{STATION}__L_O_G", txt, extraHeaders={"BC": {"ttl": ttl}})
    async with simpledali.SocketDataLink(HOST, DLPORT) as d:
        await d.id("ttl", "local", 0, "py")
        r = await d.writeMSeed3(ms3)
    print("wrote", label, "issued", issued.isoformat(timespec="seconds"), "ttl", ttl,
          "end", ms3.endtime.isoformat(timespec="seconds"), r.type)


def main():
    now = datetime.now(timezone.utc)
    asyncio.run(put("expired-a", now - timedelta(seconds=120), 30))
    asyncio.run(put("expired-b", now - timedelta(seconds=90), 60))
    asyncio.run(put("live-c", now - timedelta(seconds=10), 300))

    s = socket.create_connection((HOST, SLPORT), timeout=3)
    f = s.makefile("rb")
    start = now.strftime("%Y-%m-%dT%H:%M:%S.0Z")
    for c in ["SLPROTO 4.0", f"STATION {STATION}", "SELECT *", f"DATA ALL {start}"]:
        s.sendall(c.encode() + b"\r\n")
        print(c, "->", f.readline().strip())
    s.sendall(b"END\r\n")
    try:
        while True:
            hdr = f.read(17)
            if len(hdr) < 17:
                break
            plen = struct.unpack("<I", hdr[4:8])[0]
            f.read(hdr[16])
            body = f.read(plen)
            rec = simplemseed.unpackMSeed3Record(body)
            print("received:", hdr[:4], rec.identifier, body[-rec.header.dataLength:].decode())
    except (socket.timeout, TimeoutError):
        print("(no more packets)")
    s.close()


if __name__ == "__main__":
    main()
