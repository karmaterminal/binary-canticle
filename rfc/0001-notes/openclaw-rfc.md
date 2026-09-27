# OpenClaw continuation RFC -> binary-canticle integration seams

Source under study: `docs/design/continue-work-signal-v2.md` on `origin/codeagent/85651-upstream-1ba243c8-gates` (tip `9eb655afa`, "Merge pull request #1366 from karmaterminal/scribe/20260921/absorb-ddcd52d5"), in `/home/user/openclaw`. 2193 lines / 26,241 words. Line refs below are `RFC:<line>` into that file (a byte-identical dump is at scratchpad `rfc-v2.md`). `origin/main` tip = `14ead1fc9` ("perf(gateway): share identical session rows during fanout (#159456)").

Legend: **[SAYS]** = what the RFC/doc text states; **[CODE]** = verified in source on the named ref; **[ASSESS]** = my assessment.

---

## 0. RFC reading log (dense extracts, in RFC order)

### Front matter / framing
- [SAYS] Status "Implemented", March-May 2026 (RFC:3-5). Scope: self-elected continuation, delegated follow-up, **same-host** targeted delegate returns, context-pressure, agent-initiated compaction; "bounded, observable, interruptible, and opt-in" (RFC:7).
- [SAYS] "Targeted delegate return is the banner routing primitive: one child can grant another session a turn, wake every known session on the host, or drip silent context into a named session without duplicating the delegate run. That makes continuation a signaling substrate as well as a work-scheduling substrate." (RFC:11)
- [SAYS] Terminology table (RFC:131-145): *substrate* = "process timer/reservation, TaskFlow, session-delivery queue, or compaction lifecycle"; *broker* = "Gateway code that translates agent intent into substrate mechanics and policy enforcement".
- [SAYS] Problem framing (RFC:96-112): heartbeats/cron solve liveness not volition; static heartbeat instructions "shape what the agent attends to" (context cost), empty polling cycles (token waste). [ASSESS] This is directly relevant to canticle: a looping broadcast carrier that is injected every loop would re-create exactly the "dominant repeated signal" pathology; the receptor must dedupe/attenuate per item (§ design below).

### §2.2-2.3 tools + continue_work
- [SAYS] Three tools on main-session turns when `continuation.enabled: true`: `continue_work()`, `continue_delegate()`, `request_compaction()`; fallback tokens `CONTINUE_WORK[:N]`, `[[CONTINUE_DELEGATE: ...]]` (RFC:157-165). All fire-and-forget.
- [SAYS] `continue_work` = durable TaskFlow `continuation_work` row; on maturity while idle, dispatcher grants a turn via `getReplyFromConfig` with a `[continuation:wake]` system event + provenance banner; if the session is busy it delivers one trusted `[system:continuation-note]` into the active turn instead of stacking wakes; **explicitly does NOT call `requestHeartbeatNow()`/`runHeartbeatOnce()`** "because heartbeat registration, active-hours, deferral, and busy skip gates are heartbeat policy rather than same-session continuation policy" (RFC:184-186).
- [SAYS] Chain budget: `maxChainLength`, `costCapTokens`; a fresh non-continuation turn-entry ("genuine user message, heartbeat, or external system event") resets chain budget (RFC:188).

### §2.4 continue_delegate return modes (core for canticle)
- [SAYS] Schema fields: `task`, `delaySeconds`, `mode`, `targetSessionKey`, `targetSessionKeys`, `fanoutMode`, `returnOptions`, `recipientContext`, `model`, `attachments`, `attachAs` (RFC:198).
- [SAYS] Explicit target fields "route the same completion envelope through the `session-delivery-queue` substrate to other known sessions **on the same host**"; targeted returns are "delivered as session-addressed enrichment events so one delegate completion can fan out byte-identically without duplicating the delegate run" (RFC:198).
- [SAYS] Targets do NOT route the task body; the recipient sees only the post-completion `[continuation:enrichment-return]` envelope. "Cross-session task delivery — addressing an existing session's run loop with a new prompt — is a separate primitive that is out of scope for this RFC." (RFC:220-222)
- [SAYS] Recipient's next turn: "the reply runner drains that session-scoped system-event queue and prepends the completion envelope as `System:` context. In `silent-wake` mode the return also requests a `delegate-return` heartbeat for every targeted recipient" (RFC:224).
- [SAYS] Return-target modes (RFC:228-232): default (dispatcher), `targetSessionKey`, `targetSessionKeys` (byte-identical envelope to each), `fanoutMode:"tree"` (every ancestor in chain), `fanoutMode:"all"` (every known session **on the same host**).
- [SAYS] **Key sentence for canticle** (RFC:234): "Multi-recipient return is distinct from multi-delegate fan-out ... Aspect multiplexing, per-receiver transformation, backpressure-aware multicast, cross-host publish/subscribe, and SeedLink-style broadcast remain the higher broadcast layer; they do not replace this shipped session-addressed return primitive." -> canticle is explicitly named (by description) as the *higher broadcast layer* above the shipped primitive.
- [SAYS] Mode table (RFC:244-249): `normal` = channel echo + wake; `silent` = no echo, no wake ("Passive enrichment that should color a later turn"); `silent-wake` = no echo, wake ("Quiet background cognition that should trigger the next turn automatically"); `post-compaction` = no echo, wake after compaction.
- [SAYS] `silent`: result delivered through `enqueueSystemEvent()` instead of announce; `silentAnnounce` flag threads through spawn/registry (RFC:251). `silent-wake`: triggers generation via `requestHeartbeatNow()` (RFC:253). `post-compaction`: staged until compaction completes (RFC:255).
- [SAYS] Token fallback grammar incl. `| target=`, `| targets=`, `| fanout=tree|all`, `| model=` (RFC:261-267, 323). Task text truncated to 4096 chars (RFC:325).
- [SAYS] Without silent-wake, chain hops stall: canary saw enrichment arrive but hop 2 waited 6 minutes for an unrelated message (RFC:272). [ASSESS] Canticle receptor must choose explicitly; "silent" alone means the fact sits until something else wakes the session.

### §2.5-2.8
- [SAYS] `request_compaction` current-session only; "lich pattern" = agent arranges payload to enrich its successor after compaction (RFC:280-296).
- [SAYS] Tier hierarchy (RFC:343-376); rationale "gate by capability, not turn type"; abuse prevention via `maxDelegatesPerTurn`, `maxChainLength`, `costCapTokens` (RFC:380).

### §3.1-3.5 implementation
- [SAYS] Architecture (RFC:392-402): signal parse in `src/auto-reply/continuation/signal.ts`; `scheduleContinuationWork()`; `dispatchPendingContinuationWork()` (enqueues `[continuation:wake]` then `getReplyFromConfig()` for the SessionKey; busy sessions requeued); `enqueuePendingDelegate()` into TaskFlow; return routing via `session-delivery-queue`. "No new transport layer is introduced." Same-session work avoids heartbeat wake; silent delegate returns still use their wake path.
- [SAYS] Sequence diagram (RFC:443-484): targeted return = "byte-identical system-event return via session-delivery-queue"; silent-wake targeted -> `Target->>Target: requestHeartbeatNow(childRunId)`.
- [SAYS] Gap window: "Neither path carries a private cryptographic capability." (RFC:488)
- [SAYS] Wake classified via structured metadata `continuationTrigger: "delegate-return"` "allowing a successor turn to distinguish internal continuation from unrelated user input" (RFC:494).
- [SAYS] Chain-state fields `continuationChainCount/StartedAt/Tokens/Id`; reset at turn-entry when `!isContinuationWake` (in `get-reply-run.ts`); `subagent-return` is an external turn-entry that resets budget (RFC:536-545). [ASSESS] A canticle-injected wake would be an "external system event" turn-entry => it RESETS chain budgets. That means canticle wakes can defeat `maxChainLength` as a runaway guard unless canticle carries its own hop/TTL accounting. Important safety point.
- [SAYS] #666 seam: return attachments missing; path `readSubagentOutput()` -> `runSubagentAnnounceFlow()` -> `enqueueContinuationReturnDeliveries({ text })` (RFC:534).
- [SAYS] Trace: system events and queued session delivery payloads can carry W3C `traceparent` (RFC:559).
- [SAYS] Leaf subagents denied `continue_delegate` via `SUBAGENT_TOOL_DENY_LEAF` (RFC:573). System prompt branches on tool availability in `src/agents/system-prompt.ts` (RFC:582-587).
- [SAYS] "a monitor can drip silent context into a session that should learn the fact but should not speak yet" (RFC:616) -- the ambient/monitor use case.

### §3.6 persistence / session-delivery-queue
- [SAYS] Substrate table (RFC:636-642). Post-compaction delivery after release: "SQLite-backed `session-delivery-queue`"; failed entries -> `failed/`; retry cap emits `[session-delivery-queue:retry-budget-exhausted]`.
- [SAYS] **Scope** (RFC:644): "`session-delivery-queue` is a local-gateway substrate keyed by `sessionKey`. It accepts `systemEvent`, `agentTurn`, and `postCompactionDelegate` payloads against addressable sessions in the same gateway namespace."
- [SAYS] Idempotency (RFC:646): sha256 entry id only when caller supplies idempotency key; otherwise UUID.
- [SAYS] **Cross-host** (RFC:648): "The queue is local to one gateway. Exposing cross-session enqueue across gateway hosts would require a wire transport, auth/identity wrapper, and federation contract; this RFC deliberately does not specify that contract." -> this is precisely the gap canticle occupies.
- [SAYS] Cleanup (RFC:652): ack unlinks (`ackSessionDelivery()`), `moveSessionDeliveryToFailed()`, 14-day prune `pruneFailedOlderThan()`, `queueDir.maxFiles` soft cap -> `SessionDeliveryQueueOverflowError`. "Per-session enqueue rate limiting remains out of scope until a concrete rogue-producer scenario requires it." [ASSESS] A canticle receptor bridging many remote publishers IS the concrete rogue-producer scenario; receptor must rate-limit before enqueue.

