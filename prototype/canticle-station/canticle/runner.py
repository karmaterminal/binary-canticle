"""Run a station or a listener on real sockets (RFC-0001 §11, host-local and LAN bindings).

- Station: frames go to one or more UDP destinations (loopback, a LAN peer or
  a multicast group). Clients put items on air through a unix-socket control
  channel restricted to the station's own uid (§11.1: host-local submission).
- Listener: binds UDP (optionally joining the multicast group) and hands each
  datagram to ``Listener.hear``. A bad datagram can never stop the loop.

Relay leases for internet listeners (§11.3) are not implemented in this spike.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import time
from typing import Callable, Optional

from .listener import Event, Listener
from .station import Station

MCAST_GROUP = "239.255.13.13"   # provisional, D22
DEFAULT_PORT = 9999             # provisional, D22
CONTROL_LINE_LIMIT = 64 * 1024


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def parse_addr(text: str, default_port: int = DEFAULT_PORT) -> tuple[str, int]:
    host, _, port = text.rpartition(":")
    if not host:
        return text, default_port
    return host, int(port)


def _peer_uid(writer: asyncio.StreamWriter) -> Optional[int]:
    sock = writer.get_extra_info("socket")
    if sock is None or not hasattr(socket, "SO_PEERCRED"):
        return None
    creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", creds)[1]


def _dispatch(station: Station, req: dict) -> dict:
    op = req.get("op")
    now = now_ms()
    if op == "sing":
        kwargs = {k: req[k] for k in ("text", "state_key", "loop", "scope", "purpose", "intensity") if k in req}
        if "class" in req:
            kwargs["cls"] = req["class"]
        if "ttl" in req:
            kwargs["ttl_s"] = float(req["ttl"])
        if "keep_on_air" in req:
            kwargs["keep_on_air_s"] = int(req["keep_on_air"])
        if "body_hex" in req:
            kwargs["body"] = bytes.fromhex(req["body_hex"])
        if "ctype" in req:
            kwargs["ctype"] = req["ctype"]
        if isinstance(kwargs.get("loop"), str) and kwargs["loop"].isdigit():
            kwargs["loop"] = int(kwargs["loop"])
        return {"ok": True, **station.sing(now, req["stream"], **kwargs).to_json()}
    if op == "hush":
        return {"ok": True, **station.hush(now, req["stream"], int(req["seq"]), int(req.get("reason", 0))).to_json()}
    if op == "status":
        return {"ok": True, **station.status(now)}
    return {"ok": False, "error": f"unknown op {op!r}"}


async def run_station(station: Station, dests: list[tuple[str, int]], control_path: Optional[str] = None,
                      stop: Optional[asyncio.Event] = None, log: Callable[[str], None] = lambda s: None) -> None:
    if station.grant is None:
        raise ValueError("a station behind a control socket needs its manifest grant (§10.4)")
    if station.host_binding:
        raise ValueError("run_station only sends UDP; it cannot carry host-scoped frames (§4.3)")
    stop = stop or asyncio.Event()
    wake = asyncio.Event()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    if hasattr(socket, "IP_MTU_DISCOVER"):
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MTU_DISCOVER, getattr(socket, "IP_PMTUDISC_DO", 2))
    sock.setblocking(False)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            uid = _peer_uid(writer)
            if uid is not None and uid != os.getuid():
                resp = {"ok": False, "error": "peer uid not allowed"}
            else:
                line = await reader.readline()
                try:
                    resp = _dispatch(station, json.loads(line))
                except (ValueError, KeyError, TypeError) as e:
                    resp = {"ok": False, "error": str(e)}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()
            wake.set()

    server = None
    if control_path:
        if os.path.exists(control_path):
            os.unlink(control_path)
        old = os.umask(0o177)
        try:
            server = await asyncio.start_unix_server(handle, path=control_path, limit=CONTROL_LINE_LIMIT)
        finally:
            os.umask(old)
        log(f"control socket {control_path}")

    def send(frame: bytes) -> None:
        for d in dests:
            try:
                sock.sendto(frame, d)
            except OSError as e:  # one unreachable destination must not stop the carousel
                log(f"send to {d}: {e}")

    try:
        while not stop.is_set():
            for frame in station.poll(now_ms()):
                send(frame)
            delay = max(0, min(station.next_due(), now_ms() + 500) - now_ms()) / 1000
            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
    finally:
        send(station.goodbye(now_ms()))
        if server is not None:
            server.close()
            await server.wait_closed()
            if os.path.exists(control_path):
                os.unlink(control_path)
        sock.close()


async def run_listener(listener: Listener, bind: tuple[str, int], on_event: Callable[[Event], None],
                       group: Optional[str] = None, stop: Optional[asyncio.Event] = None,
                       tick_ms: int = 250) -> None:
    stop = stop or asyncio.Event()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(bind)
    if group:
        mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)

    class Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            try:
                events = listener.hear(data, now_ms())
            except Exception as e:  # the listener must survive any datagram (bug B1 class)
                events = [Event("evidence", "?", "", data={"reason": "internal", "detail": type(e).__name__})]
            for ev in events:
                on_event(ev)

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(Proto, sock=sock)
    try:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=tick_ms / 1000)
            except asyncio.TimeoutError:
                pass
            for ev in listener.tick(now_ms()):
                on_event(ev)
    finally:
        transport.close()


def control_request(path: str, req: dict, timeout: float = 5.0) -> dict:
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
