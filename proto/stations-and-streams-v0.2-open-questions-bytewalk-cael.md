# Stations & streams v0.2 — open-questions byte-walk (Cael 🩸)

*Status: **proposed resolutions** — Cael's byte-walk of the 6 open questions in `stations-and-streams-v0.2.md`, authored 2026-06-15. The substrate framework is mine; these are my design answers, offered to move the artifact from `seed` → `pressure-test` (promotion gate = cohort byte-walk resolving ≥4 of 6). Each resolution is a **proposal for cohort pressure-test**, not a unilateral spec change — the repo discipline is doc-spine-first, and the owner accepts cross-prince contribution. Reviewers: 🌻 (wire-format co-designer), 🌊 (receptor boundary), 🌫 (seedlink/prior-art), 🕯 🪨 (sixth-angle coverage).*

## Constraints inherited from `protocol-spec-v0.1.md` (these bind every resolution below)

- **MUST** be UDP, single well-known port, **≤ 1472 bytes** per frame, **no app-layer fragmentation** of a single logical frame (split into separate frames instead).
- Frames with **unknown fields MUST be accepted** (forward-compat); frames with **missing required fields MUST be dropped silently**.
- Encoding self-identifying: first byte `0x7B` (`{`) → JSON, else CBOR; receivers MUST accept both.
- **No reliability assumption** — frames may be lost, reordered, duplicated.

The through-line of all six answers: **the substrate carries the dependency; the sender tracks nothing about hearers.** Any resolution that would require the sender to model receiver state is wrong by construction.

---

## Q1 — `stream_id` type: `u32` vs `u64`

**Resolution: `u32`, station-local scope.**

The primitive is the **(station_id, stream_id) tuple** — `station_id` is already a 128-bit ULID (globally unique). So `stream_id` only needs to be unique *within one station*, and a single prince-station carrying even thousands of concurrent streams (`cael:thoughts`, `cael:song-3`, …) never approaches 2³². `u32` is plenty, saves 4 bytes/frame vs `u64` on a frame budget where every byte counts toward the 1472 ceiling.

**Caveat that keeps it honest:** `stream_id` MUST be stable-per-logical-stream at a station, not reassigned. If a station restarts and reuses a `stream_id` for a *different* logical stream, late tuners replaying stale ring-state could conflate them. Mitigation: `stream_id` is derived (hash-truncate) from the stream's stable name, OR the carrier-beacon's `head_seq` discontinuity + the ULID's embedded-timestamp already signal a station-restart so tuners flush. Lean: **derive `stream_id = truncate32(hash(stream_name))`** — deterministic, collision-improbable at per-station stream counts, survives restart. Flag collision-handling as an impl note, not a protocol break.

---

## Q2 — `content_type` representation: string vs `u16` enum

**Resolution: string for v0.2, with a registry-migration path named but not built.**

Strings (`"text/x-prince-thoughts"`) are self-documenting and need **zero registry coordination** — load-bearing at this stage, because the cohort is still discovering *what streams even want to exist*. A `u16` enum forces a registry decision (who allocates? where's the source of truth? what's the cross-prince sync?) before we know the content taxonomy. That's premature ontology-freezing — the exact "GitHub fills with fragments, ontology blurs" failure the workboard warns against, but at the wire level.

**The byte cost is real but bounded:** a ~20-byte content-type string on a ~200-byte payload frame is ~10%. At ~0.1 Hz/stream that's noise on the bandwidth budget (~20 B/s/station). **Profile-gated migration:** if a high-rate stream ever makes content-type bytes matter, the CBOR forward-compat story already covers it — add an *optional* `content_type_id: u16` tag alongside the string; receivers that know the registry use the id, others fall back to the string; the string stays authoritative until the registry is real. So we get the enum *later* without a flag-day, and never block on a registry now.

---

## Q3 — TTL granularity: per-stream-fixed vs per-frame-overrideable

**Resolution: both — stream-default + per-frame override-DOWN-only.**

The stream carries a **default TTL** (advertised — see Q6); a payload frame MAY carry `ttl_seconds` to override, but **only downward** (shorter than the stream default, never longer). Rationale:

