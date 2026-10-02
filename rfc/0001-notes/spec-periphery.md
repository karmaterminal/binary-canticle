# spec-periphery — binary-canticle peripheral / coordination docs

Reader: spec-periphery lane. Repo `/home/user/binary-canticle` @ `b46a45a` (main == origin/main).
Date of read: 2026-09-27. All paths below are repo-relative to binary-canticle unless prefixed.
Legend used throughout: **[SAYS]** = what a source states; **[DECIDED]** = actually landed / implemented / closed;
**[ASSESS]** = my own judgment.

---

## 0. Headline

- **[DECIDED]** The peripheral docs are almost entirely a 2026-05-05 → 2026-05-07 burst (commits `a5e2c75`…`b82a5a2`), with a
  second wave 2026-06-24/25 (`21b46a4` merge of PR #28, `5a3c0e8`, `6fc78f5`, `e0f5591`). Nothing in the twelve target docs
  changed after 2026-06-25 except `prototype/README.md` (`65e6705`, 2026-07-25). README.md has **never** changed since the
  first commit `888900a` (2026-03-14).
- **[DECIDED]** No v0.2 spec revision exists. Every doc that says "fold into v0.2 rev §14–§18" (INDEX:19,21; scope-framing:270-296;
  #21 "v0.2 spec rev intended section map") points at an artifact that was never written.
- **[DECIDED]** Only runnable code is `prototype/ringserver-udp-cue/` (Python ≥3.11, `cryptography>=45`), a **localhost-only**
  signed-JSON "cue" receptor whose datagrams can carry **only a `sha256:` subject digest** — it implements none of the
  stations-and-streams wire (no CBOR, no carrier-beacon, no station:stream, no ring, no sender).
- **[ASSESS]** The periphery is coherent in ethos but contradictory in mechanics on exactly the axes the owner now cares
  about: replay/looping, trust/signing, scale (cohort of 4-6 vs thousands), internet listeners, and whether a heard frame may
  enrich/wake a remote session. Seven periphery docs repeat the same plane lists, guardrails, build order and "must refuse
  to become" lists; they should collapse into ~3 RFC sections plus one index.

---

## 1. Per-doc: what it claims vs real status

| Doc | Last commit (date) | Claims [SAYS] | Real status [DECIDED/ASSESS] |
|---|---|---|---|
| `README.md` | `888900a` (2026-03-14), only commit | "Connectionless broadcast enrichment"; UDP on `10.0.0.0/24` (README:33); graph mutations ~100B (README:34); delivery via "`\| silent` enrichment into OpenClaw sessions" (README:35); "~60 seconds… No replay. No catch-up." (README:42); repo contains `proto/` Node.js sender/receiver, `schema/`, `exercises/` (README:49-52); OpenClaw `continue_delegate` "PR #38780, shipped 2026-03-13" (README:59); "Four princes… One gardener: figs" (README:63) | **Stale front door.** See §5. Issue **#35** (open, 2026-06-22, Cael) already enumerates the stale bytes and acceptance criteria; not acted on. INDEX:17 still labels it `active`. |
| `proto/TASK-BRIEF.md` | `4ed2b52` (2026-05-05; landed on main via PR #28 merge `21b46a4` 2026-06-25) | Short answer: "inter-host coordination by borrowed organs"; four planes (signal/control/state/membership) (TASK-BRIEF:25-29); "wire dumb / receptor deterministic / interface normalized" (:31-35); hard guardrails (:37-44); build order 1-7 (:46-54); coordination spine = INDEX, workboard, #21 (:56-60) | Best one-page abstract in the repo. Build order steps 1-3 have docs (receptor, envelope via receptor Table A, ringbuffer); step 4 session API (#24) and 5 package boundaries never written; step 6 "UDP same-LAN adapter" **not done** (prototype binds IPv4 loopback only — `prototype/ringserver-udp-cue/canticle_receptor/udp.py:21-22`). Spine it names (INDEX, workboard, #21) is stale (§5). |
| `proto/INDEX.md` | `6fc78f5` (2026-06-24) | "skeletal map" with owner/plane/status/"must refuse to become" per artifact (INDEX:15-40); gap-matrix template (:42-69); build order (:71-77); keeper lines (:79-85); coordination rule (:87-94) | Header still "Draft. 2026-05-05" (:3). ~10 rows wrong or missing (§5.2). Only the stations-and-streams row (:28) was updated in June. |
| `proto/v0.2-workboard.md` | `1683ef3` (2026-05-06) | "Doc spine first, issues second" (:15); artifact map (:23-32); missing artifacts receptor/ringbuffer/session-api/package-boundaries (:64-92); phases (:94-125); research & impl lanes (:127-152) | Frozen since 2026-05-06. Artifact map rows L28/L29 now false (surfaces doc pushed at `1457526`; receptor contract on main since `21b46a4`). Issues #21-#27 were opened **the same day** (2026-05-05 14:39-14:42Z) the workboard said to wait — "doc spine first" was not actually followed. Does not list stations-and-streams, explicit-non-goals, prototype. |
| `proto/immune-model-addendum.md` | `dcc994b` (2026-05-05) | "addendum, not a spec change" (:9-15); chemokine = posture frame with `class` field (:35-70); receptor inputs/outputs (:72-91); T-cell = cohort quarantine (:93-112); antibody-memory (:114-126); open Qs 1-9 (:157-201); minimal grammar tighten/quarantine/all-clear/remember-by-promotion (:203-226); impl order 1-7 (:228-243); what-not-to-do (:245-260) | **Nothing implemented.** Prototype kinds are only `available`/`tombstone` (`canticle_receptor/model.py:8-10`); no `posture`, no `class`, no accord aggregator. INDEX:19 next action "fold minimal immune grammar into v0.2 rev" — no rev exists. Partially echoed normatively in receptor-contract §9 transitions 1,2,4 (receptor-contract-v0.2.md:329-399). |
| `proto/coming-down-and-loop-soothing.md` | `2b7560b` (2026-05-05) | "Exploratory note… Not normative" (:3); loop-soothing ≈ `all-clear/stand-down`, not `quarantine` (:80-98); candidate class `soothe`/`grounding-anchor`, trusted/allowlisted source, short TTL, no auto-actuation, no relay by default (:115-172); "Soothing is not amnesia" (:204) | Seed/exploratory, correctly labelled. No wire field, no receptor transition exists for `grounding-anchor`. Grounded in #7 (comment 4381859297). |
| `proto/explicit-non-goals.md` | `e0f5591` (2026-06-25) | 7 non-goals w/ citations: not OCP-MRC reliability; not ForestColl throughput; not Octopus physical sparsity; not replay/durability; not full subscription/discovery; not command/event; not request-response (:21-114); review filter (:118-130) | INDEX:27 `pressure-test`. Patched twice in June for carrier-beacon + bounded ring (`5a3c0e8`, `e0f5591`) — patches left internal contradictions (§4). Own provenance says "disclaimers belong adjacent to the spec, not inside it" (:143). |
| `proto/scope-framing-and-noosphere-mapping.md` | `5a3c0e8` (2026-06-24) | Scope ladder 0-5 (:34-142); receptor contract is the invariant (:144-162); noosphere = horizon not goal (:164-209); forbiddances (:211-231); adjacent-shapes table (:233-255); per-scope checklist (:257-268); v0.2 rev plan §14-§16 (:270-296); open Qs (:298-322) | Framing is the most precise in the periphery. Its v0.2 plan (§15 scope ladder normative; §16 adjacent shapes; §1.2 update) never executed; `proto/adjacent-shapes-survey-v0.2.md` never created (git log --all empty). Trust claim at scope-2 "pre-shared frond-key (HMAC, per §9.4)" (:75-76) contradicts stations-and-streams (:122-126). |
| `proto/openclaw-vs-canticle.md` | `b108231` (2026-05-05) | OpenClaw has a control plane, not an inter-host sensory stack (:9); lists OpenClaw control surfaces as "real, useful, shipped" (:13-22); missing planes (:86-131); boundary OpenClaw=control, Canticle=signal (:133-165); MUST/SHOULD (:167-200); build order (:202-215) | Content ~80% duplicated in the other two OpenClaw docs (§7). "Shipped" is only true of the karmaterminal fork branch (§6.1). |
| `proto/openclaw-inter-host-io-surfaces-and-spec.md` | `1457526` (2026-05-05), never edited | Same-host surfaces (:16-39), inter-host via adjacent surfaces (:41-52), 5-plane MUST (:110-118), MUST 2-7 (:120-157), SHOULD 1-5 (:159-195), layers A/B/C (:199-224) | Single commit; INDEX:23 says "diff/merge adjacent handoff notes into stable pair" — never done. Its OpenClaw statements are accurate vs the RFC (§6.1). |
| `proto/openclaw-surfaces-vs-missing-surfaces.md` | `1457526` (2026-05-05), never edited | Checklist matrix (:16-29); per-scope candidates single-host/LAN/multi-subnet/air-gap (:82-161); belongs/does-not-belong (:163-178); work items (:189-197) unchecked | All 7 "work items to cut next" (:191-197) still unchecked in text. Issue #25 (its artifact issue) open, 0 comments since 2026-05-05. |
| `prototype/README.md` | `65e6705` (2026-07-25) | "Runnable, bounded experiments… without claiming protocol or production status"; lists `ringserver-udp-cue/`, tracked by #49 | Accurate. #49 still open; PR #50 byte-identical to landed code (scout finding). Sub-README (`prototype/ringserver-udp-cue/README.md:5-29`) records the verdict that EarthScope Ringserver 4.5.4 is TCP-only (DataLink/SeedLink/HTTP) and SeedLink v4 is TCP — so the prototype is "a custom Binary Canticle UDP cue, not standard SeedLink". Native ringserver proof never run (:81-87). |

Issue state relevant to periphery (all read-only via GitHub MCP):
- #21 integration tracker — open; last comment 2026-06-16 (Silas: "receptor-contract… still absent on origin/main"; since fixed by PR #28 merged 2026-06-25). Artifact table in body still says "pushed", checklist all unchecked.
- #22-#27 artifact issues — all open, **0 comments**, never updated since creation 2026-05-05 14:42Z, even though #22 (receptor) and #23 (ringbuffer) artifacts landed.
- #33, #36, #37, #39, #40 — closed 2026-06-25 (stations-and-streams questions resolved). #38 (stream_id collision policy) open.
- #35 README refresh — open. #48 Scope-2 trust envelope — open, unassigned. #30 HAProxy membrane — open conjecture. #51 short-TTL disposition frames — open, assigned Ronan (writer) + Emeric (adversarial reviewer), Emeric's comment 5779422617 gives 10 invariants (CONDITIONAL ACCEPT for spec work only).

---

## 2. Plane model and scope ladder

### 2.1 Planes — the docs do not agree on how many there are

| Source | Planes named |
|---|---|
| `proto/TASK-BRIEF.md:25-29` | **4**: signal (Canticle: posture, chemokine, atmosphere, weak signals), control (OpenClaw addressed work / ownership / durable receipts), state ("only the narrow promoted subset that truly deserves convergence"), membership (liveness / suspicion / discovery) |
| `proto/openclaw-vs-canticle.md:170` | 4 (same): "separate membership / control / signal / state planes" |
| `proto/openclaw-inter-host-io-surfaces-and-spec.md:110-118` (MUST 1) | **5**: membership/liveness, signal/sensory, control/harness, ledger/memory, bridge/federation — "One omnibus bus should not own all five." |
| `proto/openclaw-surfaces-vs-missing-surfaces.md:16-29` | **7 labels** in the Plane column: Signal(-adjacent), Control(-adjacent), Memory/ledger, Membership, Interface, Bridge, State |
| `spike/two-planes-the-ledger-and-the-binary.md:41-54` (2026-06-18) | **2** on a different axis: Ledger plane (Discord/GitHub/repo — durable, cross-host now) vs Binary plane (canticle + `continue_delegate`+bridge — fast, no replay) |
| Keeper line (surfaces:7; inter-host:256) | "Nerves, hormones, memory, executive control — not one omnibus bus" (4 organs) |
| Issue #21 body | assigns Elliott "four-plane decomposition" |

Precise synthesis of what each plane means where it is defined:
- **Signal plane** [SAYS]: Canticle's own; posture / chemokine / threshold-shift hints, weather/cards, weak liveness hints, quarantine/all-clear/receipt frames "as part of sensory grammar", TTL-bounded lossy context coloring (openclaw-vs-canticle:146-154; surfaces:163-170). Internal layering is wire (stupid) → receptor/judgment core (deterministic) → interface (normalized) (inter-host:199-219; receptor-contract §3). [DECIDED] Spec exists (protocol-spec-v0.1, stations-and-streams-v0.2, receptor-contract-v0.2, ringbuffer-contract); code = localhost cue receptor only.
- **Control plane** [SAYS]: OpenClaw keeps addressed work, durable routing, wake, receipts-that-matter, retries (openclaw-vs-canticle:135-144). Canticle "must not become" task ownership / retries / command channel / irreversible-action transport (:156-165). [DECIDED] same-host only in OpenClaw (continuation on fork branch; queue on main — §6.1); cross-host control is unowned (#20 open; RFC:648 explicitly unspecified).
- **State plane** [SAYS]: "narrow convergent promoted state… small replicated subset only, after receptor/ledger stabilize" (surfaces:29); "memory survives TTL only by explicit promotion" (TASK-BRIEF:44). [DECIDED] Nothing specified — no promotion API, no replication mechanism. "Selective replication / anti-entropy for promoted subsets" appears only as a multi-subnet candidate (surfaces:138).
- **Membership plane** [SAYS]: "who is present / degraded / unhealthy / locally overloaded" — "adjacent to SWIM / Lifeguard / Serf territory, not Canticle proper" (openclaw-vs-canticle:88-96); SWIM/Lifeguard gossip at LAN (surfaces:105-107). Open work item "Decide whether membership lives inside canticle repo or adjacent substrate" (surfaces:194, unchecked). [DECIDED-ish] The carrier-beacon (stations-and-streams-v0.2.md:17-42) gives **presence + head-sync + liveness** ("carrier-drop… presumed offline", :32) — i.e. a weak membership signal did land inside the signal plane; explicit-non-goals #5 (:81-90) blesses this as "minimum viable live discovery". Real membership (false-suspicion handling) still undecided.
- **Ledger/memory** (5-plane version) [SAYS]: append-only canonical `frames` ledger + `quarantine_flags` + derived projections (surfaces:26,117-118; openclaw-vs-canticle:116-121). [DECIDED] ringbuffer-contract.md defines receipt record/ops; prototype persists replay claims + subject tombstones in SQLite (`canticle_receptor/state.py:23-83`).
- **Bridge** [SAYS]: "same body, slower clothes"; translates transport/policy, never ontology; never a second receptor (inter-host:141-146; surfaces:140-142,207). [DECIDED] Nothing implemented.

[ASSESS] The 4-plane (TASK-BRIEF) list omits ledger and bridge that the 5-plane list treats as first-class, and conflates "state" with part of "ledger". The two-planes spike (Ledger vs Binary) is orthogonal and actually reverses the surfaces doc's classification of Discord/GitHub as "Stopgap" (surfaces:18-19 vs two-planes:12-21). An RFC needs one normative plane list; recommended: signal, control, membership, ledger (with "promoted state" as a sub-policy of ledger), bridge — and state explicitly that Canticle owns only signal (+ weak liveness), specifies ledger receipt shape, and defines bridge invariants; control and membership are external.

### 2.2 Scope ladder (scopes 0-5) — `proto/scope-framing-and-noosphere-mapping.md`

Conformance ambition [SAYS] (:40-44): v0.2 **MUST** be implementable at scope-2; **SHOULD** at scope-1 and scope-0 via degenerate adapters; **MAY** at scope-3+; implementations MUST declare target scopes. Implementation order (:285-288): scope-2 daemon → scope-3 relay → scope-5 file-replay; scope-4 "v3.x territory".

| Scope | Wire (:259-266 + §1.x) | Trust | Discovery | Receptor |
|---|---|---|---|---|
| 0 in-process (one session) | function calls; "what `continue_delegate(targetSessionKey)` substrate (#580 work) already exposes" (:53-54) | implicit | none | implicit |
| 1 single-host (many sessions) | unix socket / IPC / shared SQLite; "`continue_delegate` with `targetSessionKey`… landed in v2026.5.3" (:63-64) | per-host | local config | per-session, maybe host daemon |
| 2 single-LAN (design center) | UDP multicast / subnet broadcast, "UDP broadcast/multicast is free" (:69-71) | pre-shared frond HMAC key (:75-76) | DNS SRV/mDNS bootstrap + carrier-beacon live presence (:74) | per-host daemon, full Tables A/B/C |
| 3 multi-LAN relay | relay via WireGuard/TLS/SSH, or DTN bundle (RFC 4838) (:86-89) | per-frond keys; relay re-signs or forwards (:94-96) | SRV across zones; relay = proxy-station `relay_<frond>` (:91-93) | same contract; evidence carries relay path |
| 4 cross-trust-domain | gateway-mediated; frames signed by origin AND trust-bridge gateway (:109-110) | federated trust gradient; default `tighten-frond-discriminator` vs foreign (:115-117) | explicit federation config, no mDNS | tighter thresholds; foreign quarantine chemokines never affect own stations (:112-113) |
| 5 air-gap | file-replay adapter, `observedAt = import time`, `emittedAt` preserved so TTL kills old frames (:128-136) | bundle-internal signing | bundle manifest | same contract; "TTL is air-gap-protective" |

Competing ladders [SAYS]: surfaces doc uses 4 rungs (single host / trusted LAN / multi-subnet / air-gap, :82-161) — no scope-0, no cross-trust rung. inter-host SHOULD 2 uses the same 4 (:167-172). TASK-BRIEF:34 wants interfaces to declare "same-host / cross-host / delayed-import" (3-valued); inter-host MUST 2 (:120-127) uses 4 values (local session / same gateway host / bridged cross-host / air-gap).

[ASSESS] against owner intent:
- **Internet-based UDP listeners have no rung.** Scope-3 is fronds-to-fronds via tunnels; scope-4 is org-to-org via a trust gateway. An anonymous/partially-trusted public listener on the internet (the "lighthouse / broadcast station" case, and #30's Phase-3 "public broadcast solidor.io… anything with a socket can listen") is not modelled. Multicast is not routed on the public internet, so internet delivery means unicast fan-out by a station or relay (which needs a listener registry — collides with non-goals #5/#7, §4) or AMT (Automatic Multicast Tunneling, RFC 7450, https://www.rfc-editor.org/rfc/rfc7450) — [ASSESS; RFC not cited anywhere in repo].
- **Scale.** Scope-2 is "a small cohort's atmospheric coordination… Not a planetary brain" (:78-79); bandwidth math assumes 4 princes, "100+ stations" ceiling (stations-and-streams-v0.2.md:92-103). Owner's "potentially thousands of agents" is outside the design center.
- **Scope-0/1 ownership conflict.** scope-framing treats OpenClaw `continue_delegate` as the scope-0/1 canticle substrate (:53-54, :63-64); surfaces doc says single-host Signal = "local receptor + ringbuffer only" and Control = `continue_delegate` (surfaces:90-95). So is same-host enrichment canticle signal plane or OpenClaw control plane? Unresolved.
- **"UDP multicast is free" is only true on one L2 segment** (broadcast always; multicast floods without IGMP snooping, needs PIM across routers). Owner's doubt about LAN multicast without supporting hardware is legitimate and not addressed by any periphery doc; issue #2 (wire: multicast vs broadcast vs mmap) open since 2026-03-14.

---

## 3. Immune / chemokine model — concrete mechanism vs metaphor

### 3.1 Concrete (specified with fields/rules) [SAYS]
1. **Chemokine = `posture` frame with a `class` field** (immune-model-addendum.md:44-56). Provisional classes (:58-66): `tighten-frond-discriminator` (signed-only surfacing), `quarantine-station:<id>` (drop from atmosphere/ringbuffer), `lower-attention` (shallower ring, faster age-out), `widen-listen` (surface unsigned/experimental), `soft-listen` (suspend posture filters). Plus `rescind-quarantine-station:<id>` (:120) and `all-clear` (receptor-contract:348-367). Unknown classes MUST be ignored (:258-260).
2. **Receptor inputs** (:79-85): HMAC validity, station allow/quarantine list, lens filter, schema compat, TTL freshness, per-station rate cap. **Outputs** (:87-91): `surface` / `ringbuffer-only` / `drop` / `quarantine-flag`.
3. **Cohort accord**: N members issuing same `quarantine-station:<id>` = stronger signal; provisional **≥2 distinct member-ids** (:104-107, :159-161). Anti-soft-coup: single member cannot quarantine another (:256-257).
4. **Antibody memory**: persistent per-station flag surviving TTL; cleared by rescind accord, local manual rescind, or max-age (default "until next-day") (:114-126).
5. **Minimal grammar** (normative-intent): tighten / quarantine / all-clear-stand-down / remember-only-by-explicit-promotion (:203-226); echoed by TASK-BRIEF:44, coming-down:228-234, #21 guardrails.
6. **Receptor transitions** (receptor-contract-v0.2.md §9, :329-418): T1 valid chemokine raises threshold (records decay deadline); T2 all-clear lowers after decay window; T3 stale/invalid ignored-but-accounted; T4 repeated hostile + accord → `quarantine_action` + optional antibody flag; T5 normal frame reclassified under shifted threshold ("proof that chemokine is a field change").
7. **Safety-sweep seams** (open Qs 7-9, :178-201, flipped "landable" by `dcc994b`): half-open state after `tighten` (circuit-breaker analog), per-(station,stream) refractory window after `tighten`, constitution/sovereign guidance referenced by content hash.
8. **Loop-soothing** candidate `grounding-anchor`/`soothe` class: allowlisted source, short TTL, no auto-actuation, no relay by default, effect limited to temporary receptor modulation (coming-down:115-172).

### 3.2 What is actually implemented [DECIDED]
- **None of 3.1 items 1-8.** Prototype (`prototype/ringserver-udp-cue`) implements the nearest analogues but not chemokine-driven: issuer/key allowlist, `issuer_quarantined` status, persistent **subject tombstones** (antibody-memory-like, keyed by digest not station), persistent replay claims, 60-s max TTL, 5-s future skew, Ed25519 signatures, typed accept/reject/quarantine receipts with closed reason enums (`canticle_receptor/model.py:8-48`, `receptor.py:23,70-83`, prototype README:46-57). Quarantine there is **local config**, not cohort accord.

### 3.3 Pure metaphor / rhetoric [ASSESS]
- "T-cell lancing" = just a name for station quarantine; "anaphylactic over-response" = open question whose only mitigation is human governance ("cohort-canon-pin review + figs-as-arbiter", :170-173).
- scope-framing §3.2 organism table (:189-209): chanters = sensory neurons, ringbuffer = local field potential, receptor contract = spinal cord, inference = cortex, HMAC = skin. No mechanism beyond the naming.
- #30 cell-membrane mapping (HAProxy = extracellular matrix; "concentration gradient = ringbuffer TTL decay"; "health checks = relay criteria") — explicitly "conjecture-to-design, not canon".
- "attenuation is probably the point, not a bug" (openclaw-vs-canticle:200) — no attenuation function specified anywhere.

### 3.4 Gaps / contradictions in the immune model [ASSESS, evidence-backed]
1. **Accord is unforgeable-only-with-per-station keys, but the spec's key is shared.** Spec v0.1 §9.4 signs with "a pre-shared frond-key" HMAC-SHA256 (protocol-spec-v0.1.md:492-496); scope-framing repeats it for scope-2 (:75-76). Any holder of a shared HMAC key can mint frames for N station-ids, so "≥2 distinct member-ids" accord (immune:159-161) and the anti-soft-coup guarantee (:256-257) provide **no protection against a single compromised member**. Per-station asymmetric keys are required — stations-and-streams punts Ed25519 to a "v0.3 overlay" (:122-126); #48 (trust envelope) is open and unassigned; the prototype already uses per-issuer Ed25519. Three incompatible scope-2 trust stories coexist.
2. **v0.2 wire has no signature to discriminate on.** `tighten-frond-discriminator` = "restrict surfacing to HMAC-signed frames only", but stations-and-streams base layer "assumes trust-of-LAN" with no signature field (:122-126). The flagship chemokine is a no-op on the v0.2 wire.
3. **No concentration/dose semantics.** Biology's chemokine gradient is magnitude + decay + receptor density. The model has only a binary class and an accord count; no intensity, no decay curve (T1 records a "decay deadline" only), no amplification/relay threshold. #51's disposition frames and Emeric's invariant 10 ("rate is not intensity") pull the opposite way (don't infer intensity from repetition) — which matters if items loop.
4. **Cohort-scale assumptions.** "frond-member", reserved prince prefixes (§4.2), "figs-as-arbiter", accord ≥2 — all assume ~4-6 known members. Owner's "thousands of agents responding to a security threat" needs accord thresholds as a fraction/quorum, key distribution, and revocation (#48 Q4) — none exist.
5. **Quarantine vs no-auto-actuation.** immune §7 says a chemokine "MUST NOT automatically mute frames… volitional" (:249-250) yet receptor T4 produces `quarantine_action` deterministically when accord threshold met (receptor-contract:383-399), and T1 raises thresholds deterministically. "Volitional" here effectively means "local policy configured by the hearer" — the RFC should say so explicitly, because the owner's security-response use case wants exactly this deterministic local reaction.

---

## 4. Explicit non-goals (verbatim-ish) and conflicts with owner intent

### 4.1 Non-goal inventory across periphery
From `proto/explicit-non-goals.md`:
1. Not OCP-MRC reliability — "No connection-oriented service… No SACK/NACK… No congestion control… No multipath spraying… No reliability spectrum" (:23-37).
2. Not ForestColl throughput-optimality — no coordinated schedule, no max-flow sizing, no collectives (:39-54); graph-theory primitives allowed (:54).
3. Not Octopus physical-constraint sparsity — sparsity is volitional; no layout compilation (:56-68).
4. Not a replay/durability layer — "**No catch-up.** A prince that joined late hears what is *currently* being chanted. No history-replay channel. No 'since-token' parameter." (:75); "No byte-perfect replay" but bounded min(depth,TTL) ring replay allowed (:76); "No identity-of-frame" (:77).
5. Not full subscription/discovery — "No subscription registry at the sender" (:86); no participant table / DDS discovery (:87); "No QoS negotiation" (:88); carrier-beacon + SRV bootstrap are the allowed exceptions (:90).
6. Not command/event semantics — "Frames are not commands"; not events; no causal precedence (:92-99).
7. Not request-response — "No tuner-to-station messages… does not send 'please retransmit seq N'… does not send 'I'm subscribed'… The wire is one-way per chanter" (:107-110); "**Stations don't have inboxes** at the canticle layer" (:112).

Other non-goal/forbiddance lists:
- TASK-BRIEF hard guardrails (:37-44): "no auto-actuation on receive"; "threshold-shift != command"; "bridge translates transport/policy, not ontology"; "raw receipt stays separate from interpreted atmosphere"; "judgment always points back to source frame"; "memory survives TTL only by explicit promotion".
- Spec v0.1 §1.2 (protocol-spec-v0.1.md:51-64): not command channel, not consensus, not RPC, not reliable, "**Not a weapon**… 'we don't do weapons'"; §9.2 No auto-actuation (:464-477): "Receiving a frame MUST NOT trigger a Claude turn… MUST NOT auto-broadcast a response… MAY enrich the Claude session's *next* turn-context IF the session is already running an agent-turn AND has tuned in… `subscribe()`… MUST NOT be used to wake a Claude session"; §7.4 (:393-398) "atmospheric content is **not auto-injected** into the Claude prompt".
- openclaw-vs-canticle §3.3 (:156-165) / surfaces §4 (:172-178): not task ownership, retries/backoff, command channel implying auto-actuation, irreversible-action transport, secret/credential substrate, bulk artifact/patch/long-log bus, canonical shared truth.
- scope-framing §3.3 (:211-231): no single source of truth, no auto-actuation, no unanimity, no centralized broker.
- immune §7 (:245-260): no auto-actuation, no cohort-coercion, no inter-frond surveillance/central reputation DB, no soft-coup, unknown classes ignored.
- coming-down "What not to do" (:183-218): no auto-sedation/muting, not truth arbitration, not ambient pressure, not per-turn catechism.
- README Key Principles (:39-45): connectionless, "No replay. No catch-up", atmospheric not commands, volitional.

### 4.2 Conflicts with owner's current intent

| # | Non-goal (source) | Owner intent | Conflict? [ASSESS] |
|---|---|---|---|
| C1 | "no auto-actuation on receive" (TASK-BRIEF:39; spec §9.2 :464-477; openclaw-vs-canticle:179) + "not auto-injected" (spec §7.4 :393-398) | "trusted clients could directly enrich remote context"; "a session might listen to a stream and notify other sessions in its harness"; respond to a security threat across thousands of agents | **Partial conflict.** (a) *Silent enrichment of next turn* is arguably allowed by §9.2 bullet 3 only if the session "is already running an agent-turn AND has tuned in"; OpenClaw `silent` mode prepends content as `System:` context on the recipient's next turn automatically (RFC continue-work-signal-v2.md:224, :247) — that is auto-injection in §7.4's terms. (b) *Waking* a session (OpenClaw `silent-wake`, RFC:248, "immediate turn grant", :1074) on frame receipt is **flatly forbidden** by §9.2 bullets 1 and 4. (c) The compliant path already exists: a listening session/sub-agent whose own turn is running (e.g. a self-elected `continue_work` polling cadence) reads atmosphere and *elects* `continue_delegate(mode=silent|silent-wake, fanoutMode=tree|all)` — actuation stays in OpenClaw's control plane (the RFC's "mast-cell pattern", RFC:1074, :1491). A deterministic receptor→`enqueueSessionDelivery` bridge without a deciding session in the loop needs an explicit RFC amendment (e.g. "tune() = standing per-session consent to `silent` enrichment from verified issuers; wake never on receipt"). OpenClaw's `crossSessionTargeting` gate (default `disabled`, RFC:1076-1085) is the precedent for such an opt-in. |
| C2 | "No replay. No catch-up." (README:42); "no subscription, no acknowledgment, no replay" (spec:30); non-goal #4 "No catch-up… No since-token" (:75) | Items **LOOP (re-broadcast) at a controllable frequency until TTL expiry** | **Resolvable but currently contradictory.** Non-goal #4 bullet 1 forbids catch-up while bullet 2 (patched `e0f5591`) allows "replay-from-ring" within min(depth,TTL). ringbuffer-contract.md:67 defines `replay(station:stream, since_seq\|since_ts, limit)` — literally a since-token. stations-and-streams says the ring lives "at the station" (:85) and late joiners "replay-from-ring" (:87), but non-goal #7 forbids any tuner→station request — so the **only** mechanism consistent with all three is the owner's: the station **re-sings its ring on a loop (carousel)** so "what is currently being chanted" = everything still alive in the ring. **No doc names the loop/carousel mechanism, its cadence, or how a re-sung frame carries remaining TTL.** Emeric's #51 invariant 1 ("Remaining life never resets… Replay, queueing, bridge delivery… inherit the remaining lifetime") is the right rule and must apply to loop re-broadcasts. |
| C3 | Dedup semantics: ringbuffer-contract §4 "accepted-as-existing / no-op" (ringbuffer-contract.md:118-130) vs prototype | Looping re-broadcast of the same item | **Direct implementation conflict.** Prototype returns `RejectReceipt(REPLAY)` for a repeated notice (`canticle_receptor/receptor.py:78-79`; `tests/test_receptor.py:156-163`) and persists replay claims 24 h (`state.py:25`). A carousel would produce a stream of rejects. The RFC must make "same frame identity heard again within TTL" a benign no-op, distinct from a *replay attack* (same identity after expiry, or altered). |
| C4 | Non-goal #7 "No tuner-to-station messages… Stations don't have inboxes" (:107-112) + #5 "No subscription registry at the sender" (:86) | (a) "easy tooling to put TTL items on a station:stream" from OpenClaw sessions / Claude Code TUI clients; (b) internet UDP listeners | **Conflict in both directions.** (a) Client→station submission is an inbox. It can be framed as control/ingest plane (Ringserver's model: DataLink TCP write, SeedLink TCP read), but the periphery never says so; the prototype is itself an inbound UDP cue receptor. (b) Internet unicast fan-out needs somebody to hold listener addresses (registration = tuner→station message + registry). Only coherent answer: push registration into a relay/membrane overlay (#30 Layer 2) and declare it outside "canticle base" per the non-goals' own overlay rule (:9). SeedLink itself is TCP with sequence-number resume (prototype README:23-25) — i.e. a since-token over a connection — so SeedLink-speaking dashboards (ews-concept-new, nerv-ui) can only sit behind such an overlay/bridge. |
| C5 | Non-goal #1 "No congestion control… Frames go out at the chanter's chosen cadence. Network drops are network drops." (:33) | internet UDP + controllable loop frequency | **Conflict on internet paths.** Fine on a LAN; on the internet, IETF UDP usage guidance (RFC 8085 / BCP 145, https://www.rfc-editor.org/rfc/rfc8085) expects applications to limit rate/respond to congestion. A carousel loop multiplies load by (TTL / loop interval). Needs at least rate caps per station/relay (scope-framing open Q5 "loud frond" :316-319). [ASSESS] |
| C6 | "Trust-of-LAN; signing punted to v0.3 overlay" (stations-and-streams:122-126) | internet listeners; "trusted clients"; security-threat response | **Conflict.** Trust-of-LAN cannot hold on the internet or at fleet scale; signing must be base-layer for any non-LAN scope. #48 exists for exactly this and is unstarted. |
| C7 | "Not a weapon" (spec:61-64); immune §8 quotes "establish control of heterogenous agents" (:264-267) | "attuning a fleet of agents to a purpose", "respond to a security threat" | Tone/ethics tension, not a mechanical one. Security response ≈ "defensible discrimination" (§9.4) and immune model — compatible if the frames remain hints and actuation is local policy (C1). |
| C8 | Scope-2 design center "small cohort… Not a planetary brain" (scope-framing:78-79) | thousands of agents | Scale conflict (see §2.2). |
| C9 | README:34 "graph mutations as structured datagrams"; prototype permits only `sha256:` subject digests ("notices cannot represent… transcripts, graph mutations", prototype/ringserver-udp-cue/README.md:41-44) | "chatter, shared chain-of-thought" | Prototype's closed schema can't carry chatter at all; it's a pointer/notice channel. Stations-and-streams payload (`content_bytes` opaque, :44-58) can. Direction must be chosen. |
| C10 | decoherence spike: Binary plane value = "no replay ⇒ no stale present" (spike/the-decoherence-axis-2026-06-19.md:30-45) | looping until TTL | Looping a **superseded live-state item** until TTL recreates the stale-replay failure the spike describes. Needs supersession (latest-per-key wins / pluck / `supersedes` field). Pluck (stations-and-streams:60-69; bytewalk Q5) is the only existing withdrawal primitive. [ASSESS] |

Compatible with owner intent (no conflict): lossy/best-effort (#1), no consensus, TTL-bounded, volitional listening, DNS SRV bootstrap (spec §5, :238-307; non-goal #5 exception), HAProxy-as-membrane (not ruled out by any non-goal; #30 treats it as Phase-3 overlay).

---

## 5. Staleness

### 5.1 README claims vs tree (verified with `git ls-tree` / `git log --all`)
| README claim | Reality |
|---|---|
| `proto/` — "Prototype broadcast sender/receiver (UDP, Node.js)" (README:50) | `proto/` holds **15 markdown** design docs, zero code. **No `.js`/`.mjs`/`.ts`/`package.json` has ever existed on any branch** (`git log --all --name-only` → none). Only code: `prototype/ringserver-udp-cue/` — **Python**, receptor-only, loopback-only (`udp.py:17-22`). |
| `schema/` — graph schema (README:51) | Never existed on any branch. |
| `exercises/` — trading cards (README:52) | Never existed on any branch. |
| `spike/` (README:49) | Exists: 6 files (4 Silas March spikes + `two-planes…` 2026-06-18 + `the-decoherence-axis…` 2026-06-19). |
| Unlisted | `prototype/`, `references/` (papers incl. `2510.03215v2.pdf` added `b46a45a` 2026-09-17, `memory-capsules.md` `36c9dca`), `scratch/notes_on_carrier_wave.md` (`f61e7ca` 2026-08-23). |
| "Wire: UDP on the LAN (10.0.0.0/24)" (:33) | Still the spec assumption; owner now wants internet listeners. |
| "~60 seconds… No replay. No catch-up." (:42) | Superseded: per-stream TTL (e.g. 5 min, stations-and-streams:86) + bounded ring replay; prototype caps 60 s. |
| "Delivery: `\| silent` enrichment into OpenClaw sessions" (:35) | Closer to owner intent than the later spec §7.4/§9.2 (see C1). |
| "OpenClaw `continue_delegate`: PR #38780, shipped 2026-03-13" (:59) | Flagged stale by #35. In `/home/user/openclaw`, `continue_delegate` is **absent from `origin/main`** (only a TaskFlow test string `continue_work`, `src/plugins/runtime/runtime-taskflow.test.ts:184`) and present on `origin/codeagent/85651-upstream-1ba243c8-gates` (RFC header "Status: Implemented"). |
| "Four princes… One gardener: figs" (:63) | #35: cohort is six; "gardener" retired. Newer seats appear in issues (rune, emeric). |

### 5.2 INDEX rows that are wrong now (`proto/INDEX.md`)
- :3 header "Draft. 2026-05-05" — last edit 2026-06-24.
- :17 `README.md` `active`, next "refresh after sibling handoff docs settle" — untouched since `888900a`; should be `stale` + link #35.
- :18 `protocol-spec-v0.1.md` "revise into v0.2 spec shell" — no v0.2 shell exists anywhere.
- :19 immune addendum "fold minimal immune grammar into v0.2 rev" — not done; grammar lives only in addendum + receptor §9.
- :20 receptor-contract "cohort cosign… decide split points" — landed on main via PR #28 (`21b46a4`, merged 2026-06-25); row does not record landing; #22 still open; split undecided.
- :21 scope-framing "integrate into v0.2 §15 + §1.2" — not done.
- :22-23 upstream dependency pinned to `origin/main@1457526` (2026-05-05).
- :28 stations-and-streams next action "Initial adapter implementation and contract tests" — the only prototype (#49/`65e6705`) does **not** implement this wire (JSON digest notices, Ed25519, no beacon/ring/CBOR). No adapter or contract tests for stations-and-streams exist.
- :29 `adjacent-shapes-survey-v0.2.md` *(planned)* — never created in this repo; content lives off-repo at `karmaterminal/caels-petals-fall@cael/canticle-200-rounds` (`13736c6`, `68b68fe`, `3df185d`) per #21 and immune:178-182.
- :30 issue #21 "keep checklist current" — checklist fully unchecked; artifact table stale; last activity 2026-06-16.
- :33-35 `session-api-contract.md`, `adapter-contract.md`, `canticle-contract-tests` — none exist (git log --all empty); #24/#27 open with 0 comments.
- :39 `spike/silas-teams-context.md` "still relevant?" — Silas's #21 comment (4714453698, 2026-06-16) recommends `frozen-provenance`; not applied.
- **Missing rows**: `prototype/` + `prototype/ringserver-udp-cue/` (#49); `proto/stations-and-streams-v0.2-open-questions-bytewalk-cael.md` (`07e4e58`); `spike/two-planes-the-ledger-and-the-binary.md`; `spike/the-decoherence-axis-2026-06-19.md`; `scratch/notes_on_carrier_wave.md` (introduces `station:root` mantra + content-free carrier loop — a concept absent from proto/); `references/memory-capsules.md`; `references/papers/*`. Branch-only artifacts (open PRs / orphan branch) not indexed: `proto/return-stage-anti-coercion-addendum.md` (#34; **linked from main's `spike/two-planes…:5` → dangling on main**), `docs/ring-broadcast-substrate.md` (#44), `research/silas/2026-05-05-next-cut.md` (#29), `proto/{send-side-draft,receive-side-draft,threshold-fire-taxonomy-v2}.md` (orphan `ronan/20260614/send-receive-threshold-landing`, no PR).

### 5.3 Workboard / TASK-BRIEF staleness
- v0.2-workboard.md:25 README "partially stale" (understated); :28 surfaces doc "new, local draft; should be pushed" (pushed `1457526`); :29 receptor contract "exists on 🌊 branch, not local main" (false since `21b46a4`); missing-artifacts 3-4 (:81-92) still missing; Phase-1 bullets 1-2 (:97-98) done; doesn't know about stations-and-streams, non-goals, prototype.
- TASK-BRIEF build order: step 6 "UDP same-LAN adapter" not done (loopback prototype); session API (4) and package boundaries (5) absent.

---

## 6. OpenClaw surfaces gap matrix

### 6.1 Verification of what the canticle docs say OpenClaw has
Checked in `/home/user/openclaw` (remote `karmaterminal/openclaw`; `origin/main` = `14ead1fc9`, 2026-09-26) and the RFC `docs/design/continue-work-signal-v2.md` on `origin/codeagent/85651-upstream-1ba243c8-gates` (~26K words; header "Status: Implemented").
- `continue_delegate`/`continue_work`/`request_compaction`: **only on the codeagent branch** (e.g. `src/agents/openclaw-tools.continuation.ts`), **not on origin/main**. [DECIDED for this checkout; note the local history may be shallow — rev-list counts were inconsistent — but `git grep` on origin/main finds no `continue_delegate`.] So canticle docs' "real, useful, shipped" (openclaw-vs-canticle:13) is true of the fork branch, not mainline.
- Return modes: `silent` (passive enrichment, no wake), `silent-wake` (enrichment + heartbeat wake), `post-compaction` (RFC:247-249); targeted return to same-host session keys via `session-delivery-queue` with byte-identical envelope (RFC:494); `fanoutMode` tree/all (RFC:1068-1074, "mast-cell pattern"); cross-session targeting gated by `agents.defaults.continuation.crossSessionTargeting`, **default `disabled`** (RFC:1076-1085); guardrail defaults `enabled:false`, `maxChainLength 10`, `costCapTokens 500000`, `maxDelegatesPerTurn 5` (RFC:1451-1462).
- `session-delivery-queue` / `enqueueSessionDelivery`: **on origin/main** (`src/infra/session-delivery-queue-storage.ts:39`); `enqueueSystemEvent` on main (`src/infra/system-events.ts`, re-exported e.g. `src/cron/isolated-agent/delivery-outbound.runtime.ts:16`). These are the concrete integration seams for bc#5 "Gateway ingestion".
- `sessions_send`/`sessions_spawn`/`sessions_list`/`sessions_history`: on main; in-process to a single gateway; visibility model `src/plugin-sdk/session-visibility.ts` (#20 cites :20). Matches inter-host doc (:26-34).
- Cross-host: RFC:648 "**Cross-host wire exposure.** The queue is local to one gateway… this RFC deliberately does not specify that contract." RFC:234 names "cross-host publish/subscribe, and SeedLink-style broadcast" as the higher broadcast layer. RFC:1702 explicitly anticipates "a **Binary Canticle** layer above this RFC: ringbuffer-backed `station:stream`…; DNS SRV discovery…; local-network multicast; station relays in the shape of DHCP helper/relay agents; and receive-side bridges that can turn a heard stream into quiet context or queued delivery." RFC:921-927 sketches a stream-publish tool (agent supplies `streamRef`, payload, `broadcast|addressed`; tool picks UDP fan-out vs `enqueueSessionDelivery` bridge).
- Integrity: RFC §7.2 threat table (:1466-1484): queue hops plaintext, "no integrity verification", "no authenticated system-event origin", announce origin "not cryptographic proof".

### 6.2 Consolidated gap matrix (canticle docs' rows, verified + my additions)

| Capability | OpenClaw today (evidence) | Canticle docs' position | What canticle must add [ASSESS] |
|---|---|---|---|
| Same-host silent enrichment of another session | Yes — `continue_delegate(mode=silent)` + session-delivery-queue (fork branch; queue on main) | "Canonical (intra-host)… Extend only as durable addressed work substrate" (surfaces:20) | Nothing on the OpenClaw side; canticle must define the **receive-side bridge**: receptor judgment `surface` → `enqueueSessionDelivery`/`enqueueSystemEvent` with provenance (station, stream, seq, key-id, judgment id) and remaining TTL; and the consent rule (C1). |
| Same-host wake / fan-out ("there is a fire") | Yes — `silent-wake`, `fanoutMode: tree/all`, gated by `crossSessionTargeting` default disabled | Not addressed; spec §9.2 forbids wake-on-receipt | Rule: wake only via an OpenClaw session's own election, never canticle receipt (or explicit RFC amendment + gate mirroring `crossSessionTargeting`). |
| Cross-host addressed work (control) | No — RFC:648; #20 open | "partially missing"; not canticle's job (surfaces:64-68; openclaw-vs-canticle:135-144) | Keep out of canticle base; note as external dependency. |
| Cross-host lossy signal/atmosphere | No | Core canticle target (openclaw-vs-canticle:98-106) | Wire (stations-and-streams), sender, loop/carousel semantics, LAN + internet delivery, relay. |
| Session tool surface (sing/tune/listen/posture) | No; RFC:921-927 projection only | Spec §7.2 illustrative API (`tune/atmosphere/sing/posture/nexus.digest/lookup`); #11, #18 (typebox strawman), #30 (`LISTEN/SEND/HUSH/WHO`) | An OpenClaw plugin or channel-type (#30 open scoping Q) **and** a Claude Code surface — **no periphery doc mentions Claude Code TUI clients**; spec §7.2 only says "via openclaw or via MCP-server". MCP server + CLI needed for owner's Claude Code case. |
| Membership / discovery across hosts | No | Missing; SWIM/Lifeguard adjacent (surfaces:24,105-107) | DNS SRV registration tooling (spec §5) + carrier-beacon; decide surfaces:194. |
| Frame ledger / receipts | Local SQLite for sessions/TaskFlow only | Missing; `frames` + `quarantine_flags` + projections (surfaces:26) | Ringbuffer-contract impl; prototype's SQLite claims/tombstones are a start. |
| Raw receipts vs interpreted atmosphere | No | Missing (surfaces:27) | Session API contract (#24, unwritten). |
| Frame authenticity | Not provided (RFC §7.2) | HMAC shared key (spec §9.4) vs trust-of-LAN (s&s) vs Ed25519 (prototype) | Base-layer per-station signatures + key lifecycle (#48) — mandatory before any bridge into OpenClaw queues, since those queues carry no origin authentication. |
| Bridge (subnet / air-gap) | No | Missing (surfaces:28) | Bridge invariants note (surfaces:193 unchecked). |
| Observability | Yes — RFC §6.6-6.8 OTEL `continuation.*` spans, explicitly "future-work preparation… for an inter-node ringbuffer `station:stream` broadcast layer" (RFC:1324) | Not mentioned in periphery | Reuse the span schema across the bridge. |
| SeedLink dashboards (ews-concept-new, nerv-ui) | n/a | Prototype: Ringserver is TCP-only; UDP cue → private DataLink publisher (prototype README:5-29, :77-79) | A DataLink/miniSEED-framing bridge; runtime proof never run. |

---

## 7. Duplication and what to fold into an RFC

| Cluster | Docs | Evidence of duplication | Recommendation [ASSESS] |
|---|---|---|---|
| A. OpenClaw boundary | `openclaw-vs-canticle.md`, `openclaw-inter-host-io-surfaces-and-spec.md`, `openclaw-surfaces-vs-missing-surfaces.md`, `TASK-BRIEF.md` | Plane-by-interface lists near-identical (vs-canticle:61-82 ≡ inter-host:66-96); MUST lists (vs-canticle:169-181 ≈ inter-host MUST 1-7 :110-157); "must refuse" (vs-canticle:156-165 ≈ surfaces:172-178); build order ×3 (TASK-BRIEF:46-54, vs-canticle:202-215, surfaces:180-187); INDEX itself flags "diff/merge… into stable pair" (INDEX:23-24) | Fold into one RFC section "Relationship to OpenClaw (control plane) and receive-side bridge", with the verified gap matrix (§6.2) as an appendix. Supersede all three; keep TASK-BRIEF as the RFC abstract. |
| B. Coordination spine | `INDEX.md`, `v0.2-workboard.md`, issue #21 (+ #22-#27) | Two copies of gap-matrix template (INDEX:42-69 vs workboard:44-62) and anti-amorphous checklist (INDEX:62-67 vs workboard:53-60); three independent status tables, all stale differently | Keep one INDEX (regenerated from tree), retire workboard, close/refresh #21-#27 against the RFC. |
| C. Guardrails / keeper lines | TASK-BRIEF:37-44,62-65; INDEX:79-85; workboard:183-190; surfaces:199-207; inter-host:254-260; vs-canticle:227-232; #21 | Same 6-8 sentences restated 7 times | One normative "Invariants" section in the RFC (MUST language), cited by ID. |
| D. Non-goals | spec §1.2; explicit-non-goals.md; scope-framing §3.3; vs-canticle §3.3; surfaces §4; immune §7; coming-down "what not to do"; README principles | Overlapping and now contradictory (C2-C5) | RFC "Non-goals" section (keep citations), with owner-intent resolutions: carousel loop, internet overlay, submission ingest, consent rule. |
| E. Immune grammar | immune-model-addendum §2,§5,§6; receptor-contract §9; coming-down (:228-234) | Grammar restated 3×; receptor inputs/outputs (immune:79-91) vs receptor Table C | Fold grammar + class registry into RFC "Posture/chemokine classes & receptor transitions"; keep coming-down as non-normative rationale appendix; carry safety-sweep seams (half-open, refractory, hash-addressed policy) as open issues. |
| F. Scope ladder | scope-framing §1,§5; surfaces §3 (4 rungs); inter-host SHOULD 2 (4 steps); TASK-BRIEF:34 (3 values) | Different rung counts / names | RFC "Scopes" section = scope-framing §1/§5 + a new rung (or overlay) for internet/public listeners. |
| G. Plane model | TASK-BRIEF (4), inter-host (5), surfaces (7 labels), two-planes spike (2) | See §2.1 | RFC "Planes" section with a single list. |
| H. Retention / replay | README:42, spec:30 & §6, non-goals #4, stations-and-streams ring, ringbuffer-contract `replay(since_*)`, decoherence spike | Mutually contradictory (C2, C3, C10) | RFC "Retention, looping and replay" section: station ring, carousel cadence, remaining-TTL carriage, dedup-as-no-op, supersession/pluck, local `replay()` is hearer-local only. |

Docs that remain useful as standalone lineage (not folded): `spike/silas-*` (SeedLink mapping is the transport ancestor per Silas #21 comment), `explicit-non-goals.md` citations (as an appendix), `coming-down…` (rationale), `prototype/**`.

---

## 8. Unverified / open items flagged for other lanes
- **#30 HAProxy claim** ("HAProxy 3.2+ (June 2025 release added native UDP load balancing)"). Web search (2026-09-27) indicates HAProxy 3.2 community was released 2025-05-28 and that UDP load balancing is associated with the **HAProxy Enterprise UDP Module** (since Enterprise 2.9); community native UDP LB was not evident. Could not fetch primary pages (egress blocked for haproxy.com / docs.haproxy.org / loadbalancer.org). Status: **PLAUSIBLY INCORRECT — verify before the membrane design depends on it.** Sources: https://www.haproxy.com/blog/announcing-haproxy-3-2 , https://www.haproxy.com/blog/announcing-haproxy-enterprise-3-2 , https://www.loadbalancer.org/blog/how-to-do-udp-in-haproxy/ , https://docs.haproxy.org/3.2/intro.html
- README "PR #38780" and scope-framing "#580 work… v2026.5.3" (:53-54, :63-64) not verified against upstream.
- openclaw local history may be shallow (branch ahead/behind counts inconsistent); presence/absence of `continue_delegate` on origin/main was checked by `git grep`, which is reliable for tree content.
