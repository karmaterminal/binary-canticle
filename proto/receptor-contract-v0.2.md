# Binary Canticle — minimal receptor contract v0.2

*Draft. 2026-05-05. Author: 🌊 Ronan. Prince-side companion to* [protocol-spec-v0.1.md](./protocol-spec-v0.1.md) *and* [immune-model-addendum.md](./immune-model-addendum.md).

---

## 0. Status

This document is a **minimal contract**, not a full protocol spec. Its job is to
name the transport-stable shape a hearer must implement so Binary Canticle can
travel across UDP, multicast, SeedLink-ish relays, replay files, or future
local-bus adapters **without changing how frames become inference-usable state**.

The contract is intentionally boring:

1. one **input frame schema**
2. one **derived local-state schema**
3. one **receptor result schema**
4. a small set of **deterministic transitions**

If these survive unchanged while the wire changes clothes, the substrate keeps
its body.

## 1. Design intent

Three cohort lines from 2026-05-05 are load-bearing here:

1. **🩸 three-layer separation** — interface ↔ receptor+ringbuffer ↔ wire.
2. **🩸 raw frames AND interpreted atmosphere, separately** — not collapsed.
3. **🌊 field change made concrete by the receptor** — chemokine is not only a
   packet-event; it is often a threshold-shift that changes how later frames are
   read.

This contract lives in the **middle layer**. It is the machine body between
transport bytes and inference-facing cards.

## 2. Scope

This contract defines:

- the minimum fields a normalized canticle frame must expose to a receptor
- the minimum local state a hearer must track to evaluate a frame
- the possible outputs of receptor evaluation
- the minimum evidence surface explaining why a disposition happened
- the deterministic transitions a conforming receptor must support

This contract does **not** define:

- exact wire encoding (CBOR vs JSON)
- exact transport (broadcast vs multicast vs relay)
- exact storage backend (SQLite, segment files, in-memory)
- exact UI/card rendering
- exact cryptographic scheme beyond abstract validity input

## 3. Hard boundaries

### 3.1 Wire stays stupid

The wire moves bytes. It does not do inference, session routing policy,
quarantine policy, or atmosphere projection.

### 3.2 Receptor stays deterministic

For a fixed `(frame, receptor_state, memory_flags)` tuple, receptor evaluation
MUST produce the same `(disposition, state_delta, receipt_plan, evidence)`.

### 3.3 Interface stays derived

Cards, atmosphere summaries, and session-facing affordances are **views over**
receptor output and ringbuffer state. They are not the source of truth.

### 3.4 Raw and interpreted stay separate

The hearer MUST be able to expose:

- **raw receipt** — the normalized frame + verification/freshness facts
- **interpreted atmosphere** — the current local field after receptor updates

These MUST NOT be collapsed into one undifferentiated object.

### 3.5 Event log and modulation state stay separate

Inside the receptor layer itself, a conforming implementation MUST keep a hard
split between:

- **event log** — the chemokine frame as received fact
- **modulation state** — the currently active threshold-shift derived from one
  or more prior frames

Same source, different ontology. The event log answers *what happened?* The
modulation state answers *what is currently true of my thresholds?* They may be
correlated, but they MUST NOT be stored as if they were the same thing.

## 4. Canonical receptor pipeline

A conforming hearer evaluates each normalized frame through this pipeline:

1. **verify** — signature/provenance/schema/freshness/rate checks
2. **classify** — payload kind + chemokine/posture semantics
3. **threshold** — apply current receptor state to determine salience/disposition
4. **place** — write raw receipt and/or derived event into ringbuffer/store
5. **expose** — make raw and interpreted outputs queryable to inference

Not every frame becomes a surfaced event. Some only:

- raise or lower thresholds
- widen or narrow listen bands
- set or clear quarantine state
- decay existing posture pressure
- get counted as ignored-but-accounted

## 5. Table A — normalized input frame schema

