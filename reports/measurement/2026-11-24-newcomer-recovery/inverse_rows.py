"""The inverse rows of PLAN.md (🌫's): who keeps a known place, and for how long. Measured, never asserted.

Usage: inverse_rows.py <out.json> <name=tree:runs,...> <I-a|I-a-lead|I-b,...>        (nice -n 19 ionice -c3, nothing beside it)

I-a: the station's first four beacons reach the daemon through four keyless relays only, one each, so all four known places are theirs. Then the
real station starts sending directly, from a new port, and after ten seconds from another one; all four relays go on forwarding each
beacon of its 5 ms behind it. The 15 other keys are forged from churned ports all along. Two seconds after each start, its own key is
forged from churned ports at 100 000/s for seven seconds, and it sings ten items, which no relay forwards.
I-a-lead: the same, the relays 10 ms ahead of it on every beacon (relay-first).
I-b: an incumbent becomes known, sings, and stops; its very socket replays its last beacon ten times a second until well past the horizon."""

import json
import os
import platform
import socket
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[2] / "prototype" / "canticle-station" / "tests"
PLACE_S, ITEM_S = 1.0, 2.0                      # PLAN.md: a known place, and each item
HORIZON_S, LATEST_S = 60.0, 62.0
ITEMS, STATIONS, HEALTH_S = 10, 16, 0.05
LOCKED = "50.0.1"


