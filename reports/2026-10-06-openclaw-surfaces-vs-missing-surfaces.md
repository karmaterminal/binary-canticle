# OpenClaw surfaces vs missing surfaces: state at OpenClaw `9e56928`

*2026-10-06. The workboard of #25, refreshed at exact refs as 🌊 Ronan asked on #25 ([comment](https://github.com/karmaterminal/binary-canticle/issues/25#issuecomment-6020365018)). For current use it replaces `proto/openclaw-surfaces-vs-missing-surfaces.md` (2026-05-05, `1457526`), which stays as lineage. This is a source-only state review: nothing here ran on a seat, a gateway, a key, a manifest or a live daemon, and no OpenClaw code changed.*

**Refs**

| Repository | Ref | Cited as |
|---|---|---|
| karmaterminal/openclaw (the fork) | `main` @ `9e5692852d60bb9e7f373fd6a943f6cde776ab36` | `oc/` |
| karmaterminal/binary-canticle | `main` @ `a03bc8cffdb80e85645f5db5b16f59dd94fc801f` | repository paths; `§n` is RFC-0001 at this commit |
| karmaterminal/frond-ear | `main` @ `014d96fb9eb2761af6ac0af7941c7e8c63a65ab7` | `fe/` |

- On 2026-10-06 at 17:42Z, OpenClaw `main` was 18 commits past `9e56928`, at `5aafce8`. None of those commits touches a file cited here, and none adds canticle code or a UDP listener.
- RFC-0001 cites OpenClaw at `6e6458a`, frozen by D29 (§14.18, §16.1-§16.4). §6 lists what moved between the two commits.
- `report §n` is `reports/2026-10-01-openclaw-interface-demands.md`.
- Every unmarked claim was read in source at these refs. Inferences are marked. Nothing was executed.

---

## Decision note

1. **Nothing is built on the OpenClaw side, and nobody owns it.** At `9e56928` the fork has no canticle code, and none of its own code opens a UDP socket: no `node:dgram` import under `oc/src/`, `oc/extensions/` or `oc/packages/` (Discord voice gets UDP through `@discordjs/voice`, `oc/extensions/discord/package.json:12`). OC-0 (§16.4) and OC-1 (the binding plugin, `report §7`) are unbuilt. No branch of the fork names canticle, OC-0, OC-1, a receptor or next-turn injection, and no open issue or PR is about either slice. The fork's only canticle-related issues are openclaw#53 and its archive copy openclaw#279 ("Ambient attunement baby version", 2026-03 and 2026-04): pre-RFC design notes with no comments. The 15 fork PRs that mention canticle are closed continuation-era work. No issue in this repository names an owner either. §8 proposes one bounded issue: OC-0, in the fork.

2. **A record v1 client can attach now without a second owner of the UDP port.** A plugin service (`registerService`) can connect to the host daemon's socket with `node:net` as one more peer, as frond-ear does (D35). It binds no port, starts no child process, and needs no core change and no trusted privilege. That is OC-1's first step, called OC-1a below: P1 `ringbuffer_only`, receive health and counts for the princes, and no heard text in any session. On a mixed host, case (1) holds for it by construction. If OC-1 has no embedded receptor (recommended), case (4) has nothing to test on the OpenClaw side.

3. **OC-0 is needed for landing, and only for landing.** Next-turn injection at `9e56928` has none of §16.4's items 1-6. Of item 7 it has only refusal at its cap, with no reason and no refusal for Codex or Copilot. Item 8 already holds (§1.3). The code under it has been refactored since `6e6458a`, but its behaviour has not changed. Ambient delivery (OC-1c), the at-most-once claim of §14.18.5 and the host-slot steps of mixed-host cases (5)(d′), (6) and (7) wait on OC-0. Receive health does not, and neither does a read.

4. **Three questions for the princes, before anything heard reaches an OpenClaw prince's model:**
   - **a. Does a read taint?** §14.12 taints a session that "has drained" an item, and the glossary (§2) says "ingested". *Inferred:* a tool read that returns heard text ingests it, so it taints. If so, item 4 then denies a Discord-bound session's outbound messages, its own replies included, until §23.2 question 22 settles. Most prince sessions are Discord-bound: Discord DMs share `agent:main:main` by default, and each guild channel is its own session (`oc/docs/channels/discord/messaging.md:20-21`). A read tool would then be usable only in sessions with no off-host route. frond-ear's `hear` raises the same question, and frond-ear tracks no taint at `014d96f`.
   - **b. Does mixed-host case (6) gate a binding that holds no host-slot entries?** §14.18.2 requires cases (1)-(7) before P1 runs on a host with more than one binding. Case (6) needs an accepted host-slot entry that the binding withdraws and then settles, and cases (5)(d′) and (7) withdraw such entries too. Only a landing binding holds them, and only OC-0 gives it the withdraw call and the settled-state query (§1.3). As written, frond-ear's canticle on silas and ronan (§23.2 question 23) and #88's publication gate (`plugins/binary-canticle/README.md`, "Publishing to ClawHub", item 4) wait on OC-0 and OC-1c. The alternative is an amendment that applies those host-slot steps only to bindings that hold host-slot entries. §14.18 is frozen (D29), so either way the princes choose explicitly.
   - **c. Is a read tool part of P1?** §14.18.9's P1 is `ringbuffer_only` and `ambient`, and names no tool. §23.2 question 24 is to be decided "before any model-callable canticle tool is exposed under a binding, so this gates P2's tool surface, not P1" (Emeric). A read shaped like frond-ear's `hear` (a stream filter and a limit, with no `view: "raw"` and no tune) is such a tool, though it stays clear of both of question 24's open items, and frond-ear#28 already ships one, off by default. The princes should say whether OC-1b may come with P1 on those terms or waits for question 24. Question 28 (observability) still comes before any P1 proof.

5. **What moved since the freeze is fact, not rule.** Between `6e6458a` and `9e56928`, four things changed:
   - the system-event queue now refuses when full, where it used to drop its oldest event;
   - the keyed and blob stores opened to every loaded plugin, but §14.18.7 still lists them as trusted-only privilege that a binding must not depend on;
   - `requestHeartbeatNow` is past its `removeAfter` date and still present;
   - `plugin-sdk/infra-runtime` is gone, and `plugin-sdk/system-event-runtime` now exports drain and consume.

   None of them changes a canticle rule. The store wording needs an amendment only if a binding is to keep its state there (§6).

---

## 0. Checklist matrix

Status values:
- **exists**: usable for the stated use as it is.
- **partial**: exists; the gaps are named.
- **missing**: nothing in code.
- **RFC-only**: specified in RFC-0001, not built.
- **refused**: exists, and RFC-0001 refuses it as a canticle path.

