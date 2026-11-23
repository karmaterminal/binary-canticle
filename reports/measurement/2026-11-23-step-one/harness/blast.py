"""A producer that ignores the station regulator: signed frame v2 ITEMs straight onto UDP.

A compliant station (`canticle station`) sends each new item at once plus a 3-copy burst and
then loops it within B_station (16 kbit/s by default, RFC §7.5), so it never floods by itself.
This is the producer the §2.8 acceptance test asks for instead: one that holds a key the
manifest licenses (or forges one, or has none) and sends as fast as it is told. Frames are
built with the spike's own codec (`canticle.wire.encode_item`), so the daemon sees exactly
what a station would sign.

Modes:
  valid    every item a new (stream, seq), signed: each one costs the daemon a verify, a state
           save and a `frame` record.
  dup      one signed item sent over and over: a verify and a dedup lookup each, no record
           (what a carousel's repeats cost).
  forged   a licensed key id with a corrupted signature (R half, so S stays canonical): parsed in
           full, then rejected at verify (`bad_signature`).
  unknown  a key id the manifest doesn't list: rejected at the header (`unknown_key`).

Writes a JSON summary (sent, achieved rate, frame size) and, with --sample-log, one CSV line
per sampled item: idem, t_send_ns (CLOCK_MONOTONIC, the same clock the other probes use).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "prototype" / "canticle-station"))

from canticle import wire                                   # noqa: E402
from canticle.ids import CLASS_BY_NAME, CTYPES, SCOPES, stream_id  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

TEXT = CTYPES["text/plain; charset=utf-8"]


def body_for(size: int, tag: str, seq: int) -> bytes:
    head = f"B|{tag}|{seq}|".encode()
    return (head + b"x" * max(0, size - len(head)))[:max(size, len(head))]


def max_body(sk, epoch: int, sid: int, cls: int, ttl_ms: int) -> int:
    """The largest body whose ITEM still fits MAX_FRAME (1 100 B) with this run's field widths."""
    now = time.time_ns() // 1_000_000
    lo, hi = 1, wire.MAX_FRAME
    while lo < hi:
        mid = (lo + hi + 1) // 2
        it = wire.Item(epoch=epoch, stream=sid, seq=2**31, issued_at=now, expires_at=now + ttl_ms, cls=cls,
                       ctype=TEXT, body=b"x" * mid, scope=SCOPES["lan"])
        try:
            ok = len(wire.encode_item(sk, it)) <= wire.MAX_FRAME
        except ValueError:
            ok = False
        lo, hi = (mid, hi) if ok else (lo, mid - 1)
    return lo   # measured with seq 2**31 and a current issued_at: every seq this run uses encodes no wider


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--streams", required=True, help="comma list, or @file with one name per line")
    p.add_argument("--mode", choices=["valid", "dup", "forged", "unknown"], default="valid")
    p.add_argument("--payload", default="64", help="body bytes, or 'max' to fill the 1 100-byte frame")
    p.add_argument("--rate", type=float, default=0.0, help="items/s; 0 = as fast as this process can sign and send")
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--ttl", type=float, default=60.0, help="seconds (chatter's class default is 60)")
    p.add_argument("--cls", default="chatter")
    p.add_argument("--epoch", type=int, required=True)
    p.add_argument("--proc-index", type=int, default=0)
    p.add_argument("--proc-count", type=int, default=1)
    p.add_argument("--seq-base", type=int, default=0)
    p.add_argument("--sample-every", type=int, default=0)
    p.add_argument("--sample-log")
    p.add_argument("--summary", required=True)
    p.add_argument("--tag", default="flood")
    p.add_argument("--start-at", type=float, default=0.0, help="CLOCK_MONOTONIC seconds to wait for (aligned starts)")
    a = p.parse_args()

    host, port = a.target.rsplit(":", 1)
    dest = (host, int(port))
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(Path(a.key).read_text().strip()))
    if a.mode == "unknown":
        sk = Ed25519PrivateKey.generate()     # a key no manifest lists
    kid = wire.key_id(wire.public_key_bytes(sk)).hex()
    names = (Path(a.streams[1:]).read_text().split() if a.streams.startswith("@") else a.streams.split(","))
    sids = [stream_id(n) for n in names]
    cls = CLASS_BY_NAME[a.cls].code
    ttl_ms = int(a.ttl * 1000)
    size = max_body(sk, a.epoch, sids[0], cls, ttl_ms) if a.payload == "max" else int(a.payload)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
    seqs = [a.seq_base] * len(sids)
    samples: list[str] = []
    sent = send_errors = 0
    frame_bytes = 0
    fixed = None

    def make(i: int) -> bytes:
        s = i % len(sids)
        seqs[s] += 1
        seq = (seqs[s] - 1) * a.proc_count + a.proc_index + 1
        now = time.time_ns() // 1_000_000
        it = wire.Item(epoch=a.epoch, stream=sids[s], seq=seq, issued_at=now, expires_at=now + ttl_ms, cls=cls,
                       ctype=TEXT, body=body_for(size, a.tag, seq), scope=SCOPES["lan"])
        f = wire.encode_item(sk, it)
        if a.sample_every and i % a.sample_every == 0:
            samples.append(f"canticle:{kid}:{a.epoch}:{sids[s]:08x}:{seq}")
        return f

    if a.mode in ("dup", "forged"):
        fixed = make(0)
        if a.mode == "forged":
            b = bytearray(fixed)
            b[-wire.SIG_LEN] ^= 0x01          # R half of the signature: still canonical S, fails verify
            fixed = bytes(b)
        samples.clear()

    while time.monotonic() < a.start_at:
        time.sleep(0.001)
    t0 = time.monotonic()
    end = t0 + a.duration
    times: list[int] = []
    i = 0
    while True:
        now = time.monotonic()
        if now >= end:
            break
        if a.rate > 0:
            due = int((now - t0) * a.rate) + 1
            if i >= due:
                time.sleep(min(0.002, (i + 1) / a.rate - (now - t0)))
                continue
        frame = fixed if fixed is not None else make(i)
        try:
            sock.sendto(frame, dest)
            sent += 1
            frame_bytes = len(frame)
        except OSError:
            send_errors += 1
        if len(samples) > len(times):
            times.append(time.monotonic_ns())
        i += 1
    elapsed = time.monotonic() - t0
    if a.sample_log:
        with open(a.sample_log, "w") as f:
            for idem, t in zip(samples, times):
                f.write(f"{idem},{t}\n")
    Path(a.summary).write_text(json.dumps({
        "mode": a.mode, "key_id": kid, "epoch": a.epoch, "streams": len(sids), "payload_body_bytes": size,
        "frame_bytes": frame_bytes, "rate_asked": a.rate, "sent": sent, "send_errors": send_errors,
        "elapsed_s": round(elapsed, 3), "rate_achieved": round(sent / elapsed, 1) if elapsed else None,
        "samples": len(samples), "proc_index": a.proc_index, "proc_count": a.proc_count,
        "t0_mono_ns": int(t0 * 1e9),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
