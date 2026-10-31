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

test("binding wires OC-0 only with both seams; restart does not admit stale candidate before landing", async () => {
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

    b = make(host); await b.start();
    await waitFor(() => b!.receiver.current());
    assert.equal(host.records.length, 0, "a rejoined run cancels old candidates before rebuilding");
    await b.stop(); b = null;
  } finally { await b?.stop(); await daemon.stop(); removeDir(root); }
});

test("drained frame retracted while binding runs queues one metadata-only digest note", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), host = new Host(), now = Date.now();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const b = new Binding({ config: cfg, root, routeProof: async (key) => ({ sessionKey: key, exists: true, onHost: true }), oc0Host: host });
  try {
    await daemon.start(); await b.start(); await waitFor(() => b.receiver.current());
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 7, issued_at: now, ttl_ms: 120_000 });
    await waitFor(() => host.records.length === 1);
    host.drain(); await b.tick();
    await waitFor(() => b.isTainted({ sessionKey: session, sessionId: null, subagent: false, anonymous: false }));
    daemon.retract({ key_id: KEY_CAEL, stream: "lens.threat", seq: 7 });
    await waitFor(() => host.records.some((r) => r.text.includes("[canticle:withdrawn/expired]")));
    const note = host.records.at(-1)!;
    assert.equal(note.supersedeKey, "canticle:digest");
    assert.equal(note.text.split("\n").length, 1);
    assert.doesNotMatch(note.text, /item=1\/7/, "note does not re-expose the consumed payload");
  } finally { await b.stop(); await daemon.stop(); removeDir(root); }
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

test("landing MUTE and regulatory change withdraw pending host entry; clear state only admits new frames", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), host = new Host(), now = Date.now();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const b = new Binding({ config: cfg, root, routeProof: async (key) => ({ sessionKey: key, exists: true, onHost: true }), oc0Host: host });
  try {
    await daemon.start(); await b.start(); await waitFor(() => b.receiver.current());
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 21, issued_at: now, ttl_ms: 120_000 });
    await waitFor(() => host.pending() === 1);
    daemon.emit("landing_state", { mute: { until: null, by: "test" }, breaker: "closed", until: null, modulation: [] });
    await waitFor(() => host.pending() === 0);
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 22, issued_at: now, ttl_ms: 120_000 });
    await new Promise((resolve) => setTimeout(resolve, 20));
    assert.equal(b.candidates.pendingCount, 0);
    assert.equal(host.pending(), 0);
    daemon.emit("landing_state", { mute: null, breaker: "closed", until: null, modulation: [{ stream: "lens.threat", op: "tighten", delta_theta: 0.5 }] });
    await b.tick();
    assert.equal(host.pending(), 0, "unknown modulation must fail closed, not use stale baseline");
    daemon.emit("landing_state", { mute: null, breaker: "closed", until: null, modulation: [] });
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 23, issued_at: now, ttl_ms: 120_000 });
    await waitFor(() => host.pending() === 1);
    assert.equal(host.records.at(-1)?.text.includes("item=1/21"), false);
  } finally { await b.stop(); await daemon.stop(); removeDir(root); }
});

test("landing MUTE racing an in-flight host enqueue withdraws its accepted entry", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), now = Date.now();
  let release: (() => void) | undefined;
  let entered: (() => void) | undefined;
  const began = new Promise<void>((resolve) => { entered = resolve; });
  const gate = new Promise<void>((resolve) => { release = resolve; });
  class SlowHost extends Host {
    override async enqueue(e: HostEntry): Promise<{ accepted: true }> {
      entered?.(); await gate;
      return await super.enqueue(e) as { accepted: true };
    }
  }
  const host = new SlowHost();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const b = new Binding({ config: cfg, root, routeProof: async (key) => ({ sessionKey: key, exists: true, onHost: true }), oc0Host: host });
  try {
    await daemon.start(); await b.start(); await waitFor(() => b.receiver.current());
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 31, issued_at: now, ttl_ms: 120_000 });
    await began;
    daemon.emit("landing_state", { mute: { until: null, by: "test" }, breaker: "closed", until: null, modulation: [] });
    await waitFor(() => typeof b.receiver.status().landing?.mute === "object" && b.receiver.status().landing?.mute !== null);
    release?.();
    await waitFor(() => host.records.length === 1 && host.pending() === 0);
  } finally { release?.(); await b.stop(); await daemon.stop(); removeDir(root); }
});

test("breaker change racing an in-flight enqueue withdraws the old entry before rebuilding", async () => {
  const root = tempDir(), daemon = new FakeDaemon(root), now = Date.now();
  let release: (() => void) | undefined;
  let entered: (() => void) | undefined;
  const began = new Promise<void>((resolve) => { entered = resolve; });
  const gate = new Promise<void>((resolve) => { release = resolve; });
  class SlowHost extends Host {
    override async enqueue(e: HostEntry): Promise<{ accepted: true }> {
      if (this.records.length === 0) { entered?.(); await gate; }
      return await super.enqueue(e) as { accepted: true };
    }
  }
  const host = new SlowHost();
  const cfg = parseConfig({ binding: "rune", daemon: { socket: daemon.path }, subscriptions: [{
    id: "fleet", targets: [{ sessionKey: session }], delivery: "ambient", stations: ["cael"],
    streams: ["lens.threat"], classes: ["live-state"], perHour: 10,
  }] });
  const b = new Binding({ config: cfg, root, routeProof: async (key) => ({ sessionKey: key, exists: true, onHost: true }), oc0Host: host });
  try {
    await daemon.start(); await b.start(); await waitFor(() => b.receiver.current());
    daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "lens.threat", class: "live-state", seq: 41, issued_at: now, ttl_ms: 120_000 });
    await began;
    daemon.emit("landing_state", { mute: null, breaker: "open", until: now + 60_000, modulation: [] });
    await waitFor(() => b.receiver.status().landing?.breaker === "open");
    release?.();
    await waitFor(() => host.records.length >= 2 && host.pending() === 1);
    assert.equal(host.entries.get(host.records[0]!.idempotencyKey), "withdrawn");
  } finally { release?.(); await b.stop(); await daemon.stop(); removeDir(root); }
});
