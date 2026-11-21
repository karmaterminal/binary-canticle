// Offline receiver-policy experiment for #120, not an installed profile or a host wake implementation.
// Input records are fixtures of an already-admitted receptor; this module does not verify signatures.
// Deliberately independent of Binding, tools, session routes, clocks, sockets and publication.

import { createHash } from "node:crypto";
import { parseTune, type Tune } from "./config.ts";
import {
  heardFrameOf, idemOf, isDeliverable, isObj, isStationName, isStreamName,
  retractOf, versionOf, type HeardFrame, type Obj,
} from "./records.ts";

export const SHADOW_V = "canticle-receptor-shadow/1";
const HOUR = 3_600_000;
const MAX_IDENTITIES = 4_096;
const MAX_RECEIPTS = 128;
const KEY = /^[0-9a-f]{16}$/;
const HASH = /^[0-9a-f]{64}$/;

export type SourceGrant = { keyId: string; station: string; streams: string[]; classes: string[]; scopes: string[] };
export type ShadowCeiling = {
  revision: number; sources: SourceGrant[]; selfKeyId: string | null;
  ambient: boolean; wakePreview: boolean; freshnessMs: number;
  maxBatchItems: number; maxBatchBytes: number; maxPendingItems: number; maxPendingBytes: number;
  maxBatchesPerHour: number; minBatchIntervalMs: number;
};
export type ShadowProfile = {
  id: string; revision: number; tune: Tune[]; classes: string[] | null; scopes: string[] | null;
  mode: "ringbuffer_only" | "ambient"; wakeOnAlarm: boolean; freshnessMs: number;
  batch: { count: number; quietMs: number; maxWaitMs: number; maxItems: number; maxBytes: number; perSource: number };
};
export type ShadowPolicy = { v: typeof SHADOW_V; ceiling: ShadowCeiling; profile: ShadowProfile };
export type EffectivePolicy = {
  sources: SourceGrant[]; mode: "ringbuffer_only" | "ambient"; wakePreview: boolean; freshnessMs: number;
  batch: ShadowProfile["batch"]; maxPendingItems: number; maxPendingBytes: number;
  maxBatchesPerHour: number; minBatchIntervalMs: number; limits: string[];
};
export type ShadowItem = {
  id: string; keyId: string; station: string; stream: string; class: string; scope: string; lens: number | null;
  bodyBytes: number; bodyHash: string; stateKey: string | null; heardAt: number;
  issuedAt: number; offsetMs: number; sourceAgeAtFirstHearingMs: number | null;
  expiresAt: number; freshUntil: number; hop: number; wakeDerived: boolean | null;
  confirmation: "current" | "carried";
};
type Pending = { id: string; queuedAt: number; changedAt: number };
export type ShadowReceipt = { at: number; reason: string; item: ShadowItem | null };
export type ShadowState = {
  v: typeof SHADOW_V; now: number; policy: ShadowPolicy; effective: EffectivePolicy;
  health: "ok" | "gap" | "disconnected" | "unknown";
  items: ShadowItem[]; pending: Pending[];
  seen: { id: string; until: number }[];
  recent: ShadowReceipt[]; mutedKeys: string[]; cancelled: boolean;
  batchesAt: number[]; lastSource: string | null;
};
export type ShadowBatch = {
  evaluatedAt: number; dueAt: number; trigger: "count" | "quiet" | "max_wait";
  items: ShadowItem[]; bodyBytes: number; wouldSurface: true;
  wouldRequestWake: boolean; wakeReasons: string[]; dispatch: "none";
};
export type ShadowView = {
  at: number; effective: EffectivePolicy; health: ShadowState["health"];
  current: ShadowItem[]; carried: ShadowItem[]; pending: Pending[]; recent: ShadowReceipt[];
  cancelled: boolean; mutedKeys: string[];
  dispatch: "none"; executionLimits: string[];
};
export type ShadowStep = { state: ShadowState; batches: ShadowBatch[]; reasons: string[]; view: ShadowView };

