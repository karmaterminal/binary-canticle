"""Row J of PLAN.md: four established stations, each singing 57 items, in a flood that is half junk (no frames) and half forgeries: of the 12
other keys (junk-...), or of all 16, theirs too (junkall-...). Measured, never asserted.

Usage: junk_rows.py <out.json> <name=tree:runs,...> <junk|junkall>-<ports>-<rate>,...        (nice -n 19 ionice -c3, nothing beside it)
A run passes as #171's rows do, for each of the four: 57 of 57 during the flood, p50 at most 250 ms, none later than 4.5 s, the kernel's
drops reported. A run whose flood fell under 95 % of its rate in its lowest whole second, or on another cryptography, is no run."""

import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[2] / "prototype" / "canticle-station" / "tests"
STATIONS, ESTABLISHED, PER_PRODUCER = 16, ("quiet", "x0", "x1", "x2"), 50_000
LOCKED = "50.0.1"


def one(tree: str, row: str) -> dict:
    sys.path[:0] = [tree, str(TESTS)]
    import test_fair_admission as F
    from canticle import wire
    F.ROOT = Path(tree)

    class Case(F.FairAdmissionCase):
        def runTest(self):
            pass

        def setUp(self):
            super().setUp()
            m = json.loads(Path(self.manifest).read_text())
            for n in range(STATIONS - 2):
                sk = self.keys[f"x{n}"] = F.Ed25519PrivateKey.generate()
                m["stations"] += F.Manifest([F.StationEntry(f"x{n}", wire.public_key_bytes(sk), frozenset({1, 3}), ("quiet", "flood"))]
                                            ).to_json()["stations"]
            Path(self.manifest).write_text(json.dumps(m))

    kind, ports, rate = row.split("-")
    ports, rate = int(ports), int(rate)
    c = Case()
    c.setUp()
    try:
        c.daemon()
        qs = {name: c.quiet(name) for name in ESTABLISHED}
        deadline = time.monotonic() + 10
        while {r["key_id"] for _, r in list(c.tap.recs) if r["type"] == "presence"} < {c.kid(n) for n in ESTABLISHED}:
            if time.monotonic() > deadline:
                raise RuntimeError("the daemon never heard all of them")
            time.sleep(0.02)
        n = -(-rate // PER_PRODUCER)
        kids = ",".join(c.kid(k) for k in c.keys if kind == "junkall" or k not in ESTABLISHED)
        procs = []
        for i in range(n):
            p = subprocess.Popen(
                [sys.executable, str(HERE / "forged_flood.py"), "--tests", str(TESTS), "--port", str(c.port), "--kid", kids, "--stream", "quiet",
                 "--rate", str(rate / n), "--ports", str(ports // n + (i < ports % n)), "--index", str(i), "--junk", "--duration",
                 str(F.QUIET_ITEMS * F.QUIET_INTERVAL_S + F.TAIL_S)], env=c.env(), stdout=subprocess.PIPE)
            c.addCleanup(c._reap, p)
            procs.append(p)
        for p in procs:
            json.loads(p.stdout.readline())
        for q in qs.values():
            q.singing.set()
        totals = [json.loads(p.stdout.read()) for p in procs]
        end = min(t["t1"] for t in totals)
        time.sleep(0.3)
        h, lost = c.tap.next_health(), F.kernel_drops(c.port)
        stations = {}
        for name, q in qs.items():
            lat = [1000 * (c.tap.first[i] - t) for i, t in q.sung.items() if c.tap.first.get(i, end + 1) <= end]
            stations[name] = {"sung": len(q.sung), "during_the_flood": len(lat), "latency_ms": {
                k: round(F.percentile(lat, v), 1) for k, v in (("p50", 50), ("p90", 90), ("p99", 99), ("max", 100))} if lat else None}
        lows = [sum(t["per_s"][i] for t in totals) for i in range(min(len(t["per_s"]) for t in totals))]
        ok = all(s["during_the_flood"] == s["sung"] == F.QUIET_ITEMS and s["latency_ms"]["p50"] <= 1000 * F.LATENCY_P50_S
                 and s["latency_ms"]["max"] <= 1000 * F.LATENCY_MAX_S for s in stations.values())
        return {"stations": stations, "offered_per_s": round(sum(t["sent"] / (t["t1"] - t["t0"]) for t in totals)), "lowest_second": min(lows),
                "kernel_drops": lost, "reported_socket_dropped": h["records"].get("socket_dropped"), "receive": h.get("receive"),
                "pass": ok, "told": lost == (h["records"].get("socket_dropped") or 0), "driven": min(lows) >= 0.95 * rate}
    finally:
        c.doCleanups()


def main() -> None:
    if version("cryptography") != LOCKED:
        sys.exit(f"cryptography {version('cryptography')}, not the locked {LOCKED}: not a run of these rows")
    out, rows = Path(sys.argv[1]), sys.argv[3].split(",")
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
                load = os.getloadavg()[0]
                p = subprocess.run([sys.executable, __file__, "--one", tree, row], stdout=subprocess.PIPE, text=True)
                if p.returncode:
                    print(name, row, run, "FAILED TO RUN", p.returncode, flush=True)
                    continue
                r = {"tree": name, "row": row, "run": run, "load_before": load, "python": platform.python_version(),
                     "cryptography": version("cryptography"), **json.loads(p.stdout)}
                got.append(r)
                out.write_text("[\n" + ",\n".join(json.dumps(x) for x in got) + "\n]\n")
                print(time.strftime("%H:%M:%SZ", time.gmtime()), name, row, run, "PASS" if r["pass"] and r["told"] and r["driven"] else "FAIL",
                      {k: (s["during_the_flood"], s["latency_ms"]) for k, s in r["stations"].items()}, "offered", r["offered_per_s"], flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3])))
    else:
        main()
