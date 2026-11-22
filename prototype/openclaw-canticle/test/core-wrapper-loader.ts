// Load exact upstream source bytes, with a closed list of environmental adapters.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import type { Tool, ToolContext } from "../src/tools.ts";

export const CORE_REVISION = "21660b2182062a9a98eb28d46341283100c082e6";
export const CORE_SOURCES = {
  "tool-factory-context.ts": "b96ba524045050273de20ef0f9ed386beab5effbfcf30dac503b3add16bf089d",
  "tool-factory-runtime.ts": "2f81f1fabfe7816acc6320bb32f8221e8bfcae38ce9385765c3d0c3ad1306293",
  "registry-lifecycle.ts": "74e604827d3e7189c53fa4c83aaedb05f0151b9b010f7caa845e03e530f96da9",
  "plugin-instance-scope.ts": "076fa2b7bdc24bc43b5b97dc05aa7b5f99b295d465f504d4e7950a88b689e930",
} as const;

type Record = { id: string; enabled: boolean; status: string };
export type Registry = { plugins: Record[] };
export type Registration = { pluginId: string; source: string; contextVersion?: number; factory: (ctx: ToolContext) => Tool | null; optional: boolean };
type CoreContext = {
  createPluginToolFactoryContext: (params: { entry: Registration; registry: Registry; context: ToolContext; assertInvocationCurrent?: () => void }) => ToolContext;
};
type CoreCallbacks = {
  bindPluginToolCallbacks: (entry: Registration, registry: Registry, tool: Tool, guard?: () => void) => Tool;
  createPluginToolFactoryResolver: (onError: (message: string) => void) => {
    resolve: (entry: Registration, ctx: ToolContext, names: string[]) => { failed: boolean; resolved: Tool | null };
  };
};
type CoreLifecycle = { revokePluginRecord: (registry: Registry, record: Record) => void };

const fixtureImports = new Set([
  "@openclaw/normalization-core/promise-like", "../shared/global-singleton.js", "../shared/lazy-runtime.js",
  "./host-hook-cleanup-result.js", "./loader-cache-state.js", "./plugin-cache.js", "./runtime-state.js",
  "./runtime/load-context-state.js", "./plugin-instance-error.js", "./plugin-instance-invocation.js",
  "./plugin-instance-owned-values.js", "./memory-audience.js", "./memory-state.js",
  "../config/io.invalid-config.js", "../infra/abort-signal.js", "../infra/errors.js",
  "../logging/subsystem.js", "../shared/async-work-resources.js", "./inline-view.js",
  "./runtime/gateway-request-scope.js", "./tool-metadata.js",
]);

export async function loadCoreWrappers(dir: string) {
  const files = new Map<string, string>();
  for (const [name, sha256] of Object.entries(CORE_SOURCES)) {
    const bytes = readFileSync(join(import.meta.dirname, "fixtures/openclaw-21660b21", `${name}.source`));
    assert.equal(createHash("sha256").update(bytes).digest("hex"), sha256, `upstream source changed: ${name}`);
    const file = join(dir, `${name}.mts`); writeFileSync(file, bytes);
    files.set(`./${name.replace(/\.ts$/, ".js")}`, pathToFileURL(file).href);
  }
  const urls = new Set(files.values());
  const fixture = new URL("./core-wrapper-fixture-host.ts", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, ctx, next) {
    if (!ctx.parentURL || !urls.has(ctx.parentURL) || specifier.startsWith("node:")) return next(specifier, ctx);
    const actual = files.get(specifier);
    if (actual) return { url: actual, shortCircuit: true };
    assert.ok(fixtureImports.has(specifier), `unreviewed upstream dependency: ${specifier}`);
    return { url: fixture, shortCircuit: true };
  } });
  try {
    const context = await import(files.get("./tool-factory-context.js")!) as CoreContext;
    const callbacks = await import(files.get("./tool-factory-runtime.js")!) as CoreCallbacks;
    const lifecycle = await import(files.get("./registry-lifecycle.js")!) as CoreLifecycle;
    return { ...context, ...callbacks, ...lifecycle };
  } finally { hooks.deregister(); }
}
