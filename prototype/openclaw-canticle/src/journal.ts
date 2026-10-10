// The inbound heard journal (binary-canticle#97): append-only entries under <root>/journal/, one JSON line each,
// in segment files named by their first entry's seq. It records what this binding heard (with provenance, receive
// time, payload and expiry), what was withdrawn, presence changes and connection notes. It is history, not the air:
// "what is on air now?" is the Receiver's view.
//
// - Every entry has a seq, increasing by one, never reused. A reader's cursor names one; before the journal hands a
//   reader any seq it flushes the segment that holds it, so a crash cannot reuse a seq somebody holds.
// - A heard item is journaled once per identity (its record v1 `idem`): a resurfaced record, a snapshot entry or a
//   re-sent record of the same item is not a new entry.
// - Retention is bounded by entries, bytes and age. Whole segments go, oldest first; the newest segment is always
//   kept, so the next seq is always known.

import { closeSync, fsyncSync, openSync, readFileSync, readdirSync, truncateSync, unlinkSync, writeSync } from "node:fs";
import { join } from "node:path";
import type { Note } from "./receive.ts";
import type { HeardFrame, Tuple } from "./records.ts";
import { ensureDir, syncDir } from "./store.ts";

export type Disposition = "held" | "muted" | "self";

export type HeardEntry = {
  seq: number;
  at: number;
  kind: "heard";
  run: string;
  rec_seq: number;
  source: "live" | "snapshot";
  /** held: readable; muted: heard under a mute (readable, marked, and never eligible for a later push); self: this
   * binding's own station (read only on request). */
  disposition: Disposition;
  mute: string | null;
  frame: HeardFrame;
};
export type WithdrawnEntry = {
  seq: number;
  at: number;
  kind: "withdrawn";
  run: string;
  rec_seq: number;
  idem: string;
  reason: string;
  by: Tuple | null;
  station: string | null;
  stream: string | null;
  self: boolean;
};
export type PresenceEntry = {
  seq: number;
  at: number;
  kind: "presence";
  run: string;
  rec_seq: number;
  source: "live" | "snapshot";
  key_id: string;
  station: string | null;
  principal: string | null;
  state: string;
  last_beacon_at: number | null;
};
export type NoteEntry = { seq: number; at: number; kind: "note"; note: Note };
export type Entry = HeardEntry | WithdrawnEntry | PresenceEntry | NoteEntry;
export type Draft =
  | Omit<HeardEntry, "seq" | "at">
  | Omit<WithdrawnEntry, "seq" | "at">
  | Omit<PresenceEntry, "seq" | "at">
  | Omit<NoteEntry, "seq" | "at">;

export type Retention = { maxEntries: number; maxBytes: number; maxAgeMs: number };
export const DEFAULT_RETENTION: Retention = { maxEntries: 5_000, maxBytes: 8 * 1024 * 1024, maxAgeMs: 24 * 3_600_000 };

const SEGMENT_ENTRIES = 500;
const SEGMENT_BYTES = 512 * 1024;
const SEGMENT_NAME = /^(\d{12})\.jsonl$/;
const KEYS_MAX = 8_192;
const SKEW_MS = 5_000; // §14.18.5 [PROPOSED DEFAULT]

type Segment = { first: number; path: string; entries: Entry[]; bytes: number };

export class Journal {
  private readonly dir: string;
  private readonly retention: Retention;
  private segments: Segment[] = [];
  private fd: number | null = null;
  private next = 1;
  private synced = 0;
  private entryCount = 0;
  private byteCount = 0;
  /** Heard identities → until when a repeat of them is still a repeat (local expiry + 5 s). */
  private readonly keys = new Map<string, number>();
  /** Heard identities → how many retained entries carry them. */
  private readonly retained = new Map<string, number>();
  readonly counts = { pruned_entries: 0, pruned_segments: 0, partial_lines: 0, bad_lines: 0, repeats: 0 };

  constructor(dir: string, retention: Retention = DEFAULT_RETENTION) {
    this.dir = dir;
    this.retention = retention;
  }

  /** Read the segments on disk. ``carried`` holds identities whose entries were pruned while still live. */
  load(carried: Record<string, number>, now: number): void {
    ensureDir(this.dir);
    const names = readdirSync(this.dir)
      .filter((n) => SEGMENT_NAME.test(n))
      .sort();
    for (const [i, name] of names.entries()) {
      const path = join(this.dir, name);
      const buf = readFileSync(path);
      const end = buf.lastIndexOf(0x0a) + 1;
      if (end < buf.length) {
        this.counts.partial_lines += 1; // a write cut short by a crash: never an entry
        if (i === names.length - 1) {
          truncateSync(path, end);
        }
      }
      const seg: Segment = { first: Number(SEGMENT_NAME.exec(name)?.[1]), path, entries: [], bytes: 0 };
      for (const line of buf.subarray(0, end).toString("utf8").split("\n")) {
        if (line === "") {
          continue;
        }
        const e = parseEntry(line);
        if (e === null || e.seq < this.next) {
          this.counts.bad_lines += 1;
          continue;
        }
        seg.entries.push(e);
        seg.bytes += Buffer.byteLength(line) + 1;
        this.next = e.seq + 1;
      }
      this.segments.push(seg);
      this.entryCount += seg.entries.length;
      this.byteCount += seg.bytes;
      for (const e of seg.entries) {
        if (e.kind === "heard") {
          this.retain(e.frame.idem, 1);
          this.remember(e.frame.idem, e.frame.times.local_expiry_at + SKEW_MS);
        }
      }
    }
    for (const [idem, until] of Object.entries(carried)) {
      if (until > now) {
        this.remember(idem, until);
      }
    }
    this.synced = this.next - 1;
  }

