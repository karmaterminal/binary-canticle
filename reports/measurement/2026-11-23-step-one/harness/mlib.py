"""Shared pieces of the step-one measurement harness (binary-canticle#168, design §2.8).

Everything here builds throwaway instances in one scratch directory: its own UDP port on
127.0.0.1, its own `canticle daemon` socket and state, its own station keys and unsigned
manifest, its own frond-ear daemon config, database and socket. `Lab.guard` refuses any
path under the live seat's canticle or frond-ear directories, and every child process
gets a scrubbed environment (no DISCORD_*, no FROND_EAR_* but ours, XDG_* pointed into
the scratch directory), so a default can never fall through to a live socket.

Children inherit the driver's niceness: run the driver under `nice -n 19 ionice -c3`.
Each child is its own process group, asked to die with its parent (PR_SET_PDEATHSIG),
and killed by group when the lab closes.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]                      # .../binary-canticle worktree
STATION_SRC = REPO / "prototype" / "canticle-station"
sys.path.insert(0, str(STATION_SRC))

from canticle import wire                                        # noqa: E402
from canticle.ids import CLASS_BY_NAME, SCOPES                  # noqa: E402
from canticle.manifest import Manifest, StationEntry            # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

FROND_EAR = Path(os.environ.get("MEASURE_FROND_EAR",
                                str(REPO.parent / "frond-ear-step-one-measurement-2-ro")))
# The node binaries the live seat runs: the frond-ear daemon unit's node and the shim's (PATH) node.
NODE_DAEMON = os.environ.get("MEASURE_NODE_DAEMON", "/home/figs/.nvm/versions/node/v26.12.1/bin/node")
NODE_SHIM = os.environ.get("MEASURE_NODE_SHIM", "/home/figs/.nvm/versions/node/v26.9.0/bin/node")
PYTHON = sys.executable
CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024

HOME = os.path.expanduser("~")
LIVE_PREFIXES = [
    "/run/user/1000/canticle", "/run/user/1000/frond-ear",
    os.path.join(HOME, ".binary-canticle"), os.path.join(HOME, ".config", "frond-ear"),
    os.path.join(HOME, ".local", "state", "canticle"), os.path.join(HOME, ".local", "state", "frond-ear"),
    os.path.join(HOME, "flesh_beast_best_beast", "source", "frond-ear"),
]

_libc = ctypes.CDLL("libc.so.6", use_errno=True)
PR_SET_PDEATHSIG = 1


def _child_setup() -> None:
    os.setsid()
    _libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)


def mono_ns() -> int:
    return time.monotonic_ns()


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def udp_socket_drops(port: int) -> Optional[dict]:
    """The kernel's own counters for the socket bound to 127.0.0.1:<port> (/proc/net/udp): its receive
    queue bytes and its `drops` (datagrams the kernel discarded because the socket buffer was full).
    The daemon never sees these: they are lost before recvfrom."""
    want = "0100007F:%04X" % port
    with open("/proc/net/udp") as f:
        next(f)
        for line in f:
            parts = line.split()
            if parts[1] == want:
                tx_rx = parts[4].split(":")
                return {"rx_queue": int(tx_rx[1], 16), "drops": int(parts[-1]), "inode": int(parts[9])}
    return None


def udp_snmp() -> dict:
    """Host-wide UDP counters (/proc/net/snmp). Shared with every other UDP user on the host."""
    with open("/proc/net/snmp") as f:
        lines = [l.split() for l in f if l.startswith("Udp:")]
    return dict(zip(lines[0][1:], map(int, lines[1][1:])))


def machine() -> dict:
    """The machine every number in a run was taken on."""
    def read(p):
        try:
            return Path(p).read_text().strip()
        except OSError:
            return None
    cpus = {}
    for d in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
        mhz = read(d / "cpufreq" / "cpuinfo_max_freq")
        cpus[d.name] = int(mhz) // 1000 if mhz else None
    lscpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
    models = sorted({l.split(":", 1)[1].strip() for l in lscpu.splitlines() if l.startswith("Model name")})
    return {
        "host": socket.gethostname(), "arch": os.uname().machine, "kernel": os.uname().release,
        "nproc": os.cpu_count(), "cpu_models": models, "cpu_max_mhz": cpus,
        "mem_total_kb": int(read("/proc/meminfo").split()[1]),
        "loadavg_at_start": read("/proc/loadavg"),
        "python": sys.version.split()[0],
        "net.core.rmem_default": int(read("/proc/sys/net/core/rmem_default")),
        "net.core.rmem_max": int(read("/proc/sys/net/core/rmem_max")),
        "nvme_scheduler": read("/sys/block/nvme0n1/queue/scheduler"),
        "niceness": os.nice(0),
        "ionice": subprocess.run(["ionice", "-p", str(os.getpid())], capture_output=True, text=True).stdout.strip(),
        "cgroup": read("/proc/self/cgroup"),
        "loopback": "127.0.0.1 (lo, mtu 65536)",
    }


def loadavg() -> float:
    return float(Path("/proc/loadavg").read_text().split()[0])


# ---------------------------------------------------------------------------------------- keys


def new_key(path: Path) -> Ed25519PrivateKey:
    """A throwaway station key, in `canticle keygen`'s file format (raw private bytes as hex, 0600)."""
    sk = Ed25519PrivateKey.generate()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(sk.private_bytes_raw().hex() + "\n")
    return sk


