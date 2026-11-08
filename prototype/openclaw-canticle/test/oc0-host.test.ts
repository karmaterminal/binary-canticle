import assert from "node:assert/strict";
import { test } from "node:test";
import { oc0HostFromWorkflow, type Oc0Workflow } from "../src/oc0-host.ts";

test("OC-0 adapter maps absolute deadline, conditional predecessor and settled state", async () => {
  const calls: unknown[] = [];
  const workflow: Oc0Workflow = {
    async enqueueNextTurnInjection(entry) { calls.push(entry); return { enqueued: true }; },
    async getNextTurnInjectionState(entry) { calls.push(entry); return { state: "consumed" }; },
    async withdrawNextTurnInjection(entry) { calls.push(entry); return { state: "withdrawn" }; },
  };
  const host = oc0HostFromWorkflow(workflow);
  assert.deepEqual(await host.enqueue({ sessionKey: "agent:main:local:task", expectedSessionId: "s-1", expectedLifecycleRevision: "r-1", idempotencyKey: "new", supersedeKey: "canticle:digest", expectedPreviousKey: "old", text: "item", deadline: 123, outcomeRetention: 456, provenance: "canticle" }), { accepted: true });
  assert.deepEqual(calls[0], { sessionKey: "agent:main:local:task", expectedSessionId: "s-1", expectedLifecycleRevision: "r-1", idempotencyKey: "new", supersedeKey: "canticle:digest", expectedSupersededKey: "old", text: "item", expiresAt: 123, outcomeRetainUntil: 456, provenance: { source: "canticle" } });
  assert.equal(await host.query("agent:main:local:task", "new", "s-1", "r-1"), "consumed");
  assert.equal(await host.withdraw("agent:main:local:task", "new", "s-1", "r-1"), "withdrawn");
});


test("OC-0 adapter fails closed on missing session revision", async () => {
  let calls = 0;
  const host = oc0HostFromWorkflow({
    async enqueueNextTurnInjection() { calls++; return { enqueued: true }; },
    async getNextTurnInjectionState() { calls++; return { state: "pending" }; },
    async withdrawNextTurnInjection() { calls++; return { state: "pending" }; },
  });
  await assert.rejects(host.enqueue({ sessionKey: "agent:main:local:task", expectedSessionId: "s-1", expectedLifecycleRevision: "", idempotencyKey: "new", supersedeKey: "canticle:digest", text: "item", deadline: 123, outcomeRetention: 456, provenance: "canticle" }));
  await assert.rejects(host.query("agent:main:local:task", "new", "s-1", ""));
  await assert.rejects(host.withdraw("agent:main:local:task", "new", "s-1", ""));
  assert.equal(calls, 0);
});
