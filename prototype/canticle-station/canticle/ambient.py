"""A background ambient emitter: paced, short-TTL items from an elected fixture (issue #58, RFC-0001 §15.8).

The emitter is a client of a station's control socket (§11.1). It never signs, never listens and never
learns who hears: the station keeps the carousel (§7) and tracks nobody (I-1). At each tick it either
sings one line of its fixture or takes a breath and sends nothing. It makes no model calls; the source
is a fixture file the operator chose. A session-log-derived source would be a separate, opt-in
boundary under §15.4 content policy, and is not implemented here.
"""

from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

MAX_DURATION_S = 3_600          # a run is bounded to one hour at most
MIN_GAP_FLOOR_S = 1.0           # never more than one tick a second
ALLOWED_CLASSES = ("ambient", "chatter")
MAX_FAILURES = 3                # consecutive socket failures before the emitter gives up


class FixtureError(ValueError):
    pass


def load_fixture(path, max_bytes: int) -> tuple[str, ...]:
    """One item per line; blank lines and lines starting with '#' are skipped."""
    lines = []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if len(line.encode()) > max_bytes:
            raise FixtureError(f"{path}:{n}: {len(line.encode())} bytes > --max-bytes {max_bytes}")
        lines.append(line)
    if not lines:
        raise FixtureError(f"{path}: no items")
    return tuple(lines)


@dataclass(frozen=True)
class AmbientConfig:
    stream: str
    lines: tuple
    cls: str = "ambient"
    min_gap_s: float = 2.0
    max_gap_s: float = 10.0
    ttl_s: float = 60.0
    breath: float = 0.2          # probability that a tick sends nothing
    max_bytes: int = 256
    max_per_minute: int = 20
    duration_s: float = 600.0

    def __post_init__(self):
        if self.cls not in ALLOWED_CLASSES:
            raise ValueError(f"an ambient emitter sings only {ALLOWED_CLASSES}, not {self.cls!r}")
        if not (MIN_GAP_FLOOR_S <= self.min_gap_s <= self.max_gap_s):
            raise ValueError(f"need {MIN_GAP_FLOOR_S} <= min_gap_s <= max_gap_s")
        if not (0 <= self.breath < 1):
            raise ValueError("breath must be in [0, 1)")
        if not (0 < self.duration_s <= MAX_DURATION_S):
            raise ValueError(f"duration_s must be in (0, {MAX_DURATION_S}]")
        if self.ttl_s <= 0 or self.max_per_minute < 1 or self.max_bytes < 1:
            raise ValueError("ttl_s, max_per_minute and max_bytes must be positive")
        if not self.lines:
            raise ValueError("no fixture lines")
        for line in self.lines:
            if len(line.encode()) > self.max_bytes:
                raise ValueError(f"fixture line of {len(line.encode())} bytes exceeds max_bytes {self.max_bytes}")


class Ambient:
    """The schedule, with the clock and randomness injected. ``step`` is called once per tick."""

    def __init__(self, cfg: AmbientConfig, rng: random.Random, start_s: float):
        self.cfg, self.rng = cfg, rng
        self.end_s = start_s + cfg.duration_s
        self.next_at = start_s
        self.window: deque = deque()   # times of sings in the last 60 s

    def done(self, now_s: float) -> bool:
        return now_s >= self.end_s

    def step(self, now_s: float) -> dict:
        cfg = self.cfg
        self.next_at = now_s + self.rng.uniform(cfg.min_gap_s, cfg.max_gap_s)
        while self.window and self.window[0] <= now_s - 60:
            self.window.popleft()
        if self.rng.random() < cfg.breath:
            return {"event": "breath"}
        if len(self.window) >= cfg.max_per_minute:
            return {"event": "capped", "in_last_minute": len(self.window)}
        self.window.append(now_s)
        return {"event": "sing", "request": {"op": "sing", "stream": cfg.stream, "class": cfg.cls,
                                             "text": self.rng.choice(cfg.lines), "ttl": cfg.ttl_s}}


def run(cfg: AmbientConfig, send: Callable[[dict], dict], log: Callable[[dict], None], *,
        stop: Callable[[], bool] = lambda: False, rng: Optional[random.Random] = None,
        clock: Callable[[], float] = time.monotonic, wall_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
        sleep: Callable[[float], None] = time.sleep) -> dict:
    """Run until the duration ends, ``stop()`` is true, or the station stays unreachable.

    Items already on air are left alone: the station loops them until they expire naturally.
    """
    amb = Ambient(cfg, rng or random.Random(), clock())
    counts = {"sing": 0, "breath": 0, "capped": 0, "refused": 0}
    log({"event": "start", "t_ms": wall_ms(), "stream": cfg.stream, "class": cfg.cls, "ttl_s": cfg.ttl_s,
         "gap_s": [cfg.min_gap_s, cfg.max_gap_s], "breath": cfg.breath, "max_per_minute": cfg.max_per_minute,
         "max_bytes": cfg.max_bytes, "duration_s": cfg.duration_s, "fixture_lines": len(cfg.lines), "model_calls": 0})
    failures, reason = 0, "duration"
    while True:
        if stop():
            reason = "signal"
            break
        now = clock()
        if amb.done(now):
            break
        if now < amb.next_at:
            sleep(min(0.5, amb.next_at - now, max(0.0, amb.end_s - now)))
            continue
        rec = amb.step(now)
        req = rec.pop("request", None)
        rec["t_ms"] = wall_ms()
        if req is not None:
            try:
                resp = send(req)
                failures = 0
            except OSError as e:   # the station is gone or its socket is not there
                resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                failures += 1
            if resp.get("ok"):
                rec.update({k: resp[k] for k in ("seq", "size", "ttl_s", "loop_ms", "clamp") if k in resp})
                rec["text"] = req["text"]
            else:   # a refusal (budget, grant) is logged and the run goes on
                rec = {"event": "refused", "t_ms": rec["t_ms"], "error": resp.get("error")}
        counts[rec["event"]] += 1
        log(rec)
        if failures >= MAX_FAILURES:
            reason = "station-unreachable"
            break
    summary = {"event": "stop", "t_ms": wall_ms(), "reason": reason, **counts, "model_calls": 0}
    log(summary)
    return summary
