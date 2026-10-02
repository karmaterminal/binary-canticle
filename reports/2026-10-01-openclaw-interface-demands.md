# OpenClaw ↔ binary-canticle interface demands: assessment

*2026-10-01. A response to the princes' brief "OpenClaw ↔ binary-canticle interface: implementation demands", grounded at the same commits as the brief: OpenClaw `6e6458a98ff3894117b0449a64b6dbfd1ca348d1` and binary-canticle `234464a0cb84a568c1c562f2f6ffee550d7bdb5c`.*

**Citation prefixes**
- `oc/` is karmaterminal/openclaw at `6e6458a`.
- `bc/` is this repository at `234464a`; `bc/.../` abbreviates `bc/prototype/canticle-station/`.
- `rfc:` is `rfc/0001-binary-canticle.md` at `234464a`.
- `rfc@c9fe9cd:` is the same file at `c9fe9cdc0a401c9875aa1bf9dea46d5c52bcc041` ([permalink](https://github.com/karmaterminal/binary-canticle/blob/c9fe9cdc0a401c9875aa1bf9dea46d5c52bcc041/rfc/0001-binary-canticle.md)). That is the head of PR #62, the listener fix for issue #60, when this report was written. It changes RFC §7.4, §7.7, §7.8, §10.9, §14.6.3 and adds §23.2 question 21. Citations are pinned to that commit, so they do not move if #62 changes; if it does, re-pin before using this report as a freeze packet.

**Freeze point.** The brief and this assessment read `234464a`. PR #62 at `c9fe9cd` (the fix for issue #60) changes listener internals and the RFC sections above, but not the listener's output format; it adds the `over_quota` and `pluck_mismatch` admission results to §10.9 and §23.2 question 21 ("Class changes under one `state_key`"). Q6 asks which of the two to freeze against.

**How claims are marked**
- "Read" means seen in source.
- "Probe" means a scratch script run during this assessment and re-run by an independent verifier (not committed).
- Inferences are marked as inferred.

---

## 1. Bottom line

- **Already true**
  - A disabled OpenClaw plugin's runtime is never imported, so it registers no tools, hooks or services (oc/src/plugins/loader-registration-plan.ts:45-53; oc/src/plugins/loader-runtime-candidate.ts:225-230). Three caveats:
    - `openclaw doctor` imports a disabled plugin's setup entry (oc/src/plugins/setup-registry.ts:174-199).
    - An installed non-bundled plugin with **no** `plugins.entries` entry defaults to enabled (oc/src/plugins/config-activation-shared.ts:226-236).
    - A config block for a plugin that declares `contracts.tools` and omits `enabled` auto-enables that plugin (oc/src/config/plugin-auto-enable.shared.ts:108-121,455-473, verified by probe). "Byte-inert" therefore needs `enabled:false` written explicitly.
  - The canticle station already owns key load, sign-once, seq, a persisted monotone epoch, the carousel, PLUCK, beacons, goodbye and a 0600 control socket (bc/prototype/canticle-station/canticle/runner.py:96-165; station.py:99-134,236-316,418-436).
  - The listener already owns strict CBOR, Ed25519, class/scope/hop grants, TTL, dedup, equivocation evidence and persisted replay state (bc/.../listener.py:183-282,384-430).
  - The RFC already agrees with demands 1.2 and 1.3, with ambient emitters and with live-only late join (rfc:237, rfc:2047, rfc:2165-2181, rfc:542-554).

- **P0 seam: PARTIAL, which in practice means no.** The public SDK has four relevant pieces, and none meets the demand on its own.
  - **`api.runtime.system.enqueueSystemEvent`**
    - It is in memory only ("We intentionally avoid persistence", oc/src/infra/system-events.ts:1-3).
    - It keeps 20 events per session and silently drops the oldest (:39, :182-185).
    - It carries text and contextKey only, with no provenance and no expiry (:25-37).
    - Any plugin can call it; there is no trust gate (oc/src/plugins/registry-runtime.ts:320-339).
  - **`api.session.workflow.enqueueNextTurnInjection`** is the closest fit. It is durable in the session store and has ttlMs and an idempotencyKey. It refuses when full (32 entries per plugin per session, up to 32 KB each) and refuses unknown sessions (oc/src/plugins/host-hook-state.ts:27-29,85-144). Its gaps:
    - It has no host-rendered provenance. The text is joined raw into the active user prompt (oc/src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:342-350).
    - It has no wake and no withdraw.
    - The idempotency key covers pending entries only (host-hook-state.ts:126-133).
    - A drain consumes the entry.
    - A drain discards the entries of any plugin that is not `loaded` at that moment, then deletes the whole map (:170-182,196).
    - One drain can land 32 × 32 KB, far above the RFC dose of 5 items and 1.5 KB per turn (rfc:1727, 2003).
    - It is not drained on Codex or Copilot (oc/docs/plugins/hooks/prompt-and-session.md:68-71,316-330).
  - **`requestHeartbeat`** provides a wake, with these limits:
    - The caller chooses source and intent.
    - `manual` skips only the scheduler's deferral guards: not-due, min-spacing and flood (oc/src/infra/heartbeat-cooldown.ts:31-34). The enabled, interval, active-hours and busy checks still apply.
    - There is no plugin source value (oc/src/infra/heartbeat-wake-contracts.ts:8-22).
    - Budgets are per agent only.
    - Output goes to the owner DM by default (oc/src/infra/outbound/targets.ts:205-269).
    - The `requestHeartbeatNow` alias has `removeAfter` 2026-10-01, which is today (oc/docs/plugins/sdk-runtime/state-and-system.md:56). RFC Tier A uses that alias.
  - **The durable SQLite session-delivery queue** is core-only (oc/src/infra/session-delivery-queue-storage.ts:153). Its systemEvent rows always become in-memory events plus an immediate wake (oc/src/gateway/server-restart-sentinel.ts:106-135).
  - **So a small generic core change has to land first (section 4).**

- **Biggest gaps in binary-canticle**
  - **No receptor record contract.** `canticle listen` prints unversioned JSON lines in six event kinds. There is no disposition, stream_id, frame digest, lens, principal or local expiry (bc/.../listener.py:34-48,286-306).
  - **No readiness receipt and no `--version`** (bc/.../__main__.py:105-108,201; runner.py:139). There is also no `doctor` subcommand (__main__.py:267-363).
  - **Silent outcomes.** These produce no record at all:
    - untuned streams, unnamed streams and items held in warm-up (listener.py:276,279);
    - held items dropped in `_release_held` (listener.py:327);
    - a PLUCK resurfaced after a restart (:239-240);
    - older or repeated beacons (:167-168).
  - **Restart gaps.** After a restart, PLUCK, supersede and expiry for items the new process has not re-heard produce no record (listener.py:247-250,271-274; probe). First-heard time is not persisted (listener.py:104,280).
  - **Lineage stamping (RFC §15.4 item 5) is impossible.** The socket accepts no hop, derived_from, root or wake_derived (runner.py:62-72). `Station.sing` takes hop and flags but not derived_from or root (station.py:236-240).
  - **Hardlinked keys.** The station lease and epoch file are keyed by path, so two stations can share a key through a hardlink (bc/.../__main__.py:87-93). A probe showed equivocation only when both stations start in the same wall-clock second. Otherwise the older station's frames are rejected as `epoch-regression`.
  - **Crashes instead of degraded states.** A corrupt state file raises JSONDecodeError and an unknown manifest class raises KeyError (observed in a probe run).
  - **Manifest.** It is unsigned and never reloaded (bc/.../manifest.py:3-6,80-96), and it has no principal (manifest.py:26-32).
  - **Beacons.** They have no `trail_seq`, and the A1 layout is misparsed (bc/.../wire.py:91-106,309-313; rfc:809-817).
  - **Equivocation does not quarantine the key.**
  - **Mis-attribution.** Rejected, unverified datagrams are attributed to manifest station names (listener.py:134-141).

- **Biggest gaps in OpenClaw**
  - **Config shape.** `plugins.entries.<id>` is a strict object. Every canticle key must go under `.config`, and the file format is JSON5, not YAML (oc/src/config/zod-schema.root-support.ts:135-186; oc/src/config/io.load.ts:118).
  - **Boot refusal.** A schema-invalid config block refuses Gateway boot even when `enabled:false` (oc/src/config/validation-plugin-config.ts:345-395).
  - **Supervision.** There is no supervisor for child processes, and service health is binary (oc/src/plugins/service-health.ts:15-45).
  - **Tracing.** `canticle.*` spans cannot reach diagnostics-otel without a core change (oc/src/infra/diagnostic-events.ts:808).
  - **Mention gating.** requireMention never gates heartbeat or wake turns. It is read only to choose the activation prompt label (oc/src/auto-reply/reply/get-reply-directives.ts:319-323; oc/src/infra/heartbeat-runner-run.ts:77-115).
  - **Heartbeat outbound** (affects demand 6):
    - Heartbeat turns set `suppressOutboundHooks: true` (heartbeat-runner-run.ts:111).
    - Identical heartbeat text within 24 h is suppressed (oc/src/infra/heartbeat-dispatch.ts:429-433).
    - Discord has no `heartbeat.checkReady`.
  - **Durable host state.** `openKeyedStore` is limited to bundled or trusted plugins (oc/src/plugins/registry-runtime.ts:202-220,255).
  - **Cross-session system events.** The deprecated but typed-public `plugin-sdk/infra-runtime` lets any plugin drain or peek any session's system-event queue (oc/src/plugin-sdk/infra-runtime.ts:397-410, verified by probe).
  - **Continuation guard.** The "continuation chain guard" named in 5.5 does not exist on main.

- **Conflicts with RFC-0001**
  - **Wake.**
    - Wake "for any allowed class" contradicts decided D1 (alarm only) and the 11-item conjunction in §14.10 (rfc:1909, 1925-1937).
    - No agent may produce an alarm in v1, and the prototype CLI cannot produce one. P3 therefore has no wake source (rfc:2058-2059, rfc:1010-1012; bc/.../runner.py:30).
  - **Naming.**
    - The demands use `quarantine_action`, which §14.3 retired (rfc:1649).
    - The delivery-mode names collide with RFC class and disposition names.
    - The banner marker differs: `[binary-canticle]` vs `[canticle:heard]`.
  - **Taint.** The demands' "taint" means wrapping. In the RFC it means tool denial, including "outbound messages to off-host targets" (rfc:1962), which would block Discord replies.
  - **Landing.**
    - Newest-drop overflow contradicts latest-value for keyed items (rfc:522).
    - The demands key idempotency per subscription; the RFC keys it per session (rfc:2157).
    - The demands deliver per-frame durable rows; the RFC lands a 2-slot digest (rfc:2000).
    - The demands omit A11 desynchronised landing and the post-drain withdrawal note (rfc:2018-2021, 2004).
  - **Publishing and transport.**
    - Publishing beyond the host defaults to disabled in the RFC (rfc:2150, 2238). In the demands, `mode:"publish"` enables it implicitly.
    - The RFC uses multicast only after `canticle doctor` passes (rfc:500, 1110, 1153). The prototype has no doctor.
    - Self-broadcast is filtered by default in the RFC (rfc:1683). The demands have no `include_self`.
  - **Records, banner and UI.**
    - Missing provenance, including principal, must read "unavailable" (rfc:1976-1979, 1992).
    - The demands want per-frame "why rejected" records. §10.9 sends unknown_key and bad_signature to the "debug ring only; never a receipt" (rfc:1075-1076).
    - The demands allow an authenticated Control UI; §18.9 puts that out of scope for v1 (rfc:2484).
  - **#62.** §23.2 question 21 (class changes under one state_key) affects keyed replacement (rfc@c9fe9cd §23.2).

- **Conflicts inside the demands**
  - 5.2 says "non-surface cannot reach model context", but 10 offers a model-facing `canticle_recent`.
  - The Tempo trace gate (12.10) needs a core diagnostics change, while 2.1 prefers "outside core".
  - 3 makes `group` configurable, but canticle hard-codes it (bc/.../runner.py:26).
  - 1.1 puts judgments in the listener, which has none today.

- **Recommendation.** P0 has two parts:
  1. A bc RFC amendment that freezes the record schema, the taxonomy and the subscription shape, plus a listener record emitter.
  2. One generic OpenClaw core PR that extends next-turn injection with:
     - absolute expiry and `notBefore`;
     - settled tombstones that survive reset;
     - withdraw/supersede, reporting post-drain state;
     - per-plugin drain caps;
     - retention of entries whose plugin is not loaded at drain;
     - host-rendered provenance.

     It adds no wake.

  P1 `ringbuffer_only` can start now, behind the `allowUnsigned` dangerous flag until BC-5. The ambient mode waits for the core PR. Wake (P3) is blocked on a D1 decision, an operator alarm path and a corrected wake-intent design (section 4.5).

---

## 2. Demand matrix

| § | Where it lands | Status today | Evidence | Note |
|---|---|---|---|---|
| 0 | RFC + plugin + core seam | partial | rfc:2935; oc/src/infra/system-events.ts:1-3 | The demand is the OpenClaw part of RFC S3. S3 also covers Claude Code, A9, A11 and blind enrichment. |
| 1.1 | bc + plugin + core | partial | bc/.../runner.py:96-165; bc/.../listener.py:183-282; oc/src/infra/session-delivery-queue-storage.ts:153; oc/src/plugins/registry-runtime.ts:320-339,656-671 | Ownership matches the station and listener code. The listener emits no judgment. The session-delivery queue is not plugin-reachable. Core cannot stop a plugin from calling `enqueueSystemEvent` or `subagent.run`. |
| 1.2 | RFC + core + plugin | partial | rfc:237, rfc:1645; oc/src/infra/system-events.ts:25-37; oc/src/auto-reply/reply/session-system-events.ts:120-126 | The RFC states this. OpenClaw's boundary is `text: string` only, with a "System:" prefix and no typed provenance. |
| 1.3 | RFC + bc + plugin | partial (RFC yes; stamping impossible) | rfc:2047, rfc:2100, rfc:2140; bc/.../runner.py:62-72; bc/.../station.py:236-240 | §15.4 item 5 requires the tool to stamp hop, derived_from, root and wake_derived. The socket accepts none of them, and `sing` lacks derived_from and root. Without stamping there is no hop or causality budget and no echo-loop lineage (5.5). BC-3 adds tool-set socket fields that the agent never sets. |
| 2.1 | plugin + core | partial | oc/docs/plugins/manifest.md:20; oc/src/plugins/plugin-api.types.ts:213-273; oc/src/flows/bundled-health-checks.ts:105-111 | The native plugin format fits. Doctor checks are bundled-only. The P0 seam is needed (section 4). |
| 2.2 | plugin + bc | partial | oc/src/plugins/services.ts:665-670,700-725; oc/src/plugin-sdk/process-runtime.ts:1-40; bc/.../__main__.py:87-93,105-108,201; bc/.../runner.py:131-139 | No readiness receipt and no version. The station's JSON line is printed before bind. The lease is per path. A second station unlinks the first station's socket. Each start is awaited with no deadline at boot. |
| 2.3 | plugin + bc | partial | bc/.../runner.py:148-165; bc/.../station.py:99-134; bc/.../listener.py:219-229,384-430; bc/.../__main__.py:93; oc/src/plugins/services.ts:163-164; oc/src/plugin-sdk/runtime-env.ts:20-21 | Goodbye, monotone epoch and persisted state exist. Core never restarts services. The listener re-emits pre-restart items unmarked. Inferred: a sing acked `ok:true` in the up-to-500 ms stop window may never be sent, because the server closes after goodbye. The plugin must therefore stop publishing before sending TERM. The epoch is persisted before bind, so a failed start uses up an epoch. |
| 3 | plugin + core + bc + RFC | conflicts | oc/src/config/zod-schema.root-support.ts:135-186; oc/src/config/io.load.ts:118; oc/src/config/validation-plugin-config.ts:345-395; oc/src/plugins/config-activation-shared.ts:226-236; oc/src/config/plugin-auto-enable.shared.ts:108-121; bc/.../runner.py:26,107-110; bc/.../__main__.py:166-167,286,322-333; rfc:1683, rfc:1110, rfc:2150 | Keys must go under `.config` in JSON5. A bad block blocks boot. A missing entry, or a block with no `enabled`, enables the plugin. Group and binding are fixed. Unicast gets no IP_TTL. The listener needs its own bind and multicast settings. There is no `include_self`. Cross-host publish and multicast are gated in the RFC (C17, C18). |
| 4 | plugin + bc + RFC | partial | bc/.../runner.py:27-32,54-80,119-123; bc/.../station.py:50-65,267,270-275,295-316; rfc:2051-2094, rfc:2139-2145, rfc:2151 | The receipt lacks station, stream_id, class, scope and trace. An oversize body uses up a seq. The hush reason is unchecked. There is no request id. Alarm, regulatory and control are barred from model tools in v1. Missing from the plan: §15.4 item 4 (tainted fleet/public refusal), item 6 (secret scan, "content-policy checked"), item 7 (opaque content at fleet/public), item 9 (5 per turn, 60 per hour), item 10 (`training_eligible=0`), and §15.5 leaf sub-agents getting no publish tools. |
| 5.1 | bc + RFC | missing | bc/.../listener.py:34-48,286-306; bc/.../__main__.py:170-174; bc/.../wire.py:72; rfc:1658, rfc:1075-1076, rfc:2918 | Output is six unversioned kinds. Evidence appears only with `--evidence`, and `t_ms` only with `--timestamps`. `lens` is never emitted. There is no principal. First-heard time is not truthful after a restart. The RFC defines no serialization, and it denies receipts for unverified frames (C22). |
| 5.2 | bc + RFC | conflicts | rfc:1649, rfc:1075-1076; bc/.../listener.py:167-168,239-240,258,276,279,327 | `quarantine_action` was retired. The prototype has no disposition field. Silent outcomes: untuned and unnamed streams, warm-up holds, held-item drops, resurfaced PLUCKs and stale beacons. "Why rejected" for unverified frames conflicts with §10.9 (C22). |
| 5.3 | core + plugin + RFC | partial | oc/src/security/external-content.ts:113-154,323-354; rfc:1971-1996, rfc:2004 | `wrapExternalContent` is public and uses a random marker id. Probe: 13 look-alike variants pass through it. There is no host-authored banner, and the marker differs from the RFC's. Gap state cannot be produced without `trail_seq`. Principal reads "unavailable" (C21). Withdrawal after drain needs a note (section 4.3). |
| 5.4 | core seam + plugin | missing | oc/src/infra/system-events.ts:1-3,39; oc/src/plugins/host-hook-state.ts:27-29,85-205; oc/src/gateway/server-restart-sentinel.ts:106-135; rfc:2018-2021 | No durable ambient delivery with provenance exists. Next-turn injection is the closest fit, but it loses entries at drain when the plugin is not loaded, has no dose cap and no A11 `notBefore`. The mode names collide with RFC §14.9. |
| 5.5 | core + plugin + RFC | conflicts | rfc:1909,1925-1939; oc/src/infra/heartbeat-cooldown.ts:4-6,31-71; oc/src/infra/heartbeat-wake-policy.ts:62-90; oc/src/plugins/runtime/runtime-system.ts:18-47 | D1 allows alarm only. The caller declares source and intent. Guards are per agent. No continuation guard exists on main. Lineage stamping is impossible today (row 1.3). The plan never addresses "no automatic publish caused solely by receiving". Fix: plugin code never publishes from a receive path, and model publishes from tainted sessions are refused at fleet/public scope (§15.4 item 4, rfc:2139). |
| 6 | core + plugin + RFC | conflicts | oc/extensions/discord/src/monitor/message-handler.preflight.ts:582-593,760-780; oc/src/auto-reply/reply/get-reply-directives.ts:319-323; oc/src/infra/heartbeat-runner-run.ts:77-115,111; oc/src/infra/heartbeat-dispatch.ts:379,429-433,469; oc/src/infra/outbound/targets.ts:205-269; oc/src/infra/heartbeat-wake-contracts.ts:24-28; rfc:1962, rfc:2243 | requireMention never gates heartbeat turns. The default target is the owner. The wake override accepts `to` and `accountId`. Heartbeat turns suppress outbound hooks, and identical text within 24 h is suppressed, so "subject to normal policy" does not hold. Discord has no `checkReady`, so an outage is not detected. RFC taint denies off-host outbound. |
| 7 | bc + plugin + core | partial | bc/.../manifest.py:3-6,80-96; bc/.../listener.py:134-141; bc/.../runner.py:46-51,131-133; bc/.../__main__.py:34-35; oc/src/plugin-sdk/infra-runtime.ts:397-410; rfc:981 | Unsigned manifest with no reload. The peer-UID check fails open off Linux. The socket path is unlinked unconditionally. The key file is read with no mode or symlink check. Unverified datagrams are attributed to stations. Any plugin can drain or peek another session's system events through the deprecated SDK export. "No implied confidentiality": bodies are signed, not encrypted, and travel as cleartext on the LAN. Plugin docs, status and tool descriptions must say so. |
| 8 | bc + core + plugin | partial | bc/.../listener.py:208-282,362-368; bc/.../wire.py:91-106,309-313; rfc:438-447, rfc:522; oc/src/plugins/host-hook-state.ts:126-133 | Identity, dedup, equivocation and absolute expiry exist. Retractions cover in-memory items only. No `trail_seq`. Host idempotency covers pending entries only. Crash modes (corrupt state: JSONDecodeError; unknown class: KeyError) and clock skew have no degraded state. |
| 9 | plugin + core | partial | oc/src/infra/diagnostic-events.ts:808; oc/extensions/diagnostics-otel/src/service-events.ts:38-153; oc/src/plugin-sdk/diagnostic-runtime.ts:5-18,44-56; oc/docs/plugins/sdk-runtime/state-and-system.md:56; bc/.../station.py:440-451 | The station `status` op exists. The listener has no health output. `canticle.*` spans need a core change or the plugin's own exporter. Traceparent helpers are public. The agent's traceparent can be kept locally but cannot continue across hosts (section 5.3). `requestHeartbeatNow` is due for removal today. |
| 10 | plugin + RFC | conflicts | oc/src/plugins/tool-types.ts:94-105; oc/docs/plugins/manifest/providers.md:73-87; rfc:2082-2089, rfc:2484 | Tool gating by mode works. The RFC's `canticle_listen view:"raw"` and session-callable `canticle_tune` conflict with the demands. §18.9 limits the tuner to loopback in v1; the demands also allow "authenticated" (C23). |
| 11 | bc + plugin | partial | bc/.../tests/test_listener.py:219-245; bc/.../tests/test_udp_e2e.py:24-63; rfc:2779-2848 | 75 tests pass at 234464a (probe run with cryptography 50.0.1). No adversarial control-socket, path or hardlink tests, and no JSON depth-bomb test (11.3). The RFC adds blind enrichment, RT-112, A9 and A11. |
| 12 | process | missing | rfc:2779; bc/.../README.md:118-125 | Existing proofs are same-host only (netns). The Tempo gate depends on the section 9 seam. No OpenClaw slice covered the canary, arming, rollback or soak; OC-5 now does. |
| 13 | process + RFC | partial | rfc:1911-1923, rfc:2193, rfc:2935 | P0's generic seam replaces Tier B (§16.4). A9 and A11 are missing from P1 and P3. P4 had only a bc slice (BC-5); OC-5 is added. |
| 14 | all | missing | (rows above) | No criterion is met yet. "Byte-inert" needs the plugin to be inert when config is absent, and `enabled:false` written explicitly because of auto-enable. |

---

## 3. Conflicts and pushback

Rule for every item below: where the solution departs from RFC-0001, the RFC must be amended in the same slice (BC-1, section 7).

### 3.1 Demands vs RFC-0001

**C1. Which classes may wake (5.4, 5.5)**
- Demand: "wake requires explicit subscription allow, allowed class, …".
- RFC D1: "MAY escalate verified **alarm** frames to `silent-wake`" (rfc:1909). §14.10 item 3: "In v1 that is `alarm` only." (rfc:1929). D1 row: "silent-only until S3 implements and tests the whole conjunction" (rfc:2860).
- Recommendation: config validation hard-restricts `delivery:"wake"` to `classes:["alarm"]`. If the princes want non-alarm wakes, that reopens D1 on #54 and requires amending §14.10 item 3 and D1. **RFC amendment only if D1 is reopened.**

**C2. The §14.10 conjunction is missing from 5.5**
- The demand leaves out these items (rfc:1927-1937):
  - item 1: admission `verified`, the key not quarantined, the receiver not under MUTE;
  - item 2: the key holds the alarm capability;
  - item 6: host budget of 6 per hour plus the circuit breaker;
  - item 7: "canticle token budget (200 000 tokens per day)";
  - item 8: "`hop = 0`, and flag `wake_derived` is 0", which cannot be checked until lineage stamping exists (row 1.3);
  - item 9: age at first hearing ≤ 120 s, not superseded or plucked (rfc:1935);
  - item 10: "sandboxing is on for the agent and its bootstrap files are sealed";
  - item 11: "Proofreading has passed (§14.6.8)".
- It also leaves out "coalesceMs ≥ 5 000 ms" (rfc:1939).
- Item 10 can be checked today through `PluginRuntime.sandbox.resolveWorkspaceAuthority` (oc/src/plugins/runtime/types.ts:177-186, verified by probe). D16, the sandbox mandate behind it, is still only recommended, not decided (rfc:2875).
- Recommendation: 5.5 should cite §14.10 as the wake gate rather than restate a subset. No RFC change, unless D16 is decided.

**C3. No alarm producer exists for P3 (4, 5.5, 13)**
- Demand 4: these classes are "unavailable until typed-body and op-level auth exist".
- RFC:
  - "alarm, regulatory and control are not offered to LLM sessions" (rfc:2058-2059).
  - "An LLM-driven session MUST NOT hold a key with `quarantine`, `alarm` or `control`" (rfc:1010).
  - "in v1, `alarm` keys are operated by humans" (rfc:1012).
- Prototype: `canticle sing` goes through the socket, which refuses alarm (bc/.../runner.py:30, :57-61). Only the in-process library can sign an alarm (bc/.../tests/test_listener.py:196-202).
- Recommendations:
  - Change demand 4 to "never offered to model-facing tools in v1".
  - Add an operator-only typed `alarm-body` publish path (§14.7.6). It is signed with a human-held key that is separate from the plugin's station key.
  - Plugin start refuses publish mode when the station key's manifest grant includes alarm, quarantine or control (rfc:1010).
- RFC change: none to the rule. Specify the operator CLI path in §15.7.

**C4. Judgment taxonomy (5.2)**
- Demand: `surface | ringbuffer_only | drop | quarantine_action`.
- RFC §14.3: "`surface`, `ringbuffer_only`, `drop`, `quarantine_set`, `quarantine_strengthen`, `quarantine_rescind` … resolves `quarantine_action` vs `quarantine_flag` (C14)" (rfc:1649). Admission results (§10.9, rfc:1067-1083) are a separate axis.
- Recommendation: adopt §14.3 unchanged and carry admission as its own field (section 5). Fix the demand. No RFC change.

**C5. Delivery mode names (5.4)**
- Demand: `ambient | wake | ringbuffer_only`.
- RFC:
  - Landing modes: `silent` (default), `silent-wake` ("alarm class only") and `post-compaction` ("reserved") (rfc:1893-1897).
  - Tune postures: `silent`, `wake-on-alarm` and `off` (rfc:1681).
  - `ambient` is already a class name, and `ringbuffer_only` is already a disposition.
- Recommendation: keep the demand's config names for operators, and define the mapping in the RFC:
  - ambient → silent;
  - wake → silent-wake;
  - ringbuffer_only → off.
- Also reword "Wake is a privilege; sender flags only suggest" to "No sender wake. A sender can neither request nor force a wake." (rfc:1920).
- **Amend §14.9 to add the mapping.**

**C6. Banner marker (5.3)**
- Demand: `[binary-canticle]`.
- RFC:
  - `[canticle:heard] …` (rfc:1976).
  - "The `[canticle:` prefix gives drain accounting and log searches an anchor" (rfc:1993).
  - "MUST strip `[canticle:` prefixes and wrapper-marker look-alikes" (rfc:1994).
- Recommendation: keep `[canticle:heard]`, because the strip rule and accounting already depend on that prefix. If the princes insist on the demand's marker, **amend §14.13 and its strip rule**.

**C7. What "taint" means, and Discord (5.3, 6)**
- Demand: taint is wrapping; "Normal output routing decides whether woken session speaks."
- RFC: "A session that has drained any canticle item is **tainted** … the host MUST deny at least: … 4. outbound messages to off-host targets" (rfc:1957-1962). This applies to ambient landings too.
- Recommendation: the princes decide, and BC-1 amends §14.12 either way.
  - (a) Keep §14.12. P1 ambient may then target only sessions with no off-host channel route.
  - (b) Amend item 4 so that "the session's own bound reply route, under normal channel policy" does not count as off-host.
- What can be enforced today:
  - Partial enforcement is possible through `before_tool_call` block or requireApproval (oc/src/plugins/hook-before-tool-call-result.ts:13-34).
  - On Codex, `toolsAllow` narrowing is rejected (oc/extensions/codex/src/app-server/run-attempt-prompt.ts:294-298).
  - `before_tool_call` appears to be relayed on Codex through the native hook relay (oc/extensions/codex/src/app-server/native-hook-relay.test.ts, approval-bridge.test.ts). This is unverified.
- **RFC amendment needed** whichever option is chosen, because §16.2's "Tier A cannot deny arbitrary tools" (rfc:2243) is now partly out of date.

**C8. Mention gating (6)**
- RFC: "Internal delivery bypasses mention gating (`OC-RFC:1464`), so canticle's own admission gate is the only gate." (rfc:2243).
- Code agrees. Heartbeat turns set no WasMentioned and are never gated by mention. requireMention is read only to choose the activation prompt label (oc/src/infra/heartbeat-runner-run.ts:77-115; oc/src/auto-reply/reply/get-reply-directives.ts:319-323).
- This is a feasibility gap, not opposing rules. Demand 6's default needs a new gate in the P3 core wake seam (section 4.5). **Amend §16.2** to state the demand 6 default once it is adopted.

**C9. Overflow (3)**
- Demand: "drop_oldest forbidden for live safety state; default refuse/newest-drop".
- RFC: dedup, sticky-pluck and supersession marks "MUST NOT be evicted earlier under capacity pressure", and the receiver refuses with over-quota (rfc:444-445). That matches the demand.
- But for keyed items "the item with the greatest `(issued_at, epoch, seq)` is current" (rfc:522), and the alarm slot is "replaced in place" (rfc:2002). Newest-drop would keep a superseded value current.
- With #62 (at c9fe9cd), §23.2 question 21 adds a twist: an older item of a longer-lived class under the same state_key can outlive the mark and land as current. The recommended fix is "one class per `state_key` within an epoch", with receivers dropping class changes (rfc@c9fe9cd §23.2).
- Recommendation:
  - `refuse_newest` for unkeyed items and safety state.
  - `replace_keyed` (supersede in place) for state_key items.
  - `replace_keyed` treats a class change under one state_key as a drop with evidence, never as a replacement.
- No RFC change beyond resolving item 21. Fix the demand.

**C10. Idempotency key (8)**
- Demand: "frame identity + target subscription/session".
- RFC: `canticle:<key_id>:<epoch>:<stream_id>:<seq>:<sessionKey>` (rfc:2157, rfc:2253).
- If the subscription id enters the key, two overlapping subscriptions deliver twice into one session.
- Recommendation: use the RFC key with no subscription id, and record the subscription id as metadata only. `kind` is redundant, because a PLUCK has its own seq in the same tuple space (bc/.../wire.py:133-139). No RFC change.

**C11. Landing model (5.4, 12.4)**
- RFC: "at most two host queue slots per session", "rebuilt and replaced in place", ≤5 items and 1.5 KB per turn (rfc:2000-2003, rfc:1727).
- Demand: per-frame durable rows and "exactly one session-visible wrapped item".
- The RFC chose two slots because of OpenClaw's 20-event drop-oldest queue (rfc:2006). A seam with its own per-plugin cap (section 4) removes that reason. The seam has no aggregation hook, though, so the dose must be enforced as per-drain caps.
- Recommendation: per-frame rows, with the §14.6.5 dose enforced by per-plugin drain caps and plugin-side supersession. **Amend §14.14.**

**C12. Re-grounding §16**
- Tier B "depends on the gates branch landing upstream" (rfc:2193).
- Several functions it relies on have zero hits in oc/src, oc/extensions and oc/packages: `markTrustedContinuationHeartbeatWake`, `enqueueContinuationReturnDeliveries`, `sessionDeliveryAckId` and `awaitPromptAdoption`. That makes §16.4 item 1, `awaitPromptAdoption: true` (rfc:2253), unbuildable on main.
- "The SDK path forces `trusted: false` and strips … `traceparent`" (rfc:2215) is false at 6e6458a: SystemEvent has no such fields (oc/src/infra/system-events.ts:25-37).
- Line citations have drifted. `MAX_EVENTS`, cited at :66, is at :39. wrapExternalContent, cited at :382, is at :323. Tier A's `requestHeartbeatNow` is due for removal today (C24).
- §14.8.2 says wakes reset "the host's continuation chain budget" (rfc:1872). No such budget exists on main, so the demand's "MUST NOT reset/evade continuation chain" has nothing to apply to there.
- **Amend §16.1-§16.4**: replace Tier B with the generic seam and re-cite at 6e6458a.

**C13. Vocabulary in 5.1**
- "replay result": §7.4 says a repeat "is not a replay attack and MUST NOT be reported as one" (rfc:441). Use `duplicate` and `expired` instead.
- "correlation fields": §21 #7 says "No correlation ids; lineage references only." (rfc:2743). Any trace carrier must stay local to the host (section 5.3). Fix the demand wording.

**C14. Ownership of the tune table and wake**
- RFC: "One receptor daemon runs per host and serves every session on it" (rfc:1619). Its judgment includes `landing: {sessions, mode, slot}` (rfc:1652). The host wake budget is per host (rfc:1932).
- Demand: subscription-to-session mapping and the wake choice belong to the plugin.
- The two can coexist only if one gateway per host owns the receptor, or if per-host budgets live in the receptor. **Amend the §14 intro and §14.6.1** to allow a harness-embedded receptor, and extend the §14.2 determinism contract to cover the plugin.

**C15. Manifest (7)**
- The demand allows "plain JSON is spike-only".
- The RFC says "A receiver MUST NOT accept a manifest unless it verifies against a root set, or the SHA-256 digest of a genesis manifest" (rfc:981).
- These are consistent if the plugin refuses unsigned manifests unless `allowUnsigned:true` is set and flagged dangerous. Every 234464a manifest is unsigned, so P1 and P2 proofs run under that flag until BC-5. No RFC change.

**C16. Tools (10)**
- RFC:
  - `canticle_listen` has `view: "raw"` ("raw is for operators") (rfc:2087-2088).
  - `canticle_tune` is session-callable, and "Tuning is standing consent to silent landing" (rfc:1684, rfc:2082-2085).
- Demand: no raw-frame tools, and subscriptions managed in config.
- Recommendation: record D20 as decided on the demand's tool set. **Amend §15.1** to make `raw` operator-only (CLI, not a model tool) and tuning config-only in v1.

**C17. Cross-host publish (3, 4)**
- RFC §15.5: "Publishing beyond the host defaults to disabled" (rfc:2150), with config `publish: { crossHost: "disabled" }` (rfc:2238).
- In the demand, `mode:"publish"` with multicast enables it implicitly.
- Recommendation: a separate `station.crossHost` flag, default `false`, under which the station sends only to loopback with `--to 127.0.0.1:<port>`. `true` is a dangerous flag. No RFC change if adopted.

**C18. Multicast gate (3)**
- RFC: multicast is "OPTIONAL; used only when the doctor passes" (rfc:1110). `canticle doctor` "MUST" decide (rfc:1153; also rfc:500).
- The prototype has no `doctor` subcommand (bc/.../__main__.py:267-363).
- Recommendation:
  - Joining or sending multicast (`station.crossHost`, `receive.multicast`) stays a dangerous flag until bc ships `doctor` (BC-5).
  - After that, plugin start runs doctor and refuses to start if it fails.
  - Alternatively, amend §11.2 to grant a spike exemption.

**C19. include_self (3, 5.5)**
- §14.6.1: "Self-broadcast is filtered by default, with an explicit `include_self` override" (rfc:1683).
- In `mode:"both"`, the gateway hears its own station, which is the echo case in 5.5.
- Recommendation: `receive.includeSelf:false`, filtering by `frame.key_id == station.identity.keyId`. No RFC change.

**C20. A11 desync and the post-drain note (5.4)**
- §14.16 item 3 delays chatter, ambient and advisory items per session (rfc:2018-2021).
- §14.14 requires a "withdrawn/expired" note once for items already drained (rfc:2004).
- The demands have neither. The seam needs `notBefore`, and the plugin needs post-drain notes (section 4.3). Plugin-held timers would not be durable. No RFC change.

**C21. Principal (5.3)**
- The banner carries principal from the manifest (rfc:1976-1979), and missing provenance MUST read "unavailable" (rfc:1992).
- The prototype manifest has no principal field (bc/.../manifest.py:26-32).
- Recommendation: the record carries `station.principal: null`, rendered as "unavailable". No RFC change.

**C22. Rejected frames (5.1, 5.2)**
- The demand asks for "signature and manifest/grant result" and "why accepted/rejected".
- §10.9: `unknown_key` is "debug ring only; never quarantine, never a receipt", and `bad_signature` is "debug ring only" (rfc:1075-1076).
- Section 5 follows the RFC: counters only, as fixed per-reason aggregates plus a bounded top-16 key-id table with an `other` bucket. Key ids on unverified frames are sender-chosen, so an unbounded per-key-id map would let any LAN sender grow receptor memory.
- If the princes want per-frame rejection records (Q11), those records go to a local debug ring and are never deliverable or attributed to a station. **Amend §10.9 to say so.**

**C23. Control UI (10)**
- §18.9: serving the tuner beyond the host "needs an authenticated front end, and is out of scope for v1" (rfc:2484).
- The demand allows "loopback/authenticated".
- Recommendation: loopback only in v1. Authenticated serving requires an amendment to §18.9.

**C24. Tier A alias.** `requestHeartbeatNow` has `removeAfter` 2026-10-01 (oc/docs/plugins/sdk-runtime/state-and-system.md:56). Fold this into C12.

**Minor.** §14.7.6 "pause non-alarm wakes" (rfc:1851) contradicts §14.10 item 3 (rfc:1929). Fix this in the same amendment.

### 3.2 Conflicts inside the demands

- **I1.** 5.2 says only `surface` can reach model context, but 10 makes `canticle_recent` a model tool.
  - Resolution: `canticle_recent` returns metadata only for non-surface records, and returns bodies only for items this session already received.
- **I2.** 9 and 12.10 want canticle spans in Tempo, but the plugin can only emit core-owned event types (oc/src/infra/diagnostic-events.ts:808). otel and prometheus ignore unknown types (oc/extensions/diagnostics-otel/src/service-events.ts:38-153).
  - Resolution: either the core change in section 7 (OC-4), or the plugin brings its own OTel exporter. The princes pick one.
- **I3.** 3 makes `group` configurable, but canticle hard-codes 239.255.13.13 as provisional D22 (bc/.../runner.py:26).
  - Resolution: `const` in the schema until bc adds `--group`. The same applies to `binding`.
- **I4.** 1.1 puts judgments in the listener, but the prototype has no disposition.
  - Resolution: BC-2 adds disposition to the listener. The plugin then applies subscription policy only.
- **I5.** 3 has YAML at `plugins.entries.binary-canticle.{mode,…}`, but OpenClaw rejects these keys beside `enabled` (oc/src/config/zod-schema.root-support.ts:135-186).
  - Resolution: put them under `.config`, in JSON5 (section 6).

---

## 4. The P0 seam

### 4.1 Why the existing pieces are not enough

| Piece | Reachable by plugins | What disqualifies it |
|---|---|---|
| `api.runtime.system.enqueueSystemEvent` | Any plugin, with no trust gate (oc/src/plugins/registry-runtime.ts:320-339). The deprecated `plugin-sdk/infra-runtime` also exports drain and peek for any session (oc/src/plugin-sdk/infra-runtime.ts:397-410). | Lives in memory only (oc/src/infra/system-events.ts:1-3). Holds 20 events with silent `shift()` (:39, :182-185). Dedupes by text (:162-170). No expiry or provenance (:25-37). Rendered as `System: [ts] …`, and look-alike lines are deliberately left alone (oc/src/auto-reply/reply/session-system-events.ts:120-126). Any text containing "heartbeat wake", "heartbeat poll" or "reason periodic" is silently dropped (:33-42). In heartbeat turns, contextKey `cron:*` puts raw text into the user prompt as a reminder (oc/src/infra/heartbeat-runner-prompt.ts:231-243,277-288). Lost on restart, reset or store swap. |
| Session-delivery queue (SQLite, `sha256(idempotencyKey)`, 30-day tombstones) | No. Core only (callers: oc/src/gateway/server-restart-sentinel.ts:581,602 and subagent announce). | Its systemEvent drain is `enqueueSystemEvent` plus an `intent:"immediate"` wake, after which the row completes (oc/src/gateway/server-restart-sentinel.ts:106-135; oc/src/infra/session-delivery-queue-recovery.ts:155-162). Durability ends at the in-memory hand-off, every item wakes, and the payload has no expiry (oc/src/infra/session-delivery-queue.records.ts:55-64). |
| `api.session.workflow.enqueueNextTurnInjection` | Any plugin. Prompt injection is allowed by default; only an explicit `hooks.allowPromptInjection:false` blocks it (oc/src/plugins/registry-api.ts:140-153; oc/src/plugins/hook-policy-decisions.ts:6-8). | **Closest.** Durable in the session store and preserved over restart. Has ttlMs. Refuses when full (32 per plugin per session, up to 32 KB each) and refuses unknown sessions. Cleared on reset, delete or disable (oc/src/plugins/host-hook-state.ts:27-29,85-144; docs prompt-and-session.md:338-347). Missing: (1) text is joined raw into the active user prompt, with no host banner (oc/src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:342-350); (2) dedupe covers pending entries only, because it drops expired entries and then dedupes the rest (host-hook-state.ts:126-133); (3) no withdraw or supersede; (4) TTL is relative to `createdAt`, with no absolute deadline (:59-64); (5) not drained on Codex or Copilot; (6) drain is consumption ("not a receipt", docs :316-330); (7) no wake; (8) a drain discards the entries of plugins that are not `loaded` or not injection-allowed, then deletes the whole map (:170-182,196), so entries are lost if canticle is not loaded at the first post-restart drain or during a reload; (9) no per-drain dose cap; (10) no `notBefore` for A11. |
| `heartbeat_prompt_contribution` hook | Any plugin with hooks | Runs only on heartbeat turns and returns `prependContext`/`appendContext` (oc/docs/plugins/hooks/prompt-and-session.md:64-66). Ambient items would wait for the next heartbeat and never land on user turns. Inferred: it has no host durability, idempotency or expiry beyond what the plugin keeps itself. A candidate renderer for P3 wake turns, not a P0 seam. |
| `requestHeartbeat` / `runHeartbeatOnce` | Any plugin | Caller-chosen source and intent. `manual` skips the scheduler's deferral guards (not-due, min-spacing, flood) but not the enabled, interval, active-hours or busy checks. `runHeartbeatOnce` skips the scheduler entirely (oc/src/plugins/runtime/runtime-system.ts:34-43). Not tied to an item. Output defaults to the owner. The override accepts `to` and `accountId` (oc/src/infra/heartbeat-wake-contracts.ts:24-28). |
| `subagent.run`, `dispatchHookAgentTurn` | The first has no gate; the second is trusted-only | `subagent.run` starts a turn with the plugin's text as the prompt and no wrapping (oc/docs/plugins/sdk-runtime/background-work.md:17-19). It must be banned for canticle. Hook dispatch accepts the email source only, into `hook:*` isolated sessions (oc/src/gateway/server/hooks.ts:610-702). |
| `openKeyedStore` (for the plugin's own tombstones) | Bundled or trusted official installs only (oc/src/plugins/registry-runtime.ts:202-220,255) | A third-party canticle plugin cannot use it, so settled-idempotency tombstones belong in the seam. |

### 4.2 Recommended API: extend next-turn injection (additive, no canticle logic)

```ts
// oc/src/plugins/host-hook-turn-types.ts — new fields are optional; absent = today's behaviour
export type PluginNextTurnInjection = {
  sessionKey: string;
  agentId?: string;
  text: string;
  idempotencyKey?: string;
  placement?: "prepend_context" | "append_context";
  ttlMs?: number;
  metadata?: PluginJsonValue;
  /** Absolute deadline, epoch ms. Refused if <= now; dropped unrendered at drain if <= now. Never extended. */
  expiresAt?: number;
  /** Not drained before this epoch ms (A11 desync, rfc:2018-2021). Must be < expiresAt. Re-checked at drain. */
  notBefore?: number;
  /** Accepting this entry withdraws pending entries with the same (pluginId, session, supersedeKey). */
  supersedeKey?: string;
  /** Present => host renders the entry as quoted external data under a host-authored banner, not in the user prompt. */
  provenance?: PluginInjectionProvenance;
  /** W3C traceparent; validated with parseDiagnosticTraceparent; carried to drain diagnostics; never rendered. */
  traceparent?: string;
};

export type PluginInjectionProvenance = {
  /** Low-cardinality label shown in the banner, e.g. "broadcast". /^[a-z][a-z0-9-]{0,31}$/ */
  source: string;
  /** <= 16 facts; keys /^[a-z][a-z0-9_]{0,31}$/; strings single-line, <= 128 chars, sanitized like wrap metadata. */
  facts?: Readonly<Record<string, string | number | boolean>>;
};

export type PluginNextTurnInjectionEnqueueResult = {
  enqueued: boolean;
  id: string;
  sessionKey: string;
  outcome: "accepted" | "duplicate_pending" | "duplicate_settled" | "refused";
  reason?:
    | "expired" | "unknown_session" | "pending_limit" | "tombstone_limit"
    | "too_large" | "invalid" | "prompt_injection_disabled" | "harness_does_not_drain";
};

// OpenClawPluginSessionWorkflowApi (oc/src/plugins/plugin-api.types.ts:107) — new
withdrawNextTurnInjection(params: {
  sessionKey: string;
  agentId?: string;
  idempotencyKey?: string;
  supersedeKey?: string;
}): Promise<{ withdrawn: number; settled?: "consumed" | "withdrawn" | "expired" | "discarded" }>;
```

Host-owned drain caps are a core schema field, set by the operator and never by the plugin:

```json5
plugins: { entries: { "<id>": { injection: { maxEntriesPerDrain: 5, maxBytesPerDrain: 1536 } } } }
```

When the field is absent, behaviour is unchanged.

### 4.3 Semantics

**Durability**
- The session store survives restart (oc/src/config/sessions/plugin-host-cleanup.ts:92-112).
- Unknown sessions are still refused (`found:false`, oc/src/config/sessions/session-accessor.entry.ts:447-456).
- **Changed at drain:** entries with a deadline whose plugin is not `loaded` or not injection-allowed are kept until their deadline instead of being discarded. Entries without a deadline keep today's discard behaviour.

**Drain caps**
- A drain takes at most `maxEntriesPerDrain` entries and `maxBytesPerDrain` bytes per plugin, oldest first.
- The rest stay pending until their deadline.
- The plugin also limits its pending entries with `supersedeKey`, so keyed items never queue behind themselves.

**Settled tombstones**
- At drain, withdraw, expiry or discard, the host records `{key, state: consumed|withdrawn|expired|discarded, retainUntil}` for `(pluginId, canonical session, idempotencyKey)`.
- `retainUntil` is the deadline (`expiresAt`, or `createdAt + ttlMs`) plus 5 s skew.
- A later enqueue with the same key returns `duplicate_settled`.
- The cap is 256 per plugin per session. When the cap is full of live tombstones, new keys are refused with `tombstone_limit`. Live tombstones are never evicted, mirroring rfc:444-445.
- Entries with no deadline get no tombstone, which preserves today's behaviour.
- Reset and disable clear pending entries but **keep** tombstones until `retainUntil`, so a `resurfaced` item cannot land again after a listener restart. Delete clears both.
- Effect: gateway restarts and repeats become no-ops, and a PLUCK heard before the item stops the item from landing later.
- Discarded entries are counted in diagnostics.

**Withdrawal after drain**
- `withdrawNextTurnInjection` returns the settled state when nothing was pending.
- If the state is `consumed`, the plugin enqueues a one-line "withdrawn/expired" note once, keyed `<idem>:withdrawn` (rfc:2004; demand 5.3).

**Expiry and notBefore**
- Both are checked at enqueue and again at drain. Nothing extends them.
- An entry whose `notBefore` falls on or after its deadline is refused with `invalid`.

**Rendering of entries with `provenance`**
- Inferred: this needs a fragment hook at the injection drain site, oc/src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts:61-80.
- The host emits a new runtime-context fragment kind, `external-data`, built like conversation-data (oc/src/agents/embedded-agent-runner/run/runtime-context-prompt.ts:62-71).
- The fragment contains:
  - a host-authored one-line banner built from `provenance.source`, the stamped `pluginId`, the facts, and the age and expiry;
  - then `wrapExternalContent(text, {source: "plugin", …})`.
- The plugin's text never frames itself.
- External content rendering also needs fixes:
  - export `ExternalContentSource` and add a generic source;
  - fold all Default_Ignorable characters and bidi controls into `MARKER_CHAR_FOLDS`;
  - escape internal-context delimiters inside the wrapper. Today they are escaped only in the v4 projection (oc/src/agents/embedded-agent-runner/run/attempt-llm-boundary.ts:58-66,68-95).
- CLI and Codex prepend inbound context raw (oc/src/agents/cli-runner/prepare.ts:1857-1868), so the wrapper must be safe without the v4 projection.

**Taint input**
- The plugin learns that a session drained a canticle item from `agent_turn_prepare`, which receives `queuedInjections` (attempt-prompt-helpers.ts:72-73).
- This feeds the RFC §15.4 item 4 publish check (rfc:2139) in OC-2.

**Harnesses.** Enqueue is refused with `harness_does_not_drain` when the target agent runs on Codex or Copilot, until the drain is wired there.

**Delivery guarantee**
- Accepted entries that have not yet been drained are delivered exactly once across a restart, given the retention change above: pending entries persist and tombstones block repeats.
- After the drain, delivery is at most once, the same as session-state notices. See Q2.

**Wake.** None in P0. Ambient delivery means enqueue only.

### 4.4 What the seam must not do

- No UDP, CBOR or Ed25519, and no notion of a station, stream, epoch or manifest.
- No `deliveryContext`, `contextKey`, heartbeat target, wake source or intent parameters, so neither a payload nor a plugin can steer routing or wake privileges.
- No drop-oldest: the cap refuses with a reason.
- No TTL extension.
- No plugin-set drain caps.
- No rendering of `facts` as instructions.
- Never a trusted "System:" line.

### 4.5 Follow-up for P3 (not P0): a constrained plugin wake

```ts
requestSessionWake(params: {
  sessionKey: string; agentId?: string;
  reason: string;          // /^[a-z0-9:_-]{1,64}$/
  coalesceMs?: number;     // host clamps to >= 5000 (rfc:1939)
}): { outcome: "requested" | "coalesced" | "refused";
      reason?: "rate_limited" | "not_enabled" | "isolated_heartbeat" | "mention_gated" | "unknown_session" };
```

**Wake intent: do not use `intent:"event"`.**
- On a scheduled agent, an event wake that arrives more than 30 s after the last run is deferred to `nextDueMs` (oc/src/infra/heartbeat-cooldown.ts:56-63). The verificationer probe gave retryAtMs 1,800,000.
- That breaks the 120 s alarm freshness bound (rfc:1935).
- The host should instead force a new `HeartbeatWakeSource` value `"plugin"` with one of two rules:
  - **Recommended: spacing-only.** Run the flood guard, then retry at `lastRunStartedAt + 30 s`, never `not-due`.
  - **Alternative:** `immediate` plus the flood guard plus the host budget.

**Other wake rules**
- Per-(plugin, session) token bucket and a per-plugin hourly budget, from host-owned config `plugins.entries.<id>.wake`. Defaults come from rfc:1931-1932. This needs a core schema field, because the entry is a strict object.
- The route is the session's own (`target:"last"`) or `none`, chosen by the operator, never by the payload.
- For group routes, apply the channel's requireMention as a gate unless a per-session operator opt-in says otherwise.
- Refuse when `heartbeat.isolatedSession` is set, because the woken turn would not read the base queue (oc/src/infra/heartbeat-runner-session.ts:191-225).
- Woken turns must run outbound hooks; today heartbeat turns set `suppressOutboundHooks: true` (heartbeat-runner-run.ts:111).
- Woken turns must not be silenced by the 24 h identical-text suppression (heartbeat-dispatch.ts:429-433).
- A channel without `heartbeat.checkReady` (Discord) must report delivery failure, not success (heartbeat-dispatch.ts:379,469).

**Separate hardening for review**
- The plugin-facing `requestHeartbeat` forwards any source and intent (oc/src/plugins/runtime/runtime-system.ts:18-32). It should reject `manual` and spoofed sources.
- `requestHeartbeatNow` is past its `removeAfter`.
- The `plugin-sdk/infra-runtime` drain and peek exports should be scoped to the caller's own sessions or removed (oc/src/plugin-sdk/infra-runtime.ts:397-410).

**Alternative, if maintainers do not want SessionEntry to grow**
- Add a new SQLite queue name on the delivery-queue machinery, insert-only with 30-day tombstones (oc/src/infra/delivery-queue-sqlite-bound.ts:18,139-152,209-287).
- It would ack at drain, like session-state notices (oc/src/sessions/session-state-events.ts:238-284,349-389).
- That is more code: a new drain and ack hook plus a startup sweep.

---

## 5. P0 receptor record schema v1 (draft)

### 5.1 Transport and framing

- Emitted by `canticle listen --records v1` on stdout. Today's output stays the default, for the tuner and `proofs/web-lanes/analyze.py`.
- One JSON object per line, `ensure_ascii`, at most 64 KiB per line. Frames are at most 1100 bytes (bc/.../wire.py:26), so a body always fits.
- Diagnostics stay on stderr.

### 5.2 Record types

Every record carries `v:"canticle-receptor-record/1"`, `type`, `rec_seq` (monotone within each process run) and `run` (random hex set at start).

| type | When | Today |
|---|---|---|
| `hello` | After UDP bind, multicast join and state load. This is the readiness receipt. | New. The `listener_state` line is printed before the bind (bc/.../__main__.py:201; runner bind at bc/.../runner.py:174). |
| `frame` | Every **verified** item, whatever its disposition | Partial: today's `item` event |
| `retract` | Every valid PLUCK or supersede; local expiry of every tuple ever surfaced, **including pre-restart tuples not yet re-heard**; every held item dropped in `_release_held` | Partial: emitted only when the target is in `current` (listener.py:247-250,271-274,327,362-368) |
| `presence` | Station presence changes | Yes (listener.py:464) |
| `health` | Periodic (default 10 s): counters by admission and disposition (a fixed set of reasons), dedup occupancy and beacon age per manifest key (bounded by the manifest), a bounded table for unverified datagrams (below), records dropped, `state: ok\|degraded` with reasons (`clock_skew`, `records_lost`) | New. `evidence_counts` exists in process only (listener.py:125). |
| `fatal` | Before a non-zero exit: `reason` is `state_corrupt`, `manifest_invalid`, `bind_failed` or similar | New. Today these are tracebacks (JSONDecodeError, KeyError; bc-proto) |
| `bye` | Clean shutdown | New |

**`hello` fields:**
- `wire` (2, wire.py:21), `record`, `pid`;
- `bind` (`host:port`), `multicast` (`{group, port}` or `null`), `binding` (`"lan"`);
- `manifest_sha256`, `manifest_label`;
- `state_version` (listener.py:30), `state_path`.

**Unverified datagrams** produce **no per-frame record**. This covers `unknown_key`, `bad_signature`, `malformed`, `expired` or `not_yet_valid` at parse, and `revoked`.
- They are only counted in `health`, never by station name. Key ids on unverified datagrams are chosen by the sender, so nothing is keyed by them without a bound:
  - one fixed aggregate counter per reason;
  - at most a top-16 table of key-id hex by count (space-saving or LRU), with an `other` bucket for the rest.
  - A flood of distinct key ids then grows neither receptor memory nor the `health` record, which stays far below the 64 KiB line limit.
- This follows rfc:1075-1076 and fixes listener.py:134-141.
- It conflicts with demands 5.1 and 5.2 (C22, Q11).

### 5.3 The `frame` record

```json
{"v":"canticle-receptor-record/1","type":"frame","rec_seq":4182,"run":"9f2c1a7e",
 "frame":{"key_id":"5ad1e0c3b2a49f07","epoch":1790836981,"stream_id":447989129,"seq":12,"kind":"item",
          "sha256":"<64 hex>","bytes":312,"lens":null},
 "idem":"canticle:5ad1e0c3b2a49f07:1790836981:447989129:12",
 "station":{"name":"cael","principal":null},"stream":"lens.threat",
 "class":"advisory","scope":"lan","hop":0,
 "flags":{"refresh":false,"wake_derived":false,"exercise":false},
 "state_key":"threat","purpose":null,"intensity":null,
 "lineage":{"derived_from":[],"root":null},
 "times":{"issued_at":1790836990123,"expires_at":1790837050123,"received_at":1790836990160,
          "heard_at":1790836990160,"offset_ms":-3,"local_expiry_at":1790837050126,"age_ms":40},
 "gap":"unavailable",
 "admission":"verified",
 "dedup":"first",
 "disposition":"surface","reasons":[],
 "body":{"ctype":"text/plain; charset=utf-8","text":"…","bytes":120,"sha256":"<64 hex>"},
 "versions":{"manifest_sha256":"<64 hex>","manifest_label":"canticle-fleet/spike-0","rule":"bc-listener-rules/1","state":1},
 "trace":{"traceparent":"00-<frame.sha256[0:32]>-<random 16 hex>-01"}}
```

How each field maps to demand 5.1, and whether the prototype can fill it today:

| Field | Demand item | Prototype source (234464a) | Today |
|---|---|---|---|
| `v`, `type`, `rec_seq` | protocol version | none (`STATE_VERSION` versions the state file only, listener.py:30) | new |
| `frame.key_id`, `epoch`, `seq` | frame identity | `Event.key_id`, `seq`, `data.epoch` (listener.py:42-48,287) | yes |
| `frame.stream_id` | identity | identity tuple `body.stream` (listener.py:208; wire.py:133-139) | new, one line. The plugin can compute it today with `ids.stream_id(name)` (bc/.../ids.py:27). |
| `frame.kind` | identity | `f.kind` | new, trivial |
| `frame.sha256`, `bytes` | raw frame reference | computed `digest` (listener.py:209), not emitted | new, trivial |
| `frame.lens` | lens policy (demand 3) | `wire.Item.lens`, a uint16 (wire.py:72), not emitted by `_item_data` (listener.py:286-306) | new, trivial |
| `idem` | idempotency key (demand 8) | built from the above per rfc:2157 | new. The plugin appends `:<canonical sessionKey>`, with no subscription id (C10). |
| `station.name` | station | `_name(kid)` (listener.py:116) | yes. Emit only once verified. |
| `station.principal` | banner principal (rfc:1976-1979) | none; `StationEntry` has no principal (manifest.py:26-32) | always `null`, rendered "unavailable" (rfc:1992) until the manifest carries it (BC-5) |
| `stream`, `class`, `hop`, `state_key`, `purpose`, `intensity` | stream, class | `_item_data` (listener.py:286-306) | yes |
| `scope` | scope | emitted as an int code (listener.py:288) | change to the name |
| `flags` | — | `Item.flags` (wire.py:75); only `refresh` is emitted | partial |
| `lineage` | correlation fields (lineage only, rfc:2743) | `Item.derived_from`, `Item.root` (wire.py:66,71), not emitted | new. Values are empty until stations can stamp them (BC-3). |
| `times.issued_at`, `expires_at` | issued and expiry | listener.py:287 | yes |
| `times.received_at` | received | `t_ms` only with `--timestamps` (__main__.py:173) | partial |
| `times.heard_at`, `local_expiry_at`, `offset_ms` | effective expiry | `_Heard.first_heard`, `_Heard.local_expiry` (listener.py:56-57); `wire.local_expiry_ms` (wire.py:337); `offset_ms` (listener.py:79) | new. `heard_at` is the first hearing **in this run**. Dedup rows persist only (digest, retain) (listener.py:104), so on resurface `first_heard` becomes the re-hearing time (listener.py:280). `local_expiry_at` does survive, because `retain` is persisted. Option for BC-2: persist first_heard and rename the field `first_heard_at`. |
| `gap` | gap state (demand 5.3) | needs `trail_seq` (BC-5) | const `"unavailable"` |
| `admission` | signature and grant result | implicit: parse verifies before returning (wire.py:373-422) | new. There is no `sig` field: only verified frames produce records. |
| `dedup` (`first` or `resurfaced`) | dedup, equivocation, replay | resurface path (listener.py:219-229) | new. Removes the unmarked re-emission after restart. |
| `disposition`, `reasons[]` | disposition plus machine reasons | none | new (table 5.4) |
| `body` / `body_ref` | body or payload ref | `text` / `body_hex` / `body_ref` (listener.py:299-305) | yes, renamed. Present only for `surface` and `ringbuffer_only`. Always untrusted. |
| `versions` | rule and manifest version | none. The manifest label is read and ignored (manifest.py:80-91). | new |
| `trace.traceparent` | trace carrier | none, and frames have no trace field | new (see the trace proposal below) |

**Trace proposal for `trace.traceparent`**
- **Receive side.** The trace-id is the first 16 bytes of the frame sha256. Because each frame is signed once, every copy and every host derive the same receive-side trace-id. That gives a two-host Tempo trace (12.10) without a wire correlation id.
- **Publish side.** The publish span lives in the agent's own trace (its `traceparent`, an input to demand 4), and the frame digest is known only after the receipt. The receive trace therefore cannot join the publisher's trace. Instead, the station receipt returns `frame_sha256` (BC-3), and the publish span adds a **span link** to the derived trace-id.
- **Limit.** The agent's own trace is kept locally (demand 9), but it cannot continue across hosts, because rfc:2743 forbids correlation ids on the wire.

### 5.4 Disposition mapping (prototype outcome → RFC §10.9 admission → RFC §14.3 disposition)

| Prototype outcome (234464a unless noted) | Admission | Disposition | Record |
|---|---|---|---|
| `item` emitted (listener.py:280-281) | `verified` | `surface` | frame |
| Same tuple, same bytes (listener.py:220-224) | `duplicate` | no-op | health counter |
| Resurfaced after restart (listener.py:225-228) | `verified` | `surface`, with `dedup:"resurfaced"` | frame; the plugin no-ops on `idem` (host tombstone) |
| PLUCK resurfaced after restart (listener.py:239-240) | `duplicate` | no-op | health counter `pluck_resurfaced` |
| Older or repeated beacon (listener.py:167-168) | — | no-op | health counter `beacon_stale` |
| `capability`: class not granted (listener.py:191-193) | `capability_exceeded` | `ringbuffer_only` (rfc:1078) | frame, no body |
| `scope-violation`: scope not granted to the key (listener.py:198-201) | `capability_exceeded` | `ringbuffer_only` (rfc:1078) | frame, no body. **BC-2:** give it a reason distinct from the binding case. |
| `scope-violation`: binding narrower than the frame's scope (listener.py:194-197) | `scope_violation` | `drop` | frame, no body |
| Unnamed stream (silent at listener.py:276; manifest `streams` not enforced) | `capability_exceeded` | `ringbuffer_only` | frame. **New:** enforce the grant. |
| Untuned stream (silent at :276) | `verified` | `ringbuffer_only`, reason `untuned` | frame. **New.** |
| Live-state held for warm-up (silent at :277-279) | `verified` | `ringbuffer_only`, reason `warmup_hold`; later `surface` when released | frame twice. **New.** |
| Held item expired, plucked or superseded before release (`_release_held`, listener.py:327) | — | — | `retract` with reason `held_expired`, `held_plucked` or `held_superseded`. **New.** |
| `unknown-class` (:256-258) | `verified` | `ringbuffer_only` | frame |
| `hop-limit` (:202-205) | not in §10.9 | `drop`, reason `hop_limit` | frame. **RFC: add a row.** |
| `epoch-regression` (:146-149) | not in §10.9 | `drop`, reason `epoch_regression` | frame. **RFC: add a row.** |
| `over-quota` (:231-234) | `over_quota` (rfc@c9fe9cd §10.9) | `drop` | frame |
| PLUCK whose `expires_at` or scope differs from its held target (#62 at c9fe9cd) | `pluck_mismatch` (rfc@c9fe9cd §10.9) | `drop` | frame |
| `plucked` (:253-254) | `plucked` | `drop` | frame |
| `superseded`, older than the hwm (:264-266) | `superseded` | `drop` | frame |
| `equivocation` (:213-216) | `equivocation` | `quarantine_set` (rfc:1081) | frame. **New:** quarantine the key; the prototype does not (verified by probe). |
| Unverified datagram (listener.py:134-141) | `unknown_key`, `bad_signature`, `malformed`, `revoked`, … | — | health counter only: per-reason aggregate plus the bounded top-16 key-id table (rfc:1075-1076; C22) |
| Control-frame quarantine ops | — | `quarantine_strengthen` / `quarantine_rescind` | reserved; not implemented |

**Delivery mapping, plugin side**
- A `surface` record on a subscription with posture `silent` (config `ambient`) goes to the core seam (section 4).
- Posture `wake-on-alarm` (config `wake`) requires all of §14.10.
- Records whose `frame.key_id` is the gateway's own station key are dropped unless `includeSelf` is set (C19).
- Everything else goes to the local ring only.

### 5.5 Fail-closed rules (plugin)

- An unknown major `v`: stop delivering, set health `failed`, reason `record_version`.
- An unknown `type` within v1: count it and ignore it.
- A missing required field or a wrong type: drop the record, count `malformed_record`, never deliver.
- JSON nesting deeper than 8 levels: reject before parsing completes and count `malformed_record`. This is demand 7's depth cap; 11.3 adds a depth-bomb test.
- A line over 64 KiB: discard up to the newline and count it.
- A `rec_seq` gap: mark the receive side `degraded (records_lost)`.
- `fatal`, or exit without `bye`: health `failed` with the reason, then restart under backoff.
- `disposition !== "surface"` is never deliverable.
- A `frame` without `local_expiry_at`, or one already past it, is refused.
- Config bounds: pending records, stderr bytes and the local ring.

---

## 6. P0 subscription config draft

The conventions follow the template plugin oc/extensions/voice-call/openclaw.plugin.json:
- `activation.onStartup` and `contracts.tools` at :19-25;
- `configSchema` with `additionalProperties:false` at :336-339;
- tool `configSignals` with a `mode` guard (oc/docs/plugins/manifest/providers.md:73-87).

**Secrets.** No `configContracts.secretInputs` or SecretRef is needed, because config carries only paths. The schema rejects a `key` value matching `^[0-9a-fA-F]{64}$`.

Operator config lives at `plugins.entries["binary-canticle"].config` in `~/.openclaw/openclaw.json` (JSON5).

**Manifest skeleton (`openclaw.plugin.json`)**

```json
{
  "id": "binary-canticle",
  "activation": { "onStartup": true },
  "contracts": { "tools": ["canticle_publish", "canticle_withdraw", "canticle_status", "canticle_recent"] },
  "toolMetadata": {
    "canticle_publish":  { "optional": true, "sideEffecting": true,
      "configSignals": [{ "rootPath": "plugins.entries.binary-canticle.config", "mode": { "allowed": ["publish", "both"] } }] },
    "canticle_withdraw": { "optional": true, "sideEffecting": true,
      "configSignals": [{ "rootPath": "plugins.entries.binary-canticle.config", "mode": { "allowed": ["publish", "both"] } }] },
    "canticle_recent":   { "optional": true,
      "configSignals": [{ "rootPath": "plugins.entries.binary-canticle.config", "mode": { "allowed": ["receive", "both"] } }] }
  },
  "configContracts": {
    "dangerousFlags": [
      { "path": "receive.subscriptions.*.allowWildcard", "equals": true },
      { "path": "receive.subscriptions.*.wake.allowWithoutMention", "equals": true },
      { "path": "receive.includeSelf", "equals": true },
      { "path": "receive.multicast", "equals": true },
      { "path": "station.crossHost", "equals": true },
      { "path": "manifest.allowUnsigned", "equals": true },
      { "path": "diagnostics.captureBodies", "equals": true }
    ]
  },
  "cliCommands": [{ "name": "canticle", "description": "binary-canticle status and diagnostics", "hasSubcommands": true }],
  "configSchema": { "type": "object", "additionalProperties": false, "properties": { "...": "see below" } }
}
```

**Operator config (JSON5), with defaults**

```json5
plugins: { entries: { "binary-canticle": {
  enabled: false,   // write it explicitly: a block with config for a contracts.tools plugin and no `enabled`
                    // is auto-enabled (oc/src/config/plugin-auto-enable.shared.ts:108-121,455-473)
  // hooks.allowPromptInjection: omitted. Default is allowed; only an explicit false blocks ambient
  // landing (oc/src/plugins/hook-policy-decisions.ts:6-8).
  config: {
    mode: "receive",                      // receive | publish | both. No schema default: absent => inert, health "disabled"
    executable: "/opt/canticle/bin/canticle",  // absolute path; no PATH search; resolved and version-checked at start
    expect: { record: "canticle-receptor-record/1" },  // wire version is checked against hello.wire once BC-2 lands
    manifest: { path: "/etc/canticle/fleet.json", sha256: "<pinned hex>",
                allowUnsigned: false },   // 234464a manifests are unsigned (manifest.py:3-6,91): P1/P2 proofs need true until BC-5
    stateDir: "~/.openclaw/state/binary-canticle",  // created 0700; owner == uid; no symlinked ancestors
    station: {                            // required in publish | both; ignored in receive
      identity: { name: "gw1", keyId: "<16 hex>" },  // at start: keyId == ids.key_id(pubkey) and manifest entry name == name
      key: "/etc/canticle/keys/gw1.key",  // path only, never bytes (schema rejects 64-hex); 0600, nlink 1, O_NOFOLLOW before spawn
      controlSocket: "auto",              // auto => <stateDir>/run/station.sock; always passed via --control
      crossHost: false,                   // rfc:2150,2238. false => --to 127.0.0.1:<port> only; true => --multicast (dangerous, C17/C18)
      group: "239.255.13.13",             // schema const until bc adds --group (bc/.../runner.py:26)
      port: 9999,                         // 1024..65535; D22 provisional
      unicast: [],                        // schema const [] until BC-3 sets IP_TTL=1 (only IP_MULTICAST_TTL today, runner.py:107-110)
      socketClasses: ["chatter", "ambient", "advisory"],  // never alarm/regulatory/control (rfc:2058-2059)
      streams: [                          // minItems 1; each becomes --stream name:class:default_ttl_s (__main__.py:286)
        { name: "gw1.notes", class: "advisory", defaultTtlS: 60 }  // checked against the manifest grant at start
      ]
    },
    receive: {                            // required in receive | both
      bind: "0.0.0.0", port: 9999,        // passed as --bind host:port (__main__.py:322-333)
      multicast: false,                   // --multicast; dangerous until `canticle doctor` exists (C18)
      binding: "lan",                     // schema const: the CLI has no binding flag (listener.py:85; __main__.py:166-167)
      includeSelf: false,                 // rfc:1683; drops records whose key_id == station.identity.keyId (C19)
      subscriptions: [
        {
          id: "fleet-advisories",         // ^[a-z0-9][a-z0-9-]{0,47}$, unique, stable
          stations: ["cael"],             // manifest names; "*" only with allowWildcard
          streams: ["lens.threat"],       // exact names; patterns only with allowWildcard
          allowWildcard: false,
          classes: ["advisory", "live-state"],
          scopes: ["lan"],
          lens: null,                     // optional allow-list of lens codes (uint16, wire.py:72); null = any
          targets: [{ sessionKey: "agent:main:main" }],  // must exist at start and at enqueue
          delivery: "ringbuffer_only",    // ringbuffer_only | ambient | wake  (RFC §14.9: off | silent | silent-wake)
          consumption: "raw",             // schema const until BC-5: "completed" needs trail_seq (rfc:1757-1759)
          budget: { itemsPerMinute: 6, bytesPerMinute: 4096, burst: 3,
                    itemsPerTurn: 5, bytesPerTurn: 1536, maxBodyBytes: 512 },  // per-turn dose rfc:1727; enforced by host drain caps (4.2)
          freshness: { maxAgeAtFirstHearingS: 120,   // never extends local_expiry
                       maxTtlS: 300 },               // refuse expires_at - issued_at above this (D3 stream max_ttl)
          overflow: "refuse_newest",      // refuse_newest | replace_keyed; drop_oldest is not accepted (C9)
          wake: { allowWithoutMention: false },  // valid only with delivery:"wake" and classes == ["alarm"] (C1)
          format: { banner: "full" }
        }
      ]
    },
    limits: { recordLineBytes: 65536, recordDepth: 8, pendingRecords: 1024, stderrBytes: 65536, ringDepth: 256,
              restart: { initialMs: 1000, maxMs: 60000, jitter: 0.2, breakerExits: 5, breakerWindowS: 300 } },
    diagnostics: { captureBodies: false }
  }
} } }
```

**Validation split.** A schema failure blocks Gateway boot even under `enabled:false` (oc/src/config/validation-plugin-config.ts:345-395), so the schema checks shape, bounds and consts only. Everything else runs in service `start()` and fails the plugin, not the Gateway:
- filesystem, permission and symlink checks;
- the manifest digest;
- the identity check (key_id and name);
- the station streams against the manifest grant;
- the executable's version;
- whether target sessions exist;
- the rule that `wake` requires alarm-only.

**Reload**
- `service.reload.configPrefixes` restarts only the affected child: `…config.station` and `…config.mode` for the station, `…config.receive` for the receptor.
- `registerReload({ hotPrefixes: ["plugins.entries.binary-canticle.config.receive.subscriptions"] })` handles subscription edits live.
- Never use `restartPrefixes`, which means a Gateway restart (oc/src/gateway/config-reload-plan.ts:350-359,430).
- A reload must not leave canticle unloaded across a drain: this relies on OC-0's retention rule.

---

## 7. Proposed slices

### binary-canticle

| # | Scope | Files | Proof gate | Now? |
|---|---|---|---|---|
| BC-1 | RFC amendment: a new §14.18 "Harness interface (receptor → binding)", or RFC-0002 to resolve §23.2 item 14 (rfc:2918). **Freezes:** record v1 (section 5), the disposition mapping (5.4), the subscription shape (section 6), the delivery-mode mapping (C5), and idempotency plus expiry (C10). **Amends:** §10.9 (add `hop_limit` and `epoch_regression`; rejected-frame records per C22); §14.6.1 (harness-embedded receptor, C14); §14.9; §14.12 (C7 decision); §14.13 (C6, C21); §14.14 (C11); §15.1 and D20 (C16); §15.5 (C17); §11.2 (C18, if exempted); §18.9 (C23, if adopted); §16.1-§16.4 (re-ground at oc 6e6458a, replace Tier B, C12/C24); §14.7.6 vs §14.10; resolution of §23.2 item 21 (C9). Names the commit it freezes against: 234464a, or `c9fe9cdc0a401c9875aa1bf9dea46d5c52bcc041` (PR #62's head) re-pinned to its merge commit once #62 lands. | `rfc/0001-binary-canticle.md` (or `rfc/0002-…`), `reports/2026-09-27-survey-and-path.md` §13 | Review receipt from the princes; every quoted OpenClaw line re-cited at 6e6458a | Yes. Do it first, once Q6 picks the freeze point (§10.9 differs between them). |
| BC-2 | Listener record emitter `--records v1`. **Records:** `hello` after bind, with the 5.2 fields; records for every verified outcome; `retract` for every valid PLUCK, supersede and expiry (including restored tuples) and for held-item drops; counters for resurfaced PLUCKs and stale beacons; `health` with degraded states (`clock_skew`, `records_lost`); `fatal` instead of tracebacks for a corrupt state file and an unknown manifest class; `bye`. **Frame fields:** `lens`, `station.principal:null`, `gap:"unavailable"`, `heard_at` (or persisted first_heard). **Behaviour:** distinct reasons for scope-not-granted (`capability_exceeded`) vs binding-narrower (`scope_violation`); unverified datagrams counted without station attribution; equivocation quarantine; manifest `streams` grant enforced. | new `canticle/records.py`; `canticle/listener.py`; `canticle/runner.py`; `canticle/__main__.py`; `canticle/manifest.py`; `tests/test_records.py`; golden `vectors/records/*.jsonl` | Golden vectors. Property test: every `hear()` and `tick()` outcome maps to exactly one record or counter. Restart test: a PLUCK after restart yields a `retract`. No record names a station for an unverified frame. `hello` comes strictly after the UDP bind. A corrupt state file and an unknown class yield `fatal`, not a traceback. Adversarial distinct-key flood: 10⁶ datagrams with distinct random key ids leave receptor memory and every `health` record within fixed bounds (each line ≤ 64 KiB). | Yes (small to medium) |
| BC-3 | Station hardening for P2. **Validation:** size and field-range checks before `head_seq += 1` (station.py:270-275; wire.py:259-296); hush reason ≤ 2. **Socket protocol:** error codes; always reply (runner.py:119-123); server read timeout; `request_id` idempotency map. **Receipt** gains `key_id`, `stream_id`, `class`, `scope`, `hop`, `frame_sha256`, `requested_ttl_s` and `ttl_clamp`. **Lineage:** tool-set socket fields `hop`, `derived_from`, `root` and `wake_derived`; `Station.sing` gains `derived_from` and `root` (station.py:236-240). **Shutdown and network:** refuse `sing` once stop is set, so no acked-but-unsent items (runner.py:148-165); `IP_TTL=1` on unicast sends (runner.py:107-110). **Readiness:** JSON ready line on stderr after bind; `canticle version --json`. | `canticle/station.py`, `canticle/runner.py`, `canticle/__main__.py`, tests | Adversarial control-socket tests (non-object JSON, 70 KB line, bad loop, intensity 999). A retry with the same `request_id` returns the original receipt. Lineage fields round-trip into the frame. A sing during stop is refused, never acked and lost. Unicast frames carry TTL 1. | Yes (small) |
| BC-4 | Key and lease safety. Lease and epoch keyed by key_id in a 0700 runtime dir. Key opened with `O_NOFOLLOW`, plus mode, owner and `nlink == 1` checks. Refuse to unlink a non-socket or a live socket. Fail closed when peer credentials are unavailable (`getpeereid` on BSD and macOS). | `canticle/__main__.py`, `canticle/runner.py`, `canticle/station.py`, tests | **On one host**, a hardlinked, symlinked or copied key cannot start a second station, whatever the start timing; the key_id lease lives in a host-local runtime dir and excludes nothing elsewhere. A regular file at `--control` survives. A wrong-UID peer is refused. **Across hosts** see the note below the table. | Yes (small) |
| BC-5 | P3/P4, bc side only. A1 `trail_seq` with an explicit version rule (rfc:748 vs A1). Signed manifest with principal, genesis pin and reload. `canticle doctor` (rfc:1153). Operator alarm-body publish path (C3). | wire, station, listener, manifest, CLI, RFC | A9 proofreading vectors; revocation while live; doctor pass and fail; two-host proof | Later |

**Cross-host duplicate keys (BC-4 note).** No local mechanism stops a copied key from starting a station on another host, so BC-4's proof is not fleet-wide mutual exclusion. Fleet-wide uniqueness needs a separate key-issuance and manifest control: one key per station, issued, rotated and revoked through the signed manifest (BC-5). Below that, the invariant is detection, not exclusion:
- Two stations signing with one key are seen by any receiver that hears both, as `equivocation` (same epoch and tuple, different bytes, §10.8) or as `epoch-regression` (different epochs: the prototype's epoch is max(previous + 1, Unix seconds) per host, bc/.../station.py:99-106, so two hosts that start in different seconds hold different epochs).
- `equivocation` quarantines the key locally (rfc:1081; BC-2 adds the quarantine the prototype lacks). Revocation fleet-wide is the operator's signed-manifest reload (BC-5).
- Gap: `epoch-regression` alone does not quarantine, and an honest restart produces a few seconds of it from old-epoch copies still in flight. Recommended for BC-1/BC-2, for the princes to confirm: treat `epoch-regression` that continues past one advertised loop period after the key's epoch advanced as a duplicate-key signal, quarantined like equivocation.
- Proof gate (with BC-5's two-host proof): two hosts, one copied key; every receiver that hears both records the evidence and holds the key out.

### OpenClaw

| # | Scope | Files | Proof gate | Now? |
|---|---|---|---|---|
| OC-0 | Core seam (sections 4.2-4.4). **API:** `expiresAt`, `notBefore`, `supersedeKey`, `provenance`, `traceparent`, outcome and reason; `withdrawNextTurnInjection` returning settled state; `harness_does_not_drain`. **Drain:** settled tombstones that survive reset and disable; retention at drain for not-loaded plugins; host-owned per-plugin drain caps (core schema field). **Rendering:** `external-data` fragment; `wrapExternalContent` fold, delimiter fixes and exported source type. No wake. | `src/plugins/host-hook-turn-types.ts`, `src/plugins/host-hook-state.ts`, `src/plugins/registry-api.ts`, `src/plugins/plugin-api.types.ts`, `src/config/zod-schema.root-support.ts`, `src/agents/embedded-agent-runner/run/attempt-prompt-helpers.ts`, `src/agents/embedded-agent-runner/run/runtime-context-prompt.ts`, `src/agents/cli-runner/prepare.ts`, `src/security/external-content.ts`, `src/plugin-sdk/security-runtime.ts`, `docs/plugins/hooks/prompt-and-session.md`, tests | **Unit tests:** expiry and notBefore at enqueue and drain; pending and settled duplicates; withdraw and supersede before and after drain; refusal at the cap (no eviction); drain caps; restart persistence; plugin not loaded at the first post-restart drain, and during reload replacement (entries kept); reset keeps tombstones; unknown-session refusal. **Adversarial rendering corpus** (the 13 look-alikes, fake `System:`, fake banner, `<<<END_OPENCLAW_INTERNAL_CONTEXT>>>`) under v3, v4 and CLI. Existing injection tests unchanged. | Yes, once the princes accept the shape (Q2) |
| OC-1 | Plugin P1 (receive, no wake). **Package:** manifest and schema (section 6). **`canticle-receptor` service** with its own supervisor: explicit argv spawn, `shell:false`, env allowlist, bounded framer with a depth cap, TERM then KILL inside the 5 s grace, backoff via `computeBackoff`, breaker, PID file to reap orphans. **Receive pipeline:** record v1 parser; identity check; subscription matcher with `includeSelf` and lens; budgets; local ring; `ringbuffer_only`, then `ambient` via OC-0; post-drain withdrawal notes; taint tracking via `agent_turn_prepare`. **Surfaces:** `canticle_status`, operator-only `canticle_recent`, gateway method and CLI. No Control UI beyond loopback (C23). No publish from any receive path (5.5). **Templates:** oc/extensions/voice-call/index.ts:446-612; oc/extensions/signal/src/daemon.ts:218-310 and socket-path.ts. | new `extensions/binary-canticle/` (or an external package) | Demand 11.1 subset. One-host landing proof (raw frame → record → injection row → exactly one wrapped item). Two-host LAN proof. Restart proofs (gateway, listener). Disable and rollback proof (zero processes, sockets and tools). Proofs run with `allowUnsigned:true` until BC-5. | `ringbuffer_only` now (against BC-2); ambient after OC-0 |
| OC-2 | Plugin P2: `canticle_publish` / `canticle_withdraw` over the control socket, plus the `canticle-station` service. **§15.4 checks:** item 3 grant; item 1 TTL clamp; item 8 size; item 4 tainted-session refusal at fleet/public; item 5 lineage stamping (after BC-3); item 6 secret and high-entropy scan; item 7 opaque content at fleet/public; item 9 at most 5 per turn and 60 per hour; item 10 `training_eligible=0`. **Other gates:** §15.5 leaf sub-agents get no publish tools; `crossHost` gate (C17); traceparent validation and span link. **Shutdown:** stop accepting publishes before sending TERM to the station. | plugin | Grant, clamp, size, TTL, taint, secret-scan and rate tests. Socket timeout returns `unknown_outcome`. Receipts carry `frame_sha256`. No sing is acked during shutdown. | After BC-3 |
| OC-3 | Core wake seam (section 4.5): source `plugin` with spacing-only deferral; hardening of plugin `requestHeartbeat` (reject `manual`); `requestHeartbeatNow` removal; scoping of the infra-runtime drain and peek exports. Then the plugin wake per §14.10. | `src/infra/heartbeat-cooldown.ts`, `src/infra/heartbeat-wake-contracts.ts`, `src/infra/heartbeat-wake-policy.ts`, `src/infra/heartbeat-runner-run.ts`, `src/infra/heartbeat-dispatch.ts`, `src/infra/session-event-wake.ts`, `src/plugins/runtime/runtime-system.ts`, `src/plugin-sdk/infra-runtime.ts`, `src/config/zod-schema.root-support.ts`, plugin | Wake proofs: idle, busy, mention-gated, coalesced and suppressed. An alarm 31 s after the last run on a scheduled agent lands within 120 s. Flood vs guards. Outbound hooks run on woken turns. 24 h duplicate suppression does not silence an alarm. Discord route, including a Discord outage reported as failure. | Blocked on Q1 and C3 |
| OC-4 | Observability: either a generic `plugin.span` diagnostic event with span names declared in the manifest (exported by diagnostics-otel), or a decision that the plugin runs its own exporter. | `src/infra/diagnostic-events.ts`, `extensions/diagnostics-otel/src/service-events.ts`, manifest schema | Saved Tempo trace JSON across two hosts, using the frame-digest trace-id, with the publisher's span linked to it | After the I2 decision |
| OC-5 | P4 OpenClaw side: single-seat canary config (one session, one subscription), arming approval before `ambient` or `wake` takes effect, an `openclaw canticle rollback` command (disable, drain-clear, stop children) and soak bounds (duration, budget ceilings, breaker trips that auto-disarm). | plugin, docs | Soak report within bounds. Rollback leaves zero processes, sockets, pending injections and tools. Arming refused without approval. | Later (with BC-5) |

---

## 8. Open questions that block P0 or P1

1. **Q1. D1.** Does "allowed class" in 5.5 reopen D1 (alarm-only wake)? If not, the schema hard-restricts `wake` to `["alarm"]`, and P3 waits for an operator alarm path (C1, C3).
2. **Q2. Seam and guarantee.**
   - Do you accept extending `enqueueNextTurnInjection` (section 4.2, including retention at drain and host drain caps) rather than a new SQLite inbox?
   - Is "exactly once" satisfied by consumption at prompt assembly, with at most once after the drain? The alternative is acknowledging at transcript commit, which needs a persistence hook.
3. **Q3. Taint.** Does taint mean wrapping (demand 5.3), or §14.12 tool denial including "outbound messages to off-host targets"? This decides whether P1 `ambient` may target Discord-bound sessions (C7).
4. **Q4. Ownership.** Do subscriptions and budgets live in plugin config (demand) or in a per-host receptor (rfc:1619)? With several gateways on one host, who enforces the 6-per-hour host wake budget (C14)?
5. **Q5. Landing model.** Per-frame durable rows with the per-turn dose enforced by drain caps (recommended), or the §14.14 two-slot digest (C11)?
6. **Q6. Freeze point.** Which commit do we freeze against?
   - 234464a (main when the brief was written): §10.9 has no `over_quota` or `pluck_mismatch`.
   - `c9fe9cdc0a401c9875aa1bf9dea46d5c52bcc041`, the head of PR #62 (issue #60) when this report was written; re-pin to the merge commit if #62 changes before it lands. It adds both, gives supersession marks their own per-key limit (§7.4), restates mark retention (§7.8), checks a PLUCK against its held target (§7.7), and adds §23.2 question 21.
7. **Q7. Config posture.** Do you accept JSON5 under `.config`, and Gateway boot refusal when a canticle block is schema-invalid? The alternative is a core change that disables just that plugin (oc/src/config/validation-plugin-config.ts:345-395).
8. **Q8. Trust tier.** Third-party install, or bundled/trusted official? This decides access to `openKeyedStore`, doctor health checks and the trusted diagnostics channel (oc/src/plugins/registry-runtime.ts:202-220; oc/src/flows/bundled-health-checks.ts:105-111).
9. **Q9. Banner marker.** `[canticle:heard]` (RFC) or `[binary-canticle]` (demand) (C6)?
10. **Q10. Receptor transport and executable.**
    - Is a stdout JSON-lines child acceptable for P1, instead of the §14.15 host socket?
    - How are the Python ≥3.11 runtime and the `cryptography` pins frozen for the exact-SHA proof packet? The CLI's version is a static `0.1.0` (bc/prototype/canticle-station/pyproject.toml:7).
11. **Q11. Rejected frames.** Per-frame records for unverified datagrams (demands 5.1 and 5.2), kept in a local debug ring and never deliverable? Or counters only, per §10.9 (rfc:1075-1076) (C22)?