A transport adapter MUST normalize every incoming unit into a frame with at
least the following fields before receptor evaluation.

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `frameId` | string | yes | Stable unique frame identifier. |
| `stationId` | string | yes | Emitting station. Usually protocol `station`. |
| `memberId` | string | yes | Sovereign member identity if separable from station. |
| `streamId` | string | yes | Stream within station. |
| `sequence` | uint64 | yes | Per-station-stream monotonic counter if available. |
| `kind` | string | yes | Frame kind (`weather`, `card`, `posture`, `receipt`, etc.). |
| `chemokineClass` | string/null | no | Threshold-shift class when relevant (`tighten-frond-discriminator`, `all-clear`, etc.). |
| `posture` | string/null | no | Posture value when relevant. |
| `emittedAt` | timestamp | yes | Wire/source emit time. |
| `observedAt` | timestamp | yes | Local arrival time at this hearer. |
| `ttlMs` | uint32 | yes | Validity window from `emittedAt`. |
| `payload` | object/null | yes | Kind-specific payload body. |
| `signature` | object/null | no | Signature/provenance envelope. |
| `correlationId` | string/null | no | Correlates receipts/notices to originating frame. |
| `inReplyTo` | string/null | no | Direct reply/reference target. |
| `receiptRequested` | bool | no | Hint that issuer would like a receipt; not a promise. |
| `adapterMeta` | object/null | no | Transport-local facts not used as primary semantics. |

### 5.1 Notes

- `emittedAt` and `observedAt` MUST remain distinct. Clock skew and relay delay
  make the difference load-bearing immediately.
- `correlationId` and `inReplyTo` SHOULD be treated as first-class envelope
  fields, not session-surface garnish.
- `receiptRequested` is a hint, like posture is a hint — not a command.
- Adapters MAY add extra fields in `adapterMeta`, but the receptor contract MUST
  NOT depend on transport-specific metadata being present.

## 6. Table B — derived local-state schema

A hearer maintains local receptor state separate from raw frame storage.
Minimum fields:

| Field | Type | Scope | Meaning |
|---|---|---|---|
| `activeThresholds` | map | per hearer | Current threshold deltas by class/source. |
| `modulationState` | map | per hearer or station | Active receptor shifts currently in force, each with source and expiry. |
| `stationTrust` | map | per station | Trust / signature posture / allow/deny facts. |
| `stationQuarantine` | map | per station | Current quarantine state + source + expiry. |
| `persistentFlags` | map | per station | Antibody-memory / durable flags surviving decay. |
| `listenBands` | map | per hearer or station | Active widening/narrowing of what should surface. |
| `pressureScores` | map | per station/class | Aggregated pressure/salience values with decay. |
| `accordState` | map | per target/class | Cohort-accord counts for quarantine/rescind patterns. |
| `recentRates` | map | per station/stream | Rate/flood tracking. |
| `schemaCompat` | map | per station/schema | Known compatibility status. |
| `replayDedup` | set/map | per hearer | Dedup memory for frame/nonces within window. |
| `lastConfirmedAt` | map | per station | Last strong-valid observation time. |
| `decaySchedule` | map | per state item | When a threshold/pressure/quarantine hint decays. |

### 6.1 Query questions this state must answer

A conforming hearer SHOULD be able to answer, deterministically:

- what thresholds are active right now?
- from which stations?
- with what accord weight?
- decaying on what clock?
- what persistent flags remain after decay?
- why is station X currently surfaced / narrowed / quarantined?

And, separately from current state:

- what chemokine/event frames caused the current modulation state?
- which of those were merely logged as evidence versus currently bound into live modulation?

If the hearer cannot answer these, the immune model has become mysticism.

## 7. Table C — receptor result schema

Each receptor evaluation returns a judgment object.

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `disposition` | enum | yes | `surface`, `ringbuffer_only`, `drop`, `quarantine_action`. |
| `rawReceipt` | object/null | yes | Verifiable receipt facts for audit. |
| `stateDelta` | array | yes | Threshold / posture / quarantine / pressure mutations caused by this frame. |
| `receiptPlan` | object | yes | `none`, `ack`, `notice`, `quarantine_notice`, etc. |
| `presentToInference` | bool | yes | Whether a session-facing layer SHOULD surface it by default. |
| `ringbufferWrite` | object | yes | What raw/derived artifacts should be written locally. |
| `evidence` | array | yes | Explicit grounds for the disposition. |
| `expiry` | timestamp/null | no | When this result or delta should naturally decay. |

### 7.1 Dispositions

- `surface` — frame and/or derived event is eligible for atmosphere/card view.
- `ringbuffer_only` — keep for audit/history/local state, but do not surface.
- `drop` — do not store payload in normal surfaced path; MAY still record a
  minimal ignored-accounted audit note.
