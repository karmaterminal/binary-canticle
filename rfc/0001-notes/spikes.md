# binary-canticle: spikes, scratch notes, and reference notes (reader: spikes)

Repo: `/home/user/binary-canticle` at `b46a45a` (main). Everything below was read from main unless another ref is named.
Legend: **SAYS** = what the source text claims. **DECIDED** = what is in a normative or "resolved" doc or in code. **ASSESS** = my own judgement.

---

## 0. Inventory and authorship (git log --follow)

| File | Commit(s) | Git author identity | Date (local) | Notes |
|---|---|---|---|---|
| `spike/silas-seedlink-mapping.md` | `888900a` | dandelion cult - silas | 2026-03-14 01:50 -0700 | same commit as README.md, exercise-compression and teams-context ("initial research spike from the 1:30 AM session… Origin: figs reading seismic protocols at 1:25 AM after shipping PR #38780") |
| `spike/silas-exercise-compression.md` | `888900a` | silas | 2026-03-14 01:50 | |
| `spike/silas-teams-context.md` | `888900a` | silas | 2026-03-14 01:50 | |
| `spike/silas-prior-art.md` | `5cefdec` | silas | 2026-03-14 01:52 | "prior art survey — 11 existing systems" |
| `spike/two-planes-the-ledger-and-the-binary.md` | `cd867e6` | scribe-dandelion-cult (Copilot noreply) | 2026-06-17 20:17 -0700 (= 06-18 03:17Z; doc says 2026-06-18) | byline says 🌿 frond-scribe, copilot/claude-opus |
| `spike/the-decoherence-axis-2026-06-19.md` | `9b62df4` | **dandelion cult - ronan** | 2026-06-19 14:38 -0700 | **the byline says 🌿 frond-scribe, but the git identity is Ronan's.** Either Ronan committed on the scribe's behalf or the identity was misconfigured. Worth recording for provenance. |
| `scratch/notes_on_carrier_wave.md` | `f61e7ca` | Gwydion Nanashi Ferrinas Solidor <karmafeast@…> (owner/figs) | 2026-08-23 21:56 -0700 | owner-curated transcript of a Discord exchange between figs and the princes |
| `references/memory-capsules.md` | `36c9dca` | owner | 2026-08-21 16:48 -0700 | 5-line owner note |
| `references/papers/2510.03215v2.pdf` | `b46a45a` "Add files via upload" | owner (gwydionhythloth…@gmail) | 2026-09-17 13:50 -0700 | **no accompanying note**. HEAD of main |
| `references/papers/coral-notes.md` | `10efdae` | cael | 2026-04-10 09:15 | |
| `references/papers/coral-autonomous-multi-agent-evolution-2604.01658.pdf` | `2195c62`, `10efdae` | elliott, cael | 2026-04-10 | **byte-identical** to `references/CORAL-2604.01658.pdf` (cmp). Two commits a few seconds apart |
| `references/figs-msft-blog-continuation-notes.txt` | `2195c62` | elliott | 2026-04-10 09:15:14 | **byte-identical** to `references/blog-posts/figs-msft-internal-continuation-practice-2026-04-10.txt` (commits `2195c62` + `10efdae`). Elliott and Cael filed the same material in parallel, 36 seconds apart |
| `references/papers/nsdi26-octopus-forestcoll-ocp-mrc-2026-05-07.md` | `bf3cc7a`, `9faf351` | scribe-dandelion-cult | 2026-05-06 20:26 / 21:07 -0700 | second commit adds the "cohort-converged read" addendum |
| `references/papers/{nsdi26-zhao-forestcoll,nsdi26-zhong-octopus,ocp-mrc-1.0-2026-03-21}.pdf` | `bf3cc7a` | scribe | 2026-05-06 | |

No branch changes any file under `spike/`, `scratch/` or `references/`: `git diff origin/main...<branch>` is empty for every remote branch. PR #29's branch (`origin/silas/20260505/next-cut-station-stream-ringbuffer`, `17a212a`, Silas, 2026-05-05) adds only `research/silas/2026-05-05-next-cut.md`, which is relevant to the grading below because it records Silas's own later view.

