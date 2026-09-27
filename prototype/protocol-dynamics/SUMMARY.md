# protocol-dynamics: results

Measured on 2026-09-27 on one Linux 6.18 host (4 vCPUs). Every condition ran in
its own network namespace; loss was dropped by nftables in both directions
unless marked *data-only*. There is no delay emulation, so RTT is about 0.1 ms
and every TCP recovery time below is the floor set by Linux's timers (see
[What internet RTTs change](#what-internet-rtts-change)). Testbed, method and
limitations are in [README.md](README.md). All numbers come from
`results/*.json`, and `python summarize.py` prints these tables.

**Revision after review.** E1 and E4 were re-run with a corrected harness; E2,
E3 and E5 were not re-run.
- E1 used to count an update that had not reached a receiver by the end of the
  run as if it had arrived then, and summarised that lower bound as a latency.
  At U = 0.5 s and 30% loss that was 24 217 of 35 800 TCP samples, so the
  reported median of 187 s was not an observed latency. Latencies are now
  Kaplan–Meier estimates, with the delivered share and the censored count
  beside them.
- The E4 relay keyed leases by address. A new session whose predecessor's BYE
  had been lost got no snapshot (560 snapshots for 591 lease joins at 5% loss,
  117 for 160 at 30%). It now keys leases by session and snapshots every one.
  E4 joins that time out or are cut off by the end of the run are now censored
  rather than dropped.
- E2's "fan-out spread" was the sender's enqueue time and is now named so.
- Run ids, the git commit and a source hash are in the `manifest` of
  `results/e1_freshness.json` and `results/e4_late_joiner.json`.

## Bottom line

- **At low loss (≤ 10%) on a healthy connection, TCP keeps a receiver fresher than the carousel.**
  TCP repairs a lost update in one RTO, about 205-212 ms here. The carousel waits for its next copy: the +1 s burst, or the next update.
  - U = 10 s, 5% loss: p99 212 ms (TCP) against 1 004-1 006 ms (UDP).
  - U = 2 s, 10% loss: TCP holds a superseded value 1.3% of the time, UDP 5.4-5.5%.
- **TCP's failure mode is an unbounded tail; the carousel's is bounded.**
  - At 30% loss in both directions, TCP's RTO reached the 120 s cap. Single stalls lasted up to 576 s, and head-of-line blocking queues every superseded value behind the stall.
  - U = 0.5 s, 30% loss: when the run ended, 20 s after the last update, only 29% of (update, receiver) pairs had reached a TCP receiver. The median latency is therefore beyond 914 s, the longest the run could observe. Receivers held a stale value 90% of the time, and 2 698 frames arrived after their own signed expiry.
  - The carousel at the same point delivered every update: p99 1.5 s, max 3.5-4.5 s, stale 30% of the time, which is the loss rate.
  - With ACKs spared (data-only loss), TCP at 30% delivered every update: p99 0.86-16 s. Its slowest update still took 3.4-108 s, against 4.5-11 s for the carousel.
- **After outages, TCP resumes late.**
  - After a 10 s outage, TCP needed p95 3.9-6.3 s to deliver the newest value. That is RTO backoff: 408 → 816 → 1 632 → 3 264 → 6 528 ms.
  - The carousel needed p95 0.47-0.91 s with frequent updates, and 1.72 s (1 s loop) or 5.14 s (5 s loop) at U = 10 s.
  - After 1-3 s outages the two are comparable.
- **Fan-out (E2): TCP costs about 2.7× more CPU per listener than UDP unicast.**
  - Per listener and frame: TCP 11.6-12.0 µs of sending-host CPU (the write plus the ACK it triggers), UDP with `sendmmsg` 4.2-4.4 µs. Multicast stays at about 2% of a core whatever N.
  - At 5 000 listeners × 10 frames/s: 60.7% against 22.0% of a vCPU.
  - TCP also doubles the packets (one ACK per segment) and needs 5 006 fds against 6.
  - Handing one frame to the kernel for all 5 000 listeners took the TCP sender 56.7 ms (median), against 18.4 ms with `sendmmsg`. That is sender enqueue time; when the last listener received the frame was not measured.
  - Either is feasible; the difference is cost per listener, not whether it works.
- **Slow and dead consumers (E3).**
  - With a blocking writer, one listener that stops reading stalls all 100, 29 s after it stops (64 KiB buffers).
  - With Linux's autotuned receive buffer the sender never notices: after 590 s the reader held 4.1 MB of unread, 10-minute-old data.
  - A silently vanished TCP listener is aborted only after 938 s. Meanwhile an unbounded queue grew to 6.5 MB and the kernel retransmitted 16 times. TCP_USER_TIMEOUT = 30 s cut that to 30.4 s.
  - UDP: the slow socket overflowed alone (5 863 drops), and a dead lease lapsed after 54-74 s with no retransmission and no per-listener buffer.
- **Late joiners (E4).**
  - At 0% loss TCP connect-plus-snapshot is by far the fastest: 0.5 ms p50, against 1.1 s for a 1 s carousel and 14.6 s at the default 4 kbit/s budget.
  - At 30% loss, SYN loss hurts TCP: p50 2.1 s, p90 36 s, and 17 of 360 joins not done in 120 s, so its p99 lies beyond 120 s. The 1 s carousel does 2.9 s p50 and 6.6 s p99, with no failures.
- **Relay restart (E5).**
  - TCP notices a restarted relay at once. With a 4 096 backlog, 1 000 listeners were re-served 0.30-0.33 s after the kill.
  - With a backlog of 128, accept-queue overflow and SYN retransmits stretched that to 6.3 s. SYN-cookie half-open connections hang forever without a client timeout.
  - UDP leases took 13.2 s every time: a restarted relay cannot validate old cookies, stays silent, and listeners wait out three missed relay beacons.

**Recommendation in one line:**
- Keep the UDP carousel for the binary plane at the edge, where loss, outages, many listeners and misbehaving listeners are expected.
- Use TCP or QUIC streams where one healthy, low-loss link carries each item once: relay to relay, ledger and control, and snapshot and replay for dashboards.
- Details are in [Recommendation by plane](#recommendation-by-plane).

## E1: freshness and head-of-line blocking

**Setup.**
- A live-state value is updated every U seconds, and each update supersedes the last.
- Four arms run side by side in one namespace, each with 20 receivers:
  - `udp-live`: the real Station and Listener, keyed live-state item, `loop="fast"`, which is a 5 s loop.
  - `udp-ctl`: the same on a control-class stream, which is a 1 s loop.
  - `tcp-stream`: every update, in order, with TCP_NODELAY.
  - `tcp-latest`: TCP_NOTSENT_LOWAT = 1; the sender keeps only the newest unsent value.
- Frames are 329 B, signed and verified.
- Each condition ran 900 s: 1 800, 450 or 90 updates for U = 0.5, 2 or 10 s, times 20 receivers. Updates in the first 5 s are excluded.

Definitions:
- *Update latency*: time from the moment a value changes until a receiver holds it or anything newer.
  - An (update, receiver) pair that had not caught up when the run ended (20 s after the last update) has no latency, only a lower bound. It is *censored*.
  - *Delivered* is the share of pairs that did catch up before the run ended.
  - Latency quantiles are Kaplan–Meier estimates over all pairs, delivered and censored. Where the estimate never reaches a quantile, the table shows "> X": X is the largest time the cell observed (the longest delivered latency or censoring time), and the quantile lies beyond it.
  - Kaplan–Meier assumes censoring says nothing about a pair's latency. Here it is set by issue time, but under TCP's long stalls consecutive updates share one stall, so read high quantiles as estimates.
- *Stale %*: fraction of time a receiver holds a value that has already been superseded, sampled every 5 ms.
- *Staleness max*: the longest time any receiver held a value after it had been superseded. Like stale %, it is the receiver's state at each instant and needs no censoring correction.
- *Outages* were placed so that one update is issued inside each. Recovery that had not happened when the run ended is censored in the same way.

**U = 0.5 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.1 / 2.7 | 2.1 / 2.7 | 1.9 / 2.7 | 1.8 / 2.3 | 0.20 / 0.20 / 0.19 / 0.20 | 12.1 / 12.1 / 12.1 / 95.4 |
| 1% | 1.0% | 2.2 / 499.7 | 2.2 / 498.6 | 1.9 / 205.6 | 2.0 / 205.7 | 1.28 / 1.23 / 0.64 / 0.65 | 1000.7 / 1000.5 / 417.6 / 415.9 |
| 5% | 5.0% | 496.1 / 502.3 | 8.8 / 502.3 | 11.6 / 212.1 | 204.8 / 212.0 | 5.27 / 5.05 / 2.43 / 2.52 | 1499.7 / 1504.0 / 1476.9 / 1688.8 |
| 10% | 9.9% | 501.2 / 504.7 | 501.2 / 507.0 | 209.0 / 418.1 | 209.2 / 418.1 | 10.26 / 9.82 / 5.68 / 5.66 | 2002.5 / 2500.4 / 6205.8 / 3487.4 |
| 20% | 19.9% | 502.7 / 1002.7 | 502.7 / 1003.0 | 3282.4 / 44.9 s · 99.19% delivered | 2373.0 / 21.0 s · 99.70% delivered | 20.00 / 20.40 / 22.48 / 21.07 | 3498.9 / 3497.0 / 146.0 s / 56.6 s |
| 30% | 30.0% | 1001.2 / 1502.1 | 1001.1 / 1501.7 | > 914.5 s / > 914.5 s · 29.22% delivered | 397.8 s / > 508.5 s · 88.41% delivered | 30.41 / 30.18 / 90.16 / 78.43 | 3500.7 / 4499.5 / 897.5 s / 488.5 s |

**U = 2 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.0 / 2.4 | 2.1 / 2.7 | 1.8 / 3.1 | 1.8 / 3.0 | 0.05 / 0.05 / 0.05 / 0.05 | 5.8 / 3.6 / 5.8 / 5.8 |
| 1% | 1.0% | 2.2 / 4.4 | 2.2 / 1000.5 | 1.9 / 205.4 | 1.9 / 206.0 | 0.52 / 0.58 / 0.15 / 0.16 | 1009.9 / 1998.9 / 419.5 / 212.2 |
| 5% | 5.0% | 1000.5 / 1005.5 | 7.0 / 1004.9 | 5.0 / 210.6 | 3.2 / 210.7 | 2.80 / 2.69 / 0.59 / 0.57 | 3001.5 / 3005.6 / 655.8 / 828.9 |
| 10% | 10.1% | 1002.1 / 1007.8 | 1002.0 / 1999.9 | 207.0 / 414.2 | 206.9 / 413.6 | 5.41 / 5.45 / 1.31 / 1.28 | 3998.4 / 3998.4 / 4858.2 / 1692.2 |
| 20% | 19.9% | 1005.8 / 2002.6 | 1007.1 / 2004.2 | 415.1 / 2663.7 | 415.0 / 2732.0 · 99.96% delivered | 12.20 / 12.07 / 4.25 / 4.22 | 4000.8 / 7003.7 / 24.8 s / 24.7 s |
| 30% | 30.2% | 2001.4 / 3005.2 | 2001.6 / 3006.4 | > 758.0 s / > 758.0 s · 90.21% delivered | 76.7 s / 233.2 s · 98.36% delivered | 19.52 / 20.22 / 31.78 / 22.93 | 6996.7 / 8000.4 / 738.0 s / 333.2 s |

**U = 10 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 1.9 / 3.0 | 2.1 / 4.3 | 1.9 / 2.8 | 1.8 / 3.3 | 0.01 / 0.01 / 0.01 / 0.01 | 1.8 / 1.9 / 1.8 / 1.8 |
| 1% | 1.0% | 1.9 / 2.7 | 1.8 / 2.5 | 1.8 / 2.2 | 1.7 / 205.3 | 0.11 / 0.11 / 0.02 / 0.04 | 1002.1 / 2001.6 / 208.8 / 209.5 |
| 5% | 5.0% | 1000.7 / 1006.3 | 5.8 / 1003.8 | 205.0 / 211.9 | 5.5 / 212.0 | 0.59 / 0.50 / 0.13 / 0.11 | 2010.6 / 2002.1 / 415.7 / 422.5 |
| 10% | 10.1% | 1002.1 / 1015.1 | 1002.2 / 1005.5 | 207.1 / 219.0 | 209.7 / 413.8 | 1.15 / 1.03 / 0.23 / 0.27 | 9999.5 / 2003.7 / 1477.1 / 1478.1 |
| 20% | 20.2% | 1007.7 / 2009.6 | 1005.3 / 2016.0 | 220.0 / 826.3 | 217.5 / 648.6 | 2.80 / 2.49 / 0.63 / 0.64 | 9995.3 / 6264.0 / 3512.3 / 3497.2 |
| 30% | 29.9% | 2001.8 / 4002.3 | 2002.4 / 4006.5 | 830.6 / 68.0 s | 14.7 s / > 380.0 s · 97.58% delivered | 4.47 / 4.83 / 3.65 / 6.70 | 11.0 s / 7433.0 / 203.0 s / 360.0 s |

**Data-only loss** (pure ACKs, SYN and FIN spared). Update latency, Kaplan–Meier p95 / p99 in ms, delivered share where below 100%; staleness max in arm order.

| U | loss | udp-live | udp-ctl | tcp-stream | tcp-latest | staleness max |
|---|---|---|---|---|---|---|
| 0.5 s | 10% | 501.2 / 505.6 | 501.2 / 503.9 | 206.8 / 414.1 | 206.8 / 413.9 | 1998.2 / 2002.3 / 3342.8 / 1677.7 |
| 0.5 s | 20% | 502.7 / 1002.8 | 502.4 / 1002.2 | 349.6 / 838.8 | 354.9 / 854.3 | 3495.4 / 3498.7 / 13.3 s / 26.6 s |
| 0.5 s | 30% | 1001.5 / 1502.4 | 1001.4 / 1502.5 | 985.6 / 6613.7 | 1126.4 / 16.3 s | 4496.3 / 3501.1 / 108.2 s / 106.4 s |
| 2 s | 10% | 1002.1 / 2000.0 | 1002.2 / 1983.6 | 207.5 / 219.7 | 207.6 / 414.2 | 3005.8 / 4999.1 / 1486.1 / 1483.0 |
| 2 s | 20% | 1006.7 / 2002.7 | 1006.6 / 2002.6 | 217.4 / 661.4 | 217.7 / 657.6 | 5999.5 / 5005.0 / 6720.1 / 6622.0 |
| 2 s | 30% | 2001.4 / 3005.1 | 2001.4 / 3004.5 | 420.3 / 1672.1 | 424.1 / 1688.2 | 7000.8 / 10.0 s / 54.5 s / 13.3 s |
| 10 s | 10% | 1002.3 / 1006.0 | 1001.9 / 2001.3 | 207.4 / 215.5 | 207.5 / 219.7 | 4003.6 / 5279.4 / 1470.4 / 841.8 |
| 10 s | 20% | 1009.8 / 4000.7 | 1007.9 / 2006.9 | 220.6 / 632.6 | 216.5 / 424.6 | 12.0 s / 5124.7 / 6676.4 / 1669.6 |
| 10 s | 30% | 2003.1 / 4113.7 | 2003.4 / 4005.3 | 420.2 / 1485.8 | 419.9 / 860.4 | 11.0 s / 6250.9 / 53.4 s / 3355.0 |

**Outages.** Recovery after the outage ends (time until the receiver holds the newest value), Kaplan–Meier p50 / p95, with the number of (outage, receiver) pairs not recovered by the end of the run where nonzero · Kaplan–Meier median latency of updates issued inside the outage, ms. 20 receivers per arm.

| outage | U | outages | udp-live | udp-ctl | tcp-stream | tcp-latest |
|---|---|---|---|---|---|---|
| 1 s | 0.5 s | 54 | 243.7 / 444.6 · 905.4 | 243.7 / 445.3 · 904.8 | 239.8 / 815.7 · 845.0 | 239.7 / 815.7 · 845.0 |
| 1 s | 2 s | 50 | 503.1 / 884.3 · 1001.9 | 503.2 / 890.3 · 1002.2 | 139.6 / 787.3 · 834.7 | 139.5 / 787.4 · 834.7 |
| 1 s | 10 s | 45 | 567.7 / 899.6 · 1001.8 | 567.8 / 899.2 · 1001.6 | 155.7 / 755.7 · 841.7 | 155.6 / 755.7 · 841.8 |
| 3 s | 0.5 s | 46 | 273.3 / 449.6 · 1999.3 | 273.1 / 449.8 · 1998.8 | 599.9 / 775.7 · 1865.8 | 649.6 / 805.6 · 1900.4 |
| 3 s | 2 s | 44 | 533.2 / 891.9 · 2001.6 | 534.0 / 892.5 · 2001.9 | 703.5 / 1375.9 · 1685.8 | 703.6 / 1375.9 · 1685.8 |
| 3 s | 10 s | 40 | 634.0 / 1751.7 · 2002.0 | 634.1 / 1751.2 · 2002.0 | 567.7 / 1571.5 · 1688.1 | 567.7 / 1571.5 · 1688.2 |
| 10 s | 0.5 s | 30 | 249.1 / 473.0 · 5500.1 | 248.7 / 473.2 · 5500.2 | 3612.4 / 3912.3 · 8803.3 | 3746.7 / 4014.7 · 8915.7 |
| 10 s | 2 s | 29 | 423.8 / 912.6 · 5999.6 | 423.7 / 913.4 · 6000.0 | 4327.9 / 5087.7 · 9403.3 | 4359.5 / 5119.9 · 9451.8 |
| 10 s | 10 s | 26 | 877.7 / 5136.9 · 4031.3 | 781.9 / 1717.6 · 4031.2 | 1063.5 / 6263.9 · 6706.3 | 1063.5 / 6263.9 · 6706.2 |

**TCP pathologies** (20 connections per arm, 900 s).
- *superseded*: frames delivered after a newer value was already issued.
- *expired*: frames delivered after their signed `expires_at`; a receiver must drop them.
- *censored*: (update, receiver) pairs never caught up by the end of the run; *delivered* is the rest, as a share.
- *longest*: the longest stretch with an unacknowledged retransmission (TCP_INFO, 20 ms sampling). "≥ … (open at end)" marks a stretch still open when the run ended.

| U | loss dir | loss | arm | superseded | expired | censored | delivered | max backoff | longest | retrans (sum) | resets |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 s | both | 10% | tcp-stream | 234 | 0 | 0 | 100.00% | 4 | 6.4 s | 8403 | 0 |
| 0.5 s | both | 10% | tcp-latest | 163 | 0 | 0 | 100.00% | 3 | 3.0 s | 8184 | 0 |
| 0.5 s | both | 20% | tcp-stream | 4110 | 0 | 289 | 99.19% | 7 | 56.3 s | 17920 | 0 |
| 0.5 s | both | 20% | tcp-latest | 1214 | 0 | 109 | 99.70% | 8 | ≥ 58.6 s (open at end) | 17797 | 0 |
| 0.5 s | both | 30% | tcp-stream | 5223 | 2698 | 25340 | 29.22% | 10 | ≥ 456.6 s (open at end) | 5311 | 0 |
| 0.5 s | both | 30% | tcp-latest | 1949 | 11 | 4150 | 88.41% | 11 | 459.8 s | 10473 | 0 |
| 0.5 s | data-only | 10% | tcp-stream | 97 | 0 | 0 | 100.00% | 3 | 2.9 s | 4015 | 0 |
| 0.5 s | data-only | 10% | tcp-latest | 72 | 0 | 0 | 100.00% | 2 | 1.3 s | 3997 | 0 |
| 0.5 s | data-only | 20% | tcp-stream | 683 | 0 | 0 | 100.00% | 5 | 13.1 s | 9001 | 0 |
| 0.5 s | data-only | 20% | tcp-latest | 590 | 0 | 0 | 100.00% | 6 | 26.2 s | 8954 | 0 |
| 0.5 s | data-only | 30% | tcp-stream | 3230 | 0 | 0 | 100.00% | 8 | 107.8 s | 14929 | 0 |
| 0.5 s | data-only | 30% | tcp-latest | 1937 | 0 | 0 | 100.00% | 8 | 106.0 s | 14822 | 0 |
| 2 s | both | 10% | tcp-stream | 2 | 0 | 0 | 100.00% | 4 | 6.4 s | 2191 | 0 |
| 2 s | both | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 2152 | 0 |
| 2 s | both | 20% | tcp-stream | 93 | 0 | 0 | 100.00% | 6 | 26.4 s | 4930 | 0 |
| 2 s | both | 20% | tcp-latest | 35 | 0 | 4 | 99.96% | 7 | ≥ 27.6 s (open at end) | 5024 | 0 |
| 2 s | both | 30% | tcp-stream | 1309 | 472 | 875 | 90.21% | 12 | 576.4 s | 7056 | 0 |
| 2 s | both | 30% | tcp-latest | 172 | 3 | 147 | 98.36% | 10 | 334.8 s | 7985 | 0 |
| 2 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 995 | 0 |
| 2 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 1006 | 0 |
| 2 s | data-only | 20% | tcp-stream | 6 | 0 | 0 | 100.00% | 4 | 6.3 s | 2324 | 0 |
| 2 s | data-only | 20% | tcp-latest | 7 | 0 | 0 | 100.00% | 4 | 6.4 s | 2363 | 0 |
| 2 s | data-only | 30% | tcp-stream | 64 | 0 | 0 | 100.00% | 7 | 54.3 s | 3774 | 0 |
| 2 s | data-only | 30% | tcp-latest | 55 | 0 | 0 | 100.00% | 5 | 13.1 s | 3906 | 0 |
| 10 s | both | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 433 | 0 |
| 10 s | both | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 429 | 0 |
| 10 s | both | 20% | tcp-stream | 0 | 0 | 0 | 100.00% | 5 | 13.1 s | 1033 | 0 |
| 10 s | both | 20% | tcp-latest | 0 | 0 | 0 | 100.00% | 5 | 13.1 s | 1024 | 0 |
| 10 s | both | 30% | tcp-stream | 37 | 3 | 0 | 100.00% | 9 | 212.6 s | 1899 | 0 |
| 10 s | both | 30% | tcp-latest | 9 | 1 | 43 | 97.58% | 11 | ≥ 389.8 s (open at end) | 1791 | 0 |
| 10 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 182 | 0 |
| 10 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 1 | 0.4 s | 184 | 0 |
| 10 s | data-only | 20% | tcp-stream | 0 | 0 | 0 | 100.00% | 4 | 6.3 s | 496 | 0 |
| 10 s | data-only | 20% | tcp-latest | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 424 | 0 |
| 10 s | data-only | 30% | tcp-stream | 5 | 0 | 0 | 100.00% | 7 | 53.2 s | 777 | 0 |
| 10 s | data-only | 30% | tcp-latest | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 784 | 0 |

**Reading.**

1. **Where TCP is better.** Up to 10% loss, and at 20% when updates are sparse (U = 10 s), TCP beats the carousel on p99 and on stale time.
   - At 1% loss only the stale time differs clearly: the p99 sits at the edge of the 1% of updates that need a repair. Medians are 0.9-1.3 ms in every arm up to 10% loss, which is harness time.
   - One lost segment costs one RTO: 205-212 ms here. This kernel arms RTO = SRTT + max(200 ms, 4·RTTVAR) at HZ 250, and with one packet in flight a tail-loss probe waits just as long.
   - The carousel's first repair is the burst copy 1 s later, or the next update when that comes first (U = 0.5 s). So its p99 sits near 500 or 1 000 ms wherever TCP's is near 210 ms.
   - This per-item repair-latency advantage of one reliable connection is real.
2. **Where TCP breaks.**
   - With loss in both directions, a retransmission and its ACK both have to survive, so each attempt fails 36% of the time at 20% loss and 51% at 30%.
   - Linux doubles the RTO on each failure, up to 120 s. At 30% the RTO reached that cap in five of the six TCP cells; in the sixth (U = 10 s, `tcp-stream`) its five longest episodes reached 104 s. At 20% the five longest episodes per cell reached 6.5-52 s. Timestamp echo during loss also inflates SRTT: TCP_INFO showed a 120 s RTO at backoff 0 (U = 0.5 s, 30%, connection 0).
   - Every update queues behind the head of line. The result:
     - multi-minute stalls; the longest episode was 576.4 s, and at U = 0.5 s, 30% ten of the twenty `tcp-stream` connections were still in one when the run ended;
     - at U = 0.5 s, 30%, only 29% of (update, receiver) pairs were delivered before the run ended, 20 s after the last update, so even the median latency lies beyond the 914 s the run could observe; at U = 2 s, 30%, 90% were delivered and the p95 lies beyond 758 s;
     - 2 698 frames delivered after their signed `expires_at` (U = 0.5 s, 30%);
     - 54% of `tcp-stream` deliveries at U = 0.5 s, 30% were already superseded on arrival.
   - No connection reset: `tcp_retries2` = 15 allows about 924 s, and some ACK always got through first.
   - The carousel's worst case is set by its schedule, not its history: 3.5-4.5 s (U = 0.5 s) and 11.0 s (U = 10 s, 5 s loop) even at 30%, with every update delivered.
3. **ACK loss is most of the damage.** With data-only loss, TCP at 30% delivered every update, with a p99 of 0.86-16 s instead of minutes or never. Radio links usually lose in both directions; wired internet paths often do not.
4. **Latest-only does not fix head-of-line blocking.**
   - `tcp-latest` removes most backlog replay: after 10 s outages at U = 0.5 s it delivered 1 300 superseded frames against 15 440.
   - It does not shorten the stall, because the in-flight segment must still be retransmitted first.
   - At high loss it delivered more than `tcp-stream` at U = 0.5-2 s (30%: 88-98% against 29-90%), but its tail was sometimes worse: U = 10 s, 30%, p99 beyond 380 s with 2.4% of pairs undelivered, against 68.0 s. A thinner stream has fewer segments in flight, so fast recovery triggers less and more losses need an RTO.
   - Tails at ≥ 20% come from a few backoff episodes per run and vary between runs: `tcp-latest` at U = 0.5 s, 20% had a p99 of 155 s in the first run and 21.0 s in this one. Read them as orders of magnitude.
5. **The class floor is a real but narrow knob.**
   - The 0 / +1 / +2 / +4 s burst does almost all repair for new updates, so the 1 s and 5 s loops look alike under Bernoulli loss.
   - The floor matters once the burst has failed:
     - 10 s outage at U = 10 s: p95 recovery 1.72 s against 5.14 s;
     - U = 10 s, 30% loss: longest staleness 7.4 s against 11.0 s;
     - late joiners (E4).
   - It costs bandwidth: at U = 10 s the carousel sent 4.82 (5 s loop) or 9.58 (1 s loop) copies per update per listener. That is 305-459 B/s per listener including the 1 Hz beacon, against 33 B/s of TCP payload.

## E2: fan-out cost to N listeners

**Setup.**
- A Go sender (standard library; `sendmmsg` through `syscall.Syscall6`) pushes one 700 B frame at 10 frames/s.
- The sender runs in its own namespace (`<prefix>e2-tx`), pinned to CPU 0. The N listeners are one Go process in a second namespace (`<prefix>e2-rx`), pinned to CPUs 2-3.
- A veth pair joins the namespaces, and its counters are the wire.
- RPS steers listener-side receive work to CPUs 2-3 and returning ACKs to CPU 0. CPU 0's busy time is therefore the sending host's whole cost: the process plus the ACK softirq.
- Multicast: N sockets in the receiver process, each joined to 239.255.13.13 on the veth.
- Each row is the mean of 3 runs of 20 s after a 5 s warm-up.
- Every listener received all 280 frames in every run.
- Nothing was dropped in the RPS backlog. `netdev_max_backlog` was raised to 16 384 for the run and restored afterwards.

Idle baseline, CPU 0: 0.85% busy. Mean of 3 runs (min–max); 20 s windows after 5 s warm-up. *µs per listener·frame* = (CPU 0 busy − idle) / (N × 10). *Sender enqueue time* = how long the sender's loop took to hand one frame to the kernel for all N listeners (sender clock); when the last listener received it was not measured.

| mode | N | sender host CPU % (CPU 0) | sender process CPU % | µs per listener·frame | wire out kB/s | wire in kB/s | pkts/s out / in | sender RSS kB | sender fds | syscalls/frame | sender enqueue time, one frame to all N, p50 ms | min frames/listener | backlog drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mcast | 10 | 1.02 (0.90–1.15) | 0.22 (0.20–0.25) | 16.67 (5.00–30.00) | 7.4 | 0.0 | 10 / 0 | 4548 | 6 | 1 | 0.05 | 280 | 0 |
| tcp | 10 | 1.02 (0.70–1.30) | 0.28 (0.25–0.30) | 16.67 (-15.00–45.00) | 76.6 | 6.6 | 100 / 100 | 4560 | 16 | 10 | 0.11 | 280 | 0 |
| udp | 10 | 1.12 (0.45–2.10) | 0.28 (0.25–0.30) | 26.67 (-40.00–125.00) | 74.2 | 0.0 | 100 / 0 | 4432 | 6 | 1 | 0.10 | 280 | 0 |
| mcast | 100 | 0.90 (0.60–1.10) | 0.20 (0.20–0.20) | 0.50 (-2.50–2.50) | 7.4 | 0.0 | 10 / 0 | 4420 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 100 | 1.13 (0.60–1.50) | 1.23 (1.20–1.25) | 2.83 (-2.50–6.50) | 765.9 | 66.0 | 1000 / 1000 | 4692 | 106 | 100 | 1.03 | 280 | 0 |
| udp | 100 | 0.57 (0.40–0.75) | 0.57 (0.55–0.60) | -2.83 (-4.50–-1.00) | 745.6 | 0.0 | 1005 / 0 | 4428 | 6 | 1 | 0.38 | 280 | 0 |
| mcast | 1000 | 1.55 (1.20–2.00) | 0.20 (0.15–0.25) | 0.70 (0.35–1.15) | 7.4 | 0.0 | 10 / 0 | 4424 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 1000 | 12.48 (11.70–13.00) | 11.98 (11.75–12.35) | 11.63 (10.85–12.14) | 7676.2 | 660.9 | 10021 / 10014 | 5268 | 1006 | 1000 | 11.51 | 280 | 0 |
| udp | 1000 | 5.27 (4.55–5.90) | 4.15 (4.00–4.25) | 4.42 (3.70–5.05) | 7443.8 | 0.0 | 10032 / 0 | 4496 | 6 | 1 | 3.74 | 280 | 0 |
| mcast | 5000 | 1.95 (1.75–2.20) | 0.25 (0.20–0.30) | 0.22 (0.18–0.27) | 7.4 | 0.0 | 10 / 0 | 4484 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 5000 | 60.72 (60.14–61.19) | 58.20 (57.59–59.14) | 11.97 (11.86–12.07) | 38296.1 | 3299.6 | 49995 / 49995 | 7856 | 5006 | 5000 | 56.66 | 280 | 0 |
| udp | 5000 | 22.03 (20.35–24.90) | 19.41 (19.20–19.60) | 4.24 (3.90–4.81) | 37127.9 | 0.0 | 50038 / 0 | 4816 | 6 | 5 | 18.39 | 280 | 0 |

Memory (first run of each; slab is host-wide, so it counts both ends of every TCP connection):

| mode | N | slab Δ kB (both ends) | TCP sockets in use (tx ns) | TCP mem pages (host) | Σ skmem t (tx) | Σ skmem w (tx) | receiver RSS kB |
|---|---|---|---|---|---|---|---|
| mcast | 1000 | 1812 | 0 | 54 | – | – | 9972 |
| mcast | 5000 | 17084 | 0 | 58 | – | – | 30788 |
| tcp | 1000 | 8280 | 1001 | 310 | 0 | 0 | 16656 |
| tcp | 5000 | 47792 | 5001 | 310 | 1532 | 9192 | 59388 |
| udp | 1000 | 2180 | 0 | 54 | – | – | 9948 |
| udp | 5000 | 20016 | 0 | 314 | – | – | 31744 |

(Rows for N ≤ 100 are inside the ±0.5 MB slab noise; they are in `results/e2_fanout.json`.)

**Reading.**
- **Below 1 000 listeners it is all noise.** Every mode costs ≤ 1.5% of a core, inside the 0.85% idle baseline, so the per-listener column means nothing there.
- **Per listener, TCP costs 2.6-2.8× what UDP does.**
  - TCP: 11.6-12.0 µs of sending-host CPU per listener and frame (one `write()` plus the ACK it triggers).
  - UDP unicast with `sendmmsg`: 4.2-4.4 µs.
  - At 5 000 listeners that is 60.7% against 22.0% of a vCPU.
  - Multicast is flat at about 2%: one `sendto()` per frame whatever N. Its fan-out moves to the network and to the receiving hosts; here one namespace cloned each datagram to 5 000 sockets.
- **CPU is not what decides feasibility.** Extrapolated linearly, 100 000 TCP listeners at 1 frame/s need about 1.2 cores of this VM. That agrees with epoll servers routinely holding 100k+ connections.
- **What differs more than CPU:**
  - Packets: one 66 B ACK comes back per data segment. That is 2× the packets and 660 B/s inbound per listener (+8.6% bytes).
  - State: one fd and one kernel socket per listener, 5 006 fds against 6.
    - The slab grew 47.8 MB for 5 000 connections with both ends on this host: about 4.8 KB per idle socket end, before any queued data. E3 shows queued data reaching megabytes.
    - Go-side RSS grew 3.0 MB, about 0.6 KB per connection.
    - The UDP sender holds one socket; the 20.0 MB slab growth in the UDP run is the 5 000 receiver sockets.
  - Syscalls: 5 000 per frame, against 5 (`sendmmsg`, 1 024 per call) or 1 (multicast).
  - Sender enqueue time: handing one frame to the kernel for all 5 000 listeners took 56.7 ms over TCP (median; 5 000 `write()` calls), 18.4 ms with `sendmmsg` (5 calls) and 0.04 ms with multicast (one `sendto()`). It is timed on the sender's clock around its send loop. There are no receiver timestamps, so the arrival spread (when the last listener received the frame) was not measured.
  - This field was called `fanout_spread_*_us` when E2 was run. It is the same measurement, renamed `enqueue_all_*_us` in `fanout/main.go` and in `results/e2_fanout.json`; E2 was not re-run.
- **Portability.** Absolute µs are for this VM (virtualised, 4 vCPUs); the ratios carry over.

## E3: slow and dead consumers

**Slow consumer** (listener 0 stops reading at t = 10 s; 100 listeners, 10 × 700 B frames/s, 600 s runs). *victim unread* = FIONREAD on the victim's TCP socket at the end.

| variant | victim SO_RCVBUF | sender stalled at (s) | healthy latency p99 / max ms (delivered frames only) | healthy: last frame at (s, median) | healthy frames min / expected | victim app queue peak B | frames dropped for victim | victim disconnected at (s) | sender RSS kB | victim unread B at end | UDP RcvbufErrors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tcp-blocking | 65536 | 38.95 | 3.9 / 4.7 | 38.86 | 284 / 5890 | 0 | 0 | – | 45752 → 46264 | 118020 | 0 |
| tcp-queue | 65536 | none | 3.3 / 95.7 | 599.49 | 5890 / 5890 | 3928400 | 0 | – | 45928 → 50524 | 118020 | 0 |
| tcp-drop | 65536 | none | 4.3 / 97.0 | 599.49 | 5890 / 5890 | 65100 | 5520 | – | 45796 → 46300 | 118020 | 0 |
| tcp-disconnect | 65536 | none | 3.6 / 61.2 | 599.49 | 5890 / 5890 | 65800 | 0 | 48.38 | 45832 → 46120 | 118020 | 0 |
| udp | 65536 | none | 3.3 / 78.7 | 599.4 | 5890 / 5890 | 0 | – | – | 45720 → 45868 | – | 5863 |
| tcp-blocking-autotuned | autotuned | none | 2.7 / 67.5 | 599.43 | 5890 / 5890 | 0 | 0 | – | 45772 → 46152 | 4117400 | 0 |
| udp-autotuned | autotuned | none | 3.1 / 96.3 | 599.4 | 5890 / 5890 | 0 | – | – | 45684 → 45832 | – | 5826 |

**Dead listener** (listener 0 of 100 vanishes at t ≈ 10 s).

| variant | sender notices after | retransmissions | held for the dead listener | sender RSS kB | healthy latency p99 / max ms | note |
|---|---|---|---|---|---|---|
| tcp-kill | 0.005 s (EOF) | 0 (max RTO 204.0 ms) | 0 B app + 0 B kernel | 45788 → 45812 | 3.9 / 22.1 |  |
| tcp-silent-uto30s | 30.447 s (TimeoutError) | 8 (max RTO 26112.0 ms) | 139300 B app + 71400 B kernel | 45760 → 45948 | 4.5 / 14.0 |  |
| tcp-silent | 938.038 s (TimeoutError) | 16 (max RTO 120000.0 ms) | 6492500 B app + 71400 B kernel | 45900 → 53524 | 3.5 / 38.2 |  |
| udp-lease | lease lapsed 65.1 s (p50), 53.7–74.0 s | 0 | ≈651.5 datagrams (p50) | – | 2.0 / 88.5 | 20 died, 20 lapsed, 0 healthy lapsed |

**Reading.**
- **Blocking writer: one slow reader stops everyone.**
  - The victim's SO_RCVBUF was fixed at 64 KiB (128 KiB effective).
  - About 203 KB fitted in the kernel: 118 KB unread at the victim plus the sender's send buffer.
  - At 38.95 s the single-threaded writer blocked in `sendall()` for good. The other 99 listeners got their last frame at t = 38.86 s: 284 of 5 890 frames.
- **Surprise: an autotuned receiver never pushes back.**
  - This kernel (6.18, `tcp_rmem` max 32 MiB) kept growing the receive buffer of a socket that had stopped reading.
  - After 590 s the victim held 4 117 400 unread bytes. The window never closed, and even the blocking writer never stalled.
  - A TCP relay cannot see such a consumer by backpressure. When the consumer resumes, it reads ten minutes of stale frames first.
- **Queues.**
  - Non-blocking with an unbounded per-listener queue: the others are unaffected (p99 3.3 ms), and the queue grows at the stream rate, to 3.93 MB by 600 s (sender RSS +4.6 MB).
  - Capping it at 64 KiB with drop-oldest keeps memory flat: 5 520 frames dropped for the victim.
  - Disconnect-at-cap cut the victim at 48.4 s.
  - The relay must pick one of these policies, and hold per-listener state to apply it.
- **UDP needs none of this.**
  - The slow socket overflowed on its own (5 863 `RcvbufErrors`).
  - The sender and the other 99 listeners were unaffected: p99 3.3 ms, 5 890 of 5 890 frames.
- **Dead listeners.**
  - SIGKILL is noticed in 5 ms: the dead process's kernel sends FIN.
  - A host that silently vanishes is noticed only after 938 s: 16 retransmissions, with the RTO growing from 204 ms to the 120 s cap. Meanwhile the sender held 71.4 KB in the kernel and 6.49 MB in the unbounded app queue.
  - TCP_USER_TIMEOUT = 30 s aborted at 30.4 s. Every TCP relay needs this knob.
  - The UDP lease lapsed 53.7-74.0 s after death (p50 65.1 s), inside RFC-0001's bound of [75 − 26.4, 75] s. About 650 datagrams (455 KB) went into the void per dead listener, with no retransmission and no growing state.

## E4: late joiner

20 live items, 327 B frames; effective loops {'slow': [13080], 'fast': [1000]} ms; 10 joiners per arm back to back for 600 s; timeout 120 s. Time to hold all 20, Kaplan–Meier over every join (a join that timed out or was cut off by the end of the run is censored at its elapsed time), ms (s where marked); *max done* is the slowest completed join.

| loss | arm | joins | completed | timeouts | cut at end | p50 | p90 | p99 | max done |  |
|---|---|---|---|---|---|---|---|---|---|---|
| 0% | carousel-4kbps | 350 | 346 | 0 | 4 | 14.6 s | 16.3 s | 16.9 s | 17.1 s |  |
| 0% | carousel-1s | 1528 | 1528 | 0 | 0 | 1115.2 | 1246.8 | 1312.9 | 1331.2 |  |
| 0% | tcp-snapshot | 2139 | 2139 | 0 | 0 | 0.5 | 0.9 | 3.2 | 25.2 | connect p50/p99 0.5/3.2; server snapshots 2139 |
| 0% | lease-snapshot | 1369 | 1369 | 0 | 0 | 1570.1 | 1576.8 | 1590.4 | 1632.4 | handshake p50/p99 0.2/4.6; relay snapshots 1369 for 1369 sessions |
| 5% | carousel-4kbps | 273 | 264 | 0 | 9 | 17.2 s | 28.1 s | 38.5 s | 39.6 s |  |
| 5% | carousel-1s | 1381 | 1381 | 0 | 0 | 1357.9 | 2105.8 | 2970.6 | 4377.1 |  |
| 5% | tcp-snapshot | 2012 | 2012 | 0 | 0 | 0.6 | 1013.2 | 2040.4 | 7249.4 | connect p50/p99 0.5/1031.0; server snapshots 2012 |
| 5% | lease-snapshot | 637 | 633 | 0 | 4 | 4584.4 | 13.7 s | 27.0 s | 42.4 s | handshake p50/p99 0.3/3002.4; relay snapshots 637 for 637 sessions |
| 30% | carousel-4kbps | 141 | 136 | 0 | 5 | 38.6 s | 58.1 s | 83.3 s | 90.0 s |  |
| 30% | carousel-1s | 1011 | 1011 | 0 | 0 | 2934.4 | 4434.8 | 6637.3 | 8122.3 |  |
| 30% | tcp-snapshot | 360 | 337 | 17 | 6 | 2079.9 | 35.9 s | > 120.0 s | 118.1 s | connect p50/p99 1004.5/5087.4; server snapshots 359 |
| 30% | lease-snapshot | 175 | 167 | 0 | 8 | 28.2 s | 57.7 s | 79.8 s | 82.7 s | handshake p50/p99 2001.8/34.4 s; relay snapshots 175 for 175 sessions |

**Setup notes.**
- Each lease join is a new session from a new socket with a fresh client nonce. The relay keys leases by session (address and nonce, which is what its cookie validates), snapshots each new session once, and forwards the carousel once per address. The joiner RENEWs every 22 s × U(0.8, 1.2) (§11.3.5), so a join that runs past 75 s keeps its lease.
- *Relay snapshots* equal lease sessions at every loss level (637 of 637 at 5%, 175 of 175 at 30%). In the first run, which keyed leases by address, a session whose predecessor's BYE was lost got none: 560 snapshots for 591 joins at 5%, 117 for 160 at 30%.
- A join still running at the end of the run is censored at its elapsed time instead of being dropped (4-9 per carousel-4kbps row).

**Reading.**
- **No loss: TCP connect-plus-snapshot wins by three orders of magnitude.** 0.5 ms p50, against 1.12 s for a 1 s carousel and 1.57 s for a lease snapshot.
- **The default budget makes the carousel slow to catch up.**
  - `B_stream` = 4 kbit/s shared by 20 items of 327 B gives a fair-share loop of 13.08 s, not the 5 s class floor.
  - Passive catch-up is then 14.6 s at p50 with no loss, and 38.6 s at 30%.
  - Loop and budget, not the protocol, decide catch-up time.
- **The lease snapshot is paced, and that makes it slow.**
  - At `granted_bps` = 32 kbit/s (§7.10), 20 × 327 B take 1.57 s.
  - A lost snapshot frame waits for the relay-forwarded 13 s loop, so p50 rises to 4.6 s at 5% loss and 28.2 s at 30% (p99 27.0 s and 79.8 s).
  - Repeat the snapshot, pace it faster, or loop toward new leases at a shorter period.
- **Under loss, TCP's handshake is the weak point.**
  - A lost SYN or SYN-ACK costs the 1 s initial RTO, then 3 s, 7 s: p90 1.01 s at 5%.
  - At 30%: p50 2.08 s, p90 35.9 s, and 17 of 360 joins unfinished at 120 s (6 more were cut off by the end of the run). More than 1% of joins never finished, so the p99 lies beyond the 120 s timeout. The slowest join that finished took 118.1 s.
  - The 1 s carousel at 30%: 2.93 s p50, 6.64 s p99, 8.12 s max, and no failures.

## E5: reconnect storm

**Setup.**
- A relay serves 1 000 listeners a 20-item snapshot (20 × 330 B). It is killed with SIGKILL, and a new relay process starts at once on the same port; it is up 0.12-0.15 s later.
- TCP listeners reconnect immediately, retry every 100 ms while the port refuses, and time out after 5 s without a snapshot.
- UDP listeners follow §11.3: 3 missed relay beacons at 5 s, then HELLO/COOKIE/LISTEN with 1-2-4-8 s retransmits, then a paced snapshot.
- No loss.
- Three timed runs each, plus one `strace -c` pass (not timed) to count the new relay's syscalls. Relays and clients are Python.

N = 1000 listeners, 20 × 330 B snapshot. Times in s from SIGKILL of the old relay.

| mode | backlog | rep | pass | new relay up | all served | served p50 / p99 | ListenOverflows | SYN retrans | UDP RcvbufErrors | packets | relay syscalls | listener attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tcp | 128 | 0 | timed | 0.131 | 6.3087 | 0.3 / 6.3 | 509 | 366 | 0 | 13605 | – | {"connect": 2146, "refused": 1000, "snapshot_timeout": 143} |
| tcp | 4096 | 0 | timed | 0.123 | 0.3015 | 0.3 / 0.3 | 0 | 0 | 0 | 10886 | – | {"connect": 2000, "refused": 1000, "snapshot_timeout": 0} |
| udp-lease | – | 0 | timed | 0.153 | 13.2247 | 13.2 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |
| tcp | 128 | 0 | strace | 0.144 | 12.3773 | 1.3 / 12.4 | 1285 | 752 | 0 | 17219 | 9095 | {"connect": 2365, "refused": 1021, "snapshot_timeout": 342} |
| tcp | 4096 | 0 | strace | 0.131 | 0.6118 | 0.6 / 0.6 | 0 | 0 | 0 | 10798 | 5965 | {"connect": 2000, "refused": 1000, "snapshot_timeout": 0} |
| udp-lease | – | 0 | strace | 0.12 | 20.2478 | 14.2 / 20.2 | 0 | 0 | 1283 | 27148 | 51353 | {"hello": 1880, "listen": 1403, "renew": 0} |
| tcp | 128 | 1 | timed | 0.131 | 6.3183 | 0.3 / 6.3 | 440 | 366 | 0 | 12538 | – | {"connect": 2074, "refused": 1000, "snapshot_timeout": 74} |
| tcp | 4096 | 1 | timed | 0.123 | 0.3342 | 0.3 / 0.3 | 0 | 0 | 0 | 10921 | – | {"connect": 2001, "refused": 1001, "snapshot_timeout": 0} |
| udp-lease | – | 1 | timed | 0.154 | 13.2155 | 13.2 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |
| tcp | 128 | 2 | timed | 0.141 | 6.2834 | 0.3 / 6.3 | 397 | 353 | 0 | 11905 | – | {"connect": 2058, "refused": 1013, "snapshot_timeout": 44} |
| tcp | 4096 | 2 | timed | 0.124 | 0.3003 | 0.3 / 0.3 | 0 | 0 | 0 | 10893 | – | {"connect": 2000, "refused": 1000, "snapshot_timeout": 0} |
| udp-lease | – | 2 | timed | 0.136 | 13.2278 | 13.2 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |

**Reading.**
- **TCP notices at once.** The dead relay's kernel sends FIN, and 1 000 connects are refused while the new relay starts.
- **Backlog 4 096: back in 0.3 s.**
  - All 1 000 were re-served 0.30-0.33 s after the kill, 0.18-0.21 s after the new relay was up. No overflows.
  - About 6 syscalls per listener (strace: 993 `accept4`, 989 `sendto`, 989 `epoll_ctl`, 1 978 `getsockname`).
- **Backlog 128: 6.28-6.32 s.**
  - 63-65% were back within 0.5 s, and 86-96% within 2 s after one SYN retransmission at 1 s (353-366 SYN retransmits, 397-509 ListenOverflows).
  - The rest (44-143) were half-open: with the accept queue full, SYN cookies completed the handshake at the client, the final ACK was dropped, and the relay kept no state. Only the 5 s client timeout recovered them.
  - In a first run without that timeout, 101 of 1 000 clients hung in ESTABLISHED indefinitely. Note that asyncio's default backlog is 100.
- **UDP leases: 13.22 s in all three runs, every listener at once.**
  - The restarted relay has a new cookie secret and no leases, so it stays silent (§11.3.1).
  - Listeners notice only after 3 × 5 s without a relay beacon, then re-lease in milliseconds.
  - The HELLO storm (1 000 × 256 B at once) fitted the relay's default receive buffer in the timed runs. In the slower strace pass it overflowed (1 283 `RcvbufErrors`), and retransmits stretched recovery to 20.2 s.
- **Cost.** The paced UDP snapshot is one datagram per item per listener, about 24 `sendto` per listener with COOKIE, LISTEN_OK and beacons (23 865 in the strace pass). TCP needs one `write` per listener.
- **Conclusion.** On restart, TCP is faster (0.3 s against 13.2 s) if its backlog is sized. A lease relay could close most of that gap by persisting its cookie secret and lease table across restarts, or with a shorter `relay_beacon_ms` toward leases.

## What internet RTTs change

This testbed has RTT ≈ 0.1 ms. On a path with RTT R, by Linux's rules:

- **TCP repair of one lost update.**
  - RTO = SRTT + max(200 ms, 4·RTTVAR): about R + 200 ms. That is 220-230 ms at 20 ms, 300-320 ms at 100 ms, and 400-450 ms at 200 ms.
  - Thin streams (U ≥ R, one segment in flight) get no fast retransmit, and a tail-loss probe with one packet in flight waits 2·SRTT + 200 ms. With several segments in flight, RACK repairs in about 1.25·R.
  - TCP's low-loss advantage shrinks from about 5× (205 ms against 1 s) to about 2-3× at 100-200 ms, but it survives.
  - The carousel's repair schedule (+1, +2, +4 s, then the loop) does not depend on R.
- **Backoff and outages.** Each RTO doubles from a larger base, so post-outage stalls scale with roughly (R + 200 ms)/200 ms: about 1.5× at 100 ms and 2× at 200 ms. The carousel's post-outage wait is unchanged.
- **Late joiners.**
  - TCP needs 1.5·R to the first snapshot byte, and a lost SYN still costs 1 s, then 3 s.
  - A lease needs 2·R for HELLO/COOKIE/LISTEN plus the paced snapshot; a lost HELLO costs 1 s.
- **Dead peers.** The `tcp_retries2` = 15 abort budget is computed from the 200 ms minimum, so about 924 s holds on any path.
- **Buffers.** Per-connection memory grows with the bandwidth-delay product: 1.4 KB unacked per listener at 7 KB/s and 200 ms, small next to E2's socket overhead.
- **QUIC** (not measured).
  - Its probe timeout is smoothed_rtt + max(4·rttvar, 1 ms) + max_ack_delay, with no 200 ms floor, so a stream repairs faster than Linux TCP on short paths.
  - One stream per `state_key`, with RESET_STREAM on supersede, would remove head-of-line blocking between items (not within one stream).
  - DATAGRAM frames (RFC 9221) give carousel semantics through NAT and to browsers (RFC-0001 §11.5).

## Recommendation by plane

| Plane (RFC-0001 §3.1) | Transport | Why, from the data |
|---|---|---|
| **Binary plane, station/relay → listeners** | **UDP carousel** (unicast leases, LAN multicast); QUIC DATAGRAM / WebTransport for browsers and NAT-hostile paths | Bounded staleness under 20-30% loss and outages (E1 at 30%: every update delivered and at most 3.5-11 s stale, against TCP stalls of 203-898 s and up to 71% of updates undelivered). A slow or dead listener costs the sender nothing (E3). UDP unicast is 4.2-4.4 µs per listener·frame against TCP's 11.6-12.0 µs, with half the packets and no per-listener socket; multicast is flat on a LAN (E2). Keep the burst. Offer the 1 s floor where post-outage freshness matters, and budget it (9.6 copies/update at U = 10 s). |
| Binary plane, **relay ↔ relay backbone** | **TCP/QUIC stream** (D10: NATS), latest-only per key, bounded drop-oldest queues, TCP_USER_TIMEOUT | Backbone links are few and usually healthy. At ≤ 10% loss TCP repairs in one RTO (E1: 212 ms against 1 s) and carries each item once instead of looping it. Guard against E1's backoff tails and E3's silent peers. |
| Late-joiner catch-up | Relay snapshot over **TCP or QUIC** when the path is good; carousel when it is not | E4: TCP snapshot 0.5 ms against 1.1-15 s passive, but at 30% loss 17 of 360 joins were not done in 120 s. The lease snapshot as specified (paced, once) is slower than both at 5%: repeat it or pace it faster. |
| Ledger plane (durable truth, promotion, ringserver replay/dashboards) | **TCP** (DataLink/SeedLink, §18) | Reliability and order are the requirement there, not freshness. |
| Control plane (addressed work, acks) | **TCP/QUIC** (the harness's own queues) | Needs reliability and flow control. E3 shows the price: per-peer queues and a user timeout. |
| Membership (beacons, presence) | **UDP**, as specified | Periodic and loss-tolerant. E5: relay-restart detection took 13.2 s (3 × 5 s beacons). Persist the cookie secret and leases across restarts, or shorten `relay_beacon_ms` toward leases, if that matters. |

## Surprises

- **Linux 6.18 grows the receive buffer of a socket that has stopped reading.** It reached 4.1 MB over 590 s at 7 KB/s, and backpressure never came. Kernel buffering hides a slow consumer from its sender and turns it into a stale consumer.
- **At U = 0.5 s and 30% loss, most TCP updates never arrived.** 71% of (update, receiver) pairs were still undelivered 20 s after the last update of a 900 s run, so TCP's median latency there is beyond what the run could observe.
- **TCP delivered 2 698 frames after their own signed expiry** (U = 0.5 s, 30%). A byte stream does not know about TTLs, so the receiver's `expires_at` check is load-bearing over TCP too (RFC-0001 I-3, §20.3).
- **SRTT inflation.** At 30% loss TCP_INFO showed a 120 s RTO at backoff 0: SRTT itself had inflated, not only the RTO doubled.
- **Latest-only coalescing can make TCP's tail worse**, because the stream gets thinner.
- **The default carousel budget, not the class floor, sets catch-up time.** 20 items at 4 kbit/s loop every 13.08 s.
- **The `lo` MTU matters.** At the default 65 536, TCP autotuned its send buffer to 4 MiB at once, and one retransmission could carry a whole backlog. A first E1 pass at that MTU was discarded; everything here is at MTU 1500.
- **Half-open "ghosts" in a TCP reconnect storm.** With the accept queue full, SYN cookies completed handshakes for which the relay never had a socket. With a server-speaks-first protocol and no client timeout, 101 of 1 000 clients waited forever.

## Limitations

See [README.md](README.md#limitations). The main ones:
- There is no RTT emulation.
- Loss is Bernoulli per packet, on one host.
- The Python harness adds about 1 ms to every median.
- Tails at ≥ 20% loss rest on a few long episodes per 900 s run: orders of magnitude, not stable percentiles.
- Latencies with censoring (E1 updates and outage recovery, E4 joins) are Kaplan–Meier estimates. They assume censoring says nothing about latency, which TCP's long stalls strain: consecutive updates share one stall.
- E2's CPU numbers are for this VM, though the ratios carry over.
- E5 uses Python relays and clients.
