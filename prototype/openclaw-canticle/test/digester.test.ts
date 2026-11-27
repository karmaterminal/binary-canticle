// binary-canticle#198, RFC-0003 PR #199 head 4e9dfaf: fixture-only digester acceptance.

import assert from "node:assert/strict";
import { test } from "node:test";
import {
  FixtureConsentStore,
  FixtureTerminalSlot,
  bindingOf,
  runFixtureDigester,
  type FixtureConsent,
  type FixtureDigesterInput,
  type FixtureRunnerAttestation,
  type FixtureSource,
  type FixtureSourceEntry,
  type FixtureSummons,
} from "../src/digester.ts";

class CountedSource implements FixtureSource {
  readonly actor: string;
  readonly stream: string;
  reads: string[] = [];
  private readonly afterRead: ((record: string) => void) | undefined;

  constructor(
    actor: string,
    stream: string,
    afterRead?: (record: string) => void,
  ) {
    this.actor = actor;
    this.stream = stream;
    this.afterRead = afterRead;
  }

  async read(record: string): Promise<string> {
    this.reads.push(record);
    this.afterRead?.(record);
    return `fixture:${record}`;
  }
}

const sourceA: FixtureSourceEntry = {
  key: "src-a",
  actor: "fixture-actor-a",
  stream: "fixture:activity",
  records: ["rec-a-0001", "rec-a-0002"],
  window: { fromMs: 1_764_200_000_000, toMs: 1_764_203_600_000 },
  consentRef: "auth:fixture-actor-a",
};

const summons: FixtureSummons = {
  summonsId: "smn-fx-0001",
  worker: "fixture-digester",
  workerVersion: "0.0.0-fixture",
  workerArtifact: "sha256:fixture-digester-0.0.0-fixture",
  audience: "fixture-room",
  sources: [sourceA],
};

function consent(overrides: Partial<FixtureConsent> = {}): FixtureConsent {
  return {
    ref: "auth:fixture-actor-a",
    actor: "fixture-actor-a",
    stream: "fixture:activity",
    records: ["rec-a-0001", "rec-a-0002"],
    window: { fromMs: 1_764_200_000_000, toMs: 1_764_203_600_000 },
    audience: "fixture-room",
    grantee: "fixture-digester",
    verified: true,
    issuerControlsSource: true,
    revoked: false,
    ...overrides,
  };
}

function attestation(overrides: Partial<FixtureRunnerAttestation> = {}): FixtureRunnerAttestation {
  return {
    issuedBy: "runner",
    verified: true,
    summonsId: summons.summonsId,
    binding: bindingOf(summons),
    workerArtifact: summons.workerArtifact,
    ...overrides,
  };
}

function harness(overrides: {
  summons?: FixtureSummons;
  consents?: FixtureConsent[];
  sources?: Record<string, FixtureSource>;
  attestation?: FixtureRunnerAttestation | null;
  slot?: FixtureTerminalSlot;
  beforeAccept?: () => void;
} = {}): { input: FixtureDigesterInput; sources: Record<string, FixtureSource> } {
  const selectedSummons = overrides.summons ?? summons;
  const selectedConsents = overrides.consents ?? [consent()];
  const selectedSources = overrides.sources ?? {
    "src-a": new CountedSource("fixture-actor-a", "fixture:activity"),
  };
  const input: FixtureDigesterInput = {
      summons: selectedSummons,
      consentStore: new FixtureConsentStore(selectedConsents),
      sources: selectedSources,
      attestation: overrides.attestation === undefined ? attestation() : overrides.attestation,
      slot: overrides.slot ?? new FixtureTerminalSlot(),
      ...(overrides.beforeAccept ? { beforeAccept: overrides.beforeAccept } : {}),
  };
  return { input, sources: selectedSources };
}

test("8 i: another actor's valid consent is refused before a source read", async () => {
  const h = harness({ consents: [consent({ actor: "fixture-actor-b" })] });
  const result = await runFixtureDigester(h.input);
  assert.deepEqual(result, { status: "failed", reason: "refused_admission" });
  assert.deepEqual((h.sources["src-a"] as CountedSource).reads, []);
});

