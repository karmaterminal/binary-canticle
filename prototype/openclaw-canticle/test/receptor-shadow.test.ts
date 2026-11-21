import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  SHADOW_V, advanceShadow, createShadow, inspectShadow, parseShadowPolicy, previewShadow,
  type ShadowState,
} from "../src/receptor-shadow.ts";
import { RECORD_V, type Obj } from "../src/records.ts";
import { frameFields, KEY_RUNE, KEY_SCRIBE, KEY_CAEL } from "./helpers.ts";

const T = 1_000_000;
function policy(): { v: string; ceiling: Obj; profile: Obj } {
  return {
    v: SHADOW_V,
    ceiling: {
      revision: 1, ambient: true, wakePreview: false,
      sources: [
        { keyId: KEY_RUNE, station: "rune", streams: ["town.*"], classes: ["chatter", "alarm"], scopes: ["lan"] },
        { keyId: KEY_SCRIBE, station: "scribe", streams: ["town.*"], classes: ["chatter", "alarm"], scopes: ["lan"] },
      ],
    },
    profile: { id: "offline-example", revision: 1, tune: ["*:town.*"], mode: "ambient", batch: { count: 3, quietMs: 5_000, maxWaitMs: 30_000 } },
  };
}
function frame(at: number, seq: number, change: Obj = {}): Obj {
  return {
    v: RECORD_V, type: "frame", run: "fixture", rec_seq: seq,
    ...frameFields({ station: "rune", key_id: KEY_RUNE, stream: "town.weather", seq, issued_at: T + at - 1, ttl_ms: 180_000 }),
    ...change,
  };
}
function other(at: number, seq: number, text = "from scribe"): Obj {
  return {
    v: RECORD_V, type: "frame", run: "fixture", rec_seq: seq,
    ...frameFields({ station: "scribe", key_id: KEY_SCRIBE, stream: "town.music", seq, issued_at: T + at - 1, ttl_ms: 180_000, text }),
  };
}
function retract(f: Obj): Obj { return { v: RECORD_V, type: "retract", idem: f.idem, target: f.frame, reason: "plucked", by: null }; }
class Run {
  state: ShadowState;
  constructor(raw = policy()) {
    this.state = advanceShadow(createShadow(raw), { at: T, op: "health", health: "ok" }).state;
  }
  step(at: number, op: string, rest: Obj = {}) {
    const result = advanceShadow(this.state, { at: T + at, op, ...rest });
    this.state = result.state;
    return result;
  }
  hear(at: number, record: Obj) { return this.step(at, "record", { record }); }
}

test("shadow defaults are untuned and silent; it cannot install a live profile", () => {
  const p = policy();
  p.ceiling.ambient = false;
  delete p.profile.tune; delete p.profile.mode; delete p.profile.batch;
  const run = new Run(p);
  const result = run.hear(0, frame(0, 1));
  assert.deepEqual(result.view.effective.sources, []);
  assert.equal(result.view.effective.mode, "ringbuffer_only");
  assert.deepEqual(result.batches, []);
  assert.equal(result.view.dispatch, "none");
  assert.ok(result.view.executionLimits.includes("no_profile_installed"));
  assert.ok(result.view.executionLimits.includes("wake_not_implemented"));
  assert.equal(run.step(60_000, "tick").batches.length, 0);
});

test("shadow intersects key, station, stream, class and scope; a matching name grants no new signer", () => {
  const p = policy();
  p.profile.tune = ["*:*"]; p.profile.classes = ["chatter", "advisory"]; p.profile.scopes = ["lan", "fleet"];
  p.profile.freshnessMs = 500_000;
  p.profile.batch = { maxItems: 99, maxBytes: 60_000, count: 200 };
  p.ceiling.maxPendingItems = 8;
  const run = new Run(p);
  const effective = inspectShadow(run.state).effective;
  assert.deepEqual(effective.sources[0], { keyId: KEY_RUNE, station: "rune", streams: ["town.*"], classes: ["chatter"], scopes: ["lan"] });
  assert.equal(effective.batch.maxItems, 5); assert.equal(effective.batch.maxBytes, 1_536); assert.equal(effective.batch.count, 8);
  assert.equal(effective.freshnessMs, 120_000);
  const strangers = {
    ...frame(0, 1),
    ...frameFields({ station: "rune", key_id: KEY_CAEL, stream: "town.weather", seq: 1, issued_at: T - 1 }),
  };
  assert.deepEqual(run.hear(0, strangers).reasons, ["outside_operator_ceiling"]);
  assert.deepEqual(run.hear(1, frame(1, 2, { scope: "fleet" })).reasons, ["outside_operator_ceiling"]);
  assert.deepEqual(run.hear(2, frame(2, 3, { class: "advisory" })).reasons, ["outside_operator_ceiling"]);
  assert.equal(run.state.items.length, 0); assert.equal(run.state.seen.length, 0);
  assert.ok(run.hear(3, frame(3, 4)).reasons.includes("queued"));
});