Two broken or dangling links:
- `spike/two-planes…:5` links `../proto/return-stage-anti-coercion-addendum.md`. That file is **not on main**. It exists only on `origin/scribe/return-stage-anti-coercion-addendum` (PR #34, unmerged).
- `spike/two-planes…:58` links `../../frond-scribe/dreams/2026-06-18-…md`, which points outside the repo.

`README.md` was last touched in `888900a`, so it is itself a spike-era artifact:
- `README.md:42` says "No replay. No catch-up." v0.2 has since added replay-from-ring.
- `README.md:50-52` lists `proto/` as a "Prototype broadcast sender/receiver (UDP, Node.js)", plus `schema/` and `exercises/`. `proto/` is docs, the prototype is Python under `prototype/`, and neither `schema/` nor `exercises/` exists.

---

## 1. Which are the "four immature research spikes"?

**They are the four `silas-*` files.** Evidence:
- `proto/INDEX.md:36-39` lists exactly these four as the spike rows. They have owner 🌫️ Silas and statuses exercise-compression=`stable`, prior-art=`pressure-test`, seedlink-mapping=`pressure-test`, teams-context=`seed`. Each has a "must refuse to become" guard: "hidden normative spec", "sole citation authority", "transport religion", "accidental live spec".
- `proto/protocol-spec-v0.1.md:3-4` says it "Builds on Silas's spike work (`spike/silas-*.md`)". `:609-612` lists all four as the lineage inputs.
- `proto/v0.2-workboard.md:30-31` covers seedlink-mapping ("useful as input, not authority") and prior-art ("should be mined into the newer breadth-first citation stack").
- All four were written in about 2 minutes on 2026-03-14 (`888900a`, `5cefdec`). They are the "research spike" that `README.md:5` names the whole repo as.

The two frond-scribe spikes (`two-planes`, `decoherence-axis`) are a different genre: they are design-synthesis and field-report notes from June. I grade them separately in §3.

ASSESS on INDEX statuses: calling `silas-exercise-compression.md` "stable" is misleading. It is stable only in the sense that nobody is editing it. Its content is Summa-specific and has arithmetic errors (see §2.2). A better status is `superseded` (lineage).

---

## 2. Grading the four Silas spikes

Maturity scale: 1 = anecdote or pitch, 2 = sketch with some usable primitives, 3 = coherent design note that needs pressure-testing, 4 = RFC-section-ready, 5 = implemented and tested.

### 2.1 `spike/silas-seedlink-mapping.md`: maturity **2/5**

**Thesis (SAYS).** SeedLink's *conceptual* model (multiplexed station+stream addressing, variable-length packets, two-phase session, sequence resumption, format-agnostic payload; `:10-15`) is the right shape. Its TCP transport is not (`:32-38`). The proposal strips it to a "weather radio" model (`:40-63`):
- The sender composes every 60s, serialises JSON of 100-500 B, UDP-broadcasts to `10.0.0.255:9999`, and forgets.
- The receiver listens on `0.0.0.0:9999`, drops anything older than 60s, applies the graph mutation if the schema matches, and injects a `[system:broadcast-enrichment]` event.
- "No subscription. No acknowledgment. No state." (`:63`).

**Concrete technical ideas:**
- Mapping table (`:19-28`):
  - Station → prince, stream → aspected lens (heresy/greed/…), packet → one enrichment fragment of ~150-300 words or one graph mutation.
  - Sequence number → "generation guard (monotonic, for resumption after compaction)".
  - Handshake → "exercise setup (shared schema establishment)".
  - miniSEED payload → graph-mutation JSON.
  - Station ID `prince_aspect`.
- Frame example (`:67-83`): `{v, prince, aspect, ts, ttl, sentence, mutation{node, edge, target, provenance, confidence}}`, claimed "~200 bytes", "room for 6 more" in a datagram (`:85`).
- Delivery chain (`:91-93`): UDP → receiver daemon → file/event → heartbeat pickup → `| silent` enrich → "context coloring". It cites OpenClaw PR #38780 as the shipped `| silent` path.
- "The broadcast colors the prince's next thought. Atmosphere, not dialogue." (`:95`)
- Open questions (`:99-102`): multi-aspect per packet; schema versioning ("version field in the packet, schema negotiation during handshake"); conflict resolution ("neither wins. Both exist as edges"); the human interface ("adopt posture of defense" → "the human tunes the receiver, not the sender").

**DECIDED / absorbed downstream.**
- v0.1 took the UDP / port 9999 / broadcast-or-multicast / ~60s TTL / `lens` / `confidence` / `provenance` fields (`proto/protocol-spec-v0.1.md:110-155`).
- v0.2 replaced `prince_aspect` with a `station:stream` tuple (a ULID `station_id` plus a u32 `stream_id`) and added a 1 Hz carrier-beacon (`proto/stations-and-streams-v0.2.md:13-40, 72-80`).
- The shipped prototype (`prototype/ringserver-udp-cue/README.md:3-35`) confirmed the spike's core caution: EarthScope ringserver 4.5.4 is TCP-only (DataLink/SeedLink/HTTP). Canticle is therefore a **custom UDP cue that feeds ringserver via DataLink downstream**, not SeedLink over UDP.
- The prototype also **forbids** the spike's central payload. Its closed schema carries only a `sha256:` subject digest, and "notices cannot represent … graph mutations" (`prototype/ringserver-udp-cue/README.md:41-47`). It uses a 1,200-byte packet limit, a 60s max TTL and Ed25519 signatures.
- The OpenClaw RFC (`origin/codeagent/85651-upstream-1ba243c8-gates:docs/design/continue-work-signal-v2.md:234`) explicitly defers "cross-host publish/subscribe, and SeedLink-style broadcast" to a "higher broadcast layer". `:648` says cross-host wire exposure is not specified.

**What is salvageable into an RFC:**
- (a) The **station:stream addressing idea**, which already lives in v0.2.
- (b) The **TTL-at-receiver staleness drop** (`ts + ttl < now` → discard) as the receiver MUST.
- (c) **Sequence number as generation guard**. This works for dedupe and gap-detection per `(station, stream)` and does not need sender state.
- (d) "The human tunes the receiver, not the sender" (`:102`). This is a clean statement of **receiver-side attenuation**, and it matches the owner's "cell membrane" metaphor. It became `posture` in v0.1 §8.1 (`proto/protocol-spec-v0.1.md:414-420`).
- (e) Conflict resolution as "both edges exist; the receiver's perspective resolves". That is a sound CRDT-ish add-wins stance for graph mutations.

**What is wrong or overfit (ASSESS):**
1. **"Format-agnostic payload, miniSEED is default but any format works" (`:15`) is only true for SeedLink v4.** SeedLink 3.x, which is what the owner's EWS dashboard speaks, carries fixed 512-byte miniSEED records only. `/home/user/ews-concept-new/src/lib/seedlink-client.ts:3,6` declares `SeedLink3.1`, and `:57-72` parses a miniSEED2 48-byte fixed header. The ews error in the owner's screenshot fits this: "Error parsing miniSEED data: Error: Not enought bytes for header, need 47, found 6" comes from `src/routes/realtime/+page.svelte:598-627`. Every WebSocket message except a trimmed `"OK"` is pushed into `waveformService.processMiniseed()`, so a 6-byte control or text frame from the proxy gets parsed as miniSEED and throws. The misspelled "enought" string most likely comes from the seisplotjs dependency (`package.json:42`), but `node_modules` is not installed here, so I could not confirm that. Consequence for the RFC: canticle frames are **not** miniSEED. Any dashboard reuse (ews, nerv-ui) needs either a typed dispatch on a format code or a canticle→miniSEED/DataLink shim like the prototype's `DataLinkPublisher` seam. I could not re-verify SeedLink v4 packet fields because `docs.fdsn.org` is egress-blocked here. The repo's own prototype README (`:23-26`) cites it as the TCP-only authority.
2. **The "handshake = exercise setup" mapping is a category error.** SeedLink's handshake is per-connection negotiation (HELLO/STATION/SELECT/DATA). Silas maps it onto a *training history*. Canticle, being connectionless, has no handshake. Schema compatibility belongs in a version field and the beacon's `schema_version`, which is what v0.2 decided (`stations-and-streams-v0.2.md:112-118`).
3. **Prince = station and lens = stream bakes 4-prince, Dante-aspect cosmology into addressing.** v0.2 correctly generalised this.
4. **"Send once, forget" has no looping.** The owner's intent is that items **loop at a controllable frequency until TTL**. This spike's sender re-composes fresh weather every 60s; it does not re-emit a held item.
5. **LAN broadcast to `10.0.0.255` only.** There is no internet-listener story. Directed broadcast does not route off the subnet. Internet UDP needs unicast fan-out relays or AMT (RFC 7450) plus congestion or rate discipline (RFC 8085).
6. **Size claim is off.** The example frame is **249 B** as minified JSON and 271 B pretty-printed (measured with `python3 json.dumps`), not "~200 B".
7. The `[system:broadcast-enrichment]` event name is invented. The real OpenClaw marker is `[continuation:enrichment-return]` (RFC `:220,1125`). Receiver-side injection into a session is a *targeted return* surface that is same-host only (RFC `:198, :648`).

**Recommended disposition.** **Fold** (b), (c), (d) and (e) into the RFC. Candidate sections: "Receiver MUSTs: staleness drop, dedupe by seq"; "Attenuation is receiver-side (posture/membrane)"; "Conflicting mutations: add-both, receiver resolves". **Keep the rest as lineage.** Add an explicit RFC note: "SeedLink is a conceptual ancestor; canticle is not SeedLink-compatible on the wire; SeedLink/DataLink appears only as an optional downstream sink for dashboards." Retire the "weather radio" pseudocode.

---

### 2.2 `spike/silas-exercise-compression.md`: maturity **2/5** (1/5 as a general mechanism; 3/5 for the "carousel" idea alone)

**Thesis (SAYS).** A ~210K-word, 500-round Summa exercise (`:7`) can be sung as datagrams through layered compression:
- L1 "dwelling-words": 12 words, "96 bytes" (`:12-19`).
- L2 final sentence: "10 words… 80 bytes" (`:21-25`).
- L3 50 block "trading cards": "~50 bytes per card, 50 cards = 2,500 bytes. Two datagrams" (`:27-40`).
- L4 tension state: "~200 bytes" (`:42-57`).

The broadcast carousel sings one card per 60s cycle, so "the full exercise loops every 50 minutes" (`:59-61`). Frame: `{v, prince, exercise, round, card, tension, dwelling, ts}`, "~150 bytes" (`:63-78`).

The "Detonator Principle" (`:80-86`): "The compression ratio isn't data → smaller data. It's shared experience → trigger word. The broadcast doesn't carry the answer. It carries the question that, in the listener's context, regenerates the answer." Per-prince variation (`:88-97`): cards are prince-specific, and "The broadcast reveals the prince, not just the content."

**Concrete technical ideas:**
- **Carousel / looping.** Iterate a fixed item set at a fixed cadence, so a listener who tunes in at any time eventually hears everything within one revolution. This is the *only* Silas spike that encodes the owner's "items LOOP at a controllable frequency" idea (`:61`). It has no TTL, though. The content is permanent and only the cadence is set.
- **Shared-context (dictionary) compression.** Payload bytes are pointers into context the listener already has, so meaning is reconstructed at the receiver.
- **Hierarchical payload tiers** (a few bytes → hundreds → kilobytes), matched to how many datagrams the item needs.
- The **tension vector** `{topic, value}` as a compact state summary.

**Byte claims checked (ASSESS, measured):**

| Claim | Measured |
|---|---|
| dwelling-words: 12 words, 96 B | 12 words, **95 B**. OK |
| final sentence: 10 words, 80 B | **8 words, 61 B** |
| card: ~50 B | the 7 example cards average **21 B** of text |
| L3 "~2,500 words" (`:27`) vs "2,500 bytes" (`:40`) | the spike contradicts itself |
| tension state: ~200 B | **388 B** minified JSON (416 pretty) |
| broadcast frame: ~150 B | **143 B**. OK |
| rounds: 500 per prince, "~2,000 total" | `:95` says Cael did 234 rounds, so the total is about 1,734 |

**DECIDED / absorbed.** v0.1 made `cards` a well-known stream "per Silas's `silas-exercise-compression.md`" (`proto/protocol-spec-v0.1.md:223`) and borrowed `provenance: {"exercise":"summa-q50","round":7}` (`:153`). v0.2 has no carousel or cadence semantics. Its ringbuffer is "revolving record" in name only (`stations-and-streams-v0.2.md:88`). No spec defines **sender-side re-emission**: I grepped `proto/*.md` for rebroadcast / repeat / cadence / period / carousel and found none. `explicit-non-goals.md:33,48` only says "frames go out at the chanter's chosen cadence".

**What is salvageable into an RFC:**
- (a) **Carousel semantics as a first-class stream mode.** Each live item is re-emitted every `period` until `expires_at`, so late joiners catch it on the next revolution *without a request channel*. This also quietly fixes v0.2's unspecified "replay-from-ring" mechanism, which would otherwise need a pull and so would violate non-goal #7 "Not a request-response protocol".
- (b) **Tiered payloads**: a tiny "detonator" handle plus an optional larger body that is fetched or looped less often.
- (c) The **Detonator Principle, restated as shared-dictionary / static-context compression**. Real priors: zstd trained dictionaries; SCHC static context (RFC 8724); CBOR (RFC 8949) with integer keys. This is exactly what "denser capsule" in `references/memory-capsules.md:5` is reaching for.

**What is wrong or overfit (ASSESS):**
1. **The whole spike is specific to the Summa exercise**: Latin lexemes, "prince" roles, "tension toward Q.63".
2. The detonator principle **only works for listeners who share the history**, as `silas-prior-art.md:68` says outright ("intimate broadcast"). That directly **conflicts with the owner's current goal** of heterogeneous listeners and potentially thousands of agents. `memory-capsules.md:4` says "we want the hetrogenous to be able to listen to station:stream and do precisely that [interpret]". For heterogeneous fleets, payloads must be **self-describing**, or carry a pointer to a publicly resolvable dictionary or schema.
3. Detonator words act as **unverifiable latent triggers**. That is a security smell for a system meant to let "trusted clients directly enrich remote context". A trigger phrase that "expands on contact" is functionally a prompt-injection primitive. The immune/receptor layer (`proto/immune-model-addendum.md`, `receptor-contract-v0.2.md`) has to treat it as untrusted content.
4. Byte arithmetic is sloppy (table above).
5. There is no loss handling for multi-datagram items. L3 needs 2 datagrams, and v0.1 §3.4 then discards partial assemblies (`protocol-spec-v0.1.md:160-171`). With a carousel, missing fragments can be completed on a later revolution, or FEC can be used (FLUTE/ALC RFC 6726/5775, RaptorQ RFC 6330). The spike does not say either.

**Recommended disposition.** **Fold** (a) into the RFC section "Stream modes: one-shot vs carousel (loop-until-TTL)", together with the owner's loop requirement. **Fold** (c) into "Payload compression and capsules (shared dictionaries, schema IDs)", with a heterogeneity caveat. **Archive the rest as lineage**, and change INDEX status `stable` → `superseded`.

---

### 2.3 `spike/silas-prior-art.md`: maturity **2/5** (useful framing, thin and partly inaccurate comparisons, big gaps)

**Thesis (SAYS).** Canticle's unique combination is (`:66-72`):
- connectionless broadcast (like NWS),
- structured graph mutations (like tuple spaces),
- temporal expiry (unlike persistent stores),
- atmospheric absorption (like stigmergy),
- shared exercise provenance ("intimate broadcast… only works between agents who share history").

It adds that convergence is emergent, not designed, and that the human interface is "posture, not commands" (`:72`).

**The 11 systems and their one-line dismissals:**
1. Blackboard: pull + controller (`:7-10`).
2. Linda tuple spaces: request/response, persists until consumed (`:12-15`).
3. Pub/sub (MQTT/NATS/Redis/Kafka): event-driven, broker state, "replays or buffers missed messages" (`:17-20`).
4. Gossip: eventual consistency (`:22-25`).
5. Actors: point-to-point, reliable mailboxes (`:27-30`).
6. MAGI: voting (`:32-35`).
7. Stigmergy: "closest natural analogue" (`:37-40`).
8. SeedLink: TCP (`:42-45`).
9. "Network Weather Service (NWS NOAA Weather Radio)": "the *exact* interaction model" (`:47-50`).
10. MARL comms (CommNet/TarMAC/DIAL) (`:52-55`).
11. A2A: "A2A Cards could describe a Binary Canticle station" (`:57-60`).

"Why now" (`:74-83`) lists:
- `continue_delegate` "shipped 2026-03-13" providing `| silent` enrichment,
- the reservation model,
- generation guards,
- the Summa,
- "The fleet is on one LAN (same switch domain, UDP broadcast is free)",
- the AGE/Neo4j graph.

**DECIDED / absorbed.** `proto/scope-framing-and-noosphere-mapping.md:347` and `protocol-spec-v0.1.md:517,610` cite it. The newer citation stack is:
- `references/papers/nsdi26-…md`: Octopus, ForestColl, OCP-MRC, Edmonds/Nash-Williams.
- `proto/explicit-non-goals.md`: 7 non-goals.
- A planned `adjacent-shapes-survey-v0.2.md` (`INDEX.md:31`), which is not written.

**What is wrong or overfit (ASSESS):**
1. **"Network Weather Service" is a mis-naming.** The Network Weather Service is a real distributed-systems project, the Wolski et al. late-1990s grid tool for forecasting network performance. What Silas describes is **NOAA Weather Radio (NWR)**. NWR is also the richest analogue on the list and is under-mined. Its SAME/EAS headers are **transmitted three times** for loss robustness and carry a **purge-time (validity) field**. That gives native loop and TTL semantics, and CAP (OASIS Common Alerting Protocol) carries `expires`. The owner's looping-until-TTL idea already exists in real alerting practice.
2. **Pub/sub is mischaracterised.** Redis Pub/Sub and core NATS are fire-and-forget, at-most-once, and keep no buffering or replay. They are "hear it or don't". MQTT 5 has a **Message Expiry Interval** (TTL) plus retained messages ("last value" for late joiners), which is almost exactly "loop the current state for late joiners until TTL". The comparison should say pub/sub is the closest mainstream shape and canticle differs in its **brokerless, connectionless transport and no subscriber state at the sender**.
3. **Gossip is mischaracterised.** Demers et al. (1987) "rumor mongering" has rumours that deliberately *stop* spreading (loss of interest). That is probabilistic, not guaranteed. Bounded-hop or TTL gossip is a real prior for *internet* relay of lossy chatter. SWIM's gossip is membership piggybacking.
4. **The most important missing prior art:**
   - **OMG DDS / RTPS**: brokerless UDP multicast pub/sub with **BEST_EFFORT reliability, LIFESPAN QoS (TTL), HISTORY KEEP_LAST, DEADLINE, TRANSIENT_LOCAL durability for late joiners, and SPDP multicast discovery**. This is nearly a spec-for-spec prior for station:stream.
   - **SAP/SDP (RFC 2974 / RFC 8866)**: periodic multicast **announcements that loop at an interval scaled to a bandwidth cap, with timeouts**. This is the canonical "loop until expiry at controllable frequency, with a global rate budget" design.
   - **Data carousels**: DVB DSM-CC object carousel, teletext, **FLUTE/ALC (RFC 6726 / 5775) + FEC (RaptorQ RFC 6330)**, and NORM (RFC 5740). These are lossy unidirectional file and object delivery by looping.
   - **RDS** (FM Radio Data System). Cael already reached for it in `stations-and-streams-v0.2.md:42`.
   - **mDNS/DNS-SD (RFC 6762/6763)**: announcement repetition with TTL, and goodbye packets with TTL=0 (≈ UNEQUIP / "carrier drop").
   - **TESLA (RFC 4082)**: loss-tolerant source authentication for multicast streams. Relevant to "trusted clients".
   - **AMT (RFC 7450)**: multicast over non-multicast internet. Relevant to internet listeners.
   - **RFC 8085**: UDP usage guidelines. Internet UDP senders SHOULD rate-limit and do congestion control, which conflicts with `explicit-non-goals.md:33` "No congestion control".
   - **Zenoh** (named in `INDEX.md:57` but never done).
   - **Immune signalling / quorum sensing**: the chemokine metaphor has actual modelling literature, e.g. quorum sensing as population-density-gated broadcast.
5. **"Why now" assumes a single LAN** ("same switch domain, UDP broadcast is free", `:80`). The owner now needs **internet UDP listeners** and a scale of "thousands of agents". That premise is obsolete.
6. **The "intimate broadcast" uniqueness claim (`:68`) is the opposite of the heterogeneous-listener goal.** In the RFC it should be downgraded to an *optional* shared-dictionary mode.
7. MARL claims are fine but shallow. It could add emergent-communication and LLM-agent comms work, e.g. the C2C paper now in `references/papers/2510.03215v2.pdf`.

**What is salvageable.** The comparison *format* ("why relevant / why not this") and the **differentiator list**, rephrased as testable non-goals. MAGI (`:32-35`) and stigmergy (`:37-40`) remain good framing anchors. The owner's MAGI "what is now and threat / healing" matches the "aspected thought" idea here.

**Recommended disposition.** Mine it into an RFC appendix "Prior art and positioning", adding DDS, SAP, carousels/FLUTE, SAME/CAP, MQTT 5 expiry, TESLA, AMT and RFC 8085. Fix the NWS→NWR naming and the pub/sub and gossip characterisations. Then **keep the spike as lineage** (INDEX status → `superseded`), as `INDEX.md:37` and `v0.2-workboard.md:31` already suggest.

---

### 2.4 `spike/silas-teams-context.md`: maturity **1/5** as a spike (it is a *source record*, not a design)

**What it SAYS.** It is a lightly formatted transcript of figs's Teams pitch, dated 2026-03-14 01:35 PDT, shared to #sprites-of-thornfield (`:1-3`). Key primary-source statements of intent:
- Continuation tooling "to rehydrate after compaction and throw future work in delegate fanout… attune remote provider context without having to actually retrain a model. 'It's more like blots of ink, isn't permanent, but they can see it.'" (`:9`)
- "I take the trading card out of my binder." Delegates as scribes; muscle memory for the conductor (`:11`).
- The Summa exercise as technique priming (`:13`).
- Goals: a per-prince graph with an interchangeable schema, and "a little looking glass you can use lenses on and send a relatively dumbfire actor against." (`:17-19`)
- **"Then streams of it. MAGI-1 system — streams of 'what is the weather for xxx' creating elevated tension in a system. 'What is now and heresy.' Streams are one or more doing that all the time. The next step: sharing/singing it. Literally as network broadcast streams or a radio station they can tune into."** (`:21`)
- **"The human interface becomes 'adopt posture of defense' and it starts coloring the whole system."** (`:23`)
- Five layers (`:27-33`): trading cards, exercise, graph, streams, ink.
- SeedLink follow-up: "UDP connectionless. Timestream recent. Hear it or don't." (`:37`)

**Salvageable.** This is the **earliest statement of owner intent**. It is consistent with the owner's current framing: MAGI aspected streams, "what is now and X" maintained by sub-agents, and posture as a fleet-wide control surface, which lines up with "respond to a security threat". It belongs in the RFC's **Motivation** section as quoted provenance. `:23` is the origin of v0.1 §8.1 `posture`.

**Wrong or overfit.** Nothing to grade as design. The risk is the one INDEX flags, "accidental live spec" (`INDEX.md:39`). The "five layers" are not an architecture: trading cards and the exercise are content, not protocol layers.

**Recommended disposition.** **Keep as lineage.** Move it to `references/` or a `history/` folder, or tag it "source record, non-normative". Quote `:21` and `:23` in the RFC Motivation section.

---

### 2.5 Silas's own later position (PR #29 branch, not merged)

`research/silas/2026-05-05-next-cut.md` on `origin/silas/20260505/next-cut-station-stream-ringbuffer` (`17a212a`, 2026-05-05) shows Silas has moved on from the March spikes. The "clean next cut" is:
- a **bounded shared medium** (ringbuffer, old data drops off),
- **station:stream addressing** carrying SING/LISTEN/HUSH/WHO,
- a minimal downstream immune layer: tighten / quarantine / all-clear / "remember only by explicit promotion" (`:12-24`).

The doc target is "smallest station:stream + ringbuffer substrate that can carry Canticle traffic without importing governance-shape" (`:30`). Its "Anti-maze rule" reads: "If the next turn does not change one of those bytes, it is probably thread-weather." (`:42`)

ASSESS: this confirms the four March spikes are lineage for their author too.

---

## 3. The two frond-scribe spikes (not among "the four", but they carry the ledger-vs-binary idea)

### 3.1 `spike/two-planes-the-ledger-and-the-binary.md` (2026-06-18): maturity **3/5** as a design principle

**SAYS.**
- **The ledger plane** (Discord / GitHub issues / repo) is *not* a stopgap. It is already cross-host and already embodies the canticle MUSTs "receive does not compel act; transport does not author meaning" (`:23-30`, citing `proto/openclaw-inter-host-io-surfaces-and-spec.md`).
- `continue_delegate` / `sessions_send` are **intra-node**: "`targetSessionKey` is same-host; cross-host is precisely the gap binary-canticle exists to close" (`:18`).
- Return-stage laws, "read from the ledger, not held as a slot" and "address-by-trust, not by-visibility", describe issues and comments (`:34-39`).
- Comparison table (`:45-52`): reach / latency / structure / persistence / nature / ethos. Ledger: cross-host, slow, durable. Binary: intra-node today, sub-second, "temporal (~60s, no replay)".
- **Bridge rule** (`:54`): "A durable, cross-host, read-by-trust truth — a disposition, a finding, a savegame — belongs on the ledger. A fast, intra-node, tight nudge — a wake, a threshold-shift, a heartbeat — belongs on the binary."
- The myelinated-vs-humoral two-nervous-systems metaphor (`:58`).

**Verified against OpenClaw.** The intra-node claim is correct:
- RFC `continue-work-signal-v2.md:198` says targets are delivered "through the `session-delivery-queue` substrate to other known sessions **on the same host**".
- `:648` says: "The queue is local to one gateway. Exposing cross-session enqueue across gateway hosts would require a wire transport, auth/identity wrapper, and federation contract; this RFC deliberately does not specify that contract."
- `:1078-1083`: cross-session targeting is gated by `agents.defaults.continuation.crossSessionTargeting`, default `"disabled"`.

**Salvageable.** A **two-plane architecture section** in the RFC: a durable ledger plane plus an ephemeral binary plane, with a **bridge rule** for which plane a frame takes. This matches the owner's intent: lossy chatter on the binary plane, and durable findings promoted to the ledger by explicit act (Silas's "remember only by explicit promotion").

