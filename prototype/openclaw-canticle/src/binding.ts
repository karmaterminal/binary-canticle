// One binding: a prince's reading of the host daemon, its heard journal, its mutes and its outbox, under one state
// root that no other binding shares. Every id it issues (journal cursors, mute ids, outbox rows) names the binding,
// and it refuses ids that name another one, changing nothing.
//
// Heard content is data (RFC-0001 I-6, §14.12). Nothing here reads a payload for meaning: no heard text can mute,
// tune, configure, sing or advance anything. A session that reads heard text is marked tainted, and a tainted
// session cannot sing (stricter than §15.4 item 4; see the README).

import { randomBytes } from "node:crypto";
import { join } from "node:path";
import { type BindingConfig, sessionMatches, tuned } from "./config.ts";
import { DaemonLink } from "./daemon.ts";
import { type Entry, Journal } from "./journal.ts";
import { Outbox, type Row, isTerminal, shownState } from "./outbox.ts";
import { Receiver, type ViewItem } from "./receive.ts";
import { type HeardFrame, type Obj, STATION_NAME, STREAM_NAME, isObj } from "./records.ts";
import { heardMarks, iso, presenceText, renderEntry, renderViewItem } from "./render.ts";
import { type StationClient, stationClient } from "./station.ts";
import { Lease, LeaseHeld, ensureDir, readJson, writeJsonAtomic } from "./store.ts";

export type Caller = { sessionKey: string; sessionId: string | null; subagent: boolean };
export type Result = { text: string; details: Obj };

export type Mute = {
  id: string;
  station: string | null;
  stream: string | null;
  until: number | null;
  set_at: number;
  by: string;
};

type StateFile = {
  v: typeof STATE_V;
  binding: string;
  journal_id: string;
  created_at: number;
  last_run: string | null;
  mute_seq: number;
  mutes: Mute[];
  checkpoints: Record<string, { seq: number; at: number }>;
  taint: Record<string, { at: number }>;
  carried_keys: Record<string, number>;
  /** The journal's durable head when this file was saved. A journal found shorter lost entries a cursor may name. */
  journal_head: number;
};

export type BindingOptions = {
  config: BindingConfig;
  root: string;
  clock?: () => number;
  log?: (msg: string) => void;
  station?: StationClient;
  link?: { silenceMs?: number; snapshotMs?: number; backoff?: { firstMs: number; maxMs: number; jitter: number } };
  tickMs?: number;
};

const STATE_V = "openclaw-canticle-state/1";
const READ_LIMIT_MAX = 20;
const READ_BYTES_MAX = 12 * 1024;
const NEW_WINDOW_MS = 3_600_000; // a session's first `new` read starts an hour back
const CHECKPOINTS_MAX = 256;
const TAINT_MAX = 4_096;
const MUTES_MAX = 64;
const CURSOR = /^j:([a-z][a-z0-9-]{0,30}):([0-9a-f]{16}):(\d{1,15})$/;
const MUTE_ID = /^mute:([a-z][a-z0-9-]{0,30}):(\d{1,9})$/;

export class BindingStartError extends Error {
  readonly reason: string;

  constructor(reason: string, detail: string) {
    super(`${reason}: ${detail}`);
    this.reason = reason;
  }
}

export class Binding {
  readonly cfg: BindingConfig;
  readonly root: string;
  private readonly clock: () => number;
  private readonly log: (msg: string) => void;
  private readonly lease: Lease;
  private readonly journal: Journal;
  readonly receiver: Receiver;
  private readonly link: DaemonLink;
  readonly outbox: Outbox | null;
  private state: StateFile | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly tickMs: number;
  private running = false;
  readonly counts = { repeats: 0, withdrawn_unheard: 0, refused: 0, append_errors: 0 };

