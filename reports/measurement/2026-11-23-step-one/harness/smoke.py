"""Smoke test: one throwaway daemon, one real quiet station, one frond-ear ear and its fake session,
and the probe tap. Sings 3 items 10 s apart and checks that they are pushed. Prints a summary."""

from __future__ import annotations

import json
import sys
import time

from mlib import FROND_EAR, NODE_SHIM, PYTHON, HERE, Lab, frond_ear_status, key_id_hex, udp_socket_drops


def main() -> int:
    lab = Lab("smoke")
    try:
        quiet = lab.add_station("quiet", ["quiet"])
        lab.add_station("flood", ["flood"])
        lab.write_manifest()
        lab.start_daemon()
        lab.start_station("quiet", ["quiet:chatter"])
        cfg = lab.frond_ear_config("ear0", ["quiet:quiet"], [key_id_hex(quiet)],
                                   {"mode": "off", "stations": {"quiet": "immediate"}})
        lab.start_frond_ear("ear0", cfg)
        d = 40
        lab.spawn("tap", [PYTHON, HERE / "tap.py", "--socket", lab.daemon_sock, "--out", lab.logs / "tap",
                          "--duration", d])
        lab.spawn("session0", [PYTHON, HERE / "fake_session.py", "--frond-ear", FROND_EAR, "--node", NODE_SHIM,
                               "--socket", lab.frond_ear_sock("ear0"), "--ear", "ear0", "--out", lab.logs / "session0",
                               "--duration", d])
        time.sleep(4)
        lab.spawn("singer", [PYTHON, HERE / "singer.py", "--control", lab.run / "station-quiet.sock", "--stream", "quiet",
                             "--key-id", key_id_hex(quiet), "--interval", 10, "--duration", 25, "--out", lab.logs / "quiet"])
        time.sleep(d + 2)
        st = frond_ear_status(lab.frond_ear_sock("ear0"))
        print(json.dumps({"drops": udp_socket_drops(lab.port),
                          "canticle": st and st.get("canticle"),
                          "ear": st and st.get("ears", {}).get("ear0", {}).get("canticleDelivery")}, indent=1)[:4000])
        for f in ["tap.json", "session0.json", "quiet.json"]:
            p = lab.logs / f
            print(f, p.read_text()[:1500] if p.exists() else "missing")
        print("lab", lab.dir)
    finally:
        lab.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
