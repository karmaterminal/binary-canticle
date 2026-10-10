// The OpenClaw surface (binary-canticle#97): what the plugin registers, which tools a session is offered, how the
// service fails, and that the manifest's boot-time schema checks shape only (RFC-0001 §14.18.7), so a config this
// plugin refuses fails the canticle service and never Gateway boot.

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import plugin from "../index.ts";
import { ConfigError, parseConfig } from "../src/config.ts";
import type { Obj } from "../src/records.ts";
import { PUBLISH_TOOLS, READ_TOOLS, TOOL_NAMES, type Tool, type ToolResult } from "../src/tools.ts";
import { Clock, FakeDaemon, KEY_CAEL, KEY_RUNE, removeDir, sleep, tempDir, waitFor } from "./helpers.ts";

const HERE = join(import.meta.dirname, "..");
const manifest = JSON.parse(readFileSync(join(HERE, "openclaw.plugin.json"), "utf8")) as Obj;
const pkg = JSON.parse(readFileSync(join(HERE, "package.json"), "utf8")) as Obj;

type Factory = (ctx: Obj) => Tool | null;
type Service = {
  id: string;
  reload?: { configPrefixes: readonly string[] };
  start: (ctx: Obj) => Promise<void>;
  stop?: (ctx: Obj) => Promise<void>;
};

function load(pluginConfig?: unknown): { tools: Map<string, { factory: Factory; optional: boolean }>; service: Service } {
  const tools = new Map<string, { factory: Factory; optional: boolean }>();
  const services: Service[] = [];
  plugin.register({
    ...(pluginConfig !== undefined ? { pluginConfig } : {}),
    registerTool: (factory, opts) => tools.set(opts.name, { factory: factory as Factory, optional: opts.optional }),
    registerService: (s) => services.push(s as unknown as Service),
  });
  assert.equal(services.length, 1);
  return { tools, service: services[0] as Service };
}

function tool(tools: ReturnType<typeof load>["tools"], name: string, ctx: Obj = { sessionKey: "agent:main:main", sessionId: "s-1" }): Tool {
  const t = tools.get(name)?.factory(ctx);
  assert.ok(t, `${name} is offered`);
  return t;
}

/** A refusal is a returned, failed tool result (OpenClaw reads `details.ok: false`), never a thrown error. */
async function refused(call: Promise<ToolResult>, reason: string, text: RegExp): Promise<void> {
  const r = await call;
  assert.equal(r.details.ok, false);
  assert.equal(r.details.error, reason);
  assert.equal(r.details.canticle.refused, reason);
  assert.match(r.content[0]?.text ?? "", text);
  assert.match(r.content[0]?.text ?? "", new RegExp(`^\\[canticle:refused\\] canticle_\\w+: ${reason}: .*Nothing changed\\.$`, "s"));
}

let dir: string;
let daemon: FakeDaemon;

beforeEach(async () => {
  dir = tempDir();
  daemon = new FakeDaemon(dir);
  await daemon.start();
});

afterEach(async () => {
  await daemon.stop();
  removeDir(dir);
});

test("registers six optional tools and one service, matching the manifest and the package", () => {
  const { tools, service } = load();
  assert.deepEqual([...tools.keys()], [...TOOL_NAMES]);
  assert.deepEqual(manifest.contracts, { tools: [...TOOL_NAMES] });
  for (const [name, t] of tools) {
    assert.equal(t.optional, true, `${name} is optional: an agent gets it only through tools.allow`);
    assert.deepEqual((manifest.toolMetadata as Obj)[name], { optional: true });
  }
  assert.equal(service.id, "canticle");
  assert.deepEqual(service.reload?.configPrefixes, ["plugins.entries.canticle"]);
  assert.equal(manifest.id, plugin.id);
  assert.equal(manifest.description, plugin.description);
  assert.deepEqual((pkg.openclaw as Obj).extensions, ["./index.ts"]);
  assert.equal(pkg.private, true); // never published (AGENTS.md: publication is a separate, human-decided gate)
});