function object(v: unknown, at: string, keys: string[]): Obj {
  if (!isObj(v)) throw new Error(`${at}: expected object`);
  for (const k of Object.keys(v)) if (!keys.includes(k)) throw new Error(`${at}: unknown key`);
  return v;
}
function integer(v: unknown, at: string, min: number, max: number, fallback?: number): number {
  if (v === undefined && fallback !== undefined) return fallback;
  if (typeof v !== "number" || !Number.isSafeInteger(v) || v < min || v > max) throw new Error(`${at}: expected integer ${min}..${max}`);
  return v;
}
function bool(v: unknown, at: string): boolean {
  if (v === undefined) return false;
  if (typeof v !== "boolean") throw new Error(`${at}: expected boolean`);
  return v;
}
function strings(v: unknown, at: string, valid: (x: string) => boolean, max = 64): string[] {
  if (!Array.isArray(v) || v.length > max || v.some(x => typeof x !== "string" || !valid(x))) throw new Error(`${at}: invalid list`);
  if (new Set(v).size !== v.length) throw new Error(`${at}: duplicate entry`);
  return [...v] as string[];
}
function streamPattern(v: string): boolean {
  return v === "*" || (v.endsWith(".*") && isStreamName(v.slice(0, -2))) || isStreamName(v);
}
function streamMatches(pattern: string, stream: string): boolean {
  return pattern === "*" || pattern === stream || (pattern.endsWith(".*") && stream.startsWith(pattern.slice(0, -1)));
}
function intersectStream(a: string, b: string): string | null {
  if (a === "*") return b;
  if (b === "*" || a === b) return a;
  if (a.endsWith(".*") && streamMatches(a, b)) return b;
  if (b.endsWith(".*") && streamMatches(b, a)) return a;
  return null;
}

