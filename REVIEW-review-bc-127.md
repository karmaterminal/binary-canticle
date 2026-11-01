# Adversarial Review: binary-canticle #127

**Verdict: REQUEST_CHANGES**

One MAJOR lifecycle-identity bug remains. The lower candidate and OC-0 ledgers compare session ID and lifecycle revision correctly, but the binding's reset/delete path can use a same-ID route to erase successor taint and checkpoints from the binding state when a delayed callback carries an older lifecycle revision.

## Named refs

| category | ref | full SHA | local/tracking/server equality |
|---|---|---|---|
| product/base | PR #127 base `feat/canticle-discover-rune-20261030`; PR head `579b87e39787bdc583a184be88294781ef64cf05` | base `d910ec297ef97ec599b9e8d9024d54e9ff6982bc`; head `579b87e39787bdc583a184be88294781ef64cf05` | head is this worktree HEAD |
| lane | `codeagent/review-bc-127` | `579b87e39787bdc583a184be88294781ef64cf05` | local = `origin/codeagent/review-bc-127` = worktree HEAD |
| CI/workflow | `cd prototype/openclaw-canticle && node --test 'test/*.test.ts'` | N/A | N/A |
| presentation | N/A | N/A | N/A |
| docs/proof | N/A | N/A | N/A |

## Findings

| severity | path:line | finding |
|---|---|---|
| MAJOR | `prototype/openclaw-canticle/src/binding.ts:616-638`, `prototype/openclaw-canticle/src/binding.ts:641-648`, `prototype/openclaw-canticle/index.ts:55-64` | A delayed same-ID reset/delete can erase successor taint and checkpoint state. `resetSession()` clears `st.taint[sessionId]`, `st.taint[key:sessionKey]`, and `st.checkpoints[sessionKey]` without comparing the callback's `lifecycleRevision` with the route proof's current lifecycle revision. Because `currentIsEnded` compares only `proof.sessionId === sessionId`, a callback for old revision `r-old` arriving after the host has moved the same session ID to `r-new` is treated as ended. Concrete scenario: the route currently proves `{sessionId:"same", lifecycleRevision:"r-new"}` and the successor has read content/created a checkpoint; an out-of-order `session_reset` event for `{sessionId:"same", lifecycleRevision:"r-old"}` reaches the plugin. The plugin clears successor taint and the successor checkpoint. `deleteSession()` calls the same reset path before deleting exact ledger rows, so the stale delete has the same state-erasure risk. The candidate and OC-0 ledgers themselves preserve successor entries, but the binding taint/checkpoint composition is not generation-safe. |

## Per-property check

| property | result | paths |
|---|---|---|
| Read subscriptions are not ambient consent | Sound | `prototype/openclaw-canticle/src/config.ts:24,35,72,86-122,170`; `prototype/openclaw-canticle/src/candidates.ts:24-38,210-219`; `prototype/openclaw-canticle/test/subscriptions.test.ts:14-31,34-75`; `prototype/openclaw-canticle/test/candidates.test.ts:26-28,89-115` |
| Ambiguous dual configuration is refused | Sound | `prototype/openclaw-canticle/src/config.ts:86-122`; legacy top-level `subscriptions` is rejected at `prototype/openclaw-canticle/src/config.ts:90-92`; `prototype/openclaw-canticle/test/candidates.test.ts:25-28`; `prototype/openclaw-canticle/test/subscriptions.test.ts:14-18` |
| Untuned default | Sound | `prototype/openclaw-canticle/src/config.ts:72,93-122,170`; no read subscriptions or ambient delivery is created by default; default `listen.tune` is `["*:*"]` only for the global listen view, while exact read subscriptions remain empty. |
| Agent ID alone is not a session | Sound | `prototype/openclaw-canticle/src/tools.ts:151-163`; `prototype/openclaw-canticle/src/binding.ts:535-546,551-589`; `prototype/openclaw-canticle/src/config.ts:42,196-211`; anonymous callers and shared/main keys are rejected as exact sessions. |
| Reset/delete before ambient delivery | MAJOR finding above | lifecycle registration and callback validation: `prototype/openclaw-canticle/index.ts:55-64,66-71,86-87`; reset/delete implementation: `prototype/openclaw-canticle/src/binding.ts:616-648`; candidate callbacks: `prototype/openclaw-canticle/src/candidates.ts:193-208`; slot callbacks: `prototype/openclaw-canticle/src/ambient-slots.ts:196-215`; tests: `prototype/openclaw-canticle/test/plugin.test.ts:401-440`, `prototype/openclaw-canticle/test/candidates.test.ts:234-261`, `prototype/openclaw-canticle/test/ambient-slots-races.test.ts:78-133` |
| Identity comparison at every ambient admission point | Mostly sound; binding taint/checkpoint reset gap found | candidate route proof and persisted rows: `prototype/openclaw-canticle/src/candidates.ts:67-73,111-168,213-227`; slot route proof and reconcile/sync: `prototype/openclaw-canticle/src/ambient-slots.ts:91-166`; binding sync: `prototype/openclaw-canticle/src/binding.ts:450-474`; lifecycle reset gap remains at `prototype/openclaw-canticle/src/binding.ts:616-638` |

## Coverage and race paths

- Config/start/reload: service fails closed if lifecycle callbacks are absent for ambient subscriptions; ringbuffer-only starts without them (`prototype/openclaw-canticle/index.ts:82-97`, `prototype/openclaw-canticle/test/plugin.test.ts:385-399`).
- Persisted reload: candidate and slot ledgers validate and reload; in-flight reset/retract/run fences are covered in candidate tests.
- Candidate/slot admission: all ambient operations require route proof plus session ID and lifecycle revision (`prototype/openclaw-canticle/src/candidates.ts:67-73,213-219`; `prototype/openclaw-canticle/src/ambient-slots.ts:91-166`).
- Partial host failure: lost OC-0 replies remain durable and reconcile on restart; route-loss and supersede refusal paths fail closed.
- Missing same-ID binding-state regression: existing tests cover same-ID candidate/slot revision changes and delayed old-generation reset for ledgers, but the plugin binding taint/checkpoint reset path is not exercised with a current route revision that differs from the callback revision.

## CI receipt

- Command: `cd prototype/openclaw-canticle && node --test 'test/*.test.ts'`
- Result: 129 tests passed, 0 failed.
- Exact count: 129/129 pass.
- Mode: focused CI command specified by the workorder. No Mode-B broad fork CI was used.
- No baseline rerun was needed because the requested CI command was green.
