# Review: OpenClaw Canticle discovery and session subscriptions

| PR | Head | Verdict | Reason |
|---|---|---|---|
| #124 | d910ec297ef97ec599b9e8d9024d54e9ff6982bc | REQUEST_CHANGES | DNS browsing has no whole-call time ceiling and does not fail closed on conflicting duplicate TXT keys. |
| #127 | 23e210c42df7d92dff21ffb0609450b7f86da9fa | REQUEST_CHANGES | The durable session-targeted implementation exists, but the production plugin exposes no session-end/reset/delete lifecycle hook, so teardown and taint cleanup are not guaranteed on session end. |

## Named refs

| Category | Ref | Full SHA / state |
|---|---|---|
| Product | karmaterminal/binary-canticle #124 | d910ec297ef97ec599b9e8d9024d54e9ff6982bc; base fc383d0215f9e7ac1d8c2f684254f7d132515ce2 (`feat/dns-sd-browse-rune-20261030`) |
| Product | karmaterminal/binary-canticle #127 | 23e210c42df7d92dff21ffb0609450b7f86da9fa; base d910ec297ef97ec599b9e8d9024d54e9ff6982bc (`feat/canticle-discover-rune-20261030`) |
| Lane | `codeagent/bc-review-openclaw-seam` | local 23e210c42df7d92dff21ffb0609450b7f86da9fa; tracking 23e210c42df7d92dff21ffb0609450b7f86da9fa; server 23e210c42df7d92dff21ffb0609450b7f86da9fa |
| CI/workflow | Repository OpenClaw touched-test runner | N/A for a workflow ref; focused local proof used `node --test` on touched discovery/subscription test files |
| Presentation | N/A | N/A |
| Docs/proof | N/A | N/A |

Both PR base and head SHAs were resolved with `gh api repos/karmaterminal/binary-canticle/pulls/<n>`. The lane branch was published unchanged before evidence.

## PR #124: bounded read-only DNS-SD discovery

### [HIGH] No whole-browse time ceiling

**Location:** `prototype/openclaw-canticle/src/discover.ts:73-83`

**Failure scenario:** A cataloged station has a PTR row that matches 32 catalog entries, and every instance's SRV and TXT lookup is slow. `browse()` processes instances one at a time and each `Promise.all` can wait up to the 2-second DNS timeout from `prototype/openclaw-canticle/src/discover.ts:27-30`, so one tool call can consume roughly 64 seconds (32 instances * 2 seconds). No outer deadline applies, despite the stated bound that a discovery call has count, bytes, and time limits.

**Why this is wrong:** The implementation bounds individual DNS operations and the output count, but it does not bound the duration of the complete browse. This can make one read monopolize a session/tool call and exceeds the review's required delivery bound.

**Suggested fix:** Apply one absolute deadline at entry to `browse()`, pass a remaining-budget deadline to `query()`, and return a bounded/truncated result or refusal once that budget expires. Do not start SRV/TXT work after the deadline; test a 32-instance slow-DNS case against a deterministic whole-call deadline.

### [MEDIUM] Duplicate TXT hints are silently resolved as "first wins"

**Location:** `prototype/openclaw-canticle/src/discover.ts:90-92`

**Failure scenario:** The TXT record for a cataloged instance contains `sid=<correct-key-id>` and later `sid=<wrong-key-id>`, or similarly conflicting `k`/`streams` values. The parser leaves `hints` unchanged on the second key because `hints.has(...)` is true and then uses the first value. It does not set `invalid` or emit a mismatch, so it can claim DNS agrees when the record contains contradictory TXT input.

**Why this is wrong:** Duplicate input is not refused and the result is guessed as first-wins. A DNS locator hint must be ambiguous rather than treated as authoritative.

**Suggested fix:** Mark a TXT row invalid when a key is repeated, or reject the entire TXT bundle for duplicate keys. Emit `txt-invalid` and do not use any ambiguous hint as a matching value. Add a deterministic test with conflicting duplicate `sid`, `k`, and `streams` entries.

