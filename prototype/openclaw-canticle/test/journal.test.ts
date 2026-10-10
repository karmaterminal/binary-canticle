// The heard journal on its own (binary-canticle#97): seqs that never repeat, a crash-torn tail, retention by
// whole segments with the newest always kept, and repeat suppression that outlives pruning and restarts. Then, on a
// binding, journal files lost by hand: earlier cursors are refused as stale, never read against reused seqs.

import assert from "node:assert/strict";
import { appendFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { type Draft, Journal } from "../src/journal.ts";
import { heardFrameOf } from "../src/records.ts";
import { Clock, FakeDaemon, KEY_CAEL, SESSION, configFor, frameFields, makeBinding, removeDir, tempDir, waitFor } from "./helpers.ts";

let dir: string;
let clock: Clock;

beforeEach(() => {
  dir = tempDir();
  clock = new Clock();
});

afterEach(() => {
  removeDir(dir);
});

function heard(seq: number, issuedAt: number, text = `item ${seq}`): Draft {
  const frame = heardFrameOf(frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq, issued_at: issuedAt, text }));
  assert.ok(frame);
  return { kind: "heard", run: "run-1", rec_seq: seq, source: "live", disposition: "held", mute: null, frame };
}

function idemOf(seq: number, issuedAt: number): string {
  return (heard(seq, issuedAt) as { frame: { idem: string } }).frame.idem;
}

const RETENTION = { maxEntries: 1_000, maxBytes: 64 * 1024 * 1024, maxAgeMs: 3_600_000 };

test("seqs continue across a reload, and a crash-torn last line is cut off, never read as an entry", () => {
  const jdir = join(dir, "journal");
  const j = new Journal(jdir, RETENTION);
  j.load({}, clock.t);
  for (let i = 1; i <= 3; i += 1) {
    j.append(heard(i, clock.t), clock.t);
  }
  j.close();
  const seg = join(jdir, readdirSync(jdir)[0] as string);
  const whole = statSync(seg).size;
  appendFileSync(seg, '{"seq":4,"at":1,"kind":"note","no'); // the process died mid-write
  const k = new Journal(jdir, RETENTION);
  k.load({}, clock.t);
  assert.equal(k.counts.partial_lines, 1);
  assert.equal(statSync(seg).size, whole);
  assert.equal(k.head, 3);
  const e = k.append({ kind: "note", note: { kind: "disconnected", why: "end_of_stream" } }, clock.t);
  assert.equal(e.seq, 4);
  assert.deepEqual([...k.scan(0)].map((x) => x.seq), [1, 2, 3, 4]);
  assert.deepEqual([...k.scan(2)].map((x) => x.seq), [3, 4]);
  k.close();
});

test("an identity is journaled once; a repeat is refused until its local expiry plus skew", () => {
  const j = new Journal(join(dir, "journal"), RETENTION);
  j.load({}, clock.t);
  j.append(heard(1, clock.t), clock.t);
  assert.equal(j.heard(idemOf(1, clock.t), clock.t), true);
  assert.throws(() => j.append(heard(1, clock.t), clock.t), /already journaled/);
  // 60 s ttl + 5 s skew: after that the same identity is a new item (a station that reused a seq, §14.18.5).
  assert.equal(j.heard(idemOf(1, clock.t), clock.t + 65_001), false);
  j.close();
});

test("retention drops whole segments oldest first, keeps the newest, and still suppresses repeats it pruned", () => {
  const jdir = join(dir, "journal");
  const j = new Journal(jdir, { ...RETENTION, maxEntries: 600 });
  j.load({}, clock.t);
  for (let i = 1; i <= 1_200; i += 1) {
    j.append(heard(i, clock.t), clock.t);
  }
  assert.equal(j.size.segments, 3); // 500 + 500 + 200
  assert.equal(j.prune(clock.t), true);
  // 1 200 entries over 600: the oldest segment goes (700 left), then the next (200 left, the newest, kept).
  assert.equal(j.size.segments, 1);
  assert.equal(j.oldest, 1_001);
  assert.equal(j.head, 1_200);
  assert.equal(readdirSync(jdir).length, 1);
  const pruned = idemOf(10, clock.t);
  assert.equal(j.heard(pruned, clock.t), true); // still live: a resurfaced copy is still a repeat
  const carried = j.carried(clock.t);
  assert.equal(Object.keys(carried).length, 1_000);
  j.close();
  // After a restart, the binding hands the carried identities back.
  const k = new Journal(jdir, { ...RETENTION, maxEntries: 600 });
  k.load(carried, clock.t);
  assert.equal(k.heard(pruned, clock.t), true);
  assert.equal(k.head, 1_200);
  k.close();
});

test("age retention: a segment goes once its newest entry is older than maxAge, but never the newest segment", () => {
  const j = new Journal(join(dir, "journal"), RETENTION);
  j.load({}, clock.t);
  for (let i = 1; i <= 501; i += 1) {
    j.append(heard(i, clock.t), clock.t);
  }
  assert.equal(j.size.segments, 2);
  assert.equal(j.prune(clock.t + 3_600_000), true);
  assert.equal(j.size.segments, 1);
  assert.equal(j.prune(clock.t + 10 * 3_600_000), false); // the newest stays, however old
  assert.equal(j.oldest, 501);
  j.close();
});

test("journal files lost by hand: earlier cursors are refused as stale instead of naming reused seqs", async () => {
  const daemon = new FakeDaemon(dir);
  await daemon.start();
  const cfg = configFor("rune", dir, daemon);
  let b = makeBinding(cfg, clock);
  try {
    await b.start();
    await waitFor(() => b.receiver.current(), "the join");
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t });
    const entries = () => (b.listen(SESSION, { what: "journal", view: "digest" }).details.entries as { kind: string }[]).filter((e) => e.kind === "heard");
    await waitFor(() => entries().length === 1, "the heard entry");
    const cursor = b.listen(SESSION, { what: "journal", view: "digest" }).details.next as string;
    await b.stop();
    rmSync(join(b.root, "journal"), { recursive: true, force: true });
    b = makeBinding(cfg, clock);
    await b.start();
    const r = b.listen(SESSION, { what: "journal", since: cursor });
    assert.equal(r.details.refused, "stale_cursor");
    assert.notEqual((b.listen(SESSION, { what: "journal", view: "digest" }).details.next as string).split(":")[2], cursor.split(":")[2]);
  } finally {
    await b.stop();
    await daemon.stop();
  }
});
