// Two co-resident bindings on one host daemon (binary-canticle#97, #95): a prince's and a scribe's. Each read,
// cursor advance, mute and publish attempt that names the other binding is refused, and both bindings, both
// stations and the daemon are unchanged afterwards. Then each binding restarts on its own while the other runs on.
//
// What this proves is isolation by binding: ids, state roots and the pinned station key. It is not an OS boundary:
// on a host where both bindings run as one uid, either process can read the other's files and sockets (#95).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { type Binding, BindingStartError } from "../src/binding.ts";
import type { Obj } from "../src/records.ts";
import {
  Clock,
  FakeDaemon,
  FakeStation,
  KEY_CAEL,
  KEY_RUNE,
  KEY_SCRIBE,
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
let runeStation: FakeStation;
let scribeStation: FakeStation;
let a: Binding;
let b: Binding;
const extra: Binding[] = [];

function cfg(name: string, keyId: string, station: FakeStation, root?: string) {
  return configFor(name, dir, daemon, {
    station: { name, keyId },
    publish: { enabled: true, socket: station.path },
    ...(root !== undefined ? { stateDir: root } : {}),
  });
}

async function start(binding: Binding): Promise<Binding> {
  await binding.start();
  await waitFor(() => binding.receiver.current(), `${binding.name} to join`);
  return binding;
}

/** Everything a cross-binding attempt could disturb. */
function snapshot(binding: Binding, station: FakeStation): Obj {
  const st = JSON.parse(readFileSync(join(binding.root, "state.json"), "utf8")) as Obj;
  return {
    state: st,
    outbox: readFileSync(join(binding.root, "outbox.json"), "utf8"),
    head: binding.listen({ ...SESSION, sessionKey: "probe" }, { what: "journal", view: "digest", limit: 1 }).details.from,
    connections: binding.receiver.counts.connections,
    current: binding.receiver.current(),
    station: {
      sings: station.ops("sing").length,
      hushes: station.ops("hush").length,
      ring: JSON.stringify([...station.streams.values()].map((s) => [...s.ring.values()])),
    },
  };
}

beforeEach(async () => {
  dir = tempDir();
  clock = new Clock();
  daemon = new FakeDaemon(dir);
  await daemon.start();
  runeStation = new FakeStation(dir, "rune", KEY_RUNE, clock.now);
  scribeStation = new FakeStation(dir, "scribe", KEY_SCRIBE, clock.now);
  await runeStation.start();
  await scribeStation.start();
  bridge(runeStation, daemon);
  bridge(scribeStation, daemon);
  a = await start(makeBinding(cfg("rune", KEY_RUNE, runeStation), clock));
  b = await start(makeBinding(cfg("scribe", KEY_SCRIBE, scribeStation), clock));
});

afterEach(async () => {
  for (const x of [a, b, ...extra.splice(0)]) {
    await x.stop();
  }
  await runeStation.stop();
  await scribeStation.stop();
  await daemon.stop();
  removeDir(dir);
});

test("cross-binding read, cursor advance, mute and publish are refused, and change neither binding", async () => {
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t, text: "for both" });
  const scribeSession = { sessionKey: "agent:scribe:main", sessionId: "x-1", subagent: false };
  const runeRow = (await a.sing(SESSION, { stream: "chatter", payload: "from rune" })).details.result as Obj;
  const scribeRow = (await b.sing(scribeSession, { stream: "chatter", payload: "from scribe" })).details.result as Obj;
  assert.equal(runeRow.item, "out:rune:1");
  assert.equal(scribeRow.item, "out:scribe:1");
  await waitFor(() => a.outbox?.get("out:rune:1")?.heard_at !== null && b.outbox?.get("out:scribe:1")?.heard_at !== null, "both items heard back");
  const bRead = b.listen(scribeSession, { view: "digest" });
  const bCursor = bRead.details.next as string;
  const bMute = (b.mute(scribeSession, { station: "cael" }).details.mute as { id: string }).id;
  a.listen(SESSION, { view: "digest" });
  const beforeA = snapshot(a, runeStation);
  const beforeB = snapshot(b, scribeStation);

  const read = a.listen(SESSION, { what: "journal", since: bCursor });
  assert.equal(read.details.refused, "not_this_binding");
  const advance = a.listen(SESSION, { what: "new", since: bCursor });
  assert.equal(advance.details.refused, "not_this_binding");
  const unmute = a.mute(SESSION, { clear: bMute });
  assert.equal(unmute.details.refused, "not_this_binding");
  const hush = await a.hush(SESSION, { item: "out:scribe:1" });
  assert.equal(hush.details.refused, "not_this_binding");
  // A binding whose publish socket is the scribe's station, with rune's pinned key, cannot sing as the scribe.
  const stray = makeBinding(cfg("rune-two", KEY_RUNE, scribeStation), clock);
  extra.push(stray);
  await start(stray);
  const asScribe = (await stray.sing(SESSION, { stream: "chatter", payload: "pretending" })).details.result as Obj;
  assert.equal(asScribe.reason, "station_key_mismatch");
  // A binding started on the scribe's state root while the scribe runs is refused before it reads anything.
  const squatter = makeBinding(cfg("rune", KEY_RUNE, runeStation, b.root), clock);
  await assert.rejects(squatter.start(), (e: unknown) => e instanceof BindingStartError && e.reason === "state_locked");

  assert.deepEqual(snapshot(a, runeStation), beforeA);
  assert.deepEqual(snapshot(b, scribeStation), beforeB);
  assert.equal(scribeStation.ops("sing").length, 1);
  assert.equal(scribeStation.ops("hush").length, 0);
});

