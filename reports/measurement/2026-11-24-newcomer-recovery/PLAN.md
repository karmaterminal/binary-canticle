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

## Added 2026-11-24 18:10Z, before any run: the room's answer, and what changed in the slice

Nothing has been measured. The fork above (own-key floods) was posted at 17:15Z and answered on #173 by 🍃 with 🌫's amendments
([7138942171](https://github.com/karmaterminal/binary-canticle/pull/173#issuecomment-7138942171), [7138973579](https://github.com/karmaterminal/binary-canticle/pull/173#issuecomment-7138973579)): **A** (churned own-key
floods are outside the guarantee, with their numbers), plus a rule inside each key's slot; B stays an option, C a separate design. **Pass 3's original own-key failures stay failures in the verdict.** No row,
threshold or run count above changes, except that one diagnostic is added (W). The slice as first built (`ea633f2`, the latest datagram has the slot, a failed source stands aside for 2 s) is superseded by:

- **One pending frame per source** in a key's slot, at most 64 sources. It keeps its place until its turn: nothing that comes later replaces or sheds it. ("The latest" above is withdrawn: what is replaced has no bound.)
- **Untried sources first, in the order they came. A source whose frame failed is demoted** behind them: one turn in **M = 4** of the key's slot, so retries are bounded and nobody is banned. The next frame of its that verifies clears it, new or not.
- A key holds at most **256** sources demoted (and 64 of them waiting), for **2 × 257 · K / 500 s** (16.4 s for 16 stations): twice the rounds it takes to try them all, so that no demotion ends before the turn of a newcomer that waits for them.
- A ticket out of a slot holds none of its station's tokens until it has verified, and a turn has **16 places for slots beside its 32**, so neither what the queues hold nor how many copies they are full of keeps a key from its turns.

**The bound, restated** (S: sources claiming the newcomer's key that are not tried, or whose demotion has ended, when its copy arrives; K_f: keys whose slots are contended; T: a turn, at most 48 checks of 140 µs and one save of 40 ms = 47 ms; C_eff = min(500, 16/T) = 500/s, or 340/s when every turn carries a save):

| | its first copy is checked within | in numbers for the rows, delivery allowance of 0.1 s included |
|---|---|---|
| (B1) its key isn't forged | K/C_eff + 20 ms + T | K = 16: **0.22 s** |
| (B2) it is forged from S ≤ 63 sources that stay | (S + 1) · 4/3 · K_f/C_eff + 20 ms + T | K_f = 1: S = 40 (offset 0): **0.33 s**; S = 0 (all tried): **0.17 s**. K_f = 16, S = 0 (N2): **0.23 s** |
| the same, 63 < S ≤ 256 | not at once: a full slot has no place for its first copy. Once each was tried (S/C_eff) it is the row above, from its next copy | not a row |
| (B3) sources used once, or more than 256, or cycling faster than they are retained | **none** | N0: p ≤ (1 000 + 500)/R a copy |
| its exact source is spoofed | **none** (outside) | - |

It is a deadline from arrival to check, not only of rounds, because (i) a place: a contended newcomer's frame gets one when fewer than 64 untried sources wait; (ii) survival: nothing takes it away (`SlotTest`, `NewcomerTest`); (iii) service: a turn asks the slots first, 16 places of its own, one key after the other, and the loop turns while anything waits; the bucket is theirs alone. What it assumes is unchanged.

**The REDs of the answer**, on `f21eae8` (the rejected form, the two renamed pieces of state shimmed) and on this form: demotions retained for the claimed wait, and lost to nobody, with as many sources as a key can hold (RED, 2 of 80 newcomers never checked); more than that (RED by the cap; outside, nothing claimed); a demoted source's valid frame while untried ones keep coming (RED: 161 ms against 8 + 27 ms);
the pending frame's survival (RED); every key's service under a full flood, with a save in every turn too (RED: 44 of 640 turns for one key alone). S = 1, 4, 16, 40, 63 sources that start with the newcomer: checked within (S + 1) turns at both rates (RED on `base`).

| # | row | what | runs |
|---|---|---|---|
| **W** | #177 at the daemon (a diagnostic) | `nobudget` (pass 3's `toggles/a-budgets.patch`: the head's two check budgets lifted) on `a0862c3` and on 🕯's `0f55b1d`: `churn-40-20000-30` and `-120`. Pass 3's finding was 16.4 and 56.8 s there. 🕯's passes if its first frame is ≤ 1.0 s in every run; reverting his commit must miss it | 5 with `0f55b1d`, 3 without |

W runs after E1. It decides nothing about the slice.

**That section's time, corrected:** it was committed at 17:53Z (`38bd631`), not 18:10Z. Nothing had been measured then, or has been since.

## Added 2026-11-24 18:26Z, before any run: what two independent reviews of the code changed

Nothing has been measured. No row, threshold or run count changes; three points of the rule and the bound do, each a RED first:

- **Clears:** a demotion is cleared by a frame that is *new, or is kept* (a resurfaced one), not by any that verifies. An old beacon verifies for ever, so a source that replays one now and then would be untried for ever. A verified frame
  that changes nothing demotes its source. (7138942171 says "a valid frame"; this is its reading here, for 🍃 and 🌫 to agree or amend.)
- **A newcomer's frame waits in its lane as on the base, and the slot holds a second claim on it,** void once either serves it. So a slot is never a worse place than the queue was, and an echo behind it goes round neither.
- **Strangers pay for the slice, not established stations.** The queues keep 2 000 checks a second, strangers of all keys 1 500 of them; the slots' 500 are beside. What strangers cost is 2 000 as before (2 500 only while a known station's exact source is
  spoofed as well, which is outside). In (B1) C_gen is 1 500/s; K/C_eff stays the larger.
- A verified ITEM or PLUCK that changes nothing counts as **ten** turns of its own key. The second review's numbers (virtual time, base / the form before / this one): S = 200 sources that stay and replay, newcomers within the S = 0 bound 0 / 0 / 79 of 79; K = 64, S = 63, all keys, first frame 0.189 / 10.758 / 0.007 s; an established station's echo credited 0 / 20 / 0 of 20.

(B2)'s "S" counts sources not tried yet **or whose demotion has ended** (retained 1.03 s · K).

## Added 2026-11-24 19:17Z, before any run: 🍃's restatement of what clears a demotion

Nothing has been measured. [7140567401](https://github.com/karmaterminal/binary-canticle/pull/173#issuecomment-7140567401) (18:23Z): a demotion clears only on a frame **admitted as new**. Taken as it is: what resurfaced after a daemon restart no longer clears (the last section's "or is kept" is withdrawn; in virtual time
a station that goes on over a daemon restart is then known after 1.6 s in a fixed-40 own-key flood, median of 12 salts, against 0.5 s had it cleared and 15 s on the base).

It also says that a verified replay "counts as neither a failure nor a recovery". It is not counted as a failure here, and its source is nevertheless **no longer untried**, so it goes behind those that are (the same place as a demoted one). *Why not left where it was:* 64 sources with one old beacon
each would have all 64 untried places at every moment. With 100 more that forge (164 that stay, within the 256), 22 of 80 newcomers were never checked at K = 1 and 51 of 80 at K = 16 (virtual time; base 57 and 60 of 80); as it is here, 0 and 0, all within one round (`test_sources_that_only_replay_hold_no_untried_place_for_good`, RED under the letter). For 🍃 and 🌫 to agree or amend.

## Added 2026-11-24 19:33Z, before any run: the third review

Nothing has been measured. A third independent review, with 5.2 million fuzz steps, found five defects, each a RED before its fix. No row, threshold or run count changes.

- **A key or a stream that couldn't be served lost its turn** to whatever was served meanwhile. It is on #173 too, and there it starves *established* stations: in a flood that is half junk (no frames) and half forgeries of other keys, 392 of 784 frames of four established stations were never served (virtual time, K = 64), and 313 of 784 at K = 16. Here a
  key keeps its turn: none is lost, and the longest wait is 1 ms for them and 33 ms for a newcomer of a key that nobody forges (base 147 ms). **(B1) rests on this**, and on the base it held only while nothing else was served.
- Replayed records held up untried newcomers: they now put off only their key's demoted sources.
- A source whose forged bytes shared another's verdict stayed untried (RED: of 200 that send the same bytes, 60 of 60 newcomers never checked; here 0).
- A datagram counted nowhere (the same bytes again in a lane while a claim held them alone).
- A digest scan per datagram under the lock (5.1 µs against 1.1 µs on the base; here 1.2 µs, and 1.5 µs where a churned flood is placed, against 1.2 µs).

## Added 2026-11-24 19:45Z, before any run: row J

Row J asks over sockets what the third review found in virtual time: #173's scheduler makes established stations lose their turns while junk is served.

| # | row | what | runs | pass |
|---|---|---|---|---|
| **J** | established stations in a flood of junk and other keys' forgeries (`junk_rows.py`) | 16 stations; four established ones sing 57 items each, 150 ms apart; the flood is half junk (no frames, so the unlisted queue) and half forgeries of the 12 others' keys, from 40 ports held open, 20 000/s and 100 000/s, 13.6 s | 5 `slice`, 3 `base` | each of the four 57 of 57 during the flood in every run, p50 ≤ 250 ms, none later than 4.5 s, drops reported |

Prediction: `base` fails at 20 000/s or above, `slice` passes. J runs after W, and it gates nothing of the newcomers' rows; it is a finding about #173.

## Added 2026-11-24 20:23Z, before any run: three tiers

Nothing has been measured. 🍃 agreed at 19:53Z ([7142734748](https://github.com/karmaterminal/binary-canticle/pull/173#issuecomment-7142734748)) that a replay's source is *tried, not failed*, and stated the order inside a key's slot as three tiers: untried; tried and not failed, in turn among themselves; failed, one turn in four. A replay never
moves a source up, and an admitted new frame moves one from the third tier to the second. Built so, with both conditions as tests. Row J stays, as the standing regression row 🍃 asked for.

- **One completion, for 🍃 and 🌫 to amend:** the one turn in four is for *tried* sources, the two kinds in turn when both wait (a failed one then has one in eight). With the second tier strictly behind the first, it would never be served in a churned flood, where untried sources keep coming, while the third tier is. The bound for newcomers is the same.
- What it buys (virtual time): **a source that was tried and did not fail is served within eight turns of its key even in a churned flood of its own key** (`test_a_source_that_was_tried_and_did_not_fail_is_heard_in_a_churned_flood_of_its_key`): a station that a relay displaced, whose lease ended, or whose items resurfaced after a daemon restart (known after 0.5 s in a fixed-40 flood; 1.6 s before, 15 s on the base). It is no source authentication: whoever can replay can be tried as well, and they take turns.
- A source that loses its known place is marked as tried.

(B1) and (B2) are unchanged.

## Added 2026-11-24 22:04Z, before any run: row J corrected, and `a0862c3` as a column of it

Nothing has been measured over sockets. 🌿 asked ([7145087471](https://github.com/karmaterminal/binary-canticle/pull/173#issuecomment-7145087471)) that row J run on #173's own head `a0862c3` as well, and found no control that tells the two trees apart. Making one showed that **what this file and the lane's report of 19:44Z said about the finding was imprecise, and is corrected here**:

- The third review's flood forges *every key but the newcomers'*, the established stations' own among them. With that, and half of it junk, 216 of 784 frames of four established stations are never served on `a0862c3` at K = 16 and 392 of 784 at K = 64. **With forgeries of other keys only, or without junk, none is lost there.** On this lane none is lost in any of the eight cells ([`results/junk-model.md`](results/junk-model.md), `junk_model.py`: the trees' own `Intake` in virtual time, any tree).
- The same mechanism at its smallest, in state both trees have: `OrderTest.test_junk_that_is_served_takes_no_keys_turn`. On `a0862c3` a datagram whose turn it is loses it 19 times of 20; here never.

Row J is therefore two rows, on three trees (`head` is `a0862c3`; `base` is it with 🕯's `0f55b1d`; the intake is the same in both):

| # | row | the forgeries claim | runs `slice` / `head` / `base` | prediction |
|---|---|---|---|---|
| J | `junk-40-20000`, `junk-40-100000` | the 12 other keys | 5 / 3 / 3 | all pass |
| **J-all** | `junkall-40-20000`, `junkall-40-100000` | all 16, the four established ones' too | 5 / 3 / 3 | `head` and `base` fail, `slice` passes |

## Added 2026-11-25 01:10Z, before any run: who arrived first, and how I-a is read

Pass 3 is COMPLETE (00:57Z, `5fcc2c28c6`; 🍃 reproduced it at 01:02Z). Short smokes of the harness ran before the queue (not evidence, not kept). They showed that **row I-a would fail, on `base` and here**: a newcomer's frame waits up to about 20 ms for a stranger's check, and a *known* relay
5 ms behind it has its copy checked first, so the relay is credited, frame after frame, and the station never gets a place. Changed, RED first (`EchoTest`): **the first to be heard with a new frame has the share, whichever copy of it was checked**; the source whose copy was checked keeps its place as before. An echo that comes later has no part in it. A relay *ahead* of the station is still heard first (I-a′, outside).

I-a's "place" is read as `receive.known` growing by one or more after the start, from what it was then. A relay that is known again grows it as well, which `base` does, so on `base` this half is no evidence of the station's own place; the ten items under the churned own-key flood are.

## Added 2026-11-25 10:18Z, while N1c was running: underdriven runs, what is known of them, and how their cells are completed

🌫 ran the comparator on the published N1 corpus ([7154512527](https://github.com/karmaterminal/binary-canticle/pull/178#issuecomment-7154512527)): four of its 64 runs are INVALID, their flood having fallen under 95 % of its rate in its lowest whole second. This lane had reported "8 of 8 on both trees" from the harness's own verdict without running the
comparator on N1: **that report is withdrawn until the cells are complete.** The same check on the rest so far: N0, W, J and E1 none; N1 4 of 64 (3 `slice`, 1 `base`); N0c 10 of 64 (9, 1); N1c 9 of the first 59 (8, 1). It is the host: from about 04:15Z a self-hosted CI runner ran jobs on ronan beside the queue (the load before a run, 2-3 through N0, was 4-17), and these producers
are at `nice 19`. Nothing that was run is discarded, the floor stays, and no run is chosen by how it ended.

- An INVALID run stays in the raw file and in the tables. Its cell is run again (`complete.py`, the next run number, the same harness, at most as many again as were declared) until it has the declared number of valid runs, after the queue, one at a time. Which cells are completed depends on the flood's rate alone.
- A deadline missed in an INVALID run **fails** its cell as well (an underdriven flood is the easier one). A cell that stays short of its valid runs is INVALID, not PASS.
- `judge_rows.py` says so per cell; 🌫's `oracle.py` is untouched.

## Added 2026-11-25 10:28Z: a process of this lane's own ran beside every row so far

At 10:27Z, with N2 starting, `ps` showed a leftover of this lane: PID 3640405, a `python -m unittest` of `test_intake.py` at `nice 19`, in an endless loop of a test that a mutation of the code had made endless (an unbounded loop of the test's, bounded since). Its parent was killed at 18:00Z on 11-24 and it was not. **It held one of the host's 20 cores at
`nice 19` from 17:58Z on 11-24 until it was killed at 10:27Z on 11-25**: through E1, W, J, N0, N1, N0c and N1c here, and through the last seven hours of pass 3's queue (its full-length repeats, 17:58Z to 00:57Z). PLAN.md says that nothing runs beside a measurement, so this is a departure, and it is told to pass 3's reviewers. From N2 on it is gone.

It is not known to have changed a verdict. It ran beside every tree alike, at the lowest priority, with 17 and more cores to spare until 04:15Z, and the rows that fail (N0) fail on every tree for a reason that is not the CPU. No run is discarded for it, and what is run again (the cells of underdriven runs) is run without it. The rows it ran beside are marked in the report.

## Added 2026-11-25 11:52Z, while E2 was running: a claim of the "three tiers" section, withdrawn

That section says that a source which was tried and did not fail is served within eight turns of its key *even in a churned flood of its own key*. **That holds only while the key remembers it.** A key remembers the latest 256 tried sources, and a churned flood of its own key adds 1 500 a second, so a mark lasts 0.17 s: in virtual time a source tried up to 0.15 s before
its frame is checked in 3-24 ms, and one tried 0.2 s before it is untried again (0.18 s once, and not within 0.5 s when tried 0.5 s or 1 s before). E3's `relay-first-then-churn-100000` shows it (20, 20, 7, 0 and 20 of 20 on `slice`; 2, 1, 20, 20 and 10 on `base`): outside the guarantee, as before. The unit test sends its frame at once, and says so now. In floods from sources
that stay (fewer than 256) the claim stands. *Not changed here*, since the code is frozen for these rows: a table of its own for the sources that did not fail would keep them from being turned over by those that did, though not by replays from churned ports. For the next change, with its own rows.

## Added 2026-11-25 13:31Z: E2 failed on `d49645b`; the code changes, and what is measured on what

E2's run 0 on `d49645b` (`results/full/slice/run0/`): **R3 56 of 57 (one item 15.3 s late) and R4a 56 of 57; FAIL.** R1, R2, R3c, R4b and the F rows passed. 40 % of R3's datagrams were dropped at the socket (pass 1 on #173: 23 %, at a higher rate), so items of the established station were lost by chance to the reader being outrun. Two causes in this lane's code: the slot's
bookkeeping on every datagram (`offer`: 1.64 µs against 0.92 on the base, fixed ports), and 500 checks a second of the same forgers, each waking the loop. Runs 1-4 of E2 were not run. Both are changed (`8495138`: 0.96 µs; a quarter of the slice for sources that were tried). The rules of the slot are what they were, with one
consequence stated here: **sources that were tried have at most 125 checks a second of the slice**, also when nothing else waits (it was the turn in four only where untried ones waited).

- **All of `d49645b`'s rows stay, as that commit's.** The gate is judged on the new commit: **E1, E2, N0, N0c, N1, N1c, N2, I, E3 and J run again on it**, `slice` only where `base` (and `head`) already ran the same harness (their runs are not repeated); INVALID runs are completed as declared. Results go to `results-2/`.
- Before that, one diagnostic, not evidence for any gate: **AB**, R3 and R4a of #171's harness for 60 s, `base`, `old` (`d49645b`) and `new` in turn, three times: the share dropped at the socket. Its purpose is to not spend five hours on E2 if the reader is still outrun sooner.

## Added 2026-11-26 09:40Z, before any run on the new code: 🍃's finding, the change, and the third set

**What has run.** Everything declared for `72db59f` (`new`, results-2/). The lane stopped at 23:53Z on 11-25 in E2's run 2; its queue was not a child of the
session and went on alone to E2's runs 2-4 and the completion of every cell with an underdriven run, `new` and `base`, until 03:35Z on 11-26 (`b0047e2`, copied
as it was written). Nothing of this lane ran beside it.

**What 🍃 found** ([#178, review 6068314339](https://github.com/karmaterminal/binary-canticle/pull/178#pullrequestreview-6068314339)), in `8495138` and so in
`72db59f`: a claim is no longer re-tiered when its source sends again. On `d49645b` (`slice`), `_stand` moved a claim to its source's current tier on each of the
source's datagrams; since `8495138` a datagram from an address that has a claim is looked at once and nothing moves it, so it keeps the tier it was made with until
it is served (one turn in SLOT_M, on the retries' bucket). The commit didn't say so. **So the two earlier sets measured two rules:** `slice` (results/) with
re-tiering, `new` (results-2/: E1, E2, N0-N2, I, J, E3) without it.

**The change**, RED first, each its own commit:

- `a7d65f3`: 🍃's two tests as he gave them (the demotion ended; the mark was forgotten), the nearest sibling (a move that found its tier's ring full left a failed
  source in an untried place), and the boundary of the fix (an exact copy of bytes waiting in the source's lane re-tiers nothing; its next other datagram does).
  All four fail on `72db59f`; the first three pass on `d49645b` and fail on `8495138`.
- `00b44d7`: 🍃's line. The four pass. Its reader cost was not measured.
- `dfa0414`: the same rule at `72db59f`'s reader cost. 🍃's line asks the key for the tier on every datagram of a source that has a claim, and on a flood
  from ports held open (E2's R3: two producers, one socket each) that is every datagram. Now a claim carries `until`, when its marks stop giving its tier; its
  source's next datagram looks only from then, or at once when the key forgot the source or the move found no room. ConsistencyTest's random traffic checks at every
  step that no claim's tier differs from its marks before `until`, and that a claimant's datagram leaves its claim at its marks' tier or that tier's ring full: red
  on `72db59f` and on three mutants, green on 🍃's line and here. Station suite 599 OK.

`offer()` per datagram (`bench_offer.py`, results-3/bench-offer.log: the minimum of 11 interleaved runs on ronan, load 17, a diagnostic and no row):

| flood | base | `72db59f` | 🍃's line | `dfa0414` |
|---|---|---|---|---|
| 40 ports held open | 1.14 µs | 1.18 | 1.31 | 1.19 |
| 4 ports held open | 0.94 | 0.98 | 1.09 | 0.99 |
| churned | 1.24 | 1.29 | 1.32 | 1.31 |
| old beacons replayed | 0.57 | 0.59 | 0.59 | 0.59 |

**Which rows it could affect, from the code.** It moves something only when an address that is not known has a claim waiting in its key's slot, sends a datagram
that is not a copy of one waiting in its lane, and its marks changed meanwhile: they ended (`retain`, 1.03 s × K: 16.4 s at K = 16), the key forgot it (MARKS_MAX
other sources of the key marked since: 0.17 s in a churned flood of the key), or its tier's ring was full when it was marked.

- **Churned floods of the newcomer's own key: N0, and E3's `cold-start-churn-*` and `relay-*-then-churn` rows, and I's own-key phase.** A churned flood forgets
  in 0.17 s, and an address does come back: the kernel's ephemeral ports on loopback (28 000) turn over every 1.4 s at 20 000/s and every 0.3 s at 100 000/s, so
  forgers' addresses return, and a newcomer's port may be one a forger had a moment before. 🍃's own-key correlation (d49645b: first frame > 1 s in 21 of 40
  runs; 72db59f: 28 of 40) is about these. *These rows could change; they are outside the guarantee on every tree and stay so.*
- **Floods from ports held open (N0c, N1c, N2, J; E1 and E2's R3, R4a):** each forger is checked again within a fraction of a second, so its marks are renewed
  long before they end; the key remembers all of them (40 ≤ 256); no ring fills (40 ≤ 64). Nothing moves. Its cost there is measured above.
- **N1 (other keys, churned):** the newcomer's key is not forged, so the newcomer never has a claim. **Known sources** (R1, R2, R4b, F5, the inverse rows'
  stations once known, I-b's replays, which are repeats) never have one; their datagrams now skip one lookup.

**The third set.** The gate is judged on the code that would merge, as on 11-25: **every row runs again on it**, with the declared harness, runs and bar unchanged,
results in results-3/. The tree `fix` is a `git archive` of the commit that adds this section (its `intake.py` is `dfa0414`'s), and so is the harness. `new`'s and
`slice`'s rows stay as those commits'. 🌫's floor stands: an underdriven run stays INVALID and in the tables, its cell is completed (`complete.py`, at most as many
runs again as declared), a deadline missed in an INVALID run fails its cell, and a cell short of valid runs is INVALID, never PASS.

1. **AB** (a diagnostic first, deciding nothing): R3 and R4a of #171's harness for 60 s flat out, `new` and `fix` in turn, three times; the share dropped at the
   socket. If `fix` is outrun where `new` is not, the queue stops and the lane says so before E2.
2. E1; N0; E3; I; J; E2 run 0 (R and F rows); N0c; N1; N1c; N2; E2 runs 1-4; then the completions. The rows the change could affect come first.

**The host is shared.** At 09:20Z on 11-26 its load was 15-30 (a self-hosted CI runner and other lanes' tests), and the producers run at `nice -n 19`, which is how
runs were underdriven on 11-25. Before each step of the queue (a harness invocation, an E2 row, a completion), it waits until the one-minute load average is below
8, for at most 15 minutes, and then starts anyway; the wait is logged, and each run records `load_before` as it always has. Nothing is chosen by how it ended.
