# Adversarial read-only review: reconciled read and delivery subscriptions

## Verdict

**NEEDS CHANGES (BLOCKER).** PR #127 keeps read scope and delivery as separate planes and has a generally strong exact-session, route-proof, and bounded-ledger implementation. It is not merge-safe as an ambient-delivery design because its only reset/delete implementation is unreachable from the host lifecycle: a session reset or delete leaves ambient admission, taint, and/or tombstone state under host and in-process activity. The ambient seam is also not fail-closed at start for the lifecycle requirement. The work item in the PR context correctly says host lifecycle wiring must precede enabling ambient delivery.

## Named refs

| Category | Ref | Full SHA | Local/tracking/server equality |
|---|---|---|---|
| Product/base | PR #127 base branch `feat/canticle-discover-rune-20261030` | `d910ec297ef97ec599b9e8d9024d54e9ff6982bc` | base SHA from `gh api repos/karmaterminal/binary-canticle/pulls/127`; lane and tracking at the PR head |
| Product/head | PR #127 head `feat/canticle-subscriptions-rune-20261030` | `1e5fc499b57dd4c5f26bd5f14cc68f7c176a2a41` | `git rev-parse HEAD`, PR head, origin PR-head branch, and origin lane all equal |
| Lane/safe branch | `codeagent/bc-review-subscriptions-reconciled` | `1e5fc499b57dd4c5f26bd5f14cc68f7c176a2a41` | published unchanged to `origin` before evidence |
| CI/workflow | CI is the workorder command, no separate workflow dispatch | `N/A` | Worktree at the PR head; no workflow ref applies |
| Presentation | `N/A` | `N/A` | read-only review |
| Docs/proof | `N/A` | `N/A` | read-only review |

## Findings

### 1. [BLOCKER] Host reset/delete never calls the teardown methods

**Invariant / composition boundary:** once a session is reset or deleted, its host lifecycle must atomically clear candidate admission, OC-0 pending/settled state, taint, and session-local tombstones. The owner of this boundary is the plugin host seam (`prototype/openclaw-canticle/index.ts`) plus `Binding.resetSession/deleteSession`; persisted projection owners are `Candidates` and `AmbientSlots`.

`Binding.resetSession` and `Binding.deleteSession` exist and clear both projections at `src/binding.ts:554-577`. `Candidates.resetSession/deleteSession` exist at `src/candidates.ts:177-187`, and `AmbientSlots.reset/deleteSession` exist at `src/ambient-slots.ts:141-158`. However, no host callback, service API call, tool call, or service lifecycle path invokes them. The only references to those public binding methods are their definitions and direct tests; in particular `index.ts:43-94` exposes only `start`/`stop`.

**Concrete failure:** configure a host that supplies both `resolveLocalSessionRoute` and the three OC-0 workflow methods. The service starts the ambient adapter (`index.ts:67-78`). A session consumes a Canticle item, becomes tainted, and its OC-0/ambient state is persisted. `/new` resets or the host deletes the session, but because no callback calls `Binding.resetSession` or `Binding.deleteSession`, the persisted taint and ledger entries remain. Reconnect/restart can rebuild or reconcile stale session state instead of the session having been reset.

**Start behavior:** ambient delivery is **not** refused at start. `Binding.start` preflights routes and creates `AmbientSlots` whenever both seams are present (`src/binding.ts:124-125, 250-254`). `index.ts:67-78` wires it when the route-proof and all workflow methods exist. It does not require lifecycle callbacks.

**Fix:** before ambient `delivery: "ambient"` is enabled, register and verify real host callbacks for reset and delete and call both with the exact canonical `sessionKey` (and `sessionId` for taint reset). Fail closed if either callback seam is unavailable; add a reset/delete integration test that crosses the host callback, `Binding`, `Candidates`, `AmbientSlots`, and disk reload. Do not accept only unit calls to `AmbientSlots.reset/deleteSession`.

**Missing regression:** no test fails if host `/new` or session deletion stops calling teardown. `test/ambient-slots.test.ts:112-129` tests direct ledger reset/delete, and `test/inbound.test.ts:339-341` tests direct binding reset taint. Neither proves the host lifecycle reaches those methods.

### 2. [HIGH] Unknown and ambiguous nested config values are not refused by the start parser

**Invariant / composition boundary:** the start parser is the final authority for config semantics and must reject unknown keys, the legacy top-level key, and contradictory/duplicate values. The manifest is an additional boot-time gate, not the parser's substitute.