  get head(): number {
    return this.next - 1;
  }

  /** The highest seq known to be on disk: every seq a reader was ever handed is at or below it. */
  get durable(): number {
    return this.synced;
  }

  /** The seq of the oldest retained entry (head + 1 when there is none). */
  get oldest(): number {
    for (const s of this.segments) {
      const e = s.entries[0];
      if (e !== undefined) {
        return e.seq;
      }
    }
    return this.next;
  }

  get size(): { entries: number; bytes: number; segments: number } {
    return { entries: this.entryCount, bytes: this.byteCount, segments: this.segments.length };
  }

  /** Whether an item with this identity was already journaled (and is not yet past its local expiry + skew). */
  heard(idem: string, now: number): boolean {
    const until = this.keys.get(idem);
    return until !== undefined && until > now;
  }

  append(d: Draft, now: number): Entry {
    if (d.kind === "heard" && this.heard(d.frame.idem, now)) {
      this.counts.repeats += 1;
      throw new Error("append of a heard identity already journaled");
    }
    const e = { ...d, seq: this.next, at: now } as Entry;
    const line = `${JSON.stringify(e)}\n`;
    const bytes = Buffer.byteLength(line);
    let seg = this.segments.at(-1);
    if (seg === undefined || seg.entries.length >= SEGMENT_ENTRIES || seg.bytes + bytes > SEGMENT_BYTES) {
      seg = this.rotate(e.seq);
    }
    const fd = this.fd ?? (this.fd = openSync(seg.path, "a", 0o600));
    writeSync(fd, line);
    seg.entries.push(e);
    seg.bytes += bytes;
    this.entryCount += 1;
    this.byteCount += bytes;
    this.next += 1;
    if (e.kind === "heard") {
      this.retain(e.frame.idem, 1);
      this.remember(e.frame.idem, e.frame.times.local_expiry_at + SKEW_MS);
    }
    return e;
  }

  private rotate(first: number): Segment {
    this.sync();
    if (this.fd !== null) {
      closeSync(this.fd);
      this.fd = null;
    }
    const seg: Segment = { first, path: join(this.dir, `${String(first).padStart(12, "0")}.jsonl`), entries: [], bytes: 0 };
    this.segments.push(seg);
    this.fd = openSync(seg.path, "a", 0o600);
    syncDir(this.dir);
    return seg;
  }

  /** Flush the newest segment, so every seq up to the head survives a crash. */
  sync(): void {
    if (this.fd !== null && this.synced < this.head) {
      fsyncSync(this.fd);
    }
    this.synced = this.head;
  }

  /** Entries with seq > ``after``, oldest first. Flushes first: every seq a reader sees is durable. */
  *scan(after: number): Generator<Entry> {
    this.sync();
    for (const seg of this.segments) {
      const last = seg.entries.at(-1);
      if (last === undefined || last.seq <= after) {
        continue;
      }
      let lo = 0;
      let hi = seg.entries.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if ((seg.entries[mid] as Entry).seq <= after) {
          lo = mid + 1;
        } else {
          hi = mid;
        }
      }
      for (let i = lo; i < seg.entries.length; i += 1) {
        yield seg.entries[i] as Entry;
      }
    }
  }

  /** Apply retention. Returns whether anything was pruned (the binding then saves the identities it carries). */
  prune(now: number): boolean {
    let pruned = false;
    const r = this.retention;
    while (this.segments.length > 1) {
      const seg = this.segments[0] as Segment;
      const newest = seg.entries.at(-1);
      const aged = newest === undefined || newest.at <= now - r.maxAgeMs;
      if (!aged && this.entryCount <= r.maxEntries && this.byteCount <= r.maxBytes) {
        break;
      }
      this.segments.shift();
      unlinkSync(seg.path);
      this.entryCount -= seg.entries.length;
      this.byteCount -= seg.bytes;
      this.counts.pruned_entries += seg.entries.length;
      this.counts.pruned_segments += 1;
      for (const e of seg.entries) {
        if (e.kind === "heard") {
          this.retain(e.frame.idem, -1);
        }
      }
      pruned = true;
    }
    for (const [idem, until] of this.keys) {
      if (until <= now) {
        this.keys.delete(idem);
      }
    }
    if (pruned) {
      syncDir(this.dir);
    }
    return pruned;
  }

  /** Live identities whose entries are no longer retained: the binding persists these across a restart. */
  carried(now: number): Record<string, number> {
    const out: Record<string, number> = {};
    for (const [idem, until] of this.keys) {
      if (until > now && !this.retained.has(idem)) {
        out[idem] = until;
      }
    }
    return out;
  }

  close(): void {
    this.sync();
    if (this.fd !== null) {
      closeSync(this.fd);
      this.fd = null;
    }
  }

  private retain(idem: string, delta: number): void {
    const n = (this.retained.get(idem) ?? 0) + delta;
    if (n > 0) {
      this.retained.set(idem, n);
    } else {
      this.retained.delete(idem);
    }
  }

  private remember(idem: string, until: number): void {
    const prev = this.keys.get(idem) ?? 0;
    this.keys.delete(idem); // re-inserted last, so the eviction below takes the least recently heard
    this.keys.set(idem, Math.max(until, prev));
    if (this.keys.size > KEYS_MAX) {
      const oldest = this.keys.keys().next().value;
      if (oldest !== undefined) {
        this.keys.delete(oldest);
      }
    }
  }
}

function parseEntry(line: string): Entry | null {
  try {
    const e = JSON.parse(line) as Entry;
    if (typeof e === "object" && e !== null && Number.isSafeInteger(e.seq) && typeof e.kind === "string") {
      return e;
    }
  } catch {
    // counted by the caller
  }
  return null;
}
