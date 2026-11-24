"""Direct two-key virtual-time negative control for the _pick turn invariant.

No sockets are read, no signatures are checked, and no wall-clock flood is used.
Only Intake, KeyQueue, StreamQueue and Bucket APIs present at a0862c3 are used.

Usage:
  PYTHONPATH=<tree>/prototype/canticle-station nice -n 19 \
    ~/.venvs/bc-fair/bin/python <this-file> <tree>
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

TREE = sys.argv[1]
sys.path.insert(0, str(Path(TREE) / "prototype" / "canticle-station"))

from canticle.intake import Intake
from canticle.manifest import Manifest, StationEntry
from canticle import wire


def public_bytes(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def run(tree: str) -> dict:
    keys = [Ed25519PrivateKey.generate() for _ in range(3)]
    entries = [
        StationEntry(f"s{n}", public_bytes(key), frozenset({1}), ("quiet",))
        for n, key in enumerate(keys)
    ]
    manifest = Manifest(entries)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    intake = Intake(sock, manifest, now_ms=lambda: 0, wake=lambda: None)

    k0, k1, k2 = [intake.keys[e.key_id] for e in entries]
    a0 = (0x7F000001 << 32) | 40001
    a1 = (0x7F000001 << 32) | 40002

    frame0 = wire.MAGIC + bytes([wire.VERSION, wire.KIND_BEACON]) + entries[0].key_id + bytes(32)
    frame2 = wire.MAGIC + bytes([wire.VERSION, wire.KIND_BEACON]) + entries[2].key_id + bytes([2]) + bytes(31)

    # k0 has a waiting datagram, but its stream bucket is exhausted.
    stream0 = k0.streams[wire.stream_id if False else next(iter(k0.streams))]
    stream0.bucket.tokens = 0.0
    intake.offer([(frame0, a0)])

    # k2 has a waiting established frame that can be served.
    intake.offer([(frame2, a1)])
    k2 = intake.keys[entries[2].key_id]

    before = list(intake._ready)
    order_before = [int(k is k0) for k in before]

    served = intake._pick(time.monotonic()) if False else None
    # Call take: k0 is passed, k2 is served. Repeat 20 times to expose whether
    # k0 retains or rotates behind k2.
    got_k0 = 0
    got_k2 = 0
    for _ in range(20):
        t = intake.take(1)
        if t:
            kid = t[0].data[4:12]
            got_k0 += kid == entries[0].key_id
            got_k2 += kid == entries[2].key_id
        stream0.bucket.tokens = 0.0

    sock.close()
    has_passed = hasattr(intake, "_passed")
    return {
        "base_api": not has_passed,
        "ready_before": order_before,
        "got_k0": got_k0,
        "got_k2": got_k2,
    }


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1]), sort_keys=True))