The manifest's `additionalProperties: false` rejects unknown top-level and nested keys, and `test/plugin.test.ts:363-364` covers an unknown top-level key. The runtime parser also rejects the explicit legacy top-level key (`src/config.ts:77-79`) and duplicate delivery IDs/targets (`src/config.ts:94-113`), but it does not reject unknown keys in `obj`, `listen`, `delivery`, or subscription objects. Unknown fields in a nested config are silently ignored and existing defaults remain (for example a misspelled `deliviery` key is ignored).

**Concrete failure:** a host can bypass or race the manifest's boot schema and pass `delivery.subscriptions[0].deliviery: "ambient"` or an unknown target field. `parseConfig` returns `ringbuffer_only` or ignores the field instead of refusing start. The operator believes ambient consent is configured, while no ambient candidate is admitted.

**Fix:** add explicit allowed-key sets and reject unknown keys in every config object the parser reads, including nested delivery/listen/station/publish/discovery entries. Add parser tests for unknown delivery, target, listen, and legacy nested fields. Reconcile this with `openclaw.plugin.json` so the manifest and parser have exactly the same keys.

**Missing regression:** `test/plugin.test.ts:363-364` proves manifest unknown-key rejection, but no test calls `parseConfig` with unknown nested keys and asserts `ConfigError`.

## Path enumeration

### Plane separation

Every property has a separate owner:

- `listen.subscriptions` is parsed only in `subscriptionsOf` (`src/config.ts:161-174`) and consumed only by read visibility at `Binding.subscribed` and presence/status paths (`src/binding.ts:539-542, 774-776, 877-880`). It never reaches `Candidates`, whose constructor receives only `cfg.delivery.subscriptions` (`src/binding.ts:124`).
- `delivery.subscriptions` is parsed only as `delivery.subscriptions` (`src/config.ts:75-113`) and passed only to `Candidates` (`src/binding.ts:124`) and receiver ambient matching (`src/binding.ts:139-140, 333-334`). Read tools do not inspect it.
- The legacy top-level `subscriptions` key is explicitly rejected (`src/config.ts:77-79`). There is no migration that converts it into read scope or delivery consent.
- The untuned default is preserved: `listen.subscriptions` defaults to `[]` and `delivery.subscriptions` defaults to `[]` (`src/config.ts:54, 94-113, 137-148`). Both planes therefore remain read-only/explicit and untuned by default.
- A dual configuration of both tables is intentionally two explicit policies, not a conversion; configuring a read subscription does not set delivery consent. An old top-level key is refused.

No current code path turns `listen.subscriptions` into ambient consent or `delivery.subscriptions` into read scope.

### Exact-session and caller construction

- `ToolContext` carries `sessionKey`, `sessionId`, and `agentId`; only `sessionKey` identifies a session (`src/tools.ts:15-16, 157-163`).
- `callerOf` rejects missing/blank `sessionKey` as anonymous even if `agentId` is present (`src/tools.ts:157-163`). It also is the boundary used by every tool factory (`src/tools.ts:175-178`).
- Anonymous callers cannot make read `new`/item calls, publishing calls, or receive subscribed ambient items (`src/binding.ts:596-600, 1028-1032, 1151-1154`). Agent ID alone is not tested as delivery authority.
- Delivery targets are canonical exact keys enforced by `TARGET_SESSION_KEY` and rejected for wildcard/shared main (`src/config.ts:8-9, 84-91`). Duplicate target keys in one subscription are rejected (`src/config.ts:92`). Duplicate subscription IDs are rejected globally (`src/config.ts:112`).
- Candidate admission refreshes the host route and requires `proof.sessionKey === sessionKey`, `exists === true`, and `onHost === true` (`src/candidates.ts:46-62, 102-125`). A mismatch, rejection, or missing proof admits nothing.
- `candidates.targetSessions()` contains only the configured exact target keys (`src/candidates.ts:188-190`); it is consumed by `syncAmbient` (`src/binding.ts:434-462`).

The exact-session invariant is retained from #121 and has direct tests for agent ID alone and anonymous callers (`test/plugin.test.ts:89-104, 195-205`; `test/candidates.test.ts:21-28, 122-129, 150-163`).

### Teardown

No caller in `index.ts`, the plugin service, tools, or any host callback calls `resetSession` or `deleteSession`. The only direct callers found are direct tests and the internal `deleteSession` call to `resetSession` in `src/binding.ts:571-577`. Therefore teardown is not wired to host lifecycle at this head.

### Bounds and persistence