def key_id_hex(sk: Ed25519PrivateKey) -> str:
    return wire.key_id(wire.public_key_bytes(sk)).hex()


def entry(name: str, sk: Ed25519PrivateKey, streams, classes=("chatter", "live-state", "root"),
          scopes=("host", "lan")) -> StationEntry:
    return StationEntry(name=name, public_key=wire.public_key_bytes(sk),
                        classes=frozenset(CLASS_BY_NAME[c].code for c in classes),
                        streams=tuple(streams), scopes=frozenset(SCOPES[s] for s in scopes))


def stream_names(prefix: str, n: int) -> list[str]:
    """n stream names whose 32-bit stream ids do not collide (a collision is refused, never rehashed:
    RFC §5.4); a colliding name is skipped for the next one."""
    from canticle.ids import stream_id
    seen, out, i = set(), [], 0
    while len(out) < n:
        name = f"{prefix}{i:05d}"
        sid = stream_id(name)
        if sid not in seen:
            seen.add(sid)
            out.append(name)
        i += 1
    return out


# ---------------------------------------------------------------------------------------- lab


class Lab:
    """One scratch directory and every process started in it."""

    def __init__(self, name: str, base: Optional[Path] = None):
        # Scratch lives on the same ext4/NVMe filesystem as the live daemon's state
        # (~/.local/state/canticle/daemon), so its per-item fsync costs what the seat's does.
        root = base or Path(HOME) / ".cache" / "canticle-measure-2"
        root.mkdir(parents=True, exist_ok=True)
        self.dir = Path(f"{root}/{name}-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}")
        self.dir.mkdir(mode=0o700)
        self.guard(self.dir)
        self.run = self.dir / "run"
        self.run.mkdir(mode=0o700)
        (self.run / "canticle").mkdir(mode=0o700)
        (self.run / "frond-ear").mkdir(mode=0o700)
        self.state = self.dir / "state"
        self.state.mkdir(mode=0o700)
        self.logs = self.dir / "logs"
        self.logs.mkdir()
        self.procs: dict[str, subprocess.Popen] = {}
        self.sampler: Optional[Sampler] = None
        self.port = free_udp_port()
        self.daemon_sock = self.run / "canticle" / "daemon.sock"
        self.manifest_path = self.dir / "fleet.json"
        self.keys: dict[str, Ed25519PrivateKey] = {}
        self.entries: list[StationEntry] = []

    # -- safety
    @staticmethod
    def guard(path) -> None:
        real = os.path.realpath(os.fspath(path))
        for p in LIVE_PREFIXES:
            if real == p or real.startswith(p.rstrip("/") + "/"):
                raise RuntimeError(f"refusing a live path: {real}")

    def env(self, **extra) -> dict:
        """A scrubbed environment: nothing of the seat's but PATH, HOME and the locale."""
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": HOME, "LANG": "C.UTF-8",
               "XDG_RUNTIME_DIR": str(self.run), "XDG_STATE_HOME": str(self.state),
               "XDG_CONFIG_HOME": str(self.dir / "config"), "XDG_CACHE_HOME": str(self.dir / "cache"),
               "PYTHONPATH": str(STATION_SRC), "PYTHONDONTWRITEBYTECODE": "1"}
        env.update({k: str(v) for k, v in extra.items()})
        for k, v in env.items():
            if k.endswith(("_SOCKET", "_DATABASE", "_CONFIG", "_DIR", "_HOME")) and v.startswith("/"):
                self.guard(v)
        return env

    # -- manifest
    def add_station(self, name: str, streams, **kw) -> Ed25519PrivateKey:
        sk = new_key(self.dir / f"{name}.key")
        self.keys[name] = sk
        self.entries.append(entry(name, sk, streams, **kw))
        return sk

    def write_manifest(self) -> Path:
        m = Manifest(self.entries)
        self.manifest_path.write_text(json.dumps(m.to_json()))
        return self.manifest_path

    # -- processes
    def spawn(self, label: str, argv: list, env: Optional[dict] = None, stdin=None, stdout=None,
              stderr=None, cwd=None) -> subprocess.Popen:
        if label in self.procs and self.procs[label].poll() is None:
            raise RuntimeError(f"{label} is already running")
        out = stdout if stdout is not None else open(self.logs / f"{label}.out", "ab")
        err = stderr if stderr is not None else open(self.logs / f"{label}.err", "ab")
        p = subprocess.Popen([str(a) for a in argv], env=env or self.env(), stdin=stdin or subprocess.DEVNULL,
                             stdout=out, stderr=err, cwd=cwd or self.dir, preexec_fn=_child_setup)
        self.procs[label] = p
        if self.sampler:
            self.sampler.track(label, p.pid)
        return p

    def stop(self, label: str, sig=signal.SIGTERM, timeout: float = 10.0) -> Optional[int]:
        p = self.procs.get(label)
        if p is None or p.poll() is not None:
            return p.returncode if p else None
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            pass
        try:
            return p.wait(timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            return p.wait(5)

    def close(self) -> None:
        if self.sampler:
            self.sampler.stop()
        for label in list(self.procs):
            self.stop(label, timeout=5)
        for label, p in self.procs.items():
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def remove(self) -> None:
        self.guard(self.dir)
        shutil.rmtree(self.dir, ignore_errors=True)

    # -- canticle daemon (the multicast-off unicast shape the live seats run: --bind <addr>:<port> --no-multicast)
    def start_daemon(self, label: str = "canticle-daemon", health_s: float = 1.0) -> subprocess.Popen:
        sd = self.state / "canticle-daemon"
        self.guard(sd)
        p = self.spawn(label, [PYTHON, "-m", "canticle", "daemon", "--manifest", self.manifest_path,
                               "--bind", f"127.0.0.1:{self.port}", "--no-multicast",
                               "--socket", self.daemon_sock, "--state-dir", sd,
                               "--health-interval", health_s])
        wait_for(lambda: self.daemon_sock.exists() and udp_socket_drops(self.port) is not None, 20,
                 f"{label} socket", p)
        return p

    # -- a real station (unicast to the lab daemon, control socket in the lab)
    def start_station(self, name: str, streams: list[str], label: Optional[str] = None,
                      beacon_ms: int = 1000) -> tuple[subprocess.Popen, Path]:
        control = self.run / f"station-{name}.sock"
        argv = [PYTHON, "-m", "canticle", "station", "--key", self.dir / f"{name}.key",
                "--manifest", self.manifest_path, "--control", control, "--to", f"127.0.0.1:{self.port}",
                "--beacon-ms", beacon_ms]
        for s in streams:
            argv += ["--stream", s]
        p = self.spawn(label or f"station-{name}", argv)
        wait_for(control.exists, 20, f"station {name} control socket", p)
        return p, control

    # -- frond-ear daemon, host-daemon source, one ear, a dead loopback port standing in for Discord
    def frond_ear_config(self, ear: str, tune: list[str], wake_keys: list[str], delivery: dict,
                         manifest: Optional[Path] = None) -> Path:
        cfg = {
            "botUserId": "100000000000000001",
            "principals": ["100000000000000002"],
            "ears": {ear: {"target": "claude-channel", "channels": {}, "dms": False, "attachCanary": False}},
            "limits": {"maxNotificationChars": 6000},
            "canticle": {
                "enabled": True, "source": "host-daemon", "hostSocket": str(self.daemon_sock),
                "manifestPath": str(manifest or self.manifest_path), "binding": "lan",
                "tune": {ear: tune}, "wakeKeys": wake_keys, "delivery": {ear: delivery},
            },
        }
        path = self.dir / f"frond-ear-{ear}.json"
        path.write_text(json.dumps(cfg, indent=1))
        return path

    def start_frond_ear(self, ear: str, config: Path, label: Optional[str] = None) -> subprocess.Popen:
        label = label or f"frond-ear-{ear}"
        sock = self.run / "frond-ear" / f"{ear}.sock"
        dead = free_udp_port()   # a TCP connect to an unused loopback port is refused at once
        env = self.env(FROND_EAR_CONFIG=config, FROND_EAR_SOCKET=sock,
                       FROND_EAR_DATABASE=self.state / f"frond-ear-{ear}.db",
                       FROND_EAR_ATTACHMENTS=self.state / f"frond-ear-{ear}-attachments",
                       DISCORD_BOT_TOKEN="measurement-dummy-token-not-a-credential",
                       DISCORD_GATEWAY_URL=f"ws://127.0.0.1:{dead}", DISCORD_API_BASE=f"http://127.0.0.1:{dead}/api")
        p = self.spawn(label, [NODE_DAEMON, FROND_EAR / "src" / "cli.ts", "daemon"], env=env, cwd=FROND_EAR)
        wait_for(sock.exists, 30, f"{label} socket", p)
        return p

    def frond_ear_sock(self, ear: str) -> Path:
        return self.run / "frond-ear" / f"{ear}.sock"


def wait_for(cond, timeout: float, what: str, proc: Optional[subprocess.Popen] = None) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"{what}: process exited {proc.returncode}")
        time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for {what}")


