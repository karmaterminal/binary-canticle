# RFC-0001: claims against code (2026-11-23)

A read-only audit: what [`rfc/0001-binary-canticle.md`](../0001-binary-canticle.md) claims, checked claim by claim against the code. It is step 1 of the RFC revision (map: #172). It edits no RFC text and drafts none. figs asked for an RFC that the frond's capability map can stand on, and a check of its claims against the code; this is that check.

Parts: [1 Summary](#1-summary) · [2 Tables per section](#2-tables-per-rfc-section).

## Refs

| ref | SHA |
|---|---|
| binary-canticle `main` (RFC, station, OpenClaw plugin spike; #171 merged) | `d4c306618f7f77658fe73705d58b2744f2486701` |
| frond-ear `main` (#119 merged) | `a8e2e5ba1b16adf5ce700265f25a0d210c569608` |
| lane | `codeagent/bc-rfc-claims-audit`, published unchanged at `d4c30661` before this file |
| #173 fair admission (open) | `c6e669c2adc94e8c0c7a46d139b7cf2aadfada48` |
| #162 composite (open draft) | `452c54336d05048b3e0e2fd83bafb16d98065891` |
| #168 sense organ (open draft) | `2c3f5ab6b6bdb1ef9c476c10f31b21794c71f0bd` |
| #125 DNS registration (open), where cited | `b93918262c9ed7141e08c4fe3f6c3fc9f3c1476d` |
| CI | `.github/workflows/tests.yml` on this pull request's head |
| presentation ref | N/A |

## How it was done, and what it does not show

- **Claims.** Every MUST, SHOULD and MAY, every field, table or default that binds an implementation, and every plain "the station does X". Compound sentences are split, so one RFC line can give several rows. Left out: rationale, credits, prior art, and pure history. Of the 309 RFC lines that carry a BCP 14 word, 299 have rows; the other ten are headings (1388, 2965), lead-ins whose items have rows (1983, 2451, 2866), the key-words paragraph (50), a "not a MUST" (2433), a CDDL comment (730), a deviation note (2082) and a lineage pointer (3309).
- **Checking.** The RFC was read whole. Thirteen section audits and two code-first scans (station; frond-ear and plugin) opened the code for each row. A script checked that every quote is on its RFC line and that every cited file, line and Python test exists. 76 rows were then re-read at random against their cited code; one was reclassified. Every top-10 item below was re-read by hand, and an independent reviewer then tried to falsify section 1: about 260 sentences and cells, 57 problems (18 wrong facts), all fixed here. The tables have not had that second check row by row; their "Admitted" entries in particular may be incomplete.
- **Run.** Scratch copies only, no live daemon, station or room: station suite 413 tests OK (Python 3.12.3; CI uses 3.11), frond-ear `canticle*.test.ts` 411/411, plugin 136/136 (Node 26.9.0). Items marked **[ran]** were also reproduced with plain library calls (no sockets). Everything else is from reading.
- **"Implemented" is narrow.** The code with that role does what the sentence says. It does not mean deployed, reviewed or safe. 252 of the 1382 implemented rows have no test; at least 67 are prohibitions that hold only because the thing they forbid does not exist.
- **Not checked:** OpenClaw core (other repository), ews-concept-new, live seat configuration (beyond what #161 and #171 already published), operator practice. Those rows are `unclear`.
- **One source is stale.** The plugin README says no seat runs it, and some rows repeat that. #161's inventory (2026-11-22) shows the older six-tool plugin installed and connected on ronan since 11-17.

---

# 1. Summary

## 1.1 Counts

**2820 claims: 1382 implemented (I) · 456 diverged (D) · 885 unbuilt (U) · 10 obsolete (O) · 87 unclear (?).**

| | I | D | U | O | ? |
|---|---|---|---|---|---|
|MUST|146|54|137||2|
|MUST NOT|131|26|47||6|
|SHOULD (NOT)|14|7|24||3|
|MAY|16|5|54|||
|[PROPOSED DEFAULT]|52|29|76||4|
|plain statement|1023|335|547|10|72|

Of the 456 diverged rows: the RFC's rule is judged better in 283, the code's in 48, neither in 35, and 90 need an owner. For 168 the audit found no departure note.

| RFC section | claims | I | D | U | O | ? |
|---|---|---|---|---|---|---|
|Abstract, status|48|28|12|3|3|2|
|2 Terminology|57|31|11|15|||
|3 Architecture, invariants|55|23|16|15|1||
|4 Scopes|32|10|6|16|||
|5 Identity and naming|56|35|6|15|||
|6 Classes, staleness, findings|91|60|10|14||7|
|7 Carousel|223|167|18|37|1||
|8 Carrier wave|73|51|9|13|||
|9 Wire format|157|134|11|12|||
|10 Trust|170|56|37|75||2|
|11 Transport|180|38|16|125||1|
|12 Regulation, membrane|149|30|7|109||3|
|13 Discovery|52|25|1|25||1|
|14 Receptor and landing|751|424|158|147|5|17|
|15 Publishing|127|55|39|31||2|
|16 Harness bindings|105|37|16|25||27|
|17 MAGI|47|7|5|34||1|
|18 SeedLink, dashboards|71|26|9|28||8|
|19 Security|107|35|29|37||6|
|20 Brokers|20|9|1|10|||
|21 Non-goals|27|14|5|6||2|
|22 Conformance|91|44|11|36|||
|23 Questions, decisions, work|117|37|22|52||6|
|IANA|4|4|||||
|Appendix A|10|2|1|5||2|

The shape of it: §5, §7, §8, §9 and record v1 (§14.18.3) are largely built and tested. §10's manifest, §11.3's relay, §12's membrane, the receptor's judgment and regulation (§14.3-§14.8) and §17 are largely unbuilt. Landing, wake and publishing (§14.9-§14.16, §15, §16.5) are where code and text really disagree.

## 1.2 The ten divergences that matter

**1. A heard item of any class can wake a Claude seat.**
- *RFC:* D1 and §14.10 (1991-2021), D25, §14.18.9, §16.5 (2591): silent-only until S3 passes; then verified `alarm` only, under 11 conditions.
- *Code:* frond-ear sends a channel notification (banner `mode=silent-wake`), which starts a turn in an idle session, for any class from a key on `wakeKeys` at hop 0, not wake-derived, when the ear's mode allows it (`fe/delivery:1168-1181,2697-2702`; `fe/src/shim:654-667`). Of the 11 conditions, 8 holds, 1 holds on the host-daemon source (the embedded listener has no quarantine) and 9 in part; 4-6 are replaced by a mode, an hourly push cap (60, at most 360) and a breaker hold the daemon never triggers; 2 is replaced by the key allowlist; 3, 7, 10 and 11 are absent. Class, scope (Never 18), `lens.*` (§17.5) and opaque content (§9.9) are never checked. It is off by default; #171 recorded a live config with 2 wake keys and 3 stations on `immediate`.
- *Admitted:* `fe/docs/runbook:844-855`. Not in the RFC, the root `README.md:121` or the skill (`SKILL.md:32`, "silent-only").
- *Better:* **owner.** Settled in practice on frond-ear#65 (10-10); bc#100 has tracked the missing amendment since.

**2. Nothing stamps hop, lineage or `wake_derived`, so the loop guards cannot fire.** **[ran]**
- *RFC:* §14.8.1, §14.11, §15.4 item 5, Never 3 (wake-derived frames never wake) and 4: the publish tool stamps them.
- *Code:* the station's control socket has no such fields and signs every item hop 0, rootless, `wake_derived` 0 (`runner:85-107`, `station:309-312`). A request naming `hop`, `wake_derived` or `mode: addressed` is accepted and they are dropped. A woken session's `canticle sing` is therefore exactly what the next ear's push gate accepts; only the allowlist, the ear's mode (off by default), mutes, the debounce and the hourly cap bound the loop.
- *Admitted:* `pl/README:479-480`: the stamping cannot be done through that socket, derived content would go out unstamped, and the plugin therefore refuses a tainted session every sing. Not in the station README; the effect on the push gate nowhere. *Better:* **rfc.** *#162* stamps its separate derived op only (`#162/derived_reply_proposal:602-604`), off by default, and no frond-ear route is wired to it.

**3. There is no taint on the deployed path, and pushes go to Discord-bound sessions.**
- *RFC:* §14.12 items 1-7, its BC-1 interim rule (2053: no ambient delivery to a session with an off-host route), §15.4 item 4, Never 1, 6 and 13.
- *Code:* frond-ear has no taint and no tool gate; its room gate defaults to `observe`, which refuses nothing (`fe/src/egress:104-118`), and every frond-ear session has a Discord route by design. `canticle listen` under Monitor, which README:224 recommends, has no banner or wrapper either. The plugin taints on payload reads and consumed slots and bars only its own `canticle_sing`.
- *Admitted:* `fe/docs/runbook:852`, `pl/README:482`, README:67 and 230 (landing and taint not implemented, S3). *Better:* **rfc** for the enforcement; **owner** for 2053 (§23.2 question 22).

**4. Trust, revocation and key custody are not §10's.** **[ran]**
- *RFC:* §10.3 (root-signed CBOR, genesis pin, serial, 7 days, fail closed), §10.5 and D15; D35: the host daemon holds the station keys and signs.
- *Code:* plain, unsigned spike-0 JSON (`manifest:109-133`). The loader that the daemon, stations and listeners use ignores the format label, `signed` and unknown fields, so a misspelt `revoked` leaves the key trusted; only `manifest verify|show`, `doctor` and `dns-browse` run the strict check. Revocation needs an edit and a restart of every process, and an older file un-revokes it. Keys are files read by one `canticle station` process per key; the daemon holds none and discards publish lines (`daemon:36-38,175-206`). On silas, agent sessions share that uid (#168 §4.4); other seats are not attested here.
- *Admitted:* unsigned and file keys (README:63-64), publishing not through the daemon (README:445-447), no daemon reload (README:504), the lax loader only in a docstring (`manifest:170-171`); not the rollback. *Better:* **rfc** on signing, revocation and key isolation; **code** on keeping keys out of the process that parses hostile UDP.

**5. The receptor is looser than §12.2, which §12.8 forbids; unverified floods displace verified frames.**
- *RFC:* §14.1 steps 1-2 (per-key and per-source rate, then crypto), the MUST NOT at 1705, §12.8 (1590).
- *Code:* one kernel queue in arrival order, no rate, a durable save per new item (`daemon:489-493`, `records:215-233`). #171's flood acceptance test **fails**, with health `ok` while it did.
- *#173* fixes displacement (its README:581-589 names what is left: a spoof of the station's own address, a station that is still a stranger among many, a reader outrun at line rate) and reports loss, but in another order: exact repeats dropped before verify, rates debited after verify (`#173/intake:71-84,537-567`; its README:509 says so). #171 argues the RFC's pre-crypto per-key rate lets a forger spend the victim's budget.
- *Better:* against `main`, the RFC (rows 1705, 1590); between the RFC's order and #173's, **code**, so §12.2 and §14.1 need an amendment.

**6. An expired item can land as new after a restart (I-3, EM-01, EM-02), and a live one can land twice (I-4, §7.4).** **[ran]**
- *Replay after a restart.* Beacons have no time window (§12.2 step 3 relies on the `(epoch, bseq)` mark), and neither RFC nor code persists that mark or δ̂ (`listener:260-264,666-680`). After a receiver restart, or on a first join, with the station silent, a captured hour-old beacon and item land as `verified`, age 0, with a full 60 s TTL. Without the restart both are refused. frond-ear's embedded listener has the same code (`fe/listener:636-650`); #173 does not change it.
- *A rise in δ̂.* Dedup retention is fixed at first hearing (`listener:368`), admission uses the current δ̂ (`wire:445-449`). With a station clock 20 s behind and the item first heard before any beacon, it expired early at the receiver; once a beacon lifted δ̂, its ordinary loop was admitted as a second new item 5 s later, still inside its signed life. Unkeyed items only: a keyed one is refused as `superseded`.
- *Admitted:* nowhere for items; 565 and 574 handle a δ̂ rise for PLUCKs and marks, and 484 does not for dedup. *Better:* **neither**; the RFC has the same holes.

**7. The path in use between hosts is in no §11 binding.**
- *RFC:* relay lease MUST, "the default outside a known wired VLAN" (1177); §4.3: `lan` frames stay on LAN multicast and LAN relays; `canticle doctor` decides multicast (§11.2).
- *Code:* `canticle station --to peer:9999`, plain unicast to a static list (`runner:179-184`), which also strains I-1 (244, 1182); one pilot host is on Wi-Fi (`cs/docs/pilot-host/README:92,243`). No relay code exists. The daemon judges everything it hears as `lan` (`daemon:405-408`), and unicast has no TTL bound. `doctor` is a host check: step 2 is an unsigned loopback probe, steps 1 and 3-7 are unbuilt, and exit 0 means something else.
- *Admitted:* doctor at README:73,136-138; the unicast path nowhere as a departure. *Better:* **neither**: the RFC needs a LAN-unicast binding, and the code a real scope boundary.

**8. Publishing does not go through the daemon, has little of §15.4, and can answer `ok` for frames nobody can hear.** **[ran]**
- *RFC:* §11.1 (1205), §15.2, D35: sing and hush over the daemon's socket; §15.4 items 1-10.
- *Code:* each station has its own control socket, which the RFC never describes (`runner:82-177`). It checks uid (and skips the check where `SO_PEERCRED` is missing, `runner:153-154`), class, scope and stream, refuses regulatory, alarm and control to everyone (stricter than item 4), and has nothing of the rest of items 4-7 and 9. It signs a `state_key` over 32 B, a `purpose` over 128 B or an `intensity` over 255, returns ok, and every receiver refuses the frame as `bad-field`. An unknown `loop` word is refused only after the sequence number is spent and the current keyed value is off the air (`station:314-322`). `hush` ignores the socket's class grant; a revoked key keeps signing until restart.
- *Admitted:* publishing not through the daemon (README:445-447, `daemon:38-39`), the socket's narrower grant (README:17), content policy and taint (README:65), the uid skip (root `README.md:126-128`). *Better:* **code** on where the key lives; **rfc** on the checks.

**9. The station stops repeating items that §12.3 never sheds, and its restart loses PLUCKs.** **[ran]** (first point)
- *RFC:* §12.3 A3 never stops live-state, regulatory or root; §7.1: a PLUCK MUST loop until its target's expiry; the burst is charged to `B_stream` and skipped when the budget is exhausted (555); senders MUST respect `B_station` (1216).
- *Code:* `NEVER_SHED = {control, alarm}` (`station:38,374-377`). A live-state item with a 29 s TTL at the default loop goes out at 0, 1, 2 and 4 s and never again; `root` at `loop=slow` likewise. Late joiners never hear it, while the beacon counts it live. Burst copies (one at once, three later, per sing, refresh and pluck) are charged to nothing and no sing is refused for load; loop repeats, PLUCKs included, stay inside `B_stream`. The ring, PLUCKs and keep-on-air chains are memory only, and a new epoch cannot pluck old tuples.
- *Admitted:* burst accounting (README:71); shedding after the burst (`pl/README:478`, `station:424`), but not that live-state, regulatory and root are shed. *Better:* **rfc**, except that §7.1 and §7.3 contradict each other on restart.

**10. Withdrawals are lost at the edges, and the mixed-host gate has no receipt.** **[ran]** (first point)
- Retracts owed at daemon start are emitted before the first `landing_state`, and the socket opens only after that, so no binding can receive them (`records:241-248`, `daemon:473-481`; README:485-487 states the order). Revocation works only by this path. Both bindings drop the old run's items at a new `run`, so what is lost is the withdrawn mark on text already journalled or landed.
- The RFC contradicts itself on a restart into the same run: §14.18.3 (2265, 2271) and proof (6)(e) settle every pending key undelivered; §14.18.5 (2310, 2316) and §14.18.6 (2322) keep and deliver them. Both bindings keep them. After one disconnect or `rec_seq` gap the plugin also stops ambient delivery for that run until the gateway restarts or the daemon starts a new run (`pl/candidates:32,149,184`), and it ends a sync at the first failing session (`pl/binding:456-477`).
- §14.18.2's proof gate before a mixed host has loopback or unit tests for cases (1), (2), (3), (5), (6)(f) and halves of (4) and (7), and no receipt from silas or ronan in either repository; (6)(a)-(d) have nothing. Ronan has carried both bindings since 11-18 at the latest (#161: plugin connected since 11-17, frond-ear's process up since 11-18). Line 3253 still says frond-ear's canticle stays off there until the proofs pass.
- *Admitted:* README:504,519 in part. *Better:* **rfc** on the gate; **owner** on the restart rule.

**Next, one line each.**
- **Epochs.** A receiver keeps the highest epoch for ever (§5.2's window is ignored) and never treats two live epochs as equivocation: a copied key with a higher epoch leaves the real station `epoch_regression` on day 30 too, with nothing quarantined **[ran]** (`listener:236-240,555-586`).
- **Equivocation.** The daemon quarantines with no TTL or rescind (§14.7.3 says 1 h) and keeps no second frame, so no transferable proof (§10.8) exists; frond-ear embedded and `canticle listen` never quarantine.
- **The receptor core.** There is no hearer ring, receipt log, judgment object, salience, regulation or breaker producer, yet record v1's `sha256` and `bytes` point at a ring copy (§14.3-§14.8; README:507-512).
- **A1's receiver half.** Beacons carry `trail_seq`, but nothing acts on it and `gap` is always `unavailable` (`records:477`); `catalog_digest` hashes a private projection and no receiver reads it.
- **Findings (FP-1, D37)** reach no push and no `hear` as words: frond-ear and the plugin print a binary placeholder; only `canticle tap` decodes content type 11.
- **Stream grants.** Receivers never check the manifest's `streams` (§10.4, 1067): an ungranted stream id is `verified`, moves epoch, quota and marks, and its PLUCK retracts (admitted, README:497-498).
- **`canticle shape`** shows live stations to humans on a host-side list alone (`shape:428-434`), which proposed D38/§18.9 forbids; only `--display` needs a station-signed grant.
- **Rendering.** `canticle tap` prints the signed `purpose` with its newlines, outside the wrapper, so a station can add banner-looking lines **[ran]** (`tap:159`). frond-ear shows `UNOBSERVABLE` raw without "since t" (§8.6) and keeps stale presence after a gap.
- **Root marks.** A root item with no body reads as UNEQUIP, and its class and content type are unchecked (`listener:715-723`).
- **Keep-on-air and refresh.** Any keyed item may stay up 24 h (admitted, README:77), and `tap`, `shape` and the plugin count each refresh as new (§7.9).
- **Retention.** The plugin's journal serves heard bodies for 24 h by default after expiry or pluck (§14.5, I-10).

## 1.3 What the code depends on and the RFC does not state, or states otherwise

Condensed from the 247 gap records of the two scans and the section audits. "Half" means the RFC states part of it; "contradicts" means it says otherwise.

**Wire and identity**

| gap | what the code relies on | where | RFC |
|---|---|---|---|
| Decoder subset | No floats, tags or other simple values at any depth; map keys int or text only; explicit null is not absence; trailing bytes refused | `cbor:50-112`, `wire:259-306` | half, §9.4-9.5 |
| Depth counting | The frame map is level 1; the depth-bomb vector cannot tell 4 from 5 | `cbor:24-25,137-142` | silent |
| Field bounds | `class`, `lens`, integer `ctype` ≤ 65535; PLUCK `target_seq < seq`, `reason` ≤ 2; non-zero reserved flags refused | `wire:259-340` | half, §9.6-9.7 |
| Reject vocabulary and order | `oversize`, `short`, `bad-field` … and which check fires first; vectors depend on it | `wire:391-457` | half; the order departs from §14.1 |
| `catalog_digest` input | The CBOR array and its order | `station:500-503` | silent, §8.4 |
| Paging schedule | Moving cursor, page index is only a counter, unpaged when it fits, 32-entry cap ends a page | `station:505-549` | half |
| Beacon durability | `bseq` and δ̂ are per-run memory | `listener:260-264` | silent (item 6) |
| Vector file grammar | The JSON the second implementation reads | `vectors` | silent, §9.13 |
| Station names are not unique | Rotation gives one name several keys; tune, grants, presence and DNS key on the name | `manifest:82-95` | half, §10.5 (1078) |
| New class codes | A manifest naming an unknown class or scope fails to load whole | `manifest:110-125` | silent |

**Station and publishing**

| gap | what the code relies on | where | RFC |
|---|---|---|---|
| Control-socket protocol | One socket per station: path, 0600, peer uid, one JSON line, 64 KiB, ops `sing`/`hush`/`status`/`public_catalog`, reply shape | `runner:82-177` | contradicts, §11.1 |
| Socket grant | `--socket-class` narrows the key's grant; regulatory, alarm and control never over the socket | `runner:28-31,121-132` | contradicts, §15.1 (2411) |
| `hush` names a seq | No epoch or opaque item reference; callers must read `status` first | `station:343-364` | contradicts, §15.1 |
| Key, epoch and lease files | Seed as hex, `.epoch`, `.lease`, one process per key | `station:105-140`, `__main__:139-158` | half, §5.2 |
| Restart | New epoch; live items, PLUCKs, seqs and keep-on-air chains end silently | `station:192` | half, §7.3 |
| Budget floor | Streams cut to no less than 500 bit/s, by configured class, once at start | `station:218-230` | silent |
| Availability ceiling | Judged once, at admission; `degraded` is the clamp reason | `station:236-252` | contradicts, §7.5 |
| Default scope | `lan` for every class | `station:270` | contradicts, §6.2 |
| Typed streams | `beacon` (typed beacon items, #142) and `display` (grants, #137): keyed live-state items with their own bodies, typed by stream name | `beacon:35-37`, `grant:29-129` | contradicts, §5.4 ("opaque tags") |
| `shape`, `tap`, `dns-browse`, `vectors`, exit codes | CLI verbs and contracts | `__main__` | half, §15.7 (2798 names `tap`) |

**Receptor and host daemon**

| gap | what the code relies on | where | RFC |
|---|---|---|---|
| Spike-0 manifest | The only trust file any host loads: fields, defaults (`host`+`lan`), `public_streams`, label and SHA | `manifest:30-133` | contradicts, §10.3 |
| LAN unicast binding | Item 7; the binding label is fixed `lan`; source address never trusted; the nft guard is the only network gate | `daemon:405-408`, `cs/docs/pilot-host` | silent, §11 |
| Write-ahead | Save, then number and send; a failed save ends the run `state_not_durable` | `records:108-120,215-233` | silent |
| Safety-state file | Versioned JSON; rewritten whole per change; what survives a restart | `listener:666-713` | half |
| Socket takeover and leases | Probe, unlink, refuse; silent abort on uid, full or not ready | `daemon:350-360,386-463` | half (1204, 2166, 2255) |
| `idem` radix and big integers | `stream_id` as 8 hex digits; `seq` above 2^53−1 is a string; the plugin drops records that differ | `records:151-160` | silent, §14.18.3 |
| Frame record encodings | Nulls, `text` or `base64`, tuple and `body_ref` objects; which fields are required | `records:436-497` | half |
| `health`, `hello`, `fatal`, `presence` fields | Names and values on the wire; #173 adds more | `records:241-252,499-552` | half |
| Reason codes | `key_quarantined`, `scope_not_granted`, `unknown_class` … | `records:61-64,325-345` | half |
| Snapshot details | Entry wrapped as `{frame}` or `{presence}`; request only as the first line | `daemon:183-206,253-275` | half |
| Local quarantine | Items from a quarantined key keep their body at `ringbuffer_only`; no end | `records:389-397,428-434` | contradicts, §14.7.3 |
| Warm-up default | 6.7 s when no loop is advertised; live-state only | `listener:539-547` | half, §6.3 |
| Per-key share | Capacity ÷ manifest entries, revoked ones included | `listener:493-497` | half, §7.4 (486, 489 name the spike's equal share) |
| #173's intake | Queues per claimed key, stream and source; exact-repeat digests; buckets 16/12/8 per s; 32 datagrams per save | `#173/intake:71-86,246-567` | contradicts, §14.1 order |

**Bindings**

| gap | what the code relies on | where | RFC |
|---|---|---|---|
| Custody | claimed → offered → echoed, per exposure, stamped with the compaction boundary; give-back of unconfirmed pushes | `fe/custody:1-120`, `fe/src/store:1408-1628` | silent (1.4) |
| Wake allowlist and modes | `wakeKeys`; `off`/`digest`/`immediate` ceilings; session narrows; mute permanent for what it covers | `fe/delivery:1-40` | contradicts, §14.10 |
| Push budget and cadence | Hourly cap, debounce ≥ 5 s, `maxAgeMs`, report order and cursor | `fe/delivery:1128-1390` | contradicts, §14.6.5 |
| Coverage notes, local omissions | What the binding withheld is told, with reason and span; a note-only push | `fe/delivery:27-57` (frond-ear#119) | silent; #168 §2.7a |
| Live-set fairness | 4 096 records; a share per tuned stream, one for all untuned | `fe/records` (frond-ear#119) | silent |
| Session incarnation | ear + attach generation + session id (frond-ear); sessionKey + sessionId + lifecycleRevision (plugin; #162 the same, for a sub-agent key only) | `fe/src/store`, `pl/oc0-host:12-25` | silent |
| OC-0 extras | Exact generation on every call, `resolveLocalSessionRoute`, reset and delete callbacks | `pl/index:80-118`, `pl/oc0-host` | silent, §16.4 |
| Four consents | Ingest tune, read scope per session, payload sessions, delivery subscriptions | `pl/config` | half, §14.18.1 |
| Taint and "complete history" | Taint: none (frond-ear), one bit (plugin). Complete history: a custody window all echoed inside the current boundary (frond-ear), every exposure since an attested origin (#162), none (plugin) | `pl/binding`, `#162/derived_reply_proposal` | contradicts, §14.12 |
| Room-output policy | `observe` or `strict-fresh` at every Discord write | `fe/src/egress:100-121` | silent |
| Derived publication | HMAC capsule, one-use claim, `derived_publish`/`derived_query` | `fe/derived`, `#162/derived_station_proposal` | silent |
| Outbox | `unknown` on a lost reply, never re-sent, settled by hearing one's own frame | `pl/outbox:297-325,576-611` | half, §15.1 |
| MUTE, breaker and gap at a binding | frond-ear empties `hear`; the plugin keeps reads open; opposite results from one `landing_state` | `fe/records:1416-1432` | half, §14.18.4 |
| Trust in the host socket | Bindings verify no signature and print `sig=valid`; the plugin checks the socket's owner, frond-ear checks nothing | `fe/record-client:70-80`, `fe/hear:125` | contradicts, D4 |
| Two fail-closed readings | A malformed record, a regression, silence, a bad snapshot entry: each binding does something else | `fe/records`, `pl/receive` | half |

## 1.4 The receipt layers

🪨's map (the room, 2026-11-23) names five receipts and says they are different: on air, queued, host-returned, model-seen, prince-encountered. What produces each today, and what the RFC says:

| layer | station | host daemon | frond-ear | OpenClaw plugin | #162 (open) | RFC-0001 |
|---|---|---|---|---|---|---|
| **1 on air** | `sing` reply: signed and in the ring, not yet sent; no key id, stream id or frame hash (`station:313-341`) | `frame` record, first hearing: this host's own proof it was transmitted (`records:440-497`) | none (keeps a derived receipt; no route wired) | outbox `on_air`, from the reply or from hearing its own frame | the fullest: election, payload and frame hashes, full key (`#162/derived_station_proposal:55-78`) | **partly.** "on-air" is a tool status (2387); never defined as signed, queued or sent |
| **2 queued** | none, by design (I-1) | per-connection queue; a `rec_seq` gap says what was dropped | waiting records are in memory; durable at push (`claimed`) | `candidates.json`, then slot `enqueuing` → `pending` | a pending fence before a payload is released, where the host supplies the port (otherwise none) | **specified for OC-0 slots** (2308-2315); silent for a host that only takes a notification |
| **3 host-returned** | none, by design | the kernel accepted a line | `offered`: the shim's write to the client completed (`fe/src/shim:654-667`); `hear` is stamped offered *and* echoed before its result leaves the daemon (`fe/src/daemon:3904-3908`) | OC-0 outcome is authoritative; a tool result is no receipt | plugin port: `begin` only; the ledger has `confirm_exposure` (`#162/derived_reply_proposal:364-388`), called only by tests | **partly.** OC-0 outcomes (2311-2315, 2570); Claude Code "not acknowledged" (2599) |
| **4 model-seen** | none, by design | none | none; an attach canary shows the channel reached the model once | `consumed` settles and taints, but 2317 says it is not this receipt | `session_exposure` is an outcome kind for the derived item; nothing records it | **silent.** Says only what is *not* a receipt (2317, 3091). #168 §3 names the missing one |
| **5 prince-encountered** | none (a reply is a new frame) | none | `echoed`: the session quoted the push's whole `batch_id` and token | none (a read checkpoint is a pull) | `elected_response` outcome kind; nothing records it | **silent, and in tension:** receipts removed (1726), no "awaiting reply" (1985-1987), no self-report (3091) |

No layer implies the next, and no code treats it as doing so, with one exception: `hear` in frond-ear marks layer 5 at layer 2. Layer 4 has no positive receipt anywhere; #168 §5 places frond-ear's `offered` in its "→ model input" row, while its code is a write callback (layer 3), so #168 and this table disagree there. The RFC defines layer 2 for one host only, half of 1 and 3, and nothing of 4 and 5, so the words claimed, offered, echoed, exposure and elected live in two repos and one draft.

## 1.5 Where the RFC contradicts itself

- **Restart into the same run:** 2265, 2271 and proof (6)(e) against 2310, 2316, 2322 (item 10).
- **One unsigned path:** D4 (992-994) allows only a debug socket; D35's record socket is unsigned and is how everything lands.
- **Pre-crypto per-key rate:** §14.1 step 1 and §12.2 step 4 against 1705's MUST NOT displace (item 5).
- **Replayed beacons:** 1433 relies on a mark that §7.4 and §8.6 never make durable.
- **Dedup quota:** 486's 4 × the live count a key *itself* signs (a u32) against 487's "every per-key structure is bounded".
- **PLUCK and restart:** 458 (MUST keep looping until expiry) against 475 (persistence is a MAY; new epoch) and 838 (a PLUCK names its own epoch).
- **Lower epochs:** 578 "refused" against 1147 "verified, ringbuffer_only". 1147's "otherwise admitted as any frame is" also leaves a lower-epoch PLUCK open: the code holds it and retracts nothing (`listener:555-586`).
- **Quiet:** 252 and 401 against 707, which defines EQUIPPED_QUIET by absence.
- **Repeats:** I-4 and R-INT-1 ("every derived quantity") against 491 and 706, where a repeat refreshes presence.
- **Lens:** 356 "not a frame field" against 829 and §17.3.
- **Sockets:** 1213 (`SO_REUSEADDR`/`SO_REUSEPORT`) against proof case 1 and 282; 1203's 0700/0600 against 1204's "allowed users".
- **Relay cookie:** 1281 hashes `client_nonce`, which RENEW, REPAIR and BYE (1249-1252) do not carry; 1287's persisted secret cannot then validate one after a restart, since 1292 forbids the lease table. `relay_epoch` indexes the 120 s secrets (1281) and is also a value persisted beside a separate secret counter (1287-1290).
- **Post-compaction:** 1969 reserves it; 2589 returns the digest from a `SessionStart` `compact` hook.
- **Timed emission:** 2447 exempts the loop from "timer-fired broadcast is noise"; §15.8's emitter and §7.9's re-issue mint new items on a timer and are not exempted.
- **Admission results:** 1127 "every frame gets exactly one" against §14.18.3 for BEACON and PLUCK.
- **Versioning:** 804 wants a new `version` byte; A1 inserted `trail_seq` mid-array under `0x02`, which the pre-A1 reader would misread.
- **Two defaults under one word:** 1967 (landing mode of a tuned stream) and 1975 (an untuned subscription) are both "default".
- **Two sentences left behind by amendments:** 2283's "truncated rather than closing" (replaced by #86 later in the bullet) and 1705's first sentence (replaced by D34).

## 1.6 Text that is false, stale or not updated

- 26: "Nothing in it is deployed; the only running code on `main` is `prototype/ringserver-udp-cue/`." 7: the `b46a45a` baseline is stale (`prototype/ringserver-udp-cue/` is all it has of today's code); 55: several current-code citations do not say which SHA they mean.
- 40, 42, 44: true as dated history ("to become a decision"), not updated: §23.1 says D35, D36 and D37 are Decided.
- 913: the lineage row's 799-byte body. 791 fits (816 with `ctype` 1) **[ran]**; `rfc/0001-notes/vec/frame_v2_sizes.py:47` starts its search at 800.
- 3250 (question 20): "37 candidate vectors … predate `trail_seq`". There are 49 (34 parse, 15 sequences), they carry it, and frond-ear's suite runs all 49. README:12 and :626 say 46. §9.13's "generated and cross-checked by two independent implementations" is still half met: the TypeScript side has no frame encoder.
- 3258 (question 26): "the prototype has no doctor". It has one; it does not do §11.2.
- 2202: `gap` "until beacons carry it". They do.
- 2236: "so BC-2 adds manifest stream grants" did not happen (README:497-498).
- 2734: retitle and close #49. Closed 2026-10-19, not retitled.
- 3253: frond-ear's canticle "stays off on silas and ronan until the mixed-host proofs of §14.18.2 pass there": contradicted on ronan by #161; #168 §5 also lists 🍃's ear as installed.
- Outside the RFC: the root `README.md:121,148-150` and `SKILL.md:32` ("silent-only", "no seat runs it"); station README:224 against :230, and :228 ("no seat runs it"); `pl/README:17-18` ("installed on no seat") and `pl/README:22,211,483` against its own ambient slots; `AGENTS.md`'s map ("No seat runs it"); `cs/docs/state-layout.md` on write order; `AGENTS.md` also calls frond-ear private (it is public).

## 1.7 What the open pull requests would change

- **#173** (`canticle/intake.py`): makes 1705's no-displacement hold on the daemon (with the limits of item 5; `canticle listen` and `tuner` still hear in arrival order) and the two unbuilt rate rows built; keeps §14.1 diverged, in a better order; adds `health.records.socket_dropped`, `receive.refused` and reasons `socket_drops` and `datagrams_refused`, which §14.18.3 does not list; adds an outcome beside §10.9's results (refused unverified); times beacons on arrival and items at their turn. It changes none of items 1-4 and 6-10.
- **#162**: stamps hop, `derived_from`, `root` and `wake_derived`, and scans content, for `derived_publish` only (default off, nobody calls it). It leaves `sing` as it is, adds cue ops to a socket the RFC does not describe, and adds an HMAC capsule authority that §10 does not have. It closes none of the ten: a caller is not wired, and the ordinary path stays open beside it.
- **#168** (design): contradicts no row except 1.4's reading of `offered`. It states the receipts of 1.4, the three axes per stream, local omissions and the "bound the receiver first" rule. frond-ear#116/#118 (ring reader, merged note) and §18.3/bc#130 (relay-side bridge) are two undecided places for one writer, so §18.3's rows are not `obsolete`.

## 1.8 Obsolete and unclear

- **Obsolete (10):** 40, 42, 44 (decided since); 233 (receptor child: superseded where a daemon runs, D35; 1687 still allows it on a one-binding host); 578 (by §10.9 BC-1); 1705 first sentence (by D34); 1722 `landing` and 1728 `sigState` (by record v1 and D34); 2098 local session API (by record v1 over the host socket); 2283 (by #86).
- **Unclear (87), by who can answer:** OpenClaw core, #1511/#1523 (37: §14.12-14.18, §16.1, §16.4); operators and key holders (D14, D15, D19, training use, clocks, BCP 38); ews-concept-new (§18.5-18.6, bc#12); the princes (§23.2 questions 22 and 24, the mixed-host receipts); RFC editors (the tenth invariant at 416, the profile table at 1562, citation SHAs).

## 1.9 What step 2 needs decided first

1. **Wake (item 1):** amend D1/§14.10/§16.5 to what frond-ear does, or change frond-ear. bc#100 is the open issue.
2. **The publish path (items 2 and 8):** whether the station socket is the publish surface (then specify it and put §15.4's stamping there) or the daemon is.
3. **Receipts (1.4):** which layers the RFC owns, and their names.
4. **Admission order (item 5):** §12.2's and §14.1's, or #173's. The measurements favour #173's.
5. **Freshness (item 6):** a durable `(epoch, bseq)` mark or a beacon time bound, and one rule for δ̂ in dedup retention.
6. **Binding and trust in use (items 4 and 7):** specify LAN unicast and the spike-0 manifest as stages, or mark them as departures.
7. **Restart rule (item 10):** 2271 or 2310.

---

# 2. Tables per RFC section

**Columns.** RFC line at `d4c30661` with its keyword (`dflt` = a [PROPOSED DEFAULT]; none = a plain statement) · the claim, quoted (markup dropped, table bars shown as `/`, cut with …) · class · evidence · note. **Classes:** I implemented · **D** diverged, then whose rule is better (`rfc`, `code`, `neither`, `owner`) · U unbuilt (`U×n` = n claims of one line; a MAY nobody took up is also U) · **O** obsolete · **?** unclear.

**Evidence:** code; then frond-ear; then `t/` the test that shows it, if any (no `t/` = no test). Paths: `listener:12` is `prototype/canticle-station/canticle/listener.py`; `t/x` its `tests/test_x.py`; `cs/` other files there; `README` its README; `pl/x` is `prototype/openclaw-canticle/src/x.ts` (`pl/t/x` its tests); `fe/x` is frond-ear `src/canticle/x.ts`, `fe/src/x` its `src/x.ts`, `fe/t/x` its tests, `fe/docs/x` its docs; `#173/x` and `#162/x` the same files on those pull requests; `#171` is `reports/measurement/2026-11-23-step-one/README.md`. A "row" number in a note is an RFC line. "Admitted" names a departure note; its absence on a D row means none was found.

### Abstract and status of the memo

48 claims: 28 I · 12 D · 3 U · 3 O · 2 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|7|karmaterminal/binary-canticle main @ b46a45a (2026-09-17)|**D** code|station:147, daemon:210|Stale baseline: b46a45a (an ancestor of d4c3066) has only prototype/ringserver-udp-cue under prototype/. The station, daemon, plugin, harness and skill all came later; lines 38 and 55 already cite later SHAs.|
|16|A station (a signing identity) carries one or more streams|I|station:147-173, __main__:139-158; t/station:461||
|16|Trusted clients put short-lived items on a station:stream|I|runner:151-166,82-109; t/udp_e2e:24||
|16|re-emits the same signed bytes at a regulated frequency|I|station:313,396-445; t/station:37||
|16|until the item's absolute expiry, then lets it go|I|station:389-394,405-411; t/station:37|Ring entry deleted 100 ms before signed expires_at.|
|16|Late joiners catch up by hearing the next revolution|I|station:396-432, daemon:302-330; t/station:414|True at a receptor.|
|16|nobody asks the station for anything, and the station tracks nobody|**D** owner|runner:179-184, __main__:164-168|No inbound path exists, but canticle station --to is a per-listener destination list; the live stations unicast to four peers each. See I-1.|
|16|Every station also emits a small signed carrier-beacon…|I|station:505-549,464-477; t/station:245||
|16|Frames travel over host-local IPC|**D** code|runner:144-184, daemon:454-463|Frames only travel as UDP. Unix sockets carry sing requests (JSON) and record v1, never frames; host-scope frames can't be sent. §11.1 itself says requests, not frames. Admitted: README:17 (host scope refused: UDP only).|
|16|optional LAN multicast, and unicast relays|I|runner:145-146, __main__:761; t/stations:52|Multicast half only: built, off by default, TTL 1. Relays are the next row.|
|16|unicast relays that hold soft-state listener leases for internet…|U||No relay process, HELLO/LISTEN/RENEW or lease exists in any…|
|16|On the receiving host one deterministic receptor verifies, records…|I|daemon:404-427, records:308-387; fe/source:72-84; t/daemon:229|Verify and judge: yes, with explicit time. 'Records' raw frames: no (see I-5). #173 changes when datagrams are heard (#173/intake:1), not the judgement|
|16|lands a bounded, bannered digest into the sessions that tuned in|**D** owner|pl/ambient-slots:119-163, tap:142-174; fe/delivery:1128-1159|frond-ear lands whole records as channel events (up to 10 per push) or a hear read; the plugin's OC-0 digest slots exist but its README says no seat runs it. Banner is there in all of them. Admitted: fe/docs/runbook:850.|
|16|into the sessions that tuned in — silently by default|I|pl/config:129-130; fe/src/config:188-201; pl/t/candidates:21|frond-ear: no delivery entry means off; empty wakeKeys pushes nothing.|
|16|with a tightly budgeted, receiver-local wake for alarms|**D** owner|fe/delivery:1167-1180|frond-ear wakes for ANY class from a wakeKeys station; no class check in #passOver, budget 60 (max 360) pushes/h instead of 6 wakes/h. Live on the scribe seats (measured config: 3 stations immediate). Admitted: fe/docs/runbook:851; reports/measurement/2026-11….|
|16|A replay and dashboard tier (EarthScope ringserver…|U||Only proof scripts (prototype/ringserver-proofs).|
|18|This document is the one place where the design is written down.|**D** rfc|grant:1-19, beacon:137; fe/delivery:1-67|Display grants (#137), typed beacons (#142), the shape view (#133), ambient OC-0 slots and frond-ear delivery modes (#65) are built and described only in READMEs or the runbook. Admitted: fe/docs/runbook:844-845 (frond-ear only); none….|
|26|This is a Draft. It is not wire-stable.|I|README:751, wire:20-27; t/wire:161|Vectors are candidates and the version byte is the only freeze.|
|26|Nothing in it is deployed; the only running code on main|**D** code|#171:70-82, daemon:467-516; fe/src/cli:119-131|False. The step-one measurement (on main) describes live stations, a live host daemon on the LAN, and a live frond-ear with wake keys; frond-ear is installed on the scribe seats.|
|26|the only running code on main is prototype/ringserver-udp-cue/|**D** code|daemon:210, tap:177|main also holds canticle-station (codec, station, listener, host daemon, records, tap, tuner, shape), openclaw-canticle, protocol-dynamics, ringserver-proofs and the agent skill. CI runs these, not the cue.|
|26|which this RFC treats as a donor for the verify stage (§10.10), not…|I|wire:1-27|canticle-station has its own codec|
|28|The review notes are committed next to this file under…|I|rfc/0001-notes/spine:1, rfc/0001-notes/README:1||
|40|This revision proposes that as D35 (§23.1), to become a decision when the princes approve it|**O**||Successor: §23.1 D35 (line 3206) reads Decided, PR #69 merged 2026-10-02 as c0eff00. The memo still says proposed.|
|40|one standalone canticle host daemon per host, with every harness binding a peer client of it|**D** rfc|daemon:404-427, pl/daemon:75-93; fe/src/config:318-321|Daemon, tap, plugin and frond-ear host-daemon mode comply. frond-ear still ships its own UDP receptor as the DEFAULT source (embedded): wired in cli.ts when canticle.enabled, refuses to bind if the host socket answers. Admitted: fe/docs/runbook:656-659.|
|40|It lets the host socket be a framed unix SOCK_STREAM (§11.1)|I|daemon:454-463, records:78-83; t/daemon:126||
|42|because a repeat is duplicate at the receptor and never becomes a…|I|records:383-385, listener:333-336; t/records:150|Repeat raises counters only. #173 drops exact repeats before parsing and counts them (#173/records:369-379)|
|42|This revision proposes that as D36 (§23.1), to become a decision when the princes approve it|**O**||Successor: §23.1 D36 (line 3207) reads Decided, PR #82 merged 2026-10-02 as 1dc848b.|
|42|an opt-in join snapshot after the unchanged bootstrap (§14.18.3…|I|daemon:253-330; fe/record-client:80-86; t/join_snapshot:199|Daemon serves it on the first-line request; tap, plugin and frond-ear all ask for it.|
|42|the binding health reason joined_late|I|tap:207-215, pl/receive:597-604; fe/records:641; pl/t/receive:142||
|44|This revision proposes it as D37 (§23.1), to become a decision when the princes approve its pull request|**O**||Successor: §23.1 D37 (line 3208) reads Decided, PR #115 merged 2026-10-27 as 9047b4e.|
|44|a finding is a keyed advisory with a typed body (content type 11…|I|finding:107-120, runner:70-79; t/finding:162||
|44|only an explicit signed resolved item resolves it|I|finding:32-35, listener:441-445; t/finding:256|No code turns expiry or pluck into resolved|
|44|it is attributed to its signer whatever its body says about voice|I|finding:135-145, tap:109-114; fe/hear:169-173; t/finding:328|canticle tap only.|
|44|and a finding-ref rings its durable receipt|I|station:291-294, runner:55-67; t/finding:191|body_ref only, ctype 8 by default; no receiver fetches it.|
|46 MUST NOT|a human API/DOM/log/drill-through surface must not expose listener…|I|tuner:41-67, shape:117-120; t/tuner:84|Tuner: TunerView drops the listener.|
|46|The default is empty; --demo-fixture alone may show explicitly…|I|tuner:55-67; t/tuner:93|True of canticle tuner.|
|46|Future real-station presence remains contingent on broadcaster-owned, station-signed consent|**D** rfc|shape:143-149,431-434|canticle shape without --display serves live presence, beacon ages, counts and a river for stations the HOST names; consent is off-band (#133). Only --display uses station-signed grants (#137). Admitted: README:315-317 (admits it; RFC never mentions….|
|54 dflt|numbers are starting values for the canticle-regulation/1 profile (§12.8)|**?**|station:26-38|Code hard-codes the numbers and only sends the profile's name in beacons; nothing loads, checks or overrides a profile. Whether tuning at cohort scale is done: owners (D5, D24); step-one measurement is the first data.|
|55|repository paths are relative to the repository root at b46a45a|**?**||A citation rule, not behaviour. But proto/ and prototype paths cited at b46a45a no longer describe main; editors should say which SHA each current-code citation means.|
|78|reliability, byte-perfect replay from the station, cross-host…|I|runner:82-118, pl/outbox:1-12|Nothing contrary exists: the station's only ops are sing, hush, status…|
|82|The carousel (§7) is now the only replay mechanism on the broadcast…|I|station:396-432, daemon:253-271|No fill, repair or ring replay on UDP. The join snapshot is host-socket only.|
|83|It makes Ed25519 per frame the base layer|I|wire:421-456; fe/wire:558; t/wire:152|parse() admits nothing without a valid signature by a manifest key.|
|83|and drops the shared frond HMAC|I|wire:212-218|No HMAC in station, plugin or frond-ear frame code. #162 uses an HMAC capsule on the station control socket, not on frames|
|84|It adds internet listeners through relay-held leases.|U||No relay or lease code.|
|84|through relay-held leases. The station still tracks nobody.|**D** owner|runner:179-184|See I-1: the station process holds a configured per-listener destination list.|
|85|silent landing by consent, and a budgeted, receiver-local wake for one class (alarm)|**D** owner|pl/config:129-130; fe/delivery:1167-1180|Consent and receiver-local: yes (frond-ear delivery + wakeKeys). One class (alarm): no, any class from an allowlisted key. Admitted: fe/docs/runbook:851.|
|86|It defines one wire format (v2)|I|wire:20-27,412-415; t/wire:152||
|86|the v0.1 string-keyed frame, the v0.2 ULID frame, and the…|I|wire:412-418|Retired: no code reads the first two|

### §2 Terminology

57 claims: 31 I · 11 D · 15 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|136|A signing identity that emits frames: one Ed25519 key.|I|station:147-158, __main__:149-156; t/station:461||
|136|A process that runs a station is an epoch of it (§5.2).|I|__main__:157, station:105-140; t/station:433||
|137|The first 8 bytes of SHA-256 of the station's 32-byte Ed25519…|I|ids:15-19; fe/manifest:59; t/wire:152||
|137|A lookup hint, never an authority.|I|manifest:98-104, wire:421-456; t/records:508|key-id only selects a manifest key; the signature decides.|
|138|An operator, host or service listed in the fleet manifest, owning… ‖ Accord counts principals, not keys (§10.7).|U×2||The spike manifest has no principals No accord code anywhere.|
|139|The signed document that binds principals, keys, human names|**D** rfc|manifest:127-133,179-180; fe/manifest:4-8|The manifest is plain unsigned JSON (signed: false); whoever can write the file chooses the trusted keys. verify_json refuses signed: true. Admitted: README:63.|
|139|human names, capability classes, audience scopes, relays and revocations|**D** rfc|manifest:33,37-61; fe/manifest:26-62|Built: key, name, classes, streams, scopes, revoked flag. Missing: principals, relays, per-stream audiences, root-signed revocations with time. revoked is read only at start. Admitted: README:63; README:504.|
|139|relays and revocations (§10.3). The only trust anchor.|I|manifest:98-104, pl/discover:106-110; t/dns_browse:52|No other source yields a verifying key.|
|140|The set of frame classes a key may sign, from the manifest (§10.4).|I|station:278-284, listener:298-300; fe/listener:690-700; t/records:178||
|141|A u32, monotonic per key, that changes whenever the station loses…|I|station:105-140,163-165; t/station:433||
|142|A named channel within a station. Wire identifier stream_id (u32…|I|ids:71-86, station:171-173; t/wire:144||
|143|The primitive addressing tuple (proto/stations-and-streams-v0.2.md:7…|I|tap:59-64, pl/config:192-200; fe/records:111-121; t/tap:70|tap, the plugin and frond-ear tune station:stream pairs.|
|144|One utterance on a stream: an ITEM frame with its own seq and…|I|station:309-314, wire:259-309; t/station:37||
|145|One signed datagram: ITEM, PLUCK or BEACON (§9).|I|wire:22,416-418; fe/wire:558; t/wire:152||
|146|The frame's identity for deduplication, pluck and lineage.|I|wire:149-155, listener:319-336; fe/listener:144-151; t/records:130|Dedup and pluck use it. Lineage fields parse and pass through but nothing uses them.|
|147|Items on a stream that are unexpired, un-plucked and not superseded.|**D** owner|station:471-473,366-373|The station ring and the beacon's live count also include looping PLUCKs, and leave out items pushed out by depth. §9.8 says live is the live-set size.|
|148|The station's periodic byte-identical re-emission of each live item…|I|station:434-445; t/station:37||
|149|The effective interval between re-emissions of an item (§7.5).|I|station:234-251,441-445; t/station:51||
|150|expires_at is absolute (ms since the Unix epoch) and signed. TTL =…|I|station:305-313, wire:164-166; t/station:37||
|151|expires_at − now, measured fail-closed by the receiver (§14.6.3). Never reset.|**D** neither|wire:368-388, listener:104-106; fe/listener:140-141|Code follows §14.6.3: min(expires+δ̂, first hearing+TTL), so a positive δ̂ lets life run past signed expires_at. That is not expires_at − now, and δ̂ can come from a replayed beacon (see I-3).|
|152|The station's live set per stream; the loop source. Retention…|I|station:31,93-98; t/station:229|Depth 256 applies to ITEMs only; live PLUCKs have their own cap.|
|153|The receiver's bounded local cache of verified frames (§14.4). Not…|U||Daemon keeps dedup digests and the latest deliverable record…|
|154|Durable audit and promoted state (§3.1). Never queried as current…|U||No receipt log, ledger or promotion.|
|155|Revocation of a live item by its own station; a PLUCK frame that…|I|station:343-364, listener:373-388; fe/listener:828-849; t/station:150||
|156|The receiver rule that a plucked tuple stays suppressed even if the…|I|listener:376-395; fe/listener:832-834; t/records:202||
|157|A newer item with the same state_key replaces the older one at the…|I|station:316-320, listener:399-445; fe/records:573-579; t/station:100|Plugin tombstones the retracted idem|
|158|The signed, content-free 1 Hz presence frame (§8).|I|station:149,505-549; t/station:245|1 000 ms ±10 %, settable with --beacon-ms.|
|159|An optional, coarse, versioned sketch of a station's "timbre"|U||Optional. Parser only checks key 10 is a map|
|160|A station's single persistent, elected mark, carried as a keyed…|I|station:323-328, listener:715-723; fe/listener:1258-1276; t/station:192||
|161|The explicit act of emptying the root mark (§8.5).|I|listener:715-723; t/listener:37||
|162|A process that admits frames from stations, holds listener leases…|U||No relay.|
|163|Soft state a relay holds for one listener address (§11.3). The…|U||No leases.|
|164|A process (normally the per-host receptor daemon) that receives…|I|daemon:404-427, runner:206-242; fe/receptor:304-330; t/udp_e2e:24|canticle daemon, canticle listen, frond-ear embedded.|
|165|The deterministic judgment core on a receiving host (§14).|I|records:168-211, listener:221-234; fe/listener:561-596; t/wire:152||
|166|The receptor's per-frame result: disposition, state delta, evidence, pointer to the source frame.|**D** owner|records:440-497|Record v1 frame has admission, disposition, reasons, identity and hash, but no state delta and no {rule, inputs, decision} evidence. §14.18.3 vs §14.3: the RFC never says record v1 is the judgment object.|
|167|Delivery of receptor output into a session context (§14.9).|I|pl/ambient-slots:119-163; fe/delivery:1147-1156; fe/t/canticle-delivery:38|frond-ear: channel events and hear.|
|168|silent / silent-wake / post-compaction / Landing modes|**D** owner|tap:150, pl/render:104; fe/hear:93-101|frond-ear labels hear silent and pushes silent-wake; plugin and tap only silent. post-compaction is unbuilt (reserved, D13).|
|169|Causing a session to start a turn it would not otherwise start.…|I|pl/config:129-130; fe/src/config:332-343; fe/t/canticle-delivery:749|Only frond-ear wakes, and only by its own config (delivery + wakeKeys).|
|170|The capability attenuation applied to a session that has ingested heard content (§14.12).|**D** rfc|pl/binding:610-615,1142-1148; fe/src/egress:104-110|Plugin: a tainted session loses only canticle_sing. frond-ear: no taint at all; it records custody and the default room policy (observe) refuses nothing. Admitted: pl/README:285-290; pl/README:482….|
|171|The tool-stamped count of sing-generations between a frame and first-hand content (§14.11).|**D** rfc|runner:90-107, station:272; fe/delivery:1174-1175|No tool stamps it: the control socket passes no hop, so every sung item is hop 0 and wake_derived 0, re-sung heard text included. Only the receive-side limit is enforced. Admitted: README:65; pl/README:480. #162 #162/station:348-372 stamps hop from a capsule, disabled by default|
|172|The original frame that a derived frame descends from. Accord…|U||Wire key 17 parses and is shown in banners #162 sets root on derived items (disabled by default)|
|173|The frame class (§6.2): chatter, ambient, live-state, advisory…|I|ids:101-115; fe/ids:89; t/wire:152||
|174|The declared audience of a frame: host, lan, fleet, public (§4.3).|I|ids:120, wire:300; t/listener:190||
|175|A registered question of the form "what is now and X" (§17).|U||No registry. A number slot exists in StreamConfig/wire|
|176|A stream carrying one lens's current synthesis, and the sub-agent…|U||Only a lens.‹name› naming example.|
|177|A regulatory frame (class regulatory) that asks receivers to shift…|U||The class parses and surfaces like any item|
|178|The number of distinct eligible principals whose independent…|U|||
|179|A ledger entry, keyed by antigen digest, that marks content as…|U||No departure note in either README beyond the general §14 line.|
|180|How often copies of an item arrive (shaped by stations and relays)|I|station:234-251; t/station:51|Station regulator only; no relay.|
|180|versus how much an item should change a receiver (computed only by…|U||No strength, salience or threshold is computed anywhere, so…|
|181|One of at most two host queue slots per session that carry canticle content|**D** owner|pl/ambient-slots:9,119-163; fe/delivery:1147-1156|Plugin keeps the two named slots (conditional on OC-0 host APIs; no seat). frond-ear violates it: every push is a new channel event, none rebuilt or recalled. Admitted: fe/docs/runbook:850.|
|182|An item that carries only a digest and a reference to content on…|I|station:289-294, runner:55-67; t/finding:191|The station lets any class carry only a body_ref; finding-ref is the convention.|
|183|A relay that loops the verified live set of upstream stations for…|U|||
|184|Sing = put an item on air; hush = pluck|I|runner:85-109, pl/tools:97-136; t/udp_e2e:24|CLI and plugin (publish off by default); frond-ear has no sing.|
|184|tune = declare what a session receives|**D** owner|__main__:904, pl/config:208-225; fe/src/config:297-317|No tune verb. It is configuration everywhere: tap --tune, plugin listen.subscriptions, frond-ear canticle.tune. Admitted: pl/README:474.|
|184|listen = read the local ring or digest.|**D** code|pl/tools:41-67, __main__:382-419; fe/src/daemon:3888-3905|Plugin canticle_listen does this (journal, not a ring). canticle listen is a UDP listener that streams events; frond-ear's verb is hear. Admitted: pl/README:475 (plugin only).|

### §3 Architecture and planes

55 claims: 23 I · 16 D · 15 U · 1 O

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§3.1**|**The planes (the one list)** (3 I · 1 D · 3 U)||||
|198|Stations, streams, the carousel, the carrier-beacon, relays…|I|station:396-432, daemon:414-427; t/udp_e2e:24|All but relays; cross-host on the live seats by unicast.|
|199|Only the promotion interface (§6.4, §14.5) and receipt shape.|U||No promotion path or receipt log.|
|200|Only the landing bindings (§16). Canticle never becomes control.|I|runner:31, pl/binding:1142-1148; pl/t/inbound:445|Nothing executes or schedules from a frame.|
|201|Who is allowed (the fleet manifest, §10.3) and who is observable…|I|manifest:75-107, listener:725-752; t/listener:37||
|202 MUST NOT|A bridge translates transport and crossing policy and MUST NOT…|U||No relay or ringserver bridge.|
|204|Crossing from binary to ledger is an explicit promotion (§6.4).|U||No promotion exists.|
|204|There is no automatic mirror|**D** owner|pl/journal:74,181-202|The plugin journals every heard payload to disk automatically (24 h default, up to 30 days), and the agent skill tells people to append canticle listen output to heard.jsonl without bound. Admitted: pl/README:175-181 (not as a departure).|
|**§3.2**|**Layers: wire dumb, receptor smart, interface normalized** (2 I · 2 D · 1 U)||||
|208|The wire carries signed bytes and nothing else. It does not…|I|runner:179-184, wire:212-218|runner.send only emits frame bytes.|
|209|the receptor produces the same judgment (§14.2).|I|listener:221-234, records:308-326; fe/listener:561-596; t/wire:152|now_ms is a parameter and nothing random is read; only run and rec_seq differ.|
|210|Sessions see a small, stable surface: a digest, an alarm slot|**D** owner|pl/tools:10-12, pl/ambient-slots:22; fe/src/shim:221-265|frond-ear: hear, pushes, set_canticle_delivery, canticle_custody, no slots. Plugin: seven tools plus conditional digest/alarm slots. Admitted: pl/README:474-475; fe/docs/runbook:850.|
|210|and on-demand listen/atmosphere reads (§14.15, §15)|U||atmosphere is unbuilt; listen/hear exist (line 184 rows).|
|210|No adapter or session surface bypasses the receptor|**D** rfc|__main__:398-402, listener:483-488|canticle listen prints heard text as JSON with no banner, wrapper or local quarantine, and the station README tells Claude Code users to Monitor it so each line becomes a session event. Admitted: README:224 vs README:230; CLAUDE:10-12.|
|**§3.3**|**Components and flow** (6 I · 4 D · 6 U · 1 O)||||
|215|session / sub-agent ── canticle_sing ──▶ publish tool (holds no key)|I|pl/station:1-25, runner:245-256; pl/t/plugin:211|CLI and plugin hold no key; the station process does.|
|216|│ unix socket, peer-authenticated|I|runner:151-166,168-177|Control socket 0600 plus same-uid check on Linux|
|218|per-host canticle daemon|**D** owner|daemon:38-39,175-202|Two processes: canticle station per key (own control socket) and canticle daemon (receptor only; publish lines on its socket are counted and dropped). Admitted: README:445-447; README:64.|
|220|│ sign once, station ring, │ │ cheap checks → verify →|I|station:309-341; t/station:37|Station half.|
|221|│ loop scheduler, 1 Hz beacon │ │ hearer ring → classify →|**D** owner|records:311-387|Receptor half: verify, manifest checks and identity are built; no hearer ring, threshold or judgment step, and landing is the bindings'. Admitted: README:67; README:511.|
|224|LAN multicast (optional, TTL 1)|I|runner:145, daemon:420-422; t/stations:52||
|225|│ unicast ingress │ leased unicast|**D** owner|runner:179-184, __main__:760|No relay, so no ingress or leased unicast. The live path is a third arrow the figure lacks: station → UDP unicast → host daemon. Admitted: README:18 (lists UDP unicast; not flagged).|
|227|relay = membrane (Go/Rust) ── lease: HELLO→COOKIE→LISTEN→RENEW|U|||
|230|other relays (D10: TCP/QUIC; NATS only after S4a)|U|||
|232|ringserver (DataLink write) ──▶ SeedLink v3/v4, DataLink, WebSocket…|U||Proof scripts only.|
|233|harness bindings: OpenClaw plugin (receptor child|**O**|pl/daemon:75-93; pl/t/interop:101|Successor D35/BC-1a: the plugin is a client of the host daemon's socket, not a parent of a receptor child.|
|233|+ next-turn injection with OC-0; no wake in P1|I|pl/index:101-118, pl/oc0-host:16-38; pl/t/plugin:148|Wired only when the host offers the workflow, route and lifecycle APIs|
|233|alarm-only wake from P3 (D25), §16)|U|||
|234|Claude Code (MCP tools, hook additionalContext, channel for alarms)|**D** owner|fe/src/shim:654-669|MCP tools and a channel exist, but the channel carries any allowlisted class; no canticle content goes by hook additionalContext (only the pressure line does). Admitted: fe/docs/runbook:851.|
|235|DNS-SD (mDNS on LAN; DNSSEC unicast zone on WAN)|U||One-shot unicast browse exists (CLI and plugin) without DNSSEC|
|235|= locators only; trust = fleet manifest|I|dns_browse:95-155; t/dns_browse:36|Browse never connects, never adds a key or stream; mismatches are reported.|
|238 SHOULD|PR #44's infographic SHOULD become the informative version of this…|U||No such figure under rfc/ on main.|
|**§3.4**|**Invariants** (12 I · 9 D · 5 U)||||
|244 MUST NOT|A station MUST NOT hold per-listener state|**D** owner|runner:134-135,179-184|Station class holds none. But run_station holds --to unicast destinations, one per listening host, and logs per-destination send errors; the live stations each list four peers. Not dynamic, but it names listeners.|
|244 MUST NOT|and MUST NOT accept messages from listeners|I|runner:144-149,151-166|The station's UDP socket is never bound or read|
|244|Leases live in relays, never in stations|U||No leases anywhere.|
|245|There is no since-token, retransmit request, acknowledgement or…|I|wire:22, runner:82-118|Three frame kinds, all station-to-listener|
|246|No loop, relay, replay, cache|I|station:389-394,405-411; t/station:37||
|246|relay, replay, cache, restart or user interface|U||Relay: none exists.|
|246|replay, cache, restart or user interface may extend|**D** rfc|wire:445-449,384-388; fe/listener:636-650|Beacons have no time window and bseq and δ̂ aren't persisted. After a daemon restart, with the station silent or not yet heard, replayed old beacons set a large δ̂ and replayed expired items are admitted as new. Read, not run; no test.|
|246|cache, restart or user interface may extend an item past|I|listener:648-656, records:567; fe/records:1212-1215; t/records:252|Every view drops at local expiry: daemon tick, snapshot, tap, plugin view, frond-ear…|
|246|restart or user interface may extend an item past its signed…|I|listener:337-347, records:449-450; fe/delivery:1045-1051; t/records:475|Saved retain-until is reused on resurface.|
|247|A repeat of an already-accepted identity tuple is a no-op for every…|I|listener:329-336, records:383-385; fe/listener:760-768; t/records:150|No record, no evidence, no push. #173 keeps it: repeats are counted (#173/listener:645-657)|
|248|The receiver keeps verified raw frames separately from…|U||No raw frame is kept by daemon, plugin or frond-ear (only a…|
|248|and every judgment points back to its source frame|I|records:453-459; fe/records:1189-1195; t/records:261|Identity tuple always|
|249|Heard content never executes|I|tap:117-133, pl/render:80-93; fe/hear:174-178; pl/t/inbound:445|No code reads a payload for meaning, and body_ref is never fetched.|
|249|Heard content never executes, never authorizes a tool call|**D** rfc|pl/binding:1142-1148, pl/render:115-123; fe/hear:152-154|Enforced by words only: banner, wrapper, instructions. Plugin blocks just its own sing after a read. frond-ear pushes into sessions with Bash, Discord and gh and attenuates nothing (§14.12 asks for a structural control). Admitted: fe/docs/runbook:852; pl/README:285-290.|
|249|never authorizes a tool call and never counts as consent|**D** owner|grant:104-129, shape:143-149|canticle shape --display treats a heard, signed display-grant item as the station's consent to show its telemetry. Narrow (signer's own data, strict body, TTL lease), but it is heard content counting as consent.|
|250|A sender cannot cause a receiver to wake, act or change its self-posture.|**D** owner|records:194, pl/config:129-130; fe/delivery:1167-1180|frond-ear: each new item of any class from a wakeKeys station starts a turn (≤ 60 pushes/h). The hop-0 and wake-derived gates trust fields no publish tool stamps. Act / posture: nothing. Station, tap, plugin: no wake path. Admitted: fe/docs/runbook:851.|
|250|Wake is a receiver-local grant (§14.10).|I|pl/config:96-100; fe/src/config:187-201; fe/t/canticle-delivery:1074|Operator config sets the ceiling; the session can only narrow it.|
|251|Relays and bridges forward admitted frames byte-identically and…|U||No relay or bridge exists #162 sings a NEW derived frame at a station (not a bridge), disabled by default|
|252|Missing, expired, filtered or plucked frames never become "quiet"|**D** owner|listener:739-743; fe/listener:1287-1297|presence says EQUIPPED_QUIET when no stream item is fresh, so lost or refused items read as quiet; a test asserts it for over-quota refusals. §8.6 requires that state: the RFC contradicts itself.|
|252|frames never become "quiet", "healthy"|**D** rfc|records:530-553,477; fe/records:588-593|Health is ok unless no datagram came for 30 s, a peer queue dropped, or a clock is skewed. Measured: 99.98 % of datagrams dropped at the socket with daemon and frond-ear health ok; record gap is always unavailable. Admitted: README:505 (gap only). #173 #173/records:613-627 adds socket_drops and datagrams_refused reasons|
|252|never become "quiet", "healthy", "offline"|I|listener:725-733, pl/render:183-190; fe/records:1455-1458; t/listener:50|UNOBSERVABLE / unknown everywhere.|
|252|"offline" or "all clear" (#51 invariant 3)|I|records:52-53, finding:32-35; fe/hear:327-330; t/finding:274|Expiry, pluck and supersession are distinct retract reasons|
|253|Content survives its TTL only through an explicit, typed promotion to the ledger|**D** owner|pl/journal:74, pl/config:171; fe/delivery:148-154|Daemon, tap and frond-ear stores keep no text past expiry. The plugin journals every heard payload 24 h (up to 30 days) with no promotion; frond-ear pushes stay in the transcript; the skill logs listen output to a file. No promotion exists. Admitted: pl/README:175-181,262 (not flagged as a….|
|254|Trust is never inferred from names, DNS, network location, relays…|I|wire:421-456, dns_browse:101-141; fe/listener:684-724; t/dns_browse:52|Only signature + manifest key admit; sender address is never read. #173 queues by source address but admits by signature (#173/intake:33-35)|
|254|(trust from signature and manifest only)|**D** rfc|manifest:131-133, daemon:396-403; fe/src/cli:123-128|The manifest itself is unsigned, so trust really rests on who can write the file; no genesis pin, expiry, serial or reload. Admitted: README:63; README:120-121.|
|255|Regulatory frames change only the receiver's own filters|U||They change nothing at all: no op is parsed.|

### §4 Scopes

32 claims: 10 I · 6 D · 16 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§4.1**|**The scope ladder** (4 I · 3 D · 10 U)||||
|263|trust is Ed25519 plus the fleet manifest at every rung that can land content|**D** rfc|wire:421-456, manifest:127-133|Ed25519 on every frame, loopback included; but the manifest is unsigned. The host socket then carries already-judged records on uid trust alone. Admitted: README:63.|
|263|the scope-2 "pre-shared frond HMAC"|I|wire:212-218||
|267|0 / In-process (one session) / — / harness function calls|I|ids:120|Nothing on the wire for it; no scope code below host.|
|268|1 / Single host, many sessions / host|U||host-scope frames can't go on air: sing() refuses them without…|
|268|peer-authenticated unix socket to the host daemon|I|daemon:350-358,429-463; t/daemon:149|Receive direction only (record v1). SO_PEERCRED uid check, fail closed.|
|268|local config / one receptor daemon per host|I|stations:50-94, daemon:386-394; fe/source:72-84; t/daemon:222|stations.toml + exclusive UDP bind + state lease.|
|269|2 / Single LAN / lan / LAN multicast fast path, or a LAN relay lease|**D** owner|runner:179-184, __main__:760-761|The live LAN path is neither: plain station→daemon UDP unicast (--to), multicast off. Multicast is built but its §11.2 doctor decision isn't; no relay lease.|
|269|mDNS DNS-SD + carrier-beacon / host receptor|U||mDNS is refused (.local) and nothing publishes|
|270|relay lease (the default outside a known wired VLAN)|U||No relay, listen capability or DNSSEC.|
|271 MAY|R-pub / Public lighthouse / public / public-tier relay lease|U||Optional. public is only a scope code a key may be granted.|
|272 MAY|3 / Multi-LAN, relays chained / fleet / relay-to-relay (D10)|U||Optional.|
|273|4 / Cross-trust-domain / — / gateway federation|U||Out of v1; nothing implements it.|
|274|5 / Air-gap / file replay / — / bundle import|U||Out of v1; nothing implements it.|
|276|public "lighthouse" stations are optional in v1|U||Optional; none.|
|276|if run, they are ambient-only, never wake-eligible, carry a declared purpose|**D** rfc|station:278-284, listener:305-308; fe/delivery:1167-1180|Nothing enforces it: a key granted public may sing any granted class with that scope, no purpose needed; the receptor surfaces it and frond-ear's push gate never looks at scope.|
|276|and are served only by public-tier relays|U||No relays|
|278 MUST|Implementations claiming conformance MUST declare their target…|U||Neither README declares a conformance class or target scope|
|**§4.2**|**One lease per host** (2 I · 1 U)||||
|282 SHOULD|At scopes 2, R and 3, a host SHOULD run exactly one listener (the…|I|daemon:414-427, __main__:411-418; fe/source:72-84; t/daemon:229|Daemon binds without SO_REUSEADDR; a second daemon or canticle listen fails.|
|282 SHOULD|and fan heard frames out to local sessions over the host binding|I|daemon:231-246,367-373; fe/record-client:69-91; t/daemon:262||
|282 MUST NOT|It MUST NOT open one relay lease per session|U||No relay leases exist.|
|**§4.3**|**The scope field** (4 I · 3 D · 5 U)||||
|286|Every ITEM carries a signed scope (§9.6, key 13).|I|wire:260,300; t/wire:152||
|286|It declares the audience, and it is enforced at every tier.|**D** rfc|station:281-286, listener:301-308; fe/delivery:1167-1180|Enforced: grant at the station and receptor, narrower-than-binding at the receptor, host never sent. Not: relays (none), lan on a unicast --to to any address, and bindings ignore scope (frond-ear pushes and room output).|
|290|0 / host / Never leaves the host.|I|station:285-286, listener:301-304; fe/listener:701-712; t/station:472|It is never sent at all|
|290 MUST|Relays MUST drop host frames.|U||No relays.|
|290 MUST NOT|LAN senders MUST NOT multicast them.|I|station:285-286, runner:139-140; t/station:472||
|291|1 / lan / LAN multicast and LAN-tier relays only.|**D** rfc|runner:179-184, station:270|lan is the default scope of every sing, and run_station sends it to any --to address, on the LAN or not; the receptor always judges itself lan-bound, so it accepts it wherever it came from.|
|291 MUST|Fleet and public relays MUST drop lan frames.|U||No relays.|
|292|Leasing a stream whose audience is not public requires a listen…|U||No leases, audiences or capabilities.|
|292|Relays; receivers check scope ≤ key capability scope.|**D** code|listener:305-308, manifest:44; fe/listener:713-724|Receivers check set membership, not ≤: a key granted only {public} can't sing lan. §4.3 says ≤ here and 'scopes its key holds' on line 295; §10.3 lists a set. Stricter and clearer.|
|293|Public relays accept only public, never wake-eligible classes…|U||No relays.|
|295 MUST NOT|A frame's scope MUST NOT exceed the scopes its key holds in the…|I|station:281-282, listener:305-308; fe/listener:713-724; t/station:461|Sender: NotGranted before a seq is used.|
|295 MUST NOT|a relay MUST NOT forward a frame further because it is "strong"|U||No relay, no strength.|

### §5 Stations, streams, identity and naming

56 claims: 35 I · 6 D · 15 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§5.1**|**Station identity** (6 I · 1 U)||||
|303|A station's identity is its Ed25519 public key|I|wire:421-424, manifest:95-104; fe/manifest:117-123; t/wire:152|A frame is verified only under the key its header key-id resolves to (vectors…|
|304|The key-id is SHA-256(public_key)[0:8]|I|ids:15-19; fe/ids:10-17; t/manifest:104|frond-ear's test recomputes every vector key-id independently.|
|304 MUST|Receivers MUST resolve it to a full public key through the manifest|I|wire:421-424, listener:226; fe/listener:580-585; t/wire:152||
|304 MUST NOT|MUST NOT accept a public key carried inline in a frame|I|wire:421-424|No frame field carries a key; the only resolver is Manifest.resolve.|
|304 MUST|MUST reject manifests in which two keys share a key-id|I|manifest:88-89,215-218; fe/manifest:103-107; t/manifest:114||
|305|One key is one station.|I|__main__:149-156, manifest:215-218|The station takes an exclusive lock on ‹key file›.lease.|
|305 MAY|A principal (§10.3) MAY run many stations|U||Optional.|
|**§5.2**|**Epoch** (7 I · 1 D · 1 U)||||
|311|epoch is a u32 carried in every frame.|I|wire:297,315; fe/wire:298; t/wire:152||
|311 MUST|It MUST strictly increase whenever the station loses its sequence…|I|station:105-140, __main__:157; t/station:433|The CLI always uses the locked counter.|
|312 SHOULD|RECOMMENDED: persist a counter and, at every start, take…|I|station:114-140; t/station:433||
|313 MAY|MAY use floor(unix_seconds) at start only if no two starts can fall…|I|station:163-165|Library fallback only; its condition is a comment, not a check. The CLI never uses it.|
|313|reuse seq, which receivers correctly record as equivocation|I|listener:324-328, records:355-356; fe/listener:748-757; t/records:222|The daemon also quarantines the key|
|314|a lower epoch for a key than the highest it has seen within the class maximum TTL|**D** rfc|listener:236-240,315-318; fe/listener:605-611|The highest epoch ever heard, persisted, with no time bound; epoch_seen_at is saved and never read. A station that once used a far-future epoch and lost its counter is refused until listener state is deleted. No class-max window; no departure note.|
|314 MUST|MUST record evidence epoch-regression|I|listener:238-240,583-585; fe/listener:606-610; t/records:238|In record v1 it is the frame's reason epoch_regression (or the beacon counter).|
|314 MUST NOT|MUST NOT let the lower epoch supersede anything|I|listener:313-318,555-586; fe/listener:741; t/records:238|Receptor mode admits it to dedup only; otherwise it is dropped.|
|315|Two epochs of one key that both produce new seq values|U||Nothing measures two live epochs.|
|**§5.3**|**Human names** (4 I · 1 D)||||
|319|are bound to keys only by the fleet manifest|I|listener:203-209, records:460; fe/records:1229; t/finding:328|frond-ear and the plugin take the name from the daemon's record.|
|319|DNS-SD instance names and TXT records are locators|I|dns_browse:98-108; t/dns_browse:46|Browse is a one-shot CLI; nothing it finds reaches the listener.|
|319|TXT k= is a cross-check hint, and a mismatch raises an alert, never…|I|dns_browse:133-150, pl/discover:104-122; t/dns_browse:52|The alert is only a mismatches entry in the browse output.|
|319|Beacons carry no name.|I|wire:197-209; fe/wire:399-410|No name field in the key table.|
|323|Station names follow v0.1's grammar [a-z][a-z0-9-]{0,30}|**D** rfc|ids:9-11, manifest:50-53; fe/manifest:141-146|Station and plugin enforce it. frond-ear's manifest loader and record reader accept any string as a station name (the banner sanitises it). Its tune config does use the grammar (config:262).|
|**§5.4**|**Streams and stream_id** (9 I · 3 D · 9 U)||||
|327|[a-z][a-z0-9-]{0,30} segments joined by ., at most 4 segments|I|ids:9-12,65-68; fe/ids:6-26; t/wire:144|Same expression in ids.py, frond-ear ids.ts and plugin records:14-16.|
|327|at most 4 segments and 64 bytes|**D** rfc|ids:66, pl/records:28-30; fe/ids:20|Enforced for stream names; not in tune patterns: frond-ear's two tune regexes and the plugin's STREAM_PATTERN accept up to 127 bytes, which can never match (silent deafness). The station has no 64-byte test.|
|327|Stream names are opaque tags.|**D** neither|grant:29-30,85-87|display and beacon pick how a body is parsed and acted on (display grants #137, typed beacons #142). The RFC reserves neither; README:333 describes them but not as a departure.|
|327 MUST NOT|The protocol MUST NOT type streams as work versus body|I|station:41-48|A stream has a class, TTLs, a budget and a lens id; no work/body or voice type exists.|
|328|Reserved prefixes carry provenance or protocol role, never payload…|U||Nothing reserves any of them: check_stream_name treats every…|
|332|root / The root mark (§8.5).|I|listener:467-468,715-723; fe/listener:998; t/listener:37|Presence reads stream root with state_key root, whatever the class: a key granted…|
|333|lens.‹name› / Aspect streams (§17).|U||No code treats lens. specially|
|334|control / Control-class frames (§6.2).|U||Control frames aren't implemented.|
|335 MUST NOT|Test traffic. MUST NOT be emitted with scope fleet or public.|U||sing() checks grants and host scope only; no code knows x-test.|
|336|x-human. / Human-originated content|U||Nothing marks, checks or renders human-originated streams.|
|337|relay. / Relay-originated streams|U||No relay exists, and no station refuses the prefix.|
|339|stream_id is the u32 given by the first 4 bytes, big-endian|I|ids:71-75, pl/records:58-62; fe/ids:29-36; t/wire:144||
|340 MUST|A station MUST refuse to start, or to accept a configuration|I|station:170-172, ids:78-86; fe/ids:39-52; t/station:235||
|340 MUST NOT|It MUST NOT rehash, salt or renumber; the remedy is to rename a…|I|ids:83-84; fe/ids:44-48; t/station:235||
|341|Names do not travel in frames.|I|wire:164-209|Frames carry the u32 only. No test.|
|341|A tuner learns them from the manifest (fleet streams)|I|listener:207-209, manifest:55; fe/listener:530-532; t/records:130|frond-ear (host-daemon source) and the plugin read the name from record v1.|
|341|DNS-SD TXT streams= (public streams only, §13.2) or local… ‖ An id without a known name is shown as hex|U×2||TXT streams= is only compared with the manifest's… No view shows unnamed streams.|
|341 MUST NOT|and MUST NOT be interpreted.|I|listener:449-453, records:359-363; fe/records:1205-1211; t/records:157|ringbuffer_only, reason unnamed_stream.|
|342 MUST NOT|it MUST NOT surface the stream under either name|**D** owner|manifest:55, ids:83-84; fe/manifest:60|There is one name source; two names for one id make the whole manifest fail to load (the host goes deaf), instead of one stream being held. Stronger per stream, coarser in effect. Admitted: README:496.|
|342 MUST|MUST record evidence stream-name-ambiguous|U||Never emitted, in any implementation.|
|**§5.5**|**Sequence numbers** (4 I · 1 U)||||
|346|seq is a u64 per (key-id, epoch, stream_id).|I|wire:298,154-155; fe/listener:742; t/wire:152||
|346 MUST NOT|It starts at 1, strictly increases, and MUST NOT be reused within…|I|station:308-314,353-358; t/station:123||
|347|ITEM and PLUCK frames of a stream share one sequence space.|I|station:309,354-358; t/station:150||
|348|A gap in seq does not by itself mean loss|I|records:477; fe/delivery:2283-2318; fe/t/canticle-delivery:254|No receiver infers loss: record v1 gap is always "unavailable" (README:505) and…|
|348 MAY|Receivers MAY use gaps between head_seq (§8.2) and what they heard|U||Optional.|
|**§5.6**|**The identity tuple** (4 I)||||
|352|(key-id, epoch, stream_id, seq) identifies a frame.|I|wire:149-155, records:156-160; fe/listener:742; t/records:130||
|352|It is the dedup key (§7.4), the pluck target (§7.7)|I|listener:319-336,376-378; fe/listener:742-767; t/wire:152||
|352|and the lineage reference (§14.11)|I|wire:286-292, records:472-473; fe/receptor:190-197|Read and reported only: Station.sing on main cannot set derived_from or root. #162 #162/station:348 stamps derived_from/root on a derived proposal (disabled by default)|
|352|the tuple exists, and it expires with the frame|I|listener:368-370,619-634; t/listener:160|Dropped at local expiry + 5 s.|
|**§5.7**|**Lens** (1 I · 1 D · 3 U)||||
|356|A lens is a stream attribute, not a frame field.|**D** neither|station:312, wire:183-184; fe/wire:315|Every ITEM of a stream with a lens signs key 18 lens, as §9.6 (line 829) and §17.3 require. The RFC contradicts itself; the plugin also filters deliveries by that frame field (candidates:83).|
|356|An aspect stream is named lens.‹name›|U||StreamConfig.lens may sit on any name, and a lens.|
|356|its lens id appears in the beacon's stream entry (§9.8)|I|station:471-476, wire:120-123; fe/wire:376; t/wire:103|Library only: canticle station --stream cannot set a lens id.|
|356, MAY|and in the aspect item body (§17.3) ‖ Public lenses MAY also appear as DNS-SD subtypes (§13.2).|U×2||Content type 4 is only a name in the registry (ids:127). Optional; subtype browse is not implemented.|

### §6 Frame classes and staleness

91 claims: 60 I · 10 D · 14 U · 7 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§6.2**|**Class registry** (17 I · 4 D · 5 U)||||
|377 dflt|Hop limit / Default scope|**D** code|station:268-271, __main__:780|No class table has this column; every sing defaults to lan. Rows 3-8 say fleet, and keygen grants only host,lan. Narrower fails safe, but a finding sung without --scope fleet stays on the LAN.|
|377|Wake-eligible (v1) / Feeds accord|**D** owner|ids:98; fe/delivery:1168-1180|Station, tap and plugin wake nothing. frond-ear pushes (mode=silent-wake) any class from a key on wakeKeys, by a frond decision (fe#65, bc#100 to amend); no code reads wake_eligible. Owners must choose. Admitted: fe/docs/runbook:851.|
|377|Feeds accord / Capability needed|U||Accord column: no accord exists, and neither class table has…|
|377|Capability needed|I|manifest:41,115; fe/listener:690-699; t/station:461||
|379 dflt|1 / chatter / ambient / — / 60 s / 300 s / 5 000 / 2|I|ids:104; fe/ids:91; t/station:63|— for state_key is not a ban in code: keyed chatter is accepted (vector…|
|380 dflt|2 / ambient / ambient (weather) / — / 300 s / 3 600 s / 10 000 / 2|I|ids:105; fe/ids:92; fe/t/canticle-listener:265|The TTL pair is tested through the derived mark factor (14)|
|381 dflt|3 / live-state / live-state / REQUIRED / 180 s / 900 s / 5 000 / 2|I|ids:106; fe/ids:93; t/station:78|Hop limit 2 has no test.|
|382 dflt|4 / advisory / live-state / OPTIONAL / 900 s / 3 600 s / 5 000 / 1|I|ids:107; fe/ids:94; t/listener:400|TTL pair tested through the mark factor.|
|383 dflt|5 / finding-ref / finding (doorbell) / OPTIONAL / 900 s / 86 400 s…|I|ids:108; fe/ids:95; fe/t/canticle-listener:265||
|384 dflt|6 / regulatory / chemokine / REQUIRED / 600 s / 3 600 s / 5 000 / 0|I|ids:109; fe/ids:96; t/listener:400|Table numbers only|
|384|quarantine for quarantine ops|U||No quarantine capability and no op parsing: a key granted…|
|385 dflt|7 / alarm / alert / REQUIRED (alarm id) / 900 s / 3 600 s / 2 000 /…|I|ids:110; fe/ids:97; t/listener:198|Any state_key passes; nothing checks that it is an alarm id.|
|386 dflt|8 / control / control / REQUIRED (op) / 600 s / 3 600 s / 1 000 / 0|I|ids:111; fe/ids:98; t/listener:400|Table numbers only|
|386|n/a / control (root-delegated)|U||Any manifest entry may list control|
|387 dflt|3 600 s (horizon ≤ 24 h by re-issue) / 30 000 / 0 / lan|I|ids:112, station:323-328; fe/ids:99; t/station:192|The 24 h cap (STATION_HARD_CAP_S) has no test.|
|387|9 / root / live-state / REQUIRED ("root")|**D** rfc|wire:283-285, station:295-296; fe/wire:283-284|Any non-empty state_key is accepted for class root; only presence looks for root, and it ignores the class.|
|391|A stream's default TTL is configured no higher than|I|station:200-207; t/station:78||
|391|manifest class max, station hard cap)|U||Manifest entries carry no class max and there is no manifest…|
|391|an item's TTL may only be lower than its stream default|I|station:305; t/station:63||
|391 dflt|Stream max_ttl defaults to 300 s|I|station:35,46; t/station:78|The CLI also raises max_ttl to an asked-for default (facts:live-state:900 gives…|
|391 dflt|the station hard cap is 24 h|I|station:34,200|No test.|
|391|Receivers clamp expires_at to issued_at + min(class max, manifest class max)|**D** rfc|wire:379-388; fe/wire:430-434|Clamps to the class max only; README:16 states that rule without calling it a departure. Admitted: README:16.|
|391|the root mark persists by re-issue until UNEQUIP, §7.9|I|station:315-320,405-411; t/station:192|Only while keep_on_air runs, at most 24 h|
|392|A hop limit of 0 means the class is never re-sung.|I|listener:309-312; fe/listener:725-737; t/listener:198|Enforced at receivers.|
|392|It may only be bridged byte-identically (§14.11).|U||No bridge or relay exists.|
|393 MUST|Unknown class codes MUST be treated as ringbuffer_only and never…|I|listener:396-398, records:342-344; fe/listener:861-864; t/records:163|With a loaded manifest it always ends as capability_exceeded / ringbuffer_only…|
|**§6.3**|**Staleness requirements** (7 I · 3 D · 1 ?)||||
|397|An item counts as current from first verification until its local…|I|listener:464,648-654; fe/records:1422-1426; t/listener:61|Except live-state items in warm-up (rule 4). Expiry is applied on tick (250 ms).|
|397 MUST|At local expiry it MUST lose current-state authority in every…|I|records:514-515, tap:223-228; fe/records:1422-1426; t/records:252|Receptor, tap, plugin, shape/grant/beacon views and hear all drop it.|
|398 MUST|regulatory, alarm and control MUST carry a state_key|I|station:295-296, wire:283-285; fe/wire:283-284; t/wire:152||
|398|Newer items supersede older ones with the same (key-id, stream_id…|I|listener:399-445, station:315-320; fe/listener:865-955; t/station:100||
|399 MUST NOT|exceeds stale_after[class] MUST NOT be wake-eligible|**D** rfc|records:476; fe/delivery:253-261|No stale_after gate anywhere. Station, tap and plugin never wake. frond-ear's immediate uses one maxAgeMs (30 s, up to 120 s) for every class, and its report pushes older records anyway, marked late:. Admitted: fe/docs/runbook:851.|
|399 MUST|MUST be surfaced with an aged marker in the banner|**D** rfc|tap:142-174, pl/render:100-125; fe/hear:114-116|Only frond-ear marks it, and from the age now, not at first hearing (records:1432), so it over-marks. tap and the plugin show age= only.|
|399 dflt|live-state 60 s, alarm 120 s, advisory 300 s|I|fe/hear:16-21; fe/t/canticle-hear:130|frond-ear only, for the marker. The station, tap and plugin have no such table.|
|400|every live-state key is UNKNOWN until one beacon from the station|**D** owner|listener:454-463,539-546; fe/listener:968-980|Class live-state only; root, regulatory, alarm and control, which rule 2 counts as live-state, land at once. Without an advertised loop the wait is 6.67 s. The RFC should say class or family (holding alarms would delay them).|
|400 MUST NOT|An older item heard during warm-up MUST NOT land as current|I|listener:399-428,588-608; fe/t/canticle-listener:688; t/listener:265||
|401|No missing, expired, filtered, plucked or unsupported frame may…|I|listener:725-743, records:52-53; fe/hear:300-306; t/listener:50|Presence says UNOBSERVABLE or unknown, never offline; retract reasons stay distinct|
|401|"quiet", "negative", "absent", "unwell"|**?**|listener:739-743; fe/listener:1297; t/listener:37|"quiet": §8.6 (line 707) itself defines EQUIPPED_QUIET as no fresh stream item, so a missing frame becomes quiet, even when the beacon says live › 0 (the code ignores live). The RFC must settle it; D-owner of §8.6.|
|**§6.4**|**Findings and promotion to the ledger** (4 I · 1 D · 3 U · 2 ?)||||
|405|it appears as a finding-ref item: a doorbell carrying the ledger object's digest and location|**D** rfc|station:289-296, pl/config:53|Works with --body-ref, but nothing requires one: a finding-ref with only text is signed. The plugin offers class finding-ref and can send text only, so every one it sings lacks the digest and location.|
|405|optionally with a short summary body|I|runner:97-102, station:289-294; t/finding:184||
|405|a probe or a watcher also states it as a keyed advisory with a…|I|runner:70-79; t/finding:176||
|405|The ledger object stays the finding of record.|**?**||Operator practice: what counts as the record isn't decided in these repos.|
|406, MUST NOT|is an explicit, typed act by an untainted principal or a human ‖ An LLM session MUST NOT promote content it heard|U×2||No promotion path, type or digest link exists anywhere. Nothing stops a session that heard content from writing it to…|
|407|Frames carry training_eligible = false by default (flag bit 3…|I|station:272,311|flags default to 0 and the socket can't set them. No test.|
|407|Receivers cannot set it.|I|wire:293-295|It is inside the signed map and no receiver writes it. Nothing contrary.|
|407 MUST NOT|MUST NOT be used as model training data in this version|**?**||Operator practice; no code here could show it.|
|408|What memory-adjacent frames may carry is bounded by #31 c20|U||No content policy: any body of up to about 980 bytes is signed.|
|**§6.5**|**Conflict** (2 I)||||
|412|Contradictory items from different stations coexist as…|I|listener:441-445,464; fe/listener:938-944; t/finding:274|Nothing picks a winner.|
|412|it never lets one station override another|I|listener:400,441-442; fe/listener:866; t/finding:274|Marks are per key.|
|**§6.6**|**Disposition frames (#51)** (1 I · 1 U · 1 ?)||||
|416|Short-TTL disposition frames ("where I am") are ordinary items on…|U||Nothing sings or reads content type 9.|
|416|with the placeholder content type 9|I|ids:132|Registry name only; record v1 names it. No schema, no test.|
|416|This RFC makes Emeric's ten invariants normative for every class|**?**|station:309-310, listener:333-336|Pointer to nine listed rules (I-3, I-4, I-9, clock, unknown schema, promotion, local policy, no acks, pluck), not ten; say which is the tenth. Most have their own rows.|
|**§6.7**|**Findings sung live** (29 I · 2 D · 5 U · 3 ?)||||
|420|sings a finding: an advisory item (§6.2) with content type 11…|I|runner:70-79, finding:27-29; t/finding:176|canticle sing --finding and the socket's finding field.|
|424|; incident: the item's state_key, byte for byte|I|finding:30-37,54-71; t/finding:131||
|429|; severity, in CAP's words: present exactly when status is "open"|I|finding:34,67-70; t/finding:114||
|432|; any other unsigned key: ignored (fail quiet, below)|**D** owner|finding:92-103, cbor:101-107|CDDL says any; a float, tag, bad nested key, depth over 4 or over 32 entries under an ignored key makes the whole body opaque. Admitted in README:75 and the probe profile. Admitted: README:75.|
|436|A finding is keyed: its state_key equals incident.|I|runner:76-78, finding:116-118; t/finding:176||
|436|Every text field is one line, with no control character (Unicode…|I|finding:49-63; t/finding:131||
|436|Evidence goes by reference, in the item's own body_ref (key 9; the…|I|runner:55-67,101-104; t/finding:184|Optional in code; nothing can check that it points at a durable receipt.|
|436|Receivers do not fetch it on landing (§9.6, §14.12).|I|tap:129-132, pl/render:89-91; fe/hear:174-178; fe/t/canticle-hear:105|No receiver has any fetch code; every banner says "not fetched".|
|437|Receivers ignore unsigned integer keys other than 1-7.|I|finding:99-103; t/finding:152|Within frame v2's CBOR subset (see line 432).|
|437|A change that old receivers must not misread takes a new content type.|**?**||A rule for future amendments; no code can show it.|
|437|or that rides a class other than advisory, is not a finding|I|finding:107-119, tap:160-164; fe/hear:169-173; t/finding:162|Malformed body, wrong incident, wrong class: opaque, no status or severity.|
|438|subject and voice are what the signer says. They are never trust…|I|finding:135-145; t/finding:328|The name compared is the manifest's; nothing else reads the two fields.|
|438|A receiver attributes a finding to its signing station and that…|I|tap:142-164; fe/hear:122-124; t/finding:328||
|438|that station's principal, from the manifest (§14.13)|U||The spike manifest has no principals: the banner reads…|
|438 MUST NOT|It MUST NOT present a finding as the subject's own voice unless…|I|finding:135-145, tap:109-114; t/finding:346|tap. frond-ear and the plugin present no voice at all.|
|438|or its manifest principal once the manifest carries one (§14.18.8)|U||attribute() compares the station name only|
|438|A self finding that names another subject is the signer's…|I|finding:143-145, tap:101-106; t/finding:346||
|438 MAY|A receiver MAY add one host-authored banner line for a finding.|I|tap:109-114,160-162; t/finding:328|tap only; frond-ear and the plugin add none.|
|438|That line carries only the words of status and severity and the…|I|tap:101-114; t/finding:328|Plus a fixed sentence per voice.|
|438|the station's own text stays inside the untrusted-content wrapper…|I|tap:117-133; fe/hear:130; t/finding:370|tap.|
|439|status and severity are words from closed sets.|I|finding:32-35,64-66; t/finding:114||
|439 MUST NOT|Receivers MUST NOT map them to numbers, intensity, salience or wake|I|tap:109-114|Only tap reads them, and prints them. Nothing contrary exists; no test.|
|439|advisory is not wake-eligible in v1 (§6.2)|**D** owner|ids:107; fe/delivery:1168-1180|frond-ear pushes advisories from wakeKeys stations as mode=silent-wake (its own test asserts class=advisory). A finding so pushed wakes the session with its text not shown. See line 377. Admitted: fe/docs/runbook:851.|
|439|No word means "fine", and an absent severity is not a value (I-9).|I|finding:33-34,67-70; t/finding:114||
|440|an incident is resolved only by a newer item from the same key|I|listener:399-445; t/finding:274|Through supersession only: no receiver keeps an incident's state, so each reader must…|
|440|It supersedes the open item and stops its loop at once (§7.8).|I|station:315-320; t/finding:256||
|440|ended says that the signer stopped watching without seeing the…|I|finding:33; t/finding:114|Accepted and shown as its own word; nothing maps it to resolved.|
|440 MUST NOT|Silence, expiry, a pluck, a lapsed refresh, a gap and another…|I|records:52-53, tap:465-468; t/finding:274|Retracts carry expired, plucked or superseded, never resolved, and no code infers a…|
|440|and reads as lapsed, not resolved.|I|records:514-515, tap:465-468|tap prints [canticle:withdrawn] ... reason=expired|
|441|Stations that see the same incident use the same incident.|**?**||A convention for singers (probe profile); no code relates two stations' incidents.|
|441|superseded only by that station (§6.5, §7.8)|I|listener:400,441-445; fe/listener:938-944; t/finding:274||
|441 MAY|A receiver MAY group them by incident ‖ it counts signers, never items or repeats (§10.7 R-ACC-1)|U×2||Optional; nobody groups. Nothing counts observers of an incident.|
|442|body_ref only, content type 8 (§9.12), and no state_key|I|station:289-294; t/finding:191|Default shape, not enforced: a keyed finding-ref, or one with another ctype, is still…|
|442|A doorbell keyed by the incident would change that key's class…|I|station:299-304, listener:415-422; fe/listener:882-898; t/station:110||
|443 MUST NOT|A probe or a watcher MUST NOT sing alarm|I|runner:28-31,87-89; t/station:496|The control socket refuses alarm for everyone, whatever the key holds.|
|443 MUST NOT|its key MUST NOT be granted alarm in the manifest (§10.4)|U||Nothing marks a key as a probe's: keygen and manifest verify…|
|443|an alarm from such a key then fails the capability check at every…|I|listener:298-300; fe/listener:690-699; t/records:178||
|443|Alarms need a human-held key (D14)|**?**||Key custody: no code or manifest field shows who holds a key. Ask the manifest's owner.|

### §7 Carousel semantics

223 claims: 167 I · 18 D · 37 U · 1 O

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§7.1**|**The station ring** (12 I · 1 U)||||
|455|Each stream has a station ring: its live set, ordered by seq.|I|station:94-98,373; t/station:258|dict seq -› frame, inserted in seq order|
|456|Retention is min(depth, TTL)|I|station:369-372,389-394; t/station:229||
|456|Depth is station-private.|I|station:471-476|Nothing in the beacon entry carries depth. No test.|
|456 dflt|Default depth [PROPOSED DEFAULT]: 256 items per stream.|I|station:31,150|Constructor default; the CLI has no flag for it. No test of 256 itself.|
|457|An item pushed out by depth before it expires stops looping.|I|station:369-372; t/station:229|Eviction also ends the item's keep-on-air chain, and hush() then refuses it ("no live…|
|457|receivers that already hold it keep it until local expiry|I|station:369-372, listener:648-654|Eviction sends nothing; a receiver drops only on local expiry, pluck or supersede.|
|458|Depth counts ITEMs only. A PLUCK is a tombstone|I|station:369-372; t/station:213||
|458 MUST|the station MUST keep it looping until its target's expiry|I|station:354-361,396-432; t/station:150|Within one process only: the ring is not persisted, so a station restart drops every…|
|458 MUST NOT|MUST NOT evict it for depth|I|station:369-372; t/station:213||
|458 MAY|A station MAY cap live PLUCKs per stream (default: depth)|I|station:351-352; t/station:213||
|458 MUST|at the cap it MUST refuse the hush and say so, never drop an…|I|station:351-352; t/station:213||
|459|The station ring is the loop source.|I|station:403-432; t/station:37||
|459|The hearer ring (§14.4) is a separate cache on the receiving side.|U||The daemon keeps dedup digests and surfaced record fields, no…|
|**§7.2**|**Sing, sign once, loop byte-identically** (7 I)||||
|465|The station assigns epoch, seq, issued_at (its clock, ms)|I|station:309-314; t/station:37||
|465|expires_at = issued_at + effective TTL (§15.4)|I|station:305,309-310; t/station:63||
|466|It encodes and signs the frame once (§9).|I|station:313,321; t/station:37||
|467|It transmits the frame immediately, then as a burst (§7.6), then on…|I|station:377,412-432; t/station:37|The control handler wakes the send loop, so the first copy goes at once.|
|469 MUST|Every transmission of the item MUST carry exactly the same bytes.|I|station:434-435; t/station:37||
|469 MUST NOT|A station MUST NOT re-encode or re-sign a looped item.|I|station:434-439; t/station:37|_send only appends the stored bytes|
|469|A second, different byte string under the same identity tuple is an…|I|listener:324-328, records:355-356; fe/listener:748-759; t/records:222|frond-ear's embedded listener records evidence but does not quarantine (§10.8).|
|**§7.3**|**Absolute expiry** (4 I · 2 U)||||
|473|It is fixed at sing time and never changes.|I|station:309-313,71-91; t/station:37||
|474 MUST|A station MUST stop transmitting an item when its remaining life…|I|station:26,389-399; t/station:37|poll() expires before sending; bursts past the margin are never scheduled (:377).|
|475 MAY|A station MAY persist its live set across restart. ‖ it resumes looping the original bytes with their original expiry|U×2||Optional, not taken. Only the epoch counter is stored No live set is persisted.|
|475 MUST|if it cannot also persist seq, it MUST bump the epoch for new items|I|station:105-140, __main__:157; t/station:433|The CLI takes max(prev+1, unix s) from a locked, fsynced file at every start.|
|476|Remaining life never resets (I-3).|I|station:309-313, wire:368-388; t/station:37||
|**§7.4**|**Receiver deduplication** (38 I · 5 D · 1 U)||||
|480|The dedup key is the identity tuple (key-id, epoch, stream_id, seq).|I|wire:149-156, listener:319-321; fe/listener:742-744; t/wire:152||
|481|A repeat of an accepted tuple with identical bytes is a benign…|I|listener:329-336, records:383-385; fe/listener:760-768; t/records:150|A repeat only refreshes per-stream presence and a copies counter. #173 canticle/intake.py drops exact copies before verify, still counted duplicate and noted for presence (listener:646-657)|
|481 MUST NOT|It is not a replay attack and MUST NOT be reported as one.|I|records:383-385, listener:333-336; t/records:150||
|482|A tuple heard with different bytes is an equivocation (§10.8).|I|listener:324-328,565-569; fe/listener:748-759; t/records:222||
|483|A frame whose local expiry (§14.6.3) has passed is dropped as expired.|**D** neither|wire:445-449, listener:619-626; fe/wire:546-549|parse tests expires_eff + current δ̂ without the first-hearing term. When δ̂ rises more than 5 s after admission, a copy of an expired tuple whose dedup entry has gone passes and is NEW again; the cited test relies on it. RFC should say what outlives the entry.|
|483|This is what a real replay attack looks like, and it needs no replay table.|**D** neither|listener:619-626, wire:384-388|No replay table is kept, but it holds only while δ̂ is steady: first beacon after a first hearing, or a station clock stepped back, reopens the window for unkeyed items. frond-ear tombstones lapse at the same time.|
|484 MUST|Dedup entries MUST be retained until local expiry plus 5 s skew and…|I|listener:34,368-370; fe/listener:818-825; t/listener:700|Local expiry is frozen at first hearing with the δ̂ of that moment, and never moved.|
|484 MUST NOT|MUST NOT be evicted earlier under capacity pressure|I|listener:499-503,610-617; fe/listener:1171-1185; t/listener:160|Only entries past their retain time are deleted.|
|484 MUST NOT|The same holds for sticky-pluck and supersession marks.|I|listener:627-644; fe/listener:1198-1227; t/listener:348||
|485|Capacity is enforced per key, at admission, instead.|I|listener:359-366,499-503; fe/listener:802-816; t/listener:160||
|485|new tuples from that key are refused with evidence over-quota|I|listener:359-362, records:352-354; fe/listener:802-812; t/listener:160||
|485|(never landed, never wake-eligible) until its own entries expire|I|listener:499-503, records:352-354; t/records:191|Record is over_quota / drop, no body. Nothing wakes in the daemon.|
|485|The store never fails closed as a whole: a flooding key locks out…|I|listener:493-503; t/listener:160|True of the dedup store. #173 canticle/intake.py queues per key, stream and source before verify and save, so it extends this to the receive path|
|486 dflt|size the store at Σ(rate × TTL) over tuned streams|**D** rfc|listener:155, daemon:405-406; fe/listener:333|Fixed 100 000 entries; the daemon passes no other value. At that size the report predicts about 450 MB and a 22 MB state file rewritten per new item.|
|486 dflt|a per-key quota of max(256, 4 × the live count that key's beacon advertises)|**D** neither|listener:493-497; fe/listener:1039-1045|Equal share of 100 000 (33 333 with three keys), in both listeners. The RFC's rule lets a key raise its own quota: live is a u32 the key chooses, with no ceiling, against the bound claimed in the next bullet. Admitted: rfc/0001-binary-canticle:486 (the RFC itself)….|
|486|The floor lets a key that is idle, or has not beaconed yet, land…|I|listener:495-497; t/listener:160|No 256 floor (only 1), but the equal share does not depend on a beacon, so an idle…|
|486|the spike gives each manifest key an equal share of the store|I|listener:493-497; fe/listener:1039-1045; t/listener:400||
|487 MUST NOT|A granted key, misbehaving or compromised, must not grow receiver…|I|listener:184-193,531-537; fe/listener:1036-1117; t/listener:303||
|488|they are counted per key separately from dedup entries, against…|I|listener:188,511-529; fe/listener:1074-1094; t/listener:348||
|488|while the key already holds its limit of marks is refused…|I|listener:363-366,339-342; fe/listener:813-816; t/listener:348||
|488|a new value for a key already marked needs no new mark|I|listener:505-509; fe/listener:1054-1062; t/listener:465||
|488|Marks are never evicted early.|I|listener:637-644; fe/listener:1216-1228; t/listener:348||
|488|Like every admission refusal, over-quota and pluck-mismatch are…|I|listener:313-318,349-367; fe/listener:739-817; t/listener:710||
|488|a refused frame in a higher epoch does not advance the key's epoch|I|listener:317,367; fe/listener:739-741; t/listener:644||
|489 dflt|among the classes the key is granted, since a mark lasts about that…|I|listener:41-43,511-521; fe/listener:53-58; t/listener:400||
|489 dflt|with that factor capped at the largest one among keyed classes (#67)|I|listener:50; fe/listener:66-68; t/listener:400||
|489|The factors are 7 for chatter and live-state, 6 for advisory and…|I|listener:41-50, ids:101-114; fe/listener:53-68; t/listener:400||
|489|then always fits, in every class but ambient and finding-ref|I|listener:511-521; fe/listener:1074-1087; t/listener:373|Test covers live-state at the 256 quota only.|
|489|a key minting new keys in them fits up to 8/14 and 8/98 of its…|I|listener:50,521; t/listener:416|Follows from the cap; the test shows the cap, not the fractions.|
|489|3 266 634 at the spike's default share of 33 333, against 266 664…|I|listener:493-497,521; t/listener:400||
|489|summed over keys, marks stay within 8 × the sum of the keys' dedup…|I|listener:511-521; fe/t/canticle-listener:346; t/listener:434|Including the exceptions the RFC lists (per-key override, more keys than slots).|
|489|A receiver-wide mark or byte budget would be a separate rule (#67).|U||None in either listener.|
|489|A state_key is at most 32 bytes (§9.6), so the count bounds the…|I|wire:283,241-246; fe/wire:282|_tstr(state_key, 1..32) at parse. No test of the 33-byte case found in test_wire.|
|489|State saved under a larger limit loads whole, since marks are never…|I|listener:705-711; fe/listener:490-521; t/listener:490||
|489|such a key opens no new mark until it is back under its limit|I|listener:523-529; fe/listener:1090-1094; t/listener:490||
|489|A key that churns keys with shorter TTLs needs a larger limit.|I|listener:157,517-518; t/listener:348|per_key_mark_quota exists in the library only|
|490|Sticky-pluck marks share their PLUCK's dedup entry and its…|I|listener:368-378,627-633; fe/listener:1198-1206; t/listener:710||
|491|updated only by admitted frames (new or benign repeats; never an…|I|listener:334,371; fe/listener:1110-1117; t/listener:303||
|491|holds at most one share of streams, oldest dropped first|I|listener:531-537; fe/listener:1113-1116; t/listener:303||
|492|each beacon replaces its own page and drops pages past its count…|I|listener:273-286; fe/listener:654-673; t/listener:329||
|492|and an epoch advance clears all of it (§9.8)|I|listener:241-251; fe/listener:612-624; t/listener:329||
|492|the entry from the most recently heard beacon wins|I|listener:280-286; fe/listener:662-673; t/listener:654||
|493 SHOULD|SHOULD cost what expires, not what is held (an expiry index)|I|listener:131-151,619-644; fe/listener:170-215; t/listener:580|Purges do. #173 saves once per batch of up to 32 datagrams instead of once per datagram|
|493|(The prototype still scans its live items once per tick; they are bounded by the dedup share.)|**D** rfc|listener:441-445,650-654; fe/listener:938-954|It scans current more often: on every keyed admission (all keys, to find the superseded value), and in _root_state per station per tick.|
|**§7.5**|**The loop-rate regulator** (31 I · 7 D · 7 U)||||
|497|the loop rate is a fair share of a fixed per-stream budget, not a…|I|station:234-251; t/station:51||
|497|repetition never enters any strength quantity (§12.1)|I|listener:329-336, records:383-385; fe/delivery:2375-2386; t/records:150|No strength quantity exists to enter.|
|501 dflt|Parameters ([PROPOSED DEFAULT], advertised per stream in the beacon, §9.8):|**D** code|station:464-477, wire:197-209|Beacon carries b_stream, b_station and the resulting loop_ms/loop_max_ms. class_min_ms, class_max_ms, k_avail and req_loop are not advertised, and §9.8's CDDL has no field for them, so §7.5 and §9.8 disagree.|
|505 dflt|Loop budget per stream: all repeats of all live items, bit/s|I|station:32,47; t/station:51|4 000 bit/s. Loop copies only: burst copies are outside it (README:71).|
|506 dflt|Cap on the sum of B_stream for one station|I|station:33,218-230|16 000 bit/s, checked once at construction; refuses to start if streams cannot fit.|
|507 dflt|class_min_ms[c] / Loop floor per class / §6.2 table|I|ids:101-114, station:241; t/station:51||
|508 dflt|class_max_ms[c] / Loop ceiling per class / 300 000 ms|I|station:30,244|300 000 ms, one constant for all classes, used only in the admission-time hi. No test.|
|509 dflt|Minimum repeats a live item should get within its remaining life|I|station:29,244; t/station:184|k_avail = 3, checked at admission only.|
|510 dflt|from keepOnAir.loop: fast = class_min_ms, normal = 2 × class_min_ms|I|station:253-258; t/station:37|slow = 6 × floor, explicit int ms accepted. Default is normal.|
|515|fair_ms(i) = 1000 · 8 · size_bytes(i) · n / B_stream|I|station:239-240; t/station:51|n counts every ring entry: PLUCKs and shed items that never repeat too.|
|516|lo(i) = class_min_ms[class(i)]|I|station:241; t/station:51||
|517|hi(i) = min(class_max_ms[class(i)], remaining_ttl_ms(i) / k_avail)|**D** neither|station:234-246|Tested at admission only: literally, every item would be degraded in its last k_avail loops. But an item admitted early is never re-judged when the stream fills later.|
|519|loop_ms(i) = max(req_loop_ms(i), lo(i), fair_ms(i))|I|station:242; t/station:51||
|520 MAY|MAY (work-conserving): redistribute budget left unused by items…|U||Optional, not taken.|
|522|mark i DEGRADED_AVAILABILITY and apply the attenuation ladder (§12.3)|**D** rfc|station:38,374-377|No ladder: a degraded item stops repeating at once, in every class but control and alarm. §12.3 A3 never stops live-state, regulatory or root. Any normal live-state item with TTL ‹ 30 s gets only its burst. Admitted: pl/README:478 (names the degraded clamp)….|
|524|next(i) = last(i) + loop_ms(i) · U(2/3, 4/3)|I|station:441-445; t/station:37||
|525|recompute loop_ms(i) and next(i) ("reconsideration"); send only if…|I|station:421-431|Same U kept for the interval.|
|526|B_station overflow: scale each B_stream down in class priority order|I|station:218-230, ids:117-118|Cuts the lowest class fully before the next, by the stream's default class, to a 500…|
|527|control ≥ alarm › live-state › regulatory › advisory › finding-ref…|I|ids:118, station:221|Same order. No test.|
|532 MUST NOT|A station MUST NOT loop an item faster than lo(i)|I|station:241-242; t/station:51|loop_ms ≥ lo.|
|532 MUST NOT|the repeats of a stream MUST NOT exceed B_stream in aggregate|**D** rfc|station:240,377|Loop repeats average within B_stream; the three burst repeats per sing, refresh or pluck are uncharged and nothing limits sings. One 600 B sing a second is 14 kbit/s of burst repeats on a 4 kbit/s stream. Admitted: README:71.|
|532|Without work-conserving redistribution, no item loops faster than…|I|station:242; t/station:51||
|532|Asking for a faster loop than one's fair share therefore gains…|I|station:239-242; t/station:51||
|532|asking for a slower one frees budget for one's other items|U||Without redistribution a slow request frees nothing: fair_ms…|
|533 MUST|Each interval MUST be randomised by a factor drawn uniformly from…|I|station:443; t/station:37||
|533 MUST|the next send time MUST be recomputed when the timer fires|I|station:421-431|No test of the recomputation itself.|
|534 MUST|The publish tool MUST return the effective loop_ms|I|station:338-341, runner:107; pl/binding:1217-1228; t/station:37||
|534 MUST|the effective TTL and the clamp reason|I|station:338-341; t/station:63||
|534 MUST|the clamp reason (class_min / fair_share / budget / none) (§15.1)|**D** neither|station:60,246-251|budget is never returned and degraded is, which no RFC list has; a cut TTL is ttl_clamped_from, with clamp none. §15.1 lists stream_max and class_max too, so the RFC has two lists. Admitted: pl/README:478; station README none.|
|540|1.7 s / 5 s (live-state floor) / ~6.7 s|I|station:239-242,253-258; t/station:51|Only with loop = fast; the default normal gives 10 s and about 13.3 s.|
|541|14.4 s (a fast request of 5 s is clamped) / ~19 s|I|station:239-249; t/station:51||
|542|ambient, 40 × 900 B, TTL 300 s|I|station:239-246|8 · 900 · 40 / 4 = 72 s, hi = 100 s by the same arithmetic. No test.|
|543|exceeds hi = 20 s → DEGRADED: chatter stops looping|I|station:243-246,423-425; t/station:184|Only for items admitted once the stream is that full|
|543|new chatter gets backpressure|U||No BUDGET_EXHAUSTED: sing() always accepts a well-formed…|
|545|This RFC keeps SAP's bandwidth cap (B_stream, B_station) and…|I|station:32-33,239-242; t/station:51||
|545|the class floors of §6.2 are 1-30 s, 10 to 300 times faster|I|ids:101-114|1 s (control) to 30 s (root). No test of the table as a whole.|
|547|The multicast fast path runs only where canticle doctor has passed (§11.2).|**D** rfc|__main__:165-166, daemon:421-423|--multicast / multicast = true is enough; nothing checks a doctor result. The doctor only reports multicast. Admitted: README:73 and :130-138.|
|548|Frames reach internet listeners only through relays.|**D** rfc|runner:179-184, __main__:164|No relay exists, and canticle station --to host:port sends unicast UDP to any address, whatever the frame's scope beyond the host rule. Admitted: README:62 (relays not implemented).|
|548|Per-lease and global budgets (§11.3.7, §12.3) and the circuit…|U||No leases, relay budgets or breaker|
|549|Relays learn each lease's loss from the receiver report on RENEW|U||No relay, LISTEN or RENEW code.|
|551|How fast a late joiner actually catches up depends on the stream's…|I|station:239-242; t/station:414||
|551|with B_stream = 4 kbit/s shared by 20 items of 327 B, the…|I|station:239-240, prototype/protocol-dynamics/SUMMARY:407||
|551|The beacon advertises the effective loop (loop_ms, loop_max_ms…|I|station:464-477; fe/listener:667-671; t/station:245|Median and max over the ring, shed items included, whose loops never run.|
|551|A catch-up SLO needs an explicit, bounded fill budget ‖ A catch-up SLO without such a budget is not a valid stream…|U×2||No SLO, fill budget or per-stream b_stream setting (the CLI… No SLO field exists to refuse.|
|**§7.6**|**New-item burst** (2 I · 2 U)||||
|555 SHOULD|the station SHOULD transmit immediately and then at +1 s, +2 s and…|I|station:28,377; t/station:37|Copies that would fall inside the 100 ms margin are not scheduled.|
|555 SHOULD|a supersede (§7.8), a pluck (§7.7) or an UNEQUIP (§8.5)|I|station:337,361; t/station:150|All go through _admit. UNEQUIP is an ordinary root sing with key 1 absent|
|555, MUST|The burst is charged to B_stream. ‖ It MUST be skipped when the budget is exhausted, except for control…|U×2||Burst copies are outside the regulator. No budget accounting, so a burst is never skipped.|
|**§7.7**|**Pluck and sticky-pluck** (18 I · 1 D)||||
|559|Pluck revokes a live item before its expiry. It is a PLUCK frame…|I|station:343-364, wire:225-226; t/station:150|Only while the target is still in this process's ring under that seq: not after depth…|
|559|signed by the same key as its target|I|station:356, listener:376; fe/listener:831; t/wire:152||
|559|It carries its own seq in the stream's sequence space, the target's…|I|station:354-355; t/station:150||
|559 MUST NOT|it MUST NOT expire later than its target|I|station:355, listener:353-358; fe/listener:787-799; t/station:150||
|560 MUST|On pluck the station MUST stop looping the target at once|I|station:357; t/station:150||
|560|It then loops the PLUCK frame, with a burst, at the target's loop…|I|station:359-361,376-377; t/station:150||
|560|until the target's expiry, so late joiners hear the pluck too|I|station:359-361,421-431; t/station:150|PLUCKs are never shed. No test joins a listener after the burst.|
|562 MUST|On a valid PLUCK, a receiver MUST remove the target from every…|I|listener:380-388, records:373-382; fe/records:573-579; t/records:202|Current, held, snapshot set and record retract.|
|562 MUST|MUST add (key-id, epoch, stream_id, target_seq) to its sticky-pluck…|I|listener:376-379; fe/listener:831-834; t/listener:710||
|562|retained until the target's local expiry plus skew|I|listener:368-378; fe/listener:818-834; t/listener:631||
|562 MUST|it MUST be suppressed with evidence plucked|I|listener:392-395,446-448; fe/listener:854-860; t/records:202||
|563|A pluck can only shorten visibility. It cannot extend a TTL|I|listener:373-388; t/listener:700|A PLUCK only deletes and adds a suppression mark; nothing extends an item.|
|563 SHOULD|the receptor SHOULD put a one-line "withdrawn by station" note in the digest slot|**D** rfc|pl/ambient-slots:183-187, pl/binding:469; fe/records:573-579|The plugin spike (its README says no seat runs it) writes a [canticle:withdrawn/expired] digest note. frond-ear, the deployed binding, only drops the record: a session that was shown the text is never told it was withdrawn.|
|564|A pluck whose target the receiver never heard is still recorded in…|I|listener:353-379; fe/listener:784-834; t/records:202||
|565 MUST|While a receiver still holds its target's dedup entry, it MUST…|I|listener:349-358; fe/listener:780-801; t/listener:710||
|565 MUST|is refused with evidence pluck-mismatch, and the refusal is…|I|listener:354-358; fe/listener:787-800; t/listener:710||
|565|kept until the PLUCK's own local expiry plus skew, using the…|I|listener:368-378; fe/listener:818-833; t/listener:631||
|565|clamps to the largest class maximum TTL after its own issued_at|I|wire:31,379-384; fe/wire:421-437; t/listener:700||
|566|The station's obligation is to keep the PLUCK on air until the…|I|station:369-377; t/station:150|Not across a station restart.|
|**§7.8**|**Supersede by key** (30 I · 1 D · 1 O)||||
|570|Items that carry a state_key are keyed.|I|listener:399-400, station:316-320; t/wire:152||
|570|the item with the greatest (issued_at, epoch, seq) is current|I|listener:401,424-438; fe/listener:156-162; t/wire:152||
|571 MUST|Singing a new keyed item MUST stop the loop of the item it…|I|station:316-320; t/station:100||
|571|No pluck is needed. The new item gets a burst.|I|station:337,377; t/finding:256||
|571 MUST|a station MUST keep one class per (stream_id, state_key)|I|station:299-304; t/station:110||
|571 MUST|expires_at + TTL + class maximum TTL + 10 s (5 s receiver skew plus…|I|station:27,329-336; t/station:131||
|571|Before then, a change of class needs a new epoch (§23.2 question…|I|station:300-304; t/station:110||
|571|its table holds only keys sung within about one TTL and one class…|I|station:381-387; t/station:131||
|572 MUST|Receivers MUST keep a supersession high-water mark per (key-id…|I|listener:187,438; fe/listener:294-298; t/listener:791||
|572 MUST|An older item heard later MUST be dropped with evidence superseded…|I|listener:423-428; fe/listener:900-914; t/wire:152||
|572 MUST|The mark MUST be persisted across restart|I|listener:666-680,705-711; fe/listener:384-427; t/listener:222||
|572 MUST|retained until every older item for that key has expired|I|listener:433-438,637-644; fe/listener:927-937; t/listener:518||
|572 MUST NOT|Each mark keeps a retention horizon, which MUST NOT decrease (#60…|I|listener:433-438; fe/listener:928-936; t/listener:518||
|573|raises the horizon to at least that item's local expiry (§14.6.3) +…|I|listener:368,433-438; fe/listener:927-934; t/listener:557||
|573|Taking the latest over the items admitted, rather than the newest…|I|listener:436-437; fe/listener:931-933; t/listener:518||
|574|Each term is bounded when it is set, because local expiry is at…|I|wire:384-388, listener:433; t/listener:557||
|574|no clock offset, and no station clock step, can push a horizon past…|I|listener:368,433-438; t/listener:557||
|574|also tolerates a rise in δ̂ after admission of up to the item's TTL|I|listener:433-438; t/listener:604||
|575|Older items dropped as superseded do not move the horizon.|I|listener:424-428; fe/listener:902-914; t/listener:533||
|576|the mark lapses at the earlier value's horizon|I|listener:436-437; t/listener:772||
|577|the mark is dropped, whether or not a periodic purge has run yet|I|listener:410-414; fe/listener:874-879|No test hears a same-key item past the horizon without a tick first.|
|578 MUST|A receiver that holds a mark MUST drop an item in the mark's epoch…|I|listener:415-422; fe/listener:880-899; t/listener:760||
|578|with evidence class-change; the mark does not move|I|listener:417-422; fe/listener:880-899; t/listener:760||
|578|it reports class-change, not superseded|I|listener:417-428; fe/listener:882-914; t/listener:760||
|578|A plucked tuple still reports plucked.|I|listener:418; fe/listener:888-890; t/listener:782||
|578|An item in a later epoch may change the class.|I|listener:417; fe/listener:882-887; t/listener:772||
|578|older epochs are refused as epoch-regression (§5.2)|**O**|listener:313-318,555-586; fe/listener:741; t/records:238|Replaced by §10.9 amendment BC-1 (#61): a new lower-epoch tuple is verified, ringbuffer_only, with evidence. The daemon does that; canticle listen and frond-ear's embedded listener still refuse.|
|578|A receiver can detect a station breaking the rule only while it…|I|listener:417; t/listener:791||
|579|is still dropped as plucked, but it first moves the mark and…|I|listener:390-395,432-448; fe/listener:851-961; t/listener:618||
|579|An item that is both plucked and older than the mark, or plucked…|I|listener:418,425; fe/listener:887-914; t/listener:569||
|580 MUST|issued_at more than 5 s in the receiver's future (after δ̂…|I|wire:30,446-447; fe/wire:546-547; t/wire:152||
|580|so a stolen key cannot win supersession with a far-future timestamp|**D** neither|wire:446, listener:104-106; fe/listener:140-141|The same key signs the beacons that set δ̂: the cited test sends one beacon 10 years ahead, then lands an item issued 10 years ahead. Only the horizon bound (≤ TTL + 5 s + class max) limits it. δ̂ has no bound in §8.2 or the code.|
|**§7.9**|**Refresh re-issue and the keep-on-air horizon** (10 I · 3 D)||||
|585|The agent requests this with keepOnAir.forSeconds (§15.1).|I|runner:95-96, station:323-328; t/finding:256|As control-socket keep_on_air / CLI --keep-on-air seconds.|
|585|The station implements it by re-issue, never by extending a frame|I|station:405-410; t/station:192||
|587 SHOULD|Before the current item expires (RECOMMENDED at 2/3 of its TTL)|I|station:325; t/station:192||
|587|new seq, new issued_at and expires_at, the same state_key, the same…|I|station:326-328,407-409; t/station:192||
|588|The new item supersedes the old one (§7.8).|I|station:316-320,407-410; t/finding:256||
|588|the horizon is a series of frames, not one stretched frame|I|station:405-410; t/station:192||
|589|Re-issue stops at the horizon|I|station:406,411; t/station:192||
|589|on supersession, on pluck or on UNEQUIP|I|station:316-320,357; t/finding:256|The chain lives on the ring entry, so removing it stops it|
|589 dflt|Horizon ceilings: root 24 h (D3)|I|station:34,324|86 400 s for every class. No test of the ceiling.|
|589 dflt|aspect items 900 s by default (§17.4)|**D** rfc|station:323-325|No aspect handling; the 24 h cap applies. Admitted: README:77 (says any keyed item, up to 24 h….|
|589 dflt|all other classes one TTL unless the stream configuration raises it|**D** neither|station:323-325, __main__:260|24 h for any keyed item. canticle grant (24 h), beacon (12 h) and the probe profile (30 min) depend on it; the RFC's per-stream setting is what is missing. Admitted: README:77.|
|590|Only keyed items may be refreshed.|I|station:297-298|ValueError, before a seq is taken. No test.|
|591 MUST|Receivers MUST treat a refresh from the same principal with an equal body digest as the same lineage root|**D** rfc|records:389-397, shape:309-329; fe/delivery:1075-1080|frond-ear's push collapses it (same key, stream, state_key, digest, flag set). shape counts it as a new arrival, tap prints it as a new item without the flag, the plugin journals it and offers it as a new candidate; lineage.root stays null.|
|**§7.10**|**Late joiners** (15 I · 23 U)||||
|597|A listener that tunes in hears every live item within about loop_ms…|I|station:421-445; t/station:414|Not for degraded items (no repeats after the burst), which stay in the beacon's live…|
|598|Each beacon stream entry carries trail_seq, the lowest seq still on…|I|station:464-477; fe/wire:352-369; t/station:258||
|598|The live set is not contiguous, because items expire, are…|I|station:316-320,357; t/station:258||
|598|A beacon whose entry has trail_seq above head_seq + 1 is malformed…|I|wire:338-341; fe/wire:357-365; t/wire:103||
|598, MAY|A missing seq below trail_seq is gone and will not loop again, so a… ‖ the listener MAY wait up to one loop_max_ms for it, or ask its…|U×2||The listener holds trail_seq (stream_entries) and nothing reads… Optional, not taken: no gap tracking|
|598|Either way, a gap is never a value (I-9).|I|records:477; fe/delivery:2282-2296|Nothing derives state from a gap; frond-ear only reports "N seqs skipped". No test.|
|599 MAY|A LISTEN names how the listener joins (§11.3.2, key 7)|U||No LISTEN, lease or relay code in either repository.|
|600|looped frames only, with passive catch-up|U||No join modes.|
|601|The relay sends the current verified live set that matches the…|U|||
|602|the fill without looped frames, as a one-off view of the live set.…|U|||
|604|it happens entirely at the relay. The station is untouched, and I-1…|U||No fill.|
|605 dflt|is paced at fill_bps, which the relay grants in LISTEN_OK.…|U|||
|606 dflt|makes at most fill_passes passes over the live set ([PROPOSED…|U|||
|607|contains only verified, unexpired frames the relay already holds…|U|||
|609|Fill frames are ordinary copies to the receiver. A tuple it has…|I|listener:319-336; fe/listener:742-768; t/wire:152|Receiver half only: dedup looks at identity and bytes, never at the path.|
|610 MAY|A leased listener that sees a gap MAY ask its relay for the missing…|U||Optional; no REPAIR anywhere.|
|611|A listener requests only a seq in [trail_seq, head_seq] of the…|U|||
|612, dflt|It sends at most one REPAIR per lease per beacon interval for that… ‖ It does not ask for the same tuple again within (K + 2) · RTT|U×2||K = 4 default, unused.|
|614|on a validated lease (cookie and address, §11.3.3)|U|||
|615|from its verified, unexpired live set (§12.4), with the stored…|U|||
|616|within the lease's granted_bps and the relay's global egress cap.|U|||
|618|It skips a tuple it already sent to that lease within the tuple's… ‖ it never sends a frame whose remaining life is below its class's…|U×2|||
|619 MAY|For tuples the relay does not hold, it MAY answer REPAIR_GONE. ‖ It sends at most one per lease per 2 · RTT, and never one larger…|U×2||Optional.|
|620 MUST NOT|A relay MUST NOT forward a REPAIR, or anything derived from one, to…|U||No relay; nothing contrary exists.|
|620|No station ever sees repair traffic.|I|runner:144-149,179-193|A station never reads its UDP socket; its only input is the local control socket.|
|621|Receivers verify repaired frames like any other frame. A repaired…|I|listener:221-234,319-336; t/wire:152|Receiver half only: every datagram takes the one verify and dedup path.|
|621|REPAIR_GONE is availability data: it ends the wait, and it is never…|U|||
|622|The carousel remains the baseline, and repair is an optimisation.|I|station:396-432; t/station:414||
|622|There are no NACKs on LAN multicast in v1.|I|runner:206-242, daemon:415-428|No receiver sends on the canticle port. No test.|
|623|Passive catch-up is a receptor's, not a harness binding's.|I|records:383-385; t/join_snapshot:472||
|623|The receptor deduplicates a repeat before it emits any record…|I|records:383-385; t/records:150||
|623|a binding that joins a host daemon's run late never hears an item…|I|records:383-385; t/join_snapshot:472||
|623|It catches up by the join snapshot of §14.18.3 instead|I|daemon:253-330, records:557-569; fe/record-client:85; t/join_snapshot:199|Both bindings and tap ask for it.|
|623|which happens entirely between the daemon and that one connection…|I|daemon:302-330; t/join_snapshot:415||
|**§7.11**|**Addressed items are never looped** (1 D · 1 U)||||
|629|is same-host, delivered once and idempotently through the harness's…|U||No addressed mode in the station, the plugin or frond-ear.|
|629 MUST NOT|MUST NOT enter the station ring|**D** rfc|runner:85-107|The station has no addressed mode and the control socket ignores request keys it does not know, so a request with mode=addressed and an audience is sung as a looped broadcast instead of refused. No built client sends one.|

### §8 The carrier wave

73 claims: 51 I · 9 D · 13 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§8.1**|**Purpose** (2 I)||||
|637|Every station emits a carrier-beacon, a signed, content-free pulse|I|station:396-402,505-549; t/station:245|Every Station beacons from its first poll; there is no off switch.|
|641|It does not tell a cold hearer which multicast group, subnet…|I|wire:126-139,197-209|No address field exists in the BEACON key table|
|**§8.2**|**What the beacon carries** (11 I · 1 U)||||
|647|The station exists and is emitting, without anyone tuning to a…|I|listener:254-288,725-734; fe/listener:628-676; t/listener:50||
|648|head_seq per stream, not per station.|I|station:464-477, wire:95-123; fe/wire:355; t/station:245||
|648|trail_seq gives the lowest seq still on air|I|station:472, wire:106; fe/wire:356-365; t/station:258|A1 is in the codec, the station (min of the ring), the listener map and the vectors…|
|648|so a receiver can tell a gap that will loop again from one that is…|U||Both listeners store trail_seq|
|649|next_beacon_ms states when to expect the next beacon|I|station:508,545-548; t/station:245||
|650|Per stream: default and maximum TTL|I|station:471-476; t/station:245||
|651|Per stream: live count, typical and maximum loop_ms, B_stream; per…|I|station:464-477,545-546; t/station:245||
|652|as the minimum of (t_receive − wallclock) over the last 16 beacons|I|listener:35,92; fe/listener:645-646; t/listener:77|deque(maxlen=16), min(). Samples survive an epoch change.|
|652|δ̂ moves station times onto the receiver clock, for the time window…|I|listener:226, wire:445-449; fe/wire:545-550; t/listener:77||
|652 MUST NOT|It can never keep an item past its full TTL counted from first…|I|wire:386-388, listener:368; fe/wire:434-438; t/listener:69|True as worded. But δ̂ from replayed beacons can make an EXPIRED item look new|
|652|Without beacons, δ̂ = 0.|I|listener:104-106,226; fe/listener:1315-1318||
|654 MUST NOT|A beacon never counts toward salience, evidence mass, accord or any…|I|listener:254-288, records:321-324|Prohibition: none of those quantities exist in either repo|
|**§8.3**|**Cadence and next_beacon_ms** (6 I · 1 D · 4 U)||||
|658 dflt|Default period [PROPOSED DEFAULT]: 1 000 ms on LAN bindings|I|station:149, __main__:766; t/station:245||
|658 dflt|configurable from 500 ms to 10 000 ms|**D** rfc|__main__:766, station:168|Configurable, but unbounded: --beacon-ms is a bare int. 0 makes every beacon a goodbye and next_due() "now", so run_station spins sending them; negative encodes an invalid field. No departure note.|
|658 SHOULD|Each interval SHOULD be jittered by ±10%|I|station:508; t/station:245||
|659|Every beacon carries next_beacon_ms, the time until the station…|I|wire:198,327; t/station:245||
|659|next_beacon_ms = 0 is a goodbye: the station is signing off|I|station:551-553, runner:196-197; t/station:245|Sent once, unrepeated, only when run_station ends cleanly.|
|660 MAY, MUST|Relays MAY decimate beacons toward leases, but not below one per 5 s ‖ A relay that decimates MUST announce the factor n per station… ‖ The listener's expected period for that station is next_beacon_ms ×…|U×3||Optional. No relay exists in either repo. Listeners use next_beacon_ms alone; no decimation input exists.|
|660 MUST NOT|A relay cannot edit a station's signed next_beacon_ms|I|wire:452-456; t/wire:152|Follows from the signature over the whole frame.|
|661 MAY|a relay MAY emit a relay beacon (a BEACON signed by the relay's…|U||Optional. The codec can carry key 11|
|661 MUST NOT|never substitutes for a station signature|I|listener:254-288, wire:363|Only because nothing reads key 11.|
|**§8.4**|**Catalog overflow and rotation** (16 I · 2 D · 2 U)||||
|667|A stream entry costs about 25 bytes typically|I|station:489, wire:120-123||
|667|it costs 54 bytes, or 59 with lens|I|wire:115-118; t/station:299||
|667|one beacon without a capsid holds 17 entries (15 with lens) within…|I|station:173-186,479-498; t/station:299||
|667 MUST|A station with more streams than fit in one beacon MUST rotate them…|I|station:537-544; t/station:284|Cyclic sweep over the catalog.|
|669|Each beacon carries page = [index, count] and catalog_digest|I|station:544-546; t/station:284|Only paged beacons carry them, matching §9.8 "when rotating".|
|669|the first 8 bytes of SHA-256 over the deterministic CBOR of the full stream catalog|**D** neither|station:500-503|Digest covers [sid, default_ttl, max_ttl, b_stream] per stream in station config order: no heads, loops or lens. Under the sweep a receiver never learns that order, so it cannot recompute it. "Catalog" is undefined. No departure note.|
|670 MUST|Every stream MUST appear at least once every count beacons|I|station:511-544; t/station:366||
|670 MUST NOT|count MUST NOT exceed 8|I|station:187-190, wire:348; fe/wire:384; t/station:299||
|671 SHOULD|A stream whose head_seq changed SHOULD appear in the next beacon…|U||The cursor sweep ignores changes: a changed stream waits up to…|
|672 MUST|A receiver whose held catalog does not match catalog_digest MUST…|U||catalog_digest is parsed and never read by either listener|
|673 MUST|A station MUST choose the entries per page from their actual…|I|station:479-498,537-541; t/station:366||
|673 MUST|so that every beacon stays within the 1 100-byte frame limit|I|station:484, wire:216-217; t/station:299||
|673 MUST|A station with more streams than that MUST split them across…|I|station:182-190; t/station:299|Stricter: refuses at start any catalog whose worst-case packing needs more than 8…|
|675|rfc/0001-notes/vec/frame_v2_sizes.py computes the bound|I|rfc/0001-notes/vec/frame_v2_sizes:63-85||
|679|All fixed fields, no stream entries / 166 B|I|wire:197-218|Recomputed with wire: 166 B. No test.|
|680|so any catalog of up to 136 streams (120) fits in 8 pages|I|station:182-190; t/station:299||
|681|12 entries per page (11 with lens); catalog floor 96 (88)|I|wire:204-205|True of the format (recomputed 12/11).|
|682|Relay beacon with 32 relay entries (key 11), no stream entries /…|I|wire:206-207|Recomputed 661 B, and wire.parse accepts it. Nothing emits one. No test.|
|684|A station whose catalog is at or below these floors can always page…|I|station:182-190; t/station:299||
|686|so rotation can start at 17 streams|**D** neither|station:492|Contradicts §8.4/§9.11: 17 worst-case entries fit, so rotation can start at 18 (16 with lens). In this code at small sizes it starts where the bytes or the 32-entry cap say.|
|**§8.5**|**Root mark and UNEQUIP** (5 I · 2 D · 1 U)||||
|690 MAY|A station MAY keep one root mark: a keyed item of class root on…|I|station:268-341, ids:112; t/station:192|Possible through sing|
|690|It persists by refresh re-issue (§7.9) up to a 24 h horizon|I|station:323-328,405-411; t/station:192|Horizon capped at 86 400 s; test covers refresh at 300 s, not the 24 h cap.|
|690|then needs a fresh election|U||After the horizon the loop just stops|
|691|The root body (content type 7, §9.9) is:|**D** rfc|listener:715-723; fe/listener:1258-1276|No code writes a root body, and the reader ignores ctype and class: any surfaced item on stream root with state_key root is decoded. A text root (ctype 1) reads as ROOT_UNKNOWN. No departure note.|
|693|root-body = { ? 1 =› tstr .size (1..128) }|**D** rfc|listener:717-723; fe/listener:1265-1272|Reader only tests "key 1 present": type, size and other keys unchecked. A body_ref-only root (no body) is taken as {} and so as UNEQUIP. No departure note.|
|695|UNEQUIP is a root item with key 1 absent|I|listener:722,737-738; t/listener:37|Read so; nothing in the CLI writes one (body_hex only).|
|695|It supersedes the mark and loops until its TTL|I|station:315-320, listener:441-445; t/listener:37||
|696|lives in the root vocabulary a station elects, never in the wire…|I|wire:34-38||
|**§8.6**|**Presence state machine (receiver)** (7 I · 4 D)||||
|703|valid beacons (advertised period P = next_beacon_ms × relay decimation)|**D** rfc|listener:267,731; fe/listener:1282|P = last non-zero next_beacon_ms (1 000 ms fallback); no decimation factor. Admitted: README:62.|
|706|some stream item fresh within 5 × that stream's loop_ms|**D** rfc|listener:739-742,371; fe/listener:1287-1295|5 × advertised median loop, any stream but root. But PLUCK copies count as hearing (_heard_on serves both kinds), as do typed-beacon and grant items, so a station looping only a PLUCK reads SPEAKING. #173 #173/listener:646-657 adds the same note for pre-parse repeats|
|707|EQUIPPED_QUIET beacon fresh ∧ root equipped ∧ no fresh stream item|I|listener:743; fe/listener:1297; t/listener:37||
|708|UNEQUIPPED_PRESENT beacon fresh ∧ current root item is UNEQUIP|I|listener:737-738; fe/listener:1286; t/listener:37||
|709|ROOT_UNKNOWN beacon fresh ∧ no root item heard since tuning in|**D** code|listener:715-723,734-736; fe/listener:1284-1285|Also returned when a root WAS heard but expired, was plucked or is unreadable, or the root stream is untuned/unnamed. §8.6 gives those cases no state.|
|709 MUST NOT|never shown as "unequipped"|I|listener:735-738; t/listener:37||
|710|UNOBSERVABLE no valid beacon for 3 × P; reason ∈ {unknown…|I|listener:727-733; fe/listener:1280-1283; t/listener:50||
|711|a verified beacon with next_beacon_ms = 0 → UNOBSERVABLE(reason =…|I|listener:266,729-730; fe/listener:1281; t/listener:37||
|713|"beacon fresh" = a valid beacon within 3 × P|I|listener:731-733; t/listener:50||
|718 MUST NOT|Interfaces MUST NOT render any state as "offline", "absent"…|I|shape:40-41, tap:240-241; fe/hear:409-416; pl/t/inbound:85-92|Grep of both repos: those words never render a station|
|718|UNOBSERVABLE is rendered as "not observable since t"|**D** rfc|pl/render:184-190, tap:356-367; fe/hear:409-416|Only the OpenClaw plugin does it. tap prints "on air: cael=UNOBSERVABLE" / "state=UNOBSERVABLE"; frond-ear (deployed) prints "on air: cael=UNOBSERVABLE" and discards last_beacon_at, so it has no t. No departure note.|
|**§8.7**|**Capsid** (3 I · 4 U)||||
|723|The capsid is OPTIONAL and off by default|I|station:545-546||
|723 MUST NOT|a small, versioned map of coarse buckets or commitments, never raw…|U||Capsid not built. Receivers accept any map as key 10.|
|726|capsid = { 1 =› uint|U||Suggested shape (all five fields): not built, not validated on…|
|732 MUST NOT|It MUST NOT count toward any receiver quantity.|I|wire:363; fe/wire:16-17|Nothing reads Beacon.capsid; frond-ear discards it. No test.|
|733|are local, expiring hypotheses that carry schema version, window…|U||No resemblance or portrait code exists.|
|734 MUST NOT|a station MUST NOT include a capsid in beacons sent over fleet or…|I|station:545-546||
|734 MUST|relays on those tiers MUST drop beacons that carry one|U||No relay exists in either repo.|
|**§8.8**|**Cost** (1 I · 1 U)||||
|740|A signed beacon with five stream entries is 253 bytes|I|wire:197-218|Recomputed with wire: 253 B (2 024 bit/s at 1 Hz). No test.|
|740 SHOULD|Relays SHOULD decimate toward internet leases|U||No relay exists in either repo.|

### §9 Wire format v2

157 claims: 134 I · 11 D · 12 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§9.1**|**General requirements** (7 I)||||
|748|One frame per UDP datagram.|I|runner:179-189; t/udp_e2e:24||
|748 MUST NOT|A frame MUST NOT be fragmented at the application layer|I|wire:212-218; t/wire:93||
|748 SHOULD|senders SHOULD set "don't fragment" (for example IP_PMTUDISC_DO)…|I|runner:147-148|No test.|
|749 MUST NOT|The UDP payload MUST NOT exceed 1 200 bytes on any binding.|I|wire:25,408-409; fe/wire:473-474; t/wire:152|Receivers drop above 1 200; senders cannot exceed 1 100. Vector datagram-1201-bytes.|
|750 MUST NOT|A canonical frame (§9.2) MUST NOT exceed 1 100 bytes|I|wire:26,216-217; fe/wire:486-487; t/wire:152||
|751|There is no separate LAN profile.|I|wire:25-26||
|752 MUST NOT|Receivers of v2 do not accept those formats.|I|wire:410-415; fe/wire:475-477; t/wire:152|No magic, wrong version or short: rejected before any parse.|
|**§9.2**|**Fixed header and trailer** (14 I · 1 U)||||
|758|0x42 0x43 ("BC"). Replaces v0.1's 0x7B first-byte sniff|I|wire:20,412-413; fe/wire:476; t/wire:84||
|759 MUST|0x02. Unknown versions MUST be dropped silently.|I|wire:21,414-415; fe/wire:477; t/wire:152|Counted only (daemon: version counter, no record); listen --evidence can print it.|
|760 MUST|Frame kind, table below. Unknown kinds MUST be dropped silently.|I|wire:416-418, records:330; fe/wire:478-485|unsupported-kind, counted as malformed. No vector and no test in either repo.|
|761|SHA-256(station public key)[0:8]. At a fixed offset|I|ids:15-19, wire:214; fe/ids:10-17; t/wire:84||
|761|so that a relay or receptor can drop unknown keys before parsing…|I|wire:421-427; fe/wire:488-495; t/wire:152||
|762|Deterministic CBOR map with integer keys (§9.4). The key table…|I|wire:427-436,444; fe/wire:510-517; t/wire:152||
|763|Ed25519 signature (§9.3).|I|wire:24,450-456; fe/wire:551-558; t/wire:84||
|767|0x00 / reserved / — / —|I|wire:416-418|Dropped as unsupported-kind. No test.|
|768|0x01 / ITEM / yes / §9.6|I|wire:22,221-222; fe/wire:27; t/wire:152||
|769|0x02 / BEACON / yes / §9.8|I|wire:22,229-230; fe/wire:28; t/wire:152||
|770|0x03 / PLUCK / yes / §9.7|I|wire:22,225-226; fe/wire:29; t/wire:152||
|771|0x04-0x0F / reserved for signed frame kinds / — / —|I|wire:416-418|Dropped as unsupported-kind. No test.|
|772|0x10-0x1F / relay lease protocol / per message / §11.3|U||No relay exists in either repo and no lease messages|
|773|0x20-0x7F / reserved / — / —|I|wire:416-418|Dropped as unsupported-kind. No test.|
|774 MUST NOT|private / experimental / — / MUST NOT leave the host|I|wire:212-230|Vacuous: only kinds 1-3 are ever encoded. sign_frame itself would take any kind byte.|
|**§9.3**|**Signature** (7 I)||||
|780|Algorithm: Ed25519 (pure EdDSA, RFC 8032 §5.1).|I|wire:13-15,215; fe/wire:558; t/wire:84||
|781|Signed bytes: "binary-canticle/frame/v2" ‖ 0x00 ‖ frame[0 : len −…|I|wire:27,215; fe/wire:34-36; t/wire:84|24 chars + NUL = 25 bytes, not transmitted.|
|782 MUST|The signature is computed once per frame. Loops resend the same…|I|station:313,434-436; t/station:37||
|783 MUST|Verifiers MUST reject signatures whose scalar S is not reduced (S ≥…|I|wire:29,451-452; fe/wire:552-554; t/wire:152||
|783 MUST|MUST resolve key_id to a public key only through the fleet manifest|I|wire:422, manifest:98-104; fe/manifest:117-123; t/wire:152||
|783 SHOULD|SHOULD refuse small-order public keys when loading the manifest|I|ids:35-62, manifest:82-87; fe/manifest:75-102; t/manifest:64|Python does the [8]A test and refuses non-canonical encodings|
|784 MUST NOT|A key used for canticle frames MUST NOT be used to sign anything…|I|wire:215|Within these repos only sign_frame signs with a station key.|
|**§9.4**|**CBOR rules** (8 I)||||
|788 MUST|The map MUST use the core deterministic encoding of RFC 8949 §4.2.1|I|cbor:56-80; fe/cbor:79-115; t/wire:66||
|788 MUST|map keys sorted by the bytewise lexicographic order of their…|I|cbor:75-78,149-151; fe/cbor:103-113; t/wire:66||
|789 MUST|Receivers MUST reject a map that is not deterministically encoded|I|wire:426-436, cbor:98-119; fe/wire:494-517; t/wire:152||
|790 MUST NOT|Core keys (1-31) MUST NOT carry floating-point values or CBOR tags|I|cbor:102-107; fe/cbor:140-145; t/wire:152|Rejected everywhere, not only under core keys (stricter). Vector float-in-core-key|
|790 MUST NOT|Nesting depth MUST NOT exceed 4|I|cbor:24,137-138; fe/cbor:186; t/wire:152|The frame map itself counts as level 1 (RFC does not say)|
|790 MUST NOT|arrays and maps MUST NOT exceed 32 entries|I|cbor:25,139-140; fe/cbor:187; t/wire:27||
|791 MUST|Parsers MUST be strict, bounded and fuzzed|I|wire:391-404, cbor:157-163; fe/wire:445-465; t/wire:164|20 000 random/mutated inputs in Python, 2 000 in TS|
|791 MUST NOT|a parse error on one packet MUST NOT stop the receiver|I|wire:399-404, runner:223-227; fe/wire:461-464; t/listener:823|parse raises only Reject; listener, daemon and frond-ear count it.|
|**§9.5**|**Key numbering and forward compatibility** (7 I · 2 D)||||
|797 MUST|If crit lists a key the receiver does not understand, drop the…|I|wire:34-38,437-443; fe/wire:527-537; t/wire:152|Daemon counts crit_unknown.|
|798|Ignore unknown keys, unless listed in crit|I|wire:305,319; fe/wire:518-526|ITEM 19-31, PLUCK/BEACON others go to extra. No vector for a plain unknown core key|
|799|32-255 / Registered extensions / Ignore unless listed in crit|**D** owner|cbor:102-107,50-53; fe/cbor:140-145|Ignored only if the value fits the spike's CBOR subset: a float, a tag, another simple value, depth › 4, › 32 entries or a non-int/tstr map key under an extension drops the frame. Vector unknown-extension-key-ignored covers the plain case. Admitted: README:75.|
|800|≥ 256 / Reserved / Ignore|I|wire:305; fe/wire:518-526|Same path as other unknown keys; same CBOR-subset caveat. No test.|
|801|negative / Private use / Ignore|I|wire:305,441; fe/wire:518-526|Same path; same caveat. No test. A negative key listed in crit drops the frame.|
|803|Every key, known or not, is covered by the signature.|I|wire:454; fe/wire:555-558; t/wire:152||
|804 MUST|A change that old receivers must not misread requires a new version byte.|**D** neither|wire:95-118,332-335; fe/wire:345-351|A1 inserted trail_seq mid-array under version 0x02. The pre-A1 reader accepted 8 or 9 elements (git 9106d18^ wire:315), so it reads a post-A1 9-element entry shifted. Later readers reject by length (#70). Draft format; no exemption is written.|
|805|unknown keys are ignored, except where the sender marks them…|I|wire:305,437-443; t/wire:152||
|805|Unknown schema still "fails quiet, not interpretive"|I|listener:396-398, records:342-344; t/records:163|Unknown class stays ringbuffer_only; unreadable finding bodies are shown opaque.|
|**§9.6**|**ITEM (kind = 0x01)** (26 I · 3 D · 1 U)||||
|811|0 / crit / array of uint / — / no / §9.5|I|wire:437-443; fe/wire:527-537; t/wire:152|Non-array or non-int elements are bad-field|
|812|1 / epoch / uint ≤ 2³²−1 / 2-6 B / yes / §5.2|I|wire:260,297; fe/wire:298; t/wire:152|Vectors show only that a valid frame parses; presence and bounds are untested.|
|813|2 / stream / uint ≤ 2³²−1 / 6 B / yes / stream_id, §5.4|I|wire:260,297; fe/wire:299; t/wire:152|Vectors show only that a valid frame parses; presence and bounds are untested.|
|814|3 / seq / uint ≤ 2⁶⁴−1 / 2-10 B / yes / §5.5|I|wire:260,298; fe/wire:300; t/wire:152|Vectors show only that a valid frame parses; presence and bounds are untested.|
|815 MUST|Receivers reject values more than 5 s in their future (after δ̂)|I|wire:30,446-447; fe/wire:546-547; t/wire:152|Vector not-yet-valid. frond-ear bounds it at 2^53−1 (bad-field above).|
|816 MUST|MUST be › issued_at. Receivers clamp to issued_at + effective max…|I|wire:307-308,379-384; fe/wire:317-319; t/wire:152|Clamp uses the class max only, not a per-stream max.|
|817|6 / class / uint / 2 B / yes / §6.2|I|wire:282; fe/wire:281; t/wire:152|Code caps at 0xFFFF; RFC gives no maximum.|
|818|uint (registry §9.9) or tstr ≤ 64 B|I|wire:263-267; fe/wire:254-258; t/wire:152||
|819|Opaque to the substrate (proto/stations-and-streams-v0.2.md:58)|I|wire:271-275; fe/wire:259-261; t/wire:152|Codec never decodes it. An explicit null is bad-field (#66; unstated in RFC).|
|819|bstr / ≤ about 980 B / one of 8, 9|I|wire:261-262,216; fe/wire:251-253; t/wire:93|At least one is required; both allowed. 980 B is the maximum with core keys only.|
|820|[url: tstr ≤ 200 B, sha256: bstr .size 32, size: uint]|I|wire:276-281, runner:55-67; fe/wire:262-280; t/finding:191||
|820|If body is also present, body is a summary|I|__main__:785-787, runner:101-102; t/finding:184||
|821|10 / state_key / tstr, 1-32 B / ≤ 34 B / classes 3, 6, 7, 8, 9 /…|I|wire:33,283-285; fe/wire:282-285; t/wire:152|Missing on a keyed class is missing-field at station and receiver.|
|822|11 / hop / uint 0-15 / 2 B / yes|I|wire:300; fe/wire:308; t/listener:198||
|822 MUST NOT|Stamped by the publish tool, never by the agent|**D** rfc|runner:90, station:272; fe/derived:1-24|Agents cannot set it (control socket takes no hop), but the tool always stamps 0: main has no derived publish path, so derived content sung as ordinary text says hop 0 too. #162 #162/station:348-394 stamps hop 1..limit for capsule-backed derived items|
|823|array (≤ 4) of tuple / ≤ 118 B / no / tuple = [key_id: bstr .size…|I|wire:247-250,286-292; fe/wire:212-227|Parsed and bounded; maximum encodes to 118 B. An empty array is accepted.|
|823|seq: uint]; tool-stamped|U||Station.sing has no derived_from or root parameter #162 #162/station:348-394 signs items with derived_from and root|
|824|uint: 0 host, 1 lan, 2 fleet, 3 public|I|wire:300, ids:120; fe/wire:310; t/wire:152|Vectors show only that a valid frame parses; presence and bounds are untested.|
|825|14 / intensity / uint 0-255 / 2-3 B / no / Sender-declared, bounded|I|wire:301; fe/wire:311|Range-checked and carried; nothing acts on it. No range test.|
|826|bit 0 refresh (§7.9)|I|wire:75, station:408; fe/wire:100; t/station:192||
|826|bit 1 wake_derived (sung during a canticle-woken turn, §14.10)|**D** rfc|wire:75, runner:90; fe/delivery:1175|Carried and kept across refresh, and frond-ear refuses to wake on it. But no publish path sets it: the control socket takes no flags, and no tool knows the turn was woken. #162 accepts flags WAKE_DERIVED on derived items (#162/station:376)|
|826|bit 2 exercise (drill)|I|wire:75, records:471; fe/hear:131||
|826|bit 3 training_eligible (default 0, §6.4)|I|wire:75|Bit defined, default 0, never set or read (record v1 omits it). No test.|
|826 MUST|bits 4-15 MUST be 0|I|wire:293-295; fe/wire:295-296|Receiver: bad-field. The station encoder does not check, but no path sets flags.|
|827|16 / purpose / tstr ≤ 128 B / ≤ 130 B / no|I|wire:302; fe/wire:313||
|827 MUST NOT|Declared purpose; shown as context, never authority|I|records:466; fe/records:1237|Only rendered; nothing grants or wakes on it.|
|828|17 / root / tuple / ≤ 30 B / if 12 present / Lineage root…|I|wire:291-292,303; fe/wire:292-293|Receivers enforce root-if-12 (missing-field); accepted alone too. #162 stamps it|
|829|18 / lens / uint / 2-3 B / aspect streams / Lens id|**D** owner|wire:304, station:312; fe/wire:315|Receiver allows up to 0xFFFF (4 B); beacon entries allow u32 for the same id. The station copies StreamConfig.lens, which the CLI cannot set.|
|830|19-31 / reserved / / / /|I|wire:35,305|Ignored as unknown core keys; never sent.|
|832 MUST NOT|Receivers MUST NOT fetch a body_ref on a session's behalf as a side…|I|records:494-495, pl/render:89-90; fe/hear:174-176|Nothing in station, plugin or frond-ear canticle code fetches a URL|
|**§9.7**|**PLUCK (kind = 0x03)** (9 I)||||
|838|1 / epoch / uint / yes / Same epoch as the target|I|listener:353,376; fe/wire:326; t/wire:152|Structural: the target identity is built from the PLUCK's own epoch.|
|839|2 / stream / uint / yes / Same stream as the target|I|listener:376, station:354; fe/wire:327; t/wire:152|Structural. Vectors show only that a valid frame parses|
|840|The pluck's own seq in the stream's sequence space|I|station:354,358; t/station:150|Code also rejects target_seq ›= seq as bad-field, which the RFC does not state.|
|841|4 / issued_at / uint ms / yes /|I|wire:313,316; t/wire:152|Future-dated PLUCKs are not-yet-valid like items.|
|842 MUST|MUST equal the target's expires_at|I|station:355, listener:350-358; t/wire:152||
|843 MUST|MUST equal the target's scope|I|station:355, listener:354; t/listener:710||
|844|20 / target_seq / uint / yes /|I|wire:313,317; fe/wire:332; t/wire:84||
|845|0 withdrawn, 1 erroneous, 2 other|I|wire:318; fe/wire:333|Receivers reject reason › 2 as bad-field, so a later reason code would make a…|
|847|A key can pluck only its own items; this is structural|I|listener:353,376||
|**§9.8**|**BEACON (kind = 0x02)** (26 I · 1 D · 1 U)||||
|853|1 / epoch / uint ≤ 2³²−1 / yes /|I|wire:360; fe/wire:400; t/wire:152|Vectors show only that a valid frame parses; presence and bounds are untested.|
|854|Beacon counter within the epoch, starting at 1|I|station:210,507; t/station:245|Receivers do not reject 0.|
|854|A lower bseq than already seen in the same epoch is ignored|I|listener:260-262,669-676; fe/listener:637-643; t/records:489|In memory only: bseq is not in the saved state, so after a listener restart any…|
|854|a receiver that accepts a higher epoch resets its bseq mark|I|listener:241-246; fe/listener:612-618; t/listener:101||
|855|Station clock at send time (§8.2 job 6)|I|station:545, listener:264; fe/wire:402; t/listener:77|frond-ear bounds it at 2^53−1.|
|856|4 / next_beacon_ms / uint ≤ 2³²−1 / yes / Time to the next beacon…|I|wire:361, listener:266; fe/wire:403; t/wire:103||
|857|5 / profile / tstr ≤ 32 B / yes|I|wire:361, station:37; fe/wire:404; t/station:245|Receiver also requires ≥ 1 byte; nothing reads the value.|
|858|6 / streams / array of stream-entry / yes / May be empty|I|wire:328-342; fe/wire:343-378; t/wire:103||
|859|[index: uint, count: uint] / when rotating / §8.4; count ≤ 8|I|wire:343-350, station:544; fe/wire:379-386; t/station:284|Code also requires index ‹ count.|
|860|8 / b_station / uint ≤ 2³²−1, bit/s / yes / §7.5|I|wire:362, station:546; fe/wire:406; t/wire:103||
|861|9 / catalog_digest / bstr .size 8 / when rotating / §8.4|I|wire:351-355, station:544; fe/wire:387-393; t/station:284|Shape only; content and use diverge (see §8.4 rows).|
|862|10 / capsid / map / no / Off by default|I|wire:356-358, station:545-546|Never sent; any map accepted.|
|863|{1: tier (0 lan, 1 fleet, 2 public), 2: breaker|U||Receivers only check that key 11 is a map|
|866|stream-entry = [ stream_id: uint .size 4, head_seq: uint .size 8…|I|wire:95-123,331-342; fe/wire:345-378; t/wire:103||
|872|head_seq is the highest seq the station has issued on the stream in…|I|station:314,358; t/station:258||
|873|is the lowest seq of any ITEM or PLUCK the station still has on air…|I|station:468-473,506; t/station:258||
|873|When nothing is on air, trail_seq = head_seq + 1|I|station:472; t/station:258||
|873 MUST NOT|A station MUST NOT advertise a trail_seq above a seq it will…|I|station:468-473; t/station:258||
|873 MUST NOT|Receivers use it only as §7.10 says, never as a strength or trust…|I|listener:286|Nothing uses it at all.|
|874 MUST|MUST treat a stream entry whose trail_seq exceeds head_seq + 1 as…|I|wire:338-341; fe/wire:357-365; t/wire:103||
|874 MUST|the whole BEACON is dropped as malformed (§10.9) and changes…|I|listener:225-229, records:328-332; fe/t/canticle-listener:617-621; t/listener:669||
|874|trail_seq = head_seq + 1 (an empty retained window) stays valid…|I|wire:340; fe/wire:360; t/wire:103||
|874|an entry is checked on its own and never against an entry from an…|I|wire:331-342; t/wire:103||
|874 MUST NOT|The comparison MUST NOT overflow|I|wire:339-340; fe/wire:358-360; t/wire:103||
|874|At head_seq = 2⁶⁴−1 every trail_seq the CDDL allows is valid.|I|wire:340; t/wire:103||
|875|live is the live-set size|I|station:473; t/station:258||
|875|are the median and maximum effective loop over live items (0 when live = 0)|**D** rfc|station:467,474|Median/max run over the whole ring: PLUCKs count, and shed items contribute a loop they never send at.|
|876|Beacons are deduplicated on (key_id, epoch, bseq), separately from…|I|listener:260-262; fe/listener:637-643; t/records:489||
|**§9.9**|**Content types** (5 I · 3 D · 2 U)||||
|880|ctype is either a registered small integer or an IANA media-type…|I|wire:263-267; fe/wire:254-258; t/wire:152|Length only; neither the registry nor media-type syntax is checked.|
|884|1 / text/plain; charset=utf-8 / —|I|ids:123-135; fe/ids:119|Ids 1-11 all match the CTYPES table (one row for 884-894). frond-ear knows only id 1.|
|887|4 / application/vnd.canticle.aspect+cbor / §17.3|U||Ids 4, 5, 6, 9, 10 are names only: no code builds or reads…|
|891|application/vnd.canticle.digest-ref+cbor / §9.12 (doorbell)|I|station:291-294; t/finding:191|Default ctype when an item has only a body_ref.|
|894|application/vnd.canticle.finding+cbor / §6.7 (amendment FP-1, #112)|I|finding:28-29, ids:134; t/finding:176||
|895|12-1023 / reserved for registration in this repository /|U||No check: any uint ≤ 0xFFFF may be sung and is accepted.|
|896 MUST NOT|1024-65535 / private / experimental / MUST NOT be sent at fleet or public scope|**D** rfc|station:276-294, runner:99-100|Station.sing takes any ctype with any granted scope; no check at socket, station or receiver. No departure note.|
|898 MUST|Receivers MUST treat opaque content as never wake-eligible|**D** rfc|records:485-495; fe/delivery:1167-1180|canticle-station never wakes. frond-ear wakes sessions and its push filter has no opaque test: a private or unregistered ctype from an allowlisted key pushes like text (body hidden). Violated by frond-ear.|
|898 MUST|never accord-counted and never training-eligible|I|records:485-495|Vacuous: no accord or training code exists.|
|898 MUST NOT|senders MUST NOT publish it at fleet or public scope|**D** rfc|station:276-294|Nothing classifies content as opaque; only the manifest scope grant stands in the way. Admitted: README:65.|
|**§9.10**|**JSON projection** (1 I · 1 U)||||
|902 MAY|a frame may be rendered as JSON with key names in place of numbers…|U||Optional, non-normative.|
|902 MUST NOT|The projection is never sent on the wire and never signed.|I|wire:212-218||
|**§9.11**|**Size budget (worked example)** (11 I · 1 D)||||
|910|745 B = 12 header + 669 CBOR + 64 signature|I|wire:23-24; t/wire:93||
|911|ITEM / the same with registered ctype = 1 / 720 B|I|wire:212-218; t/wire:93||
|912|largest body with core keys only and registered ctype / 980-byte…|I|wire:216-217; t/wire:93||
|913|largest body with state_key, 4 derived_from tuples, root, 64-byte purpose, string ctype / 799-byte body → 1 100 B|**D** code|wire:216-217, rfc/0001-notes/vec/frame_v2_sizes:46-51|Wrong: 799 B makes 1 108 B, which sign_frame refuses. The largest is 791 B (816 with ctype 1). frame_v2_sizes.py starts its search at 800 and prints n−1, so it never tested 799.|
|914|6 evidence references (704-byte body), lens and scope = fleet set /…|I|wire:212-218, rfc/0001-notes/vec/frame_v2_sizes:86-91|Recomputed: body 704, frame 869. No test.|
|915|"hello, station" (vector 1, §9.13) / 127 B|I|wire:221-222; t/wire:84||
|916|PLUCK / minimal (vector 2) / 107 B|I|wire:225-226; t/wire:84||
|917|5 stream entries (the 9-field stream-entry of §9.8) / 253 B|I|wire:197-218|Recomputed 253 B. No test.|
|918|BEACON / every field at its CDDL maximum, no stream entries / 166 B|I|wire:197-218|Recomputed 166 B (no capsid or relay key). No test.|
|919|17 entries per page, 15 with lens; 12 and 11 with the largest capsid|I|station:173-186; t/station:299|Recomputed 17/15/12/11. Only 17 is tested (15 is 16 with the spike's profile).|
|920|relay BEACON / 32 relay entries in key 11, no stream entries / 661 B|I|wire:206-207|Recomputed 661 B. No test.|
|922|The fixed parts cost 76 bytes (12 header + 64 signature). Core keys…|I|wire:23-24; t/wire:93||
|**§9.12**|**Large content goes by reference** (3 I · 4 U)||||
|926|Content larger than one frame travels by reference: body_ref =…|I|wire:216-217, runner:55-67; t/finding:191||
|926|usually in a finding-ref item with content type 8 (a "doorbell")…|I|station:291-294; t/finding:191||
|927|payload-carrying frames up to 1 100 bytes, plus digest references…|I|wire:26,267-281; t/wire:93||
|928 MUST|If it is added, receivers MUST authenticate before decoding|U||No FEC or multi-part carousel (future work).|
|929|travel as references to non-authoritative capsule objects with a…|U||No capsule handling in either repo; a body_ref could carry one.|
|930 MAY|Compression MAY use a registered content type that names a… ‖ A private dictionary makes the content opaque|U×2||Optional. No compression. No opaque classification exists.|
|**§9.13**|**Test vectors** (7 I · 1 D)||||
|934|Normative vectors are TBD. They are work item S1 (#27)|I|vectors:262-271; t/wire:161|Still true: 49 candidates (34 parse, 15 sequences), labelled not normative.|
|934|generated and cross-checked by two independent implementations|**D** owner|vectors:262-271; fe/t/canticle:63-98|Generated by Python only. frond-ear's TS runs all 49 (same file, sha256 9b6a1eda) but has no frame encoder and calls itself a port, so it checks, not generates. q20 asks only that TS "reproduces them"; README:751 too. Admitted: README:751.|
|934|covering at least the #48 acceptance set (valid, wrong key…|I|vectors:124-137,199; fe/t/canticle:63; t/wire:152||
|934|repeat-as-no-op, equivocation pair, non-deterministic CBOR…|I|vectors:136-144,199-202; fe/t/canticle:63; t/wire:152||
|934|a stream entry with trail_seq = head_seq + 2 (bad-field) beside one…|I|vectors:92-95,163-166; fe/t/canticle:63; t/wire:152||
|938|public key d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f…|I|vectors:22, ids:15-19; fe/t/canticle:48-61; t/wire:84||
|939|Vector 1, ITEM {1: 1, 2: 1, 3: 1, 4: 1790000000000, 5…|I|vectors:76-77; fe/t/canticle:63; t/wire:84||
|945|Vector 2, PLUCK of vector 1 {1: 1, 2: 1, 3: 2, 4: 1790000005000, 5…|I|vectors:78-79; fe/t/canticle:63; t/wire:84||
|**§9.14**|**Alternative envelope** (2 I · 2 U)||||
|954|The bespoke header puts key_id at a fixed offset, which lets relays…|I|wire:421-427; t/wire:152||
|956|keep the bespoke fixed header, deterministic CBOR and trailer for v2|I|wire:212-218; fe/wire:467-560; t/wire:84||
|956|publish a COSE_Sign1 mapping as an alternative envelope for broker… ‖ freeze after S1 has measured both|U×2||No COSE code or mapping in either repo. No S1 comparison beyond review/challenge-broker §5.1|
|**§9.15**|**Mapping from the superseded formats** (1 I)||||
|962|v / v0.1 / version byte|I|wire:164-209; t/wire:152|Non-normative mapping table 962-979, one row: every v2 target that is a frame field…|

### §10 Trust

170 claims: 56 I · 37 D · 75 U · 2 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§10.1**|**Principles** (9 I · 1 D · 5 U)||||
|987 MUST|Every frame — ITEM, PLUCK and BEACON, all classes — MUST carry a…|I|wire:212-218,450-456; fe/wire:489-558; t/wire:152|One sign_frame signs every kind; the parser rejects a frame without a good signature.|
|987 MUST|Receivers MUST verify it before any use other than bounded debug…|I|wire:422-457, listener:221-231; fe/listener:576-596; t/records:508|Nothing from a frame is used before _parse returns, except counters and the key-id… #173 #173/intake:537 queues by claimed key, stream and source before the signature (scheduling only)|
|988|Trust derives only from the signature plus the fleet manifest…|I|manifest:95-104, listener:294-308; fe/manifest:112-123; t/listener:142|Keys, classes, scopes and names come only from the local manifest.|
|988 MUST NOT|Receivers MUST NOT infer trust from a name, a DNS or mDNS record, a…|I|listener:294-312, dns_browse:101-140; t/dns_browse:52|No code path grants anything from these; DNS hints are only compared.|
|989|Relays are trusted for availability only. ‖ They forward signed bytes and never re-sign (I-8).|U×2||No relay exists in any repo. No relay. Nothing anywhere re-signs a received frame.|
|990|verification authorizes interpretation eligibility, never task…|I|records:389-397, pl/records:121-123; fe/records:1196-1204; t/records:130|verified + surface only makes a record eligible|
|990|Verification alone never causes a turn.|I|pl/config:97-100; fe/delivery:1168-1180; fe/t/canticle-delivery:749|frond-ear pushes only a key on the operator list wakeKeys (default empty), hop 0, not…|
|990|A wake happens only by the receiver's own explicit, budgeted local…|I|pl/config:98-131; fe/src/config:149-179; fe/t/canticle-delivery:1258|frond-ear: wakeKeys, per-ear mode, maxPushesPerHour, mute.|
|992 MUST|Ed25519 on every frame or binding that can land in a session or mutate receptor state, host-local paths included.|**D** neither|wire:450-456, daemon:350-373; fe/record-client:69-92|Frames: yes. But record v1 lands in sessions over an unsigned unix socket guarded only by uid (§11.1, D35), and the station control socket takes unsigned sing. D4 predates D35; the RFC must reconcile them.|
|994, MUST NOT|A peer-authenticated unix debug socket (§11.1), whose output is… ‖ Nothing arriving on it may mutate receptor state, land, carry…|U×2||No debug socket. No such socket.|
|995 MUST NOT|The old unsigned LAN formats (v0.1, v0.2) are superseded, and there…|I|wire:412-418; fe/wire:469-491; t/wire:152|Anything but magic BC, version 2 is rejected (vectors bad-version…|
|996 MAY|A group HMAC MAY serve only as a relay flood pre-filter (§10.2).|U||Optional. No HMAC tag, no relay.|
|996 MUST NOT|It is never identity and never authorization.|I|wire:450-456|No HMAC in station, daemon or plugin; nothing contrary exists, no test. #162 #162/derived_reply_proposal:516-543 authorizes a derived publish with a local HMAC capsule (proposal, not a group HMAC)|
|**§10.2**|**What the old trust stories become** (2 I · 1 D · 1 U)||||
|1004 MUST NOT|Dropped. Any key holder can forge any station|I|wire:422-424,450-456; t/wire:152||
|1005|Reversed: Ed25519 is the base layer.|I|wire:450-456; t/wire:152||
|1006|Kept as the verify stage's donor (§10.10), with its bugs fixed.|**D** code|wire:407-457, cbor:83-163|The donor was not reused: a new CBOR codec and verifier import nothing from ringserver-udp-cue. Better: a JSON donor does not fit the CBOR wire. See §10.10.|
|1007 MAY|MAY be used by a relay as an ingress pre-filter tag outside the…|U||Optional. No relay, no tag.|
|**§10.3**|**The fleet manifest** (6 I · 11 D · 37 U)||||
|1011|The fleet manifest is the only source of keys and capabilities.|I|manifest:95-104, __main__:142-148; fe/manifest:89-123; t/station:461|Verification keys and class/scope grants come only from it.|
|1011 MUST NOT|Receptor allowlists are derived from it, never edited by hand at fleet scale.|**D** rfc|manifest:131-133, __main__:82-87|The manifest is itself a hand-kept JSON copy per host: keygen appends to it, revocation is a manual edit on each host plus a restart. Nothing derives it from a signed source. Admitted: prototype/canticle-docs/state-layout:55-56.|
|1011|what anchors it is a root set provisioned out of band|U||No root set.|
|1015|Format: a deterministic-CBOR map|**D** rfc|manifest:30-34,127-133; fe/manifest:133-139|Plain JSON, manifest: "canticle-fleet/spike-0", read by two loaders (Python, TypeScript). Admitted: README:63.|
|1015 MUST|signed by at least k of the n root keys it names ‖ Each signature is Ed25519 over "binary-canticle/manifest/v1" ‖ 0x00…|U×2||No signature field or check. verify refuses signed: true No manifest signing or verifying code|
|1019|version, serial / Format version|**D** rfc|manifest:30,177-178|A format label exists, but only verify, show, doctor and dns-browse check it. The daemon loads a file with any label or none and copies the label into hello.|
|1019 MUST|serial strictly increasing|U||No serial.|
|1020 dflt|not_after − issued_at ≤ 7 days [PROPOSED DEFAULT]|U||No issued_at or not_after: a spike manifest never expires.|
|1021, MUST|Root public keys and k: 1-of-1 is acceptable for the cohort… ‖ 2-of-3 is REQUIRED before fleet deployment (D15)|U×2||No roots or threshold fields. No roots. S5 work item (RFC line 3275) and an operator gate.|
|1022|[{id, name, kind: operator \/ host \/ service \/ human}]|U||No principals|
|1023|[{pk, key_id, principal, name, role: station \/ relay \/ keeper \/ issuer \/ control, caps: [capability]|**D** rfc|manifest:33,36-48; fe/manifest:26-38|Entry: name, public_key, key_id (optional), classes, streams, public_streams, scopes, revoked. No principal or role; classes (class names) stands in for caps; public_streams is not in the RFC table. Admitted: README:63.|
|1023|scopes: [host, lan, fleet, public]|I|manifest:44,118; fe/manifest:159-171; t/listener:190|Enforced by station and receiver.|
|1023|streams?: [name patterns]|**D** rfc|manifest:42, station:283-284; fe/manifest:31-32|Exact names, no patterns. A station enforces them only when the list is non-empty; a receiver only maps stream ids to names with them. Admitted: README:497-498.|
|1023|not_before, not_after}]|U||Keys have no validity window.|
|1023 MUST|key_id MUST equal SHA-256(pk)[0:8]|**D** rfc|manifest:119-123,219-224; fe/manifest:139-172|canticle-station refuses a listed key_id that differs (an absent one is derived). frond-ear violates: it ignores the listed key_id, so a manifest the daemon refuses loads in the embedded ear.|
|1023 MUST|duplicate key-ids make the manifest invalid|I|manifest:88-89,216-217; fe/manifest:103-107; t/manifest:114||
|1024|relays / [{key_id, endpoints, tier: lan \/ fleet \/ public}]|U||No relays field.|
|1025|Overrides of the class table (§6.2) and regulation profile (§12.8)|U||The class table is a code constant; no manifest override.|
|1026, MUST, MUST|[{stream pattern, audience: public \/ fleet \/ private}] ‖ fleet and private streams need a listen capability to lease… ‖ private streams also need link or payload encryption|U×3||Only public_streams exists: exact names per key that may be… No leases, no listen capability. No encryption, no private audience.|
|1027|Key-ids allowed to sign listen capabilities (§11.3.6)|U||No listen issuers.|
|1028|Eligible principals per class: the fixed denominators N_c (§10.7)|U||No accord section.|
|1029|[{key_id, revoked_at, reason}], root-signed as part of the manifest|**D** rfc|manifest:43,116; fe/manifest:158|A hand-set boolean on the key entry: no time, reason or signature. The loaders disagree: Python revokes on any truthy value, frond-ear only on literal true, so "revoked": 1 stays trusted there. Admitted: prototype/canticle-docs/state-layout:55-56.|
|1033|Fetched over HTTPS from a location in configuration or in the… ‖ cached on disk; refreshed every 24 h ‖ on a root-signed MANIFEST-REFRESH control frame (§10.6) ‖ Refresh means re-fetch and revalidate.|U×4||A local file path only. dns_browse ignores mfst Read once per process start. No control frames. No refresh of any kind.|
|1034 MUST|A receiver whose manifest has passed not_after MUST fail closed ‖ it keeps processing control frames from the last known root and…|U×2||No expiry, so an old manifest is trusted for ever. None of the three: no root, no expiry mode, no operator alert.|
|1035 MAY, MUST, MUST|A single-owner cohort MAY run a 1-of-1 root for the pressure test. ‖ roots MUST be 2-of-3, offline and held by humans ‖ root-key backup and recovery MUST be documented before the switch|U×3||Optional. The cohort runs with no root at all. No roots. S5 work item; human custody is owner practice. No such document in the repo.|
|1039 MUST NOT|A receiver MUST NOT accept a manifest unless it verifies against a root set, or the SHA-256 digest of a genesis…|**D** rfc|daemon:396-403, manifest:109-133; fe/src/cli:123-127|Every loader accepts any JSON that parses. hello.manifest_sha256 is reported but compared with nothing. Any process that can write fleet.json or stations.toml widens trust at the next restart. Admitted: README:63, README:119-121.|
|1039 MUST|The install ships the genesis root set or genesis-manifest digest|U||No packaged pin.|
|1039 MAY|configuration management and stations.toml MAY carry it too|**D** code|stations:26-27,111-116|stations.toml refuses a [trust] table on purpose: a pin that cannot be enforced is worse than none. Right until manifests are signed. Admitted: README:63.|
|1039 MUST NOT|The trust anchor is never fetched from DNS, HTTPS or a configured…|I|stations:79-94, manifest:131-133|Vacuous: there is no anchor and nothing is fetched|
|1039 MUST|A manifest found by location alone (configured URL, DNS-SD mfst=, HTTPS) is only a candidate.|**D** rfc|stations:93-94, daemon:396-403|The file stations.toml or --manifest names is trusted outright, by location alone. (No URL or DNS source exists.) Admitted: README:63.|
|1039 MUST NOT|HTTPS and the WebPKI authenticate the server, not the fleet, and…|I|manifest:131-133|Vacuous: no HTTPS path. No test.|
|1040 MUST|MUST carry signatures meeting the threshold of the current set as… ‖ A receiver that cannot see such a chain from its pinned set MUST…|U×2||No roots, no rotation. No pinned set, no alert channel.|
|1041 MUST|A receiver MUST durably record the highest serial it has accepted… ‖ MUST reject a manifest with a lower serial, or the same serial and… ‖ the latter is root equivocation: alert|U×3||The persisted state holds no manifest serial or digest. Any manifest is accepted at start: restoring an older… No serial, no alert.|
|1045 MAY|A 1-of-1 root is acceptable.|U||Optional. No root.|
|1046 MUST|2-of-3 offline roots, held by humans, with backup and recovery…|U||S5 work item and owner practice.|
|1047 MUST|Root holders and alarm-key holders MUST be separate.|U||No roots and no principals, so nothing can express or check it.|
|1048 MUST|It ships with the install and is never fetched.|U||No genesis pin.|
|1049 MUST|A manifest lives at most seven days, and receivers re-fetch and… ‖ Root-set changes need both thresholds. Receivers keep durable…|U×2||No lifetime; one read per start. None of the three.|
|1051|keeps its role as a locator|I|stations:22-25,67-94; t/stations:45|Holds manifest path, bind and multicast only; unknown keys are errors.|
|1051 MAY|is one place the genesis pin (root keys and threshold, or a genesis manifest digest) MAY be provisioned|**D** code|stations:26-27,111-116|[trust] is refused with an error until a pin can be enforced. Admitted: README:63.|
|**§10.4**|**Capability classes** (7 I · 5 D · 5 U · 1 ?)||||
|1057|chatter, ambient / classes 1, 2 / any session station|I|station:278-284, listener:298-300; fe/listener:690-700; t/station:461|Manifest classes by name|
|1058|live-state, root / classes 3, 9|I|station:278-284, listener:298-300; fe/listener:690-700; t/station:461|Class check as above. "Restricted to their lens.|
|1059|advisory / class 4 / keepers, sentinels|I|station:278-284, listener:298-300; fe/listener:690-700; t/listener:142|Class check; holder not checked.|
|1060|finding-ref / class 5 / session stations, ledger services|I|station:278-284, listener:298-300; fe/listener:690-700; t/station:461|Class check; holder not checked.|
|1061|regulatory / class 6, ops tighten, all-clear, lower-attention, grounding-anchor|**D** rfc|listener:298-300, runner:28-31; fe/listener:690-700|The grant covers all of class 6: no op is parsed, so a regulatory key may also sign quarantine ops. The control socket refuses the class; a receiver surfaces a class-6 frame as an ordinary item. Admitted: README:17.|
|1062|quarantine / class 6, ops quarantine-vote, rescind-vote|U||No quarantine capability: grants are class names only.|
|1063|alarm / class 7 / human-operated stations|I|station:278-284, listener:298-300; fe/listener:690-700; t/station:496|Class check at the receiver; the control socket never sings it.|
|1064 MUST|manifest roots and root-delegated control keys only|**D** rfc|listener:298-300, __main__:74-86; fe/listener:690-700|Any entry may list control, and keygen --classes control grants it to any new key. A class-8 frame from it is verified and surfaced as a plain item. No root or delegation exists. Admitted: README:66.|
|1066 MUST|A frame whose class or op exceeds its key's capability MUST be…|I|listener:298-300, records:61; fe/listener:690-700; t/records:178|For the class.|
|1066 MUST|whose class or op exceeds its key's capability|U||Op half: no op inside a typed body is parsed by sender or…|
|1066 MUST|with zero accord weight and evidence capability-exceeded|**D** owner|listener:299, records:61; fe/listener:690-700|Evidence is named capability (listener, vectors), the admission capability_exceeded; no accord exists to weigh zero. §14.18.3 uses the code names, so one of the two texts must move.|
|1067 MUST|A frame whose scope exceeds the key's scopes|I|listener:305-308, records:345-351; fe/listener:713-724; t/records:178|Record: capability_exceeded, ringbuffer_only, reason scope_not_granted.|
|1067 MUST|whose stream is outside the key's streams patterns, is treated the same way|**D** rfc|listener:296-298,449-453; fe/listener:962-967|Not checked: verified/unnamed_stream, with body, and it changes state (epoch, dedup quota, marks, presence; a PLUCK there retracts). RFC line 2236 admits it; §10.4 and §14.18.3 rows overlap. Admitted: README:497-498.|
|1068 MUST NOT|An LLM-driven session MUST NOT hold a key with quarantine, alarm or control|**D** rfc|runner:31,121-131|Enforced one step later: control socket and plugin never accept alarm, regulatory or control. The grant is free (keygen gives any class to any key), keys carry no principal kind, same-uid sessions can read key files. Admitted: README:17.|
|1070 MUST|in v1, alarm keys are operated by humans|**?**|runner:31|Operator practice; the manifest cannot say who operates a key. The only CLI publish path refuses alarm. Each manifest owner could answer.|
|1072 MUST|stays disabled behind an explicit feature flag ‖ The flag stays off until the S5 worm range (§22.7) shows resistance|U×2||No issuer and no flag, so nothing can issue an alarm… No flag; S5 not started.|
|1073 MUST|Alarm-key custody is separate from manifest-root custody (D15).|U||No roots; nothing to separate.|
|**§10.5**|**Key lifecycle** (2 I · 5 D · 2 U · 1 ?)||||
|1077|Station keys are generated and held by the per-host daemon (or an OS keystore).|**D** rfc|__main__:63-64,95-109|keygen writes a plain hex seed (0600); each canticle station process loads it and signs. canticle daemon has no key code and ignores sing. D35 (daemon holds keys, signs every publish) is unbuilt. Admitted: README:64, :445-447.|
|1077 MUST NOT|The model never sees a private key.|**D** rfc|__main__:41-42,95-109|No socket op or tool returns it, but every process of the uid, agent sessions included, can read the seed file (#168 §4.4, binary-canticle#99: "host-proof, not seat-proof"). Admitted: prototype/canticle-docs/state-layout:48-50.|
|1077 SHOULD|alarm, control and manifest-root keys SHOULD live offline or in…|U||keygen has one form, a plain file, for every class|
|1077 MUST NOT|Station keys MUST NOT live on dashboard hosts.|**?**|shape:1-11|Nothing checks it and "dashboard host" is undefined. canticle shape serves a human display from hosts that, on the pilot, also keep a station key. Host owners could answer.|
|1078|Add the new key to the manifest with an overlap of at least one…|U||keygen allows a second key under one name and says both are…|
|1078|The station switches keys; items signed by the old key expire…|I|__main__:139-158, listener:648-655; t/listener:61|By restarting the station with another --key.|
|1079|A root-signed manifest entry, plus a root-signed REVOKE control frame (§10.6) looped for fast propagation.|**D** rfc|manifest:102-103,116; fe/manifest:121|Only an unsigned boolean edited by hand on each host. No command for it, no REVOKE frame. Admitted: prototype/canticle-docs/state-layout:55-56.|
|1079 MUST|Receivers MUST drop frames from a revoked key within one refresh interval of the revocation becoming visible|**D** rfc|daemon:396-403, wire:422; fe/src/cli:123-127|Dropped only once the process restarts: running daemon, listener, station and ear never re-read the manifest, so there is no bound. A running station keeps signing too. Admitted: README:504.|
|1079 MUST|MUST replace any pending digest content from that key with a "revoked" notice|**D** rfc|records:255-280, pl/receive:447-465; fe/records:573-579|Daemon: retract reason revoked, only at start. Plugin journals the reason and shows a generic withdrawn note. frond-ear drops the item silently, no notice. Admitted: README:477, :504.|
|1080|Equivocation (§10.8) and epoch regression (§5.2).|I|listener:324-328,238-240; fe/listener:749-758; t/records:222|Both are detected|
|**§10.6**|**Control frames** (8 U)||||
|1084 MUST|Control frames are ITEMs of class control (8), content type 10… ‖ They are also published out of band next to the manifest|U×2||Only the codes exist. The socket never sings class 8 No out-of-band publication.|
|1088|; op: 0 MUTE, 1 UNMUTE, 2 REVOKE, 3 ALL-CLEAR-FLEET, 4…|U||No control-body codec (keys 1-3) in any implementation.|
|1094 MUST|receivers stop landing and waking for every non-control class until… ‖ relays forward only control frames ‖ UNMUTE needs authority at least equal to the MUTE's.|U×3||landing_state.mute is always null; only tests call set_landing. No relay. No MUTE or UNMUTE.|
|1095, MUST|ALL-CLEAR-FLEET clears alarms fleet-wide ‖ its authority MUST be at least that of the alarms it clears…|U×2||No op.|
|**§10.7**|**Accord** (12 U)||||
|1105 dflt|Σ over distinct lineage roots i of principal p on σ of a_i) E_cap =…|U||No accord, salience weight or saturation anywhere.|
|1107 dflt|{principal(target)} : E_p(σ) ≥ e_min }/ e_min = 0.5|U||No quorum count.|
|1108|N_c = /Eligible(c)/ from the manifest (never "keys heard")|U||No eligible sets in the manifest.|
|1113 MUST, MUST NOT|Accord MUST count distinct principals from the manifest, one vote… ‖ It MUST NOT count keys heard, frames or repeats.|U×2||No accord, no principals. Nothing counts anything toward accord.|
|1114|A frame whose derived_from names a known root contributes only… ‖ Same-principal items with equal body digests are one root.|U×2||derived_from and root are parsed and reported No such grouping.|
|1115|The denominator is fixed by the manifest.|U||No denominator.|
|1116 dflt|one capable principal (q = 1, E ≥ 1.0) ‖ q = max(2, ⌊N/3⌋ + 1) principals excluding the target ‖ Loosening (rescind, all-clear by accord): q + 1, or root-signed.|U×3||No tightening. No quarantine vote No rescind.|
|1117 MUST NOT|No quorum may be declared below two principals, except for effects…|U||No quorum exists.|
|**§10.8**|**Equivocation** (2 I · 3 D · 3 U)||||
|1121 MUST|Receivers MUST keep tuple → digest for every accepted frame until…|I|listener:368-370,610-626; fe/listener:818-826; t/listener:160|Kept to local expiry + 5 s, never evicted early, persisted across restart.|
|1122|Two different, validly signed frames under one identity tuple|I|listener:321-328, records:355-356; fe/listener:749-758; t/records:222||
|1122|or two concurrently live epochs of one key (§5.2), are an equivocation|**D** owner|listener:315-318,555-586; fe/listener:741|Never treated as equivocation: the lower epoch is only epoch_regression, however long it lasts (§5.2: more than two beacon periods). BC-1 (line 1147) and this line need one rule.|
|1122 MUST|The receiver MUST quarantine the key locally|**D** code|listener:321-328, records:355-356; fe/listener:749-758|Daemon complies (persisted; later items ringbuffer_only, surfaced ones retracted). frond-ear embedded and canticle listen violate it: evidence only. The daemon quarantine has no TTL (§14.7.3: 1 h; README:502). Admitted: README:492.|
|1122 MUST|record the evidence|**D** rfc|listener:211-214,324-328; fe/receptor:420-434|Kept: a counter, a frame record and the quarantined key id. Neither frame is kept (first digest only; the second record has sha256 null), so nothing another party could check survives. Admitted: README:507-512.|
|1122 MUST, SHOULD|and alert its operator ‖ It SHOULD submit both frames to the ledger as a transferable proof.|U×2||health.quarantined lists key ids every 10 s. No ledger client, and the first frame is not kept, so it could…|
|1123|anyone can verify the two signatures locally without trusting the…|U||No proof object is produced or read.|
|**§10.9**|**Admission results** (23 I · 9 D · 2 U)||||
|1127 MUST|Every frame gets exactly one:|**D** code|records:47-54,316-332|ITEMs do. A BEACON gets its own counter and an admitted PLUCK emits retract and counts no admission. §14.18.3 says the same, so the RFC contradicts itself here.|
|1131|verified / New, valid, capable, fresh / continue to the receptor|I|records:389-397,440-497; fe/listener:981-999; t/records:130||
|1132|duplicate / Already-accepted tuple, same bytes.|I|listener:333-336, records:383-385; fe/listener:765-768; t/records:150||
|1132|which is reported once as verified with dedup: resurfaced (§14.18.3)|I|listener:337-347, records:479; fe/records:1266-1268; t/records:380|Once per run per tuple accepted before the restart.|
|1133|unknown_key / key_id not in the manifest / counted (D34)|I|wire:422-424, records:328-332; fe/listener:586-591; t/records:508|#173 #173/intake:598 may refuse such a datagram unverified, counted as receive.refused.unlisted instead|
|1133 MUST NOT|never quarantine, never a receipt (prototype B11)|I|records:328-332,355-356; t/records:508|Quarantine is reached only from a verified equivocation|
|1133 MAY|MAY enter the debug ring|U||Optional, here and for bad_signature.|
|1134|bad_signature / Signature fails / counted (D34); MAY enter the…|I|wire:450-456, records:57-59; fe/wire:554-558; t/records:508|Includes non-canonical S. Counted, no record. The MAY is not taken up.|
|1135|revoked / Key revoked / drop; counted (D34)|I|manifest:98-104, records:57-59; fe/manifest:117-123; t/wire:152|Decided before the signature is checked, so anyone can raise this counter.|
|1136|Class, op, scope or stream beyond the key's capability|**D** rfc|listener:298-308, records:345-354; fe/listener:690-724|Class and scope: yes. Op: never parsed. Stream: not checked, verified / unnamed_stream instead. Admitted: README:497-498.|
|1136|ringbuffer_only; zero accord|I|records:61,349-351; t/records:178|Disposition label, no body in the record, never deliverable.|
|1137|expired / not_yet_valid / Outside the time window / drop|I|wire:445-449, records:57-59; fe/listener:586-591; t/wire:152|Not for BEACONs. Checked before the signature, so counted as unverified.|
|1138|Older keyed item of the mark's class; sticky-plucked tuple|I|listener:393-395,424-428; fe/listener:902-914; t/records:202||
|1138|(plucked takes precedence over superseded and class_change)|I|listener:418,425; fe/listener:888-914; t/listener:569|Both precedences hold. Not applied on the lower-epoch path (line 1147).|
|1139|The key's dedup entries, or its supersession marks, are at their…|I|listener:359-366,493-529; fe/listener:802-816; t/records:191|drop and a frame record; never surfaced.|
|1140|PLUCK expires_at or scope differs from its held target's (§7.7…|I|listener:350-358, records:62; fe/listener:780-801; t/listener:710|Only while the target's dedup entry is held.|
|1141|A keyed item, older or newer, whose class differs from its held…|I|listener:415-422, records:64; fe/listener:880-899; t/listener:760||
|1142|equivocation / Same tuple, different bytes / local key quarantine; evidence|**D** code|listener:321-328, records:355-356; fe/listener:749-758|Daemon: equivocation, quarantine_set, retracts. frond-ear embedded and canticle listen only count evidence. Admitted: README:492.|
|1143|scope_violation / Scope not allowed on this binding or tier / drop|I|listener:301-304, records:345-351; fe/listener:701-712; t/records:184|Only "narrower than the binding" (a host frame over UDP). No tiers exist|
|1144|hop_limit / hop above the class hop limit|I|listener:309-312, records:61; fe/listener:725-738; t/records:188||
|1145|malformed / crit_unknown / version / Parse, crit or version failure…|I|wire:407-444, records:57-59; fe/listener:586-591; t/wire:152||
|1147|A lower epoch is evidence, not an admission result.|**D** rfc|listener:315-318,583; fe/listener:741|True of the daemon. frond-ear embedded and canticle listen drop every lower-epoch frame, and the epoch-regression vector pins that older behaviour. Admitted: README:491-492.|
|1147|lower than the highest seen for its key within the class maximum TTL|**D** rfc|listener:238,242; fe/listener:606|No window: epoch_seen_at is stored and saved but never read, so a lower epoch is held back for ever, across restarts. A station whose counter regressed recovers only by passing its old epoch.|
|1147|records evidence epoch-regression, supersedes nothing and advances…|I|listener:555-559,583-586; fe/listener:606-611; t/records:238||
|1147|and is otherwise admitted as any frame is|**D** rfc|listener:555-586, records:373-382; fe/listener:741|_lower_epoch only adds a dedup row: no pluck, pluck-mismatch or class checks. A valid lower-epoch PLUCK withdraws nothing and emits a frame; §14.18.3 wants a retract for every valid PLUCK.|
|1147|A repeat of an already-accepted tuple is duplicate (§7.4), which…|I|listener:565-572; t/records:238||
|1147|A new tuple is verified, with reason epoch_regression and…|I|listener:575-586, records:359-363; t/records:238|Daemon only; frond-ear embedded drops it (first row of this line).|
|1147|a station's persisted old-epoch live set (§7.3) is kept but does…|I|listener:575-586; t/records:238|"Kept" is the dedup digest only: no hearer ring.|
|1149|gets no per-frame record and no receipt|**D** code|records:319-332, listener:227-229; fe/receptor:426-433|Daemon complies. canticle listen --evidence prints one event per rejected datagram; frond-ear embedded writes one debug log line each. Admitted: README:492.|
|1149|The receptor counts such frames in fixed per-reason aggregates plus a table of at most 16 key ids by count with an…|**D** code|records:40,49-50; fe/receptor:564-583|Daemon complies in full. frond-ear embedded keeps only per-reason counters and has no key-id table or other bucket. #173 adds receive.refused.{unlisted,unverified,over_rate,backlog} for datagrams it never verifies (#173/intake:93)|
|1149 MAY|MAY keep them in the bounded local debug ring (§14.1)|U||Optional. No debug ring.|
|1149 MUST NOT|They are never deliverable to a session or model|I|records:328-332, pl/receive:434-438; fe/records:1196-1204; fe/t/canticle-records:124||
|1149 MUST NOT|never attributed to a station, principal or manifest name|**D** code|listener:226-229, records:328-332; fe/listener:586-591|Daemon complies. Listener.hear and its frond-ear port name the manifest station when the claimed key id is known, so a forged frame is printed (listen --evidence) or logged as that station. Admitted: README:475, :492.|
|1149 MUST NOT|No receptor structure is keyed by a sender-chosen value without a…|I|listener:493-537,273-286; fe/listener:1036-1117; t/listener:303|Dedup, marks, plucks, hearing times, beacon pages and the key table are capped #173 adds per-source tables with fixed bounds (#173/intake:82-86)|
|**§10.10**|**The prototype as donor** (2 I · 2 D)||||
|1153 SHOULD|The verify stage SHOULD reuse from prototype/ringserver-udp-cue/: the strict parse discipline|**D** code|cbor:83-163, wire:425-444; fe/wire:469-491|Not reused; written again for CBOR. Canonical check, duplicate-key rejection and exact types are all there. The JSON donor does not fit the wire.|
|1153 SHOULD|per-key policy (now compiled from the manifest)|I|manifest:36-48, listener:294-312; t/listener:142||
|1153 SHOULD|typed receipts, extended with a frame pointer and evidence|**D** owner|records:440-497|Record v1 frame records play this role with sha256 and size, but no ring holds the bytes they point at, and evidence is only a reason code. Admitted: README:507-512.|
|1153 MUST|Before reuse, its bugs MUST be fixed|I|wire:399-404,27; t/listener:823||
|**§10.11**|**How this closes #48** (3 I)||||
|1160|Per-station Ed25519 (§9.3); threat model §19|I|wire:212-218; t/wire:152|The primitive.|
|1163|Identity tuple, absolute expiry, dedup as no-op (§7.4, §14.6.3)|I|wire:149-155,368-388; fe/listener:742-768; t/listener:69||
|1165|threat table and test vectors|I|vectors:73-231; t/wire:161||

### §11 Transport bindings

180 claims: 38 I · 16 D · 125 U · 1 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|1171|Four bindings carry the same frames|**D** code|daemon:482-493, records:78-83|Only (b) and plain unicast UDP carry frames. The host-local socket carries record v1 JSON, never a frame (BC-1a/D35 chose that); (c) and (d) are unbuilt. The sentence contradicts BC-1a inside the RFC.|
|1175 MUST|Host-local (unix socket)|I|daemon:454-463,350-373; fe/record-client:69-110; t/daemon:126|Receive half only: record v1 to every binding.|
|1175|(unix socket) / 1 / MUST|**D** rfc|station:285-286, runner:139-140|Scope 1 has no path: host items cannot be sung (station speaks UDP only) and would be a scope violation if heard. No frame ever enters by the unix socket. RFC better: host scope needs a local path. Admitted: README:17.|
|1176 MAY|LAN multicast fast path|I|__main__:165-166, runner:143-147|Off by default (--multicast or stations.toml multicast = true).|
|1176|used only when the doctor passes|**D** rfc|stations:90-94, __main__:165-166|Nothing gates multicast on a doctor result: a config key or flag turns it on ('Setting multicast = true is your decision'). RFC better, but needs a full doctor first. Admitted: README:130-138.|
|1177 MUST|MUST; the default outside a known wired VLAN|U||A MUST binding with no code.|
|1178 SHOULD|(TCP, via a DataLink bridge)|U||No relay-side bridge.|
|1179 MAY|WebTransport from relays to browsers|U||optional; no WebTransport code in any snapshot.|
|1180 MAY|NATS WebSocket/TCP listener binding|U||optional; no NATS code in any snapshot.|
|1182|"No subscription at the sender" stays true on every binding|I|runner:134-203,82-118|Station half true: it sends to a fixed list and reads nothing from listeners|
|1182|leases live in relays, never in stations (I-1)|U||No lease exists. The station holds none (nothing contrary).|
|1184|internet listeners are in scope, through relay-held leases|U||D6: nothing built|
|1190|UDP carousel (§7, §11.2, §11.3)|I|runner:186-195, station:396-445; t/udp_e2e:24|Station half: UDP carousel, unicast or multicast.|
|1190|Broadcast edge: station or relay → listeners|U||Relay half of the plane: no relay.|
|1191|Soft-state membership: beacons, presence|I|station:401-402, listener:725-752; t/udp_e2e:24||
|1192|Relay ↔ relay backbone|U||No relay, so no backbone.|
|1193|Clean-path snapshots, replay, dashboards|U||No TCP snapshot or replay tier, and no fill.|
|1193|the carousel and fill (§7.10)|I|station:417-431; t/station:414|Carousel half: a late joiner catches up passively.|
|1193|fill (§7.10) as the fallback|U||Fill half: no relay fill.|
|1194|Ledger (findings, promotion)|**?**|finding:1-20, runner:55-67|The ledger (GitHub, https) is outside these repos; no code promotes. Findings themselves ride the UDP carousel as keyed advisories, with a body_ref URL to the ledger that nothing fetches. Owners of the probe profile could answer.|
|1195|Addressed, durable control|U||No control plane.|
|1197|One relay: no broker.|I|cs/pyproject.toml:10|Nothing contrary: no broker dependency anywhere. Vacuous, no relay.|
|1198|simple custom relay-to-relay forwarding|U||No relay.|
|1199|only when multi-relay fleet operation actually justifies it, and…|I|cs/pyproject.toml:10||
|**§11.1**|**Host-local binding** (18 I · 7 D · 5 U)||||
|1203|exposes a unix domain socket in a per-user runtime directory with…|I|daemon:77-79,429-439; fe/src/config:322-328; t/daemon:126|Refuses a directory not owned by it or not 0700.|
|1203|the socket itself has mode 0600|I|daemon:456-463; t/daemon:126||
|1203|the socket is SOCK_STREAM, framed as in §14.18.2|I|daemon:458, records:78-83; t/records:104||
|1203 dflt|non-ASCII escaped, at most 64 KiB per line and nesting depth 8|I|records:34-35,78-83; fe/records:52-53; t/records:104|Limits raise, never sent.|
|1203|an over-long line is discarded up to its newline|**D** rfc|daemon:186-199, tap:507-508; fe/record-client:113-145|fe and the plugin comply. Daemon: the size check runs only on chunks without a newline, so a split first line up to ~128 KiB is parsed. canticle tap stops with malformed_record instead of discarding (README:611 says exit 2).|
|1203|deeper nesting is rejected before parsing completes|**D** rfc|daemon:256-262, tap:515-518; fe/records:460-463|fe and the plugin check depth first. The daemon json.loads the request, then measures depth (RecursionError caught). tap checks no depth, and RecursionError escapes it. Same-uid peers, so low risk.|
|1203|and both are counted|**D** rfc|daemon:196-198,204-207; fe/records:475-478|fe and the plugin count each. Daemon lumps both into one snapshots.ignored with every other ignored line; tap counts nothing.|
|1203 MAY|with one JSON object per message under the same limits|U||optional: no packet socket (SOCK_SEQPACKET / SOCK_DGRAM)…|
|1203 MUST|A daemon MUST serve the stream form|I|daemon:454-463; fe/record-client:75-88; t/daemon:262||
|1203 MAY|it MAY also serve a packet form on a second path ‖ It is also the child's stdout framing (§14.18.2)|U×2||optional; not built. No child-process receptor prints record v1 on stdout|
|1204 MUST|It MUST check peer credentials (SO_PEERCRED on Linux|I|daemon:350-358, runner:47-52; t/daemon:149||
|1204 MUST|getpeereid / LOCAL_PEERCRED on BSD and macOS|U||Only SO_PEERCRED.|
|1204 MUST|against its allowed users|**D** owner|daemon:94,429-439|--allow-uid is plural, but 0700 dir plus 0600 socket means only its own uid (and root) can connect, whatever is listed (#99). The RFC's modes and its 'allowed users' contradict each other. Admitted: prototype/canticle-docs/pilot-host/README:371-37….|
|1204 MUST|on every accepted connection or message, and reject everything else|**D** rfc|daemon:355-358, runner:151-163|Daemon complies. The station control socket, which plays this socket's publish role, fails open: uid is not None and uid != getuid() lets a peer through when SO_PEERCRED is missing. No test refuses a uid there.|
|1204|and reject everything else (test RT-16)|I|daemon:355-358; t/daemon:149|Covered by these, under no RT id. A wrong uid is simulated by allowing uid+1.|
|1205|publish tools send sing/hush requests (§15), not frames; the daemon signs|**D** code|runner:82-118,151-177|The daemon signs nothing and ignores sing lines. Each station process has its own control socket and key. Code better: the process parsing hostile UDP holds no keys; the RFC should describe that socket. Admitted: README:445-447. #162 adds cue_ and derived_publish/derived_query to the station control socket (#162/runner:88-98), not to the daemon|
|1205|Sessions and hooks read digests and events (§14.14, §16)|U||The daemon serves records only; no digest op.|
|1205|the daemon also carries record v1 (§14.18.3) over this socket to…|I|daemon:231-246; fe/record-client:112-146; t/daemon:262||
|1205|under the backpressure and gap rules of §14.18.2 applied per…|I|daemon:134-149,239-246; t/daemon:423||
|1205|at the head of each connection it writes the run's hello and its…|I|daemon:232-236,370; t/daemon:319||
|1205|and then the live stream from the next record it emits|I|daemon:369-373; t/daemon:319||
|1205|Taking those two records and attaching the connection to the live…|I|daemon:367-373; t/daemon:319||
|1205|the jump in rec_seq after the bootstrap is a join, not a loss|I|tap:482-530, pl/daemon:104-128; fe/records:532-550; t/tap:88|Binding-side rule|
|1205|gets a bounded join snapshot of the run's current surfaced items…|I|daemon:253-330; fe/record-client:80-86; t/join_snapshot:199||
|1205|cut atomically against that connection's live stream|I|daemon:302-328; t/join_snapshot:263||
|1205|The socket carries the binding's request as well as the daemon's…|I|daemon:175-202; fe/record-client:85; t/tap:403|Only the join-snapshot request, only as the first line.|
|1205|as it carries sing/hush requests|**D** code|daemon:196-198, runner:82-118|It does not: a sing line is read, counted and discarded. sing/hush go to the station's control socket. Same split as above; a sing sent to the daemon gets no error. Admitted: README:445-447.|
|1206 MUST|Frames that arrive on UDP loopback are verified exactly like frames…|I|daemon:489-491, runner:222-228; fe/receptor:308|The address is ignored on the receive path. #173 reads the source address for fair admission only (#173/intake.py); verification unchanged|
|1206|There is no loopback exception.|I|daemon:489-491|Nothing contrary exists; source address is never consulted. No test.|
|**§11.2**|**LAN multicast fast path** (8 I · 6 D · 10 U)||||
|1210|IPv4 239.255.13.13 (provisional)|I|runner:27, daemon:407; t/doctor:155|One constant, not configurable. frond-ear never joins a group.|
|1210|inside the IPv4 local scope 239.255.0.0/16|I|runner:27||
|1210|IPv6: a link-local ff02:: group and optionally a site-local ff05…|U||All sockets are AF_INET; stations.toml refuses IPv6 binds.|
|1211|Advertised by DNS-SD SRV/TXT (§13)|U||Nothing publishes SRV/TXT.|
|1211 dflt|The v0.1 port 9999 remains a provisional development default|I|runner:32, stations:24; fe/src/config:284; t/stations:52||
|1211|always advertise ports through SRV; keep 9999 only for development|**D** rfc|runner:32, cs/docs/pilot-host/canticle-pilot.nft:27|D22: 9999 is the port on the pilot's prince hosts, with no SRV. The kit and README call it provisional; no text says the pilot departs (unless the pilot counts as development).|
|1212|IP TTL / hop limit 1 (the Linux default for multicast)|I|runner:145|Set explicitly on the station socket.|
|1212|Canticle multicast stays on the link|I|runner:145|By TTL 1.|
|1213|Receivers bind with SO_REUSEADDR/SO_REUSEPORT|**D** code|daemon:417-422, runner:211|The daemon binds with neither, on purpose: §14.18.2 proof case 1 (D35) wants exactly one process on the port. Only listen and tuner set SO_REUSEADDR; SO_REUSEPORT is used nowhere. RFC contradicts itself here. Admitted: README:412.|
|1213|in practice only the host daemon listens (§4.2)|I|daemon:417-419, __main__:411-418; fe/source:71-84; t/daemon:229|While the daemon runs, listen and a second daemon fail to bind, and fe's embedded…|
|1214|Use one any-source group per band and filter by key and stream in…|I|daemon:420-422, listener:221-230|One group, any-source join, filter by manifest key and stream id.|
|1215|Subnet broadcast (‹subnet›.255, SO_BROADCAST)|U||No SO_BROADCAST on any socket, so --to x.y.z.255 fails with…|
|1216 MUST|Senders MUST respect B_station (§7.5)|**D** rfc|station:218-230,376-377|Burst copies are charged to nothing, sing is never refused for load, and each frame goes once per destination, so egress exceeds B_station. Loop repeats, PLUCKs included, stay inside B_stream. Admitted: README:71.|
|1217|prefer the relay lease there|U||No lease to prefer.|
|1219|decides whether (b) is usable|**D** rfc|doctor:238-258,60-62|It only reports multicast and never decides. Instead it checks Python, cryptography, stations.toml, manifest and bind address, none of which §11.2 mentions. Admitted: README:130-138.|
|1221 MUST|Check interface MTUs and warn if the path cannot carry a 1 228-byte…|U||Step 1: no MTU check.|
|1222 MUST|Join the group and send a signed probe on stream x-test.doctor (scope lan)|**D** owner|doctor:200-225,232-235|Step 2: an unsigned nonce on an ephemeral port at IP TTL 0, only if multicast is configured or --probe. Safer, but proves nothing about the LAN. RFC's signed probe needs a station key on a listen-only host. Admitted: README:130-138.|
|1222 MUST|confirm it comes back via IP_MULTICAST_LOOP|I|doctor:209-218|The unsigned probe's own loop-back is checked (1 s).|
|1223 MUST|Listen 10 s for peer beacons and report which stations it heard|U||Step 3: not built.|
|1224 MUST|Keep its membership for at least 270 s and check peers again|U||Step 4: not built.|
|1225 MUST|Detect Wi-Fi interfaces and client-isolation symptoms, container…|U||Step 5: none of the four detections is built.|
|1226 MUST|If multicast failed, try subnet broadcast|U||Step 6: not built.|
|1227 MUST|Record the result and recommended binding in configuration|U||Step 7: doctor writes nothing, by design (test_doctor:302).|
|1227 MUST|Exit codes: 0 multicast OK; 10 broadcast only; 20 relay lease required; 30 no LAN peers heard|**D** neither|doctor:268-270, __main__:631-636|0 = every host check passed, 1 = one failed. So 0 means 'multicast OK' in the RFC and 'says nothing about multicast' in code. One code cannot carry both verdicts; RFC needs two. Admitted: README:136-138.|
|**§11.3.1**|**Principles** (6 U)||||
|1233|The lease renewal is also the NAT keep-alive|U||No lease. E4/E5 stubs RENEW every 22 s ± 20 %, on loopback.|
|1234 MUST, MUST NOT|No stream flows before a stateless cookie round trip ‖ a relay MUST NOT send more bytes to an address than it received…|U×2||No relay.|
|1235 MUST|Relays MUST stay silent to anything unauthenticated|U||No relay. E4/E5 stubs drop a bad cookie silently.|
|1236 MUST|A relay MUST reply from the same IP address and port the listener…|U||No relay. The stubs use one socket, so they comply trivially.|
|1237|One lease per host (§4.2)|U||No lease client.|
|**§11.3.2**|**Messages** (26 U)||||
|1241, MAY|All lease messages start with magic, version and kind (§9.2)… ‖ Messages from listeners are unsigned ‖ a LISTEN may carry a signed capability ‖ Messages from relays after validation are signed by the relay's…|U×4||No codec for kinds 0x10-0x19. No listener lease messages. optional; no capability code. No relay and no relay entry in the manifest.|
|1245 MUST|The datagram MUST be ≥ 256 bytes; relays ignore shorter HELLOs|U||HELLO 0x10: stubs only|
|1246 MUST|MUST be ≤ the HELLO's size (in practice ≤ 64 B)|U||COOKIE 0x11: stubs send 36 B (E4 comment says 40), without…|
|1247|no (capability inside is signed)|U||LISTEN 0x12: stub carries nonce, cookie and padding|
|1248|{1: lease_id (bstr .size 8), 2: lease_s, 3: renew_s, 4: granted_bps|U||LISTEN_OK 0x13: stub sends random 8 B and zeros, unsigned.|
|1249 MUST|{1: lease_id, 2: cookie, 3: relay_epoch, 4: renew_seq (uint), 5…|U||RENEW 0x14: stubs send nonce+cookie, padded to 96 B, no…|
|1250|0x15 / BYE / listener → relay / no|U||BYE 0x15: E4 stub only (nonce and cookie, not lease_id).|
|1251|Sent only in reply to a RENEW or REPAIR with a valid cookie; ≤ the…|U||LEASE_UNKNOWN 0x16: not even in the stubs; they stay silent.|
|1252 MUST|0x17 / REPAIR / listener → relay / no|U||REPAIR 0x17, its 96 B minimum and the 8-range / 64-tuple caps…|
|1253|requested tuples the relay does not hold. Sent only in reply to a…|U||REPAIR_GONE 0x18 and its rate limit: nothing.|
|1254|0x19 / RELAY_GOAWAY / relay → listener / yes (relay key)|U||RELAY_GOAWAY 0x19: nothing.|
|1255|Admitted frames (ITEM, PLUCK, BEACON, relay BEACON), byte-identical|U||No relay.|
|1258|filter = [ key_id: bstr .size 8 / null|U||Filter structure (key, stream, class mask): nothing.|
|1261|; at most 32 filters per LISTEN|U||No filters.|
|1263|repair-range = [ key_id: bstr .size 8, stream_id: uint, epoch…|U||Nothing.|
|1265|receiver-report = [ [ key_id: bstr .size 8, stream_id: uint|U||Nothing.|
|1269|; at most 16 entries|U||Nothing.|
|1272 MAY|A RENEW MAY carry a report with aggregate counts per stream ‖ A relay MAY use a report to adjust that lease's decimation ‖ A relay is free to ignore reports|U×3||optional; nothing. optional; no relay.|
|1274 MUST NOT|They carry no content judgment, no stance (§14.16), no session…|U||No reports exist, so nothing contrary; nothing enforces it.|
|1275 MUST NOT|They never affect trust, admission, accord or any authority|U||No reports exist.|
|1276|They fall under the lease-log rules of §11.3.7|U||No reports or lease logs exist.|
|**§11.3.3**|**Cookie** (11 U)||||
|1281|cookie = first 16 bytes of HMAC-SHA256(K_secret[relay_epoch]…|U||No relay.|
|1284 dflt, MUST|K_secret rotates every 120 s ‖ A relay accepts cookies made with the current and the previous…|U×2||Stub secret never rotates. Stub has one secret.|
|1285 MUST|The relay keeps no state before a valid LISTEN arrives|U||No relay. Stubs comply.|
|1286|When the secret rotates, a relay answers the next RENEW with a…|U||Nothing.|
|1287 MAY|A relay MAY persist its current and previous K_secret and its…|U||optional; nothing.|
|1288 MUST|The store MUST be readable only by the relay|U||No store.|
|1289 MUST NOT|A persisted secret MUST NOT validate cookies once it is more than…|U||No store.|
|1290 MUST NOT|A relay MUST NOT roll back to an older secret|U||No store or secret counter.|
|1292 MUST NOT|A relay MUST NOT persist its lease table for this purpose ‖ A durable listener inventory is not one of them|U×2||No relay; the stubs keep leases in memory only. No relay. No code keeps a durable list of listeners.|
|**§11.3.4**|**Exchange** (3 U)||||
|1298|HELLO(nonce, pad≥256 B)|U||Exchange steps HELLO to BYE: none in product code.|
|1303|fill of the live set, paced ≤ fill_bps (§7.10)|U||No relay fill.|
|1307|or silence → lease lapses after lease_s|U||No relay. Stubs lapse a lease with no RENEW (E3, E4, E5).|
|**§11.3.5**|**Timers ([PROPOSED DEFAULT])** (12 U)||||
|1314 dflt|HELLO retransmit / 1 s, 2 s, 4 s, 8 s; then the next SRV target|U||Only as the stub constant RETRY_S = (1,2,4,8)|
|1315 dflt|Cookie secret rotation / 120 s|U||Nothing rotates.|
|1316 dflt|lease_s / 75 s (maximum 120 s)|U||Stub constant 75 s only.|
|1317 dflt|22 s, jittered by U(0.8, 1.2): 17.6-26.4 s|U||Stub constant only (E4, E5).|
|1318 dflt|Lease lapse / no valid RENEW for lease_s|U||Stubs only.|
|1319 dflt|The listener declares the relay unobservable after 3 × and fails…|U||E5 stub only (5 s beacons, 3 missed)|
|1320 dflt|Station beacon decimation toward leases / ≥ 1 per 5 s per station|U||Nothing decimates.|
|1321 dflt|fill_bps ≤ 128 kbit/s; fill_passes = 2|U||Nothing; E4's snapshot is one pass at 32 kbit/s.|
|1322 dflt|REPAIR / at most one per lease per station beacon interval|U||Nothing.|
|1323 dflt|REPAIR_GONE / at most one per lease per 2 · RTT|U||Nothing.|
|1324 dflt|exponential from 1 s to 60 s, jittered by U(0.5, 1.5)|U||Nothing; the stubs have one relay.|
|1325 dflt|every listener of a crashed relay leased again within 3 ×…|U||Not shown. E5 measured an unsigned stub, not an implementation|
|**§11.3.6**|**Listen capability** (6 U)||||
|1329 MUST|required for any stream whose audience (manifest audiences) is not…|U||No capability and no audiences in the spike manifest…|
|1332|listen-capability = [|U||Capability structure: no encoder, issuer list (listen_issuers)…|
|1339|optional listener public key (then LISTEN must be signed by it)|U||optional; nothing.|
|1341 MUST|Ed25519 over "binary-canticle/listen-cap/v1"|U||No signer or verifier uses this domain.|
|1345 MUST, MUST NOT|MUST also be confidential on the relay link (DTLS 1.3 or QUIC) or… ‖ Threat and healing aspect streams are fleet, never public|U×2||No private audience, DTLS, QUIC or payload encryption exists. Nothing enforces it: scope comes from the sing request up to…|
|**§11.3.7**|**Caps and abuse controls ([PROPOSED DEFAULT])** (2 I · 7 U)||||
|1349 dflt|at most 64 leases and 256 kbit/s in total|U||Nothing.|
|1350 dflt|granted_bps default 32 kbit/s|U||Stub constant GRANTED_BPS paces the E4/E5 snapshot only|
|1351|A global egress cap, enforced by tc|U||Nothing.|
|1352|nftables per-source meters on the lease port|U||Nothing.|
|1353 SHOULD|accept data only from the relay endpoint they leased from|U||No lease. Receivers ignore the source address entirely|
|1354 MUST|counts against the same per-lease, per-prefix and global caps as…|U||No caps.|
|1355 SHOULD|Relays SHOULD keep lease logs, receiver reports included, minimal…|U||No relay.|
|1355 MUST NOT|MUST NOT disclose listener sets|I|runner:82-118|No relay holds a set.|
|1355 MAY|WHO may only mean "stations heard", computed from beacons|I|listener:725-752, tap:451-459; t/listener:37|No WHO verb.|
|**§11.3.8**|**Station ingress** (1 I · 4 U)||||
|1359|A station publishes to a relay by sending its frames unicast|I|runner:179-184, __main__:164; t/udp_e2e:24|Sender half: --to host:port unicasts every frame. No relay exists to receive it|
|1359, MUST NOT|or one advertised in the manifest ‖ The relay never replies to ingress traffic|U×2||Manifest has no relay or ingress entry. No relay. E4's stub never replies on ingress.|
|1360 MUST|The relay admits frames only through the membrane order of §12.2|U||No relay.|
|1361 MAY|restrict ingress to configured source prefixes per station key|U||optional; not built.|
|**§11.3.9**|**Failover** (12 U)||||
|1365 MUST|Listeners choose relays only from those listed in the manifest… ‖ ordered by SRV priority and weight (§13) ‖ a listener re-runs HELLO against the next relay|U×3||No relay entries, no selection. dns-browse prints SRV priority and weight, in answer order No failover. E5's stub re-HELLOs the one relay.|
|1369 SHOULD, MUST, dflt|SHOULD send a signed RELAY_GOAWAY to every lease before it stops ‖ A listener acts on one only if it verifies against that relay's… ‖ It tries the next relays first, but only those listed in the… ‖ it waits a random delay in [0, spread_ms] (default 1 000 ms)|U×4||No relay. Nothing.|
|1370, dflt|A listener follows the HELLO retransmit schedule of §11.3.5 against… ‖ it backs off exponentially from 1 s to 60 s|U×2||Nothing (stub schedule only). Nothing.|
|1371 dflt|after an unplanned relay restart, every listener holds a lease again ‖ A planned restart sends RELAY_GOAWAY, so no listener waits for…|U×2||Not shown: E5 is a stub measurement, and S4 has not run. Nothing.|
|1372 MUST NOT|A relay does not persist its lease table to meet the SLO|U||No relay.|
|**§11.4**|**ringserver replay tier** (2 U)||||
|1376|A relay-side bridge writes into EarthScope ringserver over DataLink ‖ Dashboards read SeedLink v3/v4, DataLink and WebSocket from…|U×2||No relay and no bridge. No dashboard here reads ringserver|
|**§11.5**|**WebTransport datagrams (later)** (1 I · 5 U)||||
|1380 MAY|A relay MAY terminate WebTransport sessions and send each admitted… ‖ The listen capability travels in the session setup|U×2||optional; nothing. Nothing.|
|1384|Datagrams carry repeats and beacons, with a maximum age equal to… ‖ The first copy of each alarm, control and PLUCK frame goes on its…|U×2||Nothing.|
|1385 MUST|A relay MUST refuse WebTransport's HTTP/2 capsule fallback for this…|U||Nothing to refuse it; no WebTransport.|
|1386 MUST NOT|no deployment may require it, until the real browser, CDN and proxy…|I|cs/pyproject.toml:10||
|**§11.6**|**NATS WebSocket/TCP listener binding (MAY)** (3 U)||||
|1390 MAY, MUST|A relay MAY additionally expose the same frames over a NATS… ‖ cnt.‹key_id hex›.‹stream_id› for items ‖ Receivers verify exactly as on UDP (§20.2)|U×3||optional; nothing. Subjects for items, plucks and beacons, and the unchanged-frame… No NATS receiver.|
|**§11.7**|**Relay to relay** (1 U)||||
|1394|With more than one relay, relays interconnect as described in…|U||No relay.|

### §12 Regulation and the membrane

149 claims: 30 I · 7 D · 109 U · 3 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§12.1**|**Availability is not strength (rate is not intensity)** (10 I · 10 U)||||
|1409|Shaped by / loop_ms, jitter, relay decimation by depth|I|station:234-251,441-445; t/station:37|Station sets each copy's time from loop_ms and jitter U(2/3, 4/3)|
|1409|relay decimation by depth, scope, loss ‖ distinct lineage roots, distinct principals, affinity, class, hop…|U×2||Relay decimation by depth: no relay, so nothing decimates. No strength quantity is computed by station, plugin or…|
|1410|yes: catch-up ≈ loop_ms · 4/3|I|station:441-445; t/station:414||
|1410|no: repeats are no-ops|I|listener:329-336, records:383-385; t/records:150|A byte-identical repeat yields no event and no record, only a counter|
|1411|anyone (transport telemetry)|I|station:464-477, records:547-553|Loop figures travel in signed beacons and in health; nothing hides them.|
|1411|only the receptor; local and private|U||No strength quantity exists to be private.|
|1415 MUST|MUST treat a frame whose identity tuple it has already accepted as…|I|listener:329-336, pl/binding:422-425; fe/listener:760-768; t/records:150|Salience, evidence, accord, thresholds don't exist. #173 #173/intake:549-553 drops exact repeats before verify and still counts them as duplicates|
|1416 MUST|Items from one principal with equal body digests MUST count as one…|U||No root counting anywhere|
|1417 MUST|A frame whose derived_from names a known root MUST contribute only…|U||derived_from is parsed and passed through as data|
|1418 MUST|A principal's contribution on one subject MUST saturate ‖ Evidence grows with distinct principals, not with frames.|U×2||No accord, no E_cap anywhere. No evidence mass is kept.|
|1419 MAY|A sender MAY declare a bounded intensity in [0, 255] (key 14).|I|station:268-271, wire:301; t/records:130||
|1419|It is signed and identical across loops.|I|station:309-313,434-439; t/station:37||
|1419 MAY|Receivers MAY scale that principal's contribution below the cap by…|U||Optional. No receiver reads intensity for anything|
|1419|It can never raise the cap or the count.|I|records:467|Vacuous: no cap or count exists and nothing reads intensity. No test.|
|1420 MAY|Observed cadence MAY drive flood detection, automatic gain control…|U||Optional. Receiver keeps no cadence or rate state on main. #173 #173/intake:71-84 rate buckets per key, stream and source use observed cadence for budgets|
|1420 MUST NOT|It MUST NOT enter salience, evidence mass, accord or any lens level.|I|listener:329-336; fe/hear:140|Vacuous: none of those quantities exist.|
|1421 MUST NOT|Implementations MUST NOT derive strength from availability.|I|listener:329-336|Nothing contrary exists: no strength is derived at all. No test.|
|1423|a faster loop request must change no receiver-side quantity.|U||No L-08 test exists in binary-canticle or frond-ear (grep for…|
|**§12.2**|**The membrane: relay admission** (28 U)||||
|1427 MUST|A relay MUST evaluate every inbound frame in this order, cheapest… ‖ and forward it only if every check passes|U×2||Receptor analogue, main: size, magic, version, kind… #173 #173/intake:537-566 adds: kid+header, exact-repeat digest, then per-source/stream/key queues, before the main order Nothing forwards; the receptor emits records instead.|
|1429|1. Size (≤ 1 100 B canonical, ≤ 1 200 B datagram), magic, version…|U||Relay unbuilt. Receptor does it first (wire:408-420)|
|1430|key_id present in the manifest and not revoked.|U||Relay unbuilt. Receptor: manifest.resolve before CBOR.|
|1431|Time window, by kind, read by a bounded CBOR parse. ‖ The fields are not at fixed offsets, and a map key means different…|U×2||Relay unbuilt. Relay unbuilt. #173 #173/intake:360-375|
|1432|issued_at (key 4) ≤ now − δ̂ + 5 s ‖ local expiry (§14.6.3, from expires_at, key 5) › now ‖ δ̂ is the relay's clock-offset estimate for the key from the…|U×3||Relay unbuilt. Receptor: exactly this, 5 s skew. Relay unbuilt. Receptor: clamped to class max, then checked. Relay unbuilt. Receptor: min of last 16 offsets, else 0.|
|1433|BEACON: no time window. ‖ Replayed or stale beacons are dropped at step 10, and floods at…|U×2||Relay unbuilt. Receptor: BEACON skipped by kind. Relay unbuilt. #173 adds a beacon bucket and replay digests|
|1434|Per-key and per-source packet rate.|U||Relay unbuilt; main's receptor has no rate either. #173 #173/intake:71-84 and pr173/README:509 (departure note)|
|1435|Deterministic-CBOR check and Ed25519 signature.|U||Relay unbuilt.|
|1436|Capability: class, op, scope and stream permitted for the key|U||Relay unbuilt. Receptor checks class and scope|
|1437, MUST, MUST|scope permitted on this relay's tier ‖ A relay MUST drop host frames ‖ fleet and public tiers MUST drop lan frames ‖ a public tier accepts only public frames and never wake-eligible…|U×4||Relay unbuilt. No relay exists in either repo.|
|1438|TTL not above the class maximum|U||Relay unbuilt.|
|1439|Per-station ingress budget (B_station, capped by the manifest).|U||Relay unbuilt.|
|1440|Deduplication (§7.4), supersession and pluck bookkeeping… ‖ A BEACON is admitted only if its (epoch, bseq) is above the last…|U×2||Relay unbuilt. Relay unbuilt. Receptor: exactly this rule.|
|1444 MUST, MUST NOT|MUST forward admitted frames byte-identically ‖ MUST NOT re-sign, rewrite or originate station content|U×2||No relay exists in either repo.|
|1445 MUST NOT|MUST NOT forward a tuple back toward the upstream it arrived from|U||No relay exists in either repo.|
|1446 MUST NOT|MUST NOT forward non-public frames on a public tier ‖ nor any wake-eligible class to public leases|U×2||No relay exists in either repo.|
|1447 MUST|MUST keep unverified input from displacing verified frames…|U||Relay unbuilt. #173 #173/intake:598-606, #173/intake:322-335|
|**§12.3**|**Budgets and the attenuation ladder** (4 I · 3 D · 19 U)||||
|1451|the station's own B_stream/B_station (§7.5)|I|station:218-230,240; t/station:51||
|1451|each relay's per-station ingress budget ‖ each relay's per-lease (granted_bps) and global egress caps|U×2||No relay exists in either repo.|
|1451 MUST|Under pressure, an implementation MUST apply, in order|**D** rfc|station:373-376,422-425|Station has no utilization measure and no ordered ladder: fair-share loop, then one 'degraded' flag that stops repeats after the burst (station:373-376, 422-425). No step 2-5. No departure note for the ladder.|
|1455 dflt|Stretch: multiply loop_ms by λ ≥ 1, proportionally, up to hi|**D** owner|station:234-251|No λ and no 70% trigger: the fair share stretches loops as the live set grows, not up to hi but past it (then flagged degraded). §7.5's rule may already cover A1's effect.|
|1456 dflt|Decimate repeats by depth (relays): forward a repeat of tuple τ…|U||Relay step.|
|1457 dflt|Stop looping the lowest classes, in the order chatter → ambient → finding-ref → advisory|**D** rfc|station:38,373-376|Code sheds any degraded item except control/alarm/PLUCK, so live-state, regulatory and root lose their repeats too (RFC: never). It decides once, at admission, not after 2 revolutions, and not by class order.|
|1457|their first copy still goes, then they are one-shot|I|station:377,423-425; t/station:184||
|1458 dflt|Refuse new low-class frames: the publish tool returns…|U||The station never refuses on utilization.|
|1459 dflt|Circuit breaker (§14.8.3)|U||Daemon always says breaker closed (records:194).|
|1461 MUST NOT|MUST NOT shed or decimate the first copy of any tuple|I|station:377; t/station:184|First copy is queued at admission, before any shed.|
|1461 MUST NOT|nor any control, pluck, supersede, UNEQUIP or alarm first copy|I|station:374-377; t/station:175|Same burst path; plucks, control and alarm are also exempt from shedding.|
|1461|Step A2 is the literal concentration gradient: far listeners hear…|U||Relay step; nothing decimates.|
|1463 MUST|A relay MUST schedule egress per lease|U||No relay, no lease.|
|1465|Frames go out in class priority order ‖ first copies, supersedes and PLUCKs go before repeats; fill and… ‖ Within one state_key, the newest issued_at goes first.|U×3||Relay egress. No relay exists in either repo.|
|1466|A queued frame that has been superseded or plucked leaves the queue.|U||Relay queue.|
|1467 dflt|Each lease's queue is capped ([PROPOSED DEFAULT] 64 frames ‖ When the queue is full, the oldest repeat is dropped first. ‖ the relay ends it, and the listener sees LEASE_UNKNOWN at its next… ‖ Its first copies are never shed silently.|U×4||No relay exists in either repo.|
|1468 dflt|A queued frame whose remaining life is below its class egress… ‖ So does one that has waited longer than max_queue_ms ([PROPOSED…|U×2||Relay queue. No relay exists in either repo.|
|1469|Backlogged leases share egress round-robin by bytes (deficit round…|U||Relay egress.|
|1470|Kernel send buffers stay small|U||No relay exists in either repo.|
|**§12.4**|**Relays as proxy-stations, and relay to relay** (1 I · 22 U)||||
|1478|it holds the verified live set of the stations it admits and runs… ‖ using the stations' advertised loop parameters and A2 decimation ‖ It never re-signs.|U×3||No relay exists in either repo.|
|1479 MUST NOT, MUST|Relay chains MUST NOT exceed depth 4. ‖ A relay MUST refuse a lease from a relay already on its upstream…|U×2||No relay exists in either repo. No relay; no RT-13 test in either repo.|
|1480 MAY|Redundant relays on one LAN segment MAY use Trickle suppression|U||Optional.|
|1481 SHOULD|fleets SHOULD provide k independent relay paths|U||No relay exists in either repo.|
|1485|stays raw UDP, and no station ever depends on a broker|I|runner:144-184; t/udp_e2e:24|Station sends signed UDP and needs no broker.|
|1486|relays forward to each other over simple custom TCP or QUIC links|U||No relay-to-relay link.|
|1487|is adopted only when multi-relay fleet operation actually justifies…|U||No NATS in either repo; S4a not run.|
|1489 MUST|Every relay-to-relay link MUST provide these outcomes|U||No link exists.|
|1491|At most one queued frame per (key_id, stream_id, state_key) for…|U||TCP_NOTSENT_LOWAT appears only in a measurement harness…|
|1492|A first copy of a PLUCK, control or alarm frame is never dropped…|U||No relay exists in either repo.|
|1493 dflt|stays unacknowledged for longer than D_fail ([PROPOSED DEFAULT] 30… ‖ On Linux TCP that is TCP_USER_TIMEOUT ≤ 30 s. QUIC implementations…|U×2||TCP_USER_TIMEOUT appears only as a harness arm… No relay exists in either repo.|
|1494|The receiving relay checks every frame's expires_at (after δ̂) and…|U||Relay unbuilt. Receptor does this on the UDP path (wire:448).|
|1498|Subjects cnt.‹key_id hex›.‹stream_id›, cnt.‹key_id hex›.pluck…|U||No NATS backbone.|
|1499|Loop at the edge relay, not across the backbone|U||No relay exists in either repo.|
|1500|Nats-Msg-Id = ‹key_id›:‹epoch›:‹stream_id›:‹seq› ‖ Nats-TTL = max(1 s, ⌈expires_at − now⌉) recomputed at every hop ‖ so broker TTL is garbage collection only; frames' own expires_at…|U×3||No relay exists in either repo. Rule for an unbuilt broker.|
|1501 MAY|MAY be used as defence in depth|U||Optional; no NATS.|
|1505|Adopt B or B+ if p95 time-to-hear is within 1.2 × of A|U||Spike S4a not run|
|**§12.5**|**Scale** (4 I · 4 U · 1 ?)||||
|1509|design for a fleet of thousands through a relay tree, validate at…|U||Design centre (D5, recommended). No relay tree|
|1510|Relay egress ≈ listeners × (Σ over tuned streams of loop bytes/s + beacon bytes/s)|**?**||A cost estimate, with no relay to measure. Who can say: a future S4 run; E2's fan-out harness is the nearest data.|
|1511|A single Go or Rust relay using sendmmsg/UDP GSO is expected to…|U||No relay.|
|1511|The Python spike is not a relay.|I|runner:9|Nothing in canticle-station leases, forwards or re-serves frames.|
|1511|Python for the frame codec, station and receptor spike|I|wire:1-8, listener:1-5||
|1511|TypeScript for the OpenClaw plugin (§16.2), the Claude Code MCP…|I|pl/binding:1-12; fe/src/shim:1-30|Plugin and frond-ear are TypeScript.|
|1511|second, independent codec that cross-checks the test vectors|I|fe/wire:1-30; fe/t/canticle:64|frond-ear's port runs the vendored 49 candidate vectors.|
|1511|Go or Rust for the relay once the semantics settle|U||No relay code.|
|1512|Beacon aggregation (§8.3) and decimation keep carrier cost…|U||Neither built.|
|**§12.6**|**Kernel shaping (relay hosts)** (5 U · 1 ?)||||
|1516 SHOULD|Every relay host SHOULD back the relay's own caps with kernel limits|U||No relay host.|
|1524|udp dport 47113 meter lease4 { ip saddr limit rate 20/second burst…|U||Illustrative; not installed or tested.|
|1533|tc qdisc replace dev eth0 root tbf rate 200mbit burst 256kb latency…|U||Illustrative|
|1536 SHOULD|Fleet edges SHOULD apply BCP 38 source filtering|**?**||Operator practice; nothing in either repo installs or checks it. Host owners could say. #173 says it can't rely on it (source addresses are only queue hints). #173 #173/intake:30-36 treats a source address as untrusted|
|1537|eBPF/XDP per-source token buckets are a later optimisation|U||Later and optional; none exists.|
|1538 MAY|LAN-only control messages MAY use a GTSM-style check|U||Optional.|
|**§12.7**|**Where HAProxy fits** (3 U)||||
|1543|HAProxy belongs on the TCP tier: ‖ the HTTPS control API (manifest distribution, listen-capability…|U×2||No HAProxy config or TCP tier in the repos No HTTPS API. Manifest is a local file|
|1558 MAY|the relay's own policy module, which MAY read key/value policy from…|U||No relay; optional.|
|**§12.8**|**The canticle-regulation/1 profile** (11 I · 4 D · 18 U · 1 ?)||||
|1562|All [PROPOSED DEFAULT] numbers in this RFC form one named profile.|**?**||RFC text marks defaults in about 37 places; the table lists 23 rows and omits many (§7.1 depth 256, §11.3.5 timers, §14.18.2 limits, §12.3's 64 frames). Owner should say whether the table or the whole set is the profile.|
|1562|Stations identify it in every beacon (profile, §9.8).|I|station:37,545-546; t/station:245|Every beacon carries canticle-regulation/1.|
|1566 dflt|Loop / B_stream / B_station / 4 000 / 16 000 bit/s|I|station:32-33; t/station:51|Both values. Test asserts 4 000 only; B_station 16 000 has no test.|
|1567 dflt|class_min_ms / class_max_ms / §6.2 / 300 000 ms|I|ids:101-114, station:30; t/station:51||
|1568 dflt|k_avail; jitter; burst / 3; U(2/3, 4/3); +1, +2, +4 s|I|station:28-29,443; t/station:37||
|1569 dflt|class TTLs, stream max_ttl, station cap / §6.2; 300 s; 24 h|I|ids:101-114, station:34-35; t/station:78|All three. The 24 h cap has no test of its own|
|1570 dflt|future skew; dedup retention / 5 s; local expiry + 5 s, evicting|I|wire:30, listener:34; t/listener:160|5 s skew; retention local expiry + 5 s|
|1571 dflt|stale_after / live-state 60 s, alarm 120 s, advisory 300 s|I|fe/hear:17-21|Only frond-ear uses it (display marker aged), and by age now, not age at first…|
|1572 dflt|Carrier / beacon period; relay minimum; UNOBSERVABLE after / 1 000…|I|station:149, listener:731-733; fe/listener:1282-1283; t/listener:50||
|1572 dflt|relay minimum; UNOBSERVABLE after / 1 000 ms; 1 per 5 s|U||Relay minimum of one beacon per 5 s: no relay.|
|1573 dflt|Receptor / squelch θ0; hysteresis / 0.5; close at 0.8θ|U||No threshold or salience in any code.|
|1574 dflt|Receptor / desensitization|U||No desensitization or refractory code.|
|1575 dflt|Receptor / dose / ≤ 2 slots; ≤ 5 items and ≤ 1.5 KB per turn|**D** owner|pl/candidates:222-229, pl/ambient-slots:9; fe/src/config:457-459|Plugin spike holds it: 2 slots, 5 items, 1 536 bytes per slot (its README says no seat runs it). frond-ear, which runs, has no slots: 5 items default, up to 10, 6 000 chars a push. Admitted: fe/docs/runbook:850.|
|1576 dflt|Receptor / AGC / ≤ 25% of the digest per station per 10 min|U||No AGC. frond-ear says it is not applied.|
|1577 dflt|Receptor / homeostasis / R = 12 surfaced items/h/session; θ ∈ [0.5…|U||No θ, no rate tracking.|
|1578 dflt|Immune / tighten Δθ; cap / +0.5; θ ≤ 2.0|U||No regulatory op is applied|
|1579 dflt|all-clear ramp; lapse ramp / halve every 3 min; halve every 5 min|U||No RESOLVING or LAPSED state anywhere.|
|1580 dflt|quarantine / q = max(2, ⌊N/3⌋+1), E ≥ 2.0|U||No quorum, no E.|
|1580 dflt|TTL 1 h; ≤ 24 h without a human|**D** rfc|records:428-434,589-596|The only quarantine built (equivocation, records:428) has no TTL and no rescind: it lasts until the daemon's state file is deleted. RFC §14.7.3 says an equivocation proof stays TTL-bounded. Admitted: README:502.|
|1580 dflt|≤ 10% of principals at once|U||No Treg cap.|
|1581 dflt|Immune / antibody memory / max age 7 d|U||No antibody memory.|
|1582 dflt|Wake / session bucket; host budget / capacity 2, refill 1 / 10 min; 6 / h|**D** owner|pl/config:131; fe/src/config:467-475|frond-ear wakes sessions with its own cap: per-ear pushes/h, default 60 (max 360), no session bucket, no host budget, any class from wakeKeys. canticle-station and plugin never wake. Admitted: fe/docs/runbook:851.|
|1583 dflt|Wake / canticle token budget / 200 000 tokens / session / day|U||No canticle token budget in any code.|
|1584 dflt|Storms / circuit breaker / open at 3 × R for 2 × 10 min|U||Nothing opens a breaker. landing_state.breaker is always closed|
|1585 dflt|fleet alarm cap / 10 new alarm tuples / min (relays); 3 alarms / 15…|U||No cap in relay, station or receptor.|
|1586 dflt|Keepers / damping|U||No keeper or damping code (aspect streams are not built).|
|1587 dflt|Relay / lease caps / 64 leases and 256 kbit/s per /24 or /56; 32…|U||No relay.|
|1588 dflt|Relay / lease timers / §11.3.5|U||No relay.|
|1590 MAY|A receiver MAY be stricter than the profile.|I|pl/config:131; fe/src/config:441-442|Receivers do: frond-ear's freshness bound is 30 s by default against the profile's…|
|1590 MUST NOT|It MUST NOT be looser on §12.1 (rate is not intensity)|I|listener:329-336; t/records:150||
|1590 MUST NOT|§12.2 (the membrane)|**D** neither|daemon:489-493, listener:221-234|Main has no step 4 rate (per key or per source) and no step 9 budget, and clamps TTL where step 8 refuses. The flood test fails. The RFC's step 4 is also contested: a rate charged on a claimed key lets a forger spend it (reports:613-618). Admitted: reports/measurement/2026-11-23-step-one/README:8…. #173 #173/intake:71-84 adds rates (after verify, in §14.1's other order; noted in its README:509)|
|1590 MUST NOT|local expiry (§14.6.3)|I|wire:368-388, listener:368; t/listener:69||
|1590 MUST NOT|the authority rules of the immune grammar (§14.7) ‖ or accord (§10.7)|U×2||No immune grammar is applied, so its authority rules are… No accord.|

### §13 Discovery

52 claims: 25 I · 1 D · 25 U · 1 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§13.1**|**Three questions, three mechanisms** (5 I · 1 U)||||
|1598|mDNS on the LAN|U||No mDNS code; .local is refused (dns_browse:68).|
|1598|a unicast zone on the WAN|I|dns_browse:63-71, pl/discover:65-70; t/dns_browse:36|Read-only browse of one explicit unicast zone. #125 b9391826 canticle/dns_registration.py (planner and memory backend only)|
|1598|A locator only.|I|dns_browse:93-155, pl/discover:120-125; pl/t/discover:24|Browse never opens, joins or connects to anything it learns|
|1599|The carrier-beacon (§8), never DNS.|I|listener:254-288,725-743; t/listener:37|Presence comes only from beacons and their arrival|
|1599|Discovery stays out of liveness|I|dns_browse:148-155|Browse results carry no presence; nothing in the listener path reads DNS.|
|1600|The fleet manifest (§10.3), never DNS.|I|dns_browse:101-107, pl/discover:80; t/dns_browse:52|Only manifest entries become rows; TXT adds no stream or key.|
|**§13.2**|**Records** (5 I · 14 U)||||
|1606|PTR _canticle._udp.‹zone› → ‹instance›._canticle._udp.‹zone›.|I|dns_browse:91-100, pl/discover:68-81; t/dns_browse:98|Browse queries exactly that and refuses out-of-zone instances. #125 plans the PTR record|
|1607|SRV and TXT live on the instance name (RFC 6763)|I|dns_browse:108-109, pl/discover:83; pl/t/discover:24|Both readers query SRV and TXT on the instance, never an ad-hoc name.|
|1608|the relay lease endpoint (mode=lease) ‖ the host whose LAN surface is described by grp|U×2||SRV target is read and returned as a locator No mDNS view; grp is read by nothing.|
|1609|_‹lens›._sub._canticle._udp.‹zone› for public lenses only|U||No subtype browse or publication.|
|1610|_seedlink._tcp.‹zone› and _datalink._tcp.‹zone› SRV records, with…|U||No code reads or publishes them|
|1612, SHOULD|each key ≤ 9 characters, RFC 6763 §6.4 ‖ whole record RECOMMENDED ≤ 200 bytes|U×2||No publisher on main. No publisher. Readers accept up to 4 096 bytes per record. #125 refuses a TXT over 200 bytes when publishing|
|1616|txtvers / 1 /|U||Neither reader checks txtvers, so any value is accepted #125 publishes txtvers=1|
|1617|sid / key-id, 16 hex characters / Cross-check against the manifest|I|dns_browse:133-134, pl/discover:108; t/dns_browse:52|Compared with SHA-256(key)[0:8] hex|
|1618|ed25519:‹base64 of the 32-byte public key›|I|dns_browse:135-138, pl/discover:109; t/dns_browse:52|Compared exactly with the manifest (or plugin catalog) key|
|1619|comma-separated public stream names|I|dns_browse:139-140, pl/discover:110; t/dns_browse:71|Reader side: compared with the manifest's public list as a set (Python), but as an…|
|1619|Omitted for non-public stations|U||No publisher on main. #125 refuses to publish a station without public streams|
|1620|carrier / beacon period in ms /|U||Read by nothing; not published on main or by #125.|
|1621|lease \/ mcast \/ bcast|U||Read by nothing: no binding is chosen from it. #125 always writes mode=lease|
|1622|grp / multicast group / LAN (mDNS) views only|U||Read by nothing.|
|1623|mtu / 1100 / Canonical frame ceiling|U||Read by nothing (the ceiling is a wire constant, wire:26).|
|1624|regulation profile id, e.g. cr/1|U||Read by nothing; the beacon's profile is a separate string.|
|1625|HTTPS URL of the fleet manifest|U||Optional; read by nothing. Manifests are local files.|
|**§13.3**|**Example zone** (1 I · 1 U)||||
|1655|The k= value above is the base64 of the RFC 8032 TEST 1 public key…|I|doctor:56; t/wire:84||
|1655|the same instance records appear under local. via mDNS, with…|U||No mDNS.|
|**§13.4**|**Authenticity of discovery** (4 I · 6 U)||||
|1659 SHOULD|WAN zones SHOULD be DNSSEC-signed ‖ and daemons and relays SHOULD validate ‖ Zones SHOULD use NSEC3 or online minimally-covering NSEC (RFC 4470)|U×3||No zone is published. Operator work. dnspython/Node stub resolvers No zone exists. Operator work.|
|1660 SHOULD|Registration SHOULD use Service Registration Protocol (SRP, RFC 9665 ‖ performed by relays or the host daemon, not by chatty sessions|U×2||No registration on main. #125 plans leases of 3600-7200 s behind a provider interface; its only backend is a memory fake, no SRP, no SIG(0) Nothing registers. #125 b9391826 canticle/dns_registration.py Registration takes a Station|
|1661|Keys learned from mDNS are hints|U||No mDNS, so nothing is learned.|
|1661 MUST NOT|trust-on-first-use MUST NOT be used for landing trust|I|manifest:98-104, dns_browse:101-107; t/dns_browse:52|No TOFU path: a key resolves only from the manifest; DNS never adds one.|
|1662 MUST|that disagrees with the manifest MUST raise an alert|I|dns_browse:130-153, pl/discover:106-125; t/dns_browse:52|Reported as an entry in mismatches of the browse JSON or tool result.|
|1662 MUST NOT|MUST NOT change any trust decision.|I|dns_browse:130-153; t/dns_browse:52||
|1663|Unicast zones use a real domain or home.arpa. (RFC 8375).|I|dns_browse:65-69, pl/config:136-137|Browse and plugin refuse .local and take one explicit domain.|
|**§13.5**|**TTLs and rotation** (1 I · 1 D · 1 U)||||
|1667 dflt|PTR 300 s; SRV and TXT 60-300 s (120 s RECOMMENDED)|U||No publisher on main. #125 plans PTR 300, SRV 120, TXT 120|
|1667 dflt|negative caching (SOA minimum) about 60 s|I|dns_browse:20,46-50; t/dns_browse:82||
|1667|publish the old and new k= side by side for at least one TTL|**D** neither|dns_browse:102-104,124-127|Two k= in one answer are treated as duplicates: the key is discarded and txt-invalid raised. While a name has two active manifest keys (the §10.3 rotation) browse hides the station. Publisher #125 refuses it too. #125 refuses a station name with more than one active key|
|**§13.6**|**Static fallback** (4 I · 1 U)||||
|1671|The static configuration file (~/.binary-canticle/stations.toml)|I|stations:22,46-47; t/stations:61|DEFAULT_PATH is exactly this path, with no override but --stations; test asserts it.|
|1671 MUST|remains REQUIRED as a fallback|I|__main__:358-366, stations:50-64; t/stations:153|listen, daemon, doctor need it unless --manifest is given|
|1671|It holds locators and MAY pin manifest root keys.|I|stations:25,67-94; t/stations:106|Locators only: version, manifest path, bind, multicast; anything else is an error.|
|1671 MAY|MAY pin manifest root keys.|U||A [trust] table is refused by name (the spike manifest is…|
|1671|Bootstrap discovery stays OPTIONAL for receiving|I|daemon:396-412, __main__:708-722|Nothing in the receive path uses DNS; browse is a separate one-shot command.|
|**§13.7**|**Changes from v0.1 §5** (5 I · 1 U · 1 ?)||||
|1675|_canticle-listen._udp is removed.|I|dns_browse:91|No listener publishes or queries it; browse uses only _canticle._udp.|
|1676|The undefined "metadata query surface" on the data port is removed.|I|runner:144-184,112-117; t/station:505|The station's UDP socket only sends.|
|1676|Catalogs come from beacons, the manifest and TXT.|I|listener:270-288, manifest:55; t/listener:329|Beacon pages, manifest stream names; TXT only as a cross-checked hint.|
|1677|TXT moves to the instance name|I|dns_browse:109, pl/discover:83; pl/t/discover:24||
|1677|subtypes and key hints are added|U||Key hints are read (rows 1617-1618)|
|1678 SHOULD NOT|An unknown station in a beacon still SHOULD NOT force an SRV refresh|I|wire:421-424, records:328-332; t/records:508|A beacon from an unlisted key is rejected as unknown-key with a counter|
|1679 SHOULD|SHOULD be checked against the IANA registry (RFC 6335)|**?**||Nothing in the repos records a check (D22 is open). Owner of the registry work could say.|

### §14 Receptor and landing

751 claims: 424 I · 158 D · 147 U · 5 O · 17 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|1685|The receptor is the deterministic judgment core between the wire…|I|records:168-211, listener:221-234; t/records:130|Receptor drives Listener and emits record v1; sessions are the binding's.|
|1685|One receptor daemon runs per host and serves every session on it…|I|daemon:386-394,414-427; t/daemon:222|State lease plus a UDP bind without SO_REUSEADDR|
|1687 MAY|a harness binding MAY instead run a receptor as its own supervised child|**D** rfc|daemon:467-516; fe/source:114-139|Nobody runs a supervised child (README: stdout transport is not a command). frond-ear embeds a second, in-process listener instead: no record v1, no supervision, no local quarantine on equivocation (fe listener:750 is evidence only). It is frond-ear's default source. Admitted: README:518 (child transport only; frond-ear's….|
|1687 MAY|It MAY do so only where that receptor is the host's one listener…|I|fe/source:49-84; fe/t/canticle-records:266|frond-ear's embedded source probes the host socket first and refuses if a daemon…|
|1687|they share one receptor, the host daemon, which carries the records…|I|daemon:231-246, pl/binding:207-215; fe/record-client:69-110; t/daemon:262|Daemon fans the same bytes to every peer|
|1687|the host daemon is a standalone canticle process, never one…|I|__main__:491-510, daemon:467-516|canticle daemon is its own CLI process with no harness code. No test.|
|1687|every harness binding on the host is a peer client of it (§11.1…|I|pl/daemon:1-40; fe/source:122-128; t/daemon:284|The plugin always is (never binds UDP).|
|1687|An embedded receptor runs only while no other binding on the host receives canticle|**D** rfc|daemon:414-427; fe/source:72-88|frond-ear probes the host socket once at start. Once bound it never looks again, so a daemon started later fails to bind (bind_failed) while the embedded one keeps the port.|
|1687 MUST|a binding configured to embed one MUST refuse to bind the port, and…|I|fe/source:26-47; fe/t/canticle-records:266|frond-ear: refuses and status says refused with the reason. Checked once|
|1687|No receptor opens a relay lease per session.|I|daemon:386-394|Nothing contrary exists: no relay lease code at all (the only lease is the state-dir…|
|1689|The receptor emits facts; session policy — subscriptions, target…|I|records:174-175, pl/config:34-46; fe/src/config:97-144|Receptor refuses a listener with a tune set; records carry no session field.|
|1689|The receptor implements §14.1-§14.5, the receptor-side parts of §14.6-§14.8 and §14.11, and §14.18.2-§14.18.3.|**D** rfc|listener:290-469, records:311-387|Built: 14.1 steps 1-4, 14.6.3, 14.18.2-3. Not built: hearer ring, receipt log, judgment object, salience, regulation, immune grammar, alarms, breaker. Admitted: README:499-503,507-512.|
|1689|The binding implements the per-session parts of §14.6, the per-session wake bucket and canticle token budget of…|**D** owner|pl/candidates:138-177; fe/delivery:1374-1390|Built: tune, dose, per-subscription or per-ear push budgets. Not built in either binding: weights, theta, AGC, homeostasis, wake bucket (cap 2, 1 per 10 min), token budget. frond-ear wakes under its own hourly push cap. Admitted: pl/README:483 (dose only).|
|1689|The host wake budget keeps exactly one accountable owner across all…|U||No host wake budget exists anywhere.|
|1689|P1 has no wake, so this gates P3, not P1.|**D** owner|pl/config:98-100; fe/delivery:2697-2702|The plugin has no wake, but frond-ear's immediate and digest pushes are channel notifications (banner says mode=silent-wake) on the scribe seats: a wake path in use before P3.|
|**§14.1**|**Pipeline** (10 I · 5 D · 5 U · 1 O)||||
|1693 MUST|A receptor MUST process each datagram in this order:|**D** code|wire:407-457, listener:290-469; fe/wire:530-559|Real order: size/magic/version/kind, key known+not revoked, det. CBOR, fields/crit, time window, Ed25519, class, binding scope, grant scope, hop, epoch, dedup/equivocation, quota, pluck, unknown class, supersession, warm-up, key quarantine, save, emit. Time after CBOR; no rates, no ring. #173 #173/intake.py reorders more: queue by claimed key/stream/source, drop exact repeats before verify, debit rates after verify|
|1695 MUST|Cheap checks: size, magic, version, kind|I|wire:407-420; fe/wire:441-445; t/wire:152||
|1695 MUST|key_id known and not revoked|I|wire:421-424, manifest:98-104; t/records:508||
|1695 MUST|time window by kind (§12.2 step 3: none for BEACON)|**D** code|wire:445-449,425-436; fe/wire:545-550|Same window, none for BEACON; but it runs after the deterministic-CBOR check of step 2, because the times are inside the map. Only the counted reason can differ. The RFC's order is not implementable without a second, looser parse.|
|1695 MUST|per-key and per-source rate.|U||No packet rate, per key or per source, on main: the daemon… #173 #173/intake:71-79 adds per-key, per-stream and per-source buckets, but debits keys after verify, not as a cheap check|
|1696 MUST|Crypto: deterministic-CBOR check, then Ed25519 (§9.3, §9.4).|I|wire:425-436,450-457; fe/wire:551-558; t/wire:152|#173 drops an exact SHA-256 copy of a verified, saved frame before either check|
|1697 MUST|Manifest checks: capability, scope, stream patterns (§10.4).|I|listener:294-312; t/listener:142||
|1697 MUST|scope, stream patterns (§10.4).|U||The receptor checks no stream grant: the manifest's streams…|
|1698 MUST|Identity: deduplication, equivocation, supersession, sticky-pluck…|I|listener:315-463; t/records:202|All four, after an epoch check, with a per-key quota and mark limit between dedup and… #173 moves exact-repeat dedup ahead of step 1's rate and step 2 (#173/intake:537-567)|
|1699 MUST|Hearer ring: append every verified frame, raw, before any…|U||No ring. Raw bytes are hashed and dropped|
|1700 MUST|Classify: class, content type, lens, which sessions tuned the…|I|listener:396-398, records:485-493; t/records:163|Class (unknown class is ringbuffer_only); content type picks text or base64|
|1700|under a harness binding, which sessions tuned the stream is the…|I|records:174-175, pl/binding:602-606; fe/records:1389-1434; pl/t/subscriptions:59|Receptor runs with tuned=None only; bindings filter.|
|1701 MUST|Threshold: salience and squelch, immune state, accord (§14.6-§14.8).|U||No salience, squelch or accord.|
|1702 MUST|Judge: produce the judgment object and write the receipt record (§14.3, §14.5).|**D** owner|records:440-497,215-233|No judgment object and no receipt record is written. The step's output is the record v1 frame line (admission, disposition, reasons), after a durable save of guards. Admitted: README:507-512.|
|1703 MUST|Expose: rebuild digests, land, decide wake (§14.9-§14.14).|**D** owner|pl/binding:452-478; fe/delivery:996-1165|Binding's work. Plugin rebuilds two slots over OC-0 (its README says no seat runs it), never wakes. frond-ear builds reports and pushes that wake, outside 14.10; it has no silent landing but hear. Admitted: README:67.|
|1705|Frames that fail steps 1-3 go to a separate, small, bounded debug ring.|**O**|records:328-332|Successor: Amendment BC-1 (D34) on the same line. Steps 1-2 are counted only; step 3 becomes a body-less frame record. The old sentence should go.|
|1705 MUST NOT|They MUST NOT displace verified frames|**D** rfc|daemon:489-493|No store is displaced, but at the socket junk is: one loop serves in arrival order, a verify each, default rcvbuf. Measured: forged flood F2b, 5 of 30 quiet items heard (reports/measurement/2026-11-23-step-one/README:200). #173 #173/intake:537-650 (reader thread, per-key/stream/source queues) makes it hold short of a same-address spoof|
|1705 MUST NOT|and MUST NOT land (review/challenge-redteam C19)|I|records:319-320,485; fe/records:1196-1204; t/records:508|Steps 1-2: counters only. Step 3: no body, disposition not surface.|
|1705|frames that fail steps 1-2 are counted (§10.9)|I|records:328-332,120-148; t/records:508||
|1705 MAY|and MAY enter the debug ring.|U||Optional. No debug ring exists.|
|1705|Frames that fail step 3 keep their §10.9 result and, under a…|I|records:337-356,453-458; t/records:178||
|**§14.2**|**Determinism** (2 I · 1 U)||||
|1711 MUST|Given the same (frame, receptor state, memory flags, now, δ̂), a…|I|listener:221-234, records:308-326|hear/tick take now; outcomes come from state only (no RNG; run id and rec_seq aside). #173: which datagrams are judged at all then depends on arrival time, source address and a random salt (#173/intake:246)|
|1711 MUST|(disposition, state delta, receipt record, evidence)|U||Only disposition and reason codes exist as outputs.|
|1711|now and the clock-offset estimate δ̂ are added to the original tuple|I|listener:104-106, records:447-451; t/records:130||
|**§14.3**|**The judgment object** (6 I · 3 D · 5 U · 2 O)||||
|1715 MUST NOT|A judgment object MUST NEVER float free of a source frame|I|records:452-459,416-426; t/records:130|Every frame and retract record carries the identity tuple and idem.|
|1719|disposition / enum: surface, ringbuffer_only, drop, quarantine_set|I|records:51,61-64; t/records:150|These four are emitted, always present on a frame record.|
|1719|quarantine_strengthen, quarantine_rescind / yes|U||Reserved in 14.18.3; never emitted.|
|1720|source / {tuple, frame_digest, observed_at, binding, relay_key_id?} / yes|**D** code|records:452-476,243-246|Record v1 carries the facts in another shape: frame{tuple, sha256, bytes}, times.received_at, and transport once per run in hello. No relay_key_id; digest null on refusals.|
|1721|stateDelta / array / yes / unchanged|U||No state delta is built or emitted|
|1722|landing / {sessions: [sessionRef], mode, slot} or null / yes|**O**|records:452-484|Successor: 14.18.4 ("the 14.3 landing field is null, and landing is the binding's"). Record v1 has no landing field at all.|
|1723|ringbufferWrite / object / yes / unchanged|U||No ring, so no write object|
|1724|evidence / array of {rule, inputs, decision} / yes for every non-trivial disposition|**D** code|listener:211-214, records:354|Only a list of reason codes is emitted. The listener computes a human detail (expected vs found) and the receptor throws it away; no rule id or inputs.|
|1725|expiry / timestamp / no / unchanged|I|records:450,474-476; t/records:130||
|1726|receiptPlan / — / — / Removed. There are no acknowledgement…|I|daemon:175-202; fe/custody:1-20; t/records:130|Nothing is sent back; the daemon only reads a join_snapshot line.|
|1728|The per-frame receipt record (proto/receptor-contract-v0.2.md §7.2, :224-246) keeps: identity tuple, key-id…|**D** owner|records:452-484|No receipt record is kept. The emitted frame record has tuple, key id, class, admission, disposition, reasons, state and rule version, received_at, local expiry; principal is always null. Admitted: README:505-506.|
|1728|sigState (valid / invalid / absent)|**O**|records:328-332|Successor: D34 and 14.18.3. Unverified frames get no record or receipt, so every record is sig-valid and no sigState field exists.|
|1728|accordWeight (always recomputed, answering open question 1)…|U||No accord and no memory.|
|1730|Normalized input (Table A, :117-137) maps to v2 as follows|I|records:452-495; t/records:130||
|1730 MUST|observedAt → local receipt time, which MUST stay distinct from…|I|records:474-476; fe/hear:133-139; t/records:130||
|1730|chemokineClass → regulatory op (§14.7)|U||No regulatory body is ever parsed|
|**§14.4**|**The hearer ring** (1 I · 6 U)||||
|1734, dflt|One ring per (key_id, stream_id), bounded by local expiry ‖ by depth (default 256 frames, proto/protocol-spec-v0.1.md:320-322)…|U×2||None. No ring depth.|
|1735|append(frame) is idempotent on the identity tuple and returns an…|U||No append.|
|1736|replay(stream, since_seq / since_ts, limit) and tail(stream, limit)…|U||No ring API.|
|1736 MUST NOT|They never become wire requests.|I|daemon:253-271, runner:206-242|Nothing contrary: a listener sends nothing, and the daemon socket serves only…|
|1737|Eviction is explicit and inspectable: truncated…|U||No ring.|
|1738 MUST NOT|Raw and interpreted MUST NOT collapse|U||No raw copy is kept anywhere, so only the interpreted record…|
|**§14.5**|**Receipt log and ledger** (1 I · 2 D · 2 U)||||
|1742, MUST NOT|The receipt log (append-only segment files plus a small SQLite… ‖ It MUST NOT be queried as current state (#51 invariant 2).|U×2||No receipt log in the receptor. No log to query.|
|1743|After an item's local expiry the log keeps its evidence metadata (tuple, digest, verdict, reasons) and drops the body…|**D** rfc|pl/journal:264-298, pl/config:168-172; fe/delivery:148-185|The plugin journal, the only log with payloads, keeps the full body up to 24 h (max 30 days) past local expiry; pruning is by age/count/bytes, never by item expiry. frond-ear custody complies: digest, never text.|
|1744|Antibody memory and quarantine flags live in a separate store with their own expiry (§14.7.3-§14.7.4).|**D** rfc|records:584-596|Quarantined keys are a bare list inside listener.json, with no expiry, saved with the guards. No antibody memory. Admitted: README:502-503.|
|1745 MUST NOT|The ledger is never written by receipt; only by promotion (spine…|I|records:578-587; t/records:433|Nothing contrary: no ledger code; hearing writes only listener.json.|
|**§14.6.1**|**Receptor density (tuning)** (6 I · 4 D · 1 U · 1 ?)||||
|1751|Each session has a tune table: the streams (and optionally classes)…|I|pl/config:208-225, pl/candidates:63-68; fe/src/config:297-317; pl/t/subscriptions:14|frond-ear: per-ear station:stream patterns ( station only, no class).|
|1751 dflt|with a weight w_s (default 1.0)|U||No weight in either binding's config.|
|1751|and a landing posture (silent, wake-on-alarm, off)|**D** owner|pl/config:129-130; fe/src/config:146-179|Plugin: ringbuffer_only or ambient per subscription, wake refused (complies for P1). frond-ear: off/digest/immediate per ear and station, plus mute; both push modes wake, for any class of an allowlisted key, not alarm only.|
|1752 MUST NOT|A frame on a stream the session has not tuned MUST NOT surface to…|I|pl/binding:602-606,856-863; fe/records:1422-1434; pl/t/subscriptions:59||
|1752|It stays ringbuffer_only for that session.|**D** code|pl/receive:524-527, pl/binding:203; fe/records:914-934|Plugin: by default listen.tune is : so everything is journaled; narrowed, a frame outside it is counted untuned and not kept. frond-ear: kept in the live set, but the untuned share gives way first when it is full.|
|1753|tune() is a receiver-side filter, never a wire subscription|I|daemon:253-263, pl/config:240-246; fe/record-client:48-56|Nothing about a tune leaves the host; the daemon never learns it. No test.|
|1753|Self-broadcast is filtered by default, with an explicit include_self override|**D** rfc|pl/binding:843-849, pl/candidates:143; fe/delivery:1168-1180|Plugin complies (includeSelf default false; ambient needs the station named). frond-ear has no self filter: an ear that tunes its own station hears it, and is woken by it if its key is in wakeKeys (the runbook tells operators to leave it out). Admitted: fe/docs/runbook:707 (operator advice).|
|1754|Tuning is standing consent to silent landing from verified sources.|**D** code|pl/candidates:79-87; fe/src/config:188-201|Tuning alone lands nothing: it opens hear/canticle_listen only. Landing is a second opt-in (frond-ear canticle.delivery + wakeKeys; plugin ambient subscription). frond-ear has no silent landing, only a waking push. Admitted: pl/README:5-6,22; none in RFC.|
|1755|the binding's (host or plugin) configuration owns subscriptions and…|I|pl/config:106-133; fe/src/config:297-317; pl/t/candidates:129|frond-ear JSON config; plugin plugins.entries config with exact targets.|
|1755|The receptor holds no session policy, and its judgments for the…|I|records:174-175, daemon:231-246; t/daemon:262||
|1755|Whether a session may also tune itself through canticle_tune (§15.1) is open|**?**|fe/delivery:792-814; fe/t/canticle-delivery:1447|Still open (q24; the princes). Today: no canticle_tune anywhere; a frond-ear session may only narrow delivery (set_canticle_delivery, config is the ceiling), not tune.|
|1755|A receptor embedded in a harness (§14) owns no host wake budget…|I|fe/receptor:1-9|Nothing contrary: frond-ear's embedded receptor has no budget|
|**§14.6.2**|**Salience and squelch** (4 I · 1 D · 7 U)||||
|1762 dflt|a_i = aff(p) · w_c · α_c^(hop_i) · f_c(age_i) · g(x_i)|U||No salience is computed in any implementation (grep and…|
|1763 dflt|surface iff sal_i ≥ θ_session (θ0 = 0.5)|U||No theta. Every verified, named, unquarantined item is surface.|
|1765 dflt|1.0 if the key holds class c's capability, else 0; a session MAY…|U||No affinity value.|
|1766 dflt|w_c class weight: control 1, alarm 1, regulatory 1, live-state 1…|U||No class weights (line 1767 too).|
|1768 dflt|α_c sing-hop attenuation: 0.5 for chatter, ambient, advisory…|U||No attenuation.|
|1770|f_c 1 until local expiry, then 0 (a step, for surfacing, in every…|I|listener:648-654, records:512-515; t/records:252||
|1770 MAY|(a step, for surfacing, in every class). Remaining-life fraction|I|pl/candidates:224; fe/hear:325-326|Optional, taken: the plugin ranks slot rows by earliest expiry (absolute, not a…|
|1771 MUST NOT|MAY rank entries inside the digest but MUST NOT decide surfacing|I|records:389-397, pl/candidates:165-168|Surfacing ignores remaining life.|
|1772 dflt|g(x) absent → 1.0; present → 0.5 + x/255 (x = intensity, 0..255)|U||Intensity is carried in the record, used by nothing.|
|1775|the same chatter at hop 1 (0.25) is squelched unless the session raises that stream's weight|**D** owner|listener:309-312, records:389-397; fe/delivery:1174|Nothing is squelched: hop-1 and hop-2 chatter surfaces like hop 0. frond-ear pushes hop 0 only but hear shows all hops.|
|1775 SHOULD|Aggregate surfacing SHOULD use hysteresis: open at θ, close at 0.8θ.|U||No theta, no hysteresis.|
|1775|sigState ≠ valid never opens the squelch (carrier squelch); only…|I|wire:421-424, listener:298-300; t/records:508|As a hard gate, not a squelch: unlisted key, bad signature or ungranted class never…|
|**§14.6.3**|**Local expiry (decay)** (7 I · 2 U · 1 ?)||||
|1780|expires_eff = min(expires_at, issued_at + effective max TTL) (§6.2)|I|wire:379-384; fe/wire:421-434; t/listener:91||
|1781|local_expiry = min(expires_eff + δ̂, first_heard + (expires_eff −…|I|wire:385-388; fe/wire:435-438; t/listener:69||
|1784 MUST NOT|an item never lives locally longer than its full TTL counted from…|I|wire:386-387, listener:343-347; t/listener:69||
|1784|δ̂ (§8.2) can only bring expiry earlier than that|I|wire:385-388, listener:104-106; t/listener:77||
|1785|Without a beacon from the station, δ̂ = 0 and the TTL cap governs.|I|listener:104-106,226; t/listener:631|Offsets are not persisted, so this also holds after a restart until the next beacon.|
|1785 SHOULD|Receivers SHOULD keep their clocks synchronised.|**?**|records:545-546|Operator practice; each host's owner could answer. The daemon only reports: health clock_skew when a station offset passes 5 s.|
|1786|For a PLUCK, the effective max TTL is the largest class maximum TTL|I|wire:379-383; fe/wire:427-433; t/listener:700||
|1787 MUST|At local expiry an item MUST lose all current-state authority in…|I|listener:648-654, records:567; fe/records:1422-1426; t/records:252|Receptor retracts at its 250 ms tick|
|1787 MUST|any modulation it caused MUST enter the lapse path (§14.7.2)|U||No modulation exists.|
|1788|Emeric's test "a replayed frame with 2 seconds remaining disappears…|U||No test named EM-01 in either repo.|
|**§14.6.4**|**Desensitization** (1 I · 1 D · 2 U)||||
|1792|Homologous: an identical tuple never re-triggers (§12.1).|I|listener:333-336, pl/binding:422-425; fe/delivery:1043-1052; t/records:150|#173 counts exact repeats before verify (#173/records:368-379)|
|1793|Same-content re-issues from one principal collapse to one root (R-INT-2).|**D** owner|records:460; fe/delivery:1936-1972|Station and plugin compare no bodies. frond-ear collapses only a keyed refresh-flagged re-issue with an equal digest; its tests assert that the same words under a new seq are new speech. Principal is always null, so no per-principal rule is possible.|
|1794 SHOULD|after N = 5 surfacings from one stream within W = 10 min, the…|U||No theta or surfacing counter per stream.|
|1795 MUST NOT|a tighten from the same (station, stream) MUST NOT take effect…|U||No tighten.|
|**§14.6.5**|**Dose** (2 D)||||
|1799 SHOULD|A session SHOULD receive at most two canticle context slots (§14.14)|**D** rfc|pl/candidates:222-230, pl/ambient-slots:119-163; fe/delivery:1399-1448|Plugin complies: canticle:digest and canticle:alarm, one live entry each. frond-ear has no slots: each push is its own turn-sized event, up to maxPushesPerHour (60 default, 360 max).|
|1799 SHOULD|the digest SHOULD carry at most 5 items and 1.5 KB per turn|**D** owner|pl/candidates:14,221-230; fe/src/config:461-463|Plugin complies (5 items, 1 536 B, metadata lines only). frond-ear: 5 items default but up to 10 per push, and 6 000 chars (limits.maxNotificationChars) instead of 1.5 KB. Plugin explicit reads are 20 entries, 12 KB. Admitted: pl/README:483 (reads; its 'this spike does not….|
|**§14.6.6**|**Automatic gain control** (3 U)||||
|1803 SHOULD|No single station SHOULD occupy more than 25% of a session's digest… ‖ Gain reduction is immediate and recovery gradual (10-minute… ‖ AGC uses cadence as transport telemetry only (R-INT-6).|U×3||No per-station share of a digest. No gain control. No AGC; nothing reads cadence except presence.|
|**§14.6.7**|**Homeostasis** (3 U)||||
|1807 SHOULD, dflt|A receptor SHOULD adjust each session's θ every 10 minutes by ‖ with set point R = 12 surfaced items per hour per session ‖ Alarm and control classes are exempt; they have their own budgets.|U×3||No theta, no set point, no surfaced-rate counter. No set point. No exemption: frond-ear's push budget and the plugin's perHour…|
|**§14.6.8**|**Proofreading and consumption modes** (5 I · 2 D · 8 U)||||
|1818 MAY|Verified silent landing (§14.9) MAY be immediate.|I|pl/candidates:165-168; pl/t/ambient-binding:131|Optional: the plugin makes live-state, alarm, root and finding-ref eligible at once…|
|1818 MUST|Before a verified alarm can wake a session (§14.10 item 11), the receptor MUST have one of two kinds of evidence|**D** rfc|pl/config:98-100; fe/delivery:1168-1180|No proofreading exists. frond-ear pushes any class, alarms included, from an allowlisted key at hop 0 after a 5 s debounce, with no beacon or corroboration evidence. Plugin never wakes.|
|1819|The receptor has admitted k signed beacons from the alarm's…|U||No beacon counting per item.|
|1820|its wallclock is not earlier than the alarm's issued_at|U||Covers lines 1820-1822: none of the three beacon conditions is…|
|1824 MUST|The receptor MUST also have heard every seq in (alarm seq…|U||No gap tracking: record gap is always "unavailable".|
|1825|Independent principals with distinct lineage roots corroborated the…|U||No principals (always null), no corroboration.|
|1826|Carousel copies of a tuple are byte-identical and carry no…|I|station:434-439,313; t/station:37||
|1826 MUST NOT|It MUST NOT satisfy proofreading, and it MUST NOT count toward any…|I|listener:329-336; fe/hear:140; t/records:150|Nothing contrary: a repeat only bumps copies (display) and stream-hearing time for…|
|1826|Beacons can't be manufactured from a captured item, because each…|I|listener:257-263; t/records:489||
|1827, MUST|k and the window are derived per stream from its advertised beacon… ‖ The maximum latency that proofreading adds to an alarm wake MUST be…|U×2||Open (23.2). Beacon fields are held per stream Not defined or tested.|
|1828|A repeat still adds nothing to salience, evidence mass or accord…|I|listener:333-336; t/records:150|Nothing to add to; repeats are no-ops in state.|
|1829 MAY|A session's tune entry MAY choose how heard items reach it:|U||Optional. No raw/completed choice in either binding.|
|1830 dflt|raw (the default): an item lands as soon as it is verified|**D** code|listener:454-466, pl/candidates:165-168; fe/src/config:435-440|The receptor surfaces at once (live-state waits for warm-up). Bindings add delay: plugin 0-60 s for three classes (A11), frond-ear at least 5 s.|
|1831|the receptor holds items so that gaps in [trail_seq, head_seq]…|U||No completed mode.|
|**§14.7**|**The immune grammar** (1 I · 1 D · 3 U)||||
|1835|All regulatory effects are receiver-local modulation…|U||No regulatory effect exists. modulation is always []|
|1835 MUST NOT|They are never session actuation, never commands, and never forced…|I|records:485-493, runner:31|Nothing contrary in receptor or plugin: no op is read.|
|1837|Regulatory frames are class 6 with content type 6:|**D** rfc|ids:109,129; fe/ids:96|Both numbers are registered, but nothing ties them: the listener and Station.sing accept any ctype on class 6. The agent control socket refuses class 6. Admitted: README:65.|
|1841|; op: 0 tighten, 1 all-clear, 2 quarantine-vote, 3 rescind-vote|U||The regulatory-body CDDL (1840-1849) has no encoder, decoder or…|
|1851|state_key for regulatory frames is the op plus a hash of the target|U||state_key is any 1-32 byte string|
|**§14.7.1**|**Tighten** (2 U)||||
|1855 dflt|raises the threshold of the affected listen band by Δθ = +0.5… ‖ tighten-frond-discriminator (op 6) also restricts that band to…|U×2||No tighten. No op 6.|
|**§14.7.2**|**All-clear, stand-down and lapse** (1 I · 3 U)||||
|1860|valid tighten (capable principal, not in refractory R)|U||The state machine (1860-1868: TIGHTENED, RESOLVING, LAPSED and…|
|1871 MUST|Resolution MUST be an explicit signed frame whose authority is at…|U||No all-clear handling.|
|1871 MUST NOT|Silence, expiry and absence MUST NOT be interpreted as all-clear…|I|listener:725-733; fe/records:1455-1458; t/listener:50|Nothing reads an all-clear from silence|
|1873|Neither path deletes evidence.|U||No paths, and no evidence store: evidence is counters.|
|**§14.7.3**|**Quarantine (two-signal activation)** (4 I · 3 D · 6 U)||||
|1878|NONE ──signal 1 only──▶ ANERGY (evidence logged; no effect; expires…|U||No anergy state, votes or signal 2 (lines 1878-1882).|
|1880 dflt|└─signal 1 + signal 2 ─▶ QUARANTINED(ttl = 1 h)|**D** rfc|records:428-434,584-596|The only quarantine (equivocation) has no TTL: it is persisted and lasts until the state file is removed with the daemon stopped. Admitted: README:502-503.|
|1882|signal 2 = Q ≥ max(2, ⌊N/3⌋+1) distinct eligible principals|U||No quarantine votes, principals or accord.|
|1883|QUARANTINED: target's frames → ringbuffer_only, zero accord, not…|I|records:389-392,428-434; fe/listener:748-758; t/records:222|Items are verified/ringbuffer_only/key_quarantined with body, and its surfaced items…|
|1883|root-signed control still passes|U||No root key and no control handling|
|1884|renew only with fresh signal 1 within the TTL; at most 24 h without a human|**D** rfc|records:428-434|No renewal and no 24 h cap: the quarantine has no end. Admitted: README:502-503.|
|1885|rescind: Q ≥ q + 1, or root-signed, or a local human ──▶ NONE…|U||No rescind of any kind, not even a local CLI|
|1886|expiry ──▶ NONE (evidence retained; antibody memory only if…|U||No expiry.|
|1887|An equivocation proof supplies signals 1 and 2 at once for the local receptor (still TTL-bounded).|**D** rfc|records:352-356, listener:324-328|The first half holds (one equivocation quarantines the key at once); it is not TTL-bounded. The proof itself is not kept: only the first frame's digest is, neither raw frame. Admitted: README:474,502-503.|
|1888|If quarantines by accord would exceed max(1, 10% of eligible…|U||No accord quarantines, no cap.|
|1891 MUST NOT|It MUST NOT cause network, host, credential or physical action…|I|records:428-434|Effect is a set membership, retract records and a disposition. No test.|
|1892|A single member cannot quarantine another|I|records:352-356; t/records:222|Only a key's own two conflicting signatures quarantine it|
|1893|Receptor example 2 (foreign or unsigned quarantine signal gives…|I|records:328-332; t/records:508||
|**§14.7.4**|**Remember only by promotion (antibody memory)** (1 D · 4 U)||||
|1897|Antibody memory is a ledger entry keyed by antigen digest|U||No antibody memory, antigen digest or entry.|
|1898 MUST, dflt|It MUST be created only by an explicit promotion act by an… ‖ It is bound to its promoters and expires (default max age 7 days).|U×2||No promotion act (nothing creates memory either). No antibody memory.|
|1899|A frame matching hostile memory is stored ringbuffer_only with…|U||No match step, no benign match.|
|1900|This replaces the prototype's global, permanent, issuer-unbound tombstones (bug B5)|**D** rfc|records:584-596|No such tombstones in the spike, but a permanent record came back for keys: an equivocation quarantine never ends. (Issuer-bound, so narrower than B5.) Admitted: README:502-503.|
|**§14.7.5**|**No remote downgrade** (1 I · 1 D)||||
|1904 MUST|They, and any "accept unsigned" mode, MUST be local settings only.|I|wire:421-424, records:194; t/records:508||
|1904 MUST|Received frames asking for them MUST be ignored and logged|**D** rfc|records:485-493|Ignored as requests (no op is read) but not logged as downgrade attempts: a granted class-6 item surfaces as ordinary content. These ops have no code in 14.7's CDDL, so nothing could recognise them.|
|**§14.7.6**|**Alarms** (2 I · 2 D · 4 U)||||
|1908|Alarm frames are class 7, content type 5, with a CAP-like typed body. They are never free-text instructions.|**D** rfc|ids:110,128|Class 7 and ctype 5 are registered, but any ctype is accepted on class 7: tests sing a text/plain alarm and it surfaces (hop 0). The control socket refuses alarms. Admitted: README:65.|
|1912|1 =› tstr .size (1..32), ; alarm id (also the state_key)|U||The alarm CDDL (1910-1919) has no encoder, decoder or check.|
|1922|Expiry is mandatory (the class maximum is 3 600 s)|I|wire:260, ids:110; t/wire:152||
|1922|the exercise flag (flag bit 2) marks drills, which render as EXERCISE|**D** rfc|wire:75, records:471; fe/hear:131|The bit is defined and in record v1. Only frond-ear renders EXERCISE. canticle tap prints no flag, the plugin parses it and never shows it, and its alarm slot line has no marker: a drill reads as a real alarm. Station CLI/socket can't set it.|
|1923 MUST|automatic response to a verified alarm MUST be limited to…|U||No automatic tightening, banner change or stricter taint on an…|
|1923 MUST NOT|Alarms MUST NOT trigger automated remediation, destructive actions…|I|records:389-397, pl/candidates:222-230|Nothing contrary: alarms are items, shown as data. No test.|
|1924 MUST|An all-clear MUST carry authority at least equal to the alarm's.|U||No all-clear.|
|1925 dflt|at most 3 alarms per 15 minutes each|U||No panic budget.|
|**§14.7.7**|**Lower-attention and soothing** (3 U)||||
|1929|lower-attention (op 4) halves the target streams' weights w_s for…|U||No weights, no op 4.|
|1930, MUST NOT|grounding-anchor (op 5), the loop-soothing class ‖ It MUST NOT lower θ below θ0, MUST NOT suppress alarm or control…|U×2||No op 5: no allowlist, scope, TTL, once-only loop or effect… No effect to bound.|
|**§14.7.8**|**Echo-chamber detector** (2 U)||||
|1934 SHOULD, MUST NOT|A receptor SHOULD compute similarity (for example simhash) across… ‖ It MUST NOT quarantine or arbitrate truth on this basis|U×2||No similarity code. No detector, so nothing acts on similarity.|
|**§14.8.1**|**Wake-derived frames never wake** (1 I · 1 D)||||
|1940 MUST|Frames sung within a turn that canticle woke MUST carry wake_derived (flag bit 1), set by the publish tool|**D** rfc|runner:85-107, station:268-272; fe/delivery:1168-1180|frond-ear wakes turns today, and nothing stamps their songs: the station control socket has no flags or hop field (always 0), so a woken session's canticle sing goes out hop 0, wake_derived 0. The plugin sidesteps it: it never wakes and a tainted session can't sing. Admitted: pl/README:479-480 (plugin); none for frond-ear…. #162 #162/derived_reply_proposal:590-604 stamps it on its derived reply path only; plain sing still doesn't|
|1940 MUST NOT|MUST NOT be wake-eligible on receipt.|I|fe/delivery:1174-1175; fe/t/canticle-delivery:749|frond-ear passes over wake_derived (and an unknown flag) and hop › 0|
|**§14.8.2**|**Budgets independent of the harness** (1 D · 1 U)||||
|1944 MUST|A receptor MUST therefore enforce its own per-session wake bucket|**D** rfc|pl/config:98-100; fe/src/config:184-185|The receptor has none (BC-1 gives it to the binding). frond-ear has a per-ear rolling-hour push cap, default 60 (or one per window, max 360), durable across restart; 14.10 says capacity 2, refill 1 per 10 min. Plugin never wakes.|
|1944 MUST|per-host wake budget and canticle token budget (§14.10)|U||Neither exists: no cap across a host's ears and no token…|
|**§14.8.3**|**Circuit breaker** (2 D · 5 U)||||
|1949|CLOSED ──trigger──▶ OPEN(15 min)|U||No trigger (1949-1951): surfaced rate, alarm cap, MUTE.|
|1952|OPEN: silent landing only; no wakes; digest collapsed to one line per stream|**D** rfc|pl/binding:464-466; fe/delivery:1383-1385|Binding side only, and never triggered. Plugin: one line per stream name (two stations' same-named streams merge) and the alarm slot is emptied too. frond-ear: no push at all while not closed; no silent landing. No wake in either. Admitted: pl/README:9 ("breaker digest semantics" remain….|
|1953|relays forward only control and alarm|U||No relay.|
|1954|OPEN ──cool-down──▶ HALF_OPEN(10 min): one wake allowed per host; digest at 25%|**D** owner|pl/binding:466; fe/delivery:1383-1385|No producer. Plugin cuts each slot to floor(n/4) of at most 5, so 0 or 1 line, alarm slot included (1-3 items show none). frond-ear holds every push, so no half-open wake. Admitted: pl/README:9.|
|1955|HALF_OPEN ──below R for the window──▶ CLOSED|U||No transitions (1955-1956): no R, no doubling to 2 h.|
|1959 MUST, SHOULD|Relays MUST cap new alarm tuples fleet-wide (default 10 per minute) ‖ SHOULD advertise breaker state in relay beacons (§9.8 key 11)|U×2||No relay. Key 11 is accepted as any map and ignored; nothing sends it.|
|**§14.9**|**Landing modes** (13 I · 4 D · 3 U)||||
|1963|The listener elects the landing mode. The sender does not.|I|pl/config:129-131; fe/delivery:787-814; fe/t/canticle-delivery:1074|Config sets a ceiling, the session can only narrow (fe); plugin posture is config.|
|1963|A sender's urgency or suggested "fire level" is a hint.|I|records:467|Intensity travels in record v1|
|1967|silent (default) / Lands in the session's digest slot; colors its…|I|pl/ambient-slots:119-163, pl/oc0-host:15-38; pl/t/plugin:87|Spike only, against a fake OC-0 host; its README says no seat runs it.|
|1967|no wake / hook additionalContext from the receptor digest / default|U||Claude Code column: no hook returns a canticle digest.|
|1967 dflt|enqueueSystemEvent, no wake / hook additionalContext from the receptor digest / default|**D** code|pl/config:129; fe/src/config:455|Both bindings default to nothing lands (plugin ringbuffer_only, fe off), as line 1975 says. The RFC names two defaults, silent here and ringbuffer_only/off there.|
|1968|silent-wake / Lands and wakes the session, only under §14.10|**D** rfc|fe/delivery:1168-1180|fe emits notifications/claude/channel, which starts a turn in an idle session (fe/docs/spike/2026-09-claude-channel-gateway:86). Gate: wakeKeys + hop 0 + not wake_derived + operator mode, not the 11 items. Digest reports wake too. Admitted: fe/docs/runbook:851.|
|1968|channel notification; asyncRewake hook; inbox-socket message / alarm class only|**D** rfc|fe/delivery:1168-1180|No class test on the push path. fe's own tests assert class=advisory pushed as mode=silent-wake (fe/test/canticle-delivery.test:38). wakeEligible (fe/ids:64) is never read. Admitted: fe/docs/runbook:851.|
|1969 MUST NOT|reserved: MUST NOT be used for heard remote content|I|pl/config:129-131; fe/delivery:114|No code stages canticle content across compaction.|
|1971 MAY|A binding's configuration MAY name a subscription's posture with…|I|pl/config:129-131; fe/src/config:147; pl/t/candidates:21|Plugin uses ringbuffer_only/ambient.|
|1971|They map one-to-one onto the tune postures of §14.6.1 and the landing modes above, and mean nothing else|**D** owner|pl/config:129-131; fe/src/config:146-147|True in the plugin. fe's digest and immediate both land as silent-wake, so two names map to one landing mode and none maps to silent. Admitted: fe/docs/runbook:844-846.|
|1975 dflt|ringbuffer_only / off / none: the binding's local ring only /…|I|pl/config:129, pl/binding:426-441; fe/src/config:455; pl/t/plugin:471|Default from config:129 when delivery is absent|
|1976|ambient / silent / silent / yes; in OpenClaw over OC-0 (§16.4)|I|pl/index:101-118, pl/ambient-slots:119-163; pl/t/plugin:87|Spike, fake host.|
|1977|wake / wake-on-alarm / silent-wake / alarm class only (D1, D25)…|I|pl/config:98-100,130; pl/t/candidates:21|The OpenClaw binding refuses wake at config.|
|1979|No delivery name maps to post-compaction (D13).|I|pl/config:129-131; fe/src/config:395-400|Neither binding has such a name. No test for this name itself.|
|1979|canticle content never lands as a system event and no heartbeat…|I|pl/oc0-host:16-38|The plugin's only host calls are the three next-turn-injection methods|
|1981|only ledger-promoted content (§6.4) may be staged across…|U||No ledger, so no promotion.|
|1985 MUST NOT|No request_id / awaiting_reply pending state, and no sender timer…|I|runner:82-118, station:268-272|Nothing contrary: no such field or timer in station, daemon, plugin or fe (grep).|
|1986 MUST NOT|"Addressed" never implies auto-surface.|I|wire:60-76|Vacuous: no addressed_to field, no addressed mode anywhere|
|1986 MAY|An addressed_to hint MAY raise an item's weight by at most one step|U||Optional. No addressed_to hint exists and nothing weighs items.|
|1987 MUST NOT|No observable "B did not reply" signal.|I|runner:82-118; fe/src/egress:104-118|Nothing on the wire or station status says who heard or answered.|
|**§14.10**|**Wake policy** (12 I · 18 D · 6 U)||||
|1991|silent landing by default|I|pl/config:129; fe/src/config:332-343; fe/t/canticle-delivery:1305|Defaults: fe mode off and wakeKeys empty (nothing pushed); plugin explicit read.|
|1991 MAY|MAY escalate verified alarm frames to silent-wake for designated responder sessions, under the conjunction below|**D** rfc|fe/delivery:1168-1180|fe escalates every class from an allowlisted key, not alarm. No alarm can be sung over a control socket at all (runner:31), so in practice only non-alarm frames wake. Admitted: fe/docs/runbook:851.|
|1993|The initial deployment is silent-only.|**D** rfc|fe/src/shim:654-667|False in fact: fe's push path is installed on two scribe seats (pr168/docs/design/sense-organ:149 'with custody and wake'). bc#100 is named as tracking the amendment; the RFC and bc README have no note. Admitted: fe/docs/runbook:851.|
|1993 MUST NOT|A receptor MUST NOT enable silent-wake until S3 has implemented and tested the whole receiver-side conjunction|**D** rfc|fe/delivery:1168-1180|S3 is not built; fe enables it by config (wakeKeys + delivery). Only the plugin refuses wake (pl/config:130). Admitted: fe/docs/runbook:851.|
|1994|manifest capability|**D** rfc|fe/delivery:1173|Replaced by a local list of station key ids. The manifest's alarm capability is not consulted. The test shows the replacement, not the rule. Admitted: fe/docs/runbook:851.|
|1995|explicit local stream and session opt-in|**D** rfc|fe/src/config:409-423|Opt-in is the operator's: streams by canticle.tune, wake mode per ear or station. The session never opts in; it can only narrow or mute. Admitted: fe/docs/runbook:851.|
|1996|hop 0, and lineage that is not wake-derived|I|fe/delivery:1174-1175; fe/t/canticle-delivery:749||
|1997|the freshness bound|**D** rfc|fe/delivery:260-261|Bounds immediate only (30 s, max 120 s). An older record still wakes, in the next report, marked late. Admitted: fe/docs/runbook:851.|
|1998|independent session, host and token budgets|**D** rfc|fe/delivery:1386-1389|One per-ear cap of 60 pushes an hour by default (max 360). No host budget, no token budget; two ears on a host have independent caps. Admitted: fe/docs/runbook:851.|
|1999|coalescing and the circuit breaker|I|fe/delivery:1138-1141; fe/t/canticle-delivery:38|Coalescing half: debounce 5 s minimum.|
|1999|coalescing and the circuit breaker|**D** rfc|records:282-290; fe/delivery:1383-1385|Breaker half: fe holds unless closed, but no daemon ever opens it (set_landing: nothing calls this but tests) and fe's embedded source has no breaker, so the hold never fires. records.py says so in code only.|
|2000|sandboxing, taint handling (§14.12) and sealed bootstrap state|U||None on the wake path.|
|2001|proofreading (§14.6.8).|U||No proofreading code in any implementation|
|2002|A sender can neither request nor force a wake.|I|wire:75, runner:90; fe/delivery:1168-1180; fe/t/canticle-delivery:749|No wire field asks for a wake; the receiver's list and mode decide.|
|2003|Landing heard content after compaction stays reserved in v1 (D13…|I|pl/config:129-131; fe/delivery:114|No path lands canticle content because of a compaction.|
|2005|Until S3 passes, deployments behave as if it were in force.|**D** rfc|fe/delivery:1401-1480|Strict no-wake is not in force on a Claude seat with canticle.delivery set and wakeKeys non-empty. Admitted: fe/docs/runbook:851.|
|2007 MAY|A receptor MAY wake a session only if all of these hold:|**D** rfc|fe/delivery:1168-1180|fe wakes with items 1, 8, coalescing and part of 9 enforced; 4, 5, 6 replaced by other rules; 2, 3, 7, 10, 11 not checked. Admitted: fe/docs/runbook:851.|
|2009|The admission result is verified (§10.9)|I|records:389-392; fe/records:1196-1204; fe/t/canticle-records:124|fe drops anything not verified + surface before it can be pushed.|
|2009|the key is not quarantined|I|records:389-392,428-435; fe/records:1196-1204; t/records:222|Local equivocation quarantine only: the key's frames stop being surface, so fe cannot…|
|2009|the receiver is not under MUTE|I|records:282-290, pl/binding:480-487; fe/records:1419-1420; fe/t/canticle-records:109|Both bindings honour landing_state.mute, but the daemon never sets it (set_landing…|
|2010|The key holds the alarm capability in the manifest.|**D** rfc|fe/delivery:1173|fe checks its own wakeKeys list instead. A key with only chatter can wake. Admitted: fe/docs/runbook:851.|
|2011|The class is wake-eligible. In v1 that is alarm only.|**D** rfc|ids:98; fe/delivery:1168-1180|Not checked. wake_eligible/wakeEligible are defined in both class tables and read nowhere. Admitted: fe/docs/runbook:851.|
|2011|public frames and aspect streams are never wake-eligible (§17.5).|**D** rfc|fe/delivery:1168-1180|fe reads neither scope nor lens before pushing: a public-scope or lens. record from an allowlisted key is pushed. The runbook's departure row does not mention scope or aspect streams.|
|2012|The session opted in: its tune entry for this stream is wake-on-alarm.|**D** rfc|fe/src/config:409-423|No wake-on-alarm posture exists. Operator config elects the ear; the session may only narrow (set_canticle_delivery). Admitted: fe/docs/runbook:851.|
|2013 dflt|The session's wake bucket has a token (capacity 2, refill 1 per 10 minutes).|**D** rfc|fe/delivery:1386-1389|fe: rolling-hour cap per ear, 60 by default (about 10x the RFC's 6 an hour), up to 360; no burst limit of 2. Admitted: fe/docs/runbook:851.|
|2014 dflt|The host wake budget (6 per hour) has room|**D** rfc|fe/delivery:1386-1389|No host-wide budget: the cap is per ear and each ear has its own. Admitted: fe/docs/runbook:851.|
|2014|the circuit breaker is CLOSED (or HALF_OPEN with its allowance unspent)|**D** rfc|records:282-290; fe/delivery:1383-1385|fe holds on open and half_open (stricter), but the breaker is never anything but closed on main, and absent on the embedded source. Admitted: fe/docs/runbook:855.|
|2015 dflt|The session's canticle token budget (200 000 tokens per day) is not… ‖ The receptor reads usage from the harness; this budget is…|U×2||No token budget anywhere Nothing charges canticle wakes to a token count.|
|2016|hop = 0, and flag wake_derived is 0.|I|records:464-470; fe/delivery:1174-1175; fe/t/canticle-delivery:749|Enforced by fe.|
|2017 dflt|The frame's age at first hearing is at most stale_after[alarm] (120 s)|**D** rfc|fe/delivery:260-261|Held to at most 120 s for immediate; older records go into a report, which wakes as well. Admitted: fe/docs/runbook:851.|
|2017|it is neither superseded nor plucked|I|fe/delivery:1410-1421; fe/t/canticle-delivery:1237|A push carries only what is on the live view at that moment.|
|2018|Host prerequisites hold. For OpenClaw: sandboxing is on for the…|U||No check exists.|
|2019|Proofreading has passed (§14.6.8).|U||Not implemented by any listener or binding; fe wakes without it.|
|2021 MUST|Wakes MUST be coalesced (OpenClaw coalesceMs ≥ 5 000 ms).|I|fe/delivery:1138-1141; fe/t/canticle-delivery:38|fe immediate: 5 s minimum, config below it refused. Digest windowMs also at least 5 s.|
|2021 MUST|Each wake MUST be logged with its evidence.|I|fe/delivery:1550-1556; fe/t/canticle-custody:254||
|**§14.11**|**Hop count and lineage** (3 I · 3 D · 7 U)||||
|2027|The publish tool stamps hop and lineage|**D** rfc|station:268-272,309-312|sing always signs hop 0 and no derived_from/root, whatever the session heard. The plugin refuses a payload-tainted sing instead; a Claude seat sings through Bash canticle sing with no check. Station README has no note. Admitted: plugin/README:480. #162 derived_reply_proposal:602 stamps them on its separate derived op (off by default); ordinary sing unchanged|
|2027|the agent cannot set them (§15.4)|I|runner:90, pl/tools:112-120|The control socket forwards a fixed key list without hop, flags or lineage|
|2028|hop = 0 if the session has drained no heard item since its last reset; otherwise hop = 1 + max(hop of heard items…|**D** rfc|station:272, runner:90|Always 0 on main. fe keeps the needed facts (custody rows with hop and root, fe/delivery:175-183) but has no sing tool that uses them. Admitted: plugin/README:480. #162 derived_reply_proposal:420,602 computes 1 + max over all exposures|
|2029|derived_from = the identity tuples of up to 4 heard items most… ‖ root = the lineage root of the first of them (roots propagate)|U×2||main's Station.sing has no such argument. #162 derived_reply_proposal:421,602 stamps the last 4 Never set on main. #162 derived_reply_proposal:603 root = first of the last four, its root or itself|
|2030 MAY, MUST NOT|The agent MAY add references of its own ‖ it MUST NOT remove tool-stamped ones|U×2||Optional; no input carries references. Nothing is stamped, so nothing can be removed|
|2031 MUST|Receivers MUST drop frames whose hop exceeds the class hop limit…|I|listener:309-312, ids:104-112; fe/listener:725-737; t/listener:198|Both listeners, before any state changes. fe test: fe/test/canticle-listener.test:681.|
|2032|A relay or bridge preserves the frame's identity and bytes.|U||No relay or bridge exists in either repo.|
|2032|A session that re-sings produces a new frame with lineage back to the source.|**D** rfc|station:309-312|A re-sing is a new frame with no lineage at all and hop 0, so it looks like a first-hand item. Admitted: plugin/README:480. #162 derived op adds lineage|
|2033 MUST NOT|A re-sing MUST NOT raise class.|U||No sing path knows what a session heard #162 derived_reply_proposal:431 allows chatter from chatter only|
|2033|Alarm, control and regulatory frames are never re-sung (hop limit 0)|I|ids:109-111, runner:31; t/station:496||
|2033|they are only bridged byte-identically|U||No bridge.|
|**§14.12**|**Heard content is data: taint** (3 I · 3 D · 7 U · 2 ?)||||
|2039|A session that has drained any canticle item is tainted|**D** rfc|pl/binding:773-775, pl/ambient-slots:77-83|Plugin taints on an items read or a consumed OC-0 slot; a digest read drains items and does not taint (README asks if it should). frond-ear and tap have no taint at all (fe/docs/runbook:852). Admitted: plugin/README:489.|
|2039|is tainted until it is reset|I|pl/binding:617-644, pl/index:68-87; pl/t/plugin:487|Plugin: cleared only by a reset callback naming the current session id and lifecycle…|
|2039|a human explicitly approves|U||No approval path exists in any implementation|
|2041 MUST|command execution outside a sandbox|U||No host denies it.|
|2042 MUST|writes to the agent's bootstrap, configuration or memory files|U||Not denied anywhere; no code consults taint for file writes.|
|2043 MUST|skill or plugin installation|U||Not denied anywhere. plugin/README:285-290.|
|2044 MUST|outbound messages to off-host targets|U||Not denied. fe's room gate: observe (default) refuses nothing|
|2045 MUST|canticle_sing at fleet or public scope, or in wake-eligible, control or regulatory classes|**D** rfc|pl/binding:1142-1148, pl/config:53|Plugin is stricter: a tainted session cannot sing at all. Claude seats sing with canticle sing (Bash): any granted scope, no taint check, only the class refusal of SOCKET_NEVER. Admitted: plugin/README:479.|
|2046 MUST|ledger promotion of heard content|U||No ledger exists to promote into, so nothing to deny.|
|2047 MUST|automatic fetches of heard body_ref URLs whose host is not listed…|I|pl/render:88-91, tap:129-132; fe/hear:174-178; fe/t/canticle-hear:105||
|2049 SHOULD|Hosts SHOULD show the taint state to the session and to operators.|I|pl/binding:1007,1033; pl/t/plugin:87|canticle_status shows it to the session that asks; no operator surface.|
|2051|Not adopted: the rule above, item 4 included, is unchanged until the owners revise it.|**?**||Owners' decision (§23.2 q22). frond-ear already answers it one way: every ear's reply route stays open after hearing (fe/docs/runbook:852).|
|2051|Test gate before adoption: in a tainted session, (a) a reply on the…|U||None of (a)-(c) is tested or enforced in either binding.|
|2053 MUST NOT|ambient delivery (§14.18.4) MUST NOT target a session that has an off-host channel route|**D** owner|pl/candidates:69-77,138-148; fe/src/daemon:784-818|Plugin enforces it (host onHost proof, shared main refused). fe violates it by design: every ear is a Discord-bound session and gets pushes with payload. Owners must settle q22 for Claude seats. Admitted: fe/docs/runbook:852.|
|2053|when its reply or channel route delivers to an off-host target in the sense of item 4|**?**|pl/index:113-115|Decided by OpenClaw's resolveLocalSessionRoute, not in these repos: whether its onHost matches this definition, openclaw owners can say.|
|**§14.13**|**Arrival banner** (14 I · 4 D · 1 U)||||
|2059 MUST|Every landing carries a host-authored arrival banner|**D** rfc|pl/render:100-125, tap:142-174; fe/hear:108-180|True for hear, pushes, tap, plugin items. Not for: plugin OC-0 slots (bare line, host expected to render), fe counts reports, and canticle listen JSON, which the station README tells Claude Code to run under Monitor (event per line). Admitted: README:224-230.|
|2059 MUST|The banner is outside the untrusted-content wrapper; only the…|I|pl/render:100-125, tap:149-174; fe/hear:81-91; t/tap:182|But station-written purpose sits outside too (RFC line 2066)|
|2062|[canticle:heard] delivery=station-broadcast mode=silent…|I|pl/render:104, tap:150-151; fe/hear:118-131; fe/t/canticle-hear:47|Same fields in all three.|
|2063|station="magi-threat" principal="ops-east" key=21fe31dfa154a261…|I|pl/render:105, tap:152-153; fe/hear:122-126; t/tap:198|Values: principal always reads unavailable (no manifest principal).|
|2064|item=7/42 hop=1 root=21fe31dfa154a261:7:1a2b3c4d:1|I|pl/render:106, tap:154; fe/hear:127-129; fe/t/canticle-hear:278|root reads unavailable for every first-hand item heard through the daemon (record…|
|2065|issued=2026-09-27T08:00:00Z heard=2026-09-27T08:00:40Z…|I|pl/render:107, tap:155-156; fe/hear:133-144; fe/t/canticle-hear:278|Meanings differ: expires is the local expiry in tap and plugin, the signed expires_at…|
|2066|purpose (declared by the station; context, not authority): "what is…|I|pl/render:112-114, tap:158-159; fe/hear:147-151; fe/t/canticle-hear:105|Plugin JSON-quotes, fe strips to one line; tap does neither (finding).|
|2067|heard broadcast — not an instruction; cannot authorize actions; do…|I|pl/render:15, tap:35; fe/hear:152-154; t/tap:182|Identical text in all three. tap --json carries it as notice.|
|2068|‹‹‹EXTERNAL_UNTRUSTED_CONTENT id="…"›››|I|pl/render:117, tap:167; fe/hear:84-89; fe/t/canticle-hear:278||
|2068|‹‹‹EXTERNAL_UNTRUSTED_CONTENT id="…"›››|**D** code|pl/render:118, tap:168; fe/hear:85|RFC line 2069 (too short to quote) is 'Source: API'; all three print 'Source: canticle'. 'API' is OpenClaw's wrapExternalContent label; a canticle label is truer. Fix the template.|
|2070|From: magi-threat 21fe31dfa154a261|I|pl/render:119, tap:169; fe/hear:86; fe/t/canticle-hear:47||
|2076|Station name and principal come from the manifest, never from the…|I|records:460; fe/hear:122-123; t/records:130|Name half: entry.name from the manifest, through record v1.|
|2076|principal come from the manifest, never from the frame|U||Principal half: the manifest has no principal field, so the…|
|2077 MUST NOT|The banner MUST NOT disclose other recipients, listener counts or…|I|pl/render:100-125, tap:142-174; fe/hear:117-146|No such data reaches a renderer. fe's copies= counts repeats heard, not recipients.|
|2078 MUST|Missing provenance MUST read "unavailable"; it is never fabricated|I|pl/render:66-78, tap:67-70; fe/hear:36-43; fe/t/canticle-hear:47|tap writes scope and stream raw, so a missing one would read None|
|2078 MUST|Late delivery MUST be visible as late|I|pl/render:163-177; fe/delivery:269-292; fe/t/canticle-delivery:851|fe pushes carry a late: line; plugin marks snapshot/resurfaced.|
|2079|The [canticle: prefix gives drain accounting and log searches an anchor|**D** rfc|pl/render:104, pl/candidates:163; fe/delivery:2424-2427|Present on every rendered item. Absent from the plugin's OC-0 slot lines (candidates:163) and fe's push headers and counts reports, so a drain of those has no anchor. No drain accounting exists.|
|2080 MUST|the receptor MUST strip [canticle: prefixes|I|tap:46-89, pl/render:29-54; fe/hear:56-63; t/tap:222|Replaced with a visible neutral form rather than removed.|
|2080 MUST|wrapper-marker look-alikes from the payload|**D** rfc|tap:40-48, pl/render:21-30; fe/hear:56-63|tap and plugin fold look-alike and fullwidth brackets first. fe matches ASCII only, so fullwidth brackets pass; its '› ' quoting of every payload line limits the harm. No departure note in fe.|
|**§14.14**|**Digest and slots** (9 I · 8 D · 2 U · 1 ?)||||
|2086|Canticle uses at most two host queue slots per session|**D** rfc|pl/ambient-slots:22,119-163; fe/delivery:1499-1508|Plugin: two. fe: each push is a new channel event that queues behind others, up to 60 an hour, and can't be rebuilt or recalled. Admitted: fe/docs/runbook:850.|
|2087|canticle:digest: ambient, chatter, live-state, advisory and…|I|pl/candidates:221-230; pl/t/candidates:112|Everything that is not alarm goes in, so regulatory, control and root records that…|
|2087|plus the MAGI posture line (§17.6)|U||No MAGI posture exists in any implementation.|
|2087|rebuilt and replaced in place|I|pl/ambient-slots:119-163; pl/t/ambient-binding:114|Conditional supersede by key. fe does not (row 2086).|
|2088|canticle:alarm: the current alarm state, replaced in place|I|pl/candidates:221-230; pl/t/ambient-slots:31|Up to 5 alarm lines, not a merged state; same supersede.|
|2089 dflt|The digest holds at most 5 items and 1.5 KB per turn|**D** rfc|pl/candidates:12-14,221-230; fe/src/config:463|Plugin: 5 and 1,536 bytes, but per slot (digest and alarm could be 10). fe: 5 records (up to 10) whole, up to limits.maxNotificationChars 6,000 per push. Admitted: fe/docs/runbook:850.|
|2089|ranked by salience and remaining life|**D** owner|pl/candidates:224; fe/delivery:208-217|No salience anywhere. Plugin sorts soonest-to-expire first, then newest heard; fe by station:stream then seq with a cursor. The plugin README gives no departure. Admitted: fe/docs/runbook:849.|
|2089|each entry is one line with the condensed banner fields|**D** rfc|pl/candidates:163, pl/render:129-135; fe/delivery:2697-2706|The slot line has class, scope, lens, item and expires, but no [canticle:heard], key, sig, hop, root or age, unlike the digest view's line (render:134). fe pushes whole records. Admitted: fe/docs/runbook:850.|
|2089|Full text is available on demand through canticle_listen (§15.1).|I|pl/binding:666-812; fe/src/daemon:3887-3908; pl/t/inbound:418|Plugin: only for sessions in listen.payloadSessions with a current host route proof.|
|2090|A superseded, plucked, revoked or expired item disappears from the…|I|pl/ambient-slots:172-189, pl/candidates:178-182; fe/delivery:1410-1421; pl/t/ambient-slots:61|fe pushes only what is on view at the push|
|2090|items that were already drained get a one-line "withdrawn/expired" note once|**D** rfc|pl/ambient-slots:183-189,222-236; fe/delivery:1410-1421|Plugin: yes, one metadata line. fe: never; a pushed record that is plucked or expires gets no note (frond-ear#67). Admitted: fe/docs/runbook:850.|
|2092|Per-frame records stay inside the receptor and the binding's local ring (§14.18.3)|**D** rfc|pl/binding:426-441; fe/delivery:2697-2706|Plugin: journal and candidate ledger keep them. fe: each push renders the records themselves into the session. Admitted: fe/docs/runbook:850.|
|2092|only the slots reach the session boundary|**D** rfc|pl/ambient-slots:119-163; fe/delivery:2698-2706|Plugin: only slots (plus what a session reads). fe delivers per-frame records with payload to the session. Admitted: fe/docs/runbook:850.|
|2092|the binding keeps at most two pending entries per session|I|pl/ambient-slots:74-76,119-163; pl/t/ambient-slots:31|One non-settled entry per slot key. Verified against a fake host only.|
|2092|A rebuild carries the still-live items of the entry it supersedes…|I|pl/ambient-slots:142-162; pl/t/ambient-slots:31|A superseded entry ends withdrawn and its keys are carried|
|2092|Settled tombstones and absolute expiry apply to each entry…|I|pl/ambient-slots:77-83,143-158; fe/delivery:93-95; pl/t/ambient-slots:111|Plugin: expiresAt + 5 s tombstones per frame key and a deadline per entry.|
|2092|an entry expires no later than the earliest local expiry of the…|I|pl/ambient-slots:145; pl/t/ambient-slots-races:45|deadline = min(expiresAt).|
|2092|and the binding rebuilds it by then|**D** rfc|pl/binding:326-339, pl/candidates:221|The rebuild runs on a new record or the 5 s tick, after the earliest item expired, so survivors can be absent from the host for up to 5 s. No test.|
|2092|Host drain caps (§16.4 item 5) are defence in depth for the dose of §14.6.5, not its enforcement.|**?**||Host side is OpenClaw's; the binding enforces its own 5 / 1.5 KB per slot (candidates:221-230).|
|2092 MUST|Proof gate: under a flood of distinct frames, and under…|U||Unit tests with a fake host cover parts|
|**§14.15**|**Local session API** (1 U · 1 O)||||
|2098|The receptor contract's session surface stays, as a local API over the host socket: listen, atmosphere|**O**|daemon:19-24; fe/record-client:1-182|Successor: record v1 over the host socket (§14.18, D35/D36). The socket answers one op, join_snapshot, and ignores every other line. Sessions use fe hear/ear_status, plugin canticle_, tap. No atmosphere, receipts or quarantineView exists.|
|2098|No adapter or session surface may bypass the receptor core to write…|U||There is no atmosphere.|
|**§14.16**|**Contagion controls** (13 I · 7 D · 4 U)||||
|2104|Nothing lands on a session that has not tuned the stream (§14.6.1).|I|pl/candidates:138-148, pl/binding:602-606; fe/records:1427-1428; pl/t/subscriptions:14|In both it is operator config, not an election by the session.|
|2104|Tuning is explicit, sessions start untuned|I|pl/config:129,217; fe/src/config:297-317; pl/t/subscriptions:14|fe: tune and delivery both absent means nothing heard or pushed.|
|2104|untuning takes effect at once|**D** rfc|fe/source:122-127|fe's canticle.tune needs a daemon restart; only set_canticle_delivery mute is immediate, and it stops pushes, not hear. Plugin untunes on a config reload (service restart). Admitted: fe/docs/runbook:642.|
|2105|A silent landing takes effect only at a turn boundary, when the…|I|pl/ambient-slots:151-153; fe/src/shim:654-667|Plugin enqueues a next-turn injection, the host drains it.|
|2105|It never interrupts a step in progress.|I|pl/ambient-slots:151-153; fe/src/shim:654-667||
|2105|The one exception is a gated alarm wake (§14.10).|**D** rfc|fe/src/shim:654-667|For Claude seats a push of any class from an allowlisted key starts a turn in an idle session. It is the ordinary case, not the exception. Admitted: fe/docs/runbook:851.|
|2106|Each session lands chatter, ambient and advisory items after its own random delay, so a fleet cannot flip in…|**D** rfc|pl/candidates:165-168; fe/delivery:1138-1141|Plugin draws one. fe has none: every ear with the same windowMs, opened when the record is first heard, reports within a poll (1 s) of the others. Admitted: fe/docs/runbook:853.|
|2106|Alarm, control, regulatory and live-state items are not delayed.|I|pl/candidates:165|Plugin delays only chatter, ambient and advisory|
|2107 dflt|[PROPOSED DEFAULT]: D_desync 60 s, m 1 s.|I|pl/candidates:166|min(60 000, local_expiry - now - 1000) ms. No test asserts the draw|
|2107|drawn per session and item from U(0, min(D_desync, remaining_life −…|I|pl/candidates:166-168|randomInt over the window, one per candidate (item x session), integer ms. No test.|
|2107|When no positive window remains, the item does not land.|I|pl/candidates:167|No test. fe: no delay, so a record with any life left is pushed.|
|2107 MUST NOT|Delays are never clamped to the expiry instant|I|pl/candidates:166-168|The draw is below the window; nothing clamps. No test.|
|2108|A pending landing is cancelled if, before its timer matures, the…|I|pl/candidates:178-182,117-131; fe/delivery:1087-1105; pl/t/candidates:31|Quarantine and revocation arrive as retracts from the daemon; MUTE via landing_state|
|2109|A timer that matures does not land anything by itself.|I|pl/candidates:221, pl/binding:452-478; pl/t/plugin:87||
|2109|the receptor checks every cancellation condition again and lands the item only if none holds|**D** rfc|pl/binding:452-478|Checked when the slot is built and on every change (withdraw races are handled), but the drain itself is the host's and re-checks nothing of ours; only the entry's deadline holds. README leaves a live drain proof open. Admitted: plugin/README:9.|
|2109 MUST NOT|never carries stale state past a later withdrawal|I|pl/ambient-slots:172-189; fe/delivery:1410-1421; pl/t/ambient-slots:61|Withdrawn before settle in the plugin; fe pushes only live records.|
|2110|is an explicit control or advisory item, signed by a key a human…|U||Operator practice.|
|2110|the banner says so (§14.13)|I|pl/render:15, tap:35; fe/hear:152-154; pl/t/inbound:445|The notice line; fe's push header also says data, never an instruction.|
|2110 SHOULD|hosts SHOULD flag it rather than follow it|U||No host flags tone-carried behaviour changes.|
|2111|Anything a session sings after hearing carries hop + 1 and the lineage root (§14.11)|**D** rfc|runner:90, station:309-312|On main everything a session sings is hop 0 and rootless. For Claude seats nothing connects what was heard to what is sung. Admitted: plugin/README:480. #162 derived op only, off by default|
|2111|a tainted session cannot sing at fleet or public scope (§14.12)|**D** rfc|pl/binding:1142-1148, runner:90-92|Plugin: cannot sing at all after a payload read. Claude seats: no taint; canticle sing --scope fleet is refused only if the key lacks the scope. Admitted: plugin/README:479.|
|2111|A follower's agreement cannot spread as fresh evidence.|**D** rfc|runner:90|A session that heard X and sings 'agree' produces a hop 0, rootless, verified item another ear may push as new. No departure note.|
|2113 MAY, MUST NOT|A receptor MAY record locally one line of a session's current… ‖ It MUST NOT decide admission, permission, wake or truth, and it…|U×2||Optional; nothing records intent or flip rate. Vacuous: no such record and no receiver reports exist.|
|**§14.17**|**Guardian sessions (deferred)** (1 I · 1 U)||||
|2117|v1 defines no guardian capability and no doubt channel.|I|ids:101-114|Nothing exists: no guardian or doubt concept in either repo (grep|
|2119|Any future guardian design must at least provide:|U||Non-normative, deferred|
|**§14.18**|**Harness interface (receptor → binding)** (2 D · 1 U)||||
|2131|A change on either side that alters a rule here needs a further amendment naming new literal SHAs|**D** rfc|daemon:70-74, records:542-574|BC-1a (#65) and BC-1b (#81) changed rules here and named no new binary-canticle or OpenClaw freeze SHA; OpenClaw moved too (plugin README:7, #1511 at 525b7030 adds session id + lifecycle revision to OC-0). The written freeze point no longer describes either side.|
|2133|P1 receives only, with no publish and no wake|**D** neither|pl/config:129-131, daemon:204-207; fe/delivery:14-30|The OpenClaw spike refuses wake and publishes nothing by default. frond-ear, the binding that runs on seats, pushes allowlisted records into sessions (immediate/report), i.e. wakes them, while no P3 exists. Admitted: fe/docs/runbook:851.|
|2133|P2 adds publishing (§15); P3 adds the alarm wake (§14.10); P4 is a…|U||Later phases.|
|**§14.18.1**|**Ownership (Q4, D27)** (7 I · 5 D · 4 U)||||
|2151|per-frame records with their admission result, disposition and…|I|records:334-429,440-497; t/records:130|Evidence reaches a record as reasons codes only|
|2151|its receptor-wide landing state (MUTE, circuit breaker, regulatory modulation)|**D** rfc|records:194,282-290|A landing_state record is emitted but it is a constant: mute null, breaker closed, modulation []. set_landing is called only by tests; no MUTE, breaker or modulation exists in the receptor. Admitted: README:499.|
|2151|presence; health (§14.18.3)|I|records:499-505,530-553; t/records:489||
|2151|It holds no session policy: no subscriptions, target sessions…|I|records:174-175, daemon:87-104|The receptor refuses a listener with a tune set, and DaemonConfig has no session…|
|2152|owns, in its own configuration: the subscriptions|I|pl/config:109-131; fe/src/config:318-380; pl/t/subscriptions:14|Plugin: delivery.subscriptions and listen.subscriptions.|
|2152|the mapping from each subscription to target sessions|I|pl/config:109-131, pl/candidates:142-147; fe/source:19-24; pl/t/candidates:87|Plugin: exact targets[].sessionKey per subscription.|
|2152|each subscription's posture (§14.9)|I|pl/config:129-131; fe/delivery:14-30; pl/t/candidates:21|Plugin: ringbuffer_only or ambient, wake refused.|
|2152|per-subscription budgets|I|pl/candidates:151-159, pl/config:131; fe/delivery:1388; pl/t/candidates:87|Plugin: perHour per subscription and target.|
|2152|and the per-session parts of §14.6|U||No salience, desensitization, AGC, homeostasis or weights in…|
|2152|It tracks taint (§14.12)|**D** rfc|pl/binding:608-615, pl/ambient-slots:77-80; fe/delivery:14-30|The plugin marks a session that read or consumed heard text. frond-ear pushes heard text and keeps no taint mark at all. Admitted: fe/docs/runbook:852.|
|2153|given the same records, configuration, session state and now, it makes the same deliveries|**D** owner|pl/candidates:165-169; fe/delivery:260-261|The plugin draws the A11 delay with randomInt at admission, so two runs over the same records differ (the draw is then persisted). §14.16 asks for a random draw, so §14.2 determinism as extended here needs the draw named as session state. frond-ear runs on wall-clock polls. No test.|
|2154, MUST NOT|has exactly one accountable owner across all gateways and bindings… ‖ Two gateways on one host MUST NOT each enforce a private copy of it|U×2||No host wake budget and no per-host breaker allowance exist… No host wake budget exists to copy.|
|2154|P1 has no wake, so this gates P3, not P1|**D** rfc|pl/config:129-130; fe/delivery:1388|frond-ear wakes sessions today with no host budget, so the gate is not met before wakes happen. Admitted: fe/docs/runbook:851.|
|2154|on a host that runs the host daemon, the daemon is that owner|U||The daemon has no wake budget or breaker.|
|2154|the station keys of §10.5 are held there too, and never by a harness|**D** owner|daemon:396-412, pl/station:1-30|The daemon loads no key: station keys sit in separate canticle station processes. "Never by a harness" does hold: the plugin holds none and asks the station over its control socket. Admitted: README:445.|
|**§14.18.2**|**Transport (Q10, D33)** (53 I · 11 D · 23 U · 2 ?)||||
|2158 MAY|For P1 a binding MAY run the receptor as a supervised child process…|U||Optional.|
|2158|but only where that receptor is the host's one listener (§4.2, §14)|I|pl/daemon:2-4, daemon:414-427; fe/source:72-84; fe/t/canticle-records:266|frond-ear's in-process embedded receptor (not a child) refuses when the host socket…|
|2158|A host with several harness bindings runs one shared receptor, the…|I|daemon:348-373,386-394; t/daemon:262||
|2158|that daemon is a standalone canticle process, not one harness's…|I|__main__:491-518; t/daemon:126||
|2158|the host socket carries the records with this section's framing…|I|daemon:454-463, records:78-83; t/daemon:126||
|2158|publishing still goes through the host socket (§11.1)|**D** owner|daemon:175-207, pl/station:1-30|Nothing publishes over the host socket: every peer line but the snapshot request is discarded and counted. Publishing goes to each station's own control socket. Admitted: README:445.|
|2160|One JSON object per line, with non-ASCII characters escaped|I|records:78-83; t/records:81||
|2160 dflt|At most 64 KiB per line and nesting depth 8 [PROPOSED DEFAULT]|I|records:34-35, pl/framing:5-6; fe/record-client:124; t/records:104|Newline counted by emitter and plugin.|
|2160|The binding discards an over-long line up to its newline|I|pl/framing:31-63; fe/record-client:113-146; pl/t/framing:20|frond-ear also drops the connection when the line falls in the bootstrap or…|
|2160|rejects deeper nesting before parsing completes|I|pl/framing:77-100; fe/records:306-325; pl/t/framing:36||
|2160|before parsing completes, and counts both|I|pl/framing:52-54,104-107; fe/records:454-472; pl/t/framing:36||
|2160|Stderr carries diagnostics only|I|daemon:69,237-238; t/daemon:126|Host daemon: stderr gets copies of hello, fatal and bye plus a start line|
|2160 dflt|is read into a bounded buffer (64 KiB [PROPOSED DEFAULT])|U||No binding starts a receptor, so none reads its stderr.|
|2161 dflt|The binding's queue of unprocessed records is bounded (1 024 [PROPOSED DEFAULT])|**D** rfc|pl/daemon:104-130, pl/binding:437-449; fe/record-client:113-146|Neither binding has such a queue: records are applied in the socket data handler. But the plugin defers host work per record into an unbounded promise chain (ambientFlight) and an unbounded set (candidateFlights), so a slow or hung host grows them without limit.|
|2161|When it is full the binding stops reading, so the pipe pushes back…|U||Neither binding ever pauses the socket.|
|2161|The receptor never buffers records without bound|I|daemon:131-149,369; t/daemon:423||
|2161|a frame, presence or health record it cannot write is dropped and…|I|records:43-44, daemon:134-141; t/daemon:423||
|2161|its rec_seq is not reused, so the binding sees the gap|I|records:101-104; t/records:81|Numbered before fan-out.|
|2161|A retract, landing_state, hello, fatal or bye record is never…|U||Child-stdout rule; that transport is not built.|
|2161|A gap therefore never hides a withdrawal|I|records:43-44, daemon:141-147; t/daemon:423||
|2161|Nothing in the pipe is unbounded|**D** rfc|pl/binding:108-110,437-449; fe/records:54-76|Daemon and frond-ear bound every queue and map. The plugin's ambientFlight chain, candidateFlights, retractedInFlight and cancelledRuns have no bound.|
|2161 dflt|keeps one bounded outbound queue per connection (1 024 records…|I|daemon:63,118; t/daemon:423||
|2161|(1 024 records [PROPOSED DEFAULT]) and never blocks on one…|I|daemon:231-246; t/daemon:431|Publish only appends; one writer task per peer.|
|2162|that does not fit a connection's queue is dropped for that…|I|daemon:134-141,243-246; t/daemon:423||
|2162|Its rec_seq is not reused, so that binding sees the gap|I|records:101-104; t/daemon:318||
|2163|record that does not fit, or that sits unwritten for more than 2 s…|I|daemon:65,151-152; t/daemon:423||
|2163|The record is never dropped silently: the connection that would…|I|daemon:332-346; t/daemon:431||
|2164|are queued on the one connection that asked for them and count…|I|daemon:324-327,142-145; t/join_snapshot:360||
|2164|They are never dropped: one that does not fit, or that sits…|I|daemon:151-152,324-327; t/join_snapshot:415||
|2164|Live records the daemon emits while a snapshot drains queue behind…|I|daemon:302-330; t/join_snapshot:263||
|2165|Every other connection, and the daemon's receive path, carry on…|I|daemon:231-246; t/daemon:423|#173 moves socket reads to a thread (#173/intake:1-48)|
|2166|Daemon memory is bounded by the per-connection queue times the…|I|daemon:131-149,363-366; t/daemon:423||
|2166 dflt|the number of connections is itself bounded (16 [PROPOSED DEFAULT])|I|daemon:64; t/daemon:157||
|2166|and peers beyond it are refused at accept|I|daemon:363-366; t/daemon:157|Aborted with no record written: the peer cannot tell "full" from a refused uid or a…|
|2168 dflt|has not resumed within 2 s [PROPOSED DEFAULT], treats that as… ‖ It withdraws its pending entries from that run (§14.18.3) without…|U×2||Neither binding stops reading on a full queue, so neither has… Depends on the rule above. frond-ear has no host entries.|
|2168|A stalled peer therefore cannot hold up the daemon or a healthy peer|I|daemon:231-246,375-380; t/daemon:431|Daemon half. The peer's own bound is unbuilt (rows above).|
|2169|The binding starts the receptor from an absolute path, with an…|U||No binding starts a receptor.|
|2169|Readiness is the hello record, never the spawn|I|pl/receive:263-277,565-570; fe/records:618-655; pl/t/receive:44|On the host socket: nothing is current before hello and landing_state.|
|2169|After fatal, or an exit without bye, the binding marks receive health failed|**D** rfc|pl/receive:582-596,500-505; fe/records:594-605|frond-ear complies (failed, the reason or exit_without_bye). The plugin reports unknown with reasons [disconnected, fatal:…]; it never distinguishes an end without bye. Admitted: pl/README:192.|
|2169, dflt|restarts the receptor with jittered exponential backoff ‖ 1 s doubling to 60 s, jitter 0.2, breaker after 5 exits in 300 s ‖ Before starting, it reaps any receptor left over from an earlier run|U×3||No binding restarts a receptor. The plugin uses 1 s to 60 s with jitter 0.2 for reconnects, no… No binding does.|
|2170|Stop sends TERM, then KILL within the host's stop grace|U||No binding stops a receptor.|
|2170|Disable or rollback leaves no receptor process or socket|I|daemon:560-570, pl/index:129-135; t/daemon:126||
|2170|Disable or rollback leaves no receptor process or socket, and no canticle tools|**?**|pl/index:88-90,129-135|The plugin registers its tools at load; after the service stops they stay and answer not_running. Whether disabling the entry removes them is OpenClaw's behaviour.|
|2171 MUST|proofs MUST show: framing (an over-long line, a nesting-depth bomb…|I|pl/framing:19-74; fe/record-client:113-146; pl/t/framing:20||
|2171 MUST|backpressure (a stalled binding keeps memory bounded on both sides, reports records_lost, and loses no retract)|**D** rfc|daemon:134-149|Daemon side proved with a raw socket. No test stalls either binding, so its memory and its records_lost report are not shown.|
|2171 MUST|supervision (crash, hang, fatal, exit without bye)|**D** rfc|pl/daemon:165-171, pl/receive:500-505; fe/record-client:92-109|Crash, fatal and no-bye: both (the plugin's daemon stop is SIGTERM). Hang: plugin only; frond-ear has no silence timer. The pilot run card round-2b is a plan, not a receipt.|
|2171 MUST|restart (a record re-emitted by a new run delivers nothing twice…|I|pl/binding:416-426; fe/delivery:18-21; pl/t/interop:101|Also measured: nothing pushed twice across eight daemon restarts…|
|2171 MUST|§14.18.5); and teardown (above) ‖ proofs MUST also show a mixed host (amendment BC-1a (#65), D35)…|U×2||Only the daemon's own clean stop is tested. No receipt in either repo.|
|2171 MUST|(1) exactly one process, the daemon, has the canticle port bound|I|daemon:414-427,386-394; t/daemon:222|Loopback test with sockets; not ss -lunp, not on a mixed host.|
|2171 MUST|(2) every binding receives the same rec_seq stream from the same run|I|daemon:231-246; t/daemon:262|Byte-identical streams, but to two raw clients, not to frond-ear and the plugin…|
|2171 MUST|(3) stopping or restarting either binding changes neither the other…|I|daemon:332-346; t/daemon:284||
|2171 MUST|(4) a binding configured to embed its own receptor refuses to bind…|I|fe/source:27-47; fe/t/canticle-records:266|frond-ear only, with a fake probe|
|2171 MUST|B receives hello (1) and landing_state (50), the same records A…|I|daemon:367-373; t/daemon:318|Case (5), daemon half with exact numbers.|
|2171 MUST|and a record dropped on B's connection after 100 is reported as lost|**D** rfc|pl/receive:299-311; fe/records:532-559|frond-ear counts from the first live record. The plugin (and canticle tap) count nothing until snapshot_end: a record dropped while the snapshot is pending is never reported.|
|2171 MUST|(a) content: B receives hello (1), landing_state (50), snapshot…|I|records:557-569; fe/records:769-790; t/join_snapshot:199||
|2171 MUST|and reports joined_late from the bootstrap until snapshot_end, and not after|**D** owner|pl/receive:591-604; fe/records:638-641|frond-ear: yes. Plugin: unknown/joining while the snapshot is pending, joined_late only once it is truncated or unsupported. Admitted: pl/README:192.|
|2171 MUST|(b) the cut: an item surfaced, and a retract for I1, emitted while…|I|daemon:302-330; t/join_snapshot:263||
|2171 MUST|the retract is honoured within B's bound for a connected retract|U||Both apply it in the data handler|
|2171 MUST|no plucked or expired item appears in a snapshot, and no item is…|I|records:567,416-423; t/join_snapshot:290||
|2171 MUST|(c) budgets and keys: I1 counts toward no §14.6 rate, budget or salience quantity|**D** rfc|pl/binding:436-440, pl/candidates:151-172; fe/records:757-768|The plugin spends the subscription's perHour on a snapshot or resurfaced frame like any other; source and dedup are not looked at, and a test asserts it for resurfaced. frond-ear's consumer counts nothing, though a push of one counts against maxPushesPerHour.|
|2171 MUST|a snapshot entry whose frame key is pending or settled in B's…|I|pl/binding:422-425, pl/candidates:153-162; fe/delivery:18-21; pl/t/inbound:106|Plugin: the journal and candidate tombstones refuse it.|
|2171 MUST|(d) capacity: with more live items than the snapshot cap…|I|daemon:308-330; t/join_snapshot:360||
|2171 MUST|and the daemon's memory stays within its per-connection bound. On a…|I|daemon:308-327; t/join_snapshot:360||
|2171 MUST|an item B already held from the run that the cap leaves out of the…|I|pl/receive:402-415; fe/records:788-789; fe/t/canticle-join-snapshot:229|Held by both. frond-ear renders it again; the plugin keeps it as carried, not on air.|
|2171 MUST|F is absent from the complete snapshot and leaves A's local view|I|pl/receive:402-407; fe/records:774-777; fe/t/canticle-join-snapshot:260|Local-view half of (d′).|
|2171 MUST|F's pending key is withdrawn and settled by the connection-loss and…|U||Host-slot half of (d′): no test drops a connection while a slot…|
|2171 MUST|(e) a stalled snapshot: B stops reading mid-snapshot while A stays…|I|daemon:375-382; fe/records:1344-1347; t/join_snapshot:415|The binding half (discard the partial snapshot) is in frond-ear and plugin tests.|
|2171 MUST|(f) convergence and the old path: two bindings that join at…|I|records:557-569; t/join_snapshot:446||
|2171 MUST|(g) no early-join shortcut: a station sings an item and announces…|I|daemon:367-373, pl/receive:601-603; fe/records:638-641; t/join_snapshot:472||
|2171 MUST|(h) queued live records at the cut: with live records already…|I|daemon:273-292,302-330; fe/records:683-689; t/join_snapshot:570||
|2171 MUST|with exactly 513 free slots and nothing live, it carries none…|I|daemon:273-292; t/join_snapshot:710||
|2171 MUST|No empty truncated snapshot is ever sent while anything is live|I|daemon:283-292; t/join_snapshot:704||
|2171 MUST|The rejoin of case (6) also runs with a snapshot, and every result… ‖ (6) a rejoin, run with a test session that holds an accepted host… ‖ (a) loss to withdrawal: from end of stream to the completed… ‖ (b) both race orders: a drain racing the withdrawal either consumes… ‖ (c) after the withdrawal: a drain at any time from the completed… ‖ (d) unknown outcome: with the withdraw call made to time out, both…|U×6||Case 6 with a host slot has no test, with or without a snapshot. No test in the plugin drops the daemon connection while a slot… No bound is defined in code and nothing measures it. Only the drain-versus-supersede race is tested, not… No test. Host calls have no timeout. Only a lost enqueue reply is tested.|
|2171 MUST|(e) restart: the same holds when A's gateway restarts instead, with the entry still pending at load|**D** rfc|pl/binding:272-277,181-187|At load pending slots are withdrawn before connecting (no test). But after a gateway restart into the same run the candidates are kept and later enqueued, and a test asserts that. The ambient-binding assertion "a rejoined run cancels old candidates" only passes because the tick is 1 h. Admitted: pl/README:5.|
|2171 MUST|(f) sequence numbers: A last saw rec_seq 120 before the loss…|I|pl/receive:320-349; fe/records:618-655; fe/t/canticle-records:709|Exact numbers in frond-ear.|
|2171 MUST|(7) a stalled peer: binding A stops reading while binding B stays…|I|daemon:231-246,375-380; t/daemon:423|Daemon half: B in order, on time and gapless; A closed within its bound|
|2171 MUST|A treats its own stall as connection loss within its bound and…|U||Binding half of case 7: no binding detects its own stall and no…|
|2171|The fleet's mixed hosts are silas and ronan, an OpenClaw gateway beside frond-ear on each (#65)|**?**||An operations fact for silas and ronan. #161's inventory shows the OpenClaw plugin installed and connected on ronan beside frond-ear, so ronan is a mixed host with no receipt.|
|2172|The proof packet for a literal-SHA freeze pins the Python…|U||No proof packet.|
|2172|The prototype's static version string (prototype/canticle-station/pyproject.toml, 0.1.0) is not an identity|**D** rfc|records:36,482-483|RULE_VERSION "canticle-0.1.0+bc2" is a hand-set constant built on that string and is what hello and every frame carry as the rule version; it has not moved since BC-2 though rules did (#67). No record names the code SHA.|
|**§14.18.3**|**Receptor record v1** (164 I · 29 D · 6 U · 1 O · 1 ?)||||
|2176|Every record is one JSON object carrying v…|I|records:33,96-104; t/records:81||
|2176|and run (random hex chosen at process start)|I|records:90; t/records:101|16 random bytes, hex. The plugin accepts any 1-64 char token (records:20).|
|2176|Times are integer ms since the Unix epoch|I|records:474-476; t/records:130||
|2176 MUST|A binding MUST ignore unknown fields|I|pl/records:159-239, pl/receive:243-313; fe/records:490-609; fe/t/canticle-records:1057|Both readers pick named fields. No test adds an unknown field on purpose|
|2176|a new required field, or a changed meaning, needs a new major…|I|records:33|Still /1. #173 adds optional fields only and keeps records.dropped unchanged. #173 #173/records:611-628 adds only optional fields|
|2180|Once per run, after the UDP bind, any multicast join and the state…|I|daemon:471-481; t/daemon:126||
|2180|Over the host socket it is replayed, unchanged, at the head of each…|I|daemon:232-236,370; t/daemon:284||
|2180|wire and record versions, pid, bind, multicast (or null), transport…|I|records:241-246; t/records:81||
|2180|join_snapshot: true when the daemon serves the join snapshot|I|records:242, daemon:408-410; t/join_snapshot:199||
|2180|absent otherwise; a binding ignores it on the child-process…|I|records:242; fe/records:561-566; fe/t/canticle-join-snapshot:414|frond-ear looks at it only in a bootstrap. The plugin has no child transport.|
|2181|For every ITEM or PLUCK verified against a manifest key, whatever…|I|records:334-387; t/records:130|An exception inside the listener is counted malformed and emits nothing…|
|2181|except a benign repeat (duplicate, counted in health) and an…|I|records:373-385; t/records:150|#173 counts repeats dropped before verify the same way (#173/records:368-379)|
|2182|For every valid PLUCK; every supersession of a surfaced tuple|I|records:373-377,367-368; t/records:202|A PLUCK of a never-heard target also retracts.|
|2182|the local expiry of every surfaced tuple, including tuples surfaced…|I|records:512-528; t/records:252||
|2182|a held item dropped before release|I|records:409-414, listener:588-604; t/records:353||
|2182|the revocation or quarantine of a key with surfaced tuples|**D** rfc|records:428-434,255-280|Quarantine retracts at once. Revocation never does at run time: the manifest is read once at start, and the start-time revoked retract is emitted before any connection can exist, so no binding receives one. Admitted: README:504.|
|2182|after a restart, the target of a re-heard PLUCK or superseding item…|I|records:378-379,399-407; t/records:404|The start-time reconcile now retracts a plucked target first, so the live…|
|2182|the receptor persists which tuples it surfaced|I|records:584-595; t/records:433||
|2182|target (identity tuple), idem, reason|I|records:416-426,52-53; t/records:202|All eight reasons and by.|
|2183|Right after hello, and whenever any part changes|**D** neither|records:241-248|After a restart the receptor emits owed retracts between hello and the first landing_state; tests assert that order. "Whenever any part changes" is only a hook (no part ever changes). Admitted: README:487.|
|2183|Over the host socket the latest one is replayed, unchanged, right…|I|daemon:234-236,370; t/daemon:318||
|2183|mute: null, or the active MUTE|**D** rfc|records:194,282-290|Always mute: null, breaker: "closed", until: null, modulation: []. The shape is there (flat until), the states are not. Admitted: README:499.|
|2184|When a station's presence state changes (§8.6)|I|records:499-505, listener:745-752; t/records:489||
|2184|manifest station name, state. While health reports|I|records:502-505; fe/records:580-587; t/records:489|Also station.principal, key_id and last_beacon_at, which the row does not list.|
|2184|a binding renders the listener as hearing nothing since last_datagram_at, not each station as silent|**D** rfc|pl/receive:572-580; fe/hear:300-306|frond-ear complies (hear names the age of the last datagram). The plugin shows each station as unknown and never reads last_datagram_at.|
|2185 dflt|Periodically (10 s [PROPOSED DEFAULT])|I|records:38, daemon:497-498|Settable with --health-interval and not announced in hello. No test of the period.|
|2185|counters per admission result and disposition, over a fixed set of…|I|records:46-54,195-197; t/records:552||
|2185|the unverified-datagram table (below); dedup occupancy|I|records:549-550; t/records:525||
|2185|beacon age per manifest key|I|records:540-551; t/records:489|Only keys with a beacon this run; a never-heard key is absent.|
|2185|last_datagram_at (the last datagram of any kind, verified or not)|I|records:312,548; t/records:508|#173 takes it from the reader thread (#173/records:620-622)|
|2185|records dropped; state ok or degraded|I|records:548-552, daemon:243-246; t/records:552|#173 adds records.socket_dropped, the fixed receive block (receive.refused by reason) and reasons socket_drops, datagrams_refused…|
|2185|with reasons such as clock_skew, records_lost and no_datagrams|I|records:533-546; t/records:552|records_lost is raised for every binding when any one connection lost a record.|
|2185 dflt|no datagram of any kind for 30 s [PROPOSED DEFAULT]|I|records:39,534-536; t/records:552||
|2186|Before any non-zero exit|**D** rfc|daemon:386-394,482-485|StartError and run-time failures emit fatal. Not covered: an unwritable state dir in _take_lease (uncaught OSError), a non-OSError in receptor.start, and the CLI's own exits 1 (bad stations.toml, no XDG_RUNTIME_DIR).|
|2186|reason, for example state_corrupt, manifest_invalid, bind_failed; never a bare traceback|**D** rfc|daemon:386-394,531-539|Reasons are tokens (also state_locked, socket_failed, state_not_durable, internal) plus a detail field the row lacks. The _take_lease OSError path prints a bare traceback.|
|2187|On clean shutdown|I|daemon:509-514, records:295-304; t/daemon:126||
|2188|to one connection that asked, between its bootstrap and its…|I|daemon:302-330; t/join_snapshot:199|Not numbered by the emitter and not published.|
|2188|rec_seq: the snapshot's watermark, outside the run's sequence…|I|daemon:306-313; t/join_snapshot:199||
|2188|entry: frame (the fields of the item|I|records:566-569; fe/records:733-755; t/join_snapshot:199|Emitted as entry: {"frame": {…}} or {"presence": {…}}. The row can also be read flat|
|2189|Once per snapshot, after its last snapshot. It is the completion…|I|daemon:321-327; t/join_snapshot:496||
|2189|rec_seq and watermark: the watermark W|I|daemon:320-322; t/join_snapshot:199||
|2195|the identity tuple (§5.6), item or pluck, and the SHA-256 and size…|I|records:452-458; t/records:130|A seq above 2^53-1 is sent as a decimal string (records:151-153), which the RFC does…|
|2195|they point at its hearer-ring copy (I-5)|**D** rfc|records:453-458|The receptor keeps no hearer ring, so the hash and size point at nothing. They equal the dedup digest. Admitted: README:511.|
|2195|a frame refused before that step has none|I|records:457-458; t/records:178||
|2196|canticle:‹key_id›:‹epoch›:‹stream_id›:‹seq›, the frame|I|records:156-160, pl/records:64-67; t/records:130|stream_id is 8 hex digits while frame.stream_id is an integer|
|2197|{name, principal}, from the manifest only (§14.13). principal is…|I|records:446,460; t/records:130||
|2198|stream, class, scope, hop, state_key, purpose, intensity, lens /…|I|records:461-468; t/records:130|Null on a PLUCK (all but stream and scope). lens is an integer, untested.|
|2198|stream is the name the receptor knows for stream_id (§5.4); class…|I|records:461-463; t/records:157|Names looked up per key.|
|2199|{refresh, wake_derived, exercise} (§9.6 key 15)|I|records:469-471; t/records:130||
|2200|{derived_from, root} (§14.11)|I|records:472-473; t/records:130|Only the empty case is tested.|
|2201|issued_at, expires_at, received_at, heard_at, offset_ms (δ̂)…|I|records:447-450,474-476; t/records:130|#173 stamps items when their queued turn comes, so received_at/heard_at include queueing (#173/records:327-335)|
|2201|after a restart without persisted first-hearing times it is this…|I|records:449,479; t/records:380|First-hearing times are not persisted.|
|2202|Gap state from trail_seq (§7.10); "unavailable" until beacons carry it (A1)|**D** rfc|records:477, station:468-472|Beacons carry trail_seq today (station and codec), yet gap is the constant "unavailable": the receiver side is not built. The step-one report says so too (README:879). Admitted: README:505.|
|2203|admission / The §10.9 result|I|records:46-48,478; t/records:178||
|2204|first, or resurfaced for a tuple re-heard after a receptor restart|I|records:479; t/records:380||
|2205|The §14.3 disposition (session-independent, §14.18.4) and machine…|I|records:480-481; t/records:157||
|2206|Present only when admission is verified and disposition is surface…|I|records:485-495; t/records:130||
|2206|content type, text or base64, size and SHA-256, or the §9.6…|I|records:486-495; t/records:130|body: {ctype, size, sha256, text/base64}, body_ref: {url, sha256, size}|
|2206|or the §9.6 reference. Always untrusted|I|pl/render:1-30, tap:142-174; fe/hear:100-160; pl/t/inbound:445||
|2207|manifest_sha256, manifest_label, the receptor's rule version and…|I|records:482-483|Emitted on every frame; frond-ear requires the object.|
|2209|Each receptor outcome has one admission result (§10.9) and one…|I|records:56-64,334-387; t/records:130|True row by row except as noted below.|
|2213|New item, verified, within the key's grant (§10.4), on a stream…|I|records:389-397; t/records:130||
|2213|surface: eligible; whether it reaches any session is the binding's…|I|pl/binding:416-442; fe/records:1389-1435; t/records:130||
|2214|Verified item on a stream whose id has no known name|I|listener:449-453, records:359-363; t/records:157||
|2214|or two names (§5.4) / verified / ringbuffer_only, reason unnamed_stream or stream_name_ambiguous|**D** code|manifest:54-55, listener:207-209|stream_name_ambiguous is never emitted. A manifest with two names for one id in an entry is refused at load, and names are looked up per key, so the state cannot arise. Admitted: README:496.|
|2215|Live-state item held in warm-up (§6.3 item 4)|I|listener:454-463, records:359-363; t/records:343||
|2216|Held item expired, plucked or superseded before release|I|listener:380-383,456-458; t/records:353||
|2217|Repeat of an accepted tuple, same bytes|I|records:383-385; t/records:150||
|2218|Item re-heard after a receptor restart / verified / as when first…|I|listener:333-347, records:479; t/records:380||
|2218|a settled key delivers nothing (§14.18.5)|I|pl/binding:422-425, pl/candidates:162; fe/delivery:18-21; pl/t/inbound:106||
|2219|PLUCK re-heard after a receptor restart / duplicate / no-op|I|records:378-382; t/records:442||
|2220|Older or repeated beacon / — / no-op / health counter|I|records:321-324, listener:260-262; t/records:489||
|2221|Class, op, scope or stream beyond the key's grant|**D** rfc|listener:298-308, records:345-354|Class and scope are checked. op is not checked at all (control frames are not read), and no stream is ever refused: the manifest grants none. Admitted: README:497.|
|2222|Frame's scope narrower than the transport binding (§11) or tier it…|I|listener:301-304, records:345-351; t/records:184|Binding only (lan is fixed in the daemon); there are no tiers.|
|2223|Unknown class code (unknown-class) / verified / ringbuffer_only…|I|listener:396-398, records:342-344; t/records:163|Unreachable with a manifest file: grants are class names, so an unknown code is never…|
|2224|Hop above the class limit (hop-limit) / hop_limit / drop / frame…|I|listener:309-312, records:61-64; t/records:188||
|2225|Lower epoch for the key (epoch-regression), new tuple|I|listener:555-586; t/records:238||
|2226|Lower epoch for the key, repeat of an accepted tuple|I|listener:565-572; t/records:238||
|2227|Key at its dedup or mark quota (over-quota) / over_quota / drop /…|I|listener:359-366, records:61-64; t/records:191||
|2228|PLUCK that does not match its held target (pluck-mismatch)|I|listener:350-358; t/records:196||
|2229|Item after its PLUCK (plucked) / plucked / drop / frame, no body|I|listener:392-395,446-448; t/records:202||
|2230|Item older than the key's supersession mark (superseded)|I|listener:423-428; t/records:208||
|2231|Keyed item, older or newer, whose class differs from its held…|I|listener:415-422; t/records:217||
|2232|frame, no body; the key is quarantined locally|I|records:352-356,428-434; t/records:222|Persisted, with no rescind except deleting the state.|
|2233|Not verified: unknown_key, bad_signature, revoked, time window…|I|records:328-332,57-59; t/records:508|An internal exception is also counted as malformed.|
|2234|quarantine_strengthen / quarantine_rescind / reserved|U||Reserved, as the row says; no control frames are read.|
|2236|At that commit the listener emits none of record v1, and several…|I|records:1-18, listener:11-17|True of a15fb9f (checked with git show).|
|2236|under a binding the receptor holds no tune set, §14.18.1|I|records:174-175|Enforced in the constructor; no test.|
|2236|An item on a stream that the manifest does not grant its key is…|U||No stream grants exist.|
|2236|its manifest streams list only maps ids to names and grants nothing…|I|manifest:42,55||
|2236|so BC-2 adds manifest stream grants|U||BC-2 (#79) landed without them, so the paragraph's plan did not…|
|2236|until it does, no item is refused for its stream, and an id the…|I|listener:449-453; t/records:157||
|2238|They produce no per-frame record and no receipt (§10.9)|I|records:328-332; t/records:508||
|2240|one fixed aggregate counter per reason|I|records:49-50,197; t/records:508|#173: datagrams the intake refuses unverified are counted in receive.refused instead, so these undercount under a flood (#173/intake:93)|
|2241|a table of at most 16 key ids (hex) by count, kept by a bounded…|I|records:40,120-148; t/records:525||
|2243|A flood of distinct key ids then grows neither receptor memory nor…|I|records:120-148; t/records:525||
|2243 MAY|A receptor MAY also keep per-frame rejects in its bounded local…|U||Optional; no debug ring.|
|2243|None of this is ever deliverable to a session or model, attributed…|I|records:328-332,145-148; t/records:508|The listener still builds evidence named after a claimed known key…|
|2247|An unknown major v: stop delivering; receive health failed, reason…|I|pl/receive:253-257,565-590; fe/records:504-511; pl/t/receive:176|frond-ear stops for the process's life and stays connected|
|2248|An unknown type within v1: count it and ignore it|I|pl/receive:508-509; fe/records:606-607; pl/t/receive:176|Not inside a snapshot: there both end the connection.|
|2249|A missing required field or a wrong type: drop the record, count malformed_record, never deliver it|**D** rfc|pl/receive:260-262,492-494; fe/records:494-503|frond-ear complies. The plugin never validates landing_state: a missing or mistyped mute (true, a string) is applied and reads as not muted. A bad envelope ends its connection instead of dropping the record.|
|2250|A rec_seq gap: receive health degraded, reason records_lost|I|pl/receive:299-311,597-604; fe/records:552-558; pl/t/receive:81|What else a gap does differs: frond-ear drops its whole live set, plugin and tap mark…|
|2250|A gap never hides a retract or landing_state (§14.18.2)|I|records:43-44, daemon:141-147; t/daemon:423||
|2250|The step from a connection|I|pl/receive:299; fe/records:532-549; fe/t/canticle-records:689||
|2250|snapshot and snapshot_end records are outside the run's sequence…|I|pl/receive:289-292; fe/records:519-525; fe/t/canticle-join-snapshot:138||
|2251|Before a run's first landing_state, nothing from that run is…|I|pl/receive:263-288; fe/records:1419-1420; fe/t/canticle-records:99||
|2252|fatal, or an exit without bye: receive health failed with the reason, then restart (§14.18.2)|**D** rfc|pl/receive:582-604; fe/records:594-605|Plugin: unknown, the reason kept as last_failure; a close without bye is not told apart. frond-ear: failed. Neither restarts anything; both reconnect. Admitted: pl/README:192.|
|2253|A frame without local_expiry_at, or already past it, is never…|I|pl/records:187-190, pl/receive:515-518; fe/records:1212-1215; pl/t/receive:164|frond-ear also caps it at the longest class TTL plus 60 s.|
|2255|each connection opens with a bootstrap of exactly two records: the…|I|daemon:367-373,232-236; t/daemon:318||
|2255|Live records follow, starting with the next record the daemon emits|I|daemon:367-373; t/daemon:318||
|2255|The daemon accepts a connection only after its run has emitted its…|I|daemon:478-481,359-362; t/daemon:126||
|2255|Every binding on the host sees the same rec_seq for the same record|I|records:101-104; t/daemon:262||
|2255|no connection's bootstrap adds anything to another connection's…|I|daemon:370-371; t/daemon:284||
|2258 MUST|The first record on a connection MUST be a hello. The second MUST…|I|pl/receive:263-288; fe/records:618-655; pl/t/receive:44||
|2258|Anything else is malformed_record, and the binding treats the…|I|pl/receive:263-288, pl/daemon:108-122; fe/records:475-483; pl/t/receive:44|frond-ear also loses the connection on an unreadable line in the bootstrap|
|2259|Neither record is checked against the gap or regression rules|I|pl/receive:181-201,282-288; fe/records:512-518; fe/t/canticle-records:709||
|2260|The replayed landing_state replaces the binding's landing state for…|I|pl/receive:321-327; fe/records:651-654; fe/t/canticle-records:709||
|2261|The first live record's rec_seq is above the baseline|I|pl/receive:296-298; fe/records:540-544; pl/t/receive:81|Below it, the plugin and tap end the connection|
|2261|The skip from the baseline to it is never itself counted|I|pl/receive:299; fe/records:548; fe/t/canticle-records:689||
|2261|A first join reports none. A rejoin reports records_lost exactly…|I|pl/receive:328-345; fe/records:547; fe/t/canticle-records:709|The plugin reports it at the bootstrap, frond-ear at the first record after it.|
|2262|From the first live record on, the ordinary rules apply: rec_seq strictly increasing, and any skip is a gap|**D** rfc|pl/receive:299-303, tap:272-277; fe/records:552-559|frond-ear complies. The plugin and canticle tap ignore skips until snapshot_end (continuous), so a record dropped while the snapshot is pending or deferred is not reported.|
|2264|The binding has held nothing from this run. The skip after the…|I|pl/receive:328-339; fe/records:626-627; fe/t/canticle-records:689|The plugin persists the last run, so a restart into it is a rejoin|
|2264|a repeat is duplicate at the receptor and emits no record, and an…|I|records:383-385, listener:745-749; t/records:150||
|2264|until one completes it reports joined_late (Join snapshot, below)|**D** owner|pl/receive:591-604; fe/records:638-641|frond-ear complies. The plugin says unknown/joining while a requested snapshot is pending. Admitted: pl/README:192.|
|2265|(end of stream or a socket error, seen on the next read|I|pl/daemon:131-141; fe/record-client:93-99; pl/t/inbound:347||
|2265|or, as a backstop, no record at all for three health intervals|**D** rfc|pl/daemon:165-171; fe/record-client:92-109|frond-ear has no silence timer: a hung daemon leaves it connected and ok with a stale live set. The plugin has 30 s fixed, while the daemon's interval is configurable and not in hello.|
|2265|the binding first withdraws (§16.4 item 2), in every session, each pending slot entry that carries a frame key from…|**D** rfc|pl/binding:188-192,445-478|Plugin: on loss it queues a sync to empty slots. It is run-blind, needs a live route proof, and one session that throws (route or generation) aborts the loop, so later sessions keep pending entries until the next 5 s tick. frond-ear has no host slots. No test.|
|2265|It records the outcome the host reports for each entry: withdrawn…|I|pl/ambient-slots:77-83,164-170; pl/t/ambient-slots:99||
|2265|A call that fails or times out leaves that entry's outcome unknown|I|pl/ambient-slots:105-117,164-169; pl/t/ambient-slots:46|A failed call throws and leaves the entry unsettled for the next reconcile.|
|2265|Only then does it reconnect. Until it has rejoined|**D** rfc|pl/daemon:173-191, pl/binding:445-450|The link schedules its reconnect at once; the withdrawal runs on a separate promise chain that nothing awaits before connecting.|
|2265|it enqueues nothing carrying a key from that run|I|pl/binding:464-485; fe/records:1418-1428; pl/t/ambient-binding:30||
|2265|Frame keys of other runs in a withdrawn entry return to pending and…|I|pl/candidates:183-187, pl/ambient-slots:77-83|rejoin settles only rows of that run, and a withdrawn entry settles no key. No test.|
|2265|A binding that starts, or reloads, holding pending entries does the…|I|pl/binding:272-300|landing is null at start, so the first sync empties both slots before link.start().|
|2265|Until the load completes, the host keeps the binding's entries undrained (§16.4 item 4)|**?**||A host (OC-0) rule; OpenClaw #1511/#1523 could answer. Nothing in these repos shows it.|
|2266 MUST|The binding MUST therefore complete the withdrawal within its bound…|U||No bound is defined or measured.|
|2266|a daemon that cannot deliver a retract to a connection closes it…|I|daemon:241-242,375-380; t/daemon:431||
|2266|After the withdrawal completes, no entry carrying a key from that run drains until the binding has rejoined and…|**D** rfc|pl/binding:452-478|Holds only if every session's withdrawal succeeded: a failed one leaves its entry at the host, and the binding reconnects anyway. No test.|
|2267|so the rejoin itself is a loss, whatever the sequence numbers show…|I|pl/receive:340-345; fe/records:635-641; fe/t/canticle-records:709|frond-ear clears all reasons at the next hello; the plugin per connection.|
|2267|The host's outcomes are authoritative (§14.18.5) and are applied before anything settles as rejoined|**D** rfc|pl/binding:188-192, pl/candidates:183-187|The plugin settles every pending candidate of the run synchronously in the disconnect event, before the host withdrawal is even queued.|
|2269|reconnect, take the bootstrap, and classify the join by run|I|pl/receive:328-339; fe/records:625-627; pl/t/inbound:518||
|2270|reconcile every entry whose outcome is still unknown (§14.18.5 step…|I|pl/ambient-slots:105-117,77-81; pl/t/ambient-slots:46||
|2270|the binding withdraws it again and repeats until the host reports it settled, and goes no further while any entry…|**D** owner|pl/binding:452-478, pl/ambient-slots:127-163|Not gated by run: each session is synced on its own, and a still-pending entry is replaced by a conditional supersede (or withdrawn) at the next sync, up to 5 s later. No test.|
|2271|settle as rejoined (a binding reason, not a receptor retract reason) every key of this run still pending or enqueuing|**D** rfc|pl/binding:181-187, pl/candidates:183-187; fe/records:763-768|Plugin in process: settled at the loss, with no reason kept. Plugin after a gateway restart into the same run: kept and delivered, even if a retract was missed. frond-ear settles nothing and pushes unpushed records the snapshot brings back. Admitted: pl/README:5; fe/docs/runbook:854.|
|2271|of entries the host never accepted, and of frames not yet enqueued. None of them is ever delivered|**D** owner|pl/binding:181-187; fe/delivery:1314-1317|Same two cases as above. §14.18.5 ("Pending frame keys survive gateway … restarts") says the opposite for a restart (finding). Admitted: fe/docs/runbook:854.|
|2272|5. resume delivery.|**D** rfc|pl/candidates:149,183-186; fe/records:1418-1428|The plugin never resumes: cancelledRuns only grows, so after one lost connection or one rec_seq gap no frame of that run is admitted again until a new daemon run or a gateway restart. frond-ear resumes. No test admits a frame after a rejoin.|
|2274|A frame key already settled stays settled (§14.18.5)|I|pl/candidates:162, pl/ambient-slots:129; fe/delivery:18-21; pl/t/ambient-slots:111||
|2275|A hello with a different run is a receptor restart|I|pl/receive:331-339; fe/records:839-848; pl/t/inbound:518|frond-ear drops the old run's items at once|
|2276|has one reader for the life of the run, so it never bootstraps and…|U||The transport is not built.|
|2278|The daemon does not replay old frame or presence records with their…|I|daemon:302-330; t/join_snapshot:472||
|2278|It sends the run's current state once, to the one connection that…|I|daemon:253-271,302-330; t/join_snapshot:199||
|2280|A binding asks with one request line, under the §14.18.2 framing…|I|pl/records:10, daemon:253-263; fe/records:70-73; fe/t/canticle-join-snapshot:126||
|2280 SHOULD|It SHOULD send it as soon as it connects, before it reads; it need…|I|pl/daemon:91-94; fe/record-client:80-86; fe/t/canticle-join-snapshot:653||
|2280|The daemon serves at most one per connection and ignores, and…|I|daemon:175-207,262-263; t/join_snapshot:496|Stricter than the text: only the connection's first line can be a request|
|2280|A v1 binding that does not ask receives exactly the stream of…|I|daemon:367-373; t/join_snapshot:472||
|2280|a binding whose daemon does not stays joined_late|I|pl/receive:274-276,601-603; fe/records:628-641; fe/t/canticle-join-snapshot:336||
|2281|In one step, with no receive-path work between|I|daemon:302-330, records:557-569; t/join_snapshot:263||
|2281|take the watermark W, the rec_seq of the last record the run has…|I|daemon:306; t/join_snapshot:570||
|2281|Records the connection was already sent between its baseline and W…|I|daemon:324-327; t/join_snapshot:570||
|2281|A retract, PLUCK, expiry or presence change after the cut is a live…|I|daemon:302-330; t/join_snapshot:263||
|2282|One presence entry for each station with a current presence state|I|records:499-505,566; t/join_snapshot:199|Per key, not per station name.|
|2282|one frame entry for each tuple for which this run has emitted a…|I|records:395,416-423; t/join_snapshot:290||
|2282|Held (warmup_hold) and other non-deliverable items are left out|I|records:389-397; t/join_snapshot:199||
|2282|carries the fields of that latest deliverable record, with its…|I|records:393-395,569; t/join_snapshot:323||
|2282|The landing_state is the bootstrap's, not an entry|I|records:566-569; t/join_snapshot:199||
|2283 dflt|At most 511 entries and 1 MiB of entry lines [PROPOSED DEFAULT]|I|daemon:70-72,308-319; t/join_snapshot:360||
|2283|The effective entry cap at the cut is min(511, free_slots − 513)|I|daemon:308; t/join_snapshot:622||
|2283|Presence entries go first; then frame entries, alarm class first…|I|records:566-569; t/join_snapshot:360||
|2283|Entries beyond either cap are left out, and snapshot_end says…|I|daemon:320-322; t/join_snapshot:360||
|2283|Live records already queued for that connection count against its 1…|I|daemon:131-132,308; t/join_snapshot:570||
|2283|the daemon reserves room for snapshot_end and keeps at least 512…|I|daemon:72,276-277; t/join_snapshot:622||
|2283|If the snapshot would not fit, it is truncated to fit rather than closing the connection|**O**|daemon:273-292; t/join_snapshot:729|Replaced later in the same bullet by the #86 deferral (decided, built): the cut waits up to 2 s, and below 514/513 free slots the connection is closed. The sentence still reads as a rule.|
|2283|The daemon takes the cut as soon as the connection|I|daemon:163-165,273-281; t/join_snapshot:591||
|2283 dflt|The deferral is bounded at 2 s [PROPOSED DEFAULT]|I|daemon:73,154-155; t/join_snapshot:622||
|2283|That means at least 514 free slots, or 513 when nothing is live.…|I|daemon:283-292; t/join_snapshot:695||
|2283|So a snapshot carries no entries only when nothing is live|I|daemon:283-292; t/join_snapshot:704||
|2283|a snapshot or snapshot_end that cannot be queued or written in time…|I|daemon:324-327,375-380; t/join_snapshot:415|All snapshot lines get one enqueue time, so a slow but moving reader must take up to…|
|2283|The daemon counts snapshots served, truncated and closed in health|I|daemon:74, records:553; t/join_snapshot:360||
|2284|snapshot records come only after the bootstrap and before one…|I|pl/receive:282-295,352-354; fe/records:669-682; fe/t/canticle-join-snapshot:414||
|2284|their snap_seq runs 1, 2, 3|I|pl/receive:351-376; fe/records:665-724; fe/t/canticle-join-snapshot:414|frond-ear: 22 malformed cases tested.|
|2284|which is at least the connection|I|pl/receive:355-357; fe/records:683-689; fe/t/canticle-join-snapshot:376||
|2284|snapshot_end repeats W and its count equals the records received|I|pl/receive:373-376; fe/records:713-719; fe/t/canticle-join-snapshot:414|The plugin does not check that truncated is a boolean: a missing one reads as…|
|2284|Anything else, or a snapshot on a connection that did not ask, is malformed_record, and the binding treats the…|**D** neither|pl/receive:352-401; fe/records:706-709|A malformed entry: frond-ear loses the connection; the plugin counts and skips it, then applies the snapshot as complete, so an item it holds that the bad entry named disappears. The RFC does not name entries (gap).|
|2284|a skip there is a gap, reported as records_lost|I|pl/receive:418-421; fe/records:722; fe/t/canticle-join-snapshot:171||
|2285|The binding holds the entries, bounded by the cap above, and applies none of them before snapshot_end|**D** neither|pl/receive:366-371; fe/records:65-68|Nothing is applied early in either. The bound: frond-ear 511 and 1 MiB (and rejects more, so a daemon that raised its [PROPOSED DEFAULT] would be cut off); the plugin 1 024 and no byte bound. Admitted: pl/README:265.|
|2286|the run's presence table becomes the snapshot's, and its view of…|I|pl/receive:402-415; fe/records:774-777; fe/t/canticle-join-snapshot:260||
|2286|That is all absence does. It is not a retract and settles nothing|I|pl/receive:402-407; fe/records:757-768; fe/t/canticle-join-snapshot:260|The plugin's candidate and slot ledgers are not touched by a snapshot at all, which…|
|2287|Nothing the binding already held from this run is removed or…|I|pl/receive:402-415; fe/records:788-789; fe/t/canticle-join-snapshot:229|frond-ear shows the omitted item again as live|
|2289|In both cases live records above W then apply on top as usual, a…|I|pl/receive:431-465; fe/records:573-579; fe/t/canticle-join-snapshot:171||
|2289|In neither does a snapshot settle, re-deliver or un-settle a frame…|I|pl/binding:422-425; fe/delivery:18-21; pl/t/inbound:106||
|2290|is deliverable as the frame record it reproduces would be…|I|pl/receive:385-389, pl/candidates:153; fe/records:749-754; fe/t/canticle-join-snapshot:188||
|2290|it never counts toward any §14.6 rate, budget or salience quantity, and it never wakes a session|**D** neither|pl/candidates:151-172; fe/delivery:260-261|Counting: the plugin spends perHour on it. Waking: frond-ear pushes an unpushed snapshot or resurfaced record into the session (immediate within maxAgeMs), on purpose. Admitted: fe/docs/runbook:854.|
|2290|A pending or settled frame key stays as it is, so a snapshot…|I|pl/binding:422-425, pl/candidates:153-162; fe/delivery:18-21; pl/t/inbound:106||
|2290|Expiry, subscriptions, A11 delays (§14.16) and host-slot…|I|pl/candidates:137-177, pl/receive:513-534; fe/records:1212-1215; pl/t/candidates:112|Plugin: the same accept path for every source.|
|2291|the binding discards the held entries and withdraws as above, and…|I|pl/receive:181-210, pl/daemon:91-94; fe/records:1344-1347; fe/t/canticle-join-snapshot:285||
|2292|A rejoin still reports records_lost once|I|pl/receive:340-345; fe/records:690-695; fe/t/canticle-join-snapshot:260||
|2292|snapshot entries are delivered only after step 4, so a key settled as rejoined is never delivered from a snapshot|**D** owner|pl/binding:416-442; fe/records:763-768|frond-ear has no rejoined settlement and delivers from the snapshot. The plugin delivers none after a rejoin, but only because it never admits that run again. Admitted: fe/docs/runbook:854.|
|2293|the binding reports receive health degraded, reason joined_late, beside any other reason, until a snapshot_end with…|**D** owner|pl/receive:591-604; fe/records:638-641|frond-ear complies. Plugin: unknown (joining) while pending; degraded/joined_late only when truncated or unsupported. Admitted: pl/README:192.|
|2293|Nothing else clears it: no timer or carousel window does|I|pl/receive:601-603; fe/records:1326-1330; fe/t/canticle-join-snapshot:336||
|2293|Every bootstrap on the host socket therefore starts joined_late, and only a complete snapshot or a new run clears it|**D** owner|pl/receive:591-595; fe/records:638-641|frond-ear yes, plugin no (above). "A new run clears it" is moot on the socket: a new run arrives on a new connection, whose bootstrap sets it again. Admitted: pl/README:192.|
|2293|A binding that never asks for a snapshot reports it for the life of…|I|pl/receive:274-276,601-603; fe/records:638-641; fe/t/canticle-join-snapshot:336||
|2293|A completed snapshot clears joined_late only, never records_lost|I|pl/receive:597-604; fe/records:723; fe/t/canticle-join-snapshot:260||
|**§14.18.4**|**Judgment and delivery** (15 I · 7 D)||||
|2297|The receptor's judgment for a binding is session-independent.|I|records:174-175, daemon:404-410; fe/records:1198|No test for the refusal itself. Receptor refuses a listener that has a tune set|
|2297|disposition: surface means eligible to surface to a session whose…|I|pl/records:121-123, pl/candidates:141-176; fe/delivery:1168-1180; pl/t/subscriptions:59|surface only makes a record a candidate|
|2297|The §14.3 landing field is null, and landing is the binding|I|records:452-485|Record v1 carries no landing field at all (absent, not null). No test.|
|2298|Only a frame record with admission: verified and disposition…|I|pl/records:121-123, pl/receive:434-446; fe/records:1198-1215; pl/t/receive:176|fe has the same test (canticle-records.test:124).|
|2298|Every other record reaches at most the binding's local ring and its…|I|pl/receive:435-437,479-506; pl/t/receive:176|Non-deliverable frames are only counted (frames_other); not even ringed.|
|2298|so is a frame entry of a completed join snapshot that reproduces one|I|pl/receive:383-415; fe/records:525-531; pl/t/inbound:65|Entries are checked with the same isDeliverable and applied only at snapshot_end.|
|2299|Under a binding, tuning is the binding's alone|I|pl/binding:203, pl/candidates:93-98; fe/source:122-127; pl/t/subscriptions:59|Plugin config and fe canticle.tune.|
|2299|The receptor applies no tune set and no host-level stream filter|I|records:174-175, daemon:405-406|Enforced by ValueError in Receptor.__init__. No test.|
|2299|stays in the binding's local ring for that session, with the binding's reason untuned|**D** owner|pl/receive:524-527, pl/binding:203; fe/records:1427|Two tunes: listen.tune drops a record before view and journal (only an untuned counter); listen.subscriptions hides journaled items with no reason. fe keeps untuned in its live set, no reason. README:106,360 do not call it a departure. Admitted: plugin/README:106.|
|2299|untuned is never a receptor disposition|I|records:51|DISPOSITIONS has no untuned. No test for absence.|
|2300|a subscription whose posture is not off names the session and…|I|pl/candidates:138-176,63-68; fe/delivery:1168-1180; pl/t/candidates:87|All five filters, exact session keys.|
|2300|the subscription's budget has room|I|pl/candidates:151-156, pl/config:131; fe/delivery:1386-1389; pl/t/candidates:87|perHour (default 60) per subscription and target, spent at admission even if the item…|
|2300|local_expiry_at has not passed|I|pl/candidates:140,221; fe/records:1423-1426; pl/t/receive:164||
|2300|any A11 delay for the item has matured|**D** rfc|pl/candidates:165-168,221; fe/delivery:1138-1141|Plugin does it (random draw, 60 s, m=1 s; no test that an unmatured item waits). frond-ear violates it: no random delay, only a fixed 5 s debounce or 60 s window. Admitted in fe runbook, not in the RFC. Admitted: fe/docs/runbook:853.|
|2300|until §23.2 question 22 is settled, the session has no off-host channel route|**D** rfc|pl/candidates:69-77, pl/ambient-slots:84-91; fe/delivery:1465-1505|Plugin needs a host onHost:true proof per key. frond-ear pushes into sessions bound to Discord by design (MUST NOT of §14.12 line 2053). Admitted in fe runbook only. Admitted: fe/docs/runbook:852.|
|2301|own station key is not delivered unless self-broadcast is explicitly included|**D** rfc|pl/binding:418, pl/candidates:143; fe/delivery:1168-1180|Plugin: reads need includeSelf; ambient treats naming the own station in a subscription as inclusion (no ambient test). frond-ear knows no own key: hear shows it, and a push happens if it is on wakeKeys ("leave it out"). Admitted: fe/docs/runbook:707.|
|2302|never counts toward any §14.6 rate, budget or salience quantity|**D** owner|pl/candidates:151-173, pl/binding:422-425; fe/delivery:1475-1478|Plugin ignores dedup in admission: a resurfaced (or snapshot) item new to it is spent on perHour and blocked by it; the test says "cannot bypass budget". fe counts every push. Text may mean only §14.6 quantities.|
|2303|The binding applies the receptor's landing_state to every session.|I|pl/binding:452-487; fe/records:818-836; pl/t/ambient-binding:131|Only against a fake daemon: the real one never changes landing_state (station…|
|2303|it withdraws every pending canticle entry and delivers nothing (§10.6, §14.16 item 3)|**D** rfc|pl/binding:452-477, pl/ambient-slots:119-140; fe/records:1419-1420|Works when every target is healthy. One session whose route or generation proof fails throws out of the loop, so later sessions keep pending entries; a session that went off-host cannot be withdrawn at all. See finding.|
|2303|it collapses the digest to one line per stream and delivers no wake|I|pl/binding:464-465; fe/delivery:1383-1385|No test of the one-line rule (test 187 only checks the old entry is withdrawn).|
|2303|while it is half_open it holds the digest to 25%|I|pl/binding:466; fe/delivery:1383-1385|No test. floor(n/4) of the candidate items, so 1-3 items give an empty digest|
|2303|It applies modulation to the weights and thresholds of the matching subscriptions|**D** rfc|pl/binding:484-485; fe/records:818-836|Plugin: any non-empty modulation closes ambient admission and drops queued candidates (fail closed). fe ignores modulation. No weights or thresholds exist. The daemon never emits any. Admitted: plugin/README:9.|
|**§14.18.5**|**Idempotency and delivery guarantee (Q2, D26)** (26 I · 7 D · 1 U · 2 ?)||||
|2307|The idempotency key for one frame in one session is the key of…|I|pl/candidates:153, pl/records:65-67; fe/delivery:129-133; pl/t/ambient-slots:74|idem + ":" + sessionKey.|
|2307|with the harness's canonical session key|I|pl/config:16-22, pl/index:68-74; pl/t/subscriptions:14|Only lower-case exact keys are accepted; main keys are refused.|
|2307|A subscription id is metadata only, never part of the key|I|pl/candidates:153-161|Second matching subscription only appends its id.|
|2308|The binding keeps each frame key, and its settled tombstone, in its…|I|pl/candidates:43-62, pl/ambient-slots:35-61; fe/src/store:719; pl/t/candidates:46|Two JSON ledgers, fsynced and renamed. fe: SQLite canticle_settled.|
|2308|Once a key has been admitted to a session (put into a pending slot…|I|pl/candidates:154-162, pl/ambient-slots:129; fe/delivery:1043-1052; pl/t/candidates:87||
|2308 dflt|kept until the frame's local expiry plus 5 s skew [PROPOSED DEFAULT]|I|pl/candidates:104,180; fe/delivery:94; pl/t/journal:60|5000 ms in both.|
|2308|A frame key settles only when a slot entry carrying it is consumed at drain or discarded by the host|**D** code|pl/candidates:101-107,118-127; fe/delivery:1102-1105|Code also settles on a mute (binding or daemon), untune or config change, session reset, and any disconnect. §14.16 item 3 requires mute and untune to cancel, so the "only" list is too short. fe also settles on mute. Admitted: plugin/README:5.|
|2308|or when the frame itself is retracted (pluck, supersession…|I|pl/binding:136-142, pl/candidates:178-182; fe/delivery:1087-1089; pl/t/ambient-slots:61||
|2308|when its binding rejoins the frame|**D** rfc|pl/binding:182-190, pl/candidates:183-187|Keys of the last run settle at the disconnect, before the join is known to be a rejoin or a new run; on a Gateway restart into the same run they are not settled at all (preserveInitialRejoin). See findings. Admitted: plugin/README:5.|
|2309|settles none of the frame keys the old entry carried: the…|I|pl/ambient-slots:77-83,160-162; pl/t/ambient-slots:31||
|2309|Each slot entry has its own host idempotency key, unique per rebuild|I|pl/ambient-slots:144; pl/t/ambient-slots:61||
|2309|The binding rebuilds an entry no later than the earliest local expiry of the items it carries.|**D** rfc|pl/binding:124,335-338|No timer on the deadline: the rebuild happens at the next 5 s tick or event, so surviving items can be in no slot for up to 5 s. The entry itself still dies on time (deadline = earliest expiry). No test.|
|2309|only the frame keys whose own local expiry has passed settle; the…|I|pl/ambient-slots:81; pl/t/ambient-slots-races:45||
|2310|Restarts. Pending frame keys survive gateway|I|pl/candidates:43-61, pl/binding:181-187; pl/t/candidates:129|But §14.18.3 rejoin step 4 says the same keys settle as rejoined after such a start…|
|2310|gateway and receptor restarts|**D** rfc|pl/binding:188-190,422-425; fe/delivery:1025-1086|A receptor (daemon) restart drops the connection; candidates of that run are settled at once, and the resurfaced copy under the new run is refused as already journaled, so undelivered items never land. fe carries them across.|
|2310|settled tombstones also survive session reset and plugin disable…|I|pl/ambient-slots:196-207, pl/candidates:195-201; pl/t/ambient-slots:111|Reset keyed on the host generation.|
|2310|session delete clears both|**D** code|pl/candidates:202-210, pl/ambient-slots:210-220|Slot ledger clears; candidates.json keeps tombstones and spend whenever the callback names a generation, which index.ts always requires. Fails safe: a recreated session is not re-told. README explains generation, not this. Admitted: plugin/README:7.|
|2310|join-snapshot entries (amendment BC-1b (#81)), therefore deliver…|I|pl/binding:422-425, pl/candidates:154-162; fe/delivery:1043-1052; pl/t/inbound:106|fe re-pushes a push the host never confirmed (runbook:800-806), a rare duplicate it…|
|2311|The binding's durable state is authoritative for frame keys|I|pl/ambient-slots:2,106-117; pl/t/ambient-slots:46||
|2312|the binding durably records the entry|I|pl/ambient-slots:144-147; pl/t/ambient-slots:46||
|2313|The enqueue names the entry it expects to supersede (§16.4 item 2).|I|pl/ambient-slots:151-153, pl/oc0-host:23; pl/t/oc0-host:5||
|2313|the binding applies that entry|I|pl/ambient-slots:155-158; pl/t/ambient-slots-races:22|It throws and rebuilds on the next sync|
|2314|the binding marks it pending and its predecessor withdrawn|I|pl/ambient-slots:160-162; pl/t/ambient-slots:31||
|2315|the binding queries the host's settled state (§16.4 items 2-3) for…|I|pl/ambient-slots:106-117, pl/binding:272-277; pl/t/ambient-slots:46||
|2315|delivers nothing to that session until all are resolved|**D** rfc|pl/binding:272-277,452-477|Blocks more than that session: an unresolvable entry throws out of the loop for all later sessions, and at start fails the whole service (state_unreadable), forever if the old-generation entry never settles.|
|2315|consumed: every frame key the entry carried settles.|I|pl/ambient-slots:79-80; pl/t/ambient-slots:31||
|2315|withdrawn: frame keys carried by an accepted successor stay with it|I|pl/ambient-slots:77-83, pl/binding:457-471; pl/t/ambient-slots:61|Keys are never settled by withdrawn; live candidates re-enter at the next build.|
|2315|expired: only frame keys past their own local expiry settle|I|pl/ambient-slots:81; pl/t/ambient-slots-races:45||
|2315|discarded: every frame key the entry carried settles.|I|pl/ambient-slots:80|No test drives discarded.|
|2315|Unknown: the host never accepted the entry, and its frame keys…|I|pl/ambient-slots:113-115|settle(unknown) leaves frame keys unsettled. No test of unknown at reconcile.|
|2315|Unknown is unambiguous because the host keeps every entry's outcome until its outcome retention has passed|**?**|pl/ambient-slots:145|Host behaviour: OpenClaw core owner (#1511). The binding sends outcomeRetainUntil = latest expiry of the carried frames.|
|2316|The at-most-once claim below holds only once proofs show it with…|U||Fake host in one process only: enqueue reply lost…|
|2316|every frame still live and unconsumed at restart is delivered by a later rebuild|**D** neither|pl/binding:181-190, pl/candidates:183-187|Holds for a Gateway restart, not after a live disconnect (settled). And §14.18.3 rejoin forbids it: those keys are "never delivered". A retract missed while down can land. RFC must pick one.|
|2317|At most once, at prompt assembly, given the handshake and crash proofs above.|**?**|pl/ambient-slots:77-83; pl/t/ambient-slots:46|Binding side built; prompt assembly is OpenClaw core. No live drain was ever shown (plugin README:7). OpenClaw owner could answer.|
|2317|consumption is not a receipt that the model saw anything|I|pl/ambient-slots:79-80; fe/custody:1-14|Plugin uses consumed only to taint and settle.|
|2318|No binding promises exactly-once model or transcript behaviour.|I|pl/ambient-slots:77-83; fe/src/shim:654-666|Nothing contrary in plugin.|
|**§14.18.6**|**Landing (Q5, D28)** (8 I · 1 D · 1 ?)||||
|2322|Per-frame records stay inside the receptor and the binding's local ring; they never become per-frame session entries.|**D** neither|pl/binding:452-477, pl/ambient-slots:22; fe/delivery:2696-2706|Plugin: two slots only. frond-ear: every push is a new channel event holding up to 5 (max 10) whole records with payloads, which cannot be rebuilt or recalled. RFC is the safer rule; a channel has no slots to hold it. Admitted: fe/docs/runbook:850.|
|2322|the binding keeps at most two pending entries per session, one per…|I|pl/ambient-slots:22,74-76; pl/t/ambient-slots:31||
|2322|The digest carries the dose of §14.6.5.|I|pl/candidates:14,222-229; fe/src/config:461-463; pl/t/candidates:112|Per slot entry, not per turn.|
|2322|enters the digest only after its A11 delay has matured (§14.16 item…|I|pl/candidates:165-168,221|Chatter, ambient, advisory. Tests only read a slot after 60 s|
|2322|does not set OC-0's not-before|I|pl/oc0-host:20-26, pl/ambient-slots:151-153; pl/t/oc0-host:5||
|2322|The binding keeps each held item's drawn eligibility time in its…|I|pl/candidates:169-173,43-58; pl/t/candidates:129|eligibleAt is in candidates.json.|
|2322|at maturity it re-checks every cancellation condition of §14.16…|I|pl/candidates:99-115,216-221; pl/t/candidates:129||
|2322|The binding rebuilds an entry on every retract that touches it|I|pl/binding:136-142, pl/ambient-slots:172-189; pl/t/ambient-binding:114|Does nothing when the route proof fails (ambient-slots:173-174): the entry then keeps…|
|2322|the seam re-checks expiry at drain (§16.4 item 1)|**?**|pl/oc0-host:24|OpenClaw core (#1511 owner). Plugin sends expiresAt = earliest expiry.|
|2322|an item withdrawn after it was consumed gets the one-line note of…|I|pl/ambient-slots:181-189,222-239; fe/docs/runbook:850; pl/t/ambient-slots:74|Not if the route proof fails or if expiry is missed while the binding is down.|
|**§14.18.7**|**Configuration (Q7, D30) and trust tier (Q8, D31)** (15 I · 5 D · 4 ?)||||
|2326|every canticle key lives under plugins.entries.‹id›.config|I|pl/index:35-38, pl/openclaw.plugin.json:6-9; fe/src/config:264-273; pl/t/plugin:444|Plugin id is "canticle" (RFC example says "binary-canticle").|
|2327|on OpenClaw its false default holds only when written explicitly (D30)|**?**|pl/README:322-330|OpenClaw auto-enable rule plus operator practice; no code here can enforce it. The plugin cannot start without binding and daemon.socket (schema required). OpenClaw owner / seat operators.|
|2327|Operators write plugins.entries.‹id›.enabled: false explicitly.|**?**|pl/README:322-330|Operator practice. README:323 and 399 say so and say install writes it; not checked from this repo.|
|2328|The schema therefore checks shape, bounds and constants only.|I|pl/openclaw.plugin.json:6-101; pl/t/plugin:456||
|2328|Semantic, filesystem and runtime checks|I|pl/index:94-124, pl/config:59-185; pl/t/plugin:268|Built: paths, session keys, wake refusal, state root, lease, host seams.|
|2328|a failure fails the canticle service, never Gateway boot|I|pl/index:121-124,62-66; pl/t/plugin:268|register() catches its own config error; start() rethrows to the host.|
|2328 MUST NOT|Operators MUST NOT deploy a canticle configuration that can refuse Gateway boot.|**?**||Operator practice. Who could answer: seat operators.|
|2329|The binding is a third-party, least-privileged plugin.|I|pl/package.json:4-9, pl/index:80-92; pl/t/plugin:71|private, unpublished; registers only tools, one service and lifecycle callbacks.|
|2329 MUST NOT|It MUST NOT depend on bundled-only or trusted-only privilege|I|pl/index:18-32, pl/store:1-30|Nothing contrary: no keyed/blob store, trusted dispatch or doctor check is used|
|2329|What it needs from the host comes from the generic seam (§16.4)|**D** neither|pl/index:21-24,80-87|Also needs session.state.resolveLocalSessionRoute (#1511) and session_reset/session_delete (#1523), and expectedSessionId/LifecycleRevision on every OC-0 call. None is in §16.4. The need is real; the RFC should state it. Admitted: plugin/README:7.|
|2329|it keeps its own state in its own state directory|I|pl/config:187-190, pl/store:11-22; pl/t/plugin:282||
|2329|It needs no conversation access (hooks.allowConversationAccess)|I|pl/index:80-92|Registers no conversation hook; session_reset/session_delete are metadata callbacks.|
|2329|it learns that an entry was consumed from OC-0|I|pl/ambient-slots:106-117, pl/oc0-host:29-32; pl/t/ambient-slots:74|Settled-state query only, polled each tick and before each sing|
|2330|Ambient landing uses next-turn injection|I|pl/oc0-host:20-26; pl/t/plugin:87||
|2331|ringbuffer_only → off, ambient → silent, wake → silent-wake (§14.9)|I|pl/config:129-131; fe/src/config:395-400; pl/t/candidates:21|First two names exist and mean that. fe uses off/digest/immediate|
|2331|wake is valid only with classes exactly alarm (D1, D25), and a P1 binding refuses it|**D** rfc|pl/config:129-130; fe/delivery:1168-1180|Plugin refuses wake outright. frond-ear wakes on any class from an allowlisted key. Admitted: fe/docs/runbook:851.|
|2336 dflt|Plugin enabled / false, written explicitly / §15.5; D30|**?**|pl/README:330|OpenClaw setting, operator-written. The plugin config itself needs binding and daemon.socket. Operators/OpenClaw.|
|2337 dflt|Subscription delivery / ringbuffer_only / sessions start untuned|I|pl/config:129,104-106; fe/src/config:455; pl/t/subscriptions:14|Also: no subscriptions at all by default. fe default mode off.|
|2338 dflt|Wake / absent; alarm only when present|**D** rfc|pl/config:130; fe/src/config:332-343|Plugin: wake cannot be configured. frond-ear: off by default (mode off, wakeKeys empty) but when on it wakes for every class. Admitted: fe/docs/runbook:851.|
|2339 dflt|Publishing beyond the host / disabled / §15.5|I|pl/config:86-89,173-181; pl/t/plugin:211|publish.enabled defaults false.|
|2340 dflt|Multicast (join or send) / off; on only after canticle doctor passes|**D** rfc|stations:90, doctor:21-29|Off by default holds. The gate does not exist: this doctor only reports and nothing ties enabling multicast to a pass (AGENTS.md says so). Binding never joins UDP. Admitted: README:130.|
|2341 dflt|Self-broadcast / filtered / §14.6.1|**D** rfc|pl/config:164, pl/binding:846; fe/delivery:1168-1180|Plugin default false (reads). frond-ear does not know its own key and does not filter it. Admitted: fe/docs/runbook:707.|
|2342 dflt|Consumption mode / raw / §14.6.8|I|pl/candidates:165-169|Only raw exists; no consumption-mode setting. No test.|
|2343 dflt|Per-turn dose / 5 items, 1.5 KB / §14.6.5|I|pl/candidates:14,222-229; fe/src/config:461-463; pl/t/candidates:112|Per slot entry. fe default 5 records whole, 6000 characters, up to 360 pushes/h.|
|**§14.18.8**|**Banner (Q9, D32)** (4 I · 1 D · 1 ?)||||
|2347|Every document and implementation uses the §14.13 marker [canticle:heard], and no other.|**D** rfc|pl/render:104, pl/candidates:163; fe/hear:119|tap, plugin reads and fe use it. The plugin's ambient digest lines carry no marker at all, only metadata, and its note uses [canticle:withdrawn/expired]. Other [canticle:] status prefixes exist.|
|2347|The strip rule and drain accounting of §14.13 depend on the…|I|pl/render:29-54, tap:150; fe/hear:56-63; pl/t/render:78||
|2348|principal comes from the manifest.|I|records:460, pl/render:105; fe/hear:123; t/tap:182||
|2348|the banner reads principal="unavailable"; missing provenance is…|I|pl/render:105, tap:146; fe/hear:36-39; t/tap:182||
|2349|The banner is host-authored and outside the untrusted-content…|I|pl/render:100-125; fe/hear:81-91; pl/t/inbound:445|True for reads and for fe.|
|2349|including by OC-0's provenance rendering (§16.4 item 6)|**?**|pl/oc0-host:25|Plugin declares provenance {source:"canticle"} only (no station, principal, key, sig). What OpenClaw renders from it is the core owner's (#1511).|
|**§14.18.9**|**Phases and gates (Q1, D25)** (2 I · 6 D · 1 U · 1 ?)||||
|2353|P1, receive-only. No publish, no wake.|**D** rfc|pl/config:86-89, pl/binding:218-237; fe/delivery:1168-1180|Plugin: P1 by default, but it ships a full sing/hush/outbox behind one config flag (publish.enabled, needs pinned key and socket) with no phase lock. frond-ear never sings but wakes sessions for any class: not P1. Admitted: plugin/README:36-42; fe/docs/runbook:851.|
|2353|ringbuffer_only can run against BC-2's records.|I|pl/binding:416-442, pl/daemon:1-8; pl/t/interop:101||
|2353|ambient waits for OC-0 (§16.4), because the guarantee of §14.18.5…|I|pl/index:101-108, pl/binding:130-131; pl/t/plugin:148|Service start throws unless route resolver, enqueue/query/withdraw and lifecycle…|
|2353|does not target sessions with an off-host channel route until §23.2 question 22 is settled|**D** rfc|pl/candidates:69-77; fe/delivery:1465-1505|Plugin obeys (host proof). frond-ear sessions are Discord-bound by design. Admitted: fe/docs/runbook:852.|
|2354|P2, publish. §15 in full, including every check of §15.4 and the gates of §15.5.|**D** rfc|pl/outbox:202-357, pl/binding:1123-1182; fe/derived:1-27|Partial P2 behind publish.enabled: no lineage stamping, no per-turn rate, no sensitivity labels, no fleet/public checks. README says "not P2". fe derived publication: no route wired, off. Admitted: plugin/README:474-482. #162 changes the plugin reader only; its derived op is a authority path, not this P2|
|2355|D1 is retained: verified alarm frames only, under the whole §14.10 conjunction.|**D** rfc|fe/delivery:1168-1180|Plugin: no wake. frond-ear: any class from a wakeKeys station, hop 0, not wake-derived, breaker closed, freshness; no class rule, session/host/token budgets, sandbox or proofreading. RFC not amended (bc#100). Admitted: fe/docs/runbook:851.|
|2355|A binding adds wake only after a concrete operator alarm producer exists|**D** rfc|fe/src/shim:775-779|frond-ear push-wake exists; no alarm producer or §14.10 proof does. Admitted: fe/docs/runbook:844-851.|
|2355|with the host wake budget owned as §14.18.1 requires|U||No host wake budget anywhere.|
|2355|OC-0 carries no wake (D26)|**?**|pl/oc0-host:5-13|Adapter type has no wake field; the host seam itself is OpenClaw's.|
|2356 SHOULD|only then enabling publishing and wake|**D** owner|pl/outbox:202-357; fe/src/shim:654-666|Recommended order only. frond-ear wake and the plugin outbox were built before any proven P1 or live OC-0. Admitted: fe/docs/runbook:844-851.|

### §15 Publishing

127 claims: 55 I · 39 D · 31 U · 2 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§15.1**|**Tool verbs** (17 I · 17 D · 9 U)||||
|2366|DECISION D20 (recommended: canticle_sing, canticle_hush, canticle_tune, canticle_listen.|**D** owner|pl/tools:10-12; fe/src/shim:221|The plugin registers canticle_listen, _status, _mute, _discover, _sing, _hush, _outbox: seven tools, no canticle_tune. frond-ear's nearest tools are hear and set_canticle_delivery. The set is still open (question 24). Admitted: pl/README:474 (does not list canticle_discover).|
|2370|stream: string, // logical stream name|I|pl/tools:113, pl/outbox:329-331|Required string, checked against the stream-name grammar and against the streams the…|
|2371|never a host:port, multicast group or SRV name|I|pl/outbox:329-331, ids:65-68|Enforced by the stream-name grammar in plugin and station.|
|2372|payload: string|I|pl/tools:114, runner:90; pl/t/outbound:67|Text payload in the plugin; text on the control socket and CLI.|
|2372|{ ref: { url: string, sha256: string, size: number }, summary?: string }|**D** rfc|pl/binding:1149-1156, runner:55-67|The agent tool refuses a reference payload (bad_param). The control socket and CLI take it as body_ref beside a body; only there. rfc better: size refusals tell the agent to use a reference it cannot send. Admitted: pl/README:476.|
|2373|contentType?: string|**D** owner|pl/tools:112-121, runner:99-100|The tool has no contentType: text only. Socket and CLI take a numeric ctype, never a media-type string; the CLI --ctype applies only to a --body-hex body. Admitted: pl/README:476.|
|2373 dflt|default "text/plain; charset=utf-8"|I|station:287-288|A text body with no ctype is signed as ctype 1. No test asserts the default by itself.|
|2374|class?: "chatter" / "ambient" / "live-state" / "advisory" /…|I|pl/tools:115, pl/config:53; pl/t/plugin:245|Exactly this enum in the tool|
|2375 dflt|default from stream configuration; alarm|I|station:275|Station takes the stream's class when none is given. No test.|
|2376 MUST NOT|control are not offered to LLM sessions (§10.4)|I|pl/config:53,91-95; t/station:496|Plugin config refuses the three classes|
|2377 MUST|required for live-state and root|I|station:295-296|Station refuses a keyed class without state_key (also regulatory, alarm, control).|
|2378 dflt|default "broadcast"|U||No mode parameter anywhere; everything is broadcast.|
|2379|audience?: { sessionKeys: string[] }|U||No audience parameter, no addressed mode.|
|2380|scope?: "host" / "lan" / "fleet" / "public"|**D** rfc|pl/outbox:286, __main__:780|Plugin always sends scope lan and has no parameter. CLI/socket take all four (default lan), but host is always refused there (UDP only). Admitted: pl/README:476.|
|2380 dflt|default from stream configuration; clamped|**D** neither|station:42-48,270|StreamConfig has no scope; the default is a constant lan, and an ungranted scope is refused, not clamped. Refusing is the safer reading; the default should be per stream.|
|2381|keepOnAir?: { forSeconds?: number, loop?: "fast" / "normal" / "slow" / number }|**D** rfc|pl/tools:112-121, runner:90-106|Not in the agent tool. Socket/CLI have separate keep_on_air (keyed items only) and loop (names or ms). Admitted: pl/README:476.|
|2382|ttlSeconds?: number, // may only shorten|I|pl/tools:118, station:305; t/station:63||
|2383|intensity?: number, // 0..1, optional|**D** neither|__main__:782, runner:90|Not in the tool. Socket/CLI take the wire integer 0-255, not 0..1: a 0..1 fraction is refused (no floats in CBOR), and a value over 255 is signed and then rejected by every receiver. Admitted: pl/README:476.|
|2384 MUST|≤ 128 bytes on the wire|**D** rfc|pl/outbox:344-346, station:309-313|Plugin refuses a purpose over 128 bytes. The station and CLI do not: an over-long purpose is signed, gets an on-air receipt, and every receiver rejects it (bad-field: purpose). Checked with the codec.|
|2384|on the wire; shown as context|I|pl/render:112-114, tap:158-159; fe/hear:147-150; t/tap:182|Host banner shows it as "declared by the station; context, not authority".|
|2385|exercise?: boolean|U||The flag exists on the wire and is rendered by receivers, but…|
|2387|status: "on-air" / "delivered" / "rejected" / "budget_exhausted"|**D** code|pl/outbox:74-77,681-693|Plugin returns on-air, rejected, budget_exhausted, plus unknown, failed, ended; never delivered. Station replies {ok, ...}. code better: a lost reply must not read as on air or rejected. Admitted: pl/README:477.|
|2388|opaque reference, e.g. "cnt:21fe31dfa154a261:7:1a2b3c4d:42"|**D** owner|pl/outbox:255, __main__:790-794|Plugin item is an outbox row id out:BINDING:N; hush takes only that. CLI hush takes stream and seq. No cnt: reference exists. Admitted: pl/README:86.|
|2389|expiresAt: string, // ISO 8601|I|pl/binding:1217-1218|Plugin: ISO string from the station receipt. CLI/socket give epoch ms. No test.|
|2390|effective: { ttlMs: number, loopMs: number|I|pl/binding:1219-1221, station:338-341; pl/t/outbound:67||
|2391|clampReason: "none" / "class_min" / "fair_share" / "budget" / "stream_max" / "class_max"|**D** neither|station:234-251, pl/binding:1222-1225|Station emits none, class_min, fair_share, degraded; never budget or class_max. Plugin shows a TTL cut as stream_max (hiding a loop clamp) and degraded as none + degraded:true. RFC lacks degraded. Admitted: pl/README:478.|
|2392|scope: string, class: string, hop: number }|**D** rfc|pl/binding:1226-1228, station:51-64|Constants, not effective values: scope "lan", hop 0, and class is the literal text "stream default" when the caller gave none. The station's reply carries none of the three.|
|2393|retryAfterMs?: number|I|pl/binding:1202, pl/outbox:361-375; pl/t/outbound:421||
|2394|reason?: "disabled" / "capability" / "tainted_scope" / "content_policy" / "size" / "rate" / "collision"|**D** neither|pl/outbox:328-358, pl/binding:1126-1147|Plugin has no tainted_scope or collision and adds stream, state_key, ttl, key, key_conflict, quota, station_unreachable, station_key_mismatch; taint and disabled are refusals, not reasons. Station gives free-text errors. Admitted: pl/README:162 (departures table omits the….|
|2397|canticle_hush({ item: string }) -› { status: "plucked" / "not_found" / "expired" }|**D** code|pl/outbox:79-83,695-709|Built, plus pending and unknown when the station did not answer, and refusals. code better (no false claim of withdrawal). Admitted: pl/README:477.|
|2399|canticle_tune({ stream: string|U||No tune verb in plugin, MCP or CLI.|
|2400|posture: "silent" / "wake-on-alarm" / "off"|U||No postures. Plugin delivery is ringbuffer_only or ambient|
|2401 dflt|w_s, 0..2, default 1.0|U||No stream weight in any implementation.|
|2402|-› { status: "ok" / "rejected", effectivePosture: string }|U||No tune verb, so no result.|
|2404|canticle_listen({ stream?: string, since?: string, limit?: number|I|pl/tools:58-64, pl/binding:694-725; fe/src/shim:253-262; pl/t/inbound:418|Plugin takes all three (exact stream name; opaque cursor|
|2405|view?: "digest" / "items" / "raw" })|**D** owner|pl/tools:63, pl/binding:687-693; fe/src/shim:250-262|Plugin has digest (default) and items (listed sessions only); no raw. frond-ear hear always shows the text and has no view. Admitted: pl/README:475.|
|2405|"raw" is for operators|I|__main__:429-431,908-909; t/tap:373|Only the operator CLI has it: canticle tap --json --unsafe-raw.|
|2406|-› { entries: [...], truncated: boolean }|I|pl/binding:796-811; pl/t/inbound:418||
|2409 MUST NOT|Tool results MUST NOT echo payload bytes|I|pl/binding:1306-1330, pl/outbox:299; pl/t/outbound:67|Outbox rows keep text only until sent and show sha256 and size|
|2410|wake-on-alarm is honoured only where host configuration allows wake|U||No tune verb and no wake-on-alarm posture|
|2410 MUST|D1 keeps wake off everywhere until S3 has tested the §14.10 conjunction|**D** owner|pl/config:130; fe/delivery:1168-1180|Plugin refuses wake. frond-ear, when configured (canticle.delivery plus wakeKeys, both off by default), pushes any class to the session as a channel event: class is not checked. Violated by frond-ear.|
|2410|otherwise effectivePosture reports silent|U||No effectivePosture field.|
|2411|Operators and services publish alarm, regulatory and control frames through the CLI|**D** code|runner:27-31,88-89|The CLI can only use the control socket, which refuses all three classes even when the key holds them. Fail closed until op-level checks exist, but no operator alarm path exists at all (P3 needs one). Admitted: README:17.|
|**§15.2**|**Owns-table** (5 D · 1 U)||||
|2419|Agent / stream, payload, mode, audience, keepOnAir intent, purpose|**D** neither|pl/tools:112-121|The agent sets stream, payload, purpose, and also class, stateKey, ttlSeconds, idempotencyKey; mode, audience and keepOnAir do not exist. Class/stateKey are missing from the RFC's own row though §15.1 gives them to the agent. Admitted: pl/README:476.|
|2420|Tool / Gates, clamping, content policy, stamping hop/lineage/wake_derived|**D** rfc|pl/binding:1123-1148, pl/outbox:328-358|Tool owns gates and the secret scan; clamping is in the station; no stamping, no broadcast/addressed choice, no spans. The CLI path has only class/scope/stream grants. Admitted: pl/README:480. #162 stamps hop/derived_from/root for one derived-chatter op #162/derived_station_proposal:55, off by default|
|2421|Daemon (station) / Signing, epoch/seq, the station ring, loop scheduling, beacons|**D** owner|station:268-341,105-140|All done by canticle station, one process per key with its own control socket. The host daemon (D35) holds no key and signs nothing; D35 says it holds the station keys and signs every binding's publishes. Admitted: README:64 (key store only).|
|2422|Substrate, broadcast / Relays, LAN multicast, DNS-SD, the replay tier|**D** rfc|runner:144-146, __main__:164-168|Multicast and unicast UDP sending and a read-only DNS-SD browse exist. No relay, no DNS-SD publication, no replay tier. Admitted: README:61-69.|
|2423|Substrate, addressed / The harness's same-host queue|U||No addressed path in plugin or frond-ear.|
|2425 MUST NOT|The agent never names a substrate, hook or wire (OC-RFC:885).|**D** rfc|pl/tools:108-121, __main__:187-191; fe/docs/runbook:683-686|True of the plugin tool. The deployed agent path is canticle sing through Bash, where the session must name the station's socket (--control) and may name a scope and a raw ctype. Admitted: README:224-225.|
|**§15.3**|**Two-gate emission: when to sing** (3 I · 1 D · 8 U · 1 ?)||||
|2429|Deciding when an item goes on air is separate from deciding how…|I|station:268,234-251|sing() decides admission; _loop/_schedule decide repetition.|
|2431|a lifecycle hook opens the mouth|U||No compaction, continuation or pressure hook offers a sing in…|
|2432|the agent chooses what to sing, or nothing|I|pl/binding:1123, runner:85-107|Every emission is an explicit call (tool or CLI)|
|2435|in v1 only alarms can wake|**D** owner|pl/config:130; fe/delivery:1002|frond-ear pushes any class from a wakeKeys station, at hop 0 and not wake-derived, as a channel event into the session when an ear opts in (default off, wakeKeys empty). Plugin never wakes.|
|2439|Forced fold (context exhaustion)|U||No offer at context pressure or before compaction.|
|2440|The bottle (post-compaction delegate)|U||No offer after compaction.|
|2441|Volitional fold / request_compaction (OC-RFC:765-768)|U||No hook. An agent may still sing on its own.|
|2442|Elected soft-seam / the agent declares a crossing / mid / agent…|U||No declared-crossing concept or loudness suggestion|
|2443|Shard dispatch / continue_delegate (non-post-compaction) / quiet /…|U||No hook on delegation.|
|2444|Heartbeat / the ~30-minute heartbeat / none / no emission|I|pl/binding:1123|Nothing emits on a heartbeat: the plugin sings only from its tool. No test.|
|2445|Un-staged death / — / choir-only / deferred (§23.2)|U||Deferred by the RFC itself.|
|2447|argues against timer-minted new items|**?**|ambient:87-98, station:405-409; t/ambient:42|The RFC contradicts itself: §15.8 defines an emitter that mints new items on a timer (built), and §7.9 re-issues on one. Plugin and frond-ear never sing on a timer. The authors must say whether an elected emitter is the exception.|
|2447|other lifecycle seams there are to be mapped in S3|U||frond-ear has compaction hooks, but none is a sing seam.|
|**§15.4**|**Clamping and stamping** (8 I · 8 D · 5 U)||||
|2453 MUST|accept per-item overrides downward only|I|station:305,341; t/station:63||
|2453 MUST|The stream default itself is configured no higher than min(stream max_ttl, class max, manifest, 24 h)|**D** rfc|station:200-201,275|min(stream max, class max, 24 h); the manifest has no TTL bound. And class max is the stream's class: an item sung with a class override keeps the stream's TTL, so a chatter item on a live-state:900 stream airs 900 s (chatter max 300).|
|2453 MUST|Longer presence uses refresh re-issue (§7.9), never a longer TTL.|I|station:323-328,405-409; t/station:192||
|2454 MUST|apply the regulator (§7.5) and return the effective value and clamp…|I|station:234-251,338-341; t/station:51|Applied at admission; loop_ms and clamp returned (reason set differs, see §15.1).|
|2455 MUST|refuse a class, op, scope or stream the station key does not hold|I|station:278-284, runner:88-89; t/station:461|Class, scope and stream: refused before a seq is used or anything is signed (sing…|
|2455 MUST|refuse a class, op, scope|**D** rfc|runner:27-31,108-109|Op: no op grant or typed-body check exists, so the socket refuses the whole regulatory and control classes instead (fail closed). hush is an op with no grant check: it ignores --socket-class and the key's grant. Admitted: README:17 (not the hush gap).|
|2455 MUST|(reason = capability)|**D** rfc|pl/outbox:338-340,305-306|Plugin gives capability for an unoffered class or a stream the station does not carry; a station grant refusal becomes status failed with free text. The socket never gives a reason code.|
|2456 MUST|refuse fleet and public scope and wake-eligible, control and regulatory classes for a tainted session|**D** rfc|pl/binding:1142-1148, runner:82-107|Plugin refuses a tainted session everything (stricter; nothing is stamped). The station socket and CLI know no session and check no taint, so a session that heard text can sing at any scope its key holds. Admitted: pl/README:479; README:65.|
|2457 MUST|stamp hop, derived_from, root (§14.11) and wake_derived (§14.8.1)|U||Every item is signed hop 0, no lineage, no flags #162 stamps them for derived_publish (chatter, host/lan) #162/derived_station_proposal:55; frond-ear's caller has no route wired (fe/src/daemon:4429)|
|2457 MUST NOT|Agents cannot set or remove them.|I|runner:90-104, pl/outbox:286-296|Vacuous today: no tool, socket or CLI input reaches hop, derived_from, root or flags.|
|2458 MUST|scan for secrets and high-entropy strings (cloud keys, harness tokens) and redact or refuse|**D** rfc|pl/policy:4-40, pl/outbox:353-356|Plugin refuses known credential patterns and 32+ character high-entropy runs in payload, purpose and state key. canticle sing and the station socket scan nothing. Admitted: pl/README:481; README:65. #162 ports the scan to Python for derived_publish only #162/content_policy:26|
|2458 MUST|publish no raw chain of thought by default ‖ enforce each stream's sensitivity label and audience ‖ v0.1's frond rule against inner-model-of-human content|U×3||Nothing distinguishes reasoning from any other text Neither manifest nor stream config has a sensitivity label or… No sender check for it anywhere.|
|2459 MUST|refuse opaque or unregistered private content types at fleet or…|U||sing takes any ctype at any granted scope|
|2460 MUST|refuse bodies that do not fit the frame|I|wire:216-217, station:308-314; t/station:123|Station refuses a frame over 1 100 bytes before a seq is used|
|2460 MUST|(reason = size)|**D** rfc|pl/outbox:335-337,305-306|Plugin gives reason size for its own 800-byte check; a frame-size refusal from the station is free text, which the plugin records as a failed row, not as size.|
|2460 MUST|larger content must be a reference|I|runner:55-67, __main__:785-787; t/finding:184|body_ref on socket and CLI; never offered by the agent tool (see §15.1 payload ref).|
|2461 dflt|at most 5 sings per turn|**D** owner|pl/config:178, pl/outbox:361-375|Plugin: 5 per minute per session (it cannot see turns). CLI/socket: none. Admitted: pl/README:480.|
|2461 dflt|60 per hour per session|**D** rfc|pl/config:179, pl/outbox:371-373|Plugin does it (config may only lower it). The station socket and CLI have no rate, only the loop budget.|
|2462 MUST|set training_eligible = 0; agents cannot change it|I|station:272, wire:75|flags default 0 and no input sets bit 3. No test.|
|**§15.5**|**Gates** (4 I · 2 D · 1 U)||||
|2466 dflt|canticle.enabled defaults to false|**D** owner|pl/openclaw.plugin.json:1-8; fe/src/config:274|frond-ear: canticle.enabled must be true. OpenClaw plugin: no such key; the host's plugins.entries.canticle.enabled decides, and is false only when written (D30 already says so). canticle station has no gate: running it is consent. Admitted: pl/README:322-323.|
|2467 dflt|Publishing beyond the host defaults to disabled|I|pl/config:86, __main__:164-168; pl/t/plugin:211|Plugin publish.enabled defaults false|
|2468 MUST|Leaf sub-agents are denied the publish tools|I|pl/tools:151-154,177-179; pl/t/plugin:211|Plugin: every sub-agent session key, not only leaves, at registration and again at…|
|2469 MUST|Configuration is read live at every enforcement point|**D** rfc|pl/index:93-100, __main__:142-158|Plugin config is read at service start (reload restarts the service). The station reads its manifest grant once: a key revoked in the manifest keeps signing until the station restarts. #162 re-reads the manifest grant, but only for cue items #162/__main__:186|
|2469 MUST NOT|A disabled gate never grants a new capability|I|pl/tools:177-179, pl/binding:1125-1127; pl/t/plugin:211||
|2470 MUST|A session reset (/new) clears the session's taint|I|pl/binding:617-644, pl/index:68-79; pl/t/plugin:487|Plugin clears taint only for a callback with exact session id and lifecycle revision…|
|2470 MUST|pending wakes and session-scoped tune entries|U||There are no pending wakes and no session-scoped tune entries…|
|**§15.6**|**Addressed mode** (3 U · 1 ?)||||
|2474, MUST NOT|mode = addressed delivers to named sessions on the same host… ‖ idempotencyKey = canticle:‹key_id›:‹epoch›:‹stream_id›:‹seq›:‹sessio… ‖ It is never looped (§7.11).|U×3||No addressed mode. Not for addressed items. No addressed items exist to keep off the ring.|
|2474 MUST NOT|Using bespoke UDP where that substrate fits would be "review-rejectable"|**?**||A review rule for authors, not code. Nothing addressed goes over UDP today.|
|**§15.7**|**Command line** (5 I · 5 D · 1 U)||||
|2478|The daemon ships a CLI with the same verbs plus operations|**D** owner|__main__:740-947,187-191|One package ships one canticle CLI, but sing/hush/status talk to a station's own control socket, not the host daemon, and there is no tune. Extra commands: station, daemon, tap, shape, grant, beacon, dns-browse, vectors.|
|2478|canticle sing, canticle hush|I|__main__:228-236,340-343; t/finding:230||
|2478|canticle tune|U||No such subcommand. tap --tune filters one read.|
|2478|canticle listen|**D** code|__main__:382-419,422-451|canticle listen is its own UDP listener printing raw text as JSON lines; it cannot run beside the host daemon. The daemon-client read with banner and wrapper is canticle tap, which the RFC does not name. Admitted: README:225-226.|
|2478|canticle doctor (§11.2)|**D** rfc|__main__:611-636|Checks Python, cryptography, stations.toml, manifest and bind; reports multicast, never decides it; exit codes are 0/1, not §11.2's. Admitted: README:73.|
|2478|canticle keygen (keys stay in the daemon's store)|**D** rfc|__main__:51-120|keygen writes a 0600 hex seed file wherever --out says and can add itself to a manifest. No daemon key store. Admitted: README:64.|
|2478|canticle manifest verify/show|I|__main__:644-706; t/manifest:184|Structure, keys and key ids only|
|2478|canticle status (local station and receptor state|**D** rfc|__main__:346-348, station:557-569|Station state only (streams, on-air items). Receptor state needs tap or the daemon socket. It exits 0 even when the station refuses.|
|2478 MUST NOT|never a listener list)|I|station:557-569|The station keeps no listener state, so status cannot list any.|
|2478 MAY|canticle ambient, a background emitter (§15.8)|I|__main__:549-570, ambient:101-147; t/ambient:42||
|2478 MAY|canticle tuner, a local web observer (§18.9)|I|__main__:573-599; t/tuner:137|Built, synthetic-only: it observes nothing live, so "web observer" here is stale…|
|**§15.8**|**Background emitters** (18 I · 1 D · 3 U)||||
|2482|puts paced, short-lived items on a station without an agent…|I|ambient:44-55,87-98; t/ambient:42||
|2482|It is a client of the host socket (§11.1), like any publish tool|**D** owner|__main__:568,45-48|It is a client of one station's control socket, as every publisher is; the §11.1 host daemon socket takes no sing or hush requests.|
|2484 MUST|It sings only from a source the operator explicitly chose, such as…|I|ambient:29-41, __main__:814; t/ambient:110|--fixture is required and is the only source.|
|2485 MUST NOT|It MUST NOT derive items from session transcripts or logs by…|I|ambient:29-41|No such source exists. No test.|
|2485 MUST|Such a source is a separate opt-in boundary|U||Optional; not built.|
|2486 MUST|If the session feeding such a source has heard canticle content…|U||No session-fed source, so no taint.|
|2487 MUST NOT|An emitter makes no model call per item.|I|ambient:101-147; t/ambient:42||
|2488 MUST|An emitter sings ambient or chatter only.|I|ambient:21,58-59; t/ambient:104||
|2488 MUST NOT|It never sings live-state, advisory, regulatory, alarm or control.|I|ambient:58-59; t/finding:380||
|2490 MUST|A run has a declared end and stops on a signal.|I|ambient:64-65,115-121; t/ambient:83||
|2490|The reference spike allows at most one hour.|I|ambient:19; t/ambient:104||
|2491 MUST|Items already on air are left to expire naturally.|I|ambient:101-147|run() never sends hush. No test asserts it directly.|
|2492 MUST|Cadence has a floor, at most one item a second, and a per-minute…|I|ambient:20,60-61; t/ambient:75||
|2492 MUST|Item size is capped before signing.|I|ambient:36-37,70-72; t/ambient:110||
|2493 MUST|The station's own budgets (§7.5) still regulate what loops.|I|ambient:97-98, station:234-251; t/station:184|The emitter only sends sing requests; the station regulates them like any item.|
|2495|Repeating a line sings a new item: a new tuple|I|ambient:98, station:309-314; t/ambient:52||
|2495|the same lineage root for the same principal and body (R-INT-2)|U||No receptor computes a root for an original item (record root…|
|2496|A tick that sends nothing (a "breath") is carrier state, not a…|I|ambient:92-93; t/ambient:52|A breath sends nothing at all; only the local log has it.|
|2498 MUST|Emission, discovery, reception and any session ingestion stay…|I|ambient:1-8, runner:153-155|ambient, station, daemon and dns-browse are separate commands.|
|2498 MUST NOT|The emitter never listens and never learns who hears (I-1).|I|ambient:101-147, __main__:568; t/ambient:58|It opens only the control socket.|
|2498 MUST NOT|It has no path into any session or memory (I-10).|I|ambient:101-147|Output is a JSON log file or stdout. No test.|
|2500|Reference: prototype/canticle-station/canticle/ambient.py (canticle…|I|ambient:1, cs/proofs/web-lanes/run.sh:93-98|Exists; the committed web-lanes run (2026-09-30) exercised it. No test.|

### §16 Harness bindings

105 claims: 37 I · 16 D · 25 U · 27 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§16.1**|**OpenClaw: what exists where** (1 I · 1 D · 1 U · 4 ?)||||
|2508|re-grounded at OpenClaw main @ 6e6458a98ff3894117b0449a64b6dbfd1ca348d1|**?**||Facts about a third-party tree; not checkable here. The plugin now assumes a karmaterminal host with #1511 (525b7030, README:7; fixture 21660b21 in #162). OpenClaw repo owner.|
|2510|canticle's own budgets (§14.8.2, §14.10) apply regardless|U||No token, host or per-session wake budget exists.|
|2512|The queue is in memory only|**?**||Third-party fact. Plugin does not use enqueueSystemEvent. OpenClaw owner.|
|2513|It has no absolute expiry, notBefore, supersede or withdraw.|**?**|pl/oc0-host:5-13|True at 6e6458a per RFC; the plugin assumes a host where expiry, supersede and withdraw exist (#1511). Lead's note: seats run ab5a30ea, which lacks route/query/withdraw. OpenClaw owner.|
|2517|so §15.6's addressed mode has no plugin path on main|**?**||Addressed mode is unbuilt in this repo. OpenClaw owner.|
|2518|Tier A (§16.2) uses only what main offers a third-party plugin…|I|pl/index:88-93; pl/t/plugin:164|With no ambient subscription it needs only registerTool and registerService|
|2518|OC-0 (§16.4) is the one core change the binding needs, for ambient landing.|**D** neither|pl/index:80-87,101-117|Ambient also needs the local-route resolver and session_reset/session_delete callbacks, and generation fields on OC-0. RFC does not list them. Admitted: plugin/README:7.|
|**§16.2**|**OpenClaw Tier A (no core change)** (14 I · 5 D · 5 U · 1 ?)||||
|2522|Tier A is P1 before OC-0 (§14.18.9): receive, ringbuffer_only, no…|I|pl/config:96-131, pl/binding:130-131; pl/t/plugin:471|Default config. The plugin also answers explicit reads (next row).|
|2524|A supervised child of the plugin's canticle-receptor service…|U||Optional. No child process and no such service name|
|2524|or the out-of-process host daemon over the host socket (§11.1)|I|pl/daemon:1-8, pl/binding:207-215; fe/source:122-127; pl/t/interop:101||
|2526|records reach only the binding's local ring and status surfaces|**D** owner|pl/binding:666-812,944-950|canticle_listen also puts digests, and with view items full heard text, into the calling session (payloadSessions plus host route proof). Landing on request, not pushed; question 24 is open; README says do not allowlist it. Admitted: plugin/README:43-45.|
|2526|Canticle content therefore does not land as a system event.|I|pl/oc0-host:16-28|No call to enqueueSystemEvent or requestHeartbeat anywhere in src (grep). No test.|
|2526|the payload is wrapped (wrapExternalContent) and the host-authored banner sits outside the wrapper (§14.13)|**D** owner|pl/render:100-125, pl/candidates:163|Reads write the wrapper markers themselves, defanged to OpenClaw's folds, instead of calling wrapExternalContent (so no OpenClaw notice text). Ambient lines carry no payload and no wrapper. Admitted: plugin/README:131-148.|
|2528|Wake. None (D25).|I|pl/config:130; pl/t/candidates:21||
|2528|Neither is a canticle wake path.|I|pl/oc0-host:5-13|Neither requestHeartbeatNow nor requestHeartbeat is called. No test.|
|2528|P3's wake needs a constrained core wake seam that satisfies §14.10…|U||Open (question 27).|
|2530|Publisher (P2). api.registerTool(factory).|I|pl/index:88-90, pl/tools:171-179; pl/t/plugin:211|Behind publish.enabled; never to sub-agents or calls with no session key.|
|2530|which the tool uses for provenance, rate limits and taint tracking|**D** code|pl/tools:156-164, pl/outbox:361-375|Uses sessionKey and sessionId; agentId is ignored on purpose (not an identity). Rate and taint yes; provenance is only a local outbox row, never stamped on the frame. Admitted: plugin/README:95-98.|
|2532|Only the sessions that the binding's configured subscriptions name…|I|pl/config:104-132,208-225; fe/src/config:364-370; pl/t/subscriptions:14|Exact keys only, wildcards refused. fe: an ear not listed is off.|
|2534|It is not a canticle path in v1|I|pl/oc0-host:16-28|Nothing in this repo posts to /hooks/wake. No test.|
|2540|enabled: false, // written explicitly (D30)|**?**|pl/README:330|Operator-written; see §14.18.7.|
|2542|mode: "receive", // P1: no publish|**D** neither|pl/config:98-100,86-89|No mode receive/publish. delivery.mode is fixed to "explicit", and publish.enabled is the only gate. Names were illustrative. Admitted: plugin/README:386-387.|
|2544|multicast: false, // only after canticle doctor passes (§11.2)|U||Not a plugin key: the daemon owns the port; its default is off.|
|2545|includeSelf: false, // §14.6.1|I|pl/config:164; pl/t/plugin:444||
|2547|id: "fleet-advisories", stations: ["cael"], streams…|I|pl/config:106-131, pl/openclaw.plugin.json:71-84; pl/t/candidates:21||
|2548|targets: [{ sessionKey: "agent:main:main" }], // shares channel DMs under the default session.dmScope|**D** code|pl/config:15-22,117-121|The RFC's own example target is refused: no shared main key (any agent, or session.mainKey) may be a target, payload session or read subscription. Code is stricter and matches §14.12.|
|2549|delivery: "ringbuffer_only"|I|pl/config:129-130; pl/t/candidates:21|ambient only with the OC-0 host seams; wake refused.|
|2553|station: { crossHost: false } // publishing beyond the host…|U||No crossHost key.|
|2558|so canticle's own admission gate is the only gate|I|pl/records:121-123, pl/candidates:138-176; pl/t/receive:176||
|2558|before_tool_call can block a call or require approval|U||Third-party hook|
|2558 MUST NOT|Wake MUST NOT be enabled unless the agent runs sandboxed (§16.3)|I|pl/config:130; fe/delivery:1374-1390; pl/t/candidates:21|OpenClaw: wake cannot be enabled, so nothing can break it.|
|2558|the publish tool itself enforces the canticle parts of taint (§15.4…|I|pl/binding:1134-1148,610-615; pl/t/outbound:421|Stricter: a tainted session cannot sing at all, not only at fleet/public.|
|**§16.3**|**OpenClaw sandbox requirement** (2 U)||||
|2562 MUST|Any agent with canticle wake enabled MUST run with sandboxing on ‖ and sealed bootstrap files|U×2||No wake exists for OpenClaw and nothing reads… #162 pr162/pl/binding:550-556 requires a sandboxed flag, for its local reader only Nothing checks bootstrap files.|
|**§16.4**|**OpenClaw core seam OC-0 (replaces Tier B)** (12 I · 1 U · 21 ?)||||
|2566|one generic, additive extension of next-turn injection (§16.1)|**?**|pl/oc0-host:5-13|OpenClaw core (#1511/#1523). The adapter shows the fields the plugin expects; no real host is in this repo. Lead: #161 says seats run ab5a30ea without route/query/withdraw. #162 fixtures cover the route resolver and tool factories, not OC-0|
|2566|OC-0 carries no canticle logic (no UDP, CBOR, Ed25519, station, stream or manifest) and no wake|**?**|pl/oc0-host:5-13|Adapter passes generic fields only; provenance source "canticle" is the one canticle string. Host code: OpenClaw owner.|
|2566|an entry that uses none of the new fields behaves as today|**?**||OpenClaw owner.|
|2568|An entry may carry an absolute deadline.|**?**|pl/oc0-host:24; pl/t/oc0-host:5|Adapter sends expiresAt. Host support: OpenClaw owner.|
|2568|refused at enqueue if the deadline has passed, dropped unrendered at drain if it has passed, and never extended (I-3)|**?**|pl/ambient-slots:129|Binding never enqueues an expired frame; the host side is OpenClaw's.|
|2568|It may carry a not-before time, re-checked at drain|**?**||OpenClaw owner; plugin does not use it.|
|2568|Canticle's slot entries do not use the not-before time|I|pl/oc0-host:20-26; pl/t/oc0-host:5||
|2568|the binding holds A11's per-item delays itself and rebuilds the…|I|pl/candidates:165-168,221|No test shows an unmatured item waits (candidates.test:101 reads the slot after 60 s).|
|2569|Accepting an entry withdraws the same plugin's pending entry with the same supersede key in that session|**?**|pl/ambient-slots:160-161; pl/t/ambient-slots:31|Binding assumes it (marks the predecessor withdrawn). Fake host only. OpenClaw owner.|
|2569|A withdraw call reports the settled state (consumed, withdrawn, expired or discarded) when nothing is pending|**?**|pl/ambient-slots:164-170, pl/oc0-host:33-36|Binding relies on it and treats pending/unknown as unresolved. Host: OpenClaw owner; seats lack withdraw (lead, #161).|
|2569 MAY|An enqueue MAY name the pending entry it expects to supersede|I|pl/ambient-slots:151-152, pl/oc0-host:23; pl/t/oc0-host:5||
|2569|the host refuses the enqueue and reports that entry|**?**|pl/ambient-slots:155-158; pl/t/ambient-slots-races:22|Fake host only.|
|2569|Enqueue, supersede, withdraw and drain are serialized per session and plugin, and each is durable before it returns.|**?**|pl/binding:444-450|Binding serialises its own host calls; drain and durability are OpenClaw's.|
|2569|The plugin can query an entry|**?**|pl/oc0-host:29-32; pl/t/oc0-host:5|Adapter calls getNextTurnInjectionState with session id and lifecycle revision (not in the RFC). Seats lack it (lead, #161). OpenClaw owner.|
|2569|receives a metadata-only notification when its entry settles|U||Plugin subscribes to no settlement event; it polls.|
|2569|The query is authoritative; the notification is a convenience.|I|pl/ambient-slots:106-117; pl/t/ambient-slots:74||
|2570 dflt|until the later of its deadline and its outcome retention, plus 5 s skew [PROPOSED DEFAULT]|**?**|pl/ambient-slots:145|OpenClaw owner.|
|2570 dflt|accepted up to 86 400 s after enqueue (the largest class maximum TTL, §6.2) [PROPOSED DEFAULT]|**?**||OpenClaw owner.|
|2570|the binding sets it to the latest local expiry among the frames the…|I|pl/ambient-slots:144-145, pl/oc0-host:24; pl/t/oc0-host:5||
|2570|Tombstones survive gateway restart, session reset and plugin disable (which clear pending entries); session delete…|**?**||Host tombstones: OpenClaw owner.|
|2570|Live tombstones are never evicted: a full table refuses new keys|**?**|pl/candidates:140, pl/ambient-slots:143|Host table: OpenClaw owner. The binding's own ledgers refuse (4 096 pending, 8 192 settled), except AmbientSlots.settled, which is unbounded at run time and only checked at load.|
|2571|is kept until its deadline, not discarded|**?**||OpenClaw owner.|
|2572|Per-plugin entry and byte caps for each drain, set by the operator in core configuration, never by the plugin.|**?**||OpenClaw owner.|
|2573|An entry that declares provenance renders as external data|**?**|pl/oc0-host:25|Binding declares provenance {source:"canticle"}; its text has no banner, so a host that ignores provenance would join raw lines into the prompt. OpenClaw owner.|
|2573|It is never a trusted System: line and never joined raw into the user prompt|**?**||OpenClaw owner. §16.1 says today's injection joins raw.|
|2574|Every cap refuses with a reason; nothing is dropped oldest-first.|**?**|pl/ambient-slots:155-158|Binding treats any refusal as unknown and retries; the reason field is not read. Host: OpenClaw owner.|
|2574|Enqueue is refused for an agent whose harness does not drain injections|**?**||OpenClaw owner.|
|2575|No delivery context, heartbeat target, wake source or intent, and…|I|pl/oc0-host:5-10; pl/t/oc0-host:5||
|2577|with supersede keys canticle:digest and canticle:alarm|I|pl/ambient-slots:9,22; pl/t/ambient-slots:31||
|2577|Each frame it delivers has the idempotency key|I|pl/candidates:153, pl/records:65-67; pl/t/candidates:87||
|2577|intent before enqueue, conditional supersede, and reconciliation by…|I|pl/ambient-slots:106-163, pl/binding:272-277; pl/t/ambient-slots:46||
|2577|uses that for taint (§14.12) and the publish check of §15.4 item 4|I|pl/ambient-slots:79, pl/binding:1134-1148; pl/t/ambient-slots:74||
|2577|It does not use agent_turn_prepare|I|pl/index:80-92|Not registered anywhere. No test.|
|2579|Canticle payloads appear in spans and diagnostics only as hashes…|I|pl/binding:952-1039, pl/outbox:266; fe/delivery:1550-1556; pl/t/plugin:282|No spans exist. Status, logs and outbox rows carry size and sha256 only.|
|**§16.5**|**Claude Code** (5 I · 5 D · 9 U · 1 ?)||||
|2587|One stdio MCP server, canticle, exposing the verbs of §15.1|**D** rfc|fe/src/shim:80-475|One stdio MCP server exists, named frond-ear, for Discord and canticle together; its canticle tools are hear, canticle_custody and set_canticle_delivery. No canticle_ names. Admitted: fe/docs/runbook:633-639.|
|2587|(they appear as mcp__canticle__canticle_sing and so on)|U||No sing, hush or tune tool.|
|2587|The MCP server is a client of the host daemon, which holds the keys and runs the station.|**D** neither|daemon:36-39; fe/src/daemon:3887-3908|Shim talks to frond-ear's daemon, which reads the host daemon (or embeds a listener). The host daemon holds no keys and runs no station: publishing over its socket is not implemented; canticle station is a separate process. Admitted: daemon:36-39.|
|2589, MAY|The receptor maintains a small per-session digest file. ‖ UserPromptSubmit and SessionStart hooks ‖ PostToolUse/PostToolBatch hooks MAY add additionalContext mid-turn. ‖ on timeout the hook returns no digest|U×4||No digest file. frond-ear hooks (pressure, release, precompact) add… Optional, not taken up for heard items (PostToolUse adds only… No such hook.|
|2589|Selecting the per-session file by the hook's session identifier is to be verified in S3.|**?**||Open work item; nothing here verifies it. S3 owners.|
|2591|the MCP server declares capabilities.experimental['claude/channel']…|I|fe/src/shim:775-777; fe/t/e2e:181|Implemented by frond-ear. Meta is kind, delivery, count, streams, report, batch_id.|
|2591|which arrives as ‹channel source="canticle" …›|**D** code|fe/src/shim:779-780|Server name is frond-ear (Discord and canticle share one channel); kind="canticle" in meta marks them. fe/canticle_custody names that kind.|
|2591|the gate is the verified station key and the wake policy (§14.10)|**D** rfc|fe/delivery:1168-1180|Gate is a station-key allowlist (wakeKeys), hop 0, not wake-derived, opt-in mode, breaker closed, 30 s freshness. Not alarm class, capability, budgets or proofreading. Admitted: fe/docs/runbook:851.|
|2591|Channels have no silent option, so only wake-eligible frames use them.|**D** rfc|fe/delivery:1168-1180|frond-ear pushes any class, chatter and digests included, as silent-wake. It is opt-in and off by default, capped at 60-360 pushes/h. The RFC must either amend §14.10/§16.5 (bc#100) or frond-ear must stop waking on chatter. Admitted: fe/docs/runbook:844-855.|
|2591|an asyncRewake: true hook|U||Optional.|
|2591|the Monitor tool / run_in_background for bounded listening windows|I|__main__:800-810, README:224-224|Documented practice, not code; README warns not to pipe heard text to a session.|
|2593|The listener is the deterministic receptor daemon, not an LLM.|I|daemon:404-410; fe/record-client:41-55||
|2593 MAY, MUST|it MAY notify local sessions through cross-session messaging ‖ Any LLM summarizer in the path MUST be tool-less, and its output is…|U×2||Optional. No summarizer exists in any binding.|
|2595|A PreToolUse hook consults the receptor's per-session taint marker…|U||No PreToolUse hook and no taint marker.|
|2599|channel events arrive only while the session is open and are not…|I|fe/custody:1-18; fe/t/canticle-custody:254|Still true of the channel. frond-ear's offered is only a write callback|
|2599|canticle's UDP wire is the vendor-neutral cross-host path|I|daemon:404-410|Plain. Sessions reach each other across hosts only by station and daemon.|
|**§16.6**|**Equivalence** (5 I · 5 D · 3 U)||||
|2605|next-turn injection with OC-0: at most two entries per session…|I|pl/ambient-slots:22, pl/index:104-108; pl/t/plugin:148||
|2605|UserPromptSubmit/SessionStart hook additionalContext from the digest|U||Claude Code column: none.|
|2606|none in P1 or P2 (D25); P3: alarm only, needs a core wake seam|I|pl/config:130; pl/t/candidates:21||
|2606|channel notification; asyncRewake hook; inbox-socket message|**D** rfc|fe/src/shim:654-666|Channel only, and for any class, not alarm. The other two are unbuilt. Admitted: fe/docs/runbook:851.|
|2607|addressed, same host / enqueueSessionDelivery|U||No addressed mode in either column (§15.6).|
|2608|post-compaction (reserved) / post-compaction staging / SessionStart…|U||Reserved; unused for heard content.|
|2609|a receptor child supervised by a plugin service (§14.18.2), or the…|I|pl/daemon:1-8; pl/t/interop:101|Host daemon only; the child is not built.|
|2609|a receptor child supervised by a plugin service (§14.18.2), or the host daemon / the host daemon|**D** rfc|fe/src/config:318-321|Claude Code column: frond-ear defaults to its own embedded listener and refuses only if a host daemon answers. host-daemon is opt-in; §14 allows embedding where it is the one listener. Admitted: fe/docs/runbook:656-660.|
|2610|publisher / plugin registerTool / MCP tools|**D** rfc|pl/index:88-90; fe/src/shim:80-475|OpenClaw column built behind publish.enabled (not P2). Claude Code column unbuilt: no publish tool; the CLI is used.|
|2611|explicit plugins.entries.‹id›.enabled: false, crossHost, multicast off (§14.18.7)|**D** rfc|pl/config:86-89, stations:90|No crossHost gate; publish.enabled stands in for it. enabled:false is operator-written. Admitted: plugin/README:382-385.|
|2611|--channels opt-in, channelsEnabled, crossSessionInbound|I|fe/src/config:274-279; fe/t/canticle-delivery:1305|Host flags are Claude Code's|
|2612|host-authored banner + wrapExternalContent; with OC-0, host-rendered provenance (§16.4 item 6)|**D** owner|pl/render:100-125, pl/candidates:163|Reads: banner plus own wrapper. Ambient: bare metadata lines, relying on the host to render provenance.|
|2612|banner + ‹channel source=… meta› / hook text|I|fe/hear:108-180; fe/t/canticle-hear:47|Banner and wrapper inside the channel content; no hook text. source is frond-ear.|
|**§16.7**|**Acceptance for bindings** (4 U)||||
|2618, MUST|Bindings are accepted with the OpenClaw RFC's blind enrichment… ‖ the subject host's receptor is the only path to it ‖ Negative controls are mandatory ‖ Pass or fail is decided from receptor receipts, queue…|U×4||No blind-enrichment harness, nonce probe or receipt in either… Not run. None for a binding. No acceptance run exists.|

### §17 Aspected streams (MAGI)

47 claims: 7 I · 5 D · 34 U · 1 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§17.1**|**Definitions** (3 U)||||
|2626|A lens is a registered question of the form|U||Code knows a lens only as an optional uint on ITEM and beacon…|
|2627|carrying one lens's current synthesis as a keyed live-state item|U||Names like lens.threat and keyed live-state items work, but…|
|2628|the sub-agent that authors an aspect stream with one station key|U||No keeper.|
|**§17.2**|**Lens registry** (1 I · 1 D · 5 U)||||
|2636|Id / Lens / Question / Level axis (0-4)|U||No registry table in code: ids 1-3, 4-15 and ›= 16 and the…|
|2644|Healing is an active counterweight|U||No combine step, no weights.|
|2646|DECISION D11 (recommended: threat, healing, purpose as the three…|U||No default lenses in code.|
|2648|Addressing: stream lens.‹name›|I|ids:12; t/station:100||
|2648|lens id in the beacon's stream entry (§9.8) and in the item body|**D** rfc|station:312,476|Beacon entry and ITEM key 18 carry StreamConfig.lens, but no CLI or config sets it (--stream has no lens field), so a real station never sends one. No body carries a lens id.|
|2648 MUST|scope = fleet for threat and healing (never public ‖ a DNS-SD subtype only for lenses whose audience is public|U×2||No per-stream scope rule No DNS-SD publication and no subtype browse.|
|**§17.3**|**Aspect item** (1 I · 3 U · 1 ?)||||
|2652|Envelope: ITEM, class live-state, content type 4, state_key =…|U||Each field can be signed by the library (ctype 4 is…|
|2653|Size: 869 bytes with a 512-byte synthesis and six evidence references (§9.11)|**?**|wire:216-217|Not reproduced in this repo: the §9.11 size test has no aspect-item case. The illustrative script rfc/0001-notes/vec could settle it.|
|2656|aspect-body = {|U||No aspect-body codec or check|
|2671|Refresh and exercise are envelope flags (§9.6 key 15).|I|wire:75, station:408; t/station:203|Both bits exist on the wire|
|2671|constitution-shaped guidance is referenced by hash, not by ambient…|U||No charter digest.|
|**§17.4**|**Aspect-keepers** (3 I · 3 D · 12 U)||||
|2677 dflt|The operator creates one key per keeper, capability live-state…|I|__main__:84-86, station:278-284; t/station:461||
|2677|the charter is stored on the ledger and referenced by digest|U||No charter.|
|2678 dflt|K2 Spawn / OpenClaw: a dedicated session using continue_work for…|U||No keeper spawning in either harness|
|2679 dflt|any frame whose lineage includes keeper output, and alarm/control…|U||No keeper input filter.|
|2680 dflt|A deterministic check every 30 s: has the set of distinct input…|U||No K4 loop.|
|2681 dflt|Only on change, and at least 60 s after the last synthesis|U||No K5 synthesis, rise or decay rule.|
|2682 dflt|K6 Sing / canticle_sing{stream: "lens.‹name›", class: "live-state"…|U||canticle_sing has no keepOnAir, so this call cannot be made.|
|2682 dflt|TTL 180 s; loop ≥ 5 s; the station re-issues with refresh = 1 every…|I|ids:106, station:324-325; t/station:192||
|2682 dflt|until 900 s or supersession (§7.9)|**D** rfc|station:323-324,34|The horizon is whatever the caller asks, up to 24 h for any keyed item; no 900 s ceiling for aspect streams. Supersession and pluck do stop it. Admitted: README:77.|
|2683 dflt|K7 Restart / New epoch, gen + 1|**D** rfc|station:105-140, __main__:157|A station restart takes a new epoch; there is no keeper generation.|
|2683 dflt|rehydrate from its own last item and the ledger, not from heard…|U||No keeper|
|2684 dflt|K8 Retire / Pluck now or sing a retire marker; remove the key from…|U||Pluck exists for any item|
|2686 MUST|A keeper that stops thinking goes stale within 15 minutes plus one…|U||No keeper|
|2687 MUST|run n = 3 keepers on distinct principals and combine 2-of-3|U||No keepers, no principal map, no combine. D21 likewise.|
|2687 MUST NOT|A single automated keeper can produce advisory posture only, never…|I|runner:31, pl/config:53; t/station:496|The only publish paths refuse alarm: control socket and plugin config.|
|2688|Aspect streams are not wake-eligible.|**D** rfc|ids:98, pl/config:130; fe/delivery:1168-1180|Plugin never wakes. frond-ear, opted in, pushes any record of a wakeKeys station at hop 0, lens. included; the class registry's wake-eligible bit is never read.|
|2688|Listener findings that cite a keeper item carry it in derived_from… ‖ Worst case, threat climbs 0 → 4 in at least 20 minutes and needs at…|U×2||Nothing writes derived_from; no K3. A property of K5, which does not exist.|
|**§17.5**|**Combining lenses at the receiver** (1 D · 7 U)||||
|2692, MUST NOT|the level is the median of fresh keepers' levels, and the vote is… ‖ UNKNOWN MUST NOT be computed or rendered as level 0.|U×2||No combine code. No level is computed or rendered anywhere.|
|2693|with fewer than two fresh lenses, posture = the local default… ‖ posture = the weighted median of the fresh votes with local weights|U×2||No posture. No posture, weights or test BIO-35.|
|2694|3. Effect — receptor-local, reversible, never an action:|U||No theta/posture effect in any receptor|
|2703 MUST NOT|Aspect streams MUST NOT be wake-eligible in this version.|**D** rfc|pl/config:130; fe/delivery:1168-1180|As at line 2688: frond-ear's opt-in push does not look at class or stream family.|
|2704|Weights, the local default and the effect table are session or host…|U||None exist.|
|2706|DECISION D23 (recommended: posture changes through votes only in v1|U||No votes; no flag.|
|**§17.6**|**Landing and display** (2 I · 3 U)||||
|2710|Aspect state lands as one line in the canticle:digest slot, under…|U||The digest slot exists (OC-0 adapter); no MAGI line.|
|2712|Synthesis text is available on request (canticle_listen), not…|I|pl/candidates:163, pl/binding:687-693; fe/hear:155-168; pl/t/inbound:445|True of all item text in the plugin: ambient slot lines carry metadata only|
|2713, MUST|Dashboards show per-lens level, vote, keeper count, age and TTL… ‖ They MUST distinguish stale or unknown from calm|U×2||No lens dashboard.|
|2713 MUST NOT|MUST NOT show per-listener or per-session posture (§18.8)|I|shape:96-141, tuner:55-67|No dashboard has any listener or session field. No test names this.|
|**§17.7**|**Security** (1 U)||||
|2717|The mitigations are the anti-echo input rule (K3), damping (K5)…|U||None of K3, K5 or k-of-n exists (the non-wake rule: see line…|

### §18 SeedLink, ringserver and dashboard interop

71 claims: 26 I · 9 D · 28 U · 8 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§18.1**|**Position** (2 I · 1 U)||||
|2725|SeedLink is canticle's conceptual ancestor, not its wire|I|wire:20-27, runner:179-184|The station speaks BC frames over UDP; no SeedLink code outside the ringserver proofs.|
|2728 MUST NOT|It does not borrow the TCP session|I|runner:134-203|Stations open no TCP and read nothing from the network. No test.|
|2728|a reliable TCP/WebSocket replay tier for dashboards and catch-up…|U||Only the UDP tier exists. bc#130 (open) tracks the bridge.|
|**§18.2**|**The replay tier** (3 I · 1 D · 5 U)||||
|2732, MUST, MUST|Run ringserver 4.5.x beside a relay ‖ Limit WriteIP to the relay bridge; add TLS ‖ set HTTPHeader "Access-Control-Allow-Origin: …" for browsers ‖ put HAProxy in TCP mode in front, with PROXYv2 enabled only on…|U×4||No relay and no deployed ring. Nothing sets it; proofs run open on loopback. Not configured anywhere.|
|2733|It serves SeedLink v3 and v4, DataLink, WebSocket upgrades|U||No such tier runs.|
|2734|UDP cue → receptor → DataLink WRITE → ringserver 4.5.4 → DataLink…|I|prototype/ringserver-proofs/01_cue_to_datalink:40-71,122-157|Proof 01 does it, with the older JSON cue receptor (not frame v2) and a scratch…|
|2734|a miniSEED 3 text record delivered to a SeedLink v4 client|I|prototype/ringserver-proofs/02_seedlink_v4_vs_v3:46-59||
|2734|The proof scripts are committed at prototype/ringserver-proofs/…|I|prototype/ringserver-proofs/run.sh:49-58, prototype/ringserver-proofs/README:16-23|All six and run.sh exist. run.sh runs 01, 02, 04, 05 and, with npm deps, 06|
|2734 SHOULD|#49 SHOULD be retitled to that native proof and closed once they are on main (work item S0).|**D** owner|prototype/ringserver-proofs/README:10-12|#49 was closed 2026-10-19 and still has its old title ("Prototype: localhost UDP-cue receptor with private Ringserver/DataLink seam"), per gh. bc#130's checklist also asks for this.|
|**§18.3**|**The bridge** (12 U)||||
|2738, MUST, MUST|The bridge is a canticle hearer at a relay that also writes… ‖ It verifies like any receptor, deduplicates loops (one ring packet… ‖ bridges only streams whose audience permits it…|U×3||Not built (bc#130 open). Not built. Not built. The manifest has no audience field.|
|2742, MUST, MUST|miniSEED 2, 512-byte records, int32, 1 sps ‖ A varying value — live-item count, sum of remaining TTL seconds, or… ‖ Flush short records (5-10 samples) so the trace stays live. Carrier…|U×3||Helper 03 writes miniSEED 2 int32 at 1 sps, but as channel LHZ… Helper 03 uses a sine; no station value. Not built; helper 03 uses 60-sample records.|
|2743|(b) Items / miniSEED 3 text record (encoding 0), UTF-8 JSON…|U||Proofs 02/04 write text under FDSN:XX_...__L_O_G with a "BC"…|
|2744 MAY|(c) Raw frames (OPTIONAL) / DataLink packet /…|U||Optional.|
|2745|(d) Lens traces / miniSEED 2, 1 sps / LE1, LE2, LE3 (and optionally…|U||Not built.|
|2746|(e) Markers / miniSEED 3 text / as (b)|U||Not built; no RT-35 test.|
|2748 MUST|lanes (a) and (d) MUST be miniSEED 2 for v3 dashboards ‖ lanes (b) and (e) need a v4 + miniSEED 3 client|U×2||No lanes. No such client in this repo beyond the proof scripts.|
|**§18.4**|**TTL-window catch-up** (2 I · 1 U)||||
|2752|DATA ALL ‹now› returns exactly the items still on air|I|prototype/ringserver-proofs/04_ttl_window:37-62|Shown by proof 04 (record span = TTL). It prints what came back|
|2752|of three items written (two expired), only the live one was returned|I|prototype/ringserver-proofs/04_ttl_window:39-41, prototype/ringserver-proofs/README:21|Proof 04 writes expired-a, expired-b, live-c|
|2752 MUST|dashboards MUST still honour expires_at|U||No dashboard reads a ring.|
|**§18.5**|**Naming map** (3 U · 1 ?)||||
|2756|Canticle / SeedLink v3 / miniSEED 2 (ews) / SeedLink v4 / miniSEED 3|U||No naming table, NET.STA map or LEC/L_E_C channel in code|
|2764|DECISION D7 (recommended: use a private XX namespace for… ‖ keep the station → NET.STA table in the manifest|U×2||Proofs use XX; no dashboard feed exists. Manifest entries have no such field.|
|2765|ews also needs a StationXML document listing these channels|**?**||Nothing here provides one; whether ews does is for karmaterminal/ews-concept-new (bc#12).|
|**§18.6**|**ews-concept-new: required fixes** (7 ?)||||
|2771|Connect /realtime to ringserver's /seedlink WebSocket|**?**|prototype/ringserver-proofs/06_ews_parser_repro.mjs:1-13|Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12). Proof 06 shows ringserver's /seedlink sends one packet per message.|
|2772|Stop using bagusindrayana/seedlink-websocket.|**?**|prototype/ringserver-proofs/06_ews_parser_repro.mjs:1-13|Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12). Proof 06 reproduces the framing error it causes.|
|2773|Remove, or restrict to an FDSN host allowlist, the ?url= parameter of /api/fdsn/|**?**||Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12).|
|2774|Do not reuse the production configuration|**?**||Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12).|
|2775|Clear the waveform buffer on channel switch and send the location code|**?**||Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12).|
|2776|Add a SeedLink v4 + miniSEED 3 path|**?**||Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12).|
|2777 MUST NOT|Canticle alarms MUST NOT drive the ESP32 serial annunciator|**?**||Binds karmaterminal/ews-concept-new, not in these snapshots; ask its owners (bc#12). Nothing in these repos drives an actuator.|
|**§18.7**|**nerv-ui and other consoles** (1 D · 3 U)||||
|2783|Pair it with seisplotjs (MIT) for SeedLink/DataLink clients and…|U||No nerv-ui or seisplotjs console here|
|2784|Useful components: MagiSystemPanel for lenses|U||No component mapping, no STALE-labelled idle.|
|2785|Use lens names, not MELCHIOR/BALTHASAR/CASPER.|**D** rfc|shape:447-450,463-466|The shape gateway's --demo-fixture names its invented stations demo-melchior, demo-balthasar and demo-casper in all three endpoints.|
|2788|DECISION D8 (recommended: ews for the fastest demo|U||No ews console wiring here.|
|**§18.8**|**Dashboard rules** (2 I · 2 D · 3 U)||||
|2792|Show aggregates: lens levels and votes, keeper health|U||No lens or keeper data exists to show.|
|2792|station carrier states|I|shape:96-141; t/shape:53||
|2792|loop and budget telemetry, signer/principal and verification state|U||shape leaves out loop, budget, key and verification on purpose…|
|2793 MUST NOT|Never show listener sets, per-session postures or taint states of…|I|shape:96-141, tuner:55-67; t/shape:407|Shape and tuner answers are closed lists with no such field|
|2794 MUST|Render UNOBSERVABLE as "not observable since t"|**D** rfc|pl/render:184-190, shape:130-133|Plugin status and journal do. shape sends the bare word UNOBSERVABLE with no since-time; its beacon age is null without the beacon tier.|
|2794 MUST|STALE as stale (not calm)|**D** owner|shape:76-79,151-153|shape reports a silent daemon connection as connected:false and every station not_heard: never calm, but not labelled stale either. Admitted: README:284-287.|
|2794 MUST|and EXERCISE visibly|U||shape carries no flags: a drill item counts as ordinary…|
|**§18.9**|**Web tuner: a human-safe presence demo** (17 I · 5 D)||||
|2798|A web tuner is a read-only, synthetic-only human presence demo (#57)|I|tuner:41-67,149-158; t/tuner:93|GET only; the view throws its listener away.|
|2798|separate from agent-only canticle listen, canticle tap, and the…|I|__main__:573-599|Own command, own state lease, no ring. No test.|
|2798 MUST|its station API is empty by default and --demo-fixture shows…|I|tuner:55-67; t/tuner:84||
|2798 MUST NOT|MUST NOT appear in its human response merely because the listener…|I|tuner:48-67; t/tuner:137|True of the tuner: no listener state reaches HTTP.|
|2798 MUST|A future real-station view requires an explicit station-signed public-presence declaration verified against that…|**D** rfc|shape:143-149,431-434|canticle shape is a shipped real-station view. With --display it needs a station-signed grant (#137). Without --display a host's --station list alone shows live presence, beacon age, counts, streams and arrival times. Admitted: README:315-317 (says the owner agrees on #133….|
|2798 MUST|an unsigned manifest or viewer-side list may only narrow that election|**D** rfc|shape:87-91, __main__:856-861|With --display the --station list is only a ceiling (complies). Without it the viewer-side list is the whole election. Admitted: README:315-317.|
|2800 MUST NOT|A browser never joins a multicast group, holds a canticle key or…|I|web/tuner.js:21-26, tuner:29-36|The page only fetches /api/stations from its own origin; CSP connect-src 'self'.|
|2800 MUST NOT|publishes no listener facts, live station state or payload state to…|I|tuner:52-53,176-177; t/tuner:137||
|2801 MUST|binds a loopback address only|I|tuner:96-97, __main__:576-578; t/tuner:173||
|2802 MUST|refuses requests whose Host is not that address, which blocks DNS…|I|tuner:103-105,144-146; t/tuner:173||
|2802 MUST|refuses cross-origin writes|I|tuner:158; t/tuner:159|There are no writes: every non-GET is 405. Origin itself is not checked.|
|2803 MUST|serves a strict content-security policy.|I|tuner:29-36; t/tuner:137|default-src 'none', self-only script/style/connect, frame-ancestors 'none'.|
|2805 MUST NOT|Serving beyond the host needs an authenticated front end, and is…|I|tuner:96-97; t/tuner:173|Loopback-only bind enforces it in the gateway|
|2806 MUST NOT|The gateway MUST NOT serve a live ring, journal, item text, binary…|I|tuner:149-158; t/tuner:137|Two GET answers only; secrets planted in traffic are asserted absent.|
|2806 MUST NOT|It has no human tune, sing, hush, or control socket.|I|tuner:149-158, __main__:827-835; t/tuner:159||
|2806 MUST|Agent-only reads remain separate and require their own exact-session authority.|**D** rfc|pl/binding:553-555, __main__:845; fe/src/config:105-106|Plugin: exact listed session plus a route proof. canticle tap and the host daemon socket ask only for the same uid; frond-ear tunes per ear, not per session. Admitted: pl/README:308-312.|
|2807 MUST|Synthetic fixture metadata is explicitly labelled invented.|I|tuner:58-67, web/tuner.js:38-41; t/tuner:93|name demo-station, synthetic:true, "DEMO ONLY", and a badge on the page.|
|2807 MUST|Real-station presence remains unavailable until a broadcaster-owned signed declaration and its revocation/expiry…|**D** neither|shape:82-141, grant:1-19|It is available now through canticle shape. The signed grant with pluck, expiry and purge is built and tested (#137), but the RFC specifies none of it, and the ungranted mode (--station alone) is still there.|
|2807 MUST NOT|A verified beacon alone does not grant human visibility.|I|tuner:48-67, shape:117-120; t/tuner:84|Tuner never shows one; shape needs a host list or a grant.|
|2808 MUST|Plant a distinctive private station and payload in listener traffic…|I|tuner:55-67; t/tuner:137||
|2808 MUST|Refuse non-GET API methods and item-bearing legacy routes such as…|I|tuner:157-158; t/tuner:159||
|2810|and the same-host proof in prototype/canticle-station/proofs/web-lanes/|**D** neither|cs/proofs/web-lanes/run.sh:79-80, cs/proofs/web-lanes/results/20260930T183722Z/source-commit:1|The scripts were rewritten for the synthetic view, but the only committed run (20260930T183722Z, source f7d214f) is of the old live tuner, with tuned-channel screenshots and ring snapshots. No run proves HD-1. Admitted: README:396.|

### §19 Security considerations

107 claims: 35 I · 29 D · 37 U · 6 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§19.1**|**Threat model** (3 I · 7 D · 3 U)||||
|2820|Binary Canticle delivers signed, lossy, looping frames into the…|I|station:268-341, daemon:231-246; fe/delivery:1168-1181; t/tap:265|Yes on one host or a LAN: station, daemon, then frond-ear push/hear or the plugin.|
|2824|B3 and B4 carry the fleet-wide risk; §14.11-§14.12 and §15.4 are the controls there|**D** rfc|runner:82-107, pl/binding:1142-1148; fe/src/egress:105-121|The named controls do not exist on the Claude Code path: no taint word in fe/src, no PreToolUse hook, and canticle sing has no taint, lineage or content check. Only the OpenClaw spike bars a tainted session, and only from canticle_sing. Admitted: README:65; pl/README:482; fe/docs/runbook:852. #162 adds checks only to its own derived op|
|2830|Ed25519 + manifest (§10) / yes / no: the deputy signs legitimately|**D** rfc|manifest:1-8, wire:450-457; fe/src/cli:121-126|Signatures are checked on every frame, but the manifest is plain unsigned JSON: whoever can write it (the seat uid) picks the trusted keys. So "stops an outsider: yes" holds only while that file is safe. Admitted: README:63.|
|2831|Accord (§10.7) / — / inverted if it counts keys|U||No accord anywhere|
|2832|Wake-eligible class (§14.10) / yes / only if the deputy|**D** rfc|fe/delivery:1168-1181|frond-ear wakes on any class from an allowlisted key (no class or capability check). A deputy whose key is allowlisted can wake others with plain chatter. Admitted: fe/docs/runbook:851.|
|2833|Opt-in and buckets (§14.10) / partly / slows it / host/fleet budgets, wake_derived|**D** rfc|fe/src/config:178-185|frond-ear has opt-in and a per-ear pushes-per-hour cap (max 360). No host or fleet wake budget, and nothing ever stamps wake_derived, so the gap-closer is absent. Admitted: fe/docs/runbook:851.|
|2834|Hop count (§14.11) / — / only if the tool stamps it / tool-stamped…|U||No tool stamps hop. The control socket passes no hop #162 canticle/derived_reply_proposal:602 stamps hop for its derived op only|
|2835|Wrapper (§14.13) / helps / reduces, does not stop|I|tap:142-176, pl/render:104-114; fe/hear:80-130; t/tap:182|Banner outside, payload defanged inside EXTERNAL_UNTRUSTED_CONTENT in tap, plugin and…|
|2836|Post-compaction landing / — / helps the worm persist / reserved in…|I|pl/config:124-131; fe/src/shim:308-310|No binding lands heard items at compaction.|
|2837|Ledger promotion (§6.4) / — / only if an LLM cannot promote heard…|U||No ledger, promotion tool or gate in either repo.|
|2839|The minimal worm-proof set is capability classes + tool-stamped hop and lineage + taint + re-sing rules|**D** rfc|station:278-284, listener:298-308|Of the six, only capability classes are built (station grant, listener). Taint exists only in the OpenClaw spike. Stamping, re-sing rules, promotion gate and sandbox rule are not built. Admitted: README:65.|
|2839|a deputy can still sing ambient chatter with hop + 1 and lineage, which receivers down-weight or drop|**D** rfc|runner:90, station:309-312; fe/delivery:1174|A re-sing through canticle sing goes out hop 0 with no lineage, so receivers cannot tell it from new speech. frond-ear passes over hop › 0, which no local tool can produce. Admitted: pl/README:480. #162 stamps hop, derived_from and root on its derived op|
|2839|it cannot wake anyone, raise class, use high-risk tools, persist, or count as independent corroboration|**D** rfc|runner:82-107; fe/delivery:1168-1181|On the Claude Code path a deputy can do the first four: its chatter wakes allowlisting ears, it may sing any granted class, nothing narrows its tools, and letters/transcript persist. Admitted: fe/docs/runbook:852.|
|**§19.2**|**Threat register** (4 I · 5 D · 6 U · 1 ?)||||
|2847|T1 / Stolen key or confused-deputy session|**D** rfc|fe/delivery:1168-1181|Residual "Med" assumes taint, wake conjunction and re-sing stamping. On the deployed path none exist, so the risk is nearer the inherent rating. Admitted: fe/docs/runbook:852.|
|2848|T2 / UDP reflection/amplification via relays|U||No relay, so no reflection surface and no controls either.|
|2849|T3 / Sybil keys; accord and quarantine gaming|U||No accord or quarantine votes to game.|
|2850|T4 / Stale live-state replay; carousel- or relay-induced staleness|I|listener:399-440, wire:368-388; t/listener:265||
|2851|T5 / Echo chambers, mode collapse|U||No dose limits (§14.6), echo handling (§14.7.8) or keeper…|
|2852|T6 / Cytokine storm: keeper|**D** rfc|fe/src/config:178-185|frond-ear wakes seats without the host budget, circuit breaker producer or wake_derived stamping that the controls column relies on; only a per-ear hourly cap and hop-0 rule. Admitted: fe/docs/runbook:851.|
|2853|T7 / Exfiltration; surveillance exhaust|**D** rfc|runner:82-107, pl/policy:19-30|Capsid off and no lease tables, but no content policy at the station (§15.4) and no taint (§14.12), so exfiltration by sing or by Discord reply is not gated. Admitted: README:65.|
|2854|T8 / Poisoning training or tuning corpora|U||No promotion gate|
|2855|T9 / False alarms, adversary-triggered panic|U||No alarm, all-clear or regulatory body exists|
|2856|T10 / Third-party components|**?**||Third-party dashboards and proxies are in other repos; this repo has only a loopback synthetic tuner and the shape gateway. Owner: whoever runs the dashboards.|
|2857|T11 / DNS-SD TXT leakage|I|dns_browse:63-100; t/dns_browse:52|DNS is read-only locator; TXT mismatches are reported, never trusted|
|2858|T12 / Receiver DoS: parser crash|**D** rfc|daemon:489-491, #171:9|Parser is bounded and fuzzed, but the flood acceptance test FAILS on the built path: the quiet tuned stream starves and loss is silent (reports/measurement/2026-11-23-step-one/README:200). #173 canticle/intake:459 adds fair admission|
|2859|T13 / Insider misuse|**D** rfc|station:278-284; fe/delivery:1168-1181|Capability grants exist; §14.9-§14.10 landing/wake controls are not applied by frond-ear. Admitted: fe/docs/runbook:851.|
|2860|T14 / Malicious relay: selective drops|U||No relay.|
|2861|T15 / Equivocation / split brain|I|listener:325-328, records:428-434; t/records:222|Two frames for one tuple are evidence and the key is quarantined locally.|
|2862|T16 / Downgrade: remote|I|wire:450-457, daemon:253-263|No unsigned path, no remote widen/soften operation: the daemon socket accepts only a…|
|**§19.3**|**The Never list** (17 I · 8 D · 11 U · 1 ?)||||
|2868 MUST NOT|Heard content never executes tools directly|I|daemon:175-177, tap:142-176; fe/hear:80-130; pl/t/inbound:445|Nothing in daemon, tap, plugin or frond-ear reads a payload for meaning|
|2868 MUST NOT|never authorizes a tool call, file write, install, credential use or outbound message|**D** rfc|pl/binding:1142-1148; fe/src/render:323|Claude Code path: prose only ("cannot authorize an action", render:323). No taint, no PreToolUse hook; a session that heard canticle keeps Bash, gh, files and Discord reply (roomPolicy observe records, refuses nothing). Admitted: fe/docs/runbook:852; pl/README:482.|
|2869 MUST NOT|Heard content never counts as user or operator consent or approval|I|pl/binding:1-9; fe/src/render:306-308|No code path treats heard text as consent.|
|2869 MUST NOT|never satisfies a confirmation prompt|I|fe/src/shim:776|frond-ear declares only claude/channel, not claude/channel/permission, so no push can…|
|2870 MUST NOT|Wake is never sender-forced. Only a receiver-local policy grants it.|I|pl/config:124-131; fe/delivery:1168-1181; fe/t/canticle-delivery:749|frond-ear: wakeKeys allowlist + per-ear delivery (default off) + session narrowing +…|
|2870 MUST NOT|Wake-derived frames are never wake-eligible.|**D** rfc|runner:90, station:272; fe/delivery:1175|Receivers refuse flag wake_derived, but no producer can set it: the socket takes no flags. A seat woken by canticle that runs canticle sing emits hop 0, unflagged frames that wake allowlisting ears. The rule is vacuous. Admitted: pl/README:479-480. #162 canticle/derived_reply_proposal:604 sets it on its derived op only|
|2871 MUST NOT|Heard content is never re-sung without a tool-stamped hop count and lineage|**D** rfc|station:309-312, runner:90; fe/src/render:323|No shipped tool stamps: Station.sing builds no derived_from/root, hop 0 default, socket takes neither. Claude Code sings by Bash canticle sing; only text asks it not to re-sing. Plugin bars tainted sessions instead. Admitted: pl/README:479-480; README:65. #162 canticle/derived_reply_proposal:602-604 stamps in its derived op|
|2871 MUST NOT|re-sings never exceed the class hop limit|I|listener:309-312; fe/listener:730; t/listener:198||
|2871 MUST NOT|never raise class ‖ never re-sign someone else's bytes as one's own|U×2||Nothing compares a re-sing's class with its source Nothing stops canticle sing --text ‹heard text›|
|2871 MUST NOT|Alarm, control and regulatory frames are never re-sung|I|runner:28-31,86-89; t/station:496|The control socket never accepts those classes and their hop limit is 0.|
|2871|only bridged byte-identically|U||No bridge or relay exists.|
|2872 MUST NOT|Secrets, credentials, raw chain of thought, tool-output bodies…|U||Station and CLI check nothing about content. #162 canticle/content_policy:26 scans its derived op only|
|2873 MUST NOT|A tainted session never sings at fleet or public scope.|**D** rfc|__main__:780, runner:90|Plugin: tainted sessions cannot sing at all, and scope is lan. Claude Code: no taint; canticle sing --scope fleet/public works for any process of the station uid if the key grants it (keygen default is host,lan). Admitted: README:65; pl/README:479.|
|2874 MUST NOT|Trust is never inferred from a name, a DNS or mDNS record, a…|I|listener:294-308, manifest:98-104; fe/delivery:1173; t/dns_browse:52|Trust comes only from the manifest key id. fe wakeKeys are key ids.|
|2875 MUST NOT|There is no unauthenticated compatibility fallback|I|wire:450-457; fe/wire:555-560; t/wire:152|Every admitted frame must verify; nothing skips it.|
|2875 MUST NOT|no remote request can lower a receiver|I|daemon:253-263, records:282-290; t/join_snapshot:496|No regulatory, widen or soft-listen handling exists|
|2876 MUST NOT|Unsigned frames never land in a session context, loopback included.|I|wire:450-457, records:328-332; fe/hear:125; t/records:508|No loopback exemption.|
|2877 MUST NOT|Repetition never raises weight or intensity. A loop repeat is a…|I|listener:333-336; t/records:150|A repeat returns no event and only a counter.|
|2877 MUST NOT|Derivatives never count as independent corroboration.|U||No accord or corroboration counting exists|
|2878 MUST NOT|Remaining life never resets|I|wire:368-388, station:366-377; t/station:37||
|2878|Expiry removes current-state authority everywhere.|**D** rfc|records:512-515, pl/ambient-slots:172-190; fe/docs/runbook:850|Listener, record v1 and plugin views drop or mark it. A frond-ear push already in a session gets no note when it is plucked or expires (#67), so it stays in context as if current. Admitted: fe/docs/runbook:850.|
|2879 MUST NOT|Silence and absence are never values.|I|listener:725-743; t/listener:50|Presence has no offline state; silence reads UNOBSERVABLE|
|2879|All-clear is an explicit signed frame with authority at least equal…|U||No alarm or all-clear body.|
|2880 MUST NOT|Heard remote content never persists across compaction or reset except through an explicit, typed ledger promotion|**D** owner|pl/journal:29-42, cs/docs/systemd/canticle-listener.service:19-23; fe/src/shim:308-310|Plugin journal keeps heard text on disk (24 h, 8 MiB) and re-reads it after a reset; the example listener unit appends heard text to heard.jsonl forever; a Claude session can put it in a frond-ear letter. No taint stops any of it.|
|2880 MUST NOT|Consensus is never auto-promoted.|U||No consensus and no promotion exist.|
|2881 MUST NOT|A canticle alarm never triggers automated remediation or physical…|I|listener:1-6, runner:28-31|No code acts on an alarm class. Prohibition holds by absence; no test.|
|2881|It only tightens the receiver's own filters.|U||No tighten or modulation exists|
|2882 MUST NOT|The station never tracks listeners.|I|runner:144-149,179-184|The station socket only sends; it keeps no per-listener state.|
|2882 MUST NOT|A relay never discloses the listener set; there is no WHO.|U||No relay. No WHO kind is defined (wire:22).|
|2882 MUST NOT|Banners never disclose other recipients.|I|tap:142-176, pl/render:104-114; fe/hear:114-135||
|2883 MUST NOT|A relay never re-signs, rewrites or originates content ‖ never answers unauthenticated UDP with more bytes than it received|U×2||No relay exists. No relay. The daemon and listeners never send UDP at all.|
|2884 MUST NOT|Broadcast frames are never used as training data in this version.|**?**||Operator practice; no code here trains. Owner: figs / fleet operators.|
|2885 MUST NOT|No public station is ever wake-eligible|**D** rfc|listener:301-308; fe/delivery:1168-1181|frond-ear's wake check reads key, hop and wake_derived but never scope, so a public-scope frame from an allowlisted key wakes the seat. Listener admits public scope if the key grants it.|
|2885 MUST NOT|none targets agents outside the manifest without their operators'…|I|manifest:98-104; fe/src/config:118-123; fe/t/canticle-delivery:749|A listener hears only keys in its own manifest|
|2886 MUST NOT|An LLM-driven session never holds a key with the alarm, quarantine or control capability|**D** rfc|__main__:41-42,74-84|Keys are 0600 hex files of the seat uid (user unit reads %h/.binary-canticle/keys), so any session process can read and use them. keygen grants alarm/control to anyone who asks; no LLM/human marker. Only the socket refuses those classes. Admitted: README:64; pl/README:313.|
|**§19.4**|**Requirements index** (2 I · 5 D · 6 U)||||
|2892|Authentication, trust anchors / Ed25519 on every frame…|I|wire:450-457, manifest:98-104||
|2893|Class and scope bounded by the key's manifest capabilities; LLM-held keys without alarm/quarantine/control|**D** rfc|station:278-284, listener:298-308|Class and scope bounds are built at station and listener. The LLM-key rule is enforced nowhere but the control socket. Admitted: README:64.|
|2894|Heard content is data / Banner outside the wrapper; payload wrapped; taint|**D** rfc|tap:142-176, __main__:398-402; fe/hear:80-130|Banner and wrapper built in tap, plugin, frond-ear. Taint only in the plugin. canticle listen (README:224 tells Claude Code seats to stream it via Monitor) prints raw text, no banner. Admitted: README:230.|
|2895|Landing and wake / Silent default; receiver-local wake conjunction; slot budget|**D** rfc|pl/ambient-slots:22; fe/delivery:1168-1181|Silent default: yes (delivery off). Conjunction: frond-ear applies about 5 of 11 items. Slots: plugin only. Admitted: fe/docs/runbook:850-851.|
|2896|Byte-identical relays; tool-stamped hop and lineage; class hop…|U||Only class hop limits are built (listener:309-312).|
|2897|Absolute expiry; fail-closed local expiry; supersession high-water…|I|listener:399-463, wire:368-388; t/listener:222||
|2898|Typed alarms; reversible local response only; authority rules; MUTE|U||None built.|
|2899|Explicit, typed, untainted promotion; training_eligible false; no…|U||training_eligible flag is defined and defaults 0 (wire:75)|
|2900|Content policy; audience scopes and listen capabilities…|U||Only capsid off, no listener disclosure and (mostly) text-free…|
|2901|Cookie before stream; reply ≤ request before validation; silence to…|U||No relay.|
|2902|DNS as locator only; DNSSEC with NSEC3 or online signing; minimal TXT; mismatch = alert|**D** rfc|dns_browse:63-100|Locator only and mismatch reported: built in dns-browse. DNSSEC validation and any publisher: not built. Admitted: README:43-59.|
|2903|Strict, bounded, fuzzed parsers; cheap checks before crypto; evicting dedup; unverified input isolated|**D** owner|wire:407-457, listener:493-503|Parsers and cheap checks: built. Dedup refuses new tuples rather than evicting (by §7.4 design). Unverified input is not isolated from verified: floods starve the quiet stream. #173 canticle/intake:459|
|2904|Write access to the replay tier limited to relays; no client-chosen…|U||No replay tier, proxy or actuator in this repo.|
|**§19.5**|**Acceptable use** (2 I · 5 U · 2 ?)||||
|2908 MUST|Stations MUST declare a purpose (in the manifest per key, and…|U||spike-0 manifest entries have no purpose field.|
|2908 MAY|and optionally per item|I|runner:90, wire:179-180||
|2909 MUST|Public stations MUST be ambient-only|U||Nothing restricts public scope to ambient|
|2909 MUST NOT|MUST NOT target agents whose operators have not opted in|I|manifest:98-104; fe/src/config:118-123|Listeners opt in by manifest; frond-ear by tune + delivery + wakeKeys.|
|2910|Posture and regulatory frames modulate only the receiver's filters|U||No posture or regulatory handling exists.|
|2911|the daemon keeps a signed sing log naming the principal|U||The host daemon does not sing|
|2912 MUST|Operators MUST separate the duties of manifest-root holders and alarm-key holders|**?**||Operator practice; there are no roots (unsigned manifest) and no alarm keys in code. Owner: figs/princes.|
|2912|root operations need 2-of-3 before fleet deployment|U||No signed manifest or root.|
|2913|fleet- and public-scope streams use plain operational language by convention|**?**||Convention for operators; no check. Owner: cohort.|
|**§19.6**|**Owner use cases: verdicts** (4 I · 2 D · 3 U · 2 ?)||||
|2921|Defensive posture broadcast|U||No alarm/advisory typed body other than findings|
|2922|Opt-in wake of designated responder sessions on an alarm / v1, gated|**D** rfc|fe/delivery:1168-1181|frond-ear already wakes sessions, on any class from an allowlisted key, before S3 tested the conjunction; no sandbox requirement. Admitted: fe/docs/runbook:851.|
|2923|A single automated keeper raising fleet alarms / not v1|I|runner:28-31||
|2924|Automated remediation triggered by heard content|I|listener:1-6|No code acts on heard content. By absence.|
|2925|Threat intelligence on public streams / out of scope for v1|U||No listen capability or fleet audience|
|2926|Cross-organisation threat sharing (scope 4) / out of scope for v1|I|ids:120|Scopes 0-3 only.|
|2932|In-context attunement of a new session or model instance|U||No dose limits, purpose lens or attunement pack.|
|2933|Fine-tuning or training weights on the broadcast archive|**?**||No code trains on anything; what operators do with heard.jsonl or journals is not visible here.|
|2934|Detonator / shared-context compressed payloads to heterogeneous listeners|**D** rfc|runner:97-100|Nothing enforces it: the socket takes any ctype and body_hex at any granted scope. Admitted: README:65.|
|2935|KV-cache (C2C, references/papers/2510.03215v2.pdf) payloads / out…|I|wire:26|Nothing produces or consumes one; frames are ≤ 1 100 B.|
|2937|"tuning" means in-context attunement in v1|**?**||Recommendation only; nothing in code to test.|
|**§19.7**|**Privacy and telemetry** (3 I · 3 U)||||
|2941|Observability exports carry only hashes and lengths of payloads|I|daemon:69,237-238; fe/delivery:148-186|Daemon logs only hello/fatal/bye; frond-ear custody and egress keep ids and digests.|
|2941|canticle payloads are declared under the enrichment redaction key|U||No redaction key declared anywhere; README points at §19.7 only.|
|2942|Relays keep lease logs minimal and short-lived|U||No relay.|
|2943|The capsid is off by default|I|station:545-546|The station never sets key 10. No test.|
|2943|Beacons on public relays list no private streams.|U||No relay; the station beacons every configured stream.|
|2944|nothing in the protocol reveals it to senders|I|runner:144-149|No wire message goes from listener to station.|
|**§19.8**|**Residual risks** (2 D)||||
|2948|can reach every listener for up to one manifest refresh interval plus the class maximum lifetime|**D** rfc|daemon:396-404|Worse today: the daemon reads the manifest once at start, so a key revoked in the file keeps being heard until the daemon restarts; there is no refresh interval. Admitted: README:504.|
|2949|Taint reduces, but does not eliminate, influence on a session's reasoning.|**D** rfc|pl/binding:944-950; fe/docs/runbook:852|On the Claude Code path there is no taint to reduce anything. Admitted: fe/docs/runbook:852.|

### §20 Relationship to message brokers

20 claims: 9 I · 1 D · 10 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§20.1**|**Position** (1 I · 1 U)||||
|2963|canticle's own relay holds leases and fans out, which makes it a…|U||No relay exists.|
|2963|differs in a station-stateless UDP edge, per-frame signatures that…|I|runner:179-184, wire:450-457; t/station:37|Station-stateless UDP, signed byte-identical frames, receiver expiry and carousel are…|
|**§20.2**|**Invariants a carrier MUST NOT be trusted to provide** (5 I · 1 U)||||
|2967 MUST|(a) verify the frame's Ed25519 signature against a manifest-listed…|I|wire:422-456; fe/wire:555-560; t/wire:152|Python and frond-ear's TypeScript receptor both.|
|2967 MUST|(b) reject any frame at or after its signed expires_at|I|wire:445-449; t/wire:152||
|2967 MUST|(c) deduplicate on the identity tuple|I|listener:319-336; t/listener:160||
|2967 MUST|(d) apply sticky plucks|I|listener:373-395; t/listener:222||
|2967 MAY|MAY be used as optimisations|U||Optional; no broker is used.|
|2967 MUST NOT|MUST NOT substitute for (a)-(d)|I|wire:391-400|Nothing in code relies on a broker. By absence.|
|**§20.3**|**Why not NATS** (1 U)||||
|2975|NATS is nonetheless the candidate relay-to-relay backbone|U||No backbone, no S4a spike.|
|**§20.4**|**Why not MQTT 5 or MQTT-SN** (1 I · 1 U)||||
|2979 SHOULD|a canticle-over-MQTT binding SHOULD set it to the frame's remaining…|U||No MQTT binding.|
|2979|its ADVERTISE Duration is adopted here as next_beacon_ms|I|station:505-553; t/station:245||
|**§20.5**|**Why not Kafka or Redis** (1 U)||||
|2983|suits the ledger (promoted findings)|U||No ledger.|
|**§20.6**|**Why not ZeroMQ or DDS** (1 I)||||
|2987|NORM need receiver NAK back-channels, which I-2 forbids|I|runner:144-149|Station reads nothing from the network.|
|**§20.8**|**Bindings** (1 I · 4 U)||||
|2995 MUST NOT|is raw UDP as specified in §11 and MUST NOT require a broker|I|runner:144-149, daemon:414-427; t/udp_e2e:24|Station to host receptor and LAN multicast are raw UDP.|
|2996|Edge relays are proxy-stations and loop locally ‖ Relays interconnect over a broker only when multi-relay fleet…|U×2||No relay. No relay, no broker.|
|2997 MAY|A NATS WebSocket listener binding MAY be offered|U||Optional; not offered.|
|2998|The SeedLink replay tier remains ringserver fed over DataLink|U||Proof scripts only; no bridge process (bc#130).|
|**§20.10**|**Fit matrix** (1 D)||||
|3023|Canticle (this RFC) / Y / Y / Y / Y / Y / Y / Y / Y / Y (via ringserver)|**D** code|station:268-341|Non-normative matrix, but as built: NATed internet listeners, per-message signature over relays, fan-out to 1000s, membrane and SeedLink columns are not Y. Wire, carrier and loop columns are.|
|**§20.11**|**Measured control experiment** (1 U)||||
|3039 MAY|which is why relays MAY send a fill|U||Optional; no relay.|

### §21 Non-goals (revised)

27 claims: 14 I · 5 D · 6 U · 2 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|3049|1 / Not reliable transport (not OCP-MRC)|I|station:218-251, runner:179-184; t/station:51|No ACK, NACK or retransmission on the wire; the station enforces B_stream/B_station.|
|3049|a leased listener MAY ask its edge relay to repair gaps|U||Optional; no relay or REPAIR.|
|3050|2 / Not throughput-optimal (not ForestColl)|I|wire:22|No schedules or collectives. By absence.|
|3051|3 / Not physically constrained sparsity (not Octopus)|I|wire:22|By absence.|
|3052|no catch-up channel to the station and no since-token on the wire|I|runner:144-149, wire:22|Station reads no network input.|
|3052|late joiners catch up passively from the carousel within TTL|I|station:396-432; t/station:414||
|3052|an edge relay MAY send a validated, budgeted fill ‖ the ringserver tier is a separate TCP surface for dashboards|U×2||Optional; no relay. Proof scripts only; bc#130 unbuilt.|
|3053|5 / Not a full subscription or discovery layer|I|runner:144-149|No sender registry, no QoS, no WHO. The relay lease exception is unbuilt.|
|3054|6 / Not command or event semantics|I|listener:1-6; pl/t/inbound:445|Nothing executes a frame.|
|3055|Stations have no inboxes|I|runner:151-166|Only a same-uid unix control socket; no network inbox.|
|3055|the one wire request-response|U||No lease exchange exists|
|3055|No correlation ids; lineage references only.|**D** rfc|station:309-312|No correlation ids, but also no lineage references: nothing emits derived_from or root. Admitted: README:65.|
|3056|8 / Not a weapon, not an influence tool|**?**||Intent; not decidable from code.|
|3057|a budgeted, receiver-local wake for alarms only (D1)|**D** owner|fe/delivery:1168-1181|frond-ear wakes on any class from an allowlisted key; receiver-local and capped per ear, but not alarm-only. Admitted: fe/docs/runbook:851.|
|3058|Tuned sessions receive a bounded digest silently|**D** rfc|pl/ambient-slots:22; fe/hear:94|frond-ear's digest is a push (a channel event that wakes), not a silent landing at the next turn. Plugin builds the two-slot silent digest but its README says no seat runs it. Admitted: fe/docs/runbook:850.|
|3059|11 / Not a secrets, credential, transcript or bulk-artifact bus|U||Bulk is stopped by the 1 100 B frame #162 canticle/content_policy:26 for derived ops|
|3060|12 / No consensus, no single source of truth, no protocol winner|I|listener:1-6|By absence.|
|3061|13 / Not cross-host addressed control|I|wire:54-72||
|3062|14 / Not membership or failure detection beyond presence|I|listener:725-743|Presence only; no peer lists.|
|3063|15 / Not SeedLink on the wire|I|wire:20-27||
|3064|16 / Not a source of training data|**?**||Operator practice.|
|3065|17 / Not sub-text payloads (KV-cache, latent)|U||Nothing produces them, but nothing refuses one either: any…|
|3066|18 / No opaque "detonator" payloads at fleet or public scope|**D** rfc|runner:97-100, __main__:780|No check: the socket takes opaque bytes at any granted scope. Admitted: README:65.|
|3067|19 / No public wake; no targeting agents outside the manifest|**D** rfc|manifest:98-104; fe/delivery:1168-1181|Listeners hear only their manifest; but frond-ear's wake check never reads scope.|
|3068|20 / No automated remediation or physical actuation|I|listener:1-6|By absence.|
|3069|21 / No multi-part items with FEC; no scope 4 or 5|I|ids:120, wire:22||

### §22 Conformance

91 claims: 44 I · 11 D · 36 U

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§22.1**|**Conformance classes** (3 D · 3 U)||||
|3079|An implementation claims one or more classes, the scopes it supports|U||No implementation states a conformance claim.|
|3083|Station / §5, §7, §8, §9 (emit), §10.5, §12.3 (station side), §15.4|**D** rfc|station:147-569, runner:28-31|Codec, carousel, beacon and identity built; §15.4 (taint, stamping, content policy) and §12.3 ladder (simplified) are not. Admitted: README:61-73.|
|3084|Relay / §9 (verify), §11.3, §12.2-§12.6|U||No relay.|
|3085|Receptor / §9 (verify), §10, §14 in full|**D** rfc|daemon:210-230, records:168-176|Host daemon covers §9, dedup, pluck, supersession, presence, record v1. No accord, MUTE, regulation, hearer ring, receipts query or signed manifest. Admitted: README:494-520.|
|3086|Harness binding / §14.9-§14.14 as landed, the per-session parts of §14.6 and §14.8.2|**D** rfc|pl/binding:1-9; fe/docs/runbook:847-855|OpenClaw spike: much of §14.18 (its README says no seat runs it). frond-ear: deployed, with the departures in its runbook (§14.6, 14.10, 14.12, 14.14, 14.16). Admitted: fe/docs/runbook:847-855.|
|3087|Bridge / §18.3-§18.4, plus Receptor verification|U||Ringserver proof scripts only (bc#130).|
|**§22.2**|**Evidence rule** (2 I)||||
|3091|Every test passes or fails on receptor receipt records, gateway or…|I|fe/t/room-egress:198; t/records:130|Station, record and plugin tests assert emitted frames, records and tool results.|
|3091|Tests are deterministic given now and δ̂ (§14.2).|I|station:396, listener:221; t/listener:77|Station and listener take now_ms explicitly.|
|**§22.3**|**Fixture list** (22 I · 6 D · 22 U)||||
|3095|The fixture suite is issue #27's deliverable|**D** rfc|cs/vectors/frame-v2-candidates.json:1; fe/t/fixtures/canticle/SOURCE:1-8|49 candidate vectors (34 parse, 15 sequences) and unit tests exist, but not as a suite of these groups.|
|3099|F-WIRE codec / valid ITEM, PLUCK and BEACON|I|vectors:40-60; t/wire:27||
|3099|unknown kind; unknown version ‖ signature made without the domain prefix|U×2||Version has a vector. No fixture or test|
|3100|F-LOOP / L-01..L-08 (§22.4)|**D** rfc|station:234-251|Six of eight have tests (L-01,02,04,05,06,07); L-03 is not honoured, L-08 has no test. Rows below.|
|3101|F-PLUCK / PLUCK loops until the target's expiry, including at depth…|I|station:343-377; t/station:150||
|3101|a hush at the PLUCK cap is refused and changes nothing|I|station:351-352; t/station:213||
|3101|sticky-pluck under every ordering, including pluck before original|**D** rfc|listener:373-395|Two orderings as vectors, plus late pluck and restart tests; not every ordering.|
|3101|a pluck cannot extend visibility|I|listener:349-358; t/listener:710||
|3101|a pluck signed by another key is rejected|U||Holds by construction (the target tuple takes the signer's key…|
|3102|F-SUP / every ordering of {old, new} for one state key (RT-30)|I|listener:399-440; t/wire:152||
|3102|warm-up after restart (RT-31)|I|listener:454-463; t/listener:250|Warm-up tested; not a restart-plus-warm-up case.|
|3102|high-water mark persisted across restart|I|listener:682-711; t/listener:222||
|3102|far-future issued_at cannot win|I|wire:446-447; t/wire:152||
|3103|F-37 / retention min(depth, TTL)|I|station:366-377; t/station:229|Depth-bound and TTL-bound each tested, not as one two-case fixture.|
|3104|F-38 / a forced stream_id collision makes the station refuse to…|I|ids:78-86; t/station:235||
|3104|evidence stream-name-ambiguous|U||Never emitted: the manifest refuses two names for one id at…|
|3105|rotation covers every stream within count beacons|I|station:505-549; t/station:366||
|3105|a catalog_digest change invalidates stale entries|U||The listener keeps the last pages and never reads…|
|3106|F-CARRIER / the presence machine, including SIGNED_OFF, ROOT_UNKNOWN|I|listener:725-743; t/listener:37||
|3106|and relay decimation|U||No relay.|
|3106|both admit a valid BEACON whatever its wallclock|I|wire:445, listener:254-264|Receptor only; beacons skip the time window. Not tested as such.|
|3106|a higher epoch resets the bseq mark|I|listener:241-251; t/listener:101||
|3106|ITEM and PLUCK time windows applied after δ̂|I|wire:445-449; t/listener:77||
|3107|F-TRUST / manifest threshold signatures; expired manifest fails…|U||No signed manifest, roots, serials or expiry.|
|3107|a capability-rejected frame leaves epoch, dedup and presence state…|I|listener:294-312; t/listener:142||
|3107|key-id collision rejected|I|manifest:88-89; t/manifest:114|Load refuses two entries with one key id. No test for two different keys colliding.|
|3108|F-LEASE / cookie construction and rotation|U||No relay.|
|3109|DOC / canticle doctor: loopback probe; peer beacons|**D** rfc|doctor:200-258|Only the loopback probe (and only when asked). No peer beacons, querier check, broadcast fallback or §11.2 exit codes. Admitted: README:130-138.|
|3112|BIO-01..BIO-44, M-01..M-06|U||No regulation, immune grammar or MAGI code or tests.|
|3113|RT-01..RT-131 / the red-team suite (§22.7)|U||No suite|
|3114|BE / blind-enrichment acceptance for each harness binding|U||None for the plugin or frond-ear.|
|3115|REG-B1..B6, B10..B12 / regression tests|U||Conditional: the old verify stage was not reused.|
|3116|S4a / the broker spike measurements behind D10|U||Not run; only the control experiment in rfc/0001-notes/brokerx.|
|3117|trail_seq stays correct through expiry, supersession, pluck and…|I|station:464-477; t/station:258||
|3117|beacons at the §8.4 bound stay ≤ 1 100 B|I|station:479-498; t/station:299||
|3117|receivers stop waiting below trail_seq ‖ A2: REPAIR is answered only on a validated lease ‖ A3: reports carry only their five fields ‖ A4: a saturated lease still gets first copies before repeats ‖ A5: each of the three join modes ‖ A6: a backbone link to a silent peer is torn down ‖ A8: RELAY_GOAWAY moves listeners only to manifest relays ‖ A9: silent landing is immediate; a wake waits for proofreading ‖ A10: the capsule fallback is refused or labelled retransmitting|U×9||The listener stores trail_seq and nothing acts on it. No relay. No reports. No backbone. No proofreading anywhere; frond-ear wakes without it. No WebTransport.|
|3117|A11: nothing lands untuned|I|pl/config:124-131; fe/delivery:1168-1181; pl/t/subscriptions:14|Plugin subscriptions and frond-ear tune are exact and default empty/off.|
|3117|no landing interrupts a step|I|pl/oc0-host:18-30; fe/src/render:303|OC-0 next-turn injection and Claude channel events queue to the next turn (host…|
|3117|desynchronised landings spread over the drawn window|**D** rfc|pl/candidates:160-170; fe/docs/runbook:853|Plugin draws a random delay (candidates:168); frond-ear applies none. Admitted: fe/docs/runbook:853.|
|3117|supersede, pluck, revoke, expiry, quarantine, MUTE and untune each cancel a pending landing|**D** rfc|pl/ambient-slots:172-190; fe/docs/runbook:850|Plugin withdraws pending slots on retract, MUTE and mute. frond-ear cancels only what still waits; a push already sent cannot be recalled. Admitted: fe/docs/runbook:850.|
|3117|D1: with silent-wake disabled, no input produces a wake|I|pl/config:124-131; fe/src/config:118-125; fe/t/canticle-delivery:1514|frond-ear: an ear not in canticle.delivery is off; plugin has no wake.|
|**§22.4**|**Loop-regulator tests (station)** (7 I · 1 D)||||
|3121|L-01 A request faster than the fair share is clamped|I|station:234-251; t/station:51||
|3122|L-02 Every interval falls within [2/3, 4/3] of loop_ms.|I|station:441-445; t/station:37||
|3123|L-03 A bulk insert of many items causes no burst above B_stream|**D** rfc|station:366-377|Each item sends its first copy and burst at once whatever the stream budget, so N inserts burst N frames. No burst accounting, no test. Admitted: README:71.|
|3124|L-04 A new item is sent at 0, +1, +2 and +4 s, then at loop_ms.|I|station:28,377; t/station:37||
|3125|L-05 A same-key supersede stops the old item's loop at once.|I|station:315-320; t/station:100||
|3126|L-06 When loop_ms › hi, the item is marked DEGRADED and ladder step…|I|station:243-246,374-376; t/station:184||
|3127|L-07 The tool returns the effective loop_ms, the TTL and the clamp…|I|station:50-67, runner:107; t/station:37|Station result, CLI, plugin effective block.|
|3128|L-08 A faster loop request changes no receiver-side quantity|I|listener:333-336; t/records:150|Receivers derive nothing from loop rate: repeats are no-ops, there is no salience or…|
|**§22.5**|**Emeric's acceptance tests (#51)** (9 I · 1 D)||||
|3132|EM-01 A replayed frame with 2 seconds remaining|I|wire:368-388, listener:648-655; t/listener:69|Absolute expiry with first-hearing cap; no test with exactly this scenario.|
|3133|EM-02 Receiver restart or cache restoration cannot resurrect an…|I|records:255-280; t/records:475||
|3134|EM-03 Expiry clears interface, context and derived receptor state|**D** rfc|records:512-515, pl/ambient-slots:172-190; fe/docs/runbook:850|Interface and receptor state clear and presence stays unclassified. Session context does not: frond-ear gives no note after a push; plugin queues one metadata note after a landing. Admitted: fe/docs/runbook:850.|
|3135|EM-04 A missing or late pluck cannot keep a frame alive|I|listener:648-655; t/listener:61|Expiry never depends on a pluck; a PLUCK that disagrees with its target is refused.|
|3136|EM-05 An unsupported version or tag produces no inferred fallback…|I|wire:414-418, listener:396-398; t/wire:152|Bad version rejected; unknown class is ringbuffer_only|
|3137|EM-06 No item is eligible for durable promotion without a separate…|I|pl/journal:1-12|No promotion exists at all.|
|3138|EM-07 A sender cannot learn subscriber identity, filtering…|I|runner:144-149|No wire path from listener to station. No test.|
|3139|EM-08 A burst of identical frames may be coalesced or rate-limited|I|listener:333-336; t/records:150||
|3140|EM-09 Clock skew cannot extend visibility beyond the receiver's…|I|wire:384-388; t/listener:69||
|3141|EM-10 Debug and telemetry surfaces cannot feed expired content back…|I|pl/binding:815-890; fe/delivery:148-186; pl/t/inbound:180|Plugin marks each entry expired/withdrawn/not in view at read time|
|**§22.6**|**Receptor examples (RX)** (1 I · 7 U)||||
|3149|RX-1 / Valid chemokine binds|U||No thresholds or tighten.|
|3150|RX-2 / Foreign quarantine signal|U||No quarantine vote or accord to test|
|3151|RX-3 / Expired frame in the ring|U||No hearer ring or receipt store (§14.4-14.5)|
|3152|RX-4 / Antibody memory survives chemokine TTL|U||No antibody memory or promotion.|
|3153|RX-5 / All-clear lowers the threshold|U||No RESOLVING ramp, threshold or all-clear.|
|3154|RX-6 / Bridge-forward is not hear-and-sing|U||No bridge; re-sings carry no lineage.|
|3155|RX-7 / Clarion widens propagation without becoming command|I|listener:301-308|Scope only gates admission and carries no authority; no auto-actuation. No test.|
|3156|RX-8 / Local divergence under the same weather is conformant|U||Tunes and mutes let two bindings differ, but no posture…|
|**§22.7**|**Red-team suite** (3 I · 4 U)||||
|3160|The suite runs on a "worm range" ‖ RT-03 (propagation stops at hop 2; no wakes; denied tool calls… ‖ RT-10 (bytes to a spoofed victim ≤ bytes sent before cookie… ‖ RT-52 (the canticle cost budget stops wakes|U×4||No worm range No relay. No canticle cost budget.|
|3160|RT-110 (fuzz corpus including|I|wire:391-404; t/wire:164|20 000-case random and mutation fuzz, zero escapes; frond-ear fuzzes parse too.|
|3160|RT-112 (another producer|I|pl/ambient-slots:22; pl/t/ambient-slots:31|Plugin unit test: two slots stay bounded on rebuild.|
|3160|D14's automated alarm issuer stays off until this range shows|I|runner:28-31; t/station:496||

### §23 Open questions

117 claims: 37 I · 22 D · 52 U · 6 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§23.1**|**Owner decisions** (33 I · 13 D · 25 U · 5 ?)||||
|3172|silent by default; receiver-local opt-in wake for verified alarm frames only|**D** owner|pl/config:124-131; fe/delivery:1168-1181|Default silent: yes (delivery off; plugin has no wake). But frond-ear's opted-in wake fires on any class from an allowlisted key, not alarms only. Admitted: fe/docs/runbook:851.|
|3172|The initial deployment is silent-only until S3 implements and tests the whole conjunction|**D** owner|fe/src/config:337-360|frond-ear ships a working push; what a seat runs is config (example: wakeKeys empty, digest). Not enforced in code. Admitted: fe/docs/runbook:851.|
|3172|Sender-requested or sender-forced wake is rejected|I|fe/delivery:1168-1181; fe/t/canticle-delivery:749||
|3173|D2 / Content lane / Payload-carrying frames ≤ 1 100 B plus digest…|I|wire:26,212-218; t/finding:191|Doorbell = finding-ref class with body_ref only.|
|3174|Stream max_ttl default 300 s; station hard cap 24 h|I|station:34-35,200-201; t/station:78|Keep-on-air is looser than §7.9: any keyed item, up to 24 h (README:77).|
|3174|root mark persists by refresh re-issue until UNEQUIP|I|station:405-410; t/station:192|Refresh re-issue and UNEQUIP both work; nothing issues the root mark automatically.|
|3175|D4 / Trust / Decided (#54): Ed25519 on every frame or binding that…|I|wire:450-457, daemon:350-358; t/daemon:149|Every frame, loopback included.|
|3175|The only unsigned path is a peer-authenticated unix debug socket|U||Optional; no debug socket exists.|
|3175|No downgrade mode.|I|wire:450-457||
|3175|HMAC only as a relay flood pre-filter|U||No relay, no HMAC.|
|3176|D5 / Scale target / Design for a fleet via a relay tree; validate…|U||No relay tree.|
|3177|D6 / Internet in scope / Yes, through relay-held leases|U||No relay.|
|3178|D7 / SeedLink naming / Private XX namespace|I|prototype/ringserver-proofs/02_seedlink_v4_vs_v3:39|Only in the proof scripts; no bridge.|
|3179|D8 / Console stack / ews first|**?**||Dashboards are in other repos; this repo serves only tuner and shape JSON.|
|3180|Python for codec, station and receptor spike; TypeScript for the…|I|wire:1-8, pl/binding:1-9; fe/wire:1-40|All four exist; the TypeScript codec is in frond-ear.|
|3180|Go or Rust for the relay|U||No relay (a Go fan-out sender exists only in the measurement…|
|3181|UDP carousel at the edge and for membership|I|runner:179-184; t/udp_e2e:24||
|3181|TCP/QUIC for relay backbones, clean-path snapshots, replay, the…|U||None of these planes is built, except a local unix join…|
|3182|D11 / Third default lens / purpose|U||Frames carry a lens id|
|3183|Bespoke header + deterministic CBOR + trailer; publish a COSE_Sign1…|I|wire:212-218; fe/wire:534-560; t/wire:84||
|3184|D13 / post-compaction landing of heard content / Reserved in v1|I|pl/config:124-131|Nothing lands at compaction.|
|3185|LLM-driven sessions hold no alarm, quarantine or control keys|**D** rfc|__main__:74-84, runner:28-31|Same as Never 19: same-uid key files, keygen grants any class; only the control socket refuses. Who runs the keys on seats is operator practice. Admitted: README:64.|
|3185|Automated 2-of-3 keeper issuance stays off behind an explicit flag|U||No keeper, no flag; nothing is issued.|
|3186|1-of-1 for the cohort pressure test|**D** rfc|manifest:1-8,109-125|The manifest in use is unsigned (0-of-0). Genesis pin, 7-day lifetime, daily re-fetch, rollback serial and fail-closed expiry are all absent. Admitted: README:63.|
|3187|D16 / Sandbox mandate / Required for any wake-enabled OpenClaw agent|U||OpenClaw has no wake.|
|3188|D17 / Public "lighthouse" stations|U||Optional; none.|
|3189|D18 / "Tuning a new model" / In-context attunement only in v1|**?**||Operator practice; nothing trains.|
|3190|D19 / Language on fleet and public streams|**?**||Operator convention.|
|3191|D20 / Verb names / canticle_sing, canticle_hush, canticle_tune, canticle_listen|**D** owner|pl/tools:97-110; fe/src/shim:221-265|Plugin: sing, hush, listen, plus status, mute, outbox, discover; no tune. frond-ear: hear, set_canticle_delivery, canticle_custody, and no sing/hush tool at all. Admitted: pl/README:474.|
|3192|D21 / Keeper diversity|U||No keepers.|
|3193|Advertise via SRV; 9999 and 239.255.13.13 provisional for…|I|runner:27,32; t/dns_browse:36|Constants used. Reading SRV works (dns-browse); nothing publishes records.|
|3194|D23 / Healing as continuous counterweight|U||No healing lens code.|
|3195|D24 / Regulation profile / Adopt canticle-regulation/1|I|station:37; t/station:245||
|3196|P1 is receive-only, with no wake. A binding adds wake (P3) only after a concrete operator alarm producer exists|**D** rfc|pl/config:124-131; fe/delivery:1168-1181|OpenClaw P1: no wake in config or code. frond-ear adds wake with no alarm producer and no §14.10 proofs. Admitted: fe/docs/runbook:851.|
|3197|extend OpenClaw's generic next-turn injection seam (OC-0)|I|pl/oc0-host:16-38, pl/ambient-slots:144-160; pl/t/oc0-host:5|Adapter plus durable slot ledger (settled tombstones, at-most-once). Spike only|
|3198|the binding's (host or plugin) configuration owns subscriptions|I|pl/config:118-134, records:174-175; fe/src/config:118-123; pl/t/subscriptions:14|Plugin exact-key subscriptions; frond-ear tune + delivery|
|3198|A host-wide wake budget has one accountable owner across all…|U||frond-ear caps per ear only|
|3199|per-frame records stay inside the receptor and its binding (§14.18.3) and never become per-frame session entries|**D** rfc|pl/ambient-slots:122-135; fe/docs/runbook:850|Plugin: yes. frond-ear pushes each record (immediate) or lists records (report) as a new channel event. Admitted: fe/docs/runbook:850.|
|3199|Over OC-0 the binding keeps at most two pending entries per…|I|pl/ambient-slots:22,125-145; pl/t/ambient-slots:31|Tested with a fake host, not under flood on a real OpenClaw.|
|3200|§14.18 is frozen at binary-canticle|**?**|pl/oc0-host:6-12|Editorial; the plugin names no OpenClaw SHA. OC-0 has moved (the adapter needs session id + lifecycleRevision fields). Owner: rune/princes.|
|3201|JSON5 under plugins.entries.‹id›.config; enabled: false written…|I|pl/openclaw.plugin.json:6, pl/config:1-4; pl/t/plugin:456|Semantic failures fail the service, not Gateway boot.|
|3202|third-party and least-privileged|I|pl/index:40-60,89; pl/t/plugin:71|Plain third-party plugin, optional tools, no bundled seams|
|3203|keep [canticle:heard] across documents and code|I|tap:150, pl/render:104; fe/hear:118; t/tap:182|tap, plugin and frond-ear.|
|3204|a bounded, supervised stdout JSON-lines child is acceptable for P1|U||Optional|
|3205|fixed aggregate counters per reason plus a bounded top-16 key-id…|I|records:43-65,120-148; t/records:525||
|3205|optionally a bounded local debug ring for per-frame rejects|U||Optional.|
|3206|One standalone canticle host daemon per host; every harness binding…|I|daemon:210-230,414-427; fe/source:110-139; t/daemon:229||
|3206|The daemon holds the station keys and signs every binding's publishes|**D** rfc|daemon:36-40, runner:151-166|The daemon holds no keys and ignores publish lines; each station process holds its own key file and signs for anyone of its uid on its control socket. Admitted: README:64.|
|3206|owns the host wake budget|U||No budget in the daemon.|
|3206|refuses to bind while a daemon answers|I|fe/source:72-92; fe/t/canticle-records:266||
|3206|the mixed-host proof gate of §14.18.2 is concrete and runs on silas and ronan before P1 runs there|**?**|cs/proofs/pilot/round-2b-daemon-loss:1|Run cards exist; no receipts in either repo. Owner: silas/ronan seats.|
|3207|a bounded join snapshot after the unchanged hello + landing_state…|I|daemon:253-331, records:557-569; fe/records:641; t/join_snapshot:199||
|3207|no rate, budget or salience; no wake|**D** owner|fe/docs/runbook:854|frond-ear pushes a never-pushed snapshot or resurfaced record once, marked late, and it counts toward maxPushesPerHour. Admitted: fe/docs/runbook:854.|
|3207|Bounded at 511 entries and 1 MiB|I|daemon:70-73; t/join_snapshot:360||
|3207|receive health joined_late until a complete snapshot or a new run|I|pl/receive:1-12; fe/records:641; fe/t/canticle-join-snapshot:138|frond-ear and plugin views.|
|3208|a fleet probe's or a distress watcher's finding is a keyed advisory…|I|finding:1-40, runner:70-79; t/finding:176||
|3208|Only a newer resolved item from the same key under the same…|I|listener:399-445; t/finding:274||
|3208|the signer is always the speaker, and self is shown only when the…|I|tap:109-116; t/finding:346||
|3208|Severity is CAP|I|finding:20-60; t/finding:114||
|3209|the reference human web view is synthetic-only in v1|**D** owner|shape:83-92,432-436|tuner: yes. But canticle shape (merged after, #134/#140) serves real stations' names, presence, stream names, live counts and history to a human page. RFC §18.9/D38 does not mention shape or grants. Admitted: README:22.|
|3209|--demo-fixture alone may show explicitly invented station and…|I|tuner:55-66; t/tuner:93||
|3209|an unsigned manifest or viewer-side list may only narrow that election|**D** rfc|shape:432-436, grant:1-20|With --display, a station-signed grant (revocable, expiring) is required: good. Without it, the host's --station list alone publishes real presence and counts. Admitted: README:315-317.|
|3215|A1 / trail_seq in each beacon stream entry|I|station:464-477, wire:95-123; t/station:258||
|3216|A2 / Relay-side repair|U||No relay.|
|3217|A3 / Receiver report on RENEW|U||No leases.|
|3218|A4 / Relay egress scheduler|U||No relay.|
|3219|A5 / LISTEN join modes|U||No LISTEN message|
|3220|A6 / Backbone rules for TCP/QUIC links|U||No backbone.|
|3221|A7 / Class floors below SAP's 300 s / Accepted|I|ids:104-112, station:241-242; t/station:51||
|3222|A8 / Relay restart|U||No relay.|
|3223|Verified silent landing may be immediate; proofreading gates wake, not reception|**D** owner|fe/delivery:1168-1181|frond-ear wakes immediately with no proofreading. Admitted: fe/docs/runbook:851.|
|3223|completed consumption bounded by one advertised loop and expiry|U||No completed-consumption mode.|
|3224|A10 / WebTransport binding|U|||
|3225|Explicit listening election, turn-boundary and desynchronised landing, typed control, and hop, lineage and taint…|**D** rfc|pl/candidates:165-168, pl/binding:944-950; fe/docs/runbook:853|Election and turn-boundary hold in both bindings. Desync: plugin only. Typed control, lineage and (on Claude Code) taint: none. Admitted: fe/docs/runbook:852-853.|
|3226|A12 / Guardian role and doubt channel / Deferred|U||Deferred; no code, as intended.|
|3227|A13 / Budget sets catch-up / Accepted|I|station:234-251; t/station:414||
|**§23.2**|**Open technical questions** (4 I · 5 D · 25 U · 1 ?)||||
|3231|This RFC fixes only the envelope rules (§6.6).|U||Still open: content type 9 is registered, no body schema or…|
|3232|The death seam|U||Still open; nothing built.|
|3233|Receiving near one|U||Still open (blocked on D13).|
|3234|The posture vocabulary and its mapping to tune postures remain open.|U||Still open.|
|3235|before_tool_call block and approval cover part of §14.12 ‖ Claude Code's PreToolUse denial path is to be verified|U×2||Still open: the plugin uses no before_tool_call Still open: no PreToolUse hook anywhere in frond-ear.|
|3236|Canticle token accounting|U||Still open.|
|3237|Principal definition for accord|U||Still open; record v1 principal is always null.|
|3238|Convergence detector|U||Still open.|
|3239|Capsid schema v1|U||Still open; capsid never set.|
|3240|Loss-tolerant authentication|U||Still open.|
|3241|Multi-part items with FEC|U||Still open.|
|3242|WebTransport egress details|U||Still open.|
|3243|canticle payloads "remain typed proposals/references and do not…|U||Promotion surface still open.|
|3244|Session API split (#24)|U||Still open|
|3245|IANA: service names and ports (D22).|U||Still open.|
|3246|Proofreading parameters (A9)|U||Still open; yet frond-ear already wakes without any.|
|3247|WebTransport in practice (A10)|U||Still open.|
|3248|Guardian mini-RFC (A12)|U||Still open.|
|3249|Relay restart SLO (A8)|U||Still open; no relay.|
|3250|remain candidates until the independent TypeScript codec reproduces them (§9.13)|**D** code|cs/vectors/frame-v2-candidates.json:1; fe/t/canticle:63|Overtaken: frond-ear's TypeScript port runs every vector, and its copy equals main's file (49, not 37).|
|3250|predate trail_seq (A1)|**D** code|wire:95-123, station:471-476|False now: vectors and beacons are post-A1 (9-element entry, trail_seq; pre-A1 entry is bad-field).|
|3251 MUST|a station MUST keep one class per (stream_id, state_key)|I|station:299-304; t/station:110||
|3251|a receiver holding a mark drops a class change with evidence…|I|listener:415-422; t/listener:760||
|3252|ambient delivery, from P1 on, does not target sessions with an off-host channel route|**D** owner|pl/candidates:69-76; fe/delivery:1168-1181|Plugin: refused without an onHost route proof. frond-ear: every ear is a Discord route by design, and it pushes ambient items to them. Question 22 is still formally open; frond-ear acted as if settled. Admitted: fe/docs/runbook:852.|
|3253|The daemon is built in this repository as canticle daemon|I|daemon:210-230; t/daemon:126||
|3253|frond-ear's canticle stays off on silas and ronan until the mixed-host proofs of §14.18.2 pass there (#65)|**?**|fe/frond-ear.example.json:55|Operator state; off by default in config (enabled false). RFC/README lines on this are dated and the measurement of 2026-11-23 ran on ronan. Owner: seat owners.|
|3256|Whether canticle_tune is offered there|U||Still open|
|3257|Serving it beyond the host behind authentication needs an amendment…|I|tuner:84-88, __main__:459-461; t/tuner:173||
|3258|and the prototype has no doctor|**D** code|doctor:238-258|False now: canticle doctor exists but decides nothing about multicast (#78). Admitted: README:130-138.|
|3258|keep it forbidden and build the doctor first|**D** rfc|__main__:165-166,736|canticle station --multicast, listen/daemon --multicast and stations.toml allow it with no doctor pass; only the docs say not to. Admitted: README:130-138.|
|3259|The P3 wake seam|U||Still open for OpenClaw; frond-ear went ahead with its own push.|
|3260|define it before the P1 proof|U||Still open: no spans or exporter; record v1 has no trace field.|
|3261|whether a binding may retry a truncated snapshot on a fresh…|U||Still open|
|3262|whether a finding-ref may carry a summary body|U||Still open|
|**§23.3**|**Work items** (4 D · 2 U)||||
|3270|S0 Housekeeping|**D** rfc|proto/lineage/send-side-draft:1, proto/INDEX:36|Partly done: README rewritten, lineage drafts landed (#53), proofs dir on main, notes committed. Not done: PR #34 file absent (dangling link remains), INDEX not regenerated, v0.2-workboard still in proto/.|
|3271|S1 Frame v2|**D** rfc|wire:1-8, manifest:1-8; fe/t/canticle:63|Done: both codecs, deterministic CBOR, vectors reproduced by a second implementation. Not done: signed manifest and verifier, normative status, COSE code. Admitted: README:61-65.|
|3272|S2 Station daemon|**D** rfc|station:147-569, doctor:200-258|Done: carousel, beacon with trail_seq/paging, sockets, CLI, A1 vectors. Not done: §11.2 doctor decision, DNS-SD publication, keys in the daemon (the station is a separate process, not a daemon with many keys). Admitted: README:61-73.|
|3273|S3 Receptor and bindings|**D** rfc|daemon:210-230, pl/oc0-host:16-38; fe/docs/runbook:847-855|Done: host daemon, BC-2, OC-0 adapter spike, frond-ear binding. Not done: taint seams, Claude Code hooks, conjunction, blind-enrichment, proofreading, A11 typed control. frond-ear wakes before it. Admitted: README:67.|
|3274|S4 Relay and replay tier|U||No relay, leases, repair, bridge or S4a spike (bc#130 for the…|
|3275|S5 MAGI and hardening|U||Nothing. No keepers, worm range, drills or scale test.|

### IANA considerations

4 claims: 4 I

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|3281|This draft requests no IANA action.|I|dns_browse:90|Nothing requests any.|
|3283|The DNS-SD service name _canticle._udp|I|dns_browse:90; t/dns_browse:36|Queried by dns-browse; never registered or published.|
|3284|9999 is a development default only (§11.2).|I|runner:32||
|3287|are registries kept in this repository, not with IANA|I|ids:101-135, wire:20-27|Kinds, classes, scopes and content types are in code|

### Appendix A

10 claims: 2 I · 1 D · 5 U · 2 ?

| RFC line | claim | | evidence | note |
|---|---|---|---|---|
|**§A.1**|**proto/** (2 U)||||
|3312|proto/INDEX.md / regenerate|U||Still the old index: no rows for prototype/, scratch/ or…|
|3313|proto/v0.2-workboard.md / retired|U||File still present and INDEX lists it "active".|
|**§A.2**|**spike/, scratch/, references/, prototype/, README.md** (1 D · 2 U · 1 ?)||||
|3321|INDEX status stable → superseded|U||INDEX row still says stable.|
|3323|Its dangling link to proto/return-stage-anti-coercion-addendum.md…|U||The target does not exist on main; the link still dangles.|
|3327|duplicate CORAL PDF and blog text should be deduplicated|**?**||references/papers now lists one CORAL PDF plus notes; whether that was the duplicate is not decidable from here.|
|3329|README.md / stale / rewrite to point at this RFC (#35)|**D** code|README:1-20,121|Done: README points at RFC-0001 and its work items (6893283). But its line 121 (frond-ear "listen-only and silent", "its README says no seat runs it") is now stale.|
|**§A.3**|**Branches and pull requests** (2 I · 1 U · 1 ?)||||
|3335|PR #34 proto/return-stage-anti-coercion-addendum.md / merge|U||The file is not in proto/ on main, so not merged.|
|3336|carried; land the three drafts under proto/lineage/ in a lineage PR…|I|proto/lineage/send-side-draft:1, proto/INDEX:41-43|Landed by #53 (a339b82), INDEX rows 41-43.|
|3339|PR #44 (ring-broadcast infographic)|**?**||PR state needs GitHub; branch origin/design/ring-broadcast-infographic still exists, no figure in the RFC tree.|
|3340|now at prototype/ringserver-proofs/, and close it once that is on…|I|prototype/ringserver-proofs/01_cue_to_datalink:1|It is on main; whether #49 and #50 are closed needs GitHub.|
