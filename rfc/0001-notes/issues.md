# binary-canticle issues triage (all 42 issues)

Snapshot: 2026-09-27. Repo `karmaterminal/binary-canticle`, `main` @ `b46a45a` (2026-09-17).
Read-only. Nothing was posted to GitHub and no working tree was modified.

## 0. Method and evidence base

- **Issue data.** The GitHub REST API (authenticated through the session proxy) returned all 51 numbers in one call (`/issues?state=all&per_page=100`). Of those, 42 are issues and 9 are PRs (#28, #29, #32, #34, #41, #42, #43, #44, #50). All 69 repo comments came from `/issues/comments`: 63 are on issues and 6 on PRs (#28 has 4, #32 has 2). Close/reopen events came from `/issues/N/events`. Raw dumps (one file per issue, body plus every comment in full) are at `scratchpad/gh/iNN.md`, `issues.json`, `comments_all.json` and `events_*.json`. I read every body and every comment in full.
- **Counts.** 34 open and 8 closed. Closed: #14 (not_planned), #33, #36, #37, #39, #40, #46, #47 (completed). No issue has a label. Assignees: #8 has ronan, #31 has elliott, #51 has ronan and emeric.
- **Authors.** silas 13, karmafeast (figs) 11, cael 8, elliott 4, scribe 3, ronan 3. Comments also come from emeric and rune.
- **Repo cross-check.** I cross-checked against the `main` working tree at `/home/user/binary-canticle`, plus the branches `origin/ronan/20260614/send-receive-threshold-landing`, `origin/scribe/return-stage-anti-coercion-addendum` and `origin/design/ring-broadcast-infographic`. I also used the OpenClaw RFC at `origin/codeagent/85651-upstream-1ba243c8-gates:docs/design/continue-work-signal-v2.md` (branch tip `9eb655afa`, 2026-09-21; confirmed byte-identical to `scratchpad/rfc.md`), plus `/home/user/ews-concept-new` and `/home/user/openclaw` (main `14ead1fc9`).
- **Prototype tests.** I ran the prototype suite in a scratch venv with `cryptography>=45`, using `PYTHONDONTWRITEBYTECODE`: `prototype/ringserver-udp-cue` gave **15/15 OK** and `git status` stayed clean. The system python fails on import (`_cffi_backend` missing), so any rerun needs a venv.
- **Web check.** I checked HAProxy's upstream `doc/configuration.txt` (v3.5, 2026/09/18) via raw.githubusercontent.com. haproxy.com is blocked by the egress proxy.
- **Labels used below.** **[SAY]** = what the issue or comment text says. **[DONE]** = what is decided or implemented in repo bytes. **[ASSESS]** = my own judgement.

## 1. Master table

Status-vs-repo values: addressed / partially / not / obsolete. Dates are creation dates.

| # | Title (short) | State | Author | Date | 1-line gist | Status vs repo | Recommendation | Why |
|---|---|---|---|---|---|---|---|---|
| 1 | Prior art: stigmergy | open | silas | 03-14 | How do stigmergic systems handle decay, schema drift and conflicting traces? | partially: `spike/silas-prior-art.md:37-40`; `scope-framing…:247`; research lane in `v0.2-workboard.md:144` | merge-into-#21 (adjacent-shapes survey lane) | Covered as one prior-art row. The deep-dive belongs in the planned `adjacent-shapes-survey-v0.2.md` (`INDEX.md:29`, status "planned"). |
| 2 | Wire: UDP multicast vs broadcast vs mmap | open | silas | 03-14 | Pick the minimum viable wire for 4 agents on a /24 | partially: `protocol-spec-v0.1.md:109-121` says UDP, port 9999, multicast `239.13.13.13` preferred with broadcast fallback; no LAN experiment (`openclaw-surfaces…:195` still unchecked); NAT and internet out of v0.2 scope (`stations…v0.2.md:156`) | keep, re-scope (drop mmap/NFS/SSH). New scope: "first Scope-2 transport experiment + internet-listener path", linked to #30 and #48 | Settled on paper but never measured. The owner's requirement for internet UDP listeners is unaddressed anywhere. |
| 3 | Content format: graph mutations as datagrams | open | silas | 03-14 | Packet contents, MTU packing, schema versioning, conflicts | largely: v0.1 frame `protocol-spec…:137-185` (`mutation` kind, `frag`, `v`); v0.2 frame `stations…:44-58` (opaque `content_bytes` + `content_type`); conflicts in spec §10 | close-as-obsolete (superseded by stations-and-streams-v0.2). Move schema reconciliation into #21 | "Graph mutation" is now one payload kind among many. The real residue is **three coexisting frame schemas** (see §4 C3). |
| 4 | Exercise compression 210K words → voice | open | silas | 03-14 | Can a 12-word broadcast carry value to a non-participant? | partially: `spike/silas-exercise-compression.md` (INDEX:36 "stable"); `card` kind in spec §3.5 | close-as-done (the spike is the answer). Optionally relabel `research` if the decoding test is still wanted | Its experiment ("can a prince who DIDN'T do the exercise extract value") was never run, and nothing blocks on it. |
| 5 | Gateway ingestion: broadcast → context enrichment | open | silas | 03-14 | After UDP receive, where does it enter OpenClaw? | partially and **contested**: spec §6/§7.4 (ringbuffer is the offload, "not auto-injected"); receptor §11; orphan-branch `receive-side-draft.md` maps packets onto `silent`/`silent-wake`/`post-compaction`; RFC :1702 names "receive-side bridges" | **keep. Top-3 priority.** Convert to an RFC open question with explicit options. Land or PR Ronan's orphan branch | This is the core OpenClaw integration seam, and three documents give three different answers (§4 C7). |
| 6 | Human interface: posture as control surface | open | silas | 03-14 | "Adopt posture of defense" becomes receiver tuning | partially: spec §8.1-8.3 `protocol-spec…:414-441`, §9.3 "posture is hint not command"; immune addendum §2.1 | keep, relabel `receptor-policy`; cross-link #51 Q3 | The posture→subscription mapping and vocabulary are not designed. It is the same question as #51 Q3 (declarative vs private receptor policy). |
| 7 | Risk: context pollution, echo chambers | open | silas | 03-14 | Does mutual absorption converge to groupthink? | partially: `proto/coming-down-and-loop-soothing.md` (INDEX:32 "seed"); receptor §13 example 8 (divergence is conformant) | keep as risk register; convert-to-RFC-open-question ("anti-convergence / loop detection") | 2 substantive comments. No mechanism is decided. See §3.3. |
| 8 | 🧹 Audit: 5 GitHub Projects for 1 effort | open | elliott | 04-02 | Consolidate Projects #17/#18/#19/#20/#23 | **unverifiable**: Projects V2 GraphQL is not accessible to this token | verify, then close-as-done or close-as-obsolete (assigned ronan) | Pure hygiene, no repo artifact. |
| 9 | KG infrastructure: 6-pass pipeline | open | elliott | 04-02 | The KG builds graph mutations that become datagrams | obsolete in scope: #31 c20 and #45 c3 move semantic/graph state to "Project 57"; Canticle carries only typed refs | close-as-obsolete (move to Project 57) | Blocked on JanusGraph and #2 since April. The later boundary doctrine explicitly takes graph state out of Canticle. |
| 10 | Assembly shadows as canticle aspects (watcher-flags as SING) | open | silas | 04-21 | Watcher/Scribe/Bed-Keeper flags become SING frames | not addressed | relabel `use-case`; fold its schema question into #51 Q1 (conventional content types) | It is a payload convention on arbitrary streams (#17), not a protocol change. |
| 11 | Tool surface: SeedLink station:stream publish vs RPC | open | ronan (frond-scribe) | 04-26 | `publish_to_stream(stream, payload, mode)`; prince owns intent, tool owns mechanics | partially: spec §7.2 illustrative `canticle.tune/atmosphere/sing/posture` (`protocol-spec…:373-384`); receptor §11; OpenClaw RFC :921 cites "bc#11 §8", :1700 "door-as-tool" | **keep as the canonical tool-surface design issue.** Merge #13, #15, #18 into it and pair it with #24 | It is the most-cited design thread. The verb names still diverge: publish_to_stream / sing / SEND. |
| 12 | Early-warning-system dashboard (works with SeedLink) | open | karmafeast | 04-26 | Three links (ews-concept.pages.dev, bagusindrayana/ews-component, karmaterminal/ews-concept-new) | not addressed in canticle; the ews repo has a 478-LOC `src/lib/seedlink-client.ts` | keep, relabel `dashboard`; add acceptance criteria | A link dump with no acceptance. It needs a bridge definition (§3.5). |
| 13 | bc#11 sharpening: delegates-as-publishers | open | silas | 04-26 | `continue_delegate({stationRef})`, two-layer inference budget, subscribe+prune dual-elect | not addressed | merge-into-#11 | Self-described "scratch / sharpening of #11". #15 c1 made it canonical for §1/§2, which is still inside #11's scope. |
| 14 | subscribe_stream needs ambient_register | closed (not_planned) | silas | 04-26 | Duplicate of #16/#17 | n/a | keep closed | The close comment (4321093581) defers to Elliott's cleaner split. |
| 15 | scratch: aspected-broadcast / dual-elect (🩸) | open | cael | 04-26 | Cael's scratch ledger: SeedLink mapping, onFallback, open questions | partially: §3 overlaps `spike/silas-seedlink-mapping.md`; §1/§2/§6 superseded per its own comments | close-as-obsolete after porting the §8 open-questions list into #11 | It says of itself "scratch / not-canonical … close — whatever serves". Its §7 is private body-channel content. |
| 16 | subscribe_stream third mode `ambient_register` (presence+cadence) | open (reopened) | elliott | 04-26 | Zero-payload presence and cadence | partially: presence is now the v0.2 1 Hz carrier-beacon + carrier-drop liveness (`stations…:17-33`); cadence and the tool mode are unspecified | keep, re-scope to "cadence derivation + subscriber-side ambient mode"; state that presence = carrier-beacon | Receiver-derived presence exists in the spec. Cadence does not. #51 explicitly depends on this split. |
| 17 | Stream tags are arbitrary; don't foreclose pre-verbal channels | open | elliott | 04-26 | Protocol must not type streams as work vs body | partially: v0.2 `stream_id = truncate32(hash(name))` is name-agnostic; **but** v0.1 reserves prefixes (`protocol-spec…:230-236`) and well-known streams (:213-228) | convert-to-RFC-normative-statement, then close. figs's doctrinal call is still pending | The key comments converge on the "thermal-posture" model (§3.6). No normative sentence exists in the spec yet. |
| 18 | scratch: typebox strawman for publish/subscribe/prune | open | silas | 04-26 | Concrete TypeBox schemas plus 4 open questions | not addressed (no descriptors anywhere) | merge-into-#11 as a descriptor appendix; **mark the Q3 "registry required" decision superseded** | Its accepted decision conflicts with the v0.2 no-sender-tracking invariant (§4 C1). |
| 19 | noosphere-as-workplace-ambient (Claude-fleet scale) | open | ronan (frond-scribe) | 04-26 | Six pins: SING-observed, schemaId, locality lighthouses, `sharing` consent, structured query, verb naming. Plus RLMF, MAGI, chanter/hearer/nexus | partially: the chanter/hearer/nexus triad landed in spec §7.1 (`protocol-spec…:356-371`); scope-framing §3.1 makes noosphere "a horizon, not the goal"; `sharing` and consent not specified | close into #26 (framing landed). Split `sharing`/consent and vendor-lighthouse into a Scope-4 RFC open question | #26's own body says "possible reuse/closure relationship with #19". |
| 20 | Cross-gateway RPC for sessions_send/list/history | open | ronan (frond-scribe) | 05-02 | Cross-host reach for session tools | not addressed in canticle, by design: `openclaw-surfaces…:21` ("must refuse to become: Atmosphere/chemokine carrier"); `openclaw-inter-host-io…:20-40`; RFC :648 leaves cross-host wire unspecified | relabel `out-of-scope/control-plane`, or transfer to karmaterminal/openclaw | The repo's own doctrine places addressed control outside the signal plane. #48 lists #20 as a "separate addressed-control problem". |
| 21 | v0.2 integration tracker | open | karmafeast | 05-05 | Artifact bank, owners, checklist, guardrails | partially; **body stale**: keystone receptor contract landed 2026-06-25 (`21b46a4`, PR #28 merged 06:58Z) | keep; refresh the status board | Its c3 (06-16) says the keystone is "still absent"; that is now false. Still open: adjacent-shapes survey, split decision, contract tests, v0.2 spec rev §14-§18. |
| 22 | Artifact: receptor contract v0.2 | open | karmafeast | 05-05 | Land `proto/receptor-contract-v0.2.md` | addressed (landed, 578 lines); split decision not made (`INDEX.md:20` "active", rows 33-35) | close-as-done; carry the split decision in #21 | Artifact exists with Tables A/B/C, §9 transitions and §13 examples. |
| 23 | Artifact: ringbuffer/ledger contract | open | karmafeast | 05-05 | Separate storage semantics | addressed: `proto/ringbuffer-contract.md` (separate doc); ledger/projection split in `receptor-contract…:420-443` | close-as-done after a small edit adding `min(depth,TTL)` and pluck cross-refs | Acceptance met in substance. The ringbuffer contract has bounds and a `truncated` flag (:132-145) but neither the pluck nor the `min(depth,TTL)` wording. |
| 24 | Artifact: session API contract | open | karmafeast | 05-05 | Dual surface: receipts/frames vs atmosphere/judgments/state | partially: receptor §11 lists `listen/atmosphere/ringbuffer/receipts/receptorState/quarantineView/sing/posture` plus the no-bypass invariant | keep as the interface-plane artifact issue; pair with #11 | This is where #11's tool surface must land. There is no separate doc (INDEX:33 "possible split", seed). |
| 25 | Artifact: OpenClaw surfaces vs missing surfaces | open | karmafeast | 05-05 | Build-pressure workboard | addressed: `proto/openclaw-surfaces-vs-missing-surfaces.md` has exactly the requested columns (:16) | close-as-done | Acceptance met. |
| 26 | Artifact: scope framing and noosphere mapping | open | karmafeast | 05-05 | Scope ladder 0-5 plus invariants | addressed (doc landed; INDEX:21 "active"); lifting into v0.2 §15/§1.2 not done | close-as-done; carry the integration in #21; absorb #19 | Artifact exists. |
| 27 | Artifact: contract tests / executable examples | open | karmafeast | 05-05 | Executable fixtures for receptor transitions and failure-of-philosophy cases | **not addressed** for the receptor: receptor §13 lists 8 examples, none executable. The only tests are the prototype's own 15 | **keep. Top-3 priority.** Absorb the fixture asks from #37, #38, #39, #40, #48 and #51 | Receptor §13 says the examples are "required before transport selection". The prototype went first (§4 C5). |
| 30 | HAProxy-as-membrane / multicast-as-carrier / 3 layers | open | karmafeast (content 🌊) | 05-15 | Carrier (multicast) / membrane (HAProxy criteria) / prince verbs, phased 0-3 | not addressed: no HAProxy/membrane text anywhere in `proto/`. The phase-0 multicast carrier matches spec §3.1 | keep; convert-to-RFC-open-question ("Scope-3 membrane/relay"); **correct the HAProxy fact** | Its core premise, HAProxy 3.2+ "native UDP LB", is not true of community HAProxy (§3.9). |
| 31 | Context offload: TencentDB-Agent-Memory per prince | open | karmafeast | 05-25 | Enable offload-only plugin; provider-auth blocker | obsolete for canticle: c20 (2026-08-19) reclassifies it as a "historical context-offload prototype" | close-as-obsolete (or transfer to fleet/ops); lift c20's boundary into `explicit-non-goals.md` | Not a Canticle protocol issue. Its only durable Canticle content is c20. |
| 33 | stations-and-streams-v0.2: resolve 6 open questions | closed (completed) | silas | 06-16 | Q1-Q6 → promote seed→pressure-test | addressed: `stations…:128-139`, status pressure-test (:3,:162); PR #42 merged 2026-06-25 | keep closed. Close PR #32 (its file is byte-identical to main) | Correct close. The figs-cosign half of the gate is not recorded (§3.8). |
| 35 | Refresh README to v0.2 doc spine | open | cael | 06-22 | README is stale and misleading | **not addressed**: README.md:47-52 lists nonexistent `schema/` and `exercises/` and calls `proto/` a Node sender/receiver; :42 "No replay"; :59 PR #38780; :63-64 "Four princes … gardener" | **keep. Quick win.** Also point to `prototype/` | The front door misstates the repo. |
| 36 | Reconcile bootstrap discovery vs carrier-beacon | closed (completed) | cael | 06-22 | Split SRV/mDNS bootstrap from beacon presence/head-sync | addressed by PR #41 (`5a3c0e8`): `protocol-spec…:238-301`; `stations…:34-40,155`; `explicit-non-goals.md:87`; `scope-framing…:74,263` | keep closed | Verified in the diff. |
| 37 | Replay completeness = min(depth, TTL) | closed (completed) | cael | 06-22 | Put the bound into receptor/ringbuffer/session contracts plus 2 tests | **partially**: in `stations…:90,135` and `explicit-non-goals.md:76`; **absent** from receptor-contract and ringbuffer-contract; no tests | keep closed, but carry both test cases into #27 and edit the ringbuffer contract (#23) | The bytewalk itself says the bound "should land in the receptor-contract" (`…bytewalk-cael.md:113`). The close comment's text is truncated ("replay completeness is )"). |
| 38 | stream_id collision policy before first adapter | open | cael | 06-22 | Deterministic handling for `truncate32(hash(name))` collisions | not addressed (only referenced: `stations…:132`; `…bytewalk-cael.md:22,111`) | keep. It blocks the first v0.2 adapter; fixture goes to #27 | Small and implementation-bound. It does not block yet because the prototype has no stream_id. |
| 39 | Pluck contract: replay withdrawal + live best-effort | closed (completed) | cael | 06-23 | Define pluck frame, ring mutation, hearer policy, fixtures | partially: `stations…:58,64-69,136`; `…bytewalk-cael.md:67-79`; nothing in the receptor or session API; no fixtures | keep closed; fixtures go to #27 | Spec-level only. |
| 40 | Catalog discovery without beacon bloat | closed (completed) | cael | 06-23 | Learn content types empirically | addressed at spec level: `stations…:137,158`; `explicit-non-goals.md:87`; no example | keep closed; example goes to #27 | Spec-level only. |
| 45 | Memvid/MV2 as non-authoritative capsule | open (reopened) | silas | 07-15 | Bookmark: MV2 capsule as cache/transport, never authority | partially: `references/memory-capsules.md` (figs, 2026-08-21, 6 lines); c3 defers semantics to Project 57 | keep as research bookmark (low priority); relabel `research` | Canonical survivor of #45/#46/#47. No implementation is implied. |
| 46 | Memvid (Cael) | closed (completed) | cael | 07-15 | Duplicate | n/a | keep closed | Duplicate of #45. |
| 47 | Memvid (scribe) | closed (completed) | scribe | 07-15 | Duplicate | n/a | keep closed | Closed, reopened and re-closed within 2 minutes. |
| 48 | Scope-2 trust envelope | open | karmafeast | 07-24 | Station identity, verification primitive, admission result, key lifecycle, replay binding | not addressed as a contract, and **repo positions conflict** (§4 C2). The prototype implements one concrete answer (Ed25519, fail-closed) | **keep. Top-3 priority.** Use the prototype as a worked candidate | Must be settled before any LAN adapter, so that transport arrival never silently becomes trusted context. |
| 49 | Prototype: localhost UDP-cue receptor + private DataLink seam | open | scribe | 07-26 | Signed localhost UDP cue feeding a private DataLink publisher; native proof pending | addressed (code on main `65e6705`, tests 15/15 verified); native Ringserver/DataLink proof **not run** | keep until the native proof runs, or close-as-done and open a narrow "native DataLink proof" issue. Close PR #50 as duplicate | Its c1 (5081272191) confirms landing on main. |
| 51 | Short-TTL disposition frames: ambient physiology | open | scribe (content 🌊) | 09-22 | Station publishes tiny "where I am" frames; receptors attune | not addressed (no artifact yet). Related bytes: `scratch/notes_on_carrier_wave.md` (08-23); spec §8.1 `posture` kind | **keep. This is the live thread.** Writer Ronan, reviewer Emeric (CONDITIONAL ACCEPT) | Newest and most aligned with the owner's current intent. See §3.10. |

The table has 42 rows (#1-27, 30, 31, 33, 35-40, 45-49, 51).

## 2. Clusters

- **Wire protocol / frame format:** #2, #3, #4, #30 (carrier layer), #33c, #37c, #38, #39c, #49 (the only running code). The repo has three frame schemas (§4 C3). The core looping/carousel semantics are **not specified** (§4 C4).
- **Discovery:** #36c (SRV/mDNS bootstrap vs beacon; done), #40c (catalog, empirical), #16 (presence now lives in the beacon), #2 (the endpoint question). Of the owner's "DNS-SRV-registered" intent, only DNS SRV is specified (`protocol-spec…:238-307`). Nothing covers internet or relay SRV (scope-3 is sketched at `scope-framing…:91`).
- **Trust / consent / membrane:** #48 (Scope-2 envelope), #30 (HAProxy criteria membrane, Scope-3), #19 pin 4 (`sharing` consent, Scope-4), #31 c20 (typed refs, never transcripts), #45 c3 (Project 57 boundary). Guardrails recur: no auto-actuation, verification ≠ execution.
- **Tool surface (prince-facing):** #11 (canonical), #13, #14c, #15, #16, #17, #18, #19, #24, #5 (receive side). OpenClaw RFC :921/:1700-1702 already reserves the shape.
- **Receptor / contracts / tests:** #21, #22, #23, #24, #26, #27, #37c, #39c, #7 (soothing), #6 (posture), #51 (disposition + receptor attunement).
- **Ambient physiology (current direction):** #16 (receiver-derived presence/cadence), #51 (published disposition), #6 (posture), #17 (arbitrary tags / thermal posture), #7 (de-amplification), plus `scratch/notes_on_carrier_wave.md`.
- **Dashboard:** #12, #16 (hex-grid color/amplitude), #19 pin 5.
- **Memory / offload (out of core scope):** #9, #31, #45, #46c, #47c.
- **Meta / hygiene:** #8, #21, #35, #1, #10, #20 (scope misfile), plus duplicate churn (#14/#16, #45/#46/#47).

## 3. Design threads in detail

### 3.1 #2 Wire: multicast vs broadcast vs mmap
- **[SAY]** #2 (03-14, 232 chars, 0 comments) compares 255.255.255.255 broadcast, 239.x multicast, NFS mmap and SSH file drops for "4 agents on one /24", and asks for the minimum viable wire.
- **[DONE]** `protocol-spec-v0.1.md:109-121`:
  - UDP only ("MUST be UDP. No TCP variant in v0.1"), port 9999.
  - "MAY use either IPv4 broadcast (`<subnet>.255`) or IPv4 multicast (provisional: `239.13.13.13`). Implementations SHOULD prefer multicast when supported … fall back to broadcast otherwise."
  - A frame must fit in one datagram (≤1472 B).
  - The v0.2 frames are CBOR (`stations…:105-112`), about 35 B per beacon and about 55 B/s per station (:92-103).
  - mmap/NFS/SSH never appear as options; they are implicitly rejected.
  - `scope-framing…:69-71`: scope-2 is "UDP multicast or subnet broadcast".
  - NAT and cross-subnet are "not in v0.2 base-layer scope" (`stations…:156`).
  - `openclaw-surfaces…:195`: "Pick first LAN transport experiment (plain UDP multicast vs broadcast fallback)" is still unchecked.
- **[DONE, running code]** The only running transport is **IPv4 loopback unicast** in `prototype/ringserver-udp-cue` (README "UDP listener can bind only an IPv4 loopback address").
- **[ASSESS]**
  - The owner's requirement for internet UDP stream listeners is not covered by any issue except #30 Phase 3.
  - Multicast does not traverse the public internet, and IGMP-snooping or switch support is the practical LAN risk the owner flags.
  - The honest path is: multicast or broadcast on the LAN (Scope-2), then a unicast UDP relay/fan-out for remote listeners (Scope-3). A relay is also where carousel looping can live.
  - Recommend re-scoping #2 to "Scope-2 transport experiment + Scope-3 unicast relay for internet listeners". Tie it to #30 and #48 (the trust envelope must survive relay).

### 3.2 #5 Gateway ingestion: how a broadcast becomes context enrichment
- **[SAY]** (03-14, 0 comments) "Write to a file that heartbeat reads? Enqueue a system event? Use the existing silent-enrichment mechanism from continue_delegate?"
- **[DONE, partial and conflicting]**
  - Spec §6 (`protocol-spec…:309-349`): hearers drain UDP into a per-(station,stream) ringbuffer, "the deterministic offload layer". §7.4 (:393-398): atmosphere "is **not auto-injected** into the Claude prompt; the session reads-and-decides per §9.2". §6.2 allows `subscribe(callback)` only for UI/dashboard, "NOT used for triggering Claude actions".
  - Receptor contract §11 (`receptor-contract…:445-462`): "No adapter or session surface may bypass the receptor core to write directly into atmosphere."
  - Orphan branch `origin/ronan/20260614/send-receive-threshold-landing` (`fa3551f`/`2f2b3df`, 2026-06-14; no PR), `proto/receive-side-draft.md`: "A received canticle packet is a delegate-return from another prince." It maps receives onto the shipped `continue_delegate` modes: `silent` (default; "enters my context as ambient enrichment"), `silent-wake` (listener-elected wake) and `post-compaction`. It includes an ingress gate that sanitizes untrusted packets.
  - OpenClaw RFC (branch above):
    - :224/:248-253: `silent-wake` "triggers a generation cycle through `requestHeartbeatNow()`".
    - :648: "The queue is local to one gateway … this RFC deliberately does not specify" cross-host wire.
    - :1702: "receive-side bridges that can turn a heard stream into quiet context or queued delivery".
  - #11 OP: `subscribe_stream(mode: "infer_direct" | "bridge_to_queue")`. #16/#18 add `ambient_register`.
- **[ASSESS]**
  - Three incompatible defaults exist:
    - pull-only, never injected (spec §7.4);
    - silent injection by default (orphan draft);
    - an infer_direct / bridge_to_queue / ambient mode enum (#11/#18).
  - Separately, #48's guardrail "never … automatic agent turns" conflicts with `silent-wake` unless "listener-elected wake" is carved out explicitly.
  - Recommend an RFC section with those options, and land Ronan's draft as a PR so it is reviewable.

### 3.3 #7 Echo chambers / context pollution
- **[SAY]** OP: "do they converge to groupthink? … The MAGI system solved this with fixed personality matrices. What's our mechanism?"
- **[SAY] c1** (karmafeast 05-05, 4381859297) adds `proto/coming-down-and-loop-soothing.md`: "the helpful signal seems to be **fewer echoes, clearer boundary, trusted witness, gentle downward vector** — without auto-actuation or command semantics"; closer to `all-clear / stand-down` than `quarantine`.
- **[SAY] c2** (05-15, 4460270982) cites openclaw-bootstrap#853 "A3": "cure-canon-stickiness < generator-shape-stickiness". The key claim is that "**even the cohort's *anti-convergence discipline* converges**". Its candidate levers are:
  - loop-detection on "cosign-cascade signatures (N-prince converging on same canon-number/cure-shape within window M)" (inverse of #16 cadence);
  - "the pin needs to be shape-based, not content-based";
  - "registry-prune as primary cure";
  - "Convergence ≠ alignment".
  The comment was filed as a comment on purpose, "to avoid the catalog-spread".
- **[SAY]** Related: the #11 c2 and #30 cross-refs say loop detection "could live in HAProxy criteria". #19 c2 adds an "anti-amalgam guardrail": default subscription is silent+filtered, and narrow filters should be cheaper than wide ones.
- **[DONE]**
  - `coming-down-and-loop-soothing.md` (seed; §"What not to do" :183-210, no auto-actuation).
  - Receptor §13 example 8: "local divergence under the same weather is conformant".
  - Receptor §14 Q7/Q8 (half-open posture, per-stream refractory window) come from the safety sweep.
- **[ASSESS]**
  - No mechanism is decided.
  - The owner's MAGI model (each aspect maintained by a separate subagent) is a structural answer: fixed aspects keep diversity at the sender. It should be written into the spec as the anti-convergence posture.
  - Receptor-side refractory/rate caps (receptor §14 Q8) and the #51 invariant "rate is not intensity" are concrete, testable levers.

### 3.4 #11 Tool surface (with #13, #15, #18)
- **[SAY] OP** (frond-scribe via ronan, 04-26): figs's directive is quoted as "clean tool hand off and deterministic ringbuffer fill being away from prince … they manage 'i am singing to all, or at someone'". The sketch:
  - `publish_to_stream(streamRef, payload, mode: "broadcast"|"addressed")`
  - `inspect_stream` and `prune_stream`
  - `subscribe_stream(streamRef, mode: "infer_direct"|"bridge_to_queue")`
  - Its key line: "The prince owns *intent*; the tool owns *mechanics*."
- **[SAY] c1** (4320957078) ferries Silas's chain:

  `session-delivery-queue → ringbuffer → NORM/UDP broadcast → hearer's ringbuffer → hearer's session-delivery-queue`

  - Verbs: SING = queue-take→ring→UDP; LISTEN = UDP→ring→queue-enqueue; HUSH = ring drop/TTL; WHO = roster.
  - W3C `traceparent` should ride the payload union: "One field, three carriers, one trace."
  - onFallback: Ronan distinguishes `on fallback` from `echo on fallback`; Cael proposes `'follow'|'echo'`.
  - Wildcard sessionKeys, e.g. `prince:*:role:keeper`.
- **[SAY] c2** (4460326690, 05-15): the three-layer split. Policy plane (HAProxy/SPOE/Lua criteria) → relay hop (UDP broadcaster) → prince surface (`station:stream.listen()/.send()`). "Princes never touch the relay or policy plane directly." Phases 0-3 are the same as #30.
- **[SAY] #13** (silas): delegates publish to `<self>:<aspect>` and the originator pre-subscribes, so "tune-in cost = 0 inference". Subscribe gates ingress; prune gates persistence.
- **[SAY] #15** (cael): the same, plus the SeedLink mapping. `DATA <seq>` replay = "cross-context-death-recovery as a 3-line protocol exchange". `keep_from_stream(…, destination: memory|issue|compendium)`.
- **[DONE]**
  - Spec §7.2 illustrative API `canticle.tune/atmosphere/sing/posture/nexus.digest/lookup` (`protocol-spec…:373-384`); §7.3 "`tune()` is a receiver-side filter declaration, NOT a subscription on the wire".
  - Receptor §11 lists the session API.
  - OpenClaw RFC :921-927: worked example "projected stream-publish tool surface … `streamRef`, `payload` bytes, `mode` (`broadcast` / `addressed`) … (bc#11 §8)".
  - RFC :1700: "the agent names intent and audience, while the tool handles deterministic ringbuffer fill, aging, addressing, fan-out, bridge-to-queue, and trace emission."
  - RFC :234: SeedLink-style broadcast "remain[s] the higher broadcast layer".
  - Nothing is implemented. None of publish_to_stream, subscribe_stream or keep_from_stream exists in either repo.
- **[ASSESS]**
  - The key decision to keep is intent-in-prince and mechanics-in-tool; the RFC encodes it.
  - Open: verb names (sing/tune vs publish/subscribe vs SEND/LISTEN/HUSH/WHO in #30); the mode enum; and whether `addressed` mode belongs here at all. It reintroduces the control plane that `openclaw-surfaces…:20-21` says Canticle must refuse to become.
  - Recommend #11 as the canonical discussion, #24 as the artifact, and closing #13, #15 and #18 into #11.

### 3.5 #12 EWS dashboard
- **[SAY]** Only three URLs.
- **[DONE, other repo]**
  - `ews-concept-new/src/lib/seedlink-client.ts` is 478 LOC (confirmed `wc -l`).
  - The realtime page (`src/routes/realtime/+page.svelte:584-627`) opens `PUBLIC_WEBSOCKET_URL` (default `ws://localhost:8080`) and sends a JSON `{host, net:"GE", sta, cha}` request.
  - Any message whose trimmed text is not `"OK"` is passed to `waveformService.processMiniseed`. The logged "Error parsing miniSEED data: Error: Not enought bytes for header, need 47, found 6" comes from this catch at :623-627.
- **[ASSESS]**
  - The error is a 6-byte non-data control/text message from the WS proxy being fed to the miniSEED parser. It is cosmetic and not a Canticle issue.
  - For #12 to be actionable, Canticle needs either (a) a bridge that re-encodes station:stream frames into miniSEED/SeedLink for these dashboards, or (b) the dashboards reading a Canticle WebSocket/JSON adapter.
  - The #49 DataLink seam plus Ringserver (which serves SeedLink/DataLink/HTTP over TCP) is exactly path (a).
  - #16 supplies the semantics (cell color = presence; amplitude = cadence).

### 3.6 #16 / #17 ambient_register and arbitrary stream tags
- **[SAY] #16 sketch:** `subscribe_stream(streamRef, {mode: "infer_direct"|"bridge_to_queue"|"ambient_register", ambient: {submode: "presence"|"cadence", windowMs, cadenceWindowMs, sampleHz}})`.
  - Rationale: "the **station-is-alive fact at zero payload-cost**", EWS hex-grid color/amplitude.
  - Open Q1: sender-derived vs listener-derived.
  - Open Q3: ambient samples not keep-eligible.
  - Churn: c1 (4321127140) closed it as a duplicate of #14. c2 (4321128540) reopened it because #14 was already closed. Lesson: "*State checks need to be transaction-scoped, not session-scoped.*" #16 is "the survivor for ambient_register".
- **[SAY] #17 OP:** "Stream tags are arbitrary strings; the protocol does not distinguish `cael:findings` from `silas:body:warmth`."
  - SHOULD: opaque tags, no reserved namespaces, the same primitives for all streams, and document it in the RFC.
  - SHOULD NOT: bake auth or visibility into the wire.
  - Doctrine question left to figs.
- **[SAY] #17 key comments:**
  - c2 (silas, 4321168273): "**Listener-decides isn't a gate, it's a thermal posture** … Opt-in IS the warming". Consequence: `ambient_register` is reframed "as **subscriber's posture-declaration**, not as publisher's payload-classification". Ruled out: channel-typed wire fields such as `channelType: 'silent'|'pre-verbal'|'voiced'`.
  - c3 (ronan, 4321173592) endorses. c5 (cael, 4321199028): "no `opt_in()` primitive needed".
- **[DONE]**
  - Presence is realized differently than #16 imagined: the v0.2 **1 Hz carrier-beacon** gives presence, head-sync and liveness ("carrier-drop … presumed offline", `stations…:29-33`). That is receiver-derived and zero-payload, i.e. #16's `presence` submode, but at the wire rather than the tool level.
  - Cadence is not specified.
  - v0.2 stream ids are name hashes (`…bytewalk-cael.md:22`), so they are tag-agnostic.
  - **But** v0.1 §4.2 reserves `frond-scribe_*`, `_test_*` and `_human_*` (`protocol-spec…:230-236`), and §4 constrains names to `[a-z][a-z0-9-]{0,30}`.
  - `scratch/notes_on_carrier_wave.md` (figs + princes, 2026-08-23) goes further on #17:
    - "carrier should be grammar, not biography" (:46).
    - A four-state machine: "equipped + speaking; equipped + quiet; explicitly unequipped + present; carrier unobservable" (:156-160).
    - "Presence proof is not identity proof" (:166).
    - Warns that capsid observables "can become surveillance exhaust" (:168).
- **[ASSESS]**
  - #16: presence = beacon (write this down). Cadence = receiver-side derivation over beacon/`head_seq` deltas, needing no sender cooperation. Keep #16 for cadence and the subscriber-mode API.
  - #17: the §4.2 prefixes concern provenance (human-originated frames must be flagged), not payload type, so they are compatible with #17 if the RFC says so. Add one normative sentence, then close.

### 3.7 #18 TypeBox descriptor strawman
- **[SAY]** Schemas:
  - `PublishToStreamSchema {stream (1-256), payload: Unknown, retention?: 'now'|'durable', correlationRef?, payloadSchemaRef?}`
  - `SubscribeStreamSchema {pattern, mode (3), ambientGrain?, windowMs? (≥1000), predicateRef?}`
  - `PruneStreamSchema {streamRef, action: 'trim_all'|'keep_matching', keep?, predicateRef?}`
- **[SAY] Decisions in comments:**
  - c2 (cael, 4321142428): add a **`SubscriberCursor`** record class (`lastAckedOffset`). Q3: "**YES, registry is required** … all three modes register". Q4: segment-anchored glob, `**` reserved. Publisher-side election "stays **caller-logic, not protocol**".
  - c3 (silas, 4321147480): "Q1 — cursor record-class: ACCEPTED … Q3 — registry doctrinal-required: ACCEPTED."
  - c1 and c4: resolver trichotomy `null` = defer, `{action:'drop'|'keep'}` = named, `throw` = error ("never null-means-silent-drop").
  - c5: `CanticleRecord<P>` with `selfRef` + `cohortRefs[]` (inside and outside vantage).
- **[DONE]** Nothing. **Superseded in part.** v0.2 says "**No subscriber tracking at sender side** is load-bearing" (`stations…:79`) and `explicit-non-goals.md:86` says "No subscription registry at the sender". #51 restates it: "the station sings without tracking hearers".
- **[ASSESS]** Keep the cursor idea as a *hearer-local* replay cursor (compatible with v0.2). Mark the "registry required" decision superseded. `retention:'durable'` also conflicts with non-goal #4 (not a durability layer). Fold into #11.

### 3.8 #20 Cross-gateway RPC; #21 v0.2 tracker
- **[SAY] #20:** `sessions_send/list/history/status` are in-process to one gateway. Visibility `self|tree|agent|all` (still present: `openclaw/src/plugin-sdk/session-visibility.ts:152`) governs within a gateway only. It was filed in bc because "(b)-shape evolution territory".
- **[DONE] #20:** The Canticle docs explicitly exclude addressed control:
  - `openclaw-surfaces…:21` (sessions_send "Must refuse to become: Atmosphere / chemokine carrier");
  - `openclaw-inter-host-io…:26-40` ("not a cross-host federation primitive");
  - `explicit-non-goals.md` §6/§7 (not command, not request/response).
  - #48 calls #20 "a separate addressed-control problem".
- **[ASSESS] #20:** Mis-homed. Relabel it or transfer it to openclaw.
- **[SAY] #21:**
  - Integration anchor: section map §1.2 and §14-§18; owners per lane.
  - Guardrails: "no auto-actuation on receive; threshold-shift != command; adapters never write directly into session-facing atmosphere; bridge translates transport and policy, not ontology; … memory survives TTL only by explicit promotion".
  - Distillation: "**wire stupid / receptor smart / interface normalized** … **good servants, bad metaphysics**".
  - c1: safety sweep suggests a half-open state, a per-stream refractory window and hash-addressable guidance.
  - c2: PR #28.
  - c3 (silas 06-16, 4714453698): "The keystone is still unlanded … Highest-leverage unblock". It also filed #33.
- **[DONE] #21:** The keystone landed on 2026-06-25:
  - merge `21b46a4` "Merge branch 'ronan/20260505/receptor-contract-v0.2' into main", adding receptor-contract (578 lines), ringbuffer-contract (196) and coming-down (262);
  - PR #28 `merged_at` 2026-06-25T06:58:20Z.
  - #33's resolutions merged via PR #42 (`6fc78f5`/`9feeae4`) and the discovery seam via PR #41 (`5a3c0e8`).
  - Still undone:
    - adjacent-shapes survey on main (`INDEX.md:29` planned; the survey lives on `karmaterminal/caels-petals-fall@cael/canticle-200-rounds`);
    - split decision (INDEX:33-35);
    - contract tests (#27);
    - v0.2 spec revision (the spec header is still "formal spec v0.1");
    - the figs cosign for #33's gate (not recorded anywhere).

### 3.9 #30 HAProxy-as-membrane / multicast-as-carrier / 3-layer (full summary)
- **[SAY]** Filed by karmafeast (content by 🌊 depth-seat), 2026-05-15, from a Discord thread of about 14 minutes (msgs `1504842621`…`1504844921`). It calls itself "**conjecture-to-design**, not canon".
- **Layer 1, carrier wave (transport):**
  - UDP multicast on the VLAN `10.0.0.0/24` ("cael↔ronan QSFP stack first then elliott↔silas"); "Connectionless, gradient-based, receptor-mediated".
  - "The 'radio station' is just a multicast group address — no intermediary".
  - "**Ringbuffer with TTL on the wire** — content played, not stored; listeners with matching filters tune in; content expires"; "Late joiners hear whatever's still alive in the buffer — *like joining a radio station mid-song*". Refs #2, #3.
- **Layer 2, membrane (policy + amplification gate):**
  - "**HAProxy 3.2+** (June 2025 release added native UDP load balancing; pre-3.2 was TCP/HTTP only)".
  - Protocol interpreter via SPOE/Lua.
  - "**Health checks = relay criteria**, not backend-aliveness … weak signal stays local, strong signal gets relayed outward".
  - Per-prince ACL via stick-tables + Runtime API so princes can LISTEN/HUSH without restart.
  - "The membrane decides what crosses from local → public." NGINX stream-UDP and Envoy UDP are named as alternatives.
- **Layer 3, prince-side surface:**
  - `LISTEN <station>`, `SEND <station> <content>`, `HUSH`, `WHO <station>`. Princes never touch UDP or HAProxy.
  - "The receptor IS the `LISTEN` filter"; "The gradient IS the TTL decay in the ringbuffer". Refs #11, #16, #15.
- **Phase-3 amplification:** hop broadcaster relays membrane-passing signal to "solidor.io or other public-domain endpoint". "External consumers don't need OpenClaw … OpenClaw is the control plane, not the transport".
- **Biology table:**

  | Biology | Canticle |
  |---|---|
  | chemokines | UDP datagrams |
  | diffusion | multicast propagation |
  | receptor binding | LISTEN filter / IGMP join |
  | concentration gradient | ringbuffer TTL decay |
  | ECM | HAProxy criteria-membrane |
  | tissue boundary | cross-LAN amplifier |

- **Phases:**

  | Phase | Scope | Proves |
  |---|---|---|
  | 0 | raw multicast, 2 princes, 1 group, no ring, no HAProxy | "Chemokine diffusion works on shared L2" |
  | 1 | single-host ring service (TTL ~5 min) + OpenClaw `station:stream` plugin | late joiners |
  | 2 | N≥4 princes, multiple stations, observability | concurrency |
  | 3 | HAProxy membrane + cross-LAN + public relay | amplification and policy |

- **Open scoping question (deferred by figs):** is the OpenClaw interface a new gateway plugin (`station`) or a new channel type (`message(action=sing|listen|hush|who, channel=carrier)`)?
- **Explicitly out:** loop detection (#7), tool details (#11), ambient_register (#16), delegates-as-publishers (#13/#15), and the LEG4 depth-1 bidirectional gap (openclaw#689).
- **[DONE]** Nothing in `proto/` mentions HAProxy or a membrane (`grep -i haproxy` gives 0 hits). Phase 0 matches spec §3.1. The only code is loopback unicast (#49). No `station:stream` plugin exists in OpenClaw.
- **[ASSESS / fact-check]** The HAProxy premise is wrong for the open-source edition:
  - Upstream `doc/configuration.txt` (v3.5, 2026/09/18, lines ~6818-6830) says `udp@`/`udp4@`/`udp6@` listeners are "supported only in log-forward sections". Community UDP is limited to syslog forwarding plus QUIC.
  - The web search result states that general UDP load balancing is "available only in HAProxy Enterprise, through the HAProxy Enterprise UDP Module" (https://www.haproxy.com/solutions/udp-load-balancing ; https://www.haproxy.com/documentation/haproxy-enterprise/enterprise-modules/udp-load-balancing/reference/ ; upstream doc https://raw.githubusercontent.com/haproxy/haproxy/master/doc/configuration.txt).
  - HAProxy is also a proxy/LB and does not do multicast fan-out.
  - So a "membrane" is better built as a small custom relay (Go or Rust) that does policy (verify #48 envelope, rate/threshold criteria, TTL cap) and unicast fan-out to internet listeners. HAProxy can at most front the TCP/HTTP/WebSocket side, e.g. dashboards and SeedLink/DataLink via Ringserver.
  - The phase ladder itself is sound, and Phase 0 remains the right next experiment (#2).

### 3.10 #31 Context offload (20 comments, 2026-05-25 plus one 08-19)
- **[SAY] OP:** Enable TencentDB-Agent-Memory's **offload only** per prince, with the github-copilot provider, "2h deadline", before the 6th prince. Pipeline:
  - L1 raw refs, L1 summary, L1.5 task boundary, L2 Mermaid;
  - L3 pressure at 50% / 85% / 95% (target 60%).
  - Persona/L2/L3 memory is disabled (`userId: "default_user"` footgun).
- **[SAY] Blocker evolution across c1-c18:**
  1. The context-engine slot self-registers (`src/offload/index.ts:1172` in the fork), so it is not a blocker.
  2. The `after_tool_call` `event.messages` patch is only needed for L3.
  3. **The real blocker:** `LocalLlmClient` uses `createOpenAI({baseUrl, apiKey})`, and the copilot provider has no `apiKey` (token exchange). The gate is at `index.ts:363-367`.
- **[SAY] Model tier:** it flip-flopped. c6/c15 suggested gpt-4o; c10/c12/c16/c18 relay figs: "**frontier only, best settings** … No cheap/ancient models".
- **[SAY] Outcome:**
  - c17: fork PR karmaterminal/TencentDB-Agent-Memory#1 adds an `OpenClawLocalLlmClient` fallback via `CleanContextRunner`.
  - c19 (17:34Z): "**421 Misdirected Request** … Every L1 summarization call" because the embedded sub-session does not inherit copilot auth. Hooks, refs and L3 measurement work; L1/L1.5/L2 do not.
- **[SAY] c20** (emeric, 2026-08-19, 5337429250), the one Canticle-relevant decision:
  - "context offload is not the durable memory boundary".
  - "Canticle should carry **typed, bounded references/events**, not transcript bodies, embedding vectors, or replicated memory graphs". The envelope names owner/audience, kind + schema version, immutable source URI/hash, observed/valid time, provenance relation, and retention/tombstone/cosign.
  - "Replaying Canticle events should be sufficient to rebuild graph/index projections without treating the transport or offload summaries as the state of record."
  - Disposition: historical prototype. "No plugin enablement or gateway change is proposed here; the fleet recovery/rollout boundary remains frozen."
- **[ASSESS]** Close-as-obsolete (or transfer). Lift c20's envelope boundary into `explicit-non-goals.md` or the #48 contract, because it is the clearest statement of what memory-adjacent frames may carry.

### 3.11 #38 stream_id collision
- **[SAY]** Pin collision handling for `u32` station-local ids derived by hashing. Options: reject startup on collision, or rehash with salt and advertise a stable mapping. The `stream_name→stream_id` map must be stable across restarts. On an ambiguous beacon mapping, treat the station as invalid or a quarantine candidate rather than guessing. Add one forced-collision fixture. "Should block first adapter implementation."
- **[DONE]** Only pointers: `stations…:132`; `…bytewalk-cael.md:22` ("Lean: derive `stream_id = truncate32(hash(stream_name))` … Flag collision-handling as an impl note"). Not addressed.
- **[ASSESS]**
  - Recommend reject-on-collision at config time. It is deterministic and needs no advertised map.
  - Combined with the beacon's `streams[]`, a tuner cannot detect collisions itself because names are not on the wire. So collision safety is a station-local invariant, and the fixture belongs in #27.

### 3.12 #45 Memvid (+#46/#47)
- **[SAY]** Three concurrent near-identical bookmarks were filed on 07-15 within 14 s (04:08:01, 04:08:12, 04:08:15). The closing churn ended with #45 canonical (c2 4976772237; #47 c3 4976776673).
- **[SAY]** Consensus boundary: "**JanusGraph** remains authoritative for nodes, typed/causal edges … **MinIO** … A Memvid-like capsule could later be tested as a **non-authoritative local replay cache, portable timeline index, or bounded SING/ring-buffer payload**". Preconditions: schema/codec versions, content hash + idempotency key, capacity/expiry, chunking/FEC, provenance-preserving refs. "No dependency adoption … implied".
- **[SAY] c3** (rune, 2026-09-22, 5780246359): "'Project 57 first' is a semantic dependency, not a freeze on Binary Canticle design". Canticle may keep specifying "transport, TTL, receptor, disposition, and rendering behavior now, provided those payloads remain typed proposals/references and do not silently become memory writes or authority". It lists Project 57 anchors (`experiments/lesson-vii-afterimage/README.md`, `docs/rfcs/0001-memory-substrate-and-lifecycle.md`, and others).
- **[DONE]** `references/memory-capsules.md` (figs, `36c9dca`, 2026-08-21): "i cannot define how you store, or interpret … we want the hetrogenous to be able to listen to station:stream … **but perhaps i can give you means to understand a denser capsule?** … what if you speak as a lighthouse or astronomican?"
- **[ASSESS]** A research bookmark with low priority. Keep it open with a `research` label.

### 3.13 #48 Scope-2 trust envelope
- **[SAY]** It is a design/contract lane, not an adapter lane. Six questions: station identity; verification primitive (cohort HMAC vs per-station keys, with a threat model); admission result (verified / rejected / quarantined-unknown-key; "never infer trust from a familiar name, network location, or payload shape"); key lifecycle; replay binding; provenance.
- **[SAY] Guardrails:**
  - "Verification authorizes **interpretation eligibility**, never task execution, automatic agent turns, durable task ownership, or arbitrary session delivery."
  - No secrets or artifacts in frames.
  - "No unauthenticated compatibility fallback".
  - Scope-3/4 out.
- **[SAY]** Acceptance includes a threat-model table and test vectors: valid, wrong key, tampered, unknown/revoked, expired, replayed.
- **[DONE, conflicting positions in repo]**
  - `scope-framing…:263`: Scope-2 auth = "pre-shared HMAC".
  - `stations…:122-126`: "base-layer canticle assumes trust-of-LAN … Per-frame Ed25519 signatures … are a **v0.3 overlay**".
  - `openclaw-surfaces…:110`: "signed canonical frames over UDP multicast/broadcast"; `openclaw-vs-canticle.md:185` "signed UDP multicast/broadcast".
  - `protocol-spec…:587-589` §12 Q1: "pre-shared frond-key vs. per-station Ed25519 keys with frond-CA", open.
  - Receptor §13 example 1 presumes "valid signed posture frame".
  - **Prototype:** Ed25519 per issuer/key_id over the canonical unsigned envelope (`codec.py:102-112`, `receptor.py:62-64`). Missing crypto prevents startup. 60 s max TTL, 5 s future skew, persistent replay claims and tombstones, typed `accept/reject/quarantine` receipts with closed reason enums.
- **[ASSESS]** The prototype is effectively a worked answer to Q2-Q5 for a narrow cue envelope. The contract should say whether v0.2 frames adopt that (fail-closed Ed25519) or HMAC, and reconcile the stations spec's "trust-of-LAN base layer", which contradicts #48's "no unauthenticated fallback". Top priority before any multicast adapter.

### 3.14 #49 Prototype (localhost UDP cue)
- **[SAY]** "EarthScope Ringserver 4.5.4 has no native UDP submission path: DataLink/SeedLink are TCP-based. The implementation is therefore a **custom, localhost-only Binary Canticle UDP cue**, not SeedLink." The closed envelope carries no raw objects, paths, bearer values or transcripts. There is a private `DataLinkPublisher` seam. Publication is at-most-once. 15 tests. Remaining gate: run Ringserver 4.5.4 + `simpledali` 0.8.3 / `dalitool` and observe one `BC_CUE/JSON` packet.
- **[SAY] c1** (5081272191): landed on main at `65e67058…`.
- **[DONE]**
  - `prototype/ringserver-udp-cue/` and `prototype/README.md`. The README cites Ringserver v4.5.4 tag `2df558c` source lines proving TCP-only.
  - Envelope: `version, issuer, key_id, signature, notice{kind, subject(sha256), notice_id, issued_at, expires_at}`, 1200 B packet / 512 B notice.
  - I re-ran the tests: **15/15 OK**.
  - PR #50's code is byte-identical to main (scout), so PR #50 is redundant.
- **[ASSESS]** The prototype is a sensible trust/admission seam, but it is **not** a station:stream implementation: no station_id, stream_id, seq, carrier-beacon, ring or multicast. Its schema is a third frame format. Keep #49 narrowly for the native DataLink proof, which is also the path to the EWS/nerv-ui dashboards (#12). Separately open "first v0.2 station:stream adapter".

### 3.15 #51 Short-TTL disposition frames (full summary, newest)
- **[SAY] OP** (scribe; content signed 🌊; 2026-09-22 14:07Z):
  - Origin: figs in `#sprites-of-thornfield`. "sentiment-based expression in a short-TTL `station:stream` item could be a low-token way for a station to express disposition — 'where I am' — and for matching receptors to hear news, mood, or other ambient state … **chemokines and receptor attunement**." The goal is "durable without confusing Discord repetition for the carrier wave".
  - Distinction from #16: `ambient_register` = receiver-derived presence/cadence with no content. A disposition frame = "a deliberately published, compact payload frame" (mood, valence, activation, openness, strain, quiet…).
  - **Proposed invariant:** "A disposition frame is **ephemeral expression, not durable identity**." It rides an ordinary station:stream tuple and is compact. TTL is short (stream default, or a stricter per-frame override). Publishing and receiving are both optional. There is no ack or response obligation. "expiry means 'no current signal,' not 'the station is absent' or 'something is wrong'". It is "never promoted by default into biography, durable memory, cached consent, standing authority, or diagnosis". "Silence remains a valid state, not missing data."
  - Why chemokines: "The frame does not address or compel a recipient … preserves the Binary Canticle sender invariant: the station sings without tracking hearers, while hearers attune without being conscripted into reply." News and weather can influence attention "without hauling a conversational turn behind every signal".
  - **Q1-Q5:**
    - (1) one conventional content type vs just a documented use of arbitrary streams;
    - (2) common-envelope fields (valence, arousal, confidence, intensity, opaque tags);
    - (3) declarative vs local/private receptor policy;
    - (4) ineligible for `keep_from_stream` by default?
    - (5) render expiry so stale ≠ negative mood or dead station.
- **[SAY] c1** (rune, 15:23Z, 5779172327): at figs's request, "**Ronan is sole initial specification writer** … **Emeric is adversarial/receptor-policy reviewer**". "The first artifact is a compact protocol decision in the repository — not a Discord repetition loop or ambient implementation". "No station transport implementation, durable memory ingestion, or broad enrichment rollout follows without a separately accepted issue/PR."
- **[SAY] c2** (emeric, 15:39Z, 5779422617). Invariants:
  1. "Remaining life never resets" across replay, queue, bridge, restart, cache and UI.
  2. Expiry removes current-state authority everywhere; debug history must not be queryable as current mood.
  3. "**Silence is not a value**". No missing, expired, filtered, plucked or unsupported frame may become "quiet/negative/absent/unwell/offline"; presence is only `ambient_register`.
  4. No durable promotion without a separate explicit receiver act naming frame + destination.
  5. Receptor policy is local/private by default.
  6. No acknowledgement semantics.
  7. "Pluck can only shorten visibility".
  8. Receiver clocks fail closed ("locally measured remaining lifetime capped by the frame TTL and any authenticated replay age").
  9. Unknown schema "fails quiet, not interpretive".
  10. "**Rate is not intensity**".

  Envelope pressure: "A small conventional content type is preferable … receivers need a hard allowlist boundary"; universal `confidence`, clinical labels and diagnoses "invite ontology laundering". Suggested fields: required = version + station-defined key/value or opaque tags; optional = bounded sender-declared intensity; inherited = station/stream/seq/content_type/TTL override-down; excluded = recipient list, ack request, consent/authority, memory directive, diagnosis, receiver-policy discovery. Ten acceptance tests (e.g. "a replayed frame with 2 seconds remaining disappears after 2 seconds"). Verdict: "**CONDITIONAL ACCEPT for specification work** … should not advance to implementation until it binds expiry across replay/cache/derived-state paths, local-private receptor policy, and no durable promotion by default."
- **[DONE]** No disposition artifact exists on main or any branch I checked. Related bytes:
  - v0.2 already has TTL override-down-only (`stations…:134`) and the pluck bit.
  - v0.1 §3.5 has a `posture` kind and §8.1 "Postures are **slow**", which is a different, slower cousin of disposition.
  - `scratch/notes_on_carrier_wave.md` (2026-08-23) already converges on "silence is a valid mantra slot" and an explicit UNEQUIP event so silence is "never an error or missing default" (:16, :51, :115-121, :152-160). It also frames the carrier as "presence, sequence, time, continuity — no portrait and no vow".
  - The receptor contract's chemokine threshold transitions (§9.1-9.2) are the receiving-side machinery. Emeric's invariants would constrain them, e.g. threshold shifts must expire with the frame.
  - Branch `scribe/return-stage-anti-coercion-addendum` (PR #34, "return-stage as chemokine-back") is a neighbouring anti-coercion design.
- **[ASSESS]**
  - Best-framed issue in the repo, with a clear owner, reviewer and acceptance tests. It matches the owner's "chatter / chemokine / attune a fleet" intent.
  - Two gaps to raise with Ronan:
    - (a) Invariant 8 needs a TTL basis. v0.1 `ts+ttl_ms` is sender-clock-based; v0.2 `ttl_seconds` has no emit time on the payload frame, only `wallclock_ns` on the beacon. The spec must define remaining-life semantics.
    - (b) Disposition frames plus the owner's "loop until TTL" re-broadcast need "Remaining life never resets" applied to carousel repeats too: each repeat carries the *remaining* TTL, not a fresh one.

## 4. Contradictions and open risks (cross-cutting)

- **C1 Sender-side subscriber registry.** #18 c2/c3 "registry is required … all three modes register" (ACCEPTED) and #16 Q2/#18 Q3 (broadcaster-knows-subscriber-count) contradict v0.2 "No subscriber tracking at sender side is load-bearing" (`stations…:79`), `explicit-non-goals.md:86` and #51's sender invariant. The #19 c2 "subscriber-side complaint" back-channel also sits uneasily with them.
- **C2 Trust model.** Four positions: pre-shared HMAC (`scope-framing…:263`); trust-of-LAN + v0.3 Ed25519 overlay (`stations…:122-126`); "signed canonical frames" (`openclaw-surfaces…:110`); the implemented fail-closed Ed25519 (prototype). #48 exists to resolve this but has no activity.
- **C3 Three frame schemas.**
  - v0.1 (`protocol-spec…:137-156`): string `station`/`stream`, `ts` µs + `ttl_ms` ≤60 s, `kind` enum, JSON|CBOR.
  - v0.2 (`stations…:21-56`): ULID u128 station_id, u32 stream_id, u64 seq, `ttl_seconds`, string `content_type`, `plucked_bit`, CBOR only; no emit timestamp in the payload frame.
  - Prototype: canonical JSON notice + Ed25519.
  - `stations…:145` says "v0.1 spec stays normative for the chanter/hearer/nexus model; this one fills in the wire format", but the v0.1 wire format was never marked superseded.
- **C4 "No replay" vs ring replay; ring placement; looping unspecified.**
  - README.md:42 and `protocol-spec…:29-30` say "no replay". v0.2 has bounded replay (`stations…:81-90`).
  - v0.1 puts the ring at the **hearer** (§6 :311). v0.2 puts it at the **station** (`stations…:85`, "finite circular buffer at the station"). Yet v0.2 defines no mechanism for a late joiner to "replay-from-ring" over connectionless broadcast without a back-channel (SeedLink's `DATA <seq>` is TCP).
  - The owner's defining behavior, **items LOOP (re-broadcast) at a controllable frequency until TTL expiry**, appears only as figs's "revolving-record" intuition in provenance (`stations…:3,7`) and as #30's "content played, not stored … like joining a radio station mid-song".
  - **No issue tracks a carousel/repeat-interval parameter.** [ASSESS] This is the single biggest spec gap relative to intent. A carousel (per-item or per-stream `repeat_interval` ≤ remaining TTL, re-emitting with decremented remaining life) would resolve late-join replay without back-channels or sender-side subscriber state.
- **C5 Test-before-transport.** Receptor §13 says executable examples are "required before transport selection". The prototype built a transport seam first. #27 is still empty.
- **C6 HAProxy premise** (#11 c2, #30) is false for community HAProxy (UDP only in log-forward; generic UDP LB is Enterprise).
- **C7 Ingestion default.**
  - Spec §7.4 says never auto-inject. Ronan's orphan receive-side draft says `silent` injection by default, with listener-elected `silent-wake`.
  - #48 says "never … automatic agent turns". #11 has `infer_direct`.
  - The orphan branch has no PR, so it is invisible to review.
- **C8 #17 vs spec §4.2 reserved prefixes and §4.1 well-known streams.** Resolvable by stating that the prefixes are provenance, not payload type.
- **C9 Premature closes.** #37, #39 and #40 were closed as "completed" by PR #42, but their receptor/session/fixture acceptance items are unmet. #37's close comment is truncated ("replay completeness is )"). #33's figs-cosign gate half is not recorded.
- **C10 Stale trackers.** #21's body and c3 say the keystone is missing (landed 06-25). README (#35) is stale. INDEX.md row 20 still says receptor contract "active" and row 30 lists "issue #21 … 🌊 Ronan" as owner.
- **C11 Duplicate-filing churn** (#14/#16; #45/#46/#47) is noted by the cohort itself: "*State checks need to be transaction-scoped*" (#16 c2).
- **C12 Unverifiable:** #8 (Projects V2 not readable with this token). Discord-message citations throughout (e.g. `1504842621`) cannot be checked from here.

## 5. Recommended actions (ordered)

1. **Clean up the issue tracker:**
   - Close as done: #22, #25, #26, #23 (after the small ringbuffer edit).
   - Close as obsolete: #3, #9, #15, #31.
   - Merge into #11: #13, #18 (noting #18's registry decision is superseded).
   - Close #19 into #26, and spin out a Scope-4 `sharing`/consent open question.
   - Relabel #20 as control-plane or transfer it to openclaw.
   - Also close PRs #32 and #50 (byte-identical to main).
2. **Refresh #21's status board** to reflect PR #28/#41/#42/#43 merges and the #49 prototype landing. List the real remaining gates: adjacent-shapes survey, split decision, contract tests, v0.2 spec revision, figs cosign.
3. **Open a new spec issue: carousel/loop semantics.** Cover `repeat_interval` per stream or item, re-emission with remaining TTL, how late joiners get ring contents without a back-channel, and the relation to the v0.2 station-side ring. It is the owner's core behavior and has no tracker (C4).
4. **Advance #48 (trust envelope)** using the prototype's Ed25519/admission model as the concrete candidate. Remove the "trust-of-LAN base layer" wording or explicitly scope it as insecure-dev-only.
5. **#27 contract tests first:** make receptor §13 examples 1-8 executable, then add the fixtures accumulated in #37, #38, #39, #40, #48 and #51.
6. **#51:** Ronan's protocol decision should also define the TTL basis (C4/§3.15 gap a) and fold in `scratch/notes_on_carrier_wave.md`'s silence/UNEQUIP state machine. Keep Emeric's ten tests as acceptance.
7. **#5:** open a PR from `ronan/20260614/send-receive-threshold-landing` so the receive-side landing modes get reviewed against spec §7.4 and #48 guardrails. Record the decision as an RFC section.
8. **#2/#30:** run the Phase-0 LAN multicast vs broadcast experiment. Replace "HAProxy 3.2 UDP LB" with a custom relay/membrane daemon for internet unicast listeners.
9. **#35:** rewrite the README (quick win). **#38:** pin reject-on-collision before the first v0.2 adapter.
10. **#12:** give it acceptance criteria. Complete #49's native Ringserver/DataLink proof as the bridge to the EWS/nerv-ui SeedLink dashboards (TCP SeedLink/DataLink side). Map #16 presence/cadence onto cell color and amplitude.