def one(tree: str, row: str) -> dict:
    sys.path[:0] = [tree, str(TESTS)]
    import test_fair_admission as F
    from canticle import runner, wire
    from canticle.ids import stream_id
    from canticle.station import Station, StreamConfig
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

        def forged(self, kids, rate, seconds, producers):
            out = []
            for i in range(producers):
                p = subprocess.Popen(
                    [sys.executable, str(HERE / "forged_flood.py"), "--tests", str(TESTS), "--port", str(self.port), "--kid", ",".join(kids),
                     "--stream", "quiet", "--rate", str(rate / producers), "--ports", str(40 // producers), "--index", str(i + 4 * rate),
                     "--duration", str(seconds), "--churn"], env=self.env(), stdout=subprocess.PIPE)
                self.addCleanup(self._reap, p)
                out.append(p)
            return out

        def udp(self):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(("127.0.0.1", 0))
            self.addCleanup(s.close)
            return s

        def counted(self, name, want, since, deadline=20.0):
            """Seconds from ``since`` until ``health`` said that ``receive.<name>`` was ``want`` or more."""
            while time.monotonic() - since < deadline:
                at = next((t for t, r in list(self.tap.recs) if r["type"] == "health" and (r["receive"].get(name) or 0) >= want), None)
                if at is not None:
                    return round(at - since, 3)
                time.sleep(0.01)
            return None

    popen = subprocess.Popen

    def quick(argv, *a, **kw):              # the case's daemon, with a health record twenty times a second
        if "--health-interval" in argv:
            argv = argv[:argv.index("--health-interval") + 1] + [str(HEALTH_S)]
        return popen(argv, *a, **kw)

    F.subprocess.Popen = quick
    c = Case()
    c.setUp()
    try:
        c.daemon()
        F.subprocess.Popen = popen
        dest, key = ("127.0.0.1", c.port), c.keys["quiet"]
        st = Station(key, [StreamConfig("quiet")], epoch=7, rng=F.random.Random(3), now_ms=runner.now_ms(),
                     beacon_period_ms=1_000 if row == "I-b" else 250)
        if row == "I-b":
            return i_b(c, st, dest, runner, wire)
        return i_a(c, st, dest, runner, wire, stream_id, lead=row == "I-a-lead")
    finally:
        F.subprocess.Popen = popen
        c.doCleanups()


def i_a(c, st, dest, runner, wire, stream_id, lead) -> dict:
    relays = [c.udp() for _ in range(4)]
    start = time.monotonic()
    other = c.forged([c.kid(k) for k in c.keys if k != "quiet"], 20_000, 60, 1)
    json.loads(other[0].stdout.readline())
    time.sleep(1.0)
    sent = 0
    while sent < len(relays):                   # each relay is heard first, with a beacon nobody else delivers
        for f in st.poll(runner.now_ms()):
            if f[3] == wire.KIND_BEACON:
                relays[sent].sendto(f, dest)
                sent += 1
                if sent == len(relays):
                    break
        time.sleep(0.01)
    before = c.counted("known", len(relays), start)
    out = {"relays_known_s": before, "starts": []}
    idem, sung = {}, {}
    for n in range(2):                          # the real station starts, and changes its port
        sock, t0, own, done, seqs = c.udp(), None, None, 0, {}
        begin = time.monotonic()
        while time.monotonic() - begin < 10.0:
            now = time.monotonic()
            if own is None and now - begin >= 2.0:
                own = c.forged([c.kid("quiet")], 100_000, 7.0, 2)
                for p in own:
                    json.loads(p.stdout.readline())
                first_item = time.monotonic()
            if own is not None and done < ITEMS and time.monotonic() >= first_item + 0.15 * done:
                r = st.sing(runner.now_ms(), "quiet", text=f"item {n} {done}")
                seqs[r.seq] = None
                done += 1
            for f in st.poll(runner.now_ms()):
                if f[3] == wire.KIND_BEACON and lead:
                    for s in relays:
                        s.sendto(f, dest)
                    time.sleep(0.010)
                t = time.monotonic()
                sock.sendto(f, dest)
                t0 = t0 or t
                if f[3] == wire.KIND_ITEM and f not in idem:
                    seq = next(q for q, oa in st.streams["quiet"].ring.items() if oa.frame == f)
                    idem[f] = f"canticle:{st.key_id.hex()}:7:{stream_id('quiet'):08x}:{seq}"
                    if seq in seqs:
                        sung[idem[f]] = (n, t)
                if f[3] == wire.KIND_BEACON and not lead:
                    time.sleep(0.005)
                    for s in relays:
                        s.sendto(f, dest)
            time.sleep(0.002)
        place = c.counted("known", len(relays) + 1 + n, t0, deadline=time.monotonic() - t0)
        lat = [c.tap.first[i] - t if i in c.tap.first else None for i, (k, t) in sung.items() if k == n]
        totals = [json.loads(p.stdout.read()) for p in own]
        out["starts"].append({"known_after_s": place, "item_latency_s": [None if x is None else round(x, 4) for x in lat], "sung": len(lat),
                              "offered_per_s": round(sum(t["sent"] / (t["t1"] - t["t0"]) for t in totals)),
                              "lowest_second": min(sum(t["per_s"][i] for t in totals) for i in range(min(len(t["per_s"]) for t in totals))),
                              "flood_end_after_last_deadline_s": round(min(t["t1"] for t in totals) - max(t for k, t in sung.values() if k == n)
                                                                       - ITEM_S, 2),
                              "place_ok": place is not None and place <= PLACE_S,
                              "item_misses": sum(x is None or x > ITEM_S for x in lat) + ITEMS - len(lat)})
    h = c.tap.healths()[-1]
    out.update(receive=h["receive"], kernel_drops=h["records"].get("socket_dropped"))
    out["pass"] = all(s["place_ok"] and not s["item_misses"] for s in out["starts"])
    return out


def i_b(c, st, dest, runner, wire) -> dict:
    sock, last, sung = c.udp(), None, False
    begin = time.monotonic()
    while time.monotonic() - begin < 4.0:
        if not sung and time.monotonic() - begin > 1.0:
            st.sing(runner.now_ms(), "quiet", text="an incumbent")
            sung = True
        for f in st.poll(runner.now_ms()):
            sock.sendto(f, dest)
            if f[3] == wire.KIND_BEACON:
                last = (f, time.monotonic())
        time.sleep(0.01)
    beacon, at = last                           # it stops: nothing new from here on
    replays = 0
    while time.monotonic() - at < LATEST_S + 8.0:
        sock.sendto(beacon, dest)
        replays += 1
        time.sleep(0.1)
    time.sleep(2 * HEALTH_S)
    lapsed = next((t - at for t, r in c.tap.recs if r["type"] == "health" and r["receive"].get("lapsed")), None)
    h = c.tap.healths()[-1]
    return {"lapsed_after_s": None if lapsed is None else round(lapsed, 3), "replays": replays, "receive": h["receive"],
            "counts_lapses": "lapsed" in h["receive"], "pass": lapsed is not None and HORIZON_S <= lapsed <= LATEST_S}


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
                print(time.strftime("%H:%M:%SZ", time.gmtime()), name, row, run, "PASS" if r["pass"] else "FAIL",
                      r.get("starts") or r.get("lapsed_after_s"), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3])))
    else:
        main()
