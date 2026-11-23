"""Flood producers for ``test_fair_admission`` (binary-canticle#171): run as a process, print one JSON line of totals.

Each mode is one of the rerun rows of #171. Everything goes to one loopback UDP address the test picked; the keys
are the test's own throwaway keys.

  valid    every item new and signed by a key the manifest lists (R1);
  station  one key, one socket: a real carousel of the quiet stream, inside a flood of signed items on another
           stream of the same key (R2); each quiet item sung is printed as it goes out;
  forged   distinct frames naming the quiet key and stream, every one with its own invalid signature (R3). Needs no
           key: only the public key id. ``--beacons`` makes every other one a beacon;
  replay   genuine frames of the quiet station, captured before the flood and resent unchanged (R4).

``--fd`` sends from the station's own socket, which is what a perfect source spoof looks like to the receiver,
``--ports`` from that many ports in turn, and ``--churn`` from a new port for every so many datagrams, on
``--hosts`` loopback addresses in turn (the first is 127.0.0.1, the station's own).
"""

import argparse
import json
import os
import random
import socket
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cbor, runner, wire
from canticle.ids import SCOPES, stream_id
from canticle.station import Station, StreamConfig

CHUNK_S = 0.001     # a paced flood goes out in 1 ms chunks, so it never depends on one big burst
SEQ0 = 2**40        # forged seqs start here: 8 bytes wide whatever the count, so the CBOR stays shortest-form


def item(sk, stream, seq, epoch, ttl_ms=60_000, body=b"flood"):
    now = runner.now_ms()
    return wire.encode_item(sk, wire.Item(epoch=epoch, stream=stream_id(stream), seq=seq, issued_at=now,
                                          expires_at=now + ttl_ms, cls=1, ctype=1, body=body, scope=SCOPES["lan"]))


def forged_parts(kid: bytes, stream: str, epoch: int, beacon: bool = False):
    """The bytes of a frame that passes every check before the signature, split around its ``seq`` (``bseq``)."""
    now = runner.now_ms()
    if beacon:
        kind, m = wire.KIND_BEACON, wire.beacon_map(wire.Beacon(
            epoch=epoch, bseq=SEQ0, wallclock=now, next_beacon_ms=1000, profile="canticle-regulation/1", streams=(),
            b_station=16_000))
    else:
        kind, m = wire.KIND_ITEM, wire.item_map(wire.Item(
            epoch=epoch, stream=stream_id(stream), seq=SEQ0, issued_at=now, expires_at=now + 60_000, cls=1, ctype=1,
            body=b"not from the quiet station", scope=SCOPES["lan"]))
    return (wire.MAGIC + bytes([wire.VERSION, kind]) + kid + cbor.encode(m)).split(SEQ0.to_bytes(8, "big"))


class Pace:
    """How many datagrams are due by now at ``rate`` a second (0: as many as the caller can send)."""

    def __init__(self, rate: float):
        self.rate, self.t0 = rate, time.monotonic()

    def wait(self, sent: int) -> None:
        while self.rate and sent >= (time.monotonic() - self.t0) * self.rate + self.rate * CHUNK_S:
            time.sleep(0.0002)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["valid", "station", "forged", "replay"])
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--rate", type=float, default=0.0)
    p.add_argument("--key", help="file with the signing key (hex)")
    p.add_argument("--kid", help="the key id a forged frame names (hex)")
    p.add_argument("--stream", default="flood")
    p.add_argument("--epoch", type=int, default=7)
    p.add_argument("--beacons", action="store_true")
    p.add_argument("--fd", type=int, help="send from this inherited socket")
    p.add_argument("--ports", type=int, default=1)
    p.add_argument("--churn", type=int, default=0)
    p.add_argument("--hosts", type=int, default=1)
    p.add_argument("--capture", type=int, help="replay: the inherited socket genuine frames arrive on")
    p.add_argument("--quiet-items", type=int, default=0)
    p.add_argument("--quiet-interval", type=float, default=0.15)
    a = p.parse_args()
    socks = [socket.socket(fileno=a.fd)] if a.fd is not None else [
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(a.ports)]
    dest = ("127.0.0.1", a.port)
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(open(a.key).read())) if a.key else None
    sent, opened = 0, len(socks)

    def send(frame: bytes) -> None:
        nonlocal sent, opened
        if a.churn and sent % a.churn == 0:
            socks[0].close()
            socks[0] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socks[0].bind((socket.inet_ntoa((0x7F000001 + opened % a.hosts).to_bytes(4, "big")), 0))
            opened += 1
        try:
            socks[sent % len(socks)].sendto(frame, dest)
            sent += 1
        except (BlockingIOError, ConnectionRefusedError):
            pass

    print(json.dumps({"ready": True}), flush=True)
    start = time.monotonic()
    end, pace = start + a.duration, Pace(a.rate)
    if a.mode == "valid":
        seq = 0
        while time.monotonic() < end:
            pace.wait(sent)
            seq += 1
            send(item(sk, a.stream, seq, a.epoch))
    elif a.mode == "station":
        st = Station(sk, [StreamConfig("quiet"), StreamConfig(a.stream)], epoch=a.epoch, rng=random.Random(5))
        sung = seq = 0
        while time.monotonic() < end:
            if sung < a.quiet_items and time.monotonic() >= start + sung * a.quiet_interval:
                r = st.sing(runner.now_ms(), "quiet", text=f"quiet {sung}")
                sung += 1
                print(json.dumps({"seq": r.seq, "t": time.monotonic()}), flush=True)
            for frame in st.poll(runner.now_ms()):
                send(frame)
            for _ in range(20):
                pace.wait(sent)
                seq += 1
                send(item(sk, a.stream, seq, a.epoch))
    elif a.mode == "forged":
        kid, n = bytes.fromhex(a.kid), 0
        refreshed = -1.0
        while time.monotonic() < end:
            if time.monotonic() - refreshed > 1.0:      # a forgery past its own expiry would fail before its signature
                refreshed = time.monotonic()
                parts = [forged_parts(kid, a.stream, a.epoch, beacon) for beacon in ((False, True) if a.beacons else (False,))]
            for _ in range(50 if a.rate >= 50_000 else 1):
                n += 1
                head, tail = parts[n // len(socks) % len(parts)]     # each port sends both kinds
                # Any 64 bytes with a canonical S (§9.3) reach the signature check and fail it.
                send(head + (SEQ0 + n).to_bytes(8, "big") + tail + os.urandom(32) + n.to_bytes(8, "little") + bytes(24))
            pace.wait(sent)
    else:
        cap = socket.socket(fileno=a.capture)
        cap.setblocking(False)
        frames: list = []
        try:
            while True:
                frames.append(cap.recv(2048))
        except BlockingIOError:
            pass
        while time.monotonic() < end:
            for f in frames:
                send(f)
                pace.wait(sent)
    print(json.dumps({"sent": sent, "elapsed": time.monotonic() - start, "ports": opened}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
