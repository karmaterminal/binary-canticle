// The binding's reading of one host daemon (RFC-0001 §14.18.3): bootstrap validation, the join step, the join
// snapshot, live records, gaps and run boundaries, and the current view built from them. One Receiver lives as
// long as the binding; each daemon connection is a sequence of connected() ... lost() calls on it.
//
// The current view answers "what is on air now?". It is not the journal: after a connection loss every item in
// it is *carried* (heard before the gap, not known to be current) until a complete join snapshot or a live record
// confirms it, and with no connection there is no current answer at all, only "unknown" (never "offline").

import {
  type DaemonHealth,
  type HeardFrame,
  type Landing,
  type Obj,
  type Presence,
  type Retract,
  RECORD_V,
  healthOf,
  heardFrameOf,
  isDeliverable,
  isObj,
  landingOf,
  presenceOf,
  reasonCode,
  retractOf,
  versionOf,
} from "./records.ts";

/** A problem that ends the connection (§14.18.3: the binding treats the connection as lost). */
export class ProtocolError extends Error {
  readonly reason: "malformed_record" | "record_version";

  constructor(reason: "malformed_record" | "record_version", detail: string) {
    super(`${reason}: ${detail}`);
    this.reason = reason;
  }
}

export type RecordContext = { run: string; rec_seq: number; at: number };
export type HeardContext = RecordContext & { source: "live" | "snapshot" };

export type Note =
  | { kind: "joined"; join: "first" | "rejoin" | "new_run"; run: string; baseline: number }
  | { kind: "records_lost"; missing: number | null; total: number; why: "gap" | "rejoin" }
  | { kind: "snapshot"; result: "complete" | "truncated" | "unsupported"; entries: number; omitted: number; watermark: number | null }
  | { kind: "disconnected"; why: string }
  | { kind: "ended"; how: "bye" | "fatal"; reason: string | null }
  | { kind: "daemon_health"; state: string; reasons: string[] };

export type ReceiveEvents = {
  /** A deliverable frame entered the view: a live record, or an entry of a completed snapshot. */
  heard(frame: HeardFrame, ctx: HeardContext): void;
  /** A `retract` for an item. */
  withdrawn(r: Retract, ctx: RecordContext, held: HeardFrame | null): void;
  /** A station's presence changed (a live record, or an entry of a completed snapshot). */
  presence(p: Presence, ctx: HeardContext): void;
  /** Connection, gap, snapshot and run notes (journaled as `gap` entries). */
  note(n: Note): void;
};

export type ViewItem = { frame: HeardFrame; run: string; confirmed: boolean; source: "live" | "snapshot"; at: number };
type PresenceRow = { p: Presence; run: string; confirmed: boolean; at: number };

export type Connection = "connecting" | "connected" | "disconnected";

export type ReceiveStatus = {
  connection: Connection;
  since: number | null;
  /** ok | degraded | failed | unknown. `unknown` whenever this binding has no live, bootstrapped connection. */
  health: "ok" | "degraded" | "failed" | "unknown";
  reasons: string[];
  run: string | null;
  snapshot: "pending" | "complete" | "truncated" | "unsupported" | "none";
  omitted: number;
  records_lost: number;
  last_rec_seq: number | null;
  last_record_at: number | null;
  daemon: DaemonHealth | null;
  landing: Landing | null;
  last_failure: string | null;
};

export type ReceiveCounts = Record<
  | "records"
  | "frames_deliverable"
  | "frames_other"
  | "malformed_record"
  | "unknown_type"
  | "untuned"
  | "expired_on_arrival"
  | "after_retract"
  | "view_overflow"
  | "connections"
  | "protocol_errors",
  number
>;

type Conn = {
  phase: "hello" | "landing" | "live";
  requested: boolean;
  hello: Obj | null;
  run: string | null;
  baseline: number;
  last: number;
  continuous: boolean;
  snapshot: "pending" | "complete" | "truncated" | "unsupported";
  omitted: number;
  snaps: Obj[];
  inSnapshot: boolean;
  recordsLost: number;
  ended: string | null;
};

const RETRACTED_MAX = 4096;
const SKEW_MS = 5_000; // §14.18.5 [PROPOSED DEFAULT]: tombstones outlive local expiry by 5 s
const RETRACTED_DEFAULT_MS = 3_600_000; // when the item's local expiry is unknown: the largest class max TTL