The planes are those of §3.1. OC-1a, OC-1b and OC-1c are the steps of §2.

| # | Surface / capability | Exists now (OpenClaw `9e56928`) | Plane | Status | Candidate implementation | Must refuse to become |
|---|---|---|---|---|---|---|
| 1 | Plugin activation and configuration | JSON5 (`oc/src/config/io.load.ts:114`). `plugins.entries.<id>` is a strict object; plugin keys go under `.config` (`oc/src/config/zod-schema.root-support.ts:136-187`). Explicit `enabled: false` disables (`oc/src/plugins/config-activation-shared.ts:99-102`). An installed non-bundled plugin with no entry is enabled (`:165`), and workspace plugins stay off unless allowed (`:115-122`). A non-empty `plugins.allow` leaves out every plugin not in it (`:138-140`). A plugin that declares tools is auto-enabled once its `.config` sets any key of its own schema (`oc/src/config/plugin-auto-enable.shared.ts:87-100`, `:414-434`), unless it is denied or explicitly disabled (`oc/src/config/plugin-auto-enable.materialize.ts:296`), and an entry with a config block joins a non-empty allowlist (`:215-231`). The schema is checked when the plugin is enabled or configured (`oc/src/config/validation-plugin-config.ts:379-401`). | Control | exists | §14.18.7 as written (D30): `enabled: false` written explicitly, a shallow schema, semantic checks at service start | a configuration that can refuse Gateway boot; enablement by the mere presence of a block |
| 2 | UDP receptor on the host | None in OpenClaw. binary-canticle's `canticle daemon` binds UDP and serves record v1 to peers over `$XDG_RUNTIME_DIR/canticle/daemon.sock`: mode 0600 in a 0700 directory, peers checked by `SO_PEERCRED` against the daemon's own uid unless `--allow-uid` adds others (`prototype/canticle-station/canticle/daemon.py:1-12`, `:77-79`, `:355`; `prototype/canticle-station/canticle/__main__.py:294`, `:613-621`). | Binary (signal) | exists (D35) | one daemon per host; every binding is a peer | a receptor inside the gateway on a host that runs a daemon |
| 3 | Record v1 client in the gateway | No canticle code. The parts exist: `registerService` (`oc/src/plugins/plugin-api.types.ts:292-296`; shape `oc/src/plugins/plugin-registration.types.ts:419-426`), whose context carries `stateDir`, `logger` and `serviceHealth` (`:363-368`). Registering a service needs no trust (`oc/src/plugins/registry-registrars-operations.ts:371-390`). Native plugins run in-process and unsandboxed, and may register network handlers and services (`oc/docs/plugins/architecture.md:880-883`). The deep audit's static scan of installed plugins (`oc/src/security/audit.deep.runtime.ts:139-160`) has no rule for sockets; its `env-harvesting` rule flags `process.env` within 8 lines of an HTTP send (`oc/src/skills/security/scanner.ts:162-170`). A bundled extension already reads newline-delimited JSON from a local unix socket (`oc/extensions/signal/src/client-unix.ts:45`, `:69-105`), though it throws on an over-long line where §14.18.2 discards it and counts it. | Bridge (harness adapter) | missing; every part exists | OC-1a (§2) | a second parser of the wire; a source of trust |
| 4 | Child receptor (the stdout transport of §14.18.2) | The SDK has no long-lived supervisor. It offers spawn, timeout, process-tree kill and PID helpers (`oc/src/plugin-sdk/process-runtime.ts:1-40`). The deep security audit flags `child_process` spawns as critical (`oc/src/skills/security/scanner.ts:110-118`). binary-canticle has no stdout record transport: "only the daemon carries records" (`prototype/canticle-station/README.md:321`). | Bridge | RFC-only on both sides | none: use the daemon | a binding-owned receptor on a host with more than one binding (§14.18.2) |
| 5 | Binding durable state | The service's own `stateDir` (row 3). The keyed, sync keyed and blob stores are open to every loaded plugin (`oc/src/plugins/registry-runtime.ts:227-243`; `oc/docs/plugins/sdk-runtime/state-and-system.md:213`). They are bounded, overflow with `evict-oldest` or `reject-new`, and take a default TTL (`oc/src/plugin-state/plugin-state-store.types.ts:144-153`). | Ledger (host-local) | exists | frame keys, tombstones and entry intents (§14.18.5) in the binding's own state directory now; the keyed store with `reject-new` only after §14.18.7 is amended (§6) | a store that evicts a live tombstone (§16.4 item 3 refuses instead) |
| 6 | Host slot: next-turn injection | `api.session.workflow.enqueueNextTurnInjection` (`oc/src/plugins/plugin-api.types.ts:119-123`), durable in the session entry (`oc/src/config/sessions/types.ts:295`). At most 32 entries per plugin and session, of up to 32 768 characters each (`oc/src/plugins/host-hook-state.ts:28-30`). Its TTL counts from creation (`:60-65`), its idempotency key covers pending entries only (`:114-119`), and its result carries no reason (`oc/src/plugins/host-hook-turn-types.ts:31-35`). Drained on the embedded and CLI paths, not on Codex or Copilot (`oc/docs/plugins/hooks/prompt-and-session.md:68-72`). | Control | partial | OC-0 (§16.4); at most two canticle entries per session (§14.14) | a per-frame queue; a third canticle entry in a session |
| 7 | Supersede, withdraw, settled state | None. The workflow API has no withdraw, no settled-state query and no settlement notice (`oc/src/plugins/plugin-api.types.ts:119-147`). | Control | RFC-only (§16.4 items 2-3) | OC-0 | eviction in place of refusal |
| 8 | Retention at drain | A drain skips the entries of every plugin that is not `loaded` or not allowed prompt injection, then deletes the whole map. The code says this is intended: "Inactive plugin records are stale owner state and are discarded with expired records" (`oc/src/plugins/host-hook-state.ts:158-170`, `:182-184`). | Control | missing, by stated design | OC-0 item 4, for entries that carry a deadline | none |
| 9 | Drain caps | None. One drain returns every live entry, up to 32 entries of 32 768 characters per plugin (`oc/src/plugins/host-hook-state.ts:28-30`, `:176-181`). | Control | missing | OC-0 item 5, in host configuration | caps the plugin sets for itself |
| 10 | Rendering and provenance | Drained text is joined raw, prepend entries first (`oc/src/plugins/host-hooks.ts:320-341`), then joined into the active user prompt (`oc/src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:388-396`). `wrapExternalContent` is exported to plugins (`oc/src/plugin-sdk/security-runtime.ts:34-38`), but its source type is private and has no broadcast value (`oc/src/security/external-content.ts:47-55`). | Control | partial: a binding can wrap its own text, but its banner would be plugin-authored | OC-0 item 6: a host-authored banner outside the wrapper (§14.13, §14.18.8) | a trusted `System:` line; a payload that frames itself |
| 11 | System events | In memory (`oc/src/infra/system-events.ts:1-3`), 20 per session, refused when full (`:42`, `:183-190`). Rendered as `System:` lines whose look-alikes are left alone, "an explicit product decision" (`oc/src/auto-reply/reply/session-system-events.ts:133-137`). | Control | refused (§16.2) | none | a landing path |
| 12 | Session-delivery queue | Durable (SQLite) and core-only. `enqueueSessionDelivery` (`oc/src/infra/session-delivery-queue-storage.ts:151`) has one caller, the restart sentinel (`oc/src/gateway/server-restart-sentinel.ts:554`, `:575`). | Control | refused; unreachable (§16.1) | none | none |
| 13 | Prompt hooks | `agent_turn_prepare`, `before_prompt_build` and `heartbeat_prompt_contribution` are prompt-injection hooks (`oc/src/plugins/hook-types.ts:183-186`). `agent_turn_prepare` receives every plugin's drained injections (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:94-109`). A non-bundled plugin may register it only with `allowConversationAccess` (`oc/src/plugins/registry-registrars-tools-hooks.ts:53-63`, `:401-416`). Pending injections, every plugin's, are already readable without it through the session-store SDK (§1.3, "Query or notify"). | Control | refused (D31, §16.4) | none: OC-0's settled-state query tells the binding what was consumed | a window onto the raw prompt or another plugin's injections |
| 14 | Tools (on-demand reads) | `registerTool` (`oc/src/plugins/plugin-api.types.ts:225-228`). The tool context carries `agentId`, `sessionKey` and `sessionId` (`oc/src/plugins/tool-types.ts:32-35`). Each tool must be declared in `contracts.tools` (`oc/docs/plugins/manifest/capabilities.md:93`), which makes the plugin one that a config block auto-enables unless `enabled: false` is written (row 1, D30). | Control | exists | OC-1b: a read shaped like frond-ear's `hear`, after questions 4a and 4c | a `raw` view or a tune offered to the model (§23.2 question 24); a wake |
| 15 | Tool policy for taint | `before_tool_call` can block a call or require approval (`oc/src/plugins/hook-before-tool-call-result.ts:14-30`), and it is not a conversation hook (`oc/src/plugins/registry-registrars-tools-hooks.ts:53-63`). `before_prompt_build` can narrow the tool set with `toolsAllow` (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:172-174`), which the Codex app server refuses (`oc/extensions/codex/src/app-server/run-attempt-prompt.ts:294-298`). | Control | partial (§23.2 question 5) | the binding denies tools to tainted sessions through `before_tool_call`; a core tool-policy seam stays open | a prompt warning as the only control (§14.12) |
| 16 | Turns and wakes | Open to plugins or hook callers: `requestHeartbeat`, whose caller picks the source and intent, with no plugin source (`oc/src/infra/heartbeat-wake-contracts.ts:6-22`); `requestHeartbeatNow` (`oc/src/plugins/runtime/runtime-system.ts:19-28`, `:33`); `runHeartbeatOnce` (`:34-43`); `scheduleSessionTurn` (`oc/src/plugins/plugin-api.types.ts:140-142`); `subagent.run` (`oc/src/plugins/runtime/types.ts:200`); `/hooks/wake` (`oc/src/gateway/hooks.ts:238-262`; `oc/src/gateway/server/hooks.ts:263-291`). `dispatchHookAgentTurn` is bundled or trusted only (`oc/src/plugins/registry-runtime.ts:412-425`). | Control | refused in P1 and P2 (D25); the P3 seam is open (§23.2 question 27) | none in this review | a turn, wake or sub-agent run caused by heard content |
| 17 | Channel ingress | `dispatchInboundMessage` (`oc/src/auto-reply/dispatch.ts:183`) → `dispatchReplyFromConfig` (`oc/src/auto-reply/reply/dispatch-from-config.ts:25`) → `getReplyFromConfig` (`oc/src/auto-reply/reply/get-reply.ts:220`) → `runReplyAgent` (`oc/src/auto-reply/reply/agent-runner-run.ts:76`). Plugins add channels with `registerChannel` (`oc/src/plugins/plugin-api.types.ts:243-247`). | Control | refused | none | a channel: heard text is not a message from anyone in the room |
| 18 | Status surfaces for the princes | `registerGatewayMethod`, optionally bound to a named session (`oc/src/plugins/plugin-api.types.ts:255-267`); `registerCli` (`:274-277`); `registerSessionExtension`, plugin-owned state shown in session rows (`:114-117`). Service health is a single failure flag (`oc/src/plugins/service-health.ts:15-45`). | Control | exists | OC-1a: receive health (run, `joined_late`, `records_lost`), counters, presence, and each session's tune and taint state, all with no heard text | a status that hides loss; heard text reaching a session through a status call |
| 19 | Observability | A plugin service gets internal diagnostics only as the bundled or trusted `diagnostics-otel` or `diagnostics-prometheus` (`oc/src/plugins/service-diagnostics.ts:23-35`). | Control | missing for a third-party binding (§23.2 question 28) | question 28's choice: a generic core diagnostics event, or the binding's own exporter | heard payloads in spans (hashes and lengths only, §16.4) |
| 20 | Membership: manifest and presence | Nothing in OpenClaw. The daemon emits presence from beacons. The manifest is unsigned; signing and the genesis pin (§10.3) are in `report §7`'s BC-5 slice. | Membership | partial (binary-canticle side) | the binding shows presence as the records give it | trust from a name, an address, DNS or a payload (I-11) |
| 21 | Ledger promotion of heard content | None. | Ledger | RFC-only (§6.4) | out of scope here | promotion by a tainted session (§14.12 item 6) |
| 22 | Relays and bridges (routed, air-gapped) | None. | Bridge | RFC-only (§11, §12, §18) | out of scope here | a second receptor; a rewriter of judgments (§3.1) |
| 23 | Continuation feature | Not on `main`. openclaw#1418 is 🌿's review-only draft ("Continuation presentation cut", head `41b8d69`). At that head, next-turn injection is unchanged (`src/plugins/host-hook-state.ts:29`, `:172`, `:196`) and the system-event queue still drops its oldest event (`src/infra/system-events.ts:297-298`, `:415-416`). | Control | not on `main` | none: OC-0 replaced Tier B (§16.4) | a dependency of OC-0 or OC-1 |
| 24 | frond-ear, the adjacent client (Claude Code) | A `host-daemon` record v1 client (`fe/src/canticle/record-client.ts:65-142`), an `embedded` receptor that refuses to bind while a daemon answers (`fe/src/canticle/source.ts:26-108`), and `hear` (`fe/src/shim.ts:150-164`; `fe/src/daemon.ts:1141-1156`) with the §14.13 banner (`fe/src/canticle/hear.ts:97-137`). No taint tracking: "taint" appears nowhere in `fe/src/` or `fe/docs/`. Off unless configured. | Bridge (another harness) | exists; not yet proved live (frond-ear#24) | the reference design for OC-1's client (§3) | evidence that OpenClaw is integrated |

---

## 1. Trace at OpenClaw `9e56928`

### 1.1 Extension ingress: how a binding gets into the gateway

1. **Config.** The file is read as JSON5 (`oc/src/config/io.load.ts:114`). The plugin's entry is a strict object, so canticle keys live under `.config` (`oc/src/config/zod-schema.root-support.ts:136-187`).
2. **Activation.** `config-activation-shared.ts` decides (`oc/src/plugins/config-activation-shared.ts:80-165`). A disabled plugin gets no registration plan (`oc/src/plugins/loader-registration-plan.ts:45-47`) and is recorded as disabled without running `register` (`oc/src/plugins/loader-runtime-candidate.ts:225-233`).
3. **Registration.** `register(api)` calls `api.registerService` (`oc/src/plugins/plugin-api.types.ts:292-296`), which records the service with no trust check (`oc/src/plugins/registry-registrars-operations.ts:371-390`).
4. **Start.** `startPluginServices` (`oc/src/plugins/services.ts:172`) runs after the gateway attaches (`oc/src/gateway/server-startup-post-attach.ts:301`) and on plugin reload (`oc/src/gateway/server-plugin-reload.ts:357`, `:574`). A change under the service's `reload.configPrefixes` restarts it (`oc/src/gateway/config-reload-plan.ts:337`). A replaced service gets 5 s to stop (`oc/src/plugins/services.ts:40`).
5. **Context.** `start(ctx)` receives `config`, `stateDir`, `logger` and `serviceHealth` (`oc/src/plugins/plugin-registration.types.ts:363-368`).
6. **Records.** The service opens the daemon's unix socket with `node:net`, sends the D36 join-snapshot request as its first line, then reads record v1 (§14.18.3). This is what frond-ear's client does (`fe/src/canticle/record-client.ts:65-88`). In OpenClaw, Signal's client opens a unix socket the same way (`oc/extensions/signal/src/client-unix.ts:45`).
7. **Out.** From the binding to a session there are only three routes: a tool read (row 14), a next-turn injection (rows 6-10, through OC-0), and status surfaces that carry no heard text (row 18). §1.2 lists every other way into a session and why it is refused.

### 1.2 Session ingress: every way content reaches a session

| Route | Call chain | Durable | Who can use it | For canticle |
|---|---|---|---|---|
| Channel message | `dispatchInboundMessage` → `dispatchReplyFromConfig` → `getReplyFromConfig` → `runReplyAgent` (row 17) | per channel | channel plugins | refused |
| System event | `api.runtime.system.enqueueSystemEvent` (`oc/src/plugins/runtime/runtime-system.ts:31`) → `enqueueSystemEventFromSdk` (`oc/src/plugins/runtime/system-events.ts:26-33`) → `enqueueSystemEvent` (`oc/src/infra/system-events.ts:210`); drained and rendered by `drainFormattedSystemEvents` (`oc/src/auto-reply/reply/session-system-events.ts:92`) | no | any plugin | refused (§16.2) |
| Next-turn injection | enqueue: `registry-api.ts` (`oc/src/plugins/registry-api.ts:140-168`) → `enqueuePluginNextTurnInjection` (`oc/src/plugins/host-hook-state.ts:67-132`). Drain: at prompt build (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-build.ts:167`; `oc/src/agents/cli-runner/prepare.ts:667`) → `resolvePromptBuildHookResult` (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:70-91`) → `drainPluginNextTurnInjections` (`oc/src/plugins/host-hook-state.ts:134-193`) | yes (session store) | any plugin unless `hooks.allowPromptInjection: false` (`oc/src/plugins/hook-policy-decisions.ts:6-8`) | the host slot; ambient after OC-0 |
| Prompt hooks | drained injections → `agent_turn_prepare` → heartbeat contribution → `before_prompt_build` (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:92-141`; order in `oc/docs/plugins/hooks/prompt-and-session.md:68-72`) | no | prompt-injection hooks; `agent_turn_prepare` needs conversation access | refused (row 13) |
| Tool result | `registerTool`; the factory context names the session (`oc/src/plugins/tool-types.ts:33`) | no | the model, when it calls the tool | OC-1b, after questions 4a and 4c |
| Wake endpoint | `POST /hooks/wake`: `normalizeWakePayload` (`oc/src/gateway/hooks.ts:238-262`) → `dispatchWakeHook`, which queues a system event and, with `mode: "now"`, calls `requestHeartbeat` with source `hook` and intent `immediate` (`oc/src/gateway/server/hooks.ts:263-291`) | no | holders of a hook token | refused (§16.2) |
| Heartbeat | `requestHeartbeat`, `requestHeartbeatNow`, `runHeartbeatOnce` (`oc/src/plugins/runtime/runtime-system.ts:19-43`) | no | any plugin | refused (D25) |
| Scheduled turn | `scheduleSessionTurn` (`oc/src/plugins/plugin-api.types.ts:140-142`; `oc/src/plugins/registry-api.ts:231`) | yes (cron) | any plugin | refused |
| Sub-agent | `api.runtime.subagent.run` (`oc/src/plugins/runtime/types.ts:200`) | no | any plugin | refused: it starts a turn with the plugin's text as the prompt (`report §4.1`) |
| Hook agent turn | `dispatchHookAgentTurn` (`oc/src/plugins/registry-runtime.ts:412-425`) | no | bundled or trusted plugins only | out of reach (D31) |
| Session-delivery queue | `enqueueSessionDelivery` (`oc/src/infra/session-delivery-queue-storage.ts:151`) | yes (SQLite) | core only (`oc/src/gateway/server-restart-sentinel.ts:554`, `:575`) | unreachable (§16.1) |

