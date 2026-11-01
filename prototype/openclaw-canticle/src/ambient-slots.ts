// OC-0 adapter core. The service wires this only when both host seams exist.
// The binding owns frame keys; OC-0 owns entry outcomes. Every intent is durable before a host call.
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { readJson, writeJsonAtomic } from "./store.ts";
import type { RouteProof } from "./candidates.ts";
import { TARGET_SESSION_KEY } from "./config.ts";

export type SlotKey = "canticle:digest" | "canticle:alarm";
export type EntryOutcome = "pending" | "consumed" | "withdrawn" | "expired" | "discarded" | "unknown";
export type SlotFrame = { key: string; expiresAt: number; line: string; station?: string; stream?: string };
export type SlotRequest = { sessionKey: string; slot: SlotKey; frames: SlotFrame[] };
export type HostEntry = { idempotencyKey: string; sessionKey: string; expectedSessionId: string; expectedLifecycleRevision: string; supersedeKey: SlotKey; expectedPreviousKey?: string; text: string; deadline: number; outcomeRetention: number; provenance: "canticle" };
export type Oc0Host = {
  enqueue(entry: HostEntry): Promise<{ accepted: true } | { accepted: false; previousOutcome?: EntryOutcome }>;
  query(sessionKey: string, idempotencyKey: string, expectedSessionId: string, expectedLifecycleRevision: string): Promise<EntryOutcome>;
  withdraw(sessionKey: string, idempotencyKey: string, expectedSessionId: string, expectedLifecycleRevision: string): Promise<EntryOutcome>;
};
type Entry = { id: string; sessionKey: string; sessionId: string; lifecycleRevision: string; slot: SlotKey; frames: SlotFrame[]; deadline: number; retention: number; status: "enqueuing" | "pending" | "settled"; outcome?: EntryOutcome; previous?: string };
type Note = { key: string; expiresAt: number; line: string };
type Ledger = { v: 1; binding: string; entries: Entry[]; settled: Record<string, number>; tainted?: Record<string, number>; notes?: Record<string, Note> };
const SLOTS: SlotKey[] = ["canticle:digest", "canticle:alarm"];

