import assert from "node:assert/strict";
import { test } from "node:test";
import { AmbientSlots, type EntryOutcome, type HostEntry, type Oc0Host } from "../src/ambient-slots.ts";
import { removeDir, tempDir } from "./helpers.ts";

const now = 1_790_000_000_000, session = "agent:main:local:task";
const proof = async (key: string) => ({ sessionKey: key, exists: true, onHost: true, sessionId: "s-1", lifecycleRevision: "r-1" });
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
    const a = new AmbientSlots(root, "rune", host, proof); a.load();
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
    const a = new AmbientSlots(root, "rune", host, proof); a.load();
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

test("delayed reset preserves a successor consumption taint", async () => {
  const root = tempDir(), host = new Host();
  try {
    const a = new AmbientSlots(root, "rune", host, proof); a.load();
    await a.sync({ sessionKey: session, slot: "canticle:digest", frames: [{ key: "successor", line: "successor", expiresAt: now + 120_000 }] }, now);
    host.entries.set(a.pending(session)[0]!.id, "consumed");
    await a.reconcile(session, now);
    assert.equal(a.isTainted(session), true);
    a.reset(session, now, false);
    const restored = new AmbientSlots(root, "rune", host, proof); restored.load();
    assert.equal(restored.isTainted(session), true);
  } finally { removeDir(root); }
});

test("generation-free host proof refuses slots and delayed old reset preserves successor taint", async () => {
  const root = tempDir(), host = new Host();
  let generation: string | undefined;
  try {
    const route = async (sessionKey: string) => ({ sessionKey, exists: true, onHost: true, sessionId: generation, lifecycleRevision: generation ? `r-${generation}` : undefined });
    const a = new AmbientSlots(root, "rune", host, route); a.load();
    const request = (key: string) => ({ sessionKey: session, slot: "canticle:digest" as const,
      frames: [{ key, line: key, expiresAt: now + 120_000 }] });
    await assert.rejects(a.sync(request("old"), now), /generation unavailable/);
    generation = "old";
    await a.sync(request("old"), now);
    a.reset(session, now, true, "old");
    generation = "new";
    await a.sync(request("new"), now);
    host.entries.set(a.pending(session)[0]!.id, "consumed");
    await a.reconcile(session, now);
    assert.equal(a.isTainted(session, "new"), true);
    a.reset(session, now, true, "old");
    a.deleteSession(session, true, "old");
    const restored = new AmbientSlots(root, "rune", host, route); restored.load();
    assert.equal(restored.isTainted(session, "new"), true);
    assert.equal(restored.isTainted(session, "old"), false);
  } finally { removeDir(root); }
});

test("same-ID reset and route change block stale OC-0 calls; another session stays isolated", async () => {
  const root = tempDir(), host = new Host(), other = "agent:main:local:other";
  const revision = new Map([[session, "before"], [other, "other-revision"]]);
  const route = async (key: string) => ({ sessionKey: key, exists: true, onHost: true, sessionId: "same", lifecycleRevision: revision.get(key) ?? null });
  try {
    const a = new AmbientSlots(root, "rune", host, route); a.load();
    const request = (key: string, item: string) => ({ sessionKey: key, slot: "canticle:digest" as const,
      frames: [{ key: item, line: item, expiresAt: now + 120_000 }] });
    await a.sync(request(session, "old"), now);
    await a.sync(request(other, "other"), now);
    revision.set(session, "after");
    await assert.rejects(a.reconcile(session, now), /another session generation/);
    await assert.rejects(a.sync(request(session, "new"), now), /another session generation/);
    await a.reconcile(other, now);
    assert.equal(a.pending(other).length, 1);
    assert.equal(a.pending(session)[0]?.lifecycleRevision, "before");
  } finally { removeDir(root); }
});

test("delayed same-ID callback cannot clear successor revision slots or taint", async () => {
  const root = tempDir(), host = new Host();
  let revision = "before";
  const route = async (key: string) => ({ sessionKey: key, exists: true, onHost: true, sessionId: "same", lifecycleRevision: revision });
  try {
    const a = new AmbientSlots(root, "rune", host, route); a.load();
    const request = (key: string) => ({ sessionKey: session, slot: "canticle:digest" as const,
      frames: [{ key, line: key, expiresAt: now + 120_000 }] });
    await a.sync(request("old"), now);
    a.reset(session, now, true, "same", "before");
    revision = "after";
    await a.sync(request("new"), now);
    host.entries.set(a.pending(session)[0]!.id, "consumed");
    await a.reconcile(session, now);
    a.reset(session, now, true, "same", "before");
    a.deleteSession(session, true, "same", "before");
    assert.equal(a.isTainted(session, "same"), true);
    assert.equal(a.outcome("new"), true);
    a.reset(session, now, true, "same");
    assert.equal(a.isTainted(session, "same"), true, "ID-only callback retains r2 taint");
    a.reset(session, now, true, "same", "after");
    assert.equal(a.isTainted(session, "same"), false, "exact r2 callback clears r2 taint");
  } finally { removeDir(root); }
});