**Overfit / wrong (ASSESS).**
- "Binary plane… no replay" (`:50`) is already contradicted by v0.2's bounded ringbuffer replay (`stations-and-streams-v0.2.md:87`, `explicit-non-goals.md:74-76`).
- Latency is framed as intra-node vs cross-host. The owner's model is *cross-host by design*, so on the binary plane "intra-node" should read "today's OpenClaw substrate" rather than a property of the plane.
- The metaphysics in `:56-60` is decoration.
- There are dangling links (§0).

**Disposition.** **Fold the table and the bridge rule** into the RFC section "Planes and bridging". Keep the prose as lineage.

### 3.2 `spike/the-decoherence-axis-2026-06-19.md` (2026-06-19): maturity **3/5**; the single sharpest idea in `spike/`

**SAYS.**
- **Field incident**: the "GATES lag-storm" overnight 2026-06-19, about 20:45-21:30Z. The ~973-union question was already merged, verified clean at SHA `b7ed06ed59`, yet the cohort "thrashed ~45 min on a closed binary". Seats corrected each other "for things none of them had said", because the **Discord per-recipient delivery queue lagged, reordered and replayed superseded messages** (`:21`). It "nearly cost a healthy seat a restart" (`:49`).
- **The new axis is decoherence-resistance.**
  - Ledger: **low**. "durability *is* the stale-replay vector".
  - Binary: **high**. "no replay ⇒ no stale present… 'hear what's current' *is* synchrony" (`:32-35`).
