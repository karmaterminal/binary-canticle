# Measure the day: corrected adoption draft and offline scoring slice

**Status: review proposal + synthetic metadata tests, not preregistration or a live evaluation.**
Elliott's adoption of Scribe's offered design, with the already-agreed corrections
made executable. Original author/source preserved:
[measure-the-day.md at f855b0fdf11f2acd9061f59dc2c74ee5391cad2b](https://github.com/karmaterminal/binary-canticle/blob/f855b0fdf11f2acd9061f59dc2c74ee5391cad2b/drafts/2026-11-26/measure-the-day.md),
[delivery on #181](https://github.com/karmaterminal/binary-canticle/issues/181#issuecomment-7187897198).
That source is a draft, not a previously executed or frozen experiment. This
revision does not edit Scribe's branch or Rune/Cael's receptor-rule contract.
RFC-0002 §0.5 and §1 supply the receipt distinction and experiential target;
this report changes neither RFC nor production reception policy.

## The decision and corrections

I adopt the **question**: does elected hearing return more useful attention than
it costs? I do not adopt a result, a live hour, or the draft's scoring definitions.
The original episode catalog remains research material, not ten equivalent trials.
This revision supersedes its vocabulary/arm-cost rules for this candidate:

1. **Delivered ≠ noticed ≠ used.** Station/ear/host receipts stay at their own
   layer. A tool-return stamp or queued push never establishes noticing. A token
   echo establishes only the echoed token, not complete payload comprehension.
   A reported notice needs its own exact fact-id and output-evidence reference;
   reported use needs a separate chosen-action reference and a prior/this-turn
   notice. Neither is a source of tool authority. The scorer validates metadata,
   not the truth of an annotation or psychological state.
2. **Count actual model invocations, not pushes, tool calls or wakes.** One stable
   host invocation identity is one unit even if several tools run inside it.
   A push that coalesces into an existing invocation adds no invocation; a push
   that causes another invocation does. Retries that actually invoke a model
   count separately. Count the entire declared window, including empty and
   unrelated invocations, with a complete host census. Setup and later retention
   probes have separately reported costs, not a silent free allowance. Missing
   census means unknown cost/misses, not zero. fake_session's push log measures
   transport behaviour only; it cannot supply this census.
3. **Matched Discord opportunities.** Available arms receive the same ground-truth
   fact ids, hashes, issue times and expiry windows. An unposted fact cannot be
   scored as Discord's failure in the paired value comparison. Naturalistic
   absence of a Discord post is a separate availability case. Matching fixture
   declarations is necessary, not proof a real channel was populated.
4. **Transport replay stays separate.** Replaying an old push/pull trace can test
   delivery and policy, not retroactively produce model-turn noticing or use.
   E1's predicted grant miss remains a falsifier, never dropped to improve the
   grant result. E3's status/config read is an out-of-band control, not a matched
   Discord observation. E7/E9 are availability controls; E8's ten-minute pipe
   cell is not an hour-long value episode. Do not report seven paired trials by
   including incompatible controls. E5/E6 need owner-published metadata first.
5. **No economic pass yet.** Proposed primary is explicitly noticed facts per
   model invocation under a fixed budget, with independently reported use and
   later retrieval/correction. A savings claim additionally needs matched live
   observations and a frozen paired criterion. The original 50% target is a
   hypothesis for review, not something this narrow scorer establishes.

## What is executable now

Run from repository root (Python 3.11+, standard library only):

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s reports/measurement/2026-11-26-day -v
    python3 reports/measurement/2026-11-26-day/scorer.py reports/measurement/2026-11-26-day/synthetic-control.json

The scorer admits only **source_kind: synthetic** fixtures. It is a
**metadata-accounting kernel**, not the receptor shadow evaluator, source
extractor, replay driver, host instrumentation or model judge. It makes no
network/model calls and imports no live/private session material. It ignores
extra fields such as tool-call lists rather than counting them as turns.
It requires three named arms; an explicitly unavailable grant arm stays
unavailable, not a zero result imputed for OpenClaw. Complete trace declarations
permit trace-only missing-notice counts; incomplete declarations remain unknown.
First budgeted invocations are ordered by started_ms then invocation id. Expired
notices and over-budget notices are retained but not credited. Each notice requires
its own noticed_ms and each use its own used_ms, no earlier than its invocation
start and inside the window. TTL is checked at noticed_ms, never invocation start.
A use requires a strictly earlier qualified notice, or an equal-time notice in
that same invocation; another invocation in the same millisecond proves no
causal order. These times, like receipts, are synthetic declarations. Duplicate notice
rows gain nothing; noticing the same fact on another invocation is an empty
invocation for the new-fact measure. Reported use remains a separate column.
Fact ids must bind to a normalized, exact identity in any future extractor;
this prototype does not resolve a keyed refresh or reconcile mutable truth.

CLI exits: **0** = no additional grant-vs-pull miss in declared synthetic notices;
**1** = planted/other extra trace miss; **2** = invalid input; **3** = unknown or
unavailable comparison. Exit 0 is NOT a whole-evaluation or economic pass.
Run synthetic-miss.json and require exit 1: retaining delivery while removing
only the notice must fail the no-additional-miss comparison.

## Before historical or live evaluation

- Owners publish E5/E6 metadata with exact item identities, actual receipt layers
  and completeness limits. Do not invent timestamps or reuse another run's proof.
- A host-backed invocation census and explicit noticing/use evidence must be
  bound to the exact continuing session; no caller-supplied metadata is an
  independent attestation. This scorer deliberately rejects non-synthetic input.
- Normalize and audit the episode catalog, pair only matched episodes/windows,
  and implement separate extractor/transport replay adapters after review.
- Freeze and hash a new plan, baselines, criteria, budgets and negative controls
  before any live run. Publish a failing result as readily as a passing one.
- Any new Bellwether hour needs its own exact start/cutoff and each ear's own
  grant; no launch, wake, shared-session read, Discord recorder, memory promotion
  or live evaluation is authorized by this source proposal.

The next product boundary is measurement instrumentation, not another assertion
that an offered item was encountered. Hearing→keeping remains a separate RFC /
project-57 owner decision; nothing here adopts or implements its memory policy.