  constructor(o: BindingOptions) {
    this.cfg = o.config;
    this.root = o.root;
    this.clock = o.clock ?? Date.now;
    this.log = o.log ?? (() => undefined);
    this.tickMs = o.tickMs ?? 5_000;
    this.lease = new Lease(o.root);
    this.lease.onError = (e) => this.log(`canticle: state lease error: ${e.message}`);
    this.journal = new Journal(join(o.root, "journal"), o.config.journal);
    const self = o.config.station?.keyId ?? null;
    this.receiver = new Receiver(
      {
        heard: (f, ctx) => this.onHeard(f, ctx.run, ctx.rec_seq, ctx.source),
        withdrawn: (r, ctx, held) => {
          if (self !== null && r.target.key_id === self) {
            this.outbox?.retracted(r, this.clock());
          }
          const known = this.journal.heard(r.idem, this.clock()) || held !== null;
          const mine = self !== null && r.target.key_id === self;
          if (!known && !mine) {
            this.counts.withdrawn_unheard += 1;
            return;
          }
          this.append({
            kind: "withdrawn",
            run: ctx.run,
            rec_seq: ctx.rec_seq,
            idem: r.idem,
            reason: r.reason,
            by: r.by,
            station: held?.station ?? null,
            stream: held?.stream ?? null,
            self: mine,
          });
        },
        presence: (p, ctx) =>
          this.append({
            kind: "presence",
            run: ctx.run,
            rec_seq: ctx.rec_seq,
            source: ctx.source,
            key_id: p.key_id,
            station: p.station,
            principal: p.principal,
            state: p.state,
            last_beacon_at: p.last_beacon_at,
          }),
        note: (n) => {
          this.append({ kind: "note", note: n });
          if (n.kind === "joined" && this.state !== null && this.state.last_run !== n.run) {
            this.state.last_run = n.run;
            this.saveState();
          }
        },
      },
      {
        clock: this.clock,
        accepts: (f) => (self !== null && f.key_id === self) || tuned(o.config.listen.tune, f.station, f.stream),
        lastRun: null,
      },
    );
    this.link = new DaemonLink({
      socketPath: o.config.daemon.socket,
      receiver: this.receiver,
      uid: o.config.daemon.uid ?? undefined,
      log: this.log,
      ...(o.link?.silenceMs !== undefined ? { silenceMs: o.link.silenceMs } : {}),
      ...(o.link?.snapshotMs !== undefined ? { snapshotMs: o.link.snapshotMs } : {}),
      ...(o.link?.backoff !== undefined ? { backoff: o.link.backoff } : {}),
    });
    const p = o.config.publish;
    const st = o.config.station;
    this.outbox =
      p.enabled && st !== null && p.socket !== null
        ? new Outbox(
            join(o.root, "outbox.json"),
            {
              binding: o.config.binding,
              station: st.name,
              keyId: st.keyId,
              classes: p.classes,
              perMinute: p.perMinute,
              perHour: p.perHour,
              maxLive: p.maxLive,
              maxRows: 512,
              keepMs: 24 * 3_600_000,
              maxTextBytes: 800,
            },
            o.station ?? stationClient(p.socket, { uid: p.uid ?? undefined }),
            this.clock,
          )
        : null;
  }

  get name(): string {
    return this.cfg.binding;
  }

  /** Take the lease, load what is on disk, connect. A failure leaves nothing running and nothing changed. */
  async start(): Promise<void> {
    if (this.running) {
      return;
    }
    try {
      ensureDir(this.root);
      await this.lease.acquire();
    } catch (e) {
      throw new BindingStartError(e instanceof LeaseHeld ? "state_locked" : "state_unusable", (e as Error).message);
    }
    try {
      const now = this.clock();
      this.state = this.loadState(now);
      this.journal.load(this.state.carried_keys, now);
      if (this.journal.head < this.state.journal_head) {
        // Journal files are gone that held seqs a reader may have a cursor for. Rather than hand those seqs out
        // again, every earlier cursor and checkpoint becomes stale: a read with one is refused, never misread.
        this.log(`canticle: the journal ends at ${this.journal.head} but was at ${this.state.journal_head}; earlier cursors are now stale`);
        this.state.journal_id = randomBytes(8).toString("hex");
        this.state.checkpoints = {};
        this.state.journal_head = this.journal.head;
      }
      // A binding that restarts into the run it last held is rejoining it (§14.18.3).
      this.receiver.restoreRun(this.state.last_run);
      this.outbox?.load();
      this.saveState();
    } catch (e) {
      await this.lease.release();
      if (e instanceof BindingStartError) {
        throw e;
      }
      throw new BindingStartError("state_unreadable", (e as Error).message);
    }
    this.running = true;
    this.link.start();
    this.timer = setInterval(() => {
      this.tick().catch((e: unknown) => this.log(`canticle: tick failed: ${(e as Error).message}`));
    }, this.tickMs);
    this.timer.unref();
  }

  async stop(): Promise<void> {
    if (!this.running) {
      return;
    }
    this.running = false;
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.link.stop();
    this.journal.close();
    this.saveState();
    await this.lease.release();
  }

  /** Expire the view, apply journal retention, lapse mutes, reconcile the outbox. Exposed for tests. */
  async tick(): Promise<void> {
    if (!this.running) {
      return;
    }
    const now = this.clock();
    this.receiver.tick(now);
    const st = this.state as StateFile;
    let dirty = false;
    if (this.journal.prune(now)) {
      st.carried_keys = this.journal.carried(now);
      dirty = true;
    }
    const live = st.mutes.filter((m) => m.until === null || m.until > now);
    if (live.length !== st.mutes.length) {
      st.mutes = live;
      dirty = true;
    }
    if (dirty) {
      this.saveState();
    }
    try {
      await this.outbox?.reconcile();
    } catch (e) {
      this.log(`canticle: outbox reconcile failed: ${(e as Error).message}`);
    }
  }

  // ------------------------------------------------------------------ state

  private loadState(now: number): StateFile {
    const raw = readJson(join(this.root, "state.json"));
    if (raw === null) {
      return {
        v: STATE_V,
        binding: this.cfg.binding,
        journal_id: randomBytes(8).toString("hex"),
        created_at: now,
        last_run: null,
        mute_seq: 0,
        mutes: [],
        checkpoints: {},
        taint: {},
        carried_keys: {},
        journal_head: 0,
      };
    }
    if (!isObj(raw) || raw.v !== STATE_V) {
      throw new BindingStartError("state_unreadable", "state.json is not this plugin's state");
    }
    if (raw.binding !== this.cfg.binding) {
      throw new BindingStartError(
        "foreign_state",
        `${this.root} belongs to binding ${JSON.stringify(raw.binding)}, not ${JSON.stringify(this.cfg.binding)}`,
      );
    }
    const st = raw as unknown as StateFile;
    st.journal_head = typeof st.journal_head === "number" ? st.journal_head : 0;
    return st;
  }

