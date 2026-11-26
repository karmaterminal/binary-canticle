// #145 contribution: real core decision source + explicit fixture storage, actual caller/tool wrapper,
// actual Binding/Receiver and synthetic receptor records. No live host or model, no network publication.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { after, mock, test } from "node:test";
import { Binding } from "../src/binding.ts";
import { DaemonLink } from "../src/daemon.ts";
import { Lease } from "../src/store.ts";
import { parseConfig } from "../src/config.ts";
import { createTool, type ToolContext, type ToolName } from "../src/tools.ts";
import { RECORD_V } from "../src/records.ts";
import type { RouteProof } from "../src/candidates.ts";
import { Clock, frameFields, KEY_CAEL, removeDir, tempDir } from "./helpers.ts";
import { afterNextRowRead, selectStore, writeStore } from "./core-reader-fixture-host.ts";

const fixtureRoot = tempDir();
// This is a no-network composed decision regression. Lease exclusivity and daemon transport have their
// own integration suites; do not let these two fixtures turn this into a claimed real-host receipt.
const leaseFixture = mock.method(Lease.prototype, "acquire", async () => undefined);
const daemonFixture = mock.method(DaemonLink.prototype, "start", () => undefined);
const source = readFileSync(join(import.meta.dirname, "fixtures/core-local-route-21660b21.ts.source"));
const sourceHash = createHash("sha256").update(source).digest("hex");
// This hash is checked against the vendored source provenance, not reconstructed resolver logic.
assert.equal(sourceHash, "a310deb120fbe5b0fe2f8dfba49bd133babab049f32af2ee50cff41bb71c5f46");
const resolverFile = join(fixtureRoot, "core-resolver.mts");
writeFileSync(resolverFile, source);
const resolverUrl = pathToFileURL(resolverFile).href;
const fixtureHost = new URL("./core-reader-fixture-host.ts", import.meta.url).href;
const allowedImports = new Set([
  "../config/sessions/main-session.js", "../config/sessions/paths.js",
  "../config/sessions/session-entry-read-runtime.js", "../gateway/session-store-key.js",
  "../gateway/worker-environments/placement-record.js", "../gateway/worker-environments/placement-store.js",
  "../infra/outbound/session-binding-service.js",
]);
const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
  if (context.parentURL !== resolverUrl) return nextResolve(specifier, context);
  assert.ok(allowedImports.has(specifier), `unexpected runtime dependency ${specifier}`);
  return { url: fixtureHost, shortCircuit: true };
} });
const core = await import(resolverUrl) as { resolvePluginLocalSessionRoute: (p: { cfg: unknown; sessionKey: string }) => ReturnType<RouteProof> };
hooks.deregister();
after(() => { leaseFixture.mock.restore(); daemonFixture.mock.restore(); removeDir(fixtureRoot); });

const key = "agent:rune:subagent:town-reader";
const identity = { sessionKey: key, sessionId: "reader-id-1", lifecycleRevision: "revision-1" };
function config() {
  return {
    binding: "town-reader", daemon: { socket: join(fixtureRoot, "absent-daemon.sock") },
    listen: { localReader: { ...identity }, payloadSessions: [key], subscriptions: [{ sessionKey: key, tune: ["cael:chatter"] }] },
  };
}
function row(extra: Record<string, unknown> = {}) { return { sessionId: identity.sessionId, lifecycleRevision: identity.lifecycleRevision, ...extra }; }

