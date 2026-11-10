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

``/api/drum`` is the same day at finer grain, for a helicorder: 24 hours of 10-second buckets, sparse, in 96
fifteen-minute rows.

``/api/flow`` is the same shape over time (#135): for the last hour, minute by minute, whether the gateway was
observing, whether each named station's beacon was heard, how many items arrived on each stream, and the presence
state; and the last arrivals, each only a time, a station and a stream.  It is kept in memory, so it starts empty at
every gateway start, and says when it started.  A join snapshot is never counted as arrivals.
"""

from __future__ import annotations

import asyncio
import io
from collections import deque
from typing import Callable, Iterable, Optional

from . import grant
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
MINUTE_MS = 60_000
WINDOW_MIN = 60
RIVER_MAX = 50
SEEN_MAX = 4096   # item identities remembered, in memory only, to tell a new item from a replayed one
DRUM_BUCKET_MS = 10_000            # /api/drum: a helicorder day, in 10 s buckets
DRUM_ROW_MS = 15 * MINUTE_MS       # one drum turn
DRUM_ROWS = 96                     # 24 h
DRUM_BUCKETS = DRUM_ROWS * DRUM_ROW_MS // DRUM_BUCKET_MS


class _StampedView(TapView):
    """A ``TapView`` that remembers when, on the gateway's clock, it became ready and last heard ``health``."""

    def __init__(self, tune: list, clock: Callable[[], int], flow: Optional["Flow"] = None):
        super().__init__(tune)
        self._clock = clock
        self._flow = flow
        self.ready_at: Optional[int] = None
        self.health_at: Optional[int] = None

    def apply(self, rec: dict) -> list:
        changes = super().apply(rec)
        now = self._clock()
        if self.ready and self.ready_at is None:
            self.ready_at = now
        if rec.get("type") == "health":
            self.health_at = now
        if self._flow is not None and self.ready:
            self._flow.observe(self, changes, rec.get("type"), now)
        return changes

    def stale(self, now_ms: int) -> bool:
        """No health heard for ``STALE_MS``, counted from the last one or, before the first, from the join."""
        since = self.health_at if self.health_at is not None else self.ready_at
        return since is None or now_ms - since > STALE_MS


class ShapeView:
    """What the daemon connection last saw, reduced to shape for the named stations."""

    def __init__(self, stations: Iterable[str], demo_fixture: bool = False, clock: Callable[[], int] = _now_ms,
                 display: Optional[str] = None):
        self.allowed = sorted(set(stations))
        self.demo_fixture = demo_fixture
        self.clock = clock
        # With a display name, ``stations`` is only the host's ceiling and each station needs its own grant (#137).
        self.display = grant.check_display(display) if display is not None else None
        self.flow = Flow(self.allowed, clock, display=self.display)
        self.tap: Optional[_StampedView] = None
        self.connected = False

    def project(self, now_ms: int) -> dict:
        """The whole HTTP answer. Every value is a closed word, a station or stream name the host named or the
        manifest bounds, a count or an age in milliseconds."""
        if self.demo_fixture:
            return _demo(now_ms)
        view = self._live(now_ms)
        grants = self.grants(now_ms, view)
        out = {"now_ms": now_ms, "synthetic": False, "connected": view is not None,
               "daemon": _closed((view.health or {}).get("state") if view else None, HEALTH_STATES),
               "receive": view.receive()["health"] if view else "unknown",
               "stations": []}
        if self.display is not None:
            out["display"] = self.display
        live = view.live(now_ms) if view else []
        presence = {}
        if view:
            for p in view.presence.values():
                presence[p["station"].get("name")] = p
        ages = ((view.health or {}).get("beacon_age_ms") or {}) if view else {}
        # The daemon's ages were true when its health record arrived; age them by the time since.
        since_health = max(0, now_ms - view.health_at) if view and view.health_at is not None else 0
        for name in self.allowed:
            g = _shown(grants, name)
            if g is None:
                continue   # no verified grant: no row, no trace (#137)
            p = presence.get(name)
            streams: dict = {}
            for r in live:
                if r["station"].get("name") != name or (grants is not None and r.get("stream") == grant.STREAM):
                    continue
                s = streams.setdefault(str(r.get("stream") or ""), {"live": 0, "newest_heard_at": 0})
                s["live"] += 1
                s["newest_heard_at"] = max(s["newest_heard_at"], int(r["times"].get("heard_at") or 0))
            age = ages.get(p.get("key_id")) if p and grant.at_least(g, "beacon") else None
            row = {
                "name": name,
                "state": _closed(view.presence_state(p) if p else None, PRESENCE_STATES, missing="not_heard"),
                "beacon_age_ms": int(age) + since_health if isinstance(age, (int, float)) and age >= 0 else None,
                "streams": [{"stream": s, "live": v["live"],
                             "newest_age_ms": max(0, now_ms - v["newest_heard_at"]) if v["newest_heard_at"] else None}
                            for s, v in sorted(streams.items())] if grant.at_least(g, "counts") else [],
            }
            if grants is not None:
                row["withheld"] = g["withheld"]
            out["stations"].append(row)
        return out

    def grants(self, now_ms: int, view: Optional["_StampedView"] = None) -> Optional[dict]:
        """The stations a live connection shows a verified grant for, or None without a display name (host-named
        stations only).  A connection that is not live verifies nothing, so nothing is shown (fail closed)."""
        if self.display is None:
            return None
        view = view if view is not None else self._live(now_ms)
        return grant.read(view, self.display, self.allowed, now_ms)[0] if view is not None else {}

    def _live(self, now_ms: int) -> Optional[_StampedView]:
        """The connection this answer may call live: connected and not stale, else None."""
        return self.tap if self.connected and not self._stale(now_ms) else None

    def flow_project(self, now_ms: int) -> dict:
        return _demo_flow(now_ms) if self.demo_fixture else self.flow.project(now_ms, self.grants(now_ms))

    def drum_project(self, now_ms: int) -> dict:
        if self.demo_fixture:
            return _demo_drum(now_ms)
        live = self._live(now_ms)
        return self.flow.project_drum(now_ms, live, self.grants(now_ms, live))

    def _stale(self, now_ms: int) -> bool:
        return self.tap is None or self.tap.stale(now_ms)

    # TunerHttp asks its view for ``stations``.
    stations = project


class Flow:
    """The last ``WINDOW_MIN`` minutes, in memory, for the named stations only (#135).

    A minute is *observed* when at least one health record arrived in it: the gateway was connected then, which is not
    proof that it heard everything in that minute.  Each station's minute records whether its beacon was heard, its
    arrivals per stream and its presence state at the last health record of the minute.

    An arrival is a new emission, heard live: a surfaced item after the join (tap's ``item`` change) that
    - the daemon reports as ``dedup: first``, not ``resurfaced`` (a daemon restart hearing a still-live item again);
    - this gateway has not already counted (its identity is remembered, in memory only and never served, until the
      item expires);
    - had not already expired when the gateway consumed it.

    It is placed at the daemon's ``heard_at``, not at the gateway's clock.  The join snapshot never counts.  The river
    keeps the last ``RIVER_MAX`` arrivals as a time, a station and a stream, nothing else."""

    def __init__(self, stations: Iterable[str], clock: Callable[[], int] = _now_ms, display: Optional[str] = None):
        self.allowed = sorted(set(stations))
        self.display = display
        # With a display: the grant each station's history is kept under, as last verified (#137).  A station is
        # recorded only while a grant is verified now; its history is purged down to a narrower grant, or entirely,
        # only when a complete view proves the narrowing.  An unverifiable moment hides it and keeps what it has.
        self.held: dict = {}
        self.started_at = clock()
        self.observed: set = set()
        self.minutes: dict = {name: {} for name in self.allowed}
        self.river: deque = deque(maxlen=RIVER_MAX)
        self._seen: dict = {}   # idem -> local expiry: counted items, so a replay is not counted again
        # /api/drum: 10 s buckets for 24 h, sparse
        self.drum_observed: set = set()
        # coverage is an interval, not the bucket a record lands in: health comes every 10 s, the bucket is 10 s, so
        # jitter would leave a connected bucket looking unobserved (🌿 on #138).  Two records on the same connection
        # at most STALE_MS apart cover the span between them; likewise two sightings of a station's beacon.
        self._last_health: Optional[tuple] = None          # (view, at)
        self._last_beacon: dict = {}                        # name -> (view, beacon time)
        self.drum_beacons: dict = {name: set() for name in self.allowed}
        self.drum_arrivals: dict = {name: {} for name in self.allowed}

    def _bucket(self, name: str, minute: int) -> dict:
        return self.minutes[name].setdefault(minute, {"beacon": False, "arrivals": {}, "state": None})

    def _settle(self, view: TapView, now_ms: int) -> Optional[dict]:
        """The grants verified on ``view`` now (None without a display), purging what a proven narrowing removed."""
        if self.display is None:
            return None
        grants, proof = grant.read(view, self.display, self.allowed, now_ms)
        for name in self.allowed:
            new, old = grants.get(name), self.held.get(name)
            if new is None and not proof:
                continue   # unverifiable now: hide (below) and keep
            if old is not None and (new is None or grant.RANK[new["scope"]] < grant.RANK[old["scope"]]):
                self._purge(name, new)
            if new is None:
                self.held.pop(name, None)
            else:
                self.held[name] = new
        return grants

    def _purge(self, name: str, keep: Optional[dict]) -> None:
        """Drop what ``name``'s history holds beyond ``keep`` (None: everything), so a later grant cannot bring it
        back (🌫 on #137)."""
        if not grant.at_least(keep, "river"):
            self.river = deque((r for r in self.river if r[1] != name), maxlen=RIVER_MAX)
        if not grant.at_least(keep, "counts"):
            for b in self.minutes[name].values():
                b["arrivals"] = {}
            self.drum_arrivals[name] = {}
        if not grant.at_least(keep, "beacon"):
            for b in self.minutes[name].values():
                b["beacon"] = False
            self.drum_beacons[name] = set()
            self._last_beacon.pop(name, None)
        if keep is None:
            self.minutes[name] = {}

    def observe(self, view: TapView, changes: list, type_: Optional[str], now_ms: int) -> None:
        grants = self._settle(view, now_ms)

        def may(name: str, tier: str) -> bool:
            return grants is None or grant.at_least(grants.get(name), tier)

        names = {}
        for p in view.presence.values():
            name = p["station"].get("name")
            if name in self.minutes and may(name, "presence"):
                names[p.get("key_id")] = (name, p)
        if type_ == "health":
            minute = now_ms // MINUTE_MS
            self.observed.add(minute)
            self.drum_observed.update(self._span(self._last_health, view, now_ms))
            self._last_health = (view, now_ms)
            for key_id, age in ((view.health or {}).get("beacon_age_ms") or {}).items():
                if key_id in names and isinstance(age, (int, float)) and 0 <= age <= MINUTE_MS \
                        and may(names[key_id][0], "beacon"):
                    name, p = names[key_id]
                    beacon_at = now_ms - int(age)
                    self._bucket(name, beacon_at // MINUTE_MS)["beacon"] = True
                    self.drum_beacons[name].update(self._span(self._last_beacon.get(name), view, beacon_at))
                    self._last_beacon[name] = (view, beacon_at)
            for name, p in names.values():
                self._bucket(name, minute)["state"] = _closed(view.presence_state(p), PRESENCE_STATES)
        for kind, fields in changes:
            if kind != "item":
                continue
            name = fields["station"].get("name")
            if name not in self.minutes or not may(name, "counts"):
                continue
            if grants is not None and fields.get("stream") == grant.STREAM:
                continue   # the grant's own carrier is not telemetry
            times = fields.get("times") or {}
            expiry, heard = times.get("local_expiry_at"), times.get("heard_at")
            idem = fields.get("idem")
            if (fields.get("dedup", "first") != "first" or idem in self._seen
                    or not isinstance(expiry, int) or expiry <= now_ms or not isinstance(heard, int)):
                continue   # a replay, one already counted, or one already off air: not a new emission
            self._seen[idem] = expiry
            at = min(heard, now_ms)
            stream = str(fields.get("stream") or "")
            arrivals = self._bucket(name, at // MINUTE_MS)["arrivals"]
            arrivals[stream] = arrivals.get(stream, 0) + 1
            drum = self.drum_arrivals[name].setdefault(at // DRUM_BUCKET_MS, {})
            drum[stream] = drum.get(stream, 0) + 1
            if may(name, "river"):
                self.river.append((at, name, stream))
        self._prune(now_ms)

    @staticmethod
    def _span(last: Optional[tuple], view: TapView, at: int) -> range:
        """The drum buckets ``at`` covers: from the previous sighting on the same connection when it is at most
        ``STALE_MS`` earlier, else ``at``'s own bucket.  A new connection, or a longer silence, leaves its gap open."""
        if last is not None and last[0] is view and 0 <= at - last[1] <= STALE_MS:
            return range(last[1] // DRUM_BUCKET_MS, at // DRUM_BUCKET_MS + 1)
        return range(at // DRUM_BUCKET_MS, at // DRUM_BUCKET_MS + 1)

    def _prune(self, now_ms: int) -> None:
        for idem in [i for i, exp in self._seen.items() if exp <= now_ms]:
            del self._seen[idem]
        while len(self._seen) > SEEN_MAX:   # dicts keep insertion order: drop the oldest counted
            del self._seen[next(iter(self._seen))]
        oldest = (now_ms - DRUM_ROWS * DRUM_ROW_MS) // DRUM_BUCKET_MS
        self.drum_observed = {b for b in self.drum_observed if b >= oldest}
        for name in self.allowed:
            self.drum_beacons[name] = {b for b in self.drum_beacons[name] if b >= oldest}
            for b in [b for b in self.drum_arrivals[name] if b < oldest]:
                del self.drum_arrivals[name][b]
        first = now_ms // MINUTE_MS - WINDOW_MIN + 1
        self.observed = {m for m in self.observed if m >= first}
        for buckets in self.minutes.values():
            for m in [m for m in buckets if m < first]:
                del buckets[m]

    def project(self, now_ms: int, grants: Optional[dict] = None) -> dict:
        """The whole ``/api/flow`` answer: closed words, names the host named, stream names the manifest bounds,
        counts, booleans and times in milliseconds.  ``grants`` (with a display) narrows it to granted stations and
        scopes; None shows every host-named station."""
        self._prune(now_ms)
        last = now_ms // MINUTE_MS
        minutes = list(range(last - WINDOW_MIN + 1, last + 1))
        out = {"now_ms": now_ms, "since_ms": self.started_at, "minute_ms": MINUTE_MS, "synthetic": False,
               "minutes": [{"t": m * MINUTE_MS, "observed": m in self.observed} for m in minutes],
               "stations": [], "river": []}
        for name in self.allowed:
            g = _shown(grants, name)
            if g is None:
                continue
            beacon, counts = grant.at_least(g, "beacon"), grant.at_least(g, "counts")
            row = []
            for m in minutes:
                b = self.minutes[name].get(m)
                row.append({"beacon": bool(beacon and b and b["beacon"]),
                            "arrivals": [{"stream": s, "n": n} for s, n in sorted((b or {}).get("arrivals", {}).items())]
                            if counts else [],
                            "state": (b or {}).get("state")})
            out["stations"].append({"name": name, "minutes": row})
        # newest heard first: placing at heard_at can leave consumption order slightly out of time order (🌿)
        out["river"] = [{"at_ms": at, "station": name, "stream": stream}
                        for at, name, stream in sorted(self.river, key=lambda r: -r[0])
                        if at > now_ms - WINDOW_MIN * MINUTE_MS and grant.at_least(_shown(grants, name), "river")]
        return out


    def project_drum(self, now_ms: int, live: Optional[_StampedView] = None, grants: Optional[dict] = None) -> dict:
        """The whole ``/api/drum`` answer: a day of 10 s buckets, as indices from ``start_ms`` (the first of 96 rows of
        15 minutes; the last row holds now).  Sparse: ``observed`` as [from, to) index ranges, each station's beacon
        buckets, and its arrivals as [bucket, stream index, count].  Closed words, host-named stations, manifest-bounded
        stream names, counts and times only.  ``live`` is the connection ``/api/shape`` calls live now, or None."""
        self._prune(now_ms)
        start = (now_ms // DRUM_ROW_MS - DRUM_ROWS + 1) * DRUM_ROW_MS
        base = start // DRUM_BUCKET_MS

        def index(b: int) -> Optional[int]:
            i = b - base
            return i if 0 <= i < DRUM_BUCKETS else None

        observed = set(self.drum_observed)
        if (live is not None and self._last_health is not None and self._last_health[0] is live
                and 0 <= now_ms - self._last_health[1] <= STALE_MS):
            # the open interval since the last record, only while the connection that heard it is the one /api/shape
            # calls live: an EOF or a rejoin ends it at once (🌫 on #138).  Served, not stored, so a connection that
            # dies here never keeps the claim; the history up to its last record stays
            observed.update(range(self._last_health[1] // DRUM_BUCKET_MS, now_ms // DRUM_BUCKET_MS + 1))
        ranges: list = []
        for i in sorted(i for i in map(index, observed) if i is not None):
            if ranges and ranges[-1][1] == i:
                ranges[-1][1] = i + 1
            else:
                ranges.append([i, i + 1])
        shown = [(name, g) for name in self.allowed if (g := _shown(grants, name)) is not None]
        counted = [name for name, g in shown if grant.at_least(g, "counts")]
        streams = sorted({s for name in counted for per in self.drum_arrivals[name].values() for s in per})
        sid = {s: n for n, s in enumerate(streams)}
        stations = []
        for name, g in shown:
            arrivals = [[i, sid[s], n] for b, per in sorted(self.drum_arrivals[name].items())
                        if (i := index(b)) is not None for s, n in sorted(per.items())] if name in counted else []
            beacons = sorted(i for i in map(index, self.drum_beacons[name]) if i is not None) \
                if grant.at_least(g, "beacon") else []
            stations.append({"name": name, "beacons": beacons, "arrivals": arrivals})
        return {"now_ms": now_ms, "since_ms": self.started_at, "synthetic": False, "start_ms": start,
                "bucket_ms": DRUM_BUCKET_MS, "row_ms": DRUM_ROW_MS, "rows": DRUM_ROWS, "observed": ranges,
                "streams": streams, "stations": stations}


_ALL = {"scope": "river", "withheld": False, "generation": (0, 0)}


def _shown(grants: Optional[dict], name: str) -> Optional[dict]:
    """The grant ``name`` is shown under: every host-named station shows in full without a display (``grants`` is
    None); with one, only a verified grant shows it."""
    return _ALL if grants is None else grants.get(name)


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


def _demo_flow(now_ms: int) -> dict:
    """Invented, and marked so, like ``_demo``."""
    last = now_ms // MINUTE_MS
    minutes = list(range(last - WINDOW_MIN + 1, last + 1))
    def row(every: int, stream: str) -> list:
        return [{"beacon": True, "arrivals": [{"stream": stream, "n": 1 + m % 3}] if every and m % every == 0 else [],
                 "state": "EQUIPPED_SPEAKING"} for m in minutes]
    return {"now_ms": now_ms, "since_ms": now_ms - WINDOW_MIN * MINUTE_MS, "minute_ms": MINUTE_MS, "synthetic": True,
            "minutes": [{"t": m * MINUTE_MS, "observed": True} for m in minutes],
            "stations": [{"name": "demo-melchior", "minutes": row(4, "chatter")},
                         {"name": "demo-balthasar", "minutes": row(9, "facts")},
                         {"name": "demo-casper", "minutes": row(0, "chatter")}],
            "river": [{"at_ms": now_ms - i * 37_000, "station": "demo-melchior", "stream": "chatter"} for i in range(8)]}


def _demo_drum(now_ms: int) -> dict:
    """Invented, and marked so: a day with a rhythm, a quiet night, an unobserved gap and a burst."""
    start = (now_ms // DRUM_ROW_MS - DRUM_ROWS + 1) * DRUM_ROW_MS
    upto = (now_ms - start) // DRUM_BUCKET_MS + 1
    gap = (3000, 3400)   # an unobserved stretch
    observed = [[0, gap[0]], [gap[1], upto]]
    def station(period: int, burst: int, stream: int) -> dict:
        beacons = [i for i in range(upto) if not gap[0] <= i < gap[1]]
        arrivals = [[i, stream, 1 + (i // period) % 3] for i in range(0, upto, period) if not gap[0] <= i < gap[1]]
        arrivals += [[i, stream, 4] for i in range(burst, min(burst + 30, upto), 3)]
        return {"beacons": beacons, "arrivals": sorted(arrivals)}
    return {"now_ms": now_ms, "since_ms": start, "synthetic": True, "start_ms": start, "bucket_ms": DRUM_BUCKET_MS,
            "row_ms": DRUM_ROW_MS, "rows": DRUM_ROWS, "observed": observed, "streams": ["chatter", "facts"],
            "stations": [{"name": "demo-melchior", **station(37, 5200, 0)},
                         {"name": "demo-balthasar", **station(181, 7000, 1)},
                         {"name": "demo-casper", "beacons": [], "arrivals": []}]}


async def follow(socket_path: str, view: ShapeView, stop: asyncio.Event, timeout_s: float = 5.0,
                 sleep: Callable = asyncio.sleep) -> None:
    """Hold one ``tap --follow`` connection open, starting a fresh view after every end (a daemon restart),
    failure or stale connection (open, but no health for ``STALE_MS``), with backoff. What tap would print is
    discarded: only the view is read, through ``project``."""
    attempt = 0
    while not stop.is_set():
        tv = _StampedView([("*", "*")], view.clock, view.flow)
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
                    clock: Callable[[], int] = _now_ms, display: Optional[str] = None) -> None:
    view = ShapeView(stations, demo_fixture=demo_fixture, clock=clock, display=display)
    http = TunerHttp(view, http_host, http_port, clock=clock, api_path="/api/shape", static=False,
                     routes={"/api/flow": view.flow_project, "/api/drum": view.drum_project})
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
