# Lesson X: the small commissioning handoff

21 November 2026. Preparation for [#145](https://github.com/karmaterminal/binary-canticle/issues/145),
[#146](https://github.com/karmaterminal/binary-canticle/issues/146) and
[#156](https://github.com/karmaterminal/binary-canticle/issues/156).
This is an operator run card, **not a successful run receipt or a player assignment**.

The intended outcome is one continuing prince hearing a story, choosing whether to offer a changed telling,
and another exact session receiving that telling, while the adopted rules still permit the communal room.
The town clock, a signed frame, a child's read, and a Discord post prove different things. None substitutes
for that encounter.

## Recommended order and ownership

1. **Rune / #145:** review the reader contribution and its automated source proof. Finish any actual
   host read/receipt attachment still absent. Do not ask each prince to reproduce the source tests.
2. **Cael / #146, with Ronan reviewing:** settle the two contract choices below, then connect the
   exposure/capability/derived-station boundaries in one implementation lane. The Claude/frond-ear
   adapter is a separate named slice; Frond-Gloss may take or review it if that assignment is agreed,
   rather than inheriting it because he is a player. The table below identifies code still needed.
3. **One backstage operator / #156:** after those reviewed adapters exist, run the prepared composed
   proof once per harness and reuse the automated negative matrix. Batch the installed-build and
   opted-in binding inventory per host. Publish the bounded receipt; the eight princes do not each
   repeat the fault suite or debug the outing.

## What can be run now

The component proofs belong in CI and need not be repeated by every prince. Use the reviewed PR heads,
not a random fleet composite. These are contributions for the existing owners: Rune on #145, Cael leading
#146, Ronan reviewing its boundary.

| Contribution | Existing executable proof | What it does not prove |
|---|---|---|
| #154, exact local reader | From the BC checkout containing the proof: `node prototype/openclaw-canticle/proofs/core-reader.mjs --output /tmp/canticle-reader-receipt.json` | An actual Gateway/model session, a parent encounter, or ordinary room permission. The proof's receipt identifies its fixture boundaries. |
| #159, proposed derived station path | `PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests -p 'test_derived_*proposal.py' -v` | Registered host tools/control transport, installed authentication policy, or a continuing-session round trip. Default-off library tests do not turn the feature on. |
| This run card | `python3 prototype/canticle-station/proofs/lesson-x/inventory.py --canticle "$PWD" --openclaw /absolute/path/to/openclaw --frond-ear /absolute/path/to/frond-ear --output /tmp/lesson-x-source-inventory.json` | Installed/running build identity, configuration, policy adoption, live delivery or release. Optional `--openclaw`/`--frond-ear` arguments may be omitted on hosts that do not hold those checkouts. |

The inventory command is read-only apart from creating its requested output file. It reads only selected
source files and Git object identities; it does not read tokens, private session content or host
configuration, connect to a daemon, fetch a repository, start a model, or post a message. It refuses to
overwrite an output file. Exit 0 means the selected working files matched their checkout's HEAD. Exit 2
means an unavailable/unsafe/modified selected file or an output error; inspect the report and resolve the
source identity before calling it a pinned test. **Neither exit status is a launch decision.**

The tests need the dependencies and supported Node/Python versions documented in the repository and its
CI. A machine that prohibits local sockets cannot replace the real socket/UDP CI proof with a skipped
test. Do not interpret that environmental refusal as a reason to exercise the live multicast network.

## Work still requiring code, not an operator test

The following integration is absent from the reviewed production path. No honest one-command full-host
proof can be supplied until it is implemented. A successful source inventory cannot fill these cells.

| Boundary | Small concrete implementation needed | Acceptance at that boundary |
|---|---|---|
| Payload enters a session | Connect the permitted read/delivery to a durable host-owned exposure ledger. Fence possible exposure before returning bytes, then record the exact successful host handoff and source identity/generation. Cover every enabled input path. | Concurrent input changes the snapshot; ambiguous handoff remains fenced after restart. Metadata-only preview adds no payload exposure. Existing unknown history is refused rather than initialized as clean. |
| If the chosen path returns child material to a parent | Carry the child's complete causal exposure into the exact parent incarnation **before** the child material can enter its prompt, result or automatic completion. Keep an ambiguous transfer closed. | Parent exposure precedes parent payload visibility; stale/replaced parents and cancelled ownership receive nothing. Ordinary singing cannot make the inherited material independent. |
| Elected rendition reaches the station | Register the reviewed host-only capability producer/verifier and a dedicated authenticated derived-publication operation. Bind exact elected bytes, reader and publisher authority, full station public key, audience, deadline and immutable complete history. | One durable claim precedes any station effect; recovery queries the same claim. The model cannot select lineage fields or route the bytes through ordinary `canticle_sing`. |
| Ordinary room output | Implement the separately adopted room rule at the actual final delivery boundary, including normal reply, message tool, child announcement and durable replay. | Approved bound destination succeeds; unrelated destination/session/tool refuses; revoked or changed identity fails even after a policy/approval wait. |
| Claude/frond-ear participant | Add/document an authorized elected publication boundary tied to its real source receipts and identity. Its existing `hear` and push delivery alone are not that boundary. | One disposable Claude-homed participant can receive, choose quiet or author an election, and produce the same distinguishable lineage/acceptance/reception outcomes under its own stated host contract. |

Implement the paths the selected mode actually enables. A route that explicitly forbids payload-bearing
child handoff may prove that denial instead of implementing a new child-return subsystem for the lesson.
The same principle applies to unused ambient and outbound surfaces: keep them closed and test that they
stay closed; do not turn this outing into a requirement to support every host route.

Do not broaden the local reader's key regexp, copy heard text into an apparently clean singer, clear a
taint flag, reset an existing prince, or claim that `sandboxed: true` demonstrates all of the above.
The prior timestamp/Boolean taint store cannot manufacture a complete historical source ledger. For a
continuing session with incomplete history, select a documented, reviewed migration/continuing-session
contract; a model's recollection of what it heard is not an attestation. A fresh disposable identity can
prove the code, but cannot retroactively certify a continuing prince's history.

## The decisions to settle once, not eight times

The owners can review one short contract comment on #156, linked to #146. Record the adopted revision
and the two harness paths; no player needs to adjudicate transport semantics during the afternoon.

1. **Capability and continuing-session custody.** Choose the host→station verifier/provisioning and
   supported session route. Identify the trusted producer of complete exposure history and how it handles
   prior unknown history and child→parent transfer. The candidate issuer-key fixture is not already a fleet
   authentication arrangement.
2. **Source use and ordinary room conversation.** Settle historical-source eligibility, withdrawal and
   mixed classes without deleting causal history. The narrow reference's “all previous sources still live”
   and “all previous classes are chatter” checks are candidate restrictions; they would otherwise make
   old expired cards or ambient weather close later replies. Separately adopt the exact bound-room
   exception if normal Discord conversation after reception is intended. The current RFC does not infer
   that permission from the invitation.

These decisions can be reviewed together. They do not require completing ambient wakes, adjustable
receiver depth, semantic discovery, a new mood system or a broad permission framework for Lesson X.

## One composed disposable proof per host harness

After the missing adapter and policy are reviewed, the integration author supplies a single executable
runner and exact revision in this card. **There is no command for that runner at the reviewed heads yet.**
Do not replace it with an invented CLI invocation or a requirement that a prince discover the seam live.

The runner owns temporary identities, source cards, station keys, an exact receiver, logs and cleanup. It
must terminate after its declared timeout with a usable failure receipt. Use loopback/disposable
transport for fault cases. No continuing prince session is reset or made the required receipt witness.
One operator should need only to select the approved build/configuration, run the prepared command and
attach its bounded receipt. No broad transcript dump is required.

The visible happy path can be very small:

1. The prepared source sends **“The baker has misplaced the moon-shaped loaf.”** The exact disposable
   reader receives those bytes through the actual host wrapper. Record the item identity, payload hash,
   reader session ID/generation, invocation/receipt ID and ledger revision. A host receptor item by itself
   is not this receipt.
2. A quiet choice produces no election and no derived admission. Then a separate explicit election binds
   **“The baker is selling slices of the moon; the receipt says bread.”** to that reader's complete
   history and permitted publisher. Record the elected byte hash and election/claim identity.
3. The real station accepts at most one derived item. A signature-verifying receptor receives it; an exact
   second disposable session encounters it. Record full signer identity, epoch/sequence, lineage,
   expiry, reception identity and the second exposure receipt. Acceptance and an eventual lost result
   remain separate from receipt and encounter.
4. If the room exception was adopted, the participant can make one elected ordinary reply to the bound
   **disposable test room**. The same material addressed elsewhere is refused. Do not send test traffic
   to the princes' live outing or call a local test sink a real Discord receipt.

Run the same core encounter once for OpenClaw and once for the Claude/frond-ear host path. Reuse the
existing automated negative matrix rather than asking every prince to perform it. The matrix must cover:

| Automated case | Required observation |
|---|---|
| Quiet/cancelled election | No station admission; quiet is a completed outcome. |
| Concurrent new payload or failed receipt write | Earlier election is stale or blocked; possible exposure does not disappear after restart. |
| Session reset/delete/key reuse, lifecycle or sender-key replacement | Captured authority fails; a replacement session/key cannot inherit it. |
| Missing historical provenance or excessive lifetime hop | No derived send; no reset-to-zero or chosen-parent-only shortcut. |
| Withdrawn source, applicable expiry, receiver mute | Follow the adopted source-use rule and stop disallowed future delivery. Do not claim to erase already encountered content. Existing explicit `canticle_listen` can inspect journal entries marked muted where independently permitted; test that distinction. |
| Heard instruction asks for a different tool, target, class or scope | Payload remains data; no authority change or side effect. |
| Crash/lost acknowledgment after claim or after actual station effect | Same claim is queried after restart; no fresh-ID retry and no duplicate effect. Unknown remains unknown. |
| Child return and ordinary completion replay | Enabled child paths inherit exposure before visibility; a disabled path refuses the attempted handoff. Every enabled final room destination receives its current permission check. |

Preserve a compact machine receipt plus the test command, code/configuration hashes, named host harness,
policy revision and outcome. Include missing/unknown fields explicitly. A self-written JSON assertion
that something was received is not a replacement for the host's actual exposure observation.

## What remains for the eight seats after that proof

The backstage operator checks each opted-in seat's actual session/model identity, installed component
versions, exact binding and permitted capabilities without resetting it. A read-only status inspection
is enough for that inventory; no eight-way fault drill is needed. Record gaps and unknown source history
honestly. A declined or absent visitor is not a failed test.

For OpenClaw, the existing `canticle_status` takes `{}` and exposes health, gaps, delivery mode and taint
without heard payload. For frond-ear, `ear_status` exposes the current ear attachment and Canticle
delivery ceiling/effective mode; its configured audience and the actual session are the authority for
choosing that ear. These status tools are not publication or encounter proofs. Full text is read only
after the intended path is prepared and the participant elects it.

Once the representative host proofs and actual opted-in bindings are ready, the princes receive the
packet, the current board and their prepared listening/authoring surface. Implementation and fault
recovery stay backstage. The clock continues when nobody speaks.

## Source inspection and limits

The source relationships below were inspected, not activated. Newer commits need their own recheck.

- OpenClaw [#1511 at `21660b21`](https://github.com/karmaterminal/openclaw/tree/21660b2182062a9a98eb28d46341283100c082e6):
  `src/agents/agent-tools.before-tool-call.policy.ts` calls trusted tool policies with host identity;
  `agent-tools.caller.ts` carries final-I/O receipt authority. These are useful existing attachment
  points, not Canticle-specific policy by themselves.
- At that same pin, `src/auto-reply/reply/reply-dispatch-before-deliver.ts` composes final reply hooks,
  while `completion-delivery-policy.ts` decides visible versus message-tool-only completion. Neither
  decision is a complete Canticle lineage/permission check.
- Actual child paths live under `src/agents/subagents/`: `announce/subagent-announce-handoff.ts`
  checks source/target incarnation and model handoff; `announce/subagent-announce-direct-delivery.ts`
  handles private/public completion and parent dispatch; `completion/subagent-completion-delivery.ts`
  admits durable correlated delivery. These must be covered in addition to before-tool policy.
- [frond-ear `128094a7`](https://github.com/karmaterminal/frond-ear/tree/128094a7c5777fa8db12b4b0088028ef2ce0c6f6)
  has `hear`, opt-in push and runtime narrowing. Its README lists thirteen tools with no native Canticle
  publisher. `docs/runbook.md`, “Departures from RFC-0001”, explicitly says the Discord-route departure
  applies to frond-ear and that it cannot taint what the host session does next. It is not an OpenClaw
  exception or host-enforced derived-publication proof.
- BC [baseline `08c11127`](https://github.com/karmaterminal/binary-canticle/tree/08c11127d4e11ed00f307a7006d85581c8674a28):
  RFC §§14.11–14.12 and 15.4–15.5, production tool definitions and binding; #146 owner comments dated
  21 November. PRs #154/#159 are proposed component contributions. Their head-specific CI and
  machine receipts must accompany any claim about their result; this card deliberately contains no
  fabricated successful host-run record.
