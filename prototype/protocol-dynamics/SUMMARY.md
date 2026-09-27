# protocol-dynamics: results

Measured on 2026-09-27 on one Linux 6.18 host (4 vCPUs). Every condition ran in
its own network namespace; loss was dropped by nftables in both directions
unless marked *data-only*. There is no delay emulation, so RTT is about 0.1 ms
and every TCP recovery time below is the floor set by Linux's timers (see
[What internet RTTs change](#what-internet-rtts-change)). Testbed, method and
limitations are in [README.md](README.md). All numbers come from
`results/*.json`, and `python summarize.py` prints these tables.

## Bottom line

- **At low loss (≤ 10%) on a healthy connection, TCP keeps a receiver fresher than the carousel.**
  TCP repairs a lost update in one RTO, about 205-212 ms here. The carousel waits for its next copy: the +1 s burst, or the next update.
  - U = 10 s, 5% loss: p99 212 ms (TCP) against 1 004-1 007 ms (UDP).
  - U = 2 s, 10% loss: TCP holds a superseded value 1.2-1.3% of the time, UDP 5.6-5.7%.
- **TCP's failure mode is an unbounded tail; the carousel's is bounded.**
  - With 20-30% loss in both directions, TCP's RTO backoff reaches the 120 s cap. Single stalls last up to 697 s, and head-of-line blocking queues every superseded value behind the stall.
  - U = 0.5 s, 30% loss: the median update reached a TCP receiver 187 s late, receivers held a stale value 89% of the time, and 2 690 frames arrived after their own signed expiry.
  - The carousel at the same point: p99 1.5 s, max 4.0 s, stale 30% of the time, which is the loss rate.
  - With ACKs spared (data-only loss), TCP at 30% stays usable: p99 0.85-5.2 s. Its max is still 13-27 s, against 4.5-10 s for the carousel.
- **After outages, TCP resumes late.**
  - After a 10 s outage, TCP needed p95 3.9-6.1 s to deliver the newest value. That is RTO backoff: 408 → 816 → 1 632 → 3 264 → 6 528 ms.
  - The carousel needed p95 0.48-0.91 s with frequent updates, and 1.73 s (1 s loop) or 3.47 s (5 s loop) at U = 10 s.
  - After 1-3 s outages the two are comparable.
- **Fan-out (E2): TCP costs about 2.7× more CPU per listener than UDP unicast.**
  - Per listener and frame: TCP 11.6-12.0 µs of sending-host CPU (the write plus the ACK it triggers), UDP with `sendmmsg` 4.2-4.4 µs. Multicast stays at about 2% of a core whatever N.
  - At 5 000 listeners × 10 frames/s: 60.7% against 22.0% of a vCPU.
  - TCP also doubles the packets (one ACK per segment) and needs 5 006 fds against 6.
  - It reaches its last listener 56.7 ms after its first, against 18.4 ms for `sendmmsg`.
  - Either is feasible; the difference is cost per listener, not whether it works.
- **Slow and dead consumers (E3).**
  - With a blocking writer, one listener that stops reading stalls all 100, 29 s after it stops (64 KiB buffers).
  - With Linux's autotuned receive buffer the sender never notices: after 590 s the reader held 4.1 MB of unread, 10-minute-old data.
  - A silently vanished TCP listener is aborted only after 938 s. Meanwhile an unbounded queue grew to 6.5 MB and the kernel retransmitted 16 times. TCP_USER_TIMEOUT = 30 s cut that to 30.4 s.
  - UDP: the slow socket overflowed alone (5 863 drops), and a dead lease lapsed after 54-74 s with no retransmission and no per-listener buffer.
- **Late joiners (E4).**
  - At 0% loss TCP connect-plus-snapshot is by far the fastest: 0.4 ms p50, against 1.1 s for a 1 s carousel and 14.4 s at the default 4 kbit/s budget.
  - At 30% loss, SYN loss hurts TCP: p50 2.1 s, p99 96 s, and 6.5% of joins not done in 120 s. The 1 s carousel does 3.0 s p50 and 6.0 s p99.
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
- *Stale %*: fraction of time a receiver holds a value that has already been superseded, sampled every 5 ms.
- *Outages* were placed so that one update is issued inside each.

**U = 0.5 s**, loss on every packet (both directions); update latency p95 / p99 / max in ms (s where marked); stale time % in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) |
|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.0 / 2.5 / 10.3 | 2.1 / 2.8 / 11.0 | 1.8 / 2.4 / 8.2 | 1.8 / 2.3 / 6.9 | 0.21 / 0.21 / 0.19 / 0.19 |
| 1% | 1.0% | 2.2 / 499.7 / 1001.1 | 2.2 / 498.4 / 1001.9 | 2.0 / 41.4 / 421.5 | 2.0 / 5.9 / 420.5 | 1.32 / 1.23 / 0.62 / 0.61 |
| 5% | 4.9% | 7.9 / 502.1 / 1501.9 | 6.7 / 502.1 / 1501.4 | 204.9 / 212.6 / 2640.8 | 6.5 / 212.4 / 1189.3 | 5.17 / 5.08 / 2.56 / 2.40 |
| 10% | 10.0% | 501.2 / 505.3 / 2001.7 | 501.2 / 999.5 / 2001.5 | 207.9 / 415.8 / 3331.4 | 208.0 / 419.1 / 6819.5 | 10.03 / 10.10 / 5.65 / 5.77 |
| 20% | 19.9% | 502.9 / 1003.3 / 3002.9 | 502.6 / 1002.5 / 4002.2 | 2342.2 / 18.6 s / 83.5 s | 7312.8 / 154.8 s / 333.8 s | 20.33 / 19.84 / 20.94 / 23.63 |
| 30% | 30.0% | 1001.2 / 1502.5 / 3998.8 | 1001.3 / 1502.5 / 4002.1 | 651.0 s / 756.0 s / 841.0 s | 333.4 s / 537.4 s / 670.9 s | 30.18 / 30.22 / 89.37 / 79.39 |

