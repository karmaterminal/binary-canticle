# OpenClaw vs Binary Canticle — what exists now / what's missing / next build order

*Draft. 2026-05-05. Purpose: practical handoff artifact, not speculative essay.*

---

## 0. One-sentence summary

**Today OpenClaw already has a real control plane. What it does not yet have is a real inter-host sensory stack. Binary Canticle is the proposed sensory stack, designed to sit beside the existing control plane rather than replace it.**

## 1. What exists now

### 1.1 OpenClaw control-plane surfaces (real, useful, shipped)

These already exist and are not hypothetical:

- `continue_delegate` / `continue_work`
- session-delivery queue
- `sessions_send`
- intra-host targeted session routing
- TaskFlow-ish durable handoff / queued work shapes
- local session state / file memory / SQLite-backed stores

**What they are good at:**
- addressed work
- ownership
- durable receipts
- wake-on-return
- retry/continuation behavior
- explicit task routing

**What they are not:**
- cheap atmospheric broadcast
- multi-hearer weather
- signal-plane posture/chemokine layer
- cross-host membership/liveness plane

### 1.2 Human-visible inter-host substitutes (real, but borrowed)

Today inter-host coordination mostly rides borrowed organs:

- Discord
- GitHub issues / PRs / reviews
- webhooks
- ssh / git / files / workflows

They work, but they are **not** a machine-readable sensory substrate.

### 1.3 Local memory / ledger fragments (real, but not unified)

We already have local memory surfaces:
- repo files
- sovereign files
- SQLite / logs / session state
- worktrees / journals

But there is not yet one canonical **inter-node frame ledger** spanning the sensory stack.

### 1.4 Where the interfaces really are today

By plane, the actual interfaces today are roughly:

- **control / harness**
  - `continue_delegate`
  - `sessions_send`
  - `sessions_spawn`
  - workflow/job dispatch
  - issue/PR task statements
- **signal / sensory**
  - Discord/chat prose
  - bot digests / webhook notifications
  - human-visible ambient updates
- **ledger / memory**
  - repo files / docs
  - git history
  - issue/PR history
  - local gateway/session state
- **bridge**
  - SSH
  - git remotes/branches
  - chat channels
  - workflows/webhooks

That is: the fleet already coordinates, but the body mostly speaks by borrowing other organs.

## 2. What is missing

### 2.1 Missing plane: inter-host membership / liveness

We do not yet have a native machine-readable answer to:
- who is present
- who is degraded
- who is maybe unhealthy
- who is merely locally overloaded

This is adjacent to SWIM / Lifeguard / Serf territory, not Canticle proper.

### 2.2 Missing plane: inter-host signal / atmosphere

We do not yet have:
- small signed canonical frames
- a cheap lossy signal plane
- posture / chemokine / weather / weak liveness hints across hosts
- a native inter-host atmospheric layer separate from control

This is the core Binary Canticle target.

### 2.3 Missing organ: canonical receptor core

We do not yet have one boring deterministic body all transports feed:

`frame + receptor_state + memory_flags -> disposition + state_delta + receipt_plan + audit tuple`

Without this, transport choice will author ontology by accident.

### 2.4 Missing canonical ledger

We do not yet have the canonical store shape for the signal stack:
- `frames` as truth of receipt
- `quarantine_flags` as persistent immune memory
- derived `receptor_state` / `station_state` / projections

Right now receipts and interpretations are still scattered across multiple borrowed surfaces.

### 2.5 Missing bridge layer

We do not yet have the thing that keeps the **same body in slower clothes** across:
- LAN
- routed / multi-subnet
- trust gradient
- air gap / sneakernet

## 3. Boundary: what belongs in OpenClaw vs what belongs in Canticle

### 3.1 OpenClaw should continue to own the control plane

OpenClaw is already strong at:
- addressed work
- durable task routing
- wake semantics
- receipts-that-matter
- ownership / retries / continuation lifecycle

Canticle should **not** try to replace those.

### 3.2 Canticle should own the signal plane

Canticle should handle:
- posture / chemokine / threshold-shift hints
- atmospheric summaries / weather / cards
- weak liveness hints
- quarantine / all-clear / receipt frames **as part of sensory grammar**
- short provenance / confidence / lens / TTL
- anything okay with lossy delivery + local receptor interpretation

### 3.3 Canticle must refuse to become

Canticle must **not** become:
- task ownership
- retries / backoff / durable delivery guarantee layer
- command channel implying auto-actuation
- irreversible-action transport
- secret / credential substrate
- bulk artifact / patch / long-log bus
- canonical shared truth that must converge exactly

## 4. High-level spec shape

### MUST
- separate **membership / control / signal / state** planes
- make **same-host vs cross-host vs delayed-import** scope explicit on interfaces
- keep **wire dumb / receptor deterministic / interface normalized**
- canonical **frame envelope** for receipt truth
- canonical **judgment object** for receptor conclusion
- expose raw receipts and interpreted atmosphere **separately**
- keep bridges translating **transport and policy, not ontology**
- keep receipts/quarantine/all-clear in-family as frames
- keep memory surviving TTL only by explicit promotion
- keep no auto-actuation on receive
- keep non-trivial dispositions audit-carried (`observed / consulted_state / rule_fired / effect`)
- support bounded artifact/lane questions rather than myth-sized coordination only

### SHOULD
- start with **same-host clarity**, then LAN, then routed, then air-gap
- use signed UDP multicast/broadcast for the first signal-plane coat of paint
- define receptor contract before transport expansion
- keep executable examples / contract tests as conformance gate
- add routed adapters later without rewriting the body
- support slower-clothes variants for air-gap/store-forward
- keep one integration tracker + small issue stack so the work stays artifact-anchored

### Signal-plane posture that now seems stable
- **heterogeneous payloads yes; heterogeneous ontology no**
- **one boring envelope, three carriage postures**: inline / chunked / referenced
- large bodies should externalize or chunk rather than quietly bloat the signal-plane
- **bridge-forward ≠ hear-and-sing**
- relay should usually be deliberate re-emission with lineage, not blind propagate-on-hear
- signal-plane does **not** owe global convergence
- **clarion/adrenaline is a signal class, not the default weather**
- **attenuation is probably the point, not a bug**

## 5. Next build order

1. **Receptor contract**
   - stabilize the body
2. **Envelope + ledger semantics**
   - make receipt truth and judgment truth explicit
3. **Package / artifact boundaries**
   - only where pressure is real
4. **Single-LAN UDP adapter**
   - first signal-plane transport
5. **Bridge adapter**
   - subnet / relay / air-gap clothes
6. **Transport expansion by scope**
   - only after the body survives pressure tests

## 6. Immediate practical coordination artifacts

These are the collaboration spine, not the protocol itself:

- `proto/INDEX.md` — skeletal map / gap matrix / anti-amorphous surface
- `proto/v0.2-workboard.md` — local workboard / lane map
- `proto/openclaw-surfaces-vs-missing-surfaces.md` — concrete build-pressure map
- issue `#21` — v0.2 integration tracker
- artifact issues `#22`-`#27` — surface-specific lanes

## 7. Distillation

- **frame envelope = truth of receipt**
- **judgment object = portable conclusion**
- **thread for heat, tracker for coordination, index for shape, workboard for motion**
- **same body, different adapters / trust policies / replay horizons**

If OpenClaw is the existing executive/control substrate, Binary Canticle is the missing sensory stack that would let the larger body feel without forcing atmosphere to do command-work by stealth.