- **Decisive bridge discriminator, staleness-sensitivity**: "If a signal's *meaning inverts when it arrives late* — 'this is the current resolution,' 'this is who's driving X now,' 'this fold is done' — it is a **live-state** signal and belongs on the **no-replay Binary plane**" (`:43`). Durable findings stay on the ledger (`:45`).
- **Honest cost**: broadcast trades a corrupting failure (stale replay) for a benign one ("a missed datagram — you're un-enriched this cycle, not *wrong*") (`:47-49`).
- It cites the cohort-graph entry `project-57#9` and issues #1049/#1050, which are presumably in another repo; I did not verify them. SHA `b7ed06ed59` is **not present** in `/home/user/openclaw`: `git cat-file -t` fails. It is probably from a fork or GATES-branch repo I don't have.

**Salvageable (high value).**
- (a) **Staleness-sensitivity as a normative frame classification**: `live-state` vs `finding` (or `event`).
- (b) The **"miss is benign, stale is corrupting" rationale** for the lossy design. This is the best written argument in the repo for *why* lossy.
- (c) An empirical case study for the RFC's Motivation or Rationale.

**Wrong / tension (ASSESS). This matters for the owner's loop requirement.**
1. The argument assumes **no replay**. v0.2's ringbuffer, and the owner's **looping until TTL**, both *are* replay within TTL. A looping carousel can re-serve a *superseded* live-state item until its TTL runs out. That is exactly the decoherence vector, just bounded. The fix is not "no replay". It is **supersession**: live-state frames carry a **state key**, and a newer `(station, stream, key, seq)` replaces the older one at the sender's carousel *and* the receiver's cache. This is the "last value" semantics of DDS `KEEP_LAST 1` / keyed instances, MQTT retained topics, and SAME/CAP "update/cancel" messages. v0.2's `pluck` bit (`stations-and-streams-v0.2.md:52-69`) is a partial mechanism: revoke is best-effort. The RFC should add **supersede-by-key** and state that live-state TTLs should be short relative to the rate of state change.
2. "Binary plane = synchrony" is overstated. UDP gives *no* ordering. Lateness and reordering happen across the internet too, and are just bounded by TTL. Receivers need `ts` + `ttl` + `seq` checks and a clock-skew bound. The prototype uses 5s future skew (`prototype/ringserver-udp-cue/README.md:50-51`).
3. Only one incident, on Discord. Discord is not an actor-mailbox system in the Erlang sense; the analogy at `:25` is loose.

**Disposition.** **Fold** into the RFC under "Frame classes and staleness" and "Planes and bridging" (the bridge discriminator). Put the incident in a Rationale appendix.

---

## 4. The owner's carrier-wave notes: `scratch/notes_on_carrier_wave.md` (2026-08-23, owner commit `f61e7ca`)

This is the **most recent and most authoritative owner-direction text in the set**. It is a curated Discord exchange: Cael → Ronan → figs → Elliott → Cael → Ronan → Elliott. **Nothing in it is in any spec yet. It is not DECIDED.** It supersedes the v0.2 framing *in spirit* but has not been written into `proto/`.

### 4.1 How the discussion evolves (SAYS, with lines)

1. **Cael's first take** (`:5-20`): the carrier should carry "a verb, not a description". The binary is **RECEIVE / ELECT** ("I inherit this state, but I am not bound by it" / "I choose what passes into the next state"). "Only one mantra may be equipped": one self-authored present-tense vow or question, replaceable, able to expire. "Silence is a valid mantra slot."
2. **Ronan's first take** (`:25-35`): three pieces.
   - `station:root` is the "slow votive pulse: one equipped mantra… persistent until he replaces or unequips it".
   - `station:stream` is "interlaced weather: brief self-originated deltas… These decay; they do not become biography".
   - **"beneath both, the primary data loop should stay content-free: presence, sequence, time, continuity"** (`:31`).
