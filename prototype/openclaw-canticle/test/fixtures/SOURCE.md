# Composed local-reader regression provenance

`core-local-route-21660b21.ts.source` is the unchanged 6,000-byte source of
[`src/plugins/local-session-route.ts`](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/plugins/local-session-route.ts)
at OpenClaw PR #1511 head `21660b2182062a9a98eb28d46341283100c082e6`, retrieved on 2026-11-21.

SHA-256: `a310deb120fbe5b0fe2f8dfba49bd133babab049f32af2ee50cff41bb71c5f46`.

The `.source` suffix excludes this third-party file from this repository's TypeScript build. The regression
copies its unchanged bytes to a temporary `.mts` file and imports it through Node's TypeScript support.
Changing the expected hash without checking the upstream source changes the evidence and must be reviewed.
The accompanying `OPENCLAW-LICENSE` retains its upstream MIT notice.

## What runs and what is a fixture

`../local-reader.test.ts` runs the actual plugin `createTool` / `callerOf`, `Binding`, `Receiver`, journal,
taint persistence and config parser together with that actual core resolver decision function.
Synthetic receptor records supply the known payload. The core resolver's imported row, placement and active
binding storage adapters are explicitly replaced by `../core-reader-fixture-host.ts`, which uses temporary
persisted fixture rows. The module hook permits only the seven known runtime imports from that exact source.

Lease acquisition and daemon startup are explicit no-network fixtures in this regression. They do not
establish lock exclusivity, socket ownership, transport, worker execution, a live OpenClaw host, a fleet
installation or host tool-policy enforcement. Those retain their independent integration/live proof gates.
No model, prince session, actual station, credentials or live payloads are used.

This is stronger than replacing the resolver with `onHost: true`: the real branch that rejects main, channel,
cron/hook, external bindings, legacy route hints and remote placement runs, as does its second row-identity
read after awaited storage operations. It is narrower than a composed real-host receipt. #145 must not be
closed on this result alone; Rune retains ownership of that proof and review.

The trusted context fields used by the patch exist in
[`src/plugins/tool-types.ts` at the same head](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/plugins/tool-types.ts).
This fixture supplies them explicitly; it does not prove the running host supplies them or that
`sandboxed: true` prevents a parent result/announce route. Payload grants remain behind those host checks.

## Production factory and callback composition — 21 November 2026

`../core-wrapper-reader.test.ts` adds the production Canticle `index.ts` registration/service to the
same real route decision. The registered factories run through these **unchanged upstream source files**,
also retrieved from `karmaterminal/openclaw@21660b2182062a9a98eb28d46341283100c082e6`:

| File under upstream `src/plugins/` and this directory's `openclaw-21660b21/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `tool-factory-context.ts` (`.source` locally) | 3463 | `b96ba524045050273de20ef0f9ed386beab5effbfcf30dac503b3add16bf089d` |
| `tool-factory-runtime.ts` (`.source` locally) | 8918 | `2f81f1fabfe7816acc6320bb32f8221e8bfcae38ce9385765c3d0c3ad1306293` |
| `registry-lifecycle.ts` (`.source` locally) | 22754 | `74e604827d3e7189c53fa4c83aaedb05f0151b9b010f7caa845e03e530f96da9` |
| `plugin-instance-scope.ts` (`.source` locally) | 10328 | `076fa2b7bdc24bc43b5b97dc05aa7b5f99b295d465f504d4e7950a88b689e930` |

`../core-wrapper-loader.ts` verifies every hash before loading temporary `.mts` copies and permits only
the reviewed import list. The real `createPluginToolFactoryContext`, factory resolver and
`bindPluginToolCallbacks` now run. Their captured lifecycle authority and record revocation use the real
registry and instance-owner code. The no-admitted-run case verifies the V1 factory's lifecycle-only guard
does **not** become invocation authority. The post-result case ends the fixture run immediately after
the actual Binding produces its result: the core callback wrapper withholds that result, while conservative
taint remains. This is evidence of a withheld return, not an actual session encounter.

`../core-wrapper-fixture-host.ts` supplies the remaining environment: local singleton storage, scoped callback
invocation, non-policy decoration/logging, and absent memory/runtime state. Unexercised services throw.
These adapters do not implement the tested factory, callback, record-lifecycle or route decisions. They
also do not prove full plugin instance execution scope, the Gateway's admitted-run producer, actual sandbox
selection, tool allowlists, cancellation transport, parent handoff or room egress. The synthetic admitted
run and sandbox bit are still labelled fixtures. Lease and daemon startup remain no-network fixtures;
signed transport remains in the separate interop suite.

All vendored files remain under the accompanying upstream MIT notice. This is a stronger **offline source
composition** receipt, not a live-host receipt and not closure of #145 or #156.

To run both source-composition suites and produce a machine-readable receipt (Node 24 or 26, no inference,
no network, temporary disposable state, 60-second hard subprocess bound):

```sh
node prototype/openclaw-canticle/proofs/core-reader.mjs --output /tmp/canticle-reader-receipt.json
```

The output path must be outside the repository and must not exist; its `.tap` companion is also exclusive.
Exit 0 requires every selected test to pass with zero skips, cancellations or todos. The receipt pins the
Git head, worktree-dirty flag, exact input hashes, upstream source revision and all fixture/proof limits.
It contains synthetic proof metadata; no live transcript or station credential is read. Reviewers can
attach the JSON and TAP to the PR; do not promote its `result: pass` to a live launch receipt.

Run from the repository root with Node 24 or 26:

```sh
node --test prototype/openclaw-canticle/test/local-reader.test.ts
```
