// The Receiver against record v1 sequences (RFC-0001 §14.18.3): bootstrap, join kinds, gaps, the join snapshot,
// retracts, expiry, and the current view versus carried items.

import assert from "node:assert/strict";
import { test } from "node:test";
import { type Note, ProtocolError, Receiver } from "../src/receive.ts";
import { type HeardFrame, type Obj, RECORD_V } from "../src/records.ts";
import { Clock, KEY_CAEL, frameFields } from "./helpers.ts";

function rec(type: string, seq: number, fields: Obj = {}, run = "r1"): Obj {
  return { v: RECORD_V, type, rec_seq: seq, run, ...fields };
}

function setup(clock = new Clock()) {
  const heard: HeardFrame[] = [];
  const notes: Note[] = [];
  const withdrawn: string[] = [];
  const r = new Receiver(
    {
      heard: (f) => heard.push(f),
      withdrawn: (w) => withdrawn.push(w.idem),
      presence: () => undefined,
      note: (n) => notes.push(n),
    },
    { clock: clock.now },
  );
  return { r, heard, notes, withdrawn, clock };
}

function boot(r: Receiver, opts: { snapshot?: boolean; run?: string; hello?: number; landing?: number } = {}): void {
  const run = opts.run ?? "r1";
  r.connected(opts.snapshot !== false);
  r.apply(rec("hello", opts.hello ?? 1, { join_snapshot: opts.snapshot !== false }, run));
  r.apply(rec("landing_state", opts.landing ?? 50, { mute: null, breaker: "closed" }, run));
}

function frame(clock: Clock, seq: number, extra: Obj = {}): Obj {
  return frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq, issued_at: clock.t, ...extra });
}

test("bootstrap: the first record must be hello and the second a later landing_state of the same run", () => {
  const { r } = setup();
  r.connected(true);
  assert.throws(() => r.apply(rec("landing_state", 2)), ProtocolError);
  const s2 = setup();
  s2.r.connected(true);
  s2.r.apply(rec("hello", 5));
  assert.throws(() => s2.r.apply(rec("landing_state", 5)), /later landing_state/);
  const s3 = setup();
  s3.r.connected(true);
  s3.r.apply(rec("hello", 5));
  assert.throws(() => s3.r.apply(rec("landing_state", 9, {}, "r2")), /from run/);
});

test("first join: the skip from the baseline is not a gap; nothing is current until the snapshot completes", () => {
  const { r, notes, clock } = setup();
  boot(r); // hello 1, landing_state 50: the jump is the bootstrap, not a gap
  assert.equal(r.current(), false);
  assert.equal(r.status().health, "unknown");
  // The run emitted up to 98 before the cut; the watermark is 98 and the live tail starts at 99.
  r.apply(rec("snapshot_end", 98, { watermark: 98, count: 0, truncated: false, omitted: 0 }));
  r.apply(rec("frame", 99, frame(clock, 1)));
  assert.equal(r.current(), true);
  assert.equal(r.status().health, "ok");
  assert.deepEqual(
    notes.map((n) => n.kind),
    ["joined", "snapshot"],
  );
  assert.equal(r.onAir(clock.t).length, 1);
  // Without a snapshot, the skip from the baseline to the first live record is not a gap either.
  const s2 = setup();
  boot(s2.r, { snapshot: false });
  s2.r.apply(rec("frame", 99, frame(s2.clock, 1)));
  s2.r.apply(rec("frame", 100, frame(s2.clock, 2)));
  assert.equal(s2.r.status().records_lost, 0);
});

test("a rec_seq gap after the point of continuity reports records_lost; a regression ends the connection", () => {
  const { r, notes, clock } = setup();
  boot(r);
  r.apply(rec("snapshot_end", 50, { watermark: 50, count: 0, truncated: false, omitted: 0 }));
  r.apply(rec("frame", 51, frame(clock, 1)));
  r.apply(rec("frame", 54, frame(clock, 2)));
  const lost = notes.filter((n) => n.kind === "records_lost");
  assert.deepEqual(lost, [{ kind: "records_lost", missing: 2, total: 2, why: "gap" }]);
  assert.deepEqual(r.status().reasons, ["records_lost"]);
  assert.throws(() => r.apply(rec("frame", 53, frame(clock, 3))), /rec_seq 53 after 54/);
});