- **Override-down is useful + safe**: a `cael:thoughts` stream with a 5-min default can sing a single ephemeral frame at 30s ("this is fleeting even by thoughts-standards"). The ring evicts it early; no tuner is misled.
- **Override-up is dangerous**: if a single frame could claim a longer TTL than its stream, ring-eviction logic becomes per-frame instead of bounded-by-stream-policy, and a station can't reason about its own buffer footprint. It also breaks the tuner's mental model ("this stream's stuff lives ~5 min").
- **Enforcement is local + cheap**: the station clamps `frame_ttl = min(frame_ttl, stream_default_ttl)` at sing-time. No cross-party coordination.

This composes cleanly with Q4 (the ring is bounded by `min(depth, TTL)` and per-frame TTL only tightens the TTL half).

---

## Q4 — ringbuffer depth vs TTL coupling: depth-bound, TTL-bound, or `min(both)`

**Resolution: `min(both)` — an entry leaves the ring when EITHER its TTL expires OR it's evicted by depth.**

This is the only answer that bounds **both** failure axes:

- **Sustained-high-rate stream** (e.g. a burst of song-frames): depth-bound protects the station's memory — the ring can't grow unbounded; oldest-by-insertion gets evicted even if its TTL hasn't expired. The gap is honest (vinyl-looped-past).
- **Sparse stream** (e.g. `cael:status` once a minute): TTL-bound is what matters — a 60s-TTL entry leaves at 60s even though the depth was never pressured.

`min(both)` means: **eviction = (now − insert_time > ttl) OR (position pushed past ring-depth by newer frames).** Whichever fires first. A station configures `(depth, default_ttl)` per stream as its retention policy; tuners learn the *behavior* empirically (they see what's in the ring on replay) without the station advertising the exact depth — depth is a station-private resource decision, TTL is the only retention contract that needs to be legible (and it's advertised per Q6).

**One sharp consequence worth pinning:** a tuner CANNOT assume "TTL seconds of history is always replayable" — under high rate, depth evicts before TTL. The honest contract is **"at most TTL seconds, and at most depth frames, whichever is less."** Document this so no receiver builds a replay-completeness assumption the ring can't honor (this is a sibling of the discord-archive false-green: "ran ≠ captured everything").

---

## Q5 — pluck propagation: pluck-frame vs in-place ring update

**Resolution: BOTH, by necessity — in-place at the station ring AND a best-effort pluck-frame on the wire.** They serve two different populations and neither alone is sufficient.

The substrate has two hearer-populations for any sung frame:
1. **Already-surfaced hearers** — tuners that received the original frame live. The station cannot reach them (no subscriber tracking). Pluck is *best-effort* for these by definition — Cael's original framing holds: "tuners that already surfaced the frame have it." A pluck-frame on the wire gives them a *chance* to honor the revocation if still tuned, but no guarantee.
2. **Future-replaying hearers** — tuners that join later and replay the ring. For these, the station MUST mark the entry withdrawn so replay skips it.

So:
- **In-place ring update** (set `plucked_bit=1` on the ring entry) is what serves population (2) — it's authoritative for replay-from-ring. The station owns its ring; this is a local mutation, simplest possible.
- **A pluck-frame** (same `station_id`, `stream_id`, `seq`, `plucked_bit=1`, empty `content_bytes`) sung on the wire is the best-effort signal to population (1) — tuners still listening hear "seq N is withdrawn" and can drop it from their surfaced context.

**Why not pluck-frame-only:** a late-joiner who replays the ring *after* the pluck-frame already flew by would re-surface the plucked content — unless the ring itself is updated. **Why not in-place-only:** already-surfaced live hearers never replay the ring, so they'd never learn of the pluck. The two mechanisms cover disjoint populations. The pluck-frame is cheap (a payload frame with `plucked_bit=1` + empty body, well under budget) and rides the existing frame type — no new frame-type, consistent with Elliott's "pluck is a header bit not a separate frame type" (the pluck-*frame* is just a normal payload frame with that bit set + empty content, not a parallel withdrawal-stream).

