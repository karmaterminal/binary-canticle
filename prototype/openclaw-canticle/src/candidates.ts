// Durable, non-delivering ambient candidate ledger. No host queue, prompt hook, or wake call exists here.
import { join } from "node:path";
import { randomInt } from "node:crypto";
import { type Subscription } from "./config.ts";
import { type HeardFrame, isObj } from "./records.ts";
import { readJson, writeJsonAtomic } from "./store.ts";

export type RouteProof = (sessionKey: string) => Promise<{ sessionKey: string; exists: boolean; onHost: boolean }>;
export type Candidate = { key: string; sessionKey: string; subscriptionIds: string[]; run: string; station: string; stream: string; class: string; scope: string | null; lens: number | null; heardAt: number; expiresAt: number; eligibleAt: number; line: string };
type Ledger = { v: 1; binding: string; pending: Record<string, Candidate>; settled: Record<string, number>; spend: Record<string, number[]> };
export type LogicalSlot = { key: "canticle:digest" | "canticle:alarm"; items: Candidate[]; text: string; expiresAt: number };
const MAX_PENDING = 4096;
const MAX_SETTLED = 8192;
const MAX_BYTES = 1536;

function match(list: string[], value: string | number | null): boolean {
  if (typeof value === "number") value = String(value);
  return list.length === 0 || (value !== null && list.some((v) => v === "*" || v === value || (v.endsWith(".*") && value.startsWith(v.slice(0, -1)))));
}

