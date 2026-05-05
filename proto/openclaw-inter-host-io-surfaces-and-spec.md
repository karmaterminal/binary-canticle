# OpenClaw inter-host I/O today, interface surfaces, and high-level spec

*2026-05-05. First pass. Grounded against local OpenClaw docs/source and current cohort practice.*

## Purpose

Answer three questions cleanly:
1. **What inter-host I/O exists today in OpenClaw / Claude-shaped use?**
2. **Where is the interface surface actually located?**
3. **What must/should the larger-body spec support next?**

This is not the Binary Canticle protocol spec itself. It is the **current-surface / desired-surface map** for inter-host coordination.

## 1. What exists today

## 1.1 Same-host session/control surfaces exist and are real

These are load-bearing today, but **same-host scoped**:

- `continue_delegate()`
  - spawns a fresh subagent and returns its completion into the dispatching session or another **same-host** addressable session
  - uses the local `session-delivery-queue` substrate for targeted returns
  - explicitly **does not** route the original task body into a live remote session
  - docs/source make the scope explicit: `targetSessionKey` is same-host today; cross-host publish/stream is future work

- `sessions_send`
  - sends a message to another visible session and can wait for a reply
  - valid for visible sessions within the gateway's session namespace
  - not a cross-host federation primitive

- `sessions_spawn`
  - creates isolated subagent or ACP harness sessions
  - gives local orchestration and thread-bound work sessions
  - still a local gateway/session-tree primitive, not a host-federated one

- `session-delivery-queue`
  - local-gateway queue keyed by `sessionKey`
  - durable and restart-aware
  - **not exposed as a cross-host wire contract today**

## 1.2 Inter-host coordination exists mostly through adjacent surfaces

Today the fleet does coordinate across hosts, but mostly through tools built for other jobs:

- Discord / chat channels
- GitHub issues / PRs / comments / reviews
- git branches / commits / pushes
- SSH / filesystem / repo movement
- workflow dispatch / deploy / restart actions
- webhooks / digests / bot summaries

These are real. But they are **stopgap inter-host I/O surfaces**, not a coherent sensory substrate.

## 1.3 Claude / frond-scribe case today

In the `@frond-scribe` / Claude-shaped case, the effective inter-host interfaces are usually:
- channel-facing message surface (Discord)
- GitHub artifact surface (issues/PRs/docs)
- repo/file surface
- occasionally worktree/branch boundaries

That means Claude/frond-scribe can coordinate **across hosts socially and artifact-wise**, but not through a native cross-host session-addressed OpenClaw substrate yet.

## 2. Where the interfaces actually are today

## 2.1 Interface surfaces, by plane

### Control/harness plane
Actual interfaces today:
- `continue_delegate`
- `sessions_send`
- `sessions_spawn`
- workflow/job dispatch
- issue/PR assignment or task statements in GitHub

### Signal/sensory plane
Actual interfaces today:
- Discord/chat prose
- bot digests / webhook notifications
- human-visible ambient updates

This plane is **not yet formalized** as a proper OpenClaw inter-host protocol.

### Ledger/memory plane
Actual interfaces today:
- repo files / markdown docs
- git history
- issue/PR history
- local gateway/session state

### Bridge plane
Actual interfaces today:
- SSH
- git remotes/branches
- chat channels
- workflows/webhooks

These bridges move information, but they also currently smuggle ontology, which is why the body still feels partly manual.

## 2.2 The key negative finding

**OpenClaw today has strong same-host continuation/session machinery, but no first-class host-federated signal/control substrate.**

That is the seam Binary Canticle and related work are trying to name cleanly.

## 3. What the larger body must support

## 3.1 MUST

### MUST 1 — Keep planes separate
A larger body MUST distinguish at least:
- membership/liveness
- signal/sensory
- control/harness
- ledger/memory
- bridge/federation

One omnibus bus should not own all five.

### MUST 2 — Make same-host vs cross-host scope explicit
Every interface MUST say whether it is:
- local session
- same gateway host
- bridged cross-host
- air-gap / delayed import

No hidden federation assumptions.

