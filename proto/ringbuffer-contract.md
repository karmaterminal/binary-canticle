# Binary Canticle — minimal ringbuffer contract (draft)

*Draft. 2026-05-05. Purpose: define the smallest bounded shared-medium substrate that can carry `station:stream` traffic without deciding meaning.*

---

## 0. Design intent

This contract is intentionally small.

The ringbuffer exists to do four things:
1. **append** frame receipts under `station:stream`
2. **read** recent receipts back in order
3. **forget on purpose** by explicit bounds/policy
4. **expose raw receipts and cursors, not receptor meaning**

If it starts classifying threat, consensus, importance, posture, or truth, it has already become too fat.

## 1. Core shape

### 1.1 Addressing

The canonical carrier is:
- `station`
- `stream`

Together they form the routing/read key: `station:stream`.

### 1.2 Frame receipt record

Minimum canonical receipt record:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `station` | string | yes | Source station identifier. |
| `stream` | string | yes | Stream within station. |
| `seq` | uint64 | yes | Monotonic within `station:stream`. |
| `ts` | timestamp | yes | Source timestamp. |
| `observed_at` | timestamp | yes | Local append/receipt time. |
| `ttl_ms` | uint32/null | no | Optional freshness/retention hint. |
| `expires_at` | timestamp/null | no | Explicit expiry if carried/computed. |
| `content_type` | string | yes | Opaque payload type hint. |
| `payload` | bytes/blob/ref | yes | Opaque body or externalized body reference. |
| `digest` | string | yes | Integrity/dedup key for the carried body+envelope. |
| `receipt_of` | string/null | no | Digest/frame id this receipt refers to. |
| `parent_digest` | string/null | no | Parent/lineage reference when relevant. |

Notes:
- `payload` is opaque here.
- `content_type` helps carriage, not ontology.
- `seq` is a ringbuffer ordering fact, not a judgment.

## 2. Operations

The minimal operation set is:

### 2.1 `append(frame)`

Append one frame receipt into the ringbuffer for its `station:stream`.

Returns:
- accepted / rejected
- assigned or confirmed `seq`
- current head/tail window metadata
- duplicate/no-op status when applicable

### 2.2 `replay(station:stream, since_seq|since_ts, limit)`

Return recent frames for a `station:stream` in order.

Returns:
- ordered receipt list
- truncation flag if requested history has already fallen off
- current replay bounds (`head_seq`, `tail_seq`, or equivalent)

### 2.3 `tail(station:stream, limit)`

Return the most recent `N` frames for a `station:stream`.

Returns:
- ordered tail slice
- current bounds

## 3. Invariants

### 3.1 Bounded

The ringbuffer MUST drop old frames on explicit size/age bounds.

Forgetting is not a bug or mystery. It is part of the contract.

### 3.2 Replayable

Recent frames MUST be readable back in order within the surviving window.

### 3.3 Forgettable on purpose

Eviction/expiry MUST be first-class and inspectable.

At minimum, a caller should be able to tell:
- what the current surviving window is
- whether requested history has already fallen off
- whether expiry/depth policy was the reason

### 3.4 Non-interpreting

The ringbuffer substrate MUST expose bytes + receipt facts only.

It MUST NOT:
- classify threat
- decide posture
- decide consensus/accord
- decide importance/truth
- emit quarantine/clarion semantics by itself

Those belong above the ringbuffer.

## 4. Idempotency / dedup

`append(frame)` SHOULD be idempotent.

Minimum acceptable dedup key:
- `digest`

Possible stronger key where available:
- `(station, stream, seq)`

Duplicate append behavior MUST be explicit:
- accepted-as-existing / no-op
- not silently double-written

## 5. Eviction semantics

Eviction SHOULD be explicit by policy, not inferred from absence alone.

Minimum policy surfaces:
- max age
- max depth per `station:stream`
- optional max bytes / store budget

Minimum read-side signals:
- `truncated: true|false`
- surviving lower bound (`oldest_seq` and/or `oldest_ts`)
- surviving upper bound (`newest_seq` and/or `newest_ts`)

## 6. What the substrate may expose

Allowed:
- raw receipt records
- append acceptance/rejection
- duplicate/no-op result
- head/tail window metadata
- replay truncation metadata
- simple cursors/bookmarks

Not allowed as ringbuffer truths:
- receptor judgments
- atmosphere summaries
- quarantine state
- clarion/adrenaline state
- importance ranking
- control-plane commands

## 7. Distillation

One dumb frame type.
Three dumb operations.
Four hard invariants.

Small enough to carry Canticle traffic.
Too small to become governance by accident.
