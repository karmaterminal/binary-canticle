"""E2: what it costs a relay to fan one frame out to N listeners.

One ~700 B frame at 10 frames/s goes to N listeners (N = 10, 100, 1000, 5000)
by three means, sent by the Go program in ``fanout/``:

- ``tcp``: N TCP connections (TCP_NODELAY, cubic), one write() per listener per frame;
- ``udp``: UDP unicast to N ports, sendmmsg() in batches of up to 1 024;
- ``mcast``: one UDP datagram per frame to 239.255.13.13, received by N sockets
  that each joined the group (all N in one receiver process).

Testbed. The sender runs in namespace ``pd-e2-tx``, the listeners in
``pd-e2-rx``, joined by a veth pair (10.77.0.1 ↔ 10.77.0.2). The veth
counters in ``pd-e2-tx`` are the "wire": every data packet, and every TCP ACK
coming back, crosses it. The sender is pinned to CPU 0 and the listeners to
CPUs 2-3. RPS steers the listeners' receive processing to CPUs 2-3 and the
ACKs arriving at the sender to CPU 0, so CPU 0's busy time is the sending host's
cost (process + softirq), and the listeners' kernel work is not charged to it.
The kernel uses tick-based accounting (HZ 250, no IRQ-time accounting), so
softirq time lands on whichever CPU runs it; that is why RPS is set.
``net.core.netdev_max_backlog`` is raised to 16 384 for the run and restored,
so bursts of N packets are not dropped in the RPS backlog.

Run (root)::

    python e2_fanout.py --repeats 3 --measure 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import netns, stats  # noqa: E402

TX, RX = "pd-e2-tx", "pd-e2-rx"
TX_IP, RX_IP = "10.77.0.1", "10.77.0.2"
GROUP = "239.255.13.13:9999"
SENDER_CPU, ACK_CPU_MASK, RX_CPUS, RX_CPU_MASK = "0", "1", "2,3", "c"
CLK_TCK = os.sysconf("SC_CLK_TCK")
BACKLOG = "/proc/sys/net/core/netdev_max_backlog"


def sh(*argv: str) -> str:
    return netns.run(*argv)


def topology() -> None:
    for ns in (TX, RX):
        sh("ip", "netns", "del", ns) if ns in sh("ip", "netns", "list") else None
        sh("ip", "netns", "add", ns)
        sh(*netns.ns_exec(ns, "ip", "link", "set", "lo", "up"))
    sh("ip", "link", "add", "pdv0", "netns", TX, "type", "veth", "peer", "name", "pdv1", "netns", RX)
    for ns, dev, ip, mask in ((TX, "pdv0", TX_IP, ACK_CPU_MASK), (RX, "pdv1", RX_IP, RX_CPU_MASK)):
        sh(*netns.ns_exec(ns, "ip", "addr", "add", f"{ip}/24", "dev", dev))
        sh(*netns.ns_exec(ns, "ip", "link", "set", dev, "up"))
        sh(*netns.ns_exec(ns, "ip", "route", "add", "224.0.0.0/4", "dev", dev))
        sh(*netns.ns_exec(ns, "sh", "-c", f"echo {mask} > /sys/class/net/{dev}/queues/rx-0/rps_cpus"))


def teardown() -> None:
    for ns in (TX, RX):
        netns.run("ip", "netns", "del", ns, check=False)


# ---------------------------------------------------------------- snapshots

def cpu_times() -> dict:
    out = {}
    with open("/proc/stat") as f:
        for line in f:
            if re.match(r"cpu\d", line):
                p = line.split()
                user, nice, system, idle, iowait, irq, softirq, steal = (int(x) for x in p[1:9])
                out[p[0]] = {"busy": user + nice + system + irq + softirq + steal, "total": user + nice + system + idle
                             + iowait + irq + softirq + steal, "softirq": softirq, "system": system, "user": user}
    return out


def proc_cpu(pid: int) -> float:
    with open(f"/proc/{pid}/stat") as f:
        p = f.read().rsplit(")", 1)[1].split()
    return (int(p[11]) + int(p[12])) / CLK_TCK   # utime + stime, seconds


def proc_status(pid: int) -> dict:
    with open(f"/proc/{pid}/status") as f:
        kv = dict(line.split(":", 1) for line in f if ":" in line)
    return {"rss_kb": int(kv["VmRSS"].split()[0]), "threads": int(kv["Threads"]),
            "fds": len(os.listdir(f"/proc/{pid}/fd"))}


def link_stats(ns: str, dev: str) -> dict:
    d = json.loads(sh("ip", "-n", ns, "-s", "-j", "link", "show", dev))[0]["stats64"]
    return {"tx_bytes": d["tx"]["bytes"], "tx_packets": d["tx"]["packets"],
            "rx_bytes": d["rx"]["bytes"], "rx_packets": d["rx"]["packets"], "tx_dropped": d["tx"]["dropped"]}


def sockstat(pid: int) -> dict:
    out = {}
    with open(f"/proc/{pid}/net/sockstat") as f:   # the namespace of that process
        for line in f:
            proto, rest = line.split(":", 1)
            vals = rest.split()
            out[proto] = {k: int(v) for k, v in zip(vals[::2], vals[1::2])}
    return out


def meminfo() -> dict:
    with open("/proc/meminfo") as f:
        kv = dict(line.split(":", 1) for line in f)
    return {k: int(kv[k].split()[0]) for k in ("Slab", "SUnreclaim", "MemAvailable")}


def softnet_drops() -> int:
    with open("/proc/net/softnet_stat") as f:
        return sum(int(line.split()[1], 16) for line in f)


def ss_skmem(ns: str) -> dict:
    """Sum of ss -tm skmem fields over established TCP sockets in ``ns``."""
    out = sh(*netns.ns_exec(ns, "ss", "-tmnH", "state", "established"))
    tot, count = {}, 0
    for m in re.finditer(r"skmem:\(([^)]*)\)", out):
        count += 1
        for field in m.group(1).split(","):
            k = re.match(r"[a-z_]+", field).group(0)
            tot[k] = tot.get(k, 0) + int(field[len(k):])
    return {"sockets": count, **tot}


def snapshot(sender: int, receiver: int) -> dict:
    return {"t": time.monotonic(), "cpu": cpu_times(), "sender_cpu_s": proc_cpu(sender),
            "receiver_cpu_s": proc_cpu(receiver), "link": link_stats(TX, "pdv0"), "softnet_drops": softnet_drops()}


# ---------------------------------------------------------------- one run

def one(binary: str, mode: str, n: int, a) -> dict:
    topology()
    try:
        return _one(binary, mode, n, a)
    finally:
        teardown()


def _one(binary: str, mode: str, n: int, a) -> dict:
    total = a.warmup + a.measure + 3
    base = meminfo()
    send_args = ["-mode", mode, "-n", str(n), "-rate", str(a.rate), "-size", str(a.size),
                 "-duration", f"{total}s", "-listen", f"{TX_IP}:7000", "-dst", RX_IP, "-group", GROUP,
                 "-ifaddr", TX_IP]
    recv_args = ["-mode", mode, "-n", str(n), "-size", str(a.size), "-connect", f"{TX_IP}:7000",
                 "-bind", RX_IP, "-group", GROUP, "-ifaddr", RX_IP]
    sender_cmd = ["taskset", "-c", SENDER_CPU, *netns.ns_exec(TX, binary, "send", *send_args)]
    t_setup = time.monotonic()
    if mode == "tcp":
        sender = subprocess.Popen(sender_cmd, stdout=subprocess.PIPE, text=True)
        time.sleep(0.3)
        receiver = subprocess.Popen(["taskset", "-c", RX_CPUS, *netns.ns_exec(
            RX, binary, "recv", *recv_args, "-duration", f"{total + 60}s")], stdout=subprocess.PIPE, text=True)
        # (TCP receivers exit as soon as every connection has seen EOF from the departing sender)
    else:
        receiver = subprocess.Popen(["taskset", "-c", RX_CPUS, *netns.ns_exec(
            RX, binary, "recv", *recv_args, "-duration", f"{total + 4}s")], stdout=subprocess.PIPE, text=True)
        assert receiver.stdout.readline().strip() == "attached"
        sender = subprocess.Popen(sender_cmd, stdout=subprocess.PIPE, text=True)
    assert sender.stdout.readline().strip() == "ready"
    setup_s = time.monotonic() - t_setup
    time.sleep(a.warmup)
    s0 = snapshot(sender.pid, receiver.pid)
    time.sleep(a.measure)
    s1 = snapshot(sender.pid, receiver.pid)
    held = {"sender": proc_status(sender.pid), "receiver": proc_status(receiver.pid),
            "sockstat_tx": sockstat(sender.pid), "meminfo": meminfo(),
            "ss_skmem_tx": ss_skmem(TX) if mode == "tcp" else None}
    sent = json.loads(sender.stdout.readline())
    sender.wait()
    if mode == "tcp":
        receiver.wait(timeout=90)
    else:
        receiver.wait(timeout=60)
    got = json.loads([line for line in receiver.stdout.read().splitlines() if line.startswith("{")][-1])

    dt = s1["t"] - s0["t"]
    cpu = {c: {k: (s1["cpu"][c][k] - s0["cpu"][c][k]) / CLK_TCK / dt for k in ("busy", "softirq", "system", "user")}
           for c in s0["cpu"]}
    link = {k: s1["link"][k] - s0["link"][k] for k in s0["link"]}
    sender_cpu = (s1["sender_cpu_s"] - s0["sender_cpu_s"]) / dt
    host_tx_cpu = cpu["cpu0"]["busy"]                     # sender process + its softirq (ACKs via RPS)
    rx_cpu = cpu["cpu2"]["busy"] + cpu["cpu3"]["busy"]
    frames_per_s = a.rate
    return {
        "mode": mode, "n": n, "rate": a.rate, "frame_bytes": a.size, "measure_s": round(dt, 3),
        "setup_s": round(setup_s, 3),
        "sender_process_cpu_s_per_s": round(sender_cpu, 5),
        "sender_host_cpu0_busy_s_per_s": round(host_tx_cpu, 5),
        "sender_host_cpu0_softirq_s_per_s": round(cpu["cpu0"]["softirq"], 5),
        "sender_host_us_per_listener_frame": round(host_tx_cpu * 1e6 / (n * frames_per_s), 3),
        "sender_process_us_per_listener_frame": round(sender_cpu * 1e6 / (n * frames_per_s), 3),
        "receivers_cpu23_busy_s_per_s": round(rx_cpu, 5),
        "cpu1_busy_s_per_s": round(cpu["cpu1"]["busy"], 5),
        "wire": {"tx_bytes_per_s": round(link["tx_bytes"] / dt), "tx_packets_per_s": round(link["tx_packets"] / dt),
                 "rx_bytes_per_s": round(link["rx_bytes"] / dt), "rx_packets_per_s": round(link["rx_packets"] / dt),
                 "tx_bytes_per_listener_s": round(link["tx_bytes"] / dt / n, 1),
                 "rx_bytes_per_listener_s": round(link["rx_bytes"] / dt / n, 1),
                 "tx_dropped": link["tx_dropped"]},
        "softnet_drops": s1["softnet_drops"] - s0["softnet_drops"],
        "memory": {"sender_rss_kb": held["sender"]["rss_kb"], "sender_fds": held["sender"]["fds"],
                   "sender_threads": held["sender"]["threads"], "receiver_rss_kb": held["receiver"]["rss_kb"],
                   "slab_delta_kb_both_ends": held["meminfo"]["Slab"] - base["Slab"],
                   "sunreclaim_delta_kb_both_ends": held["meminfo"]["SUnreclaim"] - base["SUnreclaim"],
                   "sockstat_tx": held["sockstat_tx"], "ss_skmem_tx": held["ss_skmem_tx"]},
        "sender": sent, "receiver": got,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ns", type=int, nargs="+", default=[10, 100, 1000, 5000])
    p.add_argument("--modes", nargs="+", default=["tcp", "udp", "mcast"])
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--warmup", type=float, default=5)
    p.add_argument("--measure", type=float, default=20)
    p.add_argument("--rate", type=float, default=10)
    p.add_argument("--size", type=int, default=700)
    p.add_argument("--binary", default=os.path.join(HERE, "fanout", "fanout"))
    p.add_argument("--out", default=os.path.join(HERE, "results", "e2_fanout.json"))
    a = p.parse_args()
    if not os.path.exists(a.binary):
        subprocess.run(["go", "build", "-o", a.binary, "."], cwd=os.path.join(HERE, "fanout"), check=True)
    os.sched_setaffinity(0, {1})      # keep the harness off the measured CPUs
    with open(BACKLOG) as f:
        old_backlog = f.read().strip()
    rows = []
    try:
        with open(BACKLOG, "w") as f:
            f.write("16384")
        idle = _idle(a.measure)
        for rep in range(a.repeats):
            for n in a.ns:
                for mode in a.modes:
                    r = one(a.binary, mode, n, a)
                    r["repeat"] = rep
                    rows.append(r)
                    print(json.dumps({k: r[k] for k in ("mode", "n", "repeat", "sender_host_cpu0_busy_s_per_s",
                                                         "sender_host_us_per_listener_frame", "softnet_drops")}
                                     | {"min_frames": r["receiver"]["min_frames"], "wire": r["wire"]}), flush=True)
    finally:
        with open(BACKLOG, "w") as f:
            f.write(old_backlog)
        teardown()
    stats.write_json(a.out, {"experiment": "e2_fanout", "idle_baseline": idle, "rows": rows,
                             "config": {k: v for k, v in vars(a).items() if k != "out"}, "env": stats.env()})


def _idle(seconds: float) -> dict:
    """Per-CPU busy time with nothing running, to show the floor under every number."""
    c0 = cpu_times()
    time.sleep(seconds)
    c1 = cpu_times()
    return {c: round((c1[c]["busy"] - c0[c]["busy"]) / CLK_TCK / seconds, 5) for c in c0}


if __name__ == "__main__":
    main()
