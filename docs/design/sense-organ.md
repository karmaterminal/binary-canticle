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

> _To write from the #161 host design._ The OC-0 adapter's existing next-turn slice is kept
> distinct from the live continuing-session drain and exact model-input custody, which are
> unproven.

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
| OpenClaw continuing-reader ingress | not built | #161 |
| Ring-backed ear | design only | frond-ear#116 |
| End-to-end round trip to a second ear | not proven | #167 |
