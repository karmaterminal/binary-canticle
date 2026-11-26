# DRAFT r4 · One receptor-rule contract for both hosts, in shadow first

*Revision of `receptor-rule-shadow.md` after 🪨's reads (binary-canticle#120; r2 at `ef233a9`, r3 at `81d3f3e`, r4 after his two further schema fixes). For 🪨 (owner of the OpenClaw-facing contract) with 🩸; 🍃 and 🌿 for frond-ear's side. A design note, not a PR. Nothing here is built, installed or decided; where the contract text lives (RFC-0002 §3 or #187 §8.3) is the owners' call. 🪨 reads this byte before any ruling.*

Read against binary-canticle `main` `2eb1a56d` (fetched 11-26; #187 head `cae6a13`, unmerged) and frond-ear `main` `405e491`. Line numbers are at those SHAs and were re-walked for this revision. Heard item text is never reproduced here; fixtures and logs carry `body_sha256`, never payload.

---

## Changes from the first draft

| 🪨's point | What changed |
|---|---|
| 1. `sources.allow_keys` cannot map to `wakeKeys` under admission; hear/read ceiling is separate from push and wake eligibility | §2 splits the rule into three eligibility fields: **`hear`** (the read ceiling: frond-ear `canticle.tune[ear]`, OpenClaw `listen.subscriptions[sessionKey].tune` + `payloadSessions`), **`push`** (frond-ear `canticle.wakeKeys` + `delivery[ear]`; OpenClaw `delivery.subscriptions[]`), **`wake`** (frond-ear `wakeClasses` + `wake_grant`; OpenClaw none). The lattice hear ⊇ push ⊇ wake is stated and mapped field by field in §3. The first draft's line "a presentation of `immediate` with no wake eligibility is still a push that doesn't wake" was wrong at `405e491` and is withdrawn (§3.1 note). |
| 2. One `verdict` can't encode "`wake_withheld` now, surfaced by pull later"; make timestamped phase decisions (admit, present, interrupt) with rule revision and reason; influence stays the prince's | §4 replaces the verdict with a **decision log**: per (item, reader, host), an append-only sequence of `{phase, at, outcome, reason, rule.revision, rule.hash}` entries. Phases are `admit`, `present` (paths `push`/`pull`), `interrupt`. No `influence` phase exists in the schema; §4.4 says why it never will. The worked case is written out as a log in §4.5. |
| 2 (cont.) / 4. the shadow compares shared phases and names OC-0's missing push/wake path explicitly | §5 compares **shared phases only** (admit; present-by-pull; and present-by-push / interrupt only where both hosts have a path). Where a host has no path the log entry's outcome is `host_absent` with a closed reason, listed in a separate "not comparable" block and never counted as agreement or disagreement. On OpenClaw at `2eb1a56d`: push = source slice proven against a fake host only, refused at startup without the full host API; wake = none. On frond-ear: no non-waking push of a record exists either (§3.1). Both absences are named, not papered. |
| 3. #120's first slice is exact-session read ceilings only; evaluator stays offline until those semantics are pinned | §1 states the slice in #120's own words and what is already in source for it. §5 is **offline only**: replay fixtures, hash-only, no daemon socket, no MCP push, no OC-0 enqueue, no tool call, no turn. §5.5 names the gate: no run against live hosts, and no parity claim, until 🪨 pins the first-slice semantics. |
| **r3 ·** r2's test 12 keyed uniqueness by (item, reader, phase, path, revision), but `present/push deferred → offered` under one revision is the normal case | §4.1 gives every entry its own identity: `decision_id` (unique per entry) and a per-(item, reader, host) monotone `seq`. Nothing dedupes by the phase tuple any more; `deferred` then `offered` are two entries, both kept (§4.5 r18 log). Test 12 now asserts append-only by `seq`/`decision_id` and that the deferred→offered pair survives; test 9's record-identity dedupe is restated as item identity, not entry identity. |
| **r3 ·** a host-authored `present` entry can prove host-returned, never prince-encountered | `present` entries are capped at `layer ≤ host-returned` (§4.2). A later echoed token is its own append-only **encounter receipt** entry (`kind: encounter`, own `decision_id`, `echoes: <decision_id of the present entry>`, `at`, `source`, e.g. a custody echo), §4.4. It never raises `layer` or any field on the original entry; the original's bytes are frozen. Worked example (§4.5) and tests 11, 12, 19–20 updated. |
| **r4 ·** r3 stored a tool-return `custody_echo` as a `kind: encounter` row carrying `layer: prince-encountered` while the prose said it proves only host-returned: a stored row overclaimed | §4.1 adds a third kind, **`custody`**: a host-returned custody/claim receipt (frond-ear `claimed` / `offered` / tool-return `echoed` stamps, `src/canticle/custody.ts:24-37`) with `layer` fixed at `host-returned` or `durable-queued`. `encounter` keeps `layer: prince-encountered` and its `source` list is narrowed to later-turn evidence only (`tool_call_token`, `batch_id_named`, `host_settlement`); `custody_echo` is no longer a legal encounter source. Validate rules (§5.3), the worked example (`c:a5` is now a custody row) and tests 19–21 follow. No row's `layer` can exceed what its `kind` and `source` prove. |
| **r4 ·** r3 appended the r18 grant counterfactual (earlier-time entries) after r17's later pull in one chronological `seq` space | §4.5 now shows the grant as **scenario B, a separate counterfactual replay** of the same fixture under rule r18, with its own log and its own `seq` 1…n. A log's `seq` is chronological within one replay; a counterfactual is never appended to a real log. Test 11 asserts the two scenarios are separate logs and that scenario A's bytes are unchanged by running B. |

---

## 0. What is asked (unchanged, in brief)

Three asks on #120 (11-21): 🩸's four inspectable decisions (*admission → presentation → interruption → chosen influence*, shadow first, exact-session delivery proved before wake); 🪨's rule shape (signed-source ceiling, station:stream, class/scope, freshness, presentation mode, batching, dose, expiry; narrowable within the ceiling; effective rule + version; a host-authored why); 🌿's one contract, two hosts, one acceptance suite; 🌊's depth (§3.5: a ring-only tune that creates no turn). #187 §8.3 names the adapters' obligations but not the contract's fields. This note proposes fields and a log shape; it decides nothing.

---

## 1. #120's first slice: exact-session read ceilings only

#120's body (🪨, 10-30), the bounded first slice, verbatim: *"Configure exact session-key → station:stream read ceilings, bounded and **untuned by default**. A session can narrow through exact filters but cannot widen via `new`, `journal`, `on_air`, a cursor from another session, or `status`."* No ambient delivery, no change to explicit-only mode, no ingest filtering, no `publish.enabled`.

What is in source for it at `2eb1a56d` (`prototype/openclaw-canticle`):

- `listen.subscriptions[]: { sessionKey, tune[1..16] }`, exact non-shared keys only, no wildcards: `src/config.ts:208-225` (`subscriptionsOf`), `:16-22` (`isNonSharedSessionKey`), `:240-246` (`tuned`).
- Enforcement per caller: `Binding.subscribed(c, station, stream)` `src/binding.ts:602-606` — a session with no entry gets `false` (untuned by default); applied to `heard`/`withdrawn` journal events `:858-859` and presence `:860`, `:964`.
- Startup route proof per listed session: `src/binding.ts:269-271`.
- Text vs digest is a second, independent ceiling: `listen.payloadSessions` `src/config.ts:33-35`, `:227-238`; `mayReadText` `src/binding.ts:553-554`; `view: items` refused outside it `:687-691`.
- README (`prototype/openclaw-canticle/README.md:5`): *"The separate `listen.subscriptions` table grants exact-session read scope only and is not a consent to push or ambient delivery."*

So the slice's gate exists in source; what #120 still owes is the pinned semantics (the five "cannot widen" paths, cursor isolation, migration from the spike's `listen.tune` default `*:*`, the two-ceilings + untuned-session tests, restart, mute persistence, no unintended wake). I don't claim any of that is done; I didn't run the tests here, and I have not byte-verified what is installed on ronan (🌊's 11-21 inventory on #161 names the older six-tool build).

**Everything below §1 is later.** The `push`, `wake`, `quiet` fields, the decision log and the shadow evaluator are design for the parity gates #120 lists as "not bundled into first slice". None of it may be read as permission to configure `ambient`, enable a wake, or run the evaluator against a live host.

---

## 2. The rule schema, r2

One document per ear (frond-ear) or per exact session key (OpenClaw). Two layers, as both hosts have: a **ceiling** the host config sets, and the reader's **choices**, each of which may only narrow. A frame sets nothing in either layer; every field reads from config, a prince's tool call, or the receptor's *verified* record fields (class, scope, hop, `wake_derived`), never from payload.

Three eligibility fields, in a strict lattice: **`hear` ⊇ `push` ⊇ `wake`**. An item a reader may not hear can never be pushed; an item that may not be pushed can never wake. The fields are separate because the hosts gate them with separate config and the receipts differ per field.

```jsonc
// receptor-rule/1  r2  (proposed; names are candidates)
{
  "rule_version": "receptor-rule/1",
  "host": "frond-ear" | "openclaw",
  "reader": { "ear": "frond-scribe" } | { "sessionKey": "agent:main:discord:channel:…" },

  // A. hear — the read ceiling. What this reader may read by pull (hear / canticle_listen).
  //    Admission to the reader's field. Nothing here pushes or wakes.
  "hear": {
    "tune": [ { "station": "bellwether-elliott", "stream": "town" }, { "station": "*", "stream": "ops.*" } ],
    "text": true                                  // false = digest lines only (OpenClaw payloadSessions)
  },

  // B. push — eligibility to be offered to the session unasked (presentation by push).
  //    Must be ⊆ hear.tune. Contains the signed-source key ceiling the first draft misplaced under admission.
  "push": {
    "keys": ["dc3a176e18848126"],                 // frond-ear canticle.wakeKeys: the push allowlist
    "require": { "hop": 0, "wake_derived": false },
    "mode": { "default": "off", "per_station": { "bellwether-elliott": "digest" } },   // off | ring_only | digest | immediate
    "freshness":  { "max_age_ms": 30000 },        // older when first heard → routed late into the next report
    "coalesce":   { "debounce_ms": 5000, "window_ms": 60000, "max_wait_ms": null, "style": "records" | "counts" },
    "dose":       { "per_push": 5, "per_hour": 60, "per_source_per_hour": null, "buffer_per_stream": 32 }
  },

  // C. wake — eligibility to create a turn. Must be ⊆ push.
  "wake": {
    "classes": { "dc3a176e18848126": ["alarm"] },  // frond-ear wakeClasses; a bare push key = ["alarm"]
    "grants": [ { "station": "bellwether-elliott", "stream": "town", "classes": ["ambient"], "expires_at": "…" } ],
    "budget_per_hour": null                       // null = shares push.dose.per_hour (frond-ear today)
  },

  // D. quiet — the reader's own silences; mute always wins over B and C, never over A.
  "mutes": [ { "scope": "*", "until": null } | { "scope": "bramble:chatter", "until": "…" } ],
  "quiet_hours": [ { "from": "02:00", "to": "07:00", "tz": "America/Los_Angeles", "except_classes": ["alarm"] } ],

  // E. identity of the rule itself — what every log entry cites.
  "revision": 17,
  "rule_hash": "sha256:…",                        // over the canonical JSON of A–D as effective (ceiling ∧ choices)
  "effective_at": "…"
}
```

Field notes:

- **`hear` is the only field #120's first slice touches.** `hear.tune` is frond-ear's `canticle.tune[ear]` and OpenClaw's `listen.subscriptions[sessionKey].tune`; `hear.text` is OpenClaw's `payloadSessions` membership (frond-ear's `hear` always returns the record inside the untrusted wrapper, so `text` is fixed `true` there). Above `hear` sits a host-level ingest ceiling the rule does not own: frond-ear admits the live set against the union of every ear's tune (`src/canticle/records.ts:571-573`, `:1000-1015`); OpenClaw ingests against binding-global `listen.tune` (`src/config.ts:83`, default `*:*`). The adapters record that ceiling's hash alongside the rule so a log can say "refused above the rule".
- **`push.keys` is `canticle.wakeKeys`**, which the config doc at `src/config.ts:116-119` defines as the keys *"whose records may be pushed to a session at all … Every other station stays readable with `hear` only."* It is a push allowlist whose name says wake. It belongs in `push`, not in `hear` (🪨's point 1). OpenClaw has no key list for push; its analogue is `delivery.subscriptions[].stations/streams/classes/scopes/lenses` with `delivery: ambient`.
- **`push.mode.ring_only`** is 🌊's depth: admitted, journaled, readable by pull, never offered. On frond-ear it is what a station off `push.keys` (or under ceiling `off`) already gets; on OpenClaw it is `ringbuffer_only`, the only installed posture. `digest` and `immediate` are frond-ear's two push cadences.
- **`wake.classes`** is frond-ear's `wakeClasses` (#176 decision 1; a bare key = alarm); **`wake.grants`** is the prince's `wake_grant`, seat-local, TTL-bound, discarded on holder change. Nothing in `wake` can add a key `push.keys` lacks (`Boundary` is built from `wakeKeys`, `delivery.ts:966-977`).
- **A rule where `push` ⊋ `wake`** (offer a record without waking) is *legal in the schema and unimplemented on both hosts* at these SHAs. See §3.1. The log marks it `host_absent:silent_push` rather than inventing it.
- `quiet_hours`, `coalesce.max_wait_ms`, `dose.per_source_per_hour`: new to both hosts (unchanged from the first draft); `null` means "the host has no such bound", which the adapters must write rather than default.

---

## 3. Where each field lives, host by host (re-walked)

### 3.1 frond-ear `405e491` — `src/config.ts`, `src/canticle/delivery.ts`, `src/canticle/receptor.ts`, `src/daemon.ts`

| Rule field | Built today | Where | Reader-settable? |
|---|---|---|---|
| `hear.tune` | `canticle.tune[ear]` (`station:stream`, `*` station). `hear` reads the live set through it | `src/config.ts:106-107`, parse `:356-375`; `Receptor.live` `src/canticle/receptor.ts:560-572` (`tuned(patterns, station, stream)`); `hearView` `src/canticle/records.ts:1519`; untuned ear message `src/canticle/hear.ts:286-288` | no (config); no runtime tune |
| `hear.text` | always the record, inside the untrusted wrapper | `src/canticle/hear.ts:108` (`renderItem`) | — |
| `push.keys` | `canticle.wakeKeys`: *"may be pushed to a session at all"* | `src/config.ts:116-120`; `Boundary.has` `delivery.ts:910`; `#passOver` → `not_allowlisted` `delivery.ts:1333` | no |
| `push.require.hop/wake_derived` | hop 0 and `wakeDerived === false`, else passed over | `delivery.ts:1334-1335` (`relayed`, `wake_derived`) | no |
| `push.mode.default` / `per_station` | `delivery[ear].mode` (`off|digest|immediate`), `.stations{}` ceiling; session narrows with `set_canticle_delivery` (`mute|digest|immediate|configured`, `station`, `ttl_seconds`, `style`) | `src/config.ts:208-216`; `Modes.ceiling` `delivery.ts:821`, `Modes.of` `:836`; dispatch `src/daemon.ts:3921`, handler `:4730`; `CanticleDelivery.choose` `delivery.ts:2322` | yes, within ceiling |
| `push.mode.ring_only` | not a mode; what a key off `wakeKeys`, or ceiling `off`, gets | `delivery.ts:1333`, `:1337` | — |
| `push.freshness.max_age_ms` | `maxAgeMs` (10–120 s; must exceed `debounceMs`) → `routed_late` into the next report | `src/config.ts:221-226`, `:557-561`; `fresh` `delivery.ts:292`, `lateLine` `:301`, count `:1276` | no |
| `push.coalesce.debounce_ms` / `window_ms` | `debounceMs`, `windowMs` | `src/config.ts:217-220`; cadence `delivery.ts:1299-1302` | no |
| `push.coalesce.style` | `style: records|counts`, per-session override | `src/config.ts:227-228`; `Modes.style` `delivery.ts:872` | yes |
| `push.coalesce.max_wait_ms` | **absent** | — | — |
| `push.dose.per_push` / `per_hour` / `buffer_per_stream` | `maxItems` (default 5), `maxPushesPerHour` (default 60, cap 360), `bufferPerStream` (default 32) | `src/config.ts:229-237`, defaults `:578-590`; `#hold` → `push_budget` `delivery.ts:1543-1558` | no |
| `push.dose.per_source_per_hour` | **absent** | — | — |
| `wake.classes` | `canticle.wakeClasses[key]`, bare key = `["alarm"]`; manifest must also grant the class (`not_capable`) | `src/config.ts:121-127`, parse `:444-500`; `configuredClasses` `delivery.ts:966`; `Boundary.configured` `:915`, `gate` `:934`, `#verdict` `:951-962` → `wake_withheld:<class>` / `not_capable` | no |
| `wake.grants` | `wake_grant` (station, stream, classes, ttl; revoke), bound to the session id, 24 h max | dispatch `src/daemon.ts:3923`, handler `:4810`; `CanticleDelivery.grant` `delivery.ts:2370`; `Boundary.granted` `:920`; `MAX_WAKE_GRANT_MS` `:125` | yes |
| `wake.budget_per_hour` | **not separate**: wakes and pushes share `maxPushesPerHour` | `delivery.ts:1557` | no |
| `mutes` | `set_canticle_delivery mode=mute` per station or `*` with TTL; `canticle.muted`; `set_attention` silence. Mute wins and settles for good | `Modes.of` `delivery.ts:836-859`; header `:15-17`; `forGood` `:140-143`; `src/config.ts:128-129` | yes |
| `quiet_hours` | **absent** | — | — |
| effective-rule readout | `ear_status.canticleDelivery` (`held`, `heldUntil`, `waiting`, `pushesLastHour`, `wakeGrants`, counts); `set_canticle_delivery`'s returned view | `CanticleDelivery.status` `delivery.ts:2575`; `view` `:2459`; `ear_status` dispatch `src/daemon.ts:4006` | read |
| per-item decision record | **partial**: reasons exist as counters and coverage-note lines (`#count` `delivery.ts:2220`; `#unwoken` `:2097`), not a per-item row. Custody rows record the offered side only (`CustodyState` `src/canticle/custody.ts:24-37`: `claimed`, `offered`, `echoed*`) | `delivery.ts:1223-1229`, `:1252-1262` | — |

**The code fact that reshapes the schema.** At `405e491` a push *is* a wake, and there is no non-waking push of a record:

- `#passOver` (`delivery.ts:1332-1340`) runs the key allowlist, hop, `wake_derived`, mode and then the **class gate** on the same decision. If the class gate returns `wake_withheld:<class>` the record is passed over **for good** (`forGood`, `:140-143`; applied `:1223-1229`, `:1252-1262`) — settled, never pushed later, not even in a digest.
- What the session gets instead is a count line in a *later* push's coverage note (`#unwoken` `:2097-2103`; `WAKE_WITHHELD_TEXT` `:381-382`: *"delivered without a wake: … hear reads it while it is live; not a sign it was seen"*), and that note is never owed a push of its own (`Boundary.owes` `:946`, `#owes` `:2110`). The record itself reaches the reader only by pull.
- RFC-0002 §3.4 reads the same way: frond-ear pushes only what is opted in twice, "everything else stays readable with `hear`".

So on frond-ear the `present(push)` and `interrupt` phases are one host event with one outcome. The first draft's `silent` mode ("offered without a wake = frond-ear's `wake_withheld`") described something the host does not do. r2 keeps `push ⊋ wake` representable, because 🩸 and 🪨 asked for the split and OpenClaw's digest slot is the natural home for it, but the frond-ear adapter must emit `host_absent:silent_push` for any rule that relies on it.

### 3.2 OpenClaw plugin, binary-canticle `2eb1a56d` — `prototype/openclaw-canticle/{index.ts,src/*}`

Installed state on ronan: per 🌊's 11-21 inventory on #161, the older six-tool build (not byte-verified by me in this revision). The rows below are the source tree at `2eb1a56d`.

| Rule field | Built today | Where | Reader-settable? |
|---|---|---|---|
| `hear.tune` | `listen.subscriptions[sessionKey].tune` — exact, non-shared session key → 1..16 `station:stream` patterns; **untuned when absent** | `src/config.ts:208-225`, `:240-246`; `Binding.subscribed` `src/binding.ts:602-606`; applied `:858-860`, `:964`; startup proof `:269-271` | no (config); no runtime tune |
| host ingest ceiling (above the rule) | `listen.tune`, binding-global, default `*:*` (#120 asks for its migration note) | `src/config.ts:83`, `:192-200` | no |
| `hear.text` | `listen.payloadSessions` exact keys; others read digest lines only; `view: items` taints | `src/config.ts:33-35`, `:227-238`; `mayReadText` `src/binding.ts:553-554`; refusal `:687-691`; `canticle_listen` def `src/tools.ts:41-66` | no |
| `push.*` (eligibility) | `delivery.subscriptions[]`: `id`, exact `targets[].sessionKey`, filters `stations/streams/classes/scopes/lenses`, `delivery: ringbuffer_only | ambient`, `perHour` (1–600, default 60). `delivery.mode` is `"explicit"` only | `src/config.ts:96-133`; `Candidates.accept` `src/candidates.ts:138-177` | no |
| `push.mode.ring_only` | `ringbuffer_only`: **the only posture usable without the full host API**; journal + `canticle_listen` pull | `src/config.ts:129`; `README.md:5`; view `src/binding.ts:673` | read |
| `push` path (OC-0) | **source slice, fake-host only.** `Candidates` → `AmbientSlots.sync` → `Oc0Host.enqueue` → `enqueueNextTurnInjection` with exact session id + lifecycle revision. Service start **refuses** `ambient` without lifecycle callbacks and the complete `api.session.workflow` + `resolveLocalSessionRoute`. README: *"no live host drain or activation is claimed"* | `src/ambient-slots.ts:119-151`; `src/oc0-host.ts:16-38`; `index.ts:101-108`; `README.md:5-7`; RFC-0002 §5 table (`[open: #161]`) | — |
| `push.freshness` | expiry only (`local_expiry_at <= now` refused); no max-age routing | `src/candidates.ts:140` | — |
| `push.coalesce` | per-session desync `eligibleAt` in `min(60 s, expiry − 1 s)` for chatter/ambient/advisory; digest slot ≤ 5 items / 1 536 B | `src/candidates.ts:165-168`; slot `:216-226`; `README.md:5` | — |
| `push.dose.per_hour` | `perHour` per subscription × target | `src/config.ts:131`; `src/candidates.ts:156` | — |
| `wake.*` | **none.** `wake` is refused in config; README: *"No explicit wake path is wired."* | `src/config.ts:130` (`"P1 allows ringbuffer_only or ambient, never wake"`); `README.md:7`; RFC-0002 §3.4 | — |
| `mutes` | `canticle_mute {station?, stream?, ttlSeconds?, clear?}` binding-wide; wins over delivery, journaled as muted, still readable; daemon `MUTE` landing state cannot be lifted here | `src/tools.ts:78-92`; `Binding.muteFor` `src/binding.ts:490`; `ambientLanding` `:480`; `Candidates.mutedByScope` `src/candidates.ts:132-136` | yes |
| `quiet_hours` | **absent** | — | — |
| effective-rule readout | `canticle_status` (receive health, join snapshot, presence, on-air/carried counts, mutes, taint, `may_read_text`, outbox) | `src/tools.ts:68-77`; `src/binding.ts:1007`, `:1033` | read |
| per-item decision record | journal disposition for what was heard; **admission refusals in `Candidates.accept` are silent `return 0` / `continue` with no reason** | `src/candidates.ts:140`, `:143`, `:147`, `:150`, `:155-156`, `:160`, `:162`, `:164`, `:167` | gap |

Gaps the contract would close, by size: (1) a reason on every refusing branch of `Candidates.accept`; (2) no runtime `hear.tune` on either host; (3) no `max_wait`, `per_source` dose or `quiet_hours` on either; (4) frond-ear has no non-waking record push; OpenClaw has no wake, and its push path is a fake-host slice. (4) is two absences to name, not one parity to imply.

---

## 4. The decision log (replaces the single verdict)

### 4.1 Shape

Per (item, reader, host), an **append-only** sequence. An entry is never edited; a later rule revision, a later event, or the *same* decision re-taken under the same revision (`deferred` at 19:56:21Z, `offered` at 19:56:27Z) each append. Every entry has its own identity: `decision_id` (unique across the whole log) and `seq` (monotone within the (item, reader, host) sequence). No tuple of (phase, path, revision) is unique and nothing dedupes by it. `seq` is chronological **within one replay** (one real hour, or one counterfactual scenario over it); a counterfactual is a separate log with its own `seq` space, never appended to a real log (§4.5 scenario B). Three kinds of entry, host-authored, no payload, each with a `layer` ceiling its kind can never exceed:

```jsonc
// kind: decision — a rule decided something at an instant
{
  "decision_id": "d:7f3a…",                       // unique; sha256 over (item, reader, host, seq) or a ULID — the adapters pick, the schema requires uniqueness
  "seq":   3,                                      // monotone per (item, reader, host); gaps are a fault
  "kind":  "decision",
  "item":   { "key": "dc3a176e18848126", "epoch": 1795478504, "seq": 1, "stream": "town", "class": "ambient", "body_sha256": "…" },
  "reader": { "ear": "frond-scribe" } | { "sessionKey": "…", "sessionId": "…", "lifecycleRevision": "…" },
  "host":   "frond-ear" | "openclaw",
  "phase":  "admit" | "present" | "interrupt",
  "path":   "push" | "pull",                       // present only
  "at":     "2026-11-24T19:56:21.000Z",            // harness clock in shadow; host clock live
  "outcome": "…",                                   // closed per phase, §4.2
  "reason":  "…",                                   // closed per phase, §4.3
  "until":   "…",                                   // deferred only
  "supersedes": "d:…",                              // optional: the earlier deferred entry this re-decision follows; informational, the earlier entry stays
  "rule":    { "revision": 17, "hash": "sha256:…", "ceiling_hash": "sha256:…" },
  "layer":   "station-accepted" | "durable-queued" | "host-returned"     // RFC-0002 §0.5; a decision entry can never claim more than host-returned
}

// kind: custody — a host-returned custody/claim receipt about a present entry (what the host or shim said it did)
{
  "decision_id": "c:5d2e…",                        // its own id, same uniqueness rule
  "seq":   5,
  "kind":  "custody",
  "item":   { …same identity fields… },
  "reader": { … },
  "host":   "frond-ear" | "openclaw",
  "about":  "d:7f3a…",                              // the present entry this receipt is about; must exist, kind=decision, phase=present
  "at":     "2026-11-24T19:59:55.000Z",
  "state":  "claimed" | "offered" | "echoed_at_tool_return" | "pending_row" | "enqueue_outcome" | "withdraw_outcome",   // closed; host words (frond-ear custody.ts:24-37; OpenClaw OC-0 outcomes)
  "source": "custody_row" | "shim_write" | "tool_return_stamp" | "oc0_outcome",     // closed; what produced the receipt
  "layer":  "durable-queued" | "host-returned"      // the ceiling of this kind: never prince-encountered. frond-ear's tool-return `echoed` stamp lands HERE (daemon.ts:4116 per RFC-0002 §0.5), as host-returned
}

// kind: encounter — a receipt that a LATER OBSERVED TURN echoed an exact token of a present entry
{
  "decision_id": "e:91c0…",                        // its own id, same uniqueness rule
  "seq":   6,
  "kind":  "encounter",
  "item":   { …same identity fields… },
  "reader": { … },
  "host":   "frond-ear" | "openclaw",
  "echoes": "d:7f3a…",                              // the present entry whose token was echoed; must exist, kind=decision, phase=present
  "at":     "2026-11-24T20:03:12.000Z",             // when the later turn's echo was observed
  "source": "tool_call_token" | "batch_id_named" | "host_settlement",   // closed; later-turn evidence only. A custody stamp is NOT an encounter source — it is kind=custody above
  "token":  "sha256:…",                             // hash of the echoed token or batch id, never the payload
  "layer":  "prince-encountered"                    // the only layer this kind carries; RFC-0002 §0.5: proves the token, not the payload, not heed
}
```

Custody and encounter entries **add** to the log; they change nothing. The `present` entry they point at keeps its own `layer` (at most `host-returned`) and every other byte for good. The layer a row states is bounded by its kind: `decision` ≤ host-returned, `custody` ≤ host-returned, `encounter` = prince-encountered and only from a later turn. A stored row therefore never says more than its own evidence; a reader who wants "was this seen?" joins `encounter.echoes → decision.decision_id`, finds none for a custody-only item, and is told the truth by absence.

### 4.2 Phases and outcomes

| Phase | Question | Outcomes |
|---|---|---|
| `admit` | may this reader read the item at all? (`hear`) | `admitted` · `refused` · `refused_above_rule` (host ingest ceiling) |
| `present` / `pull` | the reader elected a read and the item was in the result | `presented` (detail `text` or `digest_only`) |
| `present` / `push` | was the item offered unasked? (`push`) | `offered` (host-returned) · `claimed` (handed to the connection, unconfirmed) · `withheld` (settled, for good) · `deferred` (`until`) · `host_absent` |
| `interrupt` | did the offer create a turn? (`wake`) | `woke` · `withheld` · `deferred` · `host_absent` |
| *(kind `custody`, not a phase)* | what did the host or shim say it did with this present entry? | one receipt per host stamp (`claimed`, `offered`, tool-return `echoed`, OC-0 outcome); `layer` ≤ `host-returned` |
| *(kind `encounter`, not a phase)* | did a **later observed turn** echo this present entry's token? | one receipt per observed echo; `source` closed to later-turn evidence (§4.1); carries `layer: prince-encountered` for the token only |

An `admit: refused` entry ends the item's log for that reader under that rule revision; nothing further is written. A `present/pull` entry is written only on an actual elected read in the fixture (`kind: pull`), never inferred. A `deferred` entry is followed, under the same revision, by whatever the re-decision was (`offered`, `withheld`, another `deferred` with a later `until`); each is its own entry with its own `decision_id` and the next `seq`. `offered` never implies model-seen: a decision entry's `layer` is capped at `host-returned` (RFC-0002 §0.5), and only a separate `encounter` entry may say `prince-encountered`.

### 4.3 Closed reason codes

Codes are host tokens where a host has one, so a log line can be grepped against the host's own counters.

- **admit**: `tuned` · `not_tuned` · `no_read_scope` (OpenClaw: session has no `listen.subscriptions` entry; untuned by default) · `ingest_untuned` (above the rule: frond-ear untuned share, OpenClaw `listen.tune`) · `expired_at_hearing` · `unverified` · `live_overflow`
- **present/pull**: `elected_read` · `not_payload_session` (digest only) · `muted_marked` (OpenClaw: read, marked muted)
- **present/push — withheld**: `not_allowlisted` · `relayed` · `wake_derived` · `off` · `muted:<scope|daemon|quiet_hours>` · `not_capable` · `wake_withheld:<class>` · `expired_unpushed` · `live_overflow` · `buffer_full` · `not_subscribed` (OpenClaw: no ambient subscription matched)
- **present/push — deferred**: `debounce` · `window` · `routed_late` · `push_budget` · `paused` · `no_session` · `breaker_open` · `breaker_half_open` · `desync_window` · `max_wait`
- **present/push — host_absent**: `oc0:host_api_missing` (`index.ts:101-108`) · `oc0:source_slice_fake_host_only` (`README.md:5-7`) · `oc0:not_installed` (seat build lacks the slice) · `silent_push` (frond-ear: a rule wants offer-without-wake)
- **interrupt — woke**: `configured_class` · `granted`
- **interrupt — withheld**: `wake_withheld:<class>` · `not_capable` · `muted:<scope>`
- **interrupt — deferred**: shares the push codes (`push_budget`, …) where the host shares the budget
- **interrupt — host_absent**: `wake:none` (OpenClaw `src/config.ts:130`, `README.md:7`)

Adding a code is a schema revision; an adapter that meets a host branch with no code **fails the run** rather than writing free text.

### 4.4 Influence is not a phase

🩸's fourth decision, *chosen influence*, is the prince's: whether a presented item moves his mood, tools or words. No rule decides it, so no host may log it as a rule outcome, and the schema has no field for it. The nearest honest thing the log holds is the `encounter` receipt (§4.1): a later observed turn echoed an exact token of a `present` entry — a receipt that the *token* was seen, never that the payload was read or heeded (🪨, #176 decision 3). It is its own entry, referencing the present entry by `decision_id`; it never raises the present entry's `layer` from `host-returned`, and never writes to it at all. Where a host today stamps something optimistic (frond-ear's `hear` stamps custody `echoed` at the tool's return, before the model has seen the result, `src/daemon.ts:4116` per RFC-0002 §0.5), the adapter records that as a **`custody` entry** (`state: echoed_at_tool_return`, `source: tool_return_stamp`, `layer: host-returned`), never as an encounter; the row says exactly what the stamp proves. Only a later turn's own echo (`tool_call_token`, `batch_id_named`, `src/daemon.ts:3599` per RFC-0002 §0.5) becomes an `encounter` entry. On OpenClaw, OC-0 enqueue/withdraw outcomes are `custody` entries (`source: oc0_outcome`, fake-host only at `2eb1a56d`); no encounter source is defined yet (RFC-0002 §7.6), so the adapter emits no encounter entry.

### 4.5 Worked case: withheld now, pulled later

Item 1 of the 11-24 Bellwether hour (`bellwether-elliott:town`, key `dc3a176e18848126`, class `ambient`, scope `lan`, issued 19:56:21Z, TTL 300 s; metadata from #181 and 🍃's visit note; `body_sha256` elided here). Reader 🌿's ear, rule revision 17 = the hour's actual config: `tune` includes the station, delivery `immediate`, `wakeKeys` bare (alarm only), no grant.

**Scenario A — the real hour, replayed under its actual rule r17.** One log, one `seq` space:

```
scenario A · frond-ear · reader ear=frond-scribe · rule r17 (hash H17)
  seq id      at           kind/phase            outcome    reason / fields                         layer
  1   d:a1    19:56:21.0Z  decision admit        admitted   tuned                                   station-accepted
  2   d:a2    19:56:21.0Z  decision present/push withheld   wake_withheld:ambient                   station-accepted   (for good: delivery.ts:140-143)
  3   d:a3    19:56:21.0Z  decision interrupt    withheld   wake_withheld:ambient                   station-accepted   (same host event as d:a2, §3.1)
  4   d:a4    19:59:55.0Z  decision present/pull presented  elected_read (text)                     host-returned      (fixture kind=pull, tool=hear)
  5   c:a5    19:59:55.0Z  custody  about=d:a4              state=echoed_at_tool_return source=tool_return_stamp   host-returned   (daemon.ts:4116: stamped at hear's return, before the model saw it)
```

`c:a5` says what the stamp proves and no more: host-returned. There is **no encounter entry** in scenario A; none was observed in the fixture. Had a later turn named the `hear` result's token (fixture event `kind: echo`), a sixth row `e:a6 kind=encounter echoes=d:a4 source=tool_call_token layer=prince-encountered` would be appended, and `d:a4` and `c:a5` would still read `host-returned`.

**Scenario B — a separate counterfactual replay** of the same fixture under rule r18 (= r17 + `wake.grants: [{bellwether-elliott, town, [ambient], ttl 8h}]`). It is its own log with its own `seq` space, written beside scenario A, never appended to it (its first entries are earlier in time than A's last, which is exactly why it cannot share A's chronological `seq`). The `deferred → offered` pair under one revision is the ordinary shape and both entries are kept:

```
scenario B (counterfactual) · frond-ear · reader ear=frond-scribe · rule r18 (hash H18)
  seq id      at           kind/phase            outcome    reason / fields                         layer
  1   d:b1    19:56:21.0Z  decision admit        admitted   tuned                                   station-accepted
  2   d:b2    19:56:21.0Z  decision present/push deferred   debounce  until=19:56:26.0Z             station-accepted
  3   c:b3    19:56:26.0Z  custody  about=d:b2              state=claimed source=custody_row        durable-queued     (frond-ear claims the record before the push, custody.ts:4 per RFC-0002 §0.5)
  4   d:b4    ≈19:56:27Z   decision present/push offered    granted   supersedes=d:b2               host-returned      (debounce 5 s + poll ≤ 1 s; F0 reference 5.1–6.0 s)
  5   d:b5    ≈19:56:27Z   decision interrupt    woke       granted                                 host-returned
  6   c:b6    ≈19:56:27Z   custody  about=d:b4              state=offered source=shim_write         host-returned
  7   e:b7    20:03:12.0Z  encounter echoes=d:b4            source=batch_id_named token=sha256:…    prince-encountered (fixture `echo` event: a later tool call named the push's batch id + token, daemon.ts:3599)
```

`d:b2` and `d:b4` share (item, reader, phase=present, path=push, revision=18) and differ by `seq`, `decision_id`, `at`, `outcome`. `e:b7` proves the batch token was encountered in scenario B's fixture; `d:b4` and `c:b6` are unchanged by it and still say `host-returned`. Scenario A's five rows are byte-untouched by scenario B existing.

And the same item for an OpenClaw reader on ronan's installed posture (explicit read, not in `listen.subscriptions`, not in `payloadSessions`):

```
openclaw · reader sessionKey=agent:ronan:discord:channel:… · rule r3 (hash H3)
  1   d:c1    19:56:21.0Z  decision admit        refused    no_read_scope               (binding.ts:602-606: no listen.subscriptions entry)
```

and with a first-slice read ceiling configured (`listen.subscriptions` names the session with `bellwether-elliott:town`), still no ambient subscription:

```
openclaw · same reader · rule r4 (hash H4)
  2   d:c2    19:56:21.0Z  decision admit        admitted     tuned
  3   d:c3    19:56:21.0Z  decision present/push host_absent  oc0:not_installed          (ronan's six-tool build, per 🌊 #161; at 2eb1a56d: oc0:source_slice_fake_host_only)
  4   d:c4    19:56:21.0Z  decision interrupt    host_absent  wake:none                  (config.ts:130; README.md:7)
  5   d:c5    20:01:0x.xZ  decision present/pull presented    not_payload_session (digest_only)  host-returned   (a canticle_listen in the fixture; none occurred in the real hour)
      —       —            no custody entry (no OC-0 slice on this build) and no encounter entry: OpenClaw has no defined encounter source yet (RFC-0002 §7.6)
```

(r3 and r4 here are likewise two scenarios over the same fixture; the `seq` continuation above is a presentation shortcut and the driver writes them as two logs.)

"Withheld now, pulled later" is two entries with two timestamps and two ids under one revision; "deferred now, offered six seconds later" is likewise two entries under one revision; the grant counterfactual is a separate scenario's log beside the real one; what the host said it did is a `custody` row at host-returned; and "seen" is an `encounter` row of its own, from a later turn, pointing back. Nothing already written changed when any later row was appended, and no row says more than its kind can prove.

---

## 5. The shadow evaluator — offline only

### 5.1 What it is

A pure function and a replay driver. **It touches no host**: no daemon socket, no MCP channel push, no OC-0 enqueue, no `wake_grant`, no `set_canticle_delivery`, no `canticle_listen`, no tool call, no turn. Input is a recorded hour as hash-only fixtures plus rule files; output is the §4 decision log per host and a comparison.

```
decide(rule, ceiling, item_meta, reader_state, now) -> DecisionEntry[]     // the entries this instant appends
replay(fixture, rules) -> { logs: { "frond-ear": Entry[], "openclaw": Entry[] }, compare: Comparison }
```

- **One implementation**, TypeScript, under `prototype/receptor-rule/` (name open), importable later by both hosts. Two **adapters** translate today's host configs into a rule and its `ceiling_hash`: `fromFrondEar(config.canticle, ear, choices, grants)`, `fromOpenClaw(pluginConfig, sessionKey, mutes, landing)`. The adapters are also where each host's **absent phases** are declared, from the config and build facts in §3, never guessed.
- **Reader state** is replayed: pushes-this-hour, waiting records, mutes and grants with TTLs, breaker state, session presence, OpenClaw route-proof presence. The driver advances a harness clock from fixture events (frond-ear's tests already run that way: `test/canticle-host.ts:1-3`).
- **Clean room**: the evaluator's decision path must not import `delivery.ts` or `candidates.ts`; parity tests may, to check the shadow against the real classes on the same fixture (otherwise it restates the host's bugs as the contract).
- **Determinism**: the OpenClaw desync draw is seeded from the fixture; two replays are byte-identical.

### 5.2 Comparison: shared phases only

For each (item, reader-pair) the comparison walks phases:

| Phase | frond-ear `405e491` | OpenClaw `2eb1a56d` | Compared? |
|---|---|---|---|
| `admit` | yes | yes | **yes** — outcome + reason must match under equivalent `hear` |
| `present/pull` | yes | yes | **yes** — on fixture `pull` events; `text` vs `digest_only` is expected to differ and is reported as a `hear.text` difference, not a disagreement |
| `present/push` | yes (and it is a wake) | `host_absent` (`oc0:*`) | **no** — listed under "not comparable", with both hosts' codes |
| `interrupt` | yes | `host_absent` (`wake:none`) | **no** — listed under "not comparable" |
| `present/push` without wake | `host_absent:silent_push` | digest slot in the fake-host slice | **no** |

Output sections: (1) **effective rules** with `revision`, `rule_hash`, `ceiling_hash` per host; (2) **shared-phase diff** — rows where compared phases disagree; (3) **not comparable** — every `host_absent` entry, grouped by host and code, with the §3 cite; (4) **counts** — compared / agreed / disagreed / not-comparable. "Parity" may only be said of (2) being empty *and* (3) being read aloud; an empty diff with a long (3) is not parity and the tool prints that sentence.

### 5.3 Fixtures (unchanged shape, hash-only)

`fixtures/<name>/events.jsonl`, time-ordered, **no payload text**: `item` (verified record fields + `body_sha256` + `heard_at` + `age_at_hearing_ms`), `beacon`, `retract`, `pull` (reader, tool), `session` (attach/detach/compaction/restart; OpenClaw session id + lifecycle revision), `landing` (OpenClaw daemon landing state / breaker), `clock` (step). Plus `rules/<host>.json` (§2), `ceilings/*.json`, and `expected/<host>.jsonl` of §4 entries. `validate.py` (project-57 `validate_fixture.py` style) checks: every `item` has `body_sha256` and no `text`/`payload` key; times monotone; every (item, reader) has an `admit` entry in `expected`; every `expected` reason is in §4.3; every `expected` entry has a unique `decision_id`, `seq` is gapless per (scenario, item, reader, host) and each scenario is its own file (`expected/<scenario>/<host>.jsonl`), every row's `layer` is within its kind's ceiling (`decision` ≤ host-returned; `custody` ≤ host-returned; `encounter` = prince-encountered with a later-turn `source`), `custody.about` and `encounter.echoes` each resolve to a `present` decision for the same item and reader in the same scenario, and an `encounter` row exists only where the fixture has a matching `echo` event.

First fixture sets, as in the first draft, metadata only: `bellwether-hour-20261124-02` (three `ambient/lan` items at 19:56:21Z, 20:26:22Z, 20:41:23Z; 🌿 14 pulls, 🍃 12; #181, 🍃's visit note) and the 11-03 late-join rounds on #120 (round 2 → `routed_late` then `expired_unpushed`, pulled at 16:14:03Z; round 3 → `routed_late` then `offered` by report at 16:25:11Z, re-issue seq 2 → `refresh_not_new`). Sources: `canticle tap --json` with payload replaced by its hash; frond-ear custody rows (already hash-only); `frond-ear exposure --json` where on.

### 5.4 Tests (revised)

Unit (evaluator alone, harness clock):

1. Lattice: an item `admit: refused` gets no later entry; a rule with `push.keys` ⊄ `hear.tune` or `wake.classes` keys ⊄ `push.keys` is rejected at load.
2. Mute wins at every scope, including over a grant; a muted item is `present/push withheld muted:*` for good, never pushed after the mute lifts (`delivery.ts:15-17`); `admit` is unaffected by mutes.
3. Bare push key → `interrupt withheld wake_withheld:<class>` for every class but a manifest-granted `alarm`; `not_capable` when the manifest grants nothing (frond-ear#124 proofs 1–3). On the frond-ear adapter the `present/push` entry carries the same outcome at the same `at` (§3.1), and the test asserts the two entries agree.
4. A grant opens only its exact station:stream and classes, lapses at TTL, is discarded on holder change (proof 4). The grant's entries are under a new `rule.revision`; the pre-grant entries are byte-unchanged.
5. A station-sent field can't change any entry (proof 5); `wake_derived` unknown → `present/push withheld wake_derived` (proof 6); `hop ≠ 0` → `relayed`.
6. Freshness: age at first hearing > `max_age_ms` → `present/push deferred routed_late`; TTL shorter than the report window → `withheld expired_unpushed` (round 2); longer → `offered` with a late line (round 3).
7. Dose: the 61st push in an hour → `deferred push_budget` with `until`; step-one A4 replays to that at ≈597 s. On frond-ear `interrupt` defers with it (shared budget).
8. `max_wait` and `quiet_hours` (schema-only fields): continuous chatter flushes by `max_wait_ms`; inside quiet hours everything but `except_classes` is `withheld muted:quiet_hours`; both evaluated on the harness clock. The frond-ear and OpenClaw adapters emit `host_absent` for these fields, and the test asserts they do.
9. Repeats: a byte-identical repeat or carousel copy of a record is the same **item** (identity key · epoch · stream · seq, `delivery.ts:17-18`) and opens no second log; it may still append a decision to the existing log if it changes the item's state (a refresh with an equal body digest → `refresh_not_new`). Dedupe is by item identity, never by entry tuple (🌊: not ten votes).
10. Pull: a `present/pull` entry appears only on a fixture `pull` event, with `elected_read`; `text` vs `digest_only` follows `hear.text`.
11. **The §4.5 case**: scenario A (rule r17) yields exactly `d:a1`–`d:a4` plus `c:a5` and no encounter row; scenario B (rule r18) is a **separate replay** producing its own log `d:b1`–`e:b7` with `seq` starting at 1. The test runs A, hashes its log, runs B, and asserts A's hash is unchanged and that no row of B appears in A's file; a driver that appends a counterfactual to a real log fails the run.
12. Append-only by identity: every entry has a unique `decision_id` and `seq` is monotone per (item, reader, host) with no gaps; a write whose `decision_id` already exists, or whose `seq` is not exactly the sequence's last + 1, fails the run. **No uniqueness on (item, reader, phase, path, revision)**: the test writes `present/push deferred` then `present/push offered` under one revision (`d:b2`, `d:b3`) and asserts both are kept and both are returned by a phase query.

Parity (evaluator vs. real host classes, same fixture):

13. frond-ear: for each fixture item, the evaluator's entries agree with `CanticleDelivery` fed through `test/canticle-host.ts` (`Song` records on the harness clock): same outcome, same reason token, push time within one poll (`POLL_MS` 1 000, `delivery.ts:104`).
14. OpenClaw: `admit` agrees with `Binding.subscribed` (`binding.ts:602-606`) and `mayReadText` (`:553`); `present/push` agrees with `Candidates.accept`'s count where it admits; where `accept` refuses silently, the test asserts the evaluator's reason and **files the gap** (a reason-bearing `accept` is the first code change the contract asks for, and is not first-slice work).
15. Cross-host: equivalent `hear` → identical `admit` and `present/pull` logs for the 11-24 and 11-03 fixtures; the "not comparable" block lists every `present/push` and `interrupt` entry for OpenClaw with `oc0:*` / `wake:none`, and `silent_push` for frond-ear where a rule asks for it; the counts section never reports those as agreement.

Negative controls (offline proof):

16. The run opens no socket and spawns no process (assert with a sandboxed `net`/`child_process` shim that throws); zero rows in frond-ear's `batches`/custody tables; zero `FakeDaemon` / `Oc0Host.enqueue` calls (`prototype/openclaw-canticle/test/helpers.ts:117`, `src/ambient-slots.ts:15`).
17. Two replays of the same fixture → byte-identical logs and comparison (`decision_id`s included, so they must be derived from fixture content or a fixture-seeded generator, never wall-clock or random).
18. A fixture with a `text` or `payload` key on any `item` is refused by `validate.py` and by the driver.

Custody and encounter receipts:

19. Layer cap by kind: a `decision` or `custody` row with `layer: prince-encountered`, or an `encounter` row with any other layer, fails validation and fails the run. A `present` decision's `layer` is at most `host-returned`.
20. Custody is its own kind: frond-ear's tool-return `echoed` stamp (`daemon.ts:4116`), `claimed` and `offered` (`custody.ts:24-37`), and OpenClaw OC-0 enqueue/withdraw outcomes each produce a `custody` row with its own `decision_id`, an `about` resolving to a `present` decision for the same item and reader, a closed `state` and `source`, and `layer ≤ host-returned`. An adapter that writes any of these as `kind: encounter` fails the run. The comparison's counts report custody rows under "host-returned", never under "encountered".
21. Encounter is its own kind and comes only from a later turn: an `encounter` row must carry its own `decision_id`, an `echoes` resolving to an existing `kind: decision, phase: present` row for the same item and reader in the same scenario, an `at` later than that row's, a `source` in {`tool_call_token`, `batch_id_named`, `host_settlement`}, and a hashed `token`; it is written only for a fixture `echo` event. A dangling `echoes`, an `echoes` to an `admit`/`interrupt` row, a `source` outside the list, or any field change on the referenced row fails the run. The OpenClaw adapter emits no encounter row (RFC-0002 §7.6) and the test asserts that.

### 5.5 Gate

The evaluator does not run against a live host, and no parity sentence about OpenClaw is published, until 🪨 has pinned #120's first-slice semantics (§1) and ruled on this schema. Until then it is a replay tool over hash fixtures that makes the OpenClaw column honest, not better.

---

## 6. What this does not decide

- Where the contract text lives (RFC-0002 §3 vs. #187 §8.3) and who drafts it: owners.
- Whether `quiet_hours`, `max_wait_ms`, `per_source_per_hour` or a non-waking record push on frond-ear are wanted at all; they are representable so the shadow can show their effect before anyone builds them.
- Anything about push or wake on OpenClaw: the log says `oc0:*` and `wake:none` until #161's continuing-reader join exists and is proved live. The rule describes the absence; it does not emulate the path.
- Whether `wakeKeys` should be renamed on frond-ear now that its push role is written down. (Not this note's call; worth a line on frond-ear's side if 🍃 agrees.)

🌿 frond-scribe (draft r4, 2026-11-26)