/** Strict fixture contract, not the plugin config schema. Defaults are untuned and silent. */
export function parseShadowPolicy(raw: unknown): ShadowPolicy {
  const r = object(raw, "policy", ["v", "ceiling", "profile"]);
  if (r.v !== SHADOW_V) throw new Error("policy.v: unsupported shadow version");
  const c = object(r.ceiling, "ceiling", ["revision", "sources", "selfKeyId", "ambient", "wakePreview", "freshnessMs", "maxBatchItems", "maxBatchBytes", "maxPendingItems", "maxPendingBytes", "maxBatchesPerHour", "minBatchIntervalMs"]);
  if (!Array.isArray(c.sources) || c.sources.length > 64) throw new Error("ceiling.sources: expected at most 64 grants");
  const sources = c.sources.map((raw, i): SourceGrant => {
    const s = object(raw, `source[${i}]`, ["keyId", "station", "streams", "classes", "scopes"]);
    if (typeof s.keyId !== "string" || !KEY.test(s.keyId) || !isStationName(s.station)) throw new Error(`source[${i}]: exact keyId and station required`);
    return {
      keyId: s.keyId, station: s.station,
      streams: strings(s.streams, `source[${i}].streams`, streamPattern),
      classes: strings(s.classes, `source[${i}].classes`, isStationName),
      scopes: strings(s.scopes, `source[${i}].scopes`, isStationName),
    };
  });
  if (c.selfKeyId !== undefined && c.selfKeyId !== null && (typeof c.selfKeyId !== "string" || !KEY.test(c.selfKeyId))) throw new Error("ceiling.selfKeyId: expected exact keyId or null");
  const ceiling: ShadowCeiling = {
    revision: integer(c.revision, "ceiling.revision", 1, Number.MAX_SAFE_INTEGER), sources,
    selfKeyId: c.selfKeyId === undefined || c.selfKeyId === null ? null : c.selfKeyId as string,
    ambient: bool(c.ambient, "ceiling.ambient"), wakePreview: bool(c.wakePreview, "ceiling.wakePreview"),
    freshnessMs: integer(c.freshnessMs, "ceiling.freshnessMs", 1, HOUR, 120_000),
    maxBatchItems: integer(c.maxBatchItems, "ceiling.maxBatchItems", 1, 5, 5),
    maxBatchBytes: integer(c.maxBatchBytes, "ceiling.maxBatchBytes", 1, 1_536, 1_536),
    maxPendingItems: integer(c.maxPendingItems, "ceiling.maxPendingItems", 1, 256, 64),
    maxPendingBytes: integer(c.maxPendingBytes, "ceiling.maxPendingBytes", 1, 65_536, 65_536),
    maxBatchesPerHour: integer(c.maxBatchesPerHour, "ceiling.maxBatchesPerHour", 1, 120, 12),
    minBatchIntervalMs: integer(c.minBatchIntervalMs, "ceiling.minBatchIntervalMs", 5_000, HOUR, 5_000),
  };
  const p = object(r.profile, "profile", ["id", "revision", "tune", "classes", "scopes", "mode", "wakeOnAlarm", "freshnessMs", "batch"]);
  if (typeof p.id !== "string" || !/^[A-Za-z0-9_.-]{1,64}$/.test(p.id)) throw new Error("profile.id: expected local fixture label");
  const tunes = strings(p.tune ?? [], "profile.tune", x => { try { parseTune(x); return true; } catch { return false; } });
  if (p.mode !== undefined && p.mode !== "ringbuffer_only" && p.mode !== "ambient") throw new Error("profile.mode: expected ringbuffer_only or ambient");
  const b = object(p.batch ?? {}, "profile.batch", ["count", "quietMs", "maxWaitMs", "maxItems", "maxBytes", "perSource"]);
  const profile: ShadowProfile = {
    id: p.id, revision: integer(p.revision, "profile.revision", 1, Number.MAX_SAFE_INTEGER), tune: tunes.map(parseTune),
    classes: p.classes === undefined ? null : strings(p.classes, "profile.classes", isStationName),
    scopes: p.scopes === undefined ? null : strings(p.scopes, "profile.scopes", isStationName),
    mode: p.mode === "ambient" ? "ambient" : "ringbuffer_only", wakeOnAlarm: bool(p.wakeOnAlarm, "profile.wakeOnAlarm"),
    freshnessMs: integer(p.freshnessMs, "profile.freshnessMs", 1, HOUR, 120_000),
    batch: {
      count: integer(b.count, "profile.batch.count", 1, 256, 3),
      quietMs: integer(b.quietMs, "profile.batch.quietMs", 5_000, 300_000, 5_000),
      maxWaitMs: integer(b.maxWaitMs, "profile.batch.maxWaitMs", 5_000, 300_000, 30_000),
      maxItems: integer(b.maxItems, "profile.batch.maxItems", 1, 256, 5),
      maxBytes: integer(b.maxBytes, "profile.batch.maxBytes", 1, 65_536, 1_536),
      perSource: integer(b.perSource, "profile.batch.perSource", 1, 256, 2),
    },
  };
  return { v: SHADOW_V, ceiling, profile };
}

export function effectiveShadowPolicy(policy: ShadowPolicy): EffectivePolicy {
  const c = policy.ceiling, p = policy.profile;
  const sources: SourceGrant[] = [];
  for (const s of c.sources) {
    if (s.keyId === c.selfKeyId) continue;
    const streams = [...new Set(p.tune.filter(t => t.station === "*" || t.station === s.station)
      .flatMap(t => s.streams.map(x => intersectStream(x, t.stream)).filter((x): x is string => x !== null)))];
    const classes = s.classes.filter(x => p.classes === null || p.classes.includes(x));
    const scopes = s.scopes.filter(x => p.scopes === null || p.scopes.includes(x));
    if (streams.length && classes.length && scopes.length) sources.push({ ...s, streams, classes, scopes });
  }
  const mode = p.mode === "ambient" && c.ambient ? "ambient" : "ringbuffer_only";
  const limits = ["source_keys_are_fixed", "profile_can_only_narrow", "body_byte_budget_excludes_host_wrapper"];
  if (p.mode === "ambient" && !c.ambient) limits.push("ambient_above_ceiling");
  if (p.wakeOnAlarm && !c.wakePreview) limits.push("wake_preview_above_ceiling");
  if (c.selfKeyId !== null) limits.push("self_excluded");
  if (p.batch.maxItems > c.maxBatchItems || p.batch.maxBytes > c.maxBatchBytes || p.freshnessMs > c.freshnessMs || p.batch.count > c.maxPendingItems) limits.push("requested_bounds_clamped");
  return {
    sources, mode, wakePreview: mode === "ambient" && p.wakeOnAlarm && c.wakePreview,
    freshnessMs: Math.min(c.freshnessMs, p.freshnessMs),
    batch: { ...p.batch, count: Math.min(p.batch.count, c.maxPendingItems), maxItems: Math.min(p.batch.maxItems, c.maxBatchItems), maxBytes: Math.min(p.batch.maxBytes, c.maxBatchBytes), perSource: Math.min(p.batch.perSource, c.maxBatchItems) },
    maxPendingItems: c.maxPendingItems, maxPendingBytes: c.maxPendingBytes,
    maxBatchesPerHour: c.maxBatchesPerHour, minBatchIntervalMs: c.minBatchIntervalMs, limits,
  };
}