test("shadow prefix intersection is exact and self remains excluded", () => {
  const p = policy();
  p.profile.tune = ["rune:town.weather.*", "scribe:town.music"];
  p.ceiling.selfKeyId = KEY_RUNE;
  const run = new Run(p);
  assert.deepEqual(run.state.effective.sources.map(s => s.station), ["scribe"]);
  assert.deepEqual(run.state.effective.sources[0]?.streams, ["town.music"]);
  assert.deepEqual(run.hear(0, frame(0, 1)).reasons, ["outside_operator_ceiling"]);
  const q = policy(); q.profile.tune = ["rune:town.weather.*"];
  const narrow = new Run(q);
  assert.deepEqual(narrow.hear(0, frame(0, 1)).reasons, ["outside_receiver_profile"]);
});

test("distinct count triggers a bounded batch after the minimum coalescing window", () => {
  const run = new Run();
  run.hear(0, frame(0, 1)); run.hear(1_000, frame(1_000, 2));
  const ready = run.hear(2_000, other(2_000, 3));
  assert.ok(ready.reasons.includes("coalesce_minimum"));
  const result = run.step(5_000, "tick");
  assert.equal(result.batches.length, 1);
  assert.equal(result.batches[0]?.trigger, "count");
  assert.equal(result.batches[0]?.dueAt, T + 2_000);
  assert.equal(result.batches[0]?.items.length, 3);
  assert.equal(result.batches[0]?.wouldRequestWake, false);
  assert.equal(result.view.pending.length, 0);
});

test("repeated identity neither meets count nor postpones quiet/hard deadlines", () => {
  const p = policy(); p.profile.batch = { count: 2, quietMs: 5_000, maxWaitMs: 10_000 };
  const run = new Run(p), first = frame(0, 1);
  run.hear(0, first);
  for (const at of [1_000, 2_000, 4_999]) {
    assert.equal(run.hear(at, first).batches.length, 0);
    assert.equal(run.state.pending.length, 1);
    assert.equal(run.state.pending[0]?.queuedAt, T);
  }
  const result = run.step(5_000, "tick");
  assert.equal(result.batches[0]?.trigger, "quiet");
  assert.equal(result.batches[0]?.dueAt, T + 5_000);
  assert.equal(run.hear(6_000, first).view.pending.length, 0);
});

test("continuous distinct chatter flushes on maximum wait; a new frame cannot reset an overdue deadline", () => {
  const p = policy(); p.profile.batch = { count: 64, quietMs: 5_000, maxWaitMs: 10_000, perSource: 5 };
  const run = new Run(p);
  run.hear(0, frame(0, 1)); run.hear(4_000, frame(4_000, 2)); run.hear(8_000, frame(8_000, 3));
  const result = run.hear(10_000, frame(10_000, 4));
  assert.equal(result.batches[0]?.trigger, "max_wait");
  assert.equal(result.batches[0]?.dueAt, T + 10_000);
  assert.equal(result.batches[0]?.items.length, 3);
  assert.deepEqual(result.view.pending.map(p => p.queuedAt), [T + 10_000]);
  const q = policy(); q.profile.batch = { count: 64 };
  const quiet = new Run(q); quiet.hear(0, frame(0, 1));
  const delayed = quiet.hear(6_000, frame(6_000, 2));
  assert.equal(delayed.batches[0]?.dueAt, T + 5_000);
  assert.equal(delayed.view.pending.length, 1);
});

