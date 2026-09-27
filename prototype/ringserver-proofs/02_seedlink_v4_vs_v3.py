"""Proof 02: a miniSEED3 text item reaches a SeedLink v4 client intact; a v3.1 client
gets raw miniSEED3 bytes it cannot parse as miniSEED2.

This is why dashboards that speak SeedLink 3.1 with a miniSEED2 parser (ews-concept-new)
need numeric miniSEED2 channels (see 03_carrier_writer.py), or an upgrade to v4 + ms3.
"""

import asyncio
import socket
import struct
import time
from datetime import datetime, timezone

import simpledali
import simplemseed

from _env import DLPORT, HOST, SLPORT


def open_seedlink(cmds):
    s = socket.create_connection((HOST, SLPORT), timeout=4)
    f = s.makefile("rb")
    for c in cmds:
        s.sendall(c.encode() + b"\r\n")
        print("sl", c, "->", f.readline().strip(), flush=True)
    s.sendall(b"END\r\n")
    return s, f


async def write_ms3():
    h = simplemseed.MSeed3Header()
    h.starttime = datetime.now(timezone.utc)
    h.sampleRatePeriod = 1.0
    h.encoding = 0
    txt = b"what is now and healing: patch 4.2 rolled; ttl 60"
    h.numSamples = len(txt)
    ms3 = simplemseed.MSeed3Record(
        h, "FDSN:XX_CANT__L_O_G", txt, extraHeaders={"BC": {"ttl": 60, "lens": "healing"}}
    )
    async with simpledali.SocketDataLink(HOST, DLPORT) as d:
        await d.id("w", "local", 0, "py")
        print("ms3 write:", (await d.writeMSeed3(ms3)).type, flush=True)


def main():
    v4s, v4f = open_seedlink(["SLPROTO 4.0", "STATION XX_CANT", "SELECT *", "DATA"])
    v3s, _ = open_seedlink(["STATION CANT XX", "DATA"])
    asyncio.run(write_ms3())

    hdr = v4f.read(17)
    plen = struct.unpack("<I", hdr[4:8])[0]
    seq = struct.unpack("<Q", hdr[8:16])[0]
    sid = v4f.read(hdr[16])
    body = v4f.read(plen)
    rec = simplemseed.unpackMSeed3Record(body)
    print("v4 packet: sig", hdr[:2], "format", chr(hdr[2]), "seq", seq, "sid", sid, "len", plen)
    print("v4 decoded:", rec.identifier, "encoding", rec.header.encoding,
          "payload", body[-rec.header.dataLength:], "extra headers", rec.eh)

    time.sleep(0.5)
    v3s.settimeout(2)
    try:
        buf = v3s.recv(2048)
        print("v3 got", len(buf), "bytes; head", buf[:8], "record starts", buf[8:12],
              "is miniSEED3:", buf[8:10] == b"MS" and buf[10] == 3)
    except (socket.timeout, TimeoutError):
        print("v3: no data within timeout")
    v3s.close()
    v4s.close()


if __name__ == "__main__":
    main()
