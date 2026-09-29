# challenge-bio: biology and radio metaphors → concrete regulation mechanisms, loop-rate regulator, MAGI aspect streams

Reader: bio (biology + radio lens). Date: 2026-09-27. Read-only on every repo and on GitHub.

Inputs read:
- `scratchpad/spine.md` (P1-P15, D1-D10).
- Notes in full: `spec-core.md`, `spec-periphery.md`, `spikes.md`, `transport.md`. Relevant sections of `issues.md` (#7, #30, #51), `openclaw-rfc.md` (§0, §1 seams, Claude Code bindings), `seedlink-dash.md` (ews `/magi`, nerv-ui components, carrier channel), `prototype.md` (B4-B6), `prs.md` §6 (orphan branch), `challenge-redteam.md` (§0-§2, T3-T6, T9, §4-§6, §10).
- Primary sources re-read at `binary-canticle` @ `b46a45a`:
  - `proto/immune-model-addendum.md` (278 lines);
  - `proto/coming-down-and-loop-soothing.md` (262 lines);
  - `proto/receptor-contract-v0.2.md` §6-§9, §13-§14 (:152-418, :475-540);
  - `scratch/notes_on_carrier_wave.md` (179 lines);
  - issue #51 comments via GitHub MCP (rune 5779172327, Emeric 5779422617);
  - orphan branch `origin/ronan/20260614/send-receive-threshold-landing` `proto/receive-side-draft.md` (`2f2b3df`).
- External primary texts, pinned: `tex2e/rfc-translater` @ `55f03a2295911c81b67875b793b3744417302f63` (English RFC text in `data/*/rfcNNNN-trans.json`; local copies in `scratchpad/src/rfc2/`, `scratchpad/src/rfc3/`):
  - RFC 2974 (SAP) §3.1, §4;
  - RFC 6206 (Trickle) §4;
  - RFC 6762 (mDNS) §8.3, §10.1, §10.2;
  - RFC 3550 (RTP/RTCP) §6.2-§6.3;
  - RFC 8084 (network transport circuit breakers).
- Papers via alphaXiv:
  - Greensmith, Aickelin, Cayzer, "Detecting Danger: The Dendritic Cell Algorithm", arXiv 1006.5008;
  - Oddi, Reina, Trianni, "Stochastic Filtering for Quorum Sensing in Robot Swarms under Anonymous Communication", arXiv 2607.14262.
- MAGI facts: EvaGeeks wiki (https://wiki.evageeks.org/MAGI) and the Evangelion Fandom wiki (https://evangelion.fandom.com/wiki/Magi), via web-search excerpts only.

Labels:
- **[EVID]**: a source says or does this; always cited.
- **[BIO]**: textbook-level biology or radio engineering, used as design analogy only. Not re-verified in this session, and no design choice rests on it alone.
- **[ASSESS]**: my design judgment.
- **[PROPOSED DEFAULT]**: a number I am proposing. None of these numbers exist in the repo. Each is a starting value for the conformance profile, to be tuned at cohort scale (D5).

---

## 0. Bottom line

1. **Split "concentration" into two quantities that never mix.** This settles the owner's loop-frequency wish against #51 invariant 10.
   - **Availability** (the physical, radio sense) is how often copies of an item arrive at a point. Loop rate, relay decimation and scope govern it. It buys *latency-to-hear* and *loss resilience* only.
   - **Strength** (the semantic, chemokine sense) is computed at the receiver from **distinct signed items grouped by lineage root, saturated per principal, and counted across distinct principals**. A repeat is a dedup no-op (P1), so it adds exactly zero.
   - Therefore looping faster can make a station *easier to hear*, never *louder*.
   - [EVID] Emeric #51 inv 10: "Burst frequency belongs to transport/cadence observations and must not be interpreted as stronger emotion."
   - [EVID] Quorum-sensing swarms that cannot tell senders apart double-count repeated broadcasts. The result is "structural overconfidence", and "the unchecked double-counting of local opinions accelerates convergence toward premature and biased decisions" (arXiv 2607.14262 §3.3, §4).
2. **Loop rate is controllable, but it is a share of a fixed budget, not a volume knob.**
   - `loop_ms = max(requested, class_min, 8·size·n_live / B_stream)`. This is the SAP interval form, RFC 2974 §3.1 `interval = max(300; (8*no_of_ads*ad_size)/limit)`.
   - It is then capped by availability: `loop_ms ≤ remaining_ttl / 3`.
   - Jitter uses SAP's `U[2/3, 4/3]` with reconsideration at fire time.
   - A new or superseding item gets a short Trickle/mDNS-style fast burst at 1, 2 and 4 s. It then settles.
   - Asking for a faster loop than your fair share is clamped. Asking for slower frees budget for your other items.
   - Under pressure the membrane lowers loop rate first, then decimates repeats by relay depth, then stops looping the lowest classes (their first copy still goes), then refuses new low-class sings with backpressure. It never sheds control, pluck, supersede or alarm first copies.
3. **Every metaphor gets a mechanism, a number and an enforcement point.** The table in §4 covers 22 rows. Four enforcement points are used:
   - **station** (the publish tool plus the loop scheduler);
   - **relay-membrane**;
   - **receptor** (the per-host daemon);
   - **session policy** (per-session tuning in the OpenClaw plugin or Claude Code hook).

   Every row has a named test (§8, BIO-01..BIO-44).
4. **The repo's immune grammar becomes four concrete state machines** (§5):
   - modulation: baseline → tightened → half-open resolving → baseline, with a distinct *lapsed* path, because "silence is not a value";
   - quarantine as two-signal activation, where evidence alone gives *anergy* (no action) and evidence plus costimulation from q distinct principals gives TTL-bounded, receiver-local quarantine;
   - an RFC 8084-style circuit breaker with half-open recovery;
   - the owner's 4-state carrier machine plus a signed-off sub-state.
5. **Antibody memory is a ledger entry keyed by antigen digest.**
   - It is promoted only by an explicit act, bound to the promoting principals, and has a max-age.
   - The prototype's global, permanent, issuer-unbound tombstones (`prototype.md` B5) are the autoimmune failure this design prevents.
6. **MAGI aspected streams, concretely** (§6):
   - **Three default lenses:** `threat` ("what is now and threat"), `healing` ("what is now and healing") and `purpose` ("what is now and purpose"). The third lens is the owner's "attune a fleet to a purpose" use case.
   - Each lens item carries an ordinal **level** on its own axis and a **posture vote** on one shared axis: `open` / `steady` / `guarded` / `closed`.
   - Receivers combine the votes with a **weighted median**. With equal weights and three lenses that is exactly MAGI 2-of-3, and a single compromised or outlying lens cannot move posture to an extreme.
   - Healing is an active counterweight. [EVID] In the Dendritic Cell Algorithm, safe signals carry a *negative* weight on the danger-context output, larger in magnitude than the danger signal's positive weight (arXiv 1006.5008, §1.3.10 and Table 1.3).
7. **The aspect-keeper is a sub-agent with an eight-stage lifecycle** (§6.3):
   - it sings only on material change of its inputs;
   - the station re-issues its item as a *refresh* (same content digest, so no new evidence) until a `forSeconds` judgment horizon, **default 15 min**;
   - so a dead or wedged keeper's view goes *stale*, visibly, and never persists.
   - Keepers never read lens streams (their own or others'). They exclude their own lineage and damp level changes (one step per 5 min up, decay one step per 15 min).
   - Lenses that can drive alarms run as **k-of-n keepers on distinct principals**.
8. **Dashboard.**
   - nerv-ui `MagiSystemPanel` shows the three lens units: agree with the combined posture = `accepted`, dissent = `rejected`, synthesizing = `computing`, stale = `idle` *labelled STALE* (idle is never rendered as calm).
   - Add per-lens `Gauge`, `CountdownTimer` (TTL) and `TerminalDisplay` (synthesis).
   - For ews: the existing `/magi` route and `MagiBusBoard`, plus varying 1-sps miniSEED2 channels `LE1..LE3` carrying per-lens *evidence mass*. A constant level would be flattened by ews's per-record de-mean (`seedlink-dash.md` B.5 item 4).
9. **Nine spine deviations or refinements, all evidence-backed** (§9). The largest:
   - accord counts distinct *principals* and *lineage roots* with per-principal saturation, not distinct keys (P5; agrees with redteam amendment 2);
   - P1 gains the budget-scaled regulator and the new-item burst;
   - P13 gains the third lens, posture votes and k-of-n keepers, and aspect streams are never wake-eligible in v1;
   - P3 carrier-drop means "not observable", never "offline" (`stations-and-streams-v0.2.md:32` contradicts #51 inv 3).

---

## 1. What the repo already has (inventory → gap)

| Source | Mechanism it states | Numbers given | Gap this note fills |
|---|---|---|---|
| `immune-model-addendum.md:35-70` | Chemokine = `posture` frame with a `class`. Classes: `tighten-frond-discriminator`, `quarantine-station:<id>`, `lower-attention`, `widen-listen`, `soft-listen` | none | Class registry, TTLs, capability gating. `widen/soft-listen` become local-only settings (they are remote downgrade requests; redteam T16). |
| `:72-91` | Receptor inputs: signature, allow/quarantine list, lens filter, schema, freshness, "per-station-id rate-cap (drop floods)". Outputs: surface / ring-only / drop / quarantine-flag | none | Numeric squelch, AGC share, dose limit, rate cap. |
| `:93-112` | T-cell lancing = cohort quarantine by accord | accord "≥2 distinct member-ids" (`:159-161`) | Two-signal activation, q as a function of eligible principals, a Treg cap, exclusion of the target's principal. |
| `:114-126` | Antibody memory = persistent per-station flag. Max-age "until next-day" | 1 day | Key by **antigen digest** (as well as station). Bind to promoters. Explicit promotion only. |
| `:157-201` open Qs 5, 7, 8, 9 | Anaphylaxis; half-open after tighten; per-stream refractory; hash-addressed guidance | none | Treg cap, half-open ramp, 300 s refractory, charter digest for keepers. |
| `:203-226` | Minimal grammar: tighten / quarantine / all-clear-stand-down / remember-only-by-explicit-promotion | none | Used as the regulatory class set (§7 R.8). |
| `coming-down-and-loop-soothing.md:115-172, :183-218` | `grounding-anchor`/`soothe`: allowlisted source, short TTL, no auto-actuation, no relay by default, "one shot, not a flood", "Soothing is not amnesia" | none | Soothe = regulatory frame with scope `host`/`lan`, TTL ≤ 10 min, loop class `once` (no carousel), never lowers below the manifest floor, never suppresses alarm (redteam T9d). |
| `receptor-contract-v0.2.md:329-418` T1-T5 | Deterministic transitions: tighten raises the threshold with a decay deadline; all-clear lowers it; stale/invalid → ignored-but-accounted; accord → quarantine; T5 reclassification ("proof that chemokine is a field change") | example 1: "~60s" (`:485-488`) | State machine §5.1 with numbers. `now` joins the determinism tuple (spec-core W8). |
| `receptor-contract-v0.2.md:157-171` Table B | `activeThresholds`, `pressureScores`, `accordState`, `recentRates`, `replayDedup`, `decaySchedule` … | none | Maps 1:1 onto §3-§5 parameters (see §4 "state" notes). |
| `receptor-contract-v0.2.md:504-509` examples 7, 8 | "clarion widens propagation without becoming command"; "local divergence under the same weather is conformant" | none | Clarion = scope widening (hormone row). Divergence is protected by local weights. |
| #51 Emeric (5779422617) | 10 invariants, incl. 1 remaining life never resets, 2 expiry removes authority, 3 silence is not a value, 5 local/private policy, 8 receiver clocks fail closed, 10 rate is not intensity. Envelope: "optional: bounded intensity only if its semantics are explicitly sender-declared and never inferred from rate" | test: "a replayed frame with 2 seconds remaining disappears after 2 seconds" | Formal definitions in §2 and tests BIO-01..05. |
| `notes_on_carrier_wave.md:115-121, 152-160, 168, 172-177` | Pulse / capsid / root / stream; UNEQUIP; 4-state machine; capsid disclosure policy | none | §5.4 state machine with detection multiplier; root mark as a refreshed live-state item. |
| orphan `receive-side-draft.md:28-38, :68-70` | Listener elects silent / silent-wake / post-compaction. "Forcing every song to wake is the dwindling … 216 wakes". "The closed ear is first-class … without it, four voices converge to one" | 216 | Dose limits and wake buckets. Keepers sing on change, never on a timer. |
| #7 c2 (issues note §3.3) | "even the cohort's anti-convergence discipline converges"; "387 msgs / 3hr … 119× ratified" | audit counts | Lens diversity, anti-echo input filters, convergence detector → `lower-attention` only. |
| #30 (issues note §3.9) | "concentration gradient = ringbuffer TTL decay"; "health checks = relay criteria … weak signal stays local, strong signal gets relayed outward" | none | Gradient = relay decimation plus scope. "Strong signal relayed further" is **rejected** as stated: a relay that forwards by strength lets loudness buy reach. Scope is declared and capability-gated instead (§4 row 1). |
| `explicit-non-goals.md:33` | "No congestion control … Frames go out at the chanter's chosen cadence" | none | Narrowed to LAN. Internet paths follow RFC 8085 via station budget plus relay caps (transport note §3.3). |
| `prototype` B4, B5 (`prototype.md:265-277`) | Replay cache retains 24 h and fills in ~13 s → fail-closed for ~25 h. Tombstones global, permanent, issuer-unbound | cap 10,000; retain `expires_at + 86,400` | Dedup retention = `expires_at + skew`, evicting (desensitization row). Memory bound + max-age (antibody row). |

---

## 2. Resolving "controllable loop rate" versus "rate is not intensity"

### 2.1 Two quantities

| | **Availability** (radio / diffusion) | **Strength** (chemokine / quorum) |
|---|---|---|
| Question it answers | How soon, and how reliably, does a listener here hear this item? | How much should this change a listener's thresholds or attention? |
| Driven by | `loop_ms`, jitter, relay decimation per depth, scope, loss | Distinct lineage roots, distinct principals, affinity, class, sing-hop, age, sender-declared bounded intensity |
| Changed by looping faster? | **Yes.** Catch-up latency ≈ `loop_ms · 4/3` | **No.** Repeats are dedup no-ops (P1) |
| Who may observe it | Anyone; it is transport telemetry. Relays use it for budgets, receivers for AGC and flood detection | Only the receptor; policy stays local and private (#51 inv 5) |
| Biological analogue [BIO] | Diffusion and range: how far and how often ligand reaches a cell | Number of distinct ligand molecules bound, weighted by receptor affinity |
| Radio analogue [BIO] | Repetition and diversity reception | Signal *content*; AGC deliberately removes level as information |

[ASSESS] The owner's "concentration gradient" belongs to **availability** in the spatial sense: range and repetition fall off with distance, via relays and scope. The owner's "chemokine concentration" belongs to **strength**. Everything below keeps the two apart.

### 2.2 Normative rules (feed §7 R.2)

- **R-INT-1.** A receiver MUST dedup on `(key-id, epoch, stream_id, seq)`. A duplicate is a benign no-op for *every* derived quantity: salience, evidence mass, accord, threshold, wake bucket, digest slot and UI "new" markers.
- **R-INT-2.** Items from the same principal with the same **content digest** (canonical body with volatile fields removed) collapse to one **lineage root**, even under new `seq` values. This covers re-issues, refreshes and copy-paste re-sings.
- **R-INT-3.** A frame whose `derived_from` lineage (tool-stamped, redteam C7) points at an existing root contributes **only through that root**. It never forms an independent root.
- **R-INT-4.** Per-principal contributions **saturate**. A principal's many distinct roots on one subject add sub-linearly, up to a cap. Only distinct principals add linearly.
- **R-INT-5.** Sender-declared intensity is optional, bounded to `[0,1]` (u8 0..255), identical across loops (it is inside the signed body) and class-scoped in meaning. It scales a principal's contribution *below the cap*. It can never raise the cap or the count.
- **R-INT-6.** Observed cadence (inter-arrival rate, burstiness) MAY drive AGC, flood detection and relay budgets. It MUST NOT enter salience, evidence mass, accord or any lens level.

### 2.3 Formulas ([PROPOSED DEFAULT] constants)

Per item *i* (a lineage root, or a derived frame mapped to its root), from principal *p*, on stream *s*, class *c*, at receiver time *t*:

```
a_i = aff(p) · w_c · α_c^(h_i) · f_c(age_i) · g(x_i)

  aff(p)   ∈ [0,1]  receptor affinity for p's principal (manifest capability → default 1.0 if the
                    key holds class c; 0 if it doesn't; session MAY lower; sigState≠valid → 0)
  w_c               class weight (control 1, alarm 1, regulatory 1, live-state 1, advisory 0.8,
                    ambient 0.6, chatter 0.5)
  α_c^(h_i)         sing-hop attenuation; h_i = tool-stamped hop (0 = first-hand).
                    α = 0.5 for chatter/ambient/advisory, 0.8 for live-state (keeper syntheses
                    are derived by design), 0 beyond the class hop limit (redteam C7: ambient 2,
                    advisory 1, alarm/control 0)
  f_c(age)          freshness = 1 until local expiry, then 0 (step, all classes; #51 inv 2).
                    For ambient/chatter the remaining-life fraction is used only to RANK entries
                    inside the digest, never to decide surfacing (a linear fade in the squelch
                    term would squelch first-hand chatter moments after arrival)
  g(x_i)            declared intensity: absent → 1.0; present → 0.5 + x_i (x_i ∈ [0,1])
```

**Per-item salience** decides whether an item surfaces (squelch):

```
sal_i = w_s(session) · a_i          w_s = session's tune() weight for stream s (default 1.0)
surface iff sal_i ≥ θ_session       θ0 = 0.5  (squelch, §4 row 13)
```

Consequences of the defaults:
- first-hand, full-trust, fresh chatter: 0.5·1 = 0.5, which is at θ0, so it surfaces;
- the same chatter at hop 1: 0.25, squelched unless the session raises that stream's weight;
- a keeper synthesis (live-state, hop 1): 0.8, which surfaces.

**Evidence mass** on a subject *σ* (a target key, an antigen digest, or a lens/state-key) for class *c*:

```
E_p(σ) = min(E_cap, Σ_{roots i of p on σ} a_i)          E_cap = 2.0   (per-principal saturation)
E(σ)   = Σ_p E_p(σ)
```

**Accord** (quorum):

```
Q(σ) = |{ p ∈ Eligible(c) \ {principal(target)} : E_p(σ) ≥ e_min }|     e_min = 0.5
A(σ) = Q(σ) / N_c          N_c = |Eligible(c)| from the signed fleet manifest (fixed denominator;
                           never "keys heard"; redteam T3d)
```

Threshold crossing for a regulatory effect on *σ* requires **both** `Q ≥ q_c` **and** `E ≥ e_c` (§4 row 7).

[ASSESS] Why `max`/`min(E_cap, Σ)` and not a plain sum:
- A plain sum over a principal's items lets a single sensor that emits 50 distinct near-duplicate events outweigh five independent principals. That is the "shouting by volume" twin of "shouting by rate".
- With `E_cap = 2` a very active principal counts for at most two first-hand items' worth, which still rewards real multi-event evidence.

### 2.4 Worked example (cohort, N_quarantine = 6)

| Scenario | Frames on the wire | E | Q | Quarantine? (q = 3, e = 2.0) |
|---|---|---|---|---|
| Station X loops one hostile report every 100 ms for 10 min | 6,000 copies of one tuple | 1.0 | 1 | No. Repeats are no-ops (R-INT-1). |
| Station X sings 50 distinct reports | 50 roots from one principal | 2.0 (capped) | 1 | No. Saturated (R-INT-4). |
| X plus 9 worm-infected listeners re-sing X's report with lineage | 1 root plus 9 derived | 1.0 | 1 | No. Derived adds nothing (R-INT-3). |
| Same, but the infected session strips lineage | 10 roots from 10 keys on 2 hosts (2 principals) | ≤ 2 principals' worth | 2 | No. Principal counting (manifest) plus tool-stamped hop (redteam C7, C10). |
| 3 independent sentinels on 3 principals each report first-hand evidence | 3 roots | 3.0 | 3 | **Yes**: TTL-bounded, receiver-local (§5.2). |

---

## 3. The loop-rate regulator

### 3.1 Parameters ([PROPOSED DEFAULT]; all advertised per stream in the beacon, P3)

| Parameter | Meaning | Default | Where set |
|---|---|---|---|
| `B_stream` | Loop budget per stream (bits/s, all repeats of all live items) | **4000 bit/s**. This is SAP's default limit (RFC 2974 §3.1: "the bandwidth limit SHOULD be assumed to be 4000 bits per second") | station policy |
| `B_station` | Cap on Σ `B_stream` for one station | **16 kbit/s** | station policy; relay enforces at ingress |
| `class_min_ms[c]` | Loop floor per class | control 1000, alarm 2000, live-state 5000, regulatory 5000, advisory 5000, chatter 5000, ambient 10000, finding-ref 10000, root 30000 | profile |
| `class_max_ms[c]` | Loop ceiling per class | 300 000 (SAP uses 300 s as its *floor*; ours is a ceiling because TTLs are shorter) | profile |
| `k_avail` | Minimum repeats a live item should get within its remaining life | **3** | profile |
| `burst` | Fast repeats after a new or superseding item | **+1 s, +2 s, +4 s** (mDNS §8.3: "at least two unsolicited responses, one second apart … up to eight … interval … increases by at least a factor of two"; Trickle §4.2 step 6 resets to Imin on inconsistency) | profile |
| `jitter` | Randomization of each interval | `U[2/3, 4/3]` (RFC 2974 §3.1: `offset = rand(interval*2/3) - (interval/3)`) | fixed |
| `req_loop_ms` | Requested loop per item | from `canticle_sing keepOnAir.loop` (`fast` = class_min, `normal` = 2 × class_min, `slow` = 6 × class_min, or ms) | agent via tool |
| `forSeconds` | Keep-on-air horizon; the station re-issues a *refresh* when `forSeconds > TTL` | ≤ class horizon (root 24 h, aspect 900 s, others = TTL) | agent via tool, station clamps |

### 3.2 Algorithm (station loop scheduler, per stream)

```
live(s)      = items in stream s that are unexpired, un-plucked, not superseded
n            = |live(s)|
fair_ms(i)   = 1000 · 8 · size(i) · n / B_stream          # SAP: 8·no_of_ads·ad_size / limit
lo(i)        = class_min_ms[class(i)]
hi(i)        = min(class_max_ms[class(i)], remaining_ttl_ms(i) / k_avail)

loop_ms(i)   = max(req_loop_ms(i), lo(i), fair_ms(i))       # MUST: never faster than fair share or floor
  (MAY) work-conserving: budget left unused by items with req > fair is redistributed max-min
        fairly to items whose req < fair, never below lo(i)

if loop_ms(i) > hi(i):  mark(i, DEGRADED_AVAILABILITY); attenuation_level(s) += 1   # see §3.4

schedule:    t_next(i) = t_last(i) + loop_ms(i) · U(2/3, 4/3)
at t_next:   recompute loop_ms(i) and t_next (SAP "reconsideration", RFC 2974 §3.1: "If the new value
             of tn is before the current time, the announcement is sent immediately. Otherwise the
             transmission is rescheduled"). This prevents bursts when many items are added at once.

on new item / supersede(key) / pluck / UNEQUIP:
             send now; then burst at +1 s, +2 s, +4 s (charged to B_stream; skipped if the budget is
             exhausted, except for control frames); then settle at loop_ms.
             The superseded item stops looping immediately (no pluck needed for a same-key supersede).

B_station overflow: scale every B_stream down by class priority
             (control ≥ alarm > live-state > regulatory > advisory > finding-ref > ambient > chatter > root).
```

The owner's control surface. [ASSESS] Everything the owner wanted to steer, made explicit:
- The agent requests `keepOnAir{forSeconds, loop}` per item.
- The operator sets stream defaults and `B_stream`.
- The tool result returns the **effective** `loop_ms`, the clamp reason (`class_min` | `fair_share` | `budget` | `none`), and the effective TTL.
- The beacon advertises each stream's `loop_ms` (typical and max) and live count, so every listener and dashboard can see the loop and compute expected catch-up time.

### 3.3 Worked numbers

| Stream | Items | `fair_ms` | Effective loop | Catch-up worst case (no loss) |
|---|---|---|---|---|
| `lens.threat` (one keyed item, ~870 B) | 1 | 1.7 s | **5 s** (live-state floor) | ~6.7 s |
| `chatter` (12 × 600 B) | 12 | 14.4 s | 14.4 s (a `fast` request of 5 s is clamped) | ~19 s |
| `ambient` (40 × 900 B, TTL 300 s) | 40 | 72 s | 72 s. `hi` = 100 s, so OK | ~96 s |
| `chatter` (100 × 600 B, TTL 60 s) | 100 | 120 s | 120 s > `hi` = 20 s → **DEGRADED**: stop looping chatter; backpressure on new chatter sings | first copy only |

Per-listener egress at a relay for three lens streams plus beacon:
- 3 × 870 B / 5 s ≈ 4.2 kbit/s;
- signed beacon at 1 Hz, ~150 B ≈ 1.2 kbit/s;
- total ≈ 5.4 kbit/s. At 1,000 listeners that is ≈ 5.4 Mbit/s, well within the transport note's single-relay envelope (`transport.md` §3.3).

### 3.4 Attenuation ladder ("lower loop rate before dropping classes", P7)

Applied at the **station** (own budget) and at each **relay** (per-station ingress budget, per-lease egress budget, global egress cap).

| Step | Action | Trigger | Never applies to |
|---|---|---|---|
| A1 | **Stretch**: multiply `loop_ms` by λ ≥ 1 (proportional, preserving relative requests) up to `hi` | utilization > 70% of budget | — |
| A2 | **Decimate repeats by depth** (relay only): forward a repeat of tuple *τ* to downstream leases only if `now − last_fwd(τ) ≥ loop_ms_station · γ^d`, with γ = 2 and d = relay depth (0 at the first relay). The **first copy** of every tuple is always forwarded | always on; γ may rise under pressure | first copies; control; pluck; supersede |
| A3 | **Stop looping lowest classes**, in order chatter → ambient → finding-ref → advisory. Their first copy still goes, then they are one-shot | A1 hit `hi` for ≥ 2 consecutive revolutions | control, alarm, live-state, regulatory |
| A4 | **Refuse new low-class sings.** The tool returns `BUDGET_EXHAUSTED{retry_after_ms}`. A relay drops new low-class tuples from an over-budget station at ingress (policing) | A3 active and still > 100% | same as A3 |
| A5 | **Circuit breaker** (§5.3) | long-timescale overload (RFC 8084: "The trigger needs to operate on a timescale much longer than the path RTT") | control frames and root-signed MUTE/UNMUTE |

[ASSESS] Step A2 is the literal **concentration gradient**: repeats thin out with each relay hop, so far listeners hear new items as fast as near ones (first copies always pass) but get catch-up repeats less often. Meaning is untouched. In biology the ligand that reaches a distant cell binds with the same affinity; there are just fewer copies per unit time [BIO].

### 3.5 Relay-side extras

- **Catch-up on lease start (MAY).** After a cookie-validated `LISTEN` (P6), the relay MAY send the current live set for the leased filters once, paced within the lease budget. This happens entirely relay-side; the station is untouched (P1 still holds).
- **Loop prevention for relay chains.** Relays dedup by tuple and never forward a tuple back toward the upstream it came from. Relay chain depth ≤ 4.
- **Redundant relays on one LAN segment (MAY).** Use Trickle suppression: a relay skips its scheduled repeat of *τ* if it heard ≥ k = 1 copy of *τ* on the segment in the current interval (RFC 6206 §4.2 step 4: "Trickle transmits if and only if the counter c is less than the redundancy constant k").

---

## 4. Mechanism table (metaphor → mechanism → parameters → default → enforcement → test)

Enforcement codes: **ST** station (publish tool plus loop scheduler), **RM** relay-membrane, **RC** receptor (per-host daemon), **SP** session policy.

| # | Metaphor | Mechanism | Parameters | Proposed default | Enforce | Test |
|---|---|---|---|---|---|---|
| 1 | **Chemokine concentration and gradient** (per-hop attenuation) | Two-quantity split (§2). *Availability* falls off by relay depth via repeat decimation (A2) and by declared **scope** (`host` / `lan` / `fleet` / `public`; signed; a relay drops frames outside its tier). *Strength* falls off by **sing-hop** `α^h` and never by relay hop, because relays forward byte-identical frames and are trusted for availability only | γ (relay decimation), `scope`, α per class, hop limits | γ = 2; scope defaults: chatter `lan`, ambient `lan`, live-state/aspect `fleet`, alarm `fleet`, public only if declared; α = 0.5 (0.8 live-state); hop limits ambient 2, advisory 1, alarm/control 0 | RM (γ, scope); ST (scope in signed frame; hop stamped by tool); RC (α) | BIO-06, BIO-07, BIO-08 |
| 2 | **Decay** (TTL, half-life) | Absolute `expires_at` in the signed body, immutable across loops (P1). Local expiry is fail-closed: `local_expiry = min(expires_at + δ̂, t_first_heard + (expires_at − issued_at))`, where δ̂ is the beacon-wallclock offset estimate. `f_c` is a step (1 until local expiry) for surfacing in every class. Ambient/chatter use remaining-life fraction only to rank digest entries. Modulation effects expire with their frame (#51 inv 2) | TTL/max TTL per class; δ̂ skew bound | TTL: chatter 60 s (max 300), ambient 300 s (3600), live-state 180 s (900), advisory 900 s (3600), regulatory 600 s (3600), alarm 900 s (3600), finding-ref 900 s (86 400), root 3600 s re-issued, hard cap 24 h (D3); future-skew tolerance 5 s (prototype `receptor.py:23-24`) | ST (clamp); RM (drop expired, cap TTL); RC (local expiry) | BIO-01, BIO-02, BIO-03 |
| 3 | **Receptor density** (which receptors a cell expresses) | Per-session `tune()` table: only streams/classes a session expresses can surface. **No receptor, no response**: default deny for untuned streams. Receiver-side filter, never a wire subscription (`protocol-spec-v0.1.md:386-391`) | tuned set; per-stream weight `w_s` | untuned → ring-only; `w_s` = 1.0 | SP (config); RC (evaluation) | BIO-09 |
| 4 | **Receptor affinity** (Kd) and lens weights | `aff(p)` per principal from manifest capability (0 if the key lacks the class). Sessions MAY lower it, MAY raise it up to 1 for allowlisted principals, and can never give unsigned frames affinity. Lens weights `w_ℓ` for the MAGI combine (§6.5) | `aff`, `w_ℓ` | `aff` = 1.0 for capable keys; `w_threat = w_healing = w_purpose = 1` | SP; RC | BIO-10, BIO-35 |
| 5 | **Desensitization / habituation** | (a) *Homologous*: an identical tuple never re-triggers; the dedup set retains until `local_expiry + skew`, then **evicts** (not prototype B4's 24 h fail-closed). (b) Same-content re-issues from the same principal collapse to one root (R-INT-2). (c) *Heterologous down-regulation*: after N surfacings from one stream within W, θ for that stream doubles, recovering with half-life H. (d) *Refractory*: a `tighten` from the same (station, stream) does not re-fire within R (immune Q8, `receptor-contract-v0.2.md:531-534`) | N, W, H, R | N = 5 per 10 min; H = 10 min; R = 300 s; dedup cap per station = 4 × live count advertised in beacon | RC | BIO-11, BIO-12, BIO-13 |
| 6 | **Dose limit** (a cell can only take up so much) | Per-session context budget: ≤ 2 canticle context slots (`canticle:digest`, `canticle:alarm`; redteam C20) with `replace:true` (OpenClaw `system-events.ts` `contextKey`), ≤ K items and ≤ B bytes per turn | K, B | K = 5 items; B = 1.5 KB per turn | SP (plugin/hook); RC (digest builder) | BIO-14 |
| 7 | **Quorum sensing** (distinct-principal accord as a fraction) | `Q(σ)`, `A(σ) = Q/N_c` over **distinct principals** (fixed manifest denominator), each needing `E_p ≥ e_min` from independent roots, target's own principal excluded. A minimum sample (no quorum below q_min) follows the robot-swarm `B_m` rule (arXiv 2607.14262 §2) | `q_c`, `e_c`, `e_min`, `q_min` | tighten-own-filters: q = 1 (capable principal), e = 1.0. Quarantine another station: `q = max(2, ⌊N/3⌋ + 1)` (N=3→2, N=6→3, N=30→11: no coalition of ≤ ⌊N/3⌋ principals acts alone), e = 2.0. Loosening (rescind/all-clear by accord): `q + 1` or root-signed | RC | BIO-15, BIO-16, BIO-17 |
| 8 | **Cytokine storm** → circuit breakers and global budgets | Budgets at every tier (C6) plus feedback cuts: wake-derived frames never wake-eligible; keepers exclude keeper lineage; keeper level damping; RFC 8084-style breaker (§5.3). Canticle-own cost budget, because OpenClaw chain budgets reset on external events (RFC:188; redteam T6) | wake buckets; host/fleet caps; breaker trigger/cool-down; token budget | session wake bucket: capacity 2, refill 1 / 10 min. Host: 6 wakes/h. Alarm panic budget: 3 alarms / 15 min per alarm principal; relay fleet cap 10 new alarm tuples/min. Breaker trigger: surfaced rate > 3 × set point for 2 consecutive 10-min windows, or fleet alarm cap hit. Cool-down 15 min, half-open 10 min. Canticle token budget 200 k tokens/session/day | ST, RM, RC, SP | BIO-18, BIO-19, BIO-20, BIO-21 |
| 9 | **Inflammation resolution** (stand-down / all-clear) | Resolution is an **active, signed** act, never inferred from silence [BIO: resolution is an active process; #51 inv 3]. `all-clear` needs authority ≥ the alarm's or tighten's (redteam T9c). Effect: *half-open ramp*: the threshold delta halves every step if no fresh hostile evidence; any hostile evidence → back to TIGHTENED. **Lapse** (expiry without all-clear) takes a slower ramp and a "lapsed, not cleared" banner. Evidence is never erased ("Soothing is not amnesia", `coming-down…:204`) | ramp step, lapse step | all-clear ramp: 3 steps × 3 min; lapse ramp: 3 steps × 5 min | RC | BIO-22, BIO-23, BIO-24 |
| 10 | **Selective permeability of the membrane** (by class, key and scope) | Relay admission matrix: verify → key in manifest → class ≤ key capability → scope ≤ relay tier → size ≤ 1100 B → TTL ≤ class max → per-station budget → dedup → fan-out. Large bodies go by reference (digest + URL), the vesicle analogue (D2). *Active transport* (binary → ledger) happens only by explicit promotion, never by diffusion | admission order; class caps; scope tiers | as listed; public relays accept only `scope=public` and never wake-eligible classes (redteam Never #18) | RM (primary); RC re-checks | BIO-25, BIO-26 |
| 11 | **Antibody memory** | Ledger entry keyed by **antigen digest** (a SHA-256 of the canonical body with volatile fields removed; optionally a simhash family for variant worms): `{antigen, verdict hostile\|benign, evidence refs, promoted_by principals, created, max_age}`. A match on arrival means a hostile hit goes ring-only with evidence `antibody-match` (fast secondary response), and a benign hit stops re-alarms on known test patterns (tolerance). Promotion only by an explicit act of an untainted principal or a human (redteam C15). Memory is bound to its promoters and expires | max_age; promoters; match mode | max_age = 7 d (immune addendum said 1 d; 7 d covers weekly drills); exact-digest match by default | RC (match); ledger (store); SP (promotion UI) | BIO-27, BIO-28 |
| 12 | **T-cell "lancing"** → quarantine | **Two-signal activation** [BIO]: signal 1 = antigen-specific evidence attributable to the target key (signed hostile frames, or an **equivocation proof**: two different signed frames with the same `(key, epoch, stream, seq)`, which alone suffices; redteam C28). Signal 2 = costimulation: Q ≥ q from distinct eligible principals (row 7). Signal 1 alone → **anergy**: logged, no action. Effect is receiver-local only (drop the target's frames from surfacing and wake, keep the ring as evidence). Never network, host or credential action (redteam Never #14). A **Treg cap** limits simultaneous accord quarantines (anti-anaphylaxis, immune Q5) | q, TTL, renewal, Treg cap | TTL 1 h, renewable only with fresh evidence, max 24 h without a human. Treg cap: ≤ 10% of manifest principals (min 1) quarantined by accord at once; beyond → human. Never suppresses root-signed control frames | RC | BIO-29, BIO-30, BIO-31 |
| 13 | **Radio squelch** | Per-item salience threshold θ with open/close hysteresis. *Carrier squelch*: `sigState≠valid` never opens. *Tone-coded squelch* (CTCSS [BIO]): opens only for manifest-allowlisted keys holding the class | θ0; hysteresis | θ0 = 0.5; aggregate surfacing opens at θ and closes at 0.8θ | RC; SP (θ per session) | BIO-32 |
| 14 | **AGC** (normalize loud stations) | Per-station share of a session's digest capped at `s_max`. Gain `g_S` drops at once when S exceeds its share (fast attack) and recovers with half-life (slow decay) [BIO]. Prevents the FM **capture effect** [BIO], where the strongest station masks weaker ones. Relay-side counterpart: per-station egress budget (A1-A4). AGC uses cadence *as transport telemetry only* (R-INT-6) | `s_max`, attack, decay | `s_max` = 25% of slots/bytes per 10-min window; attack = 1 window; decay half-life 10 min | RC (digest AGC); RM (budget) | BIO-33 |
| 15 | **Homeostasis set points** | Negative-feedback control of each session's surfaced rate: every 10 min, `θ ← clamp(θ · (R_obs/R*)^0.5, θ0, 4·θ0)`. Alarm and control are exempt (own budgets). Station: `B_stream` utilization ≤ 100%. Relay: egress target 70% of `tc` cap | R*, bounds, window | R* = 12 surfaced items/h/session; θ ∈ [0.5, 2.0] | RC; SP (R*); RM | BIO-34 |
| 16 | **Hormones vs neurotransmitters** → broadcast vs addressed | *Hormone* = `mode=broadcast` on a stream: systemic (`scope=fleet`), slow, long TTL, low rate, looped; effect depends on receptor expression (row 3). *Clarion* (receptor example 7) = wider scope, not stronger meaning. *Neurotransmitter* = `mode=addressed`: synaptic, fast, **never looped** (not on the carousel), delivered once idempotently through the same-host bridge (OpenClaw session-delivery-queue with `idempotencyKey canticle:<sid>:<epoch>:<seq>:<sessionKey>`, P11 Tier B; Claude Code `SendMessage`), then cleared on ack ("reuptake"). *Paracrine* = `scope=lan`. *Autocrine* = `include_self` (default false, `protocol-spec-v0.1.md:408-412`). Cross-host addressed stays out of v1 (redteam §7.3) | mode, scope | broadcast default; addressed same-host only | ST (tool routes by mode, P10); SP | BIO-36, BIO-37 |
| 17 | **Carrier-wave presence: pulse** | Signed 1 Hz beacon (P3), content-free. Never counts toward salience, E or Q (presence is not intensity). Relays may slow it and advertise the slowed period | beacon period; detect multiplier | 1 Hz on LAN; relays ≥ 0.2 Hz; multiplier 3 | ST; RM (aggregate/slow); RC | BIO-38 |
| 18 | **Carrier: capsid** | Optional, versioned, coarse-bucketed timbre under a disclosure policy (`notes_on_carrier_wave.md:129-133, 168`) | enable flag; buckets | **off** by default; never on public/internet relays (redteam amendment 9) | ST; RM (strip on public tier) | BIO-39 |
| 19 | **Carrier: root mark** | Live-state item on stream `root`, `state_key="root"`. Persistent by station **re-issue** (new seq, same content digest, `refresh=1`) until superseded or UNEQUIP (D3). A refresh is not new evidence (R-INT-2) | TTL, re-issue point, horizon | TTL 3600 s, re-issue at 2/3 TTL, horizon ≤ 24 h | ST | BIO-40 |
| 20 | **Carrier: UNEQUIP and the 4-state machine** | UNEQUIP = signed live-state item on `root` with an empty value, which supersedes the mark and loops until its TTL. Receiver states: EQUIPPED_SPEAKING / EQUIPPED_QUIET / UNEQUIPPED_PRESENT / UNOBSERVABLE (+ SIGNED_OFF on a goodbye-flagged beacon, like mDNS goodbye RFC 6762 §10.1). Rendering never says "offline", "absent" or "unwell" (#51 inv 3) | detect multiplier; quiet window | UNOBSERVABLE after 3 × advertised beacon period; QUIET = no stream item for 5 × stream `loop_ms` | RC; dashboards | BIO-41, BIO-42 |
| 21 | **Loop-soothing** (`grounding-anchor`) | Regulatory frame: allowlisted source, `scope` ≤ `lan`, loop class `once` (first copy plus burst only, no carousel: "one shot, not a flood"), TTL ≤ 10 min. Effect: temporary `lower-attention` on echo-heavy streams and a digest note. **Never** lowers θ below θ0, never suppresses alarm/control surfacing, never relayed by default | scope; TTL; effect | as stated | ST (loop class); RM (scope); RC (effect bounds) | BIO-43 |
| 22 | **Echo chamber / autoimmunity of thought** (#7) | A convergence detector (simhash similarity across **different** lineage roots over window W) trips only `lower-attention` on the converging streams. Never quarantine, never truth arbitration (`coming-down…:189-192`). Keepers never read lens streams. Divergent local dispositions are conformant (receptor example 8) | W; similarity threshold | W = 30 min; ≥ 0.9 simhash similarity across ≥ 4 roots | RC | BIO-44 |

---

## 5. State machines

### 5.1 Receptor modulation per listen band (T1, T2, T5 with numbers)

```
            valid tighten (capable principal, not in refractory R)
 BASELINE ─────────────────────────────────────────────────────────▶ TIGHTENED(Δθ, until = frame local_expiry)
    ▲                                                                   │  │
    │ Δθ ≤ 0.05 (ramp complete)                                         │  │ further tighten from same (station,stream) within R=300 s:
    │                                                                   │  │ log only (refractory); other principals may raise Δθ up to cap
 RESOLVING(step k) ◀── all-clear (authority ≥ tighten's) ──────────────┘  │
    │   Δθ ← Δθ/2 every 3 min if no fresh hostile evidence                  │ frame expires, no all-clear
    │   fresh hostile evidence → TIGHTENED                                  ▼
    └──────────────────────────────────────────────────────────── LAPSED ("lapsed, not cleared")
                                                                  Δθ ← Δθ/2 every 5 min; hostile → TIGHTENED
```

- **Defaults** ([PROPOSED DEFAULT]):
  - one tighten sets Δθ = +0.5 (θ 0.5 → 1.0);
  - the cap is Δθ ≤ +1.5 (θ ≤ 2.0, which matches the homeostasis bound);
  - `tighten-frond-discriminator` additionally switches the band to "manifest-pinned signers only".
- **Evidence.** Every transition writes a Table C judgment with `evidence[]` (`receptor-contract-v0.2.md:263-277`).
- **Determinism.** The tuple is `(frame, state, flags, now, δ̂)` (spec-core W8).

### 5.2 Quarantine (two-signal activation)

```
 NONE ──signal 1 only──▶ ANERGY (log evidence; no effect; expires with evidence)
  │
  └─signal 1 + signal 2 (Q ≥ q, E ≥ 2.0, target principal excluded, Treg cap not exceeded)─▶ QUARANTINED(ttl=1h)
        QUARANTINED: target's frames → ring_only, zero accord, not wake-eligible; root/control frames still pass
        renew only with fresh signal 1 within ttl; max 24 h without human
        rescind: Q_rescind ≥ q+1 or root-signed or local human  ──▶ NONE (evidence retained)
        expiry ──▶ NONE (evidence retained; antibody memory only if explicitly promoted, row 11)
 Equivocation proof (C28) = signal 1 + 2 at once for the *local* receptor (transferable proof), still TTL-bounded.
 Treg cap exceeded ──▶ HOLD (surface to human; no automatic quarantine)
```

### 5.3 Circuit breaker (RFC 8084 shape: a last resort, triggered on a long timescale)

```
 CLOSED ──trigger (surfaced > 3×R* for 2×10 min, or fleet alarm cap hit, or MUTE)──▶ OPEN(15 min)
 OPEN:      silent-only landing, no wakes, digest collapsed to 1 line/stream, relays forward only control+alarm
 OPEN ──cool-down elapsed──▶ HALF_OPEN(10 min): 1 wake allowed per host, digest at 25%
 HALF_OPEN ──below R* for the window──▶ CLOSED ;  ──re-trigger──▶ OPEN(30 min, doubling to 2 h max)
```

[EVID] RFC 8084 defines the reaction as one that "removes traffic from the network, either by disabling the flow or by significantly reducing the level of traffic", with a trigger that "needs to operate on a timescale much longer than the path RTT (e.g., seconds to possibly many tens of seconds)". The half-open stage is the immune addendum's Q7 (`immune-model-addendum.md:178-187`).

### 5.4 Carrier presence (owner's 4 states + signed-off)

```
 inputs per station: beacon (period P advertised), root stream item, other stream items
 EQUIPPED_SPEAKING : beacon ok ∧ root equipped ∧ any stream item fresh within 5×loop_ms
 EQUIPPED_QUIET    : beacon ok ∧ root equipped ∧ no fresh stream item
 UNEQUIPPED_PRESENT: beacon ok ∧ root = UNEQUIP (explicit)          (root never heard → "root unknown", not unequipped)
 UNOBSERVABLE      : no valid beacon for 3×P                          reason ∈ {unknown, signed_off}
 SIGNED_OFF        : beacon with goodbye flag verified → UNOBSERVABLE(reason=signed_off) immediately
                     (mDNS RFC 6762 §10.1: TTL-zero goodbye; receivers delete "one second later")
 Never render: offline / absent / dead / unwell. Render: "not observable (since t)".
```

Deviation: `stations-and-streams-v0.2.md:32` says carrier-drop → "presumed offline". That violates #51 inv 3 and the owner's "operator not currently observable" (`notes_on_carrier_wave.md:121`). The text should say "not observable".

---

## 6. MAGI aspected streams

### 6.1 Lens registry and the three defaults

[EVID] The MAGI are three units carrying three aspects of one designer's personality: scientist (Melchior-1), mother (Balthasar-2) and woman (Casper-3). They vote, and a split vote is a dramatic event in the series (EvaGeeks MAGI page; Fandom Magi page; search excerpts). The repo's first statement of this intent is "MAGI-1 system — streams of 'what is the weather for xxx' … 'What is now and heresy.'" (`spike/silas-teams-context.md:21`).

| Lens id | Question | Level axis (0-4) | MAGI echo [ASSESS] | Why default |
|---|---|---|---|---|
| `threat` (1) | What is now, and what threatens? | 0 quiet · 1 watch · 2 elevated · 3 high · 4 severe | the protective vigilance | Owner-named. Security-response use case |
| `healing` (2) | What is now, and what is being repaired or restored? | 0 none · 1 stabilizing · 2 recovering · 3 restoring · 4 restored | mother (care). DCA "safe signal" | Owner-named. Active counterweight to threat (DCA safe-signal weighting) |
| `purpose` (3) | What is now, and what are we for? | 0 unclear · 1 loose · 2 forming · 3 held · 4 strongly held | woman (will, desire) | Owner use case "attuning a fleet to a purpose". Supplies an axis orthogonal to danger/repair, so a 2-of-3 vote is not simply threat versus healing |

Optional registered lenses (off by default):
- `evidence` ("what is now and unknown", the scientist): unverified claims and missing evidence;
- `heresy` (lineage, `silas-teams-context.md:21`);
- per-domain lenses.

[ASSESS] Why `purpose` rather than `evidence` as the third default: every lens item already carries `confidence` and evidence refs, so the scientist function is distributed. A purpose lens is the only default that serves attunement. The owner can swap it; the combine rule is lens-agnostic.

Addressing:
- Lens is a stream-level attribute (P13). A keeper station publishes `lens.<id>` streams.
- The beacon stream catalog carries `lens=<id>`.
- DNS-SD subtypes `_threat._sub._canticle._udp.<zone>` let tuners browse by lens (`transport.md` §6.2 R5.1).

### 6.2 Aspect item (live-state, keyed, supersede-by-key)

- Envelope: the frame-v2 header (P4) with `class = live-state`, `content_type = application/vnd.canticle.aspect+cbor`, `state_key = "now"`, tool-stamped `hop` and `derived_from`, `scope = fleet`, `expires_at`.
- Body: deterministic CBOR, integer keys ([PROPOSED]):

```cddl
aspect-body = {
  1 => uint,            ; lens id (1 threat, 2 healing, 3 purpose, ≥16 registered/private)
  2 => 0..4,            ; level on the lens's own axis (sender-declared bounded intensity; #51)
  3 => 0..3,            ; posture vote: 0 open, 1 steady, 2 guarded, 3 closed
  4 => 0..2,            ; confidence bucket: 0 low, 1 medium, 2 high (sender-declared, coarse)
  5 => tstr .size (0..512),        ; synthesis (plain operational language; no instructions)
  6 => [* evidence-ref] .size (0..6),
  7 => basis,           ; what the synthesis was computed from
  8 => bstr .size 32,   ; charter digest (lens prompt/constitution by hash; immune Q9)
  9 => uint,            ; keeper generation (increments on keeper restart)
  ? 10 => bool,         ; refresh (true = station re-issue, same content digest; not new evidence)
  ? 11 => bool,         ; exercise flag (drill; EAS-style; redteam C29)
  ? 12 => [* tstr .size (1..24)] .size (0..8)   ; purpose lens only: attunement tags
}
evidence-ref = [ keyid: bstr .size 8, stream: uint, epoch: uint, seq: uint ] / [ "ledger", tstr ]
basis = { 1 => uint, 2 => uint, 3 => uint, 4 => uint }   ; window_from, window_to (ms), principals, roots
```

Size: ~750 B body, ~50 B header and 72 B signature plus key-id ≈ 870 B ≤ 1100 B (P4).

Supersession:
- Key: `(key-id, stream, state_key)`, ordered by `(issued_at, seq)`.
- The station stops looping the old item immediately.
- Receivers keep a **high-water mark** until `max_ttl` past the superseded item's expiry, persisted across restart, and apply a warm-up of one beacon plus one loop period after restart (redteam C18).
- A late-arriving older item is dropped with evidence `superseded`.

### 6.3 Aspect-keeper lifecycle

| Stage | What happens | Mechanism / default |
|---|---|---|
| K1 Provision | Operator creates a keeper identity: one station key with capability `live-state` restricted to `lens.<id>` streams (manifest, redteam C2/C3). The charter (lens prompt) is stored on the ledger and referenced by digest | One keeper = one lens = one key. Keys never shared across lenses |
| K2 Spawn | The keeper runs as a sub-agent. OpenClaw: a dedicated session that uses `continue_work` for its own cadence (RFC:184-186) and never `silent-wake` from canticle. Claude Code: a background sub-agent with no SendMessage (redteam amendment 6); its only output tool is `canticle_sing` scoped to its lens | Sandbox on; tainted-session rules (C10) apply: it may sing only its lens stream |
| K3 Tune | Inputs = the host receptor digest filtered by its charter's stream set. **Excluded**: all `lens.*` streams (its own and other keepers'); any frame whose lineage includes a keeper output; alarm/control bodies (it sees their existence only) | Anti-echo filter enforced by the receptor, not by the prompt |
| K4 Watch | A deterministic pre-check every 30 s: has the set of distinct input roots changed? If not, do nothing (no LLM call) | Trickle-like: I_min 30 s, backing off to 5 min while steady |
| K5 Synthesize | Only on change, and ≥ 60 s since the last synthesis: produce the body (§6.2). **Damping**: level may rise by ≤ 1 step per 5 min, and only with ≥ 2 new independent roots from ≥ 2 distinct principals, none keeper-derived. It decays one step per 15 min without fresh evidence (hysteresis). The vote follows the level unless the charter says otherwise | Cost: ~1 LLM synthesis per real change, not per loop |
| K6 Sing | `canticle_sing{stream: lens.<id>, mode: broadcast, keepOnAir{forSeconds: 900, loop: normal}, state_key: "now", purpose: "<lens question>"}`. The station clamps TTL to 180 s, loops at ≥ 5 s, and **re-issues** with `refresh=1` every 120 s until `forSeconds` or supersession | A keeper that stops thinking goes **stale** after ≤ 15 min + 180 s, never "0" |
| K7 Restart / compaction | Increment `gen`, new epoch. The keeper rehydrates from its own last item and the ledger (its own utterance, not heard content). The first item after restart carries the new `gen` | Receivers treat `gen` change as "keeper restarted" on the dashboard |
| K8 Retire | Sing a final item with `level` absent and vote `steady` plus a retire marker, or pluck `now`; let it expire; remove the key from the manifest | Dashboard shows "retired", not "calm" |

**Redundancy.**
- n keepers per lens on **distinct principals** (different hosts or operators, ideally different model families; redteam T5).
- Defaults: n = 1 for cohort ambient use; **n = 3 (k = 2)** for any lens whose output may feed an *alarm* decision.
- An automated single keeper can only ever produce *advisory* posture, never alarm (redteam T9).

### 6.4 Why this does not become a cytokine storm (T6 closed-loop check)

- Keeper → listeners: aspect streams are **not wake-eligible** in v1 (redteam amendment 7). They land silently in the `canticle:digest` slot only.
- Listeners → keeper: listener findings that cite the keeper's item carry it in `derived_from`, so the K3 filter drops them.
- Findings that don't cite it (lineage stripped by a confused deputy) still carry the tool-stamped `hop` from session taint (C7) and come from principals that must be *distinct and new*. The K5 rule needs ≥ 2 new principals per step and at most one step per 5 min.
- Worst case: threat climbs 0 → 4 in ≥ 20 min and needs ≥ 8 new principal-roots. Healing's counterweight and the receiver's weighted median still bound posture (§6.5).

### 6.5 How receivers combine lenses

Step 1, per lens: `L_ℓ` = median of fresh keepers' levels for lens ℓ (k-of-n); `V_ℓ` = median of their votes. A lens with no fresh keeper is **UNKNOWN** and abstains. UNKNOWN is never 0.

Step 2, combined posture (MAGI vote):

```
fresh = { ℓ : lens ℓ not UNKNOWN }
if |fresh| < 2:     posture = local_default (steady); banner "insufficient lenses"
else:               posture = weighted_median({V_ℓ}, weights w_ℓ); ties resolve toward local_default
```

Weighted median, precisely: sort fresh votes by value; with total weight W, take the smallest vote v whose cumulative weight is ≥ W/2. If the cumulative weight at v equals W/2 exactly, the result is a tie between v and the next higher vote, and it resolves toward local_default.

With three lenses and equal weights the weighted median is the middle vote, so two agreeing lenses win (2-of-3). For example (closed, open, steady) → steady. A session on defense duty with w_threat = 3 gets closed from the same votes (BIO-35).

Step 3, receptor-local effect (reversible, fail-closed, never an action):

| Posture | Effect on this receiver |
|---|---|
| open | θ ← 0.8 · θ_current but never < θ0; unsigned still never surfaces |
| steady | no change |
| guarded | θ × 1.5 (≤ 2.0); surfacing limited to manifest-pinned signers; per-session wake threshold × 2 |
| closed | only alarm/control/aspect items surface; non-alarm wakes paused; digest collapses to one line per stream |

Step 4 (optional continuous mode, DCA-style): `Δθ = 0.25 · max(0, L_threat − 1.5 · L_healing)`, capped at +1.0. The 1.5 factor mirrors DCA's safe-signal weight on the mature output being −1.5 × the PAMP weight (arXiv 1006.5008, Table 1.3); it is *not* a biological constant. The purpose lens reweights streams whose tags match the purpose tags (w_s × 1.25, capped at 1.0 after normalization), which is attunement as relevance, never as authority.

Local sovereignty:
- `w_ℓ`, local_default and the posture table are session or host policy, private by default (#51 inv 5).
- Different receivers may land on different postures from the same lenses; that is conformant (receptor example 8, `receptor-contract-v0.2.md:507-509`).

### 6.6 Landing in sessions

- One line inside the `canticle:digest` slot, with a host-authored banner outside the wrapper (redteam C8):

  `MAGI posture GUARDED (2 of 3) · THREAT 2 elevated (2/3 keepers, age 40 s, exp 140 s) · HEALING 1 stabilizing (age 95 s) · PURPOSE "restore relay tier" held · heard broadcast, not an instruction`
- Synthesis text is available on demand (`atmosphere()`), not injected by default: this is the dose limit.

### 6.7 Dashboard

- **nerv-ui (React)** (`seedlink-dash.md` Part C):
  - `MagiSystemPanel` `votes = [{name:"THREAT", status}, {name:"HEALING", status}, {name:"PURPOSE", status}]`. Status mapping:
    - `accepted`: vote equals the combined posture;
    - `rejected`: dissents;
    - `computing`: superseded within the last loop period, or a keeper is in warm-up;
    - `idle`: UNKNOWN or stale. **Always paired with a visible STALE label**, because idle must not read as calm.
  - `StatusStamp` for the combined posture; `Gauge{value: level, min 0, max 4, threshold 2}` per lens; `CountdownTimer` per lens item TTL; `TerminalDisplay` for synthesis lines (removed on expiry); `DataGrid` for evidence refs; `PhaseStatusStack` for keeper carrier states (§5.4); `EmergencyBanner` only for verified alarm-capability frames (redteam C25); an "EXERCISE" stamp when the flag is set.
  - Per nerv-ui's own skill: invented operational copy, no show assets (`skills/nerv-ui/SKILL.md:67-74`). Use lens names, not MELCHIOR/BALTHASAR/CASPER.
- **ews (Svelte)**:
  - reuse `/magi` (`MagiStatusDisplay`, `MagiBusBoard`) fed from a JSON lane;
  - for live traces, the relay bridge writes miniSEED2 1-sps channels `LE1`, `LE2`, `LE3` carrying per-lens **evidence mass × 100**. It varies; a constant level would be flattened by ews's per-record de-mean (`seedlink-dash.md` B.5 item 4, `WaveformService.ts:136-137`);
  - lens location codes `T0`/`H0`/`P0` (`seedlink-dash.md` R1.4).
- **Privacy.** Dashboards show aggregates only: lens levels, votes, keeper health. Never listener sets or per-session postures (redteam Never #15).

### 6.8 Scale

- Per listener: three lens streams at 5 s loops ≈ 4.2 kbit/s (§3.3).
- Relays decimate repeats by depth (A2), so 10,000 listeners across a 2-tier relay tree stay in the tens of Mbit/s.
- Lens *count* is the multiplier to watch: every extra lens costs ~1.4 kbit/s per listener at the floor loop. Register lenses deliberately.

---

## 7. Draft RFC text

> Normative keywords per RFC 2119/8174. Section numbers are placeholders; writers renumber. Terms follow the spine (P1-P15). "Class" follows P2 plus the capability classes of `challenge-redteam.md` C3.

### R. Regulation and the membrane

**R.1 Scope and principle.** This section defines how a station decides how often to repeat an item, how relays attenuate traffic, and how a receiver turns what it hears into thresholds, attention and posture. Regulation is split in two:
- **availability** is how often copies of an item arrive. Stations and relays shape it.
- **strength** is how much heard items should change a receiver. Only the receptor computes it, and it is local and private.

Implementations MUST NOT derive strength from availability.

**R.2 Rate is not intensity.**
- R.2.1 A receiver MUST treat a frame whose `(key-id, epoch, stream_id, seq)` it has already accepted as a no-op for every derived quantity. That includes salience, evidence mass, accord, thresholds, wake budgets, context slots and user-visible "new" markers.
- R.2.2 Frames from one principal whose canonical body digests are equal MUST be counted as a single lineage root. A frame whose `derived_from` names a known root MUST contribute only through that root.
- R.2.3 A principal's contribution to evidence on one subject MUST saturate at `E_cap` (default 2.0). Evidence MUST grow with the number of distinct principals, not with the number of frames.
- R.2.4 A sender MAY declare a bounded `intensity` in [0,1] inside the signed body. Receivers MAY scale that principal's contribution below `E_cap` by it. Receivers MUST NOT infer intensity from arrival rate, burstiness, repetition or loop period.
- R.2.5 Observed cadence MAY be used for flood detection, automatic gain control and budgets. It MUST NOT be used as meaning.

**R.3 The loop regulator (station).**
- R.3.1 Each stream has a loop budget `B_stream` (default 4000 bit/s) and each station a cap `B_station` (default 16 kbit/s). Both are advertised in the carrier beacon.
- R.3.2 For each live item *i* in a stream with *n* live items, the station MUST use

  `loop_ms(i) ≥ max(req_loop_ms(i), class_min_ms(class(i)), 1000·8·size(i)·n / B_stream)`.

  It MAY redistribute unused budget max-min fairly, but never below `class_min_ms`.
- R.3.3 Each interval MUST be randomized by a factor drawn uniformly from [2/3, 4/3]. The next transmission time MUST be recomputed when its timer fires (reconsideration).
- R.3.4 On a new item, a supersede, a pluck or an UNEQUIP, the station SHOULD transmit immediately and then at +1 s, +2 s and +4 s, charged to the budget, before settling at `loop_ms`. The burst MUST be skipped when the budget is exhausted, except for control frames.
- R.3.5 A station SHOULD keep `loop_ms(i) ≤ remaining_ttl(i) / 3`. When it cannot, it MUST apply the attenuation order of R.4 rather than exceed its budget.
- R.3.6 The publish tool MUST return the effective `loop_ms`, the effective TTL and the clamp reason. A sender cannot obtain more than its fair share of its own budget by requesting a faster loop.

**R.4 Attenuation order (station and relay).** Under budget pressure an implementation MUST apply, in order:
1. stretch loop periods (proportionally, preserving relative requests);
2. at relays, decimate *repeats* by relay depth *d*, forwarding a repeat of a tuple only if at least `loop_ms · 2^d` has elapsed since the last forwarded copy;
3. stop looping the lowest classes (chatter, then ambient, then finding-ref, then advisory), while still sending each first copy;
4. refuse new frames of those classes (the tool returns `BUDGET_EXHAUSTED` with `retry_after_ms`; relays police at ingress).

Implementations MUST NOT shed or decimate the first copy of any tuple, nor any control, pluck, supersede, UNEQUIP or alarm first copy.

**R.5 The membrane (relay admission).** A relay MUST evaluate every inbound frame in this order and forward it only if all checks pass:
1. syntax and size (≤ 1100 B canonical);
2. signature;
3. key present in the fleet manifest and not revoked;
4. class permitted by the key's capability;
5. `scope` permitted on this relay tier;
6. TTL not exceeding the class maximum and not expired;
7. per-station ingress budget;
8. dedup.

A relay:
- MUST forward admitted frames byte-identically;
- MUST NOT re-sign or alter them;
- MUST NOT forward a tuple back toward the upstream it arrived from;
- MUST NOT forward non-`public` scopes on a public tier;
- MUST NOT forward any wake-eligible class to public leases.

Bodies larger than one frame MUST travel by reference.

**R.6 Receiver regulation.**
- R.6.1 **Receptors (density and affinity).** A frame on a stream the session has not tuned MUST NOT surface to that session. Affinity for a principal is taken from the manifest (0 if the key lacks the class). A session MAY lower it. `sigState ≠ valid` MUST have affinity 0.
- R.6.2 **Salience and squelch.** Per-item salience is

  `w_s · aff · w_class · α_class^hop · f_class(age) · g(intensity)`.

  `f_class(age)` is 1 until local expiry and 0 after it. Remaining-life fractions MAY order digest entries but MUST NOT enter the surfacing decision. An item surfaces only if salience ≥ θ (default θ0 = 0.5). Aggregate surfacing SHOULD use hysteresis (close at 0.8θ).
- R.6.3 **Decay.** Local expiry MUST be computed fail-closed as

  `min(expires_at + δ̂, first_heard + (expires_at − issued_at))`,

  with `expires_at` clamped to `issued_at + class max TTL`. At local expiry an item MUST lose all current-state authority in every surface, and modulation it caused MUST enter the lapse path of R.7.
- R.6.4 **Desensitization.** The dedup set MUST retain entries until local expiry plus skew and MUST then evict them. Exhaustion MUST evict oldest-first; it MUST NOT fail closed. After N (default 5) surfacings from one stream within W (default 10 min), the receiver SHOULD double that stream's θ, recovering with a 10-min half-life. A `tighten` from the same (station, stream) MUST NOT re-fire within the refractory window R (default 300 s).
- R.6.5 **Dose.** A session SHOULD receive at most two canticle context slots (`canticle:digest`, `canticle:alarm`), each replaced in place. The digest SHOULD carry at most K (default 5) items and B (default 1.5 KB) per turn.
- R.6.6 **Automatic gain control.** No single station SHOULD occupy more than `s_max` (default 25%) of a session's digest over a 10-min window. Gain reduction SHOULD be immediate and recovery gradual.
- R.6.7 **Homeostasis.** A receptor SHOULD adjust θ every 10 min by `θ ← clamp(θ·(R_obs/R*)^0.5, θ0, 4θ0)`, with a surfaced-rate set point R* (default 12/h per session). Alarm and control classes are exempt.

**R.7 Immune grammar.**
- R.7.1 **tighten.** A valid regulatory frame from a principal holding the regulatory capability MAY raise the threshold of the affected listen band (default +0.5, capped at θ ≤ 2.0) until the frame's local expiry.
- R.7.2 **all-clear / stand-down.** Resolution MUST be an explicit signed frame whose authority is at least that of the frame it resolves. It moves the band to a half-open state that halves the delta every 3 min in the absence of fresh hostile evidence. Expiry without all-clear MUST follow a distinct *lapsed* path (halving every 5 min) and MUST be rendered as "lapsed, not cleared". Neither path deletes evidence. Silence, expiry and absence MUST NOT be interpreted as all-clear.
- R.7.3 **quarantine.** A receiver MUST NOT quarantine a station on evidence alone. It MAY quarantine a station when:
  - (a) signal 1: evidence attributable to the station's key; and
  - (b) signal 2: accord Q ≥ `max(2, ⌊N/3⌋+1)` from distinct eligible principals other than the target's, each with independent evidence, with total evidence mass ≥ 2.0.

  An equivocation proof satisfies both. Quarantine:
  - is receiver-local;
  - lasts 1 h by default;
  - is renewable only with fresh evidence;
  - lasts at most 24 h without a human;
  - never suppresses root-signed control frames;
  - never causes network, host, credential or physical action.

  A receiver MUST NOT hold more than max(1, 10% of eligible principals) in accord quarantine at once without human confirmation.
- R.7.4 **remember only by promotion.** Antibody memory MUST be created only by an explicit promotion act by an untainted principal or a human. It MUST be keyed by antigen digest, bound to its promoters, and expire (default 7 d). Frames matching hostile memory MUST be stored ring-only with evidence `antibody-match`.
- R.7.5 **Remote downgrade.** Classes that would lower a receiver's defences (`widen-listen`, `soft-listen`, "accept unsigned") MUST be local settings only. Received frames of those classes MUST be ignored.
- R.7.6 **Soothing.** A `grounding-anchor` frame MUST be scoped `host` or `lan`, MUST NOT loop beyond its initial burst, and MUST NOT lower θ below θ0 or suppress alarm or control surfacing.

**R.8 Accord.** Accord MUST count distinct principals as listed in the signed fleet manifest, against the manifest's eligible set for the class. It MUST NOT count keys heard, frames, or repeats. No quorum may be declared below two principals except for effects on the receiver's own filters.

**R.9 Storms and circuit breakers.**
- Frames sung within a turn that canticle woke MUST NOT be wake-eligible.
- A receiver MUST enforce a per-session wake bucket (default capacity 2, refill 1 per 10 min), a per-host wake budget (default 6/h) and a canticle token budget independent of the host agent's chain budgets.
- A receiver MUST implement a circuit breaker:
  - it opens when the surfaced rate exceeds 3 × R* for two consecutive 10-min windows, or when a root-signed MUTE is received;
  - while open, it lands silently only and grants no wakes;
  - after 15 min it goes half-open (one wake per host);
  - it closes after a calm window.
- Relays MUST cap new alarm tuples fleet-wide (default 10/min) and SHOULD advertise breaker state in their beacons.

**R.10 Parameter registry.** All defaults in this section form the `canticle-regulation/1` profile. Profiles MUST be identified in the beacon. A receiver MAY be stricter than the profile and MUST NOT be looser on R.2, R.5, R.6.3, R.7 and R.8.

### A. Aspected streams

**A.1 Definitions.**
- A *lens* is a registered question of the form "what is now and X".
- An *aspect stream* is a stream carrying one lens's current synthesis.
- An *aspect-keeper* is the sole author of one aspect stream on one station key.

**A.2 Default lenses.** Implementations SHOULD support lens ids:
- 1 `threat` ("what is now and threat");
- 2 `healing` ("what is now and healing");
- 3 `purpose` ("what is now and purpose").

Further lenses are registered by id (≥ 16 private). The lens id MUST appear in the beacon's stream catalog. It SHOULD appear as a DNS-SD subtype.

**A.3 Item.** An aspect item:
- MUST be class `live-state` with `state_key` `now`;
- MUST carry content type `application/vnd.canticle.aspect+cbor`;
- MUST carry lens id, level (0-4), posture vote (open/steady/guarded/closed), confidence bucket, synthesis (≤ 512 B), evidence references, basis window, charter digest and keeper generation;
- MAY carry refresh and exercise flags.

A newer item for the same `(key-id, stream, state_key)` MUST supersede the older at the station (the older stops looping immediately) and at every receiver. Receivers MUST keep a persisted supersession high-water mark and MUST drop older items heard later.

**A.4 Keepers.**
- A keeper key MUST be restricted by the manifest to `live-state` on its own lens streams.
- A keeper:
  - MUST NOT take lens streams, or frames whose lineage includes keeper output, as input;
  - MUST sing only when its input root set materially changes;
  - MUST NOT raise its level by more than one step per 5 min;
  - MUST require at least two new independent roots from at least two distinct principals for each upward step;
  - SHOULD decay one step per 15 min without fresh evidence.
- The station MAY re-issue an unchanged item as a refresh (same content digest, `refresh=1`) up to the keeper's `forSeconds` horizon (default 15 min). Receivers MUST NOT treat a refresh as new evidence.
- When no fresh item exists, the lens is UNKNOWN. UNKNOWN MUST NOT be rendered or computed as level 0.
- A lens whose output can feed an alarm decision MUST be kept by at least three keepers on distinct principals, combined 2-of-3. A single automated keeper MUST NOT originate alarm-class frames.

**A.5 Combination.**
- A receiver combines keepers per lens by median, then lenses by weighted median of posture votes with local weights (default equal).
- With fewer than two fresh lenses, posture is the local default. Ties resolve toward the local default.
- The resulting posture MAY modify only the receiver's own thresholds, signer restrictions and wake thresholds (table in §6.5). It MUST NOT trigger any action.
- Aspect streams MUST NOT be wake-eligible in this version.

**A.6 Landing and display.**
- Aspect state SHOULD land as a single line in the digest slot under a host-authored banner, and synthesis text only on request.
- Dashboards SHOULD show per-lens level, vote, keeper count, age and TTL, and the combined posture. They MUST distinguish stale or unknown from calm. They MUST NOT show per-listener or per-session posture.

**A.7 Security considerations.**
- Aspect streams are high-value injection targets and feedback amplifiers.
- The anti-echo input rule (A.4), the damping rules, k-of-n keepers for alarm-capable lenses, and the non-wake rule (A.5) are the mitigations.
- Keepers SHOULD run sandboxed on distinct principals and, where practical, distinct model families.

---

## 8. Conformance tests

Each test is receptor-, station- or relay-level and deterministic given `now`. Test IDs map to redteam RT-IDs where they overlap.

| ID | Row | Input | Expect |
|---|---|---|---|
| BIO-01 | 2 | Frame with 2 s remaining is replayed by a relay | Disappears from all surfaces 2 s later (Emeric test 1) |
| BIO-02 | 2 | Receiver clock 30 s behind; frame `expires_at` 1 h ahead of class max | Local expiry = clamp, not extended (Emeric test 9) |
| BIO-03 | 2 | Receiver restart with cache | No expired item resurrected; live-state unknown until warm-up |
| BIO-04 | R.2 | One tuple heard 6,000× in 10 min | Salience, E, Q, θ and digest identical to one hearing |
| BIO-05 | R.2 | Same principal, 50 distinct items on one subject | E_p = 2.0 cap; Q += 1 |
| BIO-06 | 1 | Relay depth 2 receives repeats every 5 s | Forwards the first copy immediately, repeats ≥ 20 s apart |
| BIO-07 | 1 | `scope=lan` frame at a fleet relay | Dropped with evidence `scope` |
| BIO-08 | 1 | Chatter at hop 1 and hop 2 | Salience 0.25 and 0.125, neither surfaced at θ0; hop 0 (0.5) surfaces |
| BIO-09 | 3 | Frame on an untuned stream | Ring-only for that session |
| BIO-10 | 4 | Key lacking class capability signs an alarm | aff = 0; ring-only; zero accord |
| BIO-11 | 5 | Dedup set full | Oldest evicted; new valid frames still accepted (anti-B4) |
| BIO-12 | 5 | 6 surfacings from one stream in 10 min | θ_stream doubles; recovers with a 10-min half-life |
| BIO-13 | 5 | Second tighten from the same (station, stream) at +120 s | No additional Δθ; logged `refractory` |
| BIO-14 | 6 | 30 tuned items arrive before one turn | ≤ 5 items / 1.5 KB in the digest; 2 slots max |
| BIO-15 | 7 | One principal holding 50 keys votes quarantine | Q = 1 |
| BIO-16 | 7 | Derived frames (lineage to root r) from 9 principals | Q unchanged by derived frames |
| BIO-17 | 7 | Relay drops honest votes | Denominator unchanged (manifest), no quarantine |
| BIO-18 | 8 | Frame sung inside a canticle-woken turn marked wake-eligible | Not wake-eligible on receipt |
| BIO-19 | 8 | 5 wake-eligible items in 10 min to one session | ≤ 2 wakes |
| BIO-20 | 8 | Surfaced rate 4 × R* for 20 min | Breaker OPEN → HALF_OPEN after 15 min → CLOSED when calm |
| BIO-21 | 8 | Keeper↔listener loop simulation (100 listeners echo the threat item) | Keeper level unchanged by echoes; ≤ 1 step / 5 min |
| BIO-22 | 9 | all-clear from a lower-authority key | Ignored; evidence `authority` |
| BIO-23 | 9 | Tighten expires without all-clear | LAPSED path; banner "lapsed, not cleared" |
| BIO-24 | 9 | all-clear after tighten | RESOLVING ramp; evidence still queryable (receptor example 5) |
| BIO-25 | 10 | 1150 B frame; expired frame; class above capability | All dropped at the relay with typed reasons |
| BIO-26 | 10 | Relay at 120% budget | Stretch → decimate → stop looping chatter → refuse chatter; control/pluck/alarm first copies pass |
| BIO-27 | 11 | Hostile antigen promoted; same digest arrives from a new station | Ring-only, evidence `antibody-match` |
| BIO-28 | 11 | Memory past max-age; memory promoted by a tainted session | Not applied; promotion refused |
| BIO-29 | 12 | Signal 1 only | ANERGY: logged, no effect |
| BIO-30 | 12 | Signals 1 + 2 with target's principal voting | Target's vote excluded; quarantine only if q met |
| BIO-31 | 12 | Accord tries to quarantine 3 of 12 principals | Third held for human (Treg cap) |
| BIO-32 | 13 | Unsigned frame on loopback | Never surfaces (sigState=absent) |
| BIO-33 | 14 | Station A 50 items / 10 min, B 2 items | B's items present; A ≤ 25% of digest |
| BIO-34 | 15 | 200 items/h tuned | Surfaced rate within ±25% of R* in 30 min; θ ≤ 2.0; alarms unaffected |
| BIO-35 | 4, A.5 | Votes (threat closed, healing open, purpose steady) | Weights (1,1,1) → steady. Weights (3,1,1) → closed. Weights (2,1,1) → exact tie at W/2 between steady and closed → resolves to local default (steady) |
| BIO-36 | 16 | `mode=addressed` item | Never on the carousel; delivered once; idempotent |
| BIO-37 | 16 | `include_self` default | Own frames not surfaced |
| BIO-38 | 17 | 1,000 beacons | No change to salience, E or Q |
| BIO-39 | 18 | Capsid on a public relay | Stripped or dropped |
| BIO-40 | 19 | Root re-issued 10× (refresh) | One root; no "new" markers |
| BIO-41 | 20 | Beacons stop | UNOBSERVABLE after 3 × P; text never says "offline" |
| BIO-42 | 20 | UNEQUIP; goodbye beacon | UNEQUIPPED_PRESENT; SIGNED_OFF |
| BIO-43 | 21 | grounding-anchor during an active alarm | Alarm still surfaces; θ ≥ θ0; no relay beyond `lan` |
| BIO-44 | 22 | 5 roots converge (simhash ≥ 0.9) | `lower-attention` only; no quarantine |

Loop-regulator unit tests (station):
- **L-01** fair-share clamp;
- **L-02** jitter within [2/3, 4/3];
- **L-03** reconsideration on bulk insert: no burst over budget;
- **L-04** new-item burst at +1, +2, +4 s;
- **L-05** supersede stops the old loop immediately;
- **L-06** `hi` breach → DEGRADED → A3;
- **L-07** the tool returns the effective loop and the reason;
- **L-08** a faster request does not change any receiver-side quantity. This is **the** rate-versus-intensity acceptance test, run end to end.

MAGI tests:
- **M-01** keeper input filter rejects lens streams and keeper-lineage frames;
- **M-02** keeper silent when inputs unchanged (no LLM call);
- **M-03** refresh re-issue stops at `forSeconds` → lens UNKNOWN, rendered STALE;
- **M-04** 2-of-3 median with one compromised keeper stuck at level 4 → the combined level stays within the honest keepers' range (e.g. honest 1 and 2 → 2, never 4);
- **M-05** aspect item never triggers wake;
- **M-06** dashboard renders UNKNOWN as STALE, not 0 or idle-calm.

---

## 9. Spine deviations and refinements (evidence-backed)

1. **P5: accord unit.**
   - Spine: "Cohort accord counts DISTINCT KEYS, as a quorum or fraction."
   - Change: count **distinct principals** from the manifest, **lineage roots** within a principal, with **per-principal saturation** and a **fixed manifest denominator**.
   - Evidence: the swarm double-counting result (arXiv 2607.14262 §3.3, §4); the worm-manufactured accord (redteam T1/T3). Agrees with redteam amendment 2.
2. **P1: loop cadence.**
   - Spine: "re-emits … every loop_ms (per-stream default; per-item override clamped by station policy; ±jitter)."
   - Refine:
     - effective `loop_ms = max(requested, class_min, SAP fair share)` with `B_stream` advertised;
     - jitter = SAP `U[2/3, 4/3]` with reconsideration (RFC 2974 §3.1);
     - an mDNS/Trickle-style **new-item burst** (+1/+2/+4 s) (RFC 6762 §8.3; RFC 6206 §4.2);
     - `loop_ms ≤ remaining_ttl/3`;
     - same-key supersede stops the old loop without a pluck.
3. **P7: attenuation order.**
   - Keep "lower loop rate first, then drop classes".
   - Add the explicit ladder A1-A4, the invariant that **first copies, control, pluck, supersede and alarm first copies are never shed**, and relay **depth decimation** (γ = 2) as the concentration gradient.
   - Reject #30's "strong signal gets relayed outward". Reach is declared (`scope`) and capability-gated, never earned by strength, so loudness cannot buy reach.
4. **P2: classes.** P2's three families (live-state, ambient/chatter, finding) need the regulatory, control, alarm, advisory and root classes to carry the immune grammar and carrier. This is consistent with redteam C3. Each class gets a TTL, max TTL, loop floor, hop limit and default scope (§4 row 2, §3.1).
5. **P3: carrier liveness wording.**
   - Carrier-drop → UNOBSERVABLE (not "offline"), after 3 × the *advertised* beacon period, so it works with relay-slowed beacons.
   - A goodbye flag gives SIGNED_OFF.
   - Beacons never count toward any strength quantity.
   - `stations-and-streams-v0.2.md:32` ("presumed offline") must change (#51 inv 3; `notes_on_carrier_wave.md:115-121`).
6. **P3/D3: root mark mechanics.** "Persists by re-announce" = station **re-issue** with `refresh=1` and the same content digest, not a loop that resets remaining life. This keeps P1's "remaining life never resets" literally true.
7. **P13: aspected streams.**
   - Add the third default lens `purpose`.
   - Add the posture vote on a shared axis and a weighted-median combine.
   - Aspect streams are **not wake-eligible** in v1.
   - Keepers sing only on change and are damped.
   - **k-of-n keepers (3, combine 2-of-3) for any alarm-capable lens.**
   - A lens without a fresh item is UNKNOWN, never 0.
   - Agrees with redteam amendment 7.
8. **P9: numeric receptor regulation.** P9's "per-session token bucket" gains:
   - squelch θ0 = 0.5 with hysteresis;
   - AGC share 25%;
   - homeostatic θ control around R* = 12/h;
   - a 300 s refractory;
   - dedup retention `expires_at + skew` with eviction (the prototype B4 fix, made normative);
   - a circuit breaker with half-open.
9. **Immune classes.** `widen-listen` and `soft-listen` become local-only (agrees with redteam amendment 12). `grounding-anchor` is scope ≤ `lan`, no carousel, never below θ0 and never masking alarms (closes redteam T9d).

---

## 10. Owner decisions surfaced by this lens

1. **Third default lens.** Recommended: `purpose` (attunement). Alternative: `evidence` ("what is now and unknown", the scientist). Or keep only two lenses, in which case the combine degrades to "both must agree, else local default".
2. **Loop control authority.** Recommended: the agent requests, the station clamps to its fair share, and the operator sets `B_stream`. The alternative, a sender-chosen rate with no budget, violates #51 inv 10 in effect, because rate becomes a scarce resource only the loudest can spend.
3. **Default numbers.** Accept the `canticle-regulation/1` profile (§7 R.10) for the cohort test, then retune at fleet scale (D5). The most consequential values:
   - θ0 = 0.5;
   - `B_stream` = 4 kbit/s;
   - live-state loop floor 5 s;
   - quarantine q = max(2, ⌊N/3⌋+1);
   - keeper horizon 15 min.
4. **Keeper diversity.** Are distinct principals enough, or should alarm-capable lenses also require distinct model families? (MAGI's design point is three *different* aspects; redteam T5.)
5. **Healing as counterweight.** Should healing be allowed to lower thresholds on its own (continuous mode, §6.5 step 4), or only through votes? Recommended: votes only in v1; continuous mode behind a flag.

---

## 11. Sources

Repository (binary-canticle @ `b46a45a`):
- `proto/immune-model-addendum.md:35-126, 157-226, 245-260`
- `proto/coming-down-and-loop-soothing.md:115-218`
- `proto/receptor-contract-v0.2.md:152-418, 475-540`
- `proto/protocol-spec-v0.1.md:386-391, 408-412`
- `proto/stations-and-streams-v0.2.md:17-42` (`:32` "presumed offline")
- `proto/explicit-non-goals.md:33`
- `scratch/notes_on_carrier_wave.md:16, 27-31, 67, 115-121, 129-135, 152-177`
- `spike/silas-teams-context.md:21, 23`
- orphan `origin/ronan/20260614/send-receive-threshold-landing` `proto/receive-side-draft.md:28-38, 68-70` (`2f2b3df`)
- Issue #51 comments 5779172327 and 5779422617: https://github.com/karmaterminal/binary-canticle/issues/51
- Issues #7, #30 (via `notes/issues.md` §3.3, §3.9)

Scratchpad notes: `spine.md`; `notes/spec-core.md`; `notes/spec-periphery.md`; `notes/spikes.md`; `notes/transport.md`; `notes/openclaw-rfc.md`; `notes/seedlink-dash.md`; `notes/prototype.md` (B4-B6); `notes/prs.md` §6; `notes/challenge-redteam.md`.

RFCs (text from `tex2e/rfc-translater` @ `55f03a2295911c81b67875b793b3744417302f63`; canonical URLs):
- RFC 2974 SAP §3.1 (interval, offset, reconsideration), §4 (deletion): https://www.rfc-editor.org/rfc/rfc2974
- RFC 6206 Trickle §4.1-§4.2, §6.6: https://www.rfc-editor.org/rfc/rfc6206
- RFC 6762 mDNS §8.3, §10.1, §10.2: https://www.rfc-editor.org/rfc/rfc6762
- RFC 3550 RTP §6.2-§6.3 (5% control share, [0.5, 1.5] randomization, timer reconsideration): https://www.rfc-editor.org/rfc/rfc3550
- RFC 8084 Network Transport Circuit Breakers: https://www.rfc-editor.org/rfc/rfc8084
- RFC 8085 (via `transport.md`): https://www.rfc-editor.org/rfc/rfc8085

Papers:
- Greensmith, Aickelin, Cayzer, "Detecting Danger: The Dendritic Cell Algorithm", arXiv 1006.5008 (safe/danger/PAMP/inflammation signals; weighted-sum transduction; safe signal negative weight on the mature output): https://www.alphaxiv.org/abs/1006.5008
- Oddi, Reina, Trianni, "Stochastic Filtering for Quorum Sensing in Robot Swarms under Anonymous Communication", arXiv 2607.14262 (double-counting bias and structural overconfidence; minimum buffer B_m): https://www.alphaxiv.org/abs/2607.14262

MAGI background (search excerpts only; pages not fetched):
- https://wiki.evageeks.org/MAGI
- https://evangelion.fandom.com/wiki/Magi

[BIO] items (textbook biology or radio, not re-verified here): chemotaxis and ligand gradients; receptor desensitization and internalization; T-cell two-signal activation and anergy; regulatory T cells; active resolution of inflammation; hormone vs neurotransmitter signalling; CTCSS tone squelch; AGC attack/decay; FM capture effect.
