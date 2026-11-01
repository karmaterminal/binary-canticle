# Review: binary-canticle #126

**Scope:** read-only review of PR #126, `feat/mirari-local-beacon`, against its PR base `main`.

## Named refs

| category | ref | resolved SHA | equality receipt |
|---|---|---|---|
| product/base | PR #126 base ref `main` | `5274f0f6bcb0de59fbd5f3d70232f8cce9502cc3` | local/base commit; `gh api` reports this SHA |
| product/head | PR #126 head `karmaterminal:feat/mirari-local-beacon` | `65a0f9acd24ce3be377e4e2bbaf9ba278dc7ae06` | local `HEAD`, `origin/feat/mirari-local-beacon`, and server `git ls-remote` agree |
| lane | `codeagent/bc-review-mirari` | `65a0f9acd24ce3be377e4e2bbaf9ba278dc7ae06` | unchanged lane branch published; local, tracking, and server refs agree |
| CI/workflow | repository `.github/workflows/tests.yml` on resolved base | blob `6e64f187354f38e490d942ac90ef08977651d990` | Git blob SHA agrees with `gh api`; focused tests only |
| presentation | N/A | N/A | N/A |
| docs/proof | N/A | N/A | N/A |

## Verdict summary

| PR | Branch/base | Verdict | Reason |
|---|---|---|---|
| #126 | `feat/mirari-local-beacon` / `main` | **REQUEST_CHANGES** | The fixture can emit indistinguishable normal `wake/chatter/LAN` items to a real station control socket and has no in-band or stream-level fixture identity. |

## Findings

### #126

1. **BLOCKER — Fixture is not distinguishable from a real station item**
   - `prototype/mirari-wake/beacon.py:137-140`
   - The emitter uses the existing station control socket to send `{"stream":"wake","class":"chatter","scope":"lan","text":"actor alice; observed ...","state_key":"wake-..."}`. There is no fixture-only stream, fixture marker in the text, fixture-specific state key namespace, or manifest/control-socket identity check.
   - Concrete failure: an operator authorizes a real station socket and sends an ordinary-looking item; a receptor admits and presents it exactly like a real wake item. The README labels this as a fixture (`prototype/mirari-wake/README.md:1-3`) and says no live station is contacted for tests, but that does not prevent a fixture item from reaching a real station at runtime.
   - Suggested fix: require a fixture-only stream or a conspicuous, unforgeable fixture marker in every signed item and reject publishing to a non-fixture manifest/control target. Add a test that the published request necessarily carries the fixture identity and that a normal production station/socket is refused.

2. **MEDIUM — Conflicting duplicate IDs are silently resolved as the last row**
   - `prototype/mirari-wake/beacon.py:83-86`, `prototype/mirari-wake/beacon.py:92-97`
   - `read_rows` checks only the persisted `seen` set. It does not add an accepted ID to a per-batch set, so two rows with the same ID but different topics enter `rows`. `summarize` then silently keeps the last value in a dict and publishes that topic.
   - Concrete failure: input rows `id=step1 topic="checked tests"` and `id=step1 topic="deploy production"` in one source batch produces one item labeled `deploy production`, even though duplicate input should be rejected, never guessed.
   - Suggested fix: maintain `batch_seen` during `read_rows`; fail the whole read on a conflicting duplicate ID or on any repeated ID after the first. Add a deterministic test with the same ID and different topics that asserts no station submission and no checkpoint advance.

3. **MEDIUM — Source digest and emitted batch are read from separate snapshots**
   - `prototype/mirari-wake/beacon.py:61-89`, `prototype/mirari-wake/beacon.py:92-97`
   - `read_rows` reads and filters source lines, then `summarize` separately calls `source.read_bytes()` for the lineage digest. A concurrent append or replace can occur between the two reads.
   - Concrete failure: source is changed after `read_rows` has selected a batch but before `summarize`; the item publishes labels from the first snapshot but a digest and identity from the later snapshot. The checkpointed batch then does not describe the provenance actually claimed by the wire text.
   - Suggested fix: read the bounded source bytes once in `tick`, verify/derive rows and digest from that same snapshot, and reject a source change detected by stat or snapshot identity. Add a focused deterministic test that replaces the source between snapshot and digest reads and asserts no publish.

4. **MEDIUM — Checkpointed `seen` state has no retention or byte ceiling**
   - `prototype/mirari-wake/beacon.py:127`, `prototype/mirari-wake/beacon.py:142-144`
   - `seen` grows by every newly observed stable ID and is written as a sorted list on every accepted batch. The source is capped at 1 MiB and a batch to 16 rows, but neither the source nor the state has a hard seen-ID count or state-byte ceiling.
   - Concrete failure: a continuously active fixture contributes unique IDs indefinitely; the process and state file grow without bound, and `_save` repeatedly rewrites a larger JSON document while line membership becomes increasingly expensive.
   - Suggested fix: impose a bounded seen history (count and byte cap), or derive dedupe from a bounded window plus source offset and fail loudly when the cap cannot be represented. Add a restart test that verifies the state does not exceed the stated bound and the nearest rollover/eviction behavior is deterministic.

## Tests and coverage

- Focused local proof passed: `prototype/mirari-wake/test_beacon.py` and `prototype/mirari-wake/test_integration.py`: 6 tests, OK.
- Focused OpenClaw interop proof passed: the Mirari mute/manual-read/revocation/untuned test and the existing real-daemon interop test, 2 tests, pass.
- The PR tests cover revocation, inactivity, source redaction, sink/checkpoint retry, loopback signed publication/expiry, mute, and untuned binding behavior.
- Missing coverage for the findings: conflicting same-ID rows, source snapshot/digest race, state/`seen` bounds, and a production-target vs fixture-target reject/identity assertion.

## Validation receipt

- **CI path:** focused-only; repository unit tests for touched Python and OpenClaw interop surfaces, as this workorder prohibits broad suite acceptance.
- **Focused commands:**
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../canticle-station python3 -m unittest test_beacon.py test_integration.py` (6 OK)
  - `cd prototype/openclaw-canticle && node --test 'test/interop.test.ts'` (2 pass)
