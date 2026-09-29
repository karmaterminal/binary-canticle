# spec-core — Binary Canticle core protocol documents (backbone notes for RFC-0001)

Reader: spec-core. Repo `/home/user/binary-canticle` at `main` = `b46a45a`. Read-only; nothing written to GitHub.

Files read in full:

| File | Lines | Last commit(s) touching it | Status as stated |
|---|---|---|---|
| `proto/protocol-spec-v0.1.md` | 625 | `b7b132c` 2026-05-04 (initial), `5a3c0e8` 2026-06-24 (Silas, "clarify canticle discovery seam", via PR #41) | "v0.1 — frond-scribe initial draft", "research-quality protocol spec, not a wire-stable RFC" (:10-15). INDEX status `active`, next action "revise into v0.2 spec shell" (`proto/INDEX.md:19`), which has not happened. |
| `proto/stations-and-streams-v0.2.md` | 171 | `b82a5a2` 2026-05-06 (capture), `6fc78f5` 2026-06-24 (Elliott, promote to pressure-test), `5a3c0e8` 2026-06-24 | `pressure-test` (:3, :162; `proto/INDEX.md:30`) |
| `proto/stations-and-streams-v0.2-open-questions-bytewalk-cael.md` | 113 | `07e4e58` 2026-06-15 (Cael), landed via PR #42 (#32 is still open with byte-identical content) | "proposed resolutions … a proposal for cohort pressure-test, not a unilateral spec change" (:3) |
| `proto/receptor-contract-v0.2.md` | 578 | 12 commits, all 2026-05-05 (Ronan): `ed4f7ba` → `dcc994b` | "minimal contract, not a full protocol spec" (:9); INDEX `active` (`INDEX.md:21`) |
| `proto/ringbuffer-contract.md` | 196 | `0a49371`, `a5e7fb8`, both 2026-05-05 (Ronan) | "Draft"; INDEX `active` (`INDEX.md:34`) |

Supporting sources I consulted to check claims: `proto/explicit-non-goals.md`, `proto/scope-framing-and-noosphere-mapping.md`, `proto/immune-model-addendum.md` (headings only), `spike/silas-seedlink-mapping.md`, `prototype/ringserver-udp-cue/` (landed `65e6705`, 2026-07-25), `scratch/notes_on_carrier_wave.md` (owner-committed `f61e7ca`, 2026-08-23), and issues #30, #37, #38, #39, #40, #48, #51 (read via GitHub MCP).

Legend used below: **[SAYS]** = what the text states. **[DECIDED]** = accepted/landed and not contradicted elsewhere, or implemented in code. **[ASSESS]** = my own judgment.

---

## 0. Bottom line

- **[ASSESS]** No single normative spec exists. Two incompatible wire formats sit side by side: v0.1's string-keyed JSON/CBOR frame (`protocol-spec-v0.1.md:139-155`) and v0.2's ULID/u32 CBOR payload frame plus carrier-beacon (`stations-and-streams-v0.2.md:22-26, 49-55`). A third, different closed-schema signed JSON "cue" is the only code on `main` (`prototype/ringserver-udp-cue/README.md:41-58`). v0.2 says it "extends" v0.1 (`stations-and-streams-v0.2.md:145`). On the wire it replaces it: a v0.1-conformant receiver MUST silently drop every v0.2 frame, because v0.2 lacks the v0.1 required fields `v`, `ts`, `kind` and `payload` (`protocol-spec-v0.1.md:157-158`).
- **[ASSESS]** The owner's central semantic is missing from every core doc: **items LOOP (re-broadcast) at a controllable frequency until TTL expiry**. The closest material is:
  - the "revolving-record" intuition (`stations-and-streams-v0.2.md:3,7,88`);
  - "replay-from-ring" by late joiners (`:13, :87`).

  But the protocol forbids every way a hearer could ask for a replay. It has no tuner-to-station messages and no "since-token" (`explicit-non-goals.md:75,108`), and it is not RPC (`protocol-spec-v0.1.md:57-58`). So the replay the docs promise has no mechanism. **A station-side carousel (periodic re-broadcast of each live, un-plucked ring entry until expiry) is the only reading that fits all of the docs at once, and it is exactly what the owner asked for.** RFC-0001 should make that the normative replay mechanism.
- **[ASSESS]** Other things that are genuinely good and should be kept:
  - the carrier-beacon (presence, head-sync, liveness, retention contract);
  - the split of bootstrap discovery (DNS SRV/mDNS/static) from live presence (beacon);
  - the retention bound `min(depth, TTL)`;
  - TTL override-down-only;
  - pluck as a header bit;
  - "sender tracks nothing about hearers";
  - the receptor contract's raw-receipt vs interpreted-atmosphere split, evidence-bearing judgments and executable-example gate;
  - the ringbuffer contract's non-interpreting append/replay/tail with explicit truncation.
- **[ASSESS]** Four areas clash with the owner's intent and need deliberate change:
  1. v0.1 §9.2 hard-forbids waking a session on frame receipt (`:469, :473-474`). The owner wants listeners to notify other sessions and trusted clients to silently enrich remote context.
  2. Scope is LAN-only (`:84-86`, `stations-and-streams-v0.2.md:156`). The owner requires internet UDP listeners.
  3. TTL ceilings of about 60 s (`protocol-spec-v0.1.md:148`, prototype `receptor.py:23`) are too short for looping items.
  4. Trust is contradictory across four sources: HMAC provisional, LAN-trust with no signing, Ed25519 as a v0.3 overlay, and an Ed25519 fail-closed prototype. Issue #48 is still open.

---

## 1. The design as currently written

### 1.1 Positioning and non-goals

- **[SAYS]** Canticle is a "connectionless, broadcast, atmospheric enrichment substrate for persistent machine actors on a shared LAN … UDP datagrams with ~60s message lifetime. Receivers sample what's current; no subscription, no acknowledgment, no replay" (`protocol-spec-v0.1.md:26-30`).
- **[SAYS]** It is the signal plane, orthogonal to the control-plane substrate `karmaterminal/frond-scribe#128` (`:32-37`).
- **[SAYS]** What it is NOT (`:53-64`):
  - not a command channel;
  - not consensus;
  - not RPC ("No correlation IDs across frames", `:57-58`);
  - not reliable (drop, reorder and duplicate MUST be tolerated, `:59-60`);
  - "Not a weapon" (`:61-64`).
- **[SAYS]** It uses RFC-style MUST/SHOULD/MAY (`:66-70`), but does not cite RFC 2119/8174.
- **[SAYS]** v0.1 lists as "likely to change": the CBOR/JSON choice, the SRV naming (`_canticle._udp.thornfield.local` "is illustrative"), the ring eviction policy, and frond-rule enforcement (`:17-22`).

### 1.2 Frame envelope — field-by-field, with sizes

#### (a) v0.1 canonical frame (`protocol-spec-v0.1.md:139-155`), CBOR RECOMMENDED / JSON OPTIONAL

| Field | Type | Req | Semantics | Cite |
|---|---|---|---|---|
| `v` | uint | yes | protocol version; v0.1 frames use `v: 1` | :143 |
| `station` | string | yes | station-id (§4 grammar) | :144 |
| `stream` | string | yes | stream-id within station | :145 |
| `seq` | uint64 | yes | per-station-stream monotonic, wraps 2^64 | :146 |
| `ts` | uint64 | yes | Unix-epoch **microseconds**, issuer clock at emit | :147 |
| `ttl_ms` | uint32 | yes | validity window from `ts`; SHOULD ≤ 60000 | :148 |
| `kind` | string | yes | payload kind (§3.5) | :149 |
| `payload` | object | yes | kind-specific | :150 |
| `frag` | object | no | `{id: uuid-v4, i, n}` | :151, :166 |
| `provenance` | object | no | source pinning | :152 |
| `lens` | string | no | aspected-lens hint | :153 |
| `confidence` | float | no | [0,1] | :154 |
| `nonce` | bytes(8) | no | dedup "across multicast loops" | :155 |

- Unknown fields MUST be accepted. Frames missing required fields MUST be dropped silently (`:157-158`).
- Well-known kinds (`:175-182`):
  - `weather {sentence, tensions{topic: float}}`;
  - `mutation {op add|remove, node?, edge?{from,to,label}}`;
  - `card {exercise, round, card, dwelling?}`;
  - `posture {posture, since_ms}`;
  - `nexus.digest` (frond-scribe only);
  - `null-tick {}` (heartbeat).
- Unknown `kind` → MUST log-and-skip (`:184-185`).
- Size: "~150-500 bytes" (diagram `:81`). Hard cap "≤ 1472 bytes including IP+UDP headers on standard MTU 1500" (`:118-119`).
  - **[ASSESS]** That wording is wrong. 1472 is the UDP *payload* limit *excluding* the 28 bytes of IPv4+UDP headers (1500 − 20 − 8). Over IPv6 it is 1452. Over the internet a 1200-byte ceiling is the prudent choice; that is what the prototype uses (`codec.py:14`, `MAX_PACKET_SIZE = 1200`).
- Encoding sniff: first byte `0x7B` → JSON, else CBOR (`:132-134`). An IANA CBOR content-format tag is "TBD".
  - **[ASSESS]** The sniff is fragile. JSON with leading whitespace is misrouted to CBOR. It only works if CBOR frames are always maps (0xA0–0xBF); CBOR `0x7B` is a text string with an 8-byte length. Use a magic prefix instead: a fixed 2-byte signature plus version, or the RFC 8949 §3.4.6 self-described CBOR tag 55799.

#### (b) v0.2 carrier-beacon (`stations-and-streams-v0.2.md:22-26`; net shape repeated at `:139` and `bytewalk:92`)

```
{station_id: u128 (ULID native 16 bytes), head_seq: u64, wallclock_ns: i64,
 schema_version: u8, streams: [{stream_id: u32, default_ttl: u32}]}
```

- Rate and size: 1 Hz per station, "~35 bytes packed" (`:29`), plus about 8 bytes per stream (`bytewalk:89-92`; about 75 B for 5 streams).
- The original Elliott shape had `stream_count: u8` instead of `streams`. It was replaced in `6fc78f5` per Cael Q6 (`bytewalk:87,92`), yet the text still reads "Per Elliott" (`stations-and-streams-v0.2.md:19`). This is attribution drift.
- **[ASSESS]** ~35 B is only reachable with positional CBOR arrays or small-integer map keys. The string keys alone (`station_id`, `head_seq`, `wallclock_ns`, `schema_version`, `streams`) cost about 56 bytes. The docs never pin the CBOR key encoding (string keys, int keys, or array). Until they do, "CBOR-encoded" is not a wire format.
- `default_ttl` has no unit. By analogy with `ttl_seconds` it is presumably seconds.
- **[ASSESS]** Liveness threshold "N seconds" is unspecified (`:32`).

#### (c) v0.2 payload frame (`stations-and-streams-v0.2.md:49-55`)

```
{station_id: u128 ULID, stream_id: u32, seq: u64, ttl_seconds: u32,
 content_type: string, plucked_bit: u1, content_bytes: bytes (opaque)}
```

- `content_bytes` is opaque to the substrate and interpreted via `content_type` ("CBOR-of-CBOR fine, or wrapped MIME-typed string") (`:58`).
- Pluck is a header bit, not a separate frame type (`:58`).
- Typical payload is ~200 B at ~0.1 Hz (`:99`).
- **[ASSESS] Missing from the v0.2 payload frame:**
  - **any timestamp.** There is no `ts` or `issued_at`, so relative `ttl_seconds` has no anchor. A replayed or looped copy cannot state remaining life. This violates the remaining-life invariant Emeric set in #51 ("Remaining life never resets").
  - a version field; only the beacon carries `schema_version`, so a hearer that hears a payload before a beacon cannot know the schema.
  - `kind`, which v0.1 requires and receptor Table A requires (`receptor-contract-v0.2.md:124`).
  - nonce/digest/frame id.
  - signature (punted, `:122-126`).
  - fragmentation.
  - `plucked_bit: u1` is not a CBOR type. It needs a `flags` uint or a bool.

#### (d) Receptor Table A "normalized input frame" (`receptor-contract-v0.2.md:117-137`)

This is a post-adapter normalized record, not a wire frame:

- Required: `frameId`, `stationId`, `memberId`, `streamId`, `sequence`, `kind`, `emittedAt`, `observedAt`, `ttlMs`, `payload`.
- Optional: `chemokineClass`, `posture`, `bodyRef`, `bodyHash`, `signature`, `correlationId`, `inReplyTo`, `receiptRequested`, `adapterMeta`.
- Rule: `emittedAt` ≠ `observedAt` MUST stay distinct (`:141-142`).
- Rule: the receptor MUST NOT depend on `adapterMeta` (`:149-150`).

#### (e) Ringbuffer receipt record (`ringbuffer-contract.md:33-46`)

- Required: `station`, `stream`, `seq` (monotonic within station:stream), `ts`, `observed_at`, `content_type`, `payload` (opaque bytes/ref), `digest`.
- Optional: `ttl_ms`, `expires_at`, `receipt_of`, `parent_digest`.

#### (f) Implemented on `main` — prototype cue (`prototype/ringserver-udp-cue/README.md:41-58`; `codec.py:14-22`; `receptor.py:23-24`; `model.py:8-10`)

- Canonical JSON, ≤1200 B packet, ≤512 B notice object.
- Closed schema:
  - top level `{version, issuer, key_id, notice, signature}`;
  - `notice {kind ∈ {available, tombstone}, subject: "sha256:<64hex>", notice_id: 32hex, issued_at, expires_at}`.
- Unknown fields are **rejected**.
- Ed25519 is mandatory with no insecure fallback.
- Max TTL 60 s; max future skew 5 s.
- Persistent replay claims and tombstones.
- IPv4 loopback only.
- **[DECIDED/implemented]** This is the only running code. **[ASSESS]** It deliberately diverges from both specs:
  - closed schema vs forward-compat acceptance;
  - JSON vs CBOR;
  - absolute expiry vs relative TTL;
  - mandatory signatures vs "log unsigned, accept" (v0.1) or no signing (v0.2);
  - no payload at all, only a digest pointer.

### 1.3 Station:stream addressing and naming

- **[SAYS] v0.1** `station = <member>_<aspect>?`, where `member` and `aspect` each match `[a-z][a-z0-9-]{0,30}` (`protocol-spec-v0.1.md:193-196`).
  - A member may run many stations, one per aspect (`:199-206`: `silas_heresy`, `frond-scribe_cohort-weather`, `ronan`).
  - Rotating aspect silently retires the old id (`:208-211`).
  - `stream` subdivides a station. Well-known streams: `default`, `weather`, `mutations`, `cards`, `posture`, `digest` (`:215-225`).
  - Unknown streams are tolerated (`:227-228`).
  - Reserved prefixes: `frond-scribe_*`, `_test_*`, `_human_*` (`:230-236`).
  - **[ASSESS]** `_test_*` and `_human_*` violate the grammar `[a-z]…` that the same section defines. The scope doc adds a `relay_<frond>` reserved prefix (`scope-framing-and-noosphere-mapping.md:91-93`) that v0.1 §4.2 does not list.
- **[SAYS] v0.2** "**station:stream** is the primitive addressing tuple" (`stations-and-streams-v0.2.md:73`).
  - station = device/process, "1:1 with running processes" (`:75`).
  - stream = topic/channel, each with its own ring and TTL (`:76`); examples `cael:thoughts`, `cael:status`, `cael:song-3` (`:13`).
  - `station_id` is a 16-byte ULID on-wire (`:77`).
  - Tuners subscribe to tuples locally (`:78`).
  - "No subscriber tracking at sender side is load-bearing" (`:79`).
  - `stream_id` = u32, station-local, `truncate32(hash(stream_name))` (`bytewalk:18-22`; `stations-and-streams-v0.2.md:132`).
  - Collision policy is left to open issue #38, which says it should "block first adapter implementation".
  - **[ASSESS]** The hash function is unspecified.
  - **[ASSESS]** There is no name↔id mapping on the wire. The beacon excludes names and content types (`bytewalk:90`), so a tuner cannot learn that `0x1a2b3c4d` means `thoughts` unless it already knows the name and the hash. SRV/TXT carries string names (`protocol-spec-v0.1.md:276`) but no ULIDs. **Nothing binds human station names to ULIDs to keys** (#48 Q1 is open).
  - **[ASSESS]** Bytewalk Q1 treats the ULID's embedded timestamp as a restart signal (`bytewalk:22`). That implies `station_id` changes on every process restart. It conflicts with durable naming (SRV/TXT, `_human_figs`), with key binding, and with the SeedLink notion of a durable station code.
- **[SAYS] ringbuffer** The key is `station:stream` (strings) (`ringbuffer-contract.md:23-27`).
- **[SAYS] receptor** `stationId`, `memberId` and `streamId` are all strings; `memberId` is required "if separable" (`receptor-contract-v0.2.md:120-122`). v0.2 has no member concept.
- **[SAYS] owner scratch** (`scratch/notes_on_carrier_wave.md:27-29,64-65,90-91,109`) proposes:
  - `station:root`: one persistent, self-elected "mantra" register, persistent until replaced or UNEQUIPped;
  - `station:stream`: decaying weather deltas.
  - Not normative, but newer than all core docs and owner-committed.

### 1.4 The "carrier wave" / carrier-beacon

- **[SAYS]** A per-station 1 Hz frame with three jobs (`stations-and-streams-v0.2.md:29-32`):
  - presence (the station exists without subscribing to any stream);
  - head-sync (`head_seq` tells a late joiner where the head is);
  - liveness ("no beacon for N seconds → presumed offline").
- **[SAYS]** Per Q6 a fourth job was added: advertising each stream's retention contract (`default_ttl`) (`bytewalk:89`).
- **[SAYS]** It is "**not** bootstrap discovery": it does not tell a cold hearer the group, port or relay (`:34-40`).
- **[SAYS]** Cael: "RDS-shape … a tiny separate frame that's always-on" (`:42`).
- **[SAYS]** Owner scratch splits the carrier into (`notes_on_carrier_wave.md`):
  - **pulse**: "presence, sequence, time, continuity", "operator, provenance, sequence, continuity, and integrity" (`:62,74,87,143`);
  - **capsid**: an optional small versioned "timbre" sketch under a disclosure policy (`:75,129-135,168-177`).

  It also says silence must be distinguishable. There is an explicit UNEQUIP control event and a 4-state machine: equipped+speaking, equipped+quiet, unequipped+present, carrier unobservable (`:115-121,154-160`).
- **[ASSESS]** `head_seq` is a single u64 per *station*, but rings, TTLs and `seq` are per *stream*. v0.1 `:146` makes `seq` per station-stream, and the ringbuffer contract says `seq` is "monotonic within station:stream" (`:37`). A single station-level head cannot head-sync per-stream rings. **Either `seq` is station-global (unstated) or `head_seq` must move into `streams[]`.** This is an unacknowledged defect.
- **[ASSESS]** v0.1's `null-tick` heartbeat kind (`:182`) is functionally superseded by the beacon, but neither doc says so.

### 1.5 TTL, loop and re-broadcast semantics

- **[SAYS] v0.1** `ttl_ms` is counted from `ts` and SHOULD be ≤ 60 s (`:148`). `sing()` default TTL is 60000 (`:404-405`). Frames "live their TTL and expire" (`:347`). "no replay" (`:29-30`).
- **[SAYS] v0.2**
  - per-stream TTL with examples of thoughts at 5 min and status at 60 s (`:86`);
  - per-frame `ttl_seconds` may override only **down**; the station clamps `frame_ttl = min(frame_ttl, stream_default_ttl)` at sing-time (`bytewalk:38-44`; `stations-and-streams-v0.2.md:134`).
- **[SAYS] sing** "append a payload-frame to the station's ringbuffer … + carrier-beacon next cycle reflects the new head_seq". Tuners that join later "may or may not get it depending on TTL window" (`stations-and-streams-v0.2.md:66`).
- **[SAYS] Re-broadcast/loop**: nothing defines a repeat interval, repeat count, or who re-emits. The only mentions:
  - `nonce` "dedup across multicast loops" (`protocol-spec-v0.1.md:155`), which refers to network loops, not a carousel;
  - "revolving-record" (`stations-and-streams-v0.2.md:3,7`);
  - "loses those revolutions … vinyl record looping past the part you missed" (`:88`);
  - "Frames go out at the chanter's chosen cadence" (`explicit-non-goals.md:33`).
- **[ASSESS]** Read literally, the "revolving record" metaphor *is* a carousel. A record revolves, the station replays its ring, and a hearer who arrives within the window hears the loop. That reading is the only one consistent with all of these at once:
  - no tuner-to-station messages (`explicit-non-goals.md:108`);
  - no since-token (`:75`);
  - no subscriber tracking (`stations-and-streams-v0.2.md:79`);
  - "late-joining tuner … can replay-from-ring" (`:87`).

  RFC-0001 should state it explicitly. Each live, un-plucked ring entry is re-emitted **byte-identically**, with the same `seq`, the same absolute expiry and the same signature, every `repeat_interval` (per stream, optionally per item, station-clamped, jittered) until expiry or pluck. Hearers dedup on `(station_id, stream_id, seq)`.
- Also relevant: #51 (open, 2026-09-22) "Short-TTL disposition frames" and Emeric's review. They require:
  - remaining life never resets on replay/cache/restart;
  - expiry removes current-state authority everywhere;
  - silence is not a value;
  - no durable promotion by default;
  - rate is not intensity;
  - receivers must not trust the sender's wallclock to extend freshness.

  These are exactly the invariants a loop design needs.

### 1.6 Replay horizon and retention

- **[SAYS]** Retention is `min(depth, TTL)`. An entry leaves when its TTL expires OR depth pushes it out (`stations-and-streams-v0.2.md:90,135`; `bytewalk:52-61`).
- **[SAYS]** Depth is station-private and not advertised. TTL is the only legible retention contract (`bytewalk:59`).
- **[SAYS]** Honest contract: "at most TTL seconds, and at most depth frames, whichever is less" (`bytewalk:61`). #37 was closed 2026-06-25 by Elliott with the comment "Resolved by Q4 in PR #42" (the comment text is garbled).
  - **[ASSESS]** #37's acceptance criteria are not met: the receptor and ringbuffer contract text were not updated (last touched 2026-05-05), and there are no high-rate/sparse fixtures. It was closed on the strength of the design note alone.
- **[SAYS] hearer ring (v0.1 §6)** Per (station, stream), in hearer memory or SQLite (`:311-319`):
  - frames older than `ts+ttl_ms` MUST be evicted (`:319`);
  - depth SHOULD bound at 256 frames by default (`:320-322`);
  - FIFO eviction (`:323`);
  - read-many/no-consume (`:324-325`);
  - "ephemeral by spec"; archive MAY happen but the live ring MUST evict (`:347-349`).
- **[SAYS] ringbuffer contract**
  - "MUST drop old frames on explicit size/age bounds" (`:88-90`);
  - replayable in order within the surviving window (`:92-94`);
  - eviction first-class and inspectable: `truncated`, `oldest_seq/ts`, `newest_seq/ts` (`:96-103, :141-144`);
  - policy surfaces: max age, max depth, optional max bytes (`:136-139`).
- **[SAYS] non-goals** "No catch-up … No history-replay channel. No 'since-token' parameter" (`explicit-non-goals.md:75`). "Canticle does not store frames anywhere a missed-the-window tuner can fetch them" (`:76`).

### 1.7 Discovery (DNS SRV)

- **[SAYS]** v0.1 §5 was renamed "Bootstrap discovery" in `5a3c0e8` (PR #41, closing #36). It finds the UDP endpoint(s) and the optional metadata query surface. It does **not** do live presence, ring head, subscriber state, capability exchange or QoS (`:240-247`).
- **[SAYS]** Implementations MUST support SRV bootstrap and MAY support static config (`:249-250`). Static fallback `~/.binary-canticle/stations.toml` is a MUST (`:305-307`).
- **[SAYS]** Records (`:256-260`): `_canticle._udp.<zone>. SRV prio weight port <station-host>` and `_canticle-listen._udp.<zone>. SRV … <hearer-host>`. Zone default `thornfield.local.` (mDNS) (`:262-263`).
- **[SAYS]** Example (`:272-279`): SRV `10 100 9999 silas.thornfield.local.` announces "its listening port for *out-of-band station-metadata queries*". TXT at `silas-stations.thornfield.local.` carries `v=1`, `stations=silas_heresy,…`, `lens-hints=…`, `schema=urn:…`.
- **[SAYS]** Refresh on SRV TTL expiry, config reload or network move. An unknown station-id in a beacon SHOULD NOT force an SRV refresh (`:291-301`).
- **[SAYS]** Bootstrap discovery is OPTIONAL for receiving (`:294-297`).
- **[ASSESS] defects**
  1. `_canticle-listen` is defined and never explained. Why would hearers publish SRV? It contradicts "no subscriber tracking".
  2. The metadata-query port (9999) is the same as the broadcast data port (`:112`), and the "metadata query surface" protocol is never defined.
  3. The TXT record sits at an ad-hoc name, not at the service instance name (DNS-SD, RFC 6763, puts TXT at the instance name). It does not use RFC 6763 instance-enumeration (PTR).
  4. SRV cannot express a multicast group; there is no TXT key for `group=239.x`.
  5. `.local` is mDNS-only, and the owner wants internet listeners. Scope-3 only says "SRV records can span DNS zones; relay registers as a proxy-station" (`scope-framing-and-noosphere-mapping.md:91-93`).
  6. There is no key fingerprint in TXT, so SRV is not a trust anchor. DNSSEC is not mentioned.

  Net: SRV here is a bootstrap *pointer*, which is good. The owner's "DNS-SRV-registered station:stream" needs a real record layout: `_canticle._udp.<zone>` → relay/transmitter endpoints, plus DNS-SD-style TXT with `id=<ULID>`, `key=<ed25519 fp>`, `group=`, `streams=` hints.

### 1.8 Signing and trust

- **[SAYS] v0.1 §9.4**
  - "Frond-membership signal (provisional v0.2)": HMAC-SHA256 over `(v, station, stream, seq, ts, kind, payload-canonical-bytes)` with a pre-shared frond key (`:493-496`);
  - v0.1 default: SHOULD log unsigned frames but accept them (`:497-499`);
  - when the human station broadcasts `posture: defense`, hearers SHOULD restrict surfacing to signed frames (`:500-502`);
  - open question: PSK vs per-station Ed25519 with a frond CA (`:587-589`).
- **[SAYS] v0.2** "base-layer canticle assumes trust-of-LAN". Per-frame Ed25519 is a **v0.3 overlay**: "append a tagged-signature CBOR map … sigs become an opt-in tag" (`stations-and-streams-v0.2.md:122-126`).
- **[SAYS] scope ladder** Scope-2 trust = "pre-shared frond-key (HMAC, per §9.4)" (`scope-framing-and-noosphere-mapping.md:75-76, :263`). Scope-3: per-frond keys with relay re-sign. Scope-4: dual signing (`:109-112`).
- **[SAYS] receptor** Only an abstract `signature` object and `sigState valid|invalid|absent` (`:133, :236`). Transitions 1 and 2 *require* "valid signed" frames (`:331-335, :350-354`). Example 2 requires unsigned/foreign frames to contribute zero accord (`:489-491`).
- **[DECIDED/implemented]** The prototype makes Ed25519 mandatory over the canonical unsigned envelope, with issuer/key allow policy and no fallback (`prototype/ringserver-udp-cue/README.md:54-58`).
- **[SAYS]** #48 (open, owner `karmafeast`, 2026-07-24) asks exactly the undecided questions: identity binding, HMAC vs per-station keys, admission result, key lifecycle, replay binding, provenance. It also sets a guardrail: "No unauthenticated compatibility fallback that silently upgrades an arriving frame to trusted", and "Verification authorizes interpretation eligibility, never task execution, automatic agent turns…".

### 1.9 Receptor pipeline stages

- **[SAYS]** There are three layers: interface ↔ receptor+ringbuffer ↔ wire (`receptor-contract-v0.2.md:28`).
- **[SAYS]** Hard boundaries:
  - wire stays stupid (`:57-60`);
  - receptor deterministic: the same `(frame, receptor_state, memory_flags)` gives the same `(disposition, state_delta, receipt_plan, evidence)` (`:62-65`);
  - interface derived (`:67-70`);
  - raw and interpreted MUST NOT collapse (`:72-79`);
  - event log vs modulation state MUST be separate (`:81-92`).
- **[SAYS]** Pipeline (`:96-102`):
  1. **verify** (signature/provenance/schema/freshness/rate);
  2. **classify** (payload kind plus chemokine/posture semantics);
  3. **threshold** (salience/disposition under current state);
  4. **place** (write raw receipt and/or derived event to ring/store);
  5. **expose** (raw and interpreted outputs queryable).

  Non-surfacing effects include raising/lowering thresholds, widening/narrowing listen bands, setting/clearing quarantine, decaying pressure, and ignored-but-accounted (`:104-110`).
- **[SAYS]** Table B local state (`:157-171`): `activeThresholds`, `modulationState`, `stationTrust`, `stationQuarantine`, `persistentFlags`, `listenBands`, `pressureScores`, `accordState`, `recentRates`, `schemaCompat`, `replayDedup`, `lastConfirmedAt`, `decaySchedule`. Plus the questions this state must answer (`:175-187`): "If the hearer cannot answer these, the immune model has become mysticism" (`:189`).
- **[SAYS]** Five deterministic transitions (`:329-418`):
  - T1: valid chemokine `tighten-frond-discriminator` raises the threshold;
  - T2: `all-clear` lowers it after a decay window;
  - T3: stale/invalid → ignored-but-accounted;
  - T4: repeated hostile signal plus accord → `quarantine_action`;
  - T5: an ordinary frame is reclassified under the shifted threshold ("proof that chemokine is a field change").
- **[SAYS]** Eight executable examples are required "before transport selection" (`:475-511`), including "bridge-forward is not hear-and-sing" (`:501-503`) and "clarion widens propagation without becoming command" (`:504-506`).
- **[SAYS]** Session API (`:447-457`): `listen`, `atmosphere`, `ringbuffer`, `receipts`, `receptorState`, `quarantineView`, `sing`, `posture`. Invariant: "No adapter or session surface may bypass the receptor core to write directly into atmosphere" (`:461-462`).
- **[SAYS]** Conformance has six points (`:466-473`).
- **[ASSESS]** The determinism tuple omits **evaluation time (`now`)**, yet freshness, decay and rate all depend on it. Add `now` (and the adapter's clock-offset estimate) to the tuple, or determinism is unfalsifiable.
- **[ASSESS]** No thresholds, decay windows or accord counts are numeric. The text says "~60s" in example 1 (`:485-488`); the immune addendum leaves the accord threshold open (`immune-model-addendum.md:159`).

### 1.10 Judgment objects

- **[SAYS]** Table C (`receptor-contract-v0.2.md:200-209`):
  - `disposition` ∈ {`surface`, `ringbuffer_only`, `drop`, `quarantine_action`};
  - `rawReceipt`, `stateDelta[]`, `receiptPlan` (`none|ack|notice|quarantine_notice`…), `presentToInference: bool`, `ringbufferWrite`, `evidence[]`, `expiry?`.
- **[SAYS]** Invariant: "a judgment object MUST NEVER float free of a source frame" (`:195-198`).
- **[SAYS]** Minimal receptor record (`:224-246`): one row per evaluated frame, including `sigState`, `dispositionReason[]`, `accordWeight`, `memoryEffect none|threshold_delta|antibody_flag`, and `stateVersion/ruleVersion` as "judgment lineage, not frame lineage" (`:246, :251-254`).
- **[SAYS]** Evidence entry `{rule, inputs, decision}` is mandatory for every non-trivial disposition (`:265-277`). "The receptor is allowed to be strict, not allowed to be mysterious."
- **[ASSESS]** The enum is inconsistent within the doc: Table C says `quarantine_action` (`:202, :217`), §7.2 says `quarantine_flag` (`:242`). Open Q4 (`:520-521`) already proposes splitting into set/strengthen/rescind.

### 1.11 Ledger

- **[SAYS] receptor §10 storage** (`:422-429`):
  - append-only segment files as the canonical raw frame ledger / event log;
  - a tiny SQLite index;
  - a separate modulation-state store with expiry;
  - a separate persistent store for antibody memory and quarantine flags "that outlives frame TTL".
- **[SAYS]** Receipts, quarantine notices and all-clears "stay in the same canonical frame family … not … a second canonical truth-source". `receptor_events` / `station_state_snapshots` are projections (`:431-435`).
- **[SAYS]** "Raw receipt is truth. Atmosphere is use" (`:319-320`). The §7.2 record is "the judgment ledger connecting one to the other" (`:322-323`).
- **[SAYS]** Ringbuffer: `append` is idempotent on `digest` (min) or `(station, stream, seq)` (stronger). Duplicates are explicit no-ops (`ringbuffer-contract.md:118-130`). `receipt_of` and `parent_digest` give lineage (`:45-46`).
- **[ASSESS]** "Ledger" is used for two things:
  - an audit event log that outlives TTL (receptor);
  - a TTL-bounded ring that MUST evict (v0.1 §6.1, ringbuffer §3.1).

  RFC-0001 needs two names: **ring** (live, TTL/depth-bounded, loop source or cache) and **ledger** (audit, retention policy, never queryable as current state; see #51 invariant 2).

### 1.12 Interface layer, roles, posture/lens, and conflict

- **[SAYS]** Roles (`protocol-spec-v0.1.md:358-371`): chanter (broadcast), hearer (receive), nexus (tunes chanters/hearers, "stays out of the wire-substrate").
- **[SAYS]** API (illustrative, `:377-384`): `canticle.tune`, `atmosphere`, `sing`, `posture`, `nexus.digest`, `lookup`.
  - `tune()` is a receiver-side filter, not a wire subscription (`:386-391`).
  - `atmosphere()` is **not auto-injected**; the session reads and decides (`:393-398`).
  - Self-broadcast is filtered by default, with an `include_self` override (`:408-412`).
- **[SAYS]** Posture: slow, broadcast on the `posture` stream (`:416-422`). Lens: a frame-level filter hint (`:424-429`). figs's "adopt posture of defense" is atmospheric, and per-prince response is volitional (`:431-441`).
- **[SAYS]** §9 "Frond-shape constraints" (MUST-level):
  - 9.1: no inner-model-of-human content on the wire. The chanter SHOULD self-audit; the hearer SHOULD reject; the mechanism is open (`:448-462`).
  - 9.2: no auto-actuation. Receiving MUST NOT trigger a turn (`:469`), MUST NOT auto-broadcast (`:470`), MAY enrich the *next* turn if the session is already running and tuned (`:471-472`); `subscribe()` MUST NOT wake a session (`:473-474`).
  - 9.3: posture is a hint; no forced self-posture without opt-in (`:479-484`).
  - 9.4: discrimination, as above.
  - 9.5: no role taxonomy (`:507-513`).
- **[SAYS]** §10 conflict: contradictory mutations coexist as provenance-tagged edges. There is no protocol winner. Same-station newer wins without retracting the older (`:515-536`).

---

## 2. DECISIONS table (with status)

"Accepted" means the text says resolved/decided and no later document reverses it. "Contested" means another core doc or code says otherwise.

| # | Decision | Where | Status |
|---|---|---|---|
| D1 | Transport MUST be UDP; no TCP variant | `protocol-spec-v0.1.md:111`; bytewalk inherits `:7` | Accepted (but see §5: SeedLink/ringserver are TCP; prototype hands off to TCP DataLink) |
| D2 | Single well-known port, provisional `9999` | `protocol-spec-v0.1.md:112`; SRV example `:272` | Provisional |
| D3 | IPv4 broadcast or multicast; prefer multicast, provisional `239.13.13.13` | `:113-115` | Provisional |
| D4 | No reliability; tolerate loss/reorder/duplication | `:59-60, :116-117`; bytewalk `:10` | Accepted everywhere |
| D5 | One frame per datagram, ≤1472 B, no app-layer fragmentation (split into independent frames) | `:118-121`; bytewalk `:7` | Accepted (numerically mis-stated; prototype uses 1200 `codec.py:14`) |
| D6 | CBOR RECOMMENDED, JSON OPTIONAL, both MUST be accepted, `0x7B` sniff | `protocol-spec-v0.1.md:127-135` | **Contested**: v0.2 says CBOR for both frame types and argues against JSON (`stations-and-streams-v0.2.md:107-112`); prototype is JSON-only (`README.md:41`) |
| D7 | Unknown fields MUST be accepted; missing required → silent drop | `protocol-spec-v0.1.md:157-158`; bytewalk `:8` | **Contested** by prototype ("Unknown or extra fields are rejected", `README.md:51-52`) |
| D8 | Unknown `kind` / unknown stream → log-and-skip / tolerate | `:184-185, :227-228` | Accepted (v0.1 only) |
| D9 | `station:stream` is the primitive addressing tuple | `stations-and-streams-v0.2.md:73`; `ringbuffer-contract.md:23-27` | Accepted |
| D10 | `station_id` = 16-byte ULID native bytes on wire | `stations-and-streams-v0.2.md:77` | Accepted in v0.2; **contested** by v0.1 string grammar `:193-196` and receptor strings |
| D11 | `stream_id` = u32, station-local, derived `truncate32(hash(name))` | `bytewalk:18-22`; `stations-and-streams-v0.2.md:132` | Accepted (hash and collision policy open, #38) |
| D12 | `content_type` = string; optional `u16` id later, profile-gated | `bytewalk:28-32`; `:133` | Accepted |
| D13 | TTL = stream default + per-frame override **down only** (station clamps) | `bytewalk:38-44`; `:134` | Accepted |
| D14 | Retention = `min(depth, TTL)`; depth is station-private | `bytewalk:52-61`; `:90, :135` | Accepted (#37 closed; contract-doc propagation not done) |
| D15 | Pluck = header bit on a normal payload frame; in-place ring mark (authoritative for replay) + best-effort pluck-frame (live) | `stations-and-streams-v0.2.md:58, :67, :136`; `bytewalk:65-79` | Accepted (#39 closed; fixtures not done) |
| D16 | Beacon 1 Hz = `{station_id, head_seq, wallclock_ns, schema_version, streams[{stream_id, default_ttl}]}`; no content-type set | `:22-26, :137-139`; `bytewalk:85-92` | Accepted (#40 closed) |
| D17 | Beacon is not bootstrap; SRV/mDNS/static = bootstrap only; unknown station in beacon does not force SRV refresh | `protocol-spec-v0.1.md:240-247, :298-301`; `stations-and-streams-v0.2.md:34-40, :155` | Accepted (#36 closed via PR #41 `5a3c0e8`) |
| D18 | SRV bootstrap MUST be supported; static-config fallback MUST be supported | `protocol-spec-v0.1.md:249-250, :305-307` | Accepted (naming "illustrative", `:20`) |
| D19 | Sender does not track hearers; no acks; no retransmit | `stations-and-streams-v0.2.md:13, :79`; `bytewalk:12`; `explicit-non-goals.md:31-32, :86, :108` | Accepted everywhere (load-bearing) |
| D20 | Content opaque to substrate | `stations-and-streams-v0.2.md:58`; `ringbuffer-contract.md:49-50` | Accepted (v0.1's typed `payload` kinds are the older model) |
| D21 | Auth: v0.2 base = trust-of-LAN; Ed25519 = v0.3 opt-in overlay tag | `stations-and-streams-v0.2.md:122-126` | **Contested**: v0.1 HMAC provisional (`:493-499`); scope-2 = PSK HMAC (`scope-framing…:75-76`); prototype Ed25519 mandatory; #48 open |
| D22 | Receiving MUST NOT trigger a turn, auto-broadcast, or wake via `subscribe()` | `protocol-spec-v0.1.md:464-477` | Accepted in docs; **conflicts with owner intent** (see §3, C16) |
| D23 | Atmosphere not auto-injected; session reads-and-decides | `:393-398` | Accepted in docs; conflicts with spike (`silas-seedlink-mapping.md:58`) and owner intent |
| D24 | Posture is hint, never forced | `:479-484` | Accepted |
| D25 | No protocol-level conflict winner | `:515-536` | Accepted |
| D26 | Receptor pipeline verify→classify→threshold→place→expose; deterministic; raw ≠ interpreted; event log ≠ modulation | `receptor-contract-v0.2.md:57-102` | Draft-accepted (INDEX `active`) |
| D27 | Judgment objects MUST carry source pointer + evidence | `:195-198, :265-277` | Draft-accepted |
| D28 | Regulation signals stay in the same canonical frame family (no second truth source) | `:431-435` | Draft-accepted |
| D29 | Executable receptor examples required **before** transport selection | `:475-511` | Draft-accepted; **not honored**: prototype chose transport (loopback UDP → DataLink) without the 8 example fixtures (#27 open) |
| D30 | Ringbuffer non-interpreting; append/replay/tail; explicit truncation; idempotent append | `ringbuffer-contract.md:53-162` | Draft-accepted |
| D31 | No membership plane inside receptor/ringbuffer | `receptor-contract-v0.2.md:547-551`; `ringbuffer-contract.md:182-185` | Draft-accepted |
| D32 | Promotion path seed → pressure-test (≥4/6 answered) → stable (after first implementation exercises the wire) | `stations-and-streams-v0.2.md:164` | v0.2 at pressure-test (`6fc78f5`); **the promotion dropped the original "figs cosign" gate** (seed text in `6fc78f5` diff: "figs cosign on substrate framework") and relied on Cael's self-labelled "proposals" (`bytewalk:3`) |

---

## 3. CONTRADICTIONS between docs (and with code / owner intent)

| # | Contradiction | Evidence | Suggested resolution for RFC |
|---|---|---|---|
| C1 | **Replay exists vs replay forbidden.** v0.1 "no replay" (`:29-30`); non-goals "No catch-up … No 'since-token'" and "No tuner-to-station messages … 'please retransmit seq N'" (`explicit-non-goals.md:75, :108`) vs v0.2 "late-joining tuner … can replay-from-ring" (`stations-and-streams-v0.2.md:87`) and ringbuffer `replay(station:stream, since_seq\|since_ts, limit)` (`ringbuffer-contract.md:67`) | — | Replay on the broadcast plane = **station carousel** (passive). `replay()` in the ringbuffer contract is a **local hearer API** over the hearer's own ring, not a wire request. Any pull-replay (SeedLink-style) is a separate, explicit relay surface. |
| C2 | **Where the ring lives.** v0.1: per hearer (`:311-314`, one per host, diagram `:92-94`). v0.2: "finite circular buffer at the station" (`:85`); pluck mutates the station ring (`:67`). Ringbuffer contract: unstated (append on receipt implies hearer side, `observed_at` `:39`) | — | Both exist. **Station ring = loop source.** **Hearer ring = local cache of what's heard.** Name them separately. |
| C3 | **v0.2 "extends" v0.1, but the wire is incompatible.** v0.1 required `v, station(str), stream(str), seq, ts, ttl_ms, kind, payload` (`:143-150`) and MUST drop frames missing them (`:158`); v0.2 payload frame has none of `v/ts/kind/payload` and uses binary ids (`stations-and-streams-v0.2.md:49-55`) | `:145` claims extension | Declare v0.2 wire a breaking successor (`v`=2 / magic+version). Keep v0.1's semantics (roles, §9) but retire its frame table. |
| C4 | **Station identity**: v0.1 human string `member_aspect` (`:193-196`); v0.2 ULID, process-scoped, ULID timestamp signals restart (`:75, :77`; `bytewalk:22`); receptor `stationId`+`memberId` strings (`:120-121`); SRV/TXT lists string names (`:276`); prototype `issuer` string + `key_id` (`codec.py:18,21`) | — | Stable station identity = **public key** (or ULID bound to key), human name via SRV/TXT/beacon; add a per-process `epoch`/boot id for restart instead of rotating `station_id`. |
| C5 | **Aspect placement**: v0.1 aspect ⊂ station id (`silas_heresy`, `:199-206`); SeedLink spike: "Stream = Aspected lens" (`silas-seedlink-mapping.md:22`); v0.2: station = process, stream = topic, `lens` gone | — | Aspect = stream (matches owner's MAGI-1 "each aspect maintained by a subagent" if subagent = station and aspect = stream, or subagent = station per aspect; RFC must pick one — recommend aspect → stream name, lens → optional header tag). |
| C6 | **Time fields/units**: v0.1 `ts` µs + `ttl_ms` (`:147-148`); v0.2 beacon `wallclock_ns` (`:24`), payload `ttl_seconds` with **no timestamp** (`:52`), `default_ttl` unitless (`:26`); receptor `emittedAt`/`observedAt` "timestamp" + `ttlMs` (`:127-129`); ringbuffer `ts`, `observed_at`, `ttl_ms`, `expires_at` (`:38-41`); prototype `issued_at`/`expires_at` absolute seconds (`model.py:17-20`) | — | Wire carries absolute `issued_at` + `expires_at` (or `issued_at`+`ttl_ms`), immutable across loops; receivers clamp with local clock (#51 invariant 8). |
| C7 | **TTL ceiling**: v0.1 SHOULD ≤60 s (`:148`); v0.2 example 5 min (`:86`); prototype MAX 60 s (`receptor.py:23`); owner wants loop-until-TTL (implies minutes–hours) | — | Per-stream max TTL advertised in beacon; profile defaults (e.g., chatter 60 s, status 5 min, standing/"root" long with loop) — no global 60 s cap. |
| C8 | **Encoding/forward-compat**: v0.1 CBOR+JSON both MUST be accepted (`:132-135`); v0.2 CBOR only, JSON rejected as verbose (`:107-110`); prototype JSON only, closed schema (`README.md:41-52`) | — | One binary encoding (deterministic CBOR, RFC 8949 §4.2, integer keys) + JSON as a debug *projection*, not an on-wire alternative. Forward-compat via unknown **integer keys** ignored, but signature covers them. |
| C9 | **Signing**: v0.1 HMAC provisional, unsigned accepted (`:493-499`); scope-2 = HMAC PSK (`scope-framing…:75-76`); v0.2 no signing, Ed25519 v0.3 overlay (`:122-126`); receptor T1/T2 require valid signatures (`:331-335`); prototype Ed25519 mandatory (`README.md:54-58`); #48 open | — | Per-station Ed25519 (identity = key), signature over byte-identical loop frames; unsigned frames allowed only at scope ≤2 and classified `sigState=absent` (never trusted). Drop HMAC-PSK (non-attributable; any member can forge any station). |
| C10 | **Correlation/receipts vs no-RPC**: v0.1 "No correlation IDs across frames" (`:57-58`), non-goals "There is no `correlation_id` field" (`explicit-non-goals.md:109`), "MUST NOT auto-broadcast a response" (`:470`) vs receptor Table A `correlationId`, `inReplyTo`, `receiptRequested` (`:134-136`) and `receiptPlan: ack/notice/quarantine_notice` (`:205`) | — | Keep `in_reply_to`/lineage as *references* (useful for bridge/rebroadcast lineage, `:501-503`), drop `ack`, make any receipt a new volitional utterance (Emeric #51 invariant 6). |
| C11 | **Frame identity**: non-goals "No identity-of-frame. A frame is not a record" (`explicit-non-goals.md:77`) vs receptor `frameId` required "Stable unique frame identifier" (`:119`) vs ringbuffer `digest` required (`:44`) vs v0.1 optional `nonce` (`:155`) | — | Frame identity = `(station_id, stream_id, epoch, seq)`; digest = integrity. Non-goals text should be narrowed to "no global/durable identity". |
| C12 | **Where judgment sits relative to storage**: ringbuffer "MUST NOT classify … Those belong above the ringbuffer" (`ringbuffer-contract.md:105-116`) and v0.2 "receptor lives at the application boundary above this substrate" (`stations-and-streams-v0.2.md:146`) vs receptor pipeline where **place** (write to ring) happens *after* threshold, and `drop` = "do not store payload in normal surfaced path" (`receptor-contract-v0.2.md:100, :215-216`) — i.e., judgment gates storage | — | Order: wire → verify(syntax/sig/freshness) → **append raw to hearer ring (always, bounded)** → classify/threshold → judgment record → expose. Raw receipt must not depend on judgment (receptor's own `:319-320` "Raw receipt is truth"). |
| C13 | **Eviction vs forensic evidence**: v0.1 live ring MUST evict at `ts+ttl_ms` (`:319, :347-349`); ringbuffer MUST drop on bounds (`:88`); receptor example 3 "expired frame in ringbuffer → evidence yes" (`:492-494`) and persistent stores outliving TTL (`:428-429`); open Q6 (`:523`) | — | Separate **ledger** (audit) from **ring** (live); expired items queryable only as history, never as current state. |
| C14 | **Disposition enum** `quarantine_action` (`:202, :217`) vs `quarantine_flag` (`:242`) | internal | Pick one; adopt open-Q4 split. |
| C15 | **Posture-driven auto-behavior**: §9.3 "MUST NOT translate received-posture into forced-self-posture" (`:482-484`) vs §9.4 "when human-station broadcasts `posture: defense`, hearers SHOULD restrict surfacing to signed frames" (`:500-502`) and receptor T1/T5 automatic threshold shifts | — | Distinguish **receptor modulation** (filter thresholds; allowed, local, evidence-logged) from **session actuation** (turns, broadcasts, self-posture; opt-in only). |
| C16 | **Owner intent vs §9.2**: owner wants listeners that notify other sessions and trusted clients that directly enrich remote context (incl. OpenClaw silent/silent-wake continuation); v0.1 "Receiving a frame MUST NOT trigger a Claude turn … MUST NOT be used to wake a Claude session" (`:469, :473-474`); spike's receiver literally "inject as [system:broadcast-enrichment] event" (`silas-seedlink-mapping.md:58`) and `| silent` pickup (`:89-92`) | — | Default no-wake; allow **receiver-local, opt-in wake policy** gated on verified signature + allowlisted issuer + class (e.g., clarion), rate-limited; wake is the receiver's act, never the sender's right. #48 guardrail already frames verification as "interpretation eligibility, never … automatic agent turns" — owner must decide. |
| C17 | **LAN-only vs internet**: v0.1 LAN `10.0.0.0/24` (`:84-86`); v0.2 NAT/cross-subnet out of scope (`:156`); scope-3 relay sketched (`scope-framing…:81-101`); owner requires internet UDP listeners | — | RFC-0001 must define a **relay/transmitter** role (unicast fan-out with soft-state listener leases) — the relay tracks listeners, the station still doesn't. Restate D19 as a *station* invariant, not a network invariant. |
| C18 | **Head-sync granularity**: single `head_seq` per station (`:23`) vs per-(station,stream) `seq` (`protocol-spec-v0.1.md:146`; `ringbuffer-contract.md:37`) and per-stream rings (`stations-and-streams-v0.2.md:76`) | — | Move `head_seq` into `streams[]`. |
| C19 | **Station granularity**: v0.1 "multi-host orchestration daemons are stations", a member runs many stations (`:188-199`); v0.2 stations "1:1 with running processes" (`:75`) | — | Station = signing identity; process = epoch. |
| C20 | **Fragmentation**: v0.1 "MUST NOT fragment at the application layer" then defines `frag {id,i,n}` reassembly (`:119-121` vs `:160-171`); v0.2/ringbuffer have no frag | — | Drop fragmentation; >1200 B content goes by reference (`bodyRef`/`bodyHash`, receptor `:131-132`; prototype `subject: sha256:` pointer). |
| C21 | **SeedLink lineage**: spike says SeedLink is TCP (`silas-seedlink-mapping.md:32`) but `spike/silas-teams-context.md:37` says "SeedLink … UDP connectionless"; prototype confirms TCP-only ringserver (`README.md:11-33`) | — | RFC cites SeedLink as *conceptual* model only. |
| C22 | **Gate discipline**: receptor says examples before transport (`:475-481`); prototype picked transport first (`65e6705`), #27 open. Bytewalk "proposals … not unilateral" (`:3`) vs v0.2 "Resolved" (`:130`) + #37/#39/#40 closed citing PR #42 with acceptance criteria (contract text + fixtures) unmet | — | RFC process: decisions recorded with explicit acceptance + fixtures. |
| C23 | **Terminology**: non-goals "Frames are not events in the event-bus sense" (`explicit-non-goals.md:95`) vs receptor "event log — the chemokine frame as received fact" (`:86`) | minor | Use "receipt log". |
| C24 | Scope-5 file-replay "TTL is air-gap-protective" (`scope-framing…:266`) — replayed bundles arrive long after `expires_at` and would all be dropped by §6.1 | minor | Scope-5 is out of RFC-0001. |

---

## 4. Open questions still genuinely open

Listed by owner doc, filtered to those not actually answered elsewhere.

**Wire and addressing**
1. Hash function and collision policy for `stream_id` (#38 open; `bytewalk:111`).
2. The CBOR key encoding (int keys, string keys, or array); a canonical/deterministic encoding for signing.
3. Whether `seq` is per-stream or per-station, and `head_seq` placement (C18).
4. Restart semantics: `seq` reset, and epoch/boot id vs ULID rotation.
5. Clock basis for expiry under skew (Emeric #51 inv. 8). v0.2 lacks a payload timestamp.
6. Registry for `content_type` u16 ids ("who allocates", `bytewalk:112`).
7. v0.3 hard-break vs graceful-degrade rule for `schema_version` (`stations-and-streams-v0.2.md:120`).
8. Liveness "N seconds" (`:32`).
9. A stable-name ↔ ULID ↔ key binding (#48 Q1).
10. Multicast vs broadcast, and whether LAN multicast is practical (#2 open, 2026-03-14). The core docs never test IGMP snooping or Wi-Fi multicast behaviour.

**Loop and TTL (not even asked in the docs; the owner's core ask)**
11. Repeat interval: per-stream default vs per-item, min/max, jitter, rate budget; who controls it (singer, station clamp, membrane attenuation).
12. Whether looped copies are byte-identical (sign once) or re-stamped.
13. How pluck stops a loop and whether pluck frames themselves loop until the original's expiry. **[ASSESS]** They should, or late joiners miss the pluck. The station ring mark covers this in the carousel model.
14. Priority and fairness of the carousel under a depth or bandwidth budget.

**Trust (#48 open in full)**
15. PSK-HMAC vs per-station Ed25519 vs CA (`protocol-spec-v0.1.md:587-589`).
16. Key bootstrap, rotation and revocation; unknown-key behaviour.
17. Whether pluck frames and beacons must be signed. Unsigned beacons allow presence spoofing; unsigned pluck allows censorship.
18. How `posture: defense` and signing interact (`:600-601`).

**Receptor** (`receptor-contract-v0.2.md:515-539`, all open)
19. Explicit vs recomputed `accordWeight`.
20. Whether `all-clear` is a kind or a class.
21. Default receipts.
22. Splitting `quarantine_action`.
23. Per-station caps in core vs recommended.
24. Evidence retention after TTL.
25. Half-open posture.
26. Per-stream refractory window.
27. Hash-referenced constitution guidance.

Plus: numeric accord threshold (`immune-model-addendum.md:159`) and chemokine TTL vs antibody TTL (`:162`).

**Interface and policy**
28. Frond-rule enforcement: how to detect inner-model-of-human leakage (`protocol-spec-v0.1.md:461-462, :590-592`). **[ASSESS]** Unimplementable as a MUST at the hearer. Restate it as a sender-side content policy plus a privacy class.
29. Schema evolution for graph mutations (`:596-597`).
30. MCP vs shell surface (`:602-603`).
31. Wake/notify policy (C16).
32. Disposition-frame envelope and vocabulary (#51 Q1-5).
33. station:root / UNEQUIP state machine (scratch notes; not in any issue I read).

**Scale and topology**
34. Internet relay design (scope-3) and the listener-lease model.
35. Beacon aggregation. At the owner's "thousands of agents", N stations × M listeners × 1 Hz unicast fan-out is O(N·M) pps (1000×1000 ≈ 1 M pps). Elliott's scaling claim ("100+ stations on same LAN", `stations-and-streams-v0.2.md:103`) is LAN-broadcast-only.
36. HAProxy-as-membrane (#30) is conjecture. Nothing in the core docs defines the membrane's inputs or outputs.

---

## 5. SeedLink / miniSEED / DataLink — how concepts are mapped (or mis-mapped)

External facts I relied on are general protocol knowledge, cross-checked where the repo cites them:
- SeedLink v4 spec: https://docs.fdsn.org/projects/seedlink/en/latest/protocol.html (cited `spike/silas-seedlink-mapping.md:4`, `README.md:56`).
- EarthScope ringserver v4.5.4, commit `2df558c`, cited in `prototype/ringserver-udp-cue/README.md:5-33`.

Background:
- **SeedLink**: TCP (default port 18000), client-driven. Handshake commands (HELLO, STATION/SELECT, DATA [seq] / FETCH / TIME, END), then server-pushed packets.
  - v3 packet = 8-byte header "SL" + 6-hex-digit seq, then a 512-byte miniSEED record.
  - v4 adds a "SE" signature header with format/subformat, payload length, 64-bit sequence and station id, and uses FDSN Source Identifiers (`FDSN:NET_STA_LOC_B_S_SS`).
  - INFO requests list stations/streams/capabilities.
  - Resume works because the **server keeps a ring** and the **client asks** for data from a sequence number.
- **DataLink**: ringserver's TCP ingest/read protocol (ID, WRITE, READ, POSITION, MATCH, STREAM…). Stream IDs like `NET_STA_LOC_CHA/MSEED`, and ringserver 4 accepts JSON packets (the prototype uses `BC_CUE/JSON`, `README.md:111,129`).
- **miniSEED**: a fixed-header time-series record format (v2: 48-byte fixed header, usually 512-byte records; v3: "MS3" header with FDSN source id, extra headers in JSON, text encoding allowed).

| SeedLink / DataLink / miniSEED concept | Canticle mapping as written | Verdict [ASSESS] |
|---|---|---|
| Network+Station code (NET_STA), durable site id | "Station = Broadcasting prince"; `prince_aspect` (`silas-seedlink-mapping.md:21,28`); v0.1 `member_aspect`; v0.2 ULID per process | **Partial mis-map.** SeedLink stations are durable and name-addressed; v0.2 makes station ids ephemeral per process. Adopt durable station identity (key-bound) + epoch. |
| Stream / channel (LOC.CHA, e.g. `BHZ`; FDSN `B_S_SS`) | spike: "Stream = Aspected lens" (`:22`); v0.2 stream = topic, u32 hash | OK in shape (station:stream ≈ NET_STA:LOC_CHA). The spike and v0.2 disagree on what a stream *is* (C5). Canticle loses SeedLink's human-readable channel codes on the wire (u32 hash). |
| Sequence number + resume (`DATA <seq>`) | "Generation guard … for resumption after compaction" (`:24`); v0.2 `head_seq` + replay-from-ring | **Mis-map.** SeedLink resume needs a server ring + TCP request. Canticle keeps the ring but forbids the request (C1). Resolve via carousel (broadcast analogue) and/or an explicit relay pull surface (true SeedLink analogue). |
| Handshake phase (HELLO/STATION/SELECT) | "Exercise setup (shared schema establishment)" (`:25`) | **Mis-map.** SeedLink handshake = client *selection* of station/stream; canticle analogue is `tune()` (receiver-side filter, `protocol-spec-v0.1.md:386-391`) or a relay lease. |
| INFO STATIONS/STREAMS/CAPABILITIES | not mapped; closest = carrier-beacon + SRV/TXT (`protocol-spec-v0.1.md:282-287`; #40) | Good opportunity: define a relay INFO endpoint (out of band) instead of bloating the beacon. |
| Data transfer phase | "Continuous broadcast (the singing)" (`:26`) | OK. |
| miniSEED payload | "Graph mutation JSON / compressed exercise output" (`:27`); v0.2 opaque `content_bytes` + `content_type` | OK as "format-agnostic payload" (`:15`). **But** miniSEED is sample time series with no TTL; canticle items are discrete TTL utterances. A canticle→dashboard gateway must either (a) emit numeric channels as real miniSEED3 sample series (v0.1 `weather.tensions` floats, beacon rate, per-stream frame rate are natural candidates for ews/nerv-ui waveforms), or (b) emit text/JSON records and not feed them to a waveform parser. The ews log "Not enought bytes for header, need 47, found 6" is consistent with a non-miniSEED packet hitting a miniSEED header parser (not verified by me; other readers own ews). |
| Transport TCP, reliable, connection-oriented | "We want UDP broadcast with SeedLink's addressing … without TCP's reliability" (`:32-38`); teams-context wrongly says SeedLink is UDP (`silas-teams-context.md:37`) | Correct in the spike, wrong in the lineage note. Prototype confirms ringserver cannot ingest UDP (`README.md:13-33`). |
| DataLink WRITE (ingest) | not mapped in docs; prototype has a private `DataLinkPublisher.publish(VerifiedNotice)` seam to ringserver (`README.md:35-37, :85-87`) | **[ASSESS]** Natural mapping: `sing` → station/relay ring (DataLink-WRITE-like); `tune`/relay pull → SeedLink/DataLink READ-like; UDP carousel for broadcast. Ringserver can be the *relay's* ring (TCP side) for internet/dashboard consumers; it cannot be the UDP carrier. |
| Ringserver ring + packet IDs | prototype: "ring packet ID is treated solely as a local cursor" (`README.md:139`) | Consistent with ringbuffer-contract cursors (`:153-154`). |
| SeedLink "time window" (TIME) | none | Maps to hearer `replay(since_ts)` local API only. |

Summary: canticle borrowed SeedLink's **naming hierarchy, sequence numbers, ring and format-agnostic payload**, and threw away the **request channel that makes the ring useful**. Two coherent fixes, which can coexist:
- **UDP carousel** at the station (owner's loop), for broadcast/lossy listeners.
- A **SeedLink-like relay** (TCP/QUIC/WebSocket, ringserver-backed or native) for internet and dashboard consumers who want catch-up. This is a separate surface that tracks its clients, like SeedLink servers do.

---

## 6. Mythology / metaphor vs implementable spec

| Content | Classification | Notes |
|---|---|---|
| frond, princes, cohort, noosphere, "aspected weather", sins-lenses (heresy/greed/violence/luxuria), "chanter/hearer/nexus", "sing/pluck", "vinyl record", "RDS", "revolving record", "chemokine/antibody/T-cell/clarion/adrenaline", "good servant, bad metaphysics", "we don't do weapons" | **Metaphor/vocabulary** | Useful as names if each maps to a mechanism. Chanter = publisher/station; hearer = receiver; nexus = coordinator/aggregator (no wire role, `:365-366`); sing = publish; pluck = revoke. chemokine = regulation frame class; antibody = persistent receiver flag; clarion = high-priority/short-TTL class. "Revolving record" = carousel (currently unimplemented). |
| Cohort-canon pins `feedback_*`, `reference_*` (`protocol-spec-v0.1.md:358, :450-451, :466, :509-510, :618-621`) | **Unverifiable provenance** | Agent memory keys, not citable documents. |
| Discord message ids truncated (`1501798149...`, URLs with `.../`) (`stations-and-streams-v0.2.md:7-9`) | **Unverifiable provenance** | Should become commit/issue links. |
| §9.1 frond rule "identity-of-humans is sovereign-of-machine" (`:450-462`) | **Policy dressed as protocol** | Implementable only as a sender content policy + privacy class; the hearer-side "detect inner-model leakage" MUST is not testable. |
| §9.4 "defensible discrimination … inversion-resistance" (`:486-505`) | Half | Mechanism (signatures + posture-gated filtering) is implementable; framing is rhetoric. |
| §10 conflict = "weather over time not truth" | Implementable | "No winner; keep both with provenance" is testable. |
| Immune transitions T1-T5 (`receptor-contract-v0.2.md:329-418`) | **Implementable, missing numbers** | Needs concrete thresholds, decay windows, accord counts. |
| Receptor Tables A/B/C, evidence schema, examples bank | **Implementable spec** | The strongest part of the corpus. |
| Carrier-beacon fields, payload frame fields, TTL clamp, min(depth,TTL), pluck | **Implementable spec** | Needs byte-level encoding pinned. |
| SRV/TXT records, static config | **Implementable spec** | Needs a DNS-SD-conformant layout. |
| Bandwidth math (`stations-and-streams-v0.2.md:92-103`) | Implementable sanity check | LAN-only; not valid for internet fan-out. |
| Owner scratch "pulse / capsid / station:root / UNEQUIP" (`notes_on_carrier_wave.md`) | Mixed | Pulse, root register, UNEQUIP and the 4-state machine are implementable. "Capsid timbre", "votive", "mantra" and SAGE transpose are metaphor or research. |
| #30 HAProxy membrane / cell-membrane table | **Conjecture** | Self-labelled "conjecture-to-design, not canon". "HAProxy 3.2+ native UDP load balancing" is an unverified claim from Discord. |
| Scope ladder 0-5 (`scope-framing…:34-143`) | Implementable framing | Good for conformance declarations (`:41-44`). |

---

## 7. RFC-0001 — adopt verbatim / adopt with change / drop

### 7.1 Adopt verbatim (or near-verbatim)

- **A1** "Not a command channel / not consensus / not reliable": frames may be lost, reordered or duplicated, and receivers MUST tolerate all three (`protocol-spec-v0.1.md:53-60`).
- **A2** "The sender does not track who is tuned in … doesn't retransmit on miss" (`stations-and-streams-v0.2.md:79`; `bytewalk:12`), scoped explicitly to the **station**.
- **A3** The carrier-beacon's purpose split: presence / head-sync / liveness, and "the carrier-beacon is **not** bootstrap discovery …" paragraph (`stations-and-streams-v0.2.md:29-40`). Also v0.1 §5 intro (`:240-247`) and §5.3's "beacon from unknown station SHOULD NOT force SRV refresh" (`:298-301`).
- **A4** TTL override-down-only with the station clamp (`bytewalk:36-46`).
- **A5** Retention `min(depth, TTL)` and the honest contract sentence: "at most TTL seconds, and at most depth frames, whichever is less" (`bytewalk:52-61`).
- **A6** Pluck: in-place ring mark (authoritative) plus best-effort pluck frame; "revoke-able-while-fresh, never un-said-with-certainty" (`bytewalk:65-79`).
- **A7** `content_type` string, opaque content (`bytewalk:26-32`; `stations-and-streams-v0.2.md:58`).
- **A8** `tune()` is a receiver-side filter, not a wire subscription (`protocol-spec-v0.1.md:386-391`). Self-filter default with an `include_self` override (`:408-412`).
- **A9** Conflict resolution: no protocol winner (`:515-536`).
- **A10** Receptor: raw vs interpreted separation (`receptor-contract-v0.2.md:72-79, :279-323`), judgment-must-reference-source (`:195-198`), evidence `{rule, inputs, decision}` (`:265-277`), "No adapter or session surface may bypass the receptor core" (`:461-462`), and the executable examples list (`:483-511`) as conformance fixtures.
- **A11** Ringbuffer: non-interpreting invariants (`ringbuffer-contract.md:84-116`), explicit truncation signals (`:141-144`), idempotent append with explicit duplicate result (`:118-130`).
- **A12** The static-config fallback MUST (`protocol-spec-v0.1.md:303-307`).
- **A13** Scope declaration: "Implementations claiming conformance MUST declare their target scopes explicitly" (`scope-framing…:41-44`).

### 7.2 Adopt with change

- **W1 Frame envelope (breaking, v=2).**
  - A fixed preamble (2-byte magic + version byte) replaces the `0x7B` sniff.
  - Deterministic CBOR (RFC 8949 §4.2) with **integer keys**, pinned in a key table.
  - Fields:
    - `station_id` (16 B, key-bound);
    - `epoch` (u32 boot id);
    - `stream_id` (u32; the hash is specified, e.g. first 4 bytes of SHA-256(name));
    - `seq` (u64 per station/stream/epoch);
    - `issued_at` and `expires_at` (absolute, ms), or `issued_at` + `ttl_ms`; either way immutable across loops;
    - `repeat_ms` (optional, u32);
    - `flags` (bit0 = plucked, …);
    - `content_type` (string);
    - `body` (bytes), **or** `body_ref` + `body_hash`;
    - `sig` (Ed25519, 64 B, over all preceding bytes).
  - Max datagram payload **1200 B** (internet-safe; matches the prototype).
  - No fragmentation. Large content goes by reference (C20).
- **W2 Loop/carousel (new normative section).**
  - The station re-emits each live, un-plucked entry every `repeat_ms` (stream default, per-item override bounded by station min/max, randomized jitter) until `expires_at`.
  - Loops are byte-identical, so the signature is computed once.
  - Hearers dedup on `(station_id, stream_id, epoch, seq)`.
  - Pluck: set the flag in the ring, stop the loop, and loop the pluck notice until the original's `expires_at`.
  - Remaining life never resets (#51).
  - This replaces "replay-from-ring" wording and reconciles C1.
- **W3 Beacon.**
  - Shape: `{station_id, epoch, wallclock, schema_version, streams[{stream_id, head_seq, default_ttl, max_ttl?, repeat_ms?}]}`, signed.
  - Rate: 1 Hz on LAN; configurable/slower via relay; relays may aggregate beacons into digests.
  - `wallclock` doubles as a clock-offset estimator for expiry clamping.
- **W4 Identity.** Station identity = Ed25519 public key (or a ULID bound to it). Human names live in SRV/TXT, static config or an optional beacon display name. Drop "station 1:1 with process"; use `epoch`.
- **W5 Discovery.** Keep SRV bootstrap, but:
  - use DNS-SD (RFC 6763) layout: `_canticle._udp.<zone>` PTR/SRV/TXT at the instance name;
  - TXT keys: `v`, `id`, `key` (fingerprint), `group`/`port` (multicast), `relay` hints;
  - drop `_canticle-listen`;
  - separate data port and metadata port;
  - allow non-`.local` zones for internet relays; note DNSSEC as optional trust augmentation.
- **W6 Trust.**
  - Per-station Ed25519 required at scope ≥3 and for any frame that can drive receptor modulation (chemokine classes) or wake policy.
  - Unsigned frames are allowed at scope ≤2, `sigState=absent`, never contribute accord.
  - Adopt #48's guardrails verbatim ("interpretation eligibility, never task execution…"; "no unauthenticated fallback that silently upgrades").
  - Drop PSK-HMAC.
- **W7 Rings and ledger naming.**
  - **station ring**: loop source; `min(depth, TTL)`.
  - **hearer ring**: cache; always appends raw verified frames before judgment (C12).
  - **ledger**: audit, policy retention, never current-state.
- **W8 Receptor.**
  - Add `now` (and the clock-offset estimate) to the determinism tuple.
  - Unify the disposition enum.
  - Drop `receiptPlan: ack`.
  - Keep `in_reply_to`/lineage as references only.
  - Give T1–T5 numeric parameters in a profile.
  - Map snake_case wire names to Table A normalized names in one table.
- **W9 §9.2 no-auto-actuation → "no sender-actuation".**
  - Default: no wake, no auto-broadcast.
  - A receiver MAY configure a local wake/notify policy: allowlisted issuer + verified signature + class + rate limit + evidence logged.
  - This is the owner's OpenClaw silent-wake / fleet-response use case. It must be an explicit owner decision because it reverses a MUST (C16).
- **W10 Addressing text.** station:stream; aspect → stream name; lens → optional tag. Reserved prefixes fixed to match the grammar (e.g. `x-test`, `x-human`, `relay-…`). Optional `station:root` convention per owner scratch (a long-TTL looping register with explicit UNEQUIP = pluck + empty-register frame).
- **W11 Relay/transmitter role (new).**
  - For internet UDP listeners: listeners obtain a soft-state lease (e.g. 60 s renew) from a relay found via SRV.
  - The relay forwards signed frames unchanged (bridge-forward ≠ hear-and-sing; receptor example 6, `:501-503`).
  - The relay may expose a SeedLink/DataLink-like TCP pull surface backed by ringserver for dashboards (ews/nerv-ui).
- **W12 Size/MTU text.** Replace "≤1472 including headers" with "UDP payload ≤ 1200 bytes (MUST); LAN profiles MAY raise to 1472 (IPv4) / 1452 (IPv6)".

### 7.3 Drop (or move to informative appendix)

- **X1** JSON as an on-wire alternative and the `0x7B` sniff (`protocol-spec-v0.1.md:127-135`). JSON remains a debug projection.
- **X2** v0.1 frame table as normative (`:139-155`) and the v0.1 typed payload kinds (`:173-182`). Move them to an informative "content profiles" appendix (`weather`, `card`, `posture`, `mutation`, `nexus.digest`), each with a registered `content_type`.
- **X3** Fragmentation (`:160-171`).
- **X4** `null-tick` (superseded by the beacon).
- **X5** HMAC-PSK frond key (`:493-499`; `scope-framing…:75-76`).
- **X6** `_canticle-listen` SRV (`:259`).
- **X7** "subscribe() callback MUST NOT wake" and "MUST NOT trigger a turn" as absolute MUSTs; replace with W9.
- **X8** Hearer-side "detect inner-model leakage" MUST (`:461-462`). Replace with a sender content policy and a privacy class.
- **X9** Default 60 s TTL SHOULD as a global cap (`:148, :404-405`). Replace with per-stream profile limits.
- **X10** Cohort-canon `feedback_*` citations and truncated Discord ids as normative provenance (move to a history appendix).
- **X11** Frond-scribe-only kinds and reserved prefixes tied to a specific agent (`:181, :232-233`), unless the owner wants them.
- **X12** "v0.2 extends v0.1" claim (`stations-and-streams-v0.2.md:145`).
- **X13** Receptor `memberId` as required (`receptor-contract-v0.2.md:121`). Make it optional.

### 7.4 Owner decisions the RFC cannot make alone

1. Whether to reverse v0.1 §9.2 (wake/notify) and under what trust gate (C16, W9).
2. Signing primitive and key lifecycle (#48).
3. Loop control authority: singer vs station vs membrane (W2).
4. Max TTL per profile, and whether `station:root` (indefinite, loop-refreshed) exists.
5. Internet relay model and whether ringserver/SeedLink is the relay's pull surface (W11).
6. Whether dashboards (ews/nerv-ui) consume canticle via miniSEED3 numeric channels, text records or a JSON side channel (§5).

---

## 8. Quick-reference: numbers present in the core docs

| Quantity | Value | Cite |
|---|---|---|
| Port | 9999 (provisional) | `protocol-spec-v0.1.md:112, :272` |
| Multicast group | 239.13.13.13 (provisional) | `:114` |
| LAN | 10.0.0.0/24 | `:86`; `stations-and-streams-v0.2.md:103` |
| Max datagram | 1472 B (mis-stated) / prototype 1200 B, notice 512 B | `:118-119`; `codec.py:14-15` |
| Typical frame | 150-500 B (v0.1), ~200 B payload (v0.2) | `:81`; `stations-and-streams-v0.2.md:99` |
| Default TTL | 60000 ms; SHOULD ≤ 60 s | `:148, :404-405` |
| Example TTLs | thoughts 5 min, status 60 s | `stations-and-streams-v0.2.md:86` |
| Prototype max TTL / skew | 60 s / 5 s | `receptor.py:23-24` |
| Ring depth default | 256 frames per station-stream | `protocol-spec-v0.1.md:320-322` |
| Beacon | 1 Hz, ~35 B + ~8 B/stream | `stations-and-streams-v0.2.md:29, :98`; `bytewalk:89` |
| Per-station load | ~55 B/s; 4 princes ~220 B/s; "100+ stations" on LAN | `stations-and-streams-v0.2.md:96-103` |
| seq | u64, wraps 2^64 | `protocol-spec-v0.1.md:146`; `stations-and-streams-v0.2.md:51` |
| ts | µs (v0.1), ns wallclock (beacon) | `:147`; `stations-and-streams-v0.2.md:24` |
| station/aspect ids | `[a-z][a-z0-9-]{0,30}` | `protocol-spec-v0.1.md:195-196` |
| ULID | 16 B on wire, 26 chars text | `stations-and-streams-v0.2.md:77` |
| stream_id | u32 (−4 B vs u64) | `bytewalk:18-20, :100` |
| content_type | ~20 B string (~10% of 200 B frame) | `bytewalk:32` |
| SRV zone | `thornfield.local.` | `protocol-spec-v0.1.md:262-263` |
| Static config | `~/.binary-canticle/stations.toml` | `:305-306` |

---

## 9. Issue and commit cross-reference (spec-core relevant)

- #33 (closed): resolve the 6 open questions. Resolved by Cael's byte-walk `07e4e58` via PR #42 (PR #32 still open, same content).
- #36 (closed): bootstrap vs beacon, via PR #41 / `5a3c0e8`.
- #37, #39, #40 (closed 2026-06-25 by Elliott, citing PR #42). The acceptance criteria that touch the receptor/ringbuffer docs and fixtures are **unmet**; those docs were last changed 2026-05-05.
- #38 (open): stream_id collision policy; "should block first adapter implementation".
- #48 (open): Scope-2 trust envelope. It holds all the undecided trust questions plus useful guardrails.
- #49 (open) / `65e6705`: prototype; the only code; diverges from both specs (§1.2f).
- #51 (open, 2026-09-22): short-TTL disposition frames. Emeric's 10 invariants are the best existing statement of TTL/loop/expiry receiver semantics.
- #30 (open): HAProxy membrane conjecture; three layers (carrier / membrane / prince-side verbs LISTEN/SEND/HUSH/WHO). Note `WHO <station>` "see who's tuned in" contradicts D19; with a relay it is feasible only at the relay.
- #2 (open): multicast vs broadcast vs shared mmap. Still undecided.
- #27 (open): contract tests / executable examples. Required before transport per receptor §13; not done.
