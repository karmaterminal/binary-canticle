"""Reconnect storm (design §2.8 step one, workorder item 4): kill and restart the host daemon and the
frond-ear ears under load, and see whether catch-up and the reports of loss are honest.

Load: a regulator-ignoring producer at 30 items/s on one stream (under the daemon's ceiling, so the
only loss is the one the restarts cause), allowlisted and tuned with `immediate` delivery (the live
seat's settings), plus the real quiet station singing every 10 s. Four ears, each a frond-ear daemon
with a fake session, plus the probe: every daemon restart is five bindings reconnecting at once,
each asking for a join snapshot.

Timeline (seconds after the producers start):
  30   SIGKILL the host daemon            33  restart it (same state dir)
  70   SIGTERM the host daemon (a `bye`)   72  restart it
  110  SIGKILL frond-ear ear0              113 restart it (same database); its shim reconnects itself
  150..166  storm: SIGKILL the host daemon every 4 s, restart 1 s after each kill (5 kills)
  200  SIGKILL the host daemon and every frond-ear at once; restart all 3 s later
  run ends at 260 s, then an 8 s drain
"""

from __future__ import annotations

import json
import signal
import sys
from pathlib import Path

from cells import run_cell
from mlib import machine


def kill_daemon(lab):
    lab.stop("canticle-daemon", sig=signal.SIGKILL)


def term_daemon(lab):
    lab.stop("canticle-daemon", sig=signal.SIGTERM)


def restart_daemon(lab):
    lab.start_daemon(health_s=1.0)


def kill_ear0(lab):
    lab.stop("frond-ear-ear0", sig=signal.SIGKILL)


def restart_ear0(lab):
    lab.start_frond_ear("ear0", lab.dir / "frond-ear-ear0.json")


def kill_all(lab):
    lab.stop("canticle-daemon", sig=signal.SIGKILL)
    for e in range(4):
        lab.stop(f"frond-ear-ear{e}", sig=signal.SIGKILL)


def restart_all(lab):
    lab.start_daemon(health_s=1.0)
    for e in range(4):
        lab.start_frond_ear(f"ear{e}", lab.dir / f"frond-ear-ear{e}.json")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "machine.json").write_text(json.dumps(machine(), indent=1))
    actions = [(30, kill_daemon), (33, restart_daemon), (70, term_daemon), (72, restart_daemon),
               (110, kill_ear0), (113, restart_ear0)]
    for k in range(5):
        actions += [(150 + 4 * k, kill_daemon), (151 + 4 * k, restart_daemon)]
    actions += [(200, kill_all), (203, restart_all)]
    p = {"name": "R1-reconnect-storm", "producers": 1, "mode": "valid", "rate": 30, "payload": "64",
         "streams": 1, "ears": 4, "ear_tune": "stream0", "prod_wake": True, "quiet_interval": 10,
         "duration": 260, "sample_every": 1, "status_every": 1}
    r = run_cell(p, out / p["name"], actions=actions)
    (out / p["name"] / "actions.json").write_text(json.dumps([[t, f.__name__] for t, f in actions]))
    print(json.dumps({k: r.get(k) for k in ("offered", "probe_verified_frames", "pushes", "quiet", "tap")},
                     default=str)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
