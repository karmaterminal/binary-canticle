"""A read-only web tuner: a loopback gateway over one listener's verified view (issue #57, RFC-0001 §18.9).

The browser never touches the network canticle travels on. It talks HTTP to this gateway on a
loopback address. The gateway runs a ``Listener`` (§7.4-§7.8, §8.6) that hears and verifies every
stream its manifest names, and serves what that listener holds now: the stations it hears, their
streams, and the live ring of the channel a browser has tuned.

Tuning here is local to the gateway: it picks what a browser is shown. It never reaches a station,
never becomes a wire subscription, and is not a session's tune (§14.6.1), so nothing lands in any
session. The gateway has no control socket and cannot sing, hush or change what the listener
accepts.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from . import wire
from .ids import CLASSES, CTYPES
from .listener import Event, Listener

WEB_DIR = Path(__file__).parent / "web"
TEXT_LIMIT = 512            # characters of heard text shown per item
RING_LIMIT = 64             # items per ring response
TOMBSTONE_MS = 60_000       # how long an expired, withdrawn or superseded item stays listed (labelled)
TOMBSTONE_LIMIT = 32
UNHEARD_WINDOW = 64         # sequence numbers below the head checked for gaps
SEEN_WINDOW = 2 * UNHEARD_WINDOW   # heard seqs kept per channel: the gap window, with room for items
                                   # heard ahead of the last beacon's head
MAX_SUBS = 16
SUB_IDLE_MS = 30_000
MIN_POLL_MS = 250
MAX_REQUEST = 8 * 1024
MAX_BODY = 4 * 1024
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
TEXT_CTYPE = CTYPES["text/plain; charset=utf-8"]


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass
class _Channel:
    epoch: int = -1                                 # the station epoch that seen and floor belong to
    seen: set = field(default_factory=set)          # heard seqs >= floor, at most SEEN_WINDOW of them
    floor: int = 0                                  # seqs below this were dropped and are never shown as gaps
    tombstones: deque = field(default_factory=lambda: deque(maxlen=TOMBSTONE_LIMIT))


class TunerView:
    """What the gateway can show, derived only from the listener's verified state and events."""

    def __init__(self, listener: Listener):
        self.listener = listener
        self.channels: dict[tuple, _Channel] = {}   # (key_id, stream_id) -> _Channel
        self.started_ms: Optional[int] = None

    def _chan(self, kid: bytes, sid: int) -> _Channel:
        return self.channels.setdefault((kid, sid), _Channel())

    def _sid(self, kid: bytes, name: Optional[str]) -> Optional[int]:
        e = self.listener.manifest.entry(kid)
        if e is None or name is None:
            return None
        return next((sid for sid, n in e.stream_names.items() if n == name), None)

    def observe(self, ev: Event, now_ms: int) -> None:
        if self.started_ms is None:
            self.started_ms = now_ms
        if not ev.key_id or ev.stream is None:
            return
        kid = bytes.fromhex(ev.key_id)
        sid = self._sid(kid, ev.stream)
        if sid is None:
            return
        ch = self._note(kid, sid, [s for s in (ev.seq, ev.data.get("by_seq")) if s is not None])
        if ev.kind in ("expired", "withdrawn", "superseded"):
            ch.tombstones.append({"seq": ev.seq, "reason": ev.kind, "at_ms": now_ms,
                                  **({"by_seq": ev.data["by_seq"]} if "by_seq" in ev.data else {})})

    def _note(self, kid: bytes, sid: int, seqs) -> _Channel:
        """Record heard seqs of the station's current epoch, keeping only a bounded window.

        The window is the SEEN_WINDOW seqs below the higher of the beacon's head and the highest seq
        heard. It moves up as the stream advances and starts afresh at an epoch change, so memory stays
        bounded however long a stream runs (Silas's review of #59).
        """
        ch = self._chan(kid, sid)
        st = self.listener.stations.get(kid)
        epoch = st.epoch_hwm if st else 0
        if ch.epoch != epoch:
            ch.epoch, ch.seen, ch.floor = epoch, set(), 0
        ch.seen.update(s for s in seqs if s >= ch.floor)
        e = st.stream_entries.get(sid) if st else None
        top = max(e.head_seq if e else 0, max(ch.seen, default=0))
        if top - SEEN_WINDOW + 1 > ch.floor:
            ch.floor = top - SEEN_WINDOW + 1
            ch.seen = {s for s in ch.seen if s >= ch.floor}
        return ch

    def _seen(self, kid: bytes, sid: int) -> _Channel:
        """Add what the listener accepted for this channel's current epoch (items and PLUCKs, from its
        dedup table, which keeps each until local expiry) to the bounded window, and return it."""
        st = self.listener.stations.get(kid)
        epoch = st.epoch_hwm if st else 0
        return self._note(kid, sid, [i[3] for i in self.listener.dedup
                                     if i[0] == kid and i[2] == sid and i[1] == epoch])

    # ------------------------------------------------------------ snapshots

    def stations(self, now_ms: int) -> dict:
        lst = self.listener
        out = []
        for kid, st in lst.stations.items():
            entry = lst.manifest.entry(kid)
            if entry is None or st.last_beacon is None:
                continue
            streams = []
            for sid, e in sorted(st.stream_entries.items()):
                name = entry.stream_names.get(sid)
                streams.append({"stream_id": f"{sid:08x}", "name": name, "tunable": name is not None,
                                "head_seq": e.head_seq, "live": e.live, "loop_ms": e.loop_ms,
                                "loop_max_ms": e.loop_max_ms, "default_ttl_s": e.default_ttl_s,
                                "max_ttl_s": e.max_ttl_s})
            out.append({"key_id": kid.hex(), "name": entry.name, "verified": True, "epoch": st.epoch_hwm,
                        "presence": lst.presence_state(kid, now_ms),
                        "last_beacon_ms": st.last_beacon, "beacon_age_ms": now_ms - st.last_beacon,
                        "beacon_period_ms": st.period_ms, "streams": streams})
        unverified = {k: v for k, v in lst.evidence_counts.items()
                      if k in ("unknown-key", "bad-signature", "malformed", "revoked")}
        return {"now_ms": now_ms, "gateway_started_ms": self.started_ms, "stations": out,
                "unverified_datagrams": unverified,
                "note": "Stations are listed only after a beacon verifies against a manifest key. "
                        "Datagrams that fail verification are counted, never attributed or shown."}

    def ring(self, kid: bytes, sid: int, now_ms: int) -> Optional[dict]:
        lst = self.listener
        entry = lst.manifest.entry(kid)
        if entry is None or sid not in entry.stream_names:
            return None
        st = lst.stations.get(kid)
        items = []
        for ident, h in lst.current.items():
            if ident[0] != kid or h.item.stream != sid:
                continue
            it = h.item
            row = {"seq": it.seq, "epoch": it.epoch, "class": CLASSES[it.cls].name, "issued_at": it.issued_at,
                   "expires_at": it.expires_at, "local_expiry_ms": h.local_expiry,
                   "remaining_ms": max(0, h.local_expiry - now_ms), "first_heard_ms": h.first_heard,
                   "copies": h.copies}
            if it.state_key is not None:
                row["state_key"] = it.state_key
            if it.body is not None and it.ctype == TEXT_CTYPE:
                text = it.body.decode("utf-8", "replace")
                row["text"] = text[:TEXT_LIMIT]
                if len(text) > TEXT_LIMIT:
                    row["truncated"] = True
            elif it.body is not None:
                row["binary_bytes"] = len(it.body)
            items.append(row)
        items.sort(key=lambda r: r["seq"], reverse=True)
        ch = self._chan(kid, sid)
        tombs = [t for t in ch.tombstones if now_ms - t["at_ms"] <= TOMBSTONE_MS]
        head = None
        unheard: list[int] = []
        e = st.stream_entries.get(sid) if st else None
        if e is not None:
            head = e.head_seq
            ch = self._seen(kid, sid)
            # Never report a seq below the retained floor as unheard: it was dropped, not missed.
            unheard = [s for s in range(max(1, head - UNHEARD_WINDOW + 1, ch.floor), head + 1) if s not in ch.seen]
        return {"now_ms": now_ms, "station": entry.name, "key_id": kid.hex(), "stream": entry.stream_names[sid],
                "stream_id": f"{sid:08x}", "epoch": st.epoch_hwm if st else None,
                "presence": lst.presence_state(kid, now_ms),
                "head_seq": head, "live_advertised": e.live if e else None,
                "loop_ms": e.loop_ms if e else None, "items": items[:RING_LIMIT],
                "items_truncated": max(0, len(items) - RING_LIMIT), "tombstones": tombs,
                "unheard_seq": unheard, "gateway_started_ms": self.started_ms,
                "note": "Live items are the ones this listener holds now, each until its local expiry. "
                        "Nothing from before the gateway started, or already expired, is shown as live. "
                        "An unheard seq may have expired before the gateway heard it, been lost, or be "
                        "on air still; this spike's beacons carry no trail_seq to tell which."}


