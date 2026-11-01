// The OpenClaw entry of the canticle prince plugin (binary-canticle#97). It registers the tools and one service. The
// service starts the binding: it reads the host daemon, keeps the heard journal and, when publishing is enabled,
// the outbox. A configuration or start failure fails this service with a reason; it never refuses Gateway boot
// (RFC-0001 §14.18.7), and the tools then answer that the service is not running.

import { Binding } from "./src/binding.ts";
import { TARGET_SESSION_KEY, parseConfig, stateRootOf } from "./src/config.ts";
import { TOOL_NAMES, type ToolContext, createTool } from "./src/tools.ts";
import { Discoverer } from "./src/discover.ts";
import { oc0HostFromWorkflow, type Oc0Workflow } from "./src/oc0-host.ts";

const PLUGIN_ID = "canticle";

type Logger = { info?: (msg: string) => void; warn?: (msg: string) => void; error?: (msg: string) => void };
type ServiceContext = { config?: unknown; stateDir: string; logger?: Logger };
type LifecycleEvent = { sessionId: string; sessionKey: string; lifecycleRevision?: string; nextSessionId?: string };
type LifecycleContext = { sessionId: string; sessionKey: string; agentId: string };
type PluginApi = {
  pluginConfig?: unknown;
  /** OpenClaw #1523: post-commit, metadata-only session lifecycle hooks. */
  on?: (name: "session_reset" | "session_delete", handler: (event: LifecycleEvent, context: LifecycleContext) => Promise<void>) => void;
  session?: { workflow?: Partial<Oc0Workflow>; state?: { resolveLocalSessionRoute?: (sessionKey: string) => Promise<{
    sessionKey: string; exists: boolean; onHost: boolean; sessionId: string | null; lifecycleRevision: string | null;
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

function completeWorkflow(workflow: Partial<Oc0Workflow> | undefined): workflow is Oc0Workflow {
  return typeof workflow?.enqueueNextTurnInjection === "function" &&
    typeof workflow.getNextTurnInjectionState === "function" &&
    typeof workflow.withdrawNextTurnInjection === "function";
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
    let lifecycleHooksReady = false;
    try {
      publish = parseConfig(api.pluginConfig).publish.enabled;
    } catch {
      publish = false; // the service reports the config error when it starts
    }
    const state = () => ({ binding, failure, publish, discovery });
    const onLifecycle = (kind: "reset" | "delete") => async (event: LifecycleEvent, context: LifecycleContext) => {
      // Reject mismatched or noncanonical metadata: never let one session clear another's state.
      if (!event || !context || event.sessionKey !== context.sessionKey || event.sessionId !== context.sessionId ||
        !event.sessionId || !TARGET_SESSION_KEY.test(event.sessionKey) || event.sessionKey === "agent:main:main" ||
        event.sessionKey !== event.sessionKey.toLowerCase() ||
        !event.sessionKey.startsWith(`agent:${context.agentId}:`)) return;
      // ID-only callbacks cannot distinguish a reset that reuses the same ID. Preserve the old generation.
      if (typeof event.lifecycleRevision !== "string" || !event.lifecycleRevision) return;
      const b = binding;
      if (!b) return;
      if (kind === "reset") await b.resetSession(event.sessionKey, event.sessionId, event.lifecycleRevision);
      else await b.deleteSession(event.sessionKey, event.sessionId, event.lifecycleRevision);
    };
    // Registration happens at plugin load, before the service can receive lifecycle events.
    if (typeof api.on === "function") {
      try {
        api.on("session_reset", onLifecycle("reset"));
        api.on("session_delete", onLifecycle("delete"));
        lifecycleHooksReady = true;
      } catch { /* An older host may reject these hook names. Ambient stays disabled. */ }
    }
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
          if (cfg.delivery.subscriptions.some((s) => s.delivery === "ambient") && !lifecycleHooksReady) {
            throw new Error("ambient delivery requires OpenClaw session_reset/session_delete callbacks; configure ringbuffer_only until the host supports them");
          }
          const ambientConfigured = cfg.delivery.subscriptions.some((s) => s.delivery === "ambient");
          const workflow = api.session?.workflow;
          if (ambientConfigured && (!api.session?.state?.resolveLocalSessionRoute || !completeWorkflow(workflow))) {
            throw new Error("ambient delivery requires complete generation-bound OpenClaw session route and workflow APIs; configure ringbuffer_only until the host supports them");
          }
          d = new Discoverer(cfg.discovery);
          b = new Binding({
            config: cfg,
            root: stateRootOf(cfg, ctx.stateDir),
            routeProof: async (sessionKey) => {
              const resolve = api.session?.state?.resolveLocalSessionRoute;
              if (!resolve) return { sessionKey, exists: false, onHost: false, sessionId: null, lifecycleRevision: null };
              return resolve(sessionKey);
            },
            ...(ambientConfigured && lifecycleHooksReady && completeWorkflow(workflow) && api.session?.state?.resolveLocalSessionRoute
              ? { oc0Host: oc0HostFromWorkflow(workflow) } : {}),
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