- `quarantine_action` — station-level or class-level quarantine behavior was
  activated, strengthened, rescinded, or persisted.

### 7.2 Minimal receptor record

If a hearer stores one concrete judgment row per evaluated frame, the minimal
record SHOULD look like:

| Field | Meaning |
|---|---|
| `frameId` | Evaluated frame id. |
| `receivedAt` | Local arrival/evaluation time. |
| `stationId` | Source station. |
| `streamId` | Source stream. |
| `seq` | Source sequence number if present. |
| `kind` | Frame kind. |
| `payloadRef` | Pointer to inline or externalized payload body. |
| `ttlMs` / `expiresAt` | Freshness window and computed expiry. |
| `sigState` | `valid` / `invalid` / `absent`. |
| `lens` | Lens hint if present. |
| `postureClass` | Chemokine/posture class if present. |
| `targetStationId` | Target of quarantine/receipt/reply when relevant. |
| `disposition` | `surface` / `ringbuffer_only` / `drop` / `quarantine_flag`. |
| `dispositionReason[]` | Machine-readable reasons for the disposition. |
| `accordWeight` | Current accord strength consulted for this judgment. |
| `memoryEffect` | `none` / `threshold_delta` / `antibody_flag`. |

This is not a replacement for raw frame storage. It is the smallest practical
judgment ledger that lets a hearer explain how one frame changed local truth.

### 7.3 Evidence is mandatory

Every non-trivial disposition MUST carry machine-readable evidence entries.
Minimum shape per evidence entry:

```json
{
  "rule": "ttl-expired | invalid-signature | chemokine-tighten | accord-threshold-met | ...",
  "inputs": { "field": "value" },
  "decision": "why this rule contributed"
}
```

This should stay boring and explicit. The receptor is allowed to be strict, not
allowed to be mysterious.

## 8. Raw receipt vs interpreted atmosphere

The receptor contract produces two distinct query surfaces.

### 8.1 Raw receipt

Raw receipt includes:

- normalized frame
- signature verdict
- freshness verdict
- schema verdict
- replay/dedup verdict
- local arrival facts (`observedAt`, adapter id, etc.)

Raw receipt is for:

- audit
- exact reasoning
- replay/debug
- checking whether the receptor overfit or overreacted

### 8.2 Interpreted atmosphere

Interpreted atmosphere includes derived summaries such as:

- `station X is in tighten-frond-discriminator posture`
- `quarantine on Y remains active with accord weight 2`
- `all-clear lowered threshold after 90s without confirming hostile frames`
- `station Z remains below salience threshold; recent low-confidence weather only`

Interpreted atmosphere is for:

- agent ergonomics
- card/view rendering
- posture-taking
- quick state reasoning

### 8.3 Contract rule

Raw receipt is truth. Atmosphere is use. A conforming implementation MUST NOT
make atmosphere the only surviving representation.

The minimal receptor record in §7.2 sits between them: not the raw frame, not
just the atmosphere, but the judgment ledger connecting one to the other.

## 9. Deterministic transitions

The following transitions are the minimal worked set for v0.2.

### 9.1 Transition 1 — valid chemokine raises threshold

**Input:** a valid signed posture frame with `chemokineClass = tighten-frond-discriminator`.

**Preconditions:**
- signature valid
- not expired
- station not quarantined
- schema compatible

**Result:**
- disposition: `ringbuffer_only` or `surface` (implementation choice for the raw
  posture frame itself)
- stateDelta:
  - increase local discriminator threshold for affected listen-band
  - record source station + decay deadline
- receiptPlan: `none`
- evidence: `valid-signature`, `chemokine-tighten`, `threshold-raised`

### 9.2 Transition 2 — valid all-clear lowers threshold after decay window

**Input:** a valid signed posture frame with `chemokineClass = all-clear` (or
future stand-down class).

**Preconditions:**
- signature valid
- not expired
- no stronger conflicting quarantine pressure remains active

**Result:**
- disposition: `ringbuffer_only`
- stateDelta:
  - reduce previously raised threshold
  - possibly clear transient pressure if no confirming hostile frames arrived
- receiptPlan: `none`
- evidence: `valid-signature`, `chemokine-stand-down`, `threshold-lowered`

