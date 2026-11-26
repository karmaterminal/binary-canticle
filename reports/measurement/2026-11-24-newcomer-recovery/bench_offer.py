"""offer() per datagram, as the reader pays it, on a tree's own Intake (no thread, virtual time, no signatures). A diagnostic of
the reader's cost, not a row: it decides nothing, and the socket's drops are what E1 and E2 report.

Usage: bench_offer.py <tree's prototype/canticle-station> <shape> <datagrams>      (python -B -I; one tree a process)
  A tree is a ``git archive`` of prototype/canticle-station. Run the trees interleaved, many times, and take the minimum: on a
  shared host the median is the neighbours'.
Shapes (16 listed keys; the flood claims key 0 at R datagrams a second, in batches of READ_BATCH, while the loop serves
CHECK_RATE checks a second that all fail, as in #171's R rows):
  fixed    forgeries from 40 ports held open                (R3, N0c)
  fixed4   forgeries from 4 ports held open                 (R3: two producers, a few sockets each)
  churn    forgeries, each from a port not used for 28 000   (R3c, N0: the kernel's ephemeral range turning over)
  replay   copies of 64 old beacons that were accepted      (R4a/R4b: counted before any queue)
Prints one JSON line: microseconds of offer() per datagram, and the intake's counters."""

import json
import socket
import struct
import sys
import time

tree, shape, total = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, tree)

from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import intake, runner, wire
from canticle.ids import stream_id
from canticle.manifest import Manifest, StationEntry

R = 700_000.0
clock = [1_000.0]
mock.patch("canticle.intake.time.monotonic", lambda: clock[0]).start()
now_ms = lambda: int(clock[0] * 1000)

sks = [Ed25519PrivateKey.generate() for _ in range(16)]
manifest = Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",)) for n, sk in enumerate(sks)])
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 0))
it = intake.Intake(sock, manifest, now_ms=now_ms, wake=lambda: None)
LO = socket.inet_aton("127.0.0.1")


def addr(port: int) -> int:
    """A sockaddr_in's first 8 bytes as the reader gives them."""
    return struct.unpack("@Q", struct.pack("@H", socket.AF_INET) + struct.pack("!H", port) + LO)[0]


def item(sk, seq):
    t = 1_700_000_000_000
    return wire.encode_item(sk, wire.Item(epoch=5, stream=stream_id("chatter"), seq=seq, issued_at=t, body=b"x" * 40, scope=1,
                                          cls=1, ctype=1, expires_at=t + 60_000_000))


base = item(sks[0], 1)
forged = [base[:-64] + n.to_bytes(32, "big") + base[-32:] for n in range(8192)]
if shape == "replay":
    beacons = [wire.encode_beacon(sks[0], wire.Beacon(epoch=5, bseq=n + 1, wallclock=1, next_beacon_ms=1000,
                                                      profile="canticle-regulation/1", streams=(), b_station=16_000)) for n in range(64)]
    for b in beacons:                                   # accepted once, from the station's own port
        it.offer([(b, addr(9))])
        for t in it.take(32):
            it.remember(t, (t.data[4:12], 5, 0, 1), now_ms() + 10**9)
            it.settle(t, True, True)
ports = {"fixed": 40, "fixed4": 4}.get(shape)
batch_n = intake.READ_BATCH
step = batch_n / R
spent, sent, n, owed = 0.0, 0, 0, 0.0
while sent < total:
    batch = []
    for _ in range(batch_n):
        if shape == "replay":
            batch.append((beacons[n % 64], addr(40_000 + n % 4)))
        else:
            port = 32_768 + (n % ports if ports else n % 28_000)
            batch.append((forged[n % len(forged)], addr(port)))
        n += 1
    t0 = time.perf_counter()
    it.offer(batch)
    spent += time.perf_counter() - t0
    sent += batch_n
    clock[0] += step
    owed += step * intake.CHECK_RATE                   # the loop's turns meanwhile, every check failing
    while owed >= 1:
        got = it.take(min(32, int(owed)))
        if not got:
            owed = 0
            break
        for t in got:
            it.settle(t, False, False)
        owed -= len(got)
s = it.stats()
print(json.dumps({"shape": shape, "us_per_datagram": 1e6 * spent / sent, "read": s["read"], "copies": s["copies"],
                  "repeats": s["repeats"], "unverified": s["unverified"], "reserved": s.get("reserved"),
                  "refused": s["refused"]}))