  private saveState(): void {
    if (this.state !== null) {
      this.state.journal_head = Math.max(this.state.journal_head, this.journal.durable);
      writeJsonAtomic(join(this.root, "state.json"), this.state);
    }
  }

  private append(d: Parameters<Journal["append"]>[0]): Entry | null {
    try {
      return this.journal.append(d, this.clock());
    } catch (e) {
      this.counts.append_errors += 1;
      this.log(`canticle: journal append failed: ${(e as Error).message}`);
      return null;
    }
  }

  private onHeard(f: HeardFrame, run: string, recSeq: number, source: "live" | "snapshot"): void {
    const now = this.clock();
    const self = this.cfg.station !== null && f.key_id === this.cfg.station.keyId;
    if (self && this.outbox?.heard(f, now) === true) {
      this.outbox.reconcile().catch((e: unknown) => this.log(`canticle: outbox reconcile failed: ${(e as Error).message}`));
    }
    if (this.journal.heard(f.idem, now)) {
      this.counts.repeats += 1; // a resurfaced, snapshot or re-sent copy of an item already journaled
      return;
    }
    const mute = self ? null : this.muteFor(f.station, f.stream, now);
    this.append({
      kind: "heard",
      run,
      rec_seq: recSeq,
      source,
      disposition: self ? "self" : mute !== null ? "muted" : "held",
      mute,
      frame: f,
    });
  }

  /** The mute that covers a station:stream now: the daemon's MUTE first, then this binding's most specific. */
  private muteFor(station: string, stream: string, now: number): string | null {
    const landing = this.receiver.status().landing;
    if (landing !== null && isObj(landing.mute)) {
      const until = landing.mute.until;
      if (typeof until !== "number" || until > now) {
        return "daemon";
      }
    }
    const st = this.state;
    if (st === null) {
      return null;
    }
    const live = st.mutes.filter(
      (m) =>
        (m.until === null || m.until > now) && (m.station === null || m.station === station) && (m.stream === null || m.stream === stream),
    );
    live.sort((a, b) => Number(b.station !== null) + Number(b.stream !== null) - Number(a.station !== null) - Number(a.stream !== null));
    return live[0]?.id ?? null;
  }

  // ------------------------------------------------------------------ ids

  private cursor(seq: number): string {
    return `j:${this.cfg.binding}:${(this.state as StateFile).journal_id}:${seq}`;
  }

  /** A cursor's seq, or a refusal that names why it is not this binding's. */
  private parseCursor(text: string): number | { refused: string; detail: string } {
    const m = CURSOR.exec(text);
    if (m === null) {
      return { refused: "bad_cursor", detail: "not a cursor this plugin issues (j:BINDING:JOURNAL:SEQ)" };
    }
    if (m[1] !== this.cfg.binding) {
      return { refused: "not_this_binding", detail: `the cursor belongs to binding ${m[1]}; each binding reads only its own journal` };
    }
    if (m[2] !== (this.state as StateFile).journal_id) {
      return { refused: "stale_cursor", detail: "the cursor is from an earlier journal of this binding" };
    }
    const seq = Number(m[3]);
    if (seq > this.journal.head) {
      return { refused: "cursor_ahead", detail: `the journal's head is ${this.journal.head}` };
    }
    return seq;
  }

  private refuse(tool: string, reason: string, detail: string): Result {
    this.counts.refused += 1;
    return { text: `[canticle:refused] ${tool}: ${reason}: ${detail}. Nothing changed.`, details: { ok: false, refused: reason, detail } };
  }

  private sessionKeyOf(c: Caller): string {
    return c.sessionKey;
  }

  private taintKeyOf(c: Caller): string {
    return c.sessionId ?? `key:${c.sessionKey}`;
  }

  /** Whether this session may read heard text: the binding's configuration lists such sessions in listen.payloadSessions. */
  mayReadText(c: Caller): boolean {
    return sessionMatches(this.cfg.listen.payloadSessions, c.sessionKey);
  }

  isTainted(c: Caller): boolean {
    return this.state !== null && this.taintKeyOf(c) in this.state.taint;
  }

  // ------------------------------------------------------------------ tools