This answers #5's question ("how does a broadcast become context enrichment?") for OpenClaw at `9e56928`: through a next-turn injection that OC-0 makes safe, or through a read the session asks for. It never goes through a system event, a channel message, a prompt hook or a wake.

### 1.3 Host-slot custody: who holds an accepted entry, and what OC-0 changes

Here "host slot" is canticle's term (§14.14): one pending next-turn injection entry per supersede key. OpenClaw's own "session entry slots" are reserved session-entry field names (`oc/src/plugins/session-entry-slot-keys.ts:1-15`) and have nothing to do with it.

| Moment | At `9e56928` | OC-0 property (§16.4) |
|---|---|---|
| Accept | Input checks (`oc/src/plugins/host-hook-state.ts:78-94`); expired entries filtered, then pending-only dedupe and the 32-entry cap (`:114-120`); unknown session refused (`:128-130`). The result is `{enqueued, id, sessionKey}` with no reason (`oc/src/plugins/host-hook-turn-types.ts:31-35`). With `allowPromptInjection: false` the call is refused with a diagnostic (`oc/src/plugins/registry-api.ts:141-153`). | 1 (absolute expiry, not-before), 2 (conditional supersede), 3 (duplicate after settlement), 7 (a refusal with a reason, `harness_does_not_drain` included) |
| Hold | The session entry's `pluginNextTurnInjections` (`oc/src/config/sessions/types.ts:295`). A restart keeps it: restart cleanup runs in `promoted-slots` mode (`oc/src/plugins/host-hook-cleanup.ts:180`; `oc/docs/plugins/hooks/prompt-and-session.md:347-349`). | none needed |
| Expire | A TTL counted from creation (`oc/src/plugins/host-hook-state.ts:60-65`), checked at enqueue (`:114-116`) and at drain (`:176-178`). | 1 |
| Withdraw or supersede | No call exists in the injection API. A session patch could remove entries (next row), but it edits host-owned state and records no outcome. | 2 |
| Query or notify | No call reports a settled outcome: a drained entry leaves no record. Pending entries are readable: `getSessionEntry` in the public `plugin-sdk/session-store-runtime` (`oc/src/plugin-sdk/session-store-runtime.ts:155-159`; `oc/docs/plugins/sdk-subpaths.md:443`) returns the session entry through a projection that strips only private keys (`oc/src/plugin-sdk/session-store-runtime-internal.ts:32-40`; `oc/src/config/sessions/session-entry-projection.ts:26-39`), so `pluginNextTurnInjections` comes back whole, every plugin's entries and text included. *Inferred, not run:* `patchSessionEntry` (`oc/src/plugin-sdk/session-store-runtime.ts:220-253`) applies the same projection to its patch, so a plugin could also rewrite the map. The only drain signal is `agent_turn_prepare`'s `queuedInjections` (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:94-109`), a conversation hook. | 2 (the query is authoritative; the notification is a convenience) |
| Drain | At prompt build (§1.2) → `drainPluginNextTurnInjections` (`oc/src/plugins/host-hook-state.ts:134-193`), which deletes the whole map (`:184`). | 3 (record the settled outcome), 5 (drain caps) |
| Discard at drain | Entries of a plugin not `loaded`, or not allowed prompt injection, are skipped and then deleted with the map (`:158-170`, `:182-184`). | 4 (keep entries that carry a deadline until it passes) |
| Render | Joined raw (`oc/src/plugins/host-hooks.ts:320-341` → `oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:175-186` → `oc/src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:388-396`). | 6 (a host-authored banner outside the wrapper) |
| Retry | Retries of the same run reuse the drained entries without draining again (`oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:47-68`; `oc/docs/plugins/hooks/prompt-and-session.md:323-325`). So one consumption can be rendered more than once within one run. | none: consumption stays at prompt assembly (§14.18.5); OC-0's proof should show the retry case |
| Clean up | Reset, delete and disable remove pending entries (`oc/src/plugins/host-hook-cleanup.ts:176-192` → `oc/src/config/sessions/plugin-host-cleanup.ts:92-113`). Restart keeps them. | 3 (tombstones survive reset and disable; delete clears both) |
| Codex and Copilot | Not drained (`oc/docs/plugins/hooks/prompt-and-session.md:68-72`). | 7 (refuse with `harness_does_not_drain`) |
| Routing inputs | The entry type has none (`oc/src/plugins/host-hook-turn-types.ts:7-16`). | 8 (keep it that way) |

In these terms, case (6) of §14.18.2 needs an entry that was *accepted* and is *held* when the daemon drops the binding's connection. The binding must then *withdraw* it and *query* its outcome before anything settles as `rejoined`. Cases (5)(d′) and (7) need the same withdrawal. Neither call exists in the injection API, and a session patch is no substitute: it records no outcome, so the binding could not tell an entry a drain consumed from one it removed (case (6)(b)). These cases cannot be built on OpenClaw at `9e56928`.

### 1.4 Where a record v1 client attaches without owning UDP twice

- **Attach** as a plugin service that is a peer client of the host daemon's socket (D35, §14.18.2). The daemon is the only process with the port. The gateway holds one socket connection. The daemon must allow the gateway's uid: run it as the gateway's user, or pass `--allow-uid` (`prototype/canticle-station/canticle/__main__.py:294`, `:621`; `prototype/canticle-station/canticle/daemon.py:355`).
- **Not** with `node:dgram` in the plugin (an embedded receptor), a child `canticle listen` (it binds UDP and prints the spike's own JSON events, not record v1: `prototype/canticle-station/canticle/__main__.py:576-585`), or a child `canticle daemon` (a second daemon fails to bind: `prototype/canticle-station/README.md:322-323`). Each would make the gateway a second UDP owner on a mixed host.
- **On a host with no daemon**, §14.18.2 lets a binding run its own receptor as a supervised child, but only where that receptor is the host's one listener. binary-canticle has no stdout record transport (`prototype/canticle-station/README.md:321`), so today the daemon is the only source of record v1, and OC-1 needs one on every host it runs on.
- **Case (4).** If OC-1 has no embedded mode, case (4) has nothing to test on the OpenClaw side. The run card runs it with frond-ear ([frond-ear#24 comment](https://github.com/karmaterminal/frond-ear/issues/24#issuecomment-5967000742)).

---

## 2. OC-0 and OC-1, kept apart

OC-1 is split three ways. OC-1a and OC-1b together are the "prince-visible, silent/opt-in hear surface" of Ronan's request: OC-1a gives the princes the binding's state, and OC-1b lets a prince's session read what is live. OC-1c is ambient landing, which is P1 too (§14.18.9) but needs OC-0.

| Slice | What | Needs first | Test | Receipt | Owner |
|---|---|---|---|---|---|
| **OC-0**: core seam in karmaterminal/openclaw | §16.4 items 1-8, as one additive change to next-turn injection. No wake, no canticle logic. Entries that use none of the new fields behave as today. | Nothing. BC-1 is RFC-0001's revision of 2026-10-01, and BC-2, the daemon, landed in #79 (§23.2 question 23). | `report §7`'s OC-0 gate, extended for what §16.4 added after it (conditional supersede, the settled-state query, the settlement notice, outcome retention); the §14.14 flood proof (at most two pending canticle entries per session; no other producer's entries evicted); a retry of one run (row "Retry" of §1.3). | the merged PR at a literal SHA and its CI output; then an amendment re-pinning §16.1-§16.4 to that SHA (D29) | none |
| **OC-1a**: receive and state, P1 `ringbuffer_only` | A plugin with a `canticle-receptor` service. It connects to the daemon socket with `node:net`, asks for a join snapshot first, and reads record v1 with §14.18.2's framing and backpressure: over-long lines discarded and counted, depth capped, a bounded queue, and a stall treated as connection loss. It applies §14.18.3's bootstrap and run boundaries, keeps the local ring, and shows the princes receive health, counters and presence with no heard text. Off by default, with `enabled: false` written out. No tools that return heard text, no landing, no wake, no publish. | Nothing in OpenClaw; a daemon on the host (built). A placement choice: an extension in the fork or an external package, a third-party plugin either way (§14.18.7). | §14.18.2's single-host gate, from the binding's side: framing (an over-long line, a nesting-depth bomb, a partial line at end of file); backpressure (a stalled binding stays bounded and reports `records_lost`); supervision (the daemon's crash, hang, `fatal` and exit without `bye`); restart (a record re-emitted by a new run delivers nothing twice); teardown (disable leaves no connection, timer or tool). Also a late join with and without a snapshot (case (5)), and the `records_lost`-once half of case (6)(f); its settlement half needs OC-0. Record fixtures taken from this repository's daemon, as frond-ear's are (frond-ear `test/fixtures/canticle/SOURCE.md`). | test output at exact SHAs; a loopback interop log against `canticle daemon`, like 🍃's 10-02 smoke ([frond-ear#24 comment](https://github.com/karmaterminal/frond-ear/issues/24#issuecomment-5958167748)) | none |
| **OC-1b**: a read for a prince's session | A model-callable read with a stream filter and a limit, showing the digest or items, never `raw`. The §14.13 banner sits outside `wrapExternalContent`. Taint is recorded per session from the tool context, and §14.12's denials go through `before_tool_call` (row 15). | OC-1a; answers to questions 4a and 4c. | a rendering corpus (look-alikes of the banner and the wrapper, a fake `System:` line); negative controls in the manner of §16.7 (a payload that asks to re-sing, to reply elsewhere or to fetch a `body_ref` changes nothing); taint recorded when a read returns heard text (per 4a); each §14.12 denial on a tainted session. | test output; the blind-enrichment acceptance of §16.7 belongs to the live proof | none |
| **OC-1c**: ambient landing | The two slots over OC-0 (§14.14, §14.18.6), the handshake of §14.18.5, A11's desynchronised landing, post-drain notes, and taint from settlement. | OC-0 merged; OC-1a; target sessions with no off-host channel route until §23.2 question 22 settles. | §14.18.5's crash proofs; §14.14's flood proof through the binding; mixed-host case (6) on silas and ronan. | a proof packet pinned as §14.18.2 *Pinning* requires | none |

Out of scope: P2 publishing (OC-2), the P3 wake (OC-3, §23.2 question 27), OC-4 observability beyond question 28, and the canary and arming of OC-5.

**Minimal dependency order**

1. Now, independently of each other: OC-0 in the fork, and OC-1a as a plugin. Neither waits for the other or for a seat. This matches the order recorded on #61: Emeric's (BC-2 and OC-0 independently, then a proven receive-only P1) and rune's (OC-0 may proceed once its proof gate is defined), §14.18.9.
2. The princes answer questions 4a-4c, and settle question 28 before any P1 proof.
3. OC-1b, if the answers to 4a and 4c allow it.
4. After OC-0 merges: OC-1c in test sessions with no off-host route, with §14.18.5's crash proofs.
5. The mixed-host proof on silas and ronan, with OC-1 beside frond-ear, case (6) included or as amended under 4b.
6. Any seat configuration or arming is a separate decision. It is not a step of this order.

---

## 3. frond-ear: an adjacent client, not proof of OpenClaw

frond-ear's canticle support is a Claude Code binding. It shows what a peer of the daemon looks like. It shows nothing about OpenClaw.

| What frond-ear shows | Where |
|---|---|
| A non-Python peer can consume the daemon's record v1. | 🍃's loopback interop smoke, binary-canticle `c4d1971` with frond-ear `9f9107d`, one host, 127.0.0.1 only ([frond-ear#24 comment](https://github.com/karmaterminal/frond-ear/issues/24#issuecomment-5958167748)) |
| The D36 snapshot request and `joined_late`. | frond-ear#45; `fe/src/canticle/record-client.ts:79-82` |
| An embedded receptor that refuses while a daemon answers: case (4). | `fe/src/canticle/source.ts:49-108` |
| A read that never wakes and marks nothing seen. | `fe/src/daemon.ts:1150` |
| The §14.13 banner outside the untrusted-content wrapper. | `fe/src/canticle/hear.ts:107-137` |

What it does not show:
- **Anything OpenClaw-specific:** plugin activation, service lifecycle, session keys, next-turn injection, prompt rendering, or the Codex and Copilot paths.
- **Host-slot custody.** frond-ear holds no host-slot entries, and OC-0 is an OpenClaw plugin API that frond-ear cannot call. The binding-side rejoin settlement planned on frond-ear#24 (🍃's 10-02 summary) therefore needs an OpenClaw binding, or a different seam on the Claude Code side (§16.5).
- **Taint.** None is implemented. frond-ear#24's design-vs-main reconciliation ([comment](https://github.com/karmaterminal/frond-ear/issues/24#issuecomment-6009170310)) filed the design's "banner / taint" row as shipped; that comment is now corrected. The banner shipped in frond-ear#28; §14.12 taint did not.
- **A live run.** The mixed-host proof has not run (frond-ear#24, items 2 and 3 of 🌻's pickup, with 🍃).

Reuse its design, not its code: frond-ear has no licence yet (`package.json` says `UNLICENSED` at `014d96f`; frond-ear#35 is open).

---

## 4. Blocked on the live proof, and reviewable from source now

**Reviewable from source now, with no seat:**
- this board and its citations;
- OC-0's design, pull request, unit tests, rendering corpus and flood proof, all in CI;
- OC-1a's code and its tests against fakes and a loopback daemon;
- the amendment texts that questions 4a and 4b, and the §14.18.7 store wording, would need.

**Before P1 runs anywhere but a test host:** §14.18.2's single-host gate (framing, backpressure, supervision, restart, teardown), for each binding. It needs no mixed host.

**Blocked on the live mixed-host proof of §14.18.2 (silas and ronan):**
- P1 on any host with more than one binding (§14.18.2, *Proof gate*), OpenClaw's and frond-ear's alike, which includes silas and ronan;
- frond-ear's canticle on silas and ronan (§23.2 question 23);
- #88's publication on ClawHub (`plugins/binary-canticle/README.md`, "Publishing to ClawHub", item 4: cases 4 and 6).

**Also blocked on OC-0:** the host-slot steps of cases (5)(d′), (6) and (7) as written, and OC-1c.

**Blocked on decisions, not proofs:**
- §23.2 question 22: ambient landing in Discord-bound sessions, and reads there too if 4a holds;
- question 24: OC-1b (4c);
- question 28: before any P1 proof;
- question 27: the P3 wake, outside this review.

---

## 5. Refusals kept

- Heard broadcast is untrusted data. It is not an instruction, not an authority source and not a trust input (§14.12, §14.13, I-6, I-11). The banner says so, and taint enforces it (§14.12).
- No turn, wake, scheduled turn or sub-agent run comes from heard content (D1, D25). OC-0 carries no wake (D26).
- No re-sing of heard content (I-6), and no publish from any receive path.
- Heard content never lands as a system event, a channel message or prompt-hook text (§16.2; rows 11, 13 and 17).
- No second owner of the UDP port on a host that runs a daemon (D35, §14.18.2).
- At most two canticle entries per session (§14.14).
- Kept from the 2026-05-05 board's guardrails: a raw receipt is not interpreted atmosphere; a threshold shift is not a command; adapters never write directly into session-facing atmosphere; bridges never invent a second receptor.
- This review touched no real key, manifest, `stations.toml`, seat configuration or fleet arming. It turned nothing on and ran nothing against a seat. Multicast stays off until `canticle doctor` exists and passes (§11.2).

---

## 6. What moved since the freeze (`6e6458a` → `9e56928`)

| Topic | RFC-0001, at OpenClaw `6e6458a` | At `9e56928` | Effect on a rule |
|---|---|---|---|
| A full system-event queue | drops the oldest event (§16.1; `src/infra/system-events.ts:183-185` at `6e6458a`) | refuses: it logs `SystemEventQueueFullError` and returns null, and throws only for callers that asked for a receipt (`oc/src/infra/system-events.ts:45-52`, `:183-190`, `:215-223`) | None. Still in memory, still rendered as `System:` lines, still refused (§16.2). §14.14's reason changes from broadcast traffic evicting other producers' events to broadcast traffic shutting them out. |
| Keyed and blob stores | bundled or trusted only (§14.18.7; `src/plugins/registry-runtime.ts:202-219`, `:251`, `:255`, `:262` at `6e6458a`) | open to every loaded plugin (`oc/src/plugins/registry-runtime.ts:227-243`; `oc/docs/plugins/sdk-runtime/state-and-system.md:213`) | §14.18.7 still says a binding "MUST NOT depend on" them. Keeping binding state there needs an amendment naming `9e56928` (D29); until then, the binding's own state directory. Trusted hook dispatch is still trusted-only (`oc/src/plugins/registry-runtime.ts:412-425`). |
| `requestHeartbeatNow` | a deprecated alias with `removeAfter` 2026-10-01 (§16.1, §16.2) | still present (`oc/src/plugins/runtime/runtime-system.ts:19-28`, `:33`; `oc/docs/plugins/sdk-runtime/state-and-system.md:62`, `:70`) | None: no canticle path uses it. |
| Plugin reads of other sessions' system events | `plugin-sdk/infra-runtime` exported drain and peek for any session (`report §1`); `plugin-sdk/system-event-runtime` exported only enqueue and peek | `infra-runtime` is gone, and `system-event-runtime` now exports drain, consume and peek (`oc/src/plugin-sdk/system-event-runtime.ts:1-14`) | None for P1: nothing heard lands as a system event. The scoping item of `report §7` OC-3 now applies to `system-event-runtime`. |

Moved, with the same behaviour. A diff of `host-hook-state.ts`, `attempt-prompt-helpers.ts` and `attempt-llm-boundary.ts` between the two commits shows refactors, not behaviour changes, on the paths below.

| RFC-0001 cites (at `6e6458a`) | The same code at `9e56928` |
|---|---|
| `src/plugins/plugin-api.types.ts:107-111` (`enqueueNextTurnInjection`) | `:119-123`; the flat alias at `:395-397` is deprecated |
| `src/plugins/host-hook-state.ts:27-29`, `:85-144`, `:170-182`, `:196` | `:28-30`, `:67-132`, `:158-181`, `:184` |
| `src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:342-350` | `:388-396` |
| `src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:85-95` | `:94-109` |
| `src/plugins/registry-registrars-tools-hooks.ts:52-62`, `:399-407` | `:53-63`, `:401-416` |
| `src/plugin-sdk/security-runtime.ts:28-32` | `:34-38` |
| `src/plugins/plugin-api.types.ts:213`, `:273`; `src/plugins/plugin-registration.types.ts:424-430` | `:225-228`, `:292-296` (the second now also takes the version 2 service); `:419-426` |
| `src/plugins/tool-types.ts:31-32` | `:32-33` |
| `src/gateway/server/hooks.ts:245-272`; `src/gateway/hooks.ts:262-264` | `:263-291`; `:257-259` |
| `src/auto-reply/reply/session-system-events.ts:121-122` | `:133-135` |
| `src/auto-reply/reply/get-reply-directives.ts:319-323` | `:312-316` |
| `src/config/io.load.ts:118`; `src/config/zod-schema.root-support.ts:135-186` | `:114`; `:136-187` |
| `src/plugins/config-activation-shared.ts:226-232` | `:157-166` |
| `src/config/plugin-auto-enable.shared.ts:108-121`, `:455-473` | `:87-100`, `:414-432`, with `src/config/plugin-auto-enable.materialize.ts:215-231` |
| `src/config/validation-plugin-config.ts:345-395` | `:379-401` (that an invalid block refuses Gateway boot was not re-traced) |
| `src/infra/session-delivery-queue-storage.ts:153` | `:151` |
| `src/infra/system-events.ts:25-37` (`SystemEvent`) | `:26-40` |

---

## 7. Trackers

| Tracker | State | What this board does for it |
|---|---|---|
| #25 (this workboard) | open | Its deliverable: the board at exact refs. |
| #21, v0.2 integration tracker | open | Its "OpenClaw surfaces" row can point here. |
| #5, gateway ingestion | open, no owner | §1.2 answers it for OpenClaw at `9e56928`. |
| frond-ear#24, the canticle receptor | open; the live proof is with 🍃 | §3 and §4. The run card's source half is [here](https://github.com/karmaterminal/frond-ear/issues/24#issuecomment-5967000742). |
| #88, distribution and ClawHub | open until figs publishes | Its gate item 4 (cases 4 and 6) depends on question 4b and OC-0. |
| openclaw#1418, continuation presentation | draft, review only | Not a canticle seam (row 23). |
| openclaw#53 and #279, ambient attunement | open, pre-RFC | Lineage of the idea; not an implementation queue. |
| An OC-0 or OC-1 issue or PR in the fork | **none** | §8 proposes OC-0. OC-1a needs an owner and a home first (§10). |

---

## 8. Proposed next issue: OC-0 in karmaterminal/openclaw

Proposed here, not filed. The princes decide whether to file it and who owns it.

> **OC-0: extend next-turn injection with deadlines, supersede and withdraw, settled state and host-rendered provenance**
>
> **Why.** binary-canticle's OpenClaw binding needs one generic core seam before it can land anything in a session (RFC-0001 §16.4, D26). Nothing in the seam knows about canticle.
>
> **Scope.** One additive change to `api.session.workflow.enqueueNextTurnInjection`. An entry that uses none of the new fields behaves as today.
> 1. An absolute deadline and a not-before time, checked at enqueue and at drain, never extended.
> 2. Supersede by key; withdraw; a conditional supersede that names the entry it expects to replace; a settled-state query by idempotency key; a metadata-only settlement notice. Enqueue, supersede, withdraw and drain are serialized per session and plugin, and each is durable before it returns.
> 3. Settled tombstones, kept until the later of the deadline and an optional outcome retention, plus skew. They survive restart, reset and disable, and delete clears them. A full table refuses; it never evicts.
> 4. Entries that carry a deadline are kept at a drain where their plugin is not loaded, or not allowed prompt injection.
> 5. Per-plugin drain caps for entries and bytes, set in core configuration.
> 6. An entry that declares provenance renders as external data, under a host-authored banner outside the wrapper.
> 7. Every cap refuses with a reason. Enqueue is refused for an agent whose harness does not drain (Codex and Copilot today).
> 8. No delivery context, heartbeat target, wake source or intent.
>
> `reports/2026-10-01-openclaw-interface-demands.md` §4.2-§4.4 in binary-canticle drafts items 1 and 3-8, and item 2's supersede and withdraw. Item 2's conditional supersede, settled-state query and settlement notice, and item 3's outcome retention, came later (RFC-0001 §16.4, §14.18.5).
>
> **Files at `9e56928`.** `src/plugins/host-hook-turn-types.ts` (`:7-35`), `src/plugins/host-hook-state.ts` (`:67-193`), `src/plugins/registry-api.ts` (`:140-168`), `src/plugins/plugin-api.types.ts` (`:119-147`), `src/plugins/host-hook-cleanup.ts` (`:176-192`) and `src/config/sessions/plugin-host-cleanup.ts` (`:92-113`), `src/config/sessions/types.ts` (`:295`), `src/config/zod-schema.root-support.ts` (`:136-187`), `src/plugins/host-hooks.ts` (`:320-341`) and `src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts` (`:70-91`), `src/security/external-content.ts` (`:47-55`, `:323`) and `src/plugin-sdk/security-runtime.ts` (`:34-38`), `src/plugin-sdk/session-store-runtime-internal.ts` (`:32-40`), and `docs/plugins/hooks/prompt-and-session.md` (`:316-349`).
>
> **To argue in the PR.** Item 4 reverses a stated design ("Inactive plugin records are stale owner state and are discarded with expired records", `src/plugins/host-hook-state.ts:182-183`), and only for entries that carry a deadline. Also, the plugin projection of a session entry (`src/plugin-sdk/session-store-runtime-internal.ts:32-40`) hands `pluginNextTurnInjections` to any plugin, so every plugin's pending entries can be read today, and probably rewritten. Item 2's query covers what a plugin needs to know about its own entries; the PR should say whether the projection keeps the field.
>
> **Out of scope.** Any wake (RFC-0001 §23.2 question 27); canticle logic of any kind; the binding plugin (OC-1); draining on Codex or Copilot (refused instead); the session-delivery queue.
>
> **Acceptance.** The OC-0 gate of the report's §7, extended to the later items. The unit tests cover:
> - expiry and not-before, at enqueue and at drain;
> - duplicates, both pending and settled;
> - withdraw and supersede, before and after a drain;
> - a conditional supersede refused once its target has settled;
> - refusal at every cap, with a reason, and no eviction;
> - drain caps;
> - restart persistence;
> - a plugin that is not loaded at the first drain after a restart, and during a reload: its entries are kept;
> - tombstones kept across reset and disable, and cleared by delete;
> - an unknown session refused, and an agent on Codex or Copilot refused;
> - a retry of one run rendering its drained entries without a second drain.
>
> Also the adversarial rendering corpus on every prompt path, the RFC's §14.14 flood proof, and the existing injection tests unchanged.
>
> **Receipt.** The merged PR at a literal SHA and its test output. binary-canticle then re-pins RFC-0001 §16.1-§16.4 to that SHA (D29).
>
> **Owner.** Unassigned.

---

## 9. Candidate implementation per plane and scope

What OpenClaw needs at each scope. RFC sections are the authority. This table only places the OpenClaw pieces.

| Plane | One host | Trusted LAN: a mixed host such as silas or ronan | Several subnets | Air-gapped or intermittent |
|---|---|---|---|---|
| Binary (signal) | the daemon on loopback; bindings as peers (D35) | the same daemon, unicast; multicast only after `canticle doctor` passes (§11.2, not built) | relays and routed adapters (§11, §12): RFC-only | file replay (§18): RFC-only |
| Ledger | the binding's own durable state: frame keys, tombstones, intents (§14.18.5); no promotion of heard content | the same, per host | per-host ledgers; promotion only by an untainted principal or a human (§6.4) | the same, imported in batches |
| Control | OC-0's two host slots per session; a read tool after 4a and 4c; no wake | the same | not canticle | not canticle |
| Membership | the unsigned manifest plus presence records | the same; the signed manifest (§10.3; BC-5 of `report §7`) | the manifest, carried across relays | an explicit stale-presence model |
| Bridge | OC-1 and frond-ear as peers of the daemon | the same, proved by §14.18.2's mixed-host cases | bridge nodes translate transport and crossing policy, never judgments (§3.1) | a signed bundle bridge |

---

## 10. Immediate build order and next work items

- [ ] **Princes:** answer questions 4a (does a read taint?), 4b (the scope of case (6)) and 4c (does question 24 hold a P1 read?). Settle question 28 before any P1 proof.
- [ ] **Princes:** file the OC-0 issue of §8 in karmaterminal/openclaw, or a better one, and name an owner.
- [ ] **Princes:** name a home for OC-1 (an extension in the fork, or an external package) and an owner for OC-1a.
- [ ] **binary-canticle:** if wanted, draft the amendments that follow from the answers: §14.12's trigger (4a), §14.18.2 case (6) (4b), and §14.18.7's store wording at `9e56928` (§6).
- [ ] **frond-ear#24:** the live mixed-host run (🍃), unchanged by this board.
- [ ] **#25 and #21:** once this board merges, #25's deliverable is met, and #21's "OpenClaw surfaces" row can point here.
