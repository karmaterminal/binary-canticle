"""The scaled rows 🌫's conditions on #173 ask for (exact-source spoof, source churn, cold start), several runs each, on
the classes of test_fair_admission. Usage: scaled_rows.py <prototype/canticle-station> <out.json> <row,row|all> <runs>
A row is measured while its flood runs; nothing is asserted. Run it under nice -n 19 ionice -c3."""
import json, os, platform, sys, time
from importlib.metadata import version
from pathlib import Path
station, out, rows, runs = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
sys.path[:0] = [str(station), str(station / "tests")]
import test_fair_admission as F

LOCKED = "50.0.1"                               # .github/ci/requirements-station.txt
if version("cryptography") != LOCKED:
    sys.exit(f"cryptography {version('cryptography')}, not the locked {LOCKED}: not a run of these rows")

RATE = F.FLOOD_RATE
#        items, seconds of flood, the station's start (s after the flood's; None: established before it), flood rate and arguments
ROWS = {
    "spoof-exact-source-100000": dict(items=20, flood=8, spoof=True, rate=RATE),
    "spoof-exact-source-500": dict(items=20, flood=8, spoof=True, rate=500),
    "churn-established-100000": dict(items=57, flood=13.6, rate=RATE, churn=True),
    "relay-first-then-churn-100000": dict(items=20, flood=20, rate=RATE, churn=True, relay="first"),
    "relay-after-then-churn-100000": dict(items=20, flood=20, rate=RATE, churn=True, relay="after"),
    "cold-start-12-ports-20000": dict(items=20, flood=30, rate=20_000, ports=12, cold=True),
    "cold-start-40-ports-20000": dict(items=20, flood=30, rate=20_000, ports=40, cold=True),
    "cold-start-200-ports-20000": dict(items=20, flood=30, rate=20_000, ports=200, cold=True),
    "cold-start-churn-own-host-20000": dict(items=20, flood=30, rate=20_000, churn=True, hosts=(1,), cold=True),
    "cold-start-churn-60000-hosts-20000": dict(items=20, flood=30, rate=20_000, churn=True, hosts=(60_000,), cold=True),
}


class Quiet(F.Quiet):
    relay_after = False

    def poll(self):
        before = set(self.distinct)
        super().poll()
        if self.relay_after:
            for frame in self.distinct - before:
                if frame[3] == F.wire.KIND_BEACON:
                    time.sleep(F.RELAY_LEAD_S)
                    self.relays.append(F.socket.socket(F.socket.AF_INET, F.socket.SOCK_DGRAM))
                    self.relays[-1].sendto(frame, self.dest)


class Case(F.FairAdmissionCase):
    def runTest(self):
        pass

    def station(self, name, items, relay=None):
        q = Quiet(self.keys[name], self.port, items=items, beacon_ms=250 if relay else 1_000, relayed=relay == "first")
        q.relay_after = relay == "after"
        q.start()
        self.addCleanup(q.join)
        self.addCleanup(q.stop.set)
        return q

    def go(self, p):
        self.daemon()
        q = other = None
        if not p.get("cold"):
            q, other = self.station("quiet", p["items"], p.get("relay")), self.station("other", p["items"])
            self.settle(q)
            time.sleep(3 if p.get("relay") else 0.5)
        hosts = p.get("hosts", (1, 60_000) if p.get("churn") else (1,))
        base = ["forged", p["flood"], "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", p["rate"] / len(hosts)]
        start = time.monotonic()
        if p.get("spoof"):
            floods = [self.flood(*base, "--fd", q.sock.fileno(), fds=(q.sock.fileno(),))]
        else:
            floods = [self.flood(*base, *(("--churn", 1, "--hosts", h) if p.get("churn") else ("--ports", p["ports"])),
                                 *(("--beacons",) if p.get("cold") else ())) for h in hosts]
        if p.get("cold") or p.get("relay"):
            time.sleep(1)
        if q is None:
            q = self.station("quiet", p["items"])
        q.singing.set()
        if other is not None:
            other.singing.set()
        totals = [self.totals(f)[1] for f in floods]
        end = time.monotonic()
        time.sleep(0.3)
        h, lost = self.tap.next_health(), F.kernel_drops(self.port)

        def dist(st):
            lat = [1000 * (self.tap.first[i] - t) for i, t in st.sung.items() if i in self.tap.first and self.tap.first[i] <= end]
            return {"sung": len(st.sung), "during_the_flood": len(lat), "ever": sum(i in self.tap.first for i in st.sung),
                    "latency_ms": {k: round(F.percentile(lat, v), 1) for k, v in
                                   (("p50", 50), ("p90", 90), ("p99", 99), ("max", 100))} if lat else None}
        first = None
        if p.get("cold"):
            try:
                first = round(1000 * self.first_frame(q))
            except StopIteration:
                pass
        return {"station": dist(q), "another_station": dist(other) if other else None, "first_valid_frame_ms": first,
                "offered_per_s": round(sum(t["sent"] / t["elapsed"] for t in totals)), "flood_s": round(end - start, 1),
                "opened": sum(t.get("opened", 0) for t in totals), "sources": sum(t.get("sources", 0) for t in totals),
                "kernel_drops": lost, "reported_socket_dropped": h["records"].get("socket_dropped"), "receive": h.get("receive"),
                "bad_signature": h["counters"]["unverified"].get("bad_signature"),
                "health_reasons_seen": sorted({r for g in self.tap.healths() for r in g["reasons"]})}


got = json.loads(out.read_text()) if out.exists() else []
for name, p in ROWS.items():
    if rows != "all" and not any(name.startswith(r) for r in rows.split(",")):
        continue
    for run in range(runs):
        c = Case()
        c.setUp()
        try:
            r = {"row": name, "run": run, "python": platform.python_version(), "cryptography": version("cryptography"), **c.go(p)}
        finally:
            c.doCleanups()
        got.append(r)
        out.write_text("[\n" + ",\n".join(json.dumps(x) for x in got) + "\n]\n")
        s, o = r["station"], r["another_station"]
        print(name, run, s, "first", r["first_valid_frame_ms"], "| other", o and o["during_the_flood"], "| offered", r["offered_per_s"],
              "drops", r["kernel_drops"], {k: (r["receive"] or {}).get(k) for k in ("known", "displaced", "unverified", "refused")}, flush=True)
