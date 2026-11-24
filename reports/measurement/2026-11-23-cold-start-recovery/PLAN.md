# Newcomer recovery under a sustained forged flood: the rows and the deadline, declared before any run

**Status:** predeclared. This file is committed and pushed before the first run, and is not edited after it. A change to
the method is a new dated section at the end, and says what had already been run.

[#173](https://github.com/karmaterminal/binary-canticle/pull/173) (cure for
[#171](https://github.com/karmaterminal/binary-canticle/issues/171)) is **held for recovery evidence**. Its pass 2 found that
a station that starts inside a forged flood from churned sources is heard later than on base. These rows decide whether that
delay is acceptable; the thresholds are 🌫's and 🍃's, confirmed before this pass began.

| ref | SHA |
|---|---|
| head: the #173 PR head, `codeagent/bc-daemon-fair-admission-2` | `ab61baf2fa1989fc3b3959db8bdcf00433508328` |
| base: `main` | `d4c306618f7f77658fe73705d58b2744f2486701` (`prototype/` is identical to `08c11127`, the base of pass 1 and pass 2) |
| this lane | `codeagent/bc-173-pass3`, published at `ab61baf2` before any run |

## Thresholds (the deciding rows)

- **Pass:** the newcomer's first valid frame is delivered to the local client **≤ 1.0 s** after the newcomer's first actual
  send, and **each item ≤ 2.0 s** after that item's first actual send.
- **Any miss fails its row.** An item later than its deadline is a miss even when it eventually arrives, a missing item is a
  miss, and one miss fails the row. A row is one cell: every run of one tree at one rate, port count and offset.
- **Severity label, not a gate:** later than **10 s** is "more than one loop late". Nothing is called superseded: an unchanged
  item may still be current, and a carousel repeat doesn't prove supersession.
- **The flood keeps running through every deadline.** Recovery after it stops does not pass, and is not counted.
- These are acceptance thresholds for this workload. Neither base nor the candidate guarantees them universally.

## How it is timed

- Every time is `CLOCK_MONOTONIC`, which all processes of a host share.
- *Actual send*: read immediately before the newcomer's `sendto` of a frame. An item's first actual send is that of its first
  copy, not when it was sung.
- *Delivered*: when the local client (a record v1 connection on the daemon's socket) reads the record. The first valid frame is
  the first `presence` or verified `frame` record of the newcomer's key; an item is its first verified `frame` record.
- *Offset*: from when the last flood producer sent its first datagram to when the newcomer starts. The flood runs before the
  newcomer at every offset, 0 included (there by milliseconds).
- The flood's producers log what they sent in each second and when they stopped, so every run shows that the flood ran, and
  at what rate, through every deadline.

## The workload

- **The newcomer** is pass 2's: a real `canticle` carousel of one key with one stream, from one bound socket on 127.0.0.1. It
  sings 20 chatter items 150 ms apart from its start (default TTL 60 s; copies at +0, +1, +2 and +4 s, then each loop), and a
  beacon a second. Nothing of its key has been heard before by that daemon.
- **The flood** is pass 2's forged one: distinct frames that name the newcomer's key and stream, each with its own invalid
  signature that reaches the signature check, every other one a beacon, from 127.0.0.1. 20 000/s from one producer process,
  100 000/s from two. "Ports" are split between the producers.
- **The flood lasts until every item's life is over**: 64 s after the newcomer starts (the last item is sung at 2.85 s and lives
  60 s). So a missing item is lost, not censored: every deadline, and every later repeat, fell inside the flood. Two seconds
  after an item's first send its deadline has passed, so nothing after that can turn a miss into a pass.
- One measurement at a time, every process at `nice -n 19 ionice -c3`, on ronan, loopback, throwaway keys, a scratch
  directory. Nothing live is touched.

### "Churned, N ports": two readings, both measured

A receiver sees only a source address and port, so the workorder's "churned forged sources … spread over N ports" can be read
two ways. Both are run; neither is dropped for its result.

- **`churn-N` (the deciding reading):** N sockets are open at once, and each datagram is sent from a newly opened one that
  replaces the oldest (the kernel picks its port out of 28 232). This is pass 2's "churned", spread over N.
- **`fixed-N` (the companion):** N sockets held open for the whole flood, used in turn. This is pass 2's `cold-start-N-ports`.
  A port closed and opened again under the same number is the same source to the receiver, so it is this reading too.

A verdict quoted without a reading is `churn-N`'s.

## Rows

| # | row | rates, /s | ports | offset, s | runs head / base |
|---|---|---|---|---|---|
| 0 | recovery (deciding) | 20 000, 100 000 | `churn-40` | 0, 5, 30, 120 | 5 / 3 |
| 0c | recovery, companion reading | 20 000, 100 000 | `fixed-40` | 0, 5, 30, 120 | 5 / 3 |
| 1 | saturation (diagnostic) | 20 000, 100 000 | `churn-12`, `-40`, `-200` | 1 | 5 / 3 |
| 1c | saturation, companion reading | 20 000, 100 000 | `fixed-12`, `-40`, `-200` | 1 | 5 / 3 |
| 2 | attribution (diagnostic) | 20 000, 100 000 | `churn-40` | 1 | 5 per toggle |

Order: 0, 1, 2, then the companions. Rows 1 and 2 are diagnostics. A flat result is not a bound, and the largest latency seen is
an observed maximum under this workload, never a guarantee.

Reported per cell: first-valid-frame latency per run; item latency, min / median / p95 / max over the runs (a lost item counts as
infinite); deadline misses, first-frame and per-item, eventual deliveries included; items more than one loop late; items lost;
kernel drops at the socket and the daemon's own report of them; refusals by reason; the flood's lowest whole second.

**Attribution toggles**, each a patch to the head's daemon, one at a time, committed beside these rows before its run:

- **(a)** per-source verify shares and the stranger pool off. It has two halves, each also run alone: the per-source lanes, and
  the budgets for checks that come to nothing (`SOURCE_RATE`, `CHECK_RATE`).
- **(b)** the key : stream round-robin off: one queue for every listed key and stream.
- **(c)** debit-after-verify off: a claim debits its key and stream before the signature is checked.

Smoke runs of the harness (a few seconds, to see that it works) are not evidence and are not kept.

## Added 2026-11-24 00:30Z, after row 0 had run and while row 1 was running

Rows 0-2 are unchanged. Three diagnostics are added, because row 0 raised a question it can't answer: on the head, a copy of the
newcomer's is verified about as often at 100 000/s (1 in 41) as at 20 000/s (1 in 29), where the code reads as if it should be
five times rarer. The paced producers send in millisecond bursts with silence between, and that may be what hides it.

| # | row | rates, /s | ports | offset, s | runs, head |
|---|---|---|---|---|---|
| 1s | saturation, evenly spaced sender | 20 000, 100 000 | `smooth-40`: `churn-40`, each datagram sent when it is due, the producer spinning between | 1 | 5 |
| 1r | saturation, rate | 200 000 (four producers; about what four can churn) | `churn-40` | 1 | 5 |
| 1m | model: the head's own `Intake` in virtual time (`newcomer_model.py`), no sockets, no signatures | 5 000 – 400 000 | churn and fixed, even and in bursts | – | – |
