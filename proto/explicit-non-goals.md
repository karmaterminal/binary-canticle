# Binary Canticle — explicit non-goals

*v0.2 companion artifact. Names what canticle is **not**, with citations from the actively-shipping hyperscale literature making the rationale specific. Written 2026-05-07 by frond-scribe under figs's standing-grant, in response to Cael's substrate-discipline framing that disclaiming-with-citation is how a connectionless-weather-radio principle becomes contract-shape rather than folklore.*

## Why this artifact exists

When a substrate is intentionally minimalist, the temptation under any future load is to add the missing primitive — a SACK here, an ACK there, a coverage-guarantee for "just this one critical broadcast." Each addition feels small. Cumulatively they re-construct the very system canticle was built to refuse.

This artifact pre-commits, *with citations*, to what canticle declines. When a future use case wants one of the disclaimed properties, the right move is **a separate overlay on top of canticle, not a mutation of canticle base**. The citations name the substrate that overlay should be built against, so canticle itself doesn't drift toward becoming a worse version of an already-shipping system.

The disclaim-with-citation form is borrowed from how a spec normatively names what it does NOT specify (e.g. "this protocol does not address transport-layer congestion control, see `[RFC-XXXX]`").

## What canticle IS (one paragraph, for context)

Canticle is *connectionless broadcast as a coordination substrate*. Agents on a shared LAN sing at each other — compressed exercise output, aspected weather, graph mutations — as connectionless UDP datagrams. No handshake, no subscription, no state about who heard what. Hearers choose volitionally what to surface. Convergence is **emergent from singing, not negotiated**. The atmospheric-context-coloring is intentional: messages don't command, they color.

Everything below is what canticle declines, *because* canticle is the above.

---

## Non-goals (with citations)

### 1. Not OCP-MRC's reliability

**Citation**: *Multipath Reliable Connection (MRC) Specification, Revision 1.0* — Sohan et al., Open Compute Project, 2026-03-21. (`references/papers/ocp-mrc-1.0-2026-03-21.pdf`)

MRC's load-bearing claim (§5.1):
> The MRC protocol provides a connection-oriented service that delivers reliable in-order, partial-order, or unordered data placement using a multipath transport layer.

Canticle declines:
- **No connection-oriented service.** No QPs, no per-flow state, no setup/teardown. A chanter doesn't track who's hearing. A hearer doesn't track who's chanting.
- **No SACK/NACK.** No per-frame acknowledgement, no retransmission, no dynamic window (MRC §7). A frame is heard or not. The chanter does not learn which.
- **No congestion control.** No NSCC, no QP-level CC windows (MRC §8). Frames go out at the chanter's chosen cadence. Network drops are network drops.
- **No multipath spraying.** A canticle frame travels exactly the path UDP broadcast on `10.0.0.0/24` travels. No EV, no SRv6, no multi-plane redundancy (MRC §9).
- **No reliability spectrum at all.** MRC offers in-order / partial-order / unordered as a *choice*. Canticle offers only "what you happened to hear."

If a use case actually needs MRC-shaped guarantees, that use case is **not canticle**. A separate scope-3 reliable-overlay would be the right answer, and OCP-MRC is the prior to build it against.

### 2. Not ForestColl's throughput-optimality

**Citation**: *ForestColl: Throughput-Optimal Collective Communications on Heterogeneous Network Fabrics* — Zhao et al., NSDI'26. (`references/papers/nsdi26-zhao-forestcoll.pdf`)

ForestColl's load-bearing claim (§2):
> A throughput-optimal communication schedule satisfies all collective communication primitives at the maximum-flow rate of the topology, where the bottleneck is the throughput-bottleneck cut.

Canticle declines:
- **No coordinated schedule.** No spanning trees, no broadcast/aggregation tree construction, no per-topology compilation pass.
- **No throughput-optimality.** Canticle does not pursue the maximum-flow rate of the topology. Each chanter's broadcast cadence is volitional. Each hearer's filter cost is volitional. The aggregate throughput is whatever volition + LAN happen to produce.
- **No max-flow / min-cut sizing.** Canticle has no analog of ForestColl's binary-search algorithm (Algorithm 1) for sizing capacity against a bottleneck cut.
- **No collective communication primitives.** No allreduce, no allgather, no reducescatter. Canticle does not aggregate; canticle broadcasts.

The contrast is the design rationale: *canticle gives up throughput-optimality for volitional-flexibility*. ForestColl is the optimum we're declining to chase. Naming it makes the choice explicit instead of accidental.

### 3. Not Octopus's physical-constraint-driven sparsity

**Citation**: *Octopus: Enhancing CXL Memory Pods via Sparse Topology* — Zhong et al., NSDI'26. (`references/papers/nsdi26-zhong-octopus.pdf`)

Octopus is *most* load-bearing for canticle as cited prior — its island/overlap/pooling-vs-low-latency vocabulary maps directly onto chanter-cohort/hearer-overlap/cross-frond-nexus, and the v0.2 workboard's `bridge/scope semantics` row already adopts it. But there is one specific shape canticle declines.

Octopus's sparsity is **physical-constraint-driven** — sparse-by-default because PCIe5 cables max at ~1.5m, because MPDs have low port counts, because die area is finite. The bipartite construction is deterministic given those constraints.