### MUST 3 — Preserve signal-plane anti-coercion
Inter-host signal surfaces MUST preserve:
- receive does not compel act
- threshold-shift != command
- transport does not author meaning
- adapters/bridges do not bypass receptor judgment

### MUST 4 — Keep raw receipt separate from interpreted atmosphere
Inter-host signal handling MUST expose:
- raw receipt / frame / evidence
- interpreted atmosphere / local judgment

These may be linked; they must not collapse into one blended authority.

### MUST 5 — Preserve one judgment core
Bridges may translate transport and crossing policy.
They MUST NOT reinterpret frames into a different judgment grammar.
Otherwise the bridge becomes a second receptor and the body loses one truth about meaning.

### MUST 6 — Make auditability first-class
Any non-trivial disposition in the inter-host path MUST carry boring explicit grounds:
- observed
- consulted state
- rule fired
- effect

### MUST 7 — Support bounded agentable questions
The larger body MUST be expressible as bounded artifacts and lanes, not only as prose thread intuition.
Otherwise collaboration remains memory-shaped.

## 3.2 SHOULD

### SHOULD 1 — Start with existing strong same-host primitives
The next design should reuse the lesson already present in OpenClaw:
- agent owns intent
- tool owns mechanics
- substrate owns durability

### SHOULD 2 — Begin with a LAN-trusted v0 before wider federation
A sane order is:
1. same-host clarity
2. trusted LAN signal-plane
3. routed multi-subnet bridge
4. air-gap/delayed-import coat-of-paint

### SHOULD 3 — Treat canticle as signal-plane, not omnibus substrate
Binary Canticle should remain mostly:
- posture/weather/chemokine
- receptor-mediated field shifts
- lossy atmosphere

It should not quietly become durable task ownership or command transport.

### SHOULD 4 — Use an append-only ledger with rebuildable projections
Inter-host signal receipts should ideally land in:
- canonical raw ledger
- derived receptor/projection/cache layers

Truth and convenience should stay distinct.

### SHOULD 5 — Support explicit bridge coats
The same body should be able to wear:
- UDP multicast/broadcast on a clean LAN
- routed pub/sub or mesh transport later
- file-replay / store-forward / air-gap bridge later

Same body, slower clothes.

## 4. What it should probably look like

## 4.1 Practical layered answer

### Layer A — wire / transport
Small signed envelopes.
Transport-specific, replaceable, intentionally stupid.

### Layer B — receptor / judgment core
Deterministic interpretation:
- verify
- classify
- threshold/modulate
- place in ringbuffer/ledger
- emit judgment + state delta + receipt plan

### Layer C — interface / agent-facing surface
Expose to sessions/agents:
- raw receipts
- atmosphere / local state
- ringbuffer queries
- quarantine view
- maybe A2A-card-like projections as views, never as truth source

### Beside, not inside, the above
- control/harness plane for durable addressed work
- ledger/memory plane for durable truth + promoted state
- bridge plane for cross-scope transport/policy translation

## 4.2 Current gap statement

The missing inter-host interface today is not “a better chat channel.”
It is:
- a named signal-plane surface
- a named receptor contract
- a named ledger/projection discipline
- a named bridge contract

## 5. Candidate near-term objective

Create a formalized artifact bank and issue stack that lets us ask, per surface:
- what exists now
- what plane it belongs to
- whether it is canonical / stopgap / missing
- candidate implementation
- what it must refuse to become

Then hang research / code-agent / implementation lanes off that substrate.

## 6. Suggested next artifacts for this specific question

1. `proto/openclaw-surfaces-vs-missing-surfaces.md`
2. `proto/INDEX.md`
3. `proto/v0.2-workboard.md`
4. `proto/receptor-contract-v0.2.md`
5. issue tracker / integration issue linking the above

## 7. Keeper lines

- **Nerves, hormones, memory, executive control — not one omnibus bus.**
- **Wire stupid / receptor smart / interface normalized.**
- **Bridge translates transport and policy, not ontology.**
- **Receive does not compel act.**
- **Raw for truth, atmosphere for use, never confuse the two.**