export function createShadow(rawPolicy: unknown, at = 0): ShadowState {
  const policy = parseShadowPolicy(rawPolicy);
  return {
    v: SHADOW_V, now: integer(at, "at", 0, Number.MAX_SAFE_INTEGER), policy, effective: effectiveShadowPolicy(policy),
    health: "unknown", items: [], pending: [], seen: [], recent: [], mutedKeys: [], cancelled: false,
    batchesAt: [], lastSource: null,
  };
}

function allowed(sources: SourceGrant[], row: ShadowItem): boolean {
  return sources.some(s => s.keyId === row.keyId && s.station === row.station && s.streams.some(x => streamMatches(x, row.stream)) && s.classes.includes(row.class) && s.scopes.includes(row.scope));
}
function muted(s: ShadowState, row: ShadowItem): boolean { return s.mutedKeys.includes("*") || s.mutedKeys.includes(row.keyId); }
function receipt(s: ShadowState, reason: string, item: ShadowItem | null = null): void {
  s.recent.push({ at: s.now, reason, item: item === null ? null : { ...item } });
  if (s.recent.length > MAX_RECEIPTS) s.recent.splice(0, s.recent.length - MAX_RECEIPTS);
}
function removePending(s: ShadowState, reason: string, predicate: (row: ShadowItem) => boolean): void {
  s.pending = s.pending.filter(p => {
    const row = s.items.find(x => x.id === p.id);
    if (!row || predicate(row)) { if (row) receipt(s, reason, row); return false; }
    return true;
  });
}
function age(s: ShadowState): void {
  removePending(s, "expired_pending", x => x.expiresAt <= s.now || x.freshUntil <= s.now);
  s.items = s.items.filter(x => x.expiresAt > s.now && x.freshUntil > s.now);
  s.seen = s.seen.filter(x => x.until > s.now);
  s.batchesAt = s.batchesAt.filter(x => x > s.now - HOUR);
}

function rowOf(f: HeardFrame, now: number, freshness: number): ShadowItem | null {
  const body = f.body ?? f.body_ref;
  if (!body || !HASH.test(body.sha256) || !Number.isSafeInteger(body.size) || body.size < 0 || body.size > 65_536 || f.scope === null) return null;
  if (f.times.heard_at < 0 || f.times.heard_at > now || f.times.local_expiry_at < 0 || f.times.expires_at < f.times.issued_at || f.hop < 0) return null;
  if (f.body) {
    const bytes = f.body.text !== undefined ? Buffer.from(f.body.text, "utf8") : Buffer.from(f.body.base64 ?? "", "base64");
    if (bytes.length !== body.size || createHash("sha256").update(bytes).digest("hex") !== body.sha256) return null;
  }
  const localIssuedAt = f.times.issued_at + f.times.offset_ms;
  if (!Number.isSafeInteger(localIssuedAt)) return null;
  return {
    id: f.idem, keyId: f.key_id, station: f.station, stream: f.stream, class: f.class, scope: f.scope, lens: f.lens,
    bodyBytes: body.size, bodyHash: body.sha256, stateKey: f.state_key, heardAt: f.times.heard_at,
    issuedAt: f.times.issued_at, offsetMs: f.times.offset_ms,
    sourceAgeAtFirstHearingMs: localIssuedAt <= f.times.heard_at ? f.times.heard_at - localIssuedAt : null,
    expiresAt: f.times.local_expiry_at, freshUntil: Math.min(f.times.local_expiry_at, f.times.heard_at + freshness),
    hop: f.hop, wakeDerived: f.flags.wake_derived, confirmation: "current",
  };
}