- 64 delivery subscriptions, 32 targets/subscription, 64 filter values, 600 per-hour target/subscription, 4,096 candidate rows, 8,192 settled keys, 2,048 spend keys, two logical slots, five items/slot, and 1,536 bytes/slot are coded (`src/config.ts:81-113`; `src/candidates.ts:8-12, 29-44, 124-125, 188-211`; `src/ambient-slots.ts:38-72`).
- Candidate reload rejects a foreign binding, out-of-bounds pending/settled/spend maps, invalid row shapes, and prunes expired or unsubscribed rows (`src/candidates.ts:29-44, 78-96`).
- Ambient reload caps the entry count at 8,192 and five frames/entry (`src/ambient-slots.ts:38-72`) and reconciles persisted entries before daemon connection at `src/binding.ts:250-254`.
- Persistence and restart behavior is covered by lost-reply, rejoin, revoke, retraction, and tombstone tests (`test/candidates.test.ts:92-119, 137-148`; `test/ambient-slots.test.ts:18-129`; `test/ambient-binding.test.ts:31-215`).

The review found no normal-code path that exceeds the listed runtime caps. The persisted ambient ledger reload should, however, be hardened to validate exact canonical session keys and bounds for `settled`, `tainted`, and `notes` map sizes and frame bytes, because `load` currently validates less than `sync` (`src/ambient-slots.ts:38-72`). This is a **MEDIUM** persistence-hardening gap, especially for corruption or stale unreviewed state.

## Severity summary

| Severity | Count | Finding |
|---|---:|---|
| BLOCKER | 1 | Host reset/delete lifecycle is unwired; ambient delivery can start without it |
| HIGH | 1 | Runtime start parser ignores unknown nested config keys |
| MEDIUM | 1 | Ambient ledger reload does not validate all persisted map and byte bounds |

### 3. [MEDIUM] Ambient persisted reload under-validates its maps

**Concrete failure:** a torn or maliciously altered local ledger can reload entries with arbitrary exact-session strings, a 64 KB frame line, or arbitrarily large `settled`, `tainted`, or `notes` maps. `load` validates only entry count, frame count, and basic frame types (`src/ambient-slots.ts:38-72`). It does not enforce the 1,536-byte slot bound or canonical session key on reload until later sync logic.

**Fix:** validate every entry's exact canonical session key, deadline/retention/status, frame key/line byte bounds, and map sizes (`settled`, `tainted`, `notes`) in `load`; fail the binding as unreadable if any bound is exceeded. Add restart tests that reload each malformed form and verify no host call occurs.

**Missing regression:** no test reloads each over-bound or malformed ambient ledger field. `test/ambient-slots.test.ts` covers entry, lost reply, reset, delete, and 5-frame behavior, but not persisted map/key/byte corruption.

## Missing coverage matrix

| Property | Existing test that fails on breakage? | Gap |
|---|---|---|
| Read vs delivery plane remains separate | `test/subscriptions.test.ts:14-27, 29-55`; `test/candidates.test.ts:122-129` | No start parser test for both tables, duplicate session keys across them, or unknown nested fields |
| Legacy top-level key refused | `test/subscriptions.test.ts:14-27`; `test/candidates.test.ts:20-28` | Covered |
| Duplicate listen keys/target IDs | `test/subscriptions.test.ts:14-27`; `test/candidates.test.ts:20-28` | Covered at parser level |
| Unknown config keys | top-level schema test only (`test/plugin.test.ts:363-364`) | Nested parser unknown fields not tested |
| Agent ID alone/anonymous delivery | `test/plugin.test.ts:195-205`; candidate route-proof tests | Covered for tools and route proof; no ambient host callback test with agentId-only |
| Session reset/delete lifecycle | Direct ledger tests only (`test/ambient-slots.test.ts:112-129`; `test/inbound.test.ts:339-341`) | Missing host callback -> binding -> both ledgers -> reload integration test |
| Persisted candidate bounds | Candidate load and restart tests (`test/candidates.test.ts:92-119, 137-148`) | Corrupt malformed spend/timestamp and out-of-range lens not byte-tested |
| Persisted ambient bounds | Entry count/slot tests (`test/ambient-slots.test.ts:18-129`) | Missing canonical-key, map-size, and line-byte reload tests |

## Validation

- PR head read at `1e5fc499b57dd4c5f26bd5f14cc68f7c176a2a41`.
- `cd prototype/openclaw-canticle && node --test 'test/*.test.ts'`: 116 tests passed, 0 failed.
- The suite does not replace the host-lifecycle and parser-boundary findings above.