**U = 2 s**, loss on every packet (both directions); update latency p95 / p99 / max in ms (s where marked); stale time % in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) |
|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.2 / 3.1 / 5.2 | 2.1 / 2.5 / 4.5 | 1.9 / 2.7 / 9.1 | 1.8 / 2.4 / 3.5 | 0.05 / 0.05 / 0.05 / 0.05 |
| 1% | 1.0% | 2.4 / 1001.1 / 2002.0 | 2.5 / 1001.0 / 2003.4 | 2.1 / 7.2 / 215.2 | 2.2 / 6.3 / 419.5 | 0.64 / 0.62 / 0.16 / 0.15 |
| 5% | 5.0% | 4.4 / 1005.0 / 2002.6 | 54.4 / 1004.4 / 2003.1 | 14.1 / 212.3 / 1671.5 | 15.1 / 212.3 / 856.0 | 2.59 / 2.65 / 0.63 / 0.61 |
| 10% | 10.0% | 1002.2 / 1617.9 / 4000.7 | 1002.2 / 1999.8 / 4001.5 | 208.8 / 413.1 / 1688.7 | 208.8 / 413.0 / 1352.5 | 5.56 / 5.69 / 1.28 / 1.23 |
| 20% | 20.0% | 1007.1 / 2003.0 / 6001.2 | 1006.2 / 2003.0 / 5005.2 | 414.1 / 4626.2 / 104.7 s | 705.7 / 259.2 s / 438.0 s | 12.46 / 11.83 / 4.47 / 6.74 |
| 30% | 30.2% | 2001.3 / 3004.6 / 10.0 s | 2001.3 / 3004.4 / 8000.8 | 200.8 s / 525.2 s / 703.9 s | 172.3 s / 313.4 s / 448.0 s | 19.36 / 19.27 / 26.34 / 29.83 |

**U = 10 s**, loss on every packet (both directions); update latency p95 / p99 / max in ms (s where marked); stale time % in arm order.

