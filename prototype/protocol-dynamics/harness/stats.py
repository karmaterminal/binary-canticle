"""Percentile summaries, reported exactly (no rounding beyond 0.1 ms)."""

from __future__ import annotations

import json
import os
import platform
import time
from typing import Iterable, Optional

import numpy as np


def summary(values: Iterable[float], unit: str = "ms") -> dict:
    """n, mean, median, p90, p95, p99, p99.9 and max; ``None`` fields when empty."""
    a = np.asarray(list(values), dtype=float)
    if a.size == 0:
        return {"n": 0, "unit": unit}
    q = np.percentile(a, [50, 90, 95, 99, 99.9])
    return {"n": int(a.size), "unit": unit, "mean": _r(a.mean()), "median": _r(q[0]), "p90": _r(q[1]),
            "p95": _r(q[2]), "p99": _r(q[3]), "p99.9": _r(q[4]), "max": _r(a.max()), "min": _r(a.min())}


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
