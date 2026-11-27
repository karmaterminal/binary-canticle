/**
 * Fixture-only seam for binary-canticle#198. The executable contract lands RED before behavior is added.
 * Nothing here reads a live OpenClaw source or publishes a result.
 */

export type FixtureSource = {
  actor: string;
  stream: string;
  read(record: string): Promise<string>;
};

export type FixtureConsent = {
  ref: string;
  actor: string;
  stream: string;
  audience: string;
  grantee: string;
  valid: boolean;
  revoked: boolean;
};

export type FixtureSummons = {
  worker: string;
  audience: string;
  source: { actor: string; stream: string; records: string[]; consentRef: string };
};

export type FixtureDigesterResult =
  | { status: "failed"; reason: "refused_admission" | "refused_read" | "not_implemented" }
  | { status: "succeeded"; summary: string };

export async function runFixtureDigester(_input: {
  summons: FixtureSummons;
  consent: FixtureConsent;
  source: FixtureSource;
}): Promise<FixtureDigesterResult> {
  const { summons, consent } = _input;
  if (consent.ref !== summons.source.consentRef || consent.actor !== summons.source.actor) {
    return { status: "failed", reason: "refused_admission" };
  }
  return { status: "failed", reason: "not_implemented" };
}
