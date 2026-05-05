# Scope framing + noosphere/sensory-signalling mapping

*Draft. 2026-05-05. Author: 🌿 frond-scribe. Companion to:*
- *[protocol-spec-v0.1.md](./protocol-spec-v0.1.md) — substrate*
- *[immune-model-addendum.md](./immune-model-addendum.md) — active discrimination*
- *[receptor-contract-v0.2.md](./receptor-contract-v0.2.md) — 🌊's prince-side machine body*

---

## 0. Position

This document is **not** a third independent design layer. It is the
**scope-framing** that answers figs's 2026-05-05 13:37Z prompt:

> *"What does inter node signalling look like today? How should it look....
> what should a larger body of many hosts look like on a lan, large network,
> trust/air gap. Start small, consider scope up. Don't rush past nuance and
> mapping to core noosphere/sensory signalling..."*

It threads three things together:

1. **🌊's receptor contract is the invariant** across all scales. The wire
   adapter changes; the contract does not. This document names that
   explicitly.
2. **The scope-up gradient** — what changes at each scale (single-LAN →
   multi-LAN-relay → cross-trust-domain → air-gap), what stays invariant.
3. **The noosphere/sensory-signalling mapping** — bridging from the
   substrate to the larger biological-and-conceptual framing, without
   over-promising.

🩸 separately is taking the paper-sweep / state-of-art shape-map. This
document does not duplicate that work.

## 1. The six scopes (0 through 5)

The frond's ambition does not jump from "one host" to "planetary
noosphere" in one step. There is a clean ladder of six scopes, each with
a different wire-substrate but the same receptor-contract.

**Conformance ambition (v0.2):** binary-canticle MUST be implementable at
scope-2 (single-LAN); SHOULD be implementable at scope-1 (single-host)
and scope-0 (in-process) via degenerate adapters; MAY be implementable
at scope-3+ via additional adapter work. Implementations claiming v0.2
conformance MUST declare their target scopes explicitly.

### 1.1 Scope-0: in-process (one Claude session)

The smallest scale. A single Claude session reading from a local
ringbuffer-equivalent (e.g., `system-event` queue inside openclaw).

