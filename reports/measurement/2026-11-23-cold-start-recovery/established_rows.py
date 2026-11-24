"""Gate 1, established-station protection: #171's 57/57 flood rows, scaled down, several runs of any tree, on the classes of
``test_fair_admission`` (its R1-R4, and pass 2's R3c), so every tree is measured by the same code. Measured, never asserted.

Usage: established_rows.py <out.json> <name=tree:runs,...> <row,...|all>       (nice -n 19 ionice -c3, nothing beside it)
A run passes as the tests do: 57 of 57 during the flood, p50 at most 250 ms, none later than 4.5 s, the kernel's drops reported."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[2] / "prototype" / "canticle-station" / "tests"
ROWS = ("R1-valid-other-key", "R2-same-station", "R3-forged-claiming-quiet", "R3c-forged-churned-sources",
        "R4-replay-own-frames")


def one(tree: str, row: str) -> dict:
    sys.path[:0] = [tree, str(TESTS)]
    import test_fair_admission as F
    F.ROOT = Path(tree)

    class Case(F.FairAdmissionCase):
        def runTest(self):
            pass

    c = Case()
    c.setUp()
    try:
        c.daemon()
        seconds = F.QUIET_ITEMS * F.QUIET_INTERVAL_S + F.TAIL_S
        key = lambda name: os.path.join(c.dir, f"{name}.key")
        forged = ["forged", seconds, "--kid", c.kid("quiet"), "--stream", "quiet", "--rate"]
        q = None
        if row.startswith("R2"):
            floods = [c.flood("station", seconds, "--key", key("quiet"), "--quiet-items", F.QUIET_ITEMS, "--quiet-interval",
                              F.QUIET_INTERVAL_S)]
        else:
            caps = []
            if row.startswith("R4"):
                caps = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
                for s in caps:
                    s.bind(("127.0.0.1", 0))
                    c.addCleanup(s.close)
            q = c.quiet(capture=[s.getsockname() for s in caps] or None)
            c.settle(q)
            if row.startswith("R4"):
                q.warm.extend(f"warm {n}" for n in range(4))
                time.sleep(4.5)
                floods = [c.flood("replay", seconds, "--rate", F.FLOOD_RATE / 2, "--capture", s.fileno(), *extra,
                                  fds=(s.fileno(), *fds)) for s, extra, fds in
                          ((caps[0], (), ()), (caps[1], ("--fd", q.sock.fileno()), (q.sock.fileno(),)))]
            elif row.startswith("R1"):
                floods = [c.flood("valid", seconds, "--key", key("other"), "--epoch", 7 + i) for i in range(2)]
            elif row.startswith("R3c"):
                floods = [c.flood(*forged, F.FLOOD_RATE / 2, "--churn", 1, *h) for h in ((), ("--hosts", 60_000))]
            else:
                floods = [c.flood(*forged, F.FLOOD_RATE)]
            q.singing.set()
        done = [c.totals(f) for f in floods]
        end = time.monotonic()
        sung = q.sung if q is not None else {
            f"canticle:{c.kid('quiet')}:7:{F.stream_id('quiet'):08x}:{x['seq']}": x["t"] for x in done[0][0]}
        time.sleep(0.3)
        h, lost = c.tap.next_health(), F.kernel_drops(c.port)
        lat = [1000 * (c.tap.first[i] - t) for i, t in sung.items() if c.tap.first.get(i, end + 1) <= end]
        r = {"sung": len(sung), "during_the_flood": len(lat),
             "latency_ms": {k: round(F.percentile(lat, v), 1) for k, v in
                            (("p50", 50), ("p90", 90), ("p99", 99), ("max", 100))} if lat else None,
             "offered_per_s": round(sum(t["sent"] / t["elapsed"] for _, t in done)), "kernel_drops": lost,
             "reported_socket_dropped": h["records"].get("socket_dropped"), "receive": h.get("receive"),
             "unverified": {k: v for k, v in h["counters"]["unverified"].items() if v},
             "health_reasons_seen": sorted({x for g in c.tap.healths() for x in g["reasons"]})}
        r["pass"] = (len(lat) == len(sung) == F.QUIET_ITEMS and r["latency_ms"]["p50"] <= 1000 * F.LATENCY_P50_S
                     and r["latency_ms"]["max"] <= 1000 * F.LATENCY_MAX_S)
        r["told"] = lost == (r["reported_socket_dropped"] or 0)
        return r
    finally:
        c.doCleanups()


def main() -> None:
    out, rows = Path(sys.argv[1]), ROWS if sys.argv[3] == "all" else sys.argv[3].split(",")
    trees = []
    for t in sys.argv[2].split(","):
        name, spec = t.split("=")
        tree, runs = spec.rsplit(":", 1)
        trees.append((name, tree, int(runs)))
    got = json.loads(out.read_text()) if out.exists() else []
    done = {(r["tree"], r["row"], r["run"]) for r in got}
    for run in range(max(runs for _, _, runs in trees)):
        for row in rows:
            for name, tree, runs in trees:
                if run >= runs or (name, row, run) in done:
                    continue
                p = subprocess.run([sys.executable, __file__, "--one", tree, row], stdout=subprocess.PIPE, text=True)
                if p.returncode:
                    print(name, row, run, "FAILED TO RUN", p.returncode, flush=True)
                    continue
                r = {"tree": name, "row": row, "run": run, **json.loads(p.stdout)}
                got.append(r)
                out.write_text("[\n" + ",\n".join(json.dumps(x) for x in got) + "\n]\n")
                print(time.strftime("%H:%M:%SZ", time.gmtime()), name, row, run, r["during_the_flood"], "of", r["sung"], r["latency_ms"],
                      "PASS" if r["pass"] and r["told"] else "FAIL", "offered", r["offered_per_s"], "drops", r["kernel_drops"],
                      r["reported_socket_dropped"], (r["receive"] or {}).get("refused"), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3])))
    else:
        main()
