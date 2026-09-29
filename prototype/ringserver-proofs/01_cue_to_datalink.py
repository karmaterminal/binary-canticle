"""Proof 01: signed UDP cue -> canticle_receptor -> DataLink WRITE -> ringserver -> DataLink READ.

Closes the gap named in issue #49: the prototype's private DataLinkPublisher seam
(prototype/ringserver-udp-cue/canticle_receptor/_publisher.py) is a bare Protocol.
This script supplies a scratch adapter for it and shows the round trip against a
real ringserver. It also writes one miniSEED3 text record and lists streams over
SeedLink v4 INFO, to show which formats ringserver exposes to SeedLink clients.

Requires: canticle_receptor installed (pip install -e ../ringserver-udp-cue),
simpledali, simplemseed, and a running ringserver (see run.sh).
"""

import asyncio
import json
import socket
import struct
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import simpledali
import simplemseed
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle_receptor import (
    IssuerPolicy,
    Notice,
    NoticeKind,
    NoticeReceptor,
    ReceptorState,
    UdpCueListener,
    encode_signed_notice,
)
from canticle_receptor._publisher import PublisherUnavailable

from _env import DLPORT, HOST, SLPORT


class RingserverDataLinkPublisher:
    """Scratch adapter implementing the private DataLinkPublisher seam."""

    def __init__(self, host=HOST, port=DLPORT):
        self.host, self.port = host, port

    def publish(self, v):
        async def go():
            async with simpledali.SocketDataLink(self.host, self.port) as dali:
                await dali.id("canticle-receptor", "local", 0, "python")
                body = {
                    "issuer": v.issuer,
                    "key_id": v.key_id,
                    "kind": v.notice.kind.value,
                    "subject": v.notice.subject,
                    "notice_id": v.notice.notice_id,
                    "issued_at": v.notice.issued_at,
                    "expires_at": v.notice.expires_at,
                }
                r = await dali.writeJSON(
                    "BC_CUE/JSON",
                    v.notice.issued_at * 1_000_000,
                    v.notice.expires_at * 1_000_000,
                    body,
                )
                if r.type != "OK":
                    raise PublisherUnavailable

        try:
            asyncio.run(go())
        except (OSError, ConnectionError) as e:
            raise PublisherUnavailable from e


async def read_back(n):
    async with simpledali.SocketDataLink(HOST, DLPORT) as dali:
        await dali.id("canticle-reader", "local", 0, "python")
        await dali.match("BC_CUE/JSON")
        r = await dali.positionEarliest()
        pid = int(r.value)
        out = []
        while len(out) < n:
            p = await asyncio.wait_for(dali.read(pid), 5)
            pid += 1
            if p.streamId == "BC_CUE/JSON":
                out.append((p.type, p.packetId, p.streamId, p.data.decode()[:120]))
        return out


async def write_ms3_text():
    h = simplemseed.MSeed3Header()
    h.starttime = datetime.now(timezone.utc)
    h.sampleRatePeriod = 1.0
    h.encoding = 0  # FDSN miniSEED3 encoding 0 = text
    txt = b"what is now and threat: port-scan burst from 10.0.0.7; ttl 60"
    h.numSamples = len(txt)
    ms3 = simplemseed.MSeed3Record(
        h, "FDSN:XX_CANT__L_O_G", txt, extraHeaders={"BC": {"ttl": 60, "lens": "threat"}}
    )
    async with simpledali.SocketDataLink(HOST, DLPORT) as dali:
        await dali.id("canticle-ms3", "local", 0, "python")
        r = await dali.writeMSeed3(ms3)
        print("ms3 write:", r.type, "len", len(ms3.pack()))


def seedlink_v4_info_streams():
    s = socket.create_connection((HOST, SLPORT), timeout=3)
    f = s.makefile("rb")
    s.sendall(b"SLPROTO 4.0\r\n")
    print("seedlink SLPROTO 4.0 ->", f.readline().strip())
    s.sendall(b"INFO STREAMS\r\n")
    hdr = f.read(17)
    assert hdr[:2] == b"SE", hdr
    plen = struct.unpack("<I", hdr[4:8])[0]
    f.read(hdr[16])  # station id
    info = json.loads(f.read(plen))
    s.close()
    for st in info.get("station", []):
        for stream in st.get("stream", []):
            print(f"seedlink INFO: station={st['id']} stream={stream['id']} format={stream['format']}")


def main():
    key = Ed25519PrivateKey.generate()
    state = ReceptorState(Path(tempfile.mkdtemp()) / "state.db")
    receptor = NoticeReceptor(
        issuers={"issuer-a": IssuerPolicy(keys={"key-a": key.public_key()})},
        state=state,
        publisher=RingserverDataLinkPublisher(),
    )
    now = int(time.time())
    packets = [
        encode_signed_notice(
            key,
            issuer="issuer-a",
            key_id="key-a",
            notice=Notice(
                kind=NoticeKind.AVAILABLE,
                subject="sha256:" + f"{now:056x}{i:08x}",
                notice_id=f"{now:024x}{i:08x}",
                issued_at=now,
                expires_at=now + 30,
            ),
        )
        for i in (1, 2)
    ]
    with UdpCueListener(receptor, port=0) as listener:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # the third send repeats packet 1: today's receptor rejects it as a replay,
            # which is the behaviour RFC-0001's carousel semantics must change (repeat = no-op)
            for p in packets + [packets[0]]:
                s.sendto(p, listener.address)
        for _ in range(3):
            print("receipt:", listener.receive_once(timeout=2))
    for row in asyncio.run(read_back(2)):
        print("dali read:", row)
    asyncio.run(write_ms3_text())
    seedlink_v4_info_streams()


if __name__ == "__main__":
    main()