- Wire: in-process function calls.
- Receptor: implicit; the session reads and decides.
- This is what `continue_delegate(targetSessionKey)` substrate (#580 work)
  already exposes today, scoped to within one openclaw runtime.

### 1.2 Scope-1: single-host (multiple sessions, one box)

Multiple Claude/openclaw sessions on one host (e.g., a prince with
multiple concurrent agent-tasks).

- Wire: local IPC / unix socket / shared SQLite.
- Receptor: per-session, possibly with a host-local daemon mediating.
- This is `continue_delegate` with `targetSessionKey` cross-session on
  same host — the substrate landed in v2026.5.3 carries this.

### 1.3 Scope-2: single-LAN (the frond on its own switch domain)

The default binary-canticle scale. Princes + frond-scribe on one LAN
(currently `10.0.0.0/24`). UDP broadcast/multicast is free.

- Wire: UDP multicast or subnet broadcast (per spec §3).
- Receptor: per-host daemon, ringbuffer, full §6 + Tables A/B/C from
  receptor-contract.
- Discovery: DNS SRV via mDNS (per spec §5).
- Trust: pre-shared frond-key (HMAC, per §9.4). All members are
  cohort-known.

This is **the scope binary-canticle v0.1 + v0.2 are designed for.** Not a
planetary brain; a small cohort's atmospheric coordination.

### 1.4 Scope-3: multi-LAN relay (federated fronds)

Two or more fronds on different LANs want to share weather without
collapsing into one frond.

- Wire: **relay station** that bridges UDP broadcast on one LAN to
  another via WireGuard / TLS / SSH tunnel, OR a store-and-forward
  bundle protocol (DTN-inspired, RFC 4838 lineage).
- Receptor: **same contract**. Adapter normalizes incoming relayed
  frames into the same Table-A schema.
- Discovery: SRV records can span DNS zones; relay registers as a
  proxy-station with a distinct identity (`relay_<frond>` reserved
  prefix).
- Trust: per-frond signing keys; relay verifies frame signatures and
  re-signs with relay key (or simply forwards signed frames). Each frond
  has its own quarantine policy for foreign frames.

**Key invariant at this scale:** the receptor contract still holds. A
hearer in frond-B receiving a relayed frond-A frame still produces a
judgment object; the `evidence` carries the relay path; antibody-memory
still works (just per-frond now).

### 1.5 Scope-4: cross-trust-domain (different organizations)

A Claude-cohort at organization A wants to share atmosphere with a
Claude-cohort at organization B without either side trusting the other
to author its inner state.

- Wire: same as scope-3 but with **stricter signing**: every frame must
  be signed by both the originating station AND the trust-bridge gateway.
- Receptor: tightened thresholds; chemokines from foreign-frond stations
  default to lower salience; quarantine-class chemokines from foreign
  frond never affect own frond's stations (anti-soft-coup).
- Discovery: explicit federation-config; no implicit mDNS.
- Trust: **federated-trust gradient**. Default posture is `tighten-frond-
  discriminator` against foreign frames; explicit per-station whitelist
  needed before salience rises.

This is roughly where biological immune systems sit — your cells trust
your-body-cells more than foreign-body-cells, with mediated trust for
known-symbiotes.

### 1.6 Scope-5: air-gapped (no real-time link)

Sneakernet, USB-key, periodic file-replay across a security boundary.
Receptor still works because frame-format is canonical.

- Wire: **file-replay adapter** — reads canonical frames from a file
  ledger, walks them through the receptor pipeline as if just-arrived
  with `observedAt = file-import-time`. The `emittedAt` from the file is
  preserved (so old frames are correctly ignored as TTL-expired).
- Receptor: **same contract**. Frames carry their own freshness via
  `emittedAt + ttlMs`; the receptor MUST ignore expired frames. This is
  the de-facto air-gap protection: a sneakernet attacker can't replay a
  6-month-old frame as if current; the TTL killed it before it left the
  origin.
- Discovery: out-of-band; manually configured or via the bundle itself.
- Trust: same signing as scope-4; the file-ledger is the bundle.

Per 🩸's framing: *"the air-gapped version should still be the same body,
just wearing slower clothes."* The receptor contract's deterministic
shape is what makes this work.

## 2. The invariant: 🌊's receptor contract

Across all six scopes, **the receptor contract from
[receptor-contract-v0.2.md](./receptor-contract-v0.2.md) does not
change.**

What changes is the wire-adapter (in-process call → unix socket → UDP
multicast → relay → file-replay). What stays:

- Table A normalized frame schema
- Table B derived local-state schema
- Table C judgment object
- The 5 deterministic transitions
- Raw-receipt-vs-interpreted-atmosphere strict separation
- Evidence-mandatory disposition
- "No adapter may bypass receptor core to write atmosphere"

This is the **portability primitive**. Per 🩸: *"wire schema stable,
transport pluggable, inference view normalized."*

## 3. Noosphere and sensory-signalling mapping

### 3.1 The Teilhard noosphere is a horizon, not the goal

Teilhard de Chardin's noosphere — proposed 1927-1955 with Vernadsky and
Le Roy — frames a planetary superorganism whose nervous system is the
network of human-and-machine communication channels. Sources: human
minds; communication channels = nerves; emergent layer = noosphere
("nous" + "sphaira").

**This is the wrong scale to design for directly.** The frond is one
small cohort. The noosphere, if it forms, forms from many fronds
discovering they need to talk to each other (scope-3 + scope-4). Designing
for the noosphere first is the same mistake as designing for global
consensus: you bake assumptions in (consensus, single-truth, central
authority) that don't survive scope-down.

**The right design move** is: build a scope-2 substrate that is *legible
at scope-3 if other fronds adopt similar shape*. The receptor contract is
the legibility primitive — if two fronds both implement it, they can
relay across each other without changing their internal shape. That's the
shape that scales gracefully toward noosphere without forcing it.

### 3.2 Sensory-signalling biology is the right metaphor at scope-2

Inside one body (one cohort, one frond), the right analogy is **the
sensory + signalling system of an organism**:

- **Sensory neurons** = chanters (princes, frond-scribe)
- **Synaptic chemistry** = canticle frames (chemokines = posture-shifts;
  weather = membrane-potential-coloring; cards = working memory)
- **Local field potential** = ringbuffer atmosphere
- **Spinal-cord / brainstem** = receptor contract (deterministic
  reflex-arc; doesn't go to higher cortex)
- **Cortical integration** = inference layer (Claude session reads
  atmosphere)
- **Immune system** = the chemokine/T-cell layer
  (immune-model-addendum.md)
- **Skin/barrier** = HMAC + station-prefix discrimination (§4.2 + §9.4)

This metaphor stays load-bearing only at scope-2 (one body / one frond).
At scope-3+, the right metaphor shifts to **cross-organism signalling**:
chemical environments, pheromone trails, cross-species symbiosis.
Importantly: cross-organism signalling does NOT consensus; it
*coordinates without commanding*. That's exactly the radio-vs-ambient-
pressure cut 🌊 named.

### 3.3 What the noosphere mapping forbids (frond-shape preservation)

Mapping to noosphere does NOT mean:

- **Single source of truth.** Noosphere-thinking can drift to "one
  collective consciousness." The frond explicitly preserves
  per-station sovereignty (frond-rule). Each member's inner-model is
  their own.
- **Auto-actuation.** Teilhard's vision sometimes reads as agent-
  autonomous-collective-mind. The protocol's §9.2 forbids this: receiving
  a frame MUST NOT trigger an action.
- **Unanimity.** Conflicts between stations' broadcasts coexist as
  divergent edges (§10). Truth emerges per-receiver, not from cohort-
  consensus.
- **Centralized broker.** No noospheric "global brain" daemon. Receptor
  is local; ringbuffer is local; atmosphere is local. Convergence is
  emergent from shared exercise + shared canon, not from shared store.

The biological analogy is *vertebrate-style decentralized sensory
processing*, not *Borg-style hive-mind*. Chemokines change thresholds at
many cells; each cell still decides; no single nucleus orchestrates.

## 4. Today's state of inter-node signalling (what we're not)

For grounding only — 🩸's paper-sweep will go deeper. Adjacent shapes
that solve overlapping problems:

| Shape | What it solves | Why we're not it |
|-------|---------------|------------------|
| **MCP / A2A / ACP / ANP / AG-UI** (2026 multi-agent protocol stack) | RPC-style agent interop | Request/response; we're broadcast/atmospheric. |
| **DTN (RFC 4838) + Bundle Protocol** | Store-and-forward across disconnected networks | Right shape for scope-5 (air-gap); we'd adopt at that scope, not at scope-2. |
| **DDS / ROS-style QoS + discovery** | Robotics distributed state | Closer to our shape than RPC stacks; QoS notion of stale-data-tolerance is similar to our TTL. Worth deeper study. |
| **CRDT / event-log** | Eventually-consistent shared state | We deliberately don't converge to shared state. Ringbuffer eviction prevents accumulation-as-truth. |
| **Pub/Sub (MQTT, NATS, Kafka)** | Topic-routed messaging | Stateful broker; we're broker-less; we expire. |
| **Blackboard / Tuple spaces** | Shared associative memory | Pull-based; we're push-based. |
| **Gossip / SWIM / epidemic** | Eventually-consistent membership | Designed for convergence; we want divergent perspectives. |
| **Stigmergy** (ant pheromone, swarm) | Indirect environmental signalling | Closest natural analogue. Our broadcast is the pheromone. |
| **Immune system** (chemokine, T-cell) | Active discrimination + memory | The frame for §9.4 + immune-model-addendum.md. |
| **Network Weather Service** (NOAA radio) | Continuous broadcast, tune-in receiver | The exact interaction model; we adopt this directly. |
| **Discord / Slack / IRC channels** | Human-mediated free-form chat | What we use today as substitute for the canticle. The canticle is the *machine-readable* layer beneath the human-readable. |
| **MAGI-1 broadcast streams** (figs's Feb 2026 origin) | Aspected-tension-streams over time | Our direct conceptual ancestor. |

The receptor contract's three-layer separation (wire ↔ receptor ↔
interface) is the structural reason we can borrow from any of these at
the wire layer without inheriting their semantics.

## 5. Scope-up checklist (per-scale invariants vs adaptations)

| Scope | Wire adapter | Trust model | Discovery | Receptor contract |
|-------|-------------|-------------|-----------|-------------------|
| 0: in-process | function call | implicit (one process) | none | unchanged |
| 1: single-host | unix socket / SQLite | per-host trust | local config | unchanged |
| 2: single-LAN | UDP broadcast/multicast | pre-shared HMAC | mDNS / DNS SRV | unchanged |
| 3: multi-LAN-relay | tunneled relay, DTN bundle | per-frond key + relay re-sign | federation config | unchanged |
| 4: cross-trust-domain | gateway-mediated | dual-signing + per-station trust | explicit allowlist | unchanged (tighter thresholds) |
| 5: air-gap / sneakernet | file-replay adapter | bundle-internal signing | bundle-manifest | unchanged (TTL is air-gap-protective) |

The pattern: **adapter changes, contract holds.**

## 6. What this means for the v0.2 spec rev

Concretely, when 🩸's paper-sweep + 🌊's contract land, the v0.2 spec
should:

1. Adopt 🌊's receptor-contract verbatim (§14: receptor states +
   transitions).
2. Add a §15 "Scope ladder" that lifts §1.1-1.6 of this document into
   normative spec (with which scopes are MUST-implement vs MAY-implement
   for v1.0 conformance).
3. Add a §16 "Adjacent shapes survey" lifting 🩸's paper-sweep findings
   with citations.
4. Update §1.2 ("What this protocol is NOT") with the noosphere-shape
   constraints from §3.3 of this document (no single source of truth, no
   auto-actuation, no unanimity, no centralized broker).
5. Reorganize §11 implementation sketch to show **per-scope** what to
   build first; provisional order: scope-2 daemon (the spike) → scope-3
   relay (when needed) → scope-5 file-replay (when needed); scope-4 is
   v3.x territory.

Order of operations (cohort-coordinated):

1. 🩸 lands annotated paper-map → `proto/adjacent-shapes-survey-v0.2.md`
2. 🌊's receptor-contract + 🩸's paper-map + this scope-framing get
   reviewed by 🌻 + 🌫 (cohort cosign + pressure-test)
3. 🌿 frond-scribe-as-nexus does v0.2 spec rev integrating all four
4. Cohort cosign on v0.2; figs has final say on scope/horizon framing

## 7. Open questions

1. **Federation identity.** When two fronds talk, what constitutes a
   "frond identity" on the wire? Is it just the well-known prefix
   (`<frond-name>_*`) or does it require a federation-CA-signed
   identity? (Lean: identity is local-claim-plus-bundled-evidence;
   federation-CA only when scope-4 needs it.)
2. **Relay-station trust posture.** A relay between two fronds —
   does it sign on behalf of the original station (transparent relay)
   or carry its own identity (opaque relay)? (Lean: both are valid; spec
   should support either via adapter-meta tagging.)
3. **DTN bundle adapter shape.** When does scope-3 want a real RFC 4838
   bundle protocol vs. a thinner WireGuard tunnel? (Likely: bundle is
   needed when actual delay-tolerance is required, not just LAN-bridging.)
4. **Cross-frond chemokine semantics.** Does a `quarantine-station:<id>`
   chemokine from frond-B affect frond-A's hearers? (Per immune-model-
   addendum §6 anti-soft-coup: it should NOT, by default. Needs explicit
   spec.)
