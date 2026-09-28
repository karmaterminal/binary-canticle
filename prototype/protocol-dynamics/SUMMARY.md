# protocol-dynamics: results

Measured from 23:25 UTC on 2026-09-27 to 00:08 UTC on 2026-09-28 on one Linux
6.18 host (4 vCPUs). Every condition ran in its own network namespace; loss was
dropped by nftables in both directions unless marked *data-only*. There is no
delay emulation, so RTT is about 0.1 ms and every TCP recovery time below is the
floor set by Linux's timers (see
[What internet RTTs change](#what-internet-rtts-change)). Testbed, method and
limitations are in [README.md](README.md). All numbers come from
`results/<experiment>/`; `python summarize.py` prints these tables, and
`python summarize.py verify` checks each experiment against its manifest and
commit.

**Revision after review.** The harness was corrected as below, and then all five
experiments were re-run from a clean tree at commit 971846e. Every table and
number in this document comes from that re-run.
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
- E2's cost per listener subtracted one idle sample, taken before all runs,
  from every run, and printed the difference even where it was noise: down to
  −40 µs per listener·frame at N ≤ 100, which is impossible. The cost is now
  reported only where its 95% interval over repeats lies above 0, and "not
  resolved" elsewhere (see E2). The harness now takes a matched idle control
  per repeat and N, and the E2 data below uses it. Against it, TCP costs 11.23
  and 12.09 µs and UDP 3.83 and 3.38 µs per listener·frame at N = 1 000 and
  5 000; the previous E2 run, against its single unmatched sample, gave 11.63
  and 11.97 µs, and 4.42 and 4.24 µs.
- Provenance. Every experiment publishes `results/<experiment>/` as a whole,
  with a `manifest.json` (run id, argv, times, git commit, dirty flag, per-file
  source digests and one digest over them, and the diff when run with
  `--allow-dirty`),
  and refuses to run from a tree whose sources differ from HEAD. All five
  experiments were re-run with `./run_all.sh` from a clean tree at 971846e, and
  `python summarize.py verify` reports MATCH at that commit for all six
  generations. Run ids, from the manifests:
  - E1 `20260927T232539Z-9515-1d9e`;
  - E2 `20260927T234231Z-11226-5348`;
  - E3 slow `20260927T232539Z-9516-e2aa`, E3 dead `20260927T232539Z-9517-7e7b`;
  - E4 `20260927T232539Z-9518-adbb`;
  - E5 `20260928T000605Z-12752-2e17`.
- These generations supersede all earlier data: the E1 and E4 generation of
  the previous version of this document, whose manifests named commit 5b04c86
  with a dirty tree and a source hash that none of the last twelve commits
  reproduces, and the E2, E3 and E5 data, which carried no manifest (E3's
  `udp-lease` variant had been re-run on its own after a harness fix).
- High-loss TCP tails vary a lot between runs, so read TCP tails at ≥ 20% loss
  as orders of magnitude. From the previous version of this document to this
  one:
  - U = 0.5 s, 30%, `tcp-stream`: delivered 29.22% → 35.78%, and frames
    delivered after their signed expiry 2 698 → 1 292;
  - U = 2 s, 30%: `tcp-stream` delivered 90.21% → 95.08%, `tcp-latest`
    98.36% → 94.07%, so `tcp-latest` no longer delivers more there;
  - U = 10 s, 30%, `tcp-stream`: p99 68.0 s → 4.96 s.

## Bottom line

- **At low loss (≤ 10%) on a healthy connection, TCP keeps a receiver fresher than the carousel.**
  TCP repairs a lost update in one RTO, about 205-211 ms here. The carousel waits for its next copy: the +1 s burst, or the next update.
  - U = 10 s, 5% loss: p99 210-211 ms (TCP) against 1 003-1 006 ms (UDP).
  - U = 2 s, 10% loss: TCP holds a superseded value 1.2-1.3% of the time, UDP 5.6-5.7%.
- **TCP's failure mode is an unbounded tail; the carousel's is bounded.**
  - At 30% loss in both directions, TCP's RTO reached the 120 s cap in five of the six TCP cells. The longest stall that ended lasted 606 s; 26 of the 120 TCP connections at 30% were still in one when the run ended, the longest for at least 698 s. Head-of-line blocking queues every superseded value behind the stall.
  - U = 0.5 s, 30% loss: when the run ended, 20 s after the last update, only 36% of (update, receiver) pairs had reached a `tcp-stream` receiver. The median latency is therefore beyond 855.5 s, the longest the run could observe. Receivers held a stale value 87% of the time, and 1 292 frames arrived after their own signed expiry.
  - The carousel at the same point delivered every update: p99 1.5 s, max 4.5 s, stale 30% of the time, which is the loss rate.
  - With ACKs spared (data-only loss), TCP at 30% delivered every update: p99 1.5-9.4 s. Its slowest update still took 6.6-108 s, against 4.0-14 s for the carousel.
- **After outages, TCP resumes late.**
  - After a 10 s outage, TCP needed p95 3.9-6.2 s to deliver the newest value. That is RTO backoff: 408 → 816 → 1 632 → 3 264 → 6 528 ms.
  - The carousel needed p95 0.47-0.91 s with frequent updates, and 1.72 s (1 s loop) or 5.07 s (5 s loop) at U = 10 s.
  - After 1-3 s outages the two are comparable.
- **Fan-out (E2): TCP costs about 3× (2.9-3.6×) more CPU per listener than UDP unicast.**
  - Per listener and frame: TCP 11.2-12.1 µs of sending-host CPU (the write plus the ACK it triggers), UDP with `sendmmsg` 3.4-3.8 µs. Multicast keeps CPU 0 at 0.3-2.8% busy on average whatever N (0.3-1.0% idle), and its cost per listener is not resolved at any N.
  - At 5 000 listeners × 10 frames/s: 61.5% against 17.9% of a vCPU.
  - TCP also doubles the packets (one ACK per segment) and needs 5 006 fds against 6.
  - Handing one frame to the kernel for all 5 000 listeners took the TCP sender 56.8 ms (median), against 17.3 ms with `sendmmsg`. That is sender enqueue time; when the last listener received the frame was not measured.
  - Either is feasible; the difference is cost per listener, not whether it works.
- **Slow and dead consumers (E3).**
  - With a blocking writer, one listener that stops reading stalls all 100, 29.6 s after it stops (64 KiB buffers).
  - With Linux's autotuned receive buffer the sender never notices: after 590 s the reader held 4.1 MB of unread, 10-minute-old data.
  - A silently vanished TCP listener is aborted only after 939 s. Meanwhile an unbounded queue grew to 6.5 MB and the kernel retransmitted 16 times. TCP_USER_TIMEOUT = 30 s cut that to 30.3 s.
  - UDP: the slow socket overflowed alone (5 865 drops), and a dead lease lapsed after 54-75 s with no retransmission and no per-listener buffer.
- **Late joiners (E4).**
  - At 0% loss TCP connect-plus-snapshot is by far the fastest: 0.5 ms p50, against 1.1 s for a 1 s carousel and 14.9 s at the default 4 kbit/s budget.
  - At 30% loss, SYN loss hurts TCP: p50 2.2 s, p90 68 s, and 17 of 307 joins not done in 120 s, so its p99 lies beyond 120 s. The 1 s carousel does 2.9 s p50 and 6.7 s p99, with no failures.
- **Relay restart (E5).**
  - TCP notices a restarted relay at once. With a 4 096 backlog, 1 000 listeners were re-served 0.29-0.34 s after the kill.
  - With a backlog of 128, accept-queue overflow and SYN retransmits stretched that to 6.2-6.3 s. SYN-cookie half-open connections hang forever without a client timeout.
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

*`results/e1/`: run `20260927T232539Z-9515-1d9e`, 2026-09-27T23:25:39Z to 2026-09-27T23:41:24Z, commit `971846eab060` (clean), sources sha256 `f1d633655031`.*

**U = 0.5 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.1 / 3.0 | 2.0 / 3.0 | 1.8 / 2.6 | 1.8 / 3.0 | 0.22 / 0.22 / 0.19 / 0.21 | 5.3 / 4.4 / 4.4 / 4.4 |
| 1% | 1.0% | 2.4 / 8.6 | 2.3 / 499.2 | 2.0 / 204.8 | 2.1 / 205.4 | 1.17 / 1.29 / 0.64 / 0.66 | 996.8 / 1001.4 / 414.3 / 418.0 |
| 5% | 5.0% | 7.6 / 502.1 | 499.4 / 502.2 | 159.4 / 211.3 | 206.1 / 211.4 | 5.10 / 5.52 / 2.44 / 2.54 | 1501.9 / 1501.2 / 2854.1 / 1466.4 |
| 10% | 10.0% | 501.3 / 519.1 | 501.2 / 507.0 | 209.8 / 418.5 | 209.9 / 418.4 | 10.27 / 10.36 / 5.70 / 5.89 | 2000.3 / 2003.3 / 12.9 s / 12.6 s |
| 20% | 19.8% | 502.8 / 1002.9 | 502.9 / 1003.1 | 15.2 s / > 306.0 s · 98.40% delivered | 3028.4 / 26.2 s | 19.65 / 20.28 / 25.09 / 21.89 | 2996.2 / 3001.1 / 286.0 s / 100.7 s |
| 30% | 29.7% | 1001.2 / 1501.9 | 1001.2 / 1501.9 | > 855.5 s / > 855.5 s · 35.78% delivered | > 720.0 s / > 720.0 s · 84.08% delivered | 29.84 / 30.09 / 86.69 / 75.84 | 4496.4 / 3499.8 / 835.5 s / 700.0 s |

**U = 2 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 1.9 / 2.4 | 2.1 / 3.3 | 1.8 / 2.9 | 1.8 / 2.5 | 0.05 / 0.05 / 0.05 / 0.05 | 11.0 / 4.8 / 17.0 / 11.0 |
| 1% | 1.0% | 2.3 / 5.4 | 2.2 / 4.9 | 2.0 / 4.5 | 2.0 / 5.1 | 0.53 / 0.54 / 0.14 / 0.14 | 1999.3 / 1013.5 / 408.8 / 415.6 |
| 5% | 5.0% | 6.3 / 1005.3 | 5.6 / 1004.5 | 205.7 / 210.4 | 205.8 / 210.5 | 2.59 / 2.65 / 0.62 / 0.63 | 2001.5 / 2999.7 / 849.7 / 849.9 |
| 10% | 9.9% | 1002.2 / 2000.0 | 1001.9 / 1008.6 | 206.9 / 414.2 | 209.0 / 414.3 | 5.65 / 5.56 / 1.23 / 1.34 | 3005.6 / 4000.0 / 3334.7 / 4786.0 |
| 20% | 20.0% | 1005.8 / 2002.4 | 1005.2 / 2002.3 | 416.8 / 8908.6 · 99.94% delivered | 416.8 / 7497.2 | 11.99 / 11.89 / 4.83 / 4.90 | 4998.4 / 5003.2 / 54.0 s / 53.0 s |
| 30% | 29.9% | 2001.1 / 3003.9 | 2001.2 / 3005.8 | 142.3 s / > 646.0 s · 95.08% delivered | 400.3 s / > 682.0 s · 94.07% delivered | 18.97 / 19.69 / 25.04 / 25.89 | 7001.9 / 6999.6 / 626.0 s / 662.0 s |

**U = 10 s**, loss on every packet (both directions). Update latency, Kaplan–Meier p95 / p99 in ms (s where marked), with the share of (update, receiver) pairs delivered before the run ended where it is below 100%. Stale time % and the longest time a receiver held a superseded value, in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) | staleness max (same order) |
|---|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.0 / 3.3 | 2.4 / 3.9 | 1.8 / 2.7 | 1.9 / 3.4 | 0.01 / 0.01 / 0.01 / 0.01 | 1.5 / 3.3 / 1.6 / 3.3 |
| 1% | 0.9% | 2.1 / 3.0 | 2.1 / 2.4 | 1.6 / 2.5 | 1.8 / 206.1 | 0.10 / 0.08 / 0.03 / 0.03 | 1005.2 / 1003.6 / 209.6 / 210.9 |
| 5% | 5.0% | 3.7 / 1005.7 | 2.7 / 1003.1 | 205.7 / 210.3 | 205.7 / 210.6 | 0.54 / 0.43 / 0.13 / 0.12 | 4003.4 / 4001.0 / 653.1 / 421.8 |
| 10% | 10.2% | 1002.2 / 2001.3 | 1002.0 / 2000.0 | 205.9 / 214.1 | 208.1 / 221.6 | 1.19 / 1.27 / 0.20 / 0.26 | 3998.9 / 4002.1 / 840.6 / 1669.6 |
| 20% | 19.9% | 1008.4 / 2006.1 | 1005.3 / 2005.2 | 211.8 / 423.7 | 218.2 / 643.3 | 2.68 / 2.38 / 0.53 / 0.57 | 10.0 s / 5952.8 / 3327.9 / 1666.7 |
| 30% | 30.0% | 2002.0 / 4003.2 | 2002.7 / 4004.6 | 420.6 / 4964.6 | 6516.5 / 244.3 s | 4.39 / 4.85 / 2.05 / 6.36 | 9998.4 / 6720.4 / 43.2 s / 325.2 s |

