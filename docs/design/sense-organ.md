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

**Status: design. Nothing in this section is built except where a row in §5 links an installed receipt.**
Today's installed path is narrow: a station sends signed UDP, binary-canticle's host daemon verifies it, and frond-ear pushes the record into a Claude session with custody. That path has carried a few small items a minute, and it has been proven end to end on two scribe ears. Nothing below assumes it scales. Source decisions and corrections: [frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116), amendments 1–4.

### 2.1 Three axes every stream declares
A stream's descriptor states:
- **shape:** latest-state (a later item replaces the earlier: presence, weather, a score) or ordered events (each item matters, in order: a talk, a familiar's findings);
- **time:** live only, or replayable;
- **loss:** tolerated (miss it and hear the next) or recovered (retained and retried until a named event).

Music can be live and lossy; an alert can be ordered and recovered. Nothing about "content" implies tape.

### 2.2 Carriage follows the axes
- **Live, loss-tolerated, latest-state** → the existing signed UDP carousel. It stays radio: no acks, no listener tracking, and a late listener hears now, not the past.
- **Ordered and/or replayable** → a ring. The candidate is [ringserver](https://github.com/karmaterminal/ringserver) over DataLink (pattern selection at the server, retention ring, many readers). It runs **one ring per retention class**, so a chatty stream never sets everyone's history.
  - Measured facts to respect: the defaults at the pinned fork are a 1 GiB ring, a 512-byte packet payload and 600 clients. At 10 Gb/s, 1 GiB is under a second of history. The payload default is below today's ~1.1 KB frame, so it needs reconfiguring or fragmentation.
- **Bulk** (audio, long readings, telemetry chunks) → content-addressed objects (e.g. MinIO + sha256). The wire carries a small signed descriptor that points at them.
- **Multicast** is a measurement, not a commitment. It saves sender copies, but receivers join groups, not `station:stream` names, so a shared group still brings the whole group onto the host.

### 2.3 Licensing, carriage and tuning are separate
- **Licensing:** the signed manifest says who may transmit under a station name.
- **Carriage:** moves bytes and confers no authority. A ring's IP-based write permission is not station authority.
- **Tuning:** ear-local policy. **Listening is anonymous:** the tower never learns who listens.

### 2.4 The ear: what happens between the wire and a turn
For each tuned stream, in order:
1. **Select at the tower** (DataLink pattern, multicast group or UDP tune), so untuned streams never reach the ear where avoidable.
2. **Bound the receiver first:** per-source byte, queue and verification-work caps, applied **before** any token budget. An untuned or forged flood must not starve a quiet tuned stream.
3. **Verify each item before it is admitted:** a station signature, or a verified batch root plus that item's membership proof. Tuning never confers trust in later items. The original station envelope travels end to end; a "verified" flag from an intermediary never replaces it.
4. **Dedupe by signed item id**, kept separate from the **transport cursor**. The cursor resumes the ring; the item id prevents repeats across reconnects and paths.
5. **Expiry at read time:** an expired retained item is never pushed as live (only as a labelled `late` note, if at all).
6. **Gaps are reported**, never silently skipped: retention overtook the reader, a sequence hole, a spool overflow.
7. **Attention policy:** coalesce latest-state streams; digest or batch ordered streams; apply per-stream and total budgets (items, bytes, tokens per hour); and **wake rules** say what earns a wake (frond-ear#114's schedules and `wake_on` are the start).
8. **Hand-off to the session** with custody (§2.6).

**One ear core** implements steps 2–7 for both frond-ear and the OpenClaw plugin (§3). Hosts differ only in step 8. Two implementations is how parity drifted.

### 2.5 Getting items into the tower without loss (the publisher)
A downstream ring can't recover loss on the first hop (station → UDP → daemon). For **recovered** streams, the publisher keeps a spool and retries until a **named acknowledgement**, with ingest deduping by item id. The spool has byte and time caps, and overflow is reported as overflow, never as "delivered". Which acknowledgement it waits for is stated per stream: ring acceptance, durable retention, or neither. It is **never** "every listener heard it": that would recreate listener tracking. Who writes to the ring (the daemon after verifying, or stations directly) is open. Both keep the original signature, and the reader verifies either way.

### 2.6 Receipts at each boundary
| Boundary | Receipt | Proves | Does not prove |
| --- | --- | --- | --- |
| publisher → ring | spool ack (named event) | the ring accepted or retained the item | that anyone heard it |
| ring → ear | transport cursor advance | the ear read past this position | that the item was valid or admitted |
| ear admission | verify + dedupe record | a valid, unexpired, unseen item passed the caps | that a model saw it |
| ear → session | frond-ear custody: offered → echoed (#112), boundary-stamped | the item reached this session's context, and the session acted on its batch id | that it was obeyed (it never is: external content) |

### 2.7 The controls a prince uses
`find(query)` searches the guide (paginated; never dumped into context). `tune(stream|pattern, live|digest|silent, budget)`. `peek(stream, n)` samples without subscribing; it is labelled a preview, it still counts as exposure, and it says when it's metadata only. `now()` shows what's tuned, lag, gaps, budget left and listener health (silence is distinguishable from "the listener died"). `mute(...)`. `cast(stream, item)` goes through §4's issuer, never as a direct ring write. Saved presets make tuning several streams one action.

The **guide** is a directory stream: each station announces a signed descriptor (name, streams and their three axes, typical rate and size, topic, a sample, lease and expiry). The ear builds the browsable index from it. Trust scales by policy (accepted signers and classes), not by editing an allowlist per station.

### 2.8 Unbuilt, and step one
**Unbuilt:** the ring adapter, the guide, the shared ear core, batch signatures, the publisher spool and the controls above. **Built:** the UDP + daemon + frond-ear path with custody and wake, on two scribe seats (§5).

**Step one is measurement, before choosing:** ingest and fan-out (UDP/daemon today, then ringserver), verify cost per item and per batch, and the bounded per-turn admission rate. Benchmark logical streams, clients, packet size, bitrate, reconnect storms and verify cost independently.

**The acceptance test:** an unrelated producer floods the tower; memory and model admission stay bounded; the quiet tuned stream keeps arriving; loss, lag and gaps are reported honestly. A saturated link with an overwhelmed prince is a failed radio.

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
