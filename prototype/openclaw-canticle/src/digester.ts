/**
 * Fixture-only seam for binary-canticle#198. Nothing here reads a live OpenClaw source, invokes a model,
 * changes a station, or reuses the production outbox. It makes RFC-0003's admission/read/accept boundaries
 * executable against counted in-memory fixtures.
 */

import { createHash } from "node:crypto";

export type FixtureWindow = { fromMs: number; toMs: number };

export type FixtureSourceEntry = {
  key: string;
  actor: string;
  stream: string;
  records: string[];
  window: FixtureWindow;
  consentRef: string;
};

export type FixtureSource = {
  actor: string;
  stream: string;
  read(record: string): Promise<string>;
};

export type FixtureConsent = {
  ref: string;
  actor: string;
  stream: string;
  records: string[];
  window: FixtureWindow;
  audience: string;
  grantee: string;
  verified: boolean;
  issuerControlsSource: boolean;
  revoked: boolean;
};

export type FixtureSummons = {
  summonsId: string;
  worker: string;
  workerVersion: string;
  workerArtifact: string;
  audience: string;
  sources: FixtureSourceEntry[];
};

export type FixtureRunnerAttestation = {
  issuedBy: "runner";
  verified: boolean;
  summonsId: string;
  binding: string;
  workerArtifact: string;
};

export type FixtureWorkerResult = {
  summary: string;
  worker?: string;
  workerVersion?: string;
  workerArtifact?: string;
};

export type FixtureSlotReceipt =
  | { summonsId: string; binding: string; state: "succeeded" | "failed"; thisSend: "accepted" | "duplicate" }
  | { summonsId: string; thisSend: "conflict" };

export type FixtureDigesterResult =
  | {
      status: "failed";
      reason: "refused_admission" | "refused_read" | "revocation" | "worker_mismatch" | "refused_result";
      publication?: "published";
    }
  | { status: "succeeded"; summary: string; binding: string; publication: "published" };

export type FixtureDigesterInput = {
  summons: FixtureSummons;
  consentStore: FixtureConsentStore;
  sources: Record<string, FixtureSource>;
  attestation: FixtureRunnerAttestation | null;
  slot: FixtureTerminalSlot;
  workerResult?: FixtureWorkerResult;
  readPlan?: Array<{ sourceKey: string; record: string }>;
  beforeAccept?: () => void;
};

export class FixtureConsentStore {
  readonly #records = new Map<string, FixtureConsent>();

  constructor(consents: readonly FixtureConsent[]) {
    for (const consent of consents) {
      this.put(consent);
    }
  }

  get(ref: string): FixtureConsent | null {
    const consent = this.#records.get(ref);
    return consent ? structuredClone(consent) : null;
  }

  put(consent: FixtureConsent): void {
    this.#records.set(consent.ref, structuredClone(consent));
  }
}

export class FixtureTerminalSlot {
  readonly #slots = new Map<string, { binding: string; state: "succeeded" | "failed" }>();

  accept(summonsId: string, binding: string, state: "succeeded" | "failed"): FixtureSlotReceipt {
    const existing = this.#slots.get(summonsId);
    if (existing) {
      if (existing.binding !== binding) {
        return { summonsId, thisSend: "conflict" };
      }
      return { summonsId, binding, state: existing.state, thisSend: "duplicate" };
    }
    this.#slots.set(summonsId, { binding, state });
    return { summonsId, binding, state, thisSend: "accepted" };
  }
}

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

function canonicalJson(value: JsonValue): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) {
      throw new TypeError("binding numbers must be safe integers");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key] as JsonValue)}`).join(",")}}`;
}

function bindingProjection(value: unknown): JsonValue {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("binding input must be an object");
  }
  const object = structuredClone(value) as Record<string, unknown>;
  if ("v" in object && "event" in object && "context" in object) {
    const context = object.context;
    if (context === null || typeof context !== "object" || Array.isArray(context)) {
      throw new TypeError("binding context must be an object");
    }
    const projectedContext = { ...(context as Record<string, unknown>) };
    delete projectedContext.log_destination;
    delete projectedContext.attempt;
    return { v: object.v, event: object.event, context: projectedContext } as JsonValue;
  }
  return object as JsonValue;
}