// A newly admitted value for the same state key is a withdrawal of the old value before presentation,
// even when its arrival coincides with a due timer. An unrelated arrival must not move that timer.
function supersedeBeforeFlush(s: ShadowState, raw: unknown): number | null {
  if (!isObj(raw) || versionOf(raw) !== "v1" || raw.type !== "frame" || !isDeliverable(raw)) return null;
  const f = heardFrameOf(raw), row = f ? rowOf(f, s.now, s.effective.freshnessMs) : null;
  if (!row || row.stateKey === null || s.seen.some(x => x.id === row.id) || row.expiresAt <= s.now || row.freshUntil <= s.now || !allowed(s.effective.sources, row)) return null;
  const replaced = (x: ShadowItem) => x.keyId === row.keyId && x.stream === row.stream && x.stateKey === row.stateKey;
  const oldIds = new Set(s.items.filter(replaced).map(x => x.id));
  const oldPending = s.pending.filter(x => oldIds.has(x.id));
  const startedAt = oldPending.length ? Math.min(...oldPending.map(x => x.queuedAt)) : null;
  removePending(s, "superseded_pending", replaced);
  s.items = s.items.filter(x => !replaced(x));
  return startedAt;
}

function ingest(s: ShadowState, raw: unknown, snapshot: boolean, reasons: string[], startedAt: number | null): void {
  if (!isObj(raw) || versionOf(raw) !== "v1" || raw.type !== "frame" || !isDeliverable(raw)) { reasons.push("not_admitted_frame"); return; }
  const f = heardFrameOf(raw), row = f ? rowOf(f, s.now, s.effective.freshnessMs) : null;
  if (!f || !row) { reasons.push("malformed_frame"); return; }
  if (row.keyId === s.policy.ceiling.selfKeyId || !allowed(s.policy.ceiling.sources, row)) { reasons.push("outside_operator_ceiling"); return; }
  if (row.expiresAt <= s.now || row.freshUntil <= s.now) { reasons.push("expired_or_stale"); return; }
  const old = s.items.find(x => x.id === row.id);
  if (s.seen.some(x => x.id === row.id)) {
    if (old && (old.bodyHash !== row.bodyHash || old.expiresAt !== row.expiresAt || old.heardAt !== row.heardAt)) { reasons.push("identity_conflict"); return; }
    if (old && s.health === "ok") old.confirmation = "current";
    reasons.push("duplicate_identity");
    return; // no new dose, budget charge, clock reset, or replay after mute/cancel/gap
  }
  if (s.seen.length >= MAX_IDENTITIES) { reasons.push("identity_capacity"); return; }
  s.seen.push({ id: row.id, until: row.expiresAt });
  if (!allowed(s.effective.sources, row)) { reasons.push("outside_receiver_profile"); return; }
  if (row.stateKey !== null) {
    const replaced = (x: ShadowItem) => x.keyId === row.keyId && x.stream === row.stream && x.stateKey === row.stateKey;
    removePending(s, "superseded_pending", replaced);
    s.items = s.items.filter(x => !replaced(x));
  }
  // Current-view retention shares the hard queue bounds, so a fixture cannot grow a hidden backlog.
  if (s.items.length >= s.effective.maxPendingItems || s.items.reduce((n, x) => n + x.bodyBytes, 0) + row.bodyBytes > s.effective.maxPendingBytes) { reasons.push("current_capacity"); return; }
  row.confirmation = s.health === "ok" ? "current" : "carried";
  s.items.push(row);
  receipt(s, "received", row);
  const reason = s.cancelled ? "profile_cancelled" : muted(s, row) ? "muted" : s.health !== "ok" ? `receiver_${s.health}` : snapshot ? "snapshot_read_only" : f.dedup === "resurfaced" ? "resurfaced_read_only" : f.flags.refresh ? "refresh_read_only" : s.effective.mode !== "ambient" ? "ringbuffer_only" : row.bodyBytes > s.effective.batch.maxBytes ? "item_exceeds_batch_bytes" : null;
  if (reason) { reasons.push(reason); return; }
  s.pending.push({ id: row.id, queuedAt: startedAt ?? s.now, changedAt: s.now });
  reasons.push("queued");
}

