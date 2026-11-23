"""Producers for the two #171 rerun rows its harness has no mode for (forged claims of the quiet key; replays of the
quiet key's own frames). Same summary format as the harness's ``blast.py``, so ``cells.collect`` reads it.

  forged   distinct frames naming the quiet key and stream, each with its own invalid signature (canonical S), flat out;
  latest   the quiet station's newest item, resent unchanged, flat out, moving on as each is captured (#171's wording);
  earlier  every frame of the quiet station captured at least 8 s ago and still inside its life, plus its beacons of
           the last 5 minutes (a beacon never expires), resent in a cycle, flat out: none of them is the next new item.
"""
import argparse, json, os, socket, sys, time
from pathlib import Path
sys.path.insert(0, os.environ["PYTHONPATH"])
from canticle import cbor, wire
from canticle.ids import SCOPES, stream_id

SEQ0 = 2**40

def parts(kid, stream, epoch):
    now = time.time_ns() // 1_000_000
    m = wire.item_map(wire.Item(epoch=epoch, stream=stream_id(stream), seq=SEQ0, issued_at=now, expires_at=now + 60_000,
                                cls=1, ctype=1, body=b"B|forged|" + b"x" * 55, scope=SCOPES["lan"]))
    return (wire.MAGIC + bytes([wire.VERSION, wire.KIND_ITEM]) + kid + cbor.encode(m)).split(SEQ0.to_bytes(8, "big"))

p = argparse.ArgumentParser()
p.add_argument("mode"); p.add_argument("--target", required=True); p.add_argument("--kid"); p.add_argument("--stream", default="quiet")
p.add_argument("--epoch", type=int, default=0); p.add_argument("--duration", type=float, required=True); p.add_argument("--summary", required=True)
p.add_argument("--capture", type=int); p.add_argument("--start-at", type=float, default=0.0); p.add_argument("--index", type=int, default=0)
a = p.parse_args()
host, port = a.target.rsplit(":", 1)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
sock.connect((host, int(port)))
cap = None
if a.capture:
    cap = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); cap.bind(("127.0.0.1", a.capture)); cap.setblocking(False)
while time.monotonic() < a.start_at:
    time.sleep(0.001)
t0 = time.monotonic(); end = t0 + a.duration; sent = errors = 0; size = 0
def send(f):
    global sent, errors, size
    try:
        sock.send(f); sent += 1; size = len(f)
    except OSError:
        errors += 1
if a.mode == "forged":
    kid, n = bytes.fromhex(a.kid), a.index << 36
    head, tail = parts(kid, a.stream, a.epoch); refreshed = t0
    while (now := time.monotonic()) < end:
        if now - refreshed > 1.0:
            (head, tail), refreshed = parts(kid, a.stream, a.epoch), now
        r = os.urandom(32)
        for _ in range(100):
            n += 1
            send(head + (SEQ0 + n).to_bytes(8, "big") + tail + r + n.to_bytes(8, "little") + bytes(24))
else:
    frames = []          # (captured at, bytes)
    while (now := time.monotonic()) < end:
        try:
            while True:
                d = cap.recv(2048)
                if all(d != f for _, f in frames):
                    frames.append((now, d))
        except BlockingIOError:
            pass
        items = [(t, f) for t, f in frames if f[3] == 1 and now - t < 55]
        beacons = [(t, f) for t, f in frames if f[3] == 2 and now - t < 300]
        frames = sorted(items + beacons)
        if a.mode == "latest":
            chosen = [f for _, f in items[-1:]]
        else:
            chosen = [f for t, f in frames if now - t >= 8]
        if not chosen:
            time.sleep(0.002); continue
        for f in (chosen * (200 // len(chosen) + 1))[:max(200, len(chosen))]:
            send(f)
el = time.monotonic() - t0
Path(a.summary).write_text(json.dumps({"mode": a.mode, "sent": sent, "send_errors": errors, "frame_bytes": size, "elapsed_s": round(el, 2),
                                       "rate_achieved": round(sent / el, 1)}))