# ---------------------------------------------------------------- subscriptions


@dataclass
class _Sub:
    kid: bytes
    sid: int
    created_ms: int
    last_ms: int
    last_poll_ms: int = 0


class Subscriptions:
    """Gateway-local tune state: which channel each browser watches. Never sent anywhere."""

    def __init__(self, view: TunerView):
        self.view = view
        self.subs: dict[str, _Sub] = {}

    def _expire(self, now_ms: int) -> None:
        for sub_id in [k for k, s in self.subs.items() if now_ms - s.last_ms > SUB_IDLE_MS]:
            del self.subs[sub_id]

    def tune(self, kid: bytes, sid: int, now_ms: int) -> str:
        self._expire(now_ms)
        entry = self.view.listener.manifest.entry(kid)
        if entry is None or sid not in entry.stream_names:
            raise LookupError("no such named stream for a manifest station")
        if len(self.subs) >= MAX_SUBS:
            raise OverflowError(f"at most {MAX_SUBS} tuned channels at once")
        sub_id = secrets.token_hex(12)
        self.subs[sub_id] = _Sub(kid, sid, now_ms, now_ms)
        return sub_id

    def leave(self, sub_id: str) -> bool:
        return self.subs.pop(sub_id, None) is not None

    def get(self, sub_id: str, now_ms: int) -> Optional[_Sub]:
        self._expire(now_ms)
        sub = self.subs.get(sub_id)
        if sub is not None:
            sub.last_ms = now_ms
        return sub


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
    """A deliberately small HTTP/1.1 server: one request per connection, loopback only, GET and POST."""

    def __init__(self, view: TunerView, subs: Subscriptions, host: str, port: int, clock=_now_ms):
        if not is_loopback(host):
            raise ValueError(f"the tuner gateway binds loopback only in this spike, not {host!r} (RFC §18.9)")
        self.view, self.subs, self.host, self.port, self.clock = view, subs, host, port, clock
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
            if url.path == "/api/ring":
                sub_id = (parse_qs(url.query).get("sub") or [""])[0]
                sub = self.subs.get(sub_id, now)
                if sub is None:
                    raise _HttpError(404, "not tuned (unknown or idle subscription)")
                if now - sub.last_poll_ms < MIN_POLL_MS:
                    raise _HttpError(429, f"poll at most every {MIN_POLL_MS} ms")
                sub.last_poll_ms = now
                return self._json(self.view.ring(sub.kid, sub.sid, now))
            raise _HttpError(404, "not found")
        if method == "POST":
            origin = headers.get("origin")
            if origin is not None and urlsplit(origin).netloc not in self.allowed_hosts():
                raise _HttpError(403, "cross-origin request refused")
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                raise _HttpError(415, "send application/json")
            length = int(headers.get("content-length", "0"))
            if length > MAX_BODY:
                raise _HttpError(413, "body too large")
            req = json.loads(await reader.readexactly(length) or b"{}")
            if not isinstance(req, dict):
                raise _HttpError(400, "expected a JSON object")
            if url.path == "/api/tune":
                try:
                    kid, sid = bytes.fromhex(str(req["station"])), int(str(req["stream"]), 16)
                except (KeyError, ValueError):
                    raise _HttpError(400, "need station (key_id hex) and stream (stream_id hex)")
                try:
                    sub_id = self.subs.tune(kid, sid, now)
                except LookupError as e:
                    raise _HttpError(404, str(e))
                except OverflowError as e:
                    raise _HttpError(503, str(e))
                return self._json({"sub": sub_id, "station": kid.hex(), "stream_id": f"{sid:08x}"})
            if url.path == "/api/leave":
                return self._json({"left": self.subs.leave(str(req.get("sub", "")))})
            raise _HttpError(404, "not found")
        raise _HttpError(405, "GET and POST only; this gateway cannot change anything on air")

    @staticmethod
    def _json(obj) -> tuple[int, str, bytes]:
        return 200, "application/json", json.dumps(obj).encode()


async def run_tuner(listener: Listener, bind: tuple[str, int], group: Optional[str], http_host: str,
                    http_port: int, stop: Optional[asyncio.Event] = None, on_event=None, ready=None) -> None:
    """Hear on UDP (optionally joining a multicast group) and serve the view on a loopback HTTP port."""
    from . import runner
    view = TunerView(listener)
    http = TunerHttp(view, Subscriptions(view), http_host, http_port)
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
