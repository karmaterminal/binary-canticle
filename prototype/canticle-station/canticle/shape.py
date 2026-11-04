"""``canticle shape``: a shape-only human view of what the host daemon hears (#133).

A dashboard (the EWS concept, #12) shows that the canticle is working: which stations are on air, how old their
carrier is, how much each stream has live and how recently it moved. It never shows what anyone said.

The gateway is one more read-only client of the host daemon's socket, through ``tap`` (#96). It binds no UDP port,
writes no state, sings nothing and wakes nothing. Its HTTP answer is built field by field from a closed list
(``project``): no item text, purpose, digest, sequence, state key, idem, lineage or key material ever reaches it.
A station appears only when the host names it with ``--station``, which the host does only after the station's
owner has said yes (#133): a manifest entry is not consent to human display (RFC §18.9).
"""

from __future__ import annotations

import asyncio
import io
from typing import Callable, Iterable, Optional

from .tap import TapError, TapView, tap
from .tuner import TunerHttp, _now_ms

# Closed words only: anything else a daemon reports is shown as "unknown", never echoed.
# The listener's presence words (listener.presence_state) and tap's "unknown" for a row carried across a gap.
PRESENCE_STATES = {"EQUIPPED_SPEAKING", "EQUIPPED_QUIET", "UNEQUIPPED_PRESENT", "ROOT_UNKNOWN", "UNOBSERVABLE",
                   "UNOBSERVABLE:signed_off", "unknown"}
HEALTH_STATES = {"ok", "degraded"}
RETRY_S = (1, 2, 5, 10, 30)


class ShapeView:
    """What the daemon connection last saw, reduced to shape for the named stations."""

    def __init__(self, stations: Iterable[str], demo_fixture: bool = False):
        self.allowed = sorted(set(stations))
        self.demo_fixture = demo_fixture
        self.tap: Optional[TapView] = None
        self.connected = False

    def project(self, now_ms: int) -> dict:
        """The whole HTTP answer. Every value is a closed word, a station or stream name the host named or the
        manifest bounds, a count or an age in milliseconds."""
        if self.demo_fixture:
            return _demo(now_ms)
        view = self.tap if self.connected else None
        out = {"now_ms": now_ms, "synthetic": False, "connected": view is not None,
               "daemon": _closed((view.health or {}).get("state") if view else None, HEALTH_STATES),
               "receive": view.receive()["health"] if view else "unknown",
               "stations": []}
        live = view.live(now_ms) if view else []
        presence = {}
        if view:
            for p in view.presence.values():
                presence[p["station"].get("name")] = p
        ages = ((view.health or {}).get("beacon_age_ms") or {}) if view else {}
        for name in self.allowed:
            p = presence.get(name)
            streams: dict = {}
            for r in live:
                if r["station"].get("name") != name:
                    continue
                s = streams.setdefault(str(r.get("stream") or ""), {"live": 0, "newest_heard_at": 0})
                s["live"] += 1
                s["newest_heard_at"] = max(s["newest_heard_at"], int(r["times"].get("heard_at") or 0))
            age = ages.get(p.get("key_id")) if p else None
            out["stations"].append({
                "name": name,
                "state": _closed(view.presence_state(p) if p else None, PRESENCE_STATES, missing="not_heard"),
                "beacon_age_ms": int(age) if isinstance(age, (int, float)) else None,
                "streams": [{"stream": s, "live": v["live"],
                             "newest_age_ms": max(0, now_ms - v["newest_heard_at"]) if v["newest_heard_at"] else None}
                            for s, v in sorted(streams.items())],
            })
        return out

    # TunerHttp asks its view for ``stations``.
    stations = project


def _closed(value, allowed: set, missing: str = "unknown") -> str:
    if value is None:
        return missing
    return value if value in allowed else "unknown"


def _demo(now_ms: int) -> dict:
    """Invented, and marked so: never derived from the daemon or the manifest."""
    return {"now_ms": now_ms, "synthetic": True, "connected": False, "daemon": "ok", "receive": "ok",
            "stations": [
                {"name": "demo-melchior", "state": "EQUIPPED_SPEAKING", "beacon_age_ms": 1200,
                 "streams": [{"stream": "chatter", "live": 2, "newest_age_ms": 8000}]},
                {"name": "demo-balthasar", "state": "EQUIPPED_QUIET", "beacon_age_ms": 4100, "streams": []},
                {"name": "demo-casper", "state": "not_heard", "beacon_age_ms": None, "streams": []},
            ]}


async def follow(socket_path: str, view: ShapeView, stop: asyncio.Event, timeout_s: float = 5.0,
                 sleep: Callable = asyncio.sleep) -> None:
    """Hold one ``tap --follow`` connection open, starting a fresh view after every end (a daemon restart) or
    failure, with backoff. What tap would print is discarded: only the view is read, through ``project``."""
    attempt = 0
    while not stop.is_set():
        tv = TapView([("*", "*")])
        view.tap, view.connected = tv, False
        try:
            task = asyncio.ensure_future(tap(socket_path, tv, _Discard(), follow=True, as_json=True,
                                             timeout_s=timeout_s, stop=stop))
            while not task.done():
                if tv.ready and not view.connected:
                    view.connected, attempt = True, 0
                await asyncio.wait({task}, timeout=0.2)
            task.result()
        except TapError:
            pass
        finally:
            view.connected = False
        if stop.is_set():
            return
        await sleep(RETRY_S[min(attempt, len(RETRY_S) - 1)])
        attempt += 1


class _Discard(io.TextIOBase):
    def write(self, s: str) -> int:
        return len(s)


async def run_shape(socket_path: str, stations: Iterable[str], http_host: str, http_port: int,
                    stop: Optional[asyncio.Event] = None, ready=None, demo_fixture: bool = False) -> None:
    view = ShapeView(stations, demo_fixture=demo_fixture)
    http = TunerHttp(view, http_host, http_port, api_path="/api/shape", static=False)
    port = await http.start()
    if ready is not None:
        ready(port)
    stop = stop or asyncio.Event()
    try:
        if demo_fixture:
            await stop.wait()
        else:
            await follow(socket_path, view, stop)
    finally:
        await http.close()