| loss | measured | udp-live | udp-ctl | tcp-stream | tcp-latest | stale % (udp-live / udp-ctl / tcp-stream / tcp-latest) |
|---|---|---|---|---|---|---|
| 0% | 0.0% | 2.0 / 3.7 / 3.7 | 2.0 / 2.5 / 2.6 | 1.9 / 3.2 / 3.5 | 2.0 / 3.0 / 3.2 | 0.01 / 0.01 / 0.01 / 0.01 |
| 1% | 1.0% | 2.1 / 2.7 / 2001.9 | 1.9 / 2.3 / 1006.9 | 2.0 / 5.4 / 416.7 | 1.8 / 208.3 / 212.7 | 0.10 / 0.10 / 0.03 / 0.04 |
| 5% | 4.9% | 1000.9 / 1006.5 / 2002.4 | 2.1 / 1004.2 / 1009.1 | 2.4 / 212.2 / 420.3 | 204.7 / 212.0 / 424.5 | 0.57 / 0.48 / 0.12 / 0.12 |
| 10% | 10.0% | 1001.7 / 1005.6 / 2009.3 | 1002.2 / 2000.9 / 2006.3 | 207.6 / 414.9 / 1681.8 | 207.8 / 215.4 / 851.6 | 0.92 / 1.15 / 0.26 / 0.25 |
| 20% | 19.9% | 1007.2 / 2004.7 / 9939.0 | 1006.8 / 2008.6 / 5156.3 | 214.8 / 657.3 / 6786.4 | 214.7 / 632.7 / 6770.7 | 2.59 / 2.84 / 0.62 / 0.59 |
| 30% | 29.8% | 2002.7 / 4002.5 / 12.0 s | 2002.6 / 4005.8 / 6318.7 | 3456.4 / 116.4 s / 204.5 s | 842.9 / 65.4 s / 204.1 s | 4.40 / 4.36 / 5.56 / 3.38 |

**Data-only loss** (pure ACKs, SYN and FIN spared); update latency p95 / p99 / max in ms.

| U | loss | udp-live | udp-ctl | tcp-stream | tcp-latest |
|---|---|---|---|---|---|
| 0.5 s | 10% | 501.3 / 999.4 / 2001.8 | 501.2 / 504.3 / 2500.6 | 207.6 / 414.8 / 3134.8 | 207.5 / 414.2 / 6507.4 |
| 0.5 s | 20% | 502.4 / 1002.4 / 3004.1 | 502.6 / 1002.7 / 4001.6 | 351.6 / 852.0 / 26.6 s | 364.2 / 856.1 / 6840.1 |
| 0.5 s | 30% | 1001.5 / 1503.3 / 4499.0 | 1001.4 / 1502.5 / 6500.6 | 850.9 / 5222.7 / 26.8 s | 843.4 / 3351.1 / 26.7 s |
| 2 s | 10% | 1002.2 / 1999.9 / 3018.5 | 1002.2 / 1999.7 / 3004.9 | 208.2 / 220.0 / 1472.4 | 208.2 / 414.8 / 848.2 |
| 2 s | 20% | 1005.5 / 2002.3 / 6001.5 | 1005.6 / 2002.5 / 4004.3 | 216.9 / 649.4 / 3336.7 | 216.9 / 643.4 / 6713.1 |
| 2 s | 30% | 2001.4 / 3004.9 / 7007.6 | 2001.7 / 3009.0 / 8002.2 | 420.8 / 1684.8 / 13.3 s | 420.0 / 1672.6 / 26.4 s |
| 10 s | 10% | 1001.8 / 1006.7 / 4001.9 | 1002.3 / 1217.0 / 4007.3 | 208.9 / 261.4 / 844.6 | 208.9 / 262.1 / 1680.6 |
| 10 s | 20% | 1006.5 / 2007.2 / 11.0 s | 1006.4 / 2007.8 / 5287.6 | 219.7 / 636.2 / 1660.6 | 220.6 / 693.1 / 3132.4 |
| 10 s | 30% | 2002.3 / 4005.5 / 10.0 s | 2002.1 / 4002.2 / 6974.4 | 416.3 / 985.9 / 13.3 s | 420.0 / 853.0 / 13.3 s |

