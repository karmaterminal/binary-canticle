# PR Review: karmaterminal/binary-canticle#184

**Verdict: REQUEST CHANGES**

## Named refs

| category | ref | local | server/tracking |
|---|---|---|---|
| product/base | PR #184; base ref `anchor/lesson-x-composed-source-20261121`; `452c54336d05048b3e0e2fd83bafb16d98065891` | exact commit present | PR base API and local commit match |
| lane/safe branch | `codeagent/bc-184-review`; `2eb1a56d8fe4f1b250d4da3adec5611292f66948` | `codeagent/bc-184-review` at `2eb1a56d8fe4f1b250d4da3adec5611292f66948` | unchanged safe lane published to `origin/codeagent/bc-184-review` |
| CI/workflow | `.github/workflows/tests.yml`; workflow SHA not exposed by the workflow run API | workflow run `45653863478` | workflow run head SHA `edc960c4f4016ebfbd219f7776f247640b153e01` |
| presentation | N/A | N/A | N/A |
| docs/proof | this `REVIEW.md` at the worktree root; pending lane commit | pending lane commit | pending origin update |

## Diff and base

PR #184 is based on the stated `452c5433` commit and has head
`edc960c4f4016ebfbd219f7776f247640b153e01`. Its diff is limited to the
derived-reply implementation, its bridge/proof documentation, and the three
related test modules. The PR CI run `45653863478` reports success for all four
jobs: `station-tests`, both OpenClaw plugin jobs, and the protocol-dynamics
harness.

## Findings

### Blocking: F3 issuer key loading bypasses the repository's Ed25519 public-key validation

**Evidence:** `prototype/canticle-station/canticle/derived_reply_proposal.py:238-240`
constructs `Ed25519PublicKey` with `from_public_bytes(issuer_public)` directly.
It checks only length, not the canonical/small-order validation implemented by
`check_public_key` in `prototype/canticle-station/canticle/ids.py:35-62`.

A deterministic probe accepted the all-zero identity/small-order encoding in
`cryptography`, while `check_public_key` rejected it as a small-order point.
This leaves a station verifier able to be configured with a public key the RFC
§9.3 verifier rule says to refuse. It can weaken the intended
issuer-verifies-only separation by making signature authenticity depend on an
unvalidated key encoding.

**Required correction:** validate `issuer_public` through `check_public_key`
before constructing `Ed25519PublicKey`; import it from `ids.py` alongside the
existing key helpers. Return a normal `Refused("authority_missing")` or a
defined key-validation refusal for invalid encodings.

### Nit: stale HMAC comment in the derived control bridge

**Evidence:** `prototype/canticle-station/canticle/derived_control.py:49-50`
still says "HMAC" even though F3 replaces the host-to-station capability
authentication with Ed25519.

The behavior is documented elsewhere, but the adjacent comment is incorrect and
could lead an operator or future maintainer to restore the wrong boundary.

## F1: heard-source scope bounds derived audience

**Invariant:** every reply audience is at least as narrow as the narrowest
heard source. A source with no recorded scope is unknown and must fail closed.

**Owner path:** `Exposure.scope` is defined and validated at
`derived_reply_proposal.py:95-116`. `begin_exposure`,
`confirm_exposure`, and `_snapshot` persist and rederive the causal ledger at
`derived_reply_proposal.py:393-433` and `454-471`. `_snapshot` stores the
narrowest scope and `_policy` checks it against the elected intent and grant at
`derived_reply_proposal.py:473-495`. Both fresh election and later claim/admit
recheck the same policy through `_check_election` at `531-540`, so replay
cannot bypass the check.

**Call-site walk:** exposure fences are written before payload delivery;
confirmation persists the canonical exposure record including `scope`; pending
entries make the history unknown; withdrawal and expiry invalidate future use;
and `_snapshot` rejects stale/active-missing sources. An election freezes the
scope-bearing snapshot, and `_check_election` requires the current snapshot to
equal the frozen one. This covers restart, replay, missing parent/history,
unknown scope, withdrawal, and ledger changes.

**Red/green:** on the post-fix head, the three focused F1 tests pass in the
47-test reply module. After removing only the F1 implementation diff, the
new F1 tests fail with `unexpected scope` because `Exposure` and `_snapshot`
have no scope field/check. Thus the tests do not pass on the rejected F1
implementation.

## F2: persisted grant intersection survives restart

**Invariant:** a persisted narrowing remains effective after every restart.
Widening requires a trusted explicit `replace_grant`; constructor reopen
cannot erase a persisted intersection.

**Owner path:** `narrower_grant` requires identity equality and intersects
authors, audiences, scope, and bounds at
`derived_reply_proposal.py:202-211`. Constructor reopen atomically reads and
intersects the existing and supplied grants at `278-290`, and writes the
effective grant before other operations. `_policy` always reads the
persisted grant at `473-495`, while `replace_grant` is the explicit trusted
widening/revision path at `357-360`.

**Call-site walk:** fresh election and claim/admission both call `_policy`,
after `_check_election` restores the same grant database. Restart cannot widen
the stored grant because the constructor uses `narrower_grant`; retry and replay
also re-enter `_policy`. The explicit `replace_grant` test restores a wider
grant only as a trusted owner operation.

**Red/green:** on the post-fix head, the 47-test reply module passes. Reversing
only the F2 implementation diff makes the three F2 controls fail: a narrower
constructor is accepted without its `max_bytes` bound, a disjoint author/audience
set remains usable, and identity-changing reopen returns instead of refusing.
The sticky stored grant assertion also shows `authors=['cael']` instead of
`authors=[]` after the old wider config reopens.

## F3: issuer signs; station verifies only

**Invariant:** only an instance holding the matching Ed25519 private key can
mint a capability capsule. Every station/bridge admission path verifies the
issuer public signature and never has a station fallback to mint.

**Owner path:** `ReplyProposal` separates `issuer_key` and `issuer_public`
at `derived_reply_proposal.py:221-240`. `claim` refuses a verify-only instance
and signs with the private key at `548-574`. `station_admit` accepts only an
Ed25519 signature over the canonical envelope at `584-614`.
`DerivedStationProposal.publish` only calls `station_admit`, then
`Station._accept_derived_proposal` signs the actual station frame with the
station key; it cannot mint the issuer capability
(`derived_station_proposal.py:30-39`, `41-78`). There is no alternate HMAC or
station-private-key capability mint path found in this PR diff.

**Call-site walk:** claim is the sole capability-mint path. It rejects first
when `issuer_key` is absent. Both station-admission and control-bridge publish
go through `station_admit` or `publish`; neither accepts an issuer key as model
input. Replay, restart, and claimed/unknown states recheck the ledger and
signature. The new tests cover verify-only mint refusal, wrong-key forgery,
key mismatch, wrong station, and station publication without mint.

**Red/green:** on the post-fix head, 47 reply tests and 17 station tests pass,
including the F3 controls, and the 10 derived-control tests pass. Reversing only
the F3 implementation leaves the new F3 tests unable to construct
`ReplyProposal(issuer_key=...)` and errors at setup, demonstrating that the
pre-fix constructor and HMAC implementation do not satisfy the asymmetric
boundary.

## Default-enabled check

No station or derived-proposal path is enabled by default. `ReplyProposal`
defaults `enabled=False` and creates no state/key/process
(`derived_reply_proposal.py:221-232`). `DerivedStationProposal` also defaults
`enabled=False` and `publish` refuses unless both proposal and station gates
are enabled (`derived_station_proposal.py:27-39`). The bridge and tests require
explicit fixture enablement. No multicast or live daemon configuration is added
by this PR.