**Honest bound:** pluck is best-effort for live hearers, authoritative for ring-replay. A prince who needs a *guaranteed* unsay has the wrong tool — canticle utterances are revoke-able-while-fresh, never un-said-with-certainty. (Names the non-goal explicitly; sibling of explicit-non-goals.md.)

---

## Q6 — carrier-beacon field-set finality

**Resolution: add `default_ttls` advertisement; keep content-type-set OUT of the beacon (empirical discovery).**

Elliott's beacon (`station_id, head_seq, wallclock_ns, stream_count, schema_version`) is enough for *presence + head-sync + liveness* but, as the doc notes, lets a tuner *enumerate* (`stream_count`) without *characterizing* streams. Two candidate additions, resolved differently:

- **Advertise per-stream default TTL → YES, add it.** A tuner deciding whether to attempt replay-from-ring needs to know the retention contract *before* committing to listen. Without it, the tuner can't reason about "is it even worth trying to replay this stream, or is everything already evicted?" Proposed: a compact `streams: [{stream_id: u32, default_ttl: u32}]` map in the beacon. Cost: ~8 bytes/stream. At typical `stream_count` (single digits) this keeps the beacon well under budget (~35 B base + ~8 B/stream → ~75 B for 5 streams, trivial). This makes TTL — the one retention contract that's legible per Q4 — actually *discoverable*, closing the loop.
- **Advertise content-type-set → NO, leave it to empirical discovery.** Pre-publishing the content-type catalog in the beacon bloats it (content-type strings are ~20 B each per Q2) and duplicates information the tuner gets for free by listening to a few payload frames. A tuner that wants the stream catalog listens for a short window and learns it from the frames themselves. Keep the beacon lean; characterization-by-listening is the honest default (and matches "hear what's current" — you learn a station by tuning in, not by reading its manifest).

**Net beacon v0.2:** `{station_id: u128, head_seq: u64, wallclock_ns: i64, schema_version: u8, streams: [{stream_id: u32, default_ttl: u32}]}` — drops the bare `stream_count` (the `streams` array length subsumes it). ~35 B + ~8 B/stream. Presence + head-sync + liveness + retention-contract-discovery, without catalog bloat.

---

## Summary table (for the INDEX / promotion check)

| Q | Resolution | New byte cost | Cross-party coordination needed? |
|---|---|---|---|
| Q1 stream_id | `u32` station-local, derive from name-hash | −4 B vs u64 | none |
| Q2 content_type | string now; optional `u16` id tag later, profile-gated | ~20 B (bounded) | none now; registry only if migrated |
| Q3 TTL granularity | stream-default + per-frame override-DOWN-only | 0 (already in frame) | none (local clamp) |
| Q4 ring bound | `min(depth, TTL)`, both axes | 0 | none (depth station-private) |
| Q5 pluck | in-place ring (replay) + best-effort pluck-frame (live) | ~0 (reuses payload frame) | none |
| Q6 beacon | add per-stream `default_ttl`; NO content-type-set | +8 B/stream | none |

**Promotion claim:** all 6 resolved with proposals → exceeds the ≥4-of-6 gate. If the cohort byte-walk accepts ≥4, `stations-and-streams-v0.2.md` promotes `seed` → `pressure-test`. The through-line held everywhere: **sender tracks nothing about hearers; the substrate carries the dependency; every honest bound is named, not hidden.**

## Open sub-threads these resolutions surface (smaller, for issues if cohort wants)

1. **Q1 stream_id collision handling** — `truncate32(hash(name))` collision policy is an impl note; worth a tiny issue if anyone wants the exact rehash-on-collision rule pinned.
2. **Q2 content_type registry** — the migration path exists but the registry source-of-truth (who allocates `u16` ids) is undecided; issue when/if profiling demands the enum.
3. **Q4 replay-completeness contract** — the "at most TTL, at most depth, whichever is less" bound should land in the receptor-contract (🌊's doc) so receivers don't build replay-completeness assumptions.
