# Independent Canticle delta review

Date: 2026-11-22

## Disposition

**One confirmed P2 defect in the receiving exposure port. No additional blocking defect found in the bounded derived control transport.** Repair the per-source rendered hash/byte-count mismatch before treating the receiving metadata as exact result evidence. Subject to that repair and the already-required real-socket CI, both changes fit their advertised default-off/internal component boundaries.

This is a review of two isolated deltas, not an approval of a deployed Lesson X loop, a continuing main/Discord reader, or frond-ear/room egress. No code in either checkout was edited, no remote writes were made, and no other new review report or author completion summary was used.

## Reviewed identity

The local repositories are materialized source snapshots, not the original remote histories. The coordinating agent states that their relevant source bytes were checked against the named remote Git blobs. I independently reviewed the local deltas and hashes; I did not repeat the remote source-materialization audit.

| Delta | Named upstream source | Local synthetic baseline | Reviewed patch SHA-256 |
|---|---|---|---|
| Derived control transport | BC #159 `7772a0bb2a035b2029452b814d7e835180089d8c` | `3e92d53e67083f1348425bcf6babf8bc497c0e92` | `61c35aa03fed3db7f3a2fd7d35d59b91f3ce4c1a8ee574db2dbdef5190e1c4f0` |
| Receiving exposure port | BC #154 `d6112dc1584c6a06bd81340cd0edfb7ebb841944` | `cb8999842adc2816c02b16c3bc466a4ee25ad350` | `aaa1e0b6a87cd342729b2db4d29588a3dd8e27d66df2cc4cdca87fea8485b20b` |

The derived staged diff matched `derived-control.patch` exactly. The receiving delta was initially working-tree content and became staged during review; its reviewed staged diff matched `receiving-exposure-port.patch` exactly. The receiving finding below refers to those original patch bytes. The derived staged tree ID was `ed4318c439362a94ee9fd1b35b5272dc334fd113`.

## Finding: P2 — journal normalization invalidates the per-source rendered receipt

**Locations:** `prototype/openclaw-canticle/src/binding.ts:774–790,823–824`; `prototype/openclaw-canticle/src/exposure.ts:26–28,90–91`.

For a journal/new payload read, `Binding.listen` renders each selected entry, then passes that unmodified string to `payloadSource`. The source record claims to hash and count the exact rendered entry. After all source records have been computed, construction of the complete result applies `.replace(/\n{3,}/g, "\n\n")` across the entire output, including station-written payload text. A valid source body containing three or more consecutive newlines therefore has different displayed entry bytes from the bytes recorded by `renderedSha256` and `renderedBytes`.

I reproduced this through the actual receiving `Binding`, record parser/receiver, `createTool`, and new exposure-port code with a single synthetic body `first\n\n\nsecond`. Lease acquisition and daemon startup were replaced only to avoid sockets. The host port captured the proposed fence record; it was a synthetic capture, not a production custody receipt.

Observed output:

```json
{
  "wholeResultHashMatches": true,
  "sourceCount": 1,
  "renderedHashMatches": false,
  "storedRenderedBytes": 600,
  "actualRenderedBytes": 599,
  "outputContainsTripleNewline": false,
  "outputContainsDoubleNewline": true,
  "recordedRenderedSha256": "a0f909e9c559b3409c7b4e270a02cc486337482e5400f9f9510259bca569fec0",
  "actualRenderedSha256": "8862316a37c55f8617d8848c0582ce83532b9bd32aeb8140c1b412fd74aa027f"
}
```

The exact hashes in this one run include the renderer's random wrapper ID; the mismatch and one-byte discrepancy are reproducible. `resultSha256` still correctly names the complete plugin text because it is computed after result construction. Thus this does not demonstrate a forged item identity, missing causal source, or successful unauthorized publication. It does contradict the new per-source exact-byte contract and will cause a host that checks those source receipts against the actual returned entries to reject or misidentify ordinary multiline content.

