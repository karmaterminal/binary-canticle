"""What the running canticle code permits, computed with that code: no live data but the manifest's station count.

Run with the live venv's Python (``~/.venvs/canticle``), which imports the canticle package from the clone the daemon
runs. Station objects are built in memory with a throwaway key; nothing is sent, signed for the wire or written but
``--out``.

- ``max_streams_per_station``: the most streams ``Station`` accepts at its defaults. Every stream keeps at least
  500 bit/s of B_station's 16 000 (``station.py`` ``_fit_budget``), and the beacon catalog may span 8 pages (§8.4);
  the smaller bound refuses first;
- ``dedup_quota_per_key``: the listener's per-key share of its 100 000-entry dedup store with this manifest
  (``listener.py`` ``_quota``): how many items one key can have live at the daemon;
- the class TTL limits that bound how long an item can stay on air.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import daemon, ids, listener, records, station, wire


def accepts(sk, n: int) -> bool:
    try:
        station.Station(sk, [station.StreamConfig(name=f"s{i}", cls="chatter") for i in range(n)], epoch=1, now_ms=0)
        return True
    except ValueError:
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    a = p.parse_args()
    sk = Ed25519PrivateKey.generate()
    n = 1
    while accepts(sk, n + 1):
        n += 1
    with open(os.path.expanduser("~/.binary-canticle/fleet.json")) as fh:
        stations = len(json.load(fh)["stations"])
    cap = inspect.signature(listener.Listener.__init__).parameters["dedup_capacity"].default
    res = {
        "max_streams_per_station": n,
        "why": "stream budgets cannot fit B_station" if not accepts(sk, n + 1) else None,
        "b_station_bps": station.DEFAULT_B_STATION, "b_stream_bps": station.DEFAULT_B_STREAM,
        "stream_budget_floor_bps": 500, "beacon_max_pages": station.MAX_PAGES,
        "ring_depth_per_stream": station.DEFAULT_DEPTH,
        "dedup_capacity": cap, "manifest_stations": stations, "dedup_quota_per_key": cap // stations,
        "daemon_max_peers": daemon.MAX_PEERS, "daemon_queue_per_peer": daemon.QUEUE_MAX,
        "snapshot_entries_max": daemon.SNAPSHOT_ENTRIES_MAX, "health_interval_ms": records.HEALTH_INTERVAL_MS,
        "max_frame": wire.MAX_FRAME, "max_datagram": wire.MAX_DATAGRAM,
        "classes": {c.name: {"default_ttl_s": c.default_ttl_s, "max_ttl_s": c.max_ttl_s,
                             "loop_floor_ms": c.loop_floor_ms, "wake_eligible": c.wake_eligible}
                    for c in ids.CLASSES.values()},
    }
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
