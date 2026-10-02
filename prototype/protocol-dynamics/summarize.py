"""Print the tables in SUMMARY.md from results/<unit>/ (Markdown on stdout), or verify published runs.

    python summarize.py                            # all experiments
    python summarize.py e1 e2                      # some
    python summarize.py --results /tmp/smoke e1
    python summarize.py verify                     # every unit: files against manifest, sources against its commit
    python summarize.py verify --commit HEAD e1    # the source digest recomputed from git show HEAD:<path>

Each experiment's generation lives in results/<unit>/ (e1, e2, e3-slow,
e3-dead, e4, e5) with a manifest.json; see harness/runs.py. Before printing a
unit, its files are checked against its manifest, and a generation that does
not match is refused. A unit without a manifest (published before manifests
existed) is printed with a note that its provenance is unknown.

Latencies with censoring (E1 updates and outage recovery, E4 joins) are
Kaplan–Meier quantiles. A quantile the survival curve never reaches is shown
as "> X", X being the largest time observed in that cell (delivered or censored).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
sys.path.insert(0, HERE)

from harness import runs  # noqa: E402

# unit directory and aggregate file of each experiment
UNITS = {"e1": [("e1", "e1_freshness.json")], "e2": [("e2", "e2_fanout.json")],
         "e3": [("e3-slow", "e3_slow.json"), ("e3-dead", "e3_dead.json")],
         "e4": [("e4", "e4_late_joiner.json")], "e5": [("e5", "e5_reconnect_storm.json")]}


def load(unit: str, name: str):
    """The aggregate of ``results/<unit>/``, after checking the generation against its manifest."""
    gen = os.path.join(RES, unit)
    path = os.path.join(gen, name)
    if not os.path.exists(path):
        return None
    if runs.load_manifest(gen) is not None:
        try:
            runs.check_generation(gen)
        except runs.RunFailed as e:
            raise SystemExit(f"summarize: refusing {unit}: {e}")
    with open(path) as f:
        return json.load(f)


def provenance(unit: str) -> str:
    m = runs.load_manifest(os.path.join(RES, unit))
    if m is None:
        return f"*`results/{unit}/`: no run manifest (published before manifests existed); provenance unknown.*"
    state = "clean" if not m["git_dirty"] else f"dirty, diff sha256 `{m['source']['patch']['sha256'][:12]}` embedded"
    return (f"*`results/{unit}/`: run `{m['run_id']}`, {m['started']} to {m['finished']}, commit"
            f" `{(m['git_commit'] or '?')[:12]}` ({state}), sources sha256 `{m['source_sha256'][:12]}`.*")


def ms(v) -> str:
    """Milliseconds, shown in s above 10 s; exact to 0.1 ms below."""
    if v is None:
        return "–"
    if v >= 10_000:
        return f"{v / 1000:.1f} s"
    return f"{v:.1f}"


def kmq(km: dict, q: str) -> str:
    """A Kaplan–Meier quantile, or '> X' when censoring leaves it undefined."""
    if km.get(q) is not None:
        return ms(km[q])
    if km.get("n"):
        return f"> {ms(km.get('censored_beyond_ms'))}"
    return "–"


def delivered(frac) -> str:
    return "" if frac is None or frac >= 1 else f" · {frac * 100:.2f}% delivered"


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ---------------------------------------------------------------- E1

ARMS = ("udp-live", "udp-ctl", "tcp-stream", "tcp-latest")


def e1() -> str:
    d = load("e1", "e1_freshness.json")
    if not d:
        return ""
    by = defaultdict(dict)
    for r in d["rows"]:
        by[(r["update_s"], r["loss_direction"], r["loss_permille"], r["outage_s"])][r["arm"]] = r

    def cell(r: dict) -> str:
        km = r["update_latency_km_ms"]
        return f"{kmq(km, 'p95')} / {kmq(km, 'p99')}{delivered(r['delivered_fraction'])}"

    out = []
    for u in sorted({k[0] for k in by}):
        rows = []
        for (uu, dirn, loss, out_s), arms in sorted(by.items()):
            if uu != u or out_s or dirn != "both":
                continue
            row = [f"{loss / 10:g}%", f"{arms['udp-live']['measured_loss'] * 100:.1f}%"]
            row += [cell(arms[a]) for a in ARMS]
            row.append(" / ".join(f"{arms[a]['stale_time_fraction'] * 100:.2f}" for a in ARMS))
            row.append(" / ".join(ms(arms[a]["staleness_ms_time_weighted"]["max"]) for a in ARMS))
            rows.append(row)
        out.append(f"**U = {u:g} s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99"
                   " in ms (s where marked), with the share of (update, receiver) pairs delivered before the run"
                   " ended where it is below 100%. Stale time % and the longest time a receiver held a superseded"
                   " value, in arm order.\n\n"
                   + table(["loss", "measured", *ARMS, "stale % (udp-live / udp-ctl / tcp-stream / tcp-latest)",
                            "staleness max (same order)"], rows))
    rows = []
    for (u, dirn, loss, out_s), arms in sorted(by.items()):
        if dirn != "data-only":
            continue
        rows.append([f"{u:g} s", f"{loss / 10:g}%", *(cell(arms[a]) for a in ARMS),
                     " / ".join(ms(arms[a]["staleness_ms_time_weighted"]["max"]) for a in ARMS)])
    out.append("**Data-only loss** (pure ACKs, SYN and FIN spared). Update latency, Kaplan–Meier p95 / p99 in ms,"
               " delivered share where below 100%; staleness max in arm order.\n\n"
               + table(["U", "loss", *ARMS, "staleness max"], rows))
    rows = []
    for (u, dirn, loss, out_s), arms in sorted(by.items(), key=lambda kv: (kv[0][3], kv[0][0])):
        if not out_s:
            continue
        row = [f"{out_s:g} s", f"{u:g} s", arms["udp-live"]["outages_x_receivers"] // arms["udp-live"]["receivers"]]
        for a in ARMS:
            rec, io = arms[a]["outage_recovery_km_ms"], arms[a]["latency_of_updates_issued_in_outage_km_ms"]
            cens = f" ({rec['censored']} censored)" if rec["censored"] else ""
            row.append(f"{kmq(rec, 'median')} / {kmq(rec, 'p95')}{cens} · {kmq(io, 'median')}")
        rows.append(row)
    out.append("**Outages.** Recovery after the outage ends (time until the receiver holds the newest value),"
               " Kaplan–Meier p50 / p95, with the number of (outage, receiver) pairs not recovered by the end of the"
               " run where nonzero · Kaplan–Meier median latency of updates issued inside the outage, ms."
               " 20 receivers per arm.\n\n"
               + table(["outage", "U", "outages", *ARMS], rows))
    rows = []
    for (u, dirn, loss, out_s), arms in sorted(by.items()):
        if out_s or loss < 100:
            continue
        for a in ("tcp-stream", "tcp-latest"):
            t = arms[a]["tcp"]
            eps = t["loss_episodes"]
            longest = eps["longest"][0] if eps["longest"] else {}
            ltxt = "–"
            if longest:
                ltxt = f"{longest['dur_ms'] / 1000:.1f} s"
                if longest.get("open_at_end"):
                    ltxt = f"≥ {ltxt} (open at end)"
            rows.append([f"{u:g} s", dirn, f"{loss / 10:g}%", a, arms[a]["superseded_deliveries"],
                         sum(t.get("rejected_on_arrival", {}).values()), arms[a]["censored"],
                         f"{arms[a]['delivered_fraction'] * 100:.2f}%",
                         max((int(k) for k in eps["max_backoff_hist"]), default=0), ltxt,
                         sum(t["total_retrans"]), len(t["sender_errors"]) + len(t["receiver_errors"])])
    out.append("**TCP pathologies** (20 connections per arm, 900 s). *superseded* = frames delivered after a newer"
               " value was already issued; *expired* = frames delivered after their signed `expires_at` (a receiver"
               " must drop them); *censored* = (update, receiver) pairs never caught up by the end of the run;"
               " *delivered* = the rest, as a share; *longest* = longest stretch with an unacknowledged"
               " retransmission (TCP_INFO, 20 ms sampling; ≥ when it was still open when the run ended).\n\n"
               + table(["U", "loss dir", "loss", "arm", "superseded", "expired", "censored", "delivered",
                        "max backoff", "longest", "retrans (sum)", "resets"], rows))
    return "\n\n".join([provenance("e1"), *out])


# ---------------------------------------------------------------- E2

def e2() -> str:
    from e2_fanout import cost
    d = load("e2", "e2_fanout.json")
    if not d:
        return ""
    costs = {(c["mode"], c["n"]): c for c in (d.get("cost") or cost(d))}
    agg = defaultdict(list)
    for r in d["rows"]:
        if r["mode"] != "idle":
            agg[(r["mode"], r["n"])].append(r)

    def mean(xs):
        return sum(xs) / len(xs)

    def rng(xs, f="{:.3f}"):
        return f.format(mean(xs)) + (f" ({f.format(min(xs))}–{f.format(max(xs))})" if len(xs) > 1 else "")

    def per_listener(c: dict) -> str:
        if c["resolved"]:
            lo, hi = c["us_per_listener_frame"]["ci95"]
            return f"{c['us_per_listener_frame']['mean']:.2f} ({lo:.2f}–{hi:.2f})"
        return f"not resolved (±{c['resolution_us']:.2f})" if c["resolution_us"] is not None else "not resolved (1 run)"

    rows = []
    for (mode, n), rs in sorted(agg.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        c = costs[(mode, n)]
        host = [r["sender_host_cpu0_busy_s_per_s"] for r in rs]
        proc = [r["sender_process_cpu_s_per_s"] for r in rs]
        w = rs[0]["wire"]
        mem = rs[0]["memory"]
        rows.append([mode, n, rng([h * 100 for h in host], "{:.2f}"),
                     rng([i * 100 for i in c["idle_cpu0_busy_s_per_s"]], "{:.2f}"),
                     rng([p * 100 for p in proc], "{:.2f}"), per_listener(c),
                     f"{w['tx_bytes_per_s'] / 1000:.1f}", f"{w['rx_bytes_per_s'] / 1000:.1f}",
                     f"{w['tx_packets_per_s']} / {w['rx_packets_per_s']}", mem["sender_rss_kb"], mem["sender_fds"],
                     rs[0]["sender"]["syscalls"] // rs[0]["sender"]["frames"],
                     f"{mean([r['sender']['enqueue_all_p50_us'] for r in rs]) / 1000:.2f}",
                     min(r["receiver"]["min_frames"] for r in rs), sum(r["softnet_drops"] for r in rs)])
    matched = all(c["idle_matched"] for c in costs.values())
    head = ["mode", "N", "sender host CPU % (CPU 0)", "idle CPU 0 %" + ("" if matched else " (one unmatched sample)"),
            "sender process CPU %", "µs per listener·frame (95% CI)", "wire out kB/s", "wire in kB/s",
            "pkts/s out / in", "sender RSS kB", "sender fds", "syscalls/frame",
            "sender enqueue time, one frame to all N, p50 ms", "min frames/listener", "backlog drops"]
    mem_rows = []
    for (mode, n), rs in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if n < 1000:
            continue
        m = rs[0]["memory"]
        sk = m.get("ss_skmem_tx") or {}
        mem_rows.append([mode, n, m["slab_delta_kb_both_ends"], m["sockstat_tx"].get("TCP", {}).get("inuse", 0),
                         m["sockstat_tx"].get("TCP", {}).get("mem", 0), sk.get("t", "–"), sk.get("w", "–"),
                         m["receiver_rss_kb"]])
    drift = [r["slab_delta_kb"] for r in d["rows"] if r["mode"] == "idle" and "slab_delta_kb" in r]
    slab_note = (f"With nothing running, the slab moved {min(drift)} to {max(drift)} kB over one window (the idle"
                 " controls), so rows for N ≤ 100 are noise; they are in `results/e2/e2_fanout.json`." if drift else
                 "Rows for N ≤ 100 are inside the slab's drift with nothing running; they are in"
                 " `results/e2/e2_fanout.json`.")
    idle_note = ("Idle is the matched control of the same repeat and N: the same namespaces and window with nothing"
                 " running, in a shuffled order with the loaded runs." if matched else
                 "This run predates matched controls: idle is one unmatched 20 s sample taken before all runs.")
    return (provenance("e2") + "\n\n"
            f"Mean of {max(len(v) for v in agg.values())} runs (min–max); {d['config']['measure']:g} s windows after"
            f" {d['config']['warmup']:g} s warm-up. {idle_note} *µs per listener·frame* = (CPU 0 busy − idle) /"
            " (N × frames/s), per repeat; the mean over repeats with its 95% t-interval, widened where needed to the"
            " two-tick quantum of CPU accounting (1/100 s per window), shown only when the interval lies above 0."
            " Otherwise the cost is *not resolved* at that N (it is inside the idle noise), and ± is the interval's"
            " half-width, about the smallest cost the run could have resolved. *Sender enqueue time* = how long"
            " the sender's loop took to hand one frame to the kernel for all N listeners (sender clock); when the"
            " last listener received it was not measured.\n\n"
            + table(head, rows) + "\n\nMemory, N ≥ 1 000 (first run of each; slab is host-wide, so it counts both"
            " ends of every TCP connection). " + slab_note + "\n\n"
            + table(["mode", "N", "slab Δ kB (both ends)", "TCP sockets in use (tx ns)", "TCP mem pages (host)",
                     "Σ skmem t (tx)", "Σ skmem w (tx)", "receiver RSS kB"], mem_rows))


# ---------------------------------------------------------------- E3

def e3() -> str:
    out = []
    d = load("e3-slow", "e3_slow.json")
    if d:
        out.append(provenance("e3-slow"))
        rows = []
        for name, r in d["runs"].items():
            if "error" in r:
                rows.append([name, "error", r["error"]] + [""] * 7)
                continue
            rel = r["relay"]
            tl = rel.get("timeline", [])
            v = rel.get("victim", {})
            h = r["healthy"]
            peak_q = max((s.get("victim_queue_bytes") or 0 for s in tl), default=0)
            rows.append([name, r.get("victim_rcvbuf_set"), rel.get("stalled_at_s") or "none",
                         f"{h['latency_ms']['p99']} / {h['latency_ms']['max']}", h["last_frame_at_s_median"],
                         f"{h['frames_per_listener_min']} / {h['frames_expected_per_listener']}",
                         peak_q, v.get("dropped", "–"), v.get("closed_at_s") or "–",
                         f"{tl[0]['rss_kb']} → {rel.get('rss_kb_end')}" if tl else rel.get("rss_kb_end"),
                         r.get("victim_unread_bytes_at_end") if name.startswith("tcp") else "–",
                         r["snmp"].get("Udp.RcvbufErrors", 0)])
        out.append("**Slow consumer** (listener 0 stops reading at t = 10 s; 100 listeners, 10 × 700 B frames/s,"
                   " 600 s runs). *victim unread* = FIONREAD on the victim's TCP socket at the end.\n\n"
                   + table(["variant", "victim SO_RCVBUF", "sender stalled at (s)",
                            "healthy latency p99 / max ms (delivered frames only)",
                            "healthy: last frame at (s, median)", "healthy frames min / expected",
                            "victim app queue peak B",
                            "frames dropped for victim", "victim disconnected at (s)", "sender RSS kB",
                            "victim unread B at end", "UDP RcvbufErrors"], rows))
    d = load("e3-dead", "e3_dead.json")
    if d:
        out.append(provenance("e3-dead"))
        rows = []
        for name, r in d["runs"].items():
            rel = r.get("relay", {})
            tl = rel.get("timeline", [])
            last_tcp = next((s["victim_tcp"] for s in reversed(tl) if s.get("victim_tcp")), {})
            h = r["healthy"]
            if name == "udp-lease":
                le = r["leases"]
                lap, dg = le["lapse_after_death_s"], le["datagrams_after_death_approx"]
                rows.append([name, f"lease lapsed {lap.get('median')} s (p50), {lap.get('min')}–{lap.get('max')} s",
                             "0", f"≈{dg.get('median')} datagrams (p50)", "–",
                             f"{h['latency_ms']['p99']} / {h['latency_ms']['max']}",
                             f"{le['died']} died, {le['lapsed']} lapsed, {le['healthy_lapsed']} healthy lapsed"])
                continue
            rows.append([name, f"{r.get('victim_closed_after_death_s')} s ({rel['victim']['error']})",
                         f"{last_tcp.get('total_retrans', '–')} (max RTO {last_tcp.get('rto_ms', '–')} ms)",
                         f"{rel['victim']['queue_bytes_end']} B app + {last_tcp.get('notsent_bytes', 0)} B kernel",
                         f"{tl[0]['rss_kb']} → {rel.get('rss_kb_end')}" if tl else "–",
                         f"{h['latency_ms']['p99']} / {h['latency_ms']['max']}", ""])
        out.append("**Dead listener** (listener 0 of 100 vanishes at t ≈ 10 s).\n\n"
                   + table(["variant", "sender notices after", "retransmissions", "held for the dead listener",
                            "sender RSS kB", "healthy latency p99 / max ms", "note"], rows))
    return "\n\n".join(out)


# ---------------------------------------------------------------- E4, E5

def e4() -> str:
    d = load("e4", "e4_late_joiner.json")
    if not d:
        return ""
    rows = []
    for c in sorted(d["conditions"], key=lambda c: c["loss_permille"]):
        for arm, m in c["arms"].items():
            km, done = m["t_full_km_ms"], m["t_full_completed_ms"]
            extra = ""
            if "handshake_ms" in m:
                extra = (f"handshake p50/p99 {ms(m['handshake_ms'].get('median'))}/{ms(m['handshake_ms'].get('p99'))};"
                         f" relay snapshots {c['relay_snapshots']} for {m['trials']} sessions")
            if "connect_ms" in m:
                extra = (f"connect p50/p99 {ms(m['connect_ms'].get('median'))}/{ms(m['connect_ms'].get('p99'))};"
                         f" server snapshots {c['tcp_snapshots']}")
            rows.append([f"{c['loss_permille'] / 10:g}%", arm, m["trials"], m["completed"], m["timeouts"],
                         m["cut_at_end"], kmq(km, "median"), kmq(km, "p90"), kmq(km, "p99"), ms(done.get("max")),
                         extra])
    c0 = d["conditions"][0]
    return (provenance("e4") + "\n\n" + f"20 live items, {c0['frame_bytes']} B frames; effective loops {c0['loop_ms']} ms; 10 joiners per arm"
            f" back to back for {c0['duration_s']:g} s; timeout {c0['trial_timeout_s']} s. Time to hold all 20,"
            " Kaplan–Meier over every join (a join that timed out or was cut off by the end of the run is censored"
            " at its elapsed time), ms (s where marked); *max done* is the slowest completed join.\n\n"
            + table(["loss", "arm", "joins", "completed", "timeouts", "cut at end", "p50", "p90", "p99", "max done",
                     ""], rows))


def e5() -> str:
    d = load("e5", "e5_reconnect_storm.json")
    if not d:
        return ""
    rows = []
    for r in d["runs"]:
        s = r["snmp"]
        sc = r.get("new_relay_syscalls") or {}
        rows.append([r["mode"], r.get("backlog") or "–", r.get("repeat"), "strace" if r.get("strace_pass") else "timed",
                     r["new_relay_ready_after_kill_s"], r["all_served_after_kill_s"],
                     f"{r['served_after_kill_s']['median']} / {r['served_after_kill_s']['p99']}",
                     s.get("TcpExt.ListenOverflows", 0), s.get("TcpExt.TCPSynRetrans", 0),
                     s.get("Udp.RcvbufErrors", 0), r["packets_offered"], sc.get("total", "–"),
                     json.dumps(r["listener_attempts_during"])])
    return (provenance("e5") + "\n\n" + f"N = {d['n']} listeners, {d['items']} × {d['frame_bytes']} B snapshot. Times in s from SIGKILL of the old"
            " relay.\n\n" + table(["mode", "backlog", "rep", "pass", "new relay up", "all served", "served p50 / p99",
                                    "ListenOverflows", "SYN retrans", "UDP RcvbufErrors", "packets",
                                    "relay syscalls", "listener attempts"], rows))


def verify(units: list[str], commit) -> int:
    """Check each unit's files against its manifest and its source digest against ``commit``; 0 if all hold."""
    bad = 0
    for exp in units:
        for unit, _ in UNITS[exp]:
            gen = os.path.join(RES, unit)
            if not os.path.isdir(gen):
                print(f"{unit}: not published")
                continue
            if runs.load_manifest(gen) is None:
                print(f"{unit}: MISMATCH no manifest.json (published before manifests existed): provenance unknown")
                bad += 1
                continue
            try:
                v = runs.verify(gen, commit)
            except runs.RunFailed as e:
                print(f"{unit}: MISMATCH {e}")
                bad += 1
                continue
            what = f"sources at {v['commit'][:12]}"
            if v["commit"] != v["recorded_commit"]:
                what += f" (run recorded {v['recorded_commit'][:12]})"
            print(f"{unit}: run {v['run_id']}: files match manifest; {what}:"
                  f" {'MATCH' if v['match'] else 'MISMATCH'} (recorded {v['recorded_digest'][:16]},"
                  f" at commit {v['digest_at_commit'][:16]})" + (f"; differ: {v['differ']}" if v["differ"] else ""))
            ok = v["match"]
            if "match_with_patch" in v:
                print(f"{unit}: dirty run: commit + embedded diff (sha256 ok: {v['patch_sha256_ok']}):"
                      f" {'MATCH' if v['match_with_patch'] else 'MISMATCH'}"
                      + (f" ({v['patch_error']})" if "patch_error" in v else ""))
                ok = ok or v["match_with_patch"]
            bad += not ok
    return 1 if bad else 0


def main() -> None:
    global RES
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", help="results directory (default: results/)")
    p.add_argument("--commit", help="verify: the commit to check source digests against (default: the recorded one)")
    p.add_argument("what", nargs="*", help="experiments (e1 … e5), optionally preceded by 'verify'")
    a = p.parse_args()
    if a.results:
        RES = os.path.abspath(a.results)
    what = a.what
    if what[:1] == ["verify"]:
        sys.exit(verify(what[1:] or list(UNITS), a.commit))
    unknown = set(what) - set(UNITS)
    if unknown:
        p.error(f"unknown experiments {sorted(unknown)}")
    from harness import stats
    stats.km_selfcheck()
    for w in what or list(UNITS):
        print(f"## {w.upper()}\n")
        print(globals()[w]())
        print()


if __name__ == "__main__":
    main()
