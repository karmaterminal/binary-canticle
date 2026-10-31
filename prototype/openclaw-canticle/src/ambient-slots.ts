// OC-0 adapter core. The service wires this only when both host seams exist.
// The binding owns frame keys; OC-0 owns entry outcomes. Every intent is durable before a host call.
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { readJson, writeJsonAtomic } from "./store.ts";

export type SlotKey = "canticle:digest" | "canticle:alarm";
export type EntryOutcome = "pending" | "consumed" | "withdrawn" | "expired" | "discarded" | "unknown";
export type SlotFrame = { key: string; expiresAt: number; line: string };
export type SlotRequest = { sessionKey: string; slot: SlotKey; frames: SlotFrame[] };
export type HostEntry = { idempotencyKey: string; sessionKey: string; supersedeKey: SlotKey; expectedPreviousKey?: string; text: string; deadline: number; outcomeRetention: number; provenance: "canticle" };
export type Oc0Host = {
  enqueue(entry: HostEntry): Promise<{ accepted: true } | { accepted: false; previousOutcome?: EntryOutcome }>;
  query(sessionKey: string, idempotencyKey: string): Promise<EntryOutcome>;
  withdraw(sessionKey: string, idempotencyKey: string): Promise<EntryOutcome>;
};
type Entry = { id: string; sessionKey: string; slot: SlotKey; frames: SlotFrame[]; deadline: number; retention: number; status: "enqueuing" | "pending" | "settled"; outcome?: EntryOutcome; previous?: string };
type Note = { key: string; expiresAt: number; line: string };
type Ledger = { v: 1; binding: string; entries: Entry[]; settled: Record<string, number>; tainted?: Record<string, number>; notes?: Record<string, Note> };
const SLOTS: SlotKey[] = ["canticle:digest", "canticle:alarm"];

export class AmbientSlots {
  private readonly path: string;
  private readonly binding: string;
  private readonly host: Oc0Host;
  private data: Ledger;
  constructor(root: string, binding: string, host: Oc0Host) {
    this.path = join(root, "ambient-slots.json"); this.binding = binding; this.host = host;
    this.data = { v: 1, binding, entries: [], settled: {}, tainted: {}, notes: {} };
  }
  private save(): void { writeJsonAtomic(this.path, this.data); }
  load(): void {
    const raw = readJson(this.path);
    if (raw === null) return;
    if (!raw || typeof raw !== "object" || (raw as Ledger).v !== 1 || (raw as Ledger).binding !== this.binding ||
      !Array.isArray((raw as Ledger).entries) || typeof (raw as Ledger).settled !== "object") throw new Error("invalid ambient slot ledger");
    const d = raw as Ledger;
    if (d.entries.length > 8192 || d.entries.some((e) => !e || typeof e.id !== "string" || !SLOTS.includes(e.slot) ||
      typeof e.sessionKey !== "string" || !Array.isArray(e.frames) || e.frames.length > 5 ||
      e.frames.some((f) => typeof f.key !== "string" || !Number.isSafeInteger(f.expiresAt) || typeof f.line !== "string") ||
      !["enqueuing", "pending", "settled"].includes(e.status))) throw new Error("invalid ambient slot entries");
    if (d.tainted !== undefined && (!d.tainted || typeof d.tainted !== "object" || Object.values(d.tainted).some((n) => !Number.isSafeInteger(n)))) throw new Error("invalid ambient taint");
    if (d.notes !== undefined && (!d.notes || typeof d.notes !== "object" || Object.values(d.notes).some((n) => !n || typeof n.key !== "string" || !Number.isSafeInteger(n.expiresAt) || typeof n.line !== "string"))) throw new Error("invalid ambient notes");
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
    if (outcome === "consumed") (this.data.tainted ??= {})[e.sessionKey] ??= now;
    if (outcome === "consumed" || outcome === "discarded") for (const f of e.frames) this.data.settled[f.key] = f.expiresAt + 5000;
    if (outcome === "expired") for (const f of e.frames) if (f.expiresAt <= now) this.data.settled[f.key] = f.expiresAt + 5000;
    this.save();
  }
  /** Query every ambiguous entry before allowing this session to deliver again. A failed query fails closed. */
  async reconcile(session: string, now: number): Promise<void> {
    this.prune(now);
    for (const e of this.data.entries.filter((x) => x.sessionKey === session && x.status !== "settled")) {
      const outcome = await this.host.query(session, e.id);
      if (outcome === "pending") { e.status = "pending"; this.save(); }
      else this.settle(e, outcome, now);
    }
  }
  /** Rebuilds one of the two slots, retaining only live, unconsumed frame keys. */
  async sync(request: SlotRequest, now: number): Promise<void> {
    if (!SLOTS.includes(request.slot)) throw new Error("invalid canticle slot");
    await this.reconcile(request.sessionKey, now);
    const previous = this.active(request.sessionKey, request.slot);
    const unique = new Map<string, SlotFrame>();
    for (const f of request.frames) if (f.expiresAt > now && this.data.settled[f.key] === undefined) unique.set(f.key, f);
    const frames = [...unique.values()].slice(0, 5);
    if (Buffer.byteLength(frames.map((f) => f.line).join("\n")) > 1536) throw new Error("ambient slot exceeds byte bound");
    const same = previous?.status === "pending" && previous.frames.length === frames.length &&
      previous.frames.every((f, i) => f.key === frames[i]?.key && f.line === frames[i]?.line);
    if (same) return;
    if (!frames.length) { if (previous) await this.withdraw(previous, now); return; }
    // A supersession may carry only confirmed-pending keys; consumed predecessors were settled above.
    if (this.data.entries.length >= 8192) throw new Error("ambient slot ledger full");
    const e: Entry = { id: `canticle-slot:${randomUUID()}`, sessionKey: request.sessionKey, slot: request.slot,
      frames, deadline: Math.min(...frames.map((f) => f.expiresAt)), retention: Math.max(...frames.map((f) => f.expiresAt)),
      status: "enqueuing", ...(previous ? { previous: previous.id } : {}) };
    this.data.entries.push(e); this.save();
    let result: Awaited<ReturnType<Oc0Host["enqueue"]>>;
    try {
      result = await this.host.enqueue({ idempotencyKey: e.id, sessionKey: e.sessionKey, supersedeKey: e.slot,
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
    const result = await this.host.withdraw(e.sessionKey, e.id);
    if (result === "pending" || result === "unknown") throw new Error("OC-0 withdrawal unresolved");
    this.settle(e, result, now);
  }
  /** Withdraw before settling a retracted frame, so a post-return drain cannot render it. */
  async retract(session: string, key: string, now: number): Promise<void> {
    await this.reconcile(session, now);
    for (const e of this.data.entries.filter((x) => x.sessionKey === session && x.status === "pending" && x.frames.some((f) => f.key === key))) await this.withdraw(e, now);
    const expiry = this.data.entries.flatMap((e) => e.frames).find((f) => f.key === key)?.expiresAt;
    if (this.data.entries.some((e) => e.sessionKey === session && e.outcome === "consumed" && e.frames.some((f) => f.key === key)) && expiry !== undefined) {
      const noteKey = `canticle-note:${key}`;
      (this.data.notes ??= {})[noteKey] ??= { key: noteKey, expiresAt: Math.max(expiry, now + 60_000), line: `[canticle:withdrawn/expired] ${key} withdrawn/expired` };
      this.save();
    }
    if (expiry !== undefined) { this.data.settled[key] = expiry + 5000; this.save(); }
  }
  isTainted(session: string): boolean { return this.data.tainted?.[session] !== undefined; }
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