test("each binding restarts on its own: the other keeps its connection, its journal and its cursors", async () => {
  const scribeSession = { sessionKey: "agent:scribe:main", sessionId: "x-1", subagent: false };
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t });
  await waitFor(() => a.receiver.onAir(clock.t).length === 1 && b.receiver.onAir(clock.t).length === 1, "both to hear it");
  const bConnections = b.receiver.counts.connections;
  const bCheckpoint = b.listen(scribeSession, { view: "digest" }).details.next;

  await a.stop();
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 2, issued_at: clock.t });
  await waitFor(() => b.receiver.onAir(clock.t).length === 2, "the scribe to hear while the prince is down");
  a = await start(makeBinding(cfg("rune", KEY_RUNE, runeStation), clock));
  assert.equal(a.receiver.onAir(clock.t).length, 2); // from the rejoin's snapshot
  assert.equal(b.receiver.counts.connections, bConnections);
  assert.equal(b.receiver.current(), true);
  const bNew = b.listen(scribeSession, { view: "digest" });
  assert.equal(bNew.details.from, bCheckpoint);
  assert.equal((bNew.details.entries as { kind: string }[]).filter((e) => e.kind === "heard").length, 1);

  const aConnections = a.receiver.counts.connections;
  const aBefore = a.listen(SESSION, { what: "journal", view: "digest", limit: 1 }).details.from;
  await b.stop();
  // The prince's state root refuses a binding of another name, so the scribe can never come back on it.
  const wrongRoot = makeBinding(cfg("scribe", KEY_SCRIBE, scribeStation, a.root), clock);
  await assert.rejects(wrongRoot.start(), (e: unknown) => e instanceof BindingStartError && e.reason === "state_locked");
  b = await start(makeBinding(cfg("scribe", KEY_SCRIBE, scribeStation), clock));
  assert.equal(a.receiver.counts.connections, aConnections);
  assert.equal(a.listen(SESSION, { what: "journal", view: "digest", limit: 1 }).details.from, aBefore);
  assert.match(b.listen(scribeSession, { what: "journal", limit: 20 }).text, /joined run run-1 \(rejoin\)/);
});

test("a stopped binding's state root refuses a binding of another name", async () => {
  const root = b.root;
  await b.stop();
  const before = readFileSync(join(root, "state.json"), "utf8");
  const other = makeBinding(cfg("rune", KEY_RUNE, runeStation, root), clock);
  await assert.rejects(other.start(), (e: unknown) => e instanceof BindingStartError && e.reason === "foreign_state");
  assert.equal(readFileSync(join(root, "state.json"), "utf8"), before);
  b = await start(makeBinding(cfg("scribe", KEY_SCRIBE, scribeStation), clock));
});
