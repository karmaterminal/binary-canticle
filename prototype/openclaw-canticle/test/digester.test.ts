// binary-canticle#198, RFC-0003 PR #199 head 4e9dfaf: fixture-only digester acceptance.

import assert from "node:assert/strict";
import { test } from "node:test";
import {
  runFixtureDigester,
  type FixtureConsent,
  type FixtureSource,
  type FixtureSummons,
} from "../src/digester.ts";

class CountedSource implements FixtureSource {
  readonly actor = "fixture-actor-a";
  readonly stream = "fixture:activity";
  reads = 0;

  async read(record: string): Promise<string> {
    this.reads += 1;
    return `fixture:${record}`;
  }
}

const summons: FixtureSummons = {
  worker: "fixture-digester",
  audience: "fixture-room",
  source: {
    actor: "fixture-actor-a",
    stream: "fixture:activity",
    records: ["rec-a-0001"],
    consentRef: "auth:fixture-other-actor",
  },
};

const otherActorConsent: FixtureConsent = {
  ref: "auth:fixture-other-actor",
  actor: "fixture-actor-b",
  stream: "fixture:activity",
  audience: "fixture-room",
  grantee: "fixture-digester",
  valid: true,
  revoked: false,
};

test("RFC-0003 case 8 i: another actor's valid consent is refused before a source read", async () => {
  const source = new CountedSource();
  const result = await runFixtureDigester({ summons, consent: otherActorConsent, source });

  assert.deepEqual(result, { status: "failed", reason: "refused_admission" });
  assert.equal(source.reads, 0);
});