test("8 ii: another stream or a narrower record scope is refused before reading it", async () => {
  for (const bad of [
    consent({ stream: "fixture:other" }),
    consent({ records: ["rec-a-0001"] }),
  ]) {
    const h = harness({ consents: [bad] });
    assert.deepEqual(await runFixtureDigester(h.input), { status: "failed", reason: "refused_admission" });
    assert.deepEqual((h.sources["src-a"] as CountedSource).reads, []);
  }
});

test("8 iii-iv: audience and grantee are admission checks", async () => {
  for (const bad of [
    consent({ audience: "fixture-private-room" }),
    consent({ grantee: "fixture-other-worker" }),
  ]) {
    const h = harness({ consents: [bad] });
    assert.deepEqual(await runFixtureDigester(h.input), { status: "failed", reason: "refused_admission" });
    assert.deepEqual((h.sources["src-a"] as CountedSource).reads, []);
  }
});

test("8 v: forged, altered, or unauthorized consent is refused at admission", async () => {
  for (const bad of [
    consent({ verified: false }),
    consent({ issuerControlsSource: false }),
  ]) {
    const h = harness({ consents: [bad] });
    assert.deepEqual(await runFixtureDigester(h.input), { status: "failed", reason: "refused_admission" });
    assert.deepEqual((h.sources["src-a"] as CountedSource).reads, []);
  }
});

test("8 vi: replacement after one read refuses the next read and sings a failure", async () => {
  const store = new FixtureConsentStore([consent()]);
  const source = new CountedSource("fixture-actor-a", "fixture:activity", () => {
    store.put(consent({ stream: "fixture:other" }));
  });
  const result = await runFixtureDigester({
    summons,
    consentStore: store,
    sources: { "src-a": source },
    attestation: attestation(),
    slot: new FixtureTerminalSlot(),
  });
  assert.deepEqual(result, { status: "failed", reason: "refused_read", publication: "published" });
  assert.deepEqual(source.reads, ["rec-a-0001"]);
});

test("9 i: revocation after the last read fills failure at accept and withholds success", async () => {
  const store = new FixtureConsentStore([consent()]);
  const source = new CountedSource("fixture-actor-a", "fixture:activity");
  const result = await runFixtureDigester({
    summons,
    consentStore: store,
    sources: { "src-a": source },
    attestation: attestation(),
    slot: new FixtureTerminalSlot(),
    beforeAccept: () => store.put(consent({ revoked: true })),
  });
  assert.deepEqual(result, { status: "failed", reason: "revocation", publication: "published" });
  assert.deepEqual(source.reads, sourceA.records);
});

test("10 i-iii: only a verified runner attestation for this artifact, summons and binding qualifies", async () => {
  const wrong = [
    attestation({ workerArtifact: "sha256:other-artifact" }),
    attestation({ verified: false }),
    attestation({ summonsId: "smn-fx-other" }),
    attestation({ binding: "sha256:other-binding" }),
    null,
  ];
  for (const candidate of wrong) {
    const h = harness({ attestation: candidate });
    assert.deepEqual(await runFixtureDigester(h.input), {
      status: "failed",
      reason: "worker_mismatch",
      publication: "published",
    });
  }
});

test("10 iv: worker-written identity fields are refused rather than stamped", async () => {
  const h = harness();
  h.input.workerResult = { summary: "fixture summary", worker: summons.worker };
  assert.deepEqual(await runFixtureDigester(h.input), {
    status: "failed",
    reason: "refused_result",
    publication: "published",
  });
});

test("11 i-ii: RFC 8785 projection matches Vector 1 and ignores only attempt-local fields", () => {
  const vector = {
    v: 1,
    event: {
      v: 1,
      kind: "digest.window",
      refs: {
        sources: [{
          key: "src-a", actor: "fixture-actor-a", stream: "fixture:activity",
          records: ["rec-a-0001", "rec-a-0002"],
          window: { from_ms: 1764200000000, to_ms: 1764203600000 },
          consent_ref: "auth:fixture-actor-a",
        }],
      },
    },
    context: {
      log_destination: "fixture://logs/smn-fx-0001",
      attempt: 1,
      summons_id: "smn-fx-0001",
      causality: { election: "mark:fixture-quiet", chain: [["mark:fixture-quiet", "smn-fx-0001"]], hop: 1 },
      deadline_ms: 1764204500000,
      invoker: { kind: "mark", rule: "mark:fixture-quiet", owner: "fixture-prince" },
      worker: "fixture-digester",
      worker_version: "0.0.0-fixture",
      worker_artifact: "sha256:fixture-digester-0.0.0-fixture",
      budget: { tokens: 20000, wall_s: 240, result_bytes: 800 },
      retry: { max_attempts: 3, backoff_base_ms: 30000 },
      audience: "fixture-room",
      aspect: "summary.plain",
    },
  };
  const first = bindingOf(vector);
  assert.equal(first, "sha256:88cdc08ee07bc70d0885a726addba1cd40c6abad2ed3a7835cbe17885b067fd9");
  const retry = structuredClone(vector);
  retry.context.log_destination = "fixture://logs/retry";
  retry.context.attempt = 2;
  assert.equal(bindingOf(retry), first);
});