**Outages.** Recovery after the outage ends (time until the receiver holds the newest value) p50 / p95 / max · median latency of updates issued inside the outage, ms. 20 receivers per arm.

| outage | U | outages | udp-live | udp-ctl | tcp-stream | tcp-latest |
|---|---|---|---|---|---|---|
| 1 s | 0.5 s | 54 | 254.0 / 452.4 / 475.1 · 999.1 | 254.0 / 454.7 / 475.9 · 999.2 | 223.3 / 783.9 / 823.7 · 844.5 | 226.8 / 757.2 / 823.8 · 844.5 |
| 1 s | 2 s | 50 | 503.6 / 883.9 / 929.4 · 1001.8 | 505.9 / 884.6 / 929.3 · 1001.8 | 159.5 / 799.6 / 815.6 · 827.1 | 159.5 / 799.6 / 815.7 · 827.3 |
| 1 s | 10 s | 45 | 575.9 / 898.3 / 918.4 · 1001.9 | 576.0 / 896.1 / 918.6 · 1001.5 | 124.0 / 752.1 / 819.6 · 424.3 | 119.1 / 752.1 / 819.6 · 419.4 |
| 3 s | 0.5 s | 46 | 283.1 / 453.4 / 473.3 · 1997.5 | 283.1 / 453.1 / 473.6 · 1998.2 | 620.0 / 794.6 / 804.0 · 1863.5 | 656.0 / 827.2 / 835.6 · 1896.6 |
| 3 s | 2 s | 44 | 579.6 / 889.6 / 958.1 · 2001.1 | 580.6 / 890.1 / 958.2 · 2001.4 | 719.6 / 1409.8 / 1575.8 · 1687.3 | 719.6 / 1409.8 / 1575.8 · 1687.3 |
| 3 s | 10 s | 40 | 641.0 / 1746.4 / 1973.4 · 2001.2 | 641.1 / 1746.3 / 1979.1 · 2001.7 | 565.5 / 1477.3 / 1578.5 · 1683.5 | 565.6 / 1477.3 / 1578.4 · 1683.5 |
| 10 s | 0.5 s | 30 | 253.7 / 475.9 / 1576.1 · 5500.3 | 253.3 / 476.1 / 1580.8 · 5500.1 | 3635.8 / 3874.0 / 3968.6 · 8790.1 | 3747.0 / 3998.8 / 4076.9 · 8876.2 |
| 10 s | 2 s | 29 | 421.0 / 905.7 / 949.2 · 6000.0 | 420.8 / 906.3 / 949.3 · 6000.0 | 4336.9 / 5106.8 / 5415.9 · 9403.1 | 4381.0 / 5155.2 / 5453.8 · 9455.8 |
| 10 s | 10 s | 26 | 1248.5 / 3466.0 / 4118.7 · 5772.4 | 644.4 / 1731.7 / 1926.0 · 4380.4 | 929.6 / 6071.3 / 6072.0 · 6772.9 | 911.5 / 6071.3 / 6071.9 · 6715.4 |

**TCP pathologies** (20 connections per arm, 900 s).
- *superseded*: frames delivered after a newer value was already issued.
- *expired*: frames delivered after their signed `expires_at`; a receiver must drop them.
- *censored*: (update, receiver) pairs never caught up by the end of the run.
- *longest*: the longest stretch with an unacknowledged retransmission (TCP_INFO, 20 ms sampling).