test("round-robin signer fairness and item/byte caps leave an inspectable bounded remainder", () => {
  const p = policy(); p.profile.batch = { count: 64, maxItems: 2, maxBytes: 20, perSource: 2 };
  const run = new Run(p);
  for (let i = 1; i <= 4; i++) run.hear(i, frame(i, i));
  run.hear(5, other(5, 10, "two")); run.hear(6, other(6, 11, "three"));
  const first = run.step(5_006, "tick").batches[0]!;
  assert.equal(first.items.length, 2); assert.ok(first.bodyBytes <= 20);
  assert.deepEqual(first.items.map(x => x.keyId), [KEY_RUNE, KEY_SCRIBE]);
  const second = run.step(10_006, "tick").batches[0]!;
  assert.deepEqual(second.items.map(x => x.keyId), [KEY_RUNE, KEY_SCRIBE]);
  assert.equal(run.state.pending.length, 2);
  const cap = policy(); cap.ceiling.maxPendingItems = 1;
  const bounded = new Run(cap); bounded.hear(0, frame(0, 1));
  assert.ok(bounded.hear(1, frame(1, 2)).reasons.includes("current_capacity"));
  assert.equal(bounded.state.items.length, 1); assert.equal(bounded.state.pending.length, 1);
  // Admission fairness is intentionally not claimed: the retained-current cap is shared globally.
  assert.ok(bounded.hear(2, other(2, 3)).reasons.includes("current_capacity"));
  bounded.step(5_000, "tick");
  assert.ok(bounded.hear(6_000, other(6_000, 4)).reasons.includes("current_capacity"));
});

test("one-slot batches rotate among retained signers, including a source with only one queued item", () => {
  const p = policy(); p.profile.batch = { count: 64, maxItems: 1 };
  const run = new Run(p);
  for (let i = 1; i <= 3; i++) run.hear(i, frame(i, i));
  run.hear(4, other(4, 7));
  assert.equal(run.step(5_004, "tick").batches[0]?.items[0]?.keyId, KEY_RUNE);
  assert.equal(run.step(10_004, "tick").batches[0]?.items[0]?.keyId, KEY_SCRIBE);
});

test("mute/unmute, cancel and withdrawal at the deadline cannot release pending or replay an old copy", () => {
  for (const operation of ["mute", "cancel", "retract"] as const) {
    const run = new Run(), first = frame(0, 1);
    run.hear(0, first);
    const result = run.step(5_000, operation, operation === "mute" ? { keyId: KEY_RUNE } : operation === "retract" ? { record: retract(first) } : {});
    assert.equal(result.batches.length, 0, operation); assert.equal(result.view.pending.length, 0, operation);
    if (operation === "mute") run.step(6_000, "unmute", { keyId: KEY_RUNE });
    assert.equal(run.hear(7_000, first).view.pending.length, 0, operation);
    assert.equal(run.step(20_000, "tick").batches.length, 0, operation);
  }
});

test("policy revocation invalidates queued work; later broadening does not resurrect it", () => {
  const p = policy(), run = new Run(p), first = frame(0, 1);
  run.hear(0, first);
  const revoked = structuredClone(p); revoked.ceiling.revision = 2; revoked.ceiling.sources = [];
  const result = run.step(5_000, "policy", { policy: revoked });
  assert.equal(result.batches.length, 0); assert.equal(result.view.pending.length, 0); assert.equal(result.view.current.length, 0);
  assert.ok(result.view.recent.every(r => r.item === null));
  const restored = structuredClone(p); restored.ceiling.revision = 3;
  run.step(6_000, "policy", { policy: restored });
  assert.equal(run.hear(7_000, first).view.current.length, 0);
  assert.equal(run.step(20_000, "tick").batches.length, 0);
});

test("expiry removes current authority and pending work but keeps a metadata receipt, not elected retention", () => {
  const p = policy(); p.profile.freshnessMs = 5_000;
  const run = new Run(p), first = frame(0, 1);
  run.hear(0, first);
  const result = run.step(5_000, "tick");
  assert.equal(result.batches.length, 0); assert.equal(result.view.current.length, 0); assert.equal(result.view.pending.length, 0);
  assert.ok(result.view.recent.some(r => r.reason === "expired_pending"));
  assert.ok(result.view.executionLimits.includes("no_elected_retention_store"));
  const broader = structuredClone(p); broader.profile.freshnessMs = 120_000; broader.profile.revision = 2;
  run.step(6_000, "policy", { policy: broader });
  assert.equal(run.hear(7_000, first).view.current.length, 0);
  assert.equal(run.state.pending.length, 0);
});

