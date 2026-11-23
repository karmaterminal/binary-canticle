# The #171 flood rows, rerun on the daemon with fair admission

**Status:** measurement for the cure in this pull request
([#171](https://github.com/karmaterminal/binary-canticle/issues/171), design #168 §2.4 step 2). Host **ronan, aarch64**
(10 × Cortex-X925, 10 × Cortex-A725, kernel `7.0.0-1019-nvidia`, Python 3.12.3). Every process ran at
`nice -n 19 ionice -c3`, on loopback, from a scratch directory with throwaway keys. Nothing live was touched. The numbers
don't carry to another host.

| ref | value |
|---|---|
| base | `origin/main` `08c11127d4e11ed00f307a7006d85581c8674a28` |
| measured | `0d8fafe42a83959aeadcfd84103f006e57e81953` (`prototype/canticle-station`, `git archive`d) |
| harness | #171's, unchanged, at `7d46e4f28420a2f20de52b442bf4731747d101b3`, with frond-ear `7c9bbd3179c50e6ad6870dcb0c74f68d47b4229d` |
| added here | [`rerun.py`](rerun.py), which drives that harness's `run_cell` (at run time it adds a second `--to` to the quiet station, so R4's senders can capture its frames), and [`flood_rows.py`](flood_rows.py), the two producers it has no mode for |

**Verdict: every row passes.** In each flood the quiet tuned stream (a real `canticle station`, one item every 10 s)
arrived whole while the flood ran, and was pushed whole. What was not heard is counted, by reason, and the kernel's own
drops at the socket equal the daemon's report of them in every row.

**Where the reader was outrun, it shows.** At 933 000 distinct forgeries a second (R3) the kernel dropped 23 % of what
arrived, whoever sent it. The quiet station's copies were among the dropped, and its burst (+1, +2 and +4 s) brought each
item again: p50 33 ms, p90 1.0 s, p99 4.0 s. A faster flood would lose items that only the later loops bring back. Beacons
are sent once, so 470 of about 590 were heard in that row, and the longest gap was 4.5 s: presence can flicker. In R4a the
kernel dropped 0.004 %, in the other rows nothing, and their latency is that of a quiet host (F0), or of a host that is
also saving 48 flood items a second (R1).

## Rows

Each row is one of #171's cells with its flood, run for the time shown: 57 quiet items in 570 s, 30 in 300 s, all sung
while the flood ran. "Pushed" is by the end of the cell, 15 s after the flood. `send → push` includes frond-ear's 5 s debounce and 1 s
poll, so 5-6 s is its floor (#171, F0).

| row | offered /s | quiet at daemon during the flood | pushed | send → record ms, p50 / p90 / p99 / max | send → push s, p50 / p90 / p99 / max | socket drops: kernel (reported by the daemon) | refused by the daemon, by reason | repeats, copies (not verified) | verified / checks that failed | health reasons seen | daemon CPU mean, RSS max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F0-quiet-only (300 s) | – | 30/30 | 30/30 | 19 / 20 / 22 / 23 | 5.6 / 6.0 / 6.0 / 6.0 | 0 (0) | none | 235, 0 | 349 / 0 | none | 0 %, 33 MiB |
| F2b-forged-own-key-2x-max (300 s) | 721,584 | 30/30 | 30/30 | 20 / 21 / 36 / 40 | 5.8 / 6.0 / 6.0 / 6.0 | 0 (0) | none | 236, 215,875,055 | 346 / 600,192 | none | 117 %, 34 MiB |
| F3b-unknown-key-2x-max (300 s) | 974,936 | 30/30 | 30/30 | 18 / 20 / 25 / 27 | 5.7 / 6.0 / 6.0 / 6.0 | 0 (0) | unlisted 292,330,104 | 236, 0 | 346 / 150,560 | none | 94 %, 34 MiB |
| F4-replay-other-key-2x-max (300 s) | 688,098 | 30/30 | 30/30 | 28 / 29 / 30 / 30 | 5.5 / 5.9 / 6.0 / 6.0 | 0 (0) | none | 203,507,018, 2,922,105 | 948 / 0 | none | 94 %, 34 MiB |
| F5-real-station-flood (300 s) | 6,396 | 30/30 | 30/30 | 14 / 21 / 21 / 21 | 5.7 / 6.0 / 6.0 / 6.0 | 0 (0) | over_rate 1,915,468, backlog 174 | 233, 36 | 4,422 / 0 | datagrams_refused | 22 %, 36 MiB |
| R1-valid-other-key-4x-max (570 s) | 150,811 | 57/57 | 57/57 | 56 / 113 / 142 / 146 | 5.7 / 6.0 / 6.1 / 6.1 | 0 (0) | over_rate 85,923,647, backlog 10,589 | 449, 0 | 28,445 / 0 | datagrams_refused | 90 %, 48 MiB |
| R2-same-station (570 s) | 6,233 | 57/57 | 57/57 | 14 / 15 / 29 / 37 | 5.6 / 5.9 / 6.0 / 6.0 | 0 (0) | over_rate 3,546,178, backlog 141 | 454, 36 | 7,641 / 0 | datagrams_refused | 24 %, 36 MiB |
| R3-forged-claiming-quiet-2x-max (570 s) | 933,041 | 57/57 | 57/57 | 33 / 1036 / 4032 / 4034 | 5.9 / 6.8 / 9.3 / 9.4 | 124,500,608 (124,500,608) | unverified 406,490,262, backlog 179,201 | 335, 0 | 527 / 570,265 | datagrams_refused, socket_drops | 106 %, 34 MiB |
| R4a-replay-earlier-frames-2x-max (570 s) | 744,451 | 57/57 | 57/57 | 20 / 25 / 28 / 29 | 5.5 / 5.9 / 6.0 / 6.0 | 18,415 (18,415) | unverified 82,459,171, over_rate 8,212,627, backlog 327,026 | 149,325,655, 183,414,803 | 406,922 / 99,494 | datagrams_refused, socket_drops | 100 %, 34 MiB |
| R4b-replay-latest-item-2x-max (570 s) | 767,532 | 57/57 | 57/57 | 19 / 20 / 20 / 20 | 5.6 / 6.0 / 6.0 / 6.0 | 0 (0) | none | 436,648,559, 768,821 | 645 / 74 | none | 95 %, 34 MiB |

What the rows are:

- **R1** (#171's F1): four producers with four other licensed keys, each flat out with new valid items.
- **R2** (F6): the quiet stream inside a real station that is being flooded through its own control socket.
- **R3** (no cell in #171): two producers of **distinct** frames naming the quiet key and stream, each with its own invalid
  signature that reaches the signature check.
- **R4a** (no cell in #171): two senders without a key replaying everything the quiet station sent at least 8 s ago and
  is still valid, and its beacons of the last 5 minutes. **R4b** (#171's wording): its newest item, moving on as each is
  sung. A replay of the newest item *delivers* it, so on its own it can't starve the stream; R4a can.
- **F2b, F3b, F4, F5**: #171's cells of those names. **F0**: the quiet station alone.

`refused` is what the daemon decided not to look at: `over_rate` (the key or stream was over its rate), `unverified` (the
source's budget for checks that come to nothing was spent), `backlog` (a queue was full for another reason) and
`unlisted` (no listed key was named). `repeats` are exact copies of a frame verified before, `copies` those of a datagram
already waiting in the same queue; neither is verified again, and neither is a loss. All of it is separate from the kernel's
socket drops, which the harness read from `/proc/net/udp` and the daemon reports as `records.socket_dropped`. In R4a the
406 922 verified are old beacons, which verify whenever they are replayed and are charged to their sender: all 588 of the
station's own were heard.

frond-ear's live set never overflowed (`live_overflow` 0 in every row). R1's four flooding keys were held to 48 new items
a second between them.

## Before

The same two new rows on base, 120 s each, and #171's own numbers for the rest:

| row | offered /s | quiet at daemon during the flood | pushed | send → record ms, p50 / p90 / p99 / max | send → push s, p50 / p90 / p99 / max | socket drops: kernel (reported by the daemon) | refused by the daemon, by reason | repeats, copies (not verified) | verified / checks that failed | health reasons seen | daemon CPU mean, RSS max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R3-forged-claiming-quiet-2x-max (120 s) | 1,110,280 | 3/12 | 3/12 | 28114 / 42090 / 42542 / 42592 | 15.1 / 23.1 / 24.9 / 25.1 | 131,066,395 (–) | – | – | – | none | 88 %, 33 MiB |
| R4a-replay-earlier-frames-2x-max (120 s) | 1,148,572 | 11/12 | 12/12 | 8030 / 8039 / 11724 / 12180 | 13.5 / 14.0 / 16.9 / 17.3 | 136,018,263 (–) | – | – | – | clock_skew | 81 %, 33 MiB |

On base R4a's items arrived only because the replay itself carried them, 8 s after they were sung (its latency is the
replay's). #171's cells: F1
0 of 60 while the flood ran, with 92 020 097 socket drops; F6 2 of 30; F2b 5 of 30; F3b 23 of 30; F4 1 of 30; F5 1 of 30.
None of those losses was reported.

## What was tried to break it

- **Patch-reverts.** Each part of the cure, undone alone, fails its own test (ronan, the scaled-down rows of
  `test_fair_admission.py`): one arrival-order queue, R1 0/57; one queue per key, R2 1/57; one queue per stream, R3 5/57;
  debit on claim, R3's p50 14 → 486 ms; no repeat check, R4 verifies 5 292 copies instead of 80; no drop count, R5
  unreported. **Speed alone fails:** the fast reader and group commit, with one arrival-order queue and no caps, drops
  nothing at the socket, verifies 11 049 items and admits 2 of 57 quiet ones (0 of 57 in two other runs).
- **Two independent review rounds** of work in progress, whose attack scripts became tests. They found what R1-R5 do not
  see, all of it fixed here: old beacons replayed at 100/s drove the clock offset up until items read `not_yet_valid`;
  forgeries from 5 or 17 ports of a host locked out a station starting there; replays of refused frames spent the
  station's bucket.
- **This rerun itself** found one more, at `d022a55e` (results not kept): #171's forged flood resends one frame, its copies
  filled the queues, and F2b lost 1 of 30. They now take no place.
- **A perfect source spoof.** Forgeries from the quiet station's very socket. At 500/s: 20/20, p99 17 ms. At 100 000/s: that
  station 0-1 of 20 on ronan and 4 of 20 on the CI runner, another station 20/20. Base, in the same flood: 12 of 20 for the
  *other* station, p99 4 s. This is the limit the code states: nothing before the signature can tell the two apart. Above
  about 1 000 spoofed forgeries a second, the spoofed station itself does **worse** than on base, which spent a whole core
  (about 15 000 checks a second, #171) on the same lottery and everyone else's frames in it.
- **A station starting inside a forged flood from its own host**, 20 000/s: from 12 or 40 ports, all items, worst 0.1 s; from
  200 ports, all items, the first ones up to 16 s late. Base, from 40 ports: all items, worst 1.0 s.
- **CI** (ubuntu-24.04, x86_64, Python 3.11, run 45240852511): the scaled rows 57/57, p99 at most 330 ms.

## Not measured

- A LAN interface: loopback only. A host whose `net.core.rmem_max` is the 212 992 B default holds a smaller burst (the CI
  runner is one, and its rows passed).
- More than two flat-out senders of distinct forgeries. Two already outran the reader by 23 % (R3 above); placing
  a datagram costs it about 0.5 µs when it is a repeat and 0.9 µs when it is refused on an X925 core, twice that on an
  A725. A faster flood loses a larger share of every sender's copies, the quiet station's included, and the carousel's
  repeats are then what delivers it.
- frond-ear's own limits (#171, findings 3-5). No row reached its 4 096-record live set (`live_overflow` 0). Its hourly push
  budget is why the rows are 57 items long.

## Rerun

```sh
H=<a checkout of 7d46e4f2>/reports/measurement/2026-11-23-step-one/harness   # beside the prototype/ under test
MEASURE_FROND_EAR=<frond-ear at 7c9bbd31, with node_modules> nice -n 19 ionice -c3 python rerun.py $H results R1,R2,R3,R4a,R4b 570 15
python table.py results
```
