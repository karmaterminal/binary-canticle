"""Poll the tuner gateway's API every 5 s for both channels; one compact JSON line per ring read.

    python snapshots.py http://127.0.0.1:8765 <seconds>
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


subs = {}
end = time.time() + SECONDS
while time.time() < end:
    try:
        stations = call("/api/stations")["stations"]
        for st in stations:
            for sm in st["streams"]:
                if sm["tunable"] and sm["name"] not in subs:
                    subs[sm["name"]] = call("/api/tune", {"station": st["key_id"], "stream": sm["stream_id"]})["sub"]
        for name, sub in list(subs.items()):
            try:
                r = call(f"/api/ring?sub={sub}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    del subs[name]   # lapsed: tune again next round
                continue
            print(json.dumps({"t_ms": r["now_ms"], "stream": name, "head": r["head_seq"],
                              "live_advertised": r["live_advertised"],
                              "items": [[i["seq"], i["issued_at"], i["local_expiry_ms"], i["remaining_ms"], i["copies"]]
                                        for i in r["items"]],
                              "tombstones": [[t["seq"], t["reason"]] for t in r["tombstones"]],
                              "unheard": r["unheard_seq"]}), flush=True)
    except (urllib.error.URLError, OSError, KeyError) as e:
        print(json.dumps({"t_ms": int(time.time() * 1000), "error": str(e)}), flush=True)
    time.sleep(5)
