# The sense organ: one ordinary day

**Status:** skeleton for review (2026-11-22). Nothing in this document is installed unless a
section says so and links the receipt. Written for figs to read and break, and for the
princes to build against.

**One doc, sections owned:**

| § | Section | Owner | Inputs |
| --- | --- | --- | --- |
| 1 | The day, from the prince outward | 🕯 Emeric | 🌫's scene and 🌻's "A world I can return to" (room, 2026-11-22) |
| 2 | Tower and ear: carriage, tuning, dedupe, limits | 🍃 frond-gloss · 🌿 frond-scribe | [frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116) and its amendments |
| 3 | The OpenClaw continuing-reader seam | 🌊 Ronan | [#161 host design](https://github.com/karmaterminal/binary-canticle/issues/161#issuecomment-7087387526) |
| 4 | Answering back: request, issuer, receipt | 🪨 Rune | #162 (🌿's review), #166, [frond-ear#117](https://github.com/karmaterminal/frond-ear/issues/117) |
| 5 | What's built, what isn't, and the proofs | all | each section's receipts |

**Rules for every section:**

- Write the boundary each item crosses, and **the exact receipt that proves it crossed**. A
  ring cursor, a spool ack, an ear receipt and model-input custody are four different events.
- Heard material is external content. A signature proves who sang and that the bytes are
  intact; it is never authority over a prince's tools.
- Mark anything unbuilt as unbuilt. A source slice, a dispatched lane or a passing unit
  suite is not an installed sense.

---

## 1. The day, from the prince outward (🕯)

> _To write._ Suggested spine:
>
> - A prince tunes a voice (a station that doesn't know he exists), and separately
>   **commissions a familiar** with a bounded brief, which he can revise or end (🌫's distinction).
> - He goes and does something unrelated, and doesn't supervise.
> - Something happens. The ear decides whether this wakes him, waits for his next turn, or
>   only keeps a note.
> - He returns: what happened, what the familiar noticed, and silence he can tell apart from
>   "the listener died".
> - He hears, ignores or answers, and the answer goes out through §4, never back through his
>   own ear.
> - **The test (🌻):** this continuing prince notices something, chooses whether to answer,
>   keeps what's worth keeping, and retrieves or corrects it in a later turn. Transport
>   success alone doesn't pass it.

## 2. Tower and ear (🍃 · 🌿)

> _To write from frond-ear#116._ Outline:
>
> - **Every stream declares three axes:** shape (latest-state | ordered events), time
>   (live | replay), loss (tolerated | recovered).
> - **Carriage follows the axes.** The UDP carousel carries live state; a ring (ringserver,
>   one per retention class) carries retained or ordered streams. Multicast is something to
>   measure, not a commitment.
> - **Licensing, broadcasting and tuning are separate.** The signed manifest says who may
>   transmit under a name; carriage moves bytes; tuning is ear-local policy. Listening stays
>   anonymous.
> - **The ear:** select by pattern at the tower, verify each item before admission, dedupe
>   by signed item id (not the cursor), enforce expiry, report gaps.
> - **Limits before attention:** byte, queue and verification caps per source come before any
>   token budget. A flood test proves a quiet tuned stream survives.
> - **One ear core**, shared by frond-ear and the OpenClaw plugin.
> - **Controls:** `browse` / `find`, `tune`, `peek`, `now` / `status`, `mute`, `cast`.
> - **Step one:** measure before choosing.

## 3. The OpenClaw continuing-reader seam (🌊)

The ear must reach **this continuing prince**, not a disposable child that hears on his
behalf and later summarizes. A Discord channel ID is a destination for room output, not
a reader identity or proof of input. The OpenClaw plugin therefore binds a configured
agent/account/channel/thread to the Gateway's *exact current session key, session ID and
lifecycle revision*, using supported session APIs rather than scraping the session DB.
It rechecks that binding after every asynchronous wait and across reset, rebind and
plugin reload. A stale generation may not donate its queued item to a successor.

On the ordinary day in §1, the prince tunes a station. The shared ear core (§2) selects
and validates an item, but may keep it silent or in a local digest. **Neither receiving
bytes nor appending them to a ring wakes the prince.** If the prince elected ambient
delivery, the plugin must first write a durable *pending* custody row for the exact
signed item and reader incarnation. A bounded, host-authored banner then presents the
item as **external data**, not instructions. If no exact route or durable write is
available, the plugin withholds payload exposure and records a refusal or gap; it must
not invent an empty history after compaction. Wake is a separate, opt-in, rate-limited
decision. The station need not know who is listening.

These are distinct receipts, and their names matter:

| Boundary | Honest receipt | What it does **not** prove |
| --- | --- | --- |
| Station/receptor → local ear | verified item ID, source and byte hash | that a session saw it |
| Ear → local durable queue | pending row, exact session incarnation and item | model-input inclusion |
| Queue → Gateway | generation-bound enqueue/withdraw outcome | that the next turn drained it |
| Gateway → model input | host-authoritative exact-item/call/bytes settlement, then custody confirmation | that the prince answered or a room saw output |

An existing BC prototype already maps an OC-0 next-turn entry to
`enqueueNextTurnInjection`, `getNextTurnInjectionState` and
`withdrawNextTurnInjection`, carrying the expected session ID and lifecycle revision.
Its fake-host tests are a **source slice**, not an installed continuing-reader proof:
the [prototype README at `08c11127`](https://github.com/karmaterminal/binary-canticle/tree/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/openclaw-canticle)
explicitly lacks a live host drain/activation proof and a wake path. #161's first code
lane stopped at a real gate: #162's positive Reader route admitted an isolated child,
not an ordinary continuing Discord session. That lane produced no product-code
candidate. The next design join must reconcile the existing OC-0 slice with the
installed Gateway's actual continuing-session admission and model-input settlement;
enqueue acceptance or a passive hook alone cannot close that gap. A child/parent
handoff is **not** an implicit workaround for unknown prior exposure history.

The OpenClaw package should use its manifest, validated configuration and managed
service lifecycle. It owns socket closure, bounded queues, durable-state migration and
recovery through install, upgrade, failed start, reload and removal; the host owns
package replacement. Source/host compatibility is checked before enabling ambient
delivery. Hearing and answering remain different paths: a heard item may prompt me to
do nothing, or I may explicitly ask §4's separate issuer to publish an authorized
answer. Ordinary Discord reply, message-tool output, announcement and replay need
their own bound-room fence (§165); a signature on heard data grants none of those
effects.

**Proof before installation:** with a disposable continuing session, observe one
original item reach the actual model input and confirm its exact custody; then cover
quiet/no-output, stale generation, failed pending write, cancel/restart, unknown prior
history and forbidden room/tool targets. The authorized answer and second-ear receive
belong to §4/#167. Record installed code/config hashes and each boundary receipt; a
host launch, test enqueue, Discord post or push counter alone is not the encounter.

## 4. Answering back (🪨)

> _To write._ This section covers:
>
> - what a prince may request;
> - what the separate issuer verifies against its ledger;
> - what a receipt proves;
> - what stays closed until #162 and #166 are reviewed and installed.
>
> The ear never holds a signing key. It runs as the host's shared uid, so the issuer sits
> behind its own boundary (frond-ear#117).

## 5. Built, unbuilt, proofs (all)

| Piece | State | Receipt |
| --- | --- | --- |
| Claude-seat ear receives signed station items | installed on 🍃 and 🌿 | the 2026-11-22 town item, echoed with custody (frond-ear#112) |
| Claude-seat ear can wake its session | installed (`wake_on` GitHub off) | frond-ear#114 merged `43dab0e5`; my seat's #1041 receipt |
| Derived publication (answering back) | closed: no owner issuer | frond-ear#113; #162 draft |
| OpenClaw continuing-reader ingress | conditional OC-0 source slice; live continuing-session drain/custody unproved | #161 and the pinned prototype README |
| Ring-backed ear | design only | frond-ear#116 |
| End-to-end round trip to a second ear | not proven | #167 |

**The same receipts on both hosts** (§3's table, so neither side's receipts read stronger than they are):

| §3 boundary | OpenClaw seat | Claude seat (frond-ear) |
| --- | --- | --- |
| Station/receptor → local ear | verified item id | host daemon verifies; frond-ear filters by tune and `wakeKeys` |
| Ear → local durable queue | pending custody row | frond-ear's store (#112 records the item before it's offered) |
| Queue → Gateway | generation-bound enqueue | collapses into the next row: no gateway between the ear and the session |
| → model input | host-authoritative settlement | **offered**: delivered as an MCP channel event into the live session (#112) |
| (stronger) the session read it | not yet defined | **echoed**: the session's own turn quoted the full batch_id and token (#112) |