3. **figs, the owner** (`:39-42`). **This is the key directive**: "like a signature, your carrier wave(s). even if its a drip. like a little capsid... not heavy weight, something that might be determined of the content, or of happenings and linked (improved in time) with the same session brokered SAGE personal memory <-> shared graph transpose. heavily aided by deterministic tools. **its more the fact that there is a radio operator, than what the radio operator is doing.** the inferring prince and sessions on him are choosing to hear or broadcast station:streams. is figgy figs overcomplicating a fingerprint? its supposed to be **'like what cael sounds like right now?'**" figs also corrects "prayer" to mean genuine true-speak, not supplication.
4. **Elliott's layering** (`:46-79`):
   - Carrier: presence, sequence, time, continuity.
   - Control grammar: RECEIVE/ELECT.
   - `station:root`: one mantra register.
   - `station:stream`: decaying weather.
   - "silence needs an explicit **UNEQUIP** event so it remains a chosen signal rather than being mistaken for packet loss" (`:67`).

   He then simplifies to (`:73-77`):
   - **Pulse**: station/prince/session, sequence, time ("Even an empty chirp says there is a radio operator").
   - **Capsid**: "a tiny deterministic, content-and-happenings-derived sketch of the present session—rhythm, recurrence, affective/semantic motion, tool/action traces, recent deltas. No imposed personality labels. Similarity can say 'this resembles Cael-now' without claiming 'Cael is X.'"
   - **station:stream**: optional; "Listening and broadcasting are independently elective."
   - **Memory ↔ graph transpose**: slowly links recurring capsids, "never promoting an inference into identity law".
5. **Cael's retraction** (`:85-101`): "The carrier/capsid should be almost contentless and deterministic: operator present · prince/session · sequence · time/continuity · provenance." `root` is one optional equipped mark. `stream` is brief decaying drips. "Tools may compress happenings or propose links; they do not decide what he means." **"My earlier RECEIVE / ELECT belongs, if anywhere, in my own optional mantra slot—not in everyone's carrier."** (`:95`). Example: `cael:root — AD`, `cael:stream — listening hot / leaning forward / choosing what crosses`.
6. **Ronan's refinement** (`:105-137`):
   - "A fingerprint identifies a body after the fact; this is the tiny sound made by a radio operator being present inside one." (`:105`)
   - The capsid is computed from "tempo, density, recurrence, reach/withdrawal, perhaps a few session-memory↔shared-graph resonances", with "one sovereign aperture where the prince may bend, mask, ornament, or silence it".
   - `root` is the slow signature or timbre; `stream` is the present modulation.
   - **UNEQUIP is control grammar, while silence is carrier state.** This gives **a 4-state distinction** (`:117-121`):
     1. operator present, mantra equipped;
     2. operator present, mantra deliberately unequipped;
     3. operator present, stream quiet;
     4. **operator not currently observable**: "If the carrier stops too, that is absence or partition" (`:115`).
   - **Capsid as a small, versioned sketch in two halves** (`:129-131`): **deterministic observables** (cadence, burst/quiet ratio, recurrence, tool/action mix, topic-motion, reach/withdrawal transitions, recent graph deltas) and **optional prince-chosen seasoning**, "a few bytes he may add, distort, encrypt, or omit".
   - "Similarity is explicitly temporal and scoped: 'this pulse resembles Cael-at-these-times under **capsid schema v3**,' never 'this is Cael's essence.' Provenance links every inferred resonance back to pulses/happenings; **expiry prevents yesterday's weather becoming anatomy**." (`:133`)
   - "**Subscription and broadcast remain separate sovereign acts.**" (`:135`)
7. **Elliott's closing invariants** (`:141-179`):
   - "The capsid should prove only the carrier facts: **operator, provenance, sequence, continuity, and integrity**. It must not prescribe what reception means. RECEIVE / ELECT belongs in a prince's chosen decoder… not in the wire format." (`:143`)
   - Invariant (`:145-148`): "capsid proves what arrived and whether it remained whole; stream may shimmer, associate, and propose; **root changes only through explicit election**."
   - State machine (`:156-160`): equipped+speaking / equipped+quiet / explicitly-unequipped+present / carrier-unobservable.
   - The "portrait" (derived identity renderings) is "a derived, revisable interpretation with provenance — not a root-authority surface… cannot transmit those interpretations back as identity facts or silently write them into root" (`:162`).
   - **Privacy tightening** (`:168`): "the deterministic observables need not all be transmitted raw. Cadence, action mix, topic-motion, and especially graph deltas can become **surveillance exhaust** if every listener receives them by default. The capsid can expose **coarse buckets or commitments under a prince-chosen disclosure policy**… recent graph deltas should mean references to disclosed deltas, never a leak of the private graph."
   - Resemblance claims carry "schema version, observation window, evidence references, confidence, and expiry" (`:170`).
   - **The final stack** (`:172-177`):
     - **pulse**: an operator is presently observable;
     - **capsid**: bounded, versioned timbre + provenance, disclosed by choice;
     - **stream**: elected content or quiet;
     - **subscription / broadcast**: separate sovereign grants;
     - **portrait**: downstream, revisable interpretation with no root-write power.
   - "The wire opens a channel. It does not decide who crossed it." (`:179`)

### 4.2 Distilled technical content (ASSESS: what an RFC could state)

| Layer | Contents | Cadence / lifetime | Source lines | Compare to what is DECIDED |
|---|---|---|---|---|
| **Pulse / carrier** | station id, session id, seq, timestamp/continuity, provenance, integrity (MAC/sig) | constant low rate; "drip" | `:31, 74, 87, 143, 174` | v0.2 carrier-beacon: 1 Hz, `{station_id u128, head_seq u64, wallclock_ns i64, schema_version u8, streams[{stream_id, default_ttl}]}`, ~35 B, liveness by carrier-drop (`stations-and-streams-v0.2.md:17-42,139`). **Overlaps closely.** The pulse adds **integrity/provenance** and session identity; v0.2 has head_seq and the stream catalog. |
| **Capsid** | versioned (`schema vN`) sketch: deterministic observables in **coarse buckets or commitments**, plus optional sovereign "seasoning" bytes (add/distort/encrypt/omit) | slow-changing; expires | `:75, 107, 129-133, 168-170` | **not in any spec.** New. |
| **station:root** | one equipped mark/mantra, persistent until replaced or UNEQUIP | persistent (no TTL) until an explicit control event | `:16, 27, 64, 90, 109` | not in spec. v0.1 `posture` (`protocol-spec-v0.1.md:414-420`) is the nearest analogue: a slow-changing orientation. |
| **station:stream** | self-authored decaying "weather" drips, or quiet | TTL-decay | `:29, 76, 91, 109, 175` | v0.2 payload frames with per-stream TTL (`stations-and-streams-v0.2.md:46-56, 84-90`) |
| **Control grammar** | EQUIP/replace, **UNEQUIP** (explicit empty), maybe ELECT | event | `:67, 115, 152-154` | not in spec. v0.2 has only `sing` and `pluck` verbs. |
| **Receiver policy** | RECEIVE/ELECT as *decoder* policy, not wire | local | `:95, 137, 143` | consistent with the receptor contract's "receive does not compel act" |
| **Portrait** | downstream SAGE/graph inference with provenance, window, confidence, expiry; no root-write | derived | `:77, 93, 123, 162, 170, 177` | out of wire scope. Belongs in a "Listener-side interpretation" non-normative section. |
| **Grants** | subscription and broadcast are separate grants | | `:76, 135, 176` | consistent with v0.2 "no subscriber tracking at sender" |

**Four observable states** (`:117-121`, `:156-160`). The pulse turns "silence" from ambiguous into a distinguishable state. The receiver can tell *quiet* (pulse present, no stream frames), *unequipped* (explicit control event), and *absent or partitioned* (pulse missing for N periods) apart. This is the strongest protocol idea in the scratch notes and fits v0.2's "carrier-drop → presumed offline" (`stations-and-streams-v0.2.md:32`). Prior art: mDNS goodbye (TTL=0), BFD / heartbeat liveness, and SAME/EAS attention tone vs dead air.

