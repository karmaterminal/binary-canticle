"""The newcomer-recovery rows of PLAN.md: a station that starts inside a sustained forged flood, against throwaway daemons.

Usage: newcomer_rows.py <out.json> <name=tree:runs,...> <row,...>
  e.g. newcomer_rows.py rows.json head=/scratch/head:5,base=/scratch/base:3 churn-40-20000-0,churn-40-100000-120
A tree is a ``git archive`` of prototype/canticle-station; a row is <churn|smooth|fixed>-<ports>-<rate>-<offset>. ``canticle`` comes
from the tree, and everything else from this repository (the daemon, the tap and the carousel are ``test_fair_admission``'s), so
every tree is measured by the same code. Runs are interleaved over the trees; what <out.json> already has is not run again.
Nothing is asserted. Run it under nice -n 19 ionice -c3, and nothing beside it."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[2] / "prototype" / "canticle-station" / "tests"
FIRST_S, ITEM_S, LOOP_S = 1.0, 2.0, 10.0        # PLAN.md: the two deadlines, and the severity label
ITEMS, AFTER_S = 20, 64.0                       # past the end of the last item's life: sung at 2.85 s, 60 s long
PER_PRODUCER = 50_000                           # datagrams/s one flood process is asked for at most


def one(tree: str, row: str, after: float) -> dict:
    sys.path[:0] = [tree, str(TESTS)]
    import test_fair_admission as F
    from canticle import wire
    from canticle.ids import stream_id
    F.ROOT = Path(tree)                         # the daemon under test is the tree's

    class Newcomer(F.Quiet):
        """The carousel, with its actual send times: each read immediately before the sendto."""

        def __init__(self, sk, port):
            super().__init__(sk, port, items=ITEMS)
            self.item_sent: dict = {}           # idem -> when its first copy went out
            self.idem: dict = {}                # frame -> idem
            self.sends: list = []               # (when, idem or None for a beacon), every copy of everything

        def poll(self):
            for frame in self.st.poll(F.runner.now_ms()):
                if frame[3] == wire.KIND_ITEM and frame not in self.idem:
                    seq = next(q for q, oa in self.st.streams["quiet"].ring.items() if oa.frame == frame)
                    self.idem[frame] = f"canticle:{self.st.key_id.hex()}:7:{stream_id('quiet'):08x}:{seq}"
                idem = self.idem.get(frame)
                now = time.monotonic()
                self.first_sent = self.first_sent or now
                if idem is not None:
                    self.item_sent.setdefault(idem, now)
                self.sends.append((now, idem))
                self.sock.sendto(frame, self.dest)

    class Case(F.FairAdmissionCase):
        def runTest(self):
            pass

    kind, ports, rate, offset = row.split("-")
    ports, rate, offset = int(ports), int(rate), float(offset)
    c = Case()
    c.setUp()
    try:
        daemon = c.daemon()
        n = -(-rate // PER_PRODUCER)
        procs = []
        for i in range(n):
            argv = [sys.executable, str(HERE / "forged_flood.py"), "--tests", str(TESTS), "--port", str(c.port), "--kid",
                    c.kid("quiet"), "--stream", "quiet", "--rate", str(rate / n), "--ports",
                    str(ports // n + (i < ports % n)), "--index", str(i), "--duration", str(offset + after)]
            p = subprocess.Popen(argv + ["--churn"] * (kind != "fixed") + ["--smooth"] * (kind == "smooth"), env=c.env(), stdout=subprocess.PIPE)
            c.addCleanup(c._reap, p)
            procs.append(p)
        t0 = max(json.loads(p.stdout.readline())["t0"] for p in procs)
        time.sleep(max(0.0, t0 + offset - time.monotonic()))
        q = Newcomer(c.keys["quiet"], c.port)
        c.addCleanup(q.join)
        c.addCleanup(q.stop.set)
        q.singing.set()
        started = time.monotonic()
        q.start()
        totals = [json.loads(p.stdout.read()) for p in procs]
        flood_end = min(t["t1"] for t in totals)            # the moment the flood was no longer whole
        time.sleep(0.3)
        kid, recs = c.kid("quiet"), list(c.tap.recs)
        health, drops = c.tap.next_health(), F.kernel_drops(c.port)
        with open(f"/proc/{daemon.pid}/stat") as fh:
            stat = fh.read().rsplit(")", 1)[1].split()
        heard = [(at, r) for at, r in recs if at <= flood_end and (
            (r["type"] == "presence" and r["key_id"] == kid) or (r["type"] == "frame" and r["admission"] == "verified"))]
        t1 = q.first_sent
        first = heard[0][0] - t1 if heard else None
        items = [{"sent_s": round(t - t1, 4),
                  "latency_s": round(c.tap.first[i] - t, 4) if c.tap.first.get(i, flood_end + 1) <= flood_end else None}
                 for i, t in sorted(q.item_sent.items(), key=lambda kv: kv[1])]
        last_deadline = max([t1 + FIRST_S] + [t + ITEM_S for t in q.item_sent.values()])
        lows = [sum(t["per_s"][i] for t in totals) for i in range(min(len(t["per_s"]) for t in totals))]
        return {
            "first_valid_frame_s": None if first is None else round(first, 4),
            "first_valid": heard[0][1]["type"] if heard else None,
            "items": items, "sung": len(q.sung),
            "first_miss": first is None or first > FIRST_S,
            "item_misses": sum(x["latency_s"] is None or x["latency_s"] > ITEM_S for x in items) + ITEMS - len(items),
            "items_lost": sum(x["latency_s"] is None for x in items) + ITEMS - len(items),
            "items_more_than_one_loop_late": sum(x["latency_s"] is not None and x["latency_s"] > LOOP_S for x in items),
            "dispositions": sorted({r["disposition"] for _, r in heard if r["type"] == "frame"}),
            "sent_before_first_valid": sum(t <= (heard[0][0] if heard else flood_end) for t, _ in q.sends),
            "sent": len(q.sends),
            "newcomer_start_after_t0_s": round(started - t0, 4), "first_send_after_t0_s": round(t1 - t0, 4),
            "flood_end_after_last_deadline_s": round(flood_end - last_deadline, 2),
            "flood_end_after_last_item_sent_s": round(flood_end - max(q.item_sent.values(), default=flood_end), 2),
            "offered_per_s": round(sum(t["sent"] / (t["t1"] - t["t0"]) for t in totals)), "lowest_second": min(lows),
            "producers": n, "opened": sum(t["opened"] for t in totals), "sources": sum(t["sources"] for t in totals),
            "kernel_drops": drops, "reported_socket_dropped": health["records"].get("socket_dropped"),
            "receive": health.get("receive"), "unverified": {k: v for k, v in health["counters"]["unverified"].items() if v},
            "health_reasons_seen": sorted({r for h in c.tap.healths() for r in h["reasons"]}),
            "daemon_cpu_s": (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK"),
            "run_s": round(time.monotonic() - t0, 1)}
    finally:
        c.doCleanups()


def main() -> None:
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
                waited = 0
                while os.getloadavg()[0] > os.cpu_count() / 2 and waited < 300:
                    time.sleep(10)
                    waited += 10
                load = os.getloadavg()[0]
                p = subprocess.run([sys.executable, __file__, "--one", tree, row, str(AFTER_S)],
                                   stdout=subprocess.PIPE, text=True)
                if p.returncode:
                    print(name, row, run, "FAILED TO RUN", p.returncode, flush=True)
                    continue
                r = {"tree": name, "row": row, "run": run, "load_before": load, **json.loads(p.stdout)}
                got.append(r)
                out.write_text("[\n" + ",\n".join(json.dumps(x) for x in got) + "\n]\n")
                lat = sorted(float("inf") if x["latency_s"] is None else x["latency_s"] for x in r["items"])
                print(time.strftime("%H:%M:%SZ", time.gmtime()), name, row, run, "first", r["first_valid_frame_s"],
                      "items min/med/max", lat[0], lat[len(lat) // 2], lat[-1], "| misses: first", int(r["first_miss"]),
                      "items", r["item_misses"], "lost", r["items_lost"], "| offered", r["offered_per_s"], "low",
                      r["lowest_second"], "| drops", r["kernel_drops"], r["reported_socket_dropped"], "| cpu",
                      r["daemon_cpu_s"], flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3], float(sys.argv[4]))))
    else:
        main()