## PR #127: session-targeted subscriptions

### [HIGH] Session-end teardown is implemented but not wired into the plugin lifecycle

**Location:** `prototype/openclaw-canticle/index.ts:41-95`; callable reset/delete boundaries at `prototype/openclaw-canticle/src/binding.ts:543-566`

**Failure scenario:** A subscription targets `agent:main:local:task`, a frame is admitted and a pending/consumed OC-0 slot remains in `ambient-slots.json`, and the host session ends or is deleted. `Binding.resetSession()` and `Binding.deleteSession()` can clear candidate, taint, tombstone, and slot state, but `index.ts` registers only tool and service lifecycle callbacks. It never calls either method or another teardown callback. In production, session end therefore leaves persisted ambient/candidate state and taint for a session that no longer exists.

**Why this is wrong:** The PR's exact-session and teardown claims are not complete at the plugin composition boundary. Unit tests call `resetSession()` and `deleteSession()` directly, but no test proves the production plugin receives or handles host session lifecycle events. A stale target can remain until route proof or later pruning acts on it, and session deletion may not remove its admission history.

**Suggested fix:** Add the real host lifecycle seam to `PluginApi`, register handlers for session `/new`, reset, disable, and deletion, and call `Binding.resetSession()` / `Binding.deleteSession()` with the exact session key and session ID. Fail closed if the lifecycle callback cannot prove the host cleared pending injections. Add an integration test that starts the plugin, creates exact-session state, invokes the production lifecycle callback, and proves the target's candidate, ambient, taint, and tombstone state is removed or reset as intended.

## Coverage and bounds checklist

- **#124 bounds:** PTR is capped at 32 input instances and 8 output stations, the catalog is capped at 128 entries, each DNS query is 2 seconds and cache entries are bounded at 128 records. A whole-browse absolute deadline is the missing case.
- **#124 fail-closed:** Catalog/domain/public stream validation is strict. The conflicting duplicate TXT key case above is not strict.
- **#124 exact session:** Not applicable; discovery is read-only and has no session-target delivery.
- **#124 secret/private content:** No heard payload is read or returned. DNS mismatch and catalog metadata only are returned.
- **#124 tests:** Existing tests cover empty catalog, catalog-only public streams, TTL, out-of-zone targets, 8-result caps, and typed DNS bounds, but no test enforces a whole-call deadline or conflicting duplicate TXT keys.
- **#127 bounds:** 64 subscriptions, 32 exact targets/subscription, 600 per-hour/subscription-target, 4096 pending candidates, 8192 settled rows, 8192 OC-0 entries, 5 items and 1536 bytes/slot are implemented.
- **#127 session exactness:** Candidate and OC-0 paths key state by exact `sessionKey`, and route proof requires `proof.sessionKey === sessionKey`, `exists === true`, and `onHost === true`. No production session named in the diff is used as a wildcard target.
- **#127 teardown:** Direct reset/delete methods exist, but their host lifecycle call path is absent.
- **#127 untrusted content:** Ambient candidate text is metadata only (`station`, `stream`, class, scope, lens, item, expiry); consumed retraction creates metadata-only withdrawal notes. No heard payload is copied into OC-0 slots.
- **#127 tests:** Tests cover route denial, exact filters, per-hour and slot budgets, rejoin, retract, reset, delete, lost replies, and landing/race behavior. They do not exercise the absent production session lifecycle callback.
- **No secret/private content:** The PR diffs and tested paths do not include keys or secrets in logs/broadcast payloads; DNS public keys are cataloged public Ed25519 keys. Candidate OC-0 text contains metadata, not framed payload text.

## Validation

Focused local test proof:

`cd prototype/openclaw-canticle && node --test test/discover.test.ts test/candidates.test.ts test/ambient-slots.test.ts test/ambient-slots-races.test.ts test/ambient-binding.test.ts test/oc0-host.test.ts test/inbound.test.ts test/plugin.test.ts`

Receipt: 55 tests passed, 0 failed. This lane used focused-only CI, not a broad suite or Mode-B workflow.