export class Receiver {
  private readonly events: ReceiveEvents;
  private readonly clock: () => number;
  private readonly maxView: number;
  private readonly accepts: (f: HeardFrame) => boolean;
  private conn: Conn | null = null;
  private connection: Connection = "disconnected";
  private since: number | null = null;
  /** Why the last connection ended or the last attempt failed; null until one has. */
  private lastFailure: string | null = null;
  private lastRecordAt: number | null = null;
  private daemon: DaemonHealth | null = null;
  private landing: Landing | null = null;
  private versionFailed = false;
  /** Runs this binding has held records from (the newest last), to tell a rejoin from a new run. */
  private runs: string[] = [];
  readonly items = new Map<string, ViewItem>();
  private readonly presenceRows = new Map<string, PresenceRow>();
  private readonly retracted = new Map<string, number>();
  readonly counts: ReceiveCounts = {
    records: 0,
    frames_deliverable: 0,
    frames_other: 0,
    malformed_record: 0,
    unknown_type: 0,
    untuned: 0,
    expired_on_arrival: 0,
    after_retract: 0,
    view_overflow: 0,
    connections: 0,
    protocol_errors: 0,
  };

  constructor(
    events: ReceiveEvents,
    opts: { clock: () => number; maxView?: number; accepts?: (f: HeardFrame) => boolean; lastRun?: string | null },
  ) {
    this.events = events;
    this.clock = opts.clock;
    this.maxView = opts.maxView ?? 1024;
    this.accepts = opts.accepts ?? (() => true);
    if (opts.lastRun) {
      this.runs.push(opts.lastRun);
    }
  }

  /** The run this binding last held records from (persisted, so a restart into the same run is a rejoin). */
  get lastRun(): string | null {
    return this.runs.at(-1) ?? null;
  }

  /** Restore the run this binding held before a restart, before its first connection. */
  restoreRun(run: string | null): void {
    this.runs = run === null ? [] : [run];
  }

  connecting(): void {
    this.connection = "connecting";
  }

  /** A new connection is open; ``requested`` says whether its first line asked for a join snapshot. */
  connected(requested: boolean): void {
    this.counts.connections += 1;
    this.connection = "connected";
    this.since = this.clock();
    this.conn = {
      phase: "hello",
      requested,
      hello: null,
      run: null,
      baseline: 0,
      last: 0,
      continuous: false,
      snapshot: "pending",
      omitted: 0,
      snaps: [],
      inSnapshot: false,
      recordsLost: 0,
      ended: null,
    };
  }

  /** The connection ended, or an attempt failed (end of stream, socket error, protocol error, a snapshot that did
   * not come, or the silence backstop). Whatever the view held is now carried: heard before the gap, not current.
   * A partial snapshot is discarded. Only the end of an open connection is a note; failed attempts are not. */
  lost(why: string): void {
    const c = this.conn;
    const how = c?.ended ?? why;
    const was = this.connection;
    this.conn = null;
    this.lastFailure = how;
    this.connection = "disconnected";
    if (was !== "connected") {
      return;
    }
    this.since = this.clock();
    for (const item of this.items.values()) {
      item.confirmed = false;
    }
    for (const row of this.presenceRows.values()) {
      row.confirmed = false;
    }
    this.events.note({ kind: "disconnected", why: how });
  }

  /** Where the open connection is: waiting for `hello`, for the bootstrap `landing_state`, or live. */
  phase(): "hello" | "landing" | "live" | null {
    return this.conn?.phase ?? null;
  }

  /** Whether the open connection asked for a join snapshot that has not completed yet. */
  snapshotPending(): boolean {
    return this.conn !== null && this.conn.snapshot === "pending";
  }