test("a complete snapshot replaces the view; a truncated one merges and reports joined_late", () => {
  const { r, clock } = setup();
  boot(r);
  const a = frame(clock, 1);
  r.apply(rec("snapshot", 50, { snap_seq: 1, entry: { frame: a } }));
  r.apply(rec("snapshot_end", 50, { watermark: 50, count: 1, truncated: false, omitted: 0 }));
  assert.deepEqual(r.onAir(clock.t).map((i) => i.frame.seq), [1]);
  r.lost("end_of_stream");
  assert.equal(r.onAir(clock.t).length, 0); // nothing is current without a connection
  assert.deepEqual(r.carried(clock.t).map((i) => i.frame.seq), [1]);
  boot(r);
  const b = frame(clock, 2);
  r.apply(rec("snapshot", 60, { snap_seq: 1, entry: { frame: b } }));
  r.apply(rec("snapshot_end", 60, { watermark: 60, count: 1, truncated: true, omitted: 3 }));
  assert.deepEqual(r.onAir(clock.t).map((i) => i.frame.seq), [2]);
  assert.deepEqual(r.carried(clock.t).map((i) => i.frame.seq), [1]); // merged, not confirmed
  assert.deepEqual(r.status().reasons, ["records_lost", "joined_late"]); // a rejoin is a loss, reported once
  r.lost("end_of_stream");
  boot(r);
  r.apply(rec("snapshot_end", 70, { watermark: 70, count: 0, truncated: false, omitted: 0 }));
  assert.equal(r.carried(clock.t).length, 0); // a complete snapshot: absence means not live
});

test("without a join snapshot the view is current at once but joined_late", () => {
  const { r, clock } = setup();
  boot(r, { snapshot: false });
  assert.equal(r.status().snapshot, "unsupported");
  r.apply(rec("frame", 51, frame(clock, 1)));
  assert.equal(r.current(), true);
  assert.deepEqual(r.status().reasons, ["joined_late"]);
});

test("a retract removes the item and keeps it out: a later copy of the same tuple is not re-admitted", () => {
  const { r, heard, withdrawn, clock } = setup();
  boot(r, { snapshot: false });
  const f = frame(clock, 7);
  r.apply(rec("frame", 51, f));
  r.apply(rec("retract", 52, { idem: f.idem, reason: "plucked", target: f.frame, by: null }));
  r.apply(rec("frame", 53, { ...f, dedup: "resurfaced" }));
  assert.equal(heard.length, 1);
  assert.deepEqual(withdrawn, [f.idem]);
  assert.equal(r.onAir(clock.t).length, 0);
  assert.equal(r.counts.after_retract, 1);
});

test("expiry: a frame past local_expiry_at is never admitted, and the view drops items as they expire", () => {
  const { r, heard, clock } = setup();
  boot(r, { snapshot: false });
  r.apply(rec("frame", 51, frameFields({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t - 120_000, ttl_ms: 60_000 })));
  assert.equal(heard.length, 0);
  assert.equal(r.counts.expired_on_arrival, 1);
  r.apply(rec("frame", 52, frame(clock, 2, { ttl_ms: 10_000 })));
  clock.advance(10_001);
  r.tick(clock.t);
  assert.equal(r.onAir(clock.t).length, 0);
});

test("fail-closed rules: unknown type counted; malformed frame dropped; other major version fails receive", () => {
  const { r, heard, clock } = setup();
  boot(r, { snapshot: false });
  r.apply(rec("mystery", 51));
  assert.equal(r.counts.unknown_type, 1);
  const bad = frame(clock, 1);
  delete (bad as Record<string, unknown>).times;
  r.apply(rec("frame", 52, bad));
  assert.equal(r.counts.malformed_record, 1);
  r.apply(rec("frame", 53, frame(clock, 2, { admission: "unverified" })));
  assert.equal(r.counts.frames_other, 1);
  assert.equal(heard.length, 0);
  assert.throws(() => r.apply({ ...rec("frame", 54), v: "canticle-receptor-record/2" }), /record_version/);
  assert.equal(r.status().health, "failed");
});

test("connection loss: on air becomes unknown and presence unknown, never offline", () => {
  const { r, clock } = setup();
  boot(r, { snapshot: false });
  r.apply(rec("presence", 51, { key_id: KEY_CAEL, station: { name: "cael", principal: null }, state: "EQUIPPED_QUIET", last_beacon_at: null }));
  assert.equal(r.presence()[0]?.state, "EQUIPPED_QUIET");
  r.lost("silent");
  assert.equal(r.presence()[0]?.state, "unknown");
  const s = r.status();
  assert.equal(s.health, "unknown");
  assert.deepEqual(s.reasons, ["disconnected", "silent"]);
  assert.equal(r.onAir(clock.t).length, 0);
});

test("a bye or fatal ends the run with its reason", () => {
  const { r, notes } = setup();
  boot(r, { snapshot: false });
  r.apply(rec("fatal", 51, { reason: "state_not_durable", detail: "disk" }));
  r.lost("end_of_stream");
  assert.equal(r.status().last_failure, "fatal:state_not_durable");
  assert.ok(notes.some((n) => n.kind === "ended" && n.how === "fatal" && n.reason === "state_not_durable"));
});