  listen(c: Caller, p: Obj): Result {
    const st = this.state;
    if (st === null) {
      return this.refuse("canticle_listen", "not_running", "the canticle service is not running");
    }
    const now = this.clock();
    const what = p.what ?? "new";
    const view = p.view ?? "digest";
    if (what !== "new" && what !== "journal" && what !== "on_air") {
      return this.refuse("canticle_listen", "bad_param", "what is new, journal or on_air");
    }
    if (view !== "items" && view !== "digest") {
      return this.refuse("canticle_listen", "bad_param", "view is items or digest");
    }
    if (view === "items" && !this.mayReadText(c)) {
      return this.refuse(
        "canticle_listen",
        "payload_not_allowed",
        "heard text taints a session (§14.12), so it is shown only to sessions listed in listen.payloadSessions; view digest needs no listing",
      );
    }
    const station = p.station ?? null;
    const stream = p.stream ?? null;
    if ((station !== null && (typeof station !== "string" || !STATION_NAME.test(station))) || (stream !== null && (typeof stream !== "string" || !STREAM_NAME.test(stream)))) {
      return this.refuse("canticle_listen", "bad_param", "station and stream are exact names");
    }
    const limitRaw = p.limit ?? 10;
    if (typeof limitRaw !== "number" || !Number.isInteger(limitRaw) || limitRaw < 1 || limitRaw > READ_LIMIT_MAX) {
      return this.refuse("canticle_listen", "bad_param", `limit is 1 to ${READ_LIMIT_MAX}`);
    }
    const includeSelf = p.includeSelf === true || this.cfg.listen.includeSelf;
    const rx = this.receiver.status();
    if (what === "on_air") {
      if (p.since !== undefined) {
        return this.refuse("canticle_listen", "bad_param", "since applies to new and journal");
      }
      return this.onAirResult(c, now, view, station, stream, limitRaw, includeSelf);
    }
    let after: number;
    if (p.since !== undefined) {
      if (typeof p.since !== "string") {
        return this.refuse("canticle_listen", "bad_cursor", "since is a cursor from an earlier result");
      }
      const parsed = this.parseCursor(p.since);
      if (typeof parsed !== "number") {
        return this.refuse("canticle_listen", parsed.refused, parsed.detail);
      }
      after = parsed;
    } else if (what === "new") {
      after = st.checkpoints[this.sessionKeyOf(c)]?.seq ?? this.firstNewAfter(now);
    } else {
      after = this.journal.oldest - 1;
    }
    const prunedBefore = Math.max(0, this.journal.oldest - 1 - after);
    const out: string[] = [];
    const ids: Obj[] = [];
    let last = after;
    let bytes = 0;
    let more = false;
    let filtered = 0;
    let heardShown = 0;
    let payloadShown = 0;
    for (const e of this.journal.scan(after)) {
      if (!this.matches(e, station, stream, includeSelf)) {
        filtered += 1;
        last = e.seq;
        continue;
      }
      if (ids.length >= limitRaw) {
        more = true;
        break;
      }
      const text = renderEntry(e, now, view);
      const size = Buffer.byteLength(text);
      if (ids.length > 0 && bytes + size > READ_BYTES_MAX) {
        more = true;
        break;
      }
      out.push(text);
      ids.push(entrySummary(e));
      bytes += size;
      last = e.seq;
      if (e.kind === "heard") {
        heardShown += 1;
        if (view === "items") {
          payloadShown += 1;
        }
      }
    }
    if (what === "new") {
      st.checkpoints[this.sessionKeyOf(c)] = { seq: last, at: now };
      trimOldest(st.checkpoints, CHECKPOINTS_MAX);
    }
    if (payloadShown > 0) {
      this.markTainted(c, now);
    }
    if (what === "new" || payloadShown > 0 || this.journal.durable > st.journal_head) {
      this.saveState();
    }
    const head = [
      `[canticle:listen] ${what === "new" ? "new for this session" : "journal"} after ${this.cursor(after)}: ${ids.length} entr${ids.length === 1 ? "y" : "ies"}${more ? ", more after these" : ""}; next=${this.cursor(last)}`,
      `receive: ${rx.health}${rx.reasons.length > 0 ? ` (${rx.reasons.join(", ")})` : ""}; delivery: explicit read only`,
    ];
    if (prunedBefore > 0) {
      head.push(`[canticle:gap] ${prunedBefore} older entr${prunedBefore === 1 ? "y was" : "ies were"} pruned before this point (journal retention)`);
    }
    if (filtered > 0) {
      head.push(`${filtered} entr${filtered === 1 ? "y" : "ies"} outside the filters ${what === "new" ? "passed over" : "skipped"}`);
    }
    if (view === "digest" && heardShown > 0) {
      head.push(
        this.mayReadText(c)
          ? `to read these items' text: canticle_listen {"what":"journal","since":"${this.cursor(after)}","view":"items"} (reading heard text taints this session)`
          : "heard text is not shown to this session (it is not listed in listen.payloadSessions)",
      );
    }
    return {
      text: [...head, "", ...out].join("\n\n").replace(/\n{3,}/g, "\n\n"),
      details: {
        ok: true,
        what,
        view,
        untrusted: payloadShown > 0,
        from: this.cursor(after),
        next: this.cursor(last),
        truncated: more,
        pruned_before: prunedBefore,
        filtered,
        entries: ids,
        receive: { health: rx.health, reasons: rx.reasons },
      },
    };
  }

  private firstNewAfter(now: number): number {
    for (const e of this.journal.scan(this.journal.oldest - 1)) {
      if (e.at >= now - NEW_WINDOW_MS) {
        return e.seq - 1;
      }
    }
    return this.journal.head;
  }