async function setup(options: { isolated?: boolean; proof?: RouteProof } = {}) {
  const dir = tempDir(); const clock = new Clock();
  const storePath = join(dir, "sessions.json"); selectStore(storePath); writeStore({ rows: { [key]: row() } });
  const raw = config();
  if (options.isolated === false) delete (raw.listen as { localReader?: unknown }).localReader;
  const cfg = parseConfig(raw);
  const proof: RouteProof = options.proof ?? ((sessionKey) => core.resolvePluginLocalSessionRoute({ cfg: { session: { store: storePath } }, sessionKey }));
  const binding = new Binding({ config: cfg, root: join(dir, "binding"), clock: clock.now, routeProof: proof, tickMs: 60_000 });
  await binding.start();
  const rec = (type: string, rec_seq: number, body: Record<string, unknown> = {}) => ({ v: RECORD_V, type, run: "fixture-run", rec_seq, ...body });
  binding.receiver.connected(true);
  binding.receiver.apply(rec("hello", 1, { join_snapshot: true }));
  binding.receiver.apply(rec("landing_state", 2, { mute: null, breaker: "closed" }));
  binding.receiver.apply(rec("snapshot_end", 2, { watermark: 2, count: 0, truncated: false, omitted: 0 }));
  binding.receiver.apply(rec("frame", 3, frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t, text: "the parcel arrived softly" })));
  const context: ToolContext = { sessionKey: key, sessionId: identity.sessionId, sandboxed: true, assertInvocationCurrent: () => undefined };
  function tool(name: ToolName, ctx = context) { return createTool(name, ctx, () => ({ binding, failure: null, publish: cfg.publish.enabled })); }
  const read = (ctx = context) => tool("canticle_listen", ctx)!.execute("read", { what: "on_air", view: "items" });
  const close = async () => { await binding.stop(); removeDir(dir); };
  return { binding, context, tool, read, close, proof, cfg, clock, stateRoot: join(dir, "binding") };
}

test("isolated local reader is opt-in and the baseline disjoint gates still refuse", async () => {
  const s = await setup({ isolated: false });
  try {
    assert.equal((await s.proof(key)).onHost, true);
    const result = await s.read();
    assert.equal(result.details.error, "payload_not_allowed");
    assert.doesNotMatch(result.content[0]!.text, /parcel arrived/);
  } finally { await s.close(); }
});

test("real core route decision composes with actual caller and tool wrapper for a scoped reader", async () => {
  const s = await setup();
  try {
    const result = await s.read();
    assert.equal(result.details.ok, true, JSON.stringify(result));
    assert.match(result.content[0]!.text, /the parcel arrived softly/);
    assert.match(result.content[0]!.text, /EXTERNAL_UNTRUSTED_CONTENT/);
    assert.match(result.content[0]!.text, /station="cael"/);
    const status = await s.tool("canticle_status")!.execute("status", {});
    assert.equal((status.details.canticle.session as { tainted: boolean }).tainted, true);
    assert.equal(s.tool("canticle_sing"), null, "read grant never grants publication");
    const mute = await s.tool("canticle_mute")!.execute("mute", { station: "cael", ttlSeconds: 60 });
    assert.equal(mute.details.ok, true, JSON.stringify(mute));
    const clear = await s.tool("canticle_mute")!.execute("clear", { clear: "all" });
    assert.equal(clear.details.ok, true);
    assert.equal((s.binding.status({ sessionKey: key, sessionId: identity.sessionId, subagent: true, anonymous: false }).details.session as { tainted: boolean }).tainted, true);
  } finally { await s.close(); }
});

test("missing sandbox, missing invocation guard, stale invocation and wrong caller generation refuse payload", async () => {
  const s = await setup();
  try {
    for (const context of [
      { ...s.context, sandboxed: false },
      { sessionKey: key, sessionId: identity.sessionId, sandboxed: true },
      { ...s.context, assertInvocationCurrent: () => { throw new Error("ended"); } },
      { ...s.context, sessionId: "old-reader" },
      { ...s.context, sessionKey: "agent:rune:main" },
      { ...s.context, sessionKey: "agent:rune:discord:channel:room" },
      { ...s.context, sessionKey: "agent:rune:subagent:other" },
    ]) {
      const result = await s.read(context); assert.equal(result.details.ok, false);
      assert.doesNotMatch(result.content[0]!.text, /parcel arrived/);
      const mute = await s.tool("canticle_mute", context)!.execute("mute", { clear: "all" });
      assert.equal(mute.details.ok, false, "an inadmissible caller cannot alter binding mutes either");
    }
  } finally { await s.close(); }
});

test("a positive locality boolean without the exact host row pair grants no payload", async () => {
  const invalidProofs = [
    { sessionKey: key, exists: true, onHost: true },
    { sessionKey: key, exists: true, onHost: true, sessionId: identity.sessionId },
    { sessionKey: key, exists: true, onHost: true, lifecycleRevision: identity.lifecycleRevision },
    { ...identity, sessionKey: "agent:rune:subagent:other", exists: true, onHost: true },
  ];
  for (const proof of invalidProofs) {
    const s = await setup({ proof: async () => proof });
    try {
      const result = await s.read();
      assert.equal(result.details.ok, false);
      assert.doesNotMatch(result.content[0]!.text, /parcel arrived/);
    } finally { await s.close(); }
  }
});

