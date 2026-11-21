# Familiar projections (#148)

> **Proposed.** Research for #119 (the familiar) and #120 (the receiver contract). Nothing here is in
> RFC-0001, wired into a harness or deployed. It changes no wire format, receptor record or vector. The
> fixtures are synthetic; nothing reads a transcript, captures a log or calls a model.

A familiar reads authorized, shareable sources near where they are written and sings a small projection of
them once. Many receivers then inhabit that projection cheaply: reading, searching and retuning need no model
call (🌫's "interpret once, inhabit cheaply" and 🌊's and 🌻's receiver notes on #119, 🪨's on #120). This note
says when a claim in a projection stops being current, what a re-sing or a rephrase may add (nothing), and what
a receiver shows when it cannot know. "Projection" here means a familiar's derived view, not §9.10's JSON
projection of a frame.

```sh
python prototype/familiar-projection/projection.py      # every fixture, one line each; exit 1 on a failure
PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/familiar-projection -v
```

Standard library only. Two of the tests also check the identifiers and the size bound against the station's own
`ids`, `records` and `wire` when `canticle` imports (through `PYTHONPATH`, as CI sets it), and skip otherwise.
CI's station-tests job runs the tests.

Contents: 1 the state and source matrix · 2 the descriptor · 3 when a claim is current · 4 producer cost and
receiver dose · 5 receiver views · 6 fixtures and the checker · 7 interfaces with other lanes · 8 RFC
amendments this would need · 9 what stays proposed.

## 1. State and source matrix

What RFC-0001, main at `08c11127` and #126 at `adf36920` do today, and what this note proposes. "—" means
the code has nothing for it.

| Concern | RFC-0001 | main `08c11127` | #126 at `adf36920` | Proposed here |
|---|---|---|---|---|
| Producer identity | Key id to manifest principal; never names, addresses or payloads (I-11) | Unsigned spike manifest | `expected_key_id` check; the auth file binds actor, station and key | Only from the signed envelope, never from the body |
| Item life | Absolute signed `expires_at`; at local expiry an item loses current-state authority in every surface, derived views included (§6.3 rule 1) | Record v1 `retract expired`; OpenClaw journal "expired at T"; frond-ear never pushes an item after it goes off air | `chatter`, `ttl_s` 1–300 | One bound on a claim, not the only one |
| Withdrawal by the signer | PLUCK, same key, sticky (§7.7) | `Station.hush`; listener sticky-pluck; record v1 `retract plucked` | Revocation stops the next sing; items already sung stay on air | A plucked or revoked projection takes all its claims |
| Supersession | Greatest `(issued_at, epoch, seq)` per `(key-id, stream_id, state_key)`; marks persist (§7.8) | Station and listener supersede by `state_key`; record v1 `retract superseded` | `state_key` `wake-<batch identity>`, one key per batch: only a retry of the same batch supersedes, and batches never supersede each other | Plus a per-key `generated_at` mark, so a restarted producer cannot roll a key back |
| Repeats and refresh | One lineage root, never new (§7.9, R-INT-1, R-INT-2) | `Station.poll` re-issues with `refresh` under the horizon; frond-ear collapses flagged refreshes only | A failed send re-sings the same batch without `refresh`, under a new seq (at-least-once, by its README) | Equal digest and `generated_at` is a repeat, flagged or not; a refresh renews airtime, never validity |
| Sources and their withdrawal | Sources are canticle roots (`derived_from`, §12.1); no per-claim dependency | — | Rows kept as `{id, kind, topic}`; the text names the source snapshot's digest and a batch identity; nothing withdraws a row once sung | Each claim cites `(actor, ref, rev)`; bodies list withdrawals; each receiver keeps a sticky ledger per producer |
| Derived synthesis | §17.3 aspect body: one synthesis, at most 6 evidence references, a basis window, distinct principals and roots | No aspect-keeper code | One summary text per batch | Up to 6 claims, each current only while every source it cites is |
| Notice and world fact | Not distinguished | Typed beacons (#142) enforce `until`; missing or expired reads unknown | — | Sources are `notice` or `record`; a `state` claim cites records only |
| Speaker, subject, inference | The signer is the speaker; voice `self` or `observer` (§6.7) | Finding body (ctype 11); beacon `origin` reported or inferred | `origin: actor`, `lineage: local` | A label from claim `basis` and source `origin`: self-report, observation, record, interpretation |
| Evidence weight | Strength from distinct principals and roots, never from rate or repeats (§12.1) | No salience, accord or strength code | — | Support counts distinct source actors; wording, copies and producers add nothing |
| Producer cost | Keepers make no model call unless input roots change (§17.4 K4, K5) | `canticle ambient` makes no model call | Deterministic text, no model | A repeat or a re-stamp needs no model; a synthesis needs a new claim |
| Reads, search, retune | Modulation is receiver-local (§14.7); the digest is host-written (§14.14) | OpenClaw explicit read; `view: digest`, or `view: items`, which taints; exact-key subscriptions | — | Served from an index of tokens, with no model call |
| Pending presentation | The digest drops superseded, plucked, revoked and expired items, with one note after drain (§14.14); landing cancellation (§14.16) | OpenClaw `Candidates.retract` and `rejoin`; frond-ear tombstones, never pushed late | — | Keyed by label and evidence, rechecked at drain; one note when a presented claim stops being current |
| Restart | Live-state is UNKNOWN through warm-up (§6.3 rule 4); a keeper rehydrates from its own last item (K7) | New epoch from `next_epoch`; the ring is not persisted; the daemon's join snapshot (`snapshot`, `snapshot_end`); the OpenClaw binding's `joined_late` | — | Nothing lapsed is presented after a restart; coverage is unknown until a complete snapshot |
| Receiver gaps | Silence is not a value (§6.3 rule 5); nor is a gap (§7.10) | Record v1 `health` (`records_lost`, `no_datagrams`); OpenClaw "carried: heard before a gap" | — | Claims are carried, never quiet; an actor the producer could not read is unknown |
| History and retention | Promotion only by an untainted principal or a human (§6.4, I-10); reading heard content taints (§14.12) | OpenClaw journal history, "withdrawn (REASON) at T"; no elected store | — | `standing: history` and elected retention: attributed, historical, never current, never support |
| Echo | Keepers exclude lens streams and keeper lineage (§17.4 K3) | — | `from_canticle` rows skipped; a heard-topic filter | A source `ref` starting `canticle:` is refused |
| Audience | Scopes host, lan, fleet, public (§4.3); private types never fleet or public (§9.9) | The station enforces granted scopes | Auth `audience: lan` | Per-source `audience`; an item may not be wider than any source it cites |

## 2. The descriptor

Who said it comes from the signed envelope: the key id, its manifest principal and station, and the item's
stream, scope, `(epoch, seq)` and expiry. The body never names its producer, so it cannot disagree with the
signature. The projection key is the item's `state_key`, so §7.8 supersedes older items on the wire.

The body, `familiar-projection/1`, is canonical JSON (sorted keys, no whitespace, UTF-8, integers only) of at
most 900 bytes, carried as ctype 3 for now. Record v1 delivers a ctype 3 body as `body.base64` with its
`sha256` (`records.py`); the reader accepts only canonical bytes, so that digest is the projection's digest.
900 is measured: a keyed item with a 48-byte `state_key`, ctype 3 and the refresh flag carries at most 920
body bytes inside the 1 100-byte frame (`test_largest_body_fits_a_keyed_item`).

| Field | Bound | Meaning |
|---|---|---|
| `v` | `familiar-projection/1` | Version. Any unknown field makes the body unreadable. |
| `key` | token, ≤ 48 | The projection key and `state_key`. One current projection per producer and key. |
| `standing` | `current`, `history` | A `history` body is never current. |
| `window` | `[from, to]` ms | The source interval read. `to` is the as-of time. |
| `generated_at` | ≥ `window[1]` | When the producer made the body. It orders bodies per key; it is never a freshness input. |
| `valid_until` | > `generated_at`, ≤ +900 s | The producer's lease: how long it vouches without checking again (§17.4's 900 s horizon). |
| `sources[]` | ≤ 6 | `id` (local), `actor`, `ref` (the authorized source id, ≤ 48), `rev` (≥ 1), `origin` (`self`, `observed`), `authority` (`notice`, `record`), `audience` (the scope it is elected for), `valid_until`. Every source is cited. |
| `claims[]` | ≤ 6 | `id`, `basis` (`report`, `state`, `interpretation`), `about` (the subject, an actor token), `topics` (1–4 tokens), `src` (source ids, all of which must hold), `text` (1–200 bytes, one line, no control or format characters). |
| `withdrawn[]` | ≤ 6, optional | `actor`, `ref`, `rev`, `reason` (`withdrawn`, `superseded`, `revoked`). |
| `unread[]` | ≤ 6, optional | Actors the producer could not read for this window. They render unknown, never quiet. |

**Labels.** The receiver derives each claim's label from the body; the producer does not pick it. A `state`
claim is a `record` and an `interpretation` claim an `interpretation`. A `report` is a `self-report` when every
source it cites is the subject's own (`origin: self`, `actor` equal to `about`), and an `observation` otherwise.
That keeps 🌊's three origins on #119 apart: a prince's own expression is their own signed item, outside this
descriptor; a familiar's attributed summary of it is a `self-report` that the familiar signs; a watcher's
"repeated ticks; cause unknown" is an `observation` to check, and a producer that names a cause marks the claim
`interpretation`. The signer is always the speaker (§6.7).

A body needs at least one claim or one withdrawal. The reader fails closed, as typed beacons do: a refused body
is dropped and counted, and never supersedes anything.

| Refusal | When |
|---|---|
| `too-large` | The canonical body is over 900 bytes. |
| `unknown-field`, `missing-field`, `shape`, `count` | The structure is wrong. |
| `not-integer`, `range`, `bad-token`, `bad-enum`, `bad-text` | A value is wrong. A bool or a float is never an integer. |
| `version` | `v` is not `familiar-projection/1`. |
| `window`, `before-window`, `validity`, `lease-too-long` | `window` runs backwards, `generated_at` precedes `window[1]`, or `valid_until` is not after `generated_at` or is more than 900 s after it. |
| `echo-source` | A source `ref` starts `canticle:`: a heard item is never a source (#119). |
| `scope`, `audience` | The item's scope is not host, lan, fleet or public, or is wider than some cited source's `audience`. |
| `lapsed-source` | A current body cites a source that lapsed before its `generated_at`. |
| `state-needs-record` | A `state` claim cites a `notice`. |
| `unknown-source`, `uncited-source`, `duplicate-id`, `duplicate-source`, `cites-withdrawn`, `empty` | The body contradicts itself. |
| `not-json`, `not-canonical` | The bytes are not canonical JSON. |
| `stale`, `conflict` | Receiver only: an older `generated_at` for the key, or a different body at the same one. |

## 3. When a claim is current

At receiver time *t*, a claim is current only while all of these hold:

1. Its item is live: not plucked, revoked, quarantined or missing from a complete snapshot; not superseded by a
   newer projection for the key; and *t* is before its local expiry.
2. *t* is before the projection's `valid_until`.
3. Every source it cites is neither withdrawn nor at a revision older than the newest this producer has named,
   and *t* is before the earliest `valid_until` this producer has ever stated for that revision.
4. Its body's `standing` is `current`.
5. The receiver's coverage is complete. Otherwise the claim is `carried`.

Each rule can only end currency, never extend it. The ledger behind rule 3 is kept per producer key: a
withdrawal sticks, and a stated validity can be shortened but never lengthened (`stated_until`, I-3 applied to
sources). Extending a source takes a new revision, which is new evidence. The ledger is never shared across
producers, because one station never overrides another (§6.5).

| Status | Means | Shown in |
|---|---|---|
| `current` | Every rule holds. | current, search, pending |
| `carried` | It would be current, but coverage is unknown. | current and search, marked; pending waits |
| `history` | A live item with `standing: history`. | history |
| `withdrawn` | A cited source was withdrawn, or its election revoked. | nowhere current |
| `source-superseded` | A cited source has a newer revision. | nowhere current |
| `source-lapsed` | A cited source's validity has passed. | nowhere current |
| `superseded` | A newer projection for the key arrived. | nowhere current |
| `lapsed` | The item expired or the lease passed. | nowhere current |
| `retracted` | The item was plucked, revoked, quarantined or found off air. | nowhere current |

When several apply, the first of these is reported: `withdrawn`, `source-superseded`, `retracted`,
`superseded`, `lapsed`, `history`, `source-lapsed`, `carried`. For a `history` body, a withdrawal is shown as a
note on the entry instead.

**Notice and record.** A crier's notice "rain from 15:00" is a `notice`: its validity is its own short life.
A ledger's "rain is committed for 15:00 to 17:00" is a `record`: an authority other than the broadcast sets its
validity. When the notice expires, only the claim that cites it goes. The `state` claim that cites the record
stays current, and nothing says the rain stopped (`n1-notice-versus-record`). A `state` claim may cite only
records, so a notice can never carry world state.

**What a producer must do.** The reader can check only what bodies show, so these are rules for producers:

- Cite only sources valid at `generated_at`, and keep the keep-on-air horizon within `valid_until`.
- On a withdrawal or revocation, re-issue every on-air projection that cites the source (mechanically, with
  no model call), and list the source under `withdrawn` until those projections' leases end. The receiver's
  ledger covers the time in between and blocks stale revival, but it only knows what it heard.
- Keep `generated_at` increasing per key across restarts, rehydrating from its own last item as a keeper does
  (K7). Never cite a heard canticle item (K3). Put actors it could not read in `unread`.

## 4. Producer cost and receiver dose

`ProducerCost` classifies each emission per producer key and projection key, from the bodies alone:

| Class | What it is | Model call |
|---|---|---|
| repeat | The same body again: a refresh re-issue or an at-least-once retry. The carousel looping one signed frame is not an emission. | no |
| mechanical | Every claim already appeared, resolved to its sources, in the key's last body: a re-stamp, or claims dropped after a withdrawal or lapse. | no |
| synthesis | Anything else. `no_new_evidence` counts the syntheses whose sources this producer had all cited before: a rephrase of known evidence. | yes |

The receiver never calls a model. Reads, search, matching and temporary retuning run over an index of each
claim's tokens (`topics`, `about`, the words of `text`). Two ids carry the rest:

- The **evidence id** of a claim is a hash of its sorted `(actor, ref, rev)` triples. Wording, producer, copy
  and timestamp play no part.
- **Support** is the number of distinct source actors a claim cites (R-INT-4). A topic's support is the number
  of distinct actors across current claims on that topic. A second familiar reading the same row is a second
  reader, not a second witness. A familiar is never a witness itself; it counts the actors it names.

Presentation dedupes on (label, evidence id), so the same kind of statement over the same evidence is shown
once, however it is worded and whoever sang it. An interpretation and a report over the same evidence are
shown separately.

## 5. Receiver views

| View | What it holds |
|---|---|
| current | Current and carried claims. Reading it is a peek: it consumes nothing. |
| search | The same, filtered by tokens. History only when asked for. |
| pending | Claims queued for presentation by interest (topics or actors, or a temporary retune with an absolute end). |
| history | Live `history` bodies, and entries a principal elected to keep. |

- **Presentation.** A claim is queued when it arrives or a retune makes it match, and comes due `window_ms`
  later. A newer claim with the same label and evidence keeps the queued entry's due time. At drain, currency,
  interest and `min_support` are checked again: a claim that stopped being current is settled, never presented
  late, and a carried one waits. A presented claim that later stops being current gets one note, with no claim
  text.
- **Gaps.** Record v1 `health` with `records_lost` or `no_datagrams`, or a restart, makes coverage unknown.
  Live claims become carried and wait; a complete snapshot restores coverage. An actor named in `unread` is
  shown as unknown. No host line ever uses a §6.3 rule 5 word; the checker tests this on every render.
- **Restart.** The journal, ledger, pending queue and presented set persist; coverage does not. Pending claims
  that lapsed while the receiver was down are settled at restart, so nothing catches up.
- **Retention.** A principal or a human may elect to keep a claim. A kept entry names its producer, subject,
  window and generation time, and when and by whom it was kept. It is marked historical, is never current,
  never counts as support, and is noted when its source is later withdrawn. A session may not keep what it
  heard (§6.4, I-10). Peeking, draining and keeping are three acts with three names.
- **Rendering.** Host lines carry the label, subject, producer, window, generation time, status, support and
  end of currency. Claim text appears only quoted, as data (I-6).

## 6. Fixtures and the checker

`projection.py` holds the reader (`read_descriptor`, `read_descriptor_bytes`), `ProducerCost`, the reference
`Receiver` and the fixture runner. A fixture (`familiar-projection-fixture/1`) names receivers and bodies, then
runs timed steps: `frame`, `retract`, `health`, `snapshot`, `restart`, `retune`, `retain`, `read`, `present`
and `descriptor`. Each step can state what it expects. Unknown keys, unknown steps and time going backwards
are fixture errors, so a typo cannot pass. Fixtures say `"synthetic": true`, use placeholder keys
(`f00d000000000001`, `f00d000000000002`), and compute record v1 idems as the station does.

| Case | Fixture | What it shows | Revert checks |
|---|---|---|---|
| AC1 | `a1-one-window-two-receivers` | Two receivers, eight reads, two searches, a refresh, two retunes and a re-stamp cost one synthesis, one mechanical re-issue and no receiver model call. | `test_ac1_*` |
| AC2 | `a2-expiry-withdrawal-supersession` | A source lapse, a withdrawal stated under another key, a newer source revision and a pluck each remove their claims from current, search and pending. | `test_ac2_*` |
| AC3 | `a3-partial-invalidation` | Only the claims citing the withdrawn source go. A fresh synthesis citing it again stays withdrawn. A restated validity is capped. A body citing a lapsed source is refused. | `test_ac3_*`, `test_ac2_ac3_*` |
| AC4 | `a4-elected-history` | A kept claim stays attributed and historical after its source is withdrawn: not current, not in default search, not support. A session cannot keep. A `history` body shows only as history. | `test_ac4_*` |
| AC5 | `a5-restart-after-validity` | A restart after the lease ends presents nothing. The restarted producer's same body is a repeat, its re-stamp citing the lapsed source is refused, its restated validity is capped, and an older body is `stale`. | `test_ac5_*` |
| AC6 | `a6-rephrase-no-weight` | Refreshes, a retry, a loop copy, a rephrase and a second familiar over one row keep support at 1 and are presented once. A second actor raises support to 2. | `test_ac6_*` |
| AC7 | `a7-receiver-gap` | Lost records and no datagrams make coverage unknown: claims carried, presentation waiting, the unread actor unknown. A complete snapshot restores coverage. | `test_ac7_*` |
| notice vs record | `n1-notice-versus-record` | The notice's lapse removes only its claim; the record's claim stays current. | `test_notice_*` |
| descriptor | `d1-descriptor-rules` | One body per reader rule. | — |

Each revert check puts one rule back to the naive behaviour it replaces (a receiver that summarizes on read,
validity that a restatement extends, support counted in claims, a gap read as current, and so on) and asserts
that the fixture guarding it then fails, with the expected message.

**What this does not prove.** The checker runs on one clock, so producer clock skew is out of scope (§14.6.3
would apply to body times as it does to `expires_at`). It assumes every frame was admitted as verified, as
#150 does, and models no loss or transport. It enforces no taint. It cannot tell an honest producer from one
that names actors it never read: support counts the actors a manifest-trusted producer names (I-11). It runs
in no harness.

## 7. Interfaces with other lanes

Coordinated through this note; this PR edits none of their files.

- **#126 (🪨, the Mirari wake emitter).** It keeps each shareable row as `{id, kind, topic}`. A row maps to a
  source: `actor`, the row's own `id` as `ref`, `rev` 1, `origin: self`, `authority: notice`, `audience` from
  the auth file. A batch holds up to 16 rows and a body cites at most 6 sources, so a batch could instead be one
  source whose `ref` is its batch identity; withdrawal is then per batch. Its summary maps to `report` claims.
  Its `from_canticle` and heard-topic filters are the producer side of the anti-echo rule; the reader's
  `canticle:` refusal is a second line. Four gaps would close:
  - *Validity.* A row has no validity of its own: it is current while its item is, at most `ttl_s` (300 s).
    `inactive_s` is when the emitter stops, not how long a row holds.
  - *Supersession.* Each batch has its own `state_key`, so batches never supersede each other and each lives
    out its `ttl_s`. A stable key per actor (`wake-<actor>`, say) would let each window replace the last.
  - *Revocation.* It stops the next sing and retracts nothing already accepted, as its README says. It would list
    the sources as `revoked` and re-issue.
  - *Retries.* A batch whose send failed is sung again without `refresh`, under a new seq. frond-ear `128094a`
    collapses only flagged refreshes, so a retry of an item it already pushed is pushed again. The control
    socket cannot set the flag, so either the station gains the idempotency #126's README names as a protocol
    change, or receivers collapse an equal digest from one principal for presentation, as R-INT-2 already does
    for weight and the checker's receiver does.
- **#120 (🪨) and #150 (the offline receiver-policy preview).** #150 decides whether an item may surface:
  ceilings, tuning, batches by count, quiet or maximum wait, mutes, gaps. Claim currency is a body-aware layer
  under that, and it can only cancel more. #150 keeps no retention store, index or summary cache; the kept
  history and token index here are proposals for #120. #150 marks observations carried after a gap and needs
  explicit reconfirmation, which a complete snapshot is here.
- **#145 (🪨) and #146 (🩸).** Untouched. Here the label, status, times and support are host-written, and claim
  text is always quoted. Whether reading `about` or `topics` taints a session (§14.12) is #145's call. A
  receiver's own synthesis would be derived content in #146's sense; this receiver makes none.
- **#147 and #149 (station-owned cues).** A cue is a station-owned notice whose window end is its validity.
  The world clock and event ledger that #149 keeps separate are what `authority: record` names. A familiar
  never cites a heard cue, only the ledger entry or its author's own elected row.
- **#142 (typed beacons).** Same reading discipline: unknown fields make a body unreadable, and a missing or
  expired value is unknown, never fine. A beacon's `reported` or `inferred` origin corresponds to the labels.
- **#51 (disposition).** A prince's own "stuck", relayed by a familiar, is a `self-report`; what it means, and
  what a receiver may do about it, stays #51's.
- **OpenClaw binding and frond-ear.** Their journal, carried view, candidate retraction, tombstones and
  late-push rules are the item-level donors. Claim-level currency and evidence dedupe would be new in both.

## 8. RFC amendments this would need

Named here, not made. None changes frame v2, receptor record v1 or the vectors.

1. **A registered content type** for the descriptor (§9.9, an id from 12–1023): compact CBOR with integer
   keys, like §17.3's aspect body. Until then, ctype 3 at `lan` scope only, under §9.9's rule for content whose
   schema a listener may not share: never wake-eligible, never accord-counted.
2. **A derived-claim dependency rule**, taking §6.3 rule 1 down to claims: a derived claim loses current-state
   authority when any source it cites is withdrawn, revised or lapses, not only when its item expires; and a
   stated validity only shortens.
3. **An R-INT addition**: equal evidence bases count once across producers, wordings and re-sings, extending
   R-INT-2 from equal body digests to equal evidence ids.
4. **Actor-signed election and withdrawal items**, so that a withdrawal reaches the receivers of every
   producer that read the source, not only of the one that learned of it.
5. **A familiar producer profile**, a sibling of §17.4: the 900 s lease, mechanical re-issue, no synthesis
   without new evidence, the anti-echo rule and a per-key `generated_at` that only increases.

## 9. What stays proposed

All of it: the descriptor, its bounds, the currency rule, the ledger, the labels, the producer classes, the
views and the retention election. Questions for the princes:

1. Is a principal's elected retention promotion under §6.4 and I-10, or a binding-local history that
   §14.12's memory rule does not reach? Who may elect it?
2. Do `about` and `topics`, which are sender tokens, taint a session that reads them (#145)?
3. Who may withdraw a source across producers (amendment 4)?
4. Should a body carry its source election's digest, as §17.3 carries a charter digest, so a receiver can see
   which election authorized a source?
5. What validity should a #126 row carry, now that it is its item's `ttl_s`? Should its `state_key` be stable
   per actor, so that each window supersedes the last?
6. Should a projection ride `chatter`, as #126 does, or `live-state`?
7. Are the 900 s lease and the 900-byte JSON bound right, or should the bound wait for compact CBOR?
