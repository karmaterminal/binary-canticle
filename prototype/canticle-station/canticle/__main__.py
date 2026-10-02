"""canticle: run a looping station, put items on air, listen.

    python -m canticle keygen  --out cael.key --manifest fleet.json --name cael --classes chatter,live-state,root --streams chatter,lens.threat,root
    python -m canticle station --key cael.key --stream chatter --stream lens.threat:live-state --stream root:root --to 127.0.0.1:9999
    python -m canticle sing    --control /tmp/canticle-<key_id>.sock --stream chatter --text "port-scan burst from 10.0.0.7" --ttl 60
    python -m canticle hush    --control ... --stream chatter --seq 1
    python -m canticle listen  --manifest fleet.json --bind 0.0.0.0:9999      # one JSON event per line
    python -m canticle listen                                                # the same, from ~/.binary-canticle/stations.toml
    python -m canticle daemon                                                # the host daemon: records over $XDG_RUNTIME_DIR/canticle/daemon.sock
    python -m canticle doctor  [--json]                                      # check this host; exit 1 if a check fails
    python -m canticle manifest verify|show [fleet.json]
    python -m canticle ambient --control ... --stream hymn --fixture hymn.txt --duration 600   # background emitter
    python -m canticle tuner   --manifest fleet.json --multicast --http 127.0.0.1:8765         # read-only web view
"""

from __future__ import annotations

