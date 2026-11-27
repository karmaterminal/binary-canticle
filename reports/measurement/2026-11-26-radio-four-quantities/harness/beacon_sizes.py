"""Beacon frame sizes as the running codec encodes them: what the code permits, not what was observed.

The host daemon's records carry no beacon bytes (a beacon is counted in ``health``, never recorded), so the
report derives beacon bytes from these sizes. Run with the live venv's Python, which imports the canticle package
from the clone the daemon runs (``~/.venvs/canticle``, editable install). The signing key is generated in memory
and dropped at exit: nothing is written but ``--out``.

- ``typical[n]``: a beacon with ``n`` stream entries at the magnitudes a station on this fleet sends today (an epoch
  and wallclock of now, a bseq of about two weeks of 1 s beacons, a few items live per stream, the default budgets);
- ``idle[n]``: the same with nothing live (live 0, loop 0);
- ``max_entries_per_page``: how many entries at their CDDL maxima fit one 1 100-byte frame beside the fixed fields
  at their widest (station.py's ``_per_page``), and ``max_streams_per_station``: that times the 8 pages §8.4 allows.
"""

from __future__ import annotations

import argparse
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import wire
from canticle.station import DEFAULT_B_STATION, DEFAULT_B_STREAM, MAX_PAGES, PROFILE


def beacon(sk, entries, page=None, digest=None, widest=False) -> int:
    now = int(time.time() * 1000)
    b = wire.Beacon(epoch=1_794_676_610, bseq=wire.U64 if widest else 1_400_000, wallclock=wire.U64 if widest else now,
                    next_beacon_ms=wire.U32 if widest else 1_000, profile=PROFILE, streams=tuple(entries),
                    b_station=DEFAULT_B_STATION, page=page, catalog_digest=digest)
    return len(wire.encode_beacon(sk, b))


def entry(i: int, live: bool) -> wire.StreamEntry:
    return wire.StreamEntry(stream_id=0x9E3779B1 ^ i, head_seq=40 + i, trail_seq=38 + i if live else 41 + i,
                            live=3 if live else 0, loop_ms=4_000 if live else 0, loop_max_ms=8_000 if live else 0,
                            default_ttl_s=60, max_ttl_s=300, b_stream=DEFAULT_B_STREAM)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True)
    a = p.parse_args()
    sk = Ed25519PrivateKey.generate()
    biggest = wire.StreamEntry(*wire.StreamEntry.MAXIMA[:9])
    per_page = 0
    while True:
        try:   # sign_frame refuses a frame above MAX_FRAME, as the station's own paging relies on
            beacon(sk, [biggest] * (per_page + 1), page=(MAX_PAGES - 1, MAX_PAGES), digest=bytes(8), widest=True)
        except ValueError:
            break
        per_page += 1
    res = {
        "typical": {n: beacon(sk, [entry(i, True) for i in range(n)]) for n in range(0, 9)},
        "idle": {n: beacon(sk, [entry(i, False) for i in range(n)]) for n in range(0, 9)},
        "max_entries_per_page": per_page,
        "max_pages": MAX_PAGES,
        "max_streams_per_station": per_page * MAX_PAGES,
        "max_frame": wire.MAX_FRAME,
        "max_datagram": wire.MAX_DATAGRAM,
    }
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