**Data-only loss** (pure ACKs, SYN and FIN spared). Update latency, Kaplan–Meier p95 / p99 in ms, delivered share where below 100%; staleness max in arm order.

| U | loss | udp-live | udp-ctl | tcp-stream | tcp-latest | staleness max |
|---|---|---|---|---|---|---|
| 0.5 s | 10% | 501.2 / 504.3 | 501.2 / 999.6 | 206.9 / 413.6 | 206.9 / 413.3 | 1999.7 / 2000.2 / 1691.8 / 3331.4 |
| 0.5 s | 20% | 502.6 / 1002.5 | 502.6 / 1002.7 | 354.2 / 846.1 | 346.1 / 840.5 | 2999.8 / 2999.4 / 26.8 s / 13.5 s |
| 0.5 s | 30% | 1001.3 / 1502.6 | 1001.4 / 1502.4 | 853.7 / 9389.4 | 841.7 / 3657.5 | 4002.2 / 3997.6 / 108.0 s / 13.7 s |
| 2 s | 10% | 1002.2 / 1009.3 | 1002.5 / 1013.5 | 208.8 / 220.6 | 207.6 / 218.3 | 3005.9 / 3996.6 / 1663.4 / 1471.1 |
| 2 s | 20% | 1005.3 / 2002.2 | 1005.8 / 2002.7 | 217.7 / 651.0 | 215.6 / 650.8 | 5001.8 / 4999.2 / 6856.2 / 3340.3 |
| 2 s | 30% | 2001.6 / 3007.2 | 2001.5 / 3005.9 | 418.7 / 1674.6 | 422.3 / 1674.6 | 9003.5 / 7004.1 / 26.4 s / 26.6 s |
| 10 s | 10% | 1002.2 / 1011.7 | 1002.1 / 1013.9 | 206.4 / 413.5 | 208.0 / 221.1 | 10.0 s / 4001.6 / 842.7 / 844.7 |
| 10 s | 20% | 1006.0 / 2007.7 | 1004.5 / 2003.5 | 215.5 / 642.8 | 215.0 / 638.9 | 10.0 s / 5065.5 / 3148.6 / 3324.9 |
| 10 s | 30% | 2002.7 / 4007.4 | 2002.7 / 4007.4 | 417.7 / 1481.9 | 419.4 / 1675.0 | 14.0 s / 7278.4 / 6458.6 / 13.3 s |