# ---------------------------------------------------------------------------------------- frond-ear status


def frond_ear_status(sock: Path, timeout: float = 5.0) -> Optional[dict]:
    """`frond-ear status` over the daemon socket: hello as a CLI client, one status call."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(sock))
            s.sendall(b'{"type":"hello","role":"cli","protocol":1}\n{"type":"status","id":1}\n')
            buf = b""
            while True:
                chunk = s.recv(1 << 20)
                if not chunk:
                    break
                buf += chunk
                for line in buf.split(b"\n"):
                    if line.startswith(b"{") and b'"result"' in line:
                        try:
                            msg = json.loads(line)
                        except ValueError:
                            continue
                        if msg.get("type") == "result" and msg.get("id") == 1:
                            return json.loads(msg["text"])
    except (OSError, ValueError):
        return None
    return None


# ---------------------------------------------------------------------------------------- sampler


class Sampler:
    """CPU% (of one core) and RSS of every tracked process, every `period` seconds, to a CSV."""

    def __init__(self, path: Path, period: float = 0.5, extra=None):
        self.path, self.period, self.extra = path, period, extra
        self.pids: dict[str, int] = {}
        self.last: dict[int, tuple] = {}
        self._stop = threading.Event()
        self.f = open(path, "w")
        self.f.write("t_s,label,pid,cpu_pct,rss_kb,threads,loadavg1\n")
        self.t0 = time.monotonic()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def track(self, label: str, pid: int) -> None:
        self.pids[label] = pid

    def _read(self, pid: int):
        try:
            with open(f"/proc/{pid}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            ticks = int(fields[11]) + int(fields[12])
            threads = int(fields[17])
            rss = int(fields[21]) * PAGE_KB
            return ticks, rss, threads
        except (OSError, IndexError, ValueError):
            return None

    def _run(self) -> None:
        while not self._stop.wait(self.period):
            now = time.monotonic()
            la = loadavg()
            for label, pid in list(self.pids.items()):
                r = self._read(pid)
                if r is None:
                    continue
                ticks, rss, threads = r
                prev = self.last.get(pid)
                self.last[pid] = (now, ticks)
                if prev is None:
                    continue
                cpu = 100.0 * (ticks - prev[1]) / CLK_TCK / (now - prev[0])
                self.f.write(f"{now - self.t0:.2f},{label},{pid},{cpu:.1f},{rss},{threads},{la}\n")
            if self.extra:
                try:
                    self.extra(now - self.t0)
                except Exception:
                    pass
            self.f.flush()

    def stop(self) -> None:
        self._stop.set()
        self.thread.join(5)
        self.f.close()


def summarize_samples(path: Path) -> dict:
    """Per label: mean and max CPU%, max and last RSS (kB)."""
    out: dict[str, dict] = {}
    with open(path) as f:
        next(f)
        for line in f:
            t, label, pid, cpu, rss, threads, la = line.strip().split(",")
            d = out.setdefault(label, {"n": 0, "cpu_sum": 0.0, "cpu_max": 0.0, "rss_max_kb": 0, "rss_first_kb": None})
            d["n"] += 1
            d["cpu_sum"] += float(cpu)
            d["cpu_max"] = max(d["cpu_max"], float(cpu))
            d["rss_max_kb"] = max(d["rss_max_kb"], int(rss))
            d["rss_last_kb"] = int(rss)
            if d["rss_first_kb"] is None:
                d["rss_first_kb"] = int(rss)
    for d in out.values():
        d["cpu_mean"] = round(d.pop("cpu_sum") / max(1, d["n"]), 1)
    return out


def percentile(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
