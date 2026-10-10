// Outbound acceptance (binary-canticle#97): the outbox against a station control socket and the daemon's records.
// say -> station receipt -> on air -> heard back -> expiry; withdraw before and after emission; a duplicate call;
// a station refusal; restart and reconciliation that never sings anything twice.

import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import type { Binding } from "../src/binding.ts";
import type { Obj } from "../src/records.ts";
import { stationClient } from "../src/station.ts";
import {
  Clock,
  FakeDaemon,
  FakeStation,
  KEY_CAEL,
  KEY_RUNE,
  SESSION,
  bridge,
  configFor,
  makeBinding,
  removeDir,
  tempDir,
  waitFor,
} from "./helpers.ts";

let dir: string;
let clock: Clock;
let daemon: FakeDaemon;
let station: FakeStation;
let b: Binding;

const PUBLISH = { station: { name: "rune", keyId: KEY_RUNE } };

async function up(extra: Obj = {}): Promise<Binding> {
  const cfg = configFor("rune", dir, daemon, { ...PUBLISH, publish: { enabled: true, socket: station.path }, ...extra });
  const binding = makeBinding(cfg, clock);
  await binding.start();
  await waitFor(() => binding.receiver.current(), "the binding to join");
  return binding;
}

function result(r: { details: Obj }): Obj {
  return r.details.result as Obj;
}

beforeEach(async () => {
  dir = tempDir();
  clock = new Clock();
  daemon = new FakeDaemon(dir);
  await daemon.start();
  station = new FakeStation(dir, "rune", KEY_RUNE, clock.now);
  await station.start();
  bridge(station, daemon);
  b = await up();
});

afterEach(async () => {
  await b.stop();
  await station.stop();
  await daemon.stop();
  removeDir(dir);
});

