# Independent recheck: inert #146 reply capability proposal

Reviewed 2026-11-21 at local commit `38fd133d38cacbfc98095ab6ea336fc1fb17e3df`, against BC base `08c11127d4e11ed00f307a7006d85581c8674a28`.

Reviewer: `/root/recover_reply_capability/reply_capability_recheck`.

Scope: the proposed library's declared metadata/permission contract, including complete exposure history, election binding, serialized claim/admission, generation retirement, cancellation and absolute deadlines. No source edits or live host/station operations were performed. The absence of production registration is explicitly documented and is not itself a finding.

## Findings

### P2 — A withdrawal during the pending exposure phase has nowhere durable to land

`begin_exposure` durably creates a pending row, but `withdraw_or_mute` only updates the confirmed `exposures` table (`derived_reply_proposal.py`, lines 315–353 and 362–368 at the reviewed head). If withdrawal arrives after payload handoff but before confirmation, the call refuses with `receipt_missing`. Later `confirm_exposure` inserts the receipt with the schema default `active=1`; the source can then support an election and admission.

The refusal is not falsely reported as successful withdrawal. The defect is that the new two-phase contract does not offer a durable way to record this valid ordering. A real adapter would have to invent an external pending-revocation queue, or avoid confirming an actual exposure and remain permanently uncertain. The proposal currently states that withdrawal/mute prevents future use while retaining causality without identifying this exception.

Reproduced with the existing test fixture and temporary SQLite DB:

```python
fence = broker.begin_exposure(reader, source)
broker.withdraw_or_mute(reader, source.receipt_id)  # Refused: receipt_missing
broker.confirm_exposure(reader, fence)
eid = elect()
admission = admit(broker.claim(eid, body))          # admitted_unknown
```

Observed output:

```text
withdraw_after_handoff_before_confirm: receipt_missing
post_withdraw_attempt: admitted_unknown
```

Suggested repair: serialize a withdrawal marker against matching pending and confirmed receipts; confirmation must preserve it when appending the actual exposure. A durable fence retained as ineligible is another conservative option. Do not treat the withdrawal as erasing the exposure or completing an unconfirmed delivery.

### P2 — A capability already observed expired can revive after clock rollback and restart

`_window` and `_check_election` compare the current supplied UTC time with the stored deadline, but an expired refusal leaves no terminal expiry observation or clock watermark (`derived_reply_proposal.py`, lines 442–455 and 457–509). `_tx` rolls the refusal back. After a clock rollback, a fresh broker instance can claim and admit that same election even though the authority already refused it as expired.

The existing regression checks `now < issued_at`, which does not cover rollback within the original validity interval. The failure reproduces with only a one-millisecond change:

```python
eid = elect()
deadline = broker.inspect(eid)["valid_until"]
now = deadline
broker.claim(eid, body)              # Refused: expired
now = deadline - 1
capsule = reopen().claim(eid, body)   # succeeds
admit(capsule)                       # succeeds
```

Observed output:

```text
at_deadline: expired
after_rollback_and_reopen: claimed_unknown
admission: Admission
```

Suggested repair: retain a durable no-revival boundary, such as a serialized clock watermark or terminal expiration evidence that survives a refused operation and restart. The exact policy should be explicit; do not merely restart or extend a deadline on retry. This is a candidate authority-state defect, not a claim that the unconnected prototype currently publishes anything.

## Confirmed strengths and prior-fix recheck

- Pending exposure fences are committed before handoff permission returns.
- Failed confirmation rolls back only the append/confirmation transaction; its earlier fence survives.
- Another instance sees the fence before claiming or admitting, and the pending state survives reopen.
- Confirmation deletes only its own fence. An independent history gap and other pending exposures still close the route.
- Claims and admissions serialize in SQLite; competing attempts cannot both consume the same state transition.
- Full causal history determines maximum hop. Selecting a later, lower-hop displayed parent cannot hide an older high-hop receipt.
- Unknown history, retired generations, changed payloads, durable policy disable/revocation and ordinary expired windows fail closed.
- The module remains unregistered, default closed, and careful about the distinction between admission, station acceptance and actual reception.

## Verification

`PYTHONPATH=prototype/canticle-station python3 -m unittest discover -s prototype/canticle-station/tests -p test_derived_reply_proposal.py`

Result: **34 passed**, zero skips. Both findings above were reproduced separately through the actual candidate library and temporary SQLite state, without changing tracked files. The full station/UDP suite was not needed to exercise these metadata-only defects and is not claimed by this review.

Disposition: fix or explicitly resolve the two boundary findings before presenting the candidate's withdrawal and expiry guarantees as proved. This review does not approve a production host contract, RFC amendment, station operation or live prince exposure.

## Exact-head recheck — 16dbdb7

Rechecked on 2026-11-21 at **`16dbdb7f84d93135948533f454a509f83861bb29`**. Both findings above are **fixed** within the candidate library's stated boundary.

1. `withdrawn_receipts` now persists revocation against either a pending or confirmed receipt, keyed to its exact generation and receipt ID. Confirmation records actual exposure as inactive when that marker exists. Identical replay cannot reactivate it, and withdrawal does not clear the pending fence or invent delivery evidence.
2. Claim/admission checks now distinguish an observed terminal deadline from a clock earlier than issue time. The former raises a private expiration signal handled inside the same SQLite writer transaction. A savepoint rolls back the attempted operation, then commits only the terminal `expired` state before releasing the lock. Reopen and clock rollback cannot restore an elected/claimable state.

The new savepoint path is narrowly triggered. Ordinary exceptions still roll back the whole transaction; there is no blanket commit-on-error and no rollback/reacquire window. `claimed_at`, the bound bytes and the original envelope remain retained for an expired claimed operation.

Independent verification at the exact head:

- **37 focused tests passed**, zero skips, including pending withdrawal, claim expiry and admission expiry regressions.
- A separate temporary-DB probe changed policy inside the operation savepoint and then raised the expiration signal. The policy mutation rolled back; only the election's terminal expiration committed.
- A second probe paused the terminal expiration UPDATE inside a SQLite trigger while a competing instance attempted a claim with its clock one millisecond before the deadline. The contender could not pass the writer lock and then refused `not_elected` after the terminal marker committed. The expiry caller returned `expired`.

No tracked source edits were made by the reviewer. **No new material findings in this recheck.** This closes these two code-review findings; it remains an inert proposal and supplies no production host/station/room-egress approval or live receipt.

### Final documentation qualification — 4e86bb2

Inspected **`4e86bb2cffedcaa6eded9874ee4badf9eeda18f4`** against the code-reviewed `16dbdb7` head. Only the station README and proposal note changed; code and tests are identical. The added language accurately states two existing scope limits: `Reader` accepts isolated subagent keys, not continuing main/Discord prince sessions; and the fixture intent binds station name plus 64-bit key ID, not a production full-public-key signer check. A real mutation must perform its own expected-full-key comparison. These qualifications prevent overclaiming the proposal and introduce no new finding. The 37-test evidence above applies to the unchanged code; no redundant rerun was made.