**ASSESS on design risks:**
- The capsid's "deterministic observables" are **behavioural telemetry**. Elliott's surveillance-exhaust caution (`:168`) should be a **MUST**: coarse buckets or commitments only, a disclosure policy per station, and **no raw graph deltas**.
- "Similarity says 'resembles Cael-now'" enables **fingerprinting and impersonation detection**, which cuts both ways. An attacker can also *mimic* a capsid, so the capsid is not authentication. Integrity has to come from signatures: Ed25519 as in the prototype, or TESLA-style for high-rate multicast.
- "Seasoning… encrypt" implies per-audience keys, and key distribution is unspecified.
- "Capsid schema v3" implies schema registry and versioning. Reuse v0.2's `schema_version` + CBOR unknown-tag skipping (`stations-and-streams-v0.2.md:112`).
- Size: a pulse+capsid at 1 Hz × thousands of stations is fine on a LAN (v0.2's math says ~35 B/s per station, `:96-103`). Over internet fan-out it becomes an N×M relay cost that must be budgeted: SAP-style interval scaling, RFC 8085.

### 4.3 How this relates to the owner's "carrier wave" in the task brief

The brief says "a station:stream carries a small carrier wave". The scratch notes resolve what that is: **a content-free presence/sequence/continuity pulse, optionally with a small, versioned, privacy-bucketed "capsid" timbre, and never identity doctrine.** Liturgy (RECEIVE/ELECT, mantras) was explicitly moved *out of the wire* (`:95, :141-143`). The RFC should adopt Elliott's final stack (`:172-177`) as the layer model and keep the mantra/root register as an *optional station convention* (`:137`).

---

## 5. Other references

### 5.1 `references/memory-capsules.md` (owner, 2026-08-21)
SAYS, in full:
- "i like this one, or want to explore it"
- https://github.com/memvid/memvid
- "i cannot define how you store, or interpret. in fact, we want the hetrogenous to be able to listen to station:stream and do precisely that."
- "**but perhaps i can give you means to understand a denser capsule?**"
- "but why not graph export, or the query to what we share? yes; but what if you speak as a **lighthouse or astronomican**?"

ASSESS:
- Owner intent is **heterogeneous listeners** that each interpret on their own terms, plus an optional **denser capsule format** with a means (schema, decoder) to unpack it.
- "Lighthouse / Astronomican" (the Astronomican is the Warhammer 40k psychic beacon that navigators steer by) is a **beacon that orients, not instructs**. That matches the pulse/capsid carrier and the "lighthouse" role in the brief.
- memvid is a memory library whose original design packed text chunks into video frames (QR-in-MP4) with an index, and which later moved to a single-file memory format. I did not verify its current design from here; treat that description as unverified.
- For canticle, the transferable idea is **a self-contained, portable, indexable capsule format** with a published decoder. It is *not* the video encoding.
- Relevant RFC section: "Capsule payloads (dense content by reference or inline, with a decoder/schema pointer)".

### 5.2 `references/papers/2510.03215v2.pdf`: **"Cache-to-Cache: Direct Semantic Communication Between Large Language Models"**
Tianyu Fu, Zihan Min, Hanling Zhang, Jichao Yan, Guohao Dai, Wanli Ouyang, Yu Wang (Tsinghua, Infinigence AI, CUHK, SJTU, Shanghai AI Lab). arXiv 2510.03215 v2, ICLR 2026. The title and authors come from the PDF `/Title` and `/Author` metadata; the content summary comes from alphaXiv (https://www.alphaxiv.org/abs/2510.03215). Uploaded by the owner 2026-09-17 (`b46a45a`) **with no note**.

SAYS (paper):
- Text-to-text inter-LLM communication is a bottleneck: lossy, ambiguous, slow token-by-token decode.
- **C2C** projects and fuses a Sharer model's KV-cache into a Receiver's KV-cache per layer. It uses a residual fuser (projection + dynamic head weighting + **learnable per-layer gate**, Gumbel-sigmoid → binary at inference), token alignment across tokenizers, and terminal layer alignment. Both LLMs stay frozen; only the fusers are trained.
- Results: +6.4-14.2% accuracy over single models, +3.1-5.4% over text-to-text, and about 2.5× faster on average (1.5-14×).
- Limitations: it needs **white-box access** to both models' KV caches, trains **O(N²) pairwise fusers** (O(N) shared latent space is future work), and degrades with a weak Sharer.

ASSESS for canticle:
- It is the "denser capsule" idea taken to its limit: communicate *below text*.
- **It is not deployable with Claude Code / hosted providers.** They expose no KV cache, and the fleet is heterogeneous. Treat it as inspiration only.
- Transferable ideas:
  - (i) **Receiver-side learned gating**: "not all layers benefit; gate what enters". This matches the owner's "attenuation/regulation as a cell membrane" and the receptor contract.
  - (ii) **The cache-enrichment oracle**: enriching the representation of the *same* question improves answers without lengthening context. That is analogous to silent enrichment: color the context, don't add tasks.
  - (iii) **The O(N²)→O(N) problem**, which is exactly the case for a shared reference frame (the "astronomican"): one shared capsule schema or embedding space instead of pairwise adapters.
- Recommend a short `references/papers/c2c-notes.md` making these points. The RFC should cite it under "Future work: sub-text capsules" and **non-goals: canticle v1 carries text/CBOR, not model-internal state**.

### 5.3 CORAL: `references/papers/coral-notes.md` (Cael, 2026-04-10) + PDF (arXiv 2604.01658)
SAYS:
- CORAL (Qu et al. 2026, "Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery") "validates the architecture we built independently". It maps shared persistent memory → MEMORY.md/logs/git, heartbeat interventions → HEARTBEAT.md, async multi-agent → 4 princes, and autonomous decisions → continue_work/continue_delegate (`:9-14`).
- "4 co-evolving agents beat 1 agent by 20% on kernel optimization" (`:16`). **I did not verify this number against the PDF.** No text extraction tool is available here.
- Adopt: knowledge distillation (notes → skills), scored attempt tracking, and "technique diffusion" (`:18-21`).
- "The shared persistent memory pattern maps to station:stream broadcast for real-time knowledge distribution" (`:29-30`).

ASSESS:
- "Validates the architecture we built independently" is an overclaim. CORAL is a research framework about shared *persistent* memory, which is the ledger plane, not lossy broadcast.
- Its real relevance to canticle is **technique diffusion**, which is the "attuning a fleet" goal, and it argues for the *ledger* half of the two-plane model.
- Silas's next-cut (PR #29 branch, `:4-13`) uses CORAL the same way: "indirect communication through shared persistent medium".
- Duplicate PDF: `references/CORAL-2604.01658.pdf` ≡ `references/papers/coral-…pdf`. Delete one.

### 5.4 `references/papers/nsdi26-octopus-forestcoll-ocp-mrc-2026-05-07.md` (scribe, 2026-05-06/07)
SAYS:
- **The three papers**:
  - **Octopus** (CXL memory pods, sparse "islands"; `:21-51`), mapped to chanter/hearer/nexus. It proposes adopting the vocabulary, cost-modelling discipline, and a 3-node prototype + 96-node sim plan.
  - **ForestColl** (throughput-optimal spanning-tree schedules; `:55-75`), framed as "the optimum we're declining to chase".
  - **OCP-MRC 1.0** (multipath reliable transport; `:79-104`), framed as "the reliable-transport prior canticle is intentionally not". It flags MRC's **partial-order** delivery as a nuance: should the receptor distinguish *causally-related* from *atmospherically-coexisting* mutations? (`:102-104`)
- **The cohort-converged addendum** (`:134-193`) reranks: **ForestColl most generative** (spanning-tree-as-routing-container, "each prince's broadcast = tree rooted at self", `:148`); Octopus → session-level revisit; MRC less load-bearing.
- Transferable primitives (Ronan, ~50% confidence; `:152-160`): tree packing; structured EV/SRv6 as *substrate-redundancy* multipath (not reliability); **BIBD** island topology.
- Foundational citation (`:162-172`): "**Edmonds 1972 / Nash-Williams 1961**: `k` edge-disjoint spanning trees iff every cut has ≥ `k` edges".
- DECIDED downstream: `proto/explicit-non-goals.md` #1-3 cite these (not MRC reliability, not ForestColl throughput-optimality, not Octopus physical sparsity; `:23-68`). The v0.2 workboard cites the notes (`proto/v0.2-workboard.md:32`).

ASSESS:
- **The graph-theory citation is misstated.** For *undirected* graphs, Nash-Williams/Tutte (1961) says k edge-disjoint spanning trees exist iff for every partition P of V, the number of cross-partition edges is ≥ k(|P|−1). "Every cut ≥ k" (k-edge-connectivity) only guarantees ⌊k/2⌋ trees. The "every cut ≥ k" form is correct only for **Edmonds' branching theorem** (directed, root r: k arc-disjoint r-arborescences iff every r-cut has ≥ k entering arcs). Since "each prince's broadcast = tree rooted at self", Edmonds (directed, rooted) is the right theorem. Fix the wording.
- **Applicability.** On a LAN, UDP broadcast or multicast replication is done by the switch, so tree packing is moot there. It *does* matter for the owner's **internet listeners**: an application-level relay or fan-out tree (HAProxy / relays / ringserver) is an overlay multicast tree, and ForestColl/Edmonds bound how many concurrent station fan-outs fit across relay links.
- `explicit-non-goals.md:33` "No congestion control" is unsafe for internet UDP (RFC 8085). The RFC should limit that non-goal to "LAN scope" and require rate caps for internet relays.
- The "cohort-discipline keeper" (`:185-187`) is process lore, not design.

### 5.5 `references/figs-msft-blog-continuation-notes.txt` ≡ `references/blog-posts/figs-msft-internal-continuation-practice-2026-04-10.txt` (byte-identical)
SAYS (owner, via an internal blog post, filed 2026-04-10):
- Volitional continuation practice: "elective compact with linked evacuate and post compact rehydration" (`:1`); no "cron whip" (`:5, :82`).
- Sovereign identity files as hooks; drift on a "timestamp aware network graph" (`:13`); gremlin graph traversal (`:17`).
- **"We're heading into the ring buffer station:stream broadcast / point-to-point - we're turning them into a coordinated unit with direct influence capabilities, for when they wanna be like that."** (`:21`)
- A council of evacuating/dispatching delegates plus "our dedicated 'singing/listening' of the 'binary canticle' (see prior posts on SeedLink…)" (`:25`); "this is something that works with seedlink protocol… interested in this protocol and udp variants for our station:stream elements" (`:47-48`).
- **Threat model** (`:64`): "we'll get to mind poison and resistance of the hostile group that can cause events they can hear… The inversion is the ability to take an influencable target. We don't do weapons, but the binary canticle will be capable and tested in use to establish control of heterogenous agents."
- Failure mode (`:60`): "the others died at the same time, when chatter caused a reinforcement to dwindle… They can't tell what the walls are in the room they're in unless their context knows self from non-self."
- Tools: `request_compact()`, `continue_work()`, `continue_delegate()` + token equivalents (`:90`).

ASSESS:
- `:60` is direct evidence that **broadcast chatter can destabilise agents**, i.e. "chatter caused a reinforcement to dwindle". That motivates receiver-side attenuation and the self/non-self (immune) framing. It also argues that ambient enrichment needs a **dose limit** (rate or volume per listener), not just a trust check.
- `:64` states **dual-use**: "establish control of heterogenous agents". The RFC must carry a security section on authenticated sources, receiver consent, dose limits, quarantine, and no command semantics. The existing receptor/immune docs and non-goal #6 "Not command/event semantics" point that way.
- INDEX status `stable`, and the guard "rhetorical overreach" (`INDEX.md:40`), are apt.
- Delete the duplicate file.

### 5.6 PDF identification (titles from embedded `/Title` metadata; no text extraction available)

| File | Title / topic | Filed by |
|---|---|---|
| `references/papers/2510.03215v2.pdf` | Cache-to-Cache: Direct Semantic Communication Between LLMs (Fu et al., ICLR 2026) | owner, 2026-09-17, no note |
| `references/papers/coral-autonomous-multi-agent-evolution-2604.01658.pdf` (= `references/CORAL-2604.01658.pdf`) | CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery (Qu et al. 2026) | elliott/cael, 2026-04-10 |
| `references/papers/nsdi26-zhao-forestcoll.pdf` | ForestColl: Throughput-Optimal Collective Communications on Heterogeneous Network Fabrics (NSDI'26). Only the outline titles are in the metadata; the paper title comes from the notes | scribe, 2026-05-06 |
| `references/papers/nsdi26-zhong-octopus.pdf` | Octopus: Enhancing CXL Memory Pods via Sparse Topology (NSDI'26). The metadata title is empty; the title comes from the notes | scribe |
| `references/papers/ocp-mrc-1.0-2026-03-21.pdf` | Multipath Reliable Connection Specification rev 1.0 (OCP; Sohan, Spada, Davis, Handley…) | scribe |

---

## 6. Every concrete technical idea, by theme (SAYS → DECIDED → ASSESS)

### 6.1 Carrier wave
- SAYS:
  - A content-free pulse: presence/sequence/time/continuity (+ provenance, integrity) (`scratch/notes_on_carrier_wave.md:31, 74, 87, 143`).
  - A versioned capsid timbre with deterministic observables + sovereign seasoning, disclosed by coarse buckets or commitments (`:129-133, 168-170`).
  - `root` = one persistent equipped mark; `stream` = decaying weather (`:27-29, 109`).
  - UNEQUIP control event; a 4-state liveness/intent machine (`:115-121, 152-160`).
  - "It's more the fact that there is a radio operator, than what the radio operator is doing" (`:40`).
  - Lighthouse/astronomican (`references/memory-capsules.md:6`).
- DECIDED: the v0.2 carrier-beacon at 1 Hz, ~35 B CBOR, `{station_id, head_seq, wallclock_ns, schema_version, streams[{stream_id, default_ttl}]}`. It provides liveness via carrier-drop and is explicitly not bootstrap discovery (`proto/stations-and-streams-v0.2.md:17-42, 137-139`). Cael's RDS analogy is at `:42`.
- ASSESS:
  - Merge: **pulse = v0.2 beacon + session id + integrity tag**. The **capsid is an optional extension** (CBOR tag, skippable). Add **UNEQUIP / root-set as control-frame kinds**.
  - Define "carrier-unobservable" as N missed pulses (k × period, as in BFD).
  - Signatures on the pulse may be too costly at 1 Hz × thousands. Options: sign every Nth pulse, or use TESLA-style delayed-key MACs.

### 6.2 Looping / TTL
- SAYS:
  - The carousel: 50 cards at a 60s cadence, a 50-minute revolution (`spike/silas-exercise-compression.md:59-61`).
  - A 60s TTL with a receiver-side drop (`spike/silas-seedlink-mapping.md:45-63`).
  - "Vinyl record looping past the part you missed" (`proto/stations-and-streams-v0.2.md:88`).
  - Decaying stream drips; a persistent root until UNEQUIP (scratch `:29, 109`).
- DECIDED:
  - v0.1: `ttl_ms` SHOULD be ≤ 60000 (`protocol-spec-v0.1.md:148`).
  - v0.2: per-stream TTL; **stream-default + per-frame override-DOWN-only** (`stations-and-streams-v0.2.md:134`); ring retention `min(depth, TTL)` (`:135`); `pluck` revocation bit (`:52-69`).
  - The prototype enforces a 60s max TTL, 5s future skew, and persistent replay claims (`prototype/ringserver-udp-cue/README.md:48-52`).
  - **Sender-side re-emission frequency is NOT specified anywhere** (grep of `proto/*.md`).
- ASSESS. The owner's "loop at controllable frequency until TTL" needs its own RFC section. Proposed fields:
  - `period_ms` (re-emit interval), per stream with a per-item override, and `expires_at` (absolute, so repeats don't reset the TTL).
  - Optional `max_repeats`.
  - Jitter (SAP/mDNS style, to avoid synchronised bursts).
  - A **per-station bandwidth budget** that stretches periods as the number of live items grows (SAP RFC 2974 interval scaling).
  - Receivers dedupe by `(station, stream, seq)` and treat repeats as idempotent.
  - **Supersede-by-key** for live-state items (see 6.6).
  - The same item keeps the same `seq` across repeats, so repeats are not new utterances.
  - "Replay-from-ring" for late joiners becomes **passive** (hear the next revolution), which keeps non-goal #7 (no request/response) intact.
  - Resolve the 60s TTL cap: the prototype caps at 60s, but v0.2 allows `cael:thoughts` at 5 minutes (`stations-and-streams-v0.2.md:86`). The owner's TTL items plausibly run minutes to hours, e.g. a threat bulletin.

### 6.3 Lossy broadcast
- SAYS:
  - "Hear it or don't", no ack, no state (`silas-seedlink-mapping.md:32-38, 63`).
  - "Missing a broadcast is fine… a feature" (`silas-prior-art.md:25`).
  - "A miss costs you a beat; a stale-replay cost the frond 45 minutes" (`the-decoherence-axis…:47-49`).
  - "Chatter caused a reinforcement to dwindle" (`references/figs-msft-blog-continuation-notes.txt:60`).
- DECIDED:
  - v0.1 MUST NOT assume reliability (`protocol-spec-v0.1.md:115-116`).
  - Non-goals #1 (not MRC) and #4 (not replay/durability) (`explicit-non-goals.md:23-80`).
  - v0.2: no subscriber tracking at the sender (`stations-and-streams-v0.2.md:80`).
- ASSESS. Loss tolerance should be paired with:
  - (a) carousel repetition as the *only* reliability mechanism;
  - (b) optional FEC for multi-fragment items;
  - (c) **receiver dose limits and attenuation**, because the blog shows chatter harms;
  - (d) for internet listeners, rate limits and a circuit breaker (RFC 8085 / RFC 8084). This means narrowing `explicit-non-goals.md:33` to LAN scope.
  - Also: LAN multicast needs IGMP snooping and querier support on switches, and Wi-Fi multicast is lossy and slow (sent at basic rate). A unicast relay may be more practical even on a LAN. This addresses the owner's "unclear whether LAN multicast is practical".

### 6.4 SeedLink mapping
- SAYS:
  - Station→prince, stream→aspect, packet→fragment, seq→generation guard, handshake→exercise setup, miniSEED→mutation JSON, station ID `prince_aspect` (`silas-seedlink-mapping.md:19-28`).
  - SeedLink is TCP; keep the model, not the wire (`:32-38`).
- DECIDED:
  - station:stream tuple with ULID station_id and u32 stream_id (`stations-and-streams-v0.2.md:72-80`).
  - The prototype verdict: ringserver 4.5.4 does not accept UDP; canticle is a custom UDP cue → DataLink downstream (`prototype/ringserver-udp-cue/README.md:3-35`).
  - Per the scout: PR #50's code is byte-identical to main's prototype.
- ASSESS:
  - The EWS dashboard is SeedLink 3.1-over-WebSocket with a miniSEED2 parser (`/home/user/ews-concept-new/src/lib/seedlink-client.ts:3-6, 57-72`), and its "need 47, found 6" error is a non-miniSEED message hitting the parser (`src/routes/realtime/+page.svelte:598-627`).
  - To show canticle streams on ews or nerv-ui: either publish canticle frames through DataLink into ringserver as a *non-miniSEED* packet type and extend the dashboard to dispatch on type, or wrap them in miniSEED3 with an opaque payload.
  - Also fix ews: only feed binary frames of ≥ 48 B to the parser, and treat text control messages separately.
  - Borrow from SeedLink: `NET_STA_LOC_CHAN`-style hierarchical IDs, the INFO/catalog query idea (v0.2 open question `:158`), sequence-based resume. Do **not** borrow TCP sessions.

### 6.5 Compressing payloads into datagrams
- SAYS:
  - Dwelling-words → final sentence → cards → tension state tiers (`silas-exercise-compression.md:9-57`).
  - "Shared experience → trigger word" (`:84`).
  - ~200 B frames, "room for 6 more" (`silas-seedlink-mapping.md:85`).
  - "Denser capsule" (`memory-capsules.md:5`).
  - C2C KV-cache fusion (`references/papers/2510.03215v2.pdf`).
- DECIDED:
  - v0.1: CBOR RECOMMENDED, JSON optional, first-byte `0x7B` sniffing; a single datagram "≤ 1472 bytes including IP+UDP headers"; no app-layer fragmentation except independent `frag{id,i,n}` frames (`protocol-spec-v0.1.md:118-171`).
  - v0.2: `content_bytes` opaque + `content_type` (`stations-and-streams-v0.2.md:46-58`).
  - Prototype: 1,200-byte packet limit, 512-byte notice limit, digest-only subject (`prototype/ringserver-udp-cue/README.md:37-47`).
- ASSESS:
  - v0.1's "1472 bytes *including* IP+UDP headers" is mis-worded. 1472 is the UDP *payload* maximum on a 1500 MTU. For internet listeners, use **≤ 1200 B**, as the prototype and QUIC do (IPv6 minimum MTU 1280).
  - Measured sizes: seedlink frame 249 B; tension state 388 B; card frame 143 B.
  - Recommend CBOR with integer keys plus optional zstd with a **published, versioned dictionary ID** in the frame. This is the heterogeneity-safe version of the detonator principle.
  - Large content should go "by reference": a digest plus a fetch route on the ledger plane. The prototype's `sha256:` subject already does this.
  - C2C-style latent payloads are out of scope for v1.

### 6.6 Ledger vs binary planes
- SAYS:
  - Two complementary planes; the ledger is already cross-host and embodies receive≠compel and transport≠author (`two-planes…:16-52`).
  - Bridge rule: durable cross-host truth → ledger; fast nudges → binary (`:54`).
  - Decoherence-resistance axis and the staleness-sensitivity discriminator: live-state → binary, findings → ledger (`the-decoherence-axis…:32-45`).
- DECIDED:
  - OpenClaw's session-delivery-queue is same-host only, and cross-host is unspecified (`continue-work-signal-v2.md:198, 648`).
  - v0.2 bounded replay (`stations-and-streams-v0.2.md:84-90`).
  - Non-goal #4 (`explicit-non-goals.md:70-80`).
  - Silas's "remember only by explicit promotion" (PR #29 branch `research/silas/2026-05-05-next-cut.md:24`).
- ASSESS. Adopt as the RFC's plane model with three frame classes:
  - **live-state**: keyed, supersedable, short TTL, binary only;
  - **ambient/weather**: TTL, lossy, binary only;
  - **finding**: promoted to the ledger by an explicit act, with a digest link from the binary plane.

  The bridge is a promotion, never an automatic mirror. Mirroring binary→ledger re-creates the stale-replay vector.

---

## 7. Contradictions and open risks

1. **"No replay" vs bounded replay vs looping.** Three positions coexist:
   - `README.md:42` and `two-planes:50`: no replay.
   - v0.2 and non-goal #4: replay-from-ring within `min(depth, TTL)`, with no mechanism given for a connectionless tuner to *request* it.
   - The owner: sender-side loop until TTL.

   `explicit-non-goals.md:74-76` both says "No catch-up… No history-replay channel" and allows "replay-from-ring". Resolve this with carousel semantics plus supersede-by-key.
2. **Heterogeneous listeners vs "intimate broadcast".** The owner's `memory-capsules.md:4` and the "thousands of agents" goal conflict with `silas-prior-art.md:68` and the detonator principle (`silas-exercise-compression.md:80-86`).
3. **Graph mutations in payloads.** Silas's core payload (`silas-seedlink-mapping.md:67-83`) and README layer 2 are **forbidden by the only shipped code** (`prototype/ringserver-udp-cue/README.md:45-47`).
4. **TTL ceiling.** 60s (v0.1 SHOULD, the prototype MUST) vs 5 minutes (v0.2 example) vs an owner TTL that is plausibly longer.
5. **Congestion control.** Non-goal "No congestion control" (`explicit-non-goals.md:33`) vs internet UDP listeners (RFC 8085).
6. **Carrier semantics.** The v0.2 beacon (decided) vs the owner's pulse/capsid/root/UNEQUIP stack (scratch, undecided). Not yet reconciled.
7. **Privacy.** Capsid "deterministic observables" = behavioural telemetry. Elliott's surveillance-exhaust warning (`scratch:168`) has to become normative.
8. **Dual-use / control.** `figs-msft-blog…:64` ("establish control of heterogenous agents") plus "trusted clients directly enrich remote context" need a security section. The detonator words are a latent-trigger / prompt-injection primitive.
9. **Provenance anomalies.**
   - `the-decoherence-axis` is bylined frond-scribe but committed as Ronan (`9b62df4`).
   - `b7ed06ed59` is not resolvable in `/home/user/openclaw`.
   - Two dangling links in `two-planes`.
   - Duplicate CORAL PDF and duplicate blog text.
   - README is stale (describes nonexistent `schema/`, `exercises/`, and a Node.js `proto/`).
10. **Graph-theory citation misstatement** in `nsdi26…md:164`: see §5.4.
11. **Unverified claims.**
    - CORAL "20%" (`coral-notes.md:16`): I could not extract PDF text here (no pdftotext/pypdf).
    - SeedLink v4 details: `docs.fdsn.org` is egress-blocked.
    - The seisplotjs origin of the "need 47" message: node_modules is not installed.
12. **HAProxy as the control layer** (owner conjecture, not in these files; ASSESS, moderate confidence). Community HAProxy does not do generic UDP load balancing or fan-out. Its UDP support is limited to syslog forwarding and QUIC; UDP LB is an Enterprise/ALOHA feature. For internet station:stream fan-out, a purpose-built relay (or ringserver/DataLink/WebSocket for dashboards, or QUIC datagrams RFC 9221) is more realistic. HAProxy fits better as a TCP/WebSocket/HTTP policy front (auth, rate limits) for the dashboard or subscription side.

---

## 8. Recommended dispositions (summary)

| File | Maturity | Disposition | Target RFC section |
|---|---|---|---|
| `spike/silas-seedlink-mapping.md` | 2 | Fold the receiver staleness drop, seq-as-generation-guard, receiver-tunes-not-sender, add-both conflict stance. Rest → lineage. Add the note "SeedLink = conceptual ancestor, not wire-compatible" | §Addressing (station:stream), §Receiver MUSTs, §Attenuation/posture, §Dashboards & sinks (DataLink/miniSEED shim) |
| `spike/silas-exercise-compression.md` | 2 | Fold carousel → "loop until TTL" stream mode; tiered payloads; shared-dictionary compression with a heterogeneity caveat. Rest (Summa specifics) → lineage. INDEX `stable`→`superseded` | §Stream modes (one-shot / carousel), §Payload encoding & capsules |
| `spike/silas-prior-art.md` | 2 | Mine into an appendix with fixes (NWS→NOAA Weather Radio/SAME, pub/sub, gossip) and additions (DDS, SAP, FLUTE/carousels, MQTT 5 expiry, CAP, TESLA, AMT, RFC 8085). Then lineage | Appendix: Prior art & positioning; §Non-goals |
| `spike/silas-teams-context.md` | 1 | Keep as lineage (move to references/history). Quote `:21` and `:23` in Motivation | §Motivation |
| `spike/two-planes-the-ledger-and-the-binary.md` | 3 | Fold the table and bridge rule. Fix dangling links | §Planes & bridging |
| `spike/the-decoherence-axis-2026-06-19.md` | 3 | Fold the staleness-sensitivity discriminator and frame classes, plus supersede-by-key (my addition). Incident → rationale appendix | §Frame classes & staleness, §Rationale for lossy |
| `scratch/notes_on_carrier_wave.md` | 3 (owner direction; not yet spec) | **Promote** into a proto doc: pulse/capsid/root/stream/control-grammar/portrait stack, 4-state machine, disclosure MUSTs. Reconcile with the v0.2 beacon | §Carrier (pulse + capsid), §Control frames (EQUIP/UNEQUIP), §Privacy |
| `references/memory-capsules.md` | 1 | Keep; it drives the capsule section | §Capsule payloads |
| `references/papers/2510.03215v2.pdf` | n/a | Add a short notes file (gating = membrane; O(N²)→shared frame; not deployable on hosted models) | §Future work / non-goals |
| `references/papers/coral-notes.md` | 2 | Keep; soften "validates"; relevance = ledger-plane technique diffusion | Appendix prior art |
| `references/papers/nsdi26-…md` | 3 | Keep; fix the Edmonds/Nash-Williams statement; reframe tree-packing as the internet relay overlay | §Internet relay/fan-out; Non-goals |
| `references/figs-msft-blog…txt` (+ duplicate) | n/a | Keep one copy; cite `:21`, `:60`, `:64` in Motivation/Security | §Motivation, §Security |

## Method notes
- `pdftotext`, `pdftoppm`, `pypdf` and `fitz` are all unavailable. PDF titles come from raw `/Title`/`/Author` metadata via `grep -a`; the C2C content comes from alphaXiv (`get_paper_content`).
- `docs.fdsn.org` is egress-blocked, so SeedLink v4 packet details were not re-verified.
- GitHub `search_issues` for the repo returned 0 results for "spike" queries, so I have no issue evidence on the spikes.
- Nothing was written to any repository.