/** RFC-0003 §5.3 fixture binding: RFC 8785 for the integer-only schema used by the acceptance vector. */
export function bindingOf(value: unknown): string {
  const bytes = canonicalJson(bindingProjection(value));
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function windowContains(outer: FixtureWindow, inner: FixtureWindow): boolean {
  return outer.fromMs <= inner.fromMs && outer.toMs >= inner.toMs;
}

function consentAllowsEntry(consent: FixtureConsent | null, summons: FixtureSummons, entry: FixtureSourceEntry): boolean {
  return Boolean(
    consent &&
      consent.ref === entry.consentRef &&
      consent.actor === entry.actor &&
      consent.stream === entry.stream &&
      consent.audience === summons.audience &&
      consent.grantee === summons.worker &&
      consent.verified &&
      consent.issuerControlsSource &&
      !consent.revoked &&
      windowContains(consent.window, entry.window) &&
      entry.records.every((record) => consent.records.includes(record)),
  );
}

function sourceAllowsEntry(source: FixtureSource | undefined, entry: FixtureSourceEntry): source is FixtureSource {
  return Boolean(source && source.actor === entry.actor && source.stream === entry.stream);
}

function admissionIsValid(input: FixtureDigesterInput): boolean {
  const identities = new Set<string>();
  const keys = new Set<string>();
  for (const entry of input.summons.sources) {
    const identity = `${entry.actor}\u0000${entry.stream}`;
    if (identities.has(identity) || keys.has(entry.key)) {
      return false;
    }
    identities.add(identity);
    keys.add(entry.key);
    if (
      !sourceAllowsEntry(input.sources[entry.key], entry) ||
      !consentAllowsEntry(input.consentStore.get(entry.consentRef), input.summons, entry)
    ) {
      return false;
    }
  }
  return input.summons.sources.length > 0;
}

function entryFor(input: FixtureDigesterInput, sourceKey: string): FixtureSourceEntry | null {
  return input.summons.sources.find((entry) => entry.key === sourceKey) ?? null;
}

function publishFailure(
  input: FixtureDigesterInput,
  binding: string,
  reason: "refused_read" | "revocation" | "worker_mismatch" | "refused_result",
): FixtureDigesterResult {
  input.slot.accept(input.summons.summonsId, binding, "failed");
  return { status: "failed", reason, publication: "published" };
}

export async function runFixtureDigester(input: FixtureDigesterInput): Promise<FixtureDigesterResult> {
  if (!admissionIsValid(input)) {
    return { status: "failed", reason: "refused_admission" };
  }

  const binding = bindingOf(input.summons);
  const readPlan =
    input.readPlan ??
    input.summons.sources.flatMap((entry) => entry.records.map((record) => ({ sourceKey: entry.key, record })));
  const readValues: string[] = [];

  for (const planned of readPlan) {
    const entry = entryFor(input, planned.sourceKey);
    const source = input.sources[planned.sourceKey];
    if (
      !entry ||
      !sourceAllowsEntry(source, entry) ||
      !entry.records.includes(planned.record) ||
      !consentAllowsEntry(input.consentStore.get(entry.consentRef), input.summons, entry)
    ) {
      return publishFailure(input, binding, "refused_read");
    }
    readValues.push(await source.read(planned.record));
  }

  input.beforeAccept?.();
  for (const entry of input.summons.sources) {
    const latest = input.consentStore.get(entry.consentRef);
    if (!latest || latest.revoked || !consentAllowsEntry(latest, input.summons, entry)) {
      return publishFailure(input, binding, latest?.revoked ? "revocation" : "refused_read");
    }
  }

  const workerResult = input.workerResult ?? { summary: readValues.join(" | ") };
  if (workerResult.worker !== undefined || workerResult.workerVersion !== undefined || workerResult.workerArtifact !== undefined) {
    return publishFailure(input, binding, "refused_result");
  }

  const attestation = input.attestation;
  if (
    !attestation ||
    attestation.issuedBy !== "runner" ||
    !attestation.verified ||
    attestation.summonsId !== input.summons.summonsId ||
    attestation.binding !== binding ||
    attestation.workerArtifact !== input.summons.workerArtifact
  ) {
    return publishFailure(input, binding, "worker_mismatch");
  }

  const receipt = input.slot.accept(input.summons.summonsId, binding, "succeeded");
  if (receipt.thisSend === "conflict") {
    return { status: "failed", reason: "refused_result" };
  }
  return { status: "succeeded", summary: workerResult.summary, binding, publication: "published" };
}