  /** Apply one parsed line. Throws ProtocolError when the connection must be treated as lost. */
  apply(raw: unknown): void {
    const c = this.conn;
    if (c === null) {
      throw new ProtocolError("malformed_record", "a record with no connection open");
    }
    this.counts.records += 1;
    this.lastRecordAt = this.clock();
    if (!isObj(raw)) {
      throw this.fail("malformed_record", "a line that is not a JSON object");
    }
    const version = versionOf(raw);
    if (version === "other_major") {
      this.versionFailed = true;
      throw this.fail("record_version", `unsupported record version ${brief(raw.v)}`);
    }
    const type = raw.type;
    const seq = raw.rec_seq;
    if (version !== "v1" || typeof type !== "string" || typeof seq !== "number" || !Number.isSafeInteger(seq)) {
      throw this.fail("malformed_record", "not a record v1 object with a type and an integer rec_seq");
    }
    if (c.phase === "hello") {
      if (type !== "hello" || typeof raw.run !== "string") {
        throw this.fail("malformed_record", `first record is ${brief(type)}, not hello`);
      }
      c.hello = raw;
      c.run = raw.run;
      c.last = seq;
      c.phase = "landing";
      if (!(c.requested && raw.join_snapshot === true)) {
        c.snapshot = "unsupported";
      }
      return;
    }
    if (raw.run !== c.run) {
      throw this.fail("malformed_record", `${brief(type)} from run ${brief(raw.run)}, not ${brief(c.run)}`);
    }
    if (c.phase === "landing") {
      if (type !== "landing_state" || seq <= c.last) {
        throw this.fail("malformed_record", "second record is not a later landing_state");
      }
      this.join(c, raw, seq);
      return;
    }
    if (type === "snapshot" || type === "snapshot_end") {
      this.snapshotRecord(c, raw, type, seq);
      return;
    }
    if (c.inSnapshot) {
      throw this.fail("malformed_record", `${brief(type)} inside a join snapshot`);
    }
    if (seq <= c.last) {
      throw this.fail("malformed_record", `rec_seq ${seq} after ${c.last}`);
    }
    const missing = c.continuous ? seq - c.last - 1 : 0;
    c.last = seq;
    if (c.snapshot === "unsupported") {
      c.continuous = true; // without a snapshot, continuity starts at the first live record
    }
    if (missing > 0) {
      c.recordsLost += missing;
      this.events.note({ kind: "records_lost", missing, total: c.recordsLost, why: "gap" });
    }
    this.live(c, raw, type, seq);
  }

  private fail(reason: "malformed_record" | "record_version", detail: string): ProtocolError {
    this.counts.protocol_errors += 1;
    return new ProtocolError(reason, detail);
  }

  /** Bootstrap step 2 and the join step (§14.18.3, *Joining a run*). */
  private join(c: Conn, landing: Obj, seq: number): void {
    const run = c.run as string;
    c.baseline = seq;
    c.last = seq;
    c.phase = "live";
    this.landing = landingOf(landing);
    this.versionFailed = false;
    let join: "first" | "rejoin" | "new_run";
    if (this.runs.includes(run)) {
      join = "rejoin";
    } else {
      // A new run is a daemon restart. What the old run surfaced stays carried (it was cleared from "current" at
      // the loss); a complete snapshot of the new run replaces it, and a resurfaced live record confirms it.
      join = this.runs.length > 0 ? "new_run" : "first";
      this.runs.push(run);
      if (this.runs.length > 8) {
        this.runs.shift();
      }
    }
    this.events.note({ kind: "joined", join, run, baseline: seq });
    if (join === "rejoin") {
      // Whatever the run emitted while this binding was away was not replayed: one loss, whatever rec_seq shows.
      c.recordsLost += 1;
      this.events.note({ kind: "records_lost", missing: null, total: c.recordsLost, why: "rejoin" });
    }
    if (c.snapshot === "unsupported") {
      this.events.note({ kind: "snapshot", result: "unsupported", entries: 0, omitted: 0, watermark: null });
    }
  }

