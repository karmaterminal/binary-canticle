"""Percentile summaries, reported exactly (no rounding beyond 0.1 ms).

``summary()`` is for values that were all observed. When some durations are
right-censored (the event had not happened when observation stopped), use
``km()``: a censoring time is a lower bound, never a latency.
"""

from __future__ import annotations

import json
import os
import platform
import time
from typing import Iterable, Optional

import numpy as np

KM_QUANTILES = (50, 90, 95, 99, 99.9)


def summary(values: Iterable[float], unit: str = "ms") -> dict:
    """n, mean, median, p90, p95, p99, p99.9 and max; ``None`` fields when empty."""
    a = np.asarray(list(values), dtype=float)
    if a.size == 0:
        return {"n": 0, "unit": unit}
    q = np.percentile(a, [50, 90, 95, 99, 99.9])
    return {"n": int(a.size), "unit": unit, "mean": _r(a.mean()), "median": _r(q[0]), "p90": _r(q[1]),
            "p95": _r(q[2]), "p99": _r(q[3]), "p99.9": _r(q[4]), "max": _r(a.max()), "min": _r(a.min())}


def km_curve(durations: Iterable[float], observed: Iterable[bool]) -> tuple[np.ndarray, np.ndarray]:
    """Kaplan–Meier survival S(t) for right-censored data, at each distinct time.

    ``observed[i]`` is False when ``durations[i]`` is a censoring time. At equal
    times, events come before censorings: a unit censored at t is still at risk
    at t. Returns (distinct times, S just after each).
    """
    t = np.asarray(list(durations), dtype=float)
    e = np.asarray(list(observed), dtype=bool)
    if t.size == 0:
        return t, t
    ut, inv = np.unique(t, return_inverse=True)
    at_time = np.bincount(inv, minlength=ut.size)
    events = np.bincount(inv, weights=e.astype(float), minlength=ut.size)
    at_risk = t.size - np.concatenate(([0], np.cumsum(at_time)[:-1]))
    return ut, np.cumprod(1.0 - events / at_risk)


def km(durations: Iterable[float], observed: Iterable[bool], unit: str = "ms", qs=KM_QUANTILES) -> dict:
    """Kaplan–Meier quantiles of a right-censored duration.

    The q-quantile is the smallest time t with S(t) <= 1 - q. Where S never
    falls that far (more than 1 - q of the samples are censored beyond the last
    event), the quantile is ``None`` and ``censored_beyond_<unit>`` gives the
    largest time observed, event or censoring (where the estimate ends): every
    such quantile lies beyond it.
    """
    t = np.asarray(list(durations), dtype=float)
    e = np.asarray(list(observed), dtype=bool)
    out: dict = {"n": int(t.size), "events": int(e.sum()), "censored": int(t.size - e.sum()), "unit": unit,
                 "method": "kaplan-meier"}
    if t.size == 0:
        return out
    ut, surv = km_curve(t, e)
    for q in qs:
        hit = np.nonzero(surv <= 1.0 - q / 100 + 1e-12)[0]
        out[_qname(q)] = _r(ut[hit[0]]) if hit.size else None
    if any(out[_qname(q)] is None for q in qs):
        out[f"censored_beyond_{unit}"] = _r(t.max())
    out["max_event"] = _r(t[e].max()) if e.any() else None
    return out


def _qname(q: float) -> str:
    return "median" if q == 50 else f"p{q:g}"


def km_selfcheck() -> None:
    """Check ``km`` against a hand-computed example and, without censoring, against numpy."""
    # 1 event, 2 event, 2 censored, 3 censored, 4 event, 5 censored (6 units):
    #   t=1: 6 at risk, 1 event -> S = 5/6
    #   t=2: 5 at risk (the unit censored at 2 still counts), 1 event -> S = 5/6 * 4/5 = 4/6
    #   t=4: 2 at risk, 1 event -> S = 4/6 * 1/2 = 2/6
    # Censorings before events at t=2 would give S(2) = 5/6 * 3/4 = 0.625 instead.
    d, o = [1, 2, 2, 3, 4, 5], [True, True, False, False, True, False]
    ut, s = km_curve(d, o)
    assert np.allclose(ut, [1, 2, 3, 4, 5]) and np.allclose(s, [5 / 6, 4 / 6, 4 / 6, 2 / 6, 2 / 6]), s
    r = km(d, o, qs=(10, 20, 35, 50, 90))
    assert (r["p10"], r["p20"], r["p35"], r["median"], r["p90"]) == (1, 2, 4, 4, None), r
    assert r["censored_beyond_ms"] == 5 and (r["events"], r["censored"]) == (3, 3), r
    x = np.random.default_rng(1).exponential(100.0, 1001)
    r = km(x, np.ones(x.size, bool))
    ref = np.percentile(x, KM_QUANTILES, method="inverted_cdf")
    assert [r[_qname(q)] for q in KM_QUANTILES] == [_r(v) for v in ref], (r, ref)
    assert "censored_beyond_ms" not in r and r["censored"] == 0


def weighted_quantiles(values: np.ndarray, weights: np.ndarray, qs=(50, 95, 99, 99.9)) -> dict:
    """Quantiles of a piecewise-constant signal: ``values[i]`` held for ``weights[i]`` seconds."""
    if values.size == 0 or weights.sum() <= 0:
        return {}
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return {f"p{q:g}": _r(float(v[min(np.searchsorted(cum, q / 100), v.size - 1)])) for q in qs}


def _r(x: float) -> float:
    return round(float(x), 1)


def env() -> dict:
    """Testbed facts recorded next to every result."""
    def read(p: str) -> Optional[str]:
        try:
            with open(p) as f:
                return f.read().strip()
        except OSError:
            return None
    return {"kernel": platform.release(), "cpus": os.cpu_count(), "python": platform.python_version(),
            "hz": 250, "tcp_retries2": read("/proc/sys/net/ipv4/tcp_retries2"),
            "tcp_congestion_control_ns": read("/proc/sys/net/ipv4/tcp_congestion_control"),
            "tcp_rmem": read("/proc/sys/net/ipv4/tcp_rmem"), "tcp_wmem": read("/proc/sys/net/ipv4/tcp_wmem"),
            "rmem_max": read("/proc/sys/net/core/rmem_max"), "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1, sort_keys=False)
        f.write("\n")


if __name__ == "__main__":
    km_selfcheck()
    print("km self-check ok")
