"""How many event-loop callbacks one second of a churned 20 000/s forged flood posts, per turn the loop can run (virtual time, the tree's
own Intake, no sockets or signatures). Usage: wakes.py <prototype/canticle-station>"""
import random, socket, sys
from pathlib import Path
sys.dont_write_bytecode = True
tree = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(tree))
from canticle import cbor, intake, wire
from canticle.ids import stream_id
from canticle.manifest import Manifest, StationEntry
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
SK = Ed25519PrivateKey.generate(); KID = wire.key_id(wire.public_key_bytes(SK)); SEQ0 = 2**40
m = [wire.item_map(wire.Item(epoch=7, stream=stream_id("quiet"), seq=SEQ0, issued_at=1, expires_at=60_001, cls=1, ctype=1, body=b"x", scope=1)),
     wire.beacon_map(wire.Beacon(epoch=7, bseq=SEQ0, wallclock=1, next_beacon_ms=1000, profile="canticle-regulation/1", streams=(), b_station=16_000))]
P = [(wire.MAGIC + bytes([wire.VERSION, k]) + KID + cbor.encode(x)).split(SEQ0.to_bytes(8, "big")) for k, x in zip((wire.KIND_ITEM, wire.KIND_BEACON), m)]
clock = [1000.0]; intake.time.monotonic = lambda: clock[0]
wakes = [0]
def wake(): wakes[0] += 1
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
i = intake.Intake(s, Manifest([StationEntry("quiet", wire.public_key_bytes(SK), frozenset({1, 3}), ("quiet",))]), now_ms=lambda: 1, wake=wake); s.close()
rng = random.Random(1); n = 0; per_turn = []
HOST = 0x0100007F << 32 | 2
TURN_MS = 1.6; owed = 0.0; turns = 0
narrow = not hasattr(intake, "KeyQueue")
for ms in range(3000):
    batch = []
    for _ in range(20):
        n += 1
        f = P[n % 2][0] + (SEQ0 + n).to_bytes(8, "big") + P[n % 2][1] + bytes(64)
        batch.append(f if narrow else (f, HOST | int.from_bytes(rng.randrange(32768, 61000).to_bytes(2, "big"), "little") << 16))
    i.offer(batch)
    clock[0] += 0.001
    owed += 1 / TURN_MS
    while owed >= 1:
        owed -= 1; turns += 1
        for t in i.take(32):
            i.settle(False) if narrow else i.settle(t, False, False)
print(tree.parents[1].name, "batches", 3000, "callbacks posted", wakes[0], "turns run", turns, "-> callbacks left queued", max(0, wakes[0] - turns))
