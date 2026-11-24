"""What one copy of a newcomer's frame is worth, against the flood's rate: the real ``Intake`` of a tree in virtual time, with no
sockets, no signatures and no scheduling noise. Usage: newcomer_model.py <prototype/canticle-station> [seconds] [rate,...]

A flood of R/s forged frames, every other one a beacon, each from a source of its own (churn: any of 28 232 ports of one host) or
from N fixed ports, arrives evenly (``smooth``), or once a millisecond with a silent rest, as a paced sender's does (``bursts``). A
newcomer on the same host sends distinct items and beacons, ten a second, at random moments, and is never made known, so every
copy meets the same queue. The event loop serves every millisecond; a check is free, so only the code's own budgets and
places decide. Printed: the share of its copies that were ever verified, and, for the crowd's lane it happens to hash to,
the spread over salts. (Not run beside a measurement.)"""

import random
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from canticle import cbor, intake, wire                                   # noqa: E402
from canticle.ids import stream_id                                        # noqa: E402
from canticle.manifest import Manifest, StationEntry                      # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey    # noqa: E402

SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
RATES = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [5_000, 20_000, 50_000, 100_000, 200_000]
SK = Ed25519PrivateKey.generate()
KID = wire.key_id(wire.public_key_bytes(SK))
HOST = 0x0100007F << 32 | 2            # a sockaddr_in's first 8 bytes, as the reader gives them
SEQ0 = 2**40


def port(n: int) -> int:
    return HOST | int.from_bytes(n.to_bytes(2, "big"), "little") << 16


def parts(kind):
    m = wire.beacon_map(wire.Beacon(epoch=7, bseq=SEQ0, wallclock=1, next_beacon_ms=1000, profile="canticle-regulation/1",
                                    streams=(), b_station=16_000)) if kind == wire.KIND_BEACON else wire.item_map(
        wire.Item(epoch=7, stream=stream_id("quiet"), seq=SEQ0, issued_at=1, expires_at=60_001, cls=1, ctype=1, body=b"x", scope=1))
    return (wire.MAGIC + bytes([wire.VERSION, kind]) + KID + cbor.encode(m)).split(SEQ0.to_bytes(8, "big"))


P = [parts(wire.KIND_ITEM), parts(wire.KIND_BEACON)]


def frame(n, kind):
    return P[kind][0] + (SEQ0 + n).to_bytes(8, "big") + P[kind][1] + bytes(64)


def run(rate, ports, bursts, seed):
    rng = random.Random(seed)
    clock = [1_000.0]
    intake.time.monotonic = lambda: clock[0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    i = intake.Intake(sock, Manifest([StationEntry("quiet", wire.public_key_bytes(SK), frozenset({1, 3}), ("quiet",))]),
                      now_ms=lambda: 1, wake=lambda: None)
    sock.close()
    n, mine, got, sent = 0, {}, 0, 0
    quanta, dt = int(SECONDS * 1000), 0.001
    slices = 1 if bursts else 10       # smooth: ten slices of each millisecond, with the turn at a random one
    per = rate * dt / slices
    owed = 0.0
    fixed = [port(p) for p in rng.sample(range(32_768, 61_000), ports)] if ports else None
    me = port(31_000)
    for ms in range(quanta):
        turn, tell = rng.randrange(slices + 1), rng.randrange(slices) if rng.random() < 0.01 else -1
        tell_at = rng.random()          # where in the slice (smooth) or in the millisecond (bursts) its copy falls
        for s in range(slices):
            if s == turn % slices:
                for t in i.take(32):
                    i.settle(t, False, False)
                    if t.data in mine:
                        got += mine.pop(t.data)
            owed += per
            flood = []
            while owed >= 1:
                owed -= 1
                n += 1
                flood.append((frame(n, n // (ports or 1) % 2), fixed[n % ports] if ports else port(rng.randrange(32_768, 61_000))))
            if s == tell:
                n += 1
                f = frame(n, n % 2)
                mine[f] = 1
                sent += ms > 2_000      # after the bursts of the buckets are spent
                if ms <= 2_000:
                    mine[f] = 0
                flood.insert(0 if bursts and tell_at > 0.5 else rng.randrange(len(flood) + 1), (f, me))
            if flood:
                i.offer(flood)
            clock[0] += dt / slices
    return got, sent


print("| flood | arrives | R, /s | copies sent | copies verified | share | C/R with C = 1 000/s |")
print("|---|---|---|---|---|---|---|")
for ports, label in ((0, "churn"), (40, "fixed, 40 ports"), (200, "fixed, 200 ports")):
    for bursts in (False, True):
        for rate in RATES:
            rs = [run(rate, ports, bursts, seed) for seed in range(4)]
            got, sent = sum(g for g, _ in rs), sum(s for _, s in rs)
            print(f"| {label} | {'once a ms' if bursts else 'smooth'} | {rate:,} | {sent} | {got} | {got / sent:.1%} "
                  f"({', '.join(f'{g / s:.0%}' for g, s in rs)}) | {min(1, 1_000 / rate):.1%} |", flush=True)
