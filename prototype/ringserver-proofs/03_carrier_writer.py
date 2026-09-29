"""Proof 03 (helper): write a canticle-style "carrier wave" as miniSEED2 int32 records
for XX.CANT..LHZ (1 sample/s), plus one miniSEED3 text record, into ringserver via DataLink.

A carrier rendered on a seismic dashboard must VARY (ews de-means each record, so a
constant carrier draws a flat line). Here it is a sine; a real station would plot e.g.
the live-item count. Usage: python 03_carrier_writer.py [records]
"""

import asyncio
import math
import sys
from datetime import datetime, timedelta, timezone

import simpledali
import simplemseed

from _env import DLPORT, HOST


async def main(n):
    async with simpledali.SocketDataLink(HOST, DLPORT) as d:
        await d.id("canticle-carrier", "local", 0, "py")
        t0 = datetime.now(timezone.utc) - timedelta(seconds=60 * n)
        for i in range(n):
            nsamp = 60
            data = [int(1000 * math.sin(2 * math.pi * (i * nsamp + k) / 20)) for k in range(nsamp)]
            h = simplemseed.MiniseedHeader("XX", "CANT", "", "LHZ", t0 + timedelta(seconds=i * nsamp), nsamp, 1.0)
            msr = simplemseed.MiniseedRecord(h, data)
            r = await d.writeMSeed(msr)
            print("ms2 write", i, r.type, len(msr.pack()), flush=True)
        h3 = simplemseed.MSeed3Header()
        h3.starttime = datetime.now(timezone.utc)
        h3.sampleRatePeriod = 1.0
        h3.encoding = 0
        txt = b'{"lens":"threat","text":"port-scan burst","ttl":60}'
        h3.numSamples = len(txt)
        ms3 = simplemseed.MSeed3Record(h3, "FDSN:XX_CANT__L_O_G", txt, extraHeaders={"BC": {"ttl": 60}})
        r = await d.writeMSeed3(ms3)
        print("ms3 write", r.type, len(ms3.pack()), flush=True)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
