import assert from "node:assert/strict";
import { test } from "node:test";
import { AmbientSlots, type EntryOutcome, type HostEntry, type Oc0Host } from "../src/ambient-slots.ts";
import { removeDir, tempDir } from "./helpers.ts";

const now = 1_790_000_000_000, session = "agent:main:local:task";
class Host implements Oc0Host {
  entries = new Map<string, EntryOutcome>();
  async enqueue(e: HostEntry) {
    if (e.expectedPreviousKey && this.entries.get(e.expectedPreviousKey) !== "pending")
      return { accepted: false as const, previousOutcome: this.entries.get(e.expectedPreviousKey) ?? "unknown" };
    if (e.expectedPreviousKey) this.entries.set(e.expectedPreviousKey, "withdrawn");
    this.entries.set(e.idempotencyKey, "pending"); return { accepted: true as const };
  }
  async query(_s: string, id: string): Promise<EntryOutcome> { return this.entries.get(id) ?? "unknown"; }
  async withdraw(_s: string, id: string): Promise<EntryOutcome> {
    if (this.entries.get(id) === "pending") this.entries.set(id, "withdrawn");
    return this.entries.get(id) ?? "unknown";
  }
}
test("consumed predecessor in conditional supersede race never carries old frame", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host); a.load();
    const request = (keys: string[]) => ({ sessionKey: session, slot: "canticle:digest" as const,
      frames: keys.map((key) => ({ key, line: key, expiresAt: now + 120_000 })) });
    await a.sync(request(["a"]), now);
    const original = a.pending(session)[0]!;
    const originalQuery = host.query.bind(host);
    let count = 0;
    host.query = async (s, id) => {
      const result = await originalQuery(s, id);
      if (id === original.id && ++count === 1) host.entries.set(id, "consumed");
      return result;
    };
    await assert.rejects(a.sync(request(["a", "b"]), now));
    assert.equal(a.pending(session).length, 0);
    await a.sync(request(["a", "b"]), now);
    assert.equal(a.outcome("a"), true);
    assert.deepEqual(a.pending(session)[0]?.frames.map((f) => f.key), ["b"]);
  } finally { removeDir(root); }
});

test("host entry expiry settles only individually expired frame keys", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host); a.load();
    await a.sync({ sessionKey: session, slot: "canticle:digest", frames: [
      { key: "early", line: "early", expiresAt: now + 1000 },
      { key: "late", line: "late", expiresAt: now + 10_000 },
    ] }, now);
    host.entries.set(a.pending(session)[0]!.id, "expired");
    await a.reconcile(session, now + 2000);
    assert.equal(a.outcome("early"), true);
    assert.equal(a.outcome("late"), false);
  } finally { removeDir(root); }
});