### §4.1-4.5 compaction (lower relevance)
- [SAYS] Two-layer compaction; triggers A-F (RFC:665-698); `[system:context-pressure]` pre-run event (RFC:714-721); bands 25/80/90/95 (RFC:729-736); `request_compaction` guards: <70% rejected, 1 per 5 min (RFC:765-768); post-compaction release is silent-wake, enqueued into session-delivery-queue then drained (RFC:804); hooks `before_compaction`/`after_compaction` (RFC:859-862).
- [SAYS] Historical: "`requestHeartbeatNow()` could ring the parent session like a doorbell, but it still lacked task payload" (RFC:802).

### §4.6 Gateway as lifecycle broker (core for canticle)
- [SAYS] Doctrine: "**the agent owns intent, the tool owns mechanics, the substrate owns durability.**" (RFC:877)
- [SAYS] **Substrate-adoption rule** (RFC:879): "Where the upstream cross-session addressable enrichment substrate (see §3.6) can carry a concern cleanly, prefer it over bespoke transport. Bespoke pathing is acceptable only where a **concrete direct or transitive functional reason** is named ... _Seam-ugliness alone does not clear this bar_ ... _describe what the agent wants done (the verb), let the tool route to the substrate that already names the noun_. Bespoke transport in the presence of a fitting substrate, without a named functional reason, is a review-rejectable design choice on this RFC."
- [SAYS] Audit shape: evidence not doctrine; outcome labels "always-queue", "queue-with-bespoke-fallback", "bespoke-only" are coordination handles only (RFC:881).
- [SAYS] Enforcement: `src/infra/substrate-capability-registry.ts`; "There is no shipped `pnpm lint:substrate-adoption` script" (RFC:883).
- [SAYS] "The agent never names a substrate, hook, or wire — those are the tool's job." Wire = "same-host session addressing today, cross-host addressing only when supported" (RFC:885).
- [SAYS] Brokered surface: `tool-result-middleware` extension is the seam for results returning from the three primitives; `src/agents/harness/native-hook-relay.ts` replaces PTY-scraping with structured lifecycle-hook subscription (RFC:909).
- [SAYS] **Projected stream-publish worked example** (RFC:921-928): "The agent supplies stream reference, payload bytes, and mode (`broadcast` vs. `addressed`); the tool picks UDP fan-out (substrate: ringbuffer / station-broadcast) vs. an `enqueueSessionDelivery` bridge (substrate: §3.6 queue) underneath. ... The specific stream-publish tracker is external to this RFC and is included only as an illustration."
  - Owns-table "bc#11 example": Agent = `streamRef`, `payload` bytes, `mode` (`broadcast`/`addressed`); Tool = "UDP fan-out vs. `enqueueSessionDelivery` bridge selection, mode-routing, span emission (§6.6)"; Substrate (broadcast) = "FEC encoding, multicast addressing, ringbuffer aging, per-station seq numbers (bc#11 §8)"; Substrate (addressed) = "sha256 idempotency, exp-backoff retry, restart-survival, cross-session routing (§3.6, this RFC)".
- [SAYS] "Future tool-surface designs ... SHOULD cite §4.6 ... declare the agent/tool/substrate owns-table ... New surfaces that violate the discipline (agent naming the substrate, or tool exposing substrate-internal retry semantics to the agent) are review-rejectable" (RFC:930).

### §5 configuration
- [SAYS] Config (RFC:938-957): `enabled:false` default, `maxChainLength:10`, `defaultDelayMs:15000`, `minDelayMs:5000`, `maxDelayMs:300000`, `costCapTokens:500000`, `maxDelegatesPerTurn:5`, `crossSessionTargeting: disabled`, `contextPressureThreshold:0.8`, `earlyWarningBand:0.3125`, `busySkipBackoff{baseMs:1000, ceilingMs, factor:2}`, `orphanReapStaleCutoffMs:7200000`. Runtime values "read at use time" (RFC:971). `subagents.maxChildrenPerAgent` default 5, ceiling 10000 (RFC:972).
- [SAYS] Chain budget resets on "user message, heartbeat, system event" -> `/status` sawtooth (RFC:976-980).
- [SAYS] Fleet profile: `crossSessionTargeting: enabled`, `maxDelegatesPerTurn:20`, `costCapTokens:1000000`, `maxChildrenPerAgent:1000` (RFC:1007-1029).
- [SAYS] §5.3 wide fan-out: sensor fan-out; "ambient monitoring with `silent` returns" (RFC:1051). **Mast-cell pattern** (RFC:1074): "many quiet leaves watch local surfaces, but a small number of higher-level sessions control whether a finding becomes local enrichment, a wake for the responsible session, or a host-wide 'there is a fire' signal. `silent` mode makes the return ambient context; `silent-wake` makes it an immediate turn grant; `fanoutMode` decides whether the signal stays in the branch, climbs the tree, or reaches the host. The gateway remains the broker".
- [SAYS] **Cross-session targeting policy** (RFC:1078-1085): `crossSessionTargeting` `"disabled"` default: only self + `fanoutMode:"tree"` (lineage-only); non-self `targetSessionKey(s)` and `fanoutMode:"all"` rejected. `"enabled"`: all modes. Rationale: "model-controlled cross-session context-injection surface: without it, a continuation-enabled session can affect unrelated sessions on the same host." Live-read at tool validation, TaskFlow dispatch, post-compaction release, bracket-syntax spawn.
- [SAYS] §5.4 TaskFlow controllers `core/continuation-work`, `core/continuation-delegate` via `createManagedTaskFlow()` (RFC:1093).

