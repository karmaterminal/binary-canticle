# Independent review: #146 proposed Station effect boundary

Reviewed 21 November 2026 by the independent reader-proof agent, at root's request.

**Reviewed local commit:** `0763af51151509560889db1264888779f235c7cf` in
`work/canticle-reply-capability`, with a clean worktree at inspection. This is the local source commit;
the GitHub publication commit may differ while preserving these source blobs.

## Disposition

**No blocking defect found within the documented default-closed, unregistered, single-Station-owner
library scope.** The code is reviewable as a candidate implementation contribution. This is not adoption
of the capability representation, a live-host receipt, a continuing-prince encounter, or readiness to
enable the lesson's communal exchange.

This review concentrated on `derived_station_proposal.py`, its actual mutation method in `station.py`,
the changed capability/full-key/budget code in `derived_reply_proposal.py`, and the new effect tests.
It also checked the proposal/README statements against those sources.

## Verified boundaries

| Concern | Result and reason |
| --- | --- |
| One effect under competing claims | Public `publish` first consumes the authenticated claim in SQLite, committing `admitted_unknown` plus the station-effect `claimed_unknown` row. A subsequent public call cannot obtain another admission. The shared Station lock serializes competing candidate calls. The eight-attempt test produces one accepted item and seven `claim_consumed` refusals. |
| Failure before mutation | A failure after durable admission but before `_apply_claim` leaves a queryable unknown claim. Reconstructing the adapter/station does not resend it. This may lose an intended item; the documentation accurately treats that as unknown, not delivered. |
| Failure after mutation | The receipt/outcome transaction can roll back while the in-memory carousel retains the item. The earlier durable claim remains consumed, so normal recovery is query-only and cannot enqueue a duplicate. The existing receipt-SQL trigger test and the independent COMMIT-failure probe below both establish this. |
| Lost returned acceptance | Once the acceptance transaction commits, `query` returns the same receipt after constructing a fresh adapter. It never restores the old carousel or infers current air/recipient exposure. |
| Full signer pin | Intent and grant bind a 32-byte public key and its matching key ID. Station admission checks the actual signer; the final private mutation independently checks the actual full key and current manifest. The test deliberately preserves the old 64-bit key ID while swapping the secret key between claim and effect, and receives `NotGranted` with no sequence allocation. |
| Current authority | `_apply_claim` reacquires the same SQLite writer lock used by generation/history/policy changes, rechecks the exact election, and rechecks current budgets. Withdrawal, concurrent exposure, recipient replacement, manifest revocation, tightened turn/hour limits and elapsed deadlines are covered before the actual mutation. |
| Exact lineage | The signed frame carries maximum hop from the complete heard history, the last four parent identities, their first root and conservative wake provenance. The elected displayed parent is not allowed to erase a different higher-hop source. Ordinary `Station.sing` is patched to throw in the successful effect test, proving this path does not fall through to it. |
| Distinct outcomes | Acceptance is explicitly signed-and-queued. The real Listener sees the exact published bytes, but the adapter does not synthesize host or exact-session exposure receipts from that event. The acceptance identifies the reader generation, immutable history digest/count, cited exposure, elected payload digest, full signer, frame digest and epoch/sequence. |
| Default closed | Both adapter `enabled=True` and Station `derived_proposals=True` are necessary. Normal runner/CLI/socket startup does not set the flag or import/register the adapter. A disabled call does not consume the pending claim. No new wire schema is introduced. |

## Tests actually run

From the reviewed worktree:

```sh
PYTHONPATH=prototype/canticle-station python -m unittest discover \
  -s prototype/canticle-station/tests -p 'test_derived_*proposal.py' -v
```

**53 tests passed, zero skips**, in 0.656 seconds of reported test time. The run included
`test_loopback_udp_reaches_signature_verifying_listener`; the loopback UDP proof ran and passed in this
environment rather than being skipped. These are synthetic local fixtures, not a fleet or model test.

### Independent post-effect COMMIT-failure probe

The existing test injects a trigger failure on the receipt UPDATE. To independently examine the later
durability boundary, I used a temporary `sqlite3.Connection` subclass that throws once from `commit()`
after the **actual** `_accept_derived_proposal` has returned. The receipt UPDATE and outcome INSERT run,
then the commit fault makes `_tx` roll them back. No repository source was modified for this probe.

Observed and asserted:

1. Actual Station `poll` has exactly one ITEM.
2. A newly constructed proposal/adapter queries `claimed_unknown` with `acceptance: null`.
3. The durable outcome table contains no fabricated station-acceptance receipt.
4. Reusing the capsule through public `publish` refuses `claim_consumed`.

Result: **PASS**. This is consistent with the stated at-most-one-attempt contract even when the effect
and durable receipt cannot be committed atomically. It does not establish guaranteed delivery.

## Limits retained, not additional lesson gates

- The adapter assumes one legitimate Station owner serializes ordinary `sing`, polling, key/manifest
  changes and candidate effects. Its candidate lock is not a replacement for station process/lease
  ownership. The docs state this explicitly; cross-process capability IPC/provisioning remains absent.
- The authority database and admitted exposure receipts are synthetic trusted-host inputs. The actual
  OpenClaw/frond-ear ledger, admitted invocation, parent inheritance and egress controls remain unproved.
- The conservative all-history-fresh and all-chatter eligibility rules remain candidate policy choices.
  This review does not promote them into RFC requirements or declare them suitable for four hours of play.
- No call to a live prince, continuing session, Discord route, installed station, or fleet key was made.
- No deployment, merge, policy adoption or publication was performed by this review.

Full CI should still run on the published commit, including the normal station and plugin suites. The
focused result above must not be represented as the full repository suite.
