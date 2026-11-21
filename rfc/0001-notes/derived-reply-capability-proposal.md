# Elected derived publication: an inert capability proposal for #146

**2026-11-21 — proposed review contribution, not adopted, deployed or connected.**

Cael leads [#146](https://github.com/karmaterminal/binary-canticle/issues/146); Ronan reviews its host/station
boundary. This contribution gives their lane executable state and failure cases to inspect. It leaves the
RFC unchanged and adds no CLI command, plugin tool, socket operation, station startup or model invocation.
It does not close #145, #146 or [#156's continuing-session/room-egress proof](https://github.com/karmaterminal/binary-canticle/issues/156).

The contract sources are [Ronan's boundary review](https://github.com/karmaterminal/binary-canticle/issues/146#issuecomment-7058229229),
[Cael's proposal](https://github.com/karmaterminal/binary-canticle/issues/146#issuecomment-7058246836), and
[the exposure/capability amendment](https://github.com/karmaterminal/binary-canticle/issues/146#issuecomment-7058282945).
The source baseline is BC **08c11127d4e11ed00f307a7006d85581c8674a28** and OpenClaw #1511
**21660b2182062a9a98eb28d46341283100c082e6**. These are inspected source revisions, not fleet receipts.

## What the reference primitive does

[derived_reply_proposal.py](../../prototype/canticle-station/canticle/derived_reply_proposal.py) is closed by
default. Default construction creates no state. Its explicitly enabled tests use temporary databases,
synthetic identities and an in-memory fixture authentication secret. Its methods are trusted-host library
operations; none is a model-callable permission or a way to bypass ordinary canticle_sing.

| Boundary | Candidate behavior |
|---|---|
| Exact identity | Reader, author and intended receiving sessions name principal, canonical **subagent** session key, session ID and lifecycle revision. A reused key or retired generation does not inherit an election. Continuing main/Discord session keys are not accepted by this reference. |
| Complete historical evidence | An origin receipt must attest observed session birth before exposure, or a verified complete history with exact count and digest. Existing Boolean/timestamp taint cannot establish this. Missing origin, a gap or a pending exposure denies publication. |
| Exposure | A durable pending fence is written **before** payload handoff. Only a host-confirmed actual delivery receipt appends the source and clears that exact fence, in one transaction. An unconfirmed or failed append remains fenced across instances and restart. |
| Election | Explicit author choice binds exact new bytes by digest, independent publisher intent, audience, one cited exposure and the immutable complete-history snapshot. Silence calls nothing. Sender text is never interpreted as policy. |
| Claim | SQLite serializes the claim, generations, ledger, policy, rates and cancellation. A one-use claim is durable before its authenticated capsule is returned for any prospective send. A lost result remains unknown; a fresh idempotency key cannot create another operation for the same generation/bytes/intent. |
| Candidate station admission | An authenticated envelope must match the stored claim and current policy. It is consumed once. The result is an **admitted permission**, not station acceptance, on-air state, host reception or session exposure. |
| Lineage | Maximum hop comes from the full drained ledger. The final four drained identities become parents; the root follows the first of those four. Unknown upstream wake provenance is conservative. The model supplies none of these fields. |
| Expiry and withdrawal | Election validity and item expiry are absolute. Lock/policy delays, claim and admission do not restart either window. An observed deadline is terminal across restart and clock rollback. Withdrawal/mute is retained even during a pending exposure and prevents use while retaining the causal record. |
| Observations | Station acceptance, host reception, exact-session exposure and elected response have separate receipt records. One does not fabricate another. |

The authority database contains metadata and payload digests, not the composed payload bytes. SQLite uses
full synchronous commits and a private state file. This assumes the host controls the private directory
and authority database; HMAC does not defend against a malicious local operator or database rollback.
No station signing key is put in the broker.

`Reader` deliberately accepts only the isolated subagent-key shape. It does not represent a continuing
main or Discord prince session, prove a child-to-parent return, or suggest resetting/moving a prince to
fit that shape. Those actual continuing-session boundaries remain part of #145/#156's host proof.

### Exposure is a two-phase host boundary

The real adapter must call **begin_exposure** before bytes can enter the session. If the fence cannot be
persisted, **do not expose the bytes**. It then obtains an actual host delivery receipt and calls
**confirm_exposure**. A failed or ambiguous handoff is not confirmed. Pending fences can be inspected
for recovery, but inspecting one proves neither delivery nor permission for a blind second handoff.

The convenience **record_exposure** method is for synthetic fixtures: it immediately performs both phases.
It is not the real host boundary. An append error after the fence persists leaves history unknown,
including an SQLite failure. Confirmation clears only its own fence; it cannot erase another pending
exposure or an independent gap.

Withdrawal or mute can be recorded against a pending receipt. A subsequent confirmed delivery retains
that receipt as inactive causal history; confirmation and idempotent replay cannot make it eligible
again. Withdrawal does not assert that the pending handoff actually arrived.

The full ledger is bounded at 256 exposure receipts in this proposal. It never evicts an old high-hop
source to make an election admissible. A full ledger or unrecordable receipt leaves a fence and closes the
route. This is preparation for the owners' storage design, not a prince's quota or a request to reset him.

### Candidate host-to-station representation

The temporary namespace is **canticle-derived-reply-proposal/1**. A host-held capsule contains an envelope
and a domain-separated HMAC-SHA256 over canonical ASCII JSON. It binds issuer, random claim nonce,
election, exact reader generation, publisher/stream/class/scope, exact intended audience generations,
payload SHA-256, complete-ledger digest/count/maximum hop/final four receipts, cited exposure, wake
provenance, absolute election validity and item expiry. Tuple counters are decimal strings so a future
JavaScript adapter cannot silently round a 64-bit identity.

This is a candidate representation for Cael, Ronan and the station owner to review, **not** a new public
wire type or an adopted authentication protocol. The fixture secret is distinct from a real station's
signing key. No key provisioning or peer-credential transport is implemented here.

`Intent` and `Grant` currently bind the fixture station name and 64-bit `key_id`, not a full public key.
That is not authentication of a complete real station identity. A production operation must separately
pin the expected full 32-byte station public key and compare it to the actual signer at the mutation
boundary, alongside current manifest authority. A previous catalog/name/key-ID check is insufficient;
the cue-control fix in [#157](https://github.com/karmaterminal/binary-canticle/pull/157) for
[#155](https://github.com/karmaterminal/binary-canticle/issues/155) demonstrates that separate boundary.

Independent policy is represented by a trusted fixture **Grant** and a required content-policy callback.
Policy changes and the publication off-switch are stored in the authority database, so a stale instance
cannot ignore durable revocation. Before real use, those inputs must come from the station manifest,
owner authority, receiver policy, content controls and budgets. A passing fixture callback is not proof.

The pure **proposed_item** helper projects a fixture permission into existing frame-v2 lineage fields
for codec tests. It does not sign, allocate a real sequence, enqueue a carousel item or authorize
Station.sing. Its Admission is a local library value, not an externally trustworthy bearer object.
A real station must accept only the new authenticated operation and perform the fresh checks at its
actual mutation boundary. Falling through to ordinary sing remains prohibited.

## Narrow policy choices for owner review

This candidate permits chatter at independently granted host or LAN scope. It enforces chatter's existing
hop ceiling of two. It also conservatively requires **all** causal source receipts to remain eligible,
unwithdrawn and unexpired at election and redemption. Old receipts remain even when they can no longer
support a new publication. The owners must settle any historical-source policy before claiming a longer
game loop; the primitive does not reinterpret expiry as forgetting.

A high-hop item cannot be omitted by choosing a nicer displayed story parent. A session that heard hop two
cannot issue another chatter derivative under this rule. A new turn, topic, repeated carrier or elapsed
time does not reset that history.

An audience list constrains publication intent; **LAN broadcast is not recipient-private delivery**.
This prototype adds neither encryption nor addressed delivery. Private story secrets cannot be put on
LAN merely because a caption names one recipient.

RFC §14.12's current off-host-send restriction and its unadopted bound-reply amendment remain separate.
A native Canticle rendition does not itself authorize ordinary Discord conversation afterward.
frond-ear's host departure does not supply an OpenClaw exception. The complete room path is tracked by #156.

## Exact production seams still needed

These are **attachment points and an API proposal**, not claims that the integration exists:

| Owner boundary | Inspected source and required change |
|---|---|
| Payload exposure | BC [binding.ts](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/openclaw-canticle/src/binding.ts): journal/on-air payload returns call markTainted, which saves a per-identity timestamp. Fence the exact source set before its result can enter a session, and obtain the actual exposure/uncertainty receipt from the host. |
| Ambient exposure | BC [ambient-slots.ts](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/openclaw-canticle/src/ambient-slots.ts): consumed OC-0 entries mark generation-specific taint. These must feed the same complete ordered history; a retained ring/journal subset is insufficient. |
| Invocation identity | Core [tool-types.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/plugins/tool-types.ts) supplies sessionId, runId, assertInvocationCurrent, sandbox and delivery context. [local-session-route.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/plugins/local-session-route.ts) supplies the exact row ID/revision. Their existence does not prove exposure, host policy or a return route. |
| Tool restrictions | Core [agent-tools.before-tool-call.policy.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/agents/agent-tools.before-tool-call.policy.ts) invokes runTrustedToolPolicies with host session/run identity; [agent-tools.caller.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/agents/agent-tools.caller.ts) carries assertToolAllowed and final-I/O receipt authority. These are generic seams; this proposal registers no Canticle policy there. |
| Non-tool egress and handoff | Core [reply-dispatch-before-deliver.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/auto-reply/reply/reply-dispatch-before-deliver.ts), [completion-delivery-policy.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/auto-reply/reply/completion-delivery-policy.ts) and [agent-runner-subagent.ts](https://github.com/karmaterminal/openclaw/blob/21660b2182062a9a98eb28d46341283100c082e6/src/auto-reply/reply/agent-runner-subagent.ts) show separate reply/completion/continuation paths. Prove derived taint reaches a parent before content arrives, and no automatic announce, ordinary sing or other egress escapes it. This Python reference enforces none of those paths. |
| Actual station mutation | BC [runner.py](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/canticle-station/canticle/runner.py)'s dispatcher has no derived capability operation. [station.py](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/canticle-station/canticle/station.py)'s Station.sing does not accept parent/root parameters. The wire codec can represent them; that is not a control-path implementation. |

Generic trusted tool-policy machinery exists in this inspected core revision. Repeating the older
README's broad “no tool-policy seam” description as a current fact would be inaccurate. The missing
work is the **specific composed Canticle policy and all-egress proof**.

A minimal proposed host contract is:

1. Register an exact incarnation and a verifiable history origin; leave unknown history closed.
2. Fence a specific eligible payload delivery, then confirm its actual ordered exposure receipt or retain
   uncertainty. The complete ledger must cover every participating read surface since reset.
3. Accept the prince's new-text election under host-stamped author/turn identity. Bind the complete
   snapshot, exact bytes, audience and separately authorized publishing principal.
4. Preserve derived taint across any child-to-parent/publisher handoff before releasing content. A
   deterministic broker may carry the bound request; an unrestricted “clean” model signer cannot replace it.
5. Claim once durably, authenticate the new station operation, recheck current authority/freshness at
   mutation, and retain unknown rather than resend after a lost result.
6. Record real station, receiving-host and exact-session receipts separately. Prove a normal room reply
   only if that route is part of an explicitly adopted host contract.

These seams cannot be filled by a fixed locality Boolean, guessed clean history or a permissive content
callback and called commissioned. Existing continuing sessions are not reset by this proposal.

## Verification and its boundary

From the repository root:

    PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests -p test_derived_reply_proposal.py -v

The focused suite tests default-off operation; unknown/pending/lost history; the complete source set;
generation/key reuse; publisher/audience/content restrictions; revoked policy; real SQLite races;
claim/result loss and restart; changed bytes; cancellation; absolute expiry after delayed checks; and
separate receipt kinds. It includes both failure regressions found in independent review: another
instance cannot claim between failed exposure append and gap recording, and an SQLite append failure
cannot restore a clean prefix after restart. The independent reviewer rechecked these fixes.

A later independent pass added RED-first cases for withdrawal between fence and confirmation, and for
an already-observed expiry followed by clock rollback. Pending withdrawals now survive confirmation and
restart. Claim/admission deadline refusals commit a terminal `expired` state while holding the same
SQLite writer lock; a savepoint discards the attempted operation before that marker is committed. A
clock earlier than the election's issue time still refuses without inventing an expired deadline.

One test encodes and parses a synthetic item with the real frame-v2 codec and its existing TEST1 fixture
key. That proves the projected bytes carry lineage. It proves **no live station write, UDP reception,
actual prince exposure, human approval or permission to converse off host**. #145's actual core reader
and #146/#156's production host/station/room proofs remain owner-reviewed gates.

The [independent review and exact-head rechecks](derived-reply-capability-review-20261121.md) retain the reproduced failures, repairs and proof limits.
