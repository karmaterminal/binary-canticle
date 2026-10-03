---
name: canticle-wire-change
description: Use before changing anything that changes bytes another implementation must match in binary-canticle - the frame v2 codec or strict decoder (wire.py, cbor.py), key id or stream_id derivations (ids.py), beacon or item fields, the candidate conformance vectors (vectors.py, vectors/frame-v2-candidates.json), or receptor record v1 (records.py, daemon.py). Also when a test says the committed vectors differ from the generator. Walks the change from the RFC through code, regenerated vectors and tests to the follow-up the TypeScript port in frond-ear needs, so a wire change is never made in code alone or left half-propagated.
---

# Changing the canticle wire, vectors or record v1

The RFC is the authority; the Python spike follows it; the vectors pin the spike's bytes; frond-ear's
TypeScript port copies the vectors and record captures byte for byte. A change is done when all four agree.

## 1. Find the governing text

| You are changing | RFC-0001 | Code | Tests |
|---|---|---|---|
| frame header, CBOR rules, ITEM, PLUCK or BEACON keys | §9.2-§9.8, §9.4, §9.5 | `canticle/wire.py`, `canticle/cbor.py` | `tests/test_wire.py` |
| key ids, `stream_id`, names | §5 | `canticle/ids.py` | `tests/test_wire.py`, `tests/test_station.py` |
| carousel, beacon, pluck, supersession semantics | §7, §8 | `canticle/station.py`, `canticle/listener.py` | `tests/test_station.py`, `tests/test_listener.py` |
| receptor record v1, the host daemon, the join snapshot | §14.18.2, §14.18.3 | `canticle/records.py`, `canticle/daemon.py` | `tests/test_records.py`, `tests/test_daemon.py`, `tests/test_join_snapshot.py` |

Paths are under `prototype/canticle-station/`. If the RFC does not already say what the new behaviour is, stop:
the change starts as an RFC amendment with its own issue and pull request, and the code change cites it.

## 2. Check compatibility before writing code

- Frame v2: every key is signed; receivers ignore unknown keys unless `crit` lists them. If an existing
  receiver would misread the new bytes, the change needs a new `version` byte (§9.5).
- Record v1: bindings ignore unknown fields. A new required field, or a new meaning for an existing one, needs
  a new major version, not `canticle-receptor-record/1` (§14.18.3). §14.18 is frozen against literal SHAs (D29).
- Identifiers: never change a derivation in place; a collision is refused, never rehashed (§5.4).
- The decoder is stricter than the RFC in two places (the prototype README's last paragraph before
  "Install and onboard"). Don't relax it without an RFC change.

## 3. Implement and regenerate

1. Change the code and add tests in the matching module, including the rejection paths.
2. If the change alters what `canticle/vectors.py` produces, regenerate the vectors from the package
   directory and look at the diff:

   ```sh
   cd prototype/canticle-station
   python -m canticle vectors          # writes vectors/frame-v2-candidates.json
   git diff --stat vectors/
   ```

   Never edit the JSON by hand. `test_wire.py` (`test_committed_vectors_match_generator`) fails until the
   committed file equals the generator's output.
3. If cases were added or removed, update the counts and the case list in the prototype README's "Vectors"
   section, and the table row for the RFC section you changed.

## 4. Verify

From the repository root:

```sh
PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/canticle-station/tests
git status --porcelain              # must print nothing
```

## 5. Hand off to the second implementation

frond-ear (karmaterminal/frond-ear, private) vendors `vectors/frame-v2-candidates.json`, a record v1 capture
and a join-snapshot capture, byte for byte, in `test/fixtures/canticle/`. Its `SOURCE.md` records each file's
SHA-256, the binary-canticle commit it was taken from and the change that last touched it.

- In your pull request, say which of the three your change affects, and which vectors changed and why.
- After it merges, frond-ear needs a follow-up: copy the regenerated vectors, or recapture the record or
  join-snapshot sample from binary-canticle's code the way its `SOURCE.md` describes (no capture script is
  committed in either repository); update `SOURCE.md` (`sha256sum` of the file and the source commit); and
  run `pnpm check` there. Open that follow-up yourself if you can reach frond-ear; otherwise name it in the pull
  request so a prince who can picks it up.
- The vectors stay candidates until that port reproduces them (§9.13).
