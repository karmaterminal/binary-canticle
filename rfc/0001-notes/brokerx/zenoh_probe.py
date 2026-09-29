"""Zenoh probe: carousel frames over a Zenoh UDP (unreliable) unicast link between two peers.
role pub: listens udp/127.0.0.1:7449, loops 20 signed frames every 1 s for --run s.
role sub: joins late, connects to the pub, reports first-hear times and RSS.
"""
import json, os, sys, time, random
import zenoh
from nacl.signing import SigningKey
import frame

role, run = sys.argv[1], float(sys.argv[2])
conf = zenoh.Config()
conf.insert_json5("scouting/multicast/enabled", "false")
if role == "pub":
    conf.insert_json5("listen/endpoints", '["udp/127.0.0.1:7449"]')
else:
    conf.insert_json5("connect/endpoints", '["udp/127.0.0.1:7449"]')
    conf.insert_json5("listen/endpoints", "[]")
rss = lambda: int([l for l in open(f"/proc/{os.getpid()}/status") if l.startswith("VmRSS")][0].split()[1])
s = zenoh.open(conf)
if role == "pub":
    sk = SigningKey(b"station-seed-000000000000000000".ljust(32, b"0"))
    items = [frame.encode(sk, 1, 7, q, ttl_s=60, body=os.urandom(600)) for q in range(1, 21)]
    pub = s.declare_publisher("canticle/st1/7")
    t_end = time.time() + run; sent = 0
    while time.time() < t_end:
        for b in items:
            pub.put(b); sent += 1
            time.sleep(1.0 / len(items) * random.uniform(0.9, 1.1))
    print(json.dumps({"role": "pub", "sent": sent, "rss_kB": rss()}))
else:
    vk = SigningKey(b"station-seed-000000000000000000".ljust(32, b"0")).verify_key
    trust = {frame.key_id(vk): vk}; first = {}; t0 = time.time()
    def cb(sample):
        kid, m = frame.decode(bytes(sample.payload.to_bytes()), trust)
        first.setdefault(m[frame.K_SEQ], time.time() - t0)
    sub = s.declare_subscriber("canticle/**", cb)
    time.sleep(run)
    print(json.dumps({"role": "sub", "heard": len(first), "all_heard_s": round(max(first.values()), 3) if first else None, "rss_kB": rss()}))
s.close()
