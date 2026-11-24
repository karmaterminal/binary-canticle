# Verification of the `_pick` turn-loss finding

**Date:** 2026-11-24

**Verdict: CONFIRMED**

`a0862c3` contains the turn-loss mechanism described for
[karmaterminal/binary-canticle#173](https://github.com/karmaterminal/binary-canticle/issues/173).
The lane's fix at `fcb4359` changes `_pick` and `KeyQueue.pick` to retain passed
keys and streams for the same turn. The exact wall-clock row-J numbers
392/784 at K=64 and 313/784 at K=16 were reported by the lane, but this
read-only verification did not repeat that timed socket row.

## Named refs

| category | ref | full SHA | local | tracking | server |
|---|---|---|---|---|---|
| product/base | issue head | `a0862c3eeb0b84236661451ca5c3d00127536d27` | N/A; detached worktree `/tmp/bc-a0862c3` | N/A | N/A |
| product/base | lane recovery head | `fcb4359db29c7c565c605cfb167b897c31042f30` | `HEAD`, lane worktree | origin recovery name resolved equal | origin recovery name resolved equal |
| lane/safe branch | `codeagent/bc-173-pick-verify` | `fcb4359db29c7c565c605cfb167b897c31042f30` before report commit | equal | equal | equal |
| CI/workflow | N/A | N/A | N/A | N/A | N/A |
| presentation | N/A | N/A | N/A | N/A | N/A |
| docs/proof | this report | to be set by pushed commit | report branch | report branch | report branch |

The lane branch was published unchanged before the identity gate. It resolved
equally in the local worktree, `origin/...`, and `ls-remote origin` before
report files were added.

## Environment

- Python: 3.12.3
- cryptography: 50.0.1
- virtual environment: `~/.venvs/bc-fair`
- All runs used `nice -n 19`, no flood/timing/measurement row, and a single process.
- Detached worktrees: `/tmp/bc-a0862c3` and `/tmp/bc-fcb4359`.

## Lane reproduction and row J

The lane's own reproduction is declared in
`reports/measurement/2026-11-24-newcomer-recovery/PLAN.md`, lines 207-215.
Row J is:

- 16 stations; four established stations (`quiet`, `x0`, `x1`, `x2`) sing 57
  items each, 150 ms apart;
- flood: half junk datagrams and half forgeries of the 12 other keys;
- 40 fixed ports, 20,000/s and 100,000/s, 13.6 s;
- 784 offered established frames (4 * 196).

The numeric claim for `a0862c3` in the PLAN and
`04e9945`'s commit is 392 of 784 lost at K=64 and 313 of 784 at K=16.
The implementation that sent row J is
`reports/measurement/2026-11-24-newcomer-recovery/junk_rows.py` and
`forged_flood.py`; those are wall-clock/socket paths and were not run under
this read-only virtual-time workorder.

## Source finding

At `a0862c3`, `KeyQueue.pick` in `prototype/canticle-station/canticle/intake.py`
rotates each stream before trying it, but returns only a frame or `None`
(`intake.py:326-341`). If no stream can be served, `_pick` continues by
rotating the key deque (`intake.py:659-672`). A key or stream passed over
therefore rotates behind work that is served meanwhile.

The same turn-loss path exists at the key and stream composition boundary:

- `KeyQueue.pick` scans streams, rotating each one before it is checked
  (`intake.py:328-332`).
- `_pick` rotates `_ready` before selecting a key (`intake.py:660-667`).
- A key that cannot be served because the checks bucket or stream/key bucket
  is not ready is merely rotated and left in the deque; it is not explicitly
  held at the front for the next pass.

At `fcb4359`, the fix preserves the passed-over turn:

- `KeyQueue.pick` iterates a snapshot of streams and the comment states that
  a stream that cannot be served keeps its turn
  (`intake.py:485-499`).
- `Intake.take` collects passed keys in `_passed`
  (`intake.py:835-853`) and `_pick` removes them from `_ready`, remembers
  that they could not be served, and restores them at the front before the
  next pass (`intake.py:883-905`).
- The fixed scheduler comment explicitly says that a key that cannot be served
  now keeps it (`intake.py:884-885`).

This is the same invariant named in the lane's commit
`04e9945b6c4f234b5d5b7e85edb874a7e24ca315`: passed-over keys and streams keep
their turns rather than rotating behind work served meanwhile.

## Minimal reproduction

Scratch file:
`reports/measurement/2026-11-24-pick-verify/pick_virtual.py`

It uses `Intake`, `KeyQueue`, `StreamQueue`, and `Bucket` APIs present in both
checkouts. It is a virtual-time, no-socket, no-signature negative control for
the scheduler boundary:

1. create a three-key manifest;
2. make one key's stream bucket exhausted and queue a frame for it;
3. queue a frame in another key;
4. call `take(1)` repeatedly and record which key is returned.

Commands:

```sh
cd /tmp/bc-a0862c3
PYTHONPATH=/tmp/bc-a0862c3/prototype/canticle-station nice -n 19 \
  ~/.venvs/bc-fair/bin/python \
  /home/figs/flesh_beast_best_beast/source/WORKTREES/binary-canticle-bc-173-pick-verify/reports/measurement/2026-11-24-pick-verify/pick_virtual.py \
  /tmp/bc-a0862c3
```

```sh
cd /tmp/bc-fcb4359
PYTHONPATH=/tmp/bc-fcb4359/prototype/canticle-station nice -n 19 \
  ~/.venvs/bc-fair/bin/python \
  /home/figs/flesh_beast_best_beast/source/WORKTREES/binary-canticle-bc-173-pick-verify/reports/measurement/2026-11-24-pick-verify/pick_virtual.py \
  /tmp/bc-fcb4359
```

Both minimal runs returned one ticket for the blocked key and one ticket for
the served key in the small sequence, so this deliberately tiny control is not
a row-J count. It also did not prove the exact 392/313 totals.

## Independent test receipt

The lane's added fixed test module passed two matching `_pick` tests:

```sh
cd /tmp/bc-fcb4359
PYTHONPATH=prototype/canticle-station \
  ~/.venvs/bc-fair/bin/python -m unittest discover \
  -s prototype/canticle-station/tests -p test_intake.py -k passed_over -q
```

Receipt: `Ran 2 tests ... OK`.

The base checkout has no `test_a_key_or_stream_that_is_passed_over_keeps_its_turn`
test at `a0862c3`; it was added in `e23d413` as a RED test. The test itself
states the invariant and runs 20 turns: an established station is served while
strangers spend checks, and the first served frame for the waited key must be
`waited == 0`. This is deterministic evidence of the mechanism and not a
socket/flood timing result.

## Result

`CONFIRMED`: `a0862c3` has the `_pick`/stream/key turn-loss mechanism. The
lane fix changes that mechanism at `fcb4359`, retaining passed-over keys and
streams.

The exact reported K=16 and K=64 784-frame counts are **lane measurements,
not independently reproduced in this pass**. This report therefore confirms
the mechanism and the red invariant, while recording that exact quantitative
392/313 equivalence is not a receipt from this verification.
