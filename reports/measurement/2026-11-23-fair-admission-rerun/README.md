# The #171 flood rows, rerun on the daemon with fair admission

**Status:** measurement for the cure in this pull request
([#171](https://github.com/karmaterminal/binary-canticle/issues/171), design #168 §2.4 step 2). Host **ronan, aarch64**
(10 × Cortex-X925, 10 × Cortex-A725, kernel `7.0.0-1019-nvidia`, Python 3.12.3). Every process ran at
`nice -n 19 ionice -c3`, on loopback, from a scratch directory with throwaway keys. Nothing live was touched. The numbers
don't carry to another host.

| ref | value |
|---|---|
| base | `origin/main` `08c11127d4e11ed00f307a7006d85581c8674a28` |
| measured, pass 1 | `0d8fafe42a83959aeadcfd84103f006e57e81953` (`prototype/canticle-station`, `git archive`d): the rows under "Rows" |
| measured, pass 2 | `e2d331d0f2d070edc38d8932389f5c1b259a7255` (`git archive`d): the rows under "Rows, pass 2". The scaled rows ran on `a3460fe8d9f8c383f80433697ca1ff3bfd4b3ad5`, whose daemon differs from it in comments only. Pass 2 changed the daemon's accounting and one bound, not its schedule ("Source churn" below) |
| harness | #171's, unchanged, [`../2026-11-23-step-one/harness/`](../2026-11-23-step-one/harness/) at `7d46e4f28420a2f20de52b442bf4731747d101b3`, with frond-ear `7c9bbd3179c50e6ad6870dcb0c74f68d47b4229d` |
| added here | [`rerun.py`](rerun.py), which drives that harness's `run_cell` (at run time it adds a second `--to` to the quiet station, so R4's senders can capture its frames), and [`flood_rows.py`](flood_rows.py), the producers it has no mode for; pass 2: [`scaled_rows.py`](scaled_rows.py) (repeated rows on `test_fair_admission`'s classes) and [`scheduler_work.py`](scheduler_work.py) |

**Verdict: R1-R5 pass, and so do #171's own flood rows. Four rows of this report FAIL.**

| row | verdict |
|---|---|
| R1 valid other-key, R2 same station, R4 replays, R5 loss visibility | PASS |
| R3: distinct forgeries of the quiet key **from other sources** | PASS |
| R3 with the sources churned (a newly opened socket per datagram), an established station | PASS |
| cold start inside a forged flood from 12 or 40 ports of the station's own host | PASS |
| **R3 from the station's exact source (address and port spoofed), above about 1 000/s** | **FAIL — outside the supported guarantee** |
| **a relay heard before the station, then R3 from churned sources** | **FAIL — outside the supported guarantee** |
| **cold start inside a forged flood from 200 ports of the station's own host** | **FAIL** (pass 1 had a run 16 s late; pass 2's five were within 2.1 s, which doesn't cure it) |
| **cold start inside a forged flood from churned sources** | **FAIL** (the rows' 4.5 s bound; worse than base at that rate) |

Scheduling by source narrows the threat model. It does not establish the original R3 guarantee (any forgery claiming the
quiet key), and no FAIL above is a pass with a footnote. In each passing flood the quiet tuned stream (in the full-length
rows a real `canticle station`, one item every 10 s) arrived whole while the flood ran, and was pushed whole. What was not
heard is counted, by reason, and the kernel's own drops at the socket equal the daemon's report of them in every row.

**Where the reader was outrun, it shows.** At 933 000 distinct forgeries a second (R3) the kernel dropped 23 % of what
arrived, whoever sent it. The quiet station's copies were among the dropped, and its burst (+1, +2 and +4 s) brought each
item again: p50 33 ms, p90 1.0 s, p99 4.0 s. A faster flood would lose items that only the later loops bring back. Beacons
are sent once, so 470 of about 590 were heard in that row, and the longest gap was 4.5 s: presence can flicker. In R4a the
kernel dropped 0.004 %, in the other rows nothing, and their latency is that of a quiet host (F0), or of a host that is
also saving 48 flood items a second (R1).

## What a source is

**A source is the IPv4 address and the UDP port the kernel reports as a datagram's sender, per listed key.** Not the host,
the interface or a MAC. In code
([`intake.py` at `e2d331d0`](https://github.com/karmaterminal/binary-canticle/blob/e2d331d0f2d070edc38d8932389f5c1b259a7255/prototype/canticle-station/canticle/intake.py)):
`_Mmsg` reads the first 8 bytes of `sockaddr_in` (family, port, address) as one integer (L442; the `recvmsg` fallback gives
`(host, port)`), `KeyQueue.source` (L271) looks it up, and `Source` (L138) is its queue's owner and its budget. The address
alone (`host_of`, L147) matters in one place: at most 16 ports of a host queue apart among the strangers (`_room`, L284).
The daemon listens on IPv4 only (`daemon.py`, `_bind_udp`).

So **ports form buckets**, and a sender has as many as it likes: hence "Source churn" below. Two ports of one host are two
sources, a station that restarts on a new port is a new one, and one that binds its port keeps its share. A source is never
trusted: it picks a queue and a budget, and admits or refuses nothing (I-11).

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

### Rows, pass 2

The R rows again, on pass 2's daemon (`e2d331d0`), 570 s each, and one more: **R3c**, R3 from churned sources. Two producers,
each opening a new socket for every datagram (which is what limits them to 197 000/s together), one on the station's own host and
one on 60 000 loopback addresses. Raw rows: `results-pass2/`.

| row | offered /s | quiet at daemon during the flood | pushed | send → record ms, p50 / p90 / p99 / max | send → push s, p50 / p90 / p99 / max | socket drops: kernel (reported by the daemon) | refused by the daemon, by reason | repeats, copies (not verified) | verified / checks that failed | health reasons seen | daemon CPU mean, RSS max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1-valid-other-key-4x-max (570 s) | 151,078 | 57/57 | 57/57 | 65 / 112 / 138 / 139 | 5.7 / 6.0 / 6.1 / 6.1 | 0 (0) | over_rate 86,075,285, backlog 11,525 | 453, 0 | 28,444 / 0 | datagrams_refused | 91 %, 48 MiB |
| R2-same-station (570 s) | 6,252 | 57/57 | 57/57 | 14 / 15 / 19 / 20 | 5.6 / 5.9 / 6.0 / 6.0 | 0 (0) | over_rate 3,557,404, backlog 129 | 453, 36 | 7,642 / 0 | datagrams_refused | 24 %, 36 MiB |
| R3-forged-claiming-quiet-2x-max (570 s) | 692,182 | 57/57 | 57/57 | 22 / 27 / 31 / 35 | 5.6 / 6.0 / 6.0 / 6.0 | 254,590 (254,590) | unverified 393,584,237, backlog 65,614 | 461, 0 | 641 / 570,259 | datagrams_refused, socket_drops | 107 %, 34 MiB |
| R3c-forged-churned-sources-2x-max (570 s) | 197,027 | 57/57 | 57/57 | 20 / 26 / 30 / 31 | 5.5 / 6.0 / 6.0 / 6.0 | 0 (0) | unverified 111,698,697, backlog 16,763 | 458, 0 | 645 / 570,240 | datagrams_refused | 85 %, 34 MiB |
| R4a-replay-earlier-frames-2x-max (570 s) | 925,584 | 57/57 | 57/57 | 27 / 34 / 39 / 41 | 5.5 / 6.0 / 6.0 / 6.0 | 6,249,186 (6,249,186) | unverified 94,347,505, over_rate 13,983,118, backlog 371,718 | 189,404,651, 222,629,881 | 436,848 / 68,904 | datagrams_refused, socket_drops | 104 %, 34 MiB |
| R4b-replay-latest-item-2x-max (570 s) | 724,637 | 57/57 | 57/57 | 18 / 19 / 23 / 26 | 5.6 / 6.0 / 6.0 / 6.0 | 33,570 (33,570) | none | 412,226,155, 711,626 | 641 / 103 | socket_drops | 95 %, 33 MiB |

Every quiet item arrived and was pushed in every row, and the reported socket drops equal the kernel's. `displaced` is 0 in
all of them, and `known` is 1 for the quiet station's key and each flooding key's own. R3 here was the easier flood: the
producers reached 692 000/s, not pass 1's 933 000/s, so the reader lost 0.06 % and not 23 %. Pass 1's row is the harder one
and stays the claim. The F rows were not rerun; they are pass 1's.

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
- **An exact-source spoof: `FAIL — outside the supported guarantee`.** Forgeries from the quiet station's very socket, so its
  address and port. At 500/s it costs nothing (20/20). At 100 000/s that station got 1-3 of 20 in five runs here and 0-2 of
  20 in three more (and 4 of 20 on the CI runner), and another station 20/20. Nothing before the signature can tell the two
  apart, and scheduling by source does not give that station R3's guarantee. Above about 1 000 spoofed forgeries a second
  the spoofed station does **worse** than on base (12-13 of 20 in three runs), which spent a whole core (about 15 000 checks
  a second, #171) on the same lottery and everyone else's frames in it (the other station: 11-19 of 20).
- **A station starting inside a forged flood** (cold start) and **churned sources**: "Scaled rows" and "Source churn" below.
- **CI** (ubuntu-24.04, x86_64, Python 3.11, run 45240852511): the scaled rows 57/57, p99 at most 330 ms.

## Scaled rows

`test_fair_admission`'s classes, repeated by `scaled_rows.py`: 8 s of flood for the spoof, 13.6 s for the churned R3, 20 s for
the relays, 30 s for the cold starts. Station items are 150 ms apart, and forgeries name the quiet station's key and stream
(in the cold starts every other one is a beacon). "Sources" are the distinct ones that the flood sent from; churned means a
newly opened socket per datagram, which the kernel gives one of some 28 000 ports, also from 60 000 addresses where the row
says so. A row passes when every run had every item during the flood, p50 at most 250 ms and none later than 4.5 s, and the
kernel's drops were reported. Refusals by the daemon are by reason and are separate from the kernel's drops; both are in the
raw runs: [`results-scaled/a3460fe8.json`](results-scaled/a3460fe8.json).

| row | runs | offered /s | sources | that station, items during the flood, per run | latency ms over the runs: p50, p99, max | its first valid frame, ms | another station | socket drops: kernel (reported) | refused, by reason (median) | checks that failed (median) | sources that gained a share, lost it | health reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| spoof-exact-source-100000 | 5 | 100,010–100,011 | 1 | 2, 3, 2, 1, 3 of 20 | 79–2,074, 83–4,093, 83–4,093 | – | 20, 20, 20, 20, 20 of 20 | 0 (0) | unverified 789,507, backlog 2,505 | 8,148 | 2, 0 | datagrams_refused | **FAIL — outside the supported guarantee** |
| spoof-exact-source-500 | 5 | 500 | 1 | 20, 20, 20, 20, 20 of 20 | 24–27, 28–60, 28–60 | – | 20, 20, 20, 20, 20 of 20 | 0 (0) | none | 4,001 | 2, 0 | none | PASS |
| churn-established-100000 | 5 | 100,005–100,007 | 708,146–708,159 | 57, 57, 57, 57, 57 of 57 | 28–32, 34–40, 34–40 | – | 57, 57, 57, 57, 57 of 57 | 0 (0) | unverified 1,346,004, backlog 80 | 14,016 | 2, 0 | datagrams_refused | PASS |
| relay-first-then-churn-100000 | 5 | 100,004–100,005 | 1,027,955–1,027,999 | 20, 2, 19, 15, 20 of 20 | 1,011–16,316, 2,028–16,766, 2,028–16,766 | – | 20, 20, 20, 20, 20 of 20 | 0 (0) | unverified 1,978,822, backlog 883 | 20,426 | 94–96, 89–91 | datagrams_refused | **FAIL — outside the supported guarantee** |
| relay-after-then-churn-100000 | 5 | 100,004–100,005 | 1,027,949–1,027,993 | 20, 20, 20, 20, 20 of 20 | 22–31, 33–38, 33–38 | – | 20, 20, 20, 20, 20 of 20 | 0 (0) | unverified 1,979,633, backlog 31 | 20,414 | 2–5, 0 | datagrams_refused | PASS |
| cold-start-12-ports-20000 | 5 | 20,000–20,001 | 12 | 20, 20, 20, 20, 20 of 20 | 19–20, 26–43, 26–43 | 29–54 | – | 0 (0) | unverified 569,414, backlog 6 | 30,499 | 1, 0 | datagrams_refused | PASS |
| cold-start-40-ports-20000 | 5 | 20,000–20,001 | 40 | 20, 20, 20, 20, 20 of 20 | 19–21, 71–95, 71–95 | 73–104 | – | 0 (0) | unverified 569,411, backlog 6 | 30,505 | 1, 0 | datagrams_refused | PASS |
| cold-start-200-ports-20000 | 5 | 20,000–20,001 | 200 | 20, 20, 20, 20, 20 of 20 | 18–21, 164–2,015, 164–2,015 | 159–1,065 | – | 0 (0) | unverified 569,414, backlog 5 | 30,499 | 1, 0 | datagrams_refused | **FAIL** (first frame up to 1,065 ms, items up to 2,015 ms: misses the ≤1 s / ≤2 s deadline declared for pass 3; within the rows' 4.5 s bound) |
| cold-start-churn-own-host-20000 | 5 | 20,000–20,001 | 28,227–28,228 | 20, 20, 20, 20, 20 of 20 | 19–16,287, 170–25,159, 170–25,159 | 162–13,768 | – | 0 (0) | unverified 569,449, backlog 0 | 30,454 | 1, 0 | datagrams_refused | **FAIL** |
| cold-start-churn-60000-hosts-20000 | 5 | 20,000–20,001 | 599,922–599,933 | 20, 20, 20, 20, 20 of 20 | 20–10,784, 1,024–17,330, 1,024–17,330 | 600–5,454 | – | 0 (0) | unverified 569,456, backlog 0 | 30,594 | 1, 0 | datagrams_refused | **FAIL** |

The same on base `08c11127` (three runs, [`results-scaled/base-08c11127.json`](results-scaled/base-08c11127.json)). Base reports no
drop and no refusal at all:

| row | runs | offered /s | sources | that station, items during the flood, per run | latency ms over the runs: p50, p99, max | its first valid frame, ms | another station | socket drops: kernel (reported) | refused, by reason (median) | checks that failed (median) | sources that gained a share, lost it | health reasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| spoof-exact-source-100000 | 3 | 100,009–100,011 | 1 | 12, 13, 13 of 20 | 1,026–2,025, 4,030–4,038, 4,030–4,038 | – | 13, 19, 11 of 20 | 666,554–668,063 (–) | – | 132,943 | – | none | **FAIL — outside the supported guarantee** |
| spoof-exact-source-500 | 3 | 500 | 1 | 20, 20, 20 of 20 | 17–20, 24–28, 24–28 | – | 20, 20, 20 of 20 | 0 (–) | – | 4,001 | – | none | PASS |
| churn-established-100000 | 3 | 100,006–100,007 | 708,139–708,167 | 27, 33, 28 of 57 | 1,020–1,033, 4,026–4,045, 4,026–4,045 | – | 25, 32, 23 of 57 | 1,135,343–1,145,924 (–) | – | 224,507 | – | none | **FAIL** |
| relay-first-then-churn-100000 | 3 | 100,004 | 1,027,970–1,027,989 | 13, 11, 14 of 20 | 1,030–2,034, 14,611–16,458, 14,611–16,458 | – | 17, 11, 16 of 20 | 1,657,637–1,661,084 (–) | – | 340,808 | – | none | **FAIL — outside the supported guarantee** |
| relay-after-then-churn-100000 | 3 | 100,004–100,005 | 1,027,939–1,027,993 | 15, 12, 15 of 20 | 2,017–4,033, 4,032–16,930, 4,032–16,930 | – | 10, 9, 12 of 20 | 1,658,008–1,660,438 (–) | – | 342,063 | – | none | **FAIL** |
| cold-start-12-ports-20000 | 3 | 20,001 | 12 | 20, 20, 20 of 20 | 27–28, 1,021–1,037, 1,021–1,037 | 26–44 | – | 70,943–71,927 (–) | – | 528,319 | – | none | **FAIL** (the items pass; the drops are not reported) |
| cold-start-40-ports-20000 | 3 | 20,000–20,001 | 40 | 20, 20, 20 of 20 | 26–27, 41–1,030, 41–1,030 | 30–38 | – | 69,264–71,152 (–) | – | 530,549 | – | none | **FAIL** (the items pass; the drops are not reported) |
| cold-start-200-ports-20000 | 3 | 20,000–20,001 | 200 | 20, 20, 20 of 20 | 27–27, 1,028–2,018, 1,028–2,018 | 26–27 | – | 68,662–70,569 (–) | – | 529,823 | – | none | **FAIL** (the items pass; the drops are not reported) |
| cold-start-churn-own-host-20000 | 3 | 20,001 | 28,227–28,228 | 20, 20, 20 of 20 | 26–26, 1,028–1,037, 1,028–1,037 | 18–27 | – | 68,336–70,846 (–) | – | 530,541 | – | none | **FAIL** (the items pass; the drops are not reported) |
| cold-start-churn-60000-hosts-20000 | 3 | 20,000–20,001 | 599,910–599,913 | 20, 20, 20 of 20 | 20–21, 1,024–2,026, 1,024–2,026 | 21 | – | 66,557–69,863 (–) | – | 531,256 | – | none | **FAIL** (the items pass; the drops are not reported) |

What they say:

- **Exact-source spoof**: above, "What was tried to break it".
- **Cold start.** The station's FIRST valid frame arrives during the forged flood, before its source has earned a share of its
  own, so it competes with the forger's ports as a stranger. From 12 and 40 ports of its own host, its first valid frame was
  admitted 29-104 ms after it went out and all 20 items arrived within 0.1 s. From 200 ports it took up to 1.1 s in these
  five runs and the items up to 2.0 s: a FAIL of the ≤1 s / ≤2 s deadline declared for pass 3 (first frame 1,065 ms, items
  2,015 ms), though within the rows' 4.5 s bound; pass 1 also had a run 16 s late.
  Against **churned sources** it took 0.2-13.8 s, and the items up to 25 s: the crowd's lanes are full of the flood, and the
  station waits for chance. All 20 arrived, but this FAILS the 4.5 s bound and is worse than base (first valid frame within
  0.05 s, items within 2 s at this rate), because base spends a whole core on checks and this spends 1 000 a second on the
  strangers of one key. At 100 000/s, base loses established stations that this serves whole (R3, "Before").

## Source churn

`ChurnTest` in `tests/test_intake.py` drives the intake alone; `SourceChurnTest` in `tests/test_fair_admission.py` a real
daemon over loopback UDP. Two of them were **RED at `c6e669c2`**, the reason for pass 2's code:

| what is held | RED at `c6e669c2` | now |
|---|---|---|
| an established source that loses its share is counted | `receive` had no such count: 4 fresh frames heard first from 4 new ports displace it, and nothing says so | `receive.displaced`, and `known`, the sources that gained a share |
| what waits stays within its bound when known sources are displaced | 1 040 datagrams in the strangers' pool of 256 | at most 256; what does not fit is refused as `backlog` |

Each half of pass 2's code, undone alone, fails its own test and the random-traffic test. Also held, and green on `c6e669c2`: an established source keeps every other turn and its whole budget through 1.36 M newly
opened sockets (R3's churn row), at 100 000/s and flat out; the worst dilution of an established source is bounded (each
other known place taken by a forging relay, and a full table of strangers: its frame is served within 2 × KNOWN_MAX = 8
turns of its stream); and a stranger that becomes known keeps what it had waiting.

**Does churn evict or dilute an established share?**

- *Unauthenticated churn cannot touch it.* Only a source a new frame of the key was **verified** from becomes known, and
  only a newly known one displaces an older. Forged ports never do (`displaced` is 0 in every forged row).
- *A relay heard first can.* It sends the station's own frames, captured, from a new port each, sooner than the station's
  copies arrive. Each wins a place among the key's 4 (`KNOWN_MAX`) known sources, and four displace the station's. It is
  counted: `receive.displaced` was 89-91 in each of the five runs. The relay needs a path faster than the station's
  (10 ms here; 2 ms was enough in a first probe), or the station's copy to be one the kernel dropped (flat out, 23 % are: R3). A relay heard *after* the
  station displaces nothing (`displaced` 0, 5 of 5 runs, 20/20).
- *What a relayed station loses when it is displaced.* It is a stranger again in a flood it cannot beat: 2-20 of 20 here, p50 1 to
  16 s. Refused datagrams are counted by reason, `datagrams_refused` degrades `health`, and `displaced` counts that
  its share went. **FAIL — outside the supported guarantee.** Who loses a known place (now: the source whose last new frame is the oldest) is a
  fairness-design choice left to review; nothing in pass 2 changes it.

**Bounds**, per listed key (line numbers of `intake.py` at `e2d331d0`; a sender cannot add keys or streams):

| what | bound | where |
|---|---|---|
| source table | 4 known + 64 strangers (16 per host) + 64 crowd lanes shared by a salted hash | `KNOWN_MAX`, `STRANGERS_MAX`, `STRANGERS_PER_HOST`, `CROWD_LANES` (L91-95); `KeyQueue.source`, `_room`, `know` (L271, 284, 301) |
| queued datagrams per stream queue (each listed stream, `OTHER` and `BEACON`) | 256 for all strangers, and 4 known × 64, or what it had waiting when it became known, at most 256: **1 280** in all | `STRANGER_POOL` (L96), `KNOWN_DEPTH`, `StreamQueue.put`, `change` (L176, 229); `change` refuses what is past the pool |
| queued bytes | 1 280 × `MAX_FRAME` 1 100 B = **1.4 MB** of datagrams per stream queue; unlisted: 64 × 1 216 B; repeats: one digest per live dedup entry plus 64 beacons a key | `wire.MAX_FRAME`, `offer` (L559, refused before queueing if larger), `UNLISTED_DEPTH` (L90) |
| scheduler work | placing a datagram: a hash lookup and at most one pass over a stream's lanes (≤ 128 strangers); a pick: each lane of a stream once; a turn: at most 32 × `TURN` 4 = 128 places, and at most 2 000 checks/s that come to nothing | `offer`, `put` (L559, 176), `pick` (L209), `take` (L632), `TURN` (L97), `CHECK_RATE` (L88); `HEAR_BATCH` 32, `RETRY_S` 20 ms (`daemon.py` L72-73) |
| a known place taken from an older source | at the pace its key's frames verify: at most 16 new frames/s, and 8 beacons/s, per key (burst 64 and 16) | `KEY_RATE`, `BEACON_RATE` (L81, 83) |

Measured with every lane of every stream open, on ronan (`scheduler_work.py`), keys × streams, real intake calls:

| keys × streams | lanes open per stream | waiting | placing a datagram, mean, each from a source of its own | a turn's tickets, the strangers' budgets spent | a turn that finds nothing to serve (at most every 20 ms) |
|---|---|---|---|---|---|
| 1 × 1 | 128–128 | 256 (30 KiB) | 1.8 µs | 10 in 0.09 ms | 0.01 ms |
| 1 × 8 | 72–72 | 2,048 (236 KiB) | 1.3 µs | 10 in 0.36 ms | 0.03 ms |
| 2 × 2 | 96–96 | 1,024 (118 KiB) | 1.4 µs | 20 in 0.25 ms | 0.02 ms |
| 9 × 4 | 80–80 | 9,216 (1,062 KiB) | 1.3 µs | 32 in 0.50 ms | 0.16 ms |

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
cd reports/measurement/2026-11-23-fair-admission-rerun
MEASURE_FROND_EAR=<frond-ear at 7c9bbd31, with node_modules> nice -n 19 ionice -c3 \
  python rerun.py ../2026-11-23-step-one/harness results R1,R2,R3,R4a,R4b 570 15
python table.py results
```
