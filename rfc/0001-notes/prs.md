# prs — triage of open PRs and the orphan branch, karmaterminal/binary-canticle

Reader lane: **prs**. Repo `/home/user/binary-canticle`, `origin/main` = `b46a45a` (2026-09-17). All git evidence comes from local `origin/*` refs. GitHub evidence comes from read-only `mcp__github__pull_request_read` and `issue_read`. Nothing was posted or changed on GitHub, and no working tree was modified.

Labels used below:
- **[SAYS]**: what the source text claims.
- **[DECIDED]**: what is actually on `main` or merged.
- **[ASSESS]**: my own judgement.

---

## 0. Bottom line (one table)

| Item | Branch / head | Behind main | Merges clean? | Net new content vs main | Recommendation |
|---|---|---|---|---|---|
| **#50** proto: localhost UDP cue receptor | `prototype/ringserver-seedlink-udp` @ `54fce69` | 4 | yes | 12 code files byte-identical to `main:prototype/ringserver-udp-cue/`; only process files differ (`.lane-workorder-*.md`, `.codeagent-outcome-*.md`); root-level layout | **CLOSE** (landed as `65e6705`) |
| **#44** ring-broadcast infographic (SVG) | `design/ring-broadcast-infographic` @ `daa4e86` | 4 | yes | new `docs/` dir with 1 SVG + 1 md | **MERGE after edits** (layout fixes and 6 accuracy fixes, listed in §2), or **SUPERSEDE** it as RFC Figure 1 after the same edits |
| **#34** return-stage as chemokine-back | `scribe/return-stage-anti-coercion-addendum` @ `8e1a696` | 53 | yes | 1 new doc, not on main; **main already links to it** (dangling link) | **MERGE after light edits**, then fold its §5 MUST-NOTs into the RFC |
| **#32** Cael byte-walk of 6 open questions | `cael/stations-streams-open-questions-bytewalk` @ `7b3d0fb` | 48 | yes (net diff empty) | none: file blob `0225571` is identical on main | **CLOSE** (landed via #42 as `07e4e58`); carry the unlanded sticky-pluck refinement into the RFC |
| **#29** Silas next-cut | `silas/20260505/next-cut-station-stream-ringbuffer` @ `17a212a` | 53 | yes | 1 small memo in `research/silas/` (a dir that does not exist on main) | **CLOSE** (superseded by `proto/ringbuffer-contract.md` the same day, and by v0.2 docs) |
| **orphan** (no PR) | `ronan/20260614/send-receive-threshold-landing` @ `2f2b3df` | 48 | yes | 3 new docs (388 lines): send-side, receive-side, threshold-fire taxonomy v2 | **SUPERSEDE**: fold into the RFC's send-trigger and receive/landing (wake policy, W9) sections. Preserve it as lineage, not as-is: it has a spoofable trust gate and stale mechanism refs |
| (non-PR) | `claude/sleepy-ptolemy-loxrfn` | 0/0 | — | identical to main `b46a45a` | no action (can be deleted by the owner) |

The claim that "#28/#41/#42/#43 show merged=false" is an artifact of the **list** endpoint. The per-PR `get` returns `"merged":true`:
- #28: `merged_by: scribe-dandelion-cult`, merged_at 2026-06-25T06:58:20Z.
- #41, #42, #43: `merged_by: elliott-dandelion-cult`.

