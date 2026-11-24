"""A sustained flood of forged frames from N source ports, churned or fixed. One JSON line when its first datagram is out, one
of totals at the end. Usage: PYTHONPATH=<prototype/canticle-station> forged_flood.py (see --help)

Pass 3's (codeagent/bc-173-pass3c, reports/measurement/2026-11-23-cold-start-recovery/), with one addition: ``--kid`` may be several
key ids, comma-joined, claimed in turn (each port claims every one of them). With one it sends what pass 3's sent.

``--churn``: N sockets open at once, and each datagram from a newly opened one that replaces the oldest (pass 2's churn,
spread over N). Without it: N sockets held open and used in turn. The frames are ``tests/flood.py``'s forgeries: distinct,
naming the newcomer's key and stream, every other one a beacon, each with an invalid signature that is checked.
"""

import argparse
import json
import os
import socket
import sys
import time
from collections import deque
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--tests", required=True, help="the directory of flood.py")
p.add_argument("--port", type=int, required=True)
p.add_argument("--kid", required=True, help="the key ids the forgeries name, in turn")
p.add_argument("--stream", required=True)
p.add_argument("--epoch", type=int, default=7)
p.add_argument("--rate", type=float, required=True)
p.add_argument("--ports", type=int, required=True)
p.add_argument("--churn", action="store_true")
p.add_argument("--smooth", action="store_true", help="each datagram when it is due, spinning between, not in 1 ms chunks")
p.add_argument("--index", type=int, default=0, help="which producer this is: its forgeries are its own")
p.add_argument("--duration", type=float, required=True)
a = p.parse_args()
sys.path.insert(0, a.tests)
from flood import SEQ0, Pace, forged_parts      # noqa: E402

BATCH = 1 if a.smooth else 50 if a.rate >= 50_000 else 10      # datagrams between looks at the clock: at most 1 ms of the flood
FIRST = SEQ0 + (a.index << 34)                  # no two producers forge the same bytes; still 8 bytes wide


def bound() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    return s


kids, dest = [bytes.fromhex(k) for k in a.kid.split(",")], ("127.0.0.1", a.port)
socks = deque(bound() for _ in range(a.ports))
seen = {s.getsockname()[1] for s in socks}
opened, sent, refreshed, per_s = a.ports, 0, -1.0, {}
pace = Pace(a.rate)
start = None
end = pace.t0 + a.duration
while (now := time.monotonic()) < end:
    if now - refreshed > 1.0:                   # a forgery past its own expiry would fail before its signature
        refreshed, parts = now, [[forged_parts(kid, a.stream, a.epoch, b) for kid in kids] for b in (False, True)]
    for _ in range(BATCH):
        turn = sent // a.ports
        head, tail = parts[turn // len(kids) % 2][turn % len(kids)]         # each port sends both kinds, of every key
        sent += 1
        if a.churn:
            socks.popleft().close()
            s = bound()
            seen.add(s.getsockname()[1])
            opened += 1
        else:
            s = socks.popleft()
        socks.append(s)
        s.sendto(head + (FIRST + sent).to_bytes(8, "big") + tail + os.urandom(32) + sent.to_bytes(8, "little") + bytes(24), dest)
        if start is None:
            start = time.monotonic()
            print(json.dumps({"t0": start}), flush=True)
    s_ = int(now - start) if now >= start else 0
    per_s[s_] = per_s.get(s_, 0) + BATCH
    if a.smooth:
        while sent >= (time.monotonic() - pace.t0) * a.rate:
            pass
    else:
        pace.wait(sent)
stop = time.monotonic()
print(json.dumps({"t0": start, "t1": stop, "sent": sent, "opened": opened, "sources": len(seen),
                  "per_s": [per_s.get(i, 0) for i in range(int(stop - start))]}), flush=True)
