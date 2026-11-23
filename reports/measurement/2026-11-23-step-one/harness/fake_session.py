"""A fake Claude session: drives frond-ear's real channel shim (`frond-ear shim`) over stdio MCP.

It sends `initialize` and `notifications/initialized` as Claude Code does, then reads every line
the shim writes. A `notifications/claude/channel` line is a push reaching the session's input;
its arrival (CLOCK_MONOTONIC, on this side of the pipe) is "push emitted" for this measurement.
The shim confirms each push to the daemon as `offered` once its write completes, so custody
advances exactly as on a seat. The session never echoes a batch and never calls a tool: it is a
reader that only counts. Heard text is logged as data, never acted on (RFC I-6).

Each push is parsed for its records' identities (`station=… key=… stream=… item=<epoch>/<seq>`)
and for the lines that report lateness or loss, and written as one JSON line.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
import ctypes
import signal

REC = re.compile(r'\[canticle:heard\][^\n]*?station="([^"]*)"[^\n]*?key=([0-9a-f]+)[^\n]*?stream=(\S+) item=(\d+)/(\d+)')
_libc = ctypes.CDLL("libc.so.6", use_errno=True)


def _child():
    os.setsid()
    _libc.prctl(1, signal.SIGTERM)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frond-ear", required=True)
    p.add_argument("--node", required=True)
    p.add_argument("--socket", required=True)
    p.add_argument("--ear", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--session-id", default="00000000-0000-4000-8000-00000000fa4e")
    p.add_argument("--keep-content", type=int, default=3, help="pushes whose whole content is kept")
    a = p.parse_args()

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
           "FROND_EAR_SOCKET": a.socket, "FROND_EAR_EAR": a.ear, "CLAUDE_CODE_SESSION_ID": a.session_id,
           "XDG_RUNTIME_DIR": os.path.dirname(os.path.dirname(a.socket))}
    shim = subprocess.Popen([a.node, os.path.join(a.frond_ear, "src", "cli.ts"), "shim"], env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(a.out + ".shim.err", "ab"),
                            cwd=a.frond_ear, preexec_fn=_child)

    def send(obj):
        shim.stdin.write((json.dumps(obj) + "\n").encode())
        shim.stdin.flush()

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                     "clientInfo": {"name": "step-one-fake-session", "version": "0"}}})
    out = open(a.out + ".pushes.jsonl", "w")
    other = open(a.out + ".other.jsonl", "w")
    deadline = time.monotonic() + a.duration
    buf = b""
    initialized = False
    pushes = records = kept = 0
    fd = shim.stdout.fileno()
    os.set_blocking(fd, False)
    while time.monotonic() < deadline and shim.poll() is None:
        r, _, _ = select.select([fd], [], [], 0.25)
        if not r:
            continue
        try:
            chunk = os.read(fd, 1 << 20)
        except BlockingIOError:
            continue
        if not chunk:
            break
        t = time.monotonic_ns()
        buf += chunk
        *lines, buf = buf.split(b"\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                other.write(json.dumps({"t_ns": t, "unparsed": line[:200].decode("utf-8", "replace")}) + "\n")
                continue
            if msg.get("id") == 1 and not initialized:
                initialized = True
                send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                other.write(json.dumps({"t_ns": t, "initialized": True}) + "\n")
                continue
            if msg.get("method") == "notifications/claude/channel":
                params = msg.get("params", {})
                content = params.get("content", "")
                meta = params.get("meta", {})
                recs = [[m[0], m[1], m[2], int(m[3]), int(m[4])] for m in REC.findall(content)]
                # the lines a push uses to account for itself (frond-ear delivery.ts render/streamLine):
                # lateness, records dropped from a full buffer, gone off air unpushed, still waiting
                body = [l for l in content.splitlines() if not l.startswith(("[canticle:heard]", "> ", "issued="))]
                late = [l for l in body if "late" in l.lower()]
                missed = [l for l in body if any(w in l.lower() for w in
                                                 ("dropped", "off air", "missed", "gap", "lost", "wait", "unknown"))]
                row = {"t_ns": t, "meta": meta, "chars": len(content), "records": recs,
                       "late_lines": late[:20], "loss_lines": missed[:20]}
                if kept < a.keep_content:
                    row["content"] = content
                    kept += 1
                out.write(json.dumps(row) + "\n")
                out.flush()
                pushes += 1
                records += len(recs)
            else:
                other.write(json.dumps({"t_ns": t, "msg": msg}, default=str)[:4000] + "\n")
    out.close()
    other.close()
    try:
        os.killpg(shim.pid, signal.SIGTERM)
        shim.wait(5)
    except Exception:
        pass
    with open(a.out + ".json", "w") as f:
        json.dump({"pushes": pushes, "records": records, "initialized": initialized,
                   "shim_exit": shim.returncode}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
