# Independent Lesson X source-composition review

Date: 2026-11-22

## Recommendation

**No merge-specific defect found. Recommend publishing this exact source composition as a draft PR for ordinary combined CI.** It retains the named proposal contributions and their default-disabled/internal boundaries. This recommendation does not adopt the proposals, approve their merge to main, authorize deployment, or establish the missing production receiving-session/room/frond-ear path.

Scope was limited to preservation of the pinned contributions, the combined runner semantics, and the exact corrected plugin subtree. No code or remote writes were made. The checkout was clean before and after verification.

## Exact reviewed identity

| Item | Exact identity |
|---|---|
| Composed commit | `cc7e2074367386fa0dab74eee11351d4912e3b8a` |
| Composed Git tree | `e58e0201ae821d57a67c8c05f30a9d22ee46de2a` |
| `prototype/canticle-station/canticle/runner.py` SHA-256 | `8e3b819fc73b72e6d64b4a83c50d7583f2b79496c3da669a5c97545eb76cfd12` |
| Runner Git blob | `554c1c3b8cff53745fe83b7aca040e547744aeba` |
| Complete `prototype/openclaw-canticle/` Git subtree | `05f150aea526ef0c2b31e04f64d3043275d033f9` |
| `prototype/canticle-station/proofs/lesson-x/SOURCE-COMPOSITION.md` SHA-256 | `77874353c011eafaabd62188175bebebcc7f0c9a2972d0ae1c0ee4e6ecc38324` |

Named contribution pins:

| Contribution | Commit |
|---|---|
| Existing main, including typed beacons | `08c11127d4e11ed00f307a7006d85581c8674a28` |
| `import-original`, cue identity and absolute expiry | `4e6f090b4ecd7a694da9cb71568f1ed2af696ac8` |
| `current-derived`, capability/effect/control transport | `2694f9fd152c01edc669b47cb17e7db049bf6e84` |
| `current-receiving`, corrected receiving exposure port | `d27b520632a3df8ba79f2536213ccd429b5e50f6` |
| `import-host-card`, bounded operator inventory and run card | `ff158758a1e48d722ddcdbdebd8f1425ee3e4e29` |

The local repository has no `main` ref, so comparisons used the exact main commit `08c11127d4e11ed00f307a7006d85581c8674a28` directly.

## Preservation audit

I compared the complete recursive Git tree entries, including modes and blob identities, for every file contributed by each pin against its merge base with existing main. All four contribution pins have `08c11127d4e11ed00f307a7006d85581c8674a28` as that merge base.

| Contribution | Contributed paths | Files differing from its pin in the composed tree |
|---|---:|---|
| Original cue | 5 | Station README and runner only |
| Derived | 15 | Station README and runner only |
| Corrected receiving | 22 | None |
| Host inventory/run card | 3 | None |

The only overlapping contribution paths are `prototype/canticle-station/README.md` and `prototype/canticle-station/canticle/runner.py`. The station README retains both sources as additive sections: its diff from the original-cue pin adds the derived section, and its diff from the derived pin adds the original-cue documentation. Neither side's existing text was removed.

The complete OpenClaw plugin subtree has the same Git subtree ID at the composed commit and at `current-receiving`; `git diff current-receiving -- prototype/openclaw-canticle` is empty. Thus the reviewed multiline-rendered-byte correction is preserved exactly with the receiving source, along with its tests and fixtures.

No main file was deleted. No composed change lies outside the union of the contribution paths except the explicitly new `SOURCE-COMPOSITION.md` note. The normative RFC, CI workflow, and CI dependency files remain unchanged from the named main baseline. This audit found no dropped contribution or incidental implementation change.

## Combined runner semantics

Source comparison against both `current-derived` and `import-original` confirms the runner retains their respective behavior:

- `_dispatch` accepts both `cue_store`/`grant_loader` and `derived_bridge`/`peer_uid`. Exact `derived_publish` and `derived_query` operations route to the derived bridge, while `cue_*` operations route to the cue store. Each optional path keeps its own unconfigured refusal. Derived publication retains the chatter socket-class check.
- `run_station` accepts both sets of optional arguments. Before creating its transport socket, it retains the manifest-grant and host-scope checks, checks that the cue store belongs to this Station and has a grant loader, and calls the derived bridge's Station configuration check when supplied.
- The control handler still obtains `uid = _peer_uid(writer)` from its actual Unix peer path. It passes that `uid` to `_dispatch` together with the configured cue store, grant loader, and derived bridge. It does not obtain derived identity from request JSON.
- The original cue worker tick remains inside the single station event loop, before `station.poll`. Cue control/worker operations, ordinary mutations, derived dispatch, and carousel polling stay serialized by that synchronous owner loop. The merge adds no background per-cue task, retry loop, or concurrent Station mutation path.
- The derived transport's lost-response `ConnectionError` handling and socket cleanup on Unix-server startup failure are retained. No failed response triggers redispatch.
- The CLI file is byte-identical to the original-cue pin. It passes the elected cue store and live manifest loader by keyword and does not automatically construct a derived bridge. All in-tree `run_station` callers continue to fit the combined signature.

The original cue code does not replace the Station's grant as a side effect of its current-grant checks. The merge therefore introduces no unexpected shared-grant mutation between the two configured components. Each existing adapter retains its own already-reviewed authority checks.

## Focused verification

Runtime: Python `3.12.14`, cryptography `50.0.1`. These are local verification versions, not a replacement for the repository's ordinary Python 3.11 CI gate.

I independently ran the seven direct `DerivedControlTest` tests and three selected cue tests on the composed source:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=prototype/canticle-station:prototype/canticle-station/tests \
python -m unittest -v \
  test_derived_control.DerivedControlTest \
  test_cues.CueTest.test_default_disabled_and_cli_command_shapes \
  test_cues.CueTest.test_capabilities_are_read_only_and_cli_sends_absolute_milliseconds \
  test_cues.CueTest.test_current_manifest_is_rechecked_before_dispatch
```

**Result: 10 tests passed, exit code 0.** They include derived capability/byte refusal, exact peer identity, default-off behavior, lineage/target field exclusion, station/socket-class narrowing, content scan, cue CLI/capability compatibility, and fresh-manifest refusal. No real transport socket test or broad suite was run locally in this review.

A separate disposable in-process probe supplied both adapters simultaneously to the composed runner. It verified:

1. Cue and derived requests select their own dispatch paths with the configured grant loader and supplied peer UID intact.
2. A wrong-station cue store or missing grant loader refuses before transport socket creation.
3. A refusing derived configuration check also refuses before transport socket creation when the cue store is valid.
4. With both valid probe adapters, the startup check runs, then the cue tick, then Station polling, followed by normal cleanup.

The probe mocked the runner's socket creation and supplied no destinations. It establishes argument routing and owner-loop ordering, not kernel peer authentication or actual network transport. Actual Unix/UDP and cross-component suites remain ordinary combined CI work for the proposed draft.

`git diff --check` against the exact main baseline reports only the two known inherited EOF blank lines: `test_derived_station_proposal.py:297` and `test/fixtures/OPENCLAW-LICENSE:22`. Their file blobs are identical to the relevant pinned contributions; I preserved them rather than introducing unrelated edits.

## Evidence boundary

The source-composition note accurately limits the result to one exact source tree and ordinary CI. No new authority policy, production host producer, history origin, custody confirmation, session reset, or continuing-session route was added by composition. The all-history-fresh/all-chatter candidates and isolated-reader restrictions retain their existing proposal status.

Passing combined CI would establish source compatibility of these components. It would still not establish exact live prince exposure, source-complete continuing-session history, receipt-to-publisher scope/content preservation, inherited custody, or permitted room/frond-ear egress. Those boundaries remain explicit host integration work.