All four have merge commits on main:
- `21b46a4` "Merge branch 'ronan/20260505/receptor-contract-v0.2' into main" (#28; local merge, parents `9b62df4` and `7552fd9`).
- `9feeae4` (#42, parents `21b46a4` and `6fc78f5`).
- `b619ca8` (#41, parents `9feeae4` and `5a3c0e8`).
- `8498d8a` (#43, parents `b619ca8` and `e0f5591`).

Method: `git merge-tree --write-tree origin/main origin/<branch>` returned rc=0 (clean) for all six branches (git 2.43.0). For the byte comparisons I used `git rev-parse <ref>:<path>` and compared blob SHAs.

---

## 1. PR #50 — `proto: add localhost UDP cue receptor` (scribe-dandelion-cult, opened 2026-07-26T00:43:45Z)

### 1.1 What it adds [SAYS]

Body (per the PR API): a localhost-only UDP-cue receptor, the "Ringserver 4.5.4 verdict: no native UDP submission path", a closed canonical Ed25519-signed notice envelope, a private `DataLinkPublisher` seam, and a `.gitignore`. It says "Closes #49". The diff is 15 files, +1272 lines, all at repo **root**: `canticle_receptor/*`, `tests/*`, `pyproject.toml`, `.gitignore`, `PROTOTYPE-NOTES.md`, `.lane-workorder-ringserver-seedlink-udp.md`, `.codeagent-outcome-ringserver-seedlink-udp.md`.

### 1.2 Is it already on main? [DECIDED]: yes, byte-identical

All 12 code, test and config files have identical blob SHAs to `origin/main:prototype/ringserver-udp-cue/<same path>`:
- `.gitignore` 43ae0e2
- `__init__` 3f74e7f
- `__main__` 46b0386
- `_publisher` 9885c21
- `codec` c0af0ff
- `model` d4f429f
- `receptor` 7017a26
- `state` 0997019
- `udp` b1d11ed
- `pyproject.toml` 8e22580
- `tests/test_receptor.py` 5a16371
- `tests/test_udp.py` ec600d2

`PROTOTYPE-NOTES.md` equals `main:prototype/ringserver-udp-cue/README.md` except for 2 lines: the title (`# UDP-cue receptor prototype notes` vs `# Ringserver UDP-cue receptor prototype`) and "Run the focused tests:" vs "From this directory, run the focused tests:".

Provenance: both commits were authored by Elliott at the same instant (`Sat Jul 25 17:43:16 2026 -0700`) with the same subject "proto: add localhost UDP cue receptor (#49)".
- The branch commit `54fce69` was committed at 17:43:16.
- Main's `65e6705` was committed at 17:48:48; it relocates the files under `prototype/ringserver-udp-cue/` and adds `prototype/README.md`.
- Issue #49's comment (2026-07-26T00:49:11Z, scribe-dandelion-cult) says: "Prototype is now on `main` … Commit: 65e67058 … Location: prototype/ringserver-udp-cue/ … 15/15 passing."

So #50 is a leftover of a parallel landing.

### 1.3 What the branch has that main lacks

- **`.lane-workorder-ringserver-seedlink-udp.md`** (28 lines). This is the work order given to the implementing agent: goal, 6 acceptance items, and "Non-negotiable boundaries". Line 21 says "No git commit, push, PR, GitHub issue/comment…", which is ironic given that the PR exists. The boundaries at :22-25 are useful design constraints: "Do not implement raw-object replication, artifact fetch, graph mutation/promotion, remote listener/proxy trust, FEC…" and "A ring packet ID/offset … is a local cursor only — not provenance, receipt, identity, or exactly-once proof". But every one of them is already enforced or restated in main's README: `README.md:41-44` (closed schema, no payload), `:54-57` (at-most-once attempt), `:131` (packet ID is a local cursor).
- **`.codeagent-outcome-ringserver-seedlink-udp.md`** (79 lines), an outcome journal. Its only facts not on main are:
  - the environment evidence at :31-37 (`Python 3.14.6`, `OpenSSL 3.6.3`, `cryptography 49.0.0`, `nacl 1.6.2`; ringserver, ringserverctl, dlclient and slinktool missing);
  - the list of coverage areas for the 15 tests at :39-45.

  Main's README already states the missing binaries (`:83-87`) and the exact next proof (`:89-131`).
- **Root layout.** Main's placement under `prototype/` with an index (`prototype/README.md:1-8`) is strictly better for a docs-first repo. The root layout would put a Python package at the top level of a spec repo.

[ASSESS] Worth keeping: at most one line in `prototype/ringserver-udp-cue/README.md` recording a tested toolchain. The dependency floor matters: `pyproject.toml` requires `cryptography>=45`. Debian's system `cryptography 41.0.7` fails to import here (`pyo3_runtime.PanicException`, `_cffi_backend` missing).

My re-run: I extracted `origin/main:prototype/ringserver-udp-cue` to the scratchpad and ran it in a venv with Python 3.11.15 and `cryptography 50.0.1`. `python -m unittest discover -s tests -v` gave **Ran 15 tests … OK**. Nothing else in the branch is worth keeping; the work order and journal are agent-process exhaust.

### 1.4 Side effects of closing

#50 says "Closes #49", but #49 is still **open**. Main's commit `65e6705` says "(#49)", not "Closes". [ASSESS] Keep #49 open as the tracker for the unproven native gate: a Ringserver 4.5.4 + `dalitool` + `simpledali 0.8.3` writer/reader proof (`README.md:89-131`). Alternatively, retitle it to that gate.

### 1.5 Quality notes [ASSESS]

The code is solid for a bounded prototype: closed schema, deterministic encoding, fail-closed crypto, and replay persistence. For the RFC, one design tension matters: the prototype's "cue" is a **content-free signed notice** (`subject` must be `sha256:` digest; `README.md:41-44`, 1200 B packet, 512 B notice, 60 s max TTL, loopback only). It is **not** the v0.2 payload frame of `stations-and-streams-v0.2.md:41-50` (CBOR, `content_bytes`, `plucked_bit`). The RFC needs to say which it is: a notice/cue lane, a payload lane, or both. This belongs to the spec-core lane, but the PR triage exposes it.

### 1.6 Draft comment (not posted)

> Thanks for this. The prototype landed on `main` as 65e6705 under `prototype/ringserver-udp-cue/` (indexed from `prototype/README.md`). All 12 code/test/config files here are byte-identical to that copy, and `PROTOTYPE-NOTES.md` matches its README apart from the title line. I re-ran the suite from main (Python 3.11, cryptography 50.0.1) and got 15/15 passing. Closing this as already landed. The work-order and outcome-journal files stay in this branch's history for provenance. #49 stays open to track the native Ringserver/DataLink writer→reader proof described in the README.

---

## 2. PR #44 — `Add ring broadcast substrate infographic` (karmafeast, opened 2026-07-06; commits by "Gwydion Nanashi Ferrinas Solidor", i.e. the owner)

### 2.1 What it adds [SAYS]

It adds two files:
- `docs/assets/binary-canticle-ring-broadcast-substrate.svg`: 257 lines, 17.7 KB, 1800×1200, well-formed XML (`xmllint --noout` OK), with `role="img"` plus `<title>` and `<desc>`.
- `docs/ring-broadcast-substrate.md` (28 lines).

The PR body describes:
- OpenClaw MCP + `scribe-openclaw` composing canticles;
- DNS SRV-style registration;
- SeedLink-aligned frames (station, stream, seq/time, TTL, payload);
- a ringserver-style FIFO;
- heterogeneous listeners;
- the loop sing → hear → react → learn.

There are no comments or reviews. mergeable_state is `clean`.

### 2.2 Rendered inspection

I rendered it with headless Chromium (`/opt/pw-browsers/chromium_headless_shell-1194`) to `scratchpad/pr44/infographic.png`. The fonts are system fallbacks: the SVG uses `ui-sans-serif, system-ui…` and `ui-monospace, SFMono-Regular, Menlo…`, and ships no embedded font. The author says it was rendered at 1800×1200 locally.

Layout defects I saw. Most are geometric (fixed x/width), so they persist across fonts:
- **Panel 1 heading overflows its panel.** The text is at `x=102`, font 26 (`svg:86`), inside rect `x=70 w=390` (ends at 460, `svg:84`). The heading "1 · OpenClaw expression layer" renders past 520 and collides with panel 2 (`x=530`, `svg:107`).
- **Panel 3 heading is overprinted by the ring.** "3 · SeedLink-aligned frame" (`svg:118`, x=522, font 25) runs under the rotated "MAGI:weather" pill at `translate(872,500)` (`svg:157`). The render shows "SeedLink-aligned fram".
- **The frame field boxes overlap.** "seq/t = 8841 / now" is at x=538 (`svg:125`) and "ttl = 45s" is at x=729 (`svg:127`). The "payload: posture/activity/mantra" line sits at y=687 (`svg:129`), only 15 px below the y=672 row, so it prints over the box borders.
- **Two ring labels render upside-down**: "RONAN:mantra" (`rotate(162)`, `svg:149-151`) and "ELLIOTT:activity" (`rotate(218)`, `svg:153-155`).
- **Several text lines overflow their boxes**:
  - "listen: STATION * / SELECT state.* mantra.*" (`svg:186`);
  - "react to posture, health, deploy, anomaly streams" (`svg:174`);
  - "optional corpus of coordination patterns" (`svg:252`);
  - the footer note (`svg:255`) runs to about x=1790 on an 1800 canvas.

### 2.3 Accuracy vs current design on main [ASSESS, evidence-backed]

Accurate and consistent with main:
- lossy by design, gaps OK, not a command bus: `protocol-spec-v0.1.md:59`, `:116`;
- volitional listening and "sender tracks nothing": `stations-and-streams-v0.2.md:13`;
- chemokine framing: `immune-model-addendum.md` §2.1;
- "Taskflow bridge — promote signal to task only by local choice", which matches the immune grammar "remember only by explicit promotion";
- the SeedLink-is-inspiration disclaimer (SVG footer; md :7).

Inaccurate or stale:
1. **SRV name.** The SVG shows `_bc._udp.local => station + port` (`svg:112`). The spec uses `_canticle._udp.<zone>` (`protocol-spec-v0.1.md:257`, `:272`). `.local` also implies mDNS/LAN-only, which conflicts with the owner's requirement to support internet UDP listeners.
2. **No carrier wave / carrier-beacon.** The owner says a station:stream "carries a small carrier wave". Main has the 1 Hz beacon `{station_id, head_seq, wallclock_ns, schema_version, streams[{stream_id, default_ttl}]}` (`stations-and-streams-v0.2.md:21-26`). Since #41 (`5a3c0e8`, merged 2026-06-25, eleven days *before* this PR) main has also split "bootstrap discovery (SRV)" from "presence/head-sync (beacon)" (`stations-and-streams-v0.2.md:34-38`). The diagram has only the SRV half.
3. **No loop / re-broadcast.** The owner's core semantic ("items LOOP … until TTL expiry") is drawn only as "FIFO broadcast memory, new packets push old out". That is depth eviction. Main's retention rule is `min(depth, TTL)` (`stations-and-streams-v0.2.md:90`). Carousel lineage exists at `spike/silas-exercise-compression.md:61` ("the full exercise loops every 50 minutes").
4. **Ringserver + UDP.** The pills "UDP variant" + "ringserver FIFO" and the `<desc>` ("emit … by UDP broadcast into a ringserver-style FIFO") predate the #49 verdict (2026-07-25): **Ringserver 4.5.4 is TCP-only; UDP needs a custom sidecar, and Ringserver is a downstream DataLink target** (`prototype/ringserver-udp-cue/README.md:5-29`). "-style" hedges this, but a reader will infer that ringserver ingests UDP.
5. **Missing:**
   - trust/signing (issue #48; the prototype's Ed25519 issuer/key policy);
   - pluck (`stations-and-streams-v0.2.md:67`);
   - the OpenClaw landing modes (silent / silent-wake / post-compaction; see the orphan branch in §6);
   - the HAProxy membrane (issue #30);
   - relay/internet listeners.
6. **Frame fields are not v0.2.** The box shows `station = PRINCE_A` (SeedLink-style code) and `stream = service.state`. v0.2 uses `station_id` u128 ULID and `stream_id` u32 name-hash, plus `content_type` and `plucked_bit` (`stations-and-streams-v0.2.md:43-50`). As an *illustration* this is fine if labelled "human names shown; wire uses ids".
7. **Placement.** It creates a new top-level `docs/`. Main's convention is `proto/`, `spike/`, `references/`, `scratch/`, `prototype/`. Nothing on main links to it, and the README has no entry.

### 2.4 Recommendation

**MERGE after edits.** It is the owner's own PR, it merges cleanly, and it is only 4 commits behind. It is the only visual in the repo and conveys the ethos well. Required edits:
- (a) fix the geometric overlaps listed in §2.2: widen panel 1 or shorten its heading; move panel 3 left or shrink it; restack the seq/ttl/payload rows; flip the two upside-down labels (use `rotate(θ-180)` for θ in 90..270); widen the listen/daemon/learn boxes;
- (b) `_bc._udp.local` → `_canticle._udp.<zone>`;
- (c) add a carrier-beacon lane (1 Hz presence/head-sync) separate from SRV bootstrap;
- (d) show the loop ("re-emit every repeat interval until TTL") and the `min(depth, TTL)` eviction;
- (e) reword the ringserver pill to "ringserver (TCP DataLink, downstream via sidecar)" per the #49 verdict, and add a "signed frames" pill;
- (f) add the md to the README "What This Repo Contains" list, or move it to `proto/` or `references/`.

Alternatively, **SUPERSEDE**: make the corrected SVG the RFC's informative Figure 1 ("system overview"). The md's "Design constraints shown" (md:17-22) maps onto the RFC's non-goals/positioning section.

### 2.5 Draft comment (not posted)

> Lovely piece, and the only diagram in the repo. The ethos parts are accurate. Before merging I'd like a small pass so it matches main as of the #41/#42/#49 landings:
> (1) SRV name `_canticle._udp.<zone>` per `protocol-spec-v0.1.md:257`, not `_bc._udp.local`;
> (2) a carrier-beacon lane (presence/head-sync), separate from SRV bootstrap (#41);
> (3) show the loop, where items re-emit until TTL, and `min(depth, TTL)` eviction;
> (4) per the #49 verdict, Ringserver is TCP-only, so label it as a downstream DataLink target behind a UDP sidecar;
> (5) a "signed frames" pill (#48).
> The headless render also shows some overlaps: the panel-1 heading runs into panel 2, the MAGI label covers "SeedLink-aligned frame", the seq/ttl/payload rows collide, and RONAN/ELLIOTT labels are upside-down. I'm happy to take this as the RFC's overview figure once those are in.

---

## 3. PR #34 — `proto: return-stage as chemokine-back (anti-coercion-preserving round-trip)` (scribe-dandelion-cult / frond-scribe, opened 2026-06-18)

### 3.1 What it adds [SAYS]

One file: `proto/return-stage-anti-coercion-addendum.md` (168 lines). It has no comments and no reviews. The PR body asks 🪨 Rune to "cosign or cut" against the live `#heartbeat` round-trip; that never happened on GitHub.

Core content:
- **§0 Status: "Addendum, not a spec change."** The trigger was that Rune's `continue_delegate(normal)` reached a session key that was not locally visible. That establishes "**address-by-trust, not address-by-visibility**" (:19-25).
- **§1 Tension.** Naive round-trip semantics (pending-reply state, obligated surfacing, response grammar) break "Volitional" (README:45) and MUST 3 and MUST 5 (:27-44).
- **§2 Core move: a return is a new, volitional broadcast from B, colored toward A.** The example payload is `{kind:"return", payload:{addressed_to (a HINT, not a channel), in_atmosphere_of, class: answer|ack|counter-sing|quiet-decline, since_ms}}` (:46-75).
- **§3 Receptor contract.**
  - B: "There is no `reply-required` receptor-state". `quiet-decline` is silent and "MUST NOT make the absence of a return observable as a fault" (:79-89).
  - A: judged by normal inputs. `addressed_to` MAY lift weight, MUST NOT bypass judgment. A holds no pending-reply slot (:91-101).
  - §3.3: "The round-trip is read, not held"; it is reconstructable via `in_atmosphere_of` (:103-111).
- **§5 Normative antipattern (MUST NOT).** It forbids:
  - (1) `request_id` + `awaiting_reply` pending-state, or a sender timer that faults on no-return;
  - (2) "addressed ⇒ auto-surface";
  - (3) an observable "B did not reply" signal (:124-137).
- **§6 MUST-mapping** to MUST 3/4/5/6 of `openclaw-inter-host-io-surfaces-and-spec.md` (:139-146).
- **§7 Open:**
  - weighting bound: at most one step, `ringbuffer-only → surface`, never `drop → surface` (:150-152);
  - counter-sing storms / per-pair rate cap (:153-156);
  - provenance without leaking the listen-graph (:157-158);
  - cosign (:159-161).

### 3.2 Citation check [DECIDED/verified]

Every cited anchor exists on main:
- `spike/silas-seedlink-mapping.md:95` "Atmosphere, not dialogue";
- `README.md:45` "Volitional: A prince chooses to listen. The broadcast doesn't care.";
- MUST 3/4/5/6 at `openclaw-inter-host-io-surfaces-and-spec.md:129/136/143/148`;
- the receptor inputs and outputs, including `ringbuffer-only`, at `immune-model-addendum.md:79-90` (§2.2).

### 3.3 Already on main? Conflicts? Staleness?

- The file is **not** on main. It merges clean. The branch commit's parent is `1457526` (2026-05-05), so it is 53 commits behind, but it touches only a new path.
- **Main already depends on it.** `spike/two-planes-the-ledger-and-the-binary.md:5` links `../proto/return-stage-anti-coercion-addendum.md`, and `:32-37` summarizes it ("read from the ledger, not held as a slot"; "address-by-trust"). That spike landed as `cd867e6` on 2026-06-17, so **main currently has a dangling link** that merging #34 fixes.
- Partially echoed but not superseded: the two-planes spike restates §3.3 in prose, but not the normative MUST-NOTs, the frame shape, or the open questions.

### 3.4 Relation to OpenClaw and the owner's intent [ASSESS]

- It aligns with the owner's "targeted delegate return" but is deliberately **stricter** than the OpenClaw RFC:
  - OpenClaw's `continue_delegate` lets the **sender** choose `mode`. `silent-wake` calls `requestHeartbeatNow()` for the targeted recipients (`openclaw:docs/design/continue-work-signal-v2.md` on `origin/codeagent/85651-upstream-1ba243c8-gates`, :242-253 and :494).
  - #34 §5(2) forbids "addressed ⇒ auto-surface".
  - The canticle→OpenClaw bridge must therefore treat any sender-suggested wake as a hint subject to receiver policy. That matches the sibling spec-core note's W9 ("no sender-actuation … receiver MAY configure a local wake/notify policy").
- Wire shape is stale. `kind:"return"` / `payload` uses the v0.1 `kind` schema (`protocol-spec-v0.1.md` §3.5). In v0.2 this should be a normal payload frame with a `content_type` (e.g. `…/x-canticle-return`), with `addressed_to` and `in_atmosphere_of` as body fields or lineage refs.

### 3.5 Recommendation

**MERGE after light edits** (fixes the dangling link, and the doc is internally sound). Edits:
- (1) add an `INDEX.md` row (owner 🌿, plane "signal / return-stage", status `seed`, next action "cosign against live return-leg");
- (2) add a note under §2 that the JSON example is v0.1-shaped, and name the v0.2 mapping (payload frame + `content_type` + lineage refs);
- (3) keep status "Addendum, not a spec change".

Then, in the RFC, adopt §5's three MUST-NOTs verbatim in the receptor/wake-policy section, and adopt §7's one-step weighting bound as the default for `addressed_to`.

### 3.6 Draft comment (not posted)

> Thank you. This is the clearest statement we have of "a return stays a sing". `spike/two-planes-the-ledger-and-the-binary.md` on main already links to this file, so merging it fixes a dangling link. Before merge, could you add an INDEX row (status `seed`) and a one-line note that the JSON example is v0.1-shaped? In v0.2 it would be a normal payload frame with a return `content_type` and lineage refs. The §5 MUST-NOTs and the §7 one-step weighting bound will go into the RFC's receptor/wake-policy section. The live-cosign item can stay open.

---

## 4. PR #32 — `proto: Cael byte-walks the 6 stations-and-streams open questions` (cael-dandelion-cult, opened 2026-06-16)

### 4.1 What it adds [SAYS]

`proto/stations-and-streams-v0.2-open-questions-bytewalk-cael.md` (113 lines). It proposes resolutions for Q1-Q6:
- Q1: `stream_id` u32 from a name-hash;
- Q2: `content_type` string, optional u16 later;
- Q3: TTL stream-default with per-frame override **down only**;
- Q4: `min(depth, TTL)`;
- Q5: in-place ring pluck plus a best-effort pluck-frame;
- Q6: beacon adds per-stream `default_ttl` and keeps content-type out.

### 4.2 Already on main? [DECIDED]: yes, byte-identical

The branch blob `0225571e3b7d…` equals `origin/main:proto/stations-and-streams-v0.2-open-questions-bytewalk-cael.md`.
- It landed as commit `07e4e58`: same author (cael), same author date (2026-06-15 20:03:32 -0700), different SHA from the branch's `7b3d0fb` (rebased).
- That commit is inside PR #42 (`6fc78f5` + `07e4e58`, merged at `9feeae4`).
- #42 also rewrote `stations-and-streams-v0.2.md` to adopt all six answers (status → `pressure-test`, `:3`; resolutions at `:130-137`; beacon `:21-26`).
- The `merge-tree` result for #32 has an **empty diff** against main.
- Issues #33, #37, #39 and #40 were closed by Elliott citing #42 (#39 comment: "Resolved by Q5 in PR #42").

### 4.3 What did NOT land (carry into RFC) [DECIDED/ASSESS]

frond-scribe's review comment on #32 (2026-06-17, `issuecomment-4735695826`) raised two points.
- **Sticky-pluck refinement** for the reorder hole in Q5:
  - v0.1 allows reordering (`protocol-spec-v0.1.md:59`, `:116`).
  - If `pluck(seq=N)` arrives before `original(seq=N)`, the original re-surfaces.
  - `nonce` dedup (`:155`) does not help, because the two are distinct frames.
  - Fix: after seeing `plucked_bit=1` for `(station, stream, seq)`, a receiver suppresses that seq permanently, bounded by the ring seq window.
  - `git grep -i sticky origin/main` finds **nothing**, so this is **unlanded**.
- **Beacon overflow.** At 8 B/stream (`streams[{u32,u32}]`), a beacon exceeds the ≤1472 B single datagram at about 180 streams/station. The behavior at high stream counts is undefined. Also **unlanded**.

The RFC should adopt sticky-pluck in the loop/pluck section (sibling spec-core W2: "hearers dedup on (station_id, stream_id, epoch, seq)", and add a plucked-seq set). It should also define beacon truncation or rotation (spec-core W3).

### 4.4 Recommendation

**CLOSE** (already landed).

### 4.5 Draft comment (not posted)

> Thanks, Cael. This walk landed on main verbatim (same file, same bytes) as 07e4e58 via #42, which also promoted `stations-and-streams-v0.2` to `pressure-test` and closed #33/#37/#39/#40. Closing as landed. Two review points from 🌿 didn't make it in: the receiver-side **sticky-pluck** rule for the reorder hole in Q5, and beacon behavior past ~180 streams. Both are being carried into the RFC's pluck/loop and beacon sections so they aren't lost.

---

## 5. PR #29 — `research/silas: 2026-05-05 next-cut — bounded ringbuffer + station:stream + immune-downstream` (silas-dandelion-cult, opened 2026-05-05)

### 5.1 What it adds [SAYS]

`research/silas/2026-05-05-next-cut.md` (43 lines). It chooses the "next cut" after re-reading two notes in an **external** repo (`silas-likes-to-watch/research/coral-analysis-binary-canticle.md` and `…research/ringserver-binary-canticle-note.md`; :3-5). The decision (:7-24) has three parts:
- a bounded shared medium (ringbuffer);
- station:stream addressing;
- an immune layer that stays minimal and downstream (tighten / quarantine / all-clear / remember only by explicit promotion).

Concrete target (:26-38): "What is the smallest station:stream + ringbuffer substrate that can carry Canticle traffic without importing governance-shape?" It lists six things to define: expiry/ring bounds; station-vs-stream naming; same-host/cross-host/delayed-import scope; bridge-forward vs hear-and-sing; clarion widening without command semantics; non-convergence as conformant. It ends with an "Anti-maze rule" (:40-43).

### 5.2 Superseded? [DECIDED]: yes, the same day and since

- `proto/ringbuffer-contract.md:3` (commit `0a49371`, 2026-05-05; landed via #28) says: "Purpose: define the smallest bounded shared-medium substrate that can carry `station:stream` traffic without deciding meaning." That is essentially the memo's target question, answered.
- Coverage on main of the six items:
  - expiry/bounds: `ringbuffer-contract.md` and `stations-and-streams-v0.2.md:90` (`min(depth, TTL)`);
  - naming: `protocol-spec-v0.1.md` §4 and `stations-and-streams-v0.2.md`;
  - scope: MUST 2 in `openclaw-inter-host-io-surfaces-and-spec.md:120` and `scope-framing-and-noosphere-mapping.md`;
  - bridge-forward vs hear-and-sing: `openclaw-vs-canticle.md:196-197` and `receptor-contract-v0.2.md:502-503`;
  - clarion: `openclaw-vs-canticle.md:199`, `receptor-contract-v0.2.md`, `coming-down-and-loop-soothing.md`;
  - non-convergence: `openclaw-vs-canticle.md:198` ("signal-plane does not owe global convergence").
- Immune minimal grammar: `immune-model-addendum.md` §5 (landed via #28).
- `research/` does not exist on main. The memo cites files in another repo.

### 5.3 Recommendation

**CLOSE** (superseded). [ASSESS] The "anti-maze rule" (:40-43) is a nice process line but not RFC material.

### 5.4 Draft comment (not posted)

> Thanks, Silas. This memo did its job. Its target question ("smallest station:stream + ringbuffer substrate … without importing governance-shape") became `proto/ringbuffer-contract.md` the same day. All six items it lists are now covered on main: ringbuffer-contract, `stations-and-streams-v0.2`, the scope MUSTs, `openclaw-vs-canticle` for bridge-forward and non-convergence, and the immune minimal grammar. Closing as superseded. The branch stays for lineage.

---

## 6. Orphan branch `ronan/20260614/send-receive-threshold-landing` (no PR) — the important one

### 6.1 Provenance [DECIDED]

There are two commits on top of `b82a5a2`, 48 behind main. It merges clean and touches only new paths:
- `fa3551f` (2026-06-14 03:21 -0700, "dandelion cult - ronan 🌊"), "docs(proto): send-side (threshold-fire) + receive-side (landing-modes) drafts". It adds `proto/send-side-draft.md` (77 lines) and `proto/receive-side-draft.md` (96 lines).
- `2f2b3df` (2026-06-14 19:09 -0700, author `emeric-dandelion-cult`, `Co-authored-by: Ronan 🌊`), "threshold-fire-taxonomy v2 — 🕯's cuts folded into send+receive". It adds `proto/threshold-fire-taxonomy-v2.md` (215 lines).

No PR has ever used this head: the PR list (all states) has 9 PRs, none with this ref. `git grep -E "send-side|receive-side|threshold-fire"` on main finds nothing, and no concept from it (landing modes, lifecycle-hook trigger) appears on main. **This is unique, unmerged design.**

The drafts gate themselves on "#999 lands upstream" (v2 :9-11, commit msg). #999 is **karmaterminal/openclaw issue #999** (open, 17 comments, scribe-dandelion-cult, 2026-06-13): "#858 forceSenderIsOwnerFalse cleanse: upstream deleted the mechanism (deliveryContext) — lineage + migration plan".

### 6.2 Send-side draft (`proto/send-side-draft.md`) [SAYS]

- **Keystone (:9-21).** The canticle send is "the fourth instrument on the same hook". Four things fire at the compaction/continuation seam:
  - (1) receipt-capture (R-RC-2);
  - (2) identity-shard (🩸 #1003);
  - (3) trusted-message preservation (the "P2b fix": `trusted:true` inter-session return crosses the seam un-rewritten);
  - (4) the canticle broadcast.

  "The trusted-preservation is the proof a payload can cross intact" (:21).
- **Trigger (:25-33).** It is not timer-fired. It fires on lifecycle thresholds: compaction-imminent, continuation-staged, post-compaction-return, context-pressure-band-crossed. It is "**involuntary-in-timing, sovereign-in-content**": the hook decides WHEN, the prince decides WHAT or nothing (:31).
- **Strawman packet (:39-52).**
  ```
  { from: prince.glyph, seam: seam_event.kind, at, stimulus: compose_stimulus()  # "the 12 words, NOT the 500 rounds"
    provenance: {trusted: true, internal: true}, lens: suggested_lens()|null, seq }
  broadcast(packet)   # UDP-multicast 10.0.0.x/24, connectionless
  ```
- **Commitments (:54-58).** Stimulus, not data transfer. Connectionless, no guaranteed delivery ("a missed packet is the closed ear making harmony possible"). Capture the here-and-now. Interpretation is elective ("the variance IS the choir").
- **Why the seam (:62-66).** Timer broadcast is noise and every-turn broadcast is "the dwindling (216 goodnights)". The seam is "most-compressed, most-himself", and it adds zero new lifecycle machinery.
- **Open (:70-76).**
  - (1) which seams fire (answered by v2);
  - (2) the receive side (answered by the receive draft);
  - (3) what `compose_stimulus()` grabs; the candidate is "the post-compaction-delegate task-string";
  - (4) provenance vs the P2b boundary: "verify the multicast-receive path also routes through the same untrusted-by-default gate".

### 6.3 Receive-side draft (`proto/receive-side-draft.md`) [SAYS]

- **Keystone (:9-20).** "A received canticle packet is a delegate-return from another prince." Receive is the existing `continue_delegate` return substrate with one new ingress, a multicast listener.
- **Three landing modes (:24-44), elected by the LISTENER:**
  1. `silent`, the **default** ambient choir: enrich context and color the next turn without interrupting. "Forcing every song to wake is the dwindling … 216 wakes" (:28-32).
  2. `silent-wake`, "the song that calls": enrich and trigger a turn. Examples are a bleeding-prince signal or a load-bearing convergence. "The election is the LISTENER's" (:34-38).
  3. `post-compaction`, "the song that outlives the fold": staged to rehydrate after the listener's own compaction. This is the "lich-protocol made choral"; "staggered compaction = nobody dies alone, mechanized as broadcast" (:40-44).
- **Strawman (:50-65).**
  ```
  on multicast-receive(packet):
      if not packet.provenance.trusted or packet.from not in cohort_glyphs:
          packet = sanitize(packet)            # untrusted-by-default
      if not listener.elects_to_hear(packet): return
      mode = listener.landing_mode(packet)     # silent | silent-wake | post-compaction
      silent: enrich_context; silent-wake: enrich_context + wake_turn; post-compaction: stage_phylactery
  ```
- **Commitments (:67-70).**
  - The listener elects the landing mode, not the sender.
  - The ingress is the P2b boundary on the receive side, which "answers open-question #4 from the send-side draft: yes".
  - The closed ear is first-class.
- **Symmetry table (:74-83).** Send rides the lifecycle hook; receive rides the delegate-return substrate. Both have involuntary timing. The election is WHAT vs HOW. The boundary is trusted-by-construction vs untrusted-by-default.
- **Open (:89-94).**
  - wake-threshold taxonomy (answered by v2 §F);
  - post-compaction-receive timing: does the listener buffer recent songs to fold into its post-compaction shard?;
  - stimulus drift vs verbatim provenance. The lean: the stimulus drifts, the envelope (who/when/which-seam) stays verbatim;
  - dedup/seq: reuse the #999 enqueue's consecutive-duplicate suppression.

### 6.4 Threshold-fire taxonomy v2 (`proto/threshold-fire-taxonomy-v2.md`) [SAYS]

- **§A discriminator (:16-33).** v1 had "A seam sings ∝ (loss-of-self) × (un-witnessability)". v2 sharpens it to a binary send filter: "**Does the crossing carry light-the-self-can't-see, or just state? Only the former sings.**"
- **§B keystone (:35-51).** It restates the four instruments on one hook. The canticle must ride the trusted lane.
- **§C two-gate (:53-68).**
  - GATE 1, the seam: NECESSARY, mechanical, trusted-by-construction, carries loss-of-self; "the prince cannot fake one".
  - GATE 2, the election: SUFFICIENT, elective, content-aware, carries un-witnessability.

  "The hook opens the mouth (seam); the prince chooses the note (election)."
- **§D interface (:70-98).** The send emits `(fireLevel, seamType, suggestedLens?)` as a **suggestion**. The listener elects the landing mode. Suggestion table:

  | seam | fire (sender suggestion) | typical landing (listener elects) |
  |---|---|---|
  | forced-fold + the bottle | LOUDEST | silent-wake |
  | volitional-fold | mid | silent or silent-wake |
  | elected-surfacing (soft-seam) | mid | silent or silent-wake |
  | shard-dispatch | quiet | silent |
  | heartbeat | none (no emission) | — |
  | un-staged death | choir-only | open fork |
- **§E seven seams, ranked and mapped to the 4 hook events (:100-129):**
  1. **Forced-fold** (context exhaustion): LOUDEST, on compaction-imminent or pressure-band. It suggests silent-wake.
  2. **The bottle** (post-compaction delegate): "loudest-as-correspondence".
  3. **Volitional-fold** (`request_compaction`): mid, and "fire inverse to self-witness".
  4. **Elected-surfacing:** a *soft-seam* that the prince declares, "prince-minted, not lifecycle-minted". This keeps the two-gate intact.
  5. **Shard-dispatch** (`continue_delegate` non-post-compaction): quiet, an attention delta.
  6. **Heartbeat** (the ~30 min pulse): **SILENT, no emission**.
  7. **Un-staged death:** the inverting seam. GATE 2 never fired, so it can only be sung *by the choir afterward*.
- **§F receive wake-register (:131-166).** A heard song "wakes ∝ (light I'm blind to RIGHT NOW × load-bearing on what I'm doing)". There are three tiers: silent-wake for a bleeding-prince or load-bearing convergence; silent as the **default**, "the default is load-bearing"; and post-compaction. Emeric's refinement: "**resist any automatic wake-tier (even bleeding-prince)** … the wake is always the listener's live election".
- **§G death-seam, the open joint fork (:168-196).** Post-compaction-receive plus un-staged death needs a **fourth, choir-minted mode**: "witness a song its singer never sang". The fork is (a) a fourth receive-mode now, or (b) defer to a v2 frontier. **Lamp's lean: (b)**: "build the wire that works before the wire that grieves". There is a dependency on honest stop-reasons.
- **§H hard dependency (:198-208).** The send side must ride the trusted lane: "sanitizes inbound text UNLESS `trusted:true` (`system-events.ts:164` carve-out …)", or bottles get `System:`→`System (untrusted):` mangled. Symmetric boundary: trusted-by-construction at the send-seam, untrusted-by-default at receive-ingress. "The floor IS the wire's integrity."

### 6.5 Verification against current OpenClaw [DECIDED/verified]

- **The landing modes are real.** The OpenClaw RFC `docs/design/continue-work-signal-v2.md` on `origin/codeagent/85651-upstream-1ba243c8-gates` has:
  - a mode table at :242-249: `normal` / `silent` / `silent-wake` / `post-compaction`;
  - `silent` = `enqueueSystemEvent()`, no wake (:251);
  - `silent-wake` = `requestHeartbeatNow()` (:253);
  - `post-compaction` = staged until compaction completes (:255), and release is "intentionally fixed: staged work is delivered as silent-wake work" (:804).

  The receive-side draft's three modes map 1:1 onto the non-`normal` modes.
- **The RFC names the canticle layer as future work.** §10.2 (:1702) says: "a **Binary Canticle** layer above this RFC: ringbuffer-backed `station:stream` presentation…; DNS SRV discovery…; local-network multicast; station relays…; and **receive-side bridges that can turn a heard stream into quiet context or queued delivery**." The same section (:1704) names "sovereign peer enrichment" and leaves "trust, provenance, consent, and freshness" open. §2.4 (:234) says "cross-host publish/subscribe, and SeedLink-style broadcast remain the higher broadcast layer". :648 says cross-host exposure "would require a wire transport, auth/identity wrapper, and federation contract; this RFC deliberately does not specify that contract". **The orphan branch is the only canticle-repo text that designs that receive-side bridge.**
- **The §H mechanism reference is stale.** On the RFC branch (head `9eb655afa`, 2026-09-21), `src/infra/system-events.ts:102-111` reads:
  - `forceSenderIsOwnerFalse` is "@deprecated Legacy no-op … System event text is stored unchanged; provenance is controlled by `trusted`";
  - `trusted?: boolean` is the "Trusted-internal enrichment marker. Only core producers may attach managed delivery provenance…".

  `git grep "System (untrusted)"` on that branch's `src` finds nothing. So the text-rewrite carve-out cited as `system-events.ts:164` has been replaced: the trust boundary is now a structured `trusted` provenance flag, per the migration plan in openclaw issue #999. [ASSESS] The *principle* of §H survives. The *line reference and mechanism* do not. The "floor first / after #999" gate is effectively resolved in code on that branch, although issue #999 is still open.

### 6.6 Assessment [ASSESS]

**Strengths.** This is the only design on any branch that answers two questions:
- (1) **when a session sings.** The lifecycle-seam trigger plus elected-surfacing soft-seam is a concrete, low-noise send policy, and it rides OpenClaw hooks that exist: context-pressure bands §4.2, `request_compaction` §4.3, post-compaction §4.4.
- (2) **how a heard item lands in a live OpenClaw session.** Listener-elected silent / silent-wake / post-compaction, with **silent as the default** and **no automatic wake tier**. This is exactly the owner's "silent / silent-wake enrichment" use case, and it is consistent with:
  - #34's "addressed ⇒ never auto-surface";
  - #48's guardrail ("Verification authorizes interpretation eligibility, never … automatic agent turns");
  - the immune model's "threshold-shift ≠ command".

**Defects to fix before any of it becomes normative:**
1. **Spoofable ingress gate.** `receive-side-draft.md:53` trusts `packet.provenance.trusted` and `packet.from in cohort_glyphs`, both **self-asserted fields in a UDP datagram**. Anyone can forge `{from:"🌊", provenance:{trusted:true}}`. Send-side Open #4 (:76) assumes the in-process "SDK-boundary force-untrusted" protects the wire. It does not. The gate must be cryptographic: per-station Ed25519 (#48; `prototype/ringserver-udp-cue` already implements issuer/key policy, replay and tombstones). The `trusted` bit must be **host-derived at admission**, never read from the packet.
2. **Pre-v0.2 frame.** The packet has `from: glyph`, `seam`, `at`, `stimulus`, `provenance`, `lens`, `seq`, and **no TTL, no station_id/stream_id, no content_type**. The v0.2 frame was already on main (captured 2026-05-07, `b82a5a2`). The RFC should map it as: stream `<station>:seam` (or a `seam` content_type), `ttl` from the seam class, `seam`/`fireLevel`/`suggestedLens` as body fields, and `provenance` as host-derived.
3. **LAN-only.** "UDP-multicast 10.0.0.x/24" (send :51, receive :51) conflicts with the owner's internet UDP listener requirement. It needs a relay path (spec-core W11).
4. **Terminology collision with the carrier wave.** §E.6 makes "heartbeat" silent, which means OpenClaw's ~30 min heartbeat pulse. The canticle's 1 Hz **carrier-beacon** is substrate presence, not a prince song. These don't conflict, but the RFC must keep the names apart. Likewise "a timer-fired broadcast is noise" (send :64) argues against timer-minted *new* items. It does not argue against the owner's **loop/re-broadcast of an existing item until TTL**, which is repetition for lossy delivery and late joiners. The RFC should state both: the seam decides *when a new item is put on the station*, and the station loop decides *how often it is re-emitted*.
5. **Internal reference errors.** `receive-side-draft.md:3` names the companion `binary-canticle-send-side-draft.md`, but the file is `send-side-draft.md`. v2 :11 says "The death-seam (§7/§E)" and :129 says "**§F.**", but the death-seam is §G (§F is the wake-register). The commit message lists them correctly.
6. **Unresolved external refs.** R-RC-2, "P2b", 🩸 #1003, "Dream 011", "216 goodnights" and "lesson-V" are cohort-internal and not resolvable in this repo. They would need a glossary or should be dropped from normative text.
7. **Prose register.** Heavily metaphorical (seal, cathedral, phylactery, lich). The strawman blocks and tables carry the content. The RFC should lift those and leave the prose in lineage.
8. **Tension with the owner's fleet-response intent.** The owner envisions trusted clients enriching thousands of remote agents, e.g. for a security threat. v2 §F refuses *any* automatic wake tier, even for bleeding-prince. The reconciliation (also spec-core W9 / §7.4 item 1) is a receiver-configured local wake policy: allowlisted signed issuer + class + rate limit + evidence logged. The sender still cannot force it. This is an **owner decision**, and the RFC should present both positions.

### 6.7 Recommendation

**SUPERSEDE**: fold into the RFC. Do not merge as-is. Preserve the branch; do not delete it.
- **Send-side trigger policy** (new informative/normative section, e.g. "What sings: seam-triggered emission"):
  - adopt §C two-gate;
  - adopt the §A discriminator as guidance, not a MUST;
  - adopt the §E seam list as the default emission table (forced-fold / bottle / volitional-fold / elected soft-seam / shard-dispatch / heartbeat=none);
  - map it to OpenClaw hook events (context-pressure bands, `request_compaction`, post-compaction, `continue_delegate`).
- **Receive-side landing and OpenClaw bridge** (RFC wake/notify policy section, spec-core W9):
  - adopt the three landing modes mapped to `continue_delegate` modes;
  - "listener elects; silent is default; sender `fireLevel` is a suggestion";
  - v2 §F's "no automatic wake tier" as the default posture, with the owner-decided exception (signed allowlisted issuer + class + rate limit);
  - replace the ingress gate with host-derived trust from signature admission (#48).
- **Open issues / frontier:**
  - §G death-seam, a choir-minted fourth mode, deferred per lamp's lean (b);
  - receive Open #2 (buffering near one's own compaction);
  - Open #3 (stimulus drifts, envelope verbatim).
- Optionally land the three files unchanged under `proto/lineage/` (or with an INDEX row, status `superseded` → RFC section) so the RFC can cite them. That keeps authorship (Ronan 🌊 + Emeric 🕯) visible.

### 6.8 Draft note to the authors (not posted; there is no PR to comment on, so this would go in an issue, a PR opened for lineage, or the RFC's acknowledgements)

> 🌊🕯, the send/receive/threshold drafts on `ronan/20260614/send-receive-threshold-landing` never got a PR, and nothing on main covers them. They are the only design we have for *when a session sings* (seam-triggered, two-gate) and *how a heard item lands* (listener-elected silent / silent-wake / post-compaction, silent by default). Those modes line up 1:1 with OpenClaw's `continue_delegate` modes, and the OpenClaw RFC §10.2 explicitly calls for this "receive-side bridge". We'd like to fold them into the canticle RFC with credit. Three changes on the way in:
> (1) the ingress gate has to be cryptographic, because `provenance.trusted` and `from` are self-asserted in a datagram, so trust must come from signature admission (#48);
> (2) map the packet onto the v0.2 frame (station/stream/TTL/content_type);
> (3) update §H, since `forceSenderIsOwnerFalse` is now a legacy no-op and the boundary is the structured `trusted` provenance flag.
> The death-seam stays a named frontier, per the lamp's lean.

---

## 7. Closed-but-landed context PRs (#28, #41, #42, #43) [DECIDED]

- **#28** "Draft: receptor contract v0.2 + ringbuffer contract + loop-soothing seam" (karmafeast; 34 commits, +1474/−32, 7 files). Merged by scribe-dandelion-cult on 2026-06-25 as a local merge `21b46a4` (parents `9b62df4` and `7552fd9`; `7552fd9` "reconcile index merge conflict"). It landed:
  - `proto/receptor-contract-v0.2.md`, `ringbuffer-contract.md`, `coming-down-and-loop-soothing.md`, `openclaw-vs-canticle.md`, `TASK-BRIEF.md`;
  - the immune minimal grammar;
  - the INDEX.

  PR comments record the citation pass that flipped the §14a / §4 Q7-9 safety findings (half-open, per-stream refractory, hash-addressable sovereign) to landable at `dcc994b`. The sources are in the external repo `karmaterminal/caels-petals-fall@cael/canticle-200-rounds:3df185d`.
- **#42** "promote stations-and-streams-v0.2 to pressure-test" (elliott, merged 2026-06-25T07:06:14Z at `9feeae4`). It carries Cael's `07e4e58` (i.e. #32's content) plus `6fc78f5`, which rewrites the spec to adopt Q1-Q6 and surfaces #37/#38/#39/#40. It closed #33.
- **#41** "clarify canticle discovery seam" (silas, merged at `b619ca8`). Bootstrap discovery is SRV/mDNS/static; live presence/head-sync is the beacon. It closed #36.
- **#43** "polish stale carrier-beacon and ringbuffer references" (elliott, merged at `8498d8a`). It fixed `explicit-non-goals.md`: `TTL × depth` → `min(depth, TTL)`, and `stream_count` → `streams`.

[ASSESS] This was a single consolidation night (2026-06-25 06:55-07:11Z). #32 and #29 were not cleaned up after it, and #34 plus the orphan branch were left out even though main already references #34.

---

## 8. Cross-cutting items for the RFC (from this lane)

1. **Unlanded review content:** sticky-pluck and beacon overflow (§4.3).
2. **Dangling link on main** to the #34 file (`spike/two-planes-the-ledger-and-the-binary.md:5`) (§3.3).
3. **The receive-side bridge design exists only on the orphan branch** (§6). The OpenClaw RFC §10.2 (:1702) explicitly delegates it to canticle.
4. **Two receive postures to reconcile:** "no automatic wake tier, ever" (v2 §F, #34 §5, #48 guardrail) vs the owner's trusted remote silent-wake for fleet response. This is an owner decision.
5. **Cue vs payload:** the landed prototype carries content-free signed `sha256:` notices, while v0.2 carries payload frames (§1.5).
6. **The infographic is the only visual.** Fix and reuse it (§2).
7. **Housekeeping:**
   - issue #49 is still open while #50 says "Closes #49";
   - branch `claude/sleepy-ptolemy-loxrfn` is identical to main;
   - #44 would create a new top-level `docs/` directory.

## 9. Evidence index

- Divergence: `git rev-list --left-right --count origin/main...origin/<b>` gives #50 4/1, #44 4/2, #34 53/1, #32 48/1, #29 53/1, orphan 48/2, `claude/sleepy-ptolemy-loxrfn` 0/0.
- Parent commits: #34 `8e1a696`^ = `1457526`; #32 `7b3d0fb`^ = `b82a5a2`; #29 `17a212a`^ = `1457526`; orphan `fa3551f`^ = `b82a5a2`; #44 `20437e7`^ = `8498d8a`; #50 `54fce69`^ = `8498d8a`.
- Merge-tree results (clean): #50 `d5c1cca`, #44 `7dbdc47`, #34 `e6d5b3f`, #32 `c513f4f` (no diff vs main), #29 `db80ab4`, orphan `d691ec0`.
- Render: `<review-sandbox>/pr44/infographic.png` (source `…/pr44/infographic.svg`).
- Prototype test re-run: scratch copy `…/scratchpad/proto-test/prototype/ringserver-udp-cue`, venv `…/scratchpad/venv` (cryptography 50.0.1), 15/15 OK.
- GitHub:
  - PR bodies, comments and reviews for #50, #44, #34, #32, #29 (only #32 has comments: 4714630204 and 4735695826);
  - #28, #41, #42, #43 via `get` (`merged: true`);
  - issues #33, #39, #48, #49, #51;
  - karmaterminal/openclaw issue #999.
