# protocol-dynamics (spike)

A measurement spike for [RFC-0001](../../rfc/0001-binary-canticle.md): **UDP
carousel versus TCP stream** for a lossy, looping, radio-like broadcast to many
listeners. It runs the real canticle Station and Listener from
[`../canticle-station`](../canticle-station/) against TCP senders that carry the
same signed bytes, on one Linux host, under emulated loss and outages. The
results and their reading are in [SUMMARY.md](SUMMARY.md); the published runs,
one directory per experiment with its run manifest, are in [`results/`](results/).

| # | Script | Question |
|---|---|---|
| E1 | `e1_freshness.py` | How stale is a superseding live-state value at each receiver, under Bernoulli loss (0-30%) and outages (1, 3, 10 s)? Where does TCP's head-of-line blocking and RTO backoff show? |
| E2 | `e2_fanout.py` + `fanout/` (Go) | What does it cost a relay, per listener, to push one 700 B frame at 10 frames/s to N = 10…5 000 listeners over TCP, UDP unicast (sendmmsg) and UDP multicast? Also: the sender enqueue time for one frame to all N listeners (not arrival: there are no receiver timestamps). |
| E3 | `e3_consumers.py` | What does one slow or dead listener out of 100 do to a TCP sender (blocking, queued, dropping, disconnecting) versus a UDP sender and a UDP lease? |
| E4 | `e4_late_joiner.py` | How long until a late joiner holds all 20 live items: passive carousel, TCP connect + snapshot, or a relay lease + snapshot? |
| E5 | `e5_reconnect_storm.py` | 1 000 listeners after a relay restart: TCP reconnect versus UDP lease re-establishment. |

## Run it

Needs root (network namespaces, nftables, `taskset`), git, Python 3.11+ with
`cryptography>=45` and `numpy`, and Go ≥ 1.22 for E2.

```sh
cd prototype/protocol-dynamics
python3 -m venv .venv && . .venv/bin/activate && pip install -e ../canticle-station numpy
sudo PYTHON=$PWD/.venv/bin/python ./run_all.sh        # everything, about 55 minutes
sudo PYTHON=$PWD/.venv/bin/python ./run_all.sh e4     # one experiment (e1 … e5)
python summarize.py verify                            # check what is published (below)
```

Every script also runs on its own (`--help`).

**Results layout.** Each experiment publishes one directory, a *generation*,
and replaces it as a whole: `results/e1/`, `results/e2/`, `results/e3-slow/`,
`results/e3-dead/`, `results/e4/`, `results/e5/`. A generation holds the
aggregate that `summarize.py` reads (`e1_freshness.json`, `e2_fanout.json`,
`e3_slow.json`, `e3_dead.json`, `e4_late_joiner.json`,
`e5_reconnect_storm.json`), `manifest.json`, and `raw/` with one file per
condition or variant (E2 has none: its aggregate holds every run) and the worker
logs (`*.log`, not in git). `results/e1_freshness.json` is a link to
`results/e1/e1_freshness.json`, kept for `reports/page/figures/make_e1_p99.py`.

**Publication is all or nothing** (`harness/runs.py`). A run writes into a fresh
`results/.staging/<unit>@<run id>/`. Only when every condition exits 0, every
raw file agrees on run id, duration and configuration, and no source file
changed during the run is the staged directory swapped with `results/<unit>/`
in one `renameat2(RENAME_EXCHANGE)`. A crash at any point leaves either the
whole old generation or the whole new one; on a filesystem without
RENAME_EXCHANGE the old directory is renamed aside first and put back by the
next run if the process died in between. A failed run changes nothing under
`results/`, keeps its staged output for inspection, and exits nonzero, as does
`run_all.sh`. A partial run (`e1 … --only`, `e4 … --losses` other than the
default, `e2 … --ns`/`--modes` subsets, `e3 … --duration`) must name its own
`--results-dir`.

