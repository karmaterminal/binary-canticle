// The outbound aging table (binary-canticle#97): one row per utterance this binding asked its station to sing,
// holding what was asked beside what the station confirmed. The station is the authority for epoch, seq and
// expiry; this table only records what it said, and what the daemon heard back.
//
// Aging is not a retry mandate:
// - A row is sent at most once. A request that was written and got no complete reply is `unknown`, never re-sent;
//   it becomes `on_air` only on evidence (this binding hearing its own frame with the same body), and otherwise
//   lapses when it could no longer be on air.
// - Nothing is inferred from a row being queued. After a restart a row that was mid-send is `unknown`, and one
//   that was never sent is `failed` (not_sent). An `on_air` row is checked against the station's own status.
// - A withdrawn, expired, superseded or stopped row is never sung again. An idempotency key (the caller's, or one
//   derived from the session and content while the row is live) returns the existing row instead of a second item.

import { createHash } from "node:crypto";
import { secretFindings } from "./policy.ts";
import { type HeardFrame, type Obj, type Retract, STREAM_NAME, idemOf, isObj, streamIdOf } from "./records.ts";
import type { StationClient } from "./station.ts";
import { readJson, writeJsonAtomic } from "./store.ts";

export type RowState = "pending" | "unknown" | "on_air" | "withdrawn" | "expired" | "superseded" | "stopped" | "failed";
const TERMINAL: ReadonlySet<RowState> = new Set(["withdrawn", "expired", "superseded", "stopped", "failed"]);

export type Receipt = {
  epoch: number;
  seq: number;
  issued_at: number;
  expires_at: number;
  ttl_s: number;
  loop_ms: number | null;
  clamp: string | null;
  size: number | null;
};

export type Row = {
  id: string;
  key: string;
  key_source: "caller" | "content";
  session: string;
  station: string;
  key_id: string;
  stream: string;
  stream_id: number;
  class: string | null;
  state_key: string | null;
  purpose: string | null;
  body: { sha256: string; size: number };
  /** The text, held only until the request is attempted. Results never echo it (§15.1). */
  text: string | null;
  ttl_s: number | null;
  created_at: number;
  state: RowState;
  attempted_at: number | null;
  /** The latest moment the item could still be on air, set when it is attempted. */
  latest_expiry: number | null;
  receipt: Receipt | null;
  idem: string | null;
  heard_at: number | null;
  withdraw: { requested_at: number; by: string; attempts: number; outcome: string | null } | null;
  ended: { at: number; reason: string } | null;
  last: { at: number; event: string };
};

export type SingRequest = {
  session: string;
  stream: string;
  text: string;
  class: string | null;
  state_key: string | null;
  purpose: string | null;
  ttl_s: number | null;
  key: string | null;
};

export type SingOutcome =
  | { status: "on-air" | "unknown" | "failed" | "ended"; row: Row; duplicate: boolean }
  | { status: "rejected"; reason: string; detail: string; row: Row | null }
  | { status: "budget_exhausted"; reason: "rate"; retryAfterMs: number; row: null };

export type HushOutcome = {
  status: "plucked" | "expired" | "not_found" | "pending" | "unknown" | "refused";
  reason?: string | undefined;
  row: Row | null;
};

export type OutboxConfig = {
  binding: string;
  station: string;
  keyId: string;
  classes: readonly string[];
  perMinute: number;
  perHour: number;
  maxLive: number;
  maxRows: number;
  keepMs: number;
  maxTextBytes: number;
};

const FILE_V = "openclaw-canticle-outbox/1";
const EVIDENCE_SLACK_MS = 2_000;
const SEND_TIMEOUT_MS = 5_000;
const STOP_BEFORE_EXPIRY_MS = 100; // the station refuses to pluck closer to expiry (station.py hush)
const KEY = /^[A-Za-z0-9._:-]{1,64}$/;
const STATE_KEY = /^[A-Za-z0-9._:/-]{1,64}$/;

export class Outbox {
  private readonly path: string;
  private readonly cfg: OutboxConfig;
  private readonly station: StationClient;
  private readonly clock: () => number;
  private rowsById = new Map<string, Row>();
  private nextId = 1;
  private chain: Promise<unknown> = Promise.resolve();
  /** What the last status call said about the station (null before any). */
  lastStation: { at: number; ok: boolean; detail: string; epoch: number | null } | null = null;
  readonly counts = { refused: 0, duplicates: 0, rate_limited: 0, evidence: 0, retracts: 0 };

