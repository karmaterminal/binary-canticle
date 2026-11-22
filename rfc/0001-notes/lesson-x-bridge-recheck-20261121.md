# Independent Canticle correction recheck

Date: 2026-11-22

## Disposition

**The P2 per-source rendered hash/byte-count defect is corrected in the reviewed receiving working tree.** My original reproducer now passes, and the 20 focused source-composition tests pass with no failures, skips, cancellations, or todos. No further defect was found in this two-file correction.

This is a bounded recheck of the correction to the original `CANTICLE.md` finding. The original report remains unchanged. No source checkout edits or remote writes were made in this recheck.

## Exact reviewed state

The receiving checkout remains the synthetic materialized baseline `cb8999842adc2816c02b16c3bc466a4ee25ad350`, naming BC #154 source `d6112dc1584c6a06bd81340cd0edfb7ebb841944`. The correction consists of two unstaged files over the original staged six-file exposure-port delta.

| Evidence | SHA-256 |
|---|---|
| Original receiving delta | `aaa1e0b6a87cd342729b2db4d29588a3dd8e27d66df2cc4cdca87fea8485b20b` |
| Correction, `receiving-rendered-bytes-fix.patch`; matches `git diff --binary` | `a6ba418acaca9ed4a38f7b028f0c737ff8d1ff21ebb995e9fb1b762229d724b0` |
| Complete corrected receiving delta, `git diff HEAD --binary` | `5c21f8f988d1c516160f1c897c0668d870597efa3e32df021171027d9ae721f9` |
| Corrected `prototype/openclaw-canticle/src/binding.ts` | `feb58dde159d7af2795853e7b161325bd1c4dd1ec96515c829e8a4d40220a1e7` |
| Corrected `prototype/openclaw-canticle/test/core-wrapper-reader.test.ts` | `6aa2e8c44a312cd01dd200a462f466e87e769769012dddf30fa07a162dc9f122` |
| Preserved original `review-outbox/CANTICLE.md` | `c8ef5977def4bc3f7a932b03d40dcfbf4f6acbce3be01c46c2d858d8551d5fbd` |

All other original receiving file hashes remain those recorded in the original report.

## Why the correction addresses the finding

`Binding.listen` now keeps the unnormalized `renderEntry` output as `rendered`, measures that original value for the existing pagination budget, and normalizes consecutive newlines into `text` before both output insertion and `payloadSource` capture. The later whole-result normalization is now idempotent for each entry. Heard entries have fixed banner/closing-marker boundaries, so joining the entries does not create an additional transformation inside an already-hashed entry.

This preserves the existing journal/new rendered content and the existing conservative pagination behavior while making each source receipt describe the bytes actually returned. On-air reads retain their prior whitespace behavior. `sourceBody.textSha256` continues to describe the original source body, which is correctly distinct from the rendered entry hash.

The added regression examines actual tool-result entries across `journal`, `new`, and `on_air`, comparing output order, each entry's byte length and SHA-256, the whole result's byte length and SHA-256, and the original source body hash. Its synthetic examples include consecutive blank lines, leading/trailing blank lines, and multibyte UTF-8 characters. This directly exercises the previously failing contract.

## Independent execution

Runtime: Node `v24.22.3`.

I reran my original single-source reproducer through the actual receiving `Binding`, receiver/parser, `createTool`, and exposure-port code. The same synthetic source body was `first\n\n\nsecond`; lease acquisition and daemon startup were fixture replacements so this reproducer required no sockets.

```json
{
  "wholeResultHashMatches": true,
  "sourceCount": 1,
  "renderedHashMatches": true,
  "storedRenderedBytes": 599,
  "actualRenderedBytes": 599,
  "outputContainsTripleNewline": false,
  "outputContainsDoubleNewline": true,
  "recordedRenderedSha256": "4afe40c5cf98f9d32565d810368a125bf0293ea13dc397b4fdf4df1cc7377b2e",
  "actualRenderedSha256": "4afe40c5cf98f9d32565d810368a125bf0293ea13dc397b4fdf4df1cc7377b2e"
}
```

The specific hash includes the renderer's random wrapper ID. Equality of the two hashes and their matching byte counts is the relevant reproduced result.

I also independently ran, from `canticle-receiving/prototype/openclaw-canticle/`:

```sh
node --test --test-reporter=tap test/local-reader.test.ts test/core-wrapper-reader.test.ts
```

Result: **20 tests, 20 passed, 0 failed, 0 cancelled, 0 skipped, 0 todo**, exit code 0. This includes the added three-mode multiline regression and the existing stale-invocation, exact-reader, malformed/failed exposure acknowledgement, pending-custody restart, argument-spoofing, and default-off boundary cases. No broad suite was rerun.

## Derived transport CI update and continuing limits

Since the original report, the coordinating root agent reports independently verifying the primary GitHub job results and logs for the derived transport at source **`2694f9fd152c01edc669b47cb17e7db049bf6e84`**: all four jobs passed in [GitHub Actions run 44968780757](https://github.com/karmaterminal/binary-canticle/actions/runs/44968780757), including the mandatory actual AF_UNIX/UDP tests. This is a coordinator-verified CI update; I did not independently fetch or inspect that remote run during this narrowly scoped recheck. The original report's outstanding transport-CI statement should be read with this later evidence, while preserving its original record.

The correction does not change any production integration limits from the original report. In particular, neither passing source-composition tests nor the derived transport's real socket CI establishes a production host incarnation/history/custody producer, scope-preserving receipt-to-publisher integration, continuing main/Discord sessions, inherited exposure, or final room/frond-ear delivery. Candidate all-history-fresh/all-chatter and isolated-reader restrictions remain unchanged proposals, not newly authorized game gates.
