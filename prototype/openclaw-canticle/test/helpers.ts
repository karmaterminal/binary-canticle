// Test fakes: a host daemon that speaks record v1 over a real unix socket (bootstrap, join snapshot, live records,
// gaps, run restarts), a station control socket, and helpers. Nothing here touches the network or real keys.

import { createHash } from "node:crypto";
import { chmodSync, mkdtempSync, rmSync } from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Binding, type BindingOptions, type Caller } from "../src/binding.ts";
import { type BindingConfig, parseConfig } from "../src/config.ts";
import { type Obj, RECORD_V, idemOf, streamIdOf } from "../src/records.ts";

export const KEY_RUNE = "1111111111111111";
export const KEY_SCRIBE = "2222222222222222";
export const KEY_CAEL = "3333333333333333";

export function tempDir(): string {
  const d = mkdtempSync(join(tmpdir(), "occ-"));
  chmodSync(d, 0o700);
  return d;
}

export function removeDir(d: string): void {
  rmSync(d, { recursive: true, force: true });
}

export async function waitFor(cond: () => boolean, what = "condition", ms = 4_000): Promise<void> {
  const end = Date.now() + ms;
  while (!cond()) {
    if (Date.now() > end) {
      throw new Error(`timed out waiting for ${what}`);
    }
    await new Promise((r) => setTimeout(r, 5));
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** A mutable clock the tests move by hand. */
export class Clock {
  t: number;

  constructor(t = 1_790_000_000_000) {
    this.t = t;
  }

  now = (): number => this.t;

  advance(ms: number): void {
    this.t += ms;
  }
}

export type FrameSpec = {
  station: string;
  key_id: string;
  stream: string;
  seq: number;
  issued_at: number;
  epoch?: number;
  text?: string;
  ttl_ms?: number;
  class?: string;
  purpose?: string | null;
  dedup?: "first" | "resurfaced";
  admission?: string;
  disposition?: string;
  state_key?: string | null;
};

/** The fields of a record v1 `frame` (records.py `_frame`), without v, type, rec_seq and run. */
export function frameFields(s: FrameSpec): Obj {
  const epoch = s.epoch ?? 1;
  const sid = streamIdOf(s.stream);
  const text = s.text ?? `item ${s.seq}`;
  const ttl = s.ttl_ms ?? 60_000;
  const body = Buffer.from(text, "utf8");
  return {
    frame: { key_id: s.key_id, epoch, stream_id: sid, seq: s.seq, kind: "item", sha256: "00".repeat(32), bytes: 200 },
    idem: idemOf(s.key_id, epoch, sid, s.seq),
    station: { name: s.station, principal: null },
    stream: s.stream,
    class: s.class ?? "chatter",
    scope: "lan",
    hop: 0,
    state_key: s.state_key ?? null,
    purpose: s.purpose ?? null,
    intensity: null,
    lens: null,
    flags: { refresh: false, wake_derived: false, exercise: false },
    lineage: { derived_from: null, root: null },
    times: {
      issued_at: s.issued_at,
      expires_at: s.issued_at + ttl,
      received_at: s.issued_at + 1,
      heard_at: s.issued_at + 1,
      offset_ms: 0,
      local_expiry_at: s.issued_at + ttl,
      age_ms: 1,
    },
    gap: null,
    admission: s.admission ?? "verified",
    dedup: s.dedup ?? "first",
    disposition: s.disposition ?? "surface",
    reasons: [],
    versions: { frame: 2 },
    body: { ctype: "text/plain; charset=utf-8", size: body.length, sha256: createHash("sha256").update(body).digest("hex"), text },
    body_ref: null,
  };
}

type Conn = { sock: net.Socket; first: string | null; buf: string; got: string[] };

/** A host daemon speaking record v1 on a unix socket. */
export class FakeDaemon {
  readonly path: string;
  run = "run-1";
  recSeq = 0;
  private server: net.Server | null = null;
  private hello: Obj | null = null;
  private landing: Obj | null = null;
  readonly conns = new Set<Conn>();
  /** What is live at the receptor now: the join snapshot's entries. */
  readonly live = new Map<string, Obj>();
  readonly presenceTable = new Map<string, Obj>();
  joinSnapshot = true;
  holdSnapshot = false;
  truncateTo: number | null = null;
  /** Abort each connection before hello, as the daemon does for a uid it does not allow, or when full or not ready. */
  refuse = false;
  refused = 0;
  accepted = 0;
  readonly firstLines: string[] = [];

  constructor(dir: string) {
    this.path = join(dir, "daemon.sock");
  }

  async start(): Promise<void> {
    this.bootstrap();
    this.server = net.createServer((sock) => this.accept(sock));
    await new Promise<void>((resolve) => this.server?.listen(this.path, () => resolve()));
  }

  private bootstrap(): void {
    this.recSeq = 0;
    this.hello = this.record("hello", { daemon: "fake", join_snapshot: this.joinSnapshot, manifest_sha256: "00".repeat(32) });
    this.recSeq += 3; // the jump from hello to landing_state is not a gap
    this.landing = this.record("landing_state", { mute: null, breaker: "closed", until: null, modulation: [] });
  }

  private record(type: string, fields: Obj): Obj {
    this.recSeq += 1;
    return { v: RECORD_V, type, rec_seq: this.recSeq, run: this.run, ...fields };
  }

  private accept(sock: net.Socket): void {
    if (this.refuse) {
      this.refused += 1;
      sock.on("error", () => undefined);
      sock.destroy();
      return;
    }
    this.accepted += 1;
    const c: Conn = { sock, first: null, buf: "", got: [] };
    this.conns.add(c);
    sock.on("error", () => undefined);
    sock.on("close", () => this.conns.delete(c));
    this.write(c, this.hello as Obj);
    this.write(c, this.landing as Obj);
    sock.on("data", (d: Buffer) => {
      c.buf += d.toString("utf8");
      const nl = c.buf.indexOf("\n");
      if (c.first === null && nl !== -1) {
        c.first = c.buf.slice(0, nl);
        this.firstLines.push(c.first);
        if (!this.holdSnapshot) {
          this.serveSnapshot(c);
        }
      }
    });
  }

  private serveSnapshot(c: Conn): void {
    let req: Obj | null = null;
    try {
      req = JSON.parse(c.first ?? "") as Obj;
    } catch {
      return;
    }
    if (!this.joinSnapshot || req.op !== "join_snapshot") {
      return;
    }
    const w = this.recSeq;
    const entries = [...[...this.presenceTable.values()].map((p) => ({ presence: p })), ...[...this.live.values()].map((f) => ({ frame: f }))];
    const shown = this.truncateTo === null ? entries : entries.slice(0, this.truncateTo);
    shown.forEach((entry, i) => this.write(c, { v: RECORD_V, type: "snapshot", rec_seq: w, run: this.run, snap_seq: i + 1, entry }));
    this.write(c, {
      v: RECORD_V,
      type: "snapshot_end",
      rec_seq: w,
      run: this.run,
      watermark: w,
      count: shown.length,
      truncated: shown.length < entries.length,
      omitted: entries.length - shown.length,
    });
  }

  write(c: Conn, rec: Obj | string): void {
    const line = typeof rec === "string" ? rec : JSON.stringify(rec);
    c.got.push(line);
    c.sock.write(`${line}\n`);
  }

  /** Emit one live record to every connection (``skip``: connections that drop it, as a full queue would). */
  emit(type: string, fields: Obj, skip: Set<Conn> = new Set()): number {
    const rec = this.record(type, fields);
    for (const c of this.conns) {
      if (!skip.has(c)) {
        this.write(c, rec);
      }
    }
    return rec.rec_seq as number;
  }

  /** While set, surfaced frames wait (a datagram the daemon has not heard yet) until releaseFrames(). */
  holdFrames = false;
  private held: FrameSpec[] = [];

  releaseFrames(): void {
    this.holdFrames = false;
    for (const spec of this.held.splice(0)) {
      this.surface(spec);
    }
  }

  /** A surfaced frame: live, and in later join snapshots until it is retracted or forgotten. */
  surface(spec: FrameSpec): Obj {
    const f = frameFields(spec);
    if (this.holdFrames) {
      this.held.push(spec);
      return f;
    }
    this.emit("frame", f);
    if (f.disposition === "surface" && f.admission === "verified") {
      this.live.set(f.idem as string, { v: RECORD_V, type: "frame", rec_seq: this.recSeq, run: this.run, ...f });
    }
    return f;
  }

  retract(spec: { key_id: string; stream: string; seq: number; epoch?: number }, reason = "plucked"): void {
    const epoch = spec.epoch ?? 1;
    const sid = streamIdOf(spec.stream);
    const idem = idemOf(spec.key_id, epoch, sid, spec.seq);
    this.live.delete(idem);
    this.emit("retract", { idem, reason, target: { key_id: spec.key_id, epoch, stream_id: sid, seq: spec.seq }, by: null });
  }

  presence(name: string, keyId: string, state: string, lastBeaconAt: number | null = null): void {
    const p = { key_id: keyId, station: { name, principal: null }, state, last_beacon_at: lastBeaconAt };
    this.presenceTable.set(keyId, { v: RECORD_V, type: "presence", rec_seq: this.recSeq + 1, run: this.run, ...p });
    this.emit("presence", p);
  }

  health(state = "ok", reasons: string[] = []): void {
    this.emit("health", { state, reasons, beacon_age_ms: {}, counters: {} });
  }

  /** Records lost for every connection: their rec_seq values are used up and never sent. */
  lose(n: number): void {
    this.recSeq += n;
  }

  dropAll(): void {
    for (const c of this.conns) {
      c.sock.destroy();
    }
    this.conns.clear();
  }

  /** A daemon restart: a new run with an empty receptor view (the live set survives as the new run's). */
  restartRun(run: string): void {
    this.dropAll();
    this.run = run;
    for (const [k, f] of this.live) {
      this.live.set(k, { ...f, run });
    }
    this.bootstrap();
  }

  async stop(): Promise<void> {
    this.dropAll();
    const s = this.server;
    this.server = null;
    if (s !== null) {
      await new Promise<void>((r) => s.close(() => r()));
    }
  }
}

type RingItem = { seq: number; kind: "item" | "pluck"; expires_at: number; issued_at: number; state_key: string | null; text: string };
export type StationFault = "drop_after" | "drop_before" | "refuse";

/** A station's control socket: sing, hush and status, with faults to inject. */
export class FakeStation {
  readonly path: string;
  readonly keyId: string;
  readonly name: string;
  epoch = 1;
  private server: net.Server | null = null;
  readonly streams = new Map<string, { head: number; ring: Map<number, RingItem>; ttl_s: number }>();
  readonly requests: Obj[] = [];
  readonly faults: { op: string; fault: StationFault }[] = [];
  onSing: ((it: RingItem & { stream: string; epoch: number }) => void) | null = null;
  onHush: ((target: { stream: string; seq: number; epoch: number }) => void) | null = null;
  private readonly clock: () => number;

  constructor(dir: string, name: string, keyId: string, clock: () => number, streams: Record<string, number> = { chatter: 60 }) {
    this.path = join(dir, `${name}.ctl`);
    this.name = name;
    this.keyId = keyId;
    this.clock = clock;
    for (const [s, ttl] of Object.entries(streams)) {
      this.streams.set(s, { head: 0, ring: new Map(), ttl_s: ttl });
    }
  }

  async start(): Promise<void> {
    this.server = net.createServer((sock) => {
      let buf = "";
      sock.on("error", () => undefined);
      sock.on("data", (d: Buffer) => {
        buf += d.toString("utf8");
        const nl = buf.indexOf("\n");
        if (nl === -1) {
          return;
        }
        const req = JSON.parse(buf.slice(0, nl)) as Obj;
        this.requests.push(req);
        const i = this.faults.findIndex((f) => f.op === req.op);
        const fault = i === -1 ? null : (this.faults.splice(i, 1)[0]?.fault ?? null);
        if (fault === "drop_before") {
          sock.destroy();
          return;
        }
        if (fault === "refuse") {
          sock.end(`${JSON.stringify({ ok: false, error: "refused by test" })}\n`);
          return;
        }
        const reply = this.dispatch(req);
        if (fault === "drop_after") {
          sock.destroy();
          return;
        }
        sock.end(`${JSON.stringify(reply)}\n`);
      });
    });
    await new Promise<void>((resolve) => this.server?.listen(this.path, () => resolve()));
  }

  ops(op: string): Obj[] {
    return this.requests.filter((r) => r.op === op);
  }

  private dispatch(req: Obj): Obj {
    const now = this.clock();
    this.forget(now);
    if (req.op === "status") {
      const streams: Obj = {};
      for (const [name, s] of this.streams) {
        streams[name] = {
          stream_id: streamIdOf(name).toString(16).padStart(8, "0"),
          head_seq: s.head,
          trail_seq: s.ring.size > 0 ? Math.min(...s.ring.keys()) : s.head + 1,
          b_stream: 1000,
          default_ttl_s: s.ttl_s,
          max_ttl_s: s.ttl_s,
          on_air: [...s.ring.values()].map((it) => ({ seq: it.seq, kind: it.kind, state_key: it.state_key, remaining_s: (it.expires_at - now) / 1000, loop_ms: 10_000, clamp: "none", size: 200 })),
        };
      }
      return { ok: true, key_id: this.keyId, epoch: this.epoch, b_station: 4000, streams };
    }
    const s = this.streams.get(req.stream as string);
    if (s === undefined) {
      return { ok: false, error: `station has no stream ${JSON.stringify(req.stream)}` };
    }
    if (req.op === "sing") {
      const ttl = Math.min(typeof req.ttl === "number" ? req.ttl : s.ttl_s, s.ttl_s);
      s.head += 1;
      let superseded: number | null = null;
      const key = typeof req.state_key === "string" ? req.state_key : null;
      if (key !== null) {
        for (const [seq, it] of s.ring) {
          if (it.kind === "item" && it.state_key === key) {
            s.ring.delete(seq);
            superseded = seq;
          }
        }
      }
      const it: RingItem = { seq: s.head, kind: "item", issued_at: now, expires_at: now + ttl * 1000, state_key: key, text: req.text as string };
      s.ring.set(it.seq, it);
      this.onSing?.({ ...it, stream: req.stream as string, epoch: this.epoch });
      return {
        ok: true,
        stream: req.stream,
        seq: it.seq,
        epoch: this.epoch,
        issued_at: now,
        expires_at: it.expires_at,
        ttl_s: ttl,
        loop_ms: 10_000,
        clamp: "none",
        size: 200,
        kind: "item",
        ...(superseded !== null ? { superseded_seq: superseded } : {}),
      };
    }
    if (req.op === "hush") {
      const target = s.ring.get(req.seq as number);
      if (target === undefined || target.kind !== "item") {
        return { ok: false, error: `no live item ${String(req.stream)}#${String(req.seq)} to pluck` };
      }
      if (target.expires_at - now < 100) {
        return { ok: false, error: "target already expiring" };
      }
      s.ring.delete(target.seq);
      s.head += 1;
      s.ring.set(s.head, { seq: s.head, kind: "pluck", issued_at: now, expires_at: target.expires_at, state_key: null, text: "" });
      this.onHush?.({ stream: req.stream as string, seq: target.seq, epoch: this.epoch });
      return { ok: true, stream: req.stream, seq: s.head, epoch: this.epoch, issued_at: now, expires_at: target.expires_at, ttl_s: (target.expires_at - now) / 1000, loop_ms: 10_000, clamp: "none", size: 120, kind: "pluck" };
    }
    return { ok: false, error: `unknown op ${JSON.stringify(req.op)}` };
  }

  private forget(now: number): void {
    for (const s of this.streams.values()) {
      for (const [seq, it] of s.ring) {
        if (it.expires_at <= now) {
          s.ring.delete(seq);
        }
      }
    }
  }

  /** A station restart: a new epoch whose seqs start again at 1, and the ring is gone (it is not persisted). */
  restart(): void {
    this.epoch += 1;
    for (const s of this.streams.values()) {
      s.ring.clear();
      s.head = 0;
    }
  }

  async stop(): Promise<void> {
    const s = this.server;
    this.server = null;
    if (s !== null) {
      await new Promise<void>((r) => s.close(() => r()));
    }
  }
}

/** Feed a station's sings and plucks into a daemon, as the daemon would hear them over UDP. */
export function bridge(station: FakeStation, daemon: FakeDaemon): void {
  station.onSing = (it) =>
    daemon.surface({
      station: station.name,
      key_id: station.keyId,
      stream: it.stream,
      seq: it.seq,
      epoch: it.epoch,
      issued_at: it.issued_at,
      ttl_ms: it.expires_at - it.issued_at,
      text: it.text,
    });
  station.onHush = (t) => daemon.retract({ key_id: station.keyId, stream: t.stream, seq: t.seq, epoch: t.epoch });
}

export function configFor(name: string, dir: string, daemon: FakeDaemon, extra: Obj = {}): BindingConfig {
  // Tests read heard text from any session unless they set listen themselves.
  return parseConfig({ binding: name, daemon: { socket: daemon.path }, stateDir: join(dir, `state-${name}`), listen: { payloadSessions: ["*"] }, ...extra });
}

export function makeBinding(cfg: BindingConfig, clock: Clock, extra: Partial<BindingOptions> = {}): Binding {
  return new Binding({
    config: cfg,
    root: cfg.stateDir as string,
    clock: clock.now,
    tickMs: 3_600_000,
    link: { backoff: { firstMs: 20, maxMs: 100, jitter: 0 }, snapshotMs: 2_000 },
    ...extra,
  });
}

export const SESSION: Caller = { sessionKey: "agent:main:main", sessionId: "s-1", subagent: false };
export const OTHER_SESSION: Caller = { sessionKey: "agent:main:other", sessionId: "s-2", subagent: false };