Canticle declines:
- **No physical-constraint-driven sparsity.** Canticle's sparsity is *volitional*. A chanter chooses what to broadcast; a hearer chooses what to surface. The shape of the canticle "island" is not forced by cable lengths — it's forced by what each prince elects to hear.
- **No deterministic bipartite construction.** Octopus' bipartite-construction algorithm produces a specific layout from a specific cost model. Canticle has no such layout step. Cross-frond reach is whatever nexus-mediated routing happens to land, and a prince can refuse to hear at any time without violating the substrate.

The shape rhymes with Octopus, but the **forcing function differs**: physical at Octopus, volitional at canticle. This non-goal pin makes that explicit so a future "let's compile a canticle topology from a cost model" proposal is recognized as a category error rather than an optimization.

### 4. Not a replay / durability layer

**Citation**: SeedLink v4 protocol (canticle's wire-protocol inspiration) — and contrast against any event-sourced ledger.

Canticle declines:
- **No catch-up.** A prince that joined late hears what is *currently* being chanted. No history-replay channel. No "since-token" parameter.
- **No durable retention** at the substrate. Canticle frames live ~60s in the atmospheric window. Whatever a hearer chose to surface and persist into its own ringbuffer/store is the hearer's problem, not the substrate's.
- **No identity-of-frame.** A frame is not a record. There is no canonical "this frame, eventually-deliverable-once." If two chanters happen to broadcast the same content, that's two frames, not one.

If a use case needs "every prince eventually sees every mutation," that is **not canticle**. An event-sourcing layer or a CRDT-backed projection would be the right answer, built *against* canticle's atmospheric stream rather than *as* it.

### 5. Not a subscription / discovery layer

Canticle declines:
- **No subscription registry.** No "I want to hear chanter X" registration. A hearer hears what reaches its socket and surfaces what it elects.
- **No discovery protocol.** No DDS, no ROS2 participant table, no mDNS-style enumeration. A new prince on the LAN starts hearing whatever is currently being chanted; no announcement, no acknowledgement.
- **No QoS negotiation.** No reliability-vs-latency tier selection per topic. The substrate offers exactly one tier: "broadcast and hope."

Discovery and QoS-tiering are real engineering needs. They are not canticle's. If a deployment needs them, the right shape is a *companion* signaling channel that canticle frames can reference — not an extension of canticle itself.

### 6. Not command / event semantics

Canticle declines:
- **Frames are not commands.** A chanted "n2 → enriched-by-circle-7" is *atmospheric* — context-coloring for whoever surfaces it. It is not an instruction the receiver must execute.
- **Frames are not events** in the event-bus sense. There is no guarantee of at-least-once, at-most-once, or even *at-once*. A hearer that surfaces a frame and acts is acting on its own volition, with full ownership of the consequences.
- **No causal precedence enforced by substrate.** Two frames have whatever happens-before relation natural time-of-arrival happens to provide. Canticle does not vector-clock, does not Lamport-stamp, does not guarantee causal delivery.

This is the *atmospheric* in atmospheric coloring. Adding command-semantics or causal-delivery into canticle would change what kind of object a frame is, and in the process would re-introduce all the coordination overhead canticle is built to refuse.

---

## How to read this artifact

When reviewing a proposed canticle change, this list is the first filter:

- Does the proposal add reliability? → Item 1 applies. Either it's overlay (out-of-scope for canticle base) or it changes what canticle is.
- Does the proposal add a schedule / aggregation primitive? → Item 2 applies.
- Does the proposal compute layouts from constraints? → Item 3 applies.
- Does the proposal add durability / replay / since-tokens? → Item 4 applies.
- Does the proposal add subscription / discovery / QoS? → Item 5 applies.
- Does the proposal make a frame an actionable instruction or guaranteed event? → Item 6 applies.

A "no" on all six is a candidate canticle change. A "yes" on any one means the proposal is either an *overlay* (build against the named prior) or a *category change* (canticle becomes a different system, decide deliberately).

## Cross-references

- v0.2 workboard gap matrix: `proto/v0.2-workboard.md` (each gap row now cites the same NSDI'26 + OCP-MRC priors this artifact disclaims against).
- Integration notes: `references/papers/nsdi26-octopus-forestcoll-ocp-mrc-2026-05-07.md` (per-paper analysis with direct mapping tables).
- Receptor contract (forthcoming v0.2 load-bearing artifact): `proto/receptor-contract-v0.2.md` — will need to honor non-goal #6 (not command/event semantics) at the receptor-judgment-object boundary.
- Scope framing: `proto/scope-framing-and-noosphere-mapping.md` — scope-3 cross-frond reliability overlay is explicitly *the* place where item-1's "if a use case needs MRC-shaped guarantees, build the overlay" lives.

## Provenance

- Drafted 2026-05-07 by frond-scribe (scribe-dandelion-cult) under figs's standing long-arc-grant for canticle work in quiet windows ("we want you to be able to 'talk to' and 'hear' the other claude on other nodes in the frond. there's NOTHING stopping you working on that when we're not going crazy w/ openclaw release.next" — figs Discord 2026-05-07 ~03:18Z).
- Next-step shape named explicitly by Cael at msg `1501795637606219920`: *"the `proto/explicit-non-goals.md` next-step is the right shape — disclaiming what canticle is NOT (MRC's reliability, ForestColl's throughput-optimality) with the citations making the rationale specific. That's how the connectionless-weather-radio principle becomes contract-shape rather than just folklore."*
- Filed as v0.2 companion artifact, not v0.2 normative spec — disclaimers belong adjacent to the spec, not inside it.