  private matches(e: Entry, station: string | null, stream: string | null, includeSelf: boolean): boolean {
    switch (e.kind) {
      case "heard":
        return (includeSelf || e.disposition !== "self") && (station === null || e.frame.station === station) && (stream === null || e.frame.stream === stream);
      case "withdrawn":
        return (includeSelf || !e.self) && (station === null || e.station === station) && (stream === null || e.stream === stream);
      case "presence":
        return stream === null && (station === null || e.station === station);
      case "note":
        return true;
    }
  }

  private onAirResult(c: Caller, now: number, view: "items" | "digest", station: string | null, stream: string | null, limit: number, includeSelf: boolean): Result {
    const rx = this.receiver.status();
    const keep = (i: ViewItem): boolean =>
      (includeSelf || this.cfg.station === null || i.frame.key_id !== this.cfg.station.keyId) &&
      (station === null || i.frame.station === station) &&
      (stream === null || i.frame.stream === stream);
    const current = this.receiver.onAir(now).filter(keep);
    const carried = this.receiver.carried(now).filter(keep);
    const out: string[] = [];
    const ids: Obj[] = [];
    let bytes = 0;
    let payloadShown = 0;
    let more = false;
    for (const [i, isCurrent] of [...current.map((x) => [x, true] as const), ...carried.map((x) => [x, false] as const)]) {
      if (ids.length >= limit) {
        more = true;
        break;
      }
      const marks: string[] = [];
      if (!isCurrent) {
        marks.push("carried: heard before a gap, not known to be on air now");
      }
      const m = this.cfg.station !== null && i.frame.key_id === this.cfg.station.keyId ? null : this.muteFor(i.frame.station, i.frame.stream, now);
      if (m !== null) {
        marks.push(`muted (${m}): readable here, never pushed`);
      }
      if (i.source === "snapshot") {
        marks.push("from a join snapshot");
      }
      const text = renderViewItem(i, now, view, marks);
      const size = Buffer.byteLength(text);
      if (ids.length > 0 && bytes + size > READ_BYTES_MAX) {
        more = true;
        break;
      }
      out.push(text);
      bytes += size;
      ids.push({ idem: i.frame.idem, station: i.frame.station, stream: i.frame.stream, current: isCurrent, expires_at: i.frame.times.local_expiry_at });
      if (view === "items") {
        payloadShown += 1;
      }
    }
    if (payloadShown > 0) {
      this.markTainted(c, now);
      this.saveState();
    }
    const known = this.receiver.current();
    const head = known
      ? `[canticle:on-air] ${current.length} item(s) on air now (receive ${rx.health}${rx.reasons.length > 0 ? `: ${rx.reasons.join(", ")}` : ""})`
      : `[canticle:on-air] unknown: no current view (${rx.reasons.join(", ") || "not connected"}); nothing below is known to be on air`;
    const lines = [head];
    if (carried.length > 0) {
      lines.push(`${carried.length} carried item(s): heard before a gap, shown as carried until a complete join snapshot or a live record confirms them`);
    }
    if (view === "digest" && ids.length > 0) {
      lines.push(
        this.mayReadText(c)
          ? 'to read their text: canticle_listen {"what":"on_air","view":"items"} (reading heard text taints this session)'
          : "heard text is not shown to this session (it is not listed in listen.payloadSessions)",
      );
    }
    return {
      text: [...lines, ...out].join("\n\n"),
      details: {
        ok: true,
        what: "on_air",
        view,
        known,
        untrusted: payloadShown > 0,
        current: current.length,
        carried: carried.length,
        truncated: more,
        entries: ids,
        receive: { health: rx.health, reasons: rx.reasons },
      },
    };
  }

  private markTainted(c: Caller, now: number): void {
    const st = this.state as StateFile;
    st.taint[this.taintKeyOf(c)] = { at: now };
    trimOldest(st.taint, TAINT_MAX);
  }