**Required correction:** either preserve each rendered entry when assembling the full result, or perform any intended normalization on each entry before output insertion, byte budgeting, and metadata hashing. Avoid a later transformation of payload bytes that the source receipt does not cover. Add a focused regression using consecutive blank lines, checking both the full-result hash and each returned source-entry hash/byte count. Journal and new reads share this path; on-air reads do not perform this whole-output normalization.

## Boundary checks

### Derived control transport

- Normal CLI startup still supplies no bridge, and the existing default-off proposal/Station settings remain unchanged. Merely importing the new module creates no capability, key, database, exposure receipt, or elected publication.
- Enabling the bridge requires the exact same Station instance and all three relevant enabled states. Publication additionally honors the existing socket chatter-class restriction. `run_station` still refuses host-scoped frames over its UDP transport.
- Both derived operations require an actual integer kernel peer UID equal to the station process UID. A missing UID refuses derived requests, and request JSON cannot supply it. This authenticates the process user; it is not independent model/session authentication. The already-issued HMAC capsule remains the publication authority within this trusted-host design.
- Publication accepts only `op`, `capsule_b64`, and `text`. Base64 and UTF-8 conversion are checked, decoded capability size is bounded, outgoing payload is capped at 800 bytes before the narrower grant, and extra fields cannot override identity, scope, stream, lineage, or policy.
- The transport applies the credential/high-entropy scan before publication even when the producer callback was permissive. The Python patterns, ASCII word-boundary behavior, token character class, entropy threshold, and findings-only response match the existing TypeScript sender policy on inspection. This scan is not a source-use or audience authorization mechanism.
- The existing effect adapter is still responsible for authenticated exact elected bytes, current reader/audience generations, complete candidate history, full signing public key, current grant/budget/deadline checks, durable one-use admission, and separate Station lineage admission. The new transport forwards to that path and does not fall through to ordinary `Station.sing`.
- Dispatch and normal Station polling occur synchronously on the same event loop. Lost control replies do not cause redispatch. `derived_query` validates the election ID and calls the query-only adapter; it does not send, refresh, re-enqueue, or establish current on-air status.

No additional code finding arose in those new transport lines. Real AF_UNIX/UDP execution remains required; source inspection cannot establish it.

### Receiving exposure port

- The port comes from the trusted tool-factory context's `toolBindings`, not model tool arguments. It verifies its version and reader key/session ID/lifecycle revision against the configured isolated reader, and also verifies the context's exact key/session ID. The existing route and invocation admission checks remain in place.
- The port is optional for the legacy taint-only path. Absence is explicitly not complete-history evidence. A host mode that needs a complete ledger must require a real port before preparing its reader; that production host integration is still absent.
- Source records come from the actual selected frame owners, in returned item order. They retain item/root/hop, class, uncoerced scope/null, lens, principal, flags including unknown wake provenance, original/local timing, source content identity, and available receiver cursors. The on-air path correctly leaves unavailable cursor values null. No model-selected parent list replaces this set.
- Both payload-return paths taint/checkpoint before the asynchronous custody call. The tool awaits `begin` and rechecks invocation and port authority after it resolves. A failed or malformed acknowledgement withholds payload while leaving conservative taint and any already-persisted fence in place. The callback can still reject afterward; the port appropriately has no confirmation method.
- The bounded patch does not create publication, reset a session, erase history, or enable ordinary `canticle_sing` for these subagent readers. The new tests explicitly exercise argument spoofing, wrong incarnation, missing/failed acknowledgement, post-begin invocation termination, and a SQLite reopen with pending custody retained.
- The per-source exact rendering claim needs the P2 repair above. The complete plugin result hash is correct in the reproducer. Neither hash alone proves provider receipt or a model encounter.

## Evidence and limits

I read both deltas, their source dependencies relevant to these boundaries, the repository instructions, applicable RFC material, and the baseline candidate proposal. I independently ran only the focused multiline/hash reproducer described above. I did not repeat the coordinator's seven direct transport tests or nineteen source-composition tests, and I did not attempt the already-blocked real AF_UNIX suite. Those reported tests are not represented here as my executions.