  private snapshotRecord(c: Conn, rec: Obj, type: string, seq: number): void {
    if (c.snapshot !== "pending") {
      throw this.fail("malformed_record", `${type} on a connection whose snapshot is ${c.snapshot}`);
    }
    if (seq < c.last) {
      throw this.fail("malformed_record", `snapshot rec_seq ${seq} below ${c.last}`);
    }
    if (type === "snapshot") {
      if (rec.snap_seq !== c.snaps.length + 1 || !isObj(rec.entry)) {
        throw this.fail("malformed_record", "snapshot out of order or without an entry");
      }
      const first = c.snaps[0];
      if (first !== undefined && first.rec_seq !== seq) {
        throw this.fail("malformed_record", "snapshot records with different watermarks");
      }
      if (c.snaps.length >= 1024) {
        throw this.fail("malformed_record", "more snapshot entries than a connection's queue holds");
      }
      c.inSnapshot = true;
      c.snaps.push(rec);
      return;
    }
    const w = rec.watermark;
    if (seq !== w || rec.count !== c.snaps.length || c.snaps.some((s) => s.rec_seq !== w)) {
      throw this.fail("malformed_record", "snapshot_end does not match its snapshot records");
    }
    const truncated = rec.truncated === true;
    const at = this.clock();
    const run = c.run as string;
    const frames: HeardFrame[] = [];
    const presence: Presence[] = [];
    for (const s of c.snaps) {
      const entry = s.entry as Obj;
      if (isObj(entry.frame)) {
        const f = isDeliverable(entry.frame) ? heardFrameOf(entry.frame) : null;
        if (f === null) {
          this.counts.malformed_record += 1;
        } else {
          frames.push(f);
        }
      } else if (isObj(entry.presence)) {
        const p = presenceOf(entry.presence);
        if (p === null) {
          this.counts.malformed_record += 1;
        } else {
          presence.push(p);
        }
      } else {
        this.counts.unknown_type += 1;
      }
    }
    if (!truncated) {
      // Complete: the run's presence table and surfaced set become the snapshot's. An item absent from it was
      // not live at the watermark and leaves the view (that is all absence does; it is not a retract).
      this.items.clear();
      this.presenceRows.clear();
    }
    const ctx: HeardContext = { run, rec_seq: w as number, at, source: "snapshot" };
    for (const p of presence) {
      this.presenceRows.set(p.key_id, { p, run, confirmed: true, at });
      this.events.presence(p, ctx);
    }
    for (const f of frames) {
      this.admit(f, ctx);
    }
    c.snapshot = truncated ? "truncated" : "complete";
    c.omitted = truncated && typeof rec.omitted === "number" ? rec.omitted : 0;
    c.last = w as number;
    c.snaps = [];
    c.inSnapshot = false;
    c.continuous = true;
    this.events.note({
      kind: "snapshot",
      result: c.snapshot,
      entries: frames.length + presence.length,
      omitted: c.omitted,
      watermark: w as number,
    });
  }

  private live(c: Conn, rec: Obj, type: string, seq: number): void {
    const ctx: HeardContext = { run: c.run as string, rec_seq: seq, at: this.clock(), source: "live" };
    switch (type) {
      case "frame": {
        if (!isDeliverable(rec)) {
          this.counts.frames_other += 1; // reaches no view: §14.18.4, only verified + surface is deliverable
          return;
        }
        const f = heardFrameOf(rec);
        if (f === null) {
          this.counts.malformed_record += 1;
          return;
        }
        this.admit(f, ctx);
        return;
      }
      case "retract": {
        const r = retractOf(rec);
        if (r === null) {
          this.counts.malformed_record += 1;
          return;
        }
        const held = this.items.get(r.idem);
        this.items.delete(r.idem);
        const until = (held?.frame.times.local_expiry_at ?? ctx.at + RETRACTED_DEFAULT_MS) + SKEW_MS;
        this.retracted.set(r.idem, until);
        if (this.retracted.size > RETRACTED_MAX) {
          const oldest = this.retracted.keys().next().value;
          if (oldest !== undefined) {
            this.retracted.delete(oldest);
          }
        }
        this.events.withdrawn(r, ctx, held?.frame ?? null);
        return;
      }
      case "presence": {
        const p = presenceOf(rec);
        if (p === null) {
          this.counts.malformed_record += 1;
          return;
        }
        const prev = this.presenceRows.get(p.key_id);
        this.presenceRows.set(p.key_id, { p, run: ctx.run, confirmed: true, at: ctx.at });
        if (prev?.p.state !== p.state) {
          this.events.presence(p, ctx);
        }
        return;
      }
      case "health": {
        const h = healthOf(rec);
        if (h === null) {
          this.counts.malformed_record += 1;
          return;
        }
        const prev = this.daemon;
        this.daemon = h;
        if (prev === null || prev.state !== h.state || prev.reasons.join() !== h.reasons.join()) {
          this.events.note({ kind: "daemon_health", state: h.state, reasons: h.reasons });
        }
        return;
      }
      case "landing_state":
        this.landing = landingOf(rec);
        return;
      case "bye":
        c.ended = "bye";
        this.events.note({ kind: "ended", how: "bye", reason: null });
        return;
      case "fatal": {
        const reason = rec.reason === undefined || rec.reason === null ? null : reasonCode(rec.reason);
        c.ended = `fatal:${reason ?? "unknown"}`;
        this.events.note({ kind: "ended", how: "fatal", reason });
        return;
      }
      case "hello":
        throw this.fail("malformed_record", "a second hello on one connection");
      default:
        this.counts.unknown_type += 1; // an unknown type within v1: counted and ignored
    }
  }