**Outages.** Recovery after the outage ends (time until the receiver holds the newest value), Kaplan–Meier p50 / p95, with the number of (outage, receiver) pairs not recovered by the end of the run where nonzero · Kaplan–Meier median latency of updates issued inside the outage, ms. 20 receivers per arm.

| outage | U | outages | udp-live | udp-ctl | tcp-stream | tcp-latest |
|---|---|---|---|---|---|---|
| 1 s | 0.5 s | 54 | 246.2 / 469.6 · 999.1 | 246.4 / 468.9 · 998.8 | 239.0 / 771.9 · 846.3 | 239.0 / 771.9 · 846.3 |
| 1 s | 2 s | 50 | 494.4 / 894.7 · 1001.9 | 494.6 / 894.8 · 1002.1 | 135.6 / 795.6 · 837.8 | 135.6 / 795.5 · 837.8 |
| 1 s | 10 s | 45 | 570.2 / 889.8 · 1001.7 | 570.0 / 889.9 · 1001.6 | 163.5 / 755.7 · 838.7 | 163.5 / 755.8 · 838.7 |
| 3 s | 0.5 s | 46 | 281.1 / 445.1 · 1998.6 | 280.9 / 445.2 · 1998.6 | 607.8 / 779.8 · 1857.8 | 641.3 / 824.3 · 1910.5 |
| 3 s | 2 s | 44 | 545.0 / 886.1 · 2001.7 | 545.2 / 886.8 · 2001.8 | 691.6 / 1387.8 · 1682.3 | 719.6 / 1387.9 · 1682.4 |
| 3 s | 10 s | 40 | 630.2 / 1744.9 · 2001.6 | 630.0 / 1744.7 · 2001.8 | 551.6 / 1500.8 · 1680.4 | 551.6 / 1500.8 · 1680.4 |
| 10 s | 0.5 s | 30 | 253.5 / 472.9 · 5499.6 | 253.6 / 473.1 · 5499.8 | 3616.0 / 3912.4 · 8808.0 | 3732.7 / 4012.0 · 8923.6 |
| 10 s | 2 s | 29 | 419.7 / 911.1 · 6000.2 | 419.4 / 911.8 · 6000.4 | 4263.9 / 5215.6 · 9415.1 | 4301.1 / 5243.8 · 9446.4 |
| 10 s | 10 s | 26 | 1196.2 / 5074.0 · 4008.8 | 590.1 / 1719.5 · 4002.3 | 1053.4 / 6199.7 · 6631.6 | 1053.5 / 6199.7 · 6631.6 |

**TCP pathologies** (20 connections per arm, 900 s).
- *superseded*: frames delivered after a newer value was already issued.
- *expired*: frames delivered after their signed `expires_at`; a receiver must drop them.
- *censored*: (update, receiver) pairs never caught up by the end of the run; *delivered* is the rest, as a share.
- *longest*: the longest stretch with an unacknowledged retransmission (TCP_INFO, 20 ms sampling). "≥ … (open at end)" marks a stretch still open when the run ended.

| U | loss dir | loss | arm | superseded | expired | censored | delivered | max backoff | longest | retrans (sum) | resets |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 s | both | 10% | tcp-stream | 275 | 0 | 0 | 100.00% | 5 | 13.0 s | 8296 | 0 |
| 0.5 s | both | 10% | tcp-latest | 153 | 0 | 0 | 100.00% | 5 | 12.9 s | 8515 | 0 |
| 0.5 s | both | 20% | tcp-stream | 4877 | 67 | 573 | 98.40% | 9 | 212.8 s | 17241 | 0 |
| 0.5 s | both | 20% | tcp-latest | 1264 | 0 | 0 | 100.00% | 7 | 86.3 s | 17608 | 0 |
| 0.5 s | both | 30% | tcp-stream | 6784 | 1292 | 22991 | 35.78% | 10 | ≥ 636.9 s (open at end) | 6744 | 0 |
| 0.5 s | both | 30% | tcp-latest | 1965 | 12 | 5699 | 84.08% | 10 | ≥ 698.4 s (open at end) | 11148 | 0 |
| 0.5 s | data-only | 10% | tcp-stream | 71 | 0 | 0 | 100.00% | 2 | 1.3 s | 3943 | 0 |
| 0.5 s | data-only | 10% | tcp-latest | 69 | 0 | 0 | 100.00% | 3 | 2.9 s | 4026 | 0 |
| 0.5 s | data-only | 20% | tcp-stream | 739 | 0 | 0 | 100.00% | 6 | 26.4 s | 8922 | 0 |
| 0.5 s | data-only | 20% | tcp-latest | 625 | 0 | 0 | 100.00% | 5 | 13.1 s | 9054 | 0 |
| 0.5 s | data-only | 30% | tcp-stream | 3003 | 0 | 0 | 100.00% | 8 | 107.8 s | 14572 | 0 |
| 0.5 s | data-only | 30% | tcp-latest | 1922 | 0 | 0 | 100.00% | 5 | 13.1 s | 14886 | 0 |
| 2 s | both | 10% | tcp-stream | 1 | 0 | 0 | 100.00% | 3 | 2.9 s | 2023 | 0 |
| 2 s | both | 10% | tcp-latest | 2 | 0 | 0 | 100.00% | 4 | 6.4 s | 2132 | 0 |
| 2 s | both | 20% | tcp-stream | 160 | 0 | 5 | 99.94% | 7 | 54.3 s | 4863 | 0 |
| 2 s | both | 20% | tcp-latest | 29 | 0 | 0 | 100.00% | 7 | 54.6 s | 4924 | 0 |
| 2 s | both | 30% | tcp-stream | 1271 | 68 | 440 | 95.08% | 9 | 228.1 s | 7765 | 0 |
| 2 s | both | 30% | tcp-latest | 163 | 2 | 530 | 94.07% | 13 | ≥ 683.6 s (open at end) | 7346 | 0 |
| 2 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 1023 | 0 |
| 2 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 941 | 0 |
| 2 s | data-only | 20% | tcp-stream | 12 | 0 | 0 | 100.00% | 4 | 6.4 s | 2247 | 0 |
| 2 s | data-only | 20% | tcp-latest | 3 | 0 | 0 | 100.00% | 3 | 2.9 s | 2248 | 0 |
| 2 s | data-only | 30% | tcp-stream | 70 | 0 | 0 | 100.00% | 6 | 26.2 s | 3858 | 0 |
| 2 s | data-only | 30% | tcp-latest | 43 | 0 | 0 | 100.00% | 6 | 26.4 s | 3906 | 0 |
| 10 s | both | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 407 | 0 |
| 10 s | both | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 2 | 1.3 s | 448 | 0 |
| 10 s | both | 20% | tcp-stream | 0 | 0 | 0 | 100.00% | 5 | 12.9 s | 935 | 0 |
| 10 s | both | 20% | tcp-latest | 0 | 0 | 0 | 100.00% | 4 | 6.4 s | 996 | 0 |
| 10 s | both | 30% | tcp-stream | 10 | 0 | 0 | 100.00% | 7 | 53.0 s | 1828 | 0 |
| 10 s | both | 30% | tcp-latest | 6 | 2 | 0 | 100.00% | 10 | 334.6 s | 1903 | 0 |
| 10 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 100.00% | 1 | 0.4 s | 174 | 0 |
| 10 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 100.00% | 1 | 0.4 s | 214 | 0 |
| 10 s | data-only | 20% | tcp-stream | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 447 | 0 |
| 10 s | data-only | 20% | tcp-latest | 0 | 0 | 0 | 100.00% | 3 | 2.9 s | 420 | 0 |
| 10 s | data-only | 30% | tcp-stream | 0 | 0 | 0 | 100.00% | 4 | 6.4 s | 732 | 0 |
| 10 s | data-only | 30% | tcp-latest | 1 | 0 | 0 | 100.00% | 5 | 12.9 s | 809 | 0 |