**Provenance.** The *sources* of a run are the experiment script,
`harness/*.py`, `../canticle-station/canticle/*.py`, and for E2 `fanout/*.go`
and `fanout/go.mod` (E2 builds its sender from them at launch, into a private
directory, with `-trimpath -buildvcs=false`, and records the binary's sha256).
Every script refuses to start, and publishes nothing, if any source file
differs from HEAD (modified, new or deleted). `--allow-dirty` (also accepted by
`run_all.sh`) runs anyway and embeds the unified diff against HEAD in the
manifest, content-addressed by its sha256, after checking that HEAD plus that
diff rebuilds the working tree's sources exactly. The manifest records the run
id, argv, start and finish times, git commit, `git_dirty`, the sha256 of every
source file and their digest (`source_sha256`: `sha256sum` of the files, sorted
by path from the repository root, then `sha256sum` of that listing), the
configuration and condition list, testbed facts, and the sha256 of every file in
the generation.

```sh
python summarize.py verify                      # every unit: files against manifest, sources against the recorded commit
python summarize.py verify --commit HEAD e1     # recompute the digest from git show HEAD:<path> for each source
```

`verify` exits nonzero on any mismatch. For a dirty run it also reports whether
the commit plus the embedded diff reproduces the recorded digest. Before
printing a unit, `summarize.py` checks its files against its manifest and
refuses a generation that does not match. The generations published before
manifests existed have no `manifest.json`; `summarize.py` marks them
"provenance unknown".

Namespaces are named with a per-run prefix, `PD_NS_PREFIX` (`run_all.sh` sets
`pd<its pid>-`; a script run alone uses `pd<its pid>-`). The harness never
reuses or deletes a namespace it did not create: creation fails if the name
exists, and each script deletes only its own, also on error. `run_all.sh`
records every namespace its run creates and on exit deletes exactly those that
are left (for example after a script was killed). If `run_all.sh` itself is
killed with SIGKILL, remove its leftovers by prefix (`ip netns list`).

Tests that need neither root nor namespaces (Kaplan–Meier, E1 censoring, E4
lease keying, namespace ownership, the staging and failure rules, dirty-tree
refusal, the embedded diff, a source change during a run, verification against
a commit, a crash injected at every filesystem step of publication, E2 costs
that are never negative):

```sh
PYTHONPATH=../canticle-station python -m unittest discover -s tests -v
```

Code layout:

- `harness/netns.py`: namespaces, nftables loss and outages, `/proc/net/snmp` deltas;
- `harness/arms.py`: the canticle side. `CarouselSender` drives an unmodified
  `canticle.station.Station` over UDP (it is `canticle.runner.run_station` with
  in-process publishing). `UdpListener` feeds an unmodified
  `canticle.listener.Listener`. `frame_for()` signs TCP payloads through the
  same `Station.sing` path;
- `harness/tcpinfo.py`: decodes `struct tcp_info` (RTO, backoff, retransmits, queues);
- `harness/stats.py`: percentiles, Kaplan–Meier quantiles for right-censored
  durations (with a self-check against a hand-computed example), testbed facts;
- `harness/runs.py`: source digests and the dirty-tree rule, staging, atomic
  publication, the run manifest and `verify`, for every experiment;
- `fanout/main.go`: the E2 sender and receivers (standard library only; `sendmmsg` via `syscall.Syscall6`).

## Testbed

Measured on 2026-09-27:

- **Host.** Linux 6.18.44, 4 vCPUs, 16 GB, `HZ=250`, tick-based CPU accounting without IRQ-time accounting.
- **Languages.** Python 3.11.15 with cryptography 50.0.1 for the canticle arms and the E1/E3/E4/E5 harness; Go 1.24.7 for the E2 sender and receivers.
- **Network.** One namespace per condition. `lo` runs at MTU 1500, so TCP gets an Ethernet MSS (1448) and Ethernet-sized buffer autotuning (see Limitations). E2 uses two namespaces joined by a veth pair.
- **TCP.** Cubic, set per socket: the host defaults to BBR, and a non-initial namespace may not change its default. TCP_NODELAY on senders, SACK, timestamps, RACK and TLP on. `tcp_retries2=15`, RTO min 200 ms, `tcp_rmem = 4096 131072 33554432`, `tcp_wmem = 4096 16384 4194304`.
- **Loss.** nftables in the namespace's `input` hook: `numgen random mod 1000 < p` on every TCP and UDP packet. On `lo` that hook sees both directions, so TCP ACKs are lost at rate p as well. E1 also has a *data-only* variant that spares packets of 100 IP bytes or less (pure ACKs, SYN, FIN). Outages add and later delete a rule that drops every TCP/UDP packet. The measured drop rate is recorded per condition (`nft.measured_loss`).
- **Timestamps.** Receivers use kernel receive stamps (`SO_TIMESTAMPNS`, CLOCK_REALTIME at `netif_rx`); senders stamp the moment a value changes. Both clocks are on one host.
- **Receiver warm-up.** Receiver warm-up (RFC-0001 §7.8 rule 4) is disabled in the experiment listeners: they measure transport freshness and catch-up; a receptor with warm-up on adds up to one advertised loop before a live-state key is surfaced after it starts.
- **E2 CPU cost.** Per listener and frame = (CPU 0 busy, loaded − CPU 0 busy, matched idle) / (N × frames/s). Each repeat runs one block per N: an idle window (same namespaces, veth, RPS, warm-up and window, nothing running) and the three loaded runs, in a shuffled order. The cost is the mean over repeats with a 95% t-interval, never narrower than the two-tick quantum of CPU accounting (`/proc/stat` counts 1/100 s ticks), reported only when the interval lies above 0; otherwise it is *not resolved* at that N and the interval's half-width is given instead. No cost is negative and none is clamped. The E2 data published before this (one unmatched idle sample before all runs) is analysed the same way and marked as unmatched.

## Limitations

- **No delay emulation.** netem is not in this kernel. RTT on `lo` is tens to a
  hundred-odd microseconds (SRTT 50-150 µs in `tcp_info`), so every TCP
  recovery number here is the *floor* set by Linux's timers: RTO =
  SRTT + max(200 ms, 4·RTTVAR), and a tail-loss probe with one packet in flight
  also waits about 200 ms. SUMMARY.md has an analytic note on what 20-200 ms
  internet RTTs change. The UDP carousel's repair times are schedule-bound
  (+1, +2, +4 s, then the loop) and do not depend on RTT.
- **One host.** Sender and receivers share CPUs, memory and one kernel. E2 uses
  RPS and CPU pinning to keep receive-side work off the sender's CPU (details
  in `e2_fanout.py`). Its absolute CPU numbers are for this VM; the ratios
  between arms are what carry over. With tick-based accounting (HZ 250) and
  about 1% of background load on CPU 0, a 20 s window cannot resolve the few
  µs per listener that N ≤ 100 costs; E2 reports those as not resolved.