function flush(s: ShadowState, batches: ShadowBatch[], reasons: string[]): void {
  if (!s.pending.length || s.cancelled || s.health !== "ok" || s.effective.mode !== "ambient") return;
  const pending = [...s.pending].sort((a, b) => a.queuedAt - b.queuedAt || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const changes = pending.map(x => x.changedAt).sort((a, b) => a - b);
  const first = pending[0]!, lastChangedAt = changes.at(-1)!, b = s.effective.batch;
  const deadlines: { at: number; trigger: ShadowBatch["trigger"] }[] = [
    { at: first.queuedAt + b.maxWaitMs, trigger: "max_wait" },
    { at: lastChangedAt + b.quietMs, trigger: "quiet" },
  ];
  if (pending.length >= b.count) deadlines.unshift({ at: changes[b.count - 1]!, trigger: "count" });
  deadlines.sort((a, b) => a.at - b.at); // count, max_wait, quiet is the tie order
  const due = deadlines[0]!;
  if (due.at > s.now) { reasons.push("batch_waiting"); return; }
  if (s.now < first.queuedAt + 5_000) { reasons.push("coalesce_minimum"); return; }
  const lastBatch = s.batchesAt.at(-1);
  if (lastBatch !== undefined && s.now < lastBatch + s.effective.minBatchIntervalMs) { reasons.push("batch_cooldown"); return; }
  if (s.batchesAt.length >= s.effective.maxBatchesPerHour) { reasons.push("batch_hour_budget"); return; }
  const queues = new Map<string, ShadowItem[]>();
  for (const p of pending) {
    const row = s.items.find(x => x.id === p.id);
    if (row && !muted(s, row)) queues.set(row.keyId, [...(queues.get(row.keyId) ?? []), row]);
  }
  const keys = [...queues.keys()].sort();
  // Rotate after the last selected signer; one slot per signer per round, including across batches.
  const start = s.lastSource === null ? 0 : keys.findIndex(k => k > s.lastSource!);
  const order = [...keys.slice(start < 0 ? 0 : start), ...keys.slice(0, start < 0 ? 0 : start)];
  const selected: ShadowItem[] = [];
  let bytes = 0;
  for (let round = 0; round < b.perSource && selected.length < b.maxItems; round++) {
    for (const key of order) {
      const row = queues.get(key)?.[round];
      if (!row || bytes + row.bodyBytes > b.maxBytes) continue;
      selected.push({ ...row }); bytes += row.bodyBytes; s.lastSource = key;
      if (selected.length === b.maxItems) break;
    }
  }
  if (!selected.length) { reasons.push("no_item_fits_batch"); return; }
  const ids = new Set(selected.map(x => x.id));
  s.pending = s.pending.filter(p => !ids.has(p.id));
  s.batchesAt.push(s.now);
  const wakeReasons = !s.effective.wakePreview ? ["wake_preview_not_elected_or_permitted"] : [];
  const directAlarms = selected.filter(x => x.class === "alarm" && x.hop === 0 && x.wakeDerived === false && x.sourceAgeAtFirstHearingMs !== null && x.sourceAgeAtFirstHearingMs <= 120_000 && s.now - x.heardAt <= 120_000);
  const aspect = (x: ShadowItem) => x.lens !== null || x.stream.startsWith("lens.");
  // RFC §14.10 item 3: neither public scope nor a known aspect can become wake-eligible.
  if (directAlarms.some(x => x.scope === "public")) wakeReasons.push("public_scope_never_wakes");
  if (directAlarms.some(aspect)) wakeReasons.push("aspect_stream_never_wakes");
  const eligibleAlarm = directAlarms.some(x => x.scope !== "public" && !aspect(x));
  if (!eligibleAlarm) wakeReasons.push("no_wake_eligible_alarm");
  const wouldRequestWake = s.effective.wakePreview && eligibleAlarm;
  if (wouldRequestWake) wakeReasons.push("receiver_policy_would_request", "alarm_capability_and_host_proofs_not_evaluated");
  const batch: ShadowBatch = { evaluatedAt: s.now, dueAt: due.at, trigger: due.trigger, items: selected, bodyBytes: bytes, wouldSurface: true, wouldRequestWake, wakeReasons, dispatch: "none" };
  batches.push(batch);
  for (const row of selected) receipt(s, "would_surface", row);
}

function changePolicy(s: ShadowState, raw: unknown): void {
  const policy = parseShadowPolicy(raw), old = s.policy;
  if (policy.profile.id !== old.profile.id) throw new Error("policy: cannot change receiver label within a fixture");
  for (const key of ["ceiling", "profile"] as const) {
    if (policy[key].revision < old[key].revision || (JSON.stringify(policy[key]) !== JSON.stringify(old[key]) && policy[key].revision === old[key].revision)) throw new Error(`policy.${key}: changes require a higher revision`);
  }
  s.policy = policy; s.effective = effectiveShadowPolicy(policy);
  removePending(s, "policy_revoked_pending", x => !allowed(s.effective.sources, x) || s.effective.mode !== "ambient" || x.bodyBytes > s.effective.batch.maxBytes);
  s.items = s.items.filter(x => allowed(s.effective.sources, x));
  // Tightening freshness is irreversible for an observed item; broadening never adds life or requeues.
  for (const x of s.items) x.freshUntil = Math.min(x.freshUntil, x.heardAt + s.effective.freshnessMs);
  s.recent = s.recent.filter(r => r.item === null || allowed(policy.ceiling.sources, r.item));
  age(s);
  while (s.items.length > s.effective.maxPendingItems || s.items.reduce((n, x) => n + x.bodyBytes, 0) > s.effective.maxPendingBytes) {
    const row = s.items.at(-1)!;
    removePending(s, "policy_capacity", x => x.id === row.id);
    s.items.pop();
  }
}

/** Pure advance: control events cancel first; a new frame cannot postpone a deadline already due. */
export function advanceShadow(previous: ShadowState, rawEvent: unknown): ShadowStep {
  const e = object(rawEvent, "event", ["at", "op", "record", "snapshot", "health", "keyId", "policy"]);
  const fields: Record<string, string[]> = { record: ["record", "snapshot"], retract: ["record"], health: ["health"], mute: ["keyId"], unmute: ["keyId"], cancel: [], policy: ["policy"], tick: [] };
  if (typeof e.op !== "string" || !Object.hasOwn(fields, e.op)) throw new Error("event.op: unsupported operation");
  object(e, "event", ["at", "op", ...fields[e.op]!]);
  const s = structuredClone(previous), batches: ShadowBatch[] = [], reasons: string[] = [];
  s.now = integer(e.at, "event.at", previous.now, Number.MAX_SAFE_INTEGER);
  age(s);
  switch (e.op) {
    case "record": {
      const startedAt = supersedeBeforeFlush(s, e.record);
      flush(s, batches, reasons);
      ingest(s, e.record, bool(e.snapshot, "event.snapshot"), reasons, startedAt);
      break;
    }
    case "retract": {
      if (!isObj(e.record) || versionOf(e.record) !== "v1" || e.record.type !== "retract") throw new Error("event.record: expected v1 retract");
      const r = retractOf(e.record);
      if (!r) throw new Error("event.record: malformed retract");
      const target = idemOf(r.target.key_id, r.target.epoch, r.target.stream_id, r.target.seq);
      removePending(s, "withdrawn_pending", x => x.id === target);
      const row = s.items.find(x => x.id === target);
      if (row) receipt(s, "withdrawn", row);
      s.items = s.items.filter(x => x.id !== target);
      reasons.push("withdrawn_or_not_observed");
      break;
    }
    case "health":
      if (!["ok", "gap", "disconnected", "unknown"].includes(e.health as string)) throw new Error("event.health: invalid receiver health");
      s.health = e.health as ShadowState["health"];
      if (s.health !== "ok") {
        removePending(s, "continuity_lost_pending", () => true);
        for (const row of s.items) row.confirmation = "carried";
      }
      reasons.push(s.health === "ok" ? "receiver_ok_requires_item_reconfirmation" : "current_view_unknown_not_absence");
      break;
    case "mute": case "unmute": {
      if (e.keyId !== "*" && (typeof e.keyId !== "string" || !KEY.test(e.keyId))) throw new Error("event.keyId: expected exact keyId or *");
      const key = e.keyId as string;
      if (e.op === "mute") {
        if (!s.mutedKeys.includes(key)) {
          if (s.mutedKeys.length >= 65) throw new Error("mute capacity");
          s.mutedKeys.push(key);
        }
        removePending(s, "muted_pending", x => key === "*" || x.keyId === key);
      } else s.mutedKeys = s.mutedKeys.filter(x => x !== key);
      reasons.push(e.op === "mute" ? "muted" : "unmuted_no_replay");
      break;
    }
    case "cancel":
      s.cancelled = true; removePending(s, "cancelled_pending", () => true); reasons.push("profile_cancelled"); break;
    case "policy": changePolicy(s, e.policy); reasons.push("policy_reconciled_no_replay"); break;
    case "tick": break;
    default: throw new Error("event.op: unsupported operation");
  }
  flush(s, batches, reasons);
  return { state: s, batches, reasons: [...new Set(reasons)], view: inspectShadow(s) };
}

export function inspectShadow(s: ShadowState): ShadowView {
  const rows = s.items.filter(x => !muted(s, x) && allowed(s.effective.sources, x) && x.freshUntil > s.now && x.expiresAt > s.now);
  return structuredClone({
    at: s.now, effective: s.effective, health: s.health,
    current: rows.filter(x => s.health === "ok" && x.confirmation === "current"),
    carried: rows.filter(x => s.health !== "ok" || x.confirmation === "carried"),
    pending: s.pending, recent: s.recent, cancelled: s.cancelled, mutedKeys: s.mutedKeys,
    dispatch: "none", executionLimits: ["offline_fixture_only", "signatures_not_verified", "no_profile_installed", "no_session_route_or_host_proofs", "wake_not_implemented", "no_publication", "no_elected_retention_store"],
  });
}

/** A bounded timeline; returned reports contain metadata, never the fixture's body text. */
export function previewShadow(raw: unknown): { v: typeof SHADOW_V; steps: Omit<ShadowStep, "state">[]; final: ShadowView } {
  const r = object(raw, "fixture", ["v", "policy", "events"]);
  if (r.v !== SHADOW_V) throw new Error("fixture.v: unsupported shadow version");
  if (!Array.isArray(r.events) || r.events.length > 2_048) throw new Error("fixture.events: expected at most 2048 events");
  let state = createShadow(r.policy);
  let reportBytes = 0;
  const steps: Omit<ShadowStep, "state">[] = [];
  for (const event of r.events) {
    const result = advanceShadow(state, event);
    state = result.state;
    const step = { batches: result.batches, reasons: result.reasons, view: result.view };
    reportBytes += Buffer.byteLength(JSON.stringify(step), "utf8");
    if (reportBytes > 4_194_304) throw new Error("fixture preview exceeds 4 MiB metadata report limit; shorten the timeline");
    steps.push(step);
  }
  return { v: SHADOW_V, steps, final: inspectShadow(state) };
}
