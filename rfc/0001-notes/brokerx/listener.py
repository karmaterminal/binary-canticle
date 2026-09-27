"""Late-joining listeners. Measures time from join until each live item is first heard.
udp: N sockets each lease from the relay (LISTEN every 20 s); Bernoulli loss p emulated on receive.
nats: N NATS connections subscribing canticle.st1.> (TCP: link loss becomes delay, not loss).
Usage: listener.py udp RELAY_HOST:PORT | nats URL  [--n N --loss P --join S --listen S]
"""
import argparse, asyncio, json, os, random, statistics, time
from nacl.signing import SigningKey
import frame

ap = argparse.ArgumentParser()
ap.add_argument("backend", choices=["udp", "nats"])
ap.add_argument("target")
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--loss", type=float, default=0.0)
ap.add_argument("--join", type=float, default=5.0)
ap.add_argument("--listen", type=float, default=15.0)
ap.add_argument("--seed", default="station-seed-000000000000000000")
a = ap.parse_args()
vk = SigningKey(a.seed.encode()[:32].ljust(32, b"0")).verify_key
trust = {frame.key_id(vk): vk}


class Ear:
    def __init__(self):
        self.t0 = None; self.first = {}; self.dups = 0; self.lost = 0; self.expiry = {}; self.bad = 0

    def hear(self, b):
        if random.random() < a.loss:
            self.lost += 1; return
        try:
            kid, m = frame.decode(b, trust)
        except Exception:
            self.bad += 1; return
        k = (kid, m[frame.K_EPOCH], m[frame.K_STREAM], m[frame.K_SEQ])
        if k in self.first:
            self.dups += 1
            assert self.expiry[k] == m[frame.K_EXPIRES]  # remaining life never resets on repeat
            return
        self.first[k] = time.time() - self.t0; self.expiry[k] = m[frame.K_EXPIRES]


async def main():
    await asyncio.sleep(a.join)
    ears = [Ear() for _ in range(a.n)]
    loop = asyncio.get_running_loop()
    closers = []
    if a.backend == "udp":
        host, port = a.target.split(":")
        class P(asyncio.DatagramProtocol):
            def __init__(s, ear): s.ear = ear
            def datagram_received(s, data, addr): s.ear.hear(data)
        for e in ears:
            tr, _ = await loop.create_datagram_endpoint(lambda e=e: P(e), local_addr=("127.0.0.1", 0))
            e.t0 = time.time(); tr.sendto(b"LISTEN", (host, int(port))); closers.append(tr.close)
    else:
        import nats
        for e in ears:
            nc = await nats.connect(a.target)
            async def cb(msg, e=e): e.hear(msg.data)
            e.t0 = time.time(); await nc.subscribe("canticle.st1.>", cb=cb); closers.append(nc.close)
    await asyncio.sleep(a.listen)
    for c in closers:
        r = c()
        if asyncio.iscoroutine(r): await r
    firsts = [t for e in ears for t in e.first.values()]
    per_ear_all = [max(e.first.values()) if e.first else None for e in ears]
    print(json.dumps({"backend": a.backend, "n": a.n, "loss": a.loss, "pid": os.getpid(),
        "items_heard_mean": statistics.mean(len(e.first) for e in ears),
        "first_hear_p50_s": round(statistics.median(firsts), 3) if firsts else None,
        "first_hear_p95_s": round(sorted(firsts)[int(0.95 * len(firsts)) - 1], 3) if firsts else None,
        "all_items_heard_max_s": round(max(x for x in per_ear_all if x is not None), 3) if firsts else None,
        "dups_per_ear": statistics.mean(e.dups for e in ears), "bad": sum(e.bad for e in ears)}), flush=True)

asyncio.run(main())