test("11 iii: changed admitted fields conflict instead of inheriting the first receipt", () => {
  const slot = new FixtureTerminalSlot();
  const firstBinding = bindingOf(summons);
  assert.equal(slot.accept(summons.summonsId, firstBinding, "succeeded").thisSend, "accepted");
  assert.equal(slot.accept(summons.summonsId, firstBinding, "succeeded").thisSend, "duplicate");
  const changed = { ...summons, audience: "fixture-other-room" };
  assert.deepEqual(slot.accept(summons.summonsId, bindingOf(changed), "succeeded"), {
    summonsId: summons.summonsId,
    thisSend: "conflict",
  });
});

test("12 i-ii: each source uses its own consent; missing or crossed references read neither", async () => {
  const sourceB: FixtureSourceEntry = {
    key: "src-b",
    actor: "fixture-actor-b",
    stream: "fixture:activity",
    records: ["rec-b-0001"],
    window: sourceA.window,
    consentRef: "auth:fixture-actor-b",
  };
  const two = { ...summons, sources: [sourceA, sourceB] };
  const consentB = consent({
    ref: "auth:fixture-actor-b",
    actor: "fixture-actor-b",
    records: ["rec-b-0001"],
  });
  const a = new CountedSource(sourceA.actor, sourceA.stream);
  const b = new CountedSource(sourceB.actor, sourceB.stream);
  const ok = harness({
    summons: two,
    consents: [consent(), consentB],
    sources: { "src-a": a, "src-b": b },
    attestation: attestation({ summonsId: two.summonsId, binding: bindingOf(two) }),
  });
  assert.equal((await runFixtureDigester(ok.input)).status, "succeeded");
  assert.deepEqual(a.reads, sourceA.records);
  assert.deepEqual(b.reads, sourceB.records);

  const crossed = { ...two, sources: [{ ...sourceA, consentRef: sourceB.consentRef }, sourceB] };
  const refused = harness({
    summons: crossed,
    consents: [consent(), consentB],
    sources: {
      "src-a": new CountedSource(sourceA.actor, sourceA.stream),
      "src-b": new CountedSource(sourceB.actor, sourceB.stream),
    },
    attestation: attestation({ summonsId: crossed.summonsId, binding: bindingOf(crossed) }),
  });
  assert.deepEqual(await runFixtureDigester(refused.input), { status: "failed", reason: "refused_admission" });
  assert.deepEqual((refused.sources["src-a"] as CountedSource).reads, []);
  assert.deepEqual((refused.sources["src-b"] as CountedSource).reads, []);
});

test("12 iii-iv: out-of-entry reads fail, and duplicate actor/stream entries are ambiguous", async () => {
  const ambiguous = { ...summons, sources: [sourceA, { ...sourceA, key: "src-a-duplicate" }] };
  const refused = harness({
    summons: ambiguous,
    sources: {
      "src-a": new CountedSource(sourceA.actor, sourceA.stream),
      "src-a-duplicate": new CountedSource(sourceA.actor, sourceA.stream),
    },
    attestation: attestation({ summonsId: ambiguous.summonsId, binding: bindingOf(ambiguous) }),
  });
  assert.deepEqual(await runFixtureDigester(refused.input), { status: "failed", reason: "refused_admission" });

  const h = harness({
    sources: { "src-a": new CountedSource(sourceA.actor, sourceA.stream) },
  });
  h.input.readPlan = [{ sourceKey: "src-a", record: "not-in-entry" }];
  assert.deepEqual(await runFixtureDigester(h.input), {
    status: "failed",
    reason: "refused_read",
    publication: "published",
  });
  assert.deepEqual((h.sources["src-a"] as CountedSource).reads, []);
});
