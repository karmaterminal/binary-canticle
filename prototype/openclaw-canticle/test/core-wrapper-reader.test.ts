// Production registration + unchanged core factory/context/callback/lifecycle sources.
// Row storage, daemon admission, lease and admitted-run producer are explicitly fixtures.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { after, mock, test } from "node:test";
import { DatabaseSync } from "node:sqlite";
import plugin from "../index.ts";
import { Binding } from "../src/binding.ts";
import { DaemonLink } from "../src/daemon.ts";
import { Lease } from "../src/store.ts";
import { RECORD_V } from "../src/records.ts";
import type { Tool, ToolContext, ToolName } from "../src/tools.ts";
import { EXPOSURE_PORT_VERSION, EXPOSURE_TOOL_BINDING, sha256, type ExposurePort, type PayloadExposure } from "../src/exposure.ts";
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

// The ledger below is a durable host-port fixture, not the installed Gateway or the #159 publisher.
// It exercises the mandatory pre-return ordering and restart uncertainty with real SQLite commits.
function exposureFixture(afterBegin?: () => void) {
  const dir = tempDir();
  const path = join(dir, "host-custody.sqlite");
  let db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE pending (id TEXT PRIMARY KEY, record TEXT NOT NULL)");
  let current = true;
  const port: ExposurePort = {
    version: EXPOSURE_PORT_VERSION,
    reader: identity,
    assertCurrent: () => { if (!current) throw new Error("host custody authority ended"); },
    begin: async (exposure) => {
      const record = JSON.stringify(exposure);
      const pendingId = sha256(record);
      db.prepare("INSERT INTO pending(id, record) VALUES (?, ?)").run(pendingId, record);
      afterBegin?.();
      return { pendingId };
    },
  };
  const rows = () => db.prepare("SELECT record FROM pending ORDER BY rowid").all()
    .map((row) => JSON.parse(String(row.record)) as PayloadExposure);
  return {
    port, rows,
    revoke: () => { current = false; },
    restart: () => { db.close(); db = new DatabaseSync(path); },
    close: () => { db.close(); removeDir(dir); },
  };
}

function exposureContext(port: unknown): ToolContext {
  return { sessionKey: key, sessionId: identity.sessionId, sandboxed: true,
    toolBindings: { [EXPOSURE_TOOL_BINDING]: port } };
}

test("actual Binding payload selection fences full ordered metadata before the core returns bytes", async () => {
  const s = await setup();
  const host = exposureFixture();
  try {
    const frame = frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 2,
      issued_at: Date.now(), text: "the wet lamp stays lit", class: "ambient" });
    const root = { key_id: KEY_CAEL, epoch: 1, stream_id: 42, seq: "9007199254740993" };
    s.binding.receiver.apply({ v: RECORD_V, type: "frame", run: "wrapper-fixture-run", rec_seq: 4,
      ...frame, scope: "host", hop: 2, lineage: { root, derived_from: [] },
      flags: { refresh: false, wake_derived: true, exercise: false } });
    const result = await s.tool("canticle_listen", { context: exposureContext(host.port) })!
      .execute("durable-read", { what: "journal", view: "items" });
    assert.equal(result.details.ok, true);
    assert.match(result.content[0]!.text, /brass QUIET/);
    assert.match(result.content[0]!.text, /wet lamp/);
    host.restart();
    const [record] = host.rows();
    assert.ok(record, "fence survives a host-ledger reopen before any confirmation");
    assert.deepEqual(record.reader, identity);
    assert.equal(record.toolCallId, "durable-read");
    assert.equal(record.resultSha256, sha256(result.content[0]!.text));
    assert.deepEqual(record.sources.map((source) => source.item.seq), [1, 2]);
    const second = record.sources[1]!;
    assert.equal(second.class, "ambient");
    assert.equal(second.scope, "host");
    assert.equal(second.hop, 2);
    assert.deepEqual(second.root, root);
    assert.equal(second.flags.wake_derived, true);
    assert.equal(second.sourceBody!.textSha256, sha256("the wet lamp stays lit"));
    assert.equal(second.times.local_expiry_at, (frame.times as { local_expiry_at: number }).local_expiry_at);
    assert.equal(second.receiver.recordSequence, 4);
    assert.ok(second.receiver.journalSequence !== null);
    assert.ok(second.renderedBytes > 0);
    assert.match(second.renderedSha256, /^[0-9a-f]{64}$/);
    assert.equal(host.rows().length, 1, "plugin does not confirm or clear its pending fence");
  } finally { host.close(); await s.close(); }
});

test("on-air payloads use the same fence while metadata previews create no exposure", async () => {
  const s = await setup();
  const host = exposureFixture();
  try {
    const tool = s.tool("canticle_listen", { context: exposureContext(host.port) })!;
    await tool.execute("preview", { what: "on_air", view: "digest" });
    assert.equal(host.rows().length, 0);
    const result = await tool.execute("air-read", { what: "on_air", view: "items" });
    assert.equal(result.details.ok, true);
    const [record] = host.rows();
    assert.equal(record!.sources.length, 1);
    assert.equal(record!.resultSha256, sha256(result.content[0]!.text));
    assert.equal(record!.sources[0]!.receiver.journalSequence, null);
    assert.equal(record!.sources[0]!.receiver.recordSequence, null, "the on-air owner cannot invent a record cursor");
  } finally { host.close(); await s.close(); }
});

