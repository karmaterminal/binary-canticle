import assert from "node:assert/strict";
import { test } from "node:test";
import { AmbientSlots, type EntryOutcome, type HostEntry, type Oc0Host, type SlotRequest } from "../src/ambient-slots.ts";
import { removeDir, tempDir } from "./helpers.ts";

const now = 1_790_000_000_000, sessionKey = "agent:main:local:task";
const req = (slot: SlotRequest["slot"], ...keys: string[]): SlotRequest => ({
  sessionKey, slot, frames: keys.map((key) => ({ key, expiresAt: now + 120_000, line: key })),
});
class Host implements Oc0Host {
  entries = new Map<string, EntryOutcome>();
  bySlot = new Map<string, string>();
  loseReply = false;
  async enqueue(e: HostEntry): Promise<{ accepted: true } | { accepted: false; previousOutcome?: EntryOutcome }> {
    if (e.expectedPreviousKey && this.entries.get(e.expectedPreviousKey) !== "pending")
      return { accepted: false, previousOutcome: this.entries.get(e.expectedPreviousKey) ?? "unknown" };
    if (e.expectedPreviousKey) this.entries.set(e.expectedPreviousKey, "withdrawn");
    this.entries.set(e.idempotencyKey, "pending"); this.bySlot.set(e.supersedeKey, e.idempotencyKey);
    if (this.loseReply) { this.loseReply = false; throw new Error("reply lost"); }
    return { accepted: true };
  }
  async query(_session: string, id: string): Promise<EntryOutcome> { return this.entries.get(id) ?? "unknown"; }
  async withdraw(_session: string, id: string): Promise<EntryOutcome> {
    if (this.entries.get(id) === "pending") this.entries.set(id, "withdrawn");
    return this.entries.get(id) ?? "unknown";
  }
  drain(slot: string): void { const id = this.bySlot.get(slot); if (id && this.entries.get(id) === "pending") this.entries.set(id, "consumed"); }
}

test("two slots stay bounded; rebuild carries keys, drain settles only its slot", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host); a.load();
    await a.sync(req("canticle:digest", "a"), now);
    await a.sync(req("canticle:alarm", "z"), now);
    await a.sync(req("canticle:digest", "a", "b"), now);
    assert.equal([...host.entries.values()].filter((x) => x === "pending").length, 2);
    assert.equal(a.outcome("a"), false);
    host.drain("canticle:digest"); await a.reconcile(sessionKey, now);
    assert.equal(a.outcome("a"), true); assert.equal(a.outcome("b"), true);
    assert.equal(a.pending(sessionKey).length, 1);
  } finally { removeDir(root); }
});

test("lost enqueue reply reconciles on restart without duplicate admission", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host); a.load(); host.loseReply = true;
    await assert.rejects(a.sync(req("canticle:digest", "a"), now));
    const b = new AmbientSlots(root, "rune", host); b.load();
    await b.reconcile(sessionKey, now); await b.sync(req("canticle:digest", "a"), now);
    assert.equal(host.entries.size, 1);
    host.drain("canticle:digest");
    const c = new AmbientSlots(root, "rune", host); c.load(); await c.reconcile(sessionKey, now);
    await c.sync(req("canticle:digest", "a"), now);
    assert.equal(host.entries.size, 1); assert.equal(c.outcome("a"), true);
  } finally { removeDir(root); }
});

test("retract withdraws first, then settles retracted key and rebuilds survivor", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host); a.load();
    await a.sync(req("canticle:digest", "a", "b"), now);
    await a.retract(sessionKey, "a", now);
    assert.equal(a.outcome("a"), true);
    await a.sync(req("canticle:digest", "a", "b"), now);
    assert.equal(host.entries.size, 2);
    assert.equal(a.pending(sessionKey)[0]?.frames.map((f) => f.key).join(), "b");
  } finally { removeDir(root); }
});