  constructor(path: string, cfg: OutboxConfig, station: StationClient, clock: () => number) {
    this.path = path;
    this.cfg = cfg;
    this.station = station;
    this.clock = clock;
  }

  /** Read the table. A row that was mid-send becomes `unknown`; one never sent becomes `failed` (not_sent). */
  load(): void {
    const raw = readJson(this.path);
    if (raw === null) {
      return;
    }
    if (!isObj(raw) || raw.v !== FILE_V || raw.binding !== this.cfg.binding || !Array.isArray(raw.rows)) {
      throw new Error(`outbox ${this.path} belongs to another binding or version`);
    }
    this.nextId = typeof raw.next_id === "number" ? raw.next_id : 1;
    const now = this.clock();
    for (const r of raw.rows as Row[]) {
      if (r.state === "pending") {
        r.text = null;
        if (r.attempted_at === null) {
          this.end(r, "failed", "not_sent", now);
        } else {
          this.touch(r, "restarted_during_send", now);
          r.state = "unknown";
        }
      }
      this.rowsById.set(r.id, r);
    }
    this.save();
  }

  private save(): void {
    writeJsonAtomic(this.path, { v: FILE_V, binding: this.cfg.binding, next_id: this.nextId, rows: [...this.rowsById.values()] });
  }