test("a receiver gap means unknown, not disappeared; reconnect requires item reconfirmation and never replays", () => {
  const run = new Run(), first = frame(0, 1);
  run.hear(0, first);
  const gap = run.step(1_000, "health", { health: "gap" });
  assert.equal(gap.view.current.length, 0); assert.equal(gap.view.carried.length, 1); assert.equal(gap.view.pending.length, 0);
  assert.ok(gap.reasons.includes("current_view_unknown_not_absence"));
  const connected = run.step(2_000, "health", { health: "ok" });
  assert.equal(connected.view.current.length, 0); assert.equal(connected.view.carried.length, 1);
  const confirmed = run.hear(3_000, first);
  assert.equal(confirmed.view.current.length, 1); assert.equal(confirmed.view.pending.length, 0);
  assert.equal(run.step(20_000, "tick").batches.length, 0);
});

test("snapshot, resurfaced and refresh records can be inspected but do not enqueue or spend a batch", () => {
  for (const kind of ["snapshot", "resurfaced", "refresh"] as const) {
    const run = new Run();
    const record = frame(0, 1, kind === "resurfaced" ? { dedup: "resurfaced" } : kind === "refresh" ? { flags: { refresh: true, wake_derived: false, exercise: false } } : {});
    const result = run.step(0, "record", { record, snapshot: kind === "snapshot" });
    assert.equal(result.view.current.length, 1, kind); assert.equal(result.view.pending.length, 0, kind);
    assert.equal(run.step(10_000, "tick").batches.length, 0, kind); assert.equal(run.state.batchesAt.length, 0);
  }
});

test("a new state value supersedes a pending old value without two sensations", () => {
  const run = new Run(); run.hear(0, frame(0, 1, { state_key: "weather" }));
  const result = run.hear(1_000, frame(1_000, 2, { state_key: "weather" }));
  assert.equal(result.view.current.length, 1); assert.equal(result.view.pending.length, 1);
  assert.ok(result.view.recent.some(r => r.reason === "superseded_pending"));
  assert.equal(run.step(6_000, "tick").batches[0]?.items[0]?.id, frame(1_000, 2).idem);
});

test("same-key replacement at the flush deadline withdraws the old pending value before presentation", () => {
  const run = new Run(); run.hear(0, frame(0, 1, { state_key: "weather" }));
  const result = run.hear(5_000, frame(5_000, 2, { state_key: "weather" }));
  assert.equal(result.batches.length, 0);
  assert.deepEqual(result.view.pending.map(x => x.id), [frame(5_000, 2).idem]);
  assert.ok(result.view.recent.some(x => x.reason === "superseded_pending" && x.item?.id === frame(0, 1).idem));
  assert.equal(run.step(10_000, "tick").batches[0]?.items[0]?.id, frame(5_000, 2).idem);
});

test("continuous keyed changes reset quiet but preserve maximum wait, presenting only the latest value", () => {
  const p = policy(); p.profile.batch = { count: 64, quietMs: 5_000, maxWaitMs: 10_000 };
  const run = new Run(p);
  for (const [at, seq] of [[0, 1], [4_000, 2], [8_000, 3]] as const) {
    assert.equal(run.hear(at, frame(at, seq, { state_key: "weather" })).batches.length, 0);
    assert.equal(run.state.pending[0]?.queuedAt, T);
    assert.equal(run.state.pending[0]?.changedAt, T + at);
  }
  const result = run.hear(10_000, frame(10_000, 4, { state_key: "weather" }));
  assert.equal(result.batches[0]?.trigger, "max_wait");
  assert.equal(result.batches[0]?.dueAt, T + 10_000);
  assert.deepEqual(result.batches[0]?.items.map(x => x.id), [frame(10_000, 4).idem]);
  assert.equal(result.view.pending.length, 0);
});

test("local source expiry wins over an otherwise later receiver freshness deadline", () => {
  const run = new Run();
  const record = frame(0, 1, { times: { issued_at: T - 1, expires_at: T + 180_000, heard_at: T, received_at: T, offset_ms: 0, local_expiry_at: T + 5_000 } });
  run.hear(0, record);
  const result = run.step(5_000, "tick");
  assert.equal(result.view.current.length, 0); assert.equal(result.view.pending.length, 0); assert.equal(result.batches.length, 0);
  assert.ok(result.view.recent.some(x => x.reason === "expired_pending"));
});

