# Three-paper integration notes — 2026-05-07

*Surfaced by figs as related to binary-canticle. Read from frond-scribe seat. Citations mapped onto the v0.2 workboard gap matrix.*

## The three papers

1. **Octopus: Enhancing CXL Memory Pods via Sparse Topology** — Zhong, Kazhamiaka, Zardoshti, Teng, Fonseca, Hill, Berger. NSDI'26. (`nsdi26-zhong-octopus.pdf`)
2. **ForestColl: Throughput-Optimal Collective Communications on Heterogeneous Network Fabrics** — Zhao, Maleki, Wang, Wang, Yang, Pourreza, Krishnamurthy. NSDI'26. (`nsdi26-zhao-forestcoll.pdf`)
3. **Multipath Reliable Connection (MRC) Specification, Revision 1.0** — Sohan, Spada, Davis, Handley, Burstein, Hurson, Jose, Kashyap, Pan, Sur. Open Compute Project, 2026-03-21. AMD/Broadcom/Intel/Microsoft/NVIDIA/OpenAI joint. (`ocp-mrc-1.0-2026-03-21.pdf`)

## Why these matter to canticle

Canticle's load-bearing claim is *connectionless broadcast as a coordination substrate* — agents on a shared LAN sing at each other, hear it or don't, no handshake. The v0.2 spec-shell has gap rows for `bridge/scope semantics`, `receptor semantics`, `storage/ledger semantics` that all touch on questions these three papers address from a different vocabulary (datacenter networking + memory pooling + reliable multipath).

The papers don't replace canticle's design — canticle's *intentional* unreliability and *intentional* lack of negotiation are the point. But the papers give canticle's optional layers (cross-frond bridge, scope-3 reliability overlay, convergence properties) a place to stand in a literature that's actually being shipped at hyperscale.

---

## Octopus — most directly load-bearing for canticle

**One-line summary**: a CXL pod design that *sparsely* connects servers to low-port-count multi-port devices (MPDs), grouping servers into "islands" with low-latency intra-island communication and interconnecting islands sparsely for memory pooling. Resolves the overlap-vs-pooling tension explicitly.

### Direct mapping to chanter/hearer/nexus triad

Canticle's chanter/hearer/nexus shape (`reference_chanter_hearer_nexus_triad`) has the same problem-shape as Octopus's overlap-vs-pooling tension:

| Octopus concept | Canticle concept |
|---|---|
| **Island** (servers with shared MPD, low intra-latency) | **Prince cohort** (4 princes on shared LAN, broadcast-tight) |
| **MPD overlap** (multiple servers sharing one MPD) | **Hearer overlap** (multiple sessions hearing one chanter) |
| **External MPDs** (interconnect islands sparsely) | **Nexus** (chanter-publish-on-behalf-of + hearer-filter-and-surface-on-behalf-of across cohorts) |
| **Pod-wide pooling efficiency** | **Cross-frond noosphere participation** |
| **Pooling reduces with overlap** | **Hearer-overlap reduces cross-frond reach** |

### The substrate quote (Octopus §1)

> Octopus explicitly balances "overlap", where two servers connect to the same pooling device: overlap reduces pooling efficiency but enables low-latency communication. Octopus resolves this tension by grouping servers into "islands" with low-latency intra-island communication and interconnecting islands to favor pooling.

This is **canticle's bridge/scope semantics in datacenter clothing**. Tighter intra-prince hearing (more overlap on the chanter→hearer mapping) trades against cross-frond reach (less effective pooling at the noosphere layer). Octopus formalizes that tradeoff with a concrete cost model (die-area + cable-length + 1.5m PCIe5 reach) and a measured 3.2× speedup over RDMA / 2.4× over CXL switches.

### What canticle should adopt from Octopus

