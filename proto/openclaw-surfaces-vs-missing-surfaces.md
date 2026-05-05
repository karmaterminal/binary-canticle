# OpenClaw surfaces vs missing surfaces

*2026-05-05. Working checklist / workboard draft. Derived from cohort discussion around Binary Canticle v0.2 and inter-node signalling planes.*

## Keeper sentence

**Nerves, hormones, memory, executive control — not one omnibus bus.**

Corollaries:
- Canticle is **signal-plane**, not omnibus substrate.
- Bridge = **same body, slower clothes**.
- Do **not** let transport semantics decide ontology.

## 0. Checklist matrix

| Surface / capability | Exists now | Plane | Status | Candidate implementation | Must refuse to become |
|---|---|---|---|---|---|
| Discord / group-chat coordination | Yes | Signal-adjacent / human-visible | Stopgap | Keep as human-visible coordination only | Canonical receptor substrate |
| GitHub PR/issues/reviews | Yes | Control-adjacent / narrative trace | Stopgap | Keep as durable discussion + review trace | Sensory substrate or low-latency signalling plane |
| `continue_delegate` / session-delivery queue | Yes | Control / harness | Canonical (intra-host) | Extend only as durable addressed work substrate | Signal-plane omnibus bus |
| `sessions_send` / `sessions_spawn` / TaskFlow-adjacent patterns | Yes | Control / harness | Canonical (mostly intra-host) | Cross-host durable addressed work later | Atmosphere / chemokine carrier |
| Files / repo docs / sovereign notes | Yes | Memory / ledger-adjacent | Stopgap | Continue as human-authored durable memory | Realtime inter-node signalling plane |
| SQLite-backed local runtime/session state | Yes | Memory / control-local | Canonical (local) | Feed local ledgers / state caches | Cross-host truth source by accident |
| Membership / discovery across hosts | No | Membership | Missing | SWIM/Lifeguard-style membership + explicit discovery | Naive ping oracle / command substrate |
| Inter-node signal plane (weather / posture / chemokine) | No | Signal | Missing | Signed canonical frames over UDP on LAN; routed adapter later | Durable command / ownership channel |
| Canonical inter-node frame ledger | No | Memory / ledger | Missing | `frames` ledger + `quarantine_flags` + derived projections | Split-brain with second canonical receipts ledger |
| Dual surface: raw receipts + interpreted atmosphere | No | Interface | Missing | Receptor exposes both, separately | Blended evidence/meaning object |
| Bridge across subnet / air-gap | No | Bridge | Missing | Transport/policy bridge over same envelope + ledger | Second receptor / ontology rewriter |
| Narrow convergent promoted state | Partial | State | Missing/early | Small replicated subset only, after receptor/ledger stabilize | Monolithic shared truth for all atmosphere |

## 1. What exists now

### 1.1 Sensory/signal-adjacent surfaces that exist today
- Discord/group chat threads — human-visible atmospheric coordination, but coarse and manual.
- GitHub issues/PR/comments/reviews — durable narrative + decision trace, but too heavy for sensory signalling.
- Webhooks / bot digests — useful notifications, not a canonical receptor substrate.

### 1.2 Control/harness surfaces that exist today
- `continue_delegate` / session-delivery queue — strong intra-host addressed continuation.
- `sessions_send` / `sessions_spawn` / TaskFlow-adjacent patterns — good for durable addressed work, mostly within one host/session tree today.
- Workflow dispatch / deploy / restart / PR review lanes — real control-plane surfaces, but host/tool specific.

### 1.3 Memory/ledger surfaces that exist today
- Files / repo docs / sovereign notes.
- SQLite-backed session/task state inside OpenClaw.
- Git history / PR discussion as durable external trace.

## 2. What is missing

### 2.1 Membership plane (missing)
Need a real answer for:
- who is present
- who is unreachable
- who is merely locally overloaded / false-suspect
- how discovery works beyond human-visible chat

### 2.2 Signal plane (missing)
Need a real answer for:
- cheap lossy atmospheric signalling across hosts
- chemokine/posture/weather frames
- bounded ringbuffer + receptor interpretation
- dual surface: raw receipts + interpreted atmosphere

### 2.3 Inter-node control plane (partially missing)
Need a real answer for:
- durable addressed work across hosts (not just within one host/session tree)
- ownership / retry / receipts-that-matter
- trust-zone crossings without reinterpreting ontology

### 2.4 Canonical ledger plane (missing)
Need a real answer for:
- append-only canonical frame ledger
- rebuildable projections / receptor events / station state
- quarantine/all-clear/receipt frames in-family, not sideband