test("a payload read persists taint across restart while a changed host row revokes reading", async () => {
  const s = await setup(); let restarted: Binding | undefined;
  try {
    assert.equal((await s.read()).details.ok, true);
    await s.binding.stop();
    restarted = new Binding({ config: s.cfg, root: s.stateRoot, clock: s.clock.now, routeProof: s.proof, tickMs: 60_000 });
    await restarted.start();
    const get = () => ({ binding: restarted!, failure: null, publish: false });
    const status = await createTool("canticle_status", s.context, get)!.execute("status", {});
    assert.equal((status.details.canticle.session as { tainted: boolean }).tainted, true);
    writeStore({ rows: { [key]: row({ lifecycleRevision: "new-revision" }) } });
    const read = await createTool("canticle_listen", s.context, get)!.execute("journal", { what: "journal", view: "items" });
    assert.equal(read.details.error, "payload_not_allowed");
    assert.doesNotMatch(read.content[0]!.text, /parcel arrived/);
    const endedStatus = await createTool("canticle_status", s.context, get)!.execute("status", {});
    assert.equal((endedStatus.details.canticle.session as { tainted: boolean }).tainted, true);
  } finally { await restarted?.stop(); await s.close(); }
});

test("real resolver refuses external routes, remote placement, active external binding and absent rows", async () => {
  const s = await setup();
  try {
    const cases = [
      { rows: {} },
      { rows: { [key]: row({ delivery: { kind: "external" } }) } },
      { rows: { [key]: row({ deliveryContext: { channel: "discord" } }) } },
      { rows: { [key]: row() }, bindings: { [key]: [{ status: "active" }] } },
      { rows: { [key]: row() }, placements: { [identity.sessionId]: { sessionId: identity.sessionId, sessionKey: key, agentId: "rune", state: "active", turnOwner: "remote" } } },
      { rows: { [key]: row({ lifecycleRevision: "replaced" }) } },
      { rows: { [key]: row({ sessionId: "replacement-id" }) } },
    ];
    for (const state of cases) {
      writeStore(state); const result = await s.read();
      assert.equal(result.details.error, "payload_not_allowed");
      assert.doesNotMatch(result.content[0]!.text, /parcel arrived/);
    }
  } finally { await s.close(); }
});

test("row replacement during actual resolver awaits and invocation expiry after proof fail closed", async () => {
  const s = await setup();
  try {
    afterNextRowRead(() => writeStore({ rows: { [key]: row({ lifecycleRevision: "changed-during-proof" }) } }));
    assert.equal((await s.read()).details.ok, false);
    writeStore({ rows: { [key]: row() } });
    let checks = 0;
    const context = { ...s.context, assertInvocationCurrent: () => { if (++checks >= 4) throw new Error("turn ended during proof"); } };
    assert.equal((await s.read(context)).details.ok, false);
  } finally { await s.close(); }
});

test("isolated binding refuses second subscribers, ambient targets, publication and malformed grants", () => {
  const raw = config();
  assert.equal(parseConfig(raw).listen.localReader?.sessionId, identity.sessionId);
  const bad = [
    { ...raw, publish: { enabled: true }, station: { name: "rune", keyId: "1111111111111111" } },
    { ...raw, delivery: { subscriptions: [{ id: "any" }] } },
    { ...raw, listen: { ...raw.listen, payloadSessions: [key, "agent:rune:other"] } },
    { ...raw, listen: { ...raw.listen, subscriptions: [] } },
    { ...raw, listen: { ...raw.listen, subscriptions: [...raw.listen.subscriptions, { sessionKey: "agent:rune:subagent:other", tune: ["cael:chatter"] }] } },
    ...["agent:rune:main", "agent:rune:discord:channel:room", "agent:rune:subagent:*"]
      .map(sessionKey => ({ ...raw, listen: { ...raw.listen, localReader: { ...identity, sessionKey } } })),
    ...["", " ", "x".repeat(201)].map(sessionId => ({ ...raw, listen: { ...raw.listen, localReader: { ...identity, sessionId } } })),
  ];
  for (const value of bad) assert.throws(() => parseConfig(value));
});