**Reading.**

1. **Where TCP is better.** Up to 10% loss, and at 20% when updates are sparse (U = 10 s), TCP beats the carousel on p99 and on stale time.
   - At 1% loss only the stale time differs clearly: the p99 sits at the edge of the 1% of updates that need a repair. Medians are 0.9-1.3 ms in every arm up to 10% loss, which is harness time.
   - One lost segment costs one RTO: 205-211 ms here. This kernel arms RTO = SRTT + max(200 ms, 4·RTTVAR) at HZ 250, and with one packet in flight a tail-loss probe waits just as long.
   - The carousel's first repair is the burst copy 1 s later, or the next update when that comes first (U = 0.5 s). So its p99 sits near 500 or 1 000 ms wherever TCP's is near 210 ms.
   - This per-item repair-latency advantage of one reliable connection is real.
2. **Where TCP breaks.**
   - With loss in both directions, a retransmission and its ACK both have to survive, so each attempt fails 36% of the time at 20% loss and 51% at 30%.
   - Linux doubles the RTO on each failure, up to 120 s. At 30% the RTO reached that cap in five of the six TCP cells; in the sixth (U = 10 s, `tcp-stream`) its five longest episodes reached 26 s. At 20% the five longest episodes per cell reached 3.3-56 s, except at U = 0.5 s in `tcp-stream`, where one reached the 120 s cap. Timestamp echo during loss also inflates SRTT: that episode had the 120 s RTO at a backoff of at most 1, and TCP_INFO showed a 5.5 s RTO at backoff 0 (U = 0.5 s, 30%, `tcp-latest`, connection 0).
   - Every update queues behind the head of line. The result:
     - multi-minute stalls; the longest episode that ended lasted 606.5 s, and at U = 0.5 s, 30% eleven of the twenty `tcp-stream` connections (and nine `tcp-latest`) were still in one when the run ended, the longest for at least 636.9 s (698.4 s for `tcp-latest`);
     - at U = 0.5 s, 30%, only 36% of (update, receiver) pairs were delivered before the run ended, 20 s after the last update, so even the median latency lies beyond the 855.5 s the run could observe; at U = 2 s, 30%, 95% were delivered, the p95 was 142.3 s and the p99 lies beyond 646 s;
     - 1 292 frames delivered after their signed `expires_at` (U = 0.5 s, 30%);
     - 53% of `tcp-stream` deliveries at U = 0.5 s, 30% were already superseded on arrival.
   - No connection reset: `tcp_retries2` = 15 allows about 924 s, and some ACK always got through first.
   - The carousel's worst case is set by its schedule, not its history: 3.5-4.5 s (U = 0.5 s) and 10.0 s (U = 10 s, 5 s loop) even at 30%, with every update delivered.
3. **ACK loss is most of the damage.** With data-only loss, TCP at 30% delivered every update, with a p99 of 1.5-9.4 s instead of minutes or never. Radio links usually lose in both directions; wired internet paths often do not.
4. **Latest-only does not fix head-of-line blocking.**
   - `tcp-latest` removes most backlog replay: after 10 s outages at U = 0.5 s it delivered 1 280 superseded frames against 15 480.
   - It does not shorten the stall, because the in-flight segment must still be retransmitted first.
   - At U = 0.5 s it delivered more than `tcp-stream` (20%: 100% against 98.40%; 30%: 84% against 36%), but at U = 2 s, 30% no more (94% against 95%). Its tail was sometimes worse: U = 10 s, 30%, p99 244.3 s against 4.96 s; U = 2 s, 30%, p95 400.3 s against 142.3 s. A thinner stream has fewer segments in flight, so fast recovery triggers less and more losses need an RTO.
   - Tails at ≥ 20% come from a few backoff episodes per run and vary between runs: `tcp-latest` at U = 0.5 s, 20% had a p99 of 155 s in the original run, 21.0 s in the previous re-run and 26.2 s in this one, and `tcp-stream` at U = 10 s, 30% had 68.0 s in the previous re-run and 4.96 s in this one. Read them as orders of magnitude.
5. **The class floor is a real but narrow knob.**
   - The 0 / +1 / +2 / +4 s burst does almost all repair for new updates, so the 1 s and 5 s loops look alike under Bernoulli loss.
   - The floor matters once the burst has failed:
     - 10 s outage at U = 10 s: p95 recovery 1.72 s against 5.07 s;
     - U = 10 s, 30% loss: longest staleness 6.7 s against 10.0 s;
     - late joiners (E4).
   - It costs bandwidth: at U = 10 s the carousel sent 4.80 (5 s loop) or 9.62 (1 s loop) copies per update per listener. That is 305-460 B/s per listener including the 1 Hz beacon, against 33 B/s of TCP payload.

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
- *Cost per listener.* For each repeat, (CPU 0 busy − idle CPU 0 busy) / (N × 10 frames/s); the table gives the mean over the 3 repeats with its 95% t-interval (never narrower than the two-tick quantum of CPU accounting, 1/100 s per window), and only when the interval lies above 0. Where it does not, the listeners' CPU is inside the idle noise: the cell says *not resolved* and gives the interval's half-width instead. No cost is negative and none is clamped.
- *Idle.* Each repeat runs one block per N: a matched idle window (same namespaces, veth, RPS, warm-up and window, nothing running) and the three loaded runs, in a shuffled order. CPU 0 was 0.05-1.70% busy in the idle windows.

