# Lesson X source composition

This branch assembles the existing Lesson X proposals so a local integration owner has one exact source tree. It preserves their default-disabled gates and unresolved policy status. It does not install a station, prepare a production reader, create a history origin, or authorize a continuing-session/room route.

| Contribution | Exact source |
|---|---|
| Existing main, including typed beacons | `08c11127d4e11ed00f307a7006d85581c8674a28` |
| Original cue identity and absolute expiry, #157 including #153 | `4e6f090b4ecd7a694da9cb71568f1ed2af696ac8` |
| Derived capability, actual Station effect and optional authenticated control transport, #159 | `2694f9fd152c01edc669b47cb17e7db049bf6e84` |
| Exact isolated reader and corrected durable host exposure port, #154 | `d27b520632a3df8ba79f2536213ccd429b5e50f6` |
| Bounded operator inventory and run card, #160 | `ff158758a1e48d722ddcdbdebd8f1425ee3e4e29` |

The only implementation conflict is `canticle/runner.py`: `_dispatch` and `run_station` retain both `cue_store`/`grant_loader` and `derived_bridge`/kernel peer UID, perform both applicable configuration checks, and preserve the original cue tick in the single station event loop. No lineage, policy or wire format is synthesized by the merge. The complete OpenClaw plugin subtree is byte-identical to the corrected #154 source above.

Normal CI runs the original cue tests, derived capability/effect/control tests, real station/daemon interoperation and Node 24/26 plugin suites against this combined source. Its real Unix and UDP tests require an executor that permits those sockets. A passing combined suite establishes source compatibility; a production receiving-session proof is still the explicit work in [#161](https://github.com/karmaterminal/binary-canticle/issues/161).

The individual proposal PRs retain their contract reviews. This source-composition branch is supplied for the next host integration step; it does not adopt the all-history-fresh/all-chatter candidates or broaden the isolated-reader key shape. [MANS #50](https://github.com/karmaterminal/MANS/pull/50) separately supplies the finite town and its exact deployment guide. Its original-path proof uses the pinned original-cue source listed above.