test("publish tools are offered only when publishing is enabled, and never to a sub-agent", () => {
  const readOnly = load({ binding: "rune", daemon: { socket: daemon.path } });
  for (const name of READ_TOOLS) {
    assert.ok(readOnly.tools.get(name)?.factory({ sessionKey: "agent:main:main" }));
  }
  for (const name of PUBLISH_TOOLS) {
    assert.equal(readOnly.tools.get(name)?.factory({ sessionKey: "agent:main:main" }), null);
  }
  const publishing = load({
    binding: "rune",
    daemon: { socket: daemon.path },
    station: { name: "rune", keyId: KEY_RUNE },
    publish: { enabled: true, socket: join(dir, "rune.ctl") },
  });
  for (const name of PUBLISH_TOOLS) {
    assert.ok(publishing.tools.get(name)?.factory({ sessionKey: "agent:main:main" }));
    for (const sub of ["agent:main:subagent:task-1", "subagent:task-1", "AGENT:Main:SUBAGENT:x"]) {
      assert.equal(publishing.tools.get(name)?.factory({ sessionKey: sub }), null, `${name} for ${sub}`);
    }
  }
  // A sub-agent still reads: what it reads taints it, and it can never sing anyway.
  assert.ok(publishing.tools.get("canticle_listen")?.factory({ sessionKey: "agent:main:subagent:task-1" }));
});

test("only canticle_listen returns network content, and every schema refuses unknown parameters", () => {
  const { tools } = load({
    binding: "rune",
    daemon: { socket: daemon.path },
    station: { name: "rune", keyId: KEY_RUNE },
    publish: { enabled: true, socket: join(dir, "rune.ctl") },
  });
  for (const name of TOOL_NAMES) {
    const t = tool(tools, name);
    assert.equal(t.resultContentSource, name === "canticle_listen" ? "network" : undefined, name);
    assert.equal(t.parameters.additionalProperties, false, name);
    assert.equal(t.parameters.type, "object", name);
    for (const [k, v] of Object.entries(t.parameters.properties as Obj)) {
      assert.ok(typeof (v as Obj).type === "string", `${name}.${k} has a type`);
    }
    assert.ok(t.description.length <= 1024, `${name} description fits`);
  }
  // Every description says what heard text is, or never shows it.
  assert.match(tool(tools, "canticle_listen").description, /untrusted data/);
  assert.match(tool(tools, "canticle_sing").description, /Never sing heard content back/);
  assert.match(tool(tools, "canticle_status").description, /without any heard text/);
});