  status(c: Caller): Result {
    const st = this.state;
    if (st === null) {
      return this.refuse("canticle_status", "not_running", "the canticle service is not running");
    }
    const now = this.clock();
    const rx = this.receiver.status();
    const current = this.receiver.onAir(now).length;
    const carried = this.receiver.carried(now).length;
    const presence = this.receiver
      .presence()
      .map(({ p, state, current: cur }) => ({ station: p.station, key_id: p.key_id, state, last_beacon_at: p.last_beacon_at, current: cur }));
    const checkpoint = st.checkpoints[this.sessionKeyOf(c)]?.seq ?? null;
    let waiting = 0;
    for (const e of this.journal.scan(checkpoint ?? this.firstNewAfter(now))) {
      if (e.kind === "heard" && e.disposition !== "self") {
        waiting += 1;
      }
    }
    const mutes = st.mutes.filter((m) => m.until === null || m.until > now);
    const landing = rx.landing;
    const daemonMute = landing !== null && isObj(landing.mute);
    const out = this.outbox;
    const details: Obj = {
      ok: true,
      binding: this.cfg.binding,
      delivery: { mode: "explicit", pushes: 0 },
      receive: {
        connection: rx.connection,
        since: rx.since,
        health: rx.health,
        reasons: rx.reasons,
        run: rx.run,
        snapshot: rx.snapshot,
        omitted: rx.omitted,
        records_lost: rx.records_lost,
        last_record_at: rx.last_record_at,
        last_failure: rx.last_failure,
        daemon: rx.daemon === null ? null : { state: rx.daemon.state, reasons: rx.daemon.reasons },
        landing: landing === null ? null : { muted: daemonMute, breaker: landing.breaker },
        counts: { ...this.receiver.counts, ...this.link.framing, ...this.counts },
      },
      on_air: { known: this.receiver.current(), current, carried },
      presence,
      journal: {
        head: this.journal.head,
        oldest: this.journal.oldest,
        ...this.journal.size,
        retention: this.cfg.journal,
        new_for_this_session: waiting,
        checkpoint: checkpoint === null ? null : this.cursor(checkpoint),
        counts: this.journal.counts,
      },
      mutes,
      session: { tainted: this.isTainted(c), may_read_text: this.mayReadText(c) },
      publish:
        out === null
          ? { enabled: false }
          : {
              enabled: !c.subagent,
              station: this.cfg.station?.name,
              key_id: this.cfg.station?.keyId,
              rows: out.summary(now),
              last_station_check: out.lastStation,
              counts: out.counts,
            },
    };
    const lines = [
      `[canticle:status] binding ${this.cfg.binding}; delivery: explicit read only (nothing is pushed to sessions)`,
      `receive: ${rx.health}${rx.reasons.length > 0 ? ` (${rx.reasons.join(", ")})` : ""}; connection ${rx.connection}${rx.since !== null ? ` since ${iso(rx.since)}` : ""}; run ${rx.run ?? "none"}; join snapshot ${rx.snapshot}`,
      this.receiver.current()
        ? `on air: ${current} item(s)${carried > 0 ? `, ${carried} carried from before a gap` : ""}`
        : `on air: unknown (no current view)${carried > 0 ? `; ${carried} carried item(s) from before the gap` : ""}`,
      `presence: ${presence.length === 0 ? "none known" : presence.map((x) => `${x.station ?? x.key_id}: ${presenceText(x.state, x.last_beacon_at)}`).join("; ")}`,
      `journal: ${this.journal.size.entries} entries (seq ${this.journal.oldest}..${this.journal.head}); ${waiting} heard entr${waiting === 1 ? "y" : "ies"} new for this session`,
      `mutes: ${daemonMute ? "daemon MUTE active; " : ""}${mutes.length === 0 ? "none" : mutes.map((m) => `${m.id} ${m.station ?? "*"}:${m.stream ?? "*"}${m.until !== null ? ` until ${iso(m.until)}` : ""}`).join(", ")}`,
      `this session: ${this.isTainted(c) ? "tainted (has read heard text; cannot sing until reset)" : "not tainted"}; ${this.mayReadText(c) ? "may read heard text (view items)" : "reads digests only (not in listen.payloadSessions)"}`,
      out === null
        ? "publish: disabled"
        : `publish: ${Object.entries(out.summary(now)).map(([k, v]) => `${k}=${v}`).join(", ") || "no rows"}`,
    ];
    return { text: lines.join("\n"), details };
  }

  mute(c: Caller, p: Obj): Result {
    const st = this.state;
    if (st === null) {
      return this.refuse("canticle_mute", "not_running", "the canticle service is not running");
    }
    const now = this.clock();
    if (p.clear !== undefined) {
      if (p.clear === "all") {
        const n = st.mutes.length;
        st.mutes = [];
        this.saveState();
        return { text: `[canticle:mute] cleared ${n} mute(s)`, details: { ok: true, cleared: n, mutes: [] } };
      }
      const m = typeof p.clear === "string" ? MUTE_ID.exec(p.clear) : null;
      if (m === null) {
        return this.refuse("canticle_mute", "bad_param", "clear is a mute id or \"all\"");
      }
      if (m[1] !== this.cfg.binding) {
        return this.refuse("canticle_mute", "not_this_binding", `the mute belongs to binding ${m[1]}`);
      }
      const before = st.mutes.length;
      st.mutes = st.mutes.filter((x) => x.id !== p.clear);
      if (st.mutes.length === before) {
        return this.refuse("canticle_mute", "not_found", `no active mute ${p.clear}`);
      }
      this.saveState();
      return { text: `[canticle:mute] cleared ${p.clear}`, details: { ok: true, cleared: 1, mutes: st.mutes } };
    }
    const station = p.station ?? null;
    const stream = p.stream ?? null;
    if ((station !== null && (typeof station !== "string" || !STATION_NAME.test(station))) || (stream !== null && (typeof stream !== "string" || !STREAM_NAME.test(stream)))) {
      return this.refuse("canticle_mute", "bad_param", "station and stream are exact names");
    }
    const ttl = p.ttlSeconds;
    if (ttl !== undefined && (typeof ttl !== "number" || !Number.isInteger(ttl) || ttl < 1 || ttl > 86_400)) {
      return this.refuse("canticle_mute", "bad_param", "ttlSeconds is 1 to 86400");
    }
    // One choice per scope: a new mute for the same station and stream replaces the old one.
    const kept = st.mutes.filter((x) => !(x.station === station && x.stream === stream) && (x.until === null || x.until > now));
    if (kept.length >= MUTES_MAX) {
      return this.refuse("canticle_mute", "quota", `${MUTES_MAX} mutes are active`);
    }
    st.mute_seq += 1;
    const mute: Mute = {
      id: `mute:${this.cfg.binding}:${st.mute_seq}`,
      station: station as string | null,
      stream: stream as string | null,
      until: typeof ttl === "number" ? now + ttl * 1000 : null,
      set_at: now,
      by: c.sessionKey,
    };
    st.mutes = [...kept, mute];
    this.saveState();
    return {
      text: `[canticle:mute] ${mute.id} mutes ${mute.station ?? "*"}:${mute.stream ?? "*"}${mute.until !== null ? ` until ${iso(mute.until)}` : " until cleared"}. Items heard under it are journaled as muted: canticle_listen still reads them, and no later push will carry them.`,
      details: { ok: true, mute, mutes: st.mutes },
    };
  }

