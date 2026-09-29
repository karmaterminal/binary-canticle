"""canticle: run a looping station, put items on air, listen.

    python -m canticle keygen  --out cael.key --manifest fleet.json --name cael --classes chatter,live-state,root --streams chatter,lens.threat,root
    python -m canticle station --key cael.key --stream chatter --stream lens.threat:live-state --stream root:root --to 127.0.0.1:9999
    python -m canticle sing    --control /tmp/canticle-<key_id>.sock --stream chatter --text "port-scan burst from 10.0.0.7" --ttl 60
    python -m canticle hush    --control ... --stream chatter --seq 1
    python -m canticle listen  --manifest fleet.json --bind 0.0.0.0:9999      # one JSON event per line
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import signal
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import runner, wire
from .ids import CLASS_BY_NAME, SCOPES
from .listener import Listener
from .manifest import Manifest, StationEntry
from .station import Station, StreamConfig, next_epoch


def _load_key(path: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(Path(path).read_text().strip()))


def _default_control(sk: Ed25519PrivateKey) -> str:
    kid = wire.key_id(wire.public_key_bytes(sk)).hex()
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(base, f"canticle-{kid}.sock")


def cmd_keygen(a) -> int:
    out = Path(a.out)
    if out.exists():
        print(f"{out} exists; refusing to overwrite", file=sys.stderr)
        return 1
    sk = Ed25519PrivateKey.generate()
    seed = sk.private_bytes_raw()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(seed.hex() + "\n")
    pub = wire.public_key_bytes(sk)
    info = {"key": str(out), "public_key": pub.hex(), "key_id": wire.key_id(pub).hex()}
    if a.manifest:
        if not a.name:
            print("--manifest needs --name", file=sys.stderr)
            return 1
        path = Path(a.manifest)
        m = Manifest.load(path) if path.exists() else Manifest()
        m.add(StationEntry(name=a.name, public_key=pub,
                           classes=frozenset(CLASS_BY_NAME[c].code for c in a.classes.split(",") if c),
                           streams=tuple(s for s in a.streams.split(",") if s),
                           scopes=frozenset(SCOPES[s] for s in a.scopes.split(",") if s)))
        m.save(path)
        info["manifest"] = str(path)
    print(json.dumps(info))
    return 0


def _stream_config(spec: str) -> StreamConfig:
    name, _, rest = spec.partition(":")
    cls, _, ttl = rest.partition(":")
    return StreamConfig(name=name, cls=cls or "chatter", default_ttl_s=int(ttl) if ttl else None)


def cmd_station(a) -> int:
    sk = _load_key(a.key)
    kid = wire.key_id(wire.public_key_bytes(sk))
    grant = Manifest.load(a.manifest).entry(kid)
    if grant is None or grant.revoked:
        print(f"key {kid.hex()} is not in {a.manifest} (or is revoked); refusing to sign", file=sys.stderr)
        return 1
    # One key is one station (§5.1): hold an exclusive lease on the key for the process lifetime,
    # so a second station cannot run with the same key and equivocate.
    lease = open(a.key + ".lease", "a")
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"another station holds {a.key}; refusing to start", file=sys.stderr)
        return 1
    st = Station(sk, [_stream_config(s) for s in a.stream], epoch=next_epoch(a.epoch_file or a.key + ".epoch"),
                 beacon_period_ms=a.beacon_ms, now_ms=runner.now_ms(), grant=grant)
    try:
        runner.socket_grant(st, a.socket_class)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    dests = [runner.parse_addr(d) for d in (a.to or [])]
    if a.multicast:
        dests.append((runner.MCAST_GROUP, a.port))
    if not dests:
        dests = [("127.0.0.1", a.port)]
    control = a.control or _default_control(sk)
    log = (lambda s: print(s, file=sys.stderr, flush=True))
    log(json.dumps({"station": st.key_id.hex(), "epoch": st.epoch, "control": control,
                    "dests": [f"{h}:{p}" for h, p in dests], "streams": list(st.streams)}))

    async def main():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await runner.run_station(st, dests, control, stop, log, socket_classes=a.socket_class)

    asyncio.run(main())
    return 0


def _control(a) -> str:
    if a.control:
        return a.control
    print("--control is required (the station prints its socket path at start)", file=sys.stderr)
    raise SystemExit(2)


def cmd_sing(a) -> int:
    req = {"op": "sing", "stream": a.stream, "loop": a.loop, "scope": a.scope}
    if a.text is not None:
        req["text"] = a.text
    elif a.body_hex is not None:
        req["body_hex"], req["ctype"] = a.body_hex, a.ctype
    else:
        req["text"] = sys.stdin.read()
    for k in ("ttl", "state_key", "purpose", "intensity", "keep_on_air"):
        v = getattr(a, k)
        if v is not None:
            req[k] = v
    if a.cls:
        req["class"] = a.cls
    resp = runner.control_request(_control(a), req)
    print(json.dumps(resp))
    return 0 if resp.get("ok") else 1


def cmd_hush(a) -> int:
    resp = runner.control_request(_control(a), {"op": "hush", "stream": a.stream, "seq": a.seq})
    print(json.dumps(resp))
    return 0 if resp.get("ok") else 1


def cmd_status(a) -> int:
    print(json.dumps(runner.control_request(_control(a), {"op": "status"}), indent=2))
    return 0


def _default_state(manifest: str, bind: str) -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    tag = hashlib.sha256(f"{os.path.abspath(manifest)}|{bind}".encode()).hexdigest()[:12]
    return os.path.join(base, "canticle", f"listener-{tag}.json")


def cmd_listen(a) -> int:
    if a.ephemeral:
        state = None
        print("warning: --ephemeral: no restart safety; after a restart this listener can surface stale "
              "or withdrawn items (§7.4-§7.8)", file=sys.stderr)
    else:
        state = a.state or _default_state(a.manifest, a.bind)
        os.makedirs(os.path.dirname(os.path.abspath(state)), exist_ok=True)
        lease = open(state + ".lease", "a")  # one listener per state file
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"another listener holds {state}; refusing to start", file=sys.stderr)
            return 1
        print(json.dumps({"listener_state": state}), file=sys.stderr, flush=True)
    lst = Listener(Manifest.load(a.manifest), tuned=set(a.stream) if a.stream else None,
                   state_path=state, ephemeral=a.ephemeral)
    bind = runner.parse_addr(a.bind)

    def on_event(ev):
        if ev.kind == "evidence" and not a.evidence:
            return
        print(json.dumps(ev.to_json()), flush=True)

    async def main():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await runner.run_listener(lst, bind, on_event, runner.MCAST_GROUP if a.multicast else None, stop)

    asyncio.run(main())
    return 0


def cmd_vectors(a) -> int:
    from .vectors import build
    Path(a.out).write_text(json.dumps(build(), indent=1) + "\n")
    print(a.out)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="canticle", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen", help="create a station key (and optionally add it to a manifest)")
    k.add_argument("--out", required=True)
    k.add_argument("--manifest")
    k.add_argument("--name")
    k.add_argument("--classes", default="chatter,ambient,live-state,root")
    k.add_argument("--streams", default="chatter,root")
    k.add_argument("--scopes", default="host,lan", help="scopes the key may sign (§4.3)")
    k.set_defaults(fn=cmd_keygen)

    s = sub.add_parser("station", help="run a looping station")
    s.add_argument("--key", required=True)
    s.add_argument("--manifest", required=True, help="fleet manifest; the station signs only what its entry grants")
    s.add_argument("--socket-class", action="append", help="class the control socket may request (repeatable); "
                   "default: every class the key is granted except regulatory, alarm and control, which the "
                   "socket never accepts in this spike")
    s.add_argument("--stream", action="append", required=True, help="name[:class[:default_ttl_s]]")
    s.add_argument("--to", action="append", help="host:port destination (repeatable)")
    s.add_argument("--multicast", action="store_true", help=f"also send to {runner.MCAST_GROUP}")
    s.add_argument("--port", type=int, default=runner.DEFAULT_PORT)
    s.add_argument("--control")
    s.add_argument("--epoch-file", help="persisted epoch counter (default: <key>.epoch); "
                   "each start takes the next epoch, so a restart never reuses seq numbers (§5.2)")
    s.add_argument("--beacon-ms", type=int, default=1000)
    s.set_defaults(fn=cmd_station)

    g = sub.add_parser("sing", help="put an item on air")
    g.add_argument("--control")
    g.add_argument("--stream", required=True)
    g.add_argument("--text")
    g.add_argument("--body-hex")
    g.add_argument("--ctype", type=int, default=2)
    g.add_argument("--class", dest="cls")
    g.add_argument("--ttl", type=float)
    g.add_argument("--loop", default="normal", help="fast | normal | slow | milliseconds")
    g.add_argument("--state-key")
    g.add_argument("--keep-on-air", type=int, help="keep a keyed item on air by refresh for N seconds")
    g.add_argument("--scope", default="lan", choices=["host", "lan", "fleet", "public"])
    g.add_argument("--purpose")
    g.add_argument("--intensity", type=int)
    g.set_defaults(fn=cmd_sing)

    h = sub.add_parser("hush", help="pluck a live item")
    h.add_argument("--control")
    h.add_argument("--stream", required=True)
    h.add_argument("--seq", type=int, required=True)
    h.set_defaults(fn=cmd_hush)

    t = sub.add_parser("status", help="show what a station has on air")
    t.add_argument("--control")
    t.set_defaults(fn=cmd_status)

    l = sub.add_parser("listen", help="listen and print one JSON event per line")
    l.add_argument("--manifest", required=True)
    l.add_argument("--bind", default=f"0.0.0.0:{runner.DEFAULT_PORT}")
    l.add_argument("--multicast", action="store_true")
    l.add_argument("--stream", action="append", help="only surface these stream names")
    l.add_argument("--evidence", action="store_true", help="also print rejected datagrams and other evidence")
    l.add_argument("--state", help="file for the safety state kept across restarts (dedup, plucks, "
                   "supersession, epochs; §7.4-§7.8). Default: $XDG_STATE_HOME/canticle/listener-<manifest+bind>.json")
    l.add_argument("--ephemeral", action="store_true", help="UNSAFE: keep no state across restarts (tests only); "
                   "a restarted listener can then surface stale or withdrawn items")
    l.set_defaults(fn=cmd_listen)

    v = sub.add_parser("vectors", help="regenerate the candidate conformance vectors")
    v.add_argument("--out", default="vectors/frame-v2-candidates.json")
    v.set_defaults(fn=cmd_vectors)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
