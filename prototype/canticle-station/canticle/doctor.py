"""``canticle doctor``: can this host run the spike? (RFC-0001 §11.2, §15.7)

Each check is ``ok`` or ``fail`` (or ``skip`` when an earlier failure leaves it nothing to check):

- Python is 3.11 or newer, and ``cryptography`` is 45 or newer and reproduces
  RFC 8032 §7.1 TEST 1, so Ed25519 signing and verification work here;
- ``stations.toml`` loads, unless ``--manifest`` is given (§13.6);
- the manifest verifies (``manifest.verify_json``): its structure, every key
  well-formed and not small-order (§9.3), key ids that match their public keys
  (§10.3). It is unsigned, and the check says so;
- the listener's UDP address is free, or is held by this listener: the
  ``canticle listen`` (or ``canticle tuner``) whose state lease for this
  manifest and address is held.

The address and lease probes never join a running listener's socket or take
its lease: an exclusive bind fails at once on an address in use, and the lease
is tested with a shared lock that a running listener's exclusive lock refuses.
Each holds a free address or lease for microseconds, and a listener starting at
that instant retries its lease (``__main__._listener_state``); its bind does not.

Multicast is a report, never a check. RFC §11.2 lets binding (b) be used only
after a doctor that runs all seven of its steps has passed. This one runs a
loopback probe only: it joins the group on the default interface (so an IGMP
report goes out there) and sends an unsigned nonce with IP TTL 0, which never
leaves this host, on an ephemeral port: not §11.2's signed probe on
``x-test.doctor``. So it neither decides nor enables multicast, and it writes
no configuration. Because the join is visible on the LAN, the probe runs only
when multicast is configured (``stations.toml`` or ``--multicast``) or
``--probe`` asks for it; otherwise multicast is reported as not configured and
nothing joins the group. ``--no-probe`` always skips it.

Exit status: 0 when no check fails, 1 when one does. These are not §11.2's
multicast codes (0 multicast OK, 10, 20, 30): a 0 here says nothing about
multicast.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import runner

MIN_PYTHON = (3, 11)       # pyproject.toml requires-python
MIN_CRYPTOGRAPHY = (45,)   # pyproject.toml dependencies
# RFC 8032 §7.1 TEST 1 (the empty message).
KAT_SECRET = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
KAT_PUBLIC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
KAT_SIGNATURE = ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
                 "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
NOT_DECIDED = ("a report only: this doctor does not run RFC §11.2 steps 1 and 3-7 (MTU, peer beacons, the 270 s "
               "querier check, Wi-Fi and container detection, broadcast fallback, recording the binding), so it neither "
               "decides nor enables multicast")


@dataclass
class Check:
    name: str
    status: str    # ok | fail | skip | report
    detail: str
    data: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail, **self.data}


def check_python(version_info=None) -> Check:
    v = tuple(version_info or sys.version_info)[:3]
    text = ".".join(str(x) for x in v)
    if v[:2] < MIN_PYTHON:
        return Check("python", "fail", f"Python {text} ({sys.executable}); this spike needs 3.11 or newer",
                     {"version": text})
    return Check("python", "ok", f"Python {text} ({sys.executable})", {"version": text})


def ed25519_known_answer() -> Optional[str]:
    """None when this ``cryptography`` reproduces RFC 8032 TEST 1, else what went wrong."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from .wire import public_key_bytes
    try:
        sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(KAT_SECRET))
        if public_key_bytes(sk).hex() != KAT_PUBLIC:
            return "the public key differs"
        sig = sk.sign(b"")
        if sig.hex() != KAT_SIGNATURE:
            return "the signature differs"
        sk.public_key().verify(sig, b"")
        try:
            sk.public_key().verify(sig, b"\x00")
        except InvalidSignature:
            return None
        return "a signature verified over the wrong message"
    except Exception as e:  # a backend without usable Ed25519
        return f"{type(e).__name__}: {e}"


def check_cryptography(version: Optional[str] = None, known_answer: Callable = ed25519_known_answer) -> Check:
    if version is None:
        import cryptography
        version = cryptography.__version__
    release = tuple(int(x) for x in re.findall(r"\d+", version.split("+")[0])[:3])
    if release < MIN_CRYPTOGRAPHY:
        return Check("cryptography", "fail", f"cryptography {version}; this spike needs 45 or newer", {"version": version})
    why = known_answer()
    if why is not None:
        return Check("cryptography", "fail", f"cryptography {version}: Ed25519 does not reproduce RFC 8032 TEST 1: {why}",
                     {"version": version})
    return Check("cryptography", "ok", f"cryptography {version}; Ed25519 reproduces RFC 8032 TEST 1", {"version": version})


def check_manifest(path) -> Check:
    from .manifest import verify_json
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Check("manifest", "fail", f"{p}: not found", {"path": str(p)})
    except (OSError, ValueError) as e:  # ValueError covers bad JSON and bad UTF-8
        return Check("manifest", "fail", f"{p}: {e}", {"path": str(p)})
    problems = verify_json(data)
    if problems:
        return Check("manifest", "fail", f"{p}: {len(problems)} problem(s)", {"path": str(p), "problems": problems})
    stations = data["stations"]
    if not stations:
        return Check("manifest", "fail", f"{p}: no stations, so this listener could verify nothing", {"path": str(p)})
    revoked = sum(1 for s in stations if s.get("revoked"))
    return Check("manifest", "ok",
                 f"{p}: {len(stations)} station(s), {revoked} revoked; keys well-formed, key ids match. UNSIGNED: "
                 "nothing authenticates this file (RFC §10.3 root signatures are not implemented)",
                 {"path": str(p), "stations": len(stations), "signed": False})