import argparse
import asyncio
import errno
import fcntl
import hashlib
import json
import os
import random
import signal
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import runner, stations, wire
from .ids import CLASS_BY_NAME, SCOPES, STATION_NAME_RE
from .listener import Listener
from .manifest import FORMAT, Manifest, StationEntry, verify_json
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
    for d in [out.parent] + ([Path(a.manifest).parent] if a.manifest else []):
        if not d.is_dir():
            print(f"{d}: no such directory; no key written", file=sys.stderr)
            return 1
    if a.manifest and os.path.realpath(out) == os.path.realpath(a.manifest):
        print("--out and --manifest name the same file; no key written", file=sys.stderr)
        return 1
    sk = Ed25519PrivateKey.generate()
    pub = wire.public_key_bytes(sk)
    path = Path(a.manifest) if a.manifest else None
    staged = None
    if path is not None:
        # Everything that can refuse runs before the key file is written, so a mistake leaves no orphan key
        # behind to block the corrected command with "exists; refusing to overwrite". The new manifest is
        # written beside the old one first, and replaces it only once the key is safely on disk.
        if not a.name or not STATION_NAME_RE.match(a.name):
            print("--manifest needs --name, matching [a-z][a-z0-9-]{0,30} (RFC §5.3); no key written", file=sys.stderr)
            return 1
        classes = [c for c in a.classes.split(",") if c]
        scopes = [s for s in a.scopes.split(",") if s]
        unknown = [f"class {c!r}" for c in classes if c not in CLASS_BY_NAME] + [f"scope {s!r}" for s in scopes if s not in SCOPES]
        if unknown:
            print(f"unknown {', '.join(unknown)} (classes: {', '.join(CLASS_BY_NAME)}; scopes: {', '.join(SCOPES)}); "
                  "no key written", file=sys.stderr)
            return 1
        try:
            m = Manifest.load(path) if path.exists() else Manifest()
            same_name = [e.key_id.hex() for e in m if e.name == a.name]
            m.add(StationEntry(name=a.name, public_key=pub, classes=frozenset(CLASS_BY_NAME[c].code for c in classes),
                               streams=tuple(s for s in a.streams.split(",") if s),
                               scopes=frozenset(SCOPES[s] for s in scopes)))
            staged = m.stage(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            why = e if isinstance(e, (OSError, ValueError)) else f"does not load ({type(e).__name__}: {e})"
            print(f"{path}: {why}; no key written (canticle manifest verify lists every problem)", file=sys.stderr)
            return 1
        if same_name:
            print(f"note: {a.name} already has key-id {', '.join(same_name)}; the manifest now trusts both keys until "
                  "one is revoked (RFC §10.3 key rotation)", file=sys.stderr)
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        if staged:
            os.unlink(staged)
        print(f"{out} exists; refusing to overwrite" if isinstance(e, FileExistsError) else f"{out}: {e}; no key written",
              file=sys.stderr)
        return 1
    try:
        with os.fdopen(fd, "w") as f:
            f.write(sk.private_bytes_raw().hex() + "\n")
            f.flush()
            os.fsync(f.fileno())
        if staged:
            os.replace(staged, os.path.realpath(path))
    except OSError as e:
        out.unlink()  # this command created it, and it is in no manifest
        if staged and os.path.exists(staged):
            os.unlink(staged)
        print(f"{e}; no key written", file=sys.stderr)
        return 1
    info = {"key": str(out), "public_key": pub.hex(), "key_id": wire.key_id(pub).hex()}
    if path is not None:
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
    m = _load_manifest(a.manifest)
    if m is None:
        return 1
    grant = m.entry(kid)
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


def _locators(a) -> tuple:
    """(manifest, bind, multicast, stations.toml path or None) for listen and doctor. With --manifest, today's
    flags and defaults apply and stations.toml is not read. Without it, the locators come from stations.toml
    (RFC §13.6), and --bind or --(no-)multicast, when given, win over the file."""
    if a.manifest is not None:
        return a.manifest, a.bind or stations.DEFAULT_BIND, bool(a.multicast), None
    cfg = stations.load(a.stations)
    return str(cfg.manifest), a.bind or cfg.bind, cfg.multicast if a.multicast is None else a.multicast, cfg.path


def _stations_hint(e: Exception, otherwise: str = "pass --manifest") -> str:
    if isinstance(e, stations.StationsMissing):
        return f"{e}: write it (prototype/canticle-station/docs/stations-toml.md), or {otherwise}"
    return str(e)


def _load_manifest(path: str):
    try:
        return Manifest.load(path)
    except (OSError, ValueError, KeyError, TypeError) as e:
        why = e if isinstance(e, (OSError, ValueError)) else f"does not load ({type(e).__name__}: {e})"
        print(f"{path}: {why} (canticle manifest verify lists every problem)", file=sys.stderr)
        return None


def cmd_listen(a) -> int:
    try:
        a.manifest, a.bind, a.multicast, source = _locators(a)
    except stations.StationsError as e:
        print(_stations_hint(e), file=sys.stderr)
        return 1
    if source is not None:
        print(json.dumps({"stations": str(source), "manifest": a.manifest, "bind": a.bind, "multicast": a.multicast}),
              file=sys.stderr, flush=True)
    m = _load_manifest(a.manifest)
    if m is None:
        return 1
    state, _lease = _listener_state(a)
    lst = Listener(m, tuned=set(a.stream) if a.stream else None, state_path=state, ephemeral=a.ephemeral)
    bind = runner.parse_addr(a.bind)

    def on_event(ev):
        if ev.kind == "evidence" and not a.evidence:
            return
        out = {"t_ms": runner.now_ms(), **ev.to_json()} if a.timestamps else ev.to_json()
        print(json.dumps(out), flush=True)

    async def main():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await runner.run_listener(lst, bind, on_event, runner.MCAST_GROUP if a.multicast else None, stop)

    try:
        asyncio.run(main())
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        print(f"{a.bind}: address in use; refusing to listen. If the canticle daemon runs on this host, it is the "
              "host's one listener (RFC §4.2): read its records from its socket instead", file=sys.stderr)
        return 1
    return 0


def cmd_daemon(a) -> int:
    from .daemon import Daemon, DaemonConfig, default_socket_path, default_state_dir
    try:
        manifest, bind, multicast, source = _locators(a)
    except stations.StationsError as e:
        print(_stations_hint(e), file=sys.stderr)
        return 1
    sock = a.socket or default_socket_path()
    if sock is None:
        print("XDG_RUNTIME_DIR is not set: pass --socket (RFC §11.1 wants a per-user runtime directory)",
              file=sys.stderr)
        return 1
    uids = frozenset(a.allow_uid) if a.allow_uid else frozenset({os.getuid()})
    cfg = DaemonConfig(manifest=manifest, bind=bind, multicast=multicast, socket_path=sock,
                       state_dir=a.state_dir or default_state_dir(), allowed_uids=uids,
                       health_interval_ms=int(a.health_interval * 1000))
    print(json.dumps({"daemon": {"manifest": manifest, "bind": bind, "multicast": multicast, "socket": sock,
                                 "state_dir": cfg.state_dir, "allowed_uids": sorted(uids),
                                 "stations": str(source) if source else None}}), file=sys.stderr, flush=True)

    async def main() -> int:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        return await Daemon(cfg).run(stop)

    return asyncio.run(main())


LEASE_WAIT_S = 0.5


def _listener_state(a, role: str = "listen") -> tuple:
    """(state path or None, lease file handle) for a CLI listener; exits if another holds the state."""
    if a.ephemeral:
        print("warning: --ephemeral: no restart safety; after a restart this listener can surface stale "
              "or withdrawn items (§7.4-§7.8)", file=sys.stderr)
        return None, None
    state = a.state or _default_state(a.manifest, a.bind if role == "listen" else f"{a.bind}|{role}")
    os.makedirs(os.path.dirname(os.path.abspath(state)), exist_ok=True)
    lease = open(state + ".lease", "a")  # one listener per state file
    # `canticle doctor` tests this lease with a shared lock held for microseconds; retrying briefly means a
    # doctor run can never make a starting listener refuse. A listener that holds it stays held.
    deadline = time.monotonic() + LEASE_WAIT_S
    while True:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                print(f"another listener holds {state}; refusing to start", file=sys.stderr)
                raise SystemExit(1)
            time.sleep(0.01)
    print(json.dumps({"listener_state": state}), file=sys.stderr, flush=True)
    return state, lease


def cmd_ambient(a) -> int:
    from .ambient import AmbientConfig, FixtureError, load_fixture, run
    try:
        cfg = AmbientConfig(stream=a.stream, lines=load_fixture(a.fixture, a.max_bytes), cls=a.cls,
                            min_gap_s=a.min_gap, max_gap_s=a.max_gap, ttl_s=a.ttl, breath=a.breath,
                            max_bytes=a.max_bytes, max_per_minute=a.max_per_minute, duration_s=a.duration)
    except (FixtureError, ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    control = _control(a)
    out = open(a.log, "a") if a.log else sys.stdout
    stopped = [False]
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.__setitem__(0, True))

    def log(rec: dict) -> None:
        out.write(json.dumps(rec) + "\n")
        out.flush()

    summary = run(cfg, lambda req: runner.control_request(control, req), log, stop=lambda: stopped[0],
                  rng=random.Random(a.seed) if a.seed is not None else None)
    return 1 if summary["reason"] == "station-unreachable" else 0


def cmd_tuner(a) -> int:
    from .tuner import is_loopback, run_tuner
    http_host, http_port = runner.parse_addr(a.http, 8765)
    if not is_loopback(http_host):
        print(f"--http must be a loopback address in this spike, not {http_host} (RFC-0001 §18.9)", file=sys.stderr)
        return 1
    m = _load_manifest(a.manifest)
    if m is None:
        return 1
    state, _lease = _listener_state(a, role="tuner")
    lst = Listener(m, state_path=state, ephemeral=a.ephemeral)
    log = open(a.log, "a") if a.log else None

    def on_event(ev) -> None:
        if log is not None:
            log.write(json.dumps({"t_ms": runner.now_ms(), **ev.to_json()}) + "\n")
            log.flush()

    def ready(port: int) -> None:
        print(json.dumps({"tuner": f"http://{http_host}:{port}/", "udp": a.bind,
                          "multicast": runner.MCAST_GROUP if a.multicast else None}), file=sys.stderr, flush=True)

    async def main():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await run_tuner(lst, runner.parse_addr(a.bind), runner.MCAST_GROUP if a.multicast else None,
                        http_host, http_port, stop, on_event=on_event, ready=ready)

    asyncio.run(main())
    return 0


def _leases(state, manifest: str, bind: str) -> dict:
    """The state leases a running `canticle listen`, `canticle tuner` or `canticle daemon` (default state
    directory) holds."""
    from .daemon import default_state_dir
    return {"listener": (state or _default_state(manifest, bind)) + ".lease",
            "tuner": _default_state(manifest, f"{bind}|tuner") + ".lease",
            "daemon": os.path.join(default_state_dir(), "daemon.lease")}


def cmd_doctor(a) -> int:
    from . import doctor
    checks = [doctor.check_python(), doctor.check_cryptography()]
    try:
        manifest, bind, multicast, source = _locators(a)
    except stations.StationsError as e:
        manifest = bind = multicast = None
        checks.append(doctor.Check("stations", "fail", _stations_hint(e)))
        checks += [doctor.Check(name, "skip", "needs stations.toml or --manifest") for name in ("manifest", "bind")]
    else:
        checks.append(doctor.Check("stations", "ok", f"{source}: manifest {manifest}, bind {bind}, "
                                   f"multicast {'on' if multicast else 'off'}", {"path": str(source)})
                      if source else doctor.Check("stations", "skip", "not read: --manifest given"))
        checks.append(doctor.check_manifest(manifest))
        checks.append(doctor.check_bind(bind, _leases(a.state, manifest, bind)))
    checks.append(doctor.multicast_report(multicast, bind, probe=None if a.no_probe else doctor.loopback_probe))
    failed = any(c.status == "fail" for c in checks)
    if a.json:
        print(json.dumps({"ok": not failed, "checks": [c.to_json() for c in checks]}, indent=2))
    else:
        print(doctor.render(checks))
    return 1 if failed else 0


UNSIGNED = ("UNSIGNED: spike-0 manifests carry no signature, so nothing authenticates this file, and whoever can "
            "write it chooses the keys a listener trusts. RFC-0001 §10.3's root signatures and genesis pin are not "
            "implemented in this spike; no signature was checked.")


def cmd_manifest(a) -> int:
    try:
        path = a.path or str(stations.load(a.stations).manifest)
    except stations.StationsError as e:
        print(_stations_hint(e, f"name the manifest: canticle manifest {a.action} PATH"), file=sys.stderr)
        return 1
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 1
    problems = verify_json(data)
    return (_manifest_verify if a.action == "verify" else _manifest_show)(a, path, data, problems)


def _manifest_verify(a, path: str, data, problems: list) -> int:
    rows = [] if problems else [
        {"name": s["name"], "key_id": wire.key_id(bytes.fromhex(s["public_key"])).hex(), "key_id_listed": "key_id" in s,
         "revoked": s.get("revoked", False)} for s in data["stations"]]
    if a.json:
        print(json.dumps({"path": path, "ok": not problems, "signed": False, "problems": problems, "stations": rows},
                         indent=2))
        return 1 if problems else 0
    if problems:
        print(f"{path}: {len(problems)} problem(s)")
        print("\n".join(f"  - {p}" for p in problems))
    else:
        print(f"{path}: {FORMAT}, {len(rows)} station(s)")
        for r in rows:
            how = "matches its public key" if r["key_id_listed"] else "derived from its public key (the entry lists none)"
            print(f"  {r['name']:<16} {r['key_id']}  {how}{'  REVOKED' if r['revoked'] else ''}")
    print(UNSIGNED)
    print(f"verify: {'FAILED' if problems else 'ok'} (structure, keys and key ids; no signature checked)")
    return 1 if problems else 0


def _manifest_show(a, path: str, data, problems: list) -> int:
    try:
        m = Manifest.from_json(data)
    except Exception as e:  # anything the listener would refuse to load
        print(f"{path}: does not load: {type(e).__name__}: {e} (canticle manifest verify lists every problem)",
              file=sys.stderr)
        return 1
    rows = []
    for e in m:
        row = e.to_json()
        row["streams"] = [{"name": name, "stream_id": f"{sid:08x}"} for sid, name in e.stream_names.items()]
        rows.append(row)
    if a.json:
        print(json.dumps({"path": path, "manifest": data.get("manifest"), "signed": False, "problems": problems,
                          "stations": rows}, indent=2))
        return 1 if problems else 0
    print(f"{path}: {data.get('manifest')}, {len(rows)} station(s), UNSIGNED (nothing authenticates it; RFC §10.3)")
    for r in rows:
        streams = ", ".join("{} ({})".format(x["name"], x["stream_id"]) for x in r["streams"])
        print(f"{r['name']}  key_id {r['key_id']}{'  REVOKED' if r.get('revoked') else ''}")
        print(f"  public_key  {r['public_key']}")
        print(f"  classes     {', '.join(r['classes']) or '-'}")
        print(f"  scopes      {', '.join(r['scopes']) or '-'}")
        print(f"  streams     {streams or '-'}")
    if problems:
        print(f"verify: {len(problems)} problem(s); see canticle manifest verify {path}")
    return 1 if problems else 0


def cmd_vectors(a) -> int:
    from .vectors import build
    Path(a.out).write_text(json.dumps(build(), indent=1) + "\n")
    print(a.out)
    return 0


def _locator_args(p) -> None:
    where = p.add_mutually_exclusive_group()
    where.add_argument("--manifest", help="fleet manifest; without it, the locators come from stations.toml (RFC §13.6)")
    where.add_argument("--stations", help=f"stations.toml to read when --manifest is not given (default {stations.DEFAULT_PATH})")
    p.add_argument("--bind", help=f"UDP address to hear on (default: stations.toml's, else {stations.DEFAULT_BIND})")
    p.add_argument("--multicast", action=argparse.BooleanOptionalAction,
                   help=f"join {runner.MCAST_GROUP} (default: stations.toml's, else off)")


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
    _locator_args(l)
    l.add_argument("--stream", action="append", help="only surface these stream names")
    l.add_argument("--evidence", action="store_true", help="also print rejected datagrams and other evidence")
    l.add_argument("--timestamps", action="store_true", help="add the local receive time (t_ms) to each event")
    l.add_argument("--state", help="file for the safety state kept across restarts (dedup, plucks, "
                   "supersession, epochs; §7.4-§7.8). Default: $XDG_STATE_HOME/canticle/listener-<manifest+bind>.json")
    l.add_argument("--ephemeral", action="store_true", help="UNSAFE: keep no state across restarts (tests only); "
                   "a restarted listener can then surface stale or withdrawn items")
    l.set_defaults(fn=cmd_listen)

    b = sub.add_parser("ambient", help="background emitter: paced short-TTL items from a fixture, no model calls")
    b.add_argument("--control")
    b.add_argument("--stream", required=True)
    b.add_argument("--fixture", required=True, help="one item per line; blank lines and # comments skipped")
    b.add_argument("--class", dest="cls", default="ambient", choices=["ambient", "chatter"])
    b.add_argument("--min-gap", type=float, default=2.0, help="seconds between ticks, at least (>= 1)")
    b.add_argument("--max-gap", type=float, default=10.0, help="seconds between ticks, at most")
    b.add_argument("--ttl", type=float, default=60.0)
    b.add_argument("--breath", type=float, default=0.2, help="probability that a tick sends nothing")
    b.add_argument("--max-bytes", type=int, default=256, help="refuse fixture lines longer than this")
    b.add_argument("--max-per-minute", type=int, default=20)
    b.add_argument("--duration", type=float, default=600.0, help="seconds to run, at most 3600")
    b.add_argument("--seed", type=int)
    b.add_argument("--log", help="append JSON records here instead of stdout")
    b.set_defaults(fn=cmd_ambient)

    u = sub.add_parser("tuner", help="read-only web tuner: a loopback gateway over one listener")
    u.add_argument("--manifest", required=True)
    u.add_argument("--bind", default=f"0.0.0.0:{runner.DEFAULT_PORT}", help="UDP address to hear on")
    u.add_argument("--multicast", action="store_true")
    u.add_argument("--http", default="127.0.0.1:8765", help="loopback host:port for the page")
    u.add_argument("--state", help="listener safety state file (as for listen)")
    u.add_argument("--ephemeral", action="store_true", help="UNSAFE: keep no listener state across restarts")
    u.add_argument("--log", help="append every listener event, as JSON lines, here")
    u.set_defaults(fn=cmd_tuner)

    dm = sub.add_parser("daemon", help="the host daemon: one UDP listener, record v1 to every binding over a unix socket",
                        description="Owns this host's canticle UDP port and serves receptor record v1 (RFC §14.18.3) "
                        "over a unix SOCK_STREAM socket (§11.1, D35). Records are not printed: frame records carry "
                        "item text. hello, fatal and bye are copied to stderr.")
    _locator_args(dm)
    dm.add_argument("--socket", help="unix socket path (default $XDG_RUNTIME_DIR/canticle/daemon.sock; "
                    "its directory must be 0700)")
    dm.add_argument("--state-dir", help="safety state and lease (default $XDG_STATE_HOME/canticle/daemon)")
    dm.add_argument("--allow-uid", type=int, action="append", help="uid allowed to connect (repeatable; default: own uid)")
    dm.add_argument("--health-interval", type=float, default=10.0, help="seconds between health records")
    dm.set_defaults(fn=cmd_daemon)

    d = sub.add_parser("doctor", help="check that this host can run a listener; exit 1 if a check fails",
                       description="Checks Python, cryptography (with an Ed25519 known answer), stations.toml, the "
                       "manifest and the listener's UDP address, then reports multicast. Exit 0 when no check fails, "
                       "1 when one does. Multicast is reported, never decided or enabled: these are not RFC §11.2's "
                       "exit codes, and a 0 says nothing about multicast.")
    _locator_args(d)
    d.add_argument("--state", help="the listener's --state, if it runs with one, to recognise it holding the address")
    d.add_argument("--no-probe", action="store_true", help=f"skip the loopback probe to {runner.MCAST_GROUP}")
    d.add_argument("--json", action="store_true", help="print the checks as JSON")
    d.set_defaults(fn=cmd_doctor)

    mf = sub.add_parser("manifest", help="verify or show a fleet manifest (unsigned in this spike)")
    msub = mf.add_subparsers(dest="action", required=True)
    for action, text in (("verify", "check structure, keys and key ids; exit 1 on any problem (no signature: spike-0 has none)"),
                         ("show", "print each station's key id, grants and streams; exit 1 if verify finds a problem")):
        x = msub.add_parser(action, help=text)
        x.add_argument("path", nargs="?", help="the manifest (default: the one stations.toml names)")
        x.add_argument("--stations", help=f"stations.toml to read when no path is given (default {stations.DEFAULT_PATH})")
        x.add_argument("--json", action="store_true")
        x.set_defaults(fn=cmd_manifest)

    v = sub.add_parser("vectors", help="regenerate the candidate conformance vectors")
    v.add_argument("--out", default="vectors/frame-v2-candidates.json")
    v.set_defaults(fn=cmd_vectors)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
