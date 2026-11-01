"""A human-facing, synthetic-only web dashboard: a loopback gateway (RFC-0001 §18.9).

The browser never touches the network Canticle travels on. It talks HTTP to this gateway on a
loopback address. The gateway runs a ``Listener`` (§7.4-§7.8, §8.6), but never publishes its
observations. The manifest is trust configuration, not broadcaster consent for human disclosure.

This is not the agent listener plane. It has no item text, summaries, journal, digests, ring, tune,
or subscription endpoint. It has no control socket and cannot sing or hush. Agent-only listening
remains a separately authorized session capability with exact subscriptions and untrusted framing.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from .listener import Event, Listener

WEB_DIR = Path(__file__).parent / "web"
MAX_REQUEST = 8 * 1024
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/tuner.js": ("tuner.js", "text/javascript; charset=utf-8"),
          "/tuner.css": ("tuner.css", "text/css; charset=utf-8")}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                               "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
}
def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class TunerView:
    """Human view with no path from listener state to HTTP output.

    A synthetic fixture can demonstrate the UI. Neither a verified beacon nor a manifest entry
    grants human visibility; a future live view needs broadcaster-controlled consent.
    """

    def __init__(self, listener: Listener, demo_fixture: bool = False):
        del listener
        self.demo_fixture = demo_fixture

    def observe(self, ev: Event, now_ms: int) -> None:
        del ev, now_ms

    def stations(self, now_ms: int) -> dict:
        out = []
        if self.demo_fixture:
            out.append({"key_id": "0000000000000000", "name": "demo-station", "verified": False,
                        "synthetic": True, "epoch": 0, "presence": "DEMO ONLY",
                        "beacon_active": False, "lease_active": False, "lease_remaining_ms": 0,
                        "beacon_age_ms": 0,
                        "streams": [{"stream_id": "00000000", "name": "demo-stream",
                                     "health": "idle", "head_seq": 0, "live": 0,
                                     "ttl_s": 60, "lease_active": False, "lease_remaining_ms": 0,
                                     "loop_ms": 1000}]})
        return {"now_ms": now_ms, "stations": out, "synthetic": self.demo_fixture,
                "note": "No observed station, stream or message metadata is exposed to humans."}


# ---------------------------------------------------------------- HTTP


class _HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
           413: "Payload Too Large", 415: "Unsupported Media Type", 421: "Misdirected Request",
           429: "Too Many Requests", 503: "Service Unavailable"}


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class TunerHttp:
    """A small read-only HTTP/1.1 server: one request per connection, loopback only, GET only."""

    def __init__(self, view: TunerView, host: str, port: int, clock=_now_ms):
        if not is_loopback(host):
            raise ValueError(f"the tuner gateway binds loopback only in this spike, not {host!r} (RFC §18.9)")
        self.view, self.host, self.port, self.clock = view, host, port, clock
        self.server: Optional[asyncio.base_events.Server] = None

    def allowed_hosts(self) -> set[str]:
        names = {self.host, "localhost"}
        return {f"{n}:{self.port}" for n in names} | {f"[{self.host}]:{self.port}"}

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, self.host, self.port, limit=MAX_REQUEST)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                status, ctype, body = await asyncio.wait_for(self._request(reader), timeout=5)
            except _HttpError as e:
                status, ctype, body = e.status, "application/json", json.dumps({"error": e.message}).encode()
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError):
                status, ctype, body = 400, "application/json", b'{"error": "bad request"}'
            head = [f"HTTP/1.1 {status} {REASONS.get(status, '')}", f"Content-Type: {ctype}",
                    f"Content-Length: {len(body)}", "Connection: close"]
            head += [f"{k}: {v}" for k, v in SECURITY_HEADERS.items()]
            writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + body)
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    async def _request(self, reader: asyncio.StreamReader) -> tuple[int, str, bytes]:
        raw = await reader.readuntil(b"\r\n\r\n")
        lines = raw.decode("latin-1").split("\r\n")
        method, target, _version = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            if line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        # DNS rebinding: a page on another origin that resolves to 127.0.0.1 still sends its own Host.
        if headers.get("host") not in self.allowed_hosts():
            raise _HttpError(421, "unexpected Host header")
        url = urlsplit(target)
        now = self.clock()
        if method == "GET":
            if url.path in STATIC:
                fname, ctype = STATIC[url.path]
                return 200, ctype, (WEB_DIR / fname).read_bytes()
            if url.path == "/api/stations":
                return self._json(self.view.stations(now))
            raise _HttpError(404, "not found")
        raise _HttpError(405, "GET only")

    @staticmethod
    def _json(obj) -> tuple[int, str, bytes]:
        return 200, "application/json", json.dumps(obj).encode()


async def run_tuner(listener: Listener, bind: tuple[str, int], group: Optional[str], http_host: str,
                    http_port: int, stop: Optional[asyncio.Event] = None, on_event=None, ready=None,
                    demo_fixture: bool = False) -> None:
    """Hear on UDP and serve a synthetic-only human view on a loopback HTTP port."""
    from . import runner
    view = TunerView(listener, demo_fixture=demo_fixture)
    http = TunerHttp(view, http_host, http_port)
    port = await http.start()
    if ready is not None:
        ready(port)

    def handle(ev: Event) -> None:
        view.observe(ev, _now_ms())
        if on_event is not None:
            on_event(ev)

    try:
        await runner.run_listener(listener, bind, handle, group, stop)
    finally:
        await http.close()