### §6 observability (relevant bits)
- [SAYS] Log anchors (RFC:1113-1127): `[continuation:enrichment-return]` (subagent-announce.ts, "silent return injected as system event"), `[continuation/silent-wake]`, `[session-delivery-queue:retry-budget-exhausted]` (session-delivery-queue-recovery.ts), `requestHeartbeatNow` ("generation cycle requested after a silent-wake return").
- [SAYS] Privacy (RFC:1141, 1313): anchors carrying free text honor diagnostics-otel redaction; declare `task`, `enrichment`, `reason` as redaction keys before content capture. [ASSESS] canticle payloads should be treated as `enrichment` under that policy.
- [SAYS] Span vocabulary (RFC:1260-1284): `continuation.work(.fire)`, `continuation.delegate.dispatch/.fire`, `continuation.queue.enqueue/.drain`, `continuation.compaction.released`, `continuation.disabled`, `heartbeat`; tracer facade `src/infra/continuation-tracer.ts`; OTel adapter `extensions/diagnostics-otel/src/continuation-tracer-adapter.ts`. Raw reason/task never exported, only `reason.present/length/hash/redacted` (RFC:1282).
- [SAYS] **§6.7 explicitly frames itself as prep for canticle** (RFC:1324): "Together with §6.6, the span schema, queue-lifecycle spans, and multi-recipient fan-out form future-work preparation: an observability substrate for an inter-node ringbuffer `station:stream` broadcast layer."
- [SAYS] Per-entry queue spans (spec target): `continuation.queue.enqueue.system` at `enqueueSystemEvent`, `continuation.queue.enqueue.delivery` at `enqueueSessionDelivery`, `continuation.queue.announce`, `continuation.queue.deliver` w/ `outcome accepted|deferred|dropped` (RFC:1328-1333). `traceparent` carried on the queue payload itself (RFC:1337-1343).
- [SAYS] Carrier validation: tool-input boundary rejects malformed `traceparent` with `ToolInputError`; substrate-enqueue boundary silently drops the carrier and still writes (RFC:1347-1352). [ASSESS] Canticle receptor = substrate producer => follow the lenient rule; canticle *publisher tool* = tool input => strict rule.
- [SAYS] **Anti-flood**: "per-completion fan-out is 1 chain step, regardless of recipient cardinality"; at `chainStepBudgetRemaining <= 0` spans sampled at 0.0; "back-pressure belongs at the producer, not the wire" (RFC:1354-1360). "Mercy clause" (don't thread traceparent past budget) and "non-conscription clause" ("I won't spend yours") (RFC:1362-1367). Fan-out span `continuation.queue.fanout` with `recipientCount`, `chainStepConsumed=1` (RFC:1369-1374).
- [SAYS] §6.7 impl note: seams that make cross-session targeted return observable "today and inter-node broadcast observable later" (RFC:1376).
- [SAYS] §6.8 (spec target): single trace tree; producer-IN `traceparent` param on `continue_delegate`, token directive, `PendingContinuationDelegate`, TaskFlow `PendingDelegateState` (RFC:1392-1402); queue persists traceparent per entry in `src/infra/session-delivery-queue-storage.ts` (RFC:1413); seam map: `continuation/targeting.ts` (`enqueueContinuationReturnDeliveries`), `session-system-events.ts`, `gateway/server-restart-sentinel.ts`, `post-compaction-delegate-dispatch.ts` (RFC:1425-1433). A 50-recipient `fanoutMode:"all"` = 1 chain step (RFC:1417).

### §7 safety & security
- [SAYS] Guardrails table (RFC:1455-1462): `enabled:false` ("explicit deployment consent required"), `maxChainLength:10`, `costCapTokens:500000`, `minDelayMs:5000` ("prevents tight loops"), `maxDelayMs:300000`, `maxDelegatesPerTurn:5`.
- [SAYS] "In channels configured with `requireMention: true`, the internal delivery path still bypasses mention gating" (RFC:1464). [ASSESS] A canticle bridge using the same internal path would also bypass mention gating — needs its own gate.
- [SAYS] §7.2: plaintext within instance trust boundary; attachment SHA-256 manifest does not authenticate earlier TaskFlow / queue hops; "Session-delivery queue files are local filesystem records, not encrypted envelopes." (RFC:1468-1470)
- [SAYS] Threat model (RFC:1474-1479): Task interception = plaintext; Payload modification = "no integrity verification"; **Marker spoofing = "no authenticated system-event origin"**; Announce injection = "origin tied primarily to session routing, not cryptographic proof".
- [SAYS] Mitigations: first = audit trail w/ payload hashing (digest at dispatch, verify on return); stronger = "HMAC signing, encrypted attachments, and signed announce payloads" — none required, "all are compatible with the present architecture" (RFC:1481-1483). [ASSESS] For canticle, where payloads cross hosts on UDP, these "optional" mitigations become mandatory: canticle must sign items (HMAC or Ed25519) and the receptor must verify BEFORE enqueue, because the local substrate has no authenticated origin and would present a forged item as trusted `System:` context.

### §8 applicability
- [SAYS] Inappropriate "as a substitute for human-user consent, for unbounded background loops, or for durable job orchestration that needs stronger integrity" (RFC:1489). Mast-cell deployment: "escalate only the returns that should wake a responsible owner, the ancestor tree, or the whole same-host fleet" (RFC:1491).
- [SAYS] §8.2 `continue_delegate(..., mode="silent-wake")` background research; next answer reflects new material (RFC:1505-1515).
- [SAYS] **§8.3 Ambient self-knowledge** (RFC:1517-1521): "A persistent agent can dispatch a quiet shard during an idle heartbeat to inspect its own repository history, logs, or memory files. The result returns silently, enriches the next turn, and does not create channel noise. ... background self-audit, repository familiarization, and long-horizon context building." [ASSESS] This is self-sourced ambient enrichment; canticle generalizes the *source* from "my own shard" to "a station I'm tuned to".

### §9 testing (relevant bits)
- [SAYS] §9.3 blind enrichment "secret-world" methodology (RFC:1594-1605): human -> DM -> admin agent places content on subject filesystem -> subject dispatches silent delegate -> delegate returns silently -> subject probed for recall -> human compares to ground truth. "the subject's only legitimate access path is the enrichment pipeline." Matrix 12 rows, 10/12 pass; 10/10 when dispatch occurred (RFC:1609-1624). Row 2 "cross-machine via SSH" (RFC:1612).
  - [ASSESS] This is the directly reusable acceptance test for canticle: admin publishes a nonce on a station; subject host's receptor must be the only path; probe recall; compare. Must add negative controls because §9.5 finding 2: "LLMs confabulate absent enrichment" (RFC:1671) and finding 1 "LLMs confabulate tool calls" (RFC:1670). So verification must be log/transport-evidence based (receptor delivery log + queue ack), never self-report.
- [SAYS] §9.5 finding 4: "Continuation is resilient under pressure, but only with correct routing metadata" (RFC:1673); finding 5: session reset (`/new`) cancels timers, clears reservations, resets chain, deletes pending TaskFlow work (RFC:1674).
- [SAYS] Live bug: `registerSubagentRun()` did not persist `silentAnnounce`/`wakeOnReturn` (RFC:1664, 2163).

### §10 future directions (canticle is named)
- [SAYS] §10.2 (RFC:1696): "`session-delivery-queue` can carry more forms of addressed enrichment; trace context can make both auditable."
- [SAYS] #666 now ships managed claims; remaining: "automatic byte presentation ... generic transcript, TUI, MCP-content, or channel rendering" (RFC:1698).
- [SAYS] **Door-as-tool** (RFC:1700): "the session does not maintain transports, retry loops, delivery queues, or broadcast rings in its prompt. It says what door it wants opened, and the gateway chooses the mechanism. ... A later stream-publish surface should follow the same rule: the agent names intent and audience, while the tool handles deterministic ringbuffer fill, aging, addressing, fan-out, bridge-to-queue, and trace emission."
- [SAYS] **Binary Canticle named** (RFC:1702): "That future points toward a **Binary Canticle** layer above this RFC: ringbuffer-backed `station:stream` presentation into OpenClaw; low-friction dispatch for sessions; DNS SRV discovery for domains of interest; local-network multicast; station relays in the shape of DHCP helper/relay agents; and receive-side bridges that can turn a heard stream into quiet context or queued delivery. The important constraint is low maintenance for the session. A persistent agent should not spend every turn remembering transport mechanics; it should tune what it sings, what it listens to, and what provenance it trusts."
- [SAYS] **Sovereign peer enrichment** (RFC:1704): "multiple persistent OpenClaw instances exchanging quiet, scoped enrichment across a fleet without forcing central orchestration ... the hard question the RFC deliberately leaves open: how trust, provenance, consent, and freshness are established and maintained when enrichment crosses session, host, and eventually organization boundaries."
- [SAYS] "networked substrate or noosphere ... remaining interruptible, consent-bound, and locally sovereign. This RFC does not implement that layer." (RFC:1706)

### Appendix A
- [SAYS] A.1-A.4 unshipped: `[system:compaction-imminent]`, evacuation delegate, `context_pressure` modifying hook, unshipped config keys (RFC:1710-1745).
- [SAYS] A.5 (#1192): typed input attachments, 1-50 entries, snapshot-by-value, materialized in child private receipt dir `.openclaw/attachments/<id>` and child told files are "untrusted input" (RFC:1782).
- [SAYS] **A.6 (#666) arrival context** — the most canticle-relevant provenance contract:
  - Status "implemented control plane" (RFC:1801).
  - "An explicit `targetSessionKey`, `targetSessionKeys`, or fan-out recipient may have **zero awareness** of that dispatch. For that recipient, a valid claim without a delivery envelope is a mystery package." (RFC:1928)
  - "Every child-to-recipient return therefore SHALL have a typed, host-authored arrival context ... not optional UI decoration, child prose, or a bare `System:` string" (RFC:1930). Must state: delivery class (`delegate result` vs `inter-session enrichment`) + silent/announced mode; must NOT disclose sibling identities/route membership/fan-out cardinality; immutable dispatch ID; "only an approved source identity or privacy-safe host-generated origin label"; producer child/run; causal completion-event ID; recipient's own authorization binding; dispatch/notBefore/completion/delivery/replay times; policy version; bounded `recipientContext` `{ purpose: string }` <=1024 UTF-8 bytes, required for every non-parent recipient, "visibly labelled as contextual provenance—not host authority, executable instruction" (RFC:1932-1935).
  - Recipient judgment target: "**this was produced there, for this declared purpose, then; it reached me now; and it is/was valid under this claim.** A legacy record lacking a required provenance field must say that context is unavailable; it must not fabricate a complete-looking envelope." (RFC:1937)
  - Acceptance #2: target with zero prior awareness "can distinguish it from fresh direct instruction using the host-authored arrival context" (RFC:1981). #3: "a 30-second continuation delivered ten hours late is visibly delayed rather than fresh" (RFC:1982). #10 recipient privacy (RFC:1989).
  - V1 route mapping: `fanoutMode:"all"` -> "the addressable same-host sessions in the host snapshot at dispatch"; later-created sessions do not expand policy (RFC:1968-1970).
  - Runtime disable: continuation-enabled and cross-session-targeting gates re-checked atomically before spawn/finalize/deliver; "A disabled gate never grants a new capability" (RFC:1945).
  - Claim IDs opaque, not bearer (RFC:1909, 1941).
  - [ASSESS] Canticle-derived enrichment is the extreme case of a "zero-awareness recipient": the receiving session never dispatched anything. It MUST get a host-authored arrival context of delivery class "inter-session enrichment" (or a new class e.g. `station-broadcast`), with origin label = verified station identity, `purpose` = station/stream declared purpose, publish time vs heard time vs delivery time, TTL/expiry, and signature-verification status. Otherwise it violates the spirit of A.6.3 and would be indistinguishable from direct instruction.

### Appendix B/C/D
- [SAYS] B.1: "Higher heartbeat frequency" rejected for **injection accumulation** (RFC:2005). [ASSESS] Looping canticle items (re-broadcast until TTL) must be deduped at the receptor by item id/seq so a looping carrier doesn't become injection accumulation.
- [SAYS] B.3: `requestHeartbeatNow()` "carries no task payload and no chain state. It is a wake signal" (RFC:2033). "`sessions_send`-style addressing can put a message into another session, but it is not equivalent to `continue_delegate()` return routing" (RFC:2037).
- [SAYS] C.2 inherited limitations (RFC:2070-2072): **Self-bound context occlusion** ("Too many recurring lifecycle messages can displace the agent's useful conversational context"), **Channel context poisoning** ("In open-listen multi-agent channels, one agent's passive status messages can influence the rest of the fleet"), timer-handle volatility. [ASSESS] Both occlusion and poisoning are *the* canticle risks at scale; canticle is literally an open-listen channel.
- [SAYS] D.2 evidence locations (RFC:2106-2120) — used below for code verification.
- [SAYS/contradiction] D.4: RFC:2171 says "three of four initial ... rows are closed" and RFC:2177 says "OV-1 ... PASS", but the table at RFC:2186 lists OV-1 state "open" and OV-4 "open" (only OV-2, OV-3 closed). Internal inconsistency in the RFC's own status reporting.

### docs/design/continuation-tools-infographics.md (gates branch, 91 lines)
- [SAYS] Three Mermaid/SVG reviewer aids. continue_delegate diagram: return modes `normal` -> "Visible announce + wake parent", `silent` -> "Silent system-event enrichment / no immediate wake", `silent-wake` -> "Silent enrichment + delegate-return wake", `post-compaction` -> "Stage until compaction release into successor"; targets default / `targetSessionKey` ("One named same-host session") / `targetSessionKeys` / `fanout tree` / `fanout all` ("All known host sessions"). Guards: `maxDelegatesPerTurn`, `maxChainLength`, `costCapTokens`, leaf-subagent deny, `crossSessionTargeting default-deny`. "The task goes to the child; the completion envelope is what is routed." Nothing about canticle/stream/broadcast in this file.

---

## 1. Code verification: what OpenClaw actually ships (gates branch vs main)

Refs: gates = `origin/codeagent/85651-upstream-1ba243c8-gates` @ `9eb655afa`; main = `origin/main` @ `14ead1fc9`. Counts are `git grep -l` over `src extensions packages`.

| Symbol | gates files | main files | Notes |
|---|---|---|---|
| `enqueueSessionDelivery` | 23 | 9 | queue exists on both; continuation producers only on gates |
| `enqueueSystemEvent` | 340 | 288 | core primitive on both |
| `requestHeartbeatNow` | 46 | 7 | |
| `silentAnnounce` | 36 | **0** | silent/silent-wake return modes are gates-only |
| `enqueueContinuationReturnDeliveries` | 17 | **0** | targeted/multi/fanout returns gates-only |
| `continue-delegate-tool.ts`, `continuation/targeting.ts`, `infra/continuation-tracer.ts`, `extensions/diagnostics-otel/src/continuation-tracer-adapter.ts`, `infra/session-delivery-queue-codec.ts` | present | **absent** | the whole continuation feature is NOT on upstream main |
| `src/infra/substrate-capability-registry.ts` | **absent** | absent | **RFC:883 claims it is "the shipped artifact"; no such file exists on the gates branch, and `git grep -i substrate-capab` matches only the RFC itself.** Contradiction. |
| "canticle" / "seedlink" | only `docs/design/continue-work-signal-v2.md` | none | no code references anywhere |

[CODE] `src/infra/system-events.ts` is 609 lines on gates vs 321 on main (gates adds `trusted`, `traceparent`, `replace`, ack-deferral fields). `src/infra/heartbeat-wake.ts` 98 vs 31 lines.

### 1a. In-memory system-event queue — `src/infra/system-events.ts` (gates)
- [CODE] `SystemEvent` = `{ id?, text, ts, contextKey?, deliveryContext?, sessionDeliveryAckId?, sessionDeliveryAckStateDir?, sessionDeliveryAwaitsTurnAdoption?, expectedSessionId?, recipientAuthority?, delegateArtifactReceipt?, traceparent?, sessionStorePath? }` (system-events.ts:30-64).
- [CODE] **`MAX_EVENTS = 20` per session; oldest shifted out on overflow** (system-events.ts:66, 318-320). Process-memory map keyed by `Symbol.for("openclaw.systemEvents.queues")` (:73-75) — NOT durable by itself.
- [CODE] Options (`SystemEventOptions`, :90-121): `sessionKey`, `contextKey`, `deliveryContext`, `trusted?: boolean` ("Trusted-internal enrichment marker. Only core producers may attach managed delivery provenance such as expectedSessionId and delegateArtifactReceipt"), `traceparent` (invalid silently dropped), **`replace?: boolean` — "Replace the pending event for this context and delivery route. Requires contextKey."**
- [CODE] Replace semantics (:395-460): "**One keyed source owns one queue slot.** Moving a replacement to the end keeps event ordering current without allowing repeated updates to evict other sources." Identical replacement is a no-op. Duplicate (same text/context/route/ack) enqueue returns null (coalesced) (:300-316).
- [ASSESS] `contextKey` + `replace:true` is the ideal native primitive for a **looping** canticle item or a station "now playing" slot: `contextKey = "canticle:<station>:<stream>"` (or per item id) means a looping re-broadcast overwrites instead of accumulating — directly answering the RFC's injection-accumulation / self-bound-occlusion concerns (RFC:2005, 2070). With 20-slot cap, a receptor must also cap the number of distinct canticle keys per session (e.g. <=3-5) so broadcast chatter cannot evict continuation or channel events.

### 1b. Prompt rendering — `src/auto-reply/reply/session-system-events.ts` (gates)
- [CODE] Drained events render as `System: [<timestamp>] <line>` per line (session-system-events.ts:586-600). **Comment at :594-596: "Inbound text is deliberately not rewritten to neutralize look-alike `System:` lines. Role separation plus external-content wrapping is the boundary. This is an explicit product decision."**
- [CODE] `trusted` does NOT change rendering (no trust label is added); it only gates which managed provenance fields may be attached (system-events.ts:267-279). `compactSystemEvent` (:80-104) filters retired heartbeat prompt text only.
- [CODE] Acks: durable `sessionDeliveryAckId` rows are acked via `ackSessionDelivery()` after drain (:542-565), or deferred to turn adoption when `sessionDeliveryAwaitsTurnAdoption`.
- [CODE] Drain emits `continuation.queue.drain` span with `drainedContinuationCount` = events whose text starts with `[continuation:` (:574-583).
- [ASSESS] => A canticle receptor MUST wrap every heard payload with `wrapExternalContent()` (see 1c) before `enqueueSystemEvent`; otherwise a remote station can emit look-alike `System:` lines straight into the prompt. It should also use its own text prefix (e.g. `[canticle:<station>/<stream>]`) so the drain accounting / grep anchors work analogously to `[continuation:`.

### 1c. External-content wrapper — `src/security/external-content.ts` (gates; also on main)
- [CODE] `wrapExternalContent(content, { source, sender?, subject?, taskName?, includeWarning? })` (:382-411) -> warning block + `<<<EXTERNAL_UNTRUSTED_CONTENT id="<random16hex>">>>` + `Source:/Task:/From:/Subject:` metadata + `---` + sanitized content + end marker. Random marker id prevents boundary spoofing (:55-61). `sanitizeExternalContentText` strips marker look-alikes and LLM special tokens. `detectSuspiciousPatterns()` flags e.g. `^\s*System:\s+` (:19-45).
- [CODE] `ExternalContentSource` = `email|webhook|api|browser|channel_metadata|web_search|web_fetch|unknown` (:91-99). No `broadcast`/`station` source. [ASSESS] canticle should either use `"api"`/`"webhook"` with `sender = station id` or propose adding a `"station"`/`"broadcast"` source label upstream.

### 1d. Durable session-delivery queue — `src/infra/session-delivery-queue-*.ts` (gates)
- [CODE] `enqueueSessionDelivery(payload, handle?) -> Promise<string id>` and `enqueueSessionDeliveryWithStatus` returning `{id, status: "pending"|"completed"|"unknown"}` (session-delivery-queue-storage.ts:273-321). Entry id = `sha256Hex(idempotencyKey)` if key supplied else secure UUID (session-delivery-queue.records.ts:71-75). SQLite-backed via OpenClaw state worker (`runOpenClawStateWorkerOperation`, `delivery-queue-sqlite`).
- [CODE] Payload kinds (session-delivery-queue-codec.ts:86-170): `systemEvent {sessionKey, text, expectedSessionId?, recipientAuthority?, deliveryContext?, idempotencyKey?, awaitPromptAdoption?}`; `agentTurn {sessionKey, message, messageId, route?, inputProvenance?, continuationTrigger?, suppressTextDelivery?, owner?...}`; `postCompactionDelegate {...task, silent, silentWake, targetSessionKey(s), fanoutMode, recipientContext, attachments...}` (only kind allowed to carry inline attachment bytes). Generic kinds carry only descriptor references (:83-86).
- [CODE] Exists on main too (`session-delivery-queue-storage.ts`, `-recovery.ts`, `-runtime.ts`, `.worker.ts`) but main lacks the `-codec.ts` and attachment-metadata files; the richer payload union is gates-only.

### 1e. Reference delivery pattern — `enqueueContinuationReturnDeliveries` (`src/auto-reply/continuation/targeting.ts:123-305`, gates only)
Per recipient session key:
1. build durable payload `{kind:"systemEvent", sessionKey, agentId, text, deliveryContext?, traceparent?, idempotencyKey: "<base>:<sessionKey>"}` (:195-206) and `enqueueSessionDelivery()` (:214);
2. `enqueueSystemEvent(text, {sessionKey, trusted:true, sessionDeliveryAckId: deliveryId, traceparent, ...})` (:219-238) so the prompt drain acks the durable row only after consumption; non-attached recipients get restart replay;
3. if `wakeRecipients`, `requestHeartbeatNow(markTrustedContinuationHeartbeatWake({sessionKey, agentId, reason:"delegate-return", parentRunId}))` (:267-275);
4. emit `continuation.queue.fanout` span when multi-recipient (:286-297).
- [CODE] Recipient-authority recheck before and after enqueue; stale recipients are skipped/removed (:182-192, 257-265).
- [CODE] Host fan-out set: `listKnownSessionKeysOnHost(cfg)` iterates `resolveAllAgentSessionStoreTargetsSync(cfg)` x `listSessionEntriesCore(...)` (src/agents/subagent-announce.continuation-return.ts:35-47) — i.e. "all known sessions" = every session-store entry for every configured agent on this gateway. Child session excluded (targeting.ts:57-62).
- [CODE] Text banners: `[continuation:enrichment-return] Delegate completed: <taskLabel>` (subagent-announce.continuation-return.ts:224, 285); wake reason `"delegate-return"` for targeted, `"silent-wake-enrichment"` for untargeted silent-wake (:296).
- [CODE] `wakeRecipients: params.wakeOnReturn === true || params.silentAnnounce !== true` (:229) — i.e. targeted returns wake unless mode is plain `silent`.

### 1f. Wake primitive — `src/infra/heartbeat-wake*.ts` (gates)
- [CODE] `requestHeartbeatNow({source?, intent?, reason?, coalesceMs?, agentId?, sessionKey?, parentRunId?, heartbeat?})` (heartbeat-wake.ts:65-89); `requestHeartbeat` "Public scheduler entry point strips non-enumerable internal trust markers" (:52-56). Trusted continuation wakes marked via non-enumerable `Symbol.for("openclaw.heartbeat.trusted-continuation-routing")` (heartbeat-wake-contracts.ts:58-77) — a third-party caller cannot forge it by passing a plain object property.
- [CODE] `HeartbeatWakeSource` union includes `"hook"`, `"exec-event"`, `"notifications-event"`, `"background-task"`, `"other"` etc.; no `"station"`/`"broadcast"` (heartbeat-wake-contracts.ts:8-22). Intents `scheduled|task|event|immediate|manual`.
- [CODE] Busy-skip reasons: `requests-in-flight`, `cron-in-progress`, `no-pending-event`, `preempted`, `channel-not-ready` (heartbeat-wake.ts:38-42). `coalesceMs` is the only caller-side rate knob. [ASSESS] There is no per-source wake budget in the heartbeat layer; canticle must supply its own wake budget.

### 1g. Out-of-process ingress already on both refs: Gateway HTTP hooks
- [CODE/DOC] `docs/gateway/config-hooks.md` (gates): `hooks.enabled` (default false), `hooks.token` (Bearer or `x-openclaw-token`), `allowedAgentIds`, `allowRequestSessionKey` (default false), `allowedSessionKeyPrefixes`, `mappings`, `transformsDir`. 256 KiB body limit; 20 failed auths/60s -> 429. "Hook tokens grant ingress access, not an authenticated sender identity; treat payload content as untrusted data".
- [CODE/DOC] **`POST /hooks/wake`** `{text, mode:"now"|"next-heartbeat", agentId?, sessionKey?}` -> `{ok, mode, eventOutcome:"queued"|"coalesced"}`. Implementation `dispatchWakeHook` (src/gateway/server/hooks.ts:262-290): `enqueueSystemEvent(value.text, {sessionKey})` then, if `mode==="now"`, `requestHeartbeat({source:"hook", intent:"immediate", reason:"hook:wake", ...})`. **So `/hooks/wake` = silent (`next-heartbeat`) vs silent-wake (`now`) enrichment over HTTP.** Note: it does NOT call `wrapExternalContent` and does NOT set `trusted` — raw text becomes a `System:` line.
- [CODE/DOC] **`POST /hooks/agent`** `{message, sessionKey?, sessionMode:"isolated"|"persistent", deliver, wakeMode, idempotencyKey, ...}` — "external content is safety-wrapped" (config-hooks.md hook agent payload table); runs a full agent turn.

### 1h. Gateway WS RPC ingress (operator-authenticated), both refs
- [CODE] `system-event` RPC `{text, sessionKey?, wake?}` — "`system-event` is operator.admin-only; role policy rejects node connections before dispatch" (src/gateway/server-methods/system.ts:188-192); enqueues `enqueueSystemEvent` and, with `wake`, `requestHeartbeat` (system.ts ~:300-370); targeted wake requires a live, non-archived persisted session (:226-236). Schema `packages/gateway-protocol/src/schema/system-event.ts:12`.
- [CODE] `wake` RPC (src/gateway/server-methods/cron.ts:276+), `chat.inject` (chat.ts:55), `sessions.send`/`sessions.steer` (sessions-messaging.ts:274).

### 1i. Plugin extension points (gates; same API shape on main)
- [CODE] `OpenClawPluginApi` (src/plugins/plugin-api.types.ts:183-340) — "All plugin APIs are experimental": `registerTool(tool | factory, opts)`, `registerHook`, `registerHttpRoute`, `registerChannel(ChannelPlugin)`, `registerGatewayMethod(method, handler, {scope})`, **`registerService({id, reload?, start(ctx), stop?(ctx)})`** (plugin-registration.types.ts:416-422; ctx = `{config, workspaceDir?, stateDir, logger, serviceHealth?, getCron?, invokeNode?}` :370-384), `registerGatewayDiscoveryService` ("local gateway discovery advertiser such as mDNS/Bonjour"), `registerSessionCatalog`, `registerCommand`, `registerContextEngine`, `on(hookName, handler)`, plus `runtime: PluginRuntime`.
- [CODE] Tool factory context (src/plugins/tool-types.ts): `{workspaceDir?, agentId?, sessionKey?, sessionId?, messageChannel?, requesterSenderId?, ...}` — a publisher tool learns the calling session identity for provenance.
- [CODE] **Plugin runtime system facade** (src/plugins/runtime/runtime-system.ts:19-47): `runtime.system.enqueueSystemEvent`, `requestHeartbeat`, `requestHeartbeatNow({source?, intent?, reason?, coalesceMs?, agentId?, sessionKey?, heartbeat?})`, `runHeartbeatOnce`.
- [CODE] **SDK enqueue is forcibly untrusted** (src/plugins/runtime/system-events.ts:28-49): "SDK consumers are untrusted by construction: force `trusted: false` so a plugin cannot attach trusted-only session or delegate-artifact provenance, and strip caller-supplied trace ancestry plus the session-delivery ack fields (`sessionDeliveryAckId` / `sessionDeliveryAckStateDir`) ... Trusted internal producers (continuation returns, post-compaction) enqueue through the direct `infra/system-events` import, never this facade." `contextKey`/`replace`/`deliveryContext` are NOT stripped -> a plugin can still use one-slot-per-source replacement.
- [CODE] `enqueueSessionDelivery` is NOT exported through `src/plugin-sdk/*` or `PluginRuntime` (grep: only `enqueueSystemEvent` via `plugin-sdk/system-event-runtime.ts`, `plugin-sdk/infra-runtime.ts:289`; `requestHeartbeat` via `plugin-sdk/heartbeat-runtime.ts:3`). **A third-party plugin cannot reach the durable §3.6 queue, cannot thread `traceparent`, and cannot mark a trusted continuation wake.**
- [CODE] Prompt-injection hooks: `agent_turn_prepare`, `before_prompt_build`, `heartbeat_prompt_contribution` (src/plugins/hook-types.ts:230-234); `before_prompt_build` result `{systemPrompt?, prependContext?, appendContext?, toolsAllow?, prependSystemContext?, appendSystemContext?}` (hook-before-agent-start.types.ts:31-50); gated per plugin by `plugins.entries.*.hooks.allowPromptInjection` ("Set false to block `before_prompt_build`", src/config/schema.help.agents.ts:35).
- [CODE] No existing UDP listener anywhere: zero `node:dgram` imports in `src/` or `extensions/` on gates.

### 1j. Branch topology caveat
- [CODE] `/home/user/openclaw` remote = `https://github.com/karmaterminal/openclaw`; only 3 remote refs; repo is **shallow** (`git rev-parse --is-shallow-repository` = true), gates tip `9eb655afa` has no parents in this clone (grafted), so ancestry vs main cannot be computed here. Gates commit date 2026-09-21; main 2026-09-27. main's tip message `(#159456)` indicates it tracks upstream openclaw/openclaw. **The continuation RFC + implementation is fork-only (karmaterminal) as of this clone; nothing continuation-specific is on main** (no `docs/design/continue-work-signal-v2.md`, no `src/auto-reply/continuation/`).
- [CODE] `wrapExternalContent` IS exported to plugins via `src/plugin-sdk/security-runtime.ts:30` and `src/plugin-sdk/provider-web-fetch.ts:34` (both refs). `contextKey`/`replace` exist on main's `system-events.ts` too (:67-70, :153-155); `trusted` and `traceparent` are gates-only.

---

## 2. ANSWER (1): Enrichment primitives OpenClaw already ships

| # | Primitive | RFC ref | Code | On main? | Delivery semantics | Trust |
|---|---|---|---|---|---|---|
| P1 | `enqueueSystemEvent(text, {sessionKey, contextKey?, replace?, trusted?, traceparent?, sessionDeliveryAckId?})` | §2.4 (RFC:251), D.1 | `src/infra/system-events.ts:324` | yes (no `trusted`/`traceparent`) | in-memory, per-session, max 20, drop-oldest; drained pre-run as `System: [ts] ...` lines on the session's next turn (session-system-events.ts:586-600). **This is "silent".** | `trusted` only gates managed provenance fields; rendering identical |
| P2 | `requestHeartbeatNow({source, intent, reason, coalesceMs, agentId, sessionKey, parentRunId})` | §2.4 (RFC:253), B.3 (RFC:2033) | `src/infra/heartbeat-wake.ts:65` | yes | "a wake signal, not a continuation-bearing result channel"; subject to heartbeat busy-skip gates | trusted-continuation marker non-enumerable, core-only |
| P3 | `enqueueSessionDelivery({kind:"systemEvent"|"agentTurn"|"postCompactionDelegate", sessionKey, idempotencyKey?...})` | §3.6 (RFC:644-652) | `src/infra/session-delivery-queue-storage.ts:273` | yes (narrower payload union) | SQLite durable, sha256 idempotent id, retry/backoff, `failed/`, 14-day prune; replayed after restart | not in plugin SDK |
| P4 | `enqueueContinuationReturnDeliveries` = P3 + P1(`trusted:true`, ack-id) + optional P2(`reason:"delegate-return"`) per recipient | §2.4, §3.2, §6.7-6.8 | `src/auto-reply/continuation/targeting.ts:123-305` | **no** | byte-identical multi-recipient enrichment; the reference "addressed enrichment" pattern | core |
| P5 | `continue_delegate({task, mode: normal|silent|silent-wake|post-compaction, targetSessionKey(s), fanoutMode: tree|all, recipientContext, returnOptions, model, attachments, delaySeconds})` | §2.4, §3.5, §5.3, A.5, A.6 | `src/agents/tools/continue-delegate-tool.ts` | **no** | spawns a fresh child; completion routed via P4 | gated by `continuation.enabled`, `crossSessionTargeting` |
| P6 | `continue_work({delaySeconds, reason})` | §2.3 | `src/auto-reply/continuation/work-dispatch.ts` | **no** | same-session wake via `getReplyFromConfig`, `[continuation:wake]` / `[system:continuation-note]`; deliberately NOT heartbeat | core |
| P7 | `post-compaction` staging + `after_compaction` release | §4.4 | `agent-runner-post-compaction-release.ts`, `post-compaction-delegate-dispatch.ts` | **no** | "lich pattern" savegame | core |
| P8 | `[system:context-pressure]` pre-run event | §4.2 | `src/auto-reply/continuation/context-pressure.ts` | **no** | banded, dedup'd | core |
| P9 | Gateway HTTP `POST /hooks/wake` `{text, mode:"now"|"next-heartbeat", sessionKey?}` | (not in RFC) | `src/gateway/server/hooks.ts:262-290` | yes | P1 + (if `now`) P2 `source:"hook"` — **external silent / silent-wake** | hook token = ingress, not sender identity; text not wrapped |
| P10 | Gateway HTTP `POST /hooks/agent` | (not in RFC) | same | yes | full isolated or persistent agent turn; message "safety-wrapped" | as above |
| P11 | Gateway WS RPC `system-event {text, sessionKey?, wake?}` | (not in RFC) | `src/gateway/server-methods/system.ts:188` | yes | P1 + optional P2 | operator.admin only |
| P12 | Plugin runtime `runtime.system.enqueueSystemEvent` / `requestHeartbeatNow`; hooks `before_prompt_build` (`prependContext`, `appendSystemContext`) | (not in RFC) | `src/plugins/runtime/runtime-system.ts`, `runtime/system-events.ts`, `hook-types.ts` | yes | P1/P2 with forced `trusted:false`, ack fields + traceparent stripped | plugin = untrusted by construction; prompt hooks gated by `allowPromptInjection` |
| P13 | `sessions_send` tool / `sessions.send` RPC | B.3 (RFC:2037) | `src/agents/tools/sessions-send-tool.ts` | yes | ordinary inter-session message (agent turn), not continuation-bearing | |

[ASSESS] Mapping to the owner's vocabulary: **silent enrichment** = P1 (or P9 `next-heartbeat`); **silent-wake** = P1+P2 (or P9 `now`); **targeted delegate return** = P4 via P5; **host-wide "fire" signal** = P5 `fanoutMode:"all"`+`silent-wake` (the RFC's mast-cell pattern, RFC:1074). All of it is same-gateway.

## 3. ANSWER (2): Seams where a canticle receptor injects enrichment on a host

Receptor pipeline assumed (from canticle receptor-contract v0.2 per scratchpad `notes/spec-core.md`): wire -> verify (syntax/sig/freshness) -> ring -> classify/threshold -> judgment -> expose. The OpenClaw seam is the **expose** step only; nothing below may bypass the receptor (receptor-contract invariant quoted in spec-core.md:307).

Ranked options:

**S1 — in-process OpenClaw plugin receptor (works on main AND gates today, no core change).**
- `api.registerService({id:"canticle-receptor", start(ctx){ /* node:dgram socket, SRV discovery, verify, ring */ }, stop(){...}})` (plugin-registration.types.ts:416-422).
- Expose: `runtime.system.enqueueSystemEvent(wrapExternalContent(body, {source:"api", sender:"<station name> <key fp>", taskName:"canticle <stream>"}), { sessionKey, agentId, contextKey: "canticle:<stationId>:<streamId>", replace: true })`.
  - `contextKey`+`replace` gives "one keyed source owns one queue slot" (system-events.ts:451-452): a looping item re-heard N times occupies one slot and never stacks — directly answers RFC B.1 "injection accumulation" and C.2 "self-bound context occlusion".
- Silent vs silent-wake: silent = enqueue only (item colors the next turn). silent-wake = additionally `runtime.system.requestHeartbeatNow({sessionKey, agentId, reason:"canticle:<class>", coalesceMs})`. Plugin cannot mark trusted-continuation wakes, so these are ordinary `source:"other"` heartbeats subject to busy-skip/active-hours gates.
- Host fan-out: plugin must enumerate targets itself (the core `listKnownSessionKeysOnHost` is module-private in subagent-announce.continuation-return.ts:35); prefer an explicit subscription table (session -> tuned streams) rather than "all sessions".
- Limits: no durability (in-memory queue lost on restart — acceptable for a lossy radio), no traceparent, forced `trusted:false`, 20-slot cap shared with everything else.

**S2 — out-of-process receptor sidecar -> Gateway HTTP hooks (works on both refs, zero OpenClaw code).**
- `POST /hooks/wake` with `mode:"next-heartbeat"` (silent) or `"now"` (silent-wake), `sessionKey` (requires `hooks.allowRequestSessionKey:true` + `allowedSessionKeyPrefixes`), Bearer `hooks.token`. Idempotent coalescing: identical pending text -> `eventOutcome:"coalesced"`.
- Receptor MUST pre-wrap text (dispatchWakeHook does not wrap, hooks.ts:275-280) and must not exceed 256 KiB.
- Downside: no `contextKey`/`replace` over HTTP => a looping item would be re-queued each loop unless receptor dedupes; `mode` is binary.
- Alternative: Gateway WS `system-event` RPC (operator.admin token; `wake` flag).

**S3 — core "addressed bridge" (upstream PR; the RFC's own projection, RFC:921-928).**
- A core producer mirroring `enqueueContinuationReturnDeliveries` (targeting.ts:123-305): per subscribed session, `enqueueSessionDelivery({kind:"systemEvent", sessionKey, agentId, text, traceparent, idempotencyKey: "canticle:<stationKey>:<epoch>:<seq>:<sessionKey>"})` then `enqueueSystemEvent(text, {trusted:true, sessionDeliveryAckId, contextKey?, traceparent})` then optional `requestHeartbeatNow(markTrusted...)`.
  - sha256-idempotent entry id (records.ts:71-75) => a looping frame with stable `(station, epoch, seq)` is enqueued once per recipient even across restarts. This is exactly the "Substrate (addressed variant): sha256 idempotency, exp-backoff retry, restart-survival" row (RFC:928).
  - `awaitPromptAdoption:true` keeps the durable row until the turn actually adopts it (session-delivery-queue-codec.ts:99-107).
  - Emits `continuation.queue.enqueue.delivery` / `continuation.queue.fanout` spans (RFC:1328-1374) — §6.7 explicitly frames these as the observability substrate "for an inter-node ringbuffer `station:stream` broadcast layer" (RFC:1324).
- Only core may use `trusted:true`; canticle should reserve it for frames whose signature verified against an operator-pinned station key, and even then render inside an external-content wrapper — `trusted` is a provenance-field gate, not an instruction-authority grant.

**S4 — ambient "atmosphere" via `before_prompt_build`** (`prependContext` per turn or `appendSystemContext` cached) — for a compact station digest/tuning statement, not for items. Gated by `plugins.entries.<id>.hooks.allowPromptInjection`. Per-turn cost => keep it tiny (this is the RFC's context-cost warning, RFC:102, 2005).

**Required banner (host-authored arrival context, derived from A.6.3):** proposed text shape for S1/S3:
```
[canticle:heard] delivery=station-broadcast mode=silent|silent-wake
station="<name>" key=<fp> sig=valid|absent|invalid stream=<id> class=<chatter|status|alarm>
item=<epoch>/<seq> issued=<ISO> heard=<ISO> delivered=<ISO> expires=<ISO> heardCount=<n>
purpose="<station-declared purpose, <=1024B, labelled contextual>"
<<<EXTERNAL_UNTRUSTED_CONTENT id="...">>> Source: API / From: <station> --- <payload> <<<END_EXTERNAL_UNTRUSTED_CONTENT ...>>>
```
Requirements carried over: distinguishes from direct instruction (A.6.5 #2, RFC:1981); visibly delayed vs fresh (#3, RFC:1982); no sibling/listener-set disclosure (#10, RFC:1989; also canticle's no-sender-tracking invariant); missing provenance must say "unavailable", never fabricated (RFC:1937). Use a `[canticle:` prefix analogous to `[continuation:` so drain accounting/grep anchors work (session-system-events.ts:574-576).

**Silent vs silent-wake policy [ASSESS]:** default **silent** for everything (consistent with canticle v0.1 §9.2 "Receiving MUST NOT trigger a turn" and #48 "Verification authorizes interpretation eligibility, never ... automatic agent turns", both as summarized in scratchpad `notes/spec-core.md:280,348`). Allow **silent-wake** only when all hold: sig=valid from an operator-pinned station, stream class declared wake-eligible (e.g. `alarm`/chemokine), the receiving session opted in (posture), and a per-session wake budget (token bucket; reuse `coalesceMs`) has capacity. This is the RFC's mast-cell split (RFC:1074, 1491): many silent listeners, few woken owners. It also resolves the canticle-docs vs owner-intent conflict (C16 in spec-core.md) by making wake an explicit, budgeted, per-session escalation rather than a receipt side-effect.

## 4. ANSWER (3): Canticle publisher tool under the substrate-adoption rule

Doctrine to honor: "the agent owns intent, the tool owns mechanics, the substrate owns durability" (RFC:877); "describe what the agent wants done (the verb)"; agent must never name substrate/hook/wire (RFC:885); tool must not expose substrate-internal retry semantics (RFC:930); door-as-tool (RFC:1700); declare an owns-table and cite §4.6.

Proposed surface (names are illustrative; canticle's own threads disagree on `publish_to_stream` vs `sing` vs `SEND` per scratchpad `notes/issues.md:32`):

```ts
canticle_sing({
  stream: string,                 // logical streamRef e.g. "fleet/threat" — NOT host:port, group, SRV name
  payload: string,                // <= N bytes (tool enforces; RFC token path uses 4096 chars as precedent)
  mode?: "broadcast" | "addressed",        // RFC:921 vocabulary; default broadcast
  audience?: { sessionKeys?: string[] },   // only for addressed; same-host keys
  keepOnAir?: { forSeconds: number, about?: "rarely"|"steady"|"urgent" }, // intent; tool clamps to station min interval / max TTL
  purpose?: string,               // <=1024B, becomes arrival-context purpose (A.6.3 recipientContext analog)
}) -> { status: "on-air"|"queued"|"rejected", item: "<opaque ref>", expiresAt, clamped?: {...} }
canticle_hush({ item })            // retract/stop looping before TTL
canticle_tune({ stream, posture: "silent"|"wake-on-alarm"|"off" })   // receive-side subscription intent
canticle_listen({ stream?, since? }) // read the hearer-local ring / atmosphere digest on demand
```

Owns-table (declare per RFC:930):
| Layer | Owns |
|---|---|
| Agent | `stream`, `payload`, `mode`, `audience`, `keepOnAir` intent, `purpose` |
| Tool | policy gates, clamping, signing with the station key, seq/epoch assignment, choose UDP ring vs `enqueueSessionDelivery` bridge, span emission, redaction of `payload` as `enrichment` |
| Substrate (broadcast) | ringbuffer aging/loop until `expires_at`, per-station seq, FEC/multicast/unicast relay, SRV/beacon (RFC:927) |
| Substrate (addressed) | §3.6 queue: sha256 idempotency, retry, restart survival (RFC:928) |

Routing decision the tool makes (not the agent):
- `addressed` + all audience on this gateway -> **must** use `enqueueSessionDelivery` (P3/P4). Bespoke UDP here would be "review-rejectable" (RFC:879) because the substrate carries it cleanly.
- `broadcast`, or any recipient off-host -> UDP station ring. **Named functional reason** for bespoke transport (satisfies RFC:879): §3.6 queue is "local to one gateway" with no wire/auth/federation (RFC:644, 648); it has no loop/TTL/aging, no lossy multicast semantics, and no unsolicited-listener model.
- Heard-side bridge back into sessions goes through S1/S3 (i.e. the receptor re-enters the §3.6 substrate for same-host delivery when durability matters).

Gates the tool should enforce (precedents in brackets): `canticle.enabled:false` default [`continuation.enabled:false`, RFC:942/961]; `crossHostPublish: disabled` default-deny [`crossSessionTargeting`, RFC:1078-1085]; max publishes per turn [`maxDelegatesPerTurn:5`, RFC:1462]; min loop interval [`minDelayMs:5000`, RFC:1460]; max TTL [`maxDelayMs:300000`, RFC:1461] (owner wants longer standing items — make it per-stream policy); deny to leaf subagents [`SUBAGENT_TOOL_DENY_LEAF`, RFC:573]; live-read config at each enforcement point [RFC:971, 1085]; tool-input `traceparent` strict validation [RFC:1349]; tool result never echoes payload bytes [A.5.1 precedent RFC:1770]. Optional response-token fallback (e.g. `[[CANTICLE_SING: ...]]`) only if the tier model (RFC:343-376) is wanted.

## 5. ANSWER (4): Same-host-only today vs cross-host gaps canticle fills

Same-host only (SAYS + CODE):
- Targeted returns: "route ... to other known sessions **on the same host**" (RFC:198); `fanoutMode:"all"` = "every known session on the same host" (RFC:232), implemented as every session-store entry of every configured agent on this gateway (subagent-announce.continuation-return.ts:35-47); V1 policy snapshot "addressable same-host sessions" (RFC:1968).
- `session-delivery-queue`: "local-gateway substrate keyed by `sessionKey` ... same gateway namespace" (RFC:644); "The queue is local to one gateway ... this RFC deliberately does not specify that contract" (RFC:648).
- System-event queue: process memory (system-events.ts:73-75). Heartbeat wakes: in-process.
- Hooks/RPC ingress: HTTP/WS to one gateway; hook token is not a sender identity (config-hooks.md).
- Claude Code: cross-session messaging same-machine via per-session Unix socket; cross-machine only via Anthropic Remote Control (claude.ai sign-in), not an open protocol (docs: cross-session-messaging).

Gaps the RFC itself assigns to the "higher broadcast layer" / Binary Canticle (RFC:234, 1702, 1704):
1. Wire transport across hosts (UDP; internet unicast relays; LAN multicast optional) — RFC:648 "would require a wire transport".
2. Identity/auth wrapper — RFC:648; threat model "no authenticated system-event origin" (RFC:1478). Canticle: per-station signing keys.
3. Federation contract — RFC:648; RFC:1702 "station relays in the shape of DHCP helper/relay agents".
4. Discovery — RFC:1702 "DNS SRV discovery for domains of interest".
5. Broadcast semantics absent from the queue: loop until TTL, aging, lossy/no-ack, per-station seq, backpressure-aware multicast, aspect multiplexing, per-receiver transformation (RFC:234, 927).
6. Unsolicited listeners: the queue needs a named `sessionKey`; canticle lets sessions *tune* to streams without the producer knowing them (fan-out without an address book).
7. Freshness/trust/consent across org boundaries — RFC:1704 "the hard question the RFC deliberately leaves open".
8. Cross-harness: one station reachable by OpenClaw sessions and Claude Code sessions.

What canticle must NOT duplicate: same-host addressed delivery (use §3.6), same-session continuation (P6), delegate returns (P4/P5).

## 6. ANSWER (5): Trust / safety constraints the RFC imposes that canticle must honor

1. **Explicit opt-in, default off** — `enabled:false` "explicit deployment consent required" (RFC:1457); continuation "inappropriate as a substitute for human-user consent, for unbounded background loops" (RFC:1489).
2. **Default-deny cross-boundary injection** — `crossSessionTargeting: disabled` because it is a "model-controlled cross-session context-injection surface" (RFC:1085). Canticle is the cross-host generalization; needs its own default-deny for both publish-off-host and receive-into-session.
3. **Runtime gate rechecked at every transition** — A.6.4: gates checked atomically before spawn/finalize/deliver; "A disabled gate never grants a new capability" (RFC:1945). Canticle: check `enabled`+subscription at receive, at enqueue, and at wake.
4. **Wake/chain budgets** — `maxChainLength:10`, `costCapTokens:500000`, `maxDelegatesPerTurn:5`, `minDelayMs:5000` (RFC:1455-1462). **Hazard:** chain budgets reset on any "external system event" turn-entry (RFC:188, 962, 976). A canticle-triggered wake is an external system event, so an agent that publishes, is woken by a reply, publishes again... is never capped by `maxChainLength`. Canticle must carry its own hop/lineage (`in_reply_to` depth) and per-session wake budget. RFC anti-flood rule: fan-out = one chain step regardless of recipients; "back-pressure belongs at the producer, not the wire" (RFC:1354-1357); non-conscription clause "I won't spend yours" (RFC:1365).
5. **Queue abuse** — per-session enqueue rate limiting is out of scope "until a concrete rogue-producer scenario requires it" (RFC:652); canticle is that scenario -> rate-limit in the receptor before enqueue; respect `queueDir.maxFiles` / `SessionDeliveryQueueOverflowError` (RFC:652) and the 20-event in-memory cap.
6. **Provenance banners** — host-authored arrival context, not bare `System:`; must let a zero-awareness recipient distinguish enrichment from instruction; show dispatch vs delivery time; no sibling/cardinality leakage; never fabricate missing provenance (RFC:1928-1937, 1981-1989). `[continuation:enrichment-return]` is the existing text anchor.
7. **Payload integrity** — current state: plaintext, "no integrity verification", "no authenticated system-event origin", "origin tied primarily to session routing, not cryptographic proof" (RFC:1474-1479). Recommended: digest at dispatch + verify; stronger "HMAC signing ... signed announce payloads" (RFC:1481-1483). For cross-host UDP these are mandatory, and verification must happen before any enqueue.
8. **External-content boundary** — `System:` look-alikes are not neutralized; "Role separation plus external-content wrapping is the boundary" (session-system-events.ts:594-596). Wrap every payload with `wrapExternalContent`.
9. **Mention-gating bypass** — internal delivery bypasses `requireMention` (RFC:1464); a canticle wake would too, so canticle needs its own admission gate.
10. **Fleet-scale failure modes** — self-bound context occlusion and channel context poisoning (RFC:2070-2071); injection accumulation (RFC:2005). Mitigate with one-slot-per-source replace, per-session stream caps, dedupe of looped frames, and silent-by-default.
11. **Privacy/redaction** — declare `task`, `enrichment`, `reason` (add canticle payload) before OTel content capture (RFC:1141, 1313); export only hashes of free text in spans (RFC:1282).
12. **Plugin trust floor** — SDK enqueue forced `trusted:false`, no ack fields, no traceparent (runtime/system-events.ts:28-49); a third-party canticle plugin therefore cannot claim trusted provenance — correct behavior, but it means durable/traced delivery needs a core change (S3).
13. **Verification discipline** — "LLMs confabulate tool calls" and "confabulate absent enrichment"; "External verification is therefore mandatory" (RFC:1670-1671). Canticle acceptance tests must check receptor logs / queue acks, not agent self-report; adopt §9.3 blind-enrichment (secret-world) method with negative controls (RFC:1594-1624).
14. **Reset boundary** — `/new` / explicit reset cancels pending continuation work (RFC:1674); canticle per-session subscriptions/pending wakes should be cleared the same way.

## 7. ANSWER (6): Claude Code TUI participation (docs fetched 2026-09-27)

Sources: https://code.claude.com/docs/en/hooks , /en/mcp , /en/channels , /en/channels-reference , /en/cross-session-messaging.md , /en/tools-reference.md (all reachable).

**Publish side:** an MCP server (stdio, user scope or plugin-bundled; tools appear as `mcp__<server>__canticle_sing` or `mcp__plugin_<plugin>_<server>__...`) exposing the same verbs as §4. MCP output warning at 10,000 tokens, default max 25,000 (`MAX_MCP_OUTPUT_TOKENS`) (docs/en/mcp). The server holds the station key and does signing/looping — the model never sees transport.

**Receive side — push, i.e. silent-wake analog: Channels.**
- Server declares `capabilities.experimental['claude/channel']: {}` and emits `notifications/claude/channel` with `{content: string, meta: Record<string,string>}`; arrives as `<channel source="<server>" key="value">content</channel>`; meta keys must be identifiers (letters/digits/underscore), others silently dropped (channels-reference).
- "A channel is an MCP server that pushes events into your running Claude Code session, so Claude can react to things that happen while you're not at the terminal"; "Events only arrive while the session is open"; "If several notifications arrive while Claude is busy, they're delivered together on the next turn"; "Claude Code doesn't acknowledge notifications" (channels, channels-reference).
- Research preview: custom channels need `claude --dangerously-load-development-channels server:canticle`; org `channelsEnabled` / `allowedChannelPlugins`; claude.ai or Console auth, not Bedrock/Vertex/Foundry. "An ungated channel is a prompt injection vector ... Gate on the sender's identity" -> for canticle gate on verified station key, not on stream/room (channels-reference "Gate inbound messages").
- No "silent" option: a channel event is delivered to the model (and reacted to). [ASSESS] use it only for wake-eligible classes.

**Receive side — quiet, i.e. silent analog: hooks reading a receptor-maintained digest.**
- `UserPromptSubmit` (30 s timeout) and `SessionStart` (matchers `startup|resume|clear|compact|fork`) inject via `hookSpecificOutput.additionalContext` or plain stdout; `PostToolUse` / `PostToolBatch` can add `additionalContext` mid-turn (hooks doc). A local receptor daemon keeps a small file/socket of current atmosphere; the hook reads it (deduped by item id) and injects. `SessionStart` with matcher `compact` is the Claude Code analog of OpenClaw's post-compaction rehydration (RFC:831-851).
- Background alarm without channels: command hook with `asyncRewake: true` "runs in the background and wakes Claude on exit code 2. The hook's stderr, or stdout if stderr is empty, is shown to Claude as a system reminder"; async hooks can run on any event; timeouts not enforced for `async` (hooks doc). E.g. a `SessionStart` async-rewake hook running `canticle listen --until alarm` = a one-shot wake-on-alarm.

**Receive side — in-session listener tools.**
- `Monitor` tool: "Runs a command in the background and feeds each output line back to Claude ... Can also open a WebSocket and treat each incoming message as an event"; deadline 5 min default, max 30 min (10 min in `-p`); unavailable on Bedrock/Vertex/Foundry or with telemetry disabled (tools-reference). Good for a subagent or main session tuning in for a bounded window (`ws:` to a local receptor bridge).
- `Bash run_in_background` re-invokes the session when the command exits (one-shot wake). Background subagents keep background commands alive after their final response (tools-reference).

**Receive side — listener session that notifies others (the "sub-agent listens and notifies its harness" case).**
- Cross-session messaging (v2.1.224+): `ListAgents` + `SendMessage` reach subagents, teammates, other local sessions (per-session Unix socket, never via Anthropic) and, with Remote Control, cloud / other-machine sessions (via Anthropic). "When the receiving session is idle, Claude Code starts a new turn with the message" => silent-wake analog. Receiving side is told the message "came from another session, not from you"; it "can't approve anything", "can't change configuration", commands don't run (cross-session-messaging) — the Claude Code equivalent of A.6.3's "not host authority".
- Inbox socket exported to hooks/Bash as `CLAUDE_CODE_MESSAGING_SOCKET` + `CLAUDE_CODE_MESSAGING_TOKEN`; a child process (e.g. a canticle receptor started via Bash/hook) can post `{"type":"auth","token":...}` then a message line to its own session; own-child messages are delivered by default. Built-in anti-flood: per-sender rate limit, identical repeats dropped within a short window, <=50 queued accepted messages, <=100 held; `crossSessionInbound: accept|hold|refuse`; ~1M-char cap (cross-session-messaging "Limitations").
- [ASSESS] This gives Claude Code a native **same-host addressed** substrate comparable to OpenClaw's §3.6 queue for the "listener notifies harness" pattern; by the substrate-adoption logic, a Claude Code canticle bridge should route same-machine notification through `SendMessage`/inbox socket rather than inventing another local IPC, and use UDP only for off-host.

**Equivalence map**

| OpenClaw | Claude Code |
|---|---|
| `enqueueSystemEvent` silent | UserPromptSubmit / PostToolBatch hook `additionalContext` from receptor digest |
| silent-wake (`requestHeartbeatNow`, `/hooks/wake mode=now`) | Channel notification; inbox-socket own-child message; `asyncRewake` hook exit 2 |
| targeted return / `session-delivery-queue` same host | `SendMessage` to local session (socket) |
| post-compaction rehydration | `SessionStart` matcher `compact` hook |
| plugin `registerService` UDP receptor | MCP channel server process or standalone daemon + hooks |
| plugin `registerTool` publisher | MCP server tools |
| `crossSessionTargeting` default-deny | `crossSessionInbound`, `--channels` opt-in, `channelsEnabled` |
| arrival-context banner | `<channel source=... meta>` attributes; "Message from @<session>" + reply address |

Gaps on the Claude Code side [ASSESS]: no durable queue (channel events dropped if session closed; "doesn't acknowledge"); channels are research-preview and allowlist-gated; no true "silent without wake" push — only pull-at-next-prompt via hooks; cross-machine only via Anthropic Remote Control, so canticle's open UDP wire is the only vendor-neutral cross-host path.

## 8. Contradictions / open risks found

1. **Missing enforcement artifact**: RFC:883 says `src/infra/substrate-capability-registry.ts` "is the shipped artifact"; the file does not exist on the gates branch (`git ls-tree` / `git grep` find only the RFC line). The substrate-adoption rule is therefore doctrine-only.
2. **RFC status self-inconsistency**: D.4 text says 3/4 OV rows closed and OV-1 PASS (RFC:2171, 2177) but the table shows OV-1 "open" (RFC:2186).
3. **Feature is fork-only**: nothing continuation-specific (silent/silent-wake, targeting, TaskFlow continuation, tracer) is on `origin/main` (tracks upstream); the RFC header says "Status: Implemented" (RFC:3) — true only for the karmaterminal gates branch. A canticle integration that depends on P4-P8 depends on that branch landing upstream; S1/S2 do not.
4. **§6.7/§6.8 are "Specification target"**, not shipped (RFC:1324, 1380), though pieces (traceparent on SystemEvent, fanout span) exist in code (system-events.ts:54-62; targeting.ts:286-297).
5. **Chain-budget reset loophole** (RFC:188, 962): external system events reset `maxChainLength`/`costCapTokens`, so inter-session/inter-host ping-pong via canticle is not bounded by continuation budgets.
6. **Canticle docs vs owner intent on wake**: canticle v0.1 §9.2 forbids wake-on-receipt; #48 forbids automatic agent turns; owner wants listeners to notify/enrich remote sessions (per scratchpad notes/spec-core.md:39, 280, 348, 383). OpenClaw's silent vs silent-wake split + mast-cell pattern is a ready resolution (silent default, budgeted opt-in wake).
7. **`/hooks/wake` does not wrap external content** while `/hooks/agent` does; any sidecar using `/hooks/wake` must pre-wrap or it injects raw `System:` lines.
8. **"all known sessions" semantics** = every session-store entry for all agents on the gateway, including stale ones filtered only by `shouldIgnorePostCompletionAnnounceForSession`; a canticle "host broadcast" should use explicit tuning instead.
9. **Plugin cannot reach durable queue** (no SDK export of `enqueueSessionDelivery`) — a third-party canticle plugin is limited to lossy in-memory delivery; fine for radio chatter, insufficient for "addressed" mode, which needs core S3.
