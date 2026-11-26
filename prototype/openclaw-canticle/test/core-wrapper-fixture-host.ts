// Explicit environmental adapters for unchanged OpenClaw wrapper sources.
// No admission, locality, factory-context or callback decision is implemented here.
// Unknown/unexercised services throw; this is not the Gateway runtime.
import { AsyncLocalStorage } from "node:async_hooks";

const singletons = new Map<symbol, unknown>();
export function resolveGlobalSingleton<T>(key: symbol, make: () => T): T {
  if (!singletons.has(key)) singletons.set(key, make());
  return singletons.get(key) as T;
}
export function isPromiseLike(value: unknown): boolean {
  return value !== null && (typeof value === "object" || typeof value === "function") &&
    typeof (value as { then?: unknown }).then === "function";
}
function unused(): never { throw new Error("unexercised core environment dependency"); }
export const createLazyRuntimeNamedExport = () => unused;
export const summarizePluginRetirementResults = unused;
export class PluginLoaderCacheState { constructor() { unused(); } }
export const getPluginCache = unused;
export const releasePluginCacheInstance = unused;
export const retainPluginCacheInstance = unused;
export const getPluginRegistryState = () => undefined;
export const getPluginRuntimeLoadContextState = () => undefined;
export class PluginInstanceUnavailableError extends Error {}
export const pluginInstanceInvocation = new AsyncLocalStorage();
export const createPluginValueInstances = () => new WeakMap();
export const assertMemoryAudienceSession = unused;
export const prepareMemoryAudienceRead = unused;
export const resolveMemoryCapabilityRegistration = () => undefined;
export const isInvalidConfigError = () => false;
export const racePromiseWithAbortSignal = unused;
export const formatErrorMessage = (value: unknown) => String(value);
export const createSubsystemLogger = () => ({ warn: unused, trace: unused, isEnabled: () => false });
export const runWithTrackedCancellation = unused;
export const bindPluginInlineViewInvocation = <T>(value: T): T => value;
export const withPluginRuntimePluginScope = <T>(_scope: unknown, action: () => T): T => action();
export const copyPluginToolMeta = () => undefined;
