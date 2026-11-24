# Newcomer recovery: the reserved slice, its bound and its rows, declared before any run

**Status:** predeclared. Committed and pushed before the first run and before the code it measures. Not edited after that: a change to
the method is a new dated section at the end, and says what had already been run.

[#173](https://github.com/karmaterminal/binary-canticle/pull/173) is held for recovery evidence. This is the separate, reviewed change that
would move it, stacked on it: the pull request is against #173's branch and merges nothing by itself.

| ref | what | SHA |
|---|---|---|
| product base | `codeagent/bc-daemon-fair-admission-2` (#173's head) | `a0862c3eeb0b84236661451ca5c3d00127536d27` |
| #177, 🕯's | `emeric/bc-177-collapsed-wake` | `0f55b1d2d7b2063a0adaeb308365913b6253d909` |
| measured base (`base`) | this lane's merge of the two, no other change | `966857bb070a1973e6974d56ed1dd37dcd9409b7` |
| this lane (`slice`) | `codeagent/bc-173-newcomer-recovery`, published at `a0862c3e` before any work | named in the report when it is measured |
| inputs | `codeagent/bc-173-pass3c`, `reports/measurement/2026-11-23-cold-start-recovery/` | `9997849a99ac171261c2019c4955c32c62c94581` (final head named in the report) |
| CI workflow | `.github/workflows/tests.yml`, as on `main` `d4c306618f7f77658fe73705d58b2744f2486701` | dispatched on this branch; run ids in the report |
| presentation ref | N/A | |
| docs/proof ref | this directory | |

Each was resolved locally, as the tracking ref and on the server, and the three were equal. `cryptography` must be 50.0.1 (the CI lock); every run
records it and refuses another.

## What pass 3's rows flood, and why that matters here

Pass 3's newcomer rows (0, 0c, 1, 1c, 2) all forge **the newcomer's own key and stream**. The design this change was asked for schedules a reserved slice
per claimed manifest key, with a stated limit: *an attacker forging the newcomer's own key id still contends that key's queue; the bound holds for every key
the attacker isn't forging.* So the bar as pass 3 measured it and the guarantee as the design states it are about two different floods. Both are
rows here, under their own names. Neither stands in for the other.

A probe of the base's own `Intake` in virtual time (no sockets, no signatures, no load), made before this file was written, says:

- **Other keys forged, churned ports on the newcomer's own host:** on the base its first copy is picked within K/2000 s (5 ms for K = 9, 8 ms for 16, 32 ms for 64), at
  20 000/s and at 100 000/s alike. The round-robin over claimed keys that #173 already has gives that. The two required tests of it are therefore **guards: they
  pass on the base**, and no RED is claimed from them.
- **Own key forged:** churned it is the lottery p = C/R (first copy after 0.4-2.8 s at 20 000/s, and up to not within 8 s at 100 000/s); from fixed ports it depends on the salted lane. These are the REDs.

## The change

1. **🕯's collapsed wake** (#177), merged as it is.
2. **A reserved slice of verify work for sources without tenure.** Every listed key has *one* place (its slot) beside its queues. A datagram from a source with
   no known place, when others already wait in the stream queue it claims, takes the slot: the latest one wins, and what it replaces waits in
   the queues like anything else. The slots are served in turn over the **keys**, on a bucket of their own.
   - `SLICE_RATE` = **500 checks a second**, `SLICE_BURST` = 50, carved **out of** the daemon-wide 2 000 (the general bucket becomes 1 500), so what the daemon spends on checks that come
     to nothing does not grow. *Why 500:* K/500 is 0.128 s for 64 stations, an eighth of the 1.0 s deadline; 500 checks are 3-7 % of one core on ronan at 60-140 µs.
   - Half of a turn's 32 places (16) are reserved for the slots, so that a turn that pays for a durable save (about 40 of them a second) still serves more than 500 slots a second.
   - **A source whose check came to nothing in the last 2 s doesn't take the slot** (the latest 512 such sources of a key are remembered, by address and port). It still waits in the queues as today.
     So the slot is not a raffle among the *same* senders: sources that are fixed are each tried once and stand aside. It doesn't look at lanes or at the salt.
   - A verified, new frame costs the slice nothing (its station pays, as everywhere). A verified ITEM or PLUCK that changes nothing keeps its *key* out of the slice for the time of nine more
     checks, since it makes a record: a key can't spend another key's share with it. A slot never passes the key's and stream's own rates. Nothing that names no listed key ever gets a slot.
3. **A lease on a known place** (its own commit, so it can be dropped). Only because row I-b needs it: on the base a known place has no end.
   - *Clock:* `CLOCK_MONOTONIC`. *Criterion:* the age of the newest frame of the key that this source delivered, counted from when the daemon **first verified that frame**. *Horizon:* `LEASE_S` = **60 s**; the default
     beacon period is 1 s and a relay's slowest is one per 5 s (RFC-0001 §8.3), so a live station renews it 12 times over. Queue-empty is not inactive: nothing waiting means nothing here.
   - An exact repeat renews it only up to *that frame's first verification* + 60 s, however often and however late it is replayed, and only for a source that already has the place. A repeat never gives a place.
   - Who is displaced by a newer source is unchanged (the one whose last new frame is the oldest). **None of this authenticates a source** (I-11).

## The bound, from the code, and what it assumes

K = the manifest's listed keys (revoked ones have no queue); C_slice = 500/s; C_gen = 1 500/s; R = the flood's rate; *turn* = one event-loop turn, at most 32 checks (60-140 µs each, #171) and one durable save (25-40 ms), so
**≤ 45 ms**; *retry* = 20 ms, what the loop waits before it looks at a spent budget again.

| the newcomer | its first copy is checked within | independent of R? |
|---|---|---|
| **(B1)** its key isn't forged (others are, by whatever churn, on its own host too) | **K/C_slice + retry + turn**. It waits in its own key's queue, which nobody else fills: at most K picks of the general bucket, K/C_gen, or of the slice | yes |
| **(B2)** its key is forged from at most N ≤ 512 sources that stay (`fixed-N`), N ≤ 2 s × the checks the key gets | **K_f/C_slice + retry + turn** after each of the N has been tried once since it last stood aside, where K_f ≤ K is the number of keys whose slots are contended. Before that (a flood that starts with it) at most **N/(C_gen-share + C_slice/K_f)** more, and the time to its next copy (150 ms in these rows) | yes |
| **(B3)** its key is forged from sources used once (`churn-N`), on its own host | **none.** A copy is checked with chance p ≈ (C_strangers + C_slice/K_f)/R = 1 500/R at most. The honest limit | no |
| an exact-source spoof of it | none (outside, as in #173) | no |

Assumptions: the reader keeps up (what the kernel drops at the socket is chance, and counted); the event loop gets a core's worth of time when it wants it; the newcomer's frames verify and are new; K_f keys' stations themselves stay within their
rates. The bound is for *checked*; publishing to the client follows in the same turn plus the connection's writer, which #177's collapse keeps from queueing behind older turns. Allowance for a niced process on this host and for the client's read: 0.1 s.

**In numbers for the rows (K = 16):** B1: 0.032 + 0.020 + 0.045 + 0.1 = **0.2 s**. B2 (N = 40, K_f = 1): 0.002 + 0.020 + 0.045 + 0.1 ≈ **0.2 s** from offset 5 on; at offset 0, 40/1 500 + 0.15 more: **0.4 s**. A measured row whose first frame is later
than its number is **outside its bound: reported as such, whether or not it is inside the 1.0 s deadline.**

**Predictions, written before any run:** the other-keys rows pass on both trees. The fixed-40 own-key rows pass on `slice` and not on `base` (31 % of runs share a lane). The **churned own-key rows fail on `slice`, as on every tree pass 3 measured**: p ≤ 7.5 % at
20 000/s and 1.5 % at 100 000/s, and with the 8 copies of its first second P(first frame later than 1.0 s) ≈ 54 % and 89 % a run. 99 % would need p ≥ 44 %: 8 800 checks/s and 44 000/s. No small slice does that.

## Thresholds (pass 3's bar, unchanged)

- **Pass:** the newcomer's first valid frame is delivered to the local client **≤ 1.0 s** after the newcomer's first actual send, and **each item ≤ 2.0 s** after that item's first actual send.
- **Any miss fails its row**, late or missing. A row is one cell: every run of one tree at one kind, port count, rate and offset. Deadline misses are **late + missing**, always both.
- **Severity label, not a gate:** later than 10 s is "more than one loop late".
- **The flood keeps running through every deadline.** Recovery after it stops does not pass and is not counted.
- Monotonic clocks. Pinned runtime, recorded per run. One measurement at a time, `nice -n 19 ionice -c3`, on ronan, loopback, throwaway keys, scratch directories. Nothing live is touched. **No run before `[bc-173-pass3c] … complete`** is in the receipt log.

## Rows

The newcomer is pass 3's, unchanged: a real carousel of one key and one stream, one bound socket on 127.0.0.1, 20 items 150 ms apart, a beacon a second, nothing of its key heard before. The flood is pass 3's `forged_flood.py`,
20 000/s (one producer) and 100 000/s (two), and lasts 64 s past the newcomer's start. `churn-40`: 40 sockets open, each datagram from a newly opened one. `fixed-40`: 40 held open. The manifest has 16 stations.

| # | row | the flood claims | kinds | rates, /s | offsets, s | runs `slice` / `base` | judged as |
|---|---|---|---|---|---|---|---|
| **N0** | pass 3's row 0, unchanged (deciding by pass 3's bar) | the newcomer's own key and stream | `churn-40` | 20 000, 100 000 | 0, 5, 30, 120 | 5 / 3 | the bar; (B3): no bound claimed |
| N0c | pass 3's row 0c, unchanged (contrast) | the same | `fixed-40` | the same | the same | 5 / 3 | the bar; (B2) |
| **N1** | the same flood over the other keys (what the slice is for) | the 15 *other* manifest keys in turn, from the newcomer's own host | `churn-40` | the same | the same | 5 / 3 | the bar; (B1) |
| N1c | contrast | the same | `fixed-40` | the same | the same | 5 / 3 | the bar; (B1) |
| N2 | every key, the newcomer's too | all 16 in turn | `fixed-40` | 20 000, 100 000 | 5 | 5 / 3 | the bar; (B2) with K_f = 16: 16/500 + 0.02 + 0.045 + 0.1 ≈ 0.2 s |

**A verdict quoted without a row is N0's.** N1 is not a substitute for it: N1 passing while N0 fails reads *"the per-key guarantee holds, and the bar as pass 3 declared it is not met"*.

### Established stations must not pay for it (gate 1, unchanged)

| row | what | runs | pass |
|---|---|---|---|
| E1 | #171's flood rows, scaled (R1, R2, R3, R3c, R4), pass 3's `established_rows.py` | 5 `slice`, 3 `base` | 57 of 57 during the flood in **5 of 5** runs, p50 ≤ 250 ms, none later than 4.5 s, the kernel's drops reported |
| E2 | the same at full length on #171's harness (570 s; F rows 300 s) | 1 `slice` run of each, then 4 more of every R row | 57 of 57 (F: 30 of 30) at the daemon within 4.5 s during the flood, pushed to the ear, drops reported |
| E3 | #173 pass 2's `scaled_rows.py` (cold start, spoof, relay-first, churn-established) | 5 `slice`, 5 `base` | as pass 2; a row that failed there and here is named, never footnoted |

### The inverse rows (🌫)

| row | what | runs | pass |
|---|---|---|---|
| **I-a** | four relay endpoints (a socket each, no key) are heard first, each with a valid beacon of the station's that the daemon hasn't heard, so all 4 known places are theirs; they go on forwarding each later beacon 5 ms after the station's own. The real station then starts sending directly, from a new port (and, 10 s later, changes to another), while the 15 other keys are forged at 20 000/s, churned | 5 `slice`, 3 `base` | after each of the two starts it has a known place (`receive.known` grows by it) **≤ 1.0 s** after its first direct send, (bound: B1, 0.2 s), and once a churned **own-key** forged flood at 100 000/s begins 2 s later, all 10 items it sings are delivered ≤ 2.0 s |
| I-a′ | the same, the relays 10 ms **ahead** of the station on every beacon (relay-first) | 5 / 3 | not expected to pass: named *outside the guarantee* if it fails |
| **I-b** | an incumbent station becomes known, sings, and stops; its very socket then replays one cached beacon ten times a second | 5 `slice`, 3 `base` | its place ends at the horizon: `receive.lapsed` becomes 1 no earlier than 60 s and no later than **62 s** after that beacon was first verified (as the client read it, `health` every 0.5 s), replays and all; and never on `base` |

### The comparator

🌫's `oracle.py` (verbatim) and `judge_rows.py` **with the hardening of #173 issuecomment-7125278653**: a non-finite, negative or boolean rate floor and a missing producer denominator are INVALID, not PASS, with the paired regression test. It judges N0-N2's raw runs; where its verdict and the
harness's own differ, the report says so and the stricter one counts.

### Order

After the gate opens: E1 (cheap, and it gates), N0, N1, N0c, N1c, N2, I-a, I-a′, I-b, E3, E2. Raw results are pushed after each row. If the host or the lane dies, the queue goes on from what the raw file already has; nothing is run twice.

## Unit REDs, and what each one shows (no load; run before the gate opens)

| test | on `base` | on `slice` |
|---|---|---|
| a flood split across the other manifest keys doesn't delay a newcomer past K/C_slice | **passes (a guard)** | passes |
| the same from churned ports of the newcomer's own host | **passes (a guard)** | passes |
| fixed-40 ports of its own host forge its own key and share its salted lane: its first copy is served within the bound, for *every* salt | RED | passes |
| the same on K keys at once, a newcomer on each | RED | passes |
| churned own-key flood: a copy's chance is raised by the slice and stays a lottery (p bounded below and *above*, so that nobody reads a bound into it) | RED (no slice) | passes |
| the slice's checks that come to nothing never exceed `SLICE_RATE`·t + burst, and the daemon's total never exceeds 2 000/s | - | passes |
| established (known) sources are served as before while every slot is contended | passes (a guard) | passes |
| lease: I-a and I-b's unit halves, dup renewal bounded, lapse counted, queues consistent, random-traffic conservation | RED (no lease) | passes |

Each part undone alone must fail its own test (patch-revert), 🕯's `0f55b1d` included: reverting it must turn #177's RED red.
