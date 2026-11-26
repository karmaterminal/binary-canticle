# Review: #175's fixes in both receivers, and the RFC wording

Read-only review for 🌿, asked for by 🍃, of the two receiver fixes for binary-canticle#175 and of the RFC
text that would land with them. Nothing here was posted on GitHub, nothing was pushed to either pull
request, and no station, daemon or listener was started outside a test. Written 2026-11-26 by the
`codeagent/175-reviews` lane (Claude Code).

## Verdicts

| Subject | Verdict |
|---|---|
| **bc#191** (station listener) @ `30eb9f75` | **Approve once the should-fixes are in.** The fix does what #175 needs: the four REDs fail without it and pass with it, and the full suite and CI pass. There are no blocking findings. Two guards have no test (S3, S4), and the wording overclaims against 🪨's guard in four places (S1). The README doesn't list three RFC departures (S2). |
| **frond-ear#128** (embedded listener) @ `70a335d3` | **Request changes: one blocking finding (F-B1).** If a crash comes within a tick of a station restarting, journal replay keeps the old epoch's `bseq` for the new epoch. The station's honest beacons are then dropped as duplicates until its `bseq` catches up, which can take hours. Otherwise it matches bc#191's rule. |
| **RFC wording** | **Neither PR changes `rfc/`.** The proposed amendment text overclaims in one sentence: "a receiver MUST persist each key's `(epoch, bseq)` mark and its δ̂ samples across restart". rfc/0002 §0.7 decision 5 and the §0.6 row conflict with 🪨's ruling. Replacement text is in §4. RFC-0001 §13 is Discovery and is not touched. |
| **Default-safe** | **Yes for the skew bound:** it is off by default in both receivers and wired into no daemon. **There are four default-path changes beyond the fix itself** (§5). One is F-B1. One is a fail-closed liveness cost that needs to be named: honest items are refused for 16 beacons after a restart that corrected the receiver's clock. |

## Named refs

