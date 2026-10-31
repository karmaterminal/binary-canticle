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
  assert.deepEqual(await host.enqueue({ sessionKey: "agent:main:local:task", idempotencyKey: "new", supersedeKey: "canticle:digest", expectedPreviousKey: "old", text: "item", deadline: 123, outcomeRetention: 456, provenance: "canticle" }), { accepted: true });
  assert.deepEqual(calls[0], { sessionKey: "agent:main:local:task", idempotencyKey: "new", supersedeKey: "canticle:digest", expectedSupersededKey: "old", text: "item", expiresAt: 123, outcomeRetainUntil: 456, provenance: { source: "canticle" } });
  assert.equal(await host.query("agent:main:local:task", "new"), "consumed");
  assert.equal(await host.withdraw("agent:main:local:task", "new"), "withdrawn");
});