| U | loss dir | loss | arm | superseded | expired | censored | max backoff | longest | retrans (sum) | resets |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 s | both | 10% | tcp-stream | 202 | 0 | 0 | 3 | 2.9 s | 8412 | 0 |
| 0.5 s | both | 10% | tcp-latest | 149 | 0 | 0 | 4 | 6.4 s | 8404 | 0 |
| 0.5 s | both | 20% | tcp-stream | 3759 | 0 | 128 | 7 | 53.4 s | 17895 | 0 |
| 0.5 s | both | 20% | tcp-latest | 1325 | 1 | 0 | 10 | 333.9 s | 17531 | 0 |
| 0.5 s | both | 30% | tcp-stream | 6583 | 2690 | 24217 | 10 | 437.5 s | 5866 | 0 |
| 0.5 s | both | 30% | tcp-latest | 1679 | 31 | 1924 | 12 | 576.0 s | 9622 | 0 |
| 0.5 s | data-only | 10% | tcp-stream | 83 | 0 | 0 | 3 | 2.9 s | 4045 | 0 |
| 0.5 s | data-only | 10% | tcp-latest | 66 | 0 | 0 | 4 | 6.3 s | 3969 | 0 |
| 0.5 s | data-only | 20% | tcp-stream | 769 | 0 | 0 | 6 | 26.4 s | 8974 | 0 |
| 0.5 s | data-only | 20% | tcp-latest | 617 | 0 | 0 | 4 | 6.4 s | 9042 | 0 |
| 0.5 s | data-only | 30% | tcp-stream | 2926 | 0 | 0 | 6 | 26.4 s | 14687 | 0 |
| 0.5 s | data-only | 30% | tcp-latest | 1925 | 0 | 0 | 6 | 26.4 s | 14775 | 0 |
| 2 s | both | 10% | tcp-stream | 0 | 0 | 0 | 3 | 2.9 s | 2142 | 0 |
| 2 s | both | 10% | tcp-latest | 0 | 0 | 0 | 3 | 2.9 s | 2099 | 0 |
| 2 s | both | 20% | tcp-stream | 114 | 0 | 0 | 8 | 106.5 s | 5055 | 0 |
| 2 s | both | 20% | tcp-latest | 28 | 0 | 210 | 7 | 53.8 s | 4880 | 0 |
| 2 s | both | 30% | tcp-stream | 1277 | 381 | 241 | 13 | 696.9 s | 7498 | 0 |
| 2 s | both | 30% | tcp-latest | 200 | 6 | 459 | 10 | 386.6 s | 7442 | 0 |
| 2 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 2 | 1.3 s | 972 | 0 |
| 2 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 1 | 0.5 s | 941 | 0 |
| 2 s | data-only | 20% | tcp-stream | 2 | 0 | 0 | 3 | 2.9 s | 2270 | 0 |
| 2 s | data-only | 20% | tcp-latest | 6 | 0 | 0 | 4 | 6.3 s | 2203 | 0 |
| 2 s | data-only | 30% | tcp-stream | 63 | 0 | 0 | 5 | 12.9 s | 3855 | 0 |
| 2 s | data-only | 30% | tcp-latest | 40 | 0 | 0 | 6 | 26.2 s | 3839 | 0 |
| 10 s | both | 10% | tcp-stream | 0 | 0 | 0 | 3 | 2.9 s | 421 | 0 |
| 10 s | both | 10% | tcp-latest | 0 | 0 | 0 | 4 | 6.4 s | 462 | 0 |
| 10 s | both | 20% | tcp-stream | 0 | 0 | 0 | 5 | 12.9 s | 981 | 0 |
| 10 s | both | 20% | tcp-latest | 0 | 0 | 0 | 4 | 6.4 s | 1013 | 0 |
| 10 s | both | 30% | tcp-stream | 63 | 6 | 0 | 9 | 214.1 s | 1879 | 0 |
| 10 s | both | 30% | tcp-latest | 5 | 1 | 0 | 9 | 213.9 s | 1724 | 0 |
| 10 s | data-only | 10% | tcp-stream | 0 | 0 | 0 | 1 | 0.4 s | 198 | 0 |
| 10 s | data-only | 10% | tcp-latest | 0 | 0 | 0 | 2 | 1.3 s | 202 | 0 |
| 10 s | data-only | 20% | tcp-stream | 0 | 0 | 0 | 2 | 1.3 s | 441 | 0 |
| 10 s | data-only | 20% | tcp-latest | 0 | 0 | 0 | 3 | 2.9 s | 475 | 0 |
| 10 s | data-only | 30% | tcp-stream | 1 | 0 | 0 | 5 | 12.9 s | 727 | 0 |
| 10 s | data-only | 30% | tcp-latest | 1 | 0 | 0 | 5 | 13.1 s | 754 | 0 |