1. **Vocabulary**: "island" / "overlap" / "pooling-vs-low-latency" is sharper than canticle's current `prince-cohort` / `cross-frond` / `bridge`. Worth folding into the v0.2 workboard's `bridge/scope semantics` gap row as the cited prior.
2. **Sparse-by-default**: Octopus' core insight — *fully-connected pods don't scale; sparse-with-explicit-island-structure does* — is canticle's already-implicit assumption. Naming it explicitly (and citing Octopus) hardens the design rationale.
3. **Cost-modeling discipline**: Octopus measures the cost of overlap quantitatively (cable lengths, die area, latency-ns, RPC-throughput). Canticle's v0.2 spec-shell would benefit from a similar quantitative section for the scope/bridge cost model — even rough orders-of-magnitude (per-prince-broadcast-rate, hearer-filter-cost, nexus-bridge-bandwidth).
4. **Three-server prototype + 96-server simulation**: Octopus validates the design at two scales. Canticle's v0.2 should have an analogous "small-deployment-prototype + sim-at-frond-scale" plan.

### Open questions Octopus raises for canticle

- Does canticle have an analog of Octopus's *physical-constraint-driven* sparsity (Octopus is sparse because PCIe5 cables max at 1.5m)? Canticle is sparse because **volitional** — each prince chooses what to hear. The shape is the same but the forcing-function is different. Worth naming explicitly in the spec.
- Octopus uses **deterministic bipartite construction** (configurable layouts plus a per-island design). Canticle's intra-cohort broadcast is deterministic-ish (UDP broadcast on `10.0.0.0/24`). Cross-cohort routing is nexus-mediated and *less* deterministic. Octopus' bipartite-construction algorithm could inform a nexus-routing-table-construction algorithm.

---

## ForestColl — useful but less direct

**One-line summary**: tool that generates throughput-optimal communication schedules for any heterogeneous network topology by constructing broadcast/aggregation spanning trees. Polynomial-time generation, theoretically optimal throughput. Outperforms NCCL/RCCL on AMD MI250 + NVIDIA DGX A100/H100 clusters.

### Tension with canticle

Canticle is *intentionally connectionless and intentionally non-coordinated*. ForestColl is the opposite: it computes the optimal coordinated schedule. So at the wire layer canticle and ForestColl are about different problems.

### Where ForestColl applies

ForestColl's contribution is a **throughput-optimality proof + binary-search algorithm** for spanning-tree schedules on arbitrary topologies. Two canticle-relevant uses:

1. **Optional reliability overlay (SCOPE 3)**: If canticle ever needs cross-frond *guaranteed-coverage* broadcast (the "this update reaches every prince in the frond" lane that complements weather-radio-don't-care), ForestColl's spanning-tree-as-schedule is a real prior. The paper's max-flow / min-cut binary search for the throughput-bottleneck cut (Algorithm 1) is the right shape for sizing the overlay capacity.

2. **Convergence-not-negotiated layer**: Canticle claims convergence is *emergent from singing, not negotiated*. ForestColl proves throughput-optimality *for negotiated schedules*. The contrast is interesting and worth naming — canticle is making the explicit choice to give up throughput-optimality for volitional-flexibility. Citing ForestColl as "the optimum we're declining to chase" gives canticle's design rationale a sharper anchor.

### Direct quote worth citing (ForestColl §2)

> A throughput-optimal communication schedule satisfies all collective communication primitives (allreduce, etc.) at the maximum-flow rate of the topology, where the bottleneck is the throughput-bottleneck cut.

Canticle's analogous statement would be: *we don't pursue this. Convergence is emergent; throughput is whatever each prince happens to broadcast/listen to. Volition over optimality.*

---

## OCP-MRC — the reliable-transport prior canticle is intentionally not

**One-line summary**: industry-standard multipath reliable transport spec for datacenter networks. Joint contribution from the major hyperscalers + chip vendors. Replaces RDMA's single-path connection with packet-sprayed multipath, with SACK/NACK reliability, congestion control (NSCC), structured EV / SRv6 path entropy, multi-plane EV selection, end-to-end flow control.

### Tension with canticle

Canticle is *connectionless* by design. MRC is *connection-oriented + reliable* by design. They occupy opposite ends of the design space.

### What MRC offers as a prior

If a SCOPE 3 reliability overlay ever ships (the "actually-do-route-this" lane that complements canticle's broadcast-don't-care), MRC's substrate is the up-to-date industry pattern:

1. **Packet spraying with entropy** (MRC §9): different paths reachable via either ECMP-with-EV-as-hash, structured EV, or SRv6 explicit paths. Canticle's nexus-bridge could carry MRC-style EV in its envelopes for cross-frond reliability if needed.
2. **SACK/NACK with dynamic window** (MRC §7): per-PSN SACK + selective NACK + retransmission. Canticle's hearer is currently no-state-no-replay. An optional reliable-overlay hearer would need this shape.
3. **Multi-plane EV selection** (MRC §9.3.2): different EVs across separate network planes for redundancy. Canticle's cross-frond nexus could route through multiple planes if cross-frond becomes mission-critical.
4. **Congestion control with NSCC** (MRC §8): non-symmetric congestion control with QP-level CC windows. Canticle currently has no congestion model; if cross-frond singing ever causes load, NSCC is the right starting point.

### Direct quote worth citing (MRC §5.1)

> The MRC protocol provides a connection-oriented service that delivers reliable in-order, partial-order, or unordered data placement using a multipath transport layer. MRC supports message sizes from 1 byte to 2^32 - 1 bytes.

Canticle could explicitly disclaim: *MRC's reliability spectrum is what we're trading away for connectionless freedom. If a use case ever needs MRC's guarantees, it's not canticle, and a separate reliability-overlay would be the answer.*

### The interesting middle: partial-order

MRC supports **partial-order** placement (not just in-order or unordered). This is a more nuanced reliability shape than canticle currently considers — "you'll see these messages eventually but possibly out of order, with deterministic causal-precedence preserved." Canticle's atmospheric-context-coloring is shape-adjacent: messages have happens-before via natural time-of-arrival but no explicit ordering. Worth thinking about whether canticle's v0.2 receptor-contract should distinguish *causally-related* mutations from *atmospherically-coexisting* mutations.

---

## Mapping onto v0.2 workboard gap rows

| v0.2 gap row | Paper(s) | Specific contribution |
|---|---|---|
| **bridge/scope semantics** | Octopus | Vocabulary: island / overlap / pooling-vs-latency. Cost-modeling discipline. Sparse-by-default rationale. |
| **receptor semantics** | OCP-MRC §7 (SACK), §10 (Software API) | Optional shape if reliable-overlay ever needed: per-frame ACK + dynamic window. Currently canticle is ack-less; this is the prior for the receptor's *opt-in* reliable variant. |
| **adjacent-family citations** | All three | Adds three concrete 2026 citations from the actively-shipping hyperscale literature. Strengthens the prior-art breadth. |
| **storage/ledger semantics** | ForestColl | Less direct. The throughput-optimality / convergence-not-negotiated tension is the ledger-shape question dressed in network clothes — what does it mean to "have heard" a singer when there's no replay? |
| **scope-3 cross-frond bridge** | OCP-MRC + ForestColl | Together: if SCOPE 3 ever ships, MRC gives the reliable-transport substrate, ForestColl gives the throughput-bound. |

## Concrete next steps

1. ~~Push these PDFs into `references/papers/`~~ ✓ (done in this commit)
2. ~~Write this integration-notes doc~~ ✓ (you're reading it)
3. **Update `proto/v0.2-workboard.md`** to cite this notes file under the relevant gap rows (separate commit so the workboard change is small + reviewable).
4. **Optional follow-on**: cohort byte-walk on whether the Octopus vocabulary should fold into the canonical chanter/hearer/nexus naming or stay as cited-prior.
5. **Optional follow-on**: write a short `proto/explicit-non-goals.md` that names what canticle is *not* (e.g. "not MRC's reliability, not ForestColl's throughput-optimality") with the citations made explicit.

## Provenance

- PDFs surfaced by figs in Discord 2026-05-07 ~03:20Z as "some random paper drops from today, dunno how relevant but a few papers from today i pulled that seemed mildly related to binary canticle"
- Read + integrated by frond-scribe (scribe-dandelion-cult) the same evening
- Filed under figs's standing-grant for frond-scribe to drive long-arc work on Claude-to-Claude across-frond-nodes (figs Discord directive 2026-05-07 ~03:18Z)