- **Loss model.** Bernoulli and independent per packet, except the outages. Real
  radio loss is bursty, and bursts favour the carousel (long gaps) less than
  they hurt TCP (backoff); the outage conditions bracket that case.
- **MTU.** The default `lo` MTU of 65536 gives TCP a 64 KiB MSS. Then one
  retransmission can carry a whole backlog, and the send buffer autotunes
  straight to 4 MiB. An earlier E1 pass at MTU 65536 was discarded for that
  reason.
- **Censoring.** In E1 an update a receiver had not caught up to when the run
  ended (20 s after the last update) has no observed latency, only a lower
  bound; the same holds for outage recovery and for E4 joins that timed out or
  were cut off by the end of the run. These are right-censored: latency
  quantiles are Kaplan–Meier estimates, reported next to the delivered
  fraction, and a quantile the estimate never reaches is reported as beyond
  the largest time observed (delivered latency or censoring time). Kaplan–Meier assumes that when a sample is censored
  says nothing about its latency. Here censoring is set by issue time, but
  under TCP's long stalls consecutive updates share one stall, so the tails
  are estimates, not exact percentiles. The time-weighted staleness measures
  need no such correction: they are the state of each receiver at each instant.
- **Python harness.** The canticle arms verify an Ed25519 signature on every
  datagram in Python. Medians around 1 ms at 0% loss are harness time (four
  arms publish in turn, in random order), not network time.
- **E5 lease keying.** E5's `udp_relay` still keys leases by source address,
  which E4's relay no longer does (a lost BYE there hid the next session's
  snapshot). It cannot trigger in E5, which has no loss and one session per
  listener per relay, but key by session nonce before E5 is extended.
- **E5.** Python relays and 1 000 Python clients in one process each: the
  kernel effects (listen-queue overflow, SYN retransmission at 1 s, SYN-cookie
  half-open connections, beacon timeouts) carry over, but absolute recovery
  times include Python. `asyncio.start_server(sock=...)` re-calls `listen()`
  with its own default backlog of 100, so the relay passes the backlog
  explicitly.
- **E5 syscalls.** The relay's syscall counts come from a separate
  `strace -c -f` pass attached for the recovery only, which is not timed:
  strace slows every syscall, and in that pass the UDP relay's receive buffer
  overflowed.
- The nftables rule is per packet and cannot express per-flow burstiness,
  asymmetric loss by host, or reordering.
