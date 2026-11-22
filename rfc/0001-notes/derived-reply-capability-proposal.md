# Elected derived publication: a default-closed capability proposal for #146

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
| Candidate station admission | An authenticated envelope must match the stored claim, full signer public key and current policy. It is consumed once. The primitive returns an **admitted permission**. The separate disabled station adapter can then sign and queue it, recording an immutable acceptance receipt. Neither result proves host reception or session exposure. |
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

The temporary namespace is **canticle-derived-reply-proposal/2**. A host-held capsule contains an envelope
and a domain-separated HMAC-SHA256 over canonical ASCII JSON. It binds issuer, random claim nonce,
election, exact reader generation, publisher/stream/class/scope, exact intended audience generations,
payload SHA-256, complete-ledger digest/count/maximum hop/final four receipts, cited exposure, wake
provenance, absolute election validity and item expiry. Tuple counters are decimal strings so a future
JavaScript adapter cannot silently round a 64-bit identity.

This is a candidate representation for Cael, Ronan and the station owner to review, **not** a new public
wire type or an adopted authentication protocol. The fixture secret is distinct from a real station's
signing key. No key provisioning or peer-credential transport is implemented here.

`Intent` and `Grant` bind the complete 32-byte station public key as canonical hex, in addition to
station name and its derived 64-bit `key_id`. The authenticated version-2 envelope includes that key;
version-1 fixture capsules are refused. The new station adapter compares it to the actual signing key
both at durable admission and at the final mutation, alongside the current manifest grant. A previous
catalog/name/key-ID check cannot replace the second check. The cue-control fix in
[#157](https://github.com/karmaterminal/binary-canticle/pull/157) addresses that same distinct boundary
for original world cues; this proposal does not depend on its implementation.

Independent policy is represented by a trusted fixture **Grant** and a required content-policy callback.
Policy changes and the publication off-switch are stored in the authority database, so a stale instance
cannot ignore durable revocation. Before real use, those inputs must come from the station manifest,
owner authority, receiver policy, content controls and budgets. A passing fixture callback is not proof.

The pure **proposed_item** helper projects a permission into existing frame-v2 lineage fields.
Its Admission is a local library value, not an externally trustworthy bearer object. The real effect
proof uses the separate adapter below; falling through to ordinary sing remains prohibited.

### Actual Station effect, still unregistered and default closed

[derived_station_proposal.py](../../prototype/canticle-station/canticle/derived_station_proposal.py)
adds **DerivedStationProposal.publish** and a read-only **query**. No CLI, socket dispatcher or agent
tool imports this module. Both the adapter's `enabled=True` and the Station's `derived_proposals=True`
are required; normal station startup passes neither. They are explicit library construction choices
for isolated tests, not an operator rollout command.

1. Under the station adapter lock, authenticate and consume the host capsule, binding the exact bytes,
   generations, complete source history and full actual signer. Commit an `admitted_unknown` election
   and a durable `claimed_unknown` station-effect row **before** mutation is possible.
2. Acquire the same SQLite writer lock used by history, generation and policy changes. Recheck all
   those inputs and the deadline. A new receipt, withdrawal, changed generation or revoked grant
   between the durable claim and this stage refuses before mutation. Current per-turn/hour budgets
   are checked again: a tightened grant can refuse an already-spent reservation, which stays spent.
3. Call Station's private `_accept_derived_proposal` effect boundary. It independently rechecks the
   full public key and manifest grant, class/scope/stream, lineage, current epoch and next sequence.
   It signs existing frame-v2 bytes and schedules the actual carousel, without calling ordinary sing.
   Absolute expiry can only shorten under station limits. No derived refresh is supported.
4. Commit an immutable station-acceptance receipt before returning it. It identifies the election,
   exact reader generation, history digest/count and cited exposure, payload digest, complete station
   key, frame digest, epoch/sequence, expiry and derived flags. Acceptance means **signed and queued**,
   not emitted, heard or exposed to a session.

If the process dies before the effect, the durable claim stays unknown and is never retried. If the
station mutates but the receipt write fails, it also stays unknown; the lost receipt does not justify
a second enqueue. If only the reply is lost after the receipt commits, `query(election_id)` recovers
that same immutable acceptance without re-enqueueing. A restart may lose the in-memory carousel even
when acceptance is known; query does not claim the item is currently on air or restore it.

The proposal remains single-host library composition: host and station checks share one SQLite
authority database, and the adapter owns one Station. Its lock serializes competing candidate calls;
the station's normal owner must serialize **all** ordinary mutations and polling too. This is not a
cross-process station protocol or an authenticated IPC provisioning design. The existing unsigned
spike manifest is still not a signed fleet trust source.

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
| Production station bridge | BC [runner.py](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/canticle-station/canticle/runner.py)'s dispatcher still has no derived capability operation. [station.py](https://github.com/karmaterminal/binary-canticle/blob/08c11127d4e11ed00f307a7006d85581c8674a28/prototype/canticle-station/canticle/station.py)'s ordinary Station.sing remains unchanged. The unregistered proposed adapter now exercises its separate private lineage admission method. Production still needs owner-approved capability transport/provisioning and trusted host integration; this library proof does not supply them. |

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

    PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests -p 'test_derived_*proposal.py' -v

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

The station suite adds real signing/carousel/Listener and bounded loopback UDP proofs. It checks a
non-chosen high-hop source, the final-four parent set, wake provenance, quiet/no operation, racing
redemptions, a full signer replacement with the same 64-bit ID, manifest revocation, expiry and
new exposure between claim and effect, restart before mutation, lost result after mutation, and an
SQLite receipt-write failure after an actual mutation. It asserts ordinary sing is never called.
Loopback sockets are temporary; no multicast, fleet station or prince session is used. CI treats a
socket permission failure as a failed transport proof, rather than skipping it.

These tests prove an actual Station effect and a signature-verifying Listener encounter under a
**synthetic host authority**. They prove no live host wrapper, complete continuing-prince history,
parent handoff, exact prince exposure, human approval or permission to converse off host. #145's
actual core reader and #146/#156's production host/bridge/room proofs remain owner-reviewed gates.

The [independent review and exact-head rechecks](derived-reply-capability-review-20261121.md) retain the reproduced failures, repairs and proof limits.


### Minimal next integration, for the owners

There is no `canticle derived-publish` CLI or configured host route to run yet. After the representation
and source-use policy are adopted, the implementation owner must wire the host's exposure fences and
complete ledger to the actual wrapper, inherit that ledger before a parent receives any child result,
and add an authenticated trusted IPC operation that calls this adapter with a host-selected station.
Do not expose `Admission`, raw lineage fields, a permissive fixture callback or an arbitrary database
path as model inputs. Then run one disposable host encounter through the real bridge and exact
recipient; all adversarial cases above already belong to automated tests. Normal bound-room egress
and the Claude/frond-ear route still require their separately specified host contracts.