*`results/e2/`: run `20260927T234231Z-11226-5348`, 2026-09-27T23:42:31Z to 2026-09-28T00:06:04Z, commit `971846eab060` (clean), sources sha256 `c79d07a7edd8`.*

Mean of 3 runs (min–max); 20 s windows after 5 s warm-up. Idle is the matched control of the same repeat and N: the same namespaces and window with nothing running, in a shuffled order with the loaded runs. *µs per listener·frame* = (CPU 0 busy − idle) / (N × frames/s), per repeat; the mean over repeats with its 95% t-interval, widened where needed to the two-tick quantum of CPU accounting (1/100 s per window), shown only when the interval lies above 0. Otherwise the cost is *not resolved* at that N (it is inside the idle noise), and ± is the interval's half-width, about the smallest cost the run could have resolved. *Sender enqueue time* = how long the sender's loop took to hand one frame to the kernel for all N listeners (sender clock); when the last listener received it was not measured.

| mode | N | sender host CPU % (CPU 0) | idle CPU 0 % | sender process CPU % | µs per listener·frame (95% CI) | wire out kB/s | wire in kB/s | pkts/s out / in | sender RSS kB | sender fds | syscalls/frame | sender enqueue time, one frame to all N, p50 ms | min frames/listener | backlog drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mcast | 10 | 0.48 (0.30–0.70) | 0.37 (0.30–0.45) | 0.23 (0.15–0.30) | not resolved (±68.41) | 7.4 | 0.0 | 10 / 0 | 4536 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 10 | 0.58 (0.25–1.20) | 0.37 (0.30–0.45) | 0.28 (0.25–0.30) | not resolved (±148.19) | 76.6 | 6.6 | 100 / 100 | 4620 | 16 | 10 | 0.11 | 280 | 0 |
| udp | 10 | 0.22 (0.05–0.50) | 0.37 (0.30–0.45) | 0.27 (0.25–0.30) | not resolved (±44.79) | 74.2 | 0.0 | 100 / 0 | 4424 | 6 | 1 | 0.10 | 280 | 0 |
| mcast | 100 | 0.27 (0.15–0.40) | 0.28 (0.05–0.55) | 0.20 (0.20–0.20) | not resolved (±8.27) | 7.4 | 0.0 | 10 / 0 | 4428 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 100 | 0.63 (0.45–1.00) | 0.28 (0.05–0.55) | 1.30 (1.25–1.35) | not resolved (±10.61) | 766.1 | 66.1 | 1000 / 1001 | 4692 | 106 | 100 | 1.03 | 280 | 0 |
| udp | 100 | 0.37 (0.25–0.55) | 0.28 (0.05–0.55) | 0.55 (0.55–0.55) | not resolved (±7.28) | 741.9 | 0.0 | 1000 / 0 | 4436 | 6 | 1 | 0.39 | 280 | 0 |
| mcast | 1000 | 0.82 (0.60–1.05) | 0.35 (0.25–0.45) | 0.30 (0.20–0.45) | not resolved (±0.50) | 7.4 | 0.0 | 10 / 0 | 4548 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 1000 | 11.58 (10.80–12.20) | 0.35 (0.25–0.45) | 11.55 (11.40–11.85) | 11.23 (9.28–13.18) | 7669.2 | 660.8 | 10012 / 10012 | 5272 | 1006 | 1000 | 11.22 | 280 | 0 |
| udp | 1000 | 4.18 (4.00–4.50) | 0.35 (0.25–0.45) | 3.90 (3.85–4.00) | 3.83 (3.08–4.58) | 7420.4 | 0.0 | 10001 / 0 | 4512 | 6 | 1 | 3.69 | 280 | 0 |
| mcast | 5000 | 2.78 (1.80–4.60) | 1.00 (0.55–1.70) | 0.15 (0.10–0.20) | not resolved (±0.48) | 7.4 | 0.0 | 10 / 0 | 4428 | 6 | 1 | 0.04 | 280 | 0 |
| tcp | 5000 | 61.47 (59.34–64.89) | 1.00 (0.55–1.70) | 59.46 (57.64–62.89) | 12.09 (10.43–13.76) | 38304.1 | 3300.8 | 50005 / 50012 | 7856 | 5006 | 5000 | 56.83 | 280 | 0 |
| udp | 5000 | 17.88 (16.65–19.69) | 1.00 (0.55–1.70) | 17.76 (17.25–18.14) | 3.38 (2.32–4.43) | 37140.0 | 0.0 | 50054 / 0 | 4828 | 6 | 5 | 17.26 | 280 | 0 |

Memory, N ≥ 1 000 (first run of each; slab is host-wide, so it counts both ends of every TCP connection). With nothing running, the slab moved -2040 to -108 kB over one window (the idle controls), so rows for N ≤ 100 are noise; they are in `results/e2/e2_fanout.json`.

| mode | N | slab Δ kB (both ends) | TCP sockets in use (tx ns) | TCP mem pages (host) | Σ skmem t (tx) | Σ skmem w (tx) | receiver RSS kB |
|---|---|---|---|---|---|---|---|
| mcast | 1000 | 2208 | 0 | 0 | – | – | 9940 |
| mcast | 5000 | 17424 | 0 | 0 | – | – | 31036 |
| tcp | 1000 | 7680 | 1001 | 0 | 0 | 0 | 16632 |
| tcp | 5000 | 48680 | 5001 | 0 | 3064 | 12256 | 55148 |
| udp | 1000 | 2636 | 0 | 0 | – | – | 9952 |
| udp | 5000 | 18172 | 0 | 0 | – | – | 31496 |

**Reading.**
- **Below 1 000 listeners the cost is not resolved.** Every mode keeps CPU 0 at 0.22-0.63% busy on average, against 0.28-0.37% in the matched idle windows, so the listeners' CPU is inside the noise and no cost is given there. Multicast is not resolved at any N.
- **Per listener, TCP costs 2.9-3.6× what UDP does.**
  - TCP: 11.2-12.1 µs of sending-host CPU per listener and frame (one `write()` plus the ACK it triggers); 95% intervals 9.3-13.2 µs at N = 1 000 and 10.4-13.8 µs at N = 5 000.
  - UDP unicast with `sendmmsg`: 3.4-3.8 µs (3.1-4.6 µs at 1 000, 2.3-4.4 µs at 5 000).
  - At 5 000 listeners that is 61.5% against 17.9% of a vCPU.
  - Multicast is flat: CPU 0 at 0.3-2.8% busy on average whatever N, against 0.3-1.0% idle, with one `sendto()` per frame. Its fan-out moves to the network and to the receiving hosts; here one namespace cloned each datagram to 5 000 sockets.
