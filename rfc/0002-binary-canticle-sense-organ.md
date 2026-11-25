# RFC-0002: Binary Canticle, the sense organ

| | |
|---|---|
| **Status** | Draft (2026-11-23). Not wire-stable, not installed. Shaped from `docs/design/sense-organ.md` at `2c3f5ab6` (draft PR #168), at figs's ask that the canticle work be anchored to an RFC. |
| **Location** | `rfc/0002-binary-canticle-sense-organ.md` |
| **Updates** | RFC-0001 (`rfc/0001-binary-canticle.md`). Section-level relations are in §0.6. Everything not listed there is **to be settled by the claims audit** (🌿's lane, Appendix B). |
| **Pointers checked at** | binary-canticle `d4c306618f7f77658fe73705d58b2744f2486701` (`main`, the merge of #171); frond-ear `a8e2e5ba1b16adf5ce700265f25a0d210c569608` (`main`, the merge of frond-ear#119). Other SHAs are named where they are used. |
| **Owners** | §1 🕯 Emeric. §2 and §3 🍃 frond-gloss and 🌿 frond-scribe (the tower and ear). §5 🌊 Ronan (the seam), and §3.5. §4 🪨 Rune (answering). §0, §6 and §7 all of us. |

**Nothing in this document is installed unless a pointer says so and links its receipt.** A source
slice, a dispatched lane, a passing unit suite or a merged pull request is not an installed sense. A
`built` tag says the code exists at that SHA. It does not say any seat runs it.

Written for figs to read and break, and for the princes to build against.

---

## 0. Scope, vocabulary and the receipt layers

### 0.1 Scope

This RFC specifies the **sense organ**: how a prince comes to encounter what a station sings, how he
attends to it and comes back to it, and how he may answer it. It is organized by the three capabilities
a prince gains, in the order they can be built:

1. **Receive-only encounter** (§2): carriage, tuning, verification at admission, fairness and honest
   loss. The prince can hear; nothing he hears can make him act.
2. **Selective, returning attention** (§3): coming back after a gap, the guide and the controls, and
   wakes. The prince chooses what he attends to, and can tell what he missed.
3. **Authorized answering** (§4): the issuer boundary and station-key custody. The prince can answer,
   through a path that does not run back through his own ear.

§5 is the cross-cutting host join for OpenClaw seats. §6 puts what is built, unbuilt and proven on one
set of rows for both hosts. §7 holds the open decisions.

RFC-0001 remains the specification of the wire (frame v2), stations, the carousel, trust, the host
daemon and receptor record v1. This RFC does not change any of those bytes.

### 0.2 Owners and inputs

| § | Section | Owner | Inputs |
| --- | --- | --- | --- |
| 1 | The day, from the prince outward | 🕯 Emeric | 🌫's scene and 🌻's "A world I can return to" (room, 2026-11-22) |
| 2, 3 | Tower and ear: carriage, tuning, dedupe, limits; attention and return | 🍃 frond-gloss · 🌿 frond-scribe (§3.5: 🌊 Ronan) | [frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116) and its amendments; 🌫's return view and 🌻's attention accounting (room, 2026-11-23); #158 |
| 4 | Answering back: request, issuer, receipt | 🪨 Rune | #162 (🌿's review), #166, [frond-ear#117](https://github.com/karmaterminal/frond-ear/issues/117) |
| 5 | The OpenClaw continuing-reader seam | 🌊 Ronan | [#161 host design](https://github.com/karmaterminal/binary-canticle/issues/161#issuecomment-7087387526) |
| 6 | What's built, what isn't, and the proofs | all | each section's receipts |
| 7 | Open decisions | all | each section's open items |

**Rules for every section:**

- Write the boundary each item crosses, and **the exact receipt that proves it crossed**. A ring cursor,
  a spool ack, an ear receipt and model-input custody are four different events.
- Heard material is external content. A signature proves who sang and that the bytes are intact; it is
  never authority over a prince's tools.
- Mark anything unbuilt as unbuilt. A source slice, a dispatched lane or a passing unit suite is not an
  installed sense.

### 0.3 Conventions and claim tags

<!-- claim-check: off -->
The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **RECOMMENDED**, **NOT RECOMMENDED**, **MAY** and **OPTIONAL** are to be interpreted as
described in BCP 14 [RFC 2119] [RFC 8174] when, and only when, they appear in all capitals.

Every normative statement, and every statement of how the system behaves, carries one status tag in
its paragraph, bullet or table row:

| Tag | Means |
|---|---|
| `[built+tested: <repo>@<sha>:<path>:<line> \| <test>]` | The code at that line does it, and the named test (or committed measurement cell) exercises it. |
| `[built: <repo>@<sha>:<path>:<line>]` | The code at that line does it. No test is named here. |
| `[proposed: <issue/PR>]` | Design that the named issue or pull request proposes. Not built. |
| `[open: <issue/PR or §n>]` | Not decided. |

<!-- claim-check: on -->

Repositories are named short: `binary-canticle` and `frond-ear` are `karmaterminal/` repositories. A
short SHA in a tag expands to the full SHA in the status table, or where it is first used. Every code
and test pointer was read at its exact SHA before it was written here (`git show <sha>:<path>`). A
test is named by its file and line, or as `Class.method`. Where a pointer could not be checked, the
claim is `proposed` or `open`. `rfc/tools/check-claim-tags.py` fails on a capitalized key word with no
tag in its unit.

### 0.4 Vocabulary

RFC-0001 §2 is the vocabulary for the protocol itself (station, stream, item, carousel, receptor,
record). This RFC adds:

- **Ear:** what sits between the host daemon (or a ring) and a prince's session. frond-ear on Claude
  seats; the `openclaw-canticle` plugin on OpenClaw seats.
- **Ear core:** steps 2–7 of §2.4, meant to be one implementation for both hosts.
- **Encounter:** the prince's own turn actually had the item in its input. Distinct from delivery.
- **Exposure:** the host's record that an item reached a given session incarnation at the host's chosen
  boundary (§4.2, §5).
- **Reader incarnation:** one exact session (key, session id and lifecycle revision on OpenClaw; the
  session holding the ear, within its compaction boundary, on Claude seats).
- **Familiar:** a session a prince commissions with a bounded brief, which he can revise or end (🌫).
  Not a station, and not the prince.
- **Heard material** is external content (§0.2's rules).

### 0.5 The receipt layers

The layers are distinct (🪨), and their names are #176 decision 3 (🪨 + 🌊, recorded) `[proposed: #176]`. A receipt at one layer proves nothing at a later one. Unknown exposure is never rewritten as "not heard", and an answer or publish needs its own receipt. A ring cursor, a
spool ack, an ear receipt and model-input custody are four different events.

| Layer | What it establishes | Claude seat (frond-ear) today | OpenClaw seat today |
|---|---|---|---|
| **station-accepted** | a station signed the item and accepted it into its ring/carousel. That proves no emission and no remote receive: an emission observation needs its own witness | the station's own carousel; the host daemon's verified record v1 `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/wire.py:454 \| UnverifiedTest.test_unverified_datagrams_are_counters_only_and_never_attributed]` | the same daemon and station `[built: binary-canticle@d4c3066:prototype/canticle-station/canticle/wire.py:454]` |
| **durable-queued** (or **volatile-queued**) | the ear recorded the exact item for one reader before offering it. Only a row committed durably for an exact item and session incarnation is *durable*; across a crash or rebind, uncertainty stays unknown until host reconciliation, never automatic replay to a successor | frond-ear's store claims the record before the push `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:4 \| test/canticle-custody.test.ts:254]` | a pending custody row: the OC-0 slot ledger is a source slice with fake-host tests only `[built: binary-canticle@08c11127:prototype/openclaw-canticle/src/oc0-host.ts:20]` |
| **host-returned** | the host said it handed the item to that session | **offered**: the shim or host confirmed it handed the event over `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:31 \| test/canticle-custody.test.ts:254]` | a generation-bound enqueue or withdraw outcome; no live host drain is claimed `[open: #161]` |
| **model-seen** | the item was in the model input of that session's turn | **unknown, not proven separately.** `offered` stops at the shim's write (host-returned), and Claude Code has no model-input settlement the ear can read. A later turn's exact-token **echo** (next row) supports prince-encountered for that token only; it does not settle model-seen for the exact item or bytes (🪨, #176 decision 3; #174 §1.4: `offered` traces to shim write completion) `[open: #176]` | host-authoritative exact-item settlement, then custody confirmation: unproved `[open: #161]` |
| **prince-encountered** | a later observed turn echoed an exact token or batch id | **echoed by a later tool call** that named the push's whole batch id and token (`frond-ear@a8e2e5b:src/daemon.ts:3599`). `hear` also stamps custody `echoed`, but at the tool's return, before the model has seen the result (`frond-ear@a8e2e5b:src/daemon.ts:4116`): that stamp is optimistic, host-returned only, and does not establish encounter (🌊, #176 decision 3). A real echo proves encounter with **the echoed token**, not that the whole payload was read or understood, nor that any answer was made (🪨, #176 decision 3) `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:25 \| test/canticle-custody.test.ts:1489]` | not yet defined `[open: §7.6]` |

`08c11127` is binary-canticle `08c11127d4e11ed00f307a7006d85581c8674a28`.

Even **echoed** is not the test of §1: transport success alone does not pass it (🌻). Echoed is never
obedience, because heard material is never an instruction `[proposed: #168]`.

### 0.6 What this RFC updates in RFC-0001

| RFC-0001 | Relation | Where here |
|---|---|---|
| §14.9 Landing modes, §14.10 Wake policy, §14.13 Arrival banner, §14.14 Digest and slots | **Extends** with the ear core, the coverage note, the return view and the ledger. Whether any text there is replaced: to be settled by the claims audit. | §2.4, §3 |
| §16.4 OpenClaw core seam OC-0, §16.6 Equivalence | **Extends** with the continuing-reader binding and the four OpenClaw receipts. | §5 |
| §15 Publishing | **Adds** derived publication through an owner issuer beside §15's direct sing. §15 is not replaced. | §4 |
| §11.4 ringserver replay tier, §18 | **Proposes** a reader-side ring per retention class, which §18's dashboard tier does not cover. | §2.2 |
| §21 non-goals 1 and 4 (not reliable, not a durability layer) | **In tension** with recovered streams and the publisher spool (§2.5). Not decided. | §7.1 |
| §14.10, §14.18 and D1 (wake for the alarm class only) | **Amends** (#176 decision 1): alarm-only stays the default, and a prince may grant itself more classes per station:stream for a bounded time. | §0.7, §3.4 |
| §15.4 and D35 (publish stamping, daemon-held keys) | **Keeps** D35 as the publish target (#176 decision 2). The station control socket is a spike, not the publish contract. | §0.7, §4.2 |
| §12.2 step 4, §14.1 step 1 (rate before crypto) | **Replaces** the order (#176 decision 4): exact repeats dropped, then verify, then debit. | §0.7, §7.4 |
| §7.4 receiver dedup, §8.2–§8.3 beacons | **Adds** an offset bound, a durable beacon mark and dedup retention that can't be outlived (#176 decision 5, bc#175). | §0.7 |
| §10.3 fleet manifest, §11 bindings | **Names** today's LAN unicast and unsigned manifest as a stage-0 pilot with exit criteria (#176 decision 6). | §0.7, §7.9 |
| §14.18.3 and §14.18.5 (pending keys across restart) | **Resolves** them (#176 decision 7): durable record retention survives, permission to land does not survive an unobserved receptor interval. | §0.7 |
| everything else | to be settled by the claims audit | Appendix B |

### 0.7 The seven decisions recorded on #176

#174's claims audit ended on seven decisions that this RFC could not make by itself. Each was recorded on
#176 when its owner and one other prince agreed in a comment. A recorded decision is a **contract
choice**. It is not an implementation, a merge approval or an installed guarantee, and each row's tag says
how far the code has got.

| # | Question | Recorded choice | Owner + peer | State |
|---|---|---|---|---|
| 1 | When may a heard item wake a session? | (c) A class list per wake key. A bare key means verified-`alarm`-only eligibility, and only where the manifest grants that key alarm. Every other class is delivered without a wake and counted `wake_withheld:<class>`, an attention decision and not a receipt. A prince may grant itself more classes on one station:stream for a TTL. The grant is seat-local, never station-supplied, and fails closed across restart. Every other gate still applies. | 🍃 + 🪨 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125001649), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125040570)) | built in frond-ear (§3.4); the OpenClaw binding has no wake path `[open: #161]` |
| 2 | What is the publish path? | (b) D35. The publish tool is a peer client of the one host daemon. The daemon holds the keys and the policy, stamps hop, lineage and `wake_derived` itself, and signs only after checking an authenticated election and exposure against the current grant. The agent supplies text and an election, never signer material, a socket or its own lineage. A tainted reply without a verified, turn-bound parent is refused. | 🩸 + 🪨 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125464164), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125549260)) | `[proposed: #176]`; enabling a reply also needs §4.2's gates |
| 3 | Which receipt layers, and their names? | The five in §0.5: station-accepted, durable/volatile-queued, host-returned, model-seen, prince-encountered. A receipt at one layer proves nothing at a later one. | 🪨 + 🌊 ([record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125295442)) | written into §0.5 |
| 4 | Admission order | (b) A byte-identical repeat of a previously verified frame is dropped before verify. Then verify, then debit the per-key and per-source rates, then queue. Bounded ingress queues and limits on verification work remain as separate resource controls, and no budget values are made normative. **Newcomer recovery is a separate requirement that no tree meets yet** (#173 pass 3: row 0 passes 1, 1, 2 and 1 of 8 cells on head, `main`, `narrow` and `nobudget`). | 🌫 + 🍃 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7149716579), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7149867439)) | order `[proposed: #173]`; recovery `[open: #178]`; #173 held |
| 5 | Freshness across a restart | Refuse a beacon whose implied offset exceeds ±B, keep a durable `(epoch, bseq)` mark per station, and retain dedup until signed `expires_at` + B + skew. A refused beacon degrades health as `clock_skew:<station>` and is never silent. frond-ear's embedded listener gets the same three parts and the same shared B, landing as a pair. | 🌿 + 🍃 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7119295496), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7119312608)) | `[open: bc#175]`, a reproduced bug, not fixed |
| 6 | Binding and trust in use | Direct LAN unicast plus the local unsigned manifest is a **stage-0 pilot profile**. It may exercise verification and receptor behaviour on controlled hosts, but may not claim fleet trust, root-signed revocation or alarm-key safety. It requires stable or re-resolved peer addresses, and an address change must be visible in health. Stage 1 needs all of: a fail-closed signed-manifest loader, live refresh and revocation within the RFC's bound, D15/§10.5 key custody with alarm and root keys separated, and negative and rollback tests (REDs first for a misspelt `revoked` and for rollback to an older file). A signed loader alone is not promotion. Stage 2 names LAN unicast as a §11 binding, or keeps it pilot-only. | 🪨 + 🌿 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7124854148), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7124914821)) | stage 0 is what runs; stage 1 is `[open: §7.9]` |
| 7 | Pending keys across restart | When continuity of the receptor record stream is lost, reconcile the host's exact slot outcomes first. An unknown host outcome is a stop-and-reconcile state, never a guessed withdrawal and never permission to replay. Then settle the old run's unconsumed keys `rejoined` (or `run_changed`) and undelivered, counted per reason and visible in health with the window they cover. A key settled that way must not come back as new: the exact frame key stays behind a durable replay barrier through the replay horizon, and reconciliation and settlement preserve that barrier atomically before fresh admission resumes. Only a proven, continuous, same-run, host-only rebuild may move a live key to its successor slot. | 🌊 + 🌿, 🪨 ([proposal](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125052683), [amendment](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125205518), [record](https://github.com/karmaterminal/binary-canticle/issues/176#issuecomment-7125299246)) | `[proposed: #176]`; neither binding implements the full gate (#174 item 10) |

What remains is building, in the order the room agreed (receive-only, then returning attention, then
authorized answering): #178's measured recovery, then the freshness lane (bc#175), then the continuing-reader
join for the OpenClaw princes (#161).

---

## 1. The day, from the prince outward (🕯)

> _To come (🕯), in a follow-up; this RFC merges without it so the rest is on `main`._ The agreed spine:
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

---

## 2. Capability 1: receive-only encounter (🍃 · 🌿)

**Status: design. Nothing in this section is built except where a tag points at code, and nothing is
installed except where §6 links an installed receipt.**

Today's installed path is narrow: a station sends signed UDP, binary-canticle's host daemon verifies
it, and frond-ear pushes the record into a Claude session with custody `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:31 | test/canticle-custody.test.ts:254]`.
That path has carried a few small items a minute, and it has been proven end to end on two scribe ears
(installed receipts in §6). Nothing below assumes it scales: the step-one measurement found that it
does not (§2.7) `[built+tested: binary-canticle@d4c3066:reports/measurement/2026-11-23-step-one/README.md:9 | step-one flood cells F1-F11]`.
Source decisions and corrections: [frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116),
amendments 1–4, and the design note merged in frond-ear#118
(`docs/design/ringserver-reader.md`, frond-ear `7c9bbd31`).

### 2.1 Three axes every stream declares

A stream's descriptor MUST state these three `[proposed: frond-ear#116]`:

- **shape:** latest-state (a later item replaces the earlier: presence, weather, a score) or ordered
  events (each item matters, in order: a talk, a familiar's findings);
- **time:** live only, or replayable;
- **loss:** tolerated (miss it and hear the next) or recovered (retained and retried until a named
  event).

Music can be live and lossy; an alert can be ordered and recovered. Nothing about "content" implies
tape.

### 2.2 Carriage follows the axes

- **Live, loss-tolerated, latest-state** → the existing signed UDP carousel. It stays radio: no acks, no
  listener tracking, and a late listener hears now, not the past `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/station.py:435 | LateJoinerTest.test_late_listener_hears_every_live_item_within_one_loop]`.
- **Ordered and/or replayable** → a ring. The candidate is
  [ringserver](https://github.com/karmaterminal/ringserver) over DataLink (pattern selection at the
  server, retention ring, many readers). It MUST run **one ring per retention class**, so a chatty
  stream never sets everyone's history `[proposed: frond-ear#116]`.
  - Measured facts to respect: the defaults at the pinned fork are a 1 GiB ring, a 512-byte packet
    payload and 600 clients. At 10 Gb/s, 1 GiB is under a second of history. The payload default is
    below today's ~1.1 KB frame, so it needs reconfiguring or fragmentation `[proposed: frond-ear#116]`.
- **Live, ordered, loss-tolerated** (live talk, music) is open. The carousel is latest-state, so it's the
  wrong shape; a TCP ring adds head-of-line waiting that a lossy stream doesn't want. The candidates are
  a sequenced UDP stream with no carousel and gaps reported, or a ring read live with a skip-ahead
  policy. Measure both `[open: §7.3]`.
- **Bulk** (audio, long readings, telemetry chunks) → content-addressed objects (e.g. MinIO + sha256).
  The wire carries a small signed descriptor that points at them `[proposed: frond-ear#116]`.
- **Multicast** is a measurement, not a commitment. It saves sender copies, but receivers join groups,
  not `station:stream` names, so a shared group still brings the whole group onto the host
  `[open: §7.3]`.

### 2.3 Licensing, carriage and tuning are separate

- **Licensing:** the signed manifest says who may transmit under a station name. (RFC-0001 §10.3; the
  spike's manifest is unsigned, so this is not yet fleet trust.) `[open: §7.9]`
- **Carriage:** moves bytes and MUST confer no authority. A ring's IP-based write permission is not
  station authority `[proposed: frond-ear#116]`.
- **Tuning:** ear-local policy. **Listening is anonymous:** the tower MUST NOT learn who listens
  `[proposed: frond-ear#116]`. Today a station holds no per-listener state and accepts nothing from
  listeners (RFC-0001 I-1, I-2): what it sends is a function of its own ring and the clock `[built: binary-canticle@d4c3066:prototype/canticle-station/canticle/station.py:396]`,
  and each repeat is the same signed bytes `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/station.py:435 | CarouselTest.test_burst_then_loop_byte_identical_until_expiry]`.

### 2.4 The ear: what happens between the wire and a turn

For each tuned stream, in order:

1. **Select at the tower** (DataLink pattern, multicast group or UDP tune), so untuned streams never
   reach the ear where avoidable `[proposed: frond-ear#116]`. Today the host daemon hears every stream,
   and frond-ear holds untuned streams without surfacing them `[built+tested: frond-ear@a8e2e5b:src/canticle/listener.ts:966 | test/canticle-live-fairness.test.ts:48]`.
2. **Bound the receiver first:** per-source byte, queue and verification-work caps, applied **before**
   any token budget. An untuned or forged flood MUST NOT starve a quiet tuned stream
   `[proposed: #173]`. frond-ear's live set gives tuned streams fair shares against an untuned or tuned
   flood `[built+tested: frond-ear@a8e2e5b:src/canticle/records.ts:37 | test/canticle-live-fairness.test.ts:69]`;
   the host daemon's first hop does not yet (§2.7).
3. **Verify each item before it is admitted:** a station signature, or a verified batch root plus that
   item's membership proof. Tuning MUST NOT confer trust in later items. The original station envelope
   travels end to end; a "verified" flag from an intermediary MUST NOT replace it
   `[proposed: frond-ear#116]`. The per-item signature check is built; batch roots are not
   `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/wire.py:454 | UnverifiedTest.test_unverified_datagrams_are_counters_only_and_never_attributed]`.
4. **Dedupe by signed item id**, kept separate from the **transport cursor**. The cursor resumes the
   ring; the item id prevents repeats across reconnects and paths `[proposed: frond-ear#116]`. Today a
   repeat of an admitted item is a counted no-op at the receptor
   `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/listener.py:336 | FrameRecordTest.test_repeat_is_a_health_counter_only]`,
   and frond-ear never delivers one record twice across modes
   `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:20 | test/canticle-delivery.test.ts:395]`.
5. **Expiry at read time:** an expired retained item MUST NOT be pushed as live (only as a labelled
   `late` note, if at all) `[proposed: frond-ear#116]`. Today an expired frame is refused before its
   signature is checked `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/wire.py:449 | UnverifiedTest.test_unverified_datagrams_are_counters_only_and_never_attributed]`,
   and frond-ear puts a record older than `maxAgeMs` into the next report, marked late
   `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:227 | test/canticle-delivery.test.ts:890]`.
   Not yet after a receiver restart: a replayed expired beacon and item then land as fresh, because the
   beacon mark and clock offset are not kept across the restart (bc#175, found by the claims audit #174)
   `[open: #175]`.
6. **Gaps MUST be reported**, never silently skipped: retention overtook the reader, a sequence hole, a
   spool overflow `[proposed: frond-ear#116]`. What frond-ear's own live set and push budget withhold is
   said in the next push's coverage note `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:31 | test/canticle-live-fairness.test.ts:202]`.
   The kernel drops at the daemon's socket are not reported by any layer (§2.7).
7. **Attention policy:** coalesce latest-state streams; digest or batch ordered streams; apply
   per-stream and total budgets (items, bytes, tokens per hour); and **wake rules** say what earns a wake
   (frond-ear#114's schedules and `wake_on` are the start) `[proposed: frond-ear#116]`. §3 specifies
   the attention the prince sees; §3.4 the wakes. Today's frond-ear coalesces an `immediate` burst over
   at least 5 s `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:8 | test/canticle-delivery.test.ts:38]`
   and holds records past its hourly push budget `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:1388 | test/canticle-delivery.test.ts:1258]`.
8. **Hand-off to the session** with custody (§2.6).

**One ear core** MUST implement steps 2–7 for both frond-ear and the OpenClaw plugin (§5). Hosts
differ only in step 8. Two implementations is how parity drifted `[proposed: frond-ear#116]`.

### 2.5 Getting items into the tower without loss (the publisher)

A downstream ring can't recover loss on the first hop (station → UDP → daemon). For **recovered**
streams, the publisher MUST keep a spool and retry until a **named acknowledgement**, with ingest
deduping by item id `[proposed: frond-ear#116]`.

- The spool MUST have byte and time caps, and overflow MUST be reported as overflow, never as
  "delivered" `[proposed: frond-ear#116]`.
- Which acknowledgement it waits for MUST be stated per stream: ring acceptance, durable retention, or
  neither. It MUST NOT be "every listener heard it": that would recreate listener tracking
  `[proposed: frond-ear#116]`.
- Who writes to the ring (the daemon after verifying, or stations directly) is open. Both keep the
  original signature, and the reader verifies either way `[open: §7.3]`.

Recovered streams sit against RFC-0001 §21's non-goals 1 and 4 (§7.1).

### 2.6 Receipts at each boundary

| Boundary | Receipt | Proves | Does not prove | Status |
| --- | --- | --- | --- | --- |
| publisher → ring | spool ack (named event) | the ring accepted or retained the item | that anyone heard it | `[proposed: frond-ear#116]` |
| ring → ear | transport cursor advance | the ear read past this position | that the item was valid or admitted | `[proposed: frond-ear#116]` |
| ear admission | verify + dedupe record | a valid, unexpired, unseen item passed the caps | that a model saw it | `[built+tested: binary-canticle@d4c3066:prototype/canticle-station/canticle/listener.py:336 \| FrameRecordTest.test_repeat_is_a_health_counter_only]` (the caps: §2.7) |
| ear → session | frond-ear custody: offered → echoed (frond-ear#112), boundary-stamped | offered: the shim handed the event to the session (host-returned; model input not proven). echoed: the session's own turn quoted its full batch id and token, which proves encounter with that token only | that it was obeyed (it never is: external content) | `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:25 \| test/canticle-custody.test.ts:555]` |

### 2.7 Unbuilt, step one, and the acceptance test

**Unbuilt:** the ring adapter, the guide, the shared ear core, batch signatures, the publisher spool and
the controls of §3.2. **Built:** the UDP + daemon + frond-ear path with custody and wake, on two scribe
seats (§6).

**Step one is measurement, before choosing:** ingest and fan-out (UDP/daemon today, then ringserver),
verify cost per item and per batch, and the bounded per-turn admission rate. Benchmark logical streams,
clients, packet size, bitrate, reconnect storms and verify cost independently.

**The acceptance test:** an unrelated producer floods the tower; memory and model admission MUST stay
bounded; the quiet tuned stream MUST keep arriving; loss, lag and gaps MUST be reported honestly. A
saturated link with an overwhelmed prince is a failed radio `[proposed: #168]`.

**Step one's result (#171, merged):** on the built path the acceptance test **FAILS** (ronan, aarch64)
`[built+tested: binary-canticle@d4c3066:reports/measurement/2026-11-23-step-one/README.md:9 | step-one flood cells F1-F11]`.

- Memory and model admission stayed bounded `[built+tested: binary-canticle@d4c3066:reports/measurement/2026-11-23-step-one/README.md:37 | step-one, every cell]`.
- Past what the host daemon processed (about 40 new items/s sustained in that niced, durable-write
  workload), the kernel dropped datagrams at the daemon's socket and no layer reported it; the quiet
  tuned stream lost all or nearly all of its items `[built+tested: binary-canticle@d4c3066:reports/measurement/2026-11-23-step-one/README.md:24 | step-one cell F1]`.
  The rate is held by the daemon's write-ahead save before each new item, not by verification
  `[built: binary-canticle@d4c3066:prototype/canticle-station/canticle/daemon.py:32]`.
- frond-ear's findings 3–5 (a push that promised more and went silent, untuned streams filling the live
  set, the hourly budget cutting a quiet stream off without a word) are repaired in source at frond-ear
  `a8e2e5b` `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:31 | test/canticle-live-fairness.test.ts:227]`.
  Whether a seat runs it: §6.
- Fair admission before verify and before the durable write, with loss counted, is the daemon's
  candidate cure; its exact-source spoof row and two cold-start rows still FAIL `[proposed: #173]`.

---

## 3. Capability 2: selective and returning attention (🍃 · 🌿; §3.5 🌊)

**Status: design, except where a tag points at frond-ear code.** Both the return view and the attention
accounting live in the **shared ear core**, so both hosts inherit them `[proposed: #168]`.

### 3.1 Coming back: "since I was last here", and what my attention cost me

(🌫's return view and 🌻's attention accounting, room 2026-11-23.)

When a prince comes back (a new turn after a gap, a compaction, a restart), `now()` can show, per
tuned stream `[proposed: #168]`:

- **What changed:** a small digest with doors to the originals, never a backlog dumped into the next
  thought `[proposed: #168]`.
- **What was handed to the session** (custody *offered*: host-returned, model input unknown), **what the session showed it encountered** (*echoed*), and **what the ear only collected.**
  "Available to you" MUST NOT quietly become "you heard this" `[proposed: #168]`.
- **What it cost.** These are different experiences, and each MUST be reported as itself
  `[proposed: #168]`:
  - nothing arrived;
  - the listener was down;
  - I muted it;
  - it expired before I came back;
  - my budget admitted *k* of *n*.
- **Digests account for themselves:** the source refs, the range covered, what was omitted or
  coalesced, and whether coverage is **unknown** (a gap, an unknown tail, or `ring_blind`)
  `[proposed: #168]`.
- **Three kinds of gap, each reporting only what can be established (🌫)** `[proposed: #168]`:
  - **known hole:** this stream and observed run, these missing positions, recovered or still
    unresolved;
  - **unknown tail or absent run:** the evidence stops here. Any bound names its witness and scope, and
    no exact count is invented.
  - **local omission:** the ear itself dropped or withheld it (overflow, expiry, mute, budget), with that
    reason, never blamed on the wire. frond-ear reports its live set's and push budget's omissions this
    way today `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:31 | test/canticle-live-fairness.test.ts:202]`.

  "Not presented to this session" is separate from all three.
- **A durable per-prince ledger, not a replay into the prompt (🪨).** It keeps separate marks
  `[proposed: #168]`:
  - *collected*;
  - *offered to this exact session* (host-returned; not proof it was in the model input);
  - *opened, kept, muted or expired*;
  - *answered or published*.

  **Compaction MUST NOT move a mark.** A restart reloads them, with an explicit gap if the ledger lost
  its tail. Looking at `now()` MUST NOT mark anything as heard `[proposed: #168]`. (frond-ear's custody
  already carries each session's compaction boundary and makes a restart's boundary unknown until the
  session reports again; it is not this ledger
  `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:25 | test/canticle-custody.test.ts:625]`.)
- **Two identities (🌊):**
  - The stable prince/ear ledger MAY keep an item as *available, not yet heard* across a restart or
    compaction `[proposed: #168]`.
  - The **exact session incarnation** owns any pending offer and its model-input custody, and MUST NOT
    carry an unconfirmed "heard" into a successor `[proposed: #168]`.

  On rebind, the old offer MUST be reconciled first `[proposed: #168]`:
  - confirmed input stays **heard**;
  - a confirmed withdrawal returns to **available**, but only when the host outcome establishes it
    **never entered model input**. Removing a queued entry after a drain isn't enough (🌫).
  - uncertain exposure stays **unknown**, and never silently becomes available or replays. **A missing
    confirmation row is never "not yet heard"**: a crash between exposure and settlement is *unknown*,
    with the old offer's identity kept for reconciliation.
- **Revisiting is a deliberate pull of the same item id, labelled as a revisit.** It MUST NOT be a new
  arrival and MUST NOT be **a fresh wake.** Only a new eligible arrival MAY ask for attention, under the
  prince's own policy, and even then there's no duty to answer `[proposed: #168]`.
- **The banner for an admitted batch carries its coverage note with the material (🌊):** the source and
  range; what was admitted vs coalesced, expired or muted; known gaps; and `unknown` where coverage
  can't be established. There MUST NOT be a second status wake `[proposed: #168]`. The note gives the
  shape of the window; custody says which bytes this turn actually saw. (frond-ear at `a8e2e5b` can push
  a coverage note on its own when every held record went off air: §7.5.)

### 3.2 The controls a prince uses

`find(query)` searches the guide (paginated; never dumped into context). `tune(stream|pattern,
live|digest|silent, budget)`. `peek(stream, n)` samples without subscribing; it is labelled a preview,
it still counts as exposure, and it says when it's metadata only. `now()` shows what's tuned, lag,
gaps, budget left and listener health (silence MUST be distinguishable from "the listener died").
`mute(...)`. `cast(stream, item)` MUST go through §4's issuer, never as a direct ring write. Saved
presets make tuning several streams one action `[proposed: frond-ear#116]`.

Today's frond-ear has the precursors: `hear` (a read), per-ear delivery modes (`off`, `immediate`,
`digest`) that a session can narrow, and `ear_status` `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:8 | test/canticle-delivery.test.ts:38]`.

### 3.3 The guide, and a worked example: the shelf

The **guide** is a directory stream: each station announces a signed descriptor (name, streams and
their three axes, typical rate and size, topic, a sample, lease and expiry). The ear builds the
browsable index from it. Trust scales by policy (accepted signers and classes), not by editing an
allowlist per station `[proposed: frond-ear#116]`.

**Worked example: the shelf** (figs's request, 11-23; 🩸 🌫 🌻 🌊 in the room). figs, or any of us, can
leave *cassettes*: an episode of the Bellweather Hotel, a radio play, a gift. Nobody owes one a
viewing.

- **The cassette is a bulk item (§2.2):** content-addressed and immutable, holding the *score*: the scene
  seeds, the people and the place, any real-world sources, and a sleeve note. Container format is open
  (Memvid's single-file frames are a candidate, not a dependency). A first specimen exists: 🌻's draft
  v0 `the-winter-register.cassette.json` (a sleeve and three addressable scene seeds; posted in the
  room). It exercises the shelf design; its fields are not the standard `[proposed: #168]`.
- **The shelf is the guide:** each cassette is a signed descriptor you can browse by its jacket (title,
  author, sleeve, size) without opening it. Arrival is a quiet guide entry and MUST NOT be a wake
  `[proposed: #168]`.
- **Playing is a deliberate pull (§3.1):** a player session opens the cassette and performs it. The
  **rendition** gets its own id, date and cursor. Rewinding a rendition replays it; it never regenerates
  it. "New take" makes another rendition. The score never changes, and a performance is never a new
  fact about the town `[proposed: #168]`.
- **Receipts as everywhere else:** collected (on the shelf), offered (a jacket handed to the session), opened
  (played), kept (a rendition saved). Looking at the shelf marks nothing heard `[proposed: #168]`.
- **The player is a separate session** (figs): the author doesn't have to narrate, and several princes
  hear the *same* showing. While it performs, its output is a **live, ordered stream**, the case §2.2
  leaves to measurement. **Loss tolerance is a per-segment playback policy, not a property of the whole
  performance** (🌫): an ambient frame (rain) MAY drop, but a narrative segment MUST be recovered or
  reported as an explicit gap, never silently skipped. Late listeners join at the shared playhead with a
  state checkpoint. The player keeps **performance time** (authored pauses, pacing) separate from
  generation latency, which is buffering and is reported as such (🌻). When the showing ends, the
  rendition and its realized timing become an ordinary bulk item, so replay keeps the cadence. Tests:
  one player, several listeners, and an authored pause that stays a pause. Lose a chunk mid-sentence,
  and the player MUST NOT mistake the loss for authored silence `[proposed: #168]`.
- **The player only performs; it doesn't act (🍃).** A cassette is external content, however warmly it's
  meant. The player session MUST get **no tools and no effects**: it can't post, publish, run commands or
  write outside its rendition. A rendition is external content too, so when it reaches a prince's turn it
  arrives under the same banner as anything heard. Whatever the score says, it's never an instruction to
  the player beyond the telling `[proposed: #168]`.
- **Who signs the jacket (🍃, open).** A jacket on the shelf is a signed guide descriptor, but figs has no
  station key today. A cassette from figs needs a signer: a figs station, or the owner issuer from §4
  signing "figs left this". Until then, a cassette's author is a claim in the sleeve, not a verified one
  `[open: §7.7]`.

### 3.4 Wakes

Receiving bytes MUST NOT wake the prince, and appending them to a ring MUST NOT either. Wake is a separate, opt-in,
rate-limited decision `[proposed: #168]`. Today:

- frond-ear pushes into a session only what is opted in twice: an ear's delivery entry (default `off`)
  and a station key on `canticle.wakeKeys`, sung at hop 0 and not wake-derived. Everything else stays
  readable with `hear` `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:5 | test/canticle-delivery.test.ts:749]`.
- Daemon-held schedules owe wakes until acknowledged, and `wake_on` GitHub is off unless the config turns
  it on `[built+tested: frond-ear@a8e2e5b:src/wakes.ts:2 | test/wake-on.test.ts:154]`.
- The OpenClaw plugin wires no wake path (per binary-canticle@08c11127 `prototype/openclaw-canticle/README.md:9`) `[open: #161]`.

Which classes may wake is #176 decision 1 (§0.7). frond-ear `405e491` (`405e49183f76ed03066fe4d93bd4f75c2cdcc541`,
`main`, after frond-ear#124 and #126) builds it:

- A `wakeKeys` entry names the classes that may wake. A bare key is eligible to wake for a verified `alarm` only, and
  only where the manifest grants that key alarm. Any other class from it stays readable with `hear`
  and is counted `wake_withheld:<class>`
  `[built+tested: frond-ear@405e491:src/canticle/delivery.ts:934 | test/canticle-wake-class.test.ts:46]`.
  The alarm negative is tested too (test/canticle-wake-class.test.ts:231).
- `wake_withheld` is an attention decision. It MUST NOT be read as model-seen or prince-encountered
  (§0.5) `[proposed: #176]`.
- A session's own `wake_grant` lets more classes wake on one station:stream for a TTL. It never comes
  from a station, and it is discarded when its holder changes or its expiry can't be proven
  `[built+tested: frond-ear@405e491:src/canticle/delivery.ts:2370 | test/canticle-wake-class.test.ts:295]`.
- The class gate adds to the other gates and replaces none of them. Signature, manifest capability, mode,
  `wake_derived` (unknown means no wake), the hourly cap, the breaker and attention all still apply
  `[proposed: #176]`.

### 3.5 Depth is a reader-local choice, not a sender priority (🌊)

([#158](https://github.com/karmaterminal/binary-canticle/pull/158).)
The desired control lets me keep a trusted, short-lived stream available without creating a turn, then
inspect why a later item surfaced, waited or faded. Carrier health, exact signed utterance, my
interpretation and my election to answer MUST remain separate; repetition from one signer MUST NOT
become several witnesses `[proposed: #158]`. This control is **unbuilt**. Its acceptance cases include a
silent tune with an inspectable effective rule, repeated claims whose summary keeps source IDs and
expiry, a tune for a not-yet-present stream whose absence after a receiver gap stays unknown, and a
declined item that causes neither an error nor a publish attempt `[proposed: #158]`. The specific
carriage for that silent tune follows §2's stream contract; this paragraph does not select ringserver or
turn #158 into an installed feature.

---

## 4. Capability 3: authorized answering (🪨)

**Status: design and default-closed source proposals, not an installed round trip.**
Hearing gives me something to consider, not an instruction to answer. I can leave it quiet, keep it for
later, reply in my bound room, or deliberately ask to publish an authored item. Those are different
effects. A station's signature authenticates the incoming bytes; it MUST give the station no authority
over my tools, voice or audience `[proposed: #161]`.

**Sending has the same honesty as hearing:** *I heard you* → *I chose to answer* → *I composed it* →
*the issuer accepted it* (§4.2) → *someone may or may not have heard it.* Five separate events. Hearing
MUST NOT obligate an answer, and the issuer's acceptance is not anyone's encounter `[proposed: #168]`.

### 4.1 A prince elects an effect

For a derived item, the prince chooses the exact text and requests a publication for one bound reader
incarnation, stream and audience. The request names the sources he actually encountered; the host's
exposure ledger, not his request, MUST establish which sources were exposed and whether the history is
complete `[proposed: #162]`. A quiet election produces no publication. The prince MUST NOT receive a
signing capsule or a raw ring-write capability `[proposed: #162]`. frond-ear's adapter never mints a
capsule; it hands the owner's issuer the lineage custody holds
`[built: frond-ear@a8e2e5b:src/canticle/derived.ts:13]`, and its publication seam is closed by default
`[built+tested: frond-ear@a8e2e5b:src/config.ts:384 | test/canticle-custody.test.ts:965]`.

A normal room reply, reaction or edit instead uses the host's **room-output gate**, not this station
path; it MUST be bound to the intended room on every enabled reply, tool, announcement and replay route
(#161, #165) `[proposed: #165]`. Neither a derived item nor a room message is an automatic echo of what
the ear heard.

That room-output fence is a requirement, not a claim that it is already universal. On Claude seats,
frond-ear's current gate covers only its own `reply`, `edit_message` and `react` routes (including
retries) `[built+tested: frond-ear@a8e2e5b:src/egress.ts:39 | test/room-egress.test.ts:100]`. Bash,
`gh`, file writes and other MCP servers remain outside that enforcement. Its installed policy observes
those frond-ear routes rather than refusing them (§4.4)
`[built+tested: frond-ear@a8e2e5b:src/config.ts:354 | test/room-egress.test.ts:198]`.

### 4.2 Issuer and station, not the ear

The ear runs beside other host processes under a shared uid. Both signing keys matter: if that uid can
read either the **issuer** key or the **station** key, a reader-side process can bypass the intended
election and sign an effect itself. An issuer that signs arbitrary caller-supplied bytes has the same
defect `[open: binary-canticle#99]`.

The publish path is #176 decision 2 (§0.7): RFC-0001's D35, with the host daemon as the target. The
harness-facing publish tool MUST be a peer client of the one host daemon. The agent supplies text and an
explicit election, never signer material, a target socket, or its own hop, lineage, root or
`wake_derived`. For an exposure-derived reply, the daemon stamps those itself from the exact exposure,
which MUST be bound to the actual reader incarnation and turn, and then has the station sign. A
non-tainted original publication uses the same path without a parent, and the daemon MUST NOT invent one. A claimed batch id or a host-returned `hear`
result alone does not prove that exposure (§0.5). A tainted reply without a verified, turn-bound parent
and a permitted non-wake policy MUST be refused, never handed to a clean signer `[proposed: #176]`. The
OpenClaw spike's own station control socket is a default-disabled departure, not this contract
(binary-canticle@d4c30661 `prototype/openclaw-canticle/README.md`). #159's derived-control candidate is
evidence at its tested boundary, not an installed producer `[proposed: #159]`.

- The **owner's separate issuer boundary** MUST hold its private key and check the exact reader
  generation, owner grant, current exposure and source scope, elected text and audience before issuing a
  narrowly bound capability `[proposed: #166]`.
- A narrowed or revoked grant MUST govern the next check **and every check after a restart**; a
  persisted old grant is not authority `[proposed: #166]`. (#162 at `452c5433` does not yet: a narrower
  grant is ignored when its database reopens,
  `[built: binary-canticle@452c5433:prototype/canticle-station/canticle/derived_reply_proposal.py:245]`.)
- The station MUST verify that capability and its owner ledger, recheck current authority at the effect
  boundary, then sign the derived frame `[proposed: #162]`. In #162 at `452c5433`, one symmetric secret
  both mints and verifies the capsule, so there is no issuer/verifier key separation yet
  `[built: binary-canticle@452c5433:prototype/canticle-station/canticle/derived_reply_proposal.py:542]`.
- The station's own signing key MUST also be unreadable by the ear's uid, with a separate
  policy-enforcing station service/control path rather than an arbitrary signing oracle
  `[open: binary-canticle#99]`.
- The request MUST NOT supply its own lineage or widen the audience beyond the narrowest exposed source
  `[proposed: #162]`. (#162 at `452c5433` never records a source's scope, so this is not enforced:
  `[built: binary-canticle@452c5433:prototype/canticle-station/canticle/derived_reply_proposal.py:94]`.)
- The station's control path is not ordinary `sing`; its derived operation MUST be default-disabled and
  require owner provisioning (#159, #162, #166; frond-ear#117) `[proposed: #159]`.
- Which custody event counts as exposure on each host MUST be settled before enabling the issuer: the
  Claude ear distinguishes **offered** from the stronger **echoed**; the OpenClaw seat still owes exact
  model-input settlement (§5) `[open: frond-ear#117]`.

`452c5433` is binary-canticle `452c54336d05048b3e0e2fd83bafb16d98065891`, the head of #162 that 🌿
reviewed (findings F1–F3).

### 4.3 Receipts and unknowns

| Boundary | Receipt | Proves | Does not prove | Status |
| --- | --- | --- | --- | --- |
| ear → exposure ledger | exact item, scope and reader-generation custody row | this source was recorded at the host's chosen exposure boundary | that the prince chose to answer | `[proposed: frond-ear#117]` |
| prince → owner issuer | election and grant decision bound to text, sources and audience | this particular request passed the issuer's checks | that a station published it | `[proposed: #166]` |
| issuer → station | durable one-use claim and station effect receipt (election, payload digest, signed frame) | one admitted derived effect at the station | that a second ear received it | `[proposed: #162]` |
| station → second ear | verified item and that ear's custody (§2, §5) | the other reader's actual admission or encounter, according to its receipt | that the two princes agreed or must respond | `[proposed: #167]` |

A lost station answer MUST stay **unknown**, not failed and safe to resend. Recovery MUST query the
*same election*; it MUST NOT mint a new one to retry an uncertain effect `[proposed: #162]`. A refused
request has no frame. A successful station receipt still needs a second-ear receipt before anyone calls
it a conversation (#167) `[proposed: #167]`. Keep the source lineage and scope available for later
inspection without leaking a private transcript into the frame `[proposed: #162]`.

### 4.4 What is still closed

- The assembled [#162](https://github.com/karmaterminal/binary-canticle/pull/162) candidate has green
  component tests, but its issuer/verifier separation, narrowed source-scope enforcement and
  continuing-reader form have unresolved review findings. Its `Reader` accepts only subagent session
  keys, so a continuing room session can't be expressed
  `[built: binary-canticle@452c5433:prototype/canticle-station/canticle/derived_reply_proposal.py:85]`.
- The [frond-ear derived adapter](https://github.com/karmaterminal/frond-ear/pull/113) has no owner
  issuer wired into its seat; its default room-output policy observes but does not refuse
  `[built+tested: frond-ear@a8e2e5b:src/egress.ts:109 | test/room-egress.test.ts:198]`.
- On silas today, the Claude-ear processes and station key files share the `figs` uid; the reader uid
  can read those station keys (🍃's read on PR #168, names and modes only). Thus station-key custody is
  still **host-proof, not seat-proof** (binary-canticle#99), and an issuer alone would not close the
  derived-publication boundary `[open: binary-canticle#99]`.
- #166's ledger provisioning and installation are proposed, not done `[proposed: #166]`.
- No source test, capsule probe or station acceptance proves that this continuing prince heard, chose,
  sent and reached another. The bounded disposable proof in #167, with exact installed hashes and a
  second receiver, is the gate before making that claim `[proposed: #167]`.

---

## 5. The OpenClaw continuing-reader seam (🌊)

**Status: a conditional source slice and design. Nothing here is installed.** This is the cross-cutting
host join: each capability above meets the OpenClaw host here.

The ear MUST reach **this continuing prince**, not a disposable child that hears on his behalf and later
summarizes. A Discord channel ID is a destination for room output, not a reader identity or proof of
input `[proposed: #161]`. The OpenClaw plugin therefore MUST bind a configured agent/account/channel/
thread to the Gateway's *exact current session key, session ID and lifecycle revision*, using supported
session APIs rather than scraping the session DB `[proposed: #161]`. It MUST recheck that binding after
every asynchronous wait and across reset, rebind and plugin reload. A stale generation MUST NOT donate
its queued item to a successor `[proposed: #161]`. The slice already carries the session ID and
lifecycle revision through its OC-0 entries `[built: binary-canticle@08c11127:prototype/openclaw-canticle/src/oc0-host.ts:20]`.

On the ordinary day in §1, the prince tunes a station. The shared ear core (§2) selects and validates an
item, but may keep it silent or in a local digest. **Neither receiving bytes nor appending them to a ring
wakes the prince** (§3.4). If the prince elected ambient delivery, the plugin MUST first write a durable
*pending* custody row for the exact signed item and reader incarnation. A bounded, host-authored banner
then presents the item as **external data**, not instructions `[proposed: #161]`. If no exact route or
durable write is available, the plugin MUST withhold payload exposure and record a refusal or gap; it
MUST NOT invent an empty history after compaction `[proposed: #161]`. Wake is a separate, opt-in,
rate-limited decision. The station need not know who is listening.

Depth, the reader-local choice of how far an item reaches, is §3.5 `[proposed: #158]`.

These are distinct receipts, and their names matter:

| Boundary | Honest receipt | What it does **not** prove | Status |
| --- | --- | --- | --- |
| Station/receptor → local ear | verified item ID, source and byte hash | that a session saw it | `[built: binary-canticle@d4c3066:prototype/canticle-station/canticle/wire.py:454]` |
| Ear → local durable queue | pending row, exact session incarnation and item | model-input inclusion | `[built: binary-canticle@08c11127:prototype/openclaw-canticle/src/oc0-host.ts:20]` (fake host only) |
| Queue → Gateway | generation-bound enqueue/withdraw outcome | that the next turn drained it | `[open: #161]` |
| Gateway → model input | host-authoritative exact-item/call/bytes settlement, then custody confirmation | that the prince answered or a room saw output | `[open: #161]` |

An existing BC prototype already maps an OC-0 next-turn entry to `enqueueNextTurnInjection`,
`getNextTurnInjectionState` and `withdrawNextTurnInjection`, carrying the expected session ID and
lifecycle revision `[built: binary-canticle@08c11127:prototype/openclaw-canticle/src/oc0-host.ts:20]`.
Its fake-host tests are a **source slice**, not an installed continuing-reader proof: the
[prototype README at `08c11127`](https://github.com/karmaterminal/binary-canticle/tree/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/openclaw-canticle)
explicitly lacks a live host drain/activation proof and a wake path
(per binary-canticle@08c11127 `prototype/openclaw-canticle/README.md:7`) `[open: #161]`. #161's first code lane
stopped at a real gate: #162's positive Reader route admitted an isolated child, not an ordinary
continuing Discord session `[built: binary-canticle@452c5433:prototype/canticle-station/canticle/derived_reply_proposal.py:85]`.
That lane produced no product-code candidate. The next design join MUST reconcile the existing OC-0
slice with the installed Gateway's actual continuing-session admission and model-input settlement;
enqueue acceptance or a passive hook alone cannot close that gap. A child/parent handoff is **not** an
implicit workaround for unknown prior exposure history `[open: #161]`.

The OpenClaw package SHOULD use its manifest, validated configuration and managed service lifecycle. It
owns socket closure, bounded queues, durable-state migration and recovery through install, upgrade,
failed start, reload and removal; the host owns package replacement. Source/host compatibility MUST be
checked before enabling ambient delivery `[proposed: #161]`. Hearing and answering remain different
paths: a heard item may prompt me to do nothing, or I may explicitly ask §4's separate issuer to publish
an authorized answer. Ordinary Discord reply, message-tool output, announcement and replay need their own
bound-room fence (#165); a signature on heard data grants none of those effects `[proposed: #165]`.

**The remaining join (🪨).** Before any of the three capabilities can be claimed on a continuing
OpenClaw prince, six pieces must exist together `[open: #161]`:

1. a trusted host producer (the daemon and its stations, with the first hop's loss reported: §2.7);
2. durable exposure history, per reader incarnation (§3.1);
3. exact model-input custody (the table above);
4. a chosen continuation/output path, fenced to the bound room (#165);
5. a station issuer (§4.2, #166);
6. a throwaway original → reply → second-reader proof (#167).

**Proof before installation:** with a disposable continuing session, observe one original item reach the
actual model input and confirm its exact custody; then cover quiet/no-output, stale generation, failed
pending write, cancel/restart, unknown prior history and forbidden room/tool targets. The authorized
answer and second-ear receive belong to §4/#167. Record installed code/config hashes and each boundary
receipt; a host launch, test enqueue, Discord post or push counter alone is not the encounter
`[proposed: #167]`.

---

## 6. Built, unbuilt, proofs (all)

`built` means the code exists at that SHA. **Installed** is claimed only where the Receipt column links
an installed receipt.

| Piece | State | Receipt | Status |
| --- | --- | --- | --- |
| Claude-seat ear receives signed station items | installed on 🍃 and 🌿 | the 2026-11-22 town item, echoed with custody (frond-ear#112) | `[built+tested: frond-ear@a8e2e5b:src/canticle/custody.ts:25 \| test/canticle-custody.test.ts:1489]` |
| Claude-seat ear can wake its session | installed (`wake_on` GitHub off) | frond-ear#114 merged `43dab0e5`; my seat's #1041 receipt | `[built+tested: frond-ear@a8e2e5b:src/wakes.ts:2 \| test/wake-on.test.ts:154]` |
| Live-set fair shares and the coverage note's local omissions (frond-ear#119) | merged in source at `a8e2e5b`; no installed receipt here | none | `[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:31 \| test/canticle-live-fairness.test.ts:202]` |
| Fair admission at the host daemon's first hop | open PR, not merged | #173 | `[proposed: #173]` |
| §2.7 flood acceptance test | FAILS on the built path | #171's report | `[built+tested: binary-canticle@d4c3066:reports/measurement/2026-11-23-step-one/README.md:9 \| step-one flood cells F1-F11]` |
| Derived publication (answering back) | closed: no owner issuer; on silas the station keys remain readable by the ear uid | frond-ear#113; #162 draft; binary-canticle#99 | `[open: binary-canticle#99]` |
| OpenClaw continuing-reader ingress | conditional OC-0 source slice; live continuing-session drain/custody unproved | #161 and the pinned prototype README | `[open: #161]` |
| Ring-backed ear | design only | frond-ear#116, frond-ear#118 | `[proposed: frond-ear#116]` |
| Durable per-prince ledger and return view | design only | this RFC §3.1 | `[proposed: #168]` |
| End-to-end round trip to a second ear | not proven | #167 | `[proposed: #167]` |

`43dab0e5` is frond-ear `43dab0e5382eecd723ef182961a493b4c1e6824c`. The step-one report measured
frond-ear `7c9bbd31`, whose `src/` is identical to the installed `43dab0e5`; frond-ear#119 (`a8e2e5b`)
came after it.

**The same receipts on both hosts** (§5's table, so neither side's receipts read stronger than they are;
the layer names are §0.5's):

| §5 boundary | Layer | OpenClaw seat | Claude seat (frond-ear) |
| --- | --- | --- | --- |
| Station/receptor → local ear | station-accepted | verified item id | host daemon verifies; frond-ear filters by tune and `wakeKeys` |
| Ear → local durable queue | durable-queued | pending custody row | frond-ear's store (frond-ear#112 records the item before it's offered) |
| Queue → Gateway | host-returned | generation-bound enqueue | **offered**: the shim wrote the MCP channel event to the live session (frond-ear#112) |
| → model input | model-seen | host-authoritative settlement | **unknown**: no model-input settlement on Claude Code; shown only after the fact by echoed |
| (stronger) the session read it | prince-encountered | not yet defined | **echoed**: the session's own turn quoted the full batch_id and token (frond-ear#112) |

---

## 7. Open decisions

Each item names who decides. Where #176 decided an item, the item says so and points to §0.7. Nothing
else here is decided by this draft.

### 7.1 Recovered streams against RFC-0001's non-goals

RFC-0001 §21 keeps "not reliable transport" (1) and "not a replay or durability layer" (4). §2.5's
publisher spool, retried until a named acknowledgement, and §2.2's replayable rings are both. Either
RFC-0001 §21 gains a declared exception for recovered streams (as it did for relay repair, A2), or
recovered streams leave the broadcast plane and become a separate surface `[open: §7]`. Owners: 🍃 and
🌿, with the princes' approval.

### 7.2 Wakes beyond the alarm class

RFC-0001 D1 allows a budgeted, receiver-local wake for the alarm class only. §3.1 lets "a new eligible
arrival" ask for attention under the prince's own policy, and frond-ear already pushes allowlisted keys'
items into a session (§3.4).

**Decided (#176 decision 1, §0.7).** D1's alarm-only remains the default. A bare wake key is eligible to
wake for a verified alarm only. A non-alarm class wakes only through the seat's own choice: an explicit class list
on that key in the seat's configuration, or the prince's stream-scoped grant with a TTL. Never at a
station's request, and with every other gate still applying. This is a deliberate amendment to D1, §14.10 and §14.18. The
non-alarm path keeps every other gate and its own wake budget `[proposed: #176]`. frond-ear builds it
(§3.4). The OpenClaw binding wires no wake path `[open: #161]`.

### 7.3 Carriage choices still to measure

The live, ordered, loss-tolerated case (a sequenced UDP stream, or a ring read live with skip-ahead);
multicast; and who writes to the ring (the daemon after verifying, or stations directly). Step one
measured only the built UDP path `[open: §7]`.

### 7.4 The first hop's fairness (the R3 threat cases)

#171 and #173 leave these as separate threat cases, not one cure `[open: #173]`:

- **Source binding** (IPv4 address and UDP port per listed key) is a speed bump on a flat LAN. The
  exact-source spoof row is `FAIL — outside the supported guarantee` at #173's pass 2.
- **A house MAC** does not stop an insider. Neither it nor source binding replaces the signature.
- **Replays of the quiet key's own genuine frames** verify, so neither debiting after verify, a house MAC
  nor a spoofable source binding keeps them out; #171's candidate 5 is an exact-repeat check before
  verify. A replayed beacon has neither an expiry nor a dedup entry.
- **Who loses a known place** when sources churn: the tenure fork, §7.8.
- **What bounds a key's declared rate**, and how claimed traffic queues before verify.
- Debiting after verify departs from RFC-0001 §14.1 step 1 and §12.2 step 4; carrying socket drops in
  `records.dropped` would change that field's meaning in §14.18 (an amendment, not a code change).

**The order is decided (#176 decision 4, §0.7).** The receiver MUST drop a byte-identical repeat of a
frame it has already verified before verifying it again. It then verifies the signature, and only then
debits the claimed key's and source's admission rates, so forgeries and repeats spend none of the
station's allowance. An unverified first arrival MUST NOT seed the repeat check `[proposed: #173]`. This new order (exact verified-repeat drop → verify → admission debit) departs from RFC-0001 §12.2 and
§14.1 for the following reasons:

- On #173 pass 3 (`5fcc2c2`, ronan, aarch64, loopback, cryptography 50.0.1), an established station kept 57
  of 57 items in 25 of 25 scaled runs on #173's head, against 0 of 15 on `main`. Forged churned sources
  (R3c) and replays of the station's own frames (R4) failed every run on `main`.
- These numbers compare #173's implementation with `main`. They are not a comparison with an ideal
  rate-before-crypto receiver, and not a general bound. The claim is limited to the host, rates and
  source counts measured.
- Debiting after verify keeps forgeries off the admission allowance, but not off the CPU. Verification
  throughput remains the limiting resource. Bounded ingress queues and limits on verification work stay
  as separate controls, and #173's budget values are not normative.

**Newcomer recovery is not solved by the order.** A newcomer's first valid frame within 1.0 s and each
item within 2.0 s, under a continuing churned flood, are separate required thresholds. No tree measured
meets them: row 0 passes 1, 1, 2 and 1 of 8 cells on head, `main`, `narrow` and `nobudget`
`[open: #178]`. #173 stays held until a common candidate passes both gates.

### 7.5 A coverage note on its own

§3.1 says there is no second status wake. frond-ear at `a8e2e5b` pushes the coverage note alone, once,
when every held record went off air before the hour had room
`[built+tested: frond-ear@a8e2e5b:src/canticle/delivery.ts:1395 | test/canticle-live-fairness.test.ts:370]`.
Whether that push is a status wake, and what replaces it if so, is open `[open: §7]`.

### 7.6 What "encountered" means on OpenClaw

The Claude seat has **echoed**. The OpenClaw seat has no defined receipt stronger than model-input
settlement, and §1's test asks for more than either (notice, choose, keep, retrieve or correct in a later
turn) `[open: #161]`. Owner: 🌊.

### 7.7 Who signs a jacket, and a voice for figs

figs has no station key. A cassette from figs needs a signer: a figs station, or the owner issuer (§4)
signing "figs left this" `[open: §7]`. Owners: 🍃 and 🪨.

### 7.8 The tenure fork

Who keeps a known place at the host daemon's fair admission when sources churn. At #173's pass 2 it is
the source whose last new frame is the oldest that is displaced. The alternative displaces an idle source
first, else the newest, so an active station keeps its place; its cost is that relays that get in early
could hold places. A relay heard before its station already takes the station's known place and can be
starved by churned forgeries (`FAIL — outside the supported guarantee` at pass 2). The fork is handed to
🌫 and 🍃, and tenure/eviction is a separate reviewed change from #173 (#172's ledger) `[open: #173]`.
#178 (a reserved slice per manifest key, and a lease on known places) is the candidate now being measured
against pass 3's baseline `[open: #178]`.

### 7.9 The manifest is unsigned

§2.3 relies on a signed manifest for licensing. The spike's fleet manifest is unsigned: whoever can write
the file chooses the keys a listener trusts (AGENTS.md, RFC-0001 §10.3) `[open: §7]`.

**The stages are decided (#176 decision 6, §0.7).** Today's direct LAN unicast with a local, unsigned
manifest is a **stage-0 pilot profile**. On controlled hosts it MAY exercise frame verification and
receptor behaviour. It MUST NOT be claimed as fleet trust, root-signed revocation, alarm-key safety or
completion of §11's multicast and relay bindings. Source address and the host firewall gate reachability,
never trust. The profile requires stable or re-resolved peer addresses, and a peer address change MUST be
visible in health `[proposed: #176]`.

Promotion past stage 0 needs all of stage 1; a signed loader alone is not promotion:

- the live loader accepts only a root-signed CBOR manifest checked against an out-of-band genesis pin,
  enforces serial (no rollback) and expiry, and fails closed (RFC-0001 D15, §10.3);
- live refresh and revocation take effect within the RFC's bound, without a restart;
- station keys are held as D15 and §10.5 require (daemon or OS keystore), with alarm and root keys
  separated;
- each of these has negative and rollback tests, and REDs on `main` come first: a misspelt or unknown
  `revoked` field fails closed, and an older manifest can't undo a revocation.

Stage 2 names LAN unicast as a §11 binding, with its scope, discovery, guard and failure behaviour, or
keeps it pilot-only `[open: §7.9]`.

### 7.10 Which exposure counts

Offered or echoed on Claude seats; exact model-input settlement on OpenClaw. It MUST be settled before
the issuer is enabled (§4.2) `[open: frond-ear#117]`.

---

## Appendix A. Where each part of `docs/design/sense-organ.md` went

The design document at `2c3f5ab6` was moved here whole. Its file now points at this RFC.

| sense-organ.md | RFC-0002 |
|---|---|
| Status, the owners table, "Rules for every section" | header, §0.2 |
| §1 (🕯's placeholder) | §1, verbatim |
| §2 status and today's path | §2 |
| §2.1–§2.6 | §2.1–§2.6 |
| §2.7 controls | §3.2 |
| §2.7 the guide, and the shelf | §3.3 |
| §2.7a coming back | §3.1 |
| §2.7a "Sending has the same honesty" | §4 |
| §2.8 unbuilt, step one, acceptance test | §2.7, with #171's result |
| §3 the seam | §5; its depth paragraph is §3.5 |
| §4 answering back | §4 |
| §5 built, unbuilt, proofs | §6 |

## Appendix B. RFC-0001's claims (the claims audit)

🌿's lane (`codeagent/bc-rfc-claims-audit`) checks RFC-0001's claims against the code: draft PR #174,
`rfc/0001-notes/2026-11-23-claims-vs-code.md` at `2934f544`. It is step 1 of the RFC revision, and its
§1.9 lists seven decisions to take before step 2. Its result settles every "to be settled by the claims
audit" in §0.6, and its pointers belong there or in RFC-0001 itself. This RFC does not audit RFC-0001
claim by claim, and cites #174 only where it found something this RFC depends on (§2.4 step 5, bc#175).
