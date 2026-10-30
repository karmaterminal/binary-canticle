import assert from "node:assert/strict";
import { test } from "node:test";
import { Candidates } from "../src/candidates.ts";
import { parseConfig } from "../src/config.ts";
import { heardFrameOf, type Obj } from "../src/records.ts";
import { frameFields, KEY_CAEL, removeDir, tempDir } from "./helpers.ts";

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
