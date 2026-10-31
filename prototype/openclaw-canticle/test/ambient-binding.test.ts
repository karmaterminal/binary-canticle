import assert from "node:assert/strict";
import { test } from "node:test";
import { Binding } from "../src/binding.ts";
import type { EntryOutcome, HostEntry, Oc0Host } from "../src/ambient-slots.ts";
import { parseConfig } from "../src/config.ts";
import { FakeDaemon, KEY_CAEL, removeDir, tempDir, waitFor } from "./helpers.ts";

const session = "agent:main:local:task";
class Host implements Oc0Host {
  entries = new Map<string, EntryOutcome>();
  records: HostEntry[] = [];
  loseReply = false;
  async enqueue(e: HostEntry): Promise<{ accepted: true } | { accepted: false; previousOutcome?: EntryOutcome }> {
    if (e.expectedPreviousKey && this.entries.get(e.expectedPreviousKey) !== "pending")
      return { accepted: false, previousOutcome: this.entries.get(e.expectedPreviousKey) ?? "unknown" };
    if (e.expectedPreviousKey) this.entries.set(e.expectedPreviousKey, "withdrawn");
    this.records.push(e); this.entries.set(e.idempotencyKey, "pending");
    if (this.loseReply) { this.loseReply = false; throw new Error("lost reply"); }
    return { accepted: true };
  }
  async query(_session: string, id: string): Promise<EntryOutcome> { return this.entries.get(id) ?? "unknown"; }
  async withdraw(_session: string, id: string): Promise<EntryOutcome> {
    if (this.entries.get(id) === "pending") this.entries.set(id, "withdrawn");
    return this.entries.get(id) ?? "unknown";
  }
  drain(): void { const id = this.records.at(-1)?.idempotencyKey; if (id) this.entries.set(id, "consumed"); }
  pending(): number { return [...this.entries.values()].filter((v) => v === "pending").length; }
}

test("binding wires OC-0 only with both seams; restart reconciles lost reply and consumed tombstone", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), host = new Host();
  const now = Date.now();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const proof = async (key: string) => ({ sessionKey: key, exists: true, onHost: true });
  const make = (oc0Host?: Oc0Host) => new Binding({ config: cfg, root, routeProof: proof, ...(oc0Host ? { oc0Host } : {}), tickMs: 3_600_000 });
  let b: Binding | null = null;
  try {
    await daemon.start();
    b = make(); await b.start(); await waitFor(() => b!.receiver.current());
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 1, issued_at: now, ttl_ms: 120_000 });
    await waitFor(() => b!.candidates.pendingCount === 1); await b.stop(); b = null;
    assert.equal(host.records.length, 0, "route proof alone never enqueues");

    host.loseReply = true;
    b = make(host); await assert.rejects(b.start(), /lost reply/); b = null;
    assert.equal(host.records.length, 1, "restart rebuilds stored candidate");
    assert.equal(host.pending(), 1);
    b = make(host); await b.start();
    assert.equal(host.records.length, 1, "lost enqueue reply reconciles without duplicate");
    host.drain(); await b.tick(); await b.stop(); b = null;
    b = make(host); await b.start();
    assert.equal(host.records.length, 1, "consumed key remains tombstoned across restart");
    await b.stop(); b = null;
  } finally { await b?.stop(); await daemon.stop(); removeDir(root); }
});

test("retract withdraws a pending slot before rebuilding the surviving frame", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), host = new Host(), now = Date.now();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const b = new Binding({ config: cfg, root, routeProof: async (key) => ({ sessionKey: key, exists: true, onHost: true }), oc0Host: host });
  try {
    await daemon.start(); await b.start(); await waitFor(() => b.receiver.current());
    for (const seq of [1, 2]) daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq, issued_at: now, ttl_ms: 120_000 });
    await waitFor(() => host.records.some((r) => r.text.includes("item=1/1") && r.text.includes("item=1/2")));
    daemon.retract({ key_id: KEY_CAEL, stream: "lens.threat", seq: 1 });
    await waitFor(() => host.records.at(-1)?.text.includes("item=1/2") === true && host.records.at(-1)?.text.includes("item=1/1") === false);
    assert.equal(host.pending(), 1);
  } finally { await b.stop(); await daemon.stop(); removeDir(root); }
});