export class AmbientSlots {
  private readonly path: string;
  private readonly binding: string;
  private readonly host: Oc0Host;
  private readonly route: RouteProof | null;
  private data: Ledger;
  constructor(root: string, binding: string, host: Oc0Host, route: RouteProof | null = null) {
    this.path = join(root, "ambient-slots.json"); this.binding = binding; this.host = host; this.route = route;
    this.data = { v: 1, binding, entries: [], settled: {}, tainted: {}, notes: {} };
  }
  private save(): void { writeJsonAtomic(this.path, this.data); }
  load(): void {
    const raw = readJson(this.path);
    if (raw === null) return;
    if (!raw || typeof raw !== "object" || (raw as Ledger).v !== 1 || (raw as Ledger).binding !== this.binding ||
      !Array.isArray((raw as Ledger).entries) || typeof (raw as Ledger).settled !== "object") throw new Error("invalid ambient slot ledger");
    const d = raw as Ledger;
    if (d.entries.length > 8192 || d.entries.some((e) => !e || typeof e.id !== "string" || e.id.length > 200 || !SLOTS.includes(e.slot) ||
      typeof e.sessionKey !== "string" || e.sessionKey !== e.sessionKey.toLowerCase() || !TARGET_SESSION_KEY.test(e.sessionKey) || e.sessionKey === "agent:main:main" ||
      (typeof e.sessionId !== "string" || !e.sessionId || typeof e.lifecycleRevision !== "string" || !e.lifecycleRevision) ||
      !Array.isArray(e.frames) || e.frames.length < 1 || e.frames.length > 5 ||
      !Number.isSafeInteger(e.deadline) || !Number.isSafeInteger(e.retention) ||
      e.frames.some((f) => !f || typeof f.key !== "string" || f.key.length > 300 || !Number.isSafeInteger(f.expiresAt) ||
        typeof f.line !== "string" || Buffer.byteLength(f.line) > 1536) ||
      (e.frames.length > 1 && Buffer.byteLength(e.frames.map((f) => f.line).join("\n")) > 1536) ||
      (e.previous !== undefined && typeof e.previous !== "string") ||
      !["enqueuing", "pending", "settled"].includes(e.status) ||
      (e.status === "settled" && (typeof e.outcome !== "string" || !["pending", "consumed", "withdrawn", "expired", "discarded", "unknown"].includes(e.outcome))))) throw new Error("invalid ambient slot entries");
    if (!d.settled || typeof d.settled !== "object" || Array.isArray(d.settled) || Object.keys(d.settled).length > 8192 ||
      Object.values(d.settled).some((n) => !Number.isSafeInteger(n))) throw new Error("invalid ambient settled tombstones");
    if (d.tainted !== undefined && (!d.tainted || typeof d.tainted !== "object" || Array.isArray(d.tainted) || Object.keys(d.tainted).length > 4096 ||
      Object.entries(d.tainted).some(([key, n]) => { const [session = "", id, extra] = key.split("\0"); return session !== session.toLowerCase() || !TARGET_SESSION_KEY.test(session) || session === "agent:main:main" || (id !== undefined && !id) || extra !== undefined || !Number.isSafeInteger(n); }))) throw new Error("invalid ambient taint");
    if (d.notes !== undefined && (!d.notes || typeof d.notes !== "object" || Array.isArray(d.notes) || Object.keys(d.notes).length > 8192 ||
      Object.values(d.notes).some((n) => !n || typeof n.key !== "string" || n.key.length > 300 || !Number.isSafeInteger(n.expiresAt) || typeof n.line !== "string" || Buffer.byteLength(n.line) > 300))) throw new Error("invalid ambient notes");
    d.tainted ??= {}; d.notes ??= {};
    this.data = d;
  }
  private prune(now: number): void {
    const entries = this.data.entries.filter((e) => e.status !== "settled" || e.retention + 5000 > now);
    let dirty = entries.length !== this.data.entries.length;
    this.data.entries = entries;
    for (const [key, until] of Object.entries(this.data.settled)) if (until <= now) {
      delete this.data.settled[key]; dirty = true;
    }
    for (const [key, note] of Object.entries(this.data.notes ?? {})) if (note.expiresAt + 5000 <= now) {
      delete this.data.notes![key]; dirty = true;
    }
    if (dirty) this.save();
  }
  private active(session: string, slot: SlotKey): Entry | undefined {
    return this.data.entries.findLast((e) => e.sessionKey === session && e.slot === slot && e.status !== "settled");
  }
  private settle(e: Entry, outcome: EntryOutcome, now: number): void {
    e.status = "settled"; e.outcome = outcome;
    if (outcome === "consumed") (this.data.tainted ??= {})[e.sessionId ? `${e.sessionKey}\0${e.sessionId}` : e.sessionKey] ??= now;
    if (outcome === "consumed" || outcome === "discarded") for (const f of e.frames) this.data.settled[f.key] = f.expiresAt + 5000;
    if (outcome === "expired") for (const f of e.frames) if (f.expiresAt <= now) this.data.settled[f.key] = f.expiresAt + 5000;
    this.save();
  }
  private async validRoute(session: string): Promise<boolean> {
    if (session !== session.toLowerCase() || !TARGET_SESSION_KEY.test(session) || session === "agent:main:main") return false;
    if (this.route === null) return true;
    try {
      const proof = await this.route(session);
      return proof.sessionKey === session && proof.exists === true && proof.onHost === true;
    } catch { return false; }
  }
  private async generation(session: string): Promise<{ sessionId: string; lifecycleRevision: string } | null> {
    if (!this.route) return null;
    try {
      const proof = await this.route(session);
      return proof.sessionKey === session && proof.exists === true && proof.onHost === true &&
        typeof proof.sessionId === "string" && proof.sessionId.length > 0 &&
        typeof proof.lifecycleRevision === "string" && proof.lifecycleRevision.length > 0
        ? { sessionId: proof.sessionId, lifecycleRevision: proof.lifecycleRevision } : null;
    } catch { return null; }
  }
  private sameGeneration(a: { sessionId: string; lifecycleRevision: string } | null, b: { sessionId: string; lifecycleRevision: string } | null): boolean {
    return a !== null && b !== null && a.sessionId === b.sessionId && a.lifecycleRevision === b.lifecycleRevision;
  }
  /** Query every ambiguous entry before allowing this session to deliver again. A failed query fails closed. */
  async reconcile(session: string, now: number): Promise<void> {
    this.prune(now);
    const generation = this.route ? await this.generation(session) : null;
    if (this.route && !generation) throw new Error("canticle host session generation unavailable");
    for (const e of this.data.entries.filter((x) => x.sessionKey === session && x.status !== "settled")) {
      if (!this.sameGeneration(e, generation)) throw new Error("canticle slot belongs to another session generation");
      if (!await this.validRoute(session)) throw new Error("canticle host route proof lost before OC-0 reconcile");
      const outcome = await this.host.query(session, e.id, e.sessionId, e.lifecycleRevision);
      if (outcome === "pending") { e.status = "pending"; this.save(); }
      else this.settle(e, outcome, now);
    }
  }
  /** Rebuilds one of the two slots, retaining only live, unconsumed frame keys. */
  async sync(request: SlotRequest, now: number): Promise<void> {
    if (!SLOTS.includes(request.slot)) throw new Error("invalid canticle slot");
    const generation = this.route ? await this.generation(request.sessionKey) : null;
    if (this.route && !generation) throw new Error("canticle host session generation unavailable");
    if (!await this.validRoute(request.sessionKey)) throw new Error("canticle host route proof lost before slot reconcile");
    await this.reconcile(request.sessionKey, now);
    if (!this.sameGeneration(generation, await this.generation(request.sessionKey))) throw new Error("canticle host session generation changed");
    if (!await this.validRoute(request.sessionKey)) throw new Error("canticle host route proof lost after slot reconcile");
    const previous = this.active(request.sessionKey, request.slot);
    const unique = new Map<string, SlotFrame>();
    for (const f of request.frames) if (f.expiresAt > now && this.data.settled[f.key] === undefined) unique.set(f.key, f);
    const frames = [...unique.values()].slice(0, 5);
    if (Buffer.byteLength(frames.map((f) => f.line).join("\n")) > 1536) throw new Error("ambient slot exceeds byte bound");
    const same = previous?.status === "pending" && previous.frames.length === frames.length &&
      previous.frames.every((f, i) => f.key === frames[i]?.key && f.line === frames[i]?.line);
    if (same) return;
    if (!frames.length) {
      if (previous) {
        if (!this.sameGeneration(previous, await this.generation(request.sessionKey))) throw new Error("canticle host generation changed before slot withdrawal");
        await this.withdraw(previous, now);
      }
      return;
    }
    // A supersession may carry only confirmed-pending keys; consumed predecessors were settled above.
    if (this.data.entries.length >= 8192) throw new Error("ambient slot ledger full");
    const e: Entry = { id: `canticle-slot:${randomUUID()}`, sessionKey: request.sessionKey, sessionId: generation!.sessionId, lifecycleRevision: generation!.lifecycleRevision, slot: request.slot,
      frames, deadline: Math.min(...frames.map((f) => f.expiresAt)), retention: Math.max(...frames.map((f) => f.expiresAt)),
      status: "enqueuing", ...(previous ? { previous: previous.id } : {}) };
    this.data.entries.push(e); this.save();
    if (!await this.validRoute(request.sessionKey) || !this.sameGeneration(generation, await this.generation(request.sessionKey))) throw new Error("canticle host route proof lost before slot enqueue");
    let result: Awaited<ReturnType<Oc0Host["enqueue"]>>;
    try {
      result = await this.host.enqueue({ idempotencyKey: e.id, sessionKey: e.sessionKey, expectedSessionId: e.sessionId, expectedLifecycleRevision: e.lifecycleRevision, supersedeKey: e.slot,
        ...(previous ? { expectedPreviousKey: previous.id } : {}), text: frames.map((f) => f.line).join("\n"),
        deadline: e.deadline, outcomeRetention: e.retention, provenance: "canticle" });
    } catch (error) { throw error; } // leave intent; caller/restart reconciles it
    if (!result.accepted) {
      this.settle(e, "unknown", now);
      if (previous && result.previousOutcome && result.previousOutcome !== "pending") this.settle(previous, result.previousOutcome, now);
      throw new Error("OC-0 refused conditional supersede; reconcile before retry");
    }
    e.status = "pending";
    if (previous) this.settle(previous, "withdrawn", now);
    this.save();
  }
  private async withdraw(e: Entry, now: number): Promise<void> {
    if (!await this.validRoute(e.sessionKey)) throw new Error("canticle host route proof lost before OC-0 withdrawal");
    if (!this.sameGeneration(e, await this.generation(e.sessionKey))) throw new Error("canticle host generation changed before OC-0 withdrawal");
    const result = await this.host.withdraw(e.sessionKey, e.id, e.sessionId, e.lifecycleRevision);
    if (result === "pending" || result === "unknown") throw new Error("OC-0 withdrawal unresolved");
    this.settle(e, result, now);
  }
  /** Withdraw before settling a retracted frame, so a post-return drain cannot render it. */
  async retract(session: string, key: string, now: number): Promise<void> {
    const initialRouteValid = await this.validRoute(session);
    if (!initialRouteValid) return;
    await this.reconcile(session, now);
    if (!await this.validRoute(session)) return;
    for (const e of this.data.entries.filter((x) => x.sessionKey === session && x.status === "pending" && x.frames.some((f) => f.key === key))) {
      if (!await this.validRoute(session)) return;
      await this.withdraw(e, now);
    }
    const routeValid = await this.validRoute(session);
    const expiry = this.data.entries.flatMap((e) => e.frames).find((f) => f.key === key)?.expiresAt;
    if (routeValid && this.data.entries.some((e) => e.sessionKey === session && e.outcome === "consumed" && e.frames.some((f) => f.key === key)) && expiry !== undefined) {
      const noteKey = `canticle-note:${key}`;
      (this.data.notes ??= {})[noteKey] ??= { key: noteKey, expiresAt: Math.max(expiry, now + 60_000), line: `[canticle:withdrawn/expired] ${key} withdrawn/expired` };
      this.save();
    }
    if (expiry !== undefined) { this.data.settled[key] = expiry + 5000; this.save(); }
  }
  isTainted(session: string, sessionId?: string | null): boolean {
    return this.data.tainted?.[session] !== undefined || (sessionId
      ? this.data.tainted?.[`${session}\0${sessionId}`] !== undefined
      : Object.keys(this.data.tainted ?? {}).some((key) => key.startsWith(`${session}\0`)));
  }
  /** The host has cleared pending entries on reset/disable. Keep admitted frame keys settled. */
  reset(session: string, now: number, clearTaint: boolean, endedId?: string, endedRevision?: string): void {
    this.prune(now);
    for (const e of this.data.entries.filter((entry) => entry.sessionKey === session && (endedId === undefined || (entry.sessionId === endedId && (endedRevision === undefined || entry.lifecycleRevision === endedRevision))))) {
      if (e.status !== "settled") for (const f of e.frames) this.data.settled[f.key] = f.expiresAt + 5000;
      e.status = "settled"; e.outcome = "withdrawn";
    }
    if (clearTaint) {
      if (endedId && !this.data.entries.some((e) => e.sessionKey === session && e.sessionId === endedId && endedRevision !== undefined && e.lifecycleRevision !== endedRevision)) delete this.data.tainted?.[`${session}\0${endedId}`];
      else delete this.data.tainted?.[session];
    }
    if (endedId === undefined) for (const key of Object.keys(this.data.notes ?? {})) if (key.endsWith(`:${session}`)) delete this.data.notes![key];
    this.save();
  }
  /** Deleting a session removes its own admission history as well as its taint. */
  deleteSession(session: string, clearTaint: boolean, endedId?: string, endedRevision?: string): void {
    const removed = this.data.entries.filter((e) => e.sessionKey === session && (endedId === undefined || (e.sessionId === endedId && (endedRevision === undefined || e.lifecycleRevision === endedRevision))));
    this.data.entries = this.data.entries.filter((e) => e.sessionKey !== session || (endedId !== undefined && (e.sessionId !== endedId || (endedRevision !== undefined && e.lifecycleRevision !== endedRevision))));
    for (const e of removed) for (const f of e.frames) delete this.data.settled[f.key];
    if (clearTaint) {
      if (endedId && !this.data.entries.some((e) => e.sessionKey === session && e.sessionId === endedId && endedRevision !== undefined && e.lifecycleRevision !== endedRevision)) delete this.data.tainted?.[`${session}\0${endedId}`];
      else delete this.data.tainted?.[session];
    }
    if (endedId === undefined) for (const key of Object.keys(this.data.notes ?? {})) if (key.endsWith(`:${session}`)) delete this.data.notes![key];
    this.save();
  }
  /** Expiry of an already consumed item is a local event, not a daemon retract. */
  async expire(now: number): Promise<void> {
    let dirty = false;
    for (const e of this.data.entries) {
      if (e.outcome !== "consumed") continue;
      if (!await this.validRoute(e.sessionKey)) continue;
      for (const f of e.frames) {
        if (f.expiresAt > now) continue;
        const key = `canticle-note:${f.key}`;
        if (this.data.notes?.[key] || this.data.settled[f.key] === undefined || this.data.settled[key] !== undefined) continue;
        (this.data.notes ??= {})[key] = { key, expiresAt: now + 60_000, line: `[canticle:withdrawn/expired] ${f.key} withdrawn/expired` };
        dirty = true;
      }
    }
    if (dirty) this.save();
  }
  notes(session: string, now: number): SlotFrame[] {
    return Object.values(this.data.notes ?? {}).filter((n) => n.expiresAt > now && n.key.endsWith(`:${session}`) && !this.outcome(n.key));
  }
  pending(session: string): Entry[] { return this.data.entries.filter((e) => e.sessionKey === session && e.status === "pending"); }
  sessions(): string[] { return [...new Set(this.data.entries.map((e) => e.sessionKey))]; }
  keysForIdem(idem: string): { session: string; key: string }[] {
    return [...new Map(this.data.entries.flatMap((e) => e.frames.filter((f) => f.key.startsWith(`${idem}:`)).map((f) => [`${e.sessionKey}\0${f.key}`, { session: e.sessionKey, key: f.key }] as const))).values()];
  }
  outcome(key: string): boolean { return this.data.settled[key] !== undefined; }
}