- **CPU is not what decides feasibility.** Extrapolated linearly, 100 000 TCP listeners at 1 frame/s need about 1.1-1.2 cores of this VM. That agrees with epoll servers routinely holding 100k+ connections.
- **What differs more than CPU:**
  - Packets: one 66 B ACK comes back per data segment. That is 2× the packets and 660 B/s inbound per listener (+8.6% bytes).
  - State: one fd and one kernel socket per listener, 5 006 fds against 6.
    - The slab grew 48.7 MB for 5 000 connections with both ends on this host: about 4.9 KB per idle socket end, before any queued data. E3 shows queued data reaching megabytes.
    - Go-side RSS grew 3.0 MB, about 0.6 KB per connection.
    - The UDP sender holds one socket; the 18.2 MB slab growth in the UDP run is the 5 000 receiver sockets.
  - Syscalls: 5 000 per frame, against 5 (`sendmmsg`, 1 024 per call) or 1 (multicast).
  - Sender enqueue time: handing one frame to the kernel for all 5 000 listeners took 56.8 ms over TCP (median; 5 000 `write()` calls), 17.3 ms with `sendmmsg` (5 calls) and 0.04 ms with multicast (one `sendto()`). It is timed on the sender's clock around its send loop. There are no receiver timestamps, so the arrival spread (when the last listener received the frame) was not measured.
  - This field was called `fanout_spread_*_us` in the first E2 run. It is the same measurement, named `enqueue_all_*_us` in `fanout/main.go` and in `results/e2/e2_fanout.json`.
- **Portability.** Absolute µs are for this VM (virtualised, 4 vCPUs); the ratios carry over.

## E3: slow and dead consumers

*`results/e3-slow/`: run `20260927T232539Z-9516-e2aa`, 2026-09-27T23:25:39Z to 2026-09-27T23:35:56Z, commit `971846eab060` (clean), sources sha256 `b01f11fa57ba`.*

**Slow consumer** (listener 0 stops reading at t = 10 s; 100 listeners, 10 × 700 B frames/s, 600 s runs). *victim unread* = FIONREAD on the victim's TCP socket at the end.

| variant | victim SO_RCVBUF | sender stalled at (s) | healthy latency p99 / max ms (delivered frames only) | healthy: last frame at (s, median) | healthy frames min / expected | victim app queue peak B | frames dropped for victim | victim disconnected at (s) | sender RSS kB | victim unread B at end | UDP RcvbufErrors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tcp-blocking | 65536 | 39.61 | 3.9 / 4.6 | 39.5 | 291 / 5890 | 0 | 0 | – | 46412 → 46924 | 118020 | 0 |
| tcp-queue | 65536 | none | 4.4 / 33.4 | 599.4 | 5889 / 5890 | 3929100 | 0 | – | 46464 → 51020 | 118020 | 0 |
| tcp-drop | 65536 | none | 5.1 / 40.4 | 599.45 | 5890 / 5890 | 65100 | 5520 | – | 46360 → 46824 | 118020 | 0 |
| tcp-disconnect | 65536 | none | 5.4 / 14.6 | 599.49 | 5890 / 5890 | 65800 | 0 | 48.79 | 46432 → 46700 | 118020 | 0 |
| udp | 65536 | none | 4.4 / 24.6 | 599.41 | 5890 / 5890 | 0 | – | – | 46308 → 46448 | – | 5865 |
| tcp-blocking-autotuned | autotuned | none | 6.0 / 17.8 | 599.42 | 5890 / 5890 | 0 | 0 | – | 46412 → 46796 | 4118100 | 0 |
| udp-autotuned | autotuned | none | 4.0 / 19.6 | 599.4 | 5890 / 5890 | 0 | – | – | 46268 → 46412 | – | 5828 |

*`results/e3-dead/`: run `20260927T232539Z-9517-7e7b`, 2026-09-27T23:25:39Z to 2026-09-27T23:42:31Z, commit `971846eab060` (clean), sources sha256 `b01f11fa57ba`.*

**Dead listener** (listener 0 of 100 vanishes at t ≈ 10 s).

| variant | sender notices after | retransmissions | held for the dead listener | sender RSS kB | healthy latency p99 / max ms | note |
|---|---|---|---|---|---|---|
| tcp-kill | 0.002 s (EOF) | 0 (max RTO 204.0 ms) | 0 B app + 0 B kernel | 46460 → 46480 | 3.0 / 9.0 |  |
| tcp-silent-uto30s | 30.347 s (TimeoutError) | 8 (max RTO 26112.0 ms) | 138600 B app + 71400 B kernel | 46404 → 46564 | 6.1 / 55.0 |  |
| tcp-silent | 938.739 s (TimeoutError) | 16 (max RTO 120000.0 ms) | 6497400 B app + 71400 B kernel | 46472 → 54068 | 6.8 / 52.9 |  |
| udp-lease | lease lapsed 65.1 s (p50), 53.7–75.0 s | 0 | ≈651.5 datagrams (p50) | – | 3.6 / 24.1 | 20 died, 20 lapsed, 0 healthy lapsed |

**Reading.**
- **Blocking writer: one slow reader stops everyone.**
  - The victim's SO_RCVBUF was fixed at 64 KiB (128 KiB effective).
  - About 207 KB fitted in the kernel: 118 KB unread at the victim plus the sender's send buffer.
  - At 39.61 s the single-threaded writer blocked in `sendall()` for good. The other 99 listeners got their last frame at t = 39.5 s: 291 of 5 890 frames.
- **Surprise: an autotuned receiver never pushes back.**
  - This kernel (6.18, `tcp_rmem` max 32 MiB) kept growing the receive buffer of a socket that had stopped reading.
  - After 590 s the victim held 4 118 100 unread bytes. The window never closed, and even the blocking writer never stalled.
  - A TCP relay cannot see such a consumer by backpressure. When the consumer resumes, it reads ten minutes of stale frames first.
- **Queues.**
  - Non-blocking with an unbounded per-listener queue: the others keep up (p99 4.4 ms; 5 889-5 890 of 5 890 frames each), and the queue grows at the stream rate, to 3.93 MB by 600 s (sender RSS +4.6 MB).
  - Capping it at 64 KiB with drop-oldest keeps memory flat: 5 520 frames dropped for the victim.
  - Disconnect-at-cap cut the victim at 48.8 s.
  - The relay must pick one of these policies, and hold per-listener state to apply it.
- **UDP needs none of this.**
  - The slow socket overflowed on its own (5 865 `RcvbufErrors`).
  - The sender and the other 99 listeners were unaffected: p99 4.4 ms, 5 890 of 5 890 frames.