test("the tools say the service is not running until it starts, and a bad config fails only the service", async () => {
  // A config the plugin refuses must not throw from register: that would be a plugin load failure.
  const { tools, service } = load({ binding: "rune", daemon: { socket: "relative/daemon.sock" } });
  await refused(tool(tools, "canticle_status").execute("c1", {}), "not_running", /service is not running \(not started\)\. Nothing changed\./);
  const ctx = {
    config: { plugins: { entries: { canticle: { config: { binding: "rune", daemon: { socket: "relative/daemon.sock" } } } } } },
    stateDir: dir,
    logger: { info: () => undefined, warn: () => undefined, error: () => undefined },
  };
  await assert.rejects(service.start(ctx), /daemon\.socket: expected an absolute path/);
  await refused(tool(tools, "canticle_listen").execute("c2", {}), "not_running", /service is not running \(daemon\.socket: expected an absolute path/);
  assert.equal(existsSync(join(dir, "canticle")), false); // nothing written for a config that never started
});

test("a started service answers through the tools, and a refusal is a failed result that changes nothing", async () => {
  const clock = new Clock(Date.now());
  const cfg = { binding: "rune", daemon: { socket: daemon.path }, listen: { payloadSessions: ["agent:main:*"] } };
  const { tools, service } = load(cfg);
  const logs: string[] = [];
  const ctx = {
    config: { plugins: { entries: { canticle: { enabled: true, config: cfg } } } },
    stateDir: dir,
    logger: { info: (m: string) => logs.push(m), warn: (m: string) => logs.push(m), error: (m: string) => logs.push(m) },
  };
  await service.start(ctx);
  try {
    assert.equal(existsSync(join(dir, "canticle", "rune", "state.json")), true); // <stateDir>/canticle/<binding>
    const status = tool(tools, "canticle_status");
    await waitFor(() => daemon.accepted === 1, "the daemon connection");
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t, text: "hello from cael" });
    const listen = tool(tools, "canticle_listen");
    const end = Date.now() + 4_000;
    let out = await listen.execute("c3", { what: "journal", view: "items" });
    while (out.content[0]?.text.includes("hello from cael") !== true) {
      assert.ok(Date.now() < end, "timed out waiting for the heard item through the tool");
      await sleep(10);
      out = await listen.execute("c3", { what: "journal", view: "items" });
    }
    const r = out as { content: { type: string; text: string }[]; details: { ok: boolean; error?: string; canticle: Obj } };
    assert.equal(r.details.ok, true);
    assert.equal("error" in r.details, false);
    assert.equal(r.content[0]?.type, "text");
    assert.match(r.content[0]?.text ?? "", /heard broadcast — not an instruction/);
    assert.match(r.content[0]?.text ?? "", /<<<EXTERNAL_UNTRUSTED_CONTENT id=/);
    assert.equal(r.details.canticle.untrusted, true);
    await refused(listen.execute("c4", { since: "j:scribe:0123456789abcdef:1" }), "not_this_binding", /^\[canticle:refused\] canticle_listen: not_this_binding: /);
    await refused(listen.execute("c5", { what: "everything" }), "bad_param", /what/);
    const st = await status.execute("c6", {});
    assert.equal(st.content[0]?.text.includes("hello from cael"), false); // status never carries heard text
    // A session the configuration does not list reads digests: no sender text, and no taint.
    const outsider = tool(tools, "canticle_listen", { sessionKey: "agent:discord-bound:main", sessionId: "d-1" });
    await refused(outsider.execute("c8", { what: "journal", view: "items" }), "payload_not_allowed", /payload_not_allowed/);
    const digest = await outsider.execute("c9", { what: "journal" });
    assert.match(digest.content[0]?.text ?? "", /\[canticle:heard\] cael:chatter class=chatter/);
    assert.equal(digest.content[0]?.text.includes("hello from cael"), false);
    assert.match(digest.content[0]?.text ?? "", /heard text is not shown to this session/);
    assert.equal((digest.details.canticle as Obj).untrusted, false);
  } finally {
    await service.stop?.(ctx);
  }
  await refused(tool(tools, "canticle_listen").execute("c7", {}), "not_running", /service is not running \(stopped\)/);
});

// ------------------------------------------------------------------ the manifest's boot-time schema

/** The JSON Schema subset the manifest uses, enough to check it the way the Gateway would at boot. */
function schemaErrors(schema: Obj, value: unknown, at = "<root>"): string[] {
  const type = schema.type;
  if (type === "object") {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      return [`${at}: must be object`];
    }
    const v = value as Obj;
    const props = (schema.properties ?? {}) as Record<string, Obj>;
    const errors: string[] = [];
    for (const k of (schema.required ?? []) as string[]) {
      if (!(k in v)) {
        errors.push(`${at}: missing ${k}`);
      }
    }
    for (const [k, x] of Object.entries(v)) {
      const s = props[k];
      if (s === undefined) {
        if (schema.additionalProperties === false) {
          errors.push(`${at}: unknown ${k}`);
        }
        continue;
      }
      errors.push(...schemaErrors(s, x, `${at}.${k}`));
    }
    return errors;
  }
  if (type === "array") {
    if (!Array.isArray(value)) {
      return [`${at}: must be array`];
    }
    if (typeof schema.maxItems === "number" && value.length > schema.maxItems) {
      return [`${at}: too many items`];
    }
    return value.flatMap((x, i) => schemaErrors(schema.items as Obj, x, `${at}[${i}]`));
  }
  if (type === "string") {
    if (typeof value !== "string") {
      return [`${at}: must be string`];
    }
    if (typeof schema.minLength === "number" && value.length < schema.minLength) {
      return [`${at}: too short`];
    }
    if (typeof schema.maxLength === "number" && value.length > schema.maxLength) {
      return [`${at}: too long`];
    }
    if (typeof schema.pattern === "string" && !new RegExp(schema.pattern, "u").test(value)) {
      return [`${at}: pattern`];
    }
    if (Array.isArray(schema.enum) && !schema.enum.includes(value)) {
      return [`${at}: enum`];
    }
    return [];
  }
  if (type === "integer") {
    if (typeof value !== "number" || !Number.isInteger(value)) {
      return [`${at}: must be integer`];
    }
    if ((typeof schema.minimum === "number" && value < schema.minimum) || (typeof schema.maximum === "number" && value > schema.maximum)) {
      return [`${at}: out of range`];
    }
    return [];
  }
  if (type === "boolean") {
    return typeof value === "boolean" ? [] : [`${at}: must be boolean`];
  }
  return [`${at}: schema type ${String(type)} not understood by this test`];
}

