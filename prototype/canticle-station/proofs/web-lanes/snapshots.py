"""Poll the synthetic-only human dashboard every 5 s.

    python snapshots.py http://127.0.0.1:8765 <seconds>

This lane intentionally reads only /api/stations. It never calls tune, ring or leave, and records
only station-card counts and explicit synthetic markers, never listener observations.
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE, SECONDS = sys.argv[1], float(sys.argv[2])


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


end = time.time() + SECONDS
while time.time() < end:
    try:
        response = call("/api/stations")
        print(json.dumps({"t_ms": response["now_ms"],
                          "synthetic": response["synthetic"],
                          "station_count": len(response["stations"]),
                          "all_synthetic": all(st.get("synthetic") is True for st in response["stations"])}),
              flush=True)
    except (urllib.error.URLError, OSError, KeyError) as e:
        print(json.dumps({"t_ms": int(time.time() * 1000), "error": str(e)}), flush=True)
    time.sleep(5)
