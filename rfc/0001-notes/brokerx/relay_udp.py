"""Minimal canticle relay ("membrane" skeleton): verify + allowlist + dedup-free forward + lease fan-out.
Ingress from stations on --in port; listeners send b"LISTEN" to --out port every ~20 s; lease lapses at 75 s.
(No cookie round-trip here: this is a footprint/complexity control, not a hardened relay.)
"""
import argparse, os, select, socket, sys, time
from nacl.signing import SigningKey
import frame

ap = argparse.ArgumentParser()
ap.add_argument("--in-port", type=int, default=47110)
ap.add_argument("--out-port", type=int, default=47111)
ap.add_argument("--run", type=float, default=60)
ap.add_argument("--seed", default="station-seed-000000000000000000")
a = ap.parse_args()
vk = SigningKey(a.seed.encode()[:32].ljust(32, b"0")).verify_key
trust = {frame.key_id(vk): vk}

sin = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sin.bind(("127.0.0.1", a.in_port))
sout = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sout.bind(("127.0.0.1", a.out_port))
leases = {}  # (ip, port) -> expiry
stats = {"in": 0, "bad": 0, "out": 0}
t_end = time.time() + a.run
while time.time() < t_end:
    r, _, _ = select.select([sin, sout], [], [], 0.5)
    now = time.time()
    if sout in r:
        msg, addr = sout.recvfrom(64)
        if msg == b"LISTEN":
            leases[addr] = now + 75
    if sin in r:
        b, _ = sin.recvfrom(1500)
        stats["in"] += 1
        try:
            frame.decode(b, trust)
        except Exception:
            stats["bad"] += 1
            continue
        for addr, exp in list(leases.items()):
            if exp < now:
                del leases[addr]
                continue
            sout.sendto(b, addr); stats["out"] += 1
print({**stats, "leases": len(leases), "pid": os.getpid()}, flush=True)