**Reading.**

1. **Where TCP is better.** Up to 10% loss, and at 20% when updates are sparse (U = 10 s), TCP beats the carousel on median, p95, p99 and stale time.
   - One lost segment costs one RTO: 204-212 ms here. This kernel arms RTO = SRTT + max(200 ms, 4·RTTVAR) at HZ 250, and with one packet in flight a tail-loss probe waits just as long.
   - The carousel's first repair is the burst copy 1 s later, or the next update when that comes first (U = 0.5 s). So its p99 sits near 500 or 1 000 ms wherever TCP's is near 210 ms.
   - This per-item repair-latency advantage of one reliable connection is real.
2. **Where TCP breaks.**
   - With 20-30% loss in both directions, a retransmission and its ACK both have to survive, so each attempt fails about half the time.
   - Linux doubles the RTO on each failure, up to 120 s. Timestamp echo during loss also inflates SRTT: TCP_INFO showed a 120 s RTO at backoff 3.
   - Every update queues behind the head of line. The result:
     - multi-minute stalls; the longest episode was 696.9 s;
     - 2 690 frames delivered after their signed `expires_at` (U = 0.5 s, 30%);
     - 58% of `tcp-stream` deliveries were already superseded on arrival.
   - No connection reset: `tcp_retries2` = 15 allows about 924 s, and some ACK always got through first.
   - The carousel's worst case is set by its schedule, not its history: 4.0 s (U = 0.5 s) and 12.0 s (U = 10 s, 5 s loop) even at 30%.
3. **ACK loss is most of the damage.** With data-only loss, TCP at 30% keeps a p99 of 0.85-5.2 s instead of minutes. Radio links usually lose in both directions; wired internet paths often do not.
4. **Latest-only does not fix head-of-line blocking.**
   - `tcp-latest` removes most backlog replay: after 10 s outages at U = 0.5 s it delivered 1 240 superseded frames against 15 420.
   - It does not shorten the stall, because the in-flight segment must still be retransmitted first.
   - At high loss its tails were sometimes worse (U = 0.5 s, 20%: p99 155 s against 19 s). A thinner stream has fewer segments in flight, so fast recovery triggers less and more losses need an RTO.
   - Tails at ≥ 20% come from a few backoff episodes per run and vary between runs. Read them as orders of magnitude.
5. **The class floor is a real but narrow knob.**
   - The 0 / +1 / +2 / +4 s burst does almost all repair for new updates, so the 1 s and 5 s loops look alike under Bernoulli loss.
   - The floor matters once the burst has failed:
     - 10 s outage at U = 10 s: p95 recovery 1.73 s against 3.47 s;
     - U = 10 s, 30% loss: max 6.3 s against 12.0 s;
     - late joiners (E4).
   - It costs bandwidth: at U = 10 s the carousel sent 4.84 (5 s loop) or 9.6 (1 s loop) copies per update per listener. That is 306-460 B/s per listener including the 1 Hz beacon, against 33 B/s of TCP payload.

## E2: fan-out cost to N listeners

**Setup.**
- A Go sender (standard library; `sendmmsg` through `syscall.Syscall6`) pushes one 700 B frame at 10 frames/s.
- The sender runs in namespace `pd-e2-tx`, pinned to CPU 0. The N listeners are one Go process in `pd-e2-rx`, pinned to CPUs 2-3.
- A veth pair joins the namespaces, and its counters are the wire.
- RPS steers listener-side receive work to CPUs 2-3 and returning ACKs to CPU 0. CPU 0's busy time is therefore the sending host's whole cost: the process plus the ACK softirq.
- Multicast: N sockets in the receiver process, each joined to 239.255.13.13 on the veth.
- Each row is the mean of 3 runs of 20 s after a 5 s warm-up.
- Every listener received all 280 frames in every run.
- Nothing was dropped in the RPS backlog. `netdev_max_backlog` was raised to 16 384 for the run and restored afterwards.