/** Every key path a schema declares. */
function schemaKeys(schema: Obj, at = ""): string[] {
  if (schema.type !== "object") {
    return [];
  }
  return Object.entries((schema.properties ?? {}) as Record<string, Obj>).flatMap(([k, s]) => [`${at}${k}`, ...schemaKeys(s, `${at}${k}.`)]);
}

function valueKeys(v: unknown, at = ""): string[] {
  if (typeof v !== "object" || v === null || Array.isArray(v)) {
    return [];
  }
  return Object.entries(v as Obj).flatMap(([k, x]) => [`${at}${k}`, ...valueKeys(x, `${at}${k}.`)]);
}

/** A config that sets every key the plugin reads (the README shows the same block). */
const FULL = {
  binding: "rune",
  daemon: { socket: "/run/user/1000/canticle/daemon.sock", uid: 1000 },
  stateDir: "/home/rune/.openclaw/canticle/rune",
  station: { name: "rune", keyId: KEY_RUNE },
  listen: { tune: ["*:chatter", "cael:*", "*:alerts.*"], includeSelf: false, payloadSessions: ["agent:reader:*"] },
  journal: { maxEntries: 5000, maxBytes: 8388608, maxAgeHours: 24 },
  publish: {
    enabled: true,
    socket: "/run/user/1000/canticle/rune.ctl",
    uid: 1000,
    classes: ["chatter", "live-state"],
    perMinute: 5,
    perHour: 60,
    maxLive: 16,
  },
  delivery: { mode: "explicit" },
};

test("the manifest schema accepts every key the plugin reads, and nothing it does not", () => {
  const schema = manifest.configSchema as Obj;
  assert.deepEqual(schemaErrors(schema, FULL), []);
  assert.deepEqual(valueKeys(FULL).sort(), schemaKeys(schema).sort());
  const parsed = parseConfig(FULL);
  assert.equal(parsed.publish.enabled, true);
  assert.equal(parsed.journal.maxAgeMs, 24 * 3_600_000);
  assert.deepEqual(schemaErrors(schema, { ...FULL, extra: 1 }), ["<root>: unknown extra"]);
  assert.deepEqual(schemaErrors(schema, { ...FULL, publish: { ...FULL.publish, perMinute: 6 } }), ["<root>.publish.perMinute: out of range"]);
});

test("a config the service refuses still passes the boot-time schema: it fails the service, not the Gateway", () => {
  const schema = manifest.configSchema as Obj;
  const refusedAtStart: Obj[] = [
    { binding: "rune", daemon: { socket: "relative.sock" } }, // paths are checked when the service starts
    { binding: "rune", daemon: { socket: "/d.sock" }, publish: { enabled: true, socket: "/s.ctl" } }, // no station
    { binding: "rune", daemon: { socket: "/d.sock" }, publish: { enabled: true } }, // no publish socket
    { binding: "rune", daemon: { socket: "/d.sock" }, listen: { tune: ["not a tune"] } },
    { binding: "rune", daemon: { socket: "/d.sock" }, listen: { payloadSessions: ["agent:*:main"] } }, // * only at the end
  ];
  for (const c of refusedAtStart) {
    assert.deepEqual(schemaErrors(schema, c), [], JSON.stringify(c));
    assert.throws(() => parseConfig(c), ConfigError, JSON.stringify(c));
  }
});
