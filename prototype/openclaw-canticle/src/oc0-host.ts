import type { EntryOutcome, HostEntry, Oc0Host } from "./ambient-slots.ts";

type State = { state: EntryOutcome };
type EnqueueResult = { enqueued: boolean; reason?: string; state?: EntryOutcome };
export type Oc0Workflow = {
  enqueueNextTurnInjection: (entry: {
    sessionKey: string; expectedSessionId: string; expectedLifecycleRevision: string; text: string; idempotencyKey: string; supersedeKey: string;
    expectedSupersededKey?: string; expiresAt: number; outcomeRetainUntil: number;
    provenance: { source: string };
  }) => Promise<EnqueueResult>;
  getNextTurnInjectionState: (entry: { sessionKey: string; idempotencyKey: string; expectedSessionId: string; expectedLifecycleRevision: string }) => Promise<State>;
  withdrawNextTurnInjection: (entry: { sessionKey: string; idempotencyKey: string; expectedSessionId: string; expectedLifecycleRevision: string }) => Promise<State>;
};

/** Maps the standalone durable slot handshake to OC-0's exact workflow fields. */
export function oc0HostFromWorkflow(workflow: Oc0Workflow): Oc0Host {
  return {
    async enqueue(entry: HostEntry) {
      if (!entry.expectedSessionId || !entry.expectedLifecycleRevision) throw new Error("OC-0 requires exact session identity and lifecycle revision");
      const result = await workflow.enqueueNextTurnInjection({
        sessionKey: entry.sessionKey, expectedSessionId: entry.expectedSessionId, expectedLifecycleRevision: entry.expectedLifecycleRevision, text: entry.text, idempotencyKey: entry.idempotencyKey,
        supersedeKey: entry.supersedeKey,
        ...(entry.expectedPreviousKey ? { expectedSupersededKey: entry.expectedPreviousKey } : {}),
        expiresAt: entry.deadline, outcomeRetainUntil: entry.outcomeRetention,
        provenance: { source: entry.provenance },
      });
      return result.enqueued ? { accepted: true } : { accepted: false, ...(result.state ? { previousOutcome: result.state } : {}) };
    },
    async query(sessionKey, idempotencyKey, expectedSessionId, expectedLifecycleRevision) {
      if (!expectedSessionId || !expectedLifecycleRevision) throw new Error("OC-0 requires exact session identity and lifecycle revision");
      return (await workflow.getNextTurnInjectionState({ sessionKey, idempotencyKey, expectedSessionId, expectedLifecycleRevision })).state;
    },
    async withdraw(sessionKey, idempotencyKey, expectedSessionId, expectedLifecycleRevision) {
      if (!expectedSessionId || !expectedLifecycleRevision) throw new Error("OC-0 requires exact session identity and lifecycle revision");
      return (await workflow.withdrawNextTurnInjection({ sessionKey, idempotencyKey, expectedSessionId, expectedLifecycleRevision })).state;
    },
  };
}
