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

Run from the repository root with Node 24 or 26:

```sh
node --test prototype/openclaw-canticle/test/local-reader.test.ts
```
