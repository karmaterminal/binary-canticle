"""Verify cost and admission cost per item, in isolation, on one pinned core of each type.

Steps, each timed over many frames (perf_counter_ns, one process, pinned with sched_setaffinity):
  ed25519_verify   the signature check alone (cryptography/OpenSSL), over the signed bytes
  cbor_roundtrip   CBOR decode + re-encode (wire.parse's determinism check)
  wire_parse       the whole admission parse: header, key lookup, CBOR, fields, time window, signature
  listener_hear    Listener.hear in receptor mode, no state file (verify + dedup + supersede + events)
  receptor_disk    Receptor.hear with its state file on the lab's ext4/NVMe disk: the daemon's per-item path,
                   write-ahead save included (json of the whole state, write, fsync file, rename, fsync dir)
  receptor_tmpfs   the same with the state file on /dev/shm (fsync is a no-op there): separates fsync from json
  fsync_small      atomic_write_json of a tiny object on the lab disk: the fixed cost of one durable save
  sign             encode_item (what a station pays once per item), for scale

Batches: frame v2 has no batch signature (RFC §9; batch roots are unbuilt, design §2.8), so per-batch
verify is "not measurable yet". Prints and writes one JSON document.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from mlib import HOME, Lab, entry, machine, percentile

from canticle import cbor, wire
from canticle.ids import CLASS_BY_NAME, CTYPES, SCOPES, stream_id
from canticle.listener import Listener, atomic_write_json
from canticle.manifest import Manifest
from canticle.records import Emitter, Receptor
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CORES = {"Cortex-X925": 19, "Cortex-A725": 14}
TEXT = CTYPES["text/plain; charset=utf-8"]


def frames_for(sk, n: int, size: int, epoch: int, sid: int, ttl_ms: int = 600_000) -> list[bytes]:
    now = time.time_ns() // 1_000_000
    out = []
    for i in range(n):
        body = (f"B|bench|{i}|".encode() + b"x" * size)[:size]
        it = wire.Item(epoch=epoch, stream=sid, seq=i + 1, issued_at=now, expires_at=now + ttl_ms,
                       cls=CLASS_BY_NAME["chatter"].code, ctype=TEXT, body=body, scope=SCOPES["lan"])
        out.append(wire.encode_item(sk, it))
    return out


def timed(fn, items) -> dict:
    ts = []
    for x in items:
        t = time.perf_counter_ns()
        fn(x)
        ts.append(time.perf_counter_ns() - t)
    us = [t / 1000 for t in ts]
    return {"n": len(us), "mean_us": round(statistics.fmean(us), 2), "p50_us": round(percentile(us, 50), 2),
            "p99_us": round(percentile(us, 99), 2), "per_core_per_s": round(1e6 / statistics.fmean(us))}


def main() -> int:
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    lab = Lab("verify")
    try:
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        names = ["s00000"]
        m = Manifest([entry("bench", sk, names)])
        sid = stream_id(names[0])
        epoch = int(time.time())
        res: dict = {"machine": machine(), "batches": "not measurable yet: frame v2 carries one Ed25519 signature per "
                     "datagram and the daemon verifies one per datagram; batch roots and membership proofs are unbuilt "
                     "(design §2.8, RFC §9)", "cores": {}}
        n = 3000
        for core_name, cpu in CORES.items():
            os.sched_setaffinity(0, {cpu})
            cres: dict = {"cpu": cpu}
            for label, size in (("64", 64), ("512", 512), ("max", 975)):
                fr = frames_for(sk, n, size, epoch, sid)
                # the largest body that still fits MAX_FRAME (1 100 B)
                while len(fr[0]) > wire.MAX_FRAME:
                    size -= 8
                    fr = frames_for(sk, n, size, epoch, sid)
                row = {"frame_bytes": len(fr[0]), "body_bytes": size}
                row["sign"] = timed(lambda i: frames_for(sk, 1, size, epoch, sid), range(300))
                row["ed25519_verify"] = timed(lambda f: pk.verify(f[-64:], wire.SIGN_DOMAIN + f[:-64]), fr)
                row["cbor_roundtrip"] = timed(lambda f: cbor.encode(cbor.decode(f[12:-64])), fr)
                now = time.time_ns() // 1_000_000
                row["wire_parse"] = timed(lambda f: wire.parse(f, m.resolve, now, 0), fr)
                lst = Listener(m, ephemeral=True, receptor_mode=True)
                row["listener_hear"] = timed(lambda f: lst.hear(f, time.time_ns() // 1_000_000), fr)
                # duplicates: the carousel's repeats (verify + dedup lookup, no state change)
                row["listener_hear_duplicate"] = timed(lambda f: lst.hear(f, time.time_ns() // 1_000_000), fr[:1000])
                cres[label] = row
            # the daemon's per-item path with its write-ahead save, as the state grows
            for where, base in (("disk", lab.state), ("tmpfs", Path("/dev/shm"))):
                d = Path(tempfile.mkdtemp(prefix="canticle-measure-2-", dir=base))
                try:
                    lst = Listener(m, state_path=d / "listener.json", receptor_mode=True)
                    rc = Receptor(lst, Emitter(), bind="127.0.0.1:0", now_ms=time.time_ns() // 1_000_000)
                    fr = frames_for(sk, 4000, 64, epoch + 1, sid)
                    curve = []
                    for start in range(0, len(fr), 250):
                        chunk = fr[start:start + 250]
                        s = timed(lambda f: rc.hear(f, time.time_ns() // 1_000_000), chunk)
                        curve.append({"dedup_entries_before": start, "state_bytes_after":
                                      os.path.getsize(d / "listener.json"), **s})
                    dup = timed(lambda f: rc.hear(f, time.time_ns() // 1_000_000), fr[:500])
                    cres[f"receptor_{where}"] = {"curve": curve, "duplicate": dup}
                finally:
                    shutil.rmtree(d, ignore_errors=True)
            d = Path(tempfile.mkdtemp(prefix="fsync-", dir=lab.state))
            cres["fsync_small"] = timed(lambda i: atomic_write_json(d / "x.json", {"i": i}), range(500))
            res["cores"][core_name] = cres
            print(core_name, json.dumps({k: (v["max"]["wire_parse"] if k == "max" else None) for k, v in [("max", cres)]}),
                  "fsync", cres["fsync_small"], flush=True)
        out.write_text(json.dumps(res, indent=1))
    finally:
        lab.close()
        lab.remove()
    return 0


if __name__ == "__main__":
    sys.exit(main())
