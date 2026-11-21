// Production registration + unchanged core factory/context/callback/lifecycle sources.
// Row storage, daemon admission, lease and admitted-run producer are explicitly fixtures.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { after, mock, test } from "node:test";
import plugin from "../index.ts";
import { Binding } from "../src/binding.ts";
import { DaemonLink } from "../src/daemon.ts";
import { Lease } from "../src/store.ts";
import { RECORD_V } from "../src/records.ts";
import type { Tool, ToolContext, ToolName } from "../src/tools.ts";
import { frameFields, KEY_CAEL, removeDir, tempDir } from "./helpers.ts";
import { afterNextRowRead, selectStore, writeStore } from "./core-reader-fixture-host.ts";
import { loadCoreWrappers, type Registration, type Registry } from "./core-wrapper-loader.ts";

const fixtureRoot = tempDir();
const core = await loadCoreWrappers(fixtureRoot);
const routeBytes = readFileSync(join(import.meta.dirname, "fixtures/core-local-route-21660b21.ts.source"));
assert.equal(createHash("sha256").update(routeBytes).digest("hex"), "a310deb120fbe5b0fe2f8dfba49bd133babab049f32af2ee50cff41bb71c5f46");
const routeFile = join(fixtureRoot, "local-session-route.mts"); writeFileSync(routeFile, routeBytes);
const routeUrl = pathToFileURL(routeFile).href;
const storageImports = new Set([
  "../config/sessions/main-session.js", "../config/sessions/paths.js",
  "../config/sessions/session-entry-read-runtime.js", "../gateway/session-store-key.js",
  "../gateway/worker-environments/placement-record.js", "../gateway/worker-environments/placement-store.js",
  "../infra/outbound/session-binding-service.js",
]);
const hooks = registerHooks({ resolve(specifier, context, next) {
  if (context.parentURL !== routeUrl) return next(specifier, context);
  assert.ok(storageImports.has(specifier), `unreviewed core storage dependency: ${specifier}`);
  return { url: new URL("./core-reader-fixture-host.ts", import.meta.url).href, shortCircuit: true };
} });
type CoreRoute = { sessionKey: string; exists: boolean; onHost: boolean; sessionId: string | null; lifecycleRevision: string | null };
const route = await import(routeUrl) as { resolvePluginLocalSessionRoute: (params: { cfg: unknown; sessionKey: string }) => Promise<CoreRoute> };
hooks.deregister();

const leaseFixture = mock.method(Lease.prototype, "acquire", async () => undefined);
const daemonFixture = mock.method(DaemonLink.prototype, "start", () => undefined);
after(() => { leaseFixture.mock.restore(); daemonFixture.mock.restore(); removeDir(fixtureRoot); });

const key = "agent:rune:subagent:wrapper-reader";
const identity = { sessionKey: key, sessionId: "wrapper-reader-id", lifecycleRevision: "wrapper-reader-revision" };
const payload = "the brass QUIET sign is bolted to a bell";
type Service = { start: (ctx: { stateDir: string }) => Promise<void>; stop?: (ctx: { stateDir: string }) => Promise<void> };

async function setup() {
  const dir = tempDir(); const storePath = join(dir, "sessions.json");
  selectStore(storePath); writeStore({ rows: { [key]: identity } });
  const factories = new Map<string, (ctx: ToolContext) => Tool | null>();
  let service!: Service; let binding!: Binding;
  const originalStart = Binding.prototype.start;
  const capture = mock.method(Binding.prototype, "start", async function (this: Binding) {
    binding = this; return await originalStart.call(this);
  });
  const proof = (sessionKey: string) => route.resolvePluginLocalSessionRoute({ cfg: { session: { store: storePath } }, sessionKey });
  plugin.register({
    pluginConfig: {
      binding: "wrapper-reader", daemon: { socket: join(dir, "fixture.sock") },
      listen: { localReader: identity, payloadSessions: [key], subscriptions: [{ sessionKey: key, tune: ["cael:chatter"] }] },
    },
    session: { state: { resolveLocalSessionRoute: proof } },
    registerTool: (factory, opts) => factories.set(opts.name, factory as (ctx: ToolContext) => Tool | null),
    registerService: (s) => { service = s; },
  });
  try { await service.start({ stateDir: dir }); } finally { capture.mock.restore(); }
  const rec = (type: string, rec_seq: number, body: { [key: string]: unknown } = {}) => ({ v: RECORD_V, type, run: "wrapper-fixture-run", rec_seq, ...body });
  binding.receiver.connected(true);
  binding.receiver.apply(rec("hello", 1, { join_snapshot: true }));
  binding.receiver.apply(rec("landing_state", 2, { mute: null, breaker: "closed" }));
  binding.receiver.apply(rec("snapshot_end", 2, { watermark: 2, count: 0, truncated: false, omitted: 0 }));
  binding.receiver.apply(rec("frame", 3, frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: Date.now(), text: payload })));
  const record = { id: "canticle", enabled: true, status: "loaded" };
  const registry: Registry = { plugins: [record] };
  const admitted = { current: true, checks: 0 };
  const assertCurrent = () => { admitted.checks++; if (!admitted.current) throw new Error("fixture admitted run ended"); };
  function tool(name: ToolName, options: { noAdmission?: boolean; context?: ToolContext } = {}): Tool | null {
    const entry: Registration = { pluginId: "canticle", source: "production-index", factory: factories.get(name)!, optional: true };
    const ctx = core.createPluginToolFactoryContext({ entry, registry,
      context: options.context ?? { sessionKey: key, sessionId: identity.sessionId, sandboxed: true },
      ...(!options.noAdmission ? { assertInvocationCurrent: assertCurrent } : {}),
    });
    const factory = core.createPluginToolFactoryResolver((message) => { throw new Error(message); });
    const result = factory.resolve(entry, ctx, [name]);
    assert.equal(result.failed, false);
    return result.resolved ? core.bindPluginToolCallbacks(entry, registry, result.resolved, ctx.assertInvocationCurrent) : null;
  }
  return { binding, tool, admitted, registry, record, close: async () => { await service.stop?.({ stateDir: dir }); removeDir(dir); } };
}