  /** One operation at a time: rows, saves and station requests never interleave. */
  private exclusive<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.chain.then(fn, fn);
    this.chain = run.catch(() => undefined);
    return run;
  }

  rows(): Row[] {
    return [...this.rowsById.values()];
  }

  get(id: string): Row | undefined {
    return this.rowsById.get(id);
  }

  /** Whether ``id`` names a row of this binding, of another binding, or nothing a binding issues. */
  owner(id: string): "this" | "other" | "malformed" {
    const m = /^out:([a-z][a-z0-9-]{0,30}):(\d+)$/.exec(id);
    if (m === null) {
      return "malformed";
    }
    return m[1] === this.cfg.binding ? "this" : "other";
  }

  sing(req: SingRequest): Promise<SingOutcome> {
    return this.exclusive(() => this.singNow(req));
  }

  private async singNow(req: SingRequest): Promise<SingOutcome> {
    const now = this.clock();
    const bad = this.check(req);
    if (bad !== null) {
      this.counts.refused += 1;
      return { status: "rejected", reason: bad[0], detail: bad[1], row: null };
    }
    const sha = createHash("sha256").update(req.text, "utf8").digest("hex");
    const key =
      req.key ??
      createHash("sha256")
        .update(JSON.stringify([req.session, req.stream, req.class, req.state_key, req.text]))
        .digest("hex")
        .slice(0, 32);
    const same = [...this.rowsById.values()].find(
      (r) => r.key === key && (req.key !== null ? r.key_source === "caller" : r.key_source === "content" && !r.ended),
    );
    if (same !== undefined) {
      if (
        same.stream !== req.stream ||
        same.body.sha256 !== sha ||
        same.class !== req.class ||
        same.state_key !== req.state_key
      ) {
        this.counts.refused += 1;
        return { status: "rejected", reason: "key_conflict", detail: `${same.id} holds this key for other content`, row: same };
      }
      this.counts.duplicates += 1;
      return { status: outcomeOf(same), row: same, duplicate: true };
    }
    const wait = this.rateWait(req.session, now);
    if (wait > 0) {
      this.counts.rate_limited += 1;
      return { status: "budget_exhausted", reason: "rate", retryAfterMs: wait, row: null };
    }
    if (this.rows().filter((r) => !r.ended).length >= this.cfg.maxLive) {
      this.counts.refused += 1;
      return { status: "rejected", reason: "quota", detail: `${this.cfg.maxLive} rows are still live`, row: null };
    }
    const status = await this.station({ op: "status" });
    const verdict = this.verifyStation(status, req.stream, now);
    if (typeof verdict === "string") {
      this.counts.refused += 1;
      return { status: "rejected", reason: verdict, detail: this.lastStation?.detail ?? verdict, row: null };
    }
    const row: Row = {
      id: `out:${this.cfg.binding}:${this.nextId}`,
      key,
      key_source: req.key !== null ? "caller" : "content",
      session: req.session,
      station: this.cfg.station,
      key_id: this.cfg.keyId,
      stream: req.stream,
      stream_id: streamIdOf(req.stream),
      class: req.class,
      state_key: req.state_key,
      purpose: req.purpose,
      body: { sha256: sha, size: Buffer.byteLength(req.text) },
      text: req.text,
      ttl_s: req.ttl_s,
      created_at: now,
      state: "pending",
      attempted_at: null,
      latest_expiry: null,
      receipt: null,
      idem: null,
      heard_at: null,
      withdraw: null,
      ended: null,
      last: { at: now, event: "accepted" },
    };
    this.nextId += 1;
    this.rowsById.set(row.id, row);
    // Write-ahead: the row is durable, and marked attempted, before the station can act on it.
    row.attempted_at = now;
    row.latest_expiry = now + verdict.defaultTtlMs + SEND_TIMEOUT_MS + EVIDENCE_SLACK_MS;
    this.save();
    const sing: Obj = { op: "sing", stream: req.stream, text: req.text, scope: "lan" };
    for (const [k, v] of [
      ["class", req.class],
      ["state_key", req.state_key],
      ["purpose", req.purpose],
      ["ttl", req.ttl_s],
    ] as const) {
      if (v !== null) {
        sing[k] = v;
      }
    }
    const a = await this.station(sing);
    const at = this.clock();
    row.text = null;
    if (a.kind === "unreachable") {
      this.end(row, "failed", `station_unreachable:${a.reason}`, at);
    } else if (a.kind === "unknown") {
      row.state = "unknown";
      this.touch(row, `no_reply:${a.reason}`, at);
    } else if (a.reply.ok !== true) {
      this.end(row, "failed", `refused:${clip(a.reply.error)}`, at);
    } else {
      const receipt = receiptOf(a.reply);
      if (receipt === null || a.reply.stream !== req.stream) {
        row.state = "unknown";
        this.touch(row, "bad_reply", at);
      } else {
        this.onAir(row, receipt, "sung", at);
        const old = a.reply.superseded_seq;
        if (typeof old === "number") {
          for (const r of this.rowsById.values()) {
            if (r.state === "on_air" && r.stream === req.stream && r.receipt?.epoch === receipt.epoch && r.receipt.seq === old) {
              this.end(r, "superseded", `superseded_by:${row.id}`, at);
            }
          }
        }
      }
    }
    this.save();
    return { status: outcomeOf(row), row, duplicate: false };
  }

  private check(req: SingRequest): [string, string] | null {
    if (!STREAM_NAME.test(req.stream) || Buffer.byteLength(req.stream) > 64) {
      return ["stream", "not a stream name"];
    }
    if (req.text.length === 0) {
      return ["size", "empty payload"];
    }
    if (Buffer.byteLength(req.text) > this.cfg.maxTextBytes) {
      return ["size", `the payload is over ${this.cfg.maxTextBytes} bytes; larger content must be a reference (§15.4 item 8)`];
    }
    if (req.class !== null && !this.cfg.classes.includes(req.class)) {
      return ["capability", `class ${req.class} is not offered to sessions here`];
    }
    if (req.state_key !== null && !STATE_KEY.test(req.state_key)) {
      return ["state_key", "not a state key"];
    }
    if (req.purpose !== null && Buffer.byteLength(req.purpose) > 128) {
      return ["size", "purpose is over 128 bytes"];
    }
    if (req.ttl_s !== null && !(req.ttl_s >= 1 && req.ttl_s <= 86_400)) {
      return ["ttl", "ttlSeconds must be between 1 and 86400 (the station only shortens it)"];
    }
    if (req.key !== null && !KEY.test(req.key)) {
      return ["key", "idempotencyKey must be 1-64 of A-Z a-z 0-9 . _ : -"];
    }
    const found = secretFindings(`${req.text}\n${req.purpose ?? ""}\n${req.state_key ?? ""}`);
    if (found.length > 0) {
      return ["content_policy", `refused: looks like ${found.join(", ")} (§15.4 item 6)`];
    }
    return null;
  }

  /** Milliseconds until this session may sing again (0 when it may now). */
  private rateWait(session: string, now: number): number {
    const mine = this.rows()
      .filter((r) => r.session === session && r.attempted_at !== null)
      .map((r) => r.attempted_at as number);
    const minute = mine.filter((t) => t > now - 60_000).sort((a, b) => a - b);
    const hour = mine.filter((t) => t > now - 3_600_000).sort((a, b) => a - b);
    let wait = 0;
    if (minute.length >= this.cfg.perMinute) {
      wait = Math.max(wait, (minute[minute.length - this.cfg.perMinute] as number) + 60_000 - now);
    }
    if (hour.length >= this.cfg.perHour) {
      wait = Math.max(wait, (hour[hour.length - this.cfg.perHour] as number) + 3_600_000 - now);
    }
    return wait;
  }

  /** The station must answer, be the pinned key, and carry the stream. */
  private verifyStation(
    a: Awaited<ReturnType<StationClient>>,
    stream: string | null,
    now: number,
  ): string | { epoch: number; onAir: Map<string, Set<number>>; defaultTtlMs: number } {
    const fail = (reason: string, detail: string): string => {
      this.lastStation = { at: now, ok: false, detail, epoch: null };
      return reason;
    };
    if (a.kind !== "reply") {
      return fail("station_unreachable", `station status: ${a.reason}`);
    }
    const r = a.reply;
    if (r.ok !== true || typeof r.epoch !== "number" || !isObj(r.streams)) {
      return fail("station_unreachable", `station status refused: ${clip(r.error)}`);
    }
    if (r.key_id !== this.cfg.keyId) {
      return fail("station_key_mismatch", "the station on this socket is not the configured station key");
    }
    const onAir = new Map<string, Set<number>>();
    for (const [name, s] of Object.entries(r.streams)) {
      const seqs = new Set<number>();
      if (isObj(s) && Array.isArray(s.on_air)) {
        for (const oa of s.on_air) {
          if (isObj(oa) && oa.kind === "item" && typeof oa.seq === "number") {
            seqs.add(oa.seq);
          }
        }
      }
      onAir.set(name, seqs);
    }
    this.lastStation = { at: now, ok: true, detail: "ok", epoch: r.epoch };
    let defaultTtlMs = 3_600_000;
    if (stream !== null) {
      const s = r.streams[stream];
      if (!isObj(s)) {
        return fail("capability", `the station carries no stream ${stream}`);
      }
      if (typeof s.default_ttl_s === "number") {
        defaultTtlMs = s.default_ttl_s * 1000;
      }
    }
    return { epoch: r.epoch, onAir, defaultTtlMs };
  }

  hush(id: string, by: string): Promise<HushOutcome> {
    return this.exclusive(() => this.hushNow(id, by));
  }

  private async hushNow(id: string, by: string): Promise<HushOutcome> {
    const owner = this.owner(id);
    if (owner !== "this") {
      this.counts.refused += 1;
      return { status: "refused", reason: owner === "other" ? "not_this_binding" : "not_a_row", row: null };
    }
    const row = this.rowsById.get(id);
    if (row === undefined) {
      return { status: "not_found", reason: "no_such_row", row: null };
    }
    const now = this.clock();
    if (row.ended !== null) {
      return { status: hushStatusOf(row), row };
    }
    row.withdraw ??= { requested_at: now, by, attempts: 0, outcome: null };
    if (row.state === "unknown") {
      row.withdraw.outcome = "waiting_for_evidence";
      this.touch(row, "withdraw_requested", now);
      this.save();
      return { status: "unknown", reason: "not confirmed on air; withdrawn if it shows up", row };
    }
    // The hush op names a seq, not an epoch: pluck only after the station proves it is still the same key and
    // epoch, or a restarted station would pluck whatever now holds that seq.
    const v = this.verifyStation(await this.station({ op: "status" }), null, this.clock());
    if (typeof v === "string") {
      row.withdraw.outcome = v;
      this.touch(row, "withdraw_requested", now);
    } else if (row.receipt !== null && row.receipt.epoch !== v.epoch) {
      this.end(row, "stopped", "station_restarted", this.clock());
    } else {
      await this.pluck(row, this.clock());
    }
    this.save();
    return { status: hushStatusOf(row), reason: row.withdraw?.outcome ?? undefined, row };
  }

  /** Ask the station to pluck an on-air row; the row stays on air, withdraw pending, unless the answer settles it.
   * The caller has just checked the station's key and epoch against the row. */
  private async pluck(row: Row, now: number): Promise<void> {
    const w = row.withdraw;
    const rc = row.receipt;
    if (w === null || rc === null || row.state !== "on_air") {
      return;
    }
    if (rc.expires_at - now <= STOP_BEFORE_EXPIRY_MS) {
      this.end(row, "expired", "expired_before_pluck", now);
      return;
    }
    w.attempts += 1;
    const a = await this.station({ op: "hush", stream: row.stream, seq: rc.seq, reason: 0 });
    const at = this.clock();
    if (a.kind === "reply" && a.reply.ok === true) {
      w.outcome = `plucked:${typeof a.reply.seq === "number" ? a.reply.seq : "?"}`;
      this.end(row, "withdrawn", "plucked", at);
    } else if (a.kind === "reply") {
      const err = clip(a.reply.error);
      if (err.startsWith("no live item")) {
        // The station no longer holds it: plucked by an earlier request whose reply was lost, or gone.
        w.outcome = "not_on_station";
        if (rc.expires_at <= at + STOP_BEFORE_EXPIRY_MS) {
          this.end(row, "expired", "expired", at);
        } else {
          this.end(row, w.attempts > 1 ? "withdrawn" : "stopped", w.attempts > 1 ? "gone_after_pluck" : "not_on_station", at);
        }
      } else if (err.startsWith("target already expiring")) {
        w.outcome = "expiring";
        this.end(row, "expired", "expiring", at);
      } else {
        w.outcome = `refused:${err}`;
        this.touch(row, "pluck_refused", at);
      }
    } else {
      w.outcome = `${a.kind}:${a.reason}`;
      this.touch(row, "pluck_unconfirmed", at);
    }
  }

  /** Expire what has passed its expiry, check on-air rows against the station, retry pending withdrawals, and
   * forget old ended rows. Never re-sends anything. */
  reconcile(): Promise<void> {
    return this.exclusive(async () => {
      const now = this.clock();
      let changed = false;
      for (const r of this.rowsById.values()) {
        if (r.state === "on_air" && r.receipt !== null && r.receipt.expires_at <= now) {
          this.end(r, "expired", "expired", now);
          changed = true;
        } else if (r.state === "unknown" && r.ended === null && r.latest_expiry !== null && r.latest_expiry <= now) {
          this.end(r, "unknown", "lapsed_unconfirmed", now);
          changed = true;
        }
      }
      const live = this.rows().filter((r) => r.state === "on_air" && r.ended === null);
      if (live.length > 0) {
        const v = this.verifyStation(await this.station({ op: "status" }), null, this.clock());
        const at = this.clock();
        if (typeof v !== "string") {
          for (const r of live) {
            const rc = r.receipt as Receipt;
            if (rc.epoch !== v.epoch) {
              this.end(r, "stopped", "station_restarted", at); // the station's ring is not persisted
            } else if (!(v.onAir.get(r.stream)?.has(rc.seq) ?? false)) {
              this.end(r, r.withdraw !== null ? "withdrawn" : "stopped", r.withdraw !== null ? "gone_after_pluck" : "evicted", at);
            } else if (r.withdraw !== null) {
              await this.pluck(r, at);
            }
          }
        }
        changed = true;
      }
      const ended = this.rows()
        .filter((r) => r.ended !== null)
        .sort((a, b) => (a.ended?.at ?? 0) - (b.ended?.at ?? 0));
      let excess = this.rowsById.size - this.cfg.maxRows;
      for (const r of ended) {
        if (excess > 0 || (r.ended?.at ?? now) <= now - this.cfg.keepMs) {
          this.rowsById.delete(r.id);
          excess -= 1;
          changed = true;
        }
      }
      if (changed) {
        this.save();
      }
    });
  }

  /** This binding's daemon heard a frame of its own station: confirm an on-air row, or settle an unknown one.
   * Returns true when a row with a pending withdrawal just turned out to be on air (reconcile it now). */
  heard(f: HeardFrame, now: number): boolean {
    if (f.key_id !== this.cfg.keyId) {
      return false;
    }
    const rows = this.rows();
    let row = rows.find(
      (r) => r.receipt !== null && r.receipt.epoch === f.epoch && String(r.receipt.seq) === String(f.seq) && r.stream_id === f.stream_id,
    );
    if (row === undefined) {
      row = rows.find(
        (r) =>
          r.state === "unknown" &&
          r.ended === null &&
          r.stream_id === f.stream_id &&
          r.body.sha256 === f.body?.sha256 &&
          r.attempted_at !== null &&
          f.times.issued_at >= r.attempted_at - EVIDENCE_SLACK_MS &&
          f.times.issued_at <= r.attempted_at + SEND_TIMEOUT_MS + EVIDENCE_SLACK_MS &&
          !rows.some((o) => o.idem === f.idem),
      );
      if (row === undefined) {
        return false;
      }
      this.counts.evidence += 1;
      const ttl = f.times.expires_at - f.times.issued_at;
      this.onAir(row, { epoch: f.epoch, seq: Number(f.seq), issued_at: f.times.issued_at, expires_at: f.times.expires_at, ttl_s: ttl / 1000, loop_ms: null, clamp: null, size: f.bytes }, "confirmed_by_hearing", now);
    }
    if (row.heard_at === null) {
      row.heard_at = now;
      this.touch(row, "heard", now);
      this.save();
    }
    return row.state === "on_air" && row.withdraw !== null && row.ended === null;
  }

  /** A `retract` for one of this station's items. */
  retracted(r: Retract, now: number): void {
    const row = this.rows().find((x) => x.idem === r.idem && x.ended === null);
    if (row === undefined) {
      return;
    }
    this.counts.retracts += 1;
    const to: RowState =
      r.reason === "plucked" ? "withdrawn" : r.reason === "superseded" ? "superseded" : r.reason === "expired" ? "expired" : "stopped";
    this.end(row, to, `retract:${r.reason}`, now);
    this.save();
  }

  private onAir(row: Row, receipt: Receipt, event: string, now: number): void {
    row.state = "on_air";
    row.receipt = receipt;
    row.idem = idemOf(row.key_id, receipt.epoch, row.stream_id, receipt.seq);
    this.touch(row, event, now);
  }

  private end(row: Row, state: RowState, reason: string, now: number): void {
    row.state = state;
    row.ended = { at: now, reason };
    this.touch(row, reason, now);
  }

  private touch(row: Row, event: string, now: number): void {
    row.last = { at: now, event };
  }

  /** Counts by shown state; `expiring` is an on-air row in its last 20% of life (at least its last 10 s). */
  summary(now: number): Record<string, number> {
    const out: Record<string, number> = {};
    for (const r of this.rowsById.values()) {
      const s = shownState(r, now);
      out[s] = (out[s] ?? 0) + 1;
    }
    return out;
  }
}

