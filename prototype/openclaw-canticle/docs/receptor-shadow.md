# Receiver-policy shadow preview (#120)

This is a runnable **offline experiment**, with a versioned JSON fixture contract and a pure TypeScript
reducer. It lets a prince or implementer inspect which already-admitted items a bounded policy would
surface, when a batch would become due, and why a candidate was suppressed. OpenClaw and frond-ear can
use its fixtures and semantics as a donor. Neither harness installs or invokes it today.

It does not open a socket, read a session transcript, change configuration, inject text, create a turn,
publish, or save a profile. The live plugin's exact-session read ceilings and route proofs remain separate;
this is no alternative access path around #145. A fixture's `admission: "verified"` is an **assumption
supplied by the fixture author**, not a cryptographic proof produced by the preview.

## Run it

From `prototype/openclaw-canticle/`, with the Node version used for plugin tests:

```sh
node src/receptor-shadow-cli.ts < examples/receptor-shadow.json
node --test test/receptor-shadow.test.ts
```

The committed example contains invented weather notices and fake key identifiers. Continuous chatter
reaches `max_wait` at fixture time 1010000; a duplicate does not postpone the batch. A later mute cancels
the new pending item, unmute does not replay it, and a receiver gap leaves an unknown current view.
Output contains metadata, hashes and reasons, **never the notice bodies**. It is a policy preview, not a
receipt that anybody heard a notice. No clock runs while this command is idle; all times are fixture input.

The CLI accepts only stdin and caps input at 1 MiB. A timeline has at most 2,048 events, and the accumulated
compact step reports are capped at 4 MiB (pretty-printing and the final view add overhead). Split a large
experiment into smaller fixtures. This deliberately does not read live configuration or station files.

## Contract

Both fixture and policy use `v: "canticle-receptor-shadow/1"`. The fixture has `policy` and `events`.
Unknown fields in the shadow policy or event envelope are rejected. Receptor records retain their existing
record-v1 parser's extension behavior; no emitted-record or wire format changes are introduced.

### Operator ceiling and receiver request

| Field | Meaning and bound |
|---|---|
| `ceiling.revision`, `profile.revision` | Positive integers. Changing either object requires increasing its own revision. |
| `ceiling.sources[]` | At most 64 explicit grants: exact `keyId` (16 lowercase hex digits) **and** `station`, with allowed `streams`, `classes`, `scopes`. |
| `ceiling.selfKeyId` | Optional known local signer. Its items are excluded. Omitting it does not discover the receiver's identity. |
| `ceiling.ambient`, `ceiling.wakePreview` | Both default false. Fixture permission for silent presentation preview and, separately, hypothetical alarm-request preview. Neither grants any live capability. |
| `ceiling.freshnessMs` | At most one hour, default 120,000 ms. Additional age-since-first-hearing ceiling, never an extension of receptor `local_expiry_at`. |
| `ceiling.maxBatchItems`, `maxBatchBytes` | At most 5 items and 1,536 source-body bytes; those are also defaults. Host wrapper/prompt bytes are **not** measured here. |
| `ceiling.maxPendingItems`, `maxPendingBytes` | At most 256 items and 65,536 body bytes, defaults 64 and 65,536. Also cap the retained current-view pool. |
| `ceiling.maxBatchesPerHour` | At most 120 preview batches in a rolling hour, default 12. A local fixture budget, not a session/host/token wake budget. |
| `ceiling.minBatchIntervalMs` | At least 5,000 ms, default 5,000. Bounds successive preview batches. |
| `profile.id` | Local fixture label, **not** an OpenClaw or Claude session identity. It cannot change within a run. |
| `profile.tune` | Default empty. Existing `station:stream` grammar: exact names, `*`, and terminal stream `.*`. `town.*` includes `town.weather`, not `town`. |
| `profile.classes`, `profile.scopes` | Optional narrowing filters. Missing means any value already granted by the ceiling; an empty list matches nothing. |
| `profile.mode` | `ringbuffer_only` (default) or `ambient`. `ambient` requires `ceiling.ambient`. |
| `profile.wakeOnAlarm` | Default false. Also needs ambient mode and `ceiling.wakePreview` for a hypothetical request. |
| `profile.freshnessMs` | Default 120,000; intersects the ceiling. Tightening shortens observed-item freshness; later broadening cannot restore it. |
| `profile.batch` | `count` (default 3), `quietMs` (5,000), `maxWaitMs` (30,000), `maxItems` (5), `maxBytes` (1,536), `perSource` (2). |

The effective policy reports the intersection of signer grants, station/stream tuning, classes, scopes,
and numeric caps. Matching a station name cannot add a signer. A profile cannot broaden the operator's
scope; wildcard tuning remains inside fixed signer grants. The supplied ceiling itself is not an
installation, manifest-capability check, or proof of a reader's authority.

### Timeline and decisions

Every event has an explicit, nondecreasing integer `at` in receiver-clock milliseconds, plus `op`:

| Operation | Additional fields and effect |
|---|---|
| `record` | `record`: an admitted v1 `frame`; optional `snapshot: true`. Validates required metadata and inline body length/hash, then evaluates the policy. No URL is fetched for `body_ref`. |
| `retract` | `record`: v1 `retract`. Removes the observed target and pending presentation. Authentication and sticky withdrawal of an unobserved target belong to the admitting receptor, not this reducer. |
| `health` | `health`: `ok`, `gap`, `disconnected`, or `unknown`. Non-OK cancels pending work and marks retained observations carried. `ok` alone cannot reconfirm their truth. |
| `mute`, `unmute` | `keyId`: exact signer or `*`. Mute cancels matching pending work. Unmute permits future distinct items without replaying cancelled ones. |
| `cancel` | Permanently cancels this preview's presentation queue; it does not claim the station ceased or the receiver forgot prior text. Start a fresh fixture for a new experiment. |
| `policy` | `policy`: a replacement policy with the same receiver label and correctly advanced revisions. Revocation, narrowing and capacity changes reconcile pending work immediately. |
| `tick` | Advances evaluation time without any input frame. Necessary to preview a deadline when the fixture is otherwise quiet. |

A batch becomes due at the earliest of **N distinct pending identities**, **a quiet interval since the
last distinct pending arrival**, or **maximum wait since the oldest pending arrival**. It also respects a
5-second minimum coalescing window, inter-batch cooldown and the rolling-hour cap. `dueAt` records the
earliest trigger even when evaluation occurs later. `batch_waiting`, `coalesce_minimum`, `batch_cooldown`
or `batch_hour_budget` explains a hold; maximum wait is not a promise of delivery through mute, expiry,
health failure, exhausted budget, or an absent clock caller.

A duplicate does not add an item, spend a batch, reset quiet/max-wait, or resurrect cancelled work.
Snapshot, `dedup: resurfaced` and refresh records are read-only. A new valid value for the same signer's
stream/state key withdraws its older pending value before a due flush. An unrelated new frame cannot
postpone a deadline that was already due. A replacement keeps the pending key's original wait start
(`queuedAt`) but updates its last distinct change (`changedAt`): continuous weather changes cannot reset
maximum wait, and only the latest value is offered. Expiry and control events take priority over presentation at
the same event time; input order disambiguates separate events with identical timestamps.

Batch selection rotates among retained signers, one item per signer per round, within item, byte and
per-source caps. **This is batch-selection fairness, not admission fairness.** A busy source can fill the
shared current-view pool before another source arrives; even surfaced items occupy that pool until
expiry. The new item then receives `current_capacity`. Admission reservations, weighted fairness and
the RFC's rolling-ten-minute AGC share are not implemented. Nothing is silently evicted to imply a
stronger guarantee. Identity tombstones are capped at 4,096 and retained through their source expiry;
new identities are refused at the limit rather than forgetting unsettled duplicates.

## Current sensation, receipt, and chosen retention

`view.current` contains fresh, policy-visible observations that were reconfirmed while receiver health was
OK. `view.carried` contains still-fresh earlier observations whose continuity is unknown. A gap is not
evidence that a station disappeared. This reducer does not model a complete join-snapshot transaction;
it requires explicit item reconfirmation and never infers absence from a partial fixture.

`view.recent` holds at most 128 **metadata** receipts. A historical `received` entry is not a claim that the
item is still current, nor that a prince read it. Expiry removes current authority and pending work; it
does not purport to erase text previously placed in a session or undo its influence. There is no elected
retention store, semantic index, summary cache, transcript reader, or beacon synthesis in this experiment.
Operator revocation removes related metadata from the active receipt view; earlier exported previews
remain earlier files, not revocable contexts.

## Hypothetical alarm request, with no dispatcher

`wouldSurface` means a metadata batch would be offered by this **receiver-policy simulation**.
`wouldRequestWake` is true only when both fixture elections allow it and the batch includes an `alarm`
with hop 0, `wake_derived: false`, source age at first hearing at most 120 seconds (using the supplied
clock offset), and at most 120 seconds since hearing. Source issue time, offset, first-hearing age and
local expiry remain in each item receipt. Unknown/future source age fails this preview predicate.
Public-scope frames and known aspects never qualify, even if the fixture grants their read scope:
`lens.*` stream names and any non-null receptor `lens` ID (including 0) exclude a request. Lens metadata
is retained in receipts, with `public_scope_never_wakes` or `aspect_stream_never_wakes` as appropriate.

That request is **not proof of a protocol-permitted wake**. Signature admission, alarm capability,
proofreading, independent session/host/token budgets, breaker allowance, sandboxing, taint handling,
sealed bootstrap and an actual exact-session route are not established by a fixture. Every batch and
view has `dispatch: "none"`, with `wake_not_implemented` and the other execution limits reported.
The initial live deployment remains silent-only under RFC-0001 §§14.9–14.10 and §14.18.9.

## Reuse and remaining work

`createShadow(policy)`, `advanceShadow(state, event)`, `inspectShadow(state)` and `previewShadow(fixture)`
are the public offline entry points in `src/receptor-shadow.ts`. The reducer clones inputs; identical
state, event and time yield identical results. The state is in-memory inspection data, not a supported
durable ledger or restart/install format. No binding, tool, runtime config or session path imports it.

This covers a small #120 donor contract, not full RFC §14.6 policy parity. Full lineage-root salience,
desensitization, circuit breakers, modulation, drift-safe host scheduling, bounded host prompt wrapping,
admission fairness, exact session authority and live profile lifecycle remain separate work. The queued
objects are metadata; the tool does not render or sanitize a real prompt. Consult RFC-0001 §§14.2–14.6,
§§14.9–14.10, §14.18 and §16.6 before integrating either harness. Tests establish the fixture behavior
only; fleet installation and a real received batch still need their own receipts.
