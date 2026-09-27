# RFC-0001 review notes

Evidence behind [`../0001-binary-canticle.md`](../0001-binary-canticle.md) and
[`../../reports/2026-09-27-survey-and-path.md`](../../reports/2026-09-27-survey-and-path.md).
RFC-0001 cites these as `review/<note> §x`.

These are working notes from the 2026-09-27 review, kept as written. They carry
path:line citations against `main` @ `b46a45a` and the other refs named inside
each note. Where a later check corrected a note, the RFC and report carry the
correction and the note does not. One example: the beacon-rotation threshold is
about 26-27 streams, not 180. Treat the RFC as authoritative and the notes as
the trail.

`<review-sandbox>/…` paths refer to the ephemeral review environment and are
not in this repository. The one exception is the ringserver proofs, which
landed as [`prototype/ringserver-proofs/`](../../prototype/ringserver-proofs/).

## Readers (what exists)

| Note | Covers |
|---|---|
| [`spec-core.md`](spec-core.md) | v0.1 spec, stations-and-streams v0.2 and byte-walk, receptor contract, ringbuffer contract. Covers the three wire formats, the decisions and contradictions between them, and the missing loop. |
| [`spec-periphery.md`](spec-periphery.md) | README, TASK-BRIEF, INDEX, workboard, immune model, loop-soothing, non-goals, scope ladder, and the three OpenClaw boundary docs. Covers staleness and plane-model drift. |
| [`spikes.md`](spikes.md) | The four `spike/silas-*` spikes (graded), the June spikes, the owner's carrier-wave notes and the references (including the unannotated `2510.03215v2.pdf` = Cache-to-Cache). |
| [`issues.md`](issues.md) | All 42 issues and 63 comments: dispositions, clusters, and the key threads (#30, #48, #51). |
| [`prs.md`](prs.md) | Open PRs #50, #44, #34, #32, #29 and branch `ronan/20260614/send-receive-threshold-landing`, with diffs and draft comments. |
| [`prototype.md`](prototype.md) | `prototype/ringserver-udp-cue`: architecture, wire format, defects B1-B6, and the native ringserver/DataLink proof. |
| [`openclaw-rfc.md`](openclaw-rfc.md) | OpenClaw continuation RFC (gates branch), enrichment seams in code, and Claude Code equivalents. |
| [`seedlink-dash.md`](seedlink-dash.md) | SeedLink v3/v4 and miniSEED 2/3; ringserver; the ews-concept-new data path and the `need 47, found 6` root cause; nerv-ui inventory. |
| [`transport.md`](transport.md) | LAN multicast reality, NAT and internet listeners, amplification, HAProxy (community has no generic UDP), DNS-SD, and per-frame auth. |

## Decision baseline

| Note | Covers |
|---|---|
| [`spine.md`](spine.md) | Positions P1-P15 and decisions D1-D10 that the report and RFC were written against. Deviations are marked in both documents. |

## Adversarial challenges (what should change)

| Note | Covers |
|---|---|
| [`challenge-broker.md`](challenge-broker.md) | Steelman of "just use a broker": a 13-system fit matrix, measured NATS/UDP/Zenoh experiments, and build-vs-borrow per layer. Scripts and raw results are in [`brokerx/`](brokerx/). |
| [`challenge-redteam.md`](challenge-redteam.md) | Threat register T1-T16 (the signed re-sing worm first), controls, the Never list, use-case verdicts and red-team tests. |
| [`challenge-bio.md`](challenge-bio.md) | Biology and radio metaphors mapped to mechanisms, parameters and tests. Also covers "rate is not intensity", the loop regulator and MAGI aspect streams. |

## Artifacts

- [`vec/frame_v2_sizes.py`](vec/frame_v2_sizes.py) and [`vec/sizes.out`](vec/sizes.out) generate the frame v2 size budget and the illustrative test vectors in RFC §9.11. They need `cbor2` and `pynacl`.
- [`brokerx/`](brokerx/) holds the control experiment: the same carousel over raw UDP plus a minimal relay, over NATS core, and over Zenoh, plus the JetStream TTL-at-hop probe (`exp_js.py`). The build caches, venv and binaries are not included; `run_compare.sh` expects `./bin/nats-server` and `./venv`.

## Errata (found by the fact-check passes; the RFC and report carry the corrections)

- `openclaw-rfc.md` §S2: `POST /hooks/wake` with `mode:"next-heartbeat"` plus a caller-chosen `sessionKey` is **not** a silent landing. A `sessionKey` requires `mode:"now"`, which always wakes (`src/gateway/hooks.ts:290-291` on the gates branch, `:282-283` on `main`). `next-heartbeat` lands only in the agent's main session.
- `seedlink-dash.md`: the ews open-proxy citation `src/routes/api/fdsn/station/+server.ts:82-97,112-131` is wrong at `c5134cb`; the file is about 70 lines and the correct range is `:5-10,35-66`.
- `seedlink-dash.md`, `prototype.md`: "ringserver sends miniSEED3 unconverted to SeedLink 3.x clients" holds for 4.5.4 only. From 4.5.5 ringserver skips miniSEED3 records for 3.x clients (ChangeLog v4.5.5).
- `seedlink-dash.md`: the exact `need 47, found 6` string was reproduced from synthetic 526-byte and 14-byte messages built from real packets. The live proxy run produced `found 4` and a RangeError (see proof 06).
- `spine.md` P3: the "beacon overflow above ~180 streams" figure assumed v0.2's 8-byte entries. With frame-v2 stream entries, rotation starts at about 26-27 streams (RFC-0001 §8.4).
- `spine.md` P11: the Tier B idempotency key must include `stream_id` (`canticle:<key_id>:<epoch>:<stream_id>:<seq>:<sessionKey>`), because `seq` is per stream (RFC-0001 §16.4).