/** pending, on_air, expiring, unknown, withdrawn, expired, superseded, stopped or failed. */
export function shownState(r: Row, now: number): string {
  if (r.state === "on_air" && r.receipt !== null) {
    const ttlMs = r.receipt.expires_at - r.receipt.issued_at;
    return r.receipt.expires_at - now <= Math.max(10_000, 0.2 * ttlMs) ? "expiring" : "on_air";
  }
  return r.state;
}

export function isTerminal(r: Row): boolean {
  return r.ended !== null && (TERMINAL.has(r.state) || r.state === "unknown");
}

/** A sing call's status for its row. `ended` only answers a repeated call whose row was on air and has ended. */
function outcomeOf(row: Row): "on-air" | "unknown" | "failed" | "ended" {
  switch (row.state) {
    case "on_air":
      return "on-air";
    case "unknown":
    case "pending":
      return "unknown";
    case "failed":
      return "failed";
    default:
      return "ended";
  }
}

function hushStatusOf(row: Row): HushOutcome["status"] {
  switch (row.state) {
    case "withdrawn":
      return "plucked";
    case "expired":
      return "expired";
    case "on_air":
      return "pending";
    case "unknown":
      return "unknown";
    default:
      return "not_found";
  }
}

function receiptOf(r: Obj): Receipt | null {
  const n = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
  if (!n(r.epoch) || !n(r.seq) || !n(r.issued_at) || !n(r.expires_at) || !n(r.ttl_s)) {
    return null;
  }
  return {
    epoch: r.epoch,
    seq: r.seq,
    issued_at: r.issued_at,
    expires_at: r.expires_at,
    ttl_s: r.ttl_s,
    loop_ms: n(r.loop_ms) ? r.loop_ms : null,
    clamp: typeof r.clamp === "string" ? r.clamp : null,
    size: n(r.size) ? r.size : null,
  };
}

function clip(v: unknown): string {
  const s = typeof v === "string" ? v : "no reason given";
  // eslint-disable-next-line no-control-regex
  const flat = s.replace(/[\u0000-\u001f\u007f]/g, " ");
  return flat.length > 160 ? `${flat.slice(0, 160)}…` : flat;
}
