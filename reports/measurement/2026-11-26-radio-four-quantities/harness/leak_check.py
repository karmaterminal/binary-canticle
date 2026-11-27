"""Checks the published results for what must never be in them; prints counts only, never what it compared.

    python3 harness/leak_check.py results/    (exit 1 on any hit)

Compared against, on the seat that ran the window: every manifest station name and key id, the seat's frond-ear tune
patterns and stream names, the session ids and custody digests in frond-ear's store, the OpenClaw binding's session
keys, the daemon's LAN address, IPv4 addresses in general, long numeric ids (Discord snowflakes) and 64-hex digests
other than the OpenClaw extension's own file digests (which name public repository code).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def secrets_to_find() -> dict:
    found: dict = {"station": set(), "key_id": set(), "stream": set(), "session": set(), "digest": set()}
    for name, kid, streams, _cl, _sc in C.manifest_entries():
        found["station"].add(name)
        found["key_id"].add(kid)
        # Short names ("town", "wake") are ordinary words, and a stream named like a class ("chatter") is the class.
        found["stream"].update(s for s in streams if len(s) > 4 and s not in C.CLASSES)
    can = C.seat_canticle_config()
    for pats in (can.get("tune") or {}).values():
        found["stream"].update(x for x in (p.split(":", 1)[1] for p in pats) if len(x) > 4 and x not in C.CLASSES)
    con = sqlite3.connect(f"file:{C.FROND_EAR_DB}?mode=ro", uri=True)
    try:
        for sid, offer, echo, digest in con.execute(
                "SELECT session_id, offer_session, echo_session, digest FROM canticle_custody"):
            found["session"].update(x for x in (sid, offer, echo) if x)
            if digest:
                found["digest"].add(digest)
    finally:
        con.close()
    for b in os.listdir(C.OPENCLAW_CANTICLE):
        try:
            st = C.load_json(os.path.join(C.OPENCLAW_CANTICLE, b, "state.json"))
            found["session"].update(st.get("checkpoints") or {})
            found["session"].update(st.get("taint") or {})
        except (OSError, ValueError):
            pass
    return found


def main() -> int:
    res = sys.argv[1]
    texts = {}
    for f in sorted(os.listdir(res)):
        with open(os.path.join(res, f), encoding="utf-8") as fh:
            # The window's own host field names the host the report names; a station may share that name.
            texts[f] = fh.read().replace('"host": "%s"' % os.uname().nodename, '"host": ""')
    allowed_hex = set()
    cat = json.loads(texts.get("catalog.json", "{}"))
    allowed_hex.update(((cat.get("openclaw_binding") or {}).get("extension_digest") or {}).get("files", {}).values())
    allowed_hex.add(((cat.get("openclaw_binding") or {}).get("extension_digest") or {}).get("all"))
    hits: dict = {}
    for kind, values in secrets_to_find().items():
        n = sum(t.count(v) for t in texts.values() for v in values if v)
        hits[kind] = n
    hits["ipv4"] = sum(len(re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", t)) for t in texts.values())
    # Not a float's fraction, and not a key's monotonic nanoseconds ("tm").
    hits["snowflake"] = sum(len(re.findall(r'(?<![.\d])(?<!"tm":)\d{17,20}\b', t)) for t in texts.values())
    hits["hex64_unexpected"] = sum(1 for t in texts.values() for h in re.findall(r"\b[0-9a-f]{64}\b", t)
                                   if h not in allowed_hex)
    hits["hex16"] = sum(len(re.findall(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{16}\b", t)) for t in texts.values())
    print(json.dumps({"files": sorted(texts), "hits": hits}, sort_keys=True))
    return 1 if any(hits.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