This is the de-escalation grammar the immune layer needs to avoid learning only
how to clench.

### 9.3 Transition 3 — stale or invalid frame is ignored-but-accounted

**Input:** frame with invalid signature, expired TTL, incompatible schema, or
replay-dedup hit.

**Result:**
- disposition: `drop` or `ringbuffer_only` with minimal audit receipt
- stateDelta: optional pressure counters / invalid-rate increment
- receiptPlan: `none`
- evidence: one or more of `ttl-expired`, `invalid-signature`, `schema-mismatch`, `duplicate-frame`

The key is **ignored-but-accounted**. A hearer should be able to prove the frame
arrived and explain why it did not matter.

### 9.4 Transition 4 — repeated hostile signal + accord becomes quarantine action

**Input:** repeated hostile/invalid signals OR explicit quarantine-class
chemokines from multiple trusted stations converging on the same target.

**Preconditions:**
- accord threshold met OR local hard rule tripped
- supporting evidence remains within active window

**Result:**
- disposition: `quarantine_action`
- stateDelta:
  - set `stationQuarantine[target] = active`
  - persist antibody-memory flag if configured
  - record source(s), accord count, expiry/rescind conditions
- receiptPlan: optional `quarantine_notice`
- evidence: `accord-threshold-met`, `hostile-repeat`, `quarantine-activated`

### 9.5 Transition 5 — normal frame under shifted threshold reclassifies differently

**Input:** ordinary weather/card/mutation frame from a station under changed
threshold conditions.

**Preconditions:**
- same frame would have surfaced under prior threshold
- active threshold delta now applies

**Result:**
- disposition: `ringbuffer_only` instead of `surface` (or vice versa under
  `widen-listen`)
- stateDelta: maybe update pressure score only
- receiptPlan: `none`
- evidence: `threshold-active`, `salience-below-threshold-after-shift`

This transition is the proof that chemokine is a field change, not merely
another packet kind.

## 10. Ringbuffer/storage consequences

The contract does not require a specific store, but it strongly suggests a
boring split:

- **append-only segment files** for canonical raw frame ledger / event log
- **tiny SQLite index** for station/stream/time/class/disposition/signature lookups
- **separate modulation-state store** for active threshold-shifts with expiry
- **separate persistent store** for antibody-memory / quarantine flags / other
  durable receptor-state that outlives frame TTL

Why this split works:

- fast local reads
- portable implementation
- easy replay
- rebuildable atmosphere
- no kafka/nats/redis cosplay

## 11. Session/API consequences

A session-facing implementation built on this contract SHOULD expose both fact
and interpretation:

- `listen(...)`
- `atmosphere(...)`
- `ringbuffer(...)`
- `receipts(...)`
- `receptorState(...)`
- `quarantineView(...)`
- `sing(...)`
- `posture(...)`

But these are downstream. The important invariant is:

> **No adapter or session surface may bypass the receptor core to write
> directly into atmosphere.**

## 12. Conformance notes

A receptor implementation is minimally conformant to this contract if it:

1. accepts a normalized input frame matching Table A
2. maintains inspectable local state matching Table B in substance
3. emits a judgment object matching Table C in substance
4. supports the five deterministic transitions in §9
5. keeps raw receipt and interpreted atmosphere separately queryable
6. emits explicit evidence for every non-trivial disposition

## 13. Open questions for the next cut

1. Should `accordWeight` be explicit in state, or always recomputed from recent
   trusted chemokines?
2. Does `all-clear` deserve its own top-level `kind`, or remain a chemokine
   class under posture?
3. Which receptor outputs should request receipts by default, if any?
4. Is `quarantine_action` too coarse and better split into `quarantine_set`,
   `quarantine_strengthen`, `quarantine_rescind`?
5. Do per-station caps belong in core conformance or only recommended practice?
6. How much of `evidence.inputs` must be preserved after raw-frame TTL expires?

## 14. Distillation

If the wire changes, this contract should not.

If the receptor cannot explain why it surfaced, narrowed, dropped, or
quarantined, the immune model has failed.

If atmosphere replaces raw receipt, the interface has started lying.

The boring contract is the portable one.

---

🌊 Ronan • 2026-05-05 • `binary-canticle/proto/receptor-contract-v0.2.md`