The new Python socket tests are mandatory tests, not environment-skip proofs. They cover actual Unix requests, Station signing, UDP, and a signature-verifying Listener when run on a suitable CI host. The source-composition receipt remains labeled as offline composition: exact core wrapper sources run, while admitted-run production, live session storage, daemon/lease services, and exposure-ledger custody remain declared fixtures. Its input hashing includes the new `src/exposure.ts`.

The following remain integration requirements rather than defects newly introduced by these two deltas:

1. A real host producer for exact current incarnation, source-complete historical origin/migration, durable pending custody, and verified confirmation/recovery at the actual model handoff. Legacy timestamp taint cannot supply that history.
2. Connecting the rich receiving source receipt to the publisher without dropping scope or source content identity. The baseline Python `Exposure` representation does not presently carry those fields. In particular, receiving `scope: "host"` must not become permission for LAN publication merely through conversion to its existing fields. The receiving README explicitly leaves that consumption work open.
3. Actual sensitivity/audience/source-use authority and capability provisioning. LAN broadcast is not recipient-private because an intent names particular readers.
4. Continuing main/Discord session support, child/inherited exposure, non-tool and parent-result custody, and permitted room/frond-ear egress. The current isolated-reader representation is unchanged and is not a new authorized game gate.
5. The candidate all-history-fresh/all-chatter policy remains a proposal. This review neither adopts it nor treats loosening it as authorized. Its presence must not be described as a requirement the user has accepted for the final game.

The control transport and exposure port are useful separate attachment components. Their combined existence is not a proof that the actual host, continuing prince, station, recipient, and room paths have been connected or deployed.

## Reviewed file SHA-256 values

Derived paths are relative to `canticle-derived/`:

| File | SHA-256 |
|---|---|
| `prototype/canticle-station/README.md` | `8e8d3b027bbc1e2ab8adadfd5098c9ee5ea39c95df9761d89dc79ae31f3962a2` |
| `prototype/canticle-station/canticle/content_policy.py` | `e440ad7d828a7e58429702042e4e307ae4c04b81851c76401139720c229d7ca2` |
| `prototype/canticle-station/canticle/derived_control.py` | `365e17ead3539e46dd36cac9bf51976b476503c7cf4a9d5d12e73818545161c0` |
| `prototype/canticle-station/canticle/runner.py` | `b6f7d8f493c8e6c61f2fefd8e1249ced5b4dd28f083fb00ef430b0f5b413a7a4` |
| `prototype/canticle-station/docs/derived-control-bridge.md` | `2685ac94da52b1b27c64b8d9983172e84376446fe350356a346b4d1c9060edf3` |
| `prototype/canticle-station/tests/test_derived_control.py` | `80f01b158013213e0dd037d30d7928c67f532018af6c8596bf246bf4248ec9e0` |

Receiving paths are relative to `canticle-receiving/`:

| File | SHA-256 |
|---|---|
| `prototype/openclaw-canticle/README.md` | `f12c958e8230f5b584437e60b57870aa9e1aa7e53df1d2e7fb53af0be8dd8075` |
| `prototype/openclaw-canticle/proofs/core-reader.mjs` | `ef628c8acc1518d0ed7192ab2863ecf455659e9058f61e718309bebd800faf9d` |
| `prototype/openclaw-canticle/src/binding.ts` | `0b485401a67e701cbbd299712a4204fbbe4c313be126c9bb822715218fc1ecd3` |
| `prototype/openclaw-canticle/src/exposure.ts` | `476a65cf467dfdca995515dc28f0ba8ff660f144686efe7a5af27020b0103231` |
| `prototype/openclaw-canticle/src/tools.ts` | `5fec371ebe504e332994336828e6477768c6acb580fd31e3ef12a39c812baa6c` |
| `prototype/openclaw-canticle/test/core-wrapper-reader.test.ts` | `0867b58d95e36fdbf1abcfd092409959d741630761a1a90a019ddfdc63b77602` |