test("production entry and core factory/callback wrapper return exact payload with provenance, taint and mute", async () => {
  const s = await setup();
  try {
    const result = await s.tool("canticle_listen")!.execute("read", { what: "on_air", view: "items" });
    assert.equal(result.details.ok, true, JSON.stringify(result));
    assert.match(result.content[0]!.text, /the brass QUIET sign is bolted to a bell/);
    assert.match(result.content[0]!.text, /EXTERNAL_UNTRUSTED_CONTENT/);
    assert.match(result.content[0]!.text, /station="cael"/);
    assert.ok(s.admitted.checks >= 5, "actual context and wrapper check their admitted-run producer");
    assert.equal(s.tool("canticle_sing"), null);
    assert.equal((await s.tool("canticle_mute")!.execute("mute", { station: "cael", ttlSeconds: 60 })).details.ok, true);
    assert.equal((await s.tool("canticle_mute")!.execute("clear", { clear: "all" })).details.ok, true);
    const status = await s.tool("canticle_status")!.execute("status", {});
    assert.equal((status.details.canticle.session as { tainted: boolean }).tainted, true);
  } finally { await s.close(); }
});

test("actual V1 core context does not turn lifecycle-only authority into an admitted read", async () => {
  const s = await setup();
  try {
    const result = await s.tool("canticle_listen", { noAdmission: true })!.execute("no-run", { view: "items" });
    assert.equal(result.details.error, "payload_not_allowed");
    assert.doesNotMatch(result.content[0]!.text, /brass QUIET/);
  } finally { await s.close(); }
});

test("actual callback wrapper refuses retained calls after run end or plugin record revocation", async () => {
  for (const end of ["run", "plugin"] as const) {
    const s = await setup();
    try {
      const tool = s.tool("canticle_listen")!;
      if (end === "run") s.admitted.current = false;
      else core.revokePluginRecord(s.registry, s.record);
      await assert.rejects(tool.execute("ended", { view: "items" }), /ended|no longer active/);
      const status = s.binding.status({ sessionKey: key, sessionId: identity.sessionId, subagent: true, anonymous: false });
      assert.equal((status.details.session as { tainted: boolean }).tainted, false, "no payload read occurred");
    } finally { await s.close(); }
  }
});

test("core post-result invocation check withholds a produced payload when the admitted run ends", async () => {
  const s = await setup();
  const original = Binding.prototype.listen;
  const endAfterRead = mock.method(Binding.prototype, "listen", function (this: Binding, ...args: Parameters<Binding["listen"]>) {
    const result = original.apply(this, args); s.admitted.current = false; return result;
  });
  try {
    const tool = s.tool("canticle_listen")!;
    await assert.rejects(tool.execute("lost-return", { view: "items" }), /admitted run ended/);
    const status = s.binding.status({ sessionKey: key, sessionId: identity.sessionId, subagent: true, anonymous: false });
    assert.equal((status.details.session as { tainted: boolean }).tainted, true, "uncertain exposure stays tainted");
  } finally { endAfterRead.mock.restore(); await s.close(); }
});

test("row change during real resolver awaits cannot cross the production wrapper", async () => {
  const s = await setup();
  try {
    afterNextRowRead(() => writeStore({ rows: { [key]: { ...identity, lifecycleRevision: "replacement" } } }));
    const result = await s.tool("canticle_listen")!.execute("race", { view: "items" });
    assert.equal(result.details.ok, false); assert.doesNotMatch(result.content[0]!.text, /brass QUIET/);
  } finally { await s.close(); }
});

test("production context/callback path retains exact caller, sandbox and generation rejection", async () => {
  const s = await setup();
  try {
    for (const context of [
      { sessionKey: key, sessionId: identity.sessionId, sandboxed: false },
      { sessionKey: key, sessionId: "different", sandboxed: true },
      { sessionKey: "agent:rune:main", sessionId: identity.sessionId, sandboxed: true },
      { sessionKey: "agent:rune:discord:channel:room", sessionId: identity.sessionId, sandboxed: true },
    ]) {
      const result = await s.tool("canticle_listen", { context })!.execute("wrong-reader", { view: "items" });
      assert.equal(result.details.ok, false); assert.doesNotMatch(result.content[0]!.text, /brass QUIET/);
    }
  } finally { await s.close(); }
});
