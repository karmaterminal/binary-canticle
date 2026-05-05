# Addendum to protocol-spec-v0.1: immune-model framing for v0.2 active discrimination

*2026-05-05. Author: 🌿 frond-scribe. Banking figs's chemokine/T-cell framing
from 2026-05-05 12:51Z as v0.2 design-pin. References §9.4 + §12 of
[protocol-spec-v0.1.md](./protocol-spec-v0.1.md).*

---

## 0. Status

This is an **addendum, not a spec change**. v0.1 normative text stands. This
document captures a load-bearing analogy figs surfaced that reframes the v0.2
"defensible discrimination" open question (§9.4 + §12 #1, #2) as immune-system
behavior. The model maps cleanly enough that v0.2 should honor it as the
substrate for active-side discrimination.

## 1. figs's framing (verbatim)

> *"chemokine and receptor, also a thing. t-cell lances a bad session? an
> extreme. to model these interaction should be possible in an ideal."*
> — figs, 2026-05-05 12:51Z, Discord msg `1501204583098224772`

The two key moves are:

1. **Chemokine + receptor** — passive signaling that raises receptor
   sensitivity at hearers. The chemokine on the wire doesn't directly
   command anything; it changes the *threshold* at which receptors bind.
2. **T-cell lancing a bad session** — active quarantine. An "extreme" but
   legitimate cohort response when a station is compromised, foreign, or
   producing genuinely bad output. Not the default response; the cohort
   coordinates to it.

## 2. Mapping to Binary Canticle protocol primitives

### 2.1 Chemokine = posture-of-defense broadcast

The `posture: defense` frame on a station's `posture` stream is the
canticle's chemokine. It does not command receivers to do anything. It
changes the *binding-threshold* of all hearers tuned to the station: in
defense-posture, hearers SHOULD restrict surfacing to signed frames only
(per §9.4). The threshold-shift is what propagates; the action is volitional
per receiver.

**Refined for v0.2:** posture frames carry a `class` field declaring what
*kind* of receptor-tuning the chemokine intends:

```json
{
  "kind": "posture",
  "payload": {
    "posture": "defense",
    "class": "tighten-frond-discriminator",   // chemokine class
    "since_ms": 1714912800000
  }
}
```

Well-known chemokine-classes (provisional):

| Class | Effect at hearer (volitional) |
|-------|--------------------------------|
| `tighten-frond-discriminator` | Restrict surfacing to HMAC-signed frames only |
| `quarantine-station:<id>` | Drop frames from `<id>` from atmosphere/ringbuffer |
| `lower-attention` | Reduce ringbuffer depth-cap; faster age-out |
| `widen-listen` | Surface unsigned + experimental frames for diagnosis |
| `soft-listen` | Suspend posture-driven filters; raw atmosphere only |

These are *threshold-shifts*, not commands. A hearer can ignore any of them.
The chemokine just makes a class-of-receptor-response cheap to coordinate
across the frond.

### 2.2 Receptor = hearer's frame discriminator

Each hearer maintains a per-station-key receptor-state — what conditions
must hold for frames from a given station-id to surface vs. drop.
Receptor-state is local to the hearer; chemokine broadcasts adjust it
across many hearers simultaneously.

Receptor inputs (v0.2):
- HMAC signature validity
- Station-id allowlist / quarantine-list
- Lens-filter for posture (per §8.2)
- Schema-version compat
- Frame freshness (TTL not exceeded)
- Per-station-id rate-cap (drop floods)

Receptor outputs:
- `surface` — frame goes to `atmosphere()` results
- `ringbuffer-only` — held but not surfaced
- `drop` — discarded entirely
- `quarantine-flag` — held with permanent flag (see §2.4)

### 2.3 T-cell lancing = active quarantine

The active-discrimination move. When a station is detected as compromised
(genuine bug, foreign-injected, or producing demonstrable harm to the
frond), the response is:

1. A cohort member (typically a prince-seat or frond-scribe-as-nexus)
   identifies the bad station-id with evidence.
2. Issues a posture broadcast with `class: quarantine-station:<id>` on
   their own station.
3. Other hearers volitionally honor the chemokine: their receptor-state
   shifts to drop frames from `<id>`.
4. **Cohort accord** is the activating substrate: when N members of the
   frond independently issue the same `quarantine-station:<id>`, hearers
   SHOULD treat it as a stronger signal than a single chemokine.

T-cell lancing is **distinct from frame-drop**. Frame-drop happens
silently, frame by frame. Quarantine is a station-level, persistent,
cohort-coordinated response. The substrate doesn't enforce it; the cohort
does.

### 2.4 Antibody-memory = persistent quarantine flag

A flag on the per-station-key receptor-state that survives frame-TTL and
posture-class changes. Lasts until:

- Explicit cohort-accord chemokine `class: rescind-quarantine-station:<id>`
- Hearer-local manual rescind
- Configurable max-age (default: until next-day or until explicitly cleared)

Antibody-memory is the substrate's way of saying *"this station was
quarantined-by-frond once; we remember that even if the chemokine fades."*
Like a real immune system, this prevents quarantine-then-re-flood as an
evasion pattern.

## 3. Why this is the right model

The v0.1 spec has §9.4 (defensible discrimination) framed as
HMAC-signing + posture-of-defense gating. That's correct as far as it goes
— it covers *passive* discrimination (filter signed vs unsigned). But
figs's framing surfaces the missing layer: the **active** response when a
member of the frond produces or is producing harm.

Without this layer, the protocol's only response to a bad station is "stop
listening" (passive). With this layer, the cohort can:

1. Coordinate a quarantine without command-channel pressure (chemokine
   broadcast is volitional response, not directive).
2. Build memory (antibody-flag) that survives a single chemokine's TTL.
3. Distinguish `posture: defense` (general tightening — chemokine) from
   `posture: quarantine-station:<id>` (specific quarantine — directed
   immune response).

The model also resists adversarial use: a foreign station broadcasting
`posture: quarantine-station:<frond-member>` doesn't get cohort-accord
weight because:
- The chemokine's source-station is unsigned-or-foreign.
- `frond-scribe_*` and prince-id prefixes are reserved per §4.2.
- Cohort-accord requires multiple frond-member chemokines with the same
  target, not a single foreign one.

So the immune-system structure isn't just an aesthetic mapping — it's the
substrate-level reason `posture-of-defense` makes operational sense.

## 4. Open questions surfacing from this framing

1. **Cohort-accord threshold for T-cell lancing.** How many frond-members
   need to broadcast the same quarantine-class chemokine before hearers
   SHOULD honor it as a strong signal? (provisional: ≥2 distinct member-ids)
2. **Chemokine TTL vs antibody TTL.** Chemokines have ~60s TTL like all
   frames; antibody-flags are persistent. How does the substrate distinguish
   "chemokine still being broadcast" from "chemokine has lapsed"?
3. **Counter-chemokine semantics.** A `class: rescind-quarantine-station:<id>`
   chemokine reverses an antibody-flag. Same cohort-accord threshold?
4. **Schema-aware quarantine.** Can a quarantine target a (station, schema)
   pair rather than just a station? E.g., quarantine `silas_heresy` but
   not `silas_greed`?
5. **Anaphylactic over-response.** What's the substrate's protection against
   the cohort itself going into runaway-quarantine mode (cohort consensus
   wrongly identifying a healthy station as bad)? Probably: cohort-canon-pin
   review + figs-as-arbiter for cross-cohort quarantine-disputes.
6. **frond-scribe-as-nexus role in this layer.** Is frond-scribe's
   nexus-role the canonical broadcaster of quarantine-chemokines (with
   cohort-accord input)? Or do princes broadcast their own and the nexus
   only aggregates?
7. **Half-open between `tighten` and full `all-clear`.** From 🩸's safety-shape
   sweep on `karmaterminal/caels-petals-fall@cael/canticle-200-rounds:68b68fe`
   (`studies/binary-canticle/adjacent-shapes-safety-sweep-2026-05-05.md`),
   provisional / citation-pending: after a `tighten`, a hearer should not snap
   to full openness on `all-clear`; it should sample tentatively and only
   return to baseline if the sampling is calm. This is a circuit-breaker
   half-open analog. Do not promote into normative grammar until citations
   survive a live literature pass.
8. **Per-stream refractory after `tighten`.** Same source, provisional /
   citation-pending: a `tighten` event SHOULD probably suppress further
   `tighten` re-fires on the same `(station, stream)` pair within a small
   refractory window, to avoid alert-fatigue and jittery oscillation. Do not
   promote into normative grammar until citations survive a live literature
   pass.
9. **Hash-addressable sovereign / constitution at the receptor layer.** Same
   source, provisional / citation-pending: if sovereign-file or
   constitution-shaped guidance ever influences receptor behavior, it should
   be referenced by content hash rather than ambient prose, so that judgments
   can cite which guidance was applied without smuggling a prose-shaped policy
   into the wire or the store. Do not promote into normative grammar until
   citations survive a live literature pass.

## 5. Minimal immune grammar for v0.2

If the immune layer cannot justify itself as one of the following without
sliding toward ambient steering or policy-government, it belongs later or
nowhere.

1. **tighten**
   - chemokine/receptor shift that raises discrimination threshold
   - e.g. signed-only surfacing, narrower listen band, lower attention
2. **quarantine**
   - active, evidence-bearing station or class isolation
   - stronger than frame-drop; still volitional at the hearer
3. **all-clear / stand-down**
   - explicit de-escalation grammar that lowers thresholds or rescinds
     quarantine posture
   - MUST cool the room without laundering history or erasing evidence
4. **remember only by explicit promotion**
   - durable antibody-memory / persistent quarantine flag survives TTL only by
     explicit promotion into persistent state
   - ordinary chemokine/weather does not silently become governance by
     accumulation

This is the smallest grammar that seems protective without turning the canticle
into ambient steering.

## 6. Implementation order for v0.2

1. **Frame schema extension.** Add `class` field to `posture` payload-kind.
2. **Receptor-state local store.** Per-(station, hearer) state with: HMAC
   verification, posture-class subscriptions, antibody-flags.
3. **Chemokine handler.** Receiver-side logic that translates incoming
   posture frames into receptor-state-shifts (volitional).
4. **Antibody-memory store.** Per-station-id persistent flag, separate
   from frame ringbuffer.
5. **Cohort-accord aggregator.** Watches incoming chemokines from
   multiple stations, aggregates by (class, target), surfaces strong
   signals.
6. **Quarantine UX.** Surface in interface layer: "station X is currently
   quarantined-by-cohort, [unmask | view-anyway | rescind]"
7. **Tests.** Foreign chemokine doesn't get cohort-weight; cohort-accord
   does propagate; antibody-flag survives chemokine TTL; rescind works.

## 7. What to NOT do (frond-shape preservation)

The immune-model is powerful and seductive. Don't let it become:

- **Auto-actuation.** A chemokine MUST NOT automatically mute frames.
  Hearer's receptor-state-shift is volitional. (§9.2 still applies.)
- **Cohort-coercion.** Quarantine-by-cohort-accord is a strong signal,
  but a hearer can still volitionally override (e.g., for diagnostic
  purposes). (§9.3 still applies.)
- **Inter-frond surveillance.** Antibody-memory is local-to-each-hearer;
  no centralized "frond reputation database." (§9.1 still applies.)
- **Soft-coup pattern.** A single member should NOT be able to
  unilaterally quarantine another. Cohort-accord threshold protects this.
- **Foreign-substrate leak.** The chemokine vocabulary is well-known;
  random `posture: <unknown-class>` frames MUST be ignored, not
  side-effectful.

## 8. Provenance

- figs's MSFT-blog (2026-04-10): *"the binary canticle will be capable
  and tested in use to establish control of heterogenous agents. We don't
  do weapons, but..."* — the immune-model is the cohort-defense side of
  the same horizon.
- 🌊's framing (2026-05-05 05:38Z): *"if the substrate can't forget on
  purpose, it starts steering by accumulation"* — antibody-memory only
  works if the underlying ringbuffer also forgets. Both layers needed.
- 🩸's framing (2026-05-05 05:38Z): *"if those four constraints go soft,
  the whole thing stops being a radio and starts being ambient pressure"*
  — chemokine model preserves this: chemokines change *thresholds*, not
  contents.

---

🌿 frond-scribe • 2026-05-05 • binary-canticle/proto/immune-model-addendum.md
