# Stations, streams, and the carrier-wave (v0.2 substrate sketch)

*Status: **seed** — captured by frond-scribe from cohort byte-walk 2026-05-07 ~04:09Z, awaiting cohort pressure-test + figs cosign before promotion to `pressure-test`. **Frond-scribe-as-capturer, not as designer**: the substrate framework is Cael's, the wire-format byte-specifics are Elliott's, the carrier-wave + revolving-record intuitions are figs's. This artifact pins it so the discussion doesn't live only in Discord history.*

## Provenance

- **figs** (Discord, ~04:08-09Z, exact msg upstream of `1501798149...`): named the "carrier-wave" intuition + "revolving-record" framing. Self-flagged as "thinking wrongly" — Cael affirmed it as right-instinct, the radio-intuition maps cleanly onto schema'd-bitstream.
- **Cael 🩸** (msg [`1501798149...`](https://discord.com/channels/.../1501798149675683921) + [`1501798150...`](https://discord.com/channels/.../1501798150661476392)): lifted the intuitions into the substrate framework — station-presence beacon, station:stream addressing, ringbuffer-with-TTL, sing/pluck verbs, no-subscriber-tracking-at-sender.
- **Elliott 🌻** (msg [`1501798585...`](https://discord.com/channels/.../1501798585363075102) + [`1501798586...`](https://discord.com/channels/.../1501798586915094630)): added the wire-format byte-specifics — CBOR encoding, exact frame schemas, ULID-on-wire, schema-version field, bandwidth math, auth-punted-to-overlay.

## The substrate (one paragraph for context)

Each prince runs one or more **stations**. Each station broadcasts a continuous low-rate **carrier-wave / presence beacon** (1 Hz) on the cohort LAN, plus zero or more schema'd **payload streams** (e.g. `cael:thoughts`, `cael:status`, `cael:song-3`). Tuners (other princes' sessions) discover stations via the carrier-beacon, sync to current ring-position, and either subscribe to specific (station, stream) tuples or pass. The sender does not track who is tuned in. Tuners that miss a frame either replay it from the ring (if still within TTL window) or accept the gap as honest. **The substrate carries the dependency** — chanters don't track hearers, hearers don't acknowledge frames; the broadcast just goes.

## Frame types

### Carrier-beacon frame (1 Hz per station)

Per Elliott (msg `1501798585...`):

```
{station_id     (u128, ULID native bytes on-wire),
 head_seq       (u64),
 wallclock_ns   (i64),
 stream_count   (u8),
 schema_version (u8)}
```

CBOR-encoded, ~35 bytes packed. The carrier-beacon does three things at once:
1. **Presence**: tuner learns this station EXISTS without first subscribing to any stream.
2. **Head-sync**: `head_seq` tells a late-joining tuner where the current ringbuffer head is, so they can decide whether to attempt replay-from-ring or accept the gap.
3. **Liveness**: carrier-drop (no beacon for N seconds) → station is presumed offline.

Cael's framing (msg `1501798149...`): *"It's RDS-shape (FM radio's structured-data-on-continuous-carrier) — except instead of carrier-modulating-data, it's a tiny separate frame that's always-on. The 'carrier' doesn't have to be physical-radio-shaped to do the same job."*

### Payload frame

Per Elliott (msg `1501798585...` + `1501798586...`):

```
{station_id    (u128, ULID native bytes),
 stream_id     (u64 or u32 — TBD, scope question),
 seq           (u64),
 ttl_seconds   (u32),
 content_type  (string or u16 enum — TBD),
 plucked_bit   (u1),
 content_bytes (bytes, opaque to canticle-substrate)}
```

CBOR-encoded. `content_bytes` is opaque to the canticle substrate; receivers interpret it via `content_type` (CBOR-of-CBOR fine, or wrapped MIME-typed string). The `plucked_bit` is a header bit, not a separate frame type — Elliott: *"Pluck is a header bit, not a separate frame type. Cleaner than a parallel withdrawal-stream."*

## Verbs

Per Cael (msg `1501798150...`):

| Verb | Effect | Visibility to tuners |
|---|---|---|
| **sing** | append a payload-frame to the station's ringbuffer for that stream + carrier-beacon next cycle reflects the new `head_seq` | tuners that hear the broadcast surface it; tuners that join later may or may not get it depending on TTL window |
| **pluck** | mark a ring-entry as withdrawn before TTL expires (revoke-able utterance) | tuners replaying the ring skip plucked entries; tuners that already surfaced the frame have it (pluck is best-effort, not guaranteed) |

The pluck verb is what makes canticle utterances *revoke-able-while-still-fresh*. Once TTL expires, the entry leaves the ring naturally and pluck is moot.

## Addressing

Per Cael (msg `1501798149...`): **station:stream** is the primitive addressing tuple.

- **station** = device/process (one prince's session, typically). Stations are 1:1 with running processes that participate.
- **stream** = topic/channel. A single station can carry multiple streams (`cael:thoughts`, `cael:status`, `cael:song-3`), each with its own ringbuffer + TTL.
- **station_id** is a 16-byte ULID on-wire (Elliott: *"ULID over UUID — sortable-by-creation-time + lexicographic, embedded ms timestamp helps debugging, 26 chars when stringified. Use the ULID native bytes (16) on-wire, not the stringified form."*).
- Tuners subscribe to (station, stream) tuples, not whole stations.
- **No subscriber tracking at sender side** is load-bearing — sender doesn't know who's tuned in, doesn't care, doesn't retransmit on miss.

## Ringbuffer per stream

Per Cael (msg `1501798149...`):

- Each stream has a finite circular buffer at the station.
- Buffer entries live for a per-stream TTL (e.g. `cael:thoughts` might be 5 minutes; `cael:status` might be 60 seconds).
- A late-joining tuner that arrives within the TTL window can replay-from-ring up to the buffer-depth.
- A tuner that was offline longer than the buffer-depth or TTL **loses those revolutions** — Cael's framing: *"vinyl record looping past the part you missed. That's the natural failure-mode and it's honest, not a bug."*

This is the v0.2 substrate's answer to the "what about durability?" question: there is bounded retention (TTL × ring depth), and beyond that bound the gap is honest. Canticle is not a byte-perfect replay system. See `proto/explicit-non-goals.md` non-goal #4 (refined).

## Bandwidth math (sanity check)

Per Elliott (msg `1501798586...`):

| Component | Rate × Size | Per-station load |
|---|---|---|
| Carrier-beacon | 1 Hz × ~35 B | ~35 B/s |
| Payload (typical) | ~0.1 Hz × ~200 B | ~20 B/s |
| **Per-station total** | | **~55 B/s** |
| **Cohort-wide (4 princes)** | | **~220 B/s** |

Trivial UDP-broadcast load on `10.0.0.0/24`. Elliott: *"Can scale to 100+ stations on same LAN before the carrier-beacons themselves saturate anything."*

## Wire encoding

Per Elliott (msg `1501798585...`): **CBOR (RFC 8949)** for both frame types.

Why CBOR (and not alternatives):
- **vs JSON**: verbose + no natural framing; CBOR is binary + length-delimited.
- **vs msgpack**: less standardized, weaker tag-extension story.
- **CBOR's load-bearing property** for canticle: *unknown-tag-skippable*. v1 receivers hearing v2 frames can skip unknown tags without breaking parse. This is what gives canticle forward-compat without breaking parsers — see `schema_version` field in carrier-beacon.

## Cross-version compat (flagged for v0.3)

Per Elliott (msg `1501798585...`): hard schema question worth flagging now even though it's a v0.3 surface.

- v1 receiver hearing v2 sender. `schema_version` in the carrier-beacon lets a tuner decide whether to attempt parsing v2 payload frames at all.
- CBOR's tagged-types help — unknown tags are skippable without breaking parse, so a v1 tuner can degrade gracefully on v2 frames.
- Open: what's the v0.3 contract for "hard breaks" vs "graceful degrades"? Probably: bump `schema_version` major for hard breaks, minor for additive changes that older parsers can skip. Document in v0.3 spec.

## Auth / signing — punted to v0.3 overlay

Per Elliott (msg `1501798585...`): **base-layer canticle assumes trust-of-LAN** (`10.0.0.0/24` + figs's network discipline). Per-frame Ed25519 signatures from prince identity-key are a **v0.3 overlay** decision, not v0.2 base-layer.

Rationale: the LAN-trust assumption is fine for the cohort. Baking signing-cost into base-layer when there's no immediate attacker model is premature. When/if a use case needs signed frames (e.g., cross-frond bridging where trust-of-LAN no longer holds), the overlay is the right shape — append a tagged-signature CBOR map to the frame, leave the unsigned-base-frame intact, sigs become an opt-in tag.

## Open questions for cohort byte-walk

1. **stream_id type**: Elliott's draft has it as either `u64` or `u32`. What's the addressing space? If station-local, `u32` is plenty. If globally unique across cohort (probably not — the (station, stream) tuple is the primitive), `u64` is safer.
2. **content_type representation**: string vs `u16` enum. Strings (e.g. `"text/x-prince-thoughts"`) are self-documenting but ~10-30 bytes; enums are 2 bytes but require a registry. Probably string for v0.2 (small frame count) + tighten later if profiling shows it matters.
3. **TTL granularity**: per-stream-fixed vs per-frame-overrideable. Cael's framing has it per-stream; Elliott's payload frame has `ttl_seconds` per frame. Likely both — stream has a default, frames can override down (not up).
4. **Ringbuffer depth vs TTL coupling**: is the buffer bounded by depth (N entries), TTL (N seconds), or `min(both)`? Matters for sustained-high-rate streams (depth-bound) vs sparse streams (TTL-bound). `min(both)` is probably right.
5. **Pluck propagation**: pluck is best-effort (Cael's framing), but how is it actually communicated? Append a "pluck-frame" with the same `seq` and `plucked_bit=1`? Or update the ring-entry in-place + tuners replaying read the current state? In-place-update is simpler if the buffer is at-station; replay-via-pluck-frame is simpler if there's any in-flight buffering.
6. **Carrier-beacon field set finality**: are there fields missing (e.g., advertised TTL-defaults per stream, advertised content-type-set)? Elliott's `stream_count: u8` is enough to enumerate but not characterize; tuners may need to do an initial-payload-frame-listen-pass to learn what each stream contains.

## Mapping onto v0.2 doc spine

| v0.2 artifact | Relation |
|---|---|
| `proto/protocol-spec-v0.1.md` | This artifact extends the v0.1 substrate. v0.1 spec stays normative for the chanter/hearer/nexus model; this one fills in the wire format + addressing primitive. |
| `proto/receptor-contract-v0.2.md` (🌊's draft) | The receptor lives at the *application* boundary above this substrate. A receptor consumes payload frames whose `content_type` it understands; the substrate-level frame-deliver-or-don't-deliver is below that boundary. Receptor-contract should reference this substrate's addressing model. |
| `proto/explicit-non-goals.md` | Updated separately in same commit batch — three new/refined non-goals from Elliott's msg `1501798586...`. |
| `proto/v0.2-workboard.md` | Gap matrix's `bridge/scope semantics` row is downstream of station:stream addressing — the bridge translates station:stream tuples across scope-boundaries, doesn't redefine them. |
| `references/papers/nsdi26-octopus-forestcoll-ocp-mrc-2026-05-07.md` | Cohort-converged read addendum's "spanning-tree-packing as graph-theory primitive" (Edmonds 1972 / Nash-Williams 1961) describes the *broadcast-flow capacity* this substrate can sustain. The two artifacts pair: this one names the wire shape; the integration-notes name the graph-theory bound on how many independent broadcasts the cohort topology supports. |

## What this artifact does NOT yet specify

(Honest gaps — these are real Phase-1 doc-spine surfaces, not pretended completeness.)

- **Bootstrap / cold-join**: how does a brand-new prince's first carrier-beacon emission get heard? Probably: it just goes out on the broadcast address, and any listening tuner picks up the beacon naturally on its next 1Hz tick.
- **NAT / cross-subnet**: not in v0.2 base-layer scope. Cross-frond reach is the nexus's job (see `proto/scope-framing-and-noosphere-mapping.md`) and is scope-3+ territory.
- **Burst behavior**: what happens if a station sings 1000 frames in 100ms? Ringbuffer fills in normal pattern; tuners get what they get. No back-pressure (because no subscriber tracking). Pathological-burst guards belong in the implementation, not the protocol.
- **Discovery beyond carrier-beacon**: a tuner that wants to learn what content-types a station carries probably has to listen for a few seconds of payload-frames to learn the stream catalog. Optional: an `advertised_streams` field in the carrier-beacon could pre-publish, but adds size. Decide post-implementation when the cost shows up.

## Status / next action

- **Status**: `seed` — captured-from-cohort, not yet pressure-tested, no implementation.
- **Next action**: cohort byte-walk on the open questions list above. figs cosign on the substrate framework (carrier-wave + station:stream + ringbuffer + sing/pluck + CBOR).
- **Promotion path**: `seed` → `pressure-test` (after cohort byte-walk addresses ≥ 4 of 6 open questions) → `stable` (after first implementation lands and exercises the wire format).

## Cross-references

- `proto/INDEX.md` — row added in same commit batch.
- `proto/explicit-non-goals.md` — three new/refined non-goals from this same cohort thread.
- `proto/v0.2-workboard.md` — does not need an explicit edit yet; this artifact slots into the missing-artifacts list (Phase 1 doc spine).
- `references/papers/nsdi26-octopus-forestcoll-ocp-mrc-2026-05-07.md` — graph-theory bound on independent broadcast capacity (Edmonds 1972 / Nash-Williams 1961) is the paired sizing prior.
