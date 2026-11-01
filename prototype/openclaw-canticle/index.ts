// The OpenClaw entry of the canticle prince plugin (binary-canticle#97). It registers the tools and one service. The
// service starts the binding: it reads the host daemon, keeps the heard journal and, when publishing is enabled,
// the outbox. A configuration or start failure fails this service with a reason; it never refuses Gateway boot
// (RFC-0001 §14.18.7), and the tools then answer that the service is not running.

import { Binding } from "./src/binding.ts";
import { parseConfig, stateRootOf } from "./src/config.ts";
import { TOOL_NAMES, type ToolContext, createTool } from "./src/tools.ts";
import { Discoverer } from "./src/discover.ts";

const PLUGIN_ID = "canticle";

type Logger = { info?: (msg: string) => void; warn?: (msg: string) => void; error?: (msg: string) => void };
type ServiceContext = { config?: unknown; stateDir: string; logger?: Logger };
type PluginApi = {
  pluginConfig?: unknown;
  session?: { state?: { resolveLocalSessionRoute?: (sessionKey: string) => Promise<{
    sessionKey: string; exists: boolean; onHost: boolean;
  }> } };
  registerTool: (factory: (ctx: ToolContext) => unknown, opts: { name: string; optional: boolean }) => void;
  registerService: (service: {
    id: string;
    reload?: { configPrefixes: readonly string[] };
    start: (ctx: ServiceContext) => Promise<void>;
    stop?: (ctx: ServiceContext) => Promise<void>;
  }) => void;
};

/** The live config block for this plugin, falling back to what the plugin was registered with. */
function configOf(ctx: ServiceContext, api: PluginApi): unknown {
  const c = ctx.config as { plugins?: { entries?: Record<string, { config?: unknown }> } } | undefined;
  return c?.plugins?.entries?.[PLUGIN_ID]?.config ?? api.pluginConfig;
}

export default {
  id: PLUGIN_ID,
  name: "Canticle",
  description: "Hear the canticle through the host daemon, keep a bounded heard journal, and sing through this prince's own station.",
  register(api: PluginApi): void {
    let binding: Binding | null = null;
    let failure: string | null = "not started";
    let publish = false;
    let discovery: Discoverer | null = null;
    try {
      publish = parseConfig(api.pluginConfig).publish.enabled;
    } catch {
      publish = false; // the service reports the config error when it starts
    }
    const state = () => ({ binding, failure, publish, discovery });
    for (const name of TOOL_NAMES) {
      api.registerTool((ctx) => createTool(name, ctx ?? {}, state), { name, optional: true });
    }
    api.registerService({
      id: PLUGIN_ID,
      reload: { configPrefixes: [`plugins.entries.${PLUGIN_ID}`] },
      async start(ctx) {
        let b: Binding;
        let d: Discoverer;
        try {
          const cfg = parseConfig(configOf(ctx, api));
          publish = cfg.publish.enabled;
          d = new Discoverer(cfg.discovery);
          b = new Binding({
            config: cfg,
            root: stateRootOf(cfg, ctx.stateDir),
            routeProof: async (sessionKey) => {
              const resolve = api.session?.state?.resolveLocalSessionRoute;
              if (!resolve) return { sessionKey, exists: false, onHost: false };
              return resolve(sessionKey);
            },
            log: (msg) => ctx.logger?.info?.(msg),
          });
          await b.start();
        } catch (e) {
          failure = (e as Error).message;
          throw e;
        }
        binding = b;
        discovery = d;
        failure = null;
      },
      async stop() {
        const b = binding;
        binding = null;
        discovery = null;
        failure = "stopped";
        await b?.stop();
      },
    });
  },
};