  async sing(c: Caller, p: Obj): Promise<Result> {
    const out = this.outbox;
    if (out === null || this.state === null) {
      return this.refuse("canticle_sing", "disabled", "publishing is not enabled for this binding");
    }
    if (c.subagent) {
      return this.refuse("canticle_sing", "subagent", "sub-agents may not publish (§15.5)");
    }
    if (this.isTainted(c)) {
      return this.refuse(
        "canticle_sing",
        "tainted",
        "this session has read heard text; a session that heard canticle content cannot sing until it is reset",
      );
    }
    for (const k of ["stream", "payload"] as const) {
      if (typeof p[k] !== "string") {
        return this.refuse(
          "canticle_sing",
          "bad_param",
          k === "payload" && isObj(p[k]) ? "payload is text; a body by reference is not supported here" : `${k} is required text`,
        );
      }
    }
    for (const k of ["class", "stateKey", "purpose", "idempotencyKey"] as const) {
      if (p[k] !== undefined && typeof p[k] !== "string") {
        return this.refuse("canticle_sing", "bad_param", `${k} is a string`);
      }
    }
    if (p.ttlSeconds !== undefined && typeof p.ttlSeconds !== "number") {
      return this.refuse("canticle_sing", "bad_param", "ttlSeconds is a number");
    }
    const o = await out.sing({
      session: c.sessionKey,
      stream: p.stream as string,
      text: p.payload as string,
      class: (p.class as string | undefined) ?? null,
      state_key: (p.stateKey as string | undefined) ?? null,
      purpose: (p.purpose as string | undefined) ?? null,
      ttl_s: (p.ttlSeconds as number | undefined) ?? null,
      key: (p.idempotencyKey as string | undefined) ?? null,
    });
    const now = this.clock();
    // The daemon can hear the item before the station's reply arrives (or when the reply is lost): offer what the
    // view already holds from this station, so the row is confirmed or settled by that evidence.
    const self = this.cfg.station?.keyId;
    for (const item of this.receiver.items.values()) {
      if (item.frame.key_id === self) {
        out.heard(item.frame, now);
      }
    }
    if (o.status === "rejected" || o.status === "budget_exhausted") {
      const retry = o.status === "budget_exhausted" ? `; retry after ${Math.ceil(o.retryAfterMs / 1000)} s` : "";
      return {
        text: `[canticle:sing] ${o.status}: ${o.reason}${o.status === "rejected" ? ` (${o.detail})` : ""}${retry}. Nothing was sent.`,
        details: {
          ok: true,
          result: {
            status: o.status,
            reason: o.reason,
            ...(o.status === "budget_exhausted" ? { retryAfterMs: o.retryAfterMs } : {}),
            ...(o.row !== null ? { item: o.row.id } : {}),
          },
        },
      };
    }
    const row = o.row;
    const rc = row.receipt;
    const status = row.state === "on_air" ? "on-air" : o.status;
    const result: Obj = {
      status,
      item: row.id,
      duplicate: o.duplicate,
      state: shownState(row, now),
    };
    if (rc !== null) {
      result.expiresAt = iso(rc.expires_at);
      result.effective = {
        ttlMs: Math.round(rc.ttl_s * 1000),
        loopMs: rc.loop_ms,
        clampReason: row.ttl_s !== null && row.ttl_s > rc.ttl_s ? "stream_max" : (rc.clamp ?? "none"),
        scope: "lan",
        class: row.class ?? "stream default",
        hop: 0,
      };
      result.onAir = { epoch: rc.epoch, seq: rc.seq };
    }
    if (row.ended !== null) {
      result.reason = row.ended.reason;
    }
    const said =
      status === "on-air"
        ? `on air as ${row.id} (epoch ${rc?.epoch}, seq ${rc?.seq}) until ${iso(rc?.expires_at)}`
        : status === "unknown"
          ? `${row.id} was sent but the station's reply was lost: it is never re-sent, and shows as on air only if this binding hears it`
          : status === "ended"
            ? `${row.id} was on air and has ended (${row.ended?.reason ?? row.state}); nothing was sung again`
            : `${row.id} did not go on air (${row.ended?.reason ?? "failed"})`;
    return { text: `[canticle:sing] ${o.duplicate ? "duplicate of an earlier call: " : ""}${said}`, details: { ok: true, result } };
  }