test("say: the station's receipt puts the row on air, the daemon hears it back, and it ages to expired", async () => {
  const r = await b.sing(SESSION, { stream: "chatter", payload: "the well is dry", ttlSeconds: 30 });
  const res = result(r);
  assert.equal(res.status, "on-air");
  assert.equal(res.item, "out:rune:1");
  assert.deepEqual(res.onAir, { epoch: 1, seq: 1 });
  assert.equal((res.effective as Obj).ttlMs, 30_000);
  assert.equal(r.text.includes("the well is dry"), false); // results never echo the payload (§15.1)
  await waitFor(() => b.outbox?.get("out:rune:1")?.heard_at !== null, "the daemon to hear the item back");
  // The daemon's record is journaled as this binding's own (self), not as something heard from another prince.
  const listen = b.listen(SESSION, { what: "journal", includeSelf: true });
  assert.match(listen.text, /self: this binding's own station/);
  assert.match(b.listen(SESSION, { what: "journal", includeSelf: true, view: "items" }).text, /the well is dry/);
  assert.doesNotMatch(b.listen(SESSION, { what: "journal", view: "items" }).text, /the well is dry/); // hidden unless asked for
  clock.advance(25_000);
  assert.match(b.outboxView(SESSION, {}).text, /out:rune:1 expiring/);
  clock.advance(5_001);
  await b.tick();
  assert.equal(b.outbox?.get("out:rune:1")?.state, "expired");
  assert.equal(station.ops("sing").length, 1);
});

test("a duplicate call returns the same row and sings once; a reused key with other content is refused", async () => {
  const first = result(await b.sing(SESSION, { stream: "chatter", payload: "once" }));
  const again = result(await b.sing(SESSION, { stream: "chatter", payload: "once" }));
  assert.equal(again.item, first.item);
  assert.equal(again.duplicate, true);
  const keyed = result(await b.sing(SESSION, { stream: "chatter", payload: "keyed", idempotencyKey: "k-1" }));
  const keyedAgain = result(await b.sing(SESSION, { stream: "chatter", payload: "keyed", idempotencyKey: "k-1" }));
  assert.equal(keyedAgain.item, keyed.item);
  const conflict = result(await b.sing(SESSION, { stream: "chatter", payload: "different", idempotencyKey: "k-1" }));
  assert.equal(conflict.status, "rejected");
  assert.equal(conflict.reason, "key_conflict");
  assert.equal(station.ops("sing").length, 2);
  // After the keyed row has expired, the same key still returns it: an ended item is never sung again.
  clock.advance(61_000);
  await b.tick();
  const late = result(await b.sing(SESSION, { stream: "chatter", payload: "keyed", idempotencyKey: "k-1" }));
  assert.equal(late.item, keyed.item);
  assert.equal(late.status, "ended");
  assert.equal(late.state, "expired");
  assert.equal(station.ops("sing").length, 2);
});

test("withdraw after emission: the station plucks it, and a second hush changes nothing", async () => {
  const { item } = result(await b.sing(SESSION, { stream: "chatter", payload: "pluck me" })) as { item: string };
  await waitFor(() => b.outbox?.get(item)?.heard_at !== null, "the item to be heard");
  const h = result(await b.hush(SESSION, { item }));
  assert.equal(h.status, "plucked");
  assert.equal(b.outbox?.get(item)?.state, "withdrawn");
  await waitFor(() => b.listen(SESSION, { what: "journal", includeSelf: true }).text.includes("[canticle:withdrawn]"), "the retract");
  const again = result(await b.hush(SESSION, { item }));
  assert.equal(again.status, "plucked");
  assert.equal(station.ops("hush").length, 1);
});

test("withdraw before emission is confirmed: a lost reply leaves the row unknown, and evidence settles it", async () => {
  station.faults.push({ op: "sing", fault: "drop_after" }); // the station acts, the reply is lost
  daemon.holdFrames = true;
  const s = result(await b.sing(SESSION, { stream: "chatter", payload: "in flight" }));
  assert.equal(s.status, "unknown");
  const item = s.item as string;
  const h = result(await b.hush(SESSION, { item }));
  assert.equal(h.status, "unknown"); // not known to be on air: withdrawn when it shows up
  assert.equal(station.ops("hush").length, 0);
  daemon.releaseFrames(); // the daemon now hears the station's datagram
  await waitFor(() => b.outbox?.get(item)?.state === "withdrawn", "the evidence and the pluck");
  assert.equal(station.ops("hush").length, 1);
  assert.equal(station.ops("sing").length, 1); // never re-sent
});

test("write-ahead: the row is on disk, marked attempted, before the station acts on it", async () => {
  let seen: Obj | null = null;
  const forward = station.onSing;
  station.onSing = (it) => {
    seen = JSON.parse(readFileSync(join(dir, "state-rune", "outbox.json"), "utf8")) as Obj;
    forward?.(it);
  };
  await b.sing(SESSION, { stream: "chatter", payload: "durable first" });
  const rows = (seen as unknown as { rows: Obj[] }).rows;
  assert.equal(rows.length, 1);
  assert.equal(rows[0]?.state, "pending");
  assert.equal(typeof rows[0]?.attempted_at, "number");
});

test("a hush after the station restarted never plucks the new epoch's item that reuses the seq", async () => {
  const { item } = result(await b.sing(SESSION, { stream: "chatter", payload: "epoch one" })) as { item: string };
  assert.deepEqual(b.outbox?.get(item)?.receipt?.seq, 1);
  station.restart(); // epoch 2: its seqs start again at 1
  const other = await stationClient(station.path)({ op: "sing", stream: "chatter", text: "epoch two", scope: "lan" });
  assert.equal(other.kind === "reply" && other.reply.seq, 1);
  const h = result(await b.hush(SESSION, { item }));
  assert.equal(h.status, "not_found");
  assert.equal(b.outbox?.get(item)?.ended?.reason, "station_restarted");
  assert.equal(station.ops("hush").length, 0);
  assert.equal(station.streams.get("chatter")?.ring.get(1)?.text, "epoch two");
});

test("an item plucked outside the plugin (the station's own CLI) is withdrawn when the daemon's retract arrives", async () => {
  const { item } = result(await b.sing(SESSION, { stream: "chatter", payload: "plucked by hand" })) as { item: string };
  const seq = b.outbox?.get(item)?.receipt?.seq;
  const a = await stationClient(station.path)({ op: "hush", stream: "chatter", seq, reason: 0 });
  assert.equal(a.kind === "reply" && a.reply.ok, true);
  await waitFor(() => b.outbox?.get(item)?.state === "withdrawn", "the retract");
  assert.equal(b.outbox?.get(item)?.ended?.reason, "retract:plucked");
});

test("withdraw after expiry reports expired and asks the station nothing", async () => {
  const { item } = result(await b.sing(SESSION, { stream: "chatter", payload: "short", ttlSeconds: 5 })) as { item: string };
  clock.advance(6_000);
  const h = result(await b.hush(SESSION, { item }));
  assert.equal(h.status, "expired");
  assert.equal(station.ops("hush").length, 0);
});

test("a station refusal fails the row; nothing goes on air and nothing is retried", async () => {
  station.faults.push({ op: "sing", fault: "refuse" });
  const s = result(await b.sing(SESSION, { stream: "chatter", payload: "refused" }));
  assert.equal(s.status, "failed");
  assert.match(String(s.reason), /^refused:refused by test/);
  await b.tick();
  assert.equal(station.ops("sing").length, 1);
  const missing = result(await b.sing(SESSION, { stream: "nowhere", payload: "x" }));
  assert.equal(missing.status, "rejected");
  assert.equal(missing.reason, "capability");
  assert.equal(station.ops("sing").length, 1);
});

test("restart: on-air rows are checked against the station, unknown rows stay unknown, nothing is re-sung", async () => {
  const on = result(await b.sing(SESSION, { stream: "chatter", payload: "survives" })).item as string;
  station.faults.push({ op: "sing", fault: "drop_after" });
  daemon.holdFrames = true;
  const lost = result(await b.sing(SESSION, { stream: "chatter", payload: "reply lost" })).item as string;
  await b.stop();
  b = await up();
  await b.tick();
  assert.equal(b.outbox?.get(on)?.state, "on_air");
  assert.equal(b.outbox?.get(lost)?.state, "unknown");
  // A station restart loses its ring: the row is stopped, never sung again.
  station.restart();
  await b.tick();
  assert.equal(b.outbox?.get(on)?.state, "stopped");
  assert.equal(b.outbox?.get(on)?.ended?.reason, "station_restarted");
  // The unknown row lapses once it could no longer be on air.
  clock.advance(70_000);
  await b.tick();
  assert.equal(b.outbox?.get(lost)?.ended?.reason, "lapsed_unconfirmed");
  assert.equal(station.ops("sing").length, 2);
});

test("a row that was mid-send when the process died comes back unknown, and one never sent comes back failed", async () => {
  await b.stop();
  const path = join(dir, "state-rune", "outbox.json");
  const base = {
    key_source: "content",
    session: "agent:main:main",
    station: "rune",
    key_id: KEY_RUNE,
    stream: "chatter",
    stream_id: 1,
    class: null,
    state_key: null,
    purpose: null,
    body: { sha256: "ab".repeat(32), size: 3 },
    text: "abc",
    ttl_s: null,
    created_at: clock.t,
    state: "pending",
    latest_expiry: clock.t + 60_000,
    receipt: null,
    idem: null,
    heard_at: null,
    withdraw: null,
    ended: null,
    last: { at: clock.t, event: "accepted" },
  };
  const rows = [
    { ...base, id: "out:rune:1", key: "a", attempted_at: clock.t },
    { ...base, id: "out:rune:2", key: "b", attempted_at: null },
  ];
  writeFileSync(path, JSON.stringify({ v: "openclaw-canticle-outbox/1", binding: "rune", next_id: 3, rows }));
  b = await up();
  assert.equal(b.outbox?.get("out:rune:1")?.state, "unknown");
  assert.equal(b.outbox?.get("out:rune:2")?.state, "failed");
  assert.equal(b.outbox?.get("out:rune:2")?.ended?.reason, "not_sent");
  assert.equal(b.outbox?.get("out:rune:1")?.text, null);
  await b.tick();
  assert.equal(station.ops("sing").length, 0);
});

test("refusals before anything is sent: taint, sub-agents, credentials, size, rate", async () => {
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t, text: "hello" });
  await waitFor(() => b.listen(SESSION, { what: "journal", view: "items" }).text.includes("hello"), "the heard item");
  const tainted = await b.sing(SESSION, { stream: "chatter", payload: "after hearing" });
  assert.equal(tainted.details.refused, "tainted");
  const other = { sessionKey: "agent:main:fresh", sessionId: "s-9", subagent: false };
  const sub = await b.sing({ ...other, subagent: true }, { stream: "chatter", payload: "x" });
  assert.equal(sub.details.refused, "subagent");
  const byRef = await b.sing(other, { stream: "chatter", payload: { ref: { url: "https://example.invalid/x", sha256: "0".repeat(64), size: 1 } } });
  assert.equal(byRef.details.refused, "bad_param");
  assert.match(byRef.text, /payload is text; a body by reference is not supported here/);
  const secret = result(await b.sing(other, { stream: "chatter", payload: "token ghp_abcdefghijklmnopqrstuvwxyz0123456789AB" }));
  assert.equal(secret.reason, "content_policy");
  assert.equal(JSON.stringify(secret).includes("ghp_"), false); // a refusal names the kind, not the match
  const big = result(await b.sing(other, { stream: "chatter", payload: "x".repeat(801) }));
  assert.equal(big.reason, "size");
  for (let i = 0; i < 5; i += 1) {
    assert.equal(result(await b.sing(other, { stream: "chatter", payload: `n${i}` })).status, "on-air");
  }
  const limited = result(await b.sing(other, { stream: "chatter", payload: "sixth" }));
  assert.equal(limited.status, "budget_exhausted");
  assert.ok((limited.retryAfterMs as number) > 0);
  assert.equal(station.ops("sing").length, 5);
});

test("a station on the socket that is not the pinned key is refused, and so is an unreachable one", async () => {
  await b.stop();
  b = await up({ station: { name: "rune", keyId: "9999999999999999" } });
  const wrong = result(await b.sing(SESSION, { stream: "chatter", payload: "as someone else" }));
  assert.equal(wrong.reason, "station_key_mismatch");
  await station.stop();
  const down = result(await b.sing(SESSION, { stream: "chatter", payload: "nobody home" }));
  assert.equal(down.reason, "station_unreachable");
  assert.equal(station.ops("sing").length, 0);
  assert.equal(b.outbox?.rows().length, 0);
  await station.start(); // afterEach stops it again
});