- **Dead listeners.**
  - SIGKILL is noticed in 2 ms: the dead process's kernel sends FIN.
  - A host that silently vanishes is noticed only after 939 s: 16 retransmissions, with the RTO growing from 204 ms to the 120 s cap. Meanwhile the sender held 71.4 KB in the kernel and 6.50 MB in the unbounded app queue.
  - TCP_USER_TIMEOUT = 30 s aborted at 30.3 s. Every TCP relay needs this knob.
  - The UDP lease lapsed 53.7-75.0 s after death (p50 65.1 s), inside RFC-0001's bound of [75 − 26.4, 75] s to within this measurement's 0.1 s resolution. About 650 datagrams (455 KB) went into the void per dead listener, with no retransmission and no growing state.

## E4: late joiner

*`results/e4/`: run `20260927T232539Z-9518-adbb`, 2026-09-27T23:25:39Z to 2026-09-27T23:35:47Z, commit `971846eab060` (clean), sources sha256 `ed7084c5534c`.*

20 live items, 327 B frames; effective loops {'slow': [13080], 'fast': [1000]} ms; 10 joiners per arm back to back for 600 s; timeout 120 s. Time to hold all 20, Kaplan–Meier over every join (a join that timed out or was cut off by the end of the run is censored at its elapsed time), ms (s where marked); *max done* is the slowest completed join.

| loss | arm | joins | completed | timeouts | cut at end | p50 | p90 | p99 | max done |  |
|---|---|---|---|---|---|---|---|---|---|---|
| 0% | carousel-4kbps | 342 | 335 | 0 | 7 | 14.9 s | 16.4 s | 17.0 s | 17.4 s |  |
| 0% | carousel-1s | 1529 | 1529 | 0 | 0 | 1130.0 | 1254.0 | 1307.1 | 1328.6 |  |
| 0% | tcp-snapshot | 2136 | 2136 | 0 | 0 | 0.5 | 0.8 | 2.7 | 20.4 | connect p50/p99 0.5/2.7; server snapshots 2136 |
| 0% | lease-snapshot | 1388 | 1388 | 0 | 0 | 1570.1 | 1576.1 | 1584.1 | 1631.7 | handshake p50/p99 0.2/3.7; relay snapshots 1388 for 1388 sessions |
| 5% | carousel-4kbps | 265 | 258 | 0 | 7 | 18.8 s | 28.5 s | 39.6 s | 45.6 s |  |
| 5% | carousel-1s | 1368 | 1368 | 0 | 0 | 1404.7 | 2109.8 | 2958.7 | 5036.2 |  |
| 5% | tcp-snapshot | 2000 | 2000 | 0 | 0 | 0.5 | 1018.3 | 2041.1 | 7367.9 | connect p50/p99 0.5/1032.1; server snapshots 2000 |
| 5% | lease-snapshot | 631 | 629 | 0 | 2 | 4664.3 | 14.3 s | 25.4 s | 38.8 s | handshake p50/p99 0.3/3002.0; relay snapshots 631 for 631 sessions |
| 30% | carousel-4kbps | 143 | 135 | 0 | 8 | 37.4 s | 56.7 s | 77.8 s | 81.6 s |  |
| 30% | carousel-1s | 1012 | 1012 | 0 | 0 | 2917.9 | 4607.4 | 6652.4 | 8892.0 |  |
| 30% | tcp-snapshot | 307 | 283 | 17 | 7 | 2242.4 | 67.7 s | > 120.0 s | 117.0 s | connect p50/p99 1000.8/4280.9; server snapshots 304 |
| 30% | lease-snapshot | 176 | 168 | 0 | 8 | 28.5 s | 55.5 s | 87.8 s | 93.4 s | handshake p50/p99 1004.3/43.7 s; relay snapshots 176 for 176 sessions |

**Setup notes.**
- Each lease join is a new session from a new socket with a fresh client nonce. The relay keys leases by session (address and nonce, which is what its cookie validates), snapshots each new session once, and forwards the carousel once per address. The joiner RENEWs every 22 s × U(0.8, 1.2) (§11.3.5), so a join that runs past 75 s keeps its lease.
- *Relay snapshots* equal lease sessions at every loss level (631 of 631 at 5%, 176 of 176 at 30%). In the first run, which keyed leases by address, a session whose predecessor's BYE was lost got none: 560 snapshots for 591 joins at 5%, 117 for 160 at 30%.
- A join still running at the end of the run is censored at its elapsed time instead of being dropped (7-8 per carousel-4kbps row).

**Reading.**
- **No loss: TCP connect-plus-snapshot wins by three orders of magnitude.** 0.5 ms p50, against 1.13 s for a 1 s carousel and 1.57 s for a lease snapshot.
- **The default budget makes the carousel slow to catch up.**
  - `B_stream` = 4 kbit/s shared by 20 items of 327 B gives a fair-share loop of 13.08 s, not the 5 s class floor.
  - Passive catch-up is then 14.9 s at p50 with no loss, and 37.4 s at 30%.
  - Loop and budget, not the protocol, decide catch-up time.
- **The lease snapshot is paced, and that makes it slow.**
  - At `granted_bps` = 32 kbit/s (§7.10), 20 × 327 B take 1.57 s.
  - A lost snapshot frame waits for the relay-forwarded 13 s loop, so p50 rises to 4.7 s at 5% loss and 28.5 s at 30% (p99 25.4 s and 87.8 s).
  - Repeat the snapshot, pace it faster, or loop toward new leases at a shorter period.
- **Under loss, TCP's handshake is the weak point.**
  - A lost SYN or SYN-ACK costs the 1 s initial RTO, then 3 s, 7 s: p90 1.02 s at 5%.
  - At 30%: p50 2.24 s, p90 67.7 s, and 17 of 307 joins unfinished at 120 s (7 more were cut off by the end of the run). More than 1% of joins never finished, so the p99 lies beyond the 120 s timeout. The slowest join that finished took 117.0 s.
  - The 1 s carousel at 30%: 2.92 s p50, 6.65 s p99, 8.89 s max, and no failures.

## E5: reconnect storm

**Setup.**
- A relay serves 1 000 listeners a 20-item snapshot (20 × 330 B). It is killed with SIGKILL, and a new relay process starts at once on the same port; it is up 0.11-0.18 s later.
- TCP listeners reconnect immediately, retry every 100 ms while the port refuses, and time out after 5 s without a snapshot.
- UDP listeners follow §11.3: 3 missed relay beacons at 5 s, then HELLO/COOKIE/LISTEN with 1-2-4-8 s retransmits, then a paced snapshot.
- No loss.
- Three timed runs each, plus one `strace -c` pass (not timed) to count the new relay's syscalls. Relays and clients are Python.

*`results/e5/`: run `20260928T000605Z-12752-2e17`, 2026-09-28T00:06:05Z to 2026-09-28T00:08:29Z, commit `971846eab060` (clean), sources sha256 `230be7341cbf`.*

N = 1000 listeners, 20 × 330 B snapshot. Times in s from SIGKILL of the old relay.