test("multiline exposure receipts hash the exact returned entries after journal normalization", async () => {
  const s = await setup();
  const host = exposureFixture();
  const bodies = [payload, "first\n\n\nsecond", "\n\n\nfirst α\n\n\n\nsecond 🍂\n\n\n"];
  try {
    for (let i = 1; i < bodies.length; i++) {
      s.binding.receiver.apply({ v: RECORD_V, type: "frame", run: "wrapper-fixture-run", rec_seq: i + 3,
        ...frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: i + 1,
          issued_at: Date.now(), text: bodies[i]! }) });
    }
    const tool = s.tool("canticle_listen", { context: exposureContext(host.port) })!;
    for (const what of ["journal", "new", "on_air"] as const) {
      const result = await tool.execute(`multiline-${what}`, { what, view: "items" });
      assert.equal(result.details.ok, true);
      const text = result.content[0]!.text;
      const record = host.rows().at(-1)!;
      assert.equal(record.toolCallId, `multiline-${what}`);
      assert.equal(record.resultSha256, sha256(text));
      assert.equal(record.resultBytes, Buffer.byteLength(text));
      // Inspect the actual tool result; production receipt capture never parses these banners.
      const entries = Array.from(text.matchAll(/^\[canticle:heard\][\s\S]*?^<<<END_EXTERNAL_UNTRUSTED_CONTENT id="[0-9a-f]+">>>/gm),
        (match) => match[0]);
      assert.equal(entries.length, 3);
      assert.deepEqual(record.sources.map((source) => source.item.seq), what === "on_air" ? [3, 2, 1] : [1, 2, 3]);
      for (const [i, entry] of entries.entries()) {
        const source = record.sources[i]!;
        assert.equal(entry.match(/^item=\d+\/(\d+) hop=/m)?.[1], String(source.item.seq), "receipt follows returned order");
        assert.equal(source.renderedBytes, Buffer.byteLength(entry), `${what} entry ${i} returned bytes`);
        assert.equal(source.renderedSha256, sha256(entry), `${what} entry ${i} returned hash`);
        assert.equal(source.sourceBody!.textSha256, sha256(bodies[Number(source.item.seq) - 1]!), "source hash retains original body");
      }
      const utf8Entry = entries[record.sources.findIndex((source) => source.item.seq === 3)]!;
      assert.ok(Buffer.byteLength(utf8Entry) > utf8Entry.length, "UTF-8 bytes differ from character count");
      if (what === "on_air") {
        assert.ok(text.includes("first\n\n\nsecond"), "on-air retains its existing payload whitespace");
      } else {
        assert.ok(text.includes("first\n\nsecond"));
        assert.doesNotMatch(text, /\n{3,}/, "journal and new retain their existing blank-line normalization");
      }
    }
  } finally { host.close(); await s.close(); }
});

test("failed durable begin or wrong host incarnation withholds every payload byte", async () => {
  const s = await setup();
  const host = exposureFixture();
  try {
    for (const port of [
      { ...host.port, reader: { ...identity, lifecycleRevision: "replaced" } },
      { ...host.port, begin: async () => { throw new Error("PRIVATE LEDGER DETAIL"); } },
      { ...host.port, begin: async () => ({ pendingId: "" }) },
      { version: EXPOSURE_PORT_VERSION },
    ]) {
      const result = await s.tool("canticle_listen", { context: exposureContext(port) })!
        .execute("refused-read", { what: "journal", view: "items" });
      assert.equal(result.details.error, "exposure_unavailable");
      assert.doesNotMatch(JSON.stringify(result), /brass QUIET|PRIVATE LEDGER/);
    }
    assert.equal(host.rows().length, 0);
    assert.equal((s.binding.status({ sessionKey: key, sessionId: identity.sessionId,
      subagent: true, anonymous: false }).details.session as { tainted: boolean }).tainted, true);
  } finally { host.close(); await s.close(); }
});

test("ended invocation after durable begin leaves a pending fence when core withholds the result", async () => {
  const s = await setup();
  const host = exposureFixture(() => { s.admitted.current = false; });
  try {
    const tool = s.tool("canticle_listen", { context: exposureContext(host.port) })!;
    await assert.rejects(tool.execute("uncertain-read", { what: "on_air", view: "items" }), /admitted run ended/);
    host.restart();
    assert.equal(host.rows().length, 1);
    assert.equal(host.rows()[0]!.toolCallId, "uncertain-read");
  } finally { host.close(); await s.close(); }
});

test("model arguments cannot supply a host port or suppress the configured exposure fence", async () => {
  const s = await setup();
  const host = exposureFixture();
  try {
    const result = await s.tool("canticle_listen", { context: exposureContext(host.port) })!
      .execute("argument-spoof", { what: "on_air", view: "items", toolBindings: {},
        exposure: { confirmed: true, hop: 0 }, lifecycleRevision: "pretend" });
    assert.equal(result.details.ok, true);
    assert.equal(host.rows().length, 1);
    assert.equal(host.rows()[0]!.reader.lifecycleRevision, identity.lifecycleRevision);
    assert.equal("confirmed" in host.rows()[0]!, false);
  } finally { host.close(); await s.close(); }
});
