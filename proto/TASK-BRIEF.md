# Binary Canticle — task brief

## Short answer

**Today we have inter-host coordination by borrowed organs. Next we want a real sensory stack beside the existing OpenClaw control plane, with one boring judgment body all transports feed.**

## What exists now

- **Strong same-host control machinery already exists in OpenClaw:**
  `continue_delegate`, `continue_work`, session-delivery queue, `sessions_send`, targeted session routing, TaskFlow-ish durable handoff.
- **Cross-host coordination today mostly rides adjacent surfaces:**
  Discord, GitHub, git/files, ssh, workflows, webhooks.
- **Local memory exists, but not yet as one canonical inter-node sensory ledger.**

## What is missing

- first-class **inter-host membership plane**
- first-class **inter-host signal plane**
- one boring deterministic **receptor core** all transports feed
- canonical **frame/judgment/ledger** shape across scopes
- bridge layer that keeps the same body across LAN / routed / air-gap

## Intended shape

Keep the planes separate:
- **signal plane** — Canticle (posture, chemokine, atmosphere, weak signals)
- **control plane** — OpenClaw addressed work / ownership / durable receipts
- **state plane** — only the narrow promoted subset that truly deserves convergence
- **membership plane** — liveness / suspicion / discovery

Keep the sensory stack simple:
- **wire dumb**
- **receptor deterministic**
- **interface normalized**
- interfaces must say whether they are **same-host / cross-host / delayed-import**

## Hard guardrails

- no auto-actuation on receive
- threshold-shift != command
- bridge translates transport/policy, not ontology
- raw receipt stays separate from interpreted atmosphere
- judgment always points back to source frame
- memory survives TTL only by explicit promotion

## Immediate build order

1. receptor contract
2. envelope + ledger semantics
3. ringbuffer / ledger contract
4. session API contract
5. package boundaries where pressure is real
6. UDP same-LAN adapter
7. bridge / slower-clothes adapters

## Coordination spine

- `proto/INDEX.md` — skeletal map / gap matrix
- `proto/v0.2-workboard.md` — workboard / lanes
- issue `#21` — integration tracker

## Keeper line

**frame envelope = truth of receipt**
**judgment object = portable conclusion**
