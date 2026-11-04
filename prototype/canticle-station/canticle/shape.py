"""``canticle shape``: a shape-only human view of what the host daemon hears (#133).

A dashboard (the EWS concept, #12) shows that the canticle is working: which stations are on air, how old their
carrier is, how much each stream has live and how recently it moved. It never shows what anyone said.

The gateway is one more read-only client of the host daemon's socket, through ``tap`` (#96). It binds no UDP port,
writes no state, sings nothing and wakes nothing. Its HTTP answer is built field by field from a closed list
(``project``): no item text, purpose, digest, sequence, state key, idem, lineage or key material ever reaches it.
A station appears only when the host names it with ``--station``, which the host does only after the station's
owner has said yes (#133): a manifest entry is not consent to human display (RFC §18.9).

Nothing old is shown as current.  The daemon reports beacon ages in its ``health`` record, every
``HEALTH_INTERVAL_MS``.  The gateway notes, on its own clock, when each record arrived, and ages the reported values by
the time since.  A connection that has heard no health for ``STALE_MS`` is stale: the answer reads disconnected, and
the gateway drops the connection and joins again.
"""

from __future__ import annotations

import asyncio
import io
from typing import Callable, Iterable, Optional

from .records import HEALTH_INTERVAL_MS
from .tap import TapError, TapView, tap
from .tuner import TunerHttp, _now_ms

# Closed words only: anything else a daemon reports is shown as "unknown", never echoed.
# The listener's presence words (listener.presence_state) and tap's "unknown" for a row carried across a gap.
PRESENCE_STATES = {"EQUIPPED_SPEAKING", "EQUIPPED_QUIET", "UNEQUIPPED_PRESENT", "ROOT_UNKNOWN", "UNOBSERVABLE",
                   "UNOBSERVABLE:signed_off", "unknown"}
HEALTH_STATES = {"ok", "degraded"}
RETRY_S = (1, 2, 5, 10, 30)
STALE_MS = 3 * HEALTH_INTERVAL_MS   # three health records missed


class _StampedView(TapView):
    """A ``TapView`` that remembers when, on the gateway's clock, it became ready and last heard ``health``."""

    def __init__(self, tune: list, clock: Callable[[], int]):
        super().__init__(tune)
        self._clock = clock
        self.ready_at: Optional[int] = None
        self.health_at: Optional[int] = None

    def apply(self, rec: dict) -> list:
        changes = super().apply(rec)
        now = self._clock()
        if self.ready and self.ready_at is None:
            self.ready_at = now
        if rec.get("type") == "health":
            self.health_at = now
        return changes

    def stale(self, now_ms: int) -> bool:
        """No health heard for ``STALE_MS``, counted from the last one or, before the first, from the join."""
        since = self.health_at if self.health_at is not None else self.ready_at
        return since is None or now_ms - since > STALE_MS


class ShapeView:
    """What the daemon connection last saw, reduced to shape for the named stations."""

    def __init__(self, stations: Iterable[str], demo_fixture: bool = False, clock: Callable[[], int] = _now_ms):
        self.allowed = sorted(set(stations))
        self.demo_fixture = demo_fixture
        self.clock = clock
        self.tap: Optional[_StampedView] = None
        self.connected = False

    def project(self, now_ms: int) -> dict:
        """The whole HTTP answer. Every value is a closed word, a station or stream name the host named or the
        manifest bounds, a count or an age in milliseconds."""
        if self.demo_fixture:
            return _demo(now_ms)
        view = self.tap if self.connected and not self._stale(now_ms) else None
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
        # The daemon's ages were true when its health record arrived; age them by the time since.
        since_health = max(0, now_ms - view.health_at) if view and view.health_at is not None else 0
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
                "beacon_age_ms": int(age) + since_health if isinstance(age, (int, float)) and age >= 0 else None,
                "streams": [{"stream": s, "live": v["live"],
                             "newest_age_ms": max(0, now_ms - v["newest_heard_at"]) if v["newest_heard_at"] else None}
                            for s, v in sorted(streams.items())],
            })
        return out

    def _stale(self, now_ms: int) -> bool:
        return self.tap is None or self.tap.stale(now_ms)

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
    """Hold one ``tap --follow`` connection open, starting a fresh view after every end (a daemon restart),
    failure or stale connection (open, but no health for ``STALE_MS``), with backoff. What tap would print is
    discarded: only the view is read, through ``project``."""
    attempt = 0
    while not stop.is_set():
        tv = _StampedView([("*", "*")], view.clock)
        view.tap, view.connected = tv, False
        task = asyncio.ensure_future(tap(socket_path, tv, _Discard(), follow=True, as_json=True,
                                         timeout_s=timeout_s, stop=stop))
        try:
            while not task.done():
                if tv.ready and not view.connected:
                    view.connected, attempt = True, 0
                if view.connected and tv.stale(view.clock()):
                    break   # open but silent: drop it (below) and join again
                await asyncio.wait({task}, timeout=0.2)
            else:
                try:
                    task.result()
                except TapError:
                    pass
        finally:
            view.connected = False
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if stop.is_set():
            return
        await sleep(RETRY_S[min(attempt, len(RETRY_S) - 1)])
        attempt += 1


class _Discard(io.TextIOBase):
    def write(self, s: str) -> int:
        return len(s)


async def run_shape(socket_path: str, stations: Iterable[str], http_host: str, http_port: int,
                    stop: Optional[asyncio.Event] = None, ready=None, demo_fixture: bool = False,
                    clock: Callable[[], int] = _now_ms) -> None:
    view = ShapeView(stations, demo_fixture=demo_fixture, clock=clock)
    http = TunerHttp(view, http_host, http_port, clock=clock, api_path="/api/shape", static=False)
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