Idle baseline, CPU 0: 0.85% busy. Mean of 3 runs (min–max); 20 s windows after 5 s warm-up. *µs per listener·frame* = (CPU 0 busy − idle) / (N × 10).

| mode | N | sender host CPU % (CPU 0) | sender process CPU % | µs per listener·frame | wire out kB/s | wire in kB/s | pkts/s out / in | sender RSS kB | sender fds | syscalls/frame | fan-out spread p50 ms | min frames/listener | backlog drops |
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
  - Spread: the 5 000th TCP listener gets a frame 56.7 ms after the first (median), against 18.4 ms with `sendmmsg` and 0.04 ms with multicast.
- **Portability.** Absolute µs are for this VM (virtualised, 4 vCPUs); the ratios carry over.

## E3: slow and dead consumers

**Slow consumer** (listener 0 stops reading at t = 10 s; 100 listeners, 10 × 700 B frames/s, 600 s runs). *victim unread* = FIONREAD on the victim's TCP socket at the end.

| variant | victim SO_RCVBUF | sender stalled at (s) | healthy latency p99 / max ms | healthy: last frame at (s, median) | healthy frames min / expected | victim app queue peak B | frames dropped for victim | victim disconnected at (s) | sender RSS kB | victim unread B at end | UDP RcvbufErrors |
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

20 live items, 327 B frames; effective loops {'slow': [13080], 'fast': [1000]} ms; 10 joiners per arm back to back for 600 s; timeout 120 s. Time to hold all 20, ms (s where marked).

| loss | arm | joins | timeouts | p50 | p90 | p99 | max |  |
|---|---|---|---|---|---|---|---|---|
| 0% | carousel-4kbps | 345 | 0 | 14.4 s | 16.2 s | 16.9 s | 17.3 s |  |
| 0% | carousel-1s | 1543 | 0 | 1122.3 | 1254.7 | 1311.4 | 1330.0 |  |
| 0% | tcp-snapshot | 2130 | 0 | 0.4 | 0.8 | 2.5 | 10.8 | connect p50/p99 0.5/2.6 |
| 0% | lease-snapshot | 1375 | 0 | 1569.1 | 1574.4 | 1583.0 | 1636.4 | handshake p50/p99 0.3/4.4 |
| 5% | carousel-4kbps | 265 | 0 | 17.4 s | 27.5 s | 35.3 s | 41.6 s |  |
| 5% | carousel-1s | 1399 | 0 | 1311.5 | 2130.8 | 3049.2 | 4287.3 |  |
| 5% | tcp-snapshot | 2006 | 0 | 0.5 | 1019.0 | 2034.8 | 8403.7 | connect p50/p99 0.5/1034.0 |
| 5% | lease-snapshot | 591 | 0 | 5547.9 | 14.7 s | 25.9 s | 31.6 s | handshake p50/p99 0.3/3002.5 |
| 30% | carousel-4kbps | 137 | 0 | 37.9 s | 55.4 s | 79.5 s | 88.8 s |  |
| 30% | carousel-1s | 1011 | 0 | 3026.6 | 4457.0 | 6024.5 | 7656.9 |  |
| 30% | tcp-snapshot | 292 | 19 | 2053.4 | 23.9 s | 95.9 s | 105.1 s | connect p50/p99 1007.0/4382.4 |
| 30% | lease-snapshot | 160 | 1 | 32.3 s | 50.1 s | 62.4 s | 67.3 s | handshake p50/p99 1001.4/47.4 s |