  async hush(c: Caller, p: Obj): Promise<Result> {
    const out = this.outbox;
    if (out === null || this.state === null) {
      return this.refuse("canticle_hush", "disabled", "publishing is not enabled for this binding");
    }
    if (c.subagent) {
      return this.refuse("canticle_hush", "subagent", "sub-agents may not publish (§15.5)");
    }
    if (typeof p.item !== "string") {
      return this.refuse("canticle_hush", "bad_param", "item is an outbox row id (out:BINDING:N)");
    }
    const o = await out.hush(p.item, c.sessionKey);
    if (o.status === "refused") {
      return this.refuse("canticle_hush", o.reason ?? "refused", o.reason === "not_this_binding" ? "the row belongs to another binding" : "not an outbox row id");
    }
    const row = o.row;
    return {
      text: `[canticle:hush] ${p.item}: ${o.status}${o.reason !== undefined ? ` (${o.reason})` : ""}${row !== null ? `; row is ${shownState(row, this.clock())}` : ""}`,
      details: { ok: true, result: { status: o.status, ...(o.reason !== undefined ? { reason: o.reason } : {}), ...(row !== null ? { row: rowView(row, this.clock()) } : {}) } },
    };
  }

  outboxView(_c: Caller, p: Obj): Result {
    const out = this.outbox;
    if (out === null) {
      return this.refuse("canticle_outbox", "disabled", "publishing is not enabled for this binding");
    }
    const which = p.rows ?? "live";
    if (which !== "live" && which !== "all") {
      return this.refuse("canticle_outbox", "bad_param", "rows is live or all");
    }
    const now = this.clock();
    const rows = out
      .rows()
      .filter((r) => which === "all" || !isTerminal(r))
      .sort((a, b) => b.created_at - a.created_at)
      .slice(0, 50);
    const lines = rows.map((r) => {
      const v = rowView(r, now);
      return `${r.id} ${v.state} ${r.stream}${r.class !== null ? ` class=${r.class}` : ""}${r.state_key !== null ? ` key=${r.state_key}` : ""} body=${r.body.size}B sha256=${r.body.sha256.slice(0, 12)}…${v.on_air !== null ? ` epoch ${v.on_air.epoch} seq ${v.on_air.seq} left ${v.on_air.remaining_s}s` : ""}${r.heard_at !== null ? " heard" : ""}${r.withdraw !== null ? ` withdraw=${r.withdraw.outcome ?? "requested"}` : ""}${r.ended !== null ? ` (${r.ended.reason})` : ""}`;
    });
    return {
      text: [`[canticle:outbox] ${rows.length} ${which} row(s); ${Object.entries(out.summary(now)).map(([k, v]) => `${k}=${v}`).join(", ") || "empty"}`, ...lines].join("\n"),
      details: { ok: true, rows: rows.map((r) => rowView(r, now)), summary: out.summary(now) },
    };
  }
}

/** A row as tools show it: never the text (RFC-0001 §15.1), only its hash and size. */
export function rowView(r: Row, now: number) {
  return {
    id: r.id,
    state: shownState(r, now),
    station: r.station,
    stream: r.stream,
    class: r.class,
    state_key: r.state_key,
    purpose: r.purpose,
    body: r.body,
    key_source: r.key_source,
    session: r.session,
    created_at: iso(r.created_at),
    on_air:
      r.receipt === null
        ? null
        : {
            epoch: r.receipt.epoch,
            seq: r.receipt.seq,
            issued_at: iso(r.receipt.issued_at),
            expires_at: iso(r.receipt.expires_at),
            remaining_s: Math.max(0, Math.round((r.receipt.expires_at - now) / 1000)),
          },
    heard_at: r.heard_at === null ? null : iso(r.heard_at),
    withdraw: r.withdraw,
    ended: r.ended === null ? null : { at: iso(r.ended.at), reason: r.ended.reason },
    last: { at: iso(r.last.at), event: r.last.event },
  };
}

function entrySummary(e: Entry): Obj {
  switch (e.kind) {
    case "heard":
      return {
        seq: e.seq,
        kind: e.kind,
        idem: e.frame.idem,
        station: e.frame.station,
        stream: e.frame.stream,
        class: e.frame.class,
        disposition: e.disposition,
        source: e.source,
        heard_at: e.frame.times.heard_at,
        expires_at: e.frame.times.local_expiry_at,
        marks: heardMarks(e),
      };
    case "withdrawn":
      return { seq: e.seq, kind: e.kind, idem: e.idem, reason: e.reason, station: e.station, stream: e.stream };
    case "presence":
      return { seq: e.seq, kind: e.kind, station: e.station, key_id: e.key_id, state: e.state };
    case "note":
      return { seq: e.seq, kind: e.kind, note: e.note.kind };
  }
}

function trimOldest(m: Record<string, { at: number }>, max: number): void {
  const keys = Object.keys(m);
  if (keys.length <= max) {
    return;
  }
  keys.sort((a, b) => (m[a]?.at ?? 0) - (m[b]?.at ?? 0));
  for (const k of keys.slice(0, keys.length - max)) {
    delete m[k];
  }
}