  private admit(f: HeardFrame, ctx: HeardContext): void {
    this.counts.frames_deliverable += 1;
    if (f.times.local_expiry_at <= ctx.at) {
      this.counts.expired_on_arrival += 1; // never delivered past local expiry (§14.18.3)
      return;
    }
    const until = this.retracted.get(f.idem);
    if (until !== undefined && until > ctx.at) {
      this.counts.after_retract += 1; // a retract is final for its tuple; a later copy does not bring it back
      return;
    }
    if (!this.accepts(f)) {
      this.counts.untuned += 1;
      return;
    }
    if (!this.items.has(f.idem) && this.items.size >= this.maxView) {
      this.counts.view_overflow += 1;
      return;
    }
    this.items.set(f.idem, { frame: f, run: ctx.run, confirmed: true, source: ctx.source, at: ctx.at });
    this.events.heard(f, ctx);
  }

  /** Drop what has passed its local expiry from the view, and lapsed retract tombstones. */
  tick(now: number): void {
    for (const [idem, item] of this.items) {
      if (item.frame.times.local_expiry_at <= now) {
        this.items.delete(idem);
      }
    }
    for (const [idem, until] of this.retracted) {
      if (until <= now) {
        this.retracted.delete(idem);
      }
    }
  }

  /** What is on air now: confirmed, unexpired items, newest heard first. Empty unless the view is current. */
  onAir(now: number): ViewItem[] {
    if (!this.current()) {
      return [];
    }
    return sortItems([...this.items.values()].filter((i) => i.confirmed && i.frame.times.local_expiry_at > now));
  }

  /** Items heard before a gap and not confirmed since: shown as carried, never as current. */
  carried(now: number): ViewItem[] {
    return sortItems(
      [...this.items.values()].filter((i) => (!i.confirmed || !this.current()) && i.frame.times.local_expiry_at > now),
    );
  }

  /** Whether the view describes the air now: connected, bootstrapped, past any requested join snapshot, and on a
   * record version this binding reads. */
  current(): boolean {
    const c = this.conn;
    return this.connection === "connected" && c !== null && c.phase === "live" && c.snapshot !== "pending" && !this.versionFailed;
  }

  presence(): { p: Presence; state: string; current: boolean }[] {
    const blind = !this.current() || (this.daemon?.reasons.includes("no_datagrams") ?? false);
    return [...this.presenceRows.values()]
      .sort((a, b) => (a.p.station ?? a.p.key_id).localeCompare(b.p.station ?? b.p.key_id))
      .map((row) => {
        const current = !blind && row.confirmed;
        return { p: row.p, state: current ? row.p.state : "unknown", current };
      });
  }

  status(): ReceiveStatus {
    const c = this.conn;
    const reasons: string[] = [];
    let health: ReceiveStatus["health"];
    if (this.connection !== "connected" || c === null || c.phase !== "live" || c.snapshot === "pending") {
      health = "unknown";
      reasons.push(this.connection === "connected" ? "joining" : this.connection);
      if (this.lastFailure !== null && this.connection !== "connected") {
        reasons.push(this.lastFailure);
      }
    } else if (this.versionFailed) {
      health = "failed";
      reasons.push("record_version");
    } else {
      if (c.recordsLost > 0) {
        reasons.push("records_lost");
      }
      if (c.snapshot !== "complete") {
        reasons.push("joined_late");
      }
      health = reasons.length > 0 ? "degraded" : "ok";
    }
    return {
      connection: this.connection,
      since: this.since,
      health,
      reasons,
      run: c?.run ?? this.lastRun,
      snapshot: c === null ? "none" : c.snapshot,
      omitted: c?.omitted ?? 0,
      records_lost: c?.recordsLost ?? 0,
      last_rec_seq: c?.last ?? null,
      last_record_at: this.lastRecordAt,
      daemon: this.daemon,
      landing: this.landing,
      last_failure: this.lastFailure,
    };
  }
}

/** A daemon-supplied value as a short, printable token for a failure reason (status surfaces show it). */
function brief(v: unknown): string {
  const text = typeof v === "string" ? v : JSON.stringify(v) ?? String(v);
  return JSON.stringify(text.length > 40 ? `${text.slice(0, 40)}…` : text);
}

function sortItems(items: ViewItem[]): ViewItem[] {
  return items.sort(
    (a, b) =>
      b.frame.times.heard_at - a.frame.times.heard_at ||
      b.frame.epoch - a.frame.epoch ||
      Number(BigInt(b.frame.seq) - BigInt(a.frame.seq)) ||
      a.frame.idem.localeCompare(b.frame.idem),
  );
}

export { RECORD_V };
