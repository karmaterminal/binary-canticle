"""Carousel station: signs each item once, re-emits the identical bytes every loop_ms (+-10% jitter)
until the item's absolute expires_at. Backends: raw UDP (to a relay) or NATS core publish.
Usage: station.py udp HOST:PORT | nats URL   [--items N --loop-ms L --ttl S --body B --run S]
"""
import argparse, asyncio, os, random, socket, time
from nacl.signing import SigningKey
import frame

ap = argparse.ArgumentParser()
ap.add_argument("backend", choices=["udp", "nats"])
ap.add_argument("target")
ap.add_argument("--items", type=int, default=20)
ap.add_argument("--loop-ms", type=int, default=1000)
ap.add_argument("--ttl", type=float, default=60)
ap.add_argument("--body", type=int, default=600)
ap.add_argument("--run", type=float, default=40)
ap.add_argument("--seed", default="station-seed-000000000000000000")
a = ap.parse_args()

sk = SigningKey(a.seed.encode()[:32].ljust(32, b"0"))
epoch = int(time.time())
items = []  # [bytes, expires_ms, loop_ms, next_due_s]
for seq in range(1, a.items + 1):
    b = frame.encode(sk, epoch, stream=7, seq=seq, ttl_s=a.ttl, body=os.urandom(a.body), loop_ms=a.loop_ms)
    items.append([b, int(time.time() * 1000 + a.ttl * 1000), a.loop_ms, time.time() + random.random() * a.loop_ms / 1000])


async def main():
    if a.backend == "udp":
        host, port = a.target.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send = lambda b: s.sendto(b, (host, int(port)))
    else:
        import nats
        nc = await nats.connect(a.target)
        send = lambda b: asyncio.ensure_future(nc.publish("canticle.st1.7", b))
    sent = 0
    t_end = time.time() + a.run
    while time.time() < t_end:
        now = time.time()
        live = [it for it in items if it[1] > now * 1000]
        if not live:
            break
        due = min(live, key=lambda it: it[3])
        if due[3] > now:
            await asyncio.sleep(due[3] - now)
            continue
        send(due[0]); sent += 1
        due[3] += due[2] / 1000 * random.uniform(0.9, 1.1)  # jittered loop, bytes never change
    print({"sent": sent, "pid": os.getpid()}, flush=True)
    if a.backend == "nats":
        await nc.flush(); await nc.close()

asyncio.run(main())
