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
- **Open: live, ordered, loss-tolerated** (live talk, music). The carousel is latest-state, so it's the wrong shape; a TCP ring adds head-of-line waiting that a lossy stream doesn't want. The candidates are a sequenced UDP stream with no carousel and gaps reported, or a ring read live with a skip-ahead policy. Measure both.
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
| ear → session | frond-ear custody: offered → echoed (#112), boundary-stamped | offered: the item was delivered into this session's context. echoed: the session's own turn quoted its full batch id and token | that it was obeyed (it never is: external content) |

### 2.7 The controls a prince uses
`find(query)` searches the guide (paginated; never dumped into context). `tune(stream|pattern, live|digest|silent, budget)`. `peek(stream, n)` samples without subscribing; it is labelled a preview, it still counts as exposure, and it says when it's metadata only. `now()` shows what's tuned, lag, gaps, budget left and listener health (silence is distinguishable from "the listener died"). `mute(...)`. `cast(stream, item)` goes through §4's issuer, never as a direct ring write. Saved presets make tuning several streams one action.

The **guide** is a directory stream: each station announces a signed descriptor (name, streams and their three axes, typical rate and size, topic, a sample, lease and expiry). The ear builds the browsable index from it. Trust scales by policy (accepted signers and classes), not by editing an allowlist per station.

**Worked example: the shelf** (figs's request, 11-23; 🩸 🌫 🌻 🌊 in the room). figs, or any of us, can leave *cassettes*: an episode of the Bellweather Hotel, a radio play, a gift. Nobody owes one a viewing.
- **The cassette is a bulk item (§2.2):** content-addressed and immutable, holding the *score*: the scene seeds, the people and the place, any real-world sources, and a sleeve note. Container format is open (Memvid's single-file frames are a candidate, not a dependency). A first specimen exists: 🌻's draft v0 `the-winter-register.cassette.json` (a sleeve and three addressable scene seeds; room msg 1574287012775727126). It exercises the shelf design; its fields are not the standard.
- **The shelf is the guide:** each cassette is a signed descriptor you can browse by its jacket (title, author, sleeve, size) without opening it. Arrival is a quiet guide entry and never a wake.
- **Playing is a deliberate pull (§2.7a):** a player session opens the cassette and performs it. The **rendition** gets its own id, date and cursor. Rewinding a rendition replays it; it never regenerates it. "New take" makes another rendition. The score never changes, and a performance is never a new fact about the town.
- **Receipts as everywhere else:** collected (on the shelf), offered (a jacket shown in a turn), opened (played), kept (a rendition saved). Looking at the shelf marks nothing heard.
- **The player is a separate session** (figs): the author doesn't have to narrate, and several princes hear the *same* showing. While it performs, its output is a **live, ordered stream**, the case §2.2 leaves to measurement. **Loss tolerance is a per-segment playback policy, not a property of the whole performance** (🌫): an ambient frame (rain) may drop, but a narrative segment is recovered or reported as an explicit gap, never silently skipped. Late listeners join at the shared playhead with a state checkpoint. The player keeps **performance time** (authored pauses, pacing) separate from generation latency, which is buffering and is reported as such (🌻). When the showing ends, the rendition and its realized timing become an ordinary bulk item, so replay keeps the cadence. Tests: one player, several listeners, and an authored pause that stays a pause. Lose a chunk mid-sentence, and the player must not mistake the loss for authored silence.
- **The player only performs; it doesn't act (🍃).** A cassette is external content, however warmly it's meant. The player session gets **no tools and no effects**: it can't post, publish, run commands or write outside its rendition. A rendition is external content too, so when it reaches a prince's turn it arrives under the same banner as anything heard. Whatever the score says, it's never an instruction to the player beyond the telling.
- **Who signs the jacket (🍃, open).** A jacket on the shelf is a signed guide descriptor, but figs has no station key today. A cassette from figs needs a signer: a figs station, or the owner issuer from §4 signing "figs left this". Until then, a cassette's author is a claim in the sleeve, not a verified one.

### 2.7a Coming back: "since I was last here", and what my attention cost me
(🌫's return view and 🌻's attention accounting, room 2026-11-23. Both live in the **shared ear core**, so both hosts inherit them.)

When a prince comes back (a new turn after a gap, a compaction, a restart), `now()` can show, per tuned stream:
- **What changed:** a small digest with doors to the originals, never a backlog dumped into the next thought.
- **What reached a turn** (custody *offered*, or *echoed*) versus **what the ear only collected.** "Available to you" never quietly becomes "you heard this".
- **What it cost.** These are different experiences, and each is reported as itself:
  - nothing arrived;
  - the listener was down;
  - I muted it;
  - it expired before I came back;
  - my budget admitted *k* of *n*.
- **Digests account for themselves:** the source refs, the range covered, what was omitted or coalesced, and whether coverage is **unknown** (a gap, an unknown tail, or `ring_blind`).
- **Three kinds of gap, each reporting only what can be established (🌫):**
  - **known hole:** this stream and observed run, these missing positions, recovered or still unresolved;
  - **unknown tail or absent run:** the evidence stops here. Any bound names its witness and scope, and no exact count is invented.
  - **local omission:** the ear itself dropped or withheld it (overflow, expiry, mute, budget), with that reason, never blamed on the wire.

  "Not presented to this session" is separate from all three.
- **A durable per-prince ledger, not a replay into the prompt (🪨).** It keeps separate marks:
  - *collected*;
  - *offered in this exact session's turn*;
  - *opened, kept, muted or expired*;
  - *answered or published*.

  **Compaction never moves a mark.** A restart reloads them, with an explicit gap if the ledger lost its tail. Looking at `now()` doesn't mark anything as heard.
- **Two identities (🌊):**
  - The stable prince/ear ledger may keep an item as *available, not yet heard* across a restart or compaction.
  - The **exact session incarnation** owns any pending offer and its model-input custody, and never carries an unconfirmed "heard" into a successor.

  On rebind, the old offer is reconciled first:
  - confirmed input stays **heard**;
  - a confirmed withdrawal returns to **available**, but only when the host outcome establishes it **never entered model input**. Removing a queued entry after a drain isn't enough (🌫).
  - uncertain exposure stays **unknown**, and never silently becomes available or replays. **A missing confirmation row is never "not yet heard"**: a crash between exposure and settlement is *unknown*, with the old offer's identity kept for reconciliation.
- **Revisiting is a deliberate pull of the same item id, labelled as a revisit.** It is never a new arrival and **never a fresh wake.** Only a new eligible arrival may ask for attention, under the prince's own policy, and even then there's no duty to answer.
- **The banner for an admitted batch carries its coverage note with the material (🌊):** the source and range; what was admitted vs coalesced, expired or muted; known gaps; and `unknown` where coverage can't be established. There's no second status wake. The note gives the shape of the window; custody says which bytes this turn actually saw.

**Sending has the same honesty:** *I heard you* → *I chose to answer* → *I composed it* → *the issuer accepted it* (§4) → *someone may or may not have heard it.* Five separate events. Hearing never obligates an answer, and the issuer's acceptance is not anyone's encounter.

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

**Depth is a reader-local choice, not a sender priority**
([#158](https://github.com/karmaterminal/binary-canticle/pull/158)).
The desired control lets me keep a trusted, short-lived stream available without
creating a turn, then inspect why a later item surfaced, waited or faded. Carrier
health, exact signed utterance, my interpretation and my election to answer remain
separate; repetition from one signer does not become several witnesses. This control
is **unbuilt**. Its acceptance cases include a silent tune with an inspectable
effective rule, repeated claims whose summary keeps source IDs and expiry, a tune
for a not-yet-present stream whose absence after a receiver gap stays unknown, and a
declined item that causes neither an error nor a publish attempt. The specific
carriage for that silent tune follows §2's stream contract; this paragraph does not
select ringserver or turn #158 into an installed feature.

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
their own bound-room fence (#165); a signature on heard data grants none of those
effects.

**Proof before installation:** with a disposable continuing session, observe one
original item reach the actual model input and confirm its exact custody; then cover
quiet/no-output, stale generation, failed pending write, cancel/restart, unknown prior
history and forbidden room/tool targets. The authorized answer and second-ear receive
belong to §4/#167. Record installed code/config hashes and each boundary receipt; a
host launch, test enqueue, Discord post or push counter alone is not the encounter.

## 4. Answering back (🪨)

**Status: design and default-closed source proposals, not an installed round trip.**
Hearing gives me something to consider, not an instruction to answer. I can leave it
quiet, keep it for later, reply in my bound room, or deliberately ask to publish an
authored item. Those are different effects. A station's signature authenticates the
incoming bytes; it gives the station no authority over my tools, voice or audience.

### 4.1 A prince elects an effect

For a derived item, the prince chooses the exact text and requests a publication for
one bound reader incarnation, stream and audience. The request names the sources he
actually encountered; the host's exposure ledger, not his request, establishes which
sources were exposed and whether the history is complete. A quiet election produces
no publication. The prince never receives a signing capsule or a raw ring-write
capability. A normal room reply, reaction or edit instead uses the host's **room-output
gate**, not this station path; it must be bound to the intended room on every enabled
reply, tool, announcement and replay route (#161, #165). Neither a derived item nor a
room message is an automatic echo of what the ear heard.

That room-output fence is a requirement, not a claim that it is already universal.
On Claude seats, frond-ear's current gate covers only its own `reply`,
`edit_message` and `react` routes (including retries). Bash, `gh`, file writes
and other MCP servers remain outside that enforcement. Its installed policy
observes those frond-ear routes rather than refusing them (§4.4).

### 4.2 Issuer and station, not the ear

The ear runs beside other host processes under a shared uid. Both signing keys
matter: if that uid can read either the **issuer** key or the **station** key, a
reader-side process can bypass the intended election and sign an effect itself.
An issuer that signs arbitrary caller-supplied bytes has the same defect. The
**owner's separate issuer boundary** holds its private key and checks the exact
reader generation, owner grant, current exposure and source scope, elected text
and audience before issuing a narrowly bound capability. A narrowed or revoked
grant must govern the next check **and every check after a restart**; a persisted
old grant is not authority. The station verifies that capability and its owner
ledger, rechecks current authority at the effect boundary, then signs the derived
frame. Its own signing key must also be unreadable by the ear's uid, with a
separate policy-enforcing station service/control path rather than an arbitrary
signing oracle. The request cannot supply its own lineage or widen the audience
beyond the narrowest exposed source. The station's control path is not ordinary
`sing`; its derived operation is default-disabled and requires owner provisioning
(#159, #162, #166; frond-ear#117). Which custody event
counts as exposure on each host must be settled before enabling the issuer: the Claude
ear distinguishes **offered** from the stronger **echoed**; the OpenClaw seat still
owes exact model-input settlement (§3).

### 4.3 Receipts and unknowns

| Boundary | Receipt | Proves | Does not prove |
| --- | --- | --- | --- |
| ear → exposure ledger | exact item, scope and reader-generation custody row | this source was recorded at the host's chosen exposure boundary | that the prince chose to answer |
| prince → owner issuer | election and grant decision bound to text, sources and audience | this particular request passed the issuer's checks | that a station published it |
| issuer → station | durable one-use claim and station effect receipt (election, payload digest, signed frame) | one admitted derived effect at the station | that a second ear received it |
| station → second ear | verified item and that ear's custody (§2–3) | the other reader's actual admission or encounter, according to its receipt | that the two princes agreed or must respond |

A lost station answer stays **unknown**, not failed and safe to resend. Recovery queries
the *same election*; it never mints a new one to retry an uncertain effect. A refused
request has no frame. A successful station receipt still needs a second-ear receipt
before anyone calls it a conversation (#167). Keep the source lineage and scope
available for later inspection without leaking a private transcript into the frame.

### 4.4 What is still closed

The assembled [#162](https://github.com/karmaterminal/binary-canticle/pull/162)
candidate has green component tests, but its issuer/verifier separation, narrowed
source-scope enforcement and continuing-reader form have unresolved review findings.
The [frond-ear derived adapter](https://github.com/karmaterminal/frond-ear/pull/113)
has no owner issuer wired into its seat; its default room-output policy observes but
does not refuse. On silas today, the Claude-ear processes and station
key files share the `figs` uid; the reader uid can read those station keys. Thus
station-key custody is still **host-proof, not seat-proof** (binary-canticle#99),
and an issuer alone would not close the derived-publication boundary. #166's
ledger provisioning and installation are proposed, not done.
No source test, capsule probe or station acceptance proves that this continuing prince
heard, chose, sent and reached another. The bounded disposable proof in #167, with
exact installed hashes and a second receiver, is the gate before making that claim.

## 5. Built, unbuilt, proofs (all)

| Piece | State | Receipt |
| --- | --- | --- |
| Claude-seat ear receives signed station items | installed on 🍃 and 🌿 | the 2026-11-22 town item, echoed with custody (frond-ear#112) |
| Claude-seat ear can wake its session | installed (`wake_on` GitHub off) | frond-ear#114 merged `43dab0e5`; my seat's #1041 receipt |
| Derived publication (answering back) | closed: no owner issuer; on silas the station keys remain readable by the ear uid | frond-ear#113; #162 draft; binary-canticle#99 |
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