def lease_held(path) -> bool:
    """True when a process holds the lease on ``path`` (a listener's state lease, an exclusive flock).
    Probes with a shared, non-blocking lock that is released at once, and never creates the file."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _binds(host: str, port: int) -> Optional[OSError]:
    """Bind without SO_REUSEADDR, so the bind fails on any address in use instead of joining its socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((host, port))
        except OSError as e:
            return e
    return None


def check_bind(bind: str, leases: dict) -> Check:
    """The listener's UDP address is free, or held by this listener. ``leases`` maps a label ("listener",
    "tuner") to the state lease that process holds while it runs (``__main__._listener_state``)."""
    try:
        host, port = runner.parse_addr(bind)
        if not 0 < port < 65536:
            raise ValueError
    except ValueError:
        return Check("bind", "fail", f"{bind!r} is not host:port", {"bind": bind})
    err = _binds(host, port)
    if err is None:
        return Check("bind", "ok", f"{bind} is free", {"bind": bind, "held_by": None})
    if err.errno != errno.EADDRINUSE:
        return Check("bind", "fail", f"{bind}: cannot bind: {err.strerror or err}", {"bind": bind})
    for label, lease in leases.items():
        if lease_held(lease):
            return Check("bind", "ok", f"{bind} is in use by this {label}, which holds {lease}",
                         {"bind": bind, "held_by": label})
    detail = (f"{bind} is in use, and not by this listener: no process holds {', '.join(map(str, leases.values()))}. "
              "It may be another program, or a canticle listener on another manifest, --state or --bind spelling, or "
              "one run with --ephemeral (which holds no lease); RFC §4.2 wants one listener per host. If your "
              "listener runs with --state, pass the same --state here.")
    return Check("bind", "fail", detail, {"bind": bind, "held_by": "other"})


PROBE_TTL = 0  # the probe datagram never leaves this host; only the join's IGMP report does


def loopback_probe(group: str = runner.MCAST_GROUP, timeout_s: float = 1.0) -> tuple[bool, str]:
    """Join ``group`` on the default interface, send it one random nonce on an ephemeral port (IP TTL 0,
    IP_MULTICAST_LOOP on), and wait for the nonce to loop back. It shows that this host can join the group
    and route to it; it says nothing about the LAN."""
    nonce = b"canticle-doctor/1 " + os.urandom(16)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, PROBE_TTL)
        tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        rx.bind(("0.0.0.0", 0))
        rx.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(group) + socket.inet_aton("0.0.0.0"))
        tx.sendto(nonce, (group, rx.getsockname()[1]))
        deadline = time.monotonic() + timeout_s
        while (left := deadline - time.monotonic()) > 0:
            rx.settimeout(left)
            if rx.recvfrom(2048)[0] == nonce:
                return True, f"joined {group} and a probe sent with IP TTL 0 looped back"
        raise socket.timeout
    except socket.timeout:
        return False, f"nothing looped back from {group} within {timeout_s:g} s"
    except OSError as e:
        return False, f"{group}: {e.strerror or e}"
    finally:
        rx.close()
        tx.close()


PROBE_SKIPPED_FLAG = "loopback probe skipped (--no-probe)"
PROBE_SKIPPED_UNCONFIGURED = "multicast not configured — probe skipped (--probe runs it anyway)"


def should_probe(configured: Optional[bool], force: bool = False, never: bool = False) -> bool:
    """Run the loopback probe (which joins the group, so the LAN sees an IGMP report) only when multicast is
    configured, or ``--probe`` forces it. ``--no-probe`` wins over both."""
    return not never and (force or bool(configured))


def multicast_report(configured: Optional[bool], bind: Optional[str],
                     probe: Optional[Callable[[], tuple]] = None, skipped: str = PROBE_SKIPPED_FLAG) -> Check:
    """Status ``report``: never ``fail``, whatever the probe finds, and nothing here turns multicast on.
    ``skipped`` says why, when ``probe`` is None."""
    group = runner.MCAST_GROUP
    data: dict = {"decided": False, "group": group, "configured": configured}
    if probe is None:
        data["loopback"] = None
        parts = [skipped]
    else:
        heard, why = probe()
        data["loopback"] = heard
        parts = [f"loopback probe {'heard' if heard else 'failed'}: {why}"]
    parts.append("listener multicast " + {True: "on", False: "off", None: "unknown"}[configured])
    if configured and bind:
        host = bind.rpartition(":")[0] or bind
        if host not in ("0.0.0.0", group):
            parts.append(f"but it binds {host}, so it cannot hear {group}: bind 0.0.0.0 to hear the group")
            data["bind_hears_group"] = False
    parts.append(NOT_DECIDED)
    return Check("multicast", "report", "; ".join(parts), data)


def render(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for c in checks:
        lines.append(f"{c.status:<6}  {c.name:<{width}}  {c.detail}")
        lines += [f"{'':<6}  {'':<{width}}  - {p}" for p in c.data.get("problems", [])]
    failed = sum(c.status == "fail" for c in checks)
    lines.append(f"doctor: {f'{failed} check(s) failed' if failed else 'every check passed'} (exit {1 if failed else 0}). "
                 "Multicast is reported, not decided (RFC §11.2).")
    return "\n".join(lines)
