"""What placing a datagram and serving a turn cost with every lane of every stream open (🌫's condition on #173): no
socket traffic, the intake's own calls timed. Usage: scheduler_work.py <prototype/canticle-station> <keys> <streams per key>"""
import gc, socket, sys, time
from pathlib import Path
station, K, S = Path(sys.argv[1]).resolve(), int(sys.argv[2]), int(sys.argv[3])
sys.path[:0] = [str(station), str(station / "tests")]
import test_intake as T
from canticle import intake, runner, wire
from canticle.ids import stream_id
from canticle.manifest import Manifest, StationEntry

names = tuple(f"s{i}" for i in range(S))
sks = [T.Ed25519PrivateKey.generate() for _ in range(K)]
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 0))
it = intake.Intake(sock, Manifest([StationEntry(f"k{i}", wire.public_key_bytes(sk), frozenset({1}), names)
                                   for i, sk in enumerate(sks)]), now_ms=runner.now_ms, wake=lambda: None)


def source(host: int, port: int) -> int:
    """As the reader gives it: the sockaddr_in's first 8 bytes."""
    return int.from_bytes(b"\x02\x00" + port.to_bytes(2, "big") + (0x0A000000 + host).to_bytes(4, "big"), sys.byteorder)


STATION = source(1, 9)
for sk in sks:
    it.offer([(T.item(sk, 1, names[0]), STATION)])
    for t in it.take(8):
        it.settle(t, True, True)
frames = [T.item(sk, 10, s) for sk in sks for s in names]
n, batches = 0, []
for _ in range(2_000):                                   # every datagram from a source of its own
    b = []
    for f in frames:
        n += 1
        b.append((T.forge(f, n), source(2 + n % 60_000, 1 + n % 65_535)))
    batches.append(b)
t0 = time.perf_counter()
for b in batches:
    it.offer(b)
placed = (time.perf_counter() - t0) / n
lanes = [len(q.lanes) for k in it.keys.values() for s, q in k.streams.items() if s not in (intake.OTHER, intake.BEACON)]
for sk in sks:                                           # the strangers of every key have spent their budget
    key = it.keys[wire.key_id(wire.public_key_bytes(sk))]
    key.stranger_budget.tokens, key.stranger_budget.at = -1e6, time.monotonic()
    it.offer([(T.item(sk, 100 + j, names[0]), STATION) for j in range(10)])
it.checks.tokens = 1e9
gc.disable()
t0 = time.perf_counter()
batch = it.take(32)
turn = time.perf_counter() - t0
for t in batch:
    it.settle(t, True, True)
while it.take(32):
    pass
empty = []
for _ in range(200):
    t0 = time.perf_counter()
    assert not it.take(32)
    empty.append(time.perf_counter() - t0)
q = it.stats()["queued"]
size = sum(len(e[0]) for k in it.keys.values() for s in k.streams.values() for lane in s.lanes.values() for e in lane.queue)
print(f"| {K} x {S} | {min(lanes)}–{max(lanes)} | {q:,} ({size / 1024:,.0f} KiB) | {placed * 1e6:.1f} µs | "
      f"{len(batch)} in {turn * 1e3:.2f} ms | {sorted(empty)[100] * 1e3:.2f} ms |")