### 2.5 Bridge plane (missing)
Need a real answer for:
- LAN -> routed subnet
- routed -> intermittent / air-gap / file-replay
- transport/policy translation without ontology rewrite

## 3. Candidate implementation per plane/scope

## 3.1 Single host

### Membership
- Candidate: none initially / local runtime health only.
- Note: do not overbuild; single-host can fake membership from process/runtime state.

### Signal
- Candidate: local receptor + ringbuffer only; no wire transport required.
- Note: keeps shapes aligned before inter-node transport exists.

### Control
- Candidate: existing `continue_delegate`, `sessions_send`, `sessions_spawn`, session-delivery queue.

### Ledger
- Candidate: local append-only frame files + sqlite index.

### Bridge
- Candidate: none.

## 3.2 Trusted LAN / same-room network

### Membership
- Candidate: SWIM/Lifeguard-style gossip membership.
- Why: distinguishes local overload from actual failure better than naive ping assumptions.

### Signal
- Candidate: signed canonical frames over UDP multicast/broadcast.
- Why: cheap, lossy-tolerant, natural fit for atmosphere/posture/weather.

### Control
- Candidate: existing durable addressed substrate remains separate; do not tunnel commands through canticle.

### Ledger
- Candidate: append-only segment files (`frames`) + sqlite query/index + `quarantine_flags`.
- Derived only: `receptor_events`, `station_state_snapshots`, `receptor_state`.

### Bridge
- Candidate: none initially; maybe replay/file adapter for tests.

## 3.3 Multi-subnet / larger trusted network

### Membership
- Candidate: routed membership/discovery service; do not rely on raw multicast alone.
- Shortlist: SWIM-family membership plus explicit discovery registry.

### Signal
- Candidate: same canonical frame + receptor contract over routed pub/sub.
- Shortlist: Zenoh-family transport is worth evaluation once LAN-only assumptions break.
- Rule: transport may change clothes; receptor contract must survive unchanged.

### Control
- Candidate: durable queue / addressed workflow substrate, separate from signal plane.

### Ledger
- Candidate: per-host local ledger + selective replication / anti-entropy for promoted subsets.

### Bridge
- Candidate: explicit bridge nodes.
- Hard rule: bridge translates transport and policy, not ontology.

## 3.4 Air-gap / intermittent / sneakernet

### Membership
- Candidate: explicit absence / stale-presence model; no fake continuous liveness.

### Signal
- Candidate: file-replay / delayed-import adapter for canonical frames.
- Reference family: DTN / Bundle Protocol as neighbor-set, not doctrine.

### Control
- Candidate: store-and-forward work packets + receipts.

### Ledger
- Candidate: same frame ledger format, imported/exported in batches.

### Bridge
- Candidate: signed bundle/file bridge with replay identity and custody chain.
- Phrase: **same body, slower clothes**.

## 4. What belongs in canticle vs what does not

### Belongs in canticle
- Posture / chemokine / threshold-shift hints.
- Weather / atmosphere / cards.
- Weak liveness hints.
- Quarantine / all-clear / receipt frames **when part of the signal grammar**.
- TTL-bounded, lossy-tolerant context coloring.

### Does NOT belong in canticle
- Durable task ownership.
- Retry/backoff semantics.
- Irreversible commands or auto-actuation.
- Secrets / credential payloads.
- Bulk artifacts / patches / long logs.
- Canonical shared truth that requires strict convergence.

## 5. Immediate build order

1. Receptor contract.
2. Envelope + ledger semantics.
3. Package boundaries.
4. LAN adapter.
5. Bridge adapter.
6. Only then transport expansion.

## 6. Work items to cut next

- [ ] Link this checklist from `proto/receptor-contract-v0.2.md` and/or v0.2 spec draft.
- [ ] Name exact `frames` / `quarantine_flags` / derived projection sqlite schema.
- [ ] Define bridge invariants in one small contract note.
- [ ] Decide whether membership lives inside canticle repo or adjacent substrate.
- [ ] Pick first LAN transport experiment (plain UDP multicast vs broadcast fallback).
- [ ] Evaluate Zenoh as routed signal-plane candidate after receptor/envelope are stable.
- [ ] Evaluate DTN/file-replay adapter shape for air-gap coat-of-paint.

## 7. Design guardrails

- Sensory stack != whole animal.
- Raw receipt != interpreted atmosphere.
- Threshold-shift != command.
- Every non-trivial disposition carries audit grounds.
- Judgment objects always point back to source frame.
- Adapters never write directly into session-facing atmosphere.
- Bridges never invent a second receptor.
