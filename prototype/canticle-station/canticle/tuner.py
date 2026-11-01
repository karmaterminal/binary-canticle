"""A human-facing, metadata-only web dashboard: a loopback gateway over one listener (RFC-0001 §18.9).

The browser never touches the network Canticle travels on. It talks HTTP to this gateway on a
loopback address. The gateway runs a ``Listener`` (§7.4-§7.8, §8.6) and publishes only verified
station, beacon, presence, lease and stream-contract metadata.

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
    """A metadata-only projection of the listener's verified state.

    It deliberately has no item, ring, tombstone, gap or text view. Its only purpose is human
    observability of station presence and stream/beacon/TTL contracts.
    """

    def __init__(self, listener: Listener):
        self.listener = listener
        self.started_ms: Optional[int] = None

    def observe(self, ev: Event, now_ms: int) -> None:
        del ev
        if self.started_ms is None:
            self.started_ms = now_ms

    def stations(self, now_ms: int) -> dict:
        lst = self.listener
        out = []
        for kid, st in lst.stations.items():
            entry = lst.manifest.entry(kid)
            if entry is None or st.last_beacon is None:
                continue
            presence = lst.presence_state(kid, now_ms)
            beacon_active = presence not in ("UNOBSERVABLE", "UNOBSERVABLE:signed_off")
            beacon_age_ms = max(0, now_ms - st.last_beacon)
            beacon_period_ms = st.period_ms
            lease_remaining_ms = max(0, 3 * (beacon_period_ms or 1000) - beacon_age_ms) if beacon_active else 0
            streams = []
            for sid, e in sorted(st.stream_entries.items()):
                name = entry.stream_names.get(sid)
                if name is None:
                    continue  # private or unnamed streams never enter the human projection
                stream_health = "active" if beacon_active and e.live > 0 else (
                    "idle" if beacon_active else "unobservable")
                streams.append({"stream_id": f"{sid:08x}", "name": name,
                                "health": stream_health, "head_seq": e.head_seq, "live": e.live,
                                "loop_ms": e.loop_ms, "loop_max_ms": e.loop_max_ms,
                                "ttl_s": e.default_ttl_s, "default_ttl_s": e.default_ttl_s,
                                "max_ttl_s": e.max_ttl_s, "lease_active": beacon_active,
                                "lease_remaining_ms": lease_remaining_ms})
            out.append({"key_id": kid.hex(), "name": entry.name, "verified": True, "epoch": st.epoch_hwm,
                        "presence": presence, "beacon_active": beacon_active,
                        "lease_active": beacon_active, "lease_remaining_ms": lease_remaining_ms,
                        "last_beacon_ms": st.last_beacon, "beacon_age_ms": beacon_age_ms,
                        "beacon_period_ms": beacon_period_ms,
                        "beacon": {"active": beacon_active, "age_ms": beacon_age_ms,
                                   "period_ms": beacon_period_ms, "lease_remaining_ms": lease_remaining_ms},
                        "streams": streams})
        unverified = {k: v for k, v in lst.evidence_counts.items()
                      if k in ("unknown-key", "bad-signature", "malformed", "revoked")}
        return {"now_ms": now_ms, "gateway_started_ms": self.started_ms, "stations": out,
                "unverified_datagrams": unverified,
                "note": "Human view: verified station and public stream metadata only. "
                        "No item text, summaries, journal entries or payload-bearing events are exposed."}


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
        raise _HttpError(405, "GET only; this human-facing gateway cannot change or reveal listener payloads")

    @staticmethod
    def _json(obj) -> tuple[int, str, bytes]:
        return 200, "application/json", json.dumps(obj).encode()


async def run_tuner(listener: Listener, bind: tuple[str, int], group: Optional[str], http_host: str,
                    http_port: int, stop: Optional[asyncio.Event] = None, on_event=None, ready=None) -> None:
    """Hear on UDP and serve only the human metadata projection on a loopback HTTP port."""
    from . import runner
    view = TunerView(listener)
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