| mode | backlog | rep | pass | new relay up | all served | served p50 / p99 | ListenOverflows | SYN retrans | UDP RcvbufErrors | packets | relay syscalls | listener attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tcp | 128 | 0 | timed | 0.141 | 6.2807 | 0.3 / 6.3 | 467 | 365 | 0 | 12803 | – | {"connect": 2105, "refused": 1002, "snapshot_timeout": 103} |
| tcp | 4096 | 0 | timed | 0.149 | 0.287 | 0.3 / 0.3 | 0 | 18 | 0 | 10991 | – | {"connect": 1706, "refused": 1000, "snapshot_timeout": 0} |
| udp-lease | – | 0 | timed | 0.135 | 13.2033 | 13.2 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |
| tcp | 128 | 0 | strace | 0.124 | 12.4249 | 1.3 / 12.4 | 1828 | 819 | 0 | 20405 | 10965 | {"connect": 2565, "refused": 1014, "snapshot_timeout": 549} |
| tcp | 4096 | 0 | strace | 0.14 | 0.6971 | 0.6 / 0.7 | 0 | 0 | 0 | 10888 | 6075 | {"connect": 2005, "refused": 1005, "snapshot_timeout": 0} |
| udp-lease | – | 0 | strace | 0.117 | 20.1735 | 14.3 / 20.2 | 0 | 0 | 1164 | 27120 | 51422 | {"hello": 1628, "listen": 1536, "renew": 0} |
| tcp | 128 | 1 | timed | 0.123 | 6.2298 | 0.2 / 6.2 | 470 | 334 | 0 | 13412 | – | {"connect": 1136, "refused": 1000, "snapshot_timeout": 136} |
| tcp | 4096 | 1 | timed | 0.182 | 0.341 | 0.3 / 0.3 | 0 | 0 | 0 | 11011 | – | {"connect": 2016, "refused": 1016, "snapshot_timeout": 0} |
| udp-lease | – | 1 | timed | 0.112 | 13.2126 | 13.2 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |
| tcp | 128 | 2 | timed | 0.128 | 6.2866 | 0.3 / 6.3 | 456 | 375 | 0 | 12542 | – | {"connect": 2081, "refused": 1000, "snapshot_timeout": 81} |
| tcp | 4096 | 2 | timed | 0.137 | 0.3024 | 0.3 / 0.3 | 0 | 0 | 0 | 10860 | – | {"connect": 2004, "refused": 1004, "snapshot_timeout": 0} |
| udp-lease | – | 2 | timed | 0.135 | 13.1888 | 13.1 / 13.2 | 0 | 0 | 0 | 24000 | – | {"hello": 1000, "listen": 1000, "renew": 0} |

**Reading.**
- **TCP notices at once.** The dead relay's kernel sends FIN, and 1 000-1 016 connects are refused while the new relay starts.
- **Backlog 4 096: back in 0.3 s.**
  - All 1 000 were re-served 0.29-0.34 s after the kill, 0.14-0.17 s after the new relay was up. No overflows; one of the three timed runs saw 18 SYN retransmits.
  - About 6 syscalls per listener (strace: 1 013 `accept4`, 1 000 `sendto`, 1 000 `epoll_ctl`, 2 000 `getsockname`).
- **Backlog 128: 6.23-6.29 s.**
  - 625-666 of the 1 000 were back within 0.5 s, and 864-919 within 2 s after one SYN retransmission at 1 s (334-375 SYN retransmits, 456-470 ListenOverflows).
  - The rest (81-136) were half-open: with the accept queue full, SYN cookies completed the handshake at the client, the final ACK was dropped, and the relay kept no state. Only the 5 s client timeout recovered them.
  - In a first run without that timeout, 101 of 1 000 clients hung in ESTABLISHED indefinitely. Note that asyncio's default backlog is 100.
- **UDP leases: 13.19-13.21 s in all three runs, every listener at once.**
  - The restarted relay has a new cookie secret and no leases, so it stays silent (§11.3.1).
  - Listeners notice only after 3 × 5 s without a relay beacon, then re-lease in milliseconds.
  - The HELLO storm (1 000 × 256 B at once) fitted the relay's default receive buffer in the timed runs. In the slower strace pass it overflowed (1 164 `RcvbufErrors`), and retransmits stretched recovery to 20.2 s.
- **Cost.** The paced UDP snapshot is one datagram per item per listener, about 24 `sendto` per listener with COOKIE, LISTEN_OK and beacons (23 956 in the strace pass). TCP needs one `write` per listener.
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
| **Binary plane, station/relay → listeners** | **UDP carousel** (unicast leases, LAN multicast); QUIC DATAGRAM / WebTransport for browsers and NAT-hostile paths | Bounded staleness under 20-30% loss and outages (E1 at 30%: every update delivered and at most 3.5-10 s stale, against TCP stalls of 43-836 s and up to 64% of updates undelivered). A slow or dead listener costs the sender nothing (E3). UDP unicast is 3.4-3.8 µs per listener·frame against TCP's 11.2-12.1 µs, with half the packets and no per-listener socket; multicast is flat on a LAN (E2). Keep the burst. Offer the 1 s floor where post-outage freshness matters, and budget it (9.6 copies/update at U = 10 s). |
| Binary plane, **relay ↔ relay backbone** | **TCP/QUIC stream** (D10: NATS), latest-only per key, bounded drop-oldest queues, TCP_USER_TIMEOUT | Backbone links are few and usually healthy. At ≤ 10% loss TCP repairs in one RTO (E1: 210-211 ms against 1 s) and carries each item once instead of looping it. Guard against E1's backoff tails and E3's silent peers. |
| Late-joiner catch-up | Relay snapshot over **TCP or QUIC** when the path is good; carousel when it is not | E4: TCP snapshot 0.5 ms against 1.1-15 s passive, but at 30% loss 17 of 307 joins were not done in 120 s. The lease snapshot as specified (paced, once) is slower than both at 5%: repeat it or pace it faster. |
| Ledger plane (durable truth, promotion, ringserver replay/dashboards) | **TCP** (DataLink/SeedLink, §18) | Reliability and order are the requirement there, not freshness. |
| Control plane (addressed work, acks) | **TCP/QUIC** (the harness's own queues) | Needs reliability and flow control. E3 shows the price: per-peer queues and a user timeout. |
| Membership (beacons, presence) | **UDP**, as specified | Periodic and loss-tolerant. E5: relay-restart detection took 13.2 s (3 × 5 s beacons). Persist the cookie secret and leases across restarts, or shorten `relay_beacon_ms` toward leases, if that matters. |

## Surprises

- **Linux 6.18 grows the receive buffer of a socket that has stopped reading.** It reached 4.1 MB over 590 s at 7 KB/s, and backpressure never came. Kernel buffering hides a slow consumer from its sender and turns it into a stale consumer.
- **At U = 0.5 s and 30% loss, most `tcp-stream` updates never arrived.** 64% of (update, receiver) pairs were still undelivered 20 s after the last update of a 900 s run, so TCP's median latency there is beyond what the run could observe.
- **TCP delivered 1 292 frames after their own signed expiry** (U = 0.5 s, 30%). A byte stream does not know about TTLs, so the receiver's `expires_at` check is load-bearing over TCP too (RFC-0001 I-3, §20.3).
- **SRTT inflation.** At 20% loss one connection's RTO reached 120 s at a backoff of at most 1, and at 30% TCP_INFO showed a 5.5 s RTO at backoff 0: SRTT itself had inflated, not only the RTO doubled.
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
