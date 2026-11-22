// Storage adapters for the byte-pinned real core resolver in local-reader.test.ts.
// These are explicit fixtures, not a claim to run OpenClaw's worker/storage stack.
import { readFileSync, writeFileSync } from "node:fs";

type Row = Record<string, unknown>;
type Store = { rows: Record<string, Row>; placements?: Record<string, Row>; bindings?: Record<string, Row[]> };
let path = "";
let afterRead: (() => void) | null = null;

export function selectStore(p: string): void { path = p; afterRead = null; }
export function afterNextRowRead(fn: () => void): void { afterRead = fn; }
export function writeStore(value: Store): void { writeFileSync(path, JSON.stringify(value)); }
function store(): Store { return JSON.parse(readFileSync(path, "utf8")) as Store; }
export function resolveAgentMainSessionKey({ agentId }: { agentId: string }): string { return `agent:${agentId}:main`; }
export function resolveSessionStorePathCore(p: string): string { return p; }
export function resolveSessionStoreKey({ sessionKey }: { sessionKey: string }): string { return sessionKey; }
export function resolveSessionStoreAgentId(_cfg: unknown, key: string): string { return key.split(":")[1] ?? ""; }
export async function readSessionEntryReadOnlyInWorker({ storePath, sessionKey }: { storePath: string; sessionKey: string }): Promise<Row | undefined> {
  const row = (JSON.parse(readFileSync(storePath, "utf8")) as Store).rows[sessionKey];
  const callback = afterRead; afterRead = null; callback?.();
  return row;
}
export async function listSessionBindingsBySessionAsync(key: string): Promise<Row[]> { return store().bindings?.[key] ?? []; }
export function placementTurnOwner(row: Row): { kind: string } { return { kind: String(row.turnOwner) }; }
export function createWorkerSessionPlacementStore(): { readProjection: () => Promise<{ placements: Map<string, Row> }> } {
  return { readProjection: async () => ({ placements: new Map(Object.entries(store().placements ?? {})) }) };
}
