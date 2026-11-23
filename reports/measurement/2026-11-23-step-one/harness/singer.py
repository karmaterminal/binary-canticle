"""Put items on a real `canticle station` through its control socket (`{"op":"sing"}`, RFC §11.1).

`--interval 10` is the §2.8 quiet tuned stream: one item every 10 s. `--rate 0` sings as fast as
the control socket answers (one connection per request, as `canticle sing` does), which is how
hard a real station can be pushed by a chatty local client: each item still leaves as a first
copy plus a 3-copy burst and then loops within the station's budget.

Each sing is logged: the request time and the answer (CLOCK_MONOTONIC), and what the station
assigned (epoch, seq, issued_at, expires_at, frame size, clamp). The idem the daemon will give
the item is derived from those, so arrival can be joined against it.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "prototype" / "canticle-station"))
from canticle.ids import stream_id   # noqa: E402


def sing(path: str, req: dict, timeout: float = 5.0) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(path)
        s.sendall((json.dumps(req) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--control", required=True)
    p.add_argument("--stream", required=True)
    p.add_argument("--key-id", required=True, help="the station's key id, for the idem")
    p.add_argument("--interval", type=float, default=0.0)
    p.add_argument("--rate", type=float, default=None, help="items/s; 0 = as fast as the socket answers")
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--payload", type=int, default=64)
    p.add_argument("--ttl", type=float)
    p.add_argument("--tag", default="quiet")
    p.add_argument("--out", required=True)
    p.add_argument("--first-at", type=float, default=0.0, help="seconds to wait before the first sing")
    a = p.parse_args()

    sid = stream_id(a.stream)
    rows = []
    errors = 0
    time.sleep(a.first_at)
    t0 = time.monotonic()
    end = t0 + a.duration
    n = 0
    while time.monotonic() < end:
        if a.interval:
            due = t0 + n * a.interval
            while time.monotonic() < due:
                time.sleep(min(0.05, due - time.monotonic()))
            if time.monotonic() >= end:
                break
        elif a.rate:
            due = t0 + n / a.rate
            if time.monotonic() < due:
                time.sleep(min(0.002, due - time.monotonic()))
                continue
        head = f"{a.tag.upper()}|{n}|"
        req = {"op": "sing", "stream": a.stream, "text": head + "q" * max(0, a.payload - len(head))}
        if a.ttl:
            req["ttl"] = a.ttl
        t_req = time.monotonic_ns()
        try:
            r = sing(a.control, req)
        except (OSError, ValueError) as e:
            errors += 1
            rows.append({"n": n, "t_req_ns": t_req, "error": str(e)})
            n += 1
            continue
        t_ok = time.monotonic_ns()
        if r.get("ok"):
            rows.append({"n": n, "t_req_ns": t_req, "t_ok_ns": t_ok, "seq": r["seq"], "epoch": r["epoch"],
                         "issued_at": r["issued_at"], "expires_at": r["expires_at"], "size": r["size"],
                         "clamp": r["clamp"], "loop_ms": r["loop_ms"],
                         "idem": f"canticle:{a.key_id}:{r['epoch']}:{sid:08x}:{r['seq']}"})
        else:
            errors += 1
            rows.append({"n": n, "t_req_ns": t_req, "t_ok_ns": t_ok, "refused": r.get("error")})
        n += 1
    elapsed = time.monotonic() - t0
    with open(a.out + ".jsonl", "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    with open(a.out + ".json", "w") as f:
        json.dump({"sung": sum(1 for r in rows if "seq" in r), "errors": errors, "elapsed_s": round(elapsed, 2),
                   "rate": round(sum(1 for r in rows if "seq" in r) / elapsed, 1) if elapsed else None}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
