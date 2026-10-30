import assert from "node:assert/strict";
import { test } from "node:test";
import { Candidates } from "../src/candidates.ts";
import { Binding } from "../src/binding.ts";
import { parseConfig } from "../src/config.ts";
import { heardFrameOf, type Obj } from "../src/records.ts";
import { FakeDaemon, frameFields, KEY_CAEL, removeDir, tempDir, waitFor } from "./helpers.ts";

const session = "agent:main:local:task";
const base = { binding: "rune", daemon: { socket: "/tmp/canticle.sock" } };
function config(extra: Record<string, unknown> = {}) {
  return parseConfig({ ...base, subscriptions: [{ id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"], streams: ["lens.threat"], classes: ["advisory"], scopes: ["lan"], lenses: ["42"], perHour: 1, ...extra }] });
}
function frame(now: number, seq: number) {
  const fields = frameFields({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", seq, issued_at: now, class: "advisory", ttl_ms: 120_000 });
  const f = heardFrameOf({ ...fields, lens: 42 } as Obj);
  assert.ok(f);
  return f;
}

test("subscription shape rejects wildcards, shared main, duplicate ids and wake", () => {
  for (const key of ["*", "agent:main:main", "agent:main:discord:channel:ABC", "agent:main:local:*"]) {
    assert.throws(() => config({ targets: [{ sessionKey: key }] }));
  }
  assert.throws(() => config({ delivery: "wake" }));
  assert.throws(() => config({ lenses: ["100000"] }));
  assert.throws(() => parseConfig({ ...base, subscriptions: [config().subscriptions[0], config().subscriptions[0]] }));
});

test("candidate ledger fails closed without host route proof, filters and budgets before persistence", () => {
  const root = tempDir(); const now = 1_790_000_000_000;
  try {
    const cfg = config();
    const denied = new Candidates(root, "rune", cfg.subscriptions, () => ({ canonicalKey: session, offHost: true }));
    denied.load(now);
    assert.equal(denied.accept(frame(now, 1), "run", now, false, false), 0);
    const ledger = new Candidates(root, "rune", cfg.subscriptions, (key) => ({ canonicalKey: key, offHost: false }));
    ledger.load(now);
    const f = frame(now, 1);
    assert.equal(ledger.accept(f, "run", now, false, false), 1);
    assert.equal(ledger.accept(f, "run", now, false, false), 0);
    assert.equal(ledger.accept(frame(now, 2), "run", now, false, false), 0); // per-hour budget
    assert.equal(ledger.accept({ ...frame(now, 3), dedup: "resurfaced" }, "run", now, false, false), 0); // resurfacing cannot bypass budget
    assert.equal(ledger.slots(session, now + 60_001).length, 1);
    assert.equal(ledger.slots(session, now + 60_001)[0]?.key, "canticle:digest");
    const restored = new Candidates(root, "rune", cfg.subscriptions, (key) => ({ canonicalKey: key, offHost: false }));
    restored.load(now);
    assert.equal(restored.pendingCount, 1);
    restored.retract(f.idem, now);
    assert.equal(restored.pendingCount, 0);
    assert.equal(restored.accept(f, "run", now, false, false), 0); // settled tombstone
  } finally { removeDir(root); }
});

test("logical slots stay bounded by five items and 1536 bytes; rejoin settles candidates", () => {
  const root = tempDir(); const now = 1_790_000_000_000;
  try {
    const cfg = config({ perHour: 600 });
    const ledger = new Candidates(root, "rune", cfg.subscriptions, (key) => ({ canonicalKey: key, offHost: false }));
    ledger.load(now);
    for (let i = 1; i <= 50; i++) ledger.accept(frame(now, i), "run", now, false, false);
    const slots = ledger.slots(session, now + 60_001);
    assert.equal(slots.length, 1);
    assert.equal(slots[0]?.items.length, 5);
    assert.ok(Buffer.byteLength(slots[0]?.text ?? "") <= 1536);
    ledger.rejoin("run", now);
    assert.equal(ledger.pendingCount, 0);
    assert.equal(ledger.slots(session, now).length, 0);
  } finally { removeDir(root); }
});

test("restart retains candidates, while untune, target and filter changes revoke old slots", async () => {
  const root = tempDir(); const now = 1_790_000_000_000;
  const daemon = new FakeDaemon(root);
  const proof = (key: string) => ({ canonicalKey: key, offHost: false });
  const cfg = parseConfig({ ...base, daemon: { socket: daemon.path }, subscriptions: config({ perHour: 10 }).subscriptions });
  let binding: Binding | null = null;
  try {
    await daemon.start();
    binding = new Binding({ config: cfg, root, clock: () => now, routeProof: proof, tickMs: 3_600_000 });
    await binding.start();
    await waitFor(() => binding!.receiver.current());
    assert.equal(binding.candidates.accept(frame(now, 1), daemon.run, now, false, false), 1);
    await binding.stop();
    binding = new Binding({ config: cfg, root, clock: () => now, routeProof: proof, tickMs: 3_600_000 });
    await binding.start();
    await waitFor(() => binding!.receiver.current());
    assert.equal(binding.candidates.pendingCount, 1);
    assert.equal(binding.candidates.slots(session, now + 60_001).length, 1);
    await binding.stop(); binding = null;

    let seq = 2;
    for (const change of [{ delivery: "ringbuffer_only" }, { targets: [{ sessionKey: "agent:main:local:other" }] }, { streams: ["other"] }]) {
      const ledger = new Candidates(root, "rune", config(change).subscriptions, proof);
      ledger.load(now);
      assert.equal(ledger.slots(session, now + 60_001).length, 0);
      assert.equal(ledger.pendingCount, 0);
      // Restore a fresh candidate so every change is tested against persisted state.
      const fresh = new Candidates(root, "rune", cfg.subscriptions, proof);
      fresh.load(now);
      assert.equal(fresh.accept(frame(now, seq++), daemon.run, now, false, false), 1);
    }
  } finally { await binding?.stop(); await daemon.stop(); removeDir(root); }
});

test("ambient receiver acceptance requires a local route and matching stream", () => {
  const root = tempDir(); const f = frame(1_790_000_000_000, 1);
  try {
    const subs = config({ perHour: 10 }).subscriptions;
    assert.equal(new Candidates(root, "rune", subs, () => null).acceptsAmbient(f), false);
    assert.equal(new Candidates(root, "rune", subs, () => ({ canonicalKey: session, offHost: true })).acceptsAmbient(f), false);
    assert.equal(new Candidates(root, "rune", subs, (key) => ({ canonicalKey: key, offHost: false })).acceptsAmbient(f), true);
    assert.equal(new Candidates(root, "rune", config({ streams: ["other"] }).subscriptions, (key) => ({ canonicalKey: key, offHost: false })).acceptsAmbient(f), false);
  } finally { removeDir(root); }
});