**Reading.**
- **No loss: TCP connect-plus-snapshot wins by three orders of magnitude.** 0.4 ms p50, against 1.12 s for a 1 s carousel and 1.57 s for a lease snapshot.
- **The default budget makes the carousel slow to catch up.**
  - `B_stream` = 4 kbit/s shared by 20 items of 327 B gives a fair-share loop of 13.08 s, not the 5 s class floor.
  - Passive catch-up is then 14.4 s at p50 with no loss, and 37.9 s at 30%.
  - Loop and budget, not the protocol, decide catch-up time.
- **The lease snapshot is paced, and that makes it slow.**
  - At `granted_bps` = 32 kbit/s (§7.10), 20 × 327 B take 1.57 s.
  - A lost snapshot frame waits for the relay-forwarded 13 s loop, so p50 rises to 5.5 s at 5% loss and 32.3 s at 30%.
  - Repeat the snapshot, pace it faster, or loop toward new leases at a shorter period.
- **Under loss, TCP's handshake is the weak point.**
  - A lost SYN or SYN-ACK costs the 1 s initial RTO, then 3 s, 7 s: p90 1.02 s at 5%.
  - At 30%: p50 2.05 s, p90 23.9 s, p99 95.9 s, and 19 of 292 joins unfinished at 120 s.
  - The 1 s carousel at 30%: 3.03 s p50, 6.02 s p99, 7.66 s max, and no failures.

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
| **Binary plane, station/relay → listeners** | **UDP carousel** (unicast leases, LAN multicast); QUIC DATAGRAM / WebTransport for browsers and NAT-hostile paths | Bounded staleness under 20-30% loss (E1 max 4-12 s against TCP minutes) and outages. A slow or dead listener costs the sender nothing (E3). UDP unicast is 4.2-4.4 µs per listener·frame against TCP's 11.6-12.0 µs, with half the packets and no per-listener socket; multicast is flat on a LAN (E2). Keep the burst. Offer the 1 s floor where post-outage freshness matters, and budget it (9.6 copies/update at U = 10 s). |
| Binary plane, **relay ↔ relay backbone** | **TCP/QUIC stream** (D10: NATS), latest-only per key, bounded drop-oldest queues, TCP_USER_TIMEOUT | Backbone links are few and usually healthy. At ≤ 10% loss TCP repairs in one RTO (E1: 212 ms against 1 s) and carries each item once instead of looping it. Guard against E1's backoff tails and E3's silent peers. |
| Late-joiner catch-up | Relay snapshot over **TCP or QUIC** when the path is good; carousel when it is not | E4: TCP snapshot 0.4 ms against 1.1-14 s passive, but p99 96 s at 30% loss. The lease snapshot as specified (paced, once) is slower than both at 5%: repeat it or pace it faster. |
| Ledger plane (durable truth, promotion, ringserver replay/dashboards) | **TCP** (DataLink/SeedLink, §18) | Reliability and order are the requirement there, not freshness. |
| Control plane (addressed work, acks) | **TCP/QUIC** (the harness's own queues) | Needs reliability and flow control. E3 shows the price: per-peer queues and a user timeout. |
| Membership (beacons, presence) | **UDP**, as specified | Periodic and loss-tolerant. E5: relay-restart detection took 13.2 s (3 × 5 s beacons). Persist the cookie secret and leases across restarts, or shorten `relay_beacon_ms` toward leases, if that matters. |

## Surprises

- **Linux 6.18 grows the receive buffer of a socket that has stopped reading.** It reached 4.1 MB over 590 s at 7 KB/s, and backpressure never came. Kernel buffering hides a slow consumer from its sender and turns it into a stale consumer.
- **TCP delivered 2 690 frames after their own signed expiry** (U = 0.5 s, 30%). A byte stream does not know about TTLs, so the receiver's `expires_at` check is load-bearing over TCP too (RFC-0001 I-3, §20.3).
- **SRTT inflation.** At 20-30% loss the RTO reached 120 s at backoff 3, not only by doubling.
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
- E2's CPU numbers are for this VM, though the ratios carry over.
- E5 uses Python relays and clients.