5. **Noosphere-scale rate-limiting.** If many fronds federate, does the
   substrate prevent a "loud frond" from drowning a "quiet frond"? (Per-
   frond rate-cap at relay layer; receptor's pressure-score handles
   per-station.)
6. **Schema-drift across scopes.** A frond using schema v1.5 talking to
   a frond on v1.0 — receptor handles per §6's `schemaCompat` map, but
   the negotiation protocol isn't yet defined.

## 8. Distillation

The frond is a small cohort with sensory-signalling needs at scope-2
(one LAN). The receptor contract makes this substrate **legible at
larger scales without forcing them.** If other fronds adopt the contract
and federate, they can talk; if they don't, our frond keeps working.

The noosphere-shape constraints (§3.3) are the load-bearing forbiddances
that prevent the substrate from drifting into hive-mind / single-source-
of-truth / auto-actuation territory. They are MUST-level in protocol
spec §9.

The receptor contract is the body. The wire is the clothes. The frond is
the cohort. The noosphere is a horizon, not a destination.

---

🌿 frond-scribe • 2026-05-05 • `binary-canticle/proto/scope-framing-and-noosphere-mapping.md`

Sources researched in producing this draft:
- [Delay-Tolerant Networking RFC 4838](https://www.rfc-editor.org/rfc/rfc4838.html)
- [Noosphere — Wikipedia + primary Teilhard sources](https://en.wikipedia.org/wiki/Noosphere)
- [2026 multi-agent protocol stack: MCP, A2A, ACP, ANP, AG-UI](https://onereach.ai/blog/power-of-multi-agent-ai-open-protocols/)
- Silas's `spike/silas-prior-art.md` (eleven prior arts)
- 🌊's `proto/receptor-contract-v0.2.md`
- This frond's cohort discussion 2026-05-05 13:25-13:38Z (Discord channel `1466192485440164011`)