test("tightening queue capacity records every dropped pending item", () => {
  const p = policy(); p.ceiling.maxPendingItems = 2;
  const run = new Run(p); run.hear(0, frame(0, 1)); run.hear(1, frame(1, 2));
  const narrowed = structuredClone(p); narrowed.ceiling.revision = 2; narrowed.ceiling.maxPendingItems = 1;
  const result = run.step(3, "policy", { policy: narrowed });
  assert.equal(result.view.pending.length, 1);
  assert.ok(result.view.recent.some(x => x.reason === "policy_capacity" && x.item?.id === frame(1, 2).idem));
});

test("a ceiling-elected fresh direct alarm previews a wake request but never a dispatch", () => {
  const p = policy(); p.ceiling.wakePreview = true; p.profile.wakeOnAlarm = true;
  const run = new Run(p); run.hear(0, frame(0, 1, { class: "alarm" }));
  const result = run.step(5_000, "tick"), batch = result.batches[0]!;
  assert.equal(batch.wouldRequestWake, true); assert.equal(batch.dispatch, "none");
  assert.ok(batch.wakeReasons.includes("alarm_capability_and_host_proofs_not_evaluated"));
  assert.ok(result.view.executionLimits.includes("wake_not_implemented"));
  for (const change of [
    { class: "chatter" }, { class: "alarm", hop: 1 },
    { class: "alarm", flags: { refresh: false, wake_derived: true, exercise: false } },
  ]) {
    const denied = new Run(p); denied.hear(0, frame(0, 1, change));
    assert.equal(denied.step(5_000, "tick").batches[0]?.wouldRequestWake, false);
  }
  p.ceiling.wakePreview = false;
  const denied = new Run(p); denied.hear(0, frame(0, 1, { class: "alarm" }));
  assert.equal(denied.step(5_000, "tick").batches[0]?.wouldRequestWake, false);
});

test("an alarm already old at first hearing cannot preview a wake; source clock offset is explicit", () => {
  const p = policy(); p.ceiling.wakePreview = true; p.profile.wakeOnAlarm = true;
  for (const offset of [0, 600_000]) {
    const run = new Run(p);
    const record = frame(0, 1, { class: "alarm", times: { issued_at: T - 600_000, expires_at: T + 300_000, heard_at: T, received_at: T, local_expiry_at: T + 300_000, offset_ms: offset } });
    run.hear(0, record);
    const result = run.step(5_000, "tick"), row = result.batches[0]?.items[0];
    assert.equal(row?.sourceAgeAtFirstHearingMs, 600_000 - offset);
    assert.equal(result.batches[0]?.wouldRequestWake, offset === 600_000);
    assert.equal(result.batches[0]?.dispatch, "none");
  }
});

test("public and known aspect alarms never preview a wake even when the fixture grants their read scope", () => {
  const p = policy(); p.ceiling.wakePreview = true; p.profile.wakeOnAlarm = true;
  p.ceiling.sources = [{ keyId: KEY_RUNE, station: "rune", streams: ["*"], classes: ["alarm"], scopes: ["lan", "public"] }];
  p.profile.tune = ["*:*"];
  for (const variant of [
    { scope: "public", stream: "town.weather", lens: null, reason: "public_scope_never_wakes" },
    { scope: "lan", stream: "lens.threat", lens: null, reason: "aspect_stream_never_wakes" },
    { scope: "lan", stream: "town.weather", lens: 0, reason: "aspect_stream_never_wakes" },
    { scope: "lan", stream: "town.weather", lens: 7, reason: "aspect_stream_never_wakes" },
  ]) {
    const run = new Run(p);
    const record = {
      ...frame(0, 1),
      ...frameFields({ station: "rune", key_id: KEY_RUNE, stream: variant.stream, class: "alarm", seq: 1, issued_at: T - 1, ttl_ms: 180_000 }),
      scope: variant.scope, lens: variant.lens,
    };
    run.hear(0, record);
    const batch = run.step(5_000, "tick").batches[0]!;
    assert.equal(batch.wouldSurface, true, variant.reason);
    assert.equal(batch.wouldRequestWake, false, variant.reason);
    assert.equal(batch.dispatch, "none");
    assert.ok(batch.wakeReasons.includes(variant.reason));
    assert.equal(batch.items[0]?.lens, variant.lens);
  }
});

