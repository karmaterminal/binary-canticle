# protocol-dynamics (spike)

A measurement spike for [RFC-0001](../../rfc/0001-binary-canticle.md): **UDP
carousel versus TCP stream** for a lossy, looping, radio-like broadcast to many
listeners. It runs the real canticle Station and Listener from
[`../canticle-station`](../canticle-station/) against TCP senders that carry the
same signed bytes, on one Linux host, under emulated loss and outages. The
results and their reading are in [SUMMARY.md](SUMMARY.md); raw summaries are
in [`results/`](results/).

| # | Script | Question |
|---|---|---|
| E1 | `e1_freshness.py` | How stale is a superseding live-state value at each receiver, under Bernoulli loss (0-30%) and outages (1, 3, 10 s)? Where does TCP's head-of-line blocking and RTO backoff show? |
| E2 | `e2_fanout.py` + `fanout/` (Go) | What does it cost a relay, per listener, to push one 700 B frame at 10 frames/s to N = 10…5 000 listeners over TCP, UDP unicast (sendmmsg) and UDP multicast? |
| E3 | `e3_consumers.py` | What does one slow or dead listener out of 100 do to a TCP sender (blocking, queued, dropping, disconnecting) versus a UDP sender and a UDP lease? |
| E4 | `e4_late_joiner.py` | How long until a late joiner holds all 20 live items: passive carousel, TCP connect + snapshot, or a relay lease + snapshot? |
| E5 | `e5_reconnect_storm.py` | 1 000 listeners after a relay restart: TCP reconnect versus UDP lease re-establishment. |

## Run it

Needs root (network namespaces, nftables, `taskset`), Python 3.11+ with
`cryptography>=45` and `numpy`, and Go ≥ 1.22 for E2.

```sh
cd prototype/protocol-dynamics
python3 -m venv .venv && . .venv/bin/activate && pip install -e ../canticle-station numpy
sudo PYTHON=$PWD/.venv/bin/python ./run_all.sh        # everything, about 50 minutes
sudo PYTHON=$PWD/.venv/bin/python ./run_all.sh e4     # one experiment (e1 … e5)
```

Every script also runs on its own (`--help`). E1 and E4 write one raw file per
condition to `results/raw/` and a collated file to `results/`. Namespaces are
named `pd-*` and are always deleted, also on error; `run_all.sh` deletes any
left over from an interrupted run before it starts.

Code layout:

- `harness/netns.py`: namespaces, nftables loss and outages, `/proc/net/snmp` deltas;
- `harness/arms.py`: the canticle side. `CarouselSender` drives an unmodified
  `canticle.station.Station` over UDP (it is `canticle.runner.run_station` with
  in-process publishing). `UdpListener` feeds an unmodified
  `canticle.listener.Listener`. `frame_for()` signs TCP payloads through the
  same `Station.sing` path;
- `harness/tcpinfo.py`: decodes `struct tcp_info` (RTO, backoff, retransmits, queues);
- `harness/stats.py`: percentiles and testbed facts;
- `fanout/main.go`: the E2 sender and receivers (standard library only; `sendmmsg` via `syscall.Syscall6`).

## Testbed

Measured on 2026-09-27:

- **Host.** Linux 6.18.44, 4 vCPUs, 16 GB, `HZ=250`, tick-based CPU accounting without IRQ-time accounting.
- **Languages.** Python 3.11.15 with cryptography 50.0.1 for the canticle arms and the E1/E3/E4/E5 harness; Go 1.24.7 for the E2 sender and receivers.
- **Network.** One namespace per condition. `lo` runs at MTU 1500, so TCP gets an Ethernet MSS (1448) and Ethernet-sized buffer autotuning (see Limitations). E2 uses two namespaces joined by a veth pair.
- **TCP.** Cubic, set per socket: the host defaults to BBR, and a non-initial namespace may not change its default. TCP_NODELAY on senders, SACK, timestamps, RACK and TLP on. `tcp_retries2=15`, RTO min 200 ms, `tcp_rmem = 4096 131072 33554432`, `tcp_wmem = 4096 16384 4194304`.
- **Loss.** nftables in the namespace's `input` hook: `numgen random mod 1000 < p` on every TCP and UDP packet. On `lo` that hook sees both directions, so TCP ACKs are lost at rate p as well. E1 also has a *data-only* variant that spares packets of 100 IP bytes or less (pure ACKs, SYN, FIN). Outages add and later delete a rule that drops every TCP/UDP packet. The measured drop rate is recorded per condition (`nft.measured_loss`).
- **Timestamps.** Receivers use kernel receive stamps (`SO_TIMESTAMPNS`, CLOCK_REALTIME at `netif_rx`); senders stamp the moment a value changes. Both clocks are on one host.

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
  between arms are what carry over.
- **Loss model.** Bernoulli and independent per packet, except the outages. Real
  radio loss is bursty, and bursts favour the carousel (long gaps) less than
  they hurt TCP (backoff); the outage conditions bracket that case.
- **MTU.** The default `lo` MTU of 65536 gives TCP a 64 KiB MSS. Then one
  retransmission can carry a whole backlog, and the send buffer autotunes
  straight to 4 MiB. An earlier E1 pass at MTU 65536 was discarded for that
  reason.
- **Python harness.** The canticle arms verify an Ed25519 signature on every
  datagram in Python. Medians around 1 ms at 0% loss are harness time (four
  arms publish in turn, in random order), not network time.
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