export class Candidates {
  private readonly path: string;
  private readonly binding: string;
  private readonly subscriptions: Subscription[];
  private readonly route: RouteProof;
  private data: Ledger;
  private readonly proven = new Set<string>();
  private readonly retractedInFlight = new Set<string>();
  private readonly cancelledRuns = new Set<string>();
  constructor(root: string, binding: string, subscriptions: Subscription[], route: RouteProof) {
    this.path = join(root, "candidates.json");
    this.binding = binding;
    this.subscriptions = subscriptions;
    this.route = route;
    this.data = { v: 1, binding, pending: {}, settled: {}, spend: {} };
  }
  load(now: number): void {
    const raw = readJson(this.path);
    if (raw !== null) {
      if (!isObj(raw) || raw.v !== 1 || raw.binding !== this.binding || !isObj(raw.pending) || !isObj(raw.settled) || !isObj(raw.spend)) throw new Error("candidate ledger is not this binding's state");
      const d = raw as unknown as Ledger;
      if (Object.keys(d.pending).length > MAX_PENDING || Object.keys(d.settled).length > MAX_SETTLED || Object.keys(d.spend).length > 2048) throw new Error("candidate ledger exceeds bounds");
      for (const [key, c] of Object.entries(d.pending)) {
        if (!isObj(c) || c.key !== key || typeof c.sessionKey !== "string" ||
          !Array.isArray(c.subscriptionIds) || c.subscriptionIds.length > 64 || c.subscriptionIds.some((id: unknown) => typeof id !== "string") ||
          typeof c.station !== "string" || typeof c.stream !== "string" || typeof c.class !== "string" ||
          (c.scope !== null && typeof c.scope !== "string") || (c.lens !== null && !Number.isSafeInteger(c.lens)) ||
          typeof c.expiresAt !== "number" || !Number.isSafeInteger(c.expiresAt) ||
          typeof c.line !== "string" || Buffer.byteLength(c.line) > MAX_BYTES) throw new Error("candidate ledger has an invalid row");
      }
      this.data = d;
    }
    this.prune(now);
  }
  private save(): void { writeJsonAtomic(this.path, this.data); }
  private matchingSubscriptions(c: Pick<Candidate, "subscriptionIds" | "sessionKey" | "station" | "stream" | "class" | "scope" | "lens">): string[] {
    return c.subscriptionIds.filter((id) => this.subscriptions.some((s) =>
      s.id === id && s.delivery === "ambient" && s.targets.some((t) => t.sessionKey === c.sessionKey) &&
      match(s.stations, c.station) && match(s.streams, c.stream) && match(s.classes, c.class) &&
      match(s.scopes, c.scope) && match(s.lenses, c.lens)));
  }
  private async validRoute(sessionKey: string): Promise<boolean> {
    try {
      const proof = await this.route(sessionKey);
      const valid = proof !== null && proof.sessionKey === sessionKey && proof.exists === true && proof.onHost === true;
      if (valid) this.proven.add(sessionKey); else this.proven.delete(sessionKey);
      return valid;
    } catch { this.proven.delete(sessionKey); return false; }
  }
  /** A subscription can broaden receiver acceptance only with a proven local target. */
  async acceptsAmbient(frame: HeardFrame): Promise<boolean> {
    for (const s of this.subscriptions) {
      if (s.delivery !== "ambient" || !match(s.stations, frame.station) || !match(s.streams, frame.stream) ||
        !match(s.classes, frame.class) || !match(s.scopes, frame.scope) || !match(s.lenses, frame.lens)) continue;
      for (const t of s.targets) if (await this.validRoute(t.sessionKey)) return true;
    }
    return false;
  }
  async preflightRoutes(): Promise<void> {
    for (const key of new Set(this.subscriptions.flatMap((s) => s.delivery === "ambient" ? s.targets.map((t) => t.sessionKey) : []))) await this.validRoute(key);
  }
  /** Cached preflight gates receiver acceptance; admission refreshes the proof before persistence. */
  matchesAmbient(frame: HeardFrame): boolean {
    return this.subscriptions.some((s) => s.delivery === "ambient" &&
      match(s.stations, frame.station) && match(s.streams, frame.stream) &&
      match(s.classes, frame.class) && match(s.scopes, frame.scope) && match(s.lenses, frame.lens) &&
      s.targets.some((t) => this.proven.has(t.sessionKey)));
  }
  private prune(now: number): void {
    let dirty = false;
    for (const [key, c] of Object.entries(this.data.pending)) {
      const validIds = this.matchingSubscriptions(c);
      if (c.expiresAt <= now || validIds.length === 0) {
        delete this.data.pending[key]; this.data.settled[key] = Math.max(now, c.expiresAt) + 5000; dirty = true;
      } else if (validIds.length !== c.subscriptionIds.length) {
        c.subscriptionIds = validIds; dirty = true;
      }
    }
    for (const [key, until] of Object.entries(this.data.settled)) if (until <= now) { delete this.data.settled[key]; dirty = true; }
    for (const [id, times] of Object.entries(this.data.spend)) {
      const recent = times.filter((t) => t > now - 3_600_000);
      if (recent.length !== times.length) { this.data.spend[id] = recent; dirty = true; }
    }
    if (dirty) this.save();
  }
  tick(now: number): void { this.prune(now); }
  /** A route proof must come from the host, never from the frame or the subscription itself. */
  async accept(frame: HeardFrame, run: string, now: number, self: boolean, muted: boolean): Promise<number> {
    this.prune(now);
    if (muted || frame.times.local_expiry_at <= now || Object.keys(this.data.pending).length >= MAX_PENDING || Object.keys(this.data.settled).length >= MAX_SETTLED) return 0;
    let added = 0;
    for (const sub of this.subscriptions) {
      if (sub.delivery !== "ambient" || (self && !sub.stations.includes(frame.station)) || !match(sub.stations, frame.station) || !match(sub.streams, frame.stream) || !match(sub.classes, frame.class) || !match(sub.scopes, frame.scope) || !match(sub.lenses, frame.lens)) continue;
      for (const target of sub.targets) {
        if (!await this.validRoute(target.sessionKey)) continue;
        if (this.retractedInFlight.has(frame.idem) || this.cancelledRuns.has(run)) continue;
        const spendKey = `${sub.id}:${target.sessionKey}`;
        const spent = this.data.spend[spendKey] ?? [];
        const key = `${frame.idem}:${target.sessionKey}`;
        const existing = this.data.pending[key];
        if (existing?.subscriptionIds.includes(sub.id) || spent.length >= sub.perHour) continue;
        if (existing) {
          existing.subscriptionIds.push(sub.id);
          spent.push(now); this.data.spend[spendKey] = spent; this.save();
          continue;
        }
        if (this.data.settled[key] !== undefined || Object.keys(this.data.pending).length >= MAX_PENDING) continue;
        const line = `${frame.station}:${frame.stream} ${frame.class} scope=${frame.scope ?? "unavailable"} lens=${frame.lens ?? "unavailable"} item=${frame.epoch}/${frame.seq} expires=${new Date(frame.times.local_expiry_at).toISOString()}`;
        if (Buffer.byteLength(line) > MAX_BYTES) continue;
        const delayed = ["chatter", "ambient", "advisory"].includes(frame.class);
        const window = Math.min(60_000, frame.times.local_expiry_at - now - 1000);
        if (delayed && window <= 0) continue;
        const eligibleAt = delayed ? now + randomInt(window + 1) : now;
        this.data.pending[key] = { key, sessionKey: target.sessionKey, subscriptionIds: [sub.id], run, station: frame.station, stream: frame.stream, class: frame.class, scope: frame.scope, lens: frame.lens, heardAt: frame.times.heard_at, expiresAt: frame.times.local_expiry_at, eligibleAt, line };
        spent.push(now);
        this.data.spend[spendKey] = spent;
        added++;
        this.save();
      }
    }
    return added;
  }
  retract(idem: string, now: number): void {
    this.retractedInFlight.add(idem);
    for (const [key, c] of Object.entries(this.data.pending)) if (key.startsWith(`${idem}:`)) { delete this.data.pending[key]; this.data.settled[key] = c.expiresAt + 5000; }
    this.prune(now); this.save();
  }
  rejoin(run: string, now: number): void {
    this.cancelledRuns.add(run);
    for (const [key, c] of Object.entries(this.data.pending)) if (c.run === run) { delete this.data.pending[key]; this.data.settled[key] = c.expiresAt + 5000; }
    this.prune(now); this.save();
  }
  /** Read-only logical slots for a later OC-0 adapter; never enqueued or shown to a model. */
  async slots(sessionKey: string, now: number): Promise<LogicalSlot[]> {
    this.prune(now);
    if (!await this.validRoute(sessionKey)) return [];
    const rows = Object.values(this.data.pending).filter((c) => c.sessionKey === sessionKey && c.expiresAt > now && c.eligibleAt <= now);
    return (["canticle:digest", "canticle:alarm"] as const).flatMap((slot) => {
      const chosen: Candidate[] = []; let bytes = 0;
      for (const c of rows.filter((r) => (r.class === "alarm") === (slot === "canticle:alarm")).sort((a, b) => a.expiresAt - b.expiresAt || b.heardAt - a.heardAt)) {
        const size = Buffer.byteLength(c.line) + (chosen.length ? 1 : 0);
        if (chosen.length >= 5 || bytes + size > MAX_BYTES) continue;
        chosen.push(c); bytes += size;
      }
      return chosen.length ? [{ key: slot, items: chosen, text: chosen.map((c) => c.line).join("\n"), expiresAt: Math.min(...chosen.map((c) => c.expiresAt)) }] : [];
    });
  }
  get pendingCount(): number { return Object.keys(this.data.pending).length; }
}