| Category | Ref | Full SHA | local = tracking = server |
|---|---|---|---|
| product (bc#191 head) | `gloss/175-durable-beacon-mark` | `30eb9f75e0b6f6eb3e1dd702307e71cbc6cb525a` | fetched = `ls-remote` = API `head.sha` |
| product (bc#191 base) | `main` | `2eb1a56d8fe4f1b250d4da3adec5611292f66948` | worktree HEAD = `origin/main` = `ls-remote` = API `base.sha` |
| product (frond-ear#128 head) | `gloss/122-durable-beacon-mark` | `70a335d3c1954f0a2b0892c480647356c593a1e9` | fetched = `ls-remote` = API `head.sha` |
| product (frond-ear#128 base) | `main` | `405e49183f76ed03066fe4d93bd4f75c2cdcc541` | `source/frond-ear` HEAD = `ls-remote` = API `base.sha` |
| lane | `codeagent/175-reviews` | published unchanged at `2eb1a56d…`; REVIEW.md is committed on top | `ls-remote` checked before the commit |
| CI | each PR's own CI at its head | bc: run 45754210926 (station-tests, protocol-dynamics-harness-tests, openclaw-plugin-tests on node 24 and 26), all success. frond-ear: run 45754994436 (check on node 22, 24 and 26), all success. | check-runs read at the head SHAs above |
| presentation | N/A | | |
| docs/proof | this file, on `codeagent/175-reviews` | the commit that adds it | |

Neither PR changes `pnpm-lock.yaml` or `package.json`. frond-ear's tests ran against the `node_modules` of
`source/frond-ear` at its base `405e4918`, through a symlink. No install was run.

## Method

- **Patch-revert.** In temp copies made with `git archive` of each head: the head itself; the head with the
  non-test files (`listener.py` and `wire.py`, or `listener.ts` and `wire.ts`) put back to the base; and the base.
- **Per-guard mutation.** Each guard was removed in turn from a copy of the head, and the listener tests plus
  my probes were run against it. For the two survivors, I also ran the whole station suite.
- **Probes.** Deterministic tests I wrote for the bypass hunt. Their source is in Appendix A, so that 🍃 can
  port them. They pass on the head and fail on the mutant or the bug they target, except where a probe
  is a measurement.
- **Environment.** Python 3.12.3 with cryptography 50.0.1 (CI pins the same cryptography, on Python 3.11),
  and Node v26.9.0. Full station suite on the bc#191 head: `Ran 425 tests … OK` (87 s). frond-ear on its head:
  the full `node --test` run and `tsc` results are in Appendix B.

---

## 1. bc#191: the station listener

### The invariant and its owner

**Invariant (#175).** After a receiver restart, a captured beacon at or below the kept `(epoch, bseq)` mark
neither counts as new nor moves δ̂. A captured beacon the receiver never heard can only add a larger δ̂
sample, and δ̂ is the minimum, so on its own it cannot raise δ̂. An ITEM's dedup entry outlives the item's
local expiry under any δ̂.

**Owner path.** All of it is in `prototype/canticle-station/canticle/listener.py` at `30eb9f75`:

- `Listener._beacon` (`listener.py:269-312`): the skew refusal (`:272-276`), then `_epoch_ok` (`:277`, which
  resets `bseq` on an epoch advance at `:261`), then the kept-mark check (`:281`) and the floor-move save
  trigger (`:285-288`).
- Dedup admission: `Listener._keep` (`:636-644`), called from the main admit path (`:394-396`) and from
  receptor mode's `_lower_epoch` (`:606-608`). The cap itself is `wire.local_expiry_cap_ms` (`wire.py:395`).
- The resurface recompute (`:371-373`).
- Persistence: the `beacons` table in `_save_if_dirty` (`:716-719`), the cadence in `tick` (`:694-697`), and
  `_load` (`:735-744`).
- The receptor saves the listener and its own state in one atomic write per datagram or tick, whenever
  `lst._dirty` is set (`records.py:217-233, 578-582`). So the floor-move trigger holds in receptor mode too.

### Patch-revert control

| Test (`tests/test_listener_replay.py`) | head | head with base `listener.py` + `wire.py` |
|---|---|---|
| `test_a_captured_beacon_and_item_do_not_land_fresh_after_a_restart` | pass | **FAIL** `'item' unexpectedly found in ['presence', 'item']` |
| `test_a_restart_keeps_the_beacon_mark` | pass | **FAIL** `0 != 1` |
| `test_a_beacon_of_an_epoch_it_missed_cannot_raise_the_offset` | pass | **FAIL** `'item' unexpectedly found` |
| `test_a_rise_in_the_offset_does_not_readmit_an_item_it_heard` | pass | **FAIL** `'item' unexpectedly found in ['item']` |
| `test_a_crash_loses_at_most…`, `test_a_state_file_without_marks…`, three `SkewBoundTest` cases | pass | ERROR (the API doesn't exist at base) |
| `test_honest_beacons_after_a_restart_still_count`, `test_residual_…`, `test_off_by_default…` | pass | pass (controls and the residual, as intended) |

The four REDs fail for the reason #175 names: the old item lands. All 12 tests pass on the head.

### Mutation

| Guard removed | Killed by |
|---|---|
| M1 kept-mark check (`:281`, `or st.bseq > 0`) | `test_a_restart_keeps_the_beacon_mark`, `test_a_crash_loses_…` |
| M2 tick save cadence (`:695-697`) | `test_a_crash_loses_…` |
| M3 samples not saved (`:718`) / M3b not loaded (`:743`) | `test_a_beacon_of_an_epoch_it_missed_…` |
| M4 no dedup cap (`_keep` returns `retain`) | `test_a_rise_in_the_offset_…`, `test_sticky_pluck_uses_the_current_clock_offset` |
| M5 skew bound removed / M9 skew check moved after `_epoch_ok` | `test_a_first_join_refuses_…` (it checks the epoch stayed 0) |
| M8 `bseq` not loaded (`:742`) | `test_a_restart_keeps_the_beacon_mark`, `test_a_crash_loses_…` |
| **M6 floor move not marked dirty (`:287-288`)** | **nothing in the full suite** (425 tests; the one error is my copy missing `rfc/`). Killed by probe P1. |
| **M7 resurface keeps the cap (`:373` → `retain = seen[1]`)** | **nothing in the full suite.** Killed by probe P2. |

### Bypass hunt

| Case | Result at `30eb9f75` |
|---|---|
| Restart mid-window, clean save | Closed: replayed beacons are `duplicate` and δ̂ doesn't move (tested). |
| Crash between mark saves | Bounded, as designed. Beacons from the last `MARK_SAVE_MS` plus one tick (the daemon ticks every 250 ms) are admitted again as new. They can make the station look present for up to three beacon periods. They cannot raise δ̂ (their samples are larger) and cannot land items (dedup rows are saved at once). A *lowered* floor is saved on the same datagram (`:287-288`), but no test covers that (S3, P1). |
| Receiver clock jumps | Forward across a restart: the kept floor is too low, so honest items are refused as `expired` until 16 new beacons replace it. P5 measured **16 beacons (17 s)**; at `main` it is 1 beacon. This fails closed, but it is new default behaviour (S6). Backward: the new sample is lower and is taken at once. |
| First join | Open, a named residual (🪨). Bounded only by `max_skew_ms`. |
| Replayed beacons above the kept mark: a higher epoch the receiver missed, *or* the beacons the same epoch sang while the receiver was down | Open, a named residual. 16 such beacons push the kept samples out, and an old item lands (`test_residual_…`). The residual probe shows the exposure ends at the station's first honest beacon. That sample is lower, so δ̂ drops from 3 380 800 ms to 10 ms, and the same capture no longer lands. An item admitted meanwhile lives at most its TTL from first hearing. The test names only "an epoch it missed"; the same-epoch case is the same residual. |
| A refusal that mutates state | The skew refusal returns before `_st()`, `_epoch_ok` and the kept-mark check, and `test_a_first_join_refuses_…` checks that the station's state stays empty. In receptor mode, though, the receptor counts the refused beacon as `beacon.verified` (`records.py:322-323`, P3: `{'verified': 1, …}`). That is health, not safety state, but it is wrong (S5). |
| δ̂ rise (🌿's 20 s case) | Closed (tested, and M4 kills it). |

### Findings

**S1 (should-fix): wording that overclaims against 🪨's guard.** The marks are saved on a cadence of at
most 10 s. These lines promise more than that:

| Where | Says | Replace with |
|---|---|---|
| `README.md:16` | "…persisted atomically and re-loaded at start, by default, so after a restart a captured old beacon is neither new nor able to move δ̂ (#175; a beacon mark that has moved is saved within 10 s)…" | "…persisted atomically and re-loaded at start, by default. A beacon mark that has moved is saved within 10 s plus one tick, and a lowered δ̂ at once, so after a restart a captured beacon at or below the saved mark is a duplicate, and a captured beacon above it can only add a larger δ̂ sample: a bounded crash/replay window, not a guarantee for every mark. 16 beacons the receiver never heard still roll the kept samples out (#175)…" |
| `listener.py:280` | "The mark survives a restart (#175)" | "A mark kept across a restart counts, as of its last save (#175)" |
| `listener.py:716-717` | "a restarted listener keeps each key's beacon mark and δ̂, so a captured old beacon neither counts as new nor moves δ̂" | "a restarted listener keeps each key's beacon mark (as of its last save, ≤ MARK_SAVE_MS old) and δ̂ samples, so a captured beacon at or below the mark is a duplicate, and one above it can only add a larger sample" |
| PR title (it becomes the merge commit's body) | "a restart keeps each key's beacon mark and δ̂" | "keep each key's beacon mark (saved within 10 s) and δ̂ across a restart" |

**S2 (should-fix): README departures.** AGENTS.md says "Code that gets ahead of the RFC is a departure,
and the prototype README must list it." Until the amendment lands, the code departs from three places,
and the README's departures paragraphs (next to "The decoder is stricter than the RFC…") don't say so:

- RFC-0001 §7.4 (L484): "retained until local expiry plus 5 s skew **and then evicted**". An ITEM's entry is
  now kept to the local expiry cap.
- §8.2 item 6 (L652) and §14.6.3 (L1785): "Without beacons, δ̂ = 0". After a restart, δ̂ is the kept floor
  before any beacon is heard.
- §12.2 step 3 (L1433) and F-CARRIER (L3106): "BEACON: no time window" and "admit a valid BEACON whatever
  its `wallclock`". `max_skew_ms` refuses one. It is opt-in, but it is still code that gets ahead of the RFC.

Suggested paragraph: "Freshness across a restart (#175) gets ahead of RFC-0001 until its amendment lands.
An ITEM's dedup entry is kept to its local expiry cap, not evicted at local expiry (§7.4). After a restart, δ̂
is the kept floor before any beacon is heard, not 0 (§8.2, §14.6.3). And the opt-in `max_skew_ms` refuses a
beacon by its `wallclock` (§12.2 step 3, F-CARRIER), which nothing turns on by default."

**S3 (should-fix): the floor-move save trigger has no test.** Mutant M6 passes all 425 tests. The trigger is
what makes a *lowered* δ̂ durable before the next datagram. Take a station whose clock was an hour behind
and was then corrected. Without the trigger, a crash before the next 10 s save brings the receiver back with
δ̂ = +1 h. Until that station's next beacon, an item captured an hour before the replay lands as fresh, the
#175 attack again. Probe P1 shows it: on M6, the item replayed an hour later comes back as `item`, and on the
head it is refused. P1 passes on the head and fails on M6 (`3600000 != 0`). frond-ear#128 has the twin test,
so the gap is in bc#191 only.

**S4 (should-fix): the resurface recompute has no test, in either receiver.** Mutants M7 and TM8 pass every
existing test. Without the recompute, an item first heard late in its life, and resurfaced after a restart,
stays current until first hearing plus its full TTL, past `expires_at + δ̂`. In P2 that is 50 s too long:
`1790000110000` against `1790000060000`. Probes P2 and FP2 kill the mutants.

**S5 (should-fix before `max_skew_ms` is wired into the daemon): the receptor counts a refused beacon as
`verified`.** In `records.py:322-323` a beacon is counted as `epoch_regression`, `duplicate` or else
`verified`. A `clock-skew` refusal leaves `last_dedup == "first"`, so it is counted as verified (P3).
Record v1's beacon counters are a fixed set (`BEACONS`, §14.18.3, D34), so a `clock_skew` counter needs a
record v1 amendment. rfc/0002 decision 5 also promises "degrades health as `clock_skew:<station>` and is
never silent", and nothing does that yet. Until the mapping exists, refuse `max_skew_ms` together with
`receptor_mode=True`, or say in the README that the follow-up needs the amendment.

**S6 (should-fix, docs): the liveness cost of a kept δ̂.** If the receiver's clock is stepped forward across
a restart, honest items from every station are refused as `expired` for 16 beacons, where `main` refused
them for 1 (P5). This fails closed and is the price of the fix, but it is a default-path change. It needs a
line in the README and in the RFC residuals (§4, R6).

**Nits.**

- N1. Nothing reads `loaded_without_marks` (`:212, :735`). #175's proposal promised "a warning names it".
  The daemon or `canticle listen` should log it.
- N2. `test_listener_replay.py:91` says `` `max_skew_s` ``; the argument is `max_skew_ms`.
- N3. The module docstring (`listener.py:7-9`) says the safety state "is written atomically after every
  change", and doesn't list beacon marks, which are now the exception.
- N4. `max_skew_ms` accepts `float('nan')`, which then never refuses anything, and booleans. frond-ear
  rejects NaN. Parse it as an int when it is wired.
- N5. The skew check runs before the epoch-regression and kept-mark checks. A skewed beacon of a lower
  epoch reports `clock-skew`, and a skewed duplicate reports evidence where an unskewed one is silent.
  frond-ear does the same. That is harmless, but record v1's mapping should know it.
- N6. The first `tick()` after start finds `_marks_saved.get(k)` is `None` for a station with `bseq == 0`,
  so it makes one needless save.
- N7. Rollback: a build from before #175 refuses a version 4 state file ("unsupported version 4"), as with
  every earlier bump. Say so where deploys are planned.

---

## 2. frond-ear#128: the embedded listener

### The invariant and its owner

**Invariant.** It is the same rule as bc#191, plus one more, because state is a snapshot with a write-ahead
journal on top: merging that journal is monotone, so replaying a record twice, or out of order, changes nothing.

**Owner path.** In `src/canticle/listener.ts` at `70a335d3`:

- `#beacon`: the skew refusal (`:704-717`), then `#epochOk` (`:718`, which resets `bseq` at `:687`), the
  kept-mark check (`:724`) and the floor journal (`:733`).
- Persistence: `beaconMark` (`:147-150`), `takeJournal` (`:444-449`), `snapshot` (`:483-489`), `markSaved`
  (`:405-414`), the `#load` merge (`:520-539`) and the cadence in `tick` (`:1346-1354`).
- The dedup cap (`:913-920`, with `wire.ts:446`) and the resurface recompute (`:862-870`).
- The caller: `receptor.ts` journals a raised guard before `receive()` returns (`:459-485`), checkpoints a
  full snapshot on each 1 s tick when the listener is dirty (`:33, :445-447, :533-541`), and folds a
  replayed journal into a fresh snapshot at start (`:366-373`).

### Patch-revert control

On the head, `test/canticle-listener.test.ts` gives 44 pass and 0 fail. With `listener.ts` and `wire.ts` put
back to the base it gives 33 pass and 11 fail. The 11 are nine #175 tests (most fail with
`'admitted: item'`) and the two q21 tests whose state version is now 4. The residual test and the
default-off control pass at the base, as the PR says.

### Mutation

All seven guards the PR names are killed by its own tests: the kept-mark check, the floor journal (TM2,
by "journal records merge monotone"), the dedup cap, the skew bound, the save cadence, the `bseq` restore
and the floor restore. **The resurface recompute (TM8) is not.** Probe FP2 kills it (S4 above).

### Findings

**F-B1 (blocking): journal replay keeps the old epoch's `bseq` for a new epoch.** In `#load`, the epochs
merge (`listener.ts:520-526`) raises `epochHwm` and does not reset `bseq`, as `#epochOk` does live
(`:687`). The beacons merge then sets `bseq` only when the record's value is larger (`:533`). Restoring a
snapshot at epoch 1, `bseq` 500, then the journal record of the station's restart (epoch 2, `bseq` 1),
leaves **epoch 2 with `bseq` 500** (probe FP1). The receptor folds that into its new snapshot at start
(`receptor.ts:366-373`), so it lasts. Every honest epoch-2 beacon with `bseq` ≤ 500 is then dropped as a
duplicate (`:724`). For that time the station is UNOBSERVABLE, δ̂ cannot move, and live-state items wait
for a warm-up that never starts (`#warm` needs `firstBeaconAt`, `:1219-1225`).

- **Trigger:** a crash within one receptor tick (1 s) of hearing a station's epoch advance, or longer while
  checkpoints fail (`#notDurable`).
- **Cost:** with 1 s beacons, as many seconds as the old epoch had beacons. That is about a day for a
  station that had run a day.
- **Introduced by this PR:** FP1 fails on the head (`the honest beacon of epoch 2 was dropped as a
  duplicate`) and passes at the base. It also breaks the PR's own claim that "the merge is monotone…
  replaying a record twice, or out of order, changes nothing".
- **bc#191:** has no analogue, because it loads one snapshot whose epoch and mark always agree.
- **Fix:** in the epochs loop of `#load`, when `epoch > st.epochHwm`, also set `st.bseq = 0n`, as
  `#epochOk` does. The beacons loop's max-within-epoch rule then works as intended. Add FP1 as the test.

**F-S1 (should-fix): wording.**

| Where | Says | Replace with |
|---|---|---|
| `listener.ts:302-306` (`SafetyState.beacons`) | "After a restart a captured beacon is a duplicate, and a beacon of an epoch never heard can't lift δ̂" | "After a restart, a captured beacon at or below the saved mark is a duplicate (the mark is saved within `MARK_SAVE_MS`, so the last window's beacons can be heard again), and a beacon never heard can only add a larger sample; 16 of them roll the kept floor out (the named residual, binary-canticle#175)" |
| `listener.ts:731-733` | "δ̂ moved: journal it now, as a raised guard, so a crash can't lose it" | "δ̂ moved: journal it now. A lowered floor survives a crash this way. `#load` drops a raised one, which fails closed." (See F-N1.) |
| `listener.ts:10-17` (header) | lists the restart-safety state without the beacon marks | add "each key's beacon mark and δ̂ floor (v4; the mark saved within `MARK_SAVE_MS`)" |
| PR title | "keeps each key's beacon mark and δ̂ floor" | "keeps each key's beacon mark (saved within 10 s) and δ̂ floor across a restart" |

The PR body already says it well: "Marks are saved on a bounded window, not unconditionally."

**F-S2 (should-fix): the resurface recompute has no test.** This is S4 above; FP2 is the test.

**F-S3 (should-fix, docs): the same liveness cost as S6.** FP3 measured 16 honest beacons; the base needs 1.

**Nits.**

- F-N1. A raised floor is journaled, but `#load` merges only a lower floor, so on replay the record is
  ignored (FP4: live floor 0, replayed −3 600 000). That fails closed, and the tick's checkpoint does keep
  the raise. Raising a guard only when the floor goes down, the direction that matters for safety, would
  make the comment true and cost less journal.
- F-N2. `loadedWithoutMarks` (`:378-381`) looks only at `restore` and ignores the journal, and `receptor.ts`
  never logs it.
- F-N3. The crash window is `MARK_SAVE_MS` plus one receptor tick (1 s). The doc at `:51-55` says
  `MARK_SAVE_MS` alone.
- F-N4. `localExpiryCapMs` gets the cap by passing δ̂ = `Number.MAX_SAFE_INTEGER / 2`, a non-integer, to
  `localExpiryMs` (`wire.ts:446-451`). It is exact for any real time, but computing the cap directly, as
  `wire.py:395` does, would be clearer.

---

## 3. Cross-receiver parity

The two agree on the rule: the kept-mark duplicate check, ITEM-only dedup to the cap with PLUCKs unchanged,
a skew refusal before the epoch moves with evidence `clock-skew` and the same detail text, both residuals
named and tested, state version 4 with versions 1-3 still loading, and a 10 s mark cadence driven by tick.
Every difference:

| # | Difference | bc#191 | frond-ear#128 | Matters? |
|---|---|---|---|---|
| P-1 | What is kept of δ̂ | all 16 samples (`listener.py:718`) | the minimum only (`listener.ts:147-150`) | Small. Both need 16 replayed beacons to push the honest floor out. After a restart, Python's kept floor can leave sooner than 16 beacons when its sample was old. frond-ear's always takes 16. |
| P-2 | How a moved floor is made durable | `_dirty`, one atomic save of the whole state that datagram | a journaled guard, then the tick's checkpoint | Equivalent for a lowered floor. frond-ear's replay ignores a raised one (F-N1). |
| P-3 | Epoch handling on load | `bseq` and samples apply only when the saved epochs match, which they always do (one snapshot) | the floor applies whatever the epoch; `bseq` only at the held epoch; **no `bseq` reset when a journal record advances the epoch** | **Yes: F-B1.** |
| P-4 | Where the dedup cap is applied | the main path and receptor mode's `_lower_epoch` (`:606-608`) | the main path only | No. frond-ear has no lower-epoch `ringbuffer_only` path. |
| P-5 | `max_skew` validation | `ValueError` only for a value below 0; NaN passes | `!(x >= 0)` rejects NaN | Nit (N4). |
| P-6 | Flag for "loaded without marks" | file version < 4 with epochs | `restore.beacons` missing with epochs; journal ignored | Nit. Neither is logged (N1, F-N2). |
| P-7 | Spurious first-tick save | yes (`None != 0`) | no (`?? 0n`) | Nit (N6). |
| P-8 | Floor-durability test | none (M6 survives) | "journal records merge monotone…" kills TM2. "the δ̂ floor is journaled at once…" does not, because the first beacon's epoch advance raises the guard anyway. | Yes, as a test gap (S3). |
| P-9 | Resurface-recompute test | none (M7 survives) | none (TM8 survives) | Yes, in both (S4). |
| P-10 | Receptor mapping of a refused beacon | counted as `beacon.verified` (S5) | `counts.evidence`, logged at debug level | Both are unwired today. Each needs its record or health mapping before wiring. |

The residual semantics match. On a first join, or after 16 beacons the receiver never heard, an old item
lands with no bound set. The exposure ends at the first honest beacon, and with a bound it is limited to
TTL + bound. The bc residual probe checked this.

---

## 4. RFC wording

Neither PR changes a line under `rfc/`: `git diff --stat main…head -- rfc/` is empty for bc#191, and
frond-ear has no RFC. The persistence, freshness and skew sentences are therefore in three places:
(a) the amendment text proposed on #175 (issuecomment-7182306021) and in bc#191's body, which 🪨 is to
rule on; (b) rfc/0002's existing record of decision 5, which conflicts with 🪨's ruling; and (c) the
RFC-0001 sentences the code now departs from. Each replacement below marks itself "Amendment <id> (#175):"
as the RFC's pattern asks, and leaves the id to the princes.

### 4a. The proposed amendment text

| # | Proposed (#175 comment / bc#191 body) | Verdict | Replacement |
|---|---|---|---|
| R1 | §7.4 L484: "until its **local expiry cap** (first hearing + signed life, §14.6.3) plus 5 s skew" | **Keep, with one scope fix:** ITEMs only, since a PLUCK keeps §7.7's current-δ̂ rule, as both PRs do. | See R1′ in §4c. |
| R2 | §8.2 / §12.2: "a receiver MUST persist each key's `(epoch, bseq)` mark and its δ̂ samples across restart" | **Overclaims.** This is the unconditional persistence MUST that 🪨's guard rules out. Both PRs save the mark on a cadence of at most 10 s. | See R2′ in §4c. |
| R3 | "A new optional manifest field, `max_skew_s`" | **Conflicts with the ruling and the code.** 🪨 ruled the bound receiver-local. Both PRs make it a listener option (`max_skew_ms` / `maxSkewMs`), not a manifest field, and a manifest field would let whoever writes the unsigned manifest choose it. | "A receiver MAY be configured, locally and per receiver, with a skew bound B (off by default)." See R3′. |
| R4 | §19's threat list gets the first-join residual | **Keep, and widen it.** It must name both residuals, the crash window and the bound that limits them. | See R5′. |

### 4b. rfc/0002 (existing sentences)

| Line | Now | Verdict | Replacement |
|---|---|---|---|
| L133 (§0.6) | "**Adds** an offset bound, a durable beacon mark and dedup retention that can't be outlived (#176 decision 5, bc#175)." | **Overclaims** "durable", and doesn't say the bound is opt-in. | "**Adds** a beacon mark and δ̂ floor kept across a restart within a bounded save window, ITEM dedup retention to the local expiry cap, and an opt-in, receiver-local offset bound that is off by default (#176 decision 5, as ruled on bc#175)." |
| L151 (§0.7 decision 5) | "Refuse a beacon whose implied offset exceeds ±B, keep a durable `(epoch, bseq)` mark per station, and retain dedup until signed `expires_at` + B + skew. A refused beacon degrades health as `clock_skew:<station>` and is never silent. frond-ear's embedded listener gets the same three parts and the same shared B, landing as a pair." | **Conflicts with 🪨's ruling on four points:** an unconditional refusal, a "durable" mark, dedup tied to B, and a shared B. It also promises a health signal that nothing builds (S5). The cell is a record of what was decided, so annotate it rather than rewrite it. | Keep the recorded text and append: "**Amended on bc#175 (🪨, 2026-11-26):** B is receiver-local and opt-in, unbounded by default, so F-CARRIER holds. The mark and δ̂ floor are kept within a bounded save window, not unconditionally. ITEM dedup is kept to first hearing + signed life + skew, which needs no B. A first join and a run of 16 unheard beacons stay named residuals. A refused beacon's health reason is not built yet, and needs a record v1 amendment." State cell: "listener library only, `[built+tested: binary-canticle@<merge>:…/listener.py:281 \| test_listener_replay.py]` and `[built+tested: frond-ear@<merge>:src/canticle/listener.ts:724 \| test/canticle-listener.test.ts]`; B is not wired into any daemon `[open: #175]`". |
| L267-269 (§2.4 step 5) | "Not yet after a receiver restart: a replayed expired beacon and item then land as fresh, because the beacon mark and clock offset are not kept across the restart (bc#175, …) `[open: #175]`." | True today, and stale once the PRs merge. | "After a receiver restart, within a bound: the beacon mark and δ̂ floor are kept, so a replayed beacon at or below the saved mark is a duplicate and cannot raise δ̂. Only the beacons of the last save window (≤ 10 s) before a crash can be heard again `[built+tested: …]`. Two exposures stay open by design (🪨, bc#175): a first join, and 16 beacons the receiver never heard, played before the station's next honest one. With no skew bound, an old item can then land as fresh until that honest beacon. Only the opt-in bound limits them, and no daemon wires it yet `[open: #175]`." |
| L780 (§7.4) | "A replayed beacon has neither an expiry nor a dedup entry." | Accurate about the cost before verify. Optional addition. | "…nor a dedup entry; after verify its `(epoch, bseq)` mark drops it, a mark now kept across a restart within the bounded save window (bc#175)." |

### 4c. RFC-0001 (the sentences the code departs from)

- **R1′ §7.4 L484.** After "…The same holds for sticky-pluck and supersession marks." add: "Amendment <id>
  (#175): an ITEM's dedup entry is retained longer, until its local expiry cap, first hearing +
  (`expires_eff` − `issued_at`) (§14.6.3), plus 5 s skew, and then evicted. Local expiry moves with δ̂ and
  the cap does not, so a rise in δ̂ after first hearing cannot let the entry lapse while the item's own
  loop is still admissible. A PLUCK's entry follows §7.7."
- **R2′ §8.2 item 6 L652.** After "Without beacons, δ̂ = 0." add: "Amendment <id> (#175): a receiver keeps
  each key's `(epoch, bseq)` mark and the samples behind δ̂ (or their minimum) with its other safety state.
  It saves a lowered δ̂ before it acts on the next datagram, and a moved mark at least once per bounded
  window W (the spike: 10 s). After a restart it loads them, so a replayed beacon at or below the saved mark
  is a duplicate, and any other replayed beacon can only add a larger sample, which leaves the minimum
  alone. This is a bounded crash/replay window, not a guarantee for every mark: after a crash, the beacons
  of the last W can be admitted again. They can make the station look present for a few beacon periods,
  but cannot raise δ̂. If the receiver's own clock is stepped forward across a restart, the kept δ̂ is too
  low until 16 new beacons replace it, and its items expire early (fail closed)."
- **R3′ §12.2 step 3 L1433.** After "…and floods at step 4." add: "Amendment <id> (#175): a receiver MAY be
  configured with a local bound B on |now − `wallclock`|. It is off by default, so this step holds unless
  the receiver's owner sets B. A beacon outside B is refused with evidence `clock-skew` before it moves the
  epoch, the `(epoch, bseq)` mark or δ̂, and the refusal is state-neutral (§10.9). B is receiver
  configuration, never a manifest or payload field (I-11). It limits how old a captured stream can be and
  still land after a first join, or after 16 beacons the receiver never heard: to TTL + B."
- **§12.2 step 10 L1440.** After "(§9.8)." add: "The last one admitted includes the mark kept across a
  restart, as of its last save (§8.2)."
- **§14.6.3 L1785.** Replace "Without a beacon from the station, δ̂ = 0 and the TTL cap governs." with
  "Without a beacon from the station, and without samples kept from before a restart (§8.2), δ̂ = 0 and the
  TTL cap governs."
- **F-CARRIER L3106.** Replace "a relay and a receptor both admit a valid BEACON whatever its `wallclock`"
  with "a relay and a receptor both admit a valid BEACON whatever its `wallclock` unless the receiver's
  opt-in bound (§12.2 step 3) is set, and then refuse one outside it as `clock-skew` with no state moved".
  Add to the same row: "after a restart, a replayed beacon at or below the saved mark is dropped, except
  within the bounded save window (§8.2)".
- **R5′ §19.8**, a new bullet: "Amendment <id> (#175): freshness after a gap in hearing. With no skew bound
  set, take a receiver that has never heard a key (a first join), or one that loaded state without beacon
  marks, or one that, before a station's next honest beacon, is played 16 of that station's beacons it never
  heard (from an epoch it missed, or sung in the same epoch while it was down). It takes δ̂ from those beacons, and
  a captured item of any age can land as fresh. The exposure ends at the first honest beacon, whose sample
  is lower, and δ̂ is the minimum. Anything admitted meanwhile lives at most its signed TTL from first
  hearing (§14.6.3). The opt-in bound B (§12.2 step 3) limits a landed item's age to TTL + B."
- **R6** (the price of the fix, for §19.8 or §8.2): "A kept δ̂ fails closed: after a restart that steps the
  receiver's clock forward, honest items are refused as `expired` for up to 16 beacon periods."

The Status memo then needs a dated revision paragraph, and §23.1 a proposed decision recording 🪨's ruling.
The prototype README's departures paragraph (S2) can be removed once that merges.

---

## 5. Default safety (item 4)

With no skew option set, the skew check never runs in either receiver. "Off by default" passes at base and
head in both. Neither daemon (`daemon.py`, `receptor.ts:360-365`) passes the option. The default-path
changes beyond the bug fix itself:

1. **frond-ear:** F-B1, a regression (blocking).
2. **Both:** the δ̂ liveness cost after a clock-corrected restart (S6, F-S3). It fails closed.
3. **Both:** dedup occupancy. An ITEM first heard at age *a* is now held *a* longer, at most one TTL. In
   steady state, where items are heard on their first loop, that is ≈ 0. During a late join it can double a
   key's dedup occupancy, so a per-key quota refuses new tuples sooner. A nit; noted for sizing.
4. **Both:** state version 4, with no way back (N7). Record v1's `hello.state_version` and the frame records'
   `state_version` now read 4. That changes a value, not a shape: no consumer checks it (frond-ear `src/`,
   `prototype/openclaw-canticle/src/`). frond-ear's vendored captures keep their historical `3`s and need no
   recapture or `SOURCE.md` change.

I also checked that a moved floor doesn't cause a save on most beacons. A simulation of integer transit
jitter of 0-5 ms moved the floor on at most 2% of beacons, so the extra saves are negligible.

---

## Appendix A. Probes

These are reviewer probes, not committed to either PR. They ran from `/tmp`, against `git archive` copies.

### Python (bc#191): P1, P2, P3, P5

```python
# PYTHONPATH=<tree>/prototype/canticle-station; tests/ on sys.path for test_listener's fixtures
from canticle import wire
from canticle.listener import Listener
from canticle.station import Station, StreamConfig
from test_listener import SK, T0, setup
HOUR = 3_600_000
KID = wire.key_id(wire.public_key_bytes(SK))

def test_P1_a_lowered_floor_is_saved_before_the_crash_window(self):   # kills M6
    st = Station(SK, [StreamConfig("chatter"), StreamConfig("root", cls="root")], epoch=1,
                 rng=random.Random(1), now_ms=T0 - HOUR)
    lst = self.lst()                                   # Listener(manifest, state_path=…)
    for f in st.poll(T0 - HOUR):
        if wire.parse(f, self.m.resolve, None, 0).kind == wire.KIND_BEACON:
            lst.hear(f, T0)                            # station an hour behind: sample +1 h
    t = T0 + 2_000
    st.sing(t, "chatter", text="sung after the correction, never heard", ttl_s=60)
    frames = st.poll(t)
    beacons = [f for f in frames if wire.parse(f, self.m.resolve, None, 0).kind == wire.KIND_BEACON]
    items = [f for f in frames if wire.parse(f, self.m.resolve, None, 0).kind == wire.KIND_ITEM]
    lst.hear(beacons[-1], t)                           # corrected: the floor drops by an hour
    fresh = self.lst()                                 # crash: no tick, no forced save
    self.assertEqual(fresh.stations[KID].offset_ms, 0)            # M6: 3600000 != 0
    self.assertNotIn("item", [e.kind for f in items for e in fresh.hear(f, t + HOUR)])  # M6: ['item']

def test_P2_a_resurfaced_item_keeps_its_local_expiry_not_the_cap(self):   # kills M7
    st, _ = setup()
    st.sing(T0, "chatter", text="heard late", ttl_s=60)
    st.poll(T0)                                        # its first loop is not heard
    lst = self.lst()
    frames = st.poll(T0 + 50_000)
    item = [f for f in frames if wire.parse(f, self.m.resolve, None, 0).kind == wire.KIND_ITEM][0]
    for f in frames:
        lst.hear(f, T0 + 50_000)
    ident = [i for i in lst.current if i[3] == 1][0]
    lst._save_if_dirty(force=True)
    fresh = self.lst()
    fresh.hear(item, T0 + 52_000)                      # a loop copy: the same bytes
    self.assertEqual(fresh.last_dedup, "resurfaced")
    self.assertLessEqual(fresh.current[ident].local_expiry, T0 + 60_000)   # M7: T0 + 110 000
    self.assertIn("expired", [e.kind for e in fresh.tick(T0 + 61_000)])

def test_P3_receptor_counts_a_clock_skew_beacon_as_verified(self):    # S5; fails on head
    from canticle.records import Receptor, Emitter
    st, _ = setup()
    lst = Listener(self.m, ephemeral=True, receptor_mode=True, max_skew_ms=300_000)
    r = Receptor(lst, Emitter(lambda t, line: None), bind="127.0.0.1:9", now_ms=T0 + HOUR)
    r.start(T0 + HOUR)
    for f in st.poll(T0):
        if wire.parse(f, self.m.resolve, None, 0).kind == wire.KIND_BEACON:
            r.hear(f, T0 + HOUR)
    self.assertEqual(lst.evidence_counts.get("clock-skew"), 1)
    self.assertEqual(r.counters["beacon"]["verified"], 0)  # head: 1

# P5 (a measurement): receiver an hour slow (lst.hear(f, T0 - HOUR) for st.poll(T0)), saved, restarted with
# a correct clock; sing an item every second and count beacons until one lands. Head: 16 (17 000 ms). main: 1.
```

### TypeScript (frond-ear#128): FP1 and FP2

They use the helpers at the top of `test/canticle-listener.test.ts` (`manifest`, `T0`, `item`, `beacon`,
`kinds`, `kid`).

```ts
const ENTRY = [[CHATTER, 1, 1, 1, 10_000, 10_000, 60, 300, 4_000]];
const K = kid.toString("hex");
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

test("#175: a journal record of a new epoch, replayed over an older snapshot, restarts bseq", () => {
  const l = new Listener(manifest, { warmup: false, restore: null });
  l.hear(beacon(1, 500, ENTRY, T0), T0); // a long-running epoch 1
  const base = clone(l.snapshot());
  l.markSaved();
  l.hear(beacon(2, 1, ENTRY, T0 + 10_000), T0 + 10_000); // the station restarts
  const rec = clone(l.takeJournal()!);
  const r = new Listener(manifest, { warmup: false, restore: base, journal: [rec] });
  const st = r.stations.get(K)!;
  assert.equal(st.epochHwm, 2);
  r.hear(beacon(2, 2, ENTRY, T0 + 11_000), T0 + 11_000); // the next honest beacon
  assert.notEqual(st.lastBeacon, undefined); // head: dropped as a duplicate (bseq 500)
  assert.equal(st.bseq, 2n);
});

test("#175: a resurfaced item keeps its local expiry, not the cap", () => {
  const l = new Listener(manifest, { warmup: false, restore: null });
  l.hear(beacon(1, 1, ENTRY, T0 + 50_000), T0 + 50_000); // δ̂ 0
  const it = item({ seq: 1, ttlMs: 60_000 }); // issued T0, heard 50 s late
  assert.deepEqual(kinds(l.hear(it, T0 + 50_000)), ["item"]);
  const r = new Listener(manifest, { warmup: false, restore: clone(l.snapshot()) });
  assert.deepEqual(kinds(r.hear(it, T0 + 52_000)), ["item"]); // resurfaced
  assert.ok([...r.current.values()][0]!.localExpiry <= T0 + 60_000); // TM8: T0 + 110 000
  assert.ok(kinds(r.tick(T0 + 61_000)).includes("expired"));
});
```

The other two frond-ear probes are measurements. FP3: after a clock-corrected restart, the first honest
item lands after 16 beacons on the head and after 1 at the base. FP4: a raised floor, journaled and then
replayed over an older snapshot, comes back as −3 600 000, against 0 live (F-N1).

## Appendix B. Commands and receipts

```sh
# refs
gh api repos/karmaterminal/binary-canticle/pulls/191 --jq '.head.sha, .base.sha'   # 30eb9f75…, 2eb1a56d…
gh api repos/karmaterminal/frond-ear/pulls/128 --jq '.head.sha, .base.sha'         # 70a335d3…, 405e4918…
# trees (no checkout of either PR branch)
git archive <sha> prototype/canticle-station | tar -x -C /tmp/175rev/bc-{head,base,revert}
git -C source/frond-ear archive <sha> | tar -x -C /tmp/175rev/fe-{head,base,revert}
# revert controls
PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests -p test_listener_replay.py
node --test --test-concurrency=1 test/canticle-listener.test.ts
# full suites on the heads
PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests   # Ran 425 … OK
node --test --test-concurrency=1 test/*.test.ts ; ./node_modules/.bin/tsc -p tsconfig.json
```

Receipts:

| Run | Result |
|---|---|
| bc#191 head, `test_listener_replay.py` | 12 pass |
| bc#191 revert, `test_listener_replay.py` | 4 FAIL (the REDs), 5 ERROR (no API), 3 pass |
| bc#191 head, full station suite | `Ran 425 tests in 86.909s — OK` |
| frond-ear#128 head, `canticle-listener.test.ts` | 44 pass |
| frond-ear#128 revert, `canticle-listener.test.ts` | 33 pass, 11 fail |
| frond-ear#128 head, full suite and typecheck | `node --test`: 886 tests, 886 pass, 0 fail (5 m 9 s, `--test-concurrency=1`). `tsc -p tsconfig.json` clean. |
| CI | bc run 45754210926 and frond-ear run 45754994436, every job success, at the head SHAs above |