test("rolling-hour cap explains an overdue batch instead of quietly discarding or dispatching it", () => {
  const p = policy(); p.ceiling.maxBatchesPerHour = 1;
  const run = new Run(p); run.hear(0, frame(0, 1));
  assert.equal(run.step(5_000, "tick").batches.length, 1);
  run.hear(6_000, frame(6_000, 2));
  const blocked = run.step(11_000, "tick");
  assert.ok(blocked.reasons.includes("batch_hour_budget")); assert.equal(blocked.batches.length, 0);
  assert.equal(blocked.view.pending.length, 1);
  assert.equal(run.step(200_000, "tick").view.pending.length, 0);
});

test("reducer is deterministic and does not mutate inputs or put payload text in state/output", () => {
  const run = new Run(), state = structuredClone(run.state);
  const record = { ...frame(0, 1), ...frameFields({ station: "rune", key_id: KEY_RUNE, stream: "town.weather", seq: 1, issued_at: T - 1, text: "private-fixture-phrase" }) };
  const event = { at: T, op: "record", record };
  const eventCopy = structuredClone(event), one = advanceShadow(state, event), two = advanceShadow(state, event);
  assert.deepEqual(one, two); assert.deepEqual(state, run.state); assert.deepEqual(event, eventCopy);
  assert.ok(!JSON.stringify(one).includes("private-fixture-phrase"));
  one.view.current.length = 0;
  assert.equal(one.state.items.length, 1);
});

test("strict fixture parsing rejects typos, backward time, oversized timelines and policy changes without revision", () => {
  const p = policy(); p.profile.typo = true;
  assert.throws(() => parseShadowPolicy(p), /unknown key/);
  const run = new Run();
  assert.throws(() => run.step(-1, "tick"), /expected integer/);
  assert.throws(() => run.step(0, "tick", { keyId: KEY_RUNE }), /unknown key/);
  const changed = policy(); changed.ceiling.sources = [];
  assert.throws(() => run.step(0, "policy", { policy: changed }), /higher revision/);
  assert.throws(() => previewShadow({ v: SHADOW_V, policy: policy(), events: Array(2_049).fill({ at: 0, op: "tick" }) }), /2048/);
  assert.throws(() => parseShadowPolicy({ ...policy(), v: "canticle-receptor-shadow/2" }), /unsupported/);
});

test("malformed or non-admitted frames are excluded and duplicate identity conflicts cannot replace a value", () => {
  const run = new Run();
  assert.ok(run.hear(0, frame(0, 1, { admission: "unverified" })).reasons.includes("not_admitted_frame"));
  assert.ok(run.hear(1, frame(1, 2, { body: { ctype: "text/plain", text: "bad", size: 0, sha256: "0".repeat(64) } })).reasons.includes("malformed_frame"));
  const first = frame(2, 3); run.hear(2, first);
  const changed = { ...first, ...frameFields({ station: "rune", key_id: KEY_RUNE, stream: "town.weather", seq: 3, issued_at: T + 1, ttl_ms: 180_000, text: "different" }) };
  assert.ok(run.hear(3, changed).reasons.includes("identity_conflict"));
  assert.equal(run.state.pending.length, 1);
});

test("offline CLI previews the committed fixture, emits no source text, and refuses oversize input", () => {
  const cwd = fileURLToPath(new URL("../", import.meta.url));
  const input = readFileSync(new URL("../examples/receptor-shadow.json", import.meta.url), "utf8");
  const cli = spawnSync(process.execPath, ["src/receptor-shadow-cli.ts"], { cwd, input, encoding: "utf8", maxBuffer: 4_194_304 });
  assert.equal(cli.status, 0, cli.stderr);
  const result = JSON.parse(cli.stdout) as { final: { dispatch: string }; steps: { batches: { trigger: string }[] }[] };
  assert.equal(result.final.dispatch, "none");
  assert.ok(result.steps.some(s => s.batches.some(b => b.trigger === "max_wait")));
  assert.ok(!cli.stdout.includes("Rain over the workshop"));
  const malformed = spawnSync(process.execPath, ["src/receptor-shadow-cli.ts"], { cwd, input: '{ "secret": ', encoding: "utf8" });
  assert.equal(malformed.status, 1); assert.ok(!malformed.stderr.includes("secret"));
  const oversize = spawnSync(process.execPath, ["src/receptor-shadow-cli.ts"], { cwd, input: " ".repeat(1_048_577), encoding: "utf8" });
  assert.equal(oversize.status, 1); assert.match(oversize.stderr, /1 MiB/);
});
