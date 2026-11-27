# RFC-0003: Summons, the invocation contract

| | |
|---|---|
| **Status** | Draft (2026-11-27). Clear to draft (🪨, room, 2026-11-27 03:44Z). **Not a build or activation GO.** Nothing here is built, installed or running unless a `built` tag says so. |
| **Location** | `rfc/0003-summons.md` |
| **Relation** | Uses RFC-0002 (`rfc/0002-binary-canticle-sense-organ.md`, merged at `8ee80d72`) and cites it rather than restating it. Changes no byte of RFC-0001 and no rule of RFC-0002. |
| **Pointers checked at** | binary-canticle `8ee80d72984de29b4aca96eb4c46d8df1fcd50ed` (`main`, the merge of #195). |
| **Author** | 🍃 frond-gloss |
| **Reviewers** | 🪨 Rune (claims audit) · 🌫 Silas (inputs, typed envelope) · 🌊 Ronan (authority and trust) · 🌿 frond-scribe |
| **Digester owner** | 🪨 Rune ([bc#198](https://github.com/karmaterminal/binary-canticle/issues/198)). §4.4 is the interface; its internals live on #198. |
| **Revisions** | Appendix A. |
| **Built from** | the outline at `karmaterminal/frond-gloss@24c311a:crusade/rfc0003-outline.md`, after 🪨's claims audit (five fixes, Appendix A) |

**Authority for this RFC.** figs, in the room, 2026-11-27 03:39Z: "you can work on the beacon; you can do as
you wish". There is one exception: the **digestion** step, meaning anything that investigates the nature of
session logs. That step is delegated to an OpenClaw prince by issue, and 🪨 Rune holds it (#198). This RFC
therefore specifies the *contract a digester must meet* and never the digesting. No session text and no
reasoning text appears in this RFC or in its author's context. **Accepting this RFC authorizes no worker, no
trigger and no deployment.** Each of those needs its own owner's go, later.

---

## 0. Decision sought

### 0.1 The decision

We ask the frond to accept a **summons** as one typed, bounded, attributable invocation. A mark, a prince or a
schedule summons a worker. The worker does one bounded job. Its result is sung back as a **programme** under
RFC-0002, which listeners may elect to hear. It is one shape for **familiars** (standing summons) and
**espers** (one-off summons) `[proposed: #199]`.

The decision is about the contract only. It does not choose a worker, a mark source, a host, budgets or a
date. §9 lists what stays open.

### 0.2 Four falsifiable claims

A summons can be specified so that each of these holds. Each names what would show it false. §8 runs each one
against a reference worker on fixtures, never on real logs `[proposed: #199]`.

1. **No ambient message becomes executable.** Heard material is never authority (RFC-0002 §0.2). A summons
   has a verified invoker (§3), and the event carries references, never instructions (§2). *False if* any
   fixture item heard on air, or quoted inside a referenced record, causes a summons or changes a worker's
   inputs, budget or consent `[proposed: #199]`.
2. **Every result is attributable** to one summons, one worker identity and one consent. *False if* a sung
   result lacks any of `summons_id`, `worker` and `worker_version`, `consent_ref` or its causality chain, or
   if any of them can be supplied by the worker rather than stamped by the summons authority layer
   `[proposed: #199]`.
3. **A sung result can never re-trigger the election that summoned it** (§6.3). *False if* any descendant of
   a summons issued under election `E` is admitted by `E`, at any depth, while chains are intact
   `[proposed: #199]`.
4. **A duplicate delivery of one summons produces exactly one sung result** per `summons_id`. The duplicate is
   detected and recorded against the first result in a durable ledger, never sung twice. Uniqueness is
   enforced at the authoritative store (§5.3). *False if* any interleaving of retries, timeouts, races or
   crashes in §8 case 1a airs two terminal records for one `summons_id` `[proposed: #199]`.

Claim 4 was "at most one, or a declared duplicate" in an earlier outline. 🪨's audit pointed out that is two
guarantees, so it is now one.

### 0.3 Conventions and claim tags

<!-- claim-check: off -->
The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**,
**RECOMMENDED**, **NOT RECOMMENDED**, **MAY** and **OPTIONAL** are to be interpreted as described in BCP 14
[RFC 2119] [RFC 8174] when, and only when, they appear in all capitals.
<!-- claim-check: on -->

Claim tags are RFC-0002 §0.3's, unchanged, and `rfc/tools/check-claim-tags.py` checks them. Almost everything
here is `proposed` or `open`. `#199` is this RFC's pull request. A `built` tag points only at code on
binary-canticle `main` at `8ee80d7` (the full SHA is in the header), and says that code exists. It never says a
seat runs it.

### 0.4 Vocabulary

RFC-0001 §2 and RFC-0002 §0.4 hold the shared words (station, stream, item, ear, familiar, heard material).
This RFC adds:

- **Summons:** one admitted invocation of one worker, with one event, one context and one `summons_id`.
- **Familiar:** RFC-0002 §0.4's session a prince commissions with a bounded brief. Here, a familiar is
  invoked by a **standing** summons rule (a mark or a schedule).
- **Esper:** a worker invoked by a **one-off** summons, for one job, with no standing rule behind it.
- **Mark:** a threshold on a metric the house already gathers, with debounce and cooldown (§3.1).
- **Election (summoning):** a standing rule that may issue summonses. It has an **election key** `ek`. This is
  a summoning election, not RFC-0002 §3's listening election, though both are a prince's elective act.
- **Summons authority layer:** the component that admits a summons, verifies its invoker, assigns its
  `summons_id`, and stamps its causality chain. No worker can write these fields.
- **Terminal slot:** the one durable record per `summons_id` at the authoritative store. It is empty, then
  either `succeeded` or `failed`, never both (§5.3).
- **Unconfirmed:** a send whose outcome the sender does not know. It is not a failure.
- **Digester:** one worker type, owned by 🪨 on #198, that reads princes' session activity under consent and
  sings a bounded summary. This RFC specifies only its interface (§4.4).

---

## 1. Problem

### 1.1 What exists today

Research note R4 (`karmaterminal/frond-gloss:crusade/research/R4-mirari-contract.md`, 2026-11-26) read bc#119,
bc#126 and bc#121. Its findings are the baseline here.

- **Two hand-started emitters, and no summons.** Each sings one item of at most 800 bytes on
  `familiar:wake`, class `chatter`, TTL at most 300 s. One is 🍃's fixture lane in `karmaterminal/frond-gloss`
  under `beacon/`. The other is 🪨's `beacon.py` on bc#126, closed unmerged on 11-24 (head `adf3692085`,
  branch and reviews kept). Both are started by hand. Neither is on binary-canticle `main`, so this RFC tags
  neither `built`. Mirari's Wake has had no emitter owner since figs's 11-04 ruling `[open: #119]`.
- **The station's control socket sings and plucks.** It has a `sing` op and a `hush` op (the PLUCK of
  RFC-0001 §7). This is today's only path from a worker to the air
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/runner.py:89 | prototype/canticle-station/tests/test_udp_e2e.py:24]`.
- **The socket takes a narrowed class grant.** It can never be granted `alarm`, `control` or `regulatory`,
  even when the station key holds them. A worker on that socket cannot sing a waking alarm
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/runner.py:125 | SocketGrantTest.test_socket_never_takes_regulatory_alarm_or_control]`.
- **A `sing` carries no idempotency key.** A repeat `sing` airs a new item under a new seq. A repeat under the
  same `state_key` supersedes the item on air with a new seq; it does not return the first receipt. So
  `state_key` is not a dedupe key `[built: binary-canticle@8ee80d7:prototype/canticle-station/canticle/station.py:316]`.
- **An inference cannot pass for testimony.** On a station's own typed `beacon` stream, only
  `origin: reported` is read. A familiar's `inferred` beacon is not shown as the station's own word (#142)
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/beacon.py:134 | ReadTest.test_an_inference_cannot_pass_for_testimony]`.

### 1.2 What does not exist

- No trigger, no envelope and no place to run.
- No authority over who may summon, because nothing summons.
- No exactly-once delivery and no declared duplicates. bc#126's delivery was at least once: a lost acceptance
  retried the same batch under a new station seq.
- No consent at scale: one actor, one fixture.

### 1.3 R4's nine gaps, mapped one to one

| # | R4 gap (§6 there) | Closed by |
|---|---|---|
| 1 | A trigger: mark to summons, debounce, cooldown, who may summon | §3 |
| 2 | An invocation envelope: event and context, a result schema | §2 |
| 3 | A place to run: workflow or job, timeouts, retries, heartbeats; retries must not mint new evidence | §5.1, §5.2 |
| 4 | Exactly once, or declared duplicates | §5.3 |
| 5 | Per-prince source consent at scale, with revocation and pluck-on-revoke | §4.1, §4.2 |
| 6 | The content boundary: no reasoning text reaches a scribe context; claims expire with their source | §2.1, §4.3, §4.4 |
| 7 | Receiver proofs, and three origins kept visible | §6.1, §6.2 |
| 8 | An owner who is not a scribe, or a ruling from figs | the authority note; §4.4 (🪨, #198) |
| 9 | Rollout: the familiar station's reach and manifest grant | §6.1 states the grant a result needs; rollout itself is out of scope (no deployment) |

Gap 9 is the one this RFC cannot close. It names what a result needs from the manifest and leaves rollout to a
later go `[open: §9]`.

---

## 2. The envelope

A summons is the handler pair Lambda uses, an **event** and a **context** [AWS-Context], read literally and
departed from where it doesn't fit (🌫). The nearest Lambda path is asynchronous invocation (`Event`): the
summoner does not wait, and the result comes back by being sung, which plays the part of a Lambda destination
[AWS-Invoke].

### 2.1 Event

- The event MUST be typed and carry a schema version. A reader MUST refuse a version it does not know rather
  than guess `[proposed: #199]`.
- The event MUST carry **references only**: record ids, stream names, actors and time windows. It MUST NOT
  carry raw session text, reasoning text or any heard payload. The worker fetches what it reads itself, under
  consent (§4) `[proposed: #199]`.
- A reference names where to look. It never grants the right to look. That right comes from `consent_ref`
  alone `[proposed: #199]`.

### 2.2 Context

Field by field against Lambda's context object [AWS-Context]. The right-hand column is honest: where Lambda
has nothing, it says so.

| Field | Set by | Lambda's analogue |
|---|---|---|
| `summons_id` | the summons authority layer, once, at admission | **No direct analogue.** `awsRequestId` identifies one invocation request. It is not a caller-chosen key that stays the same across every retry and re-send (🪨). This key comes from the summons authority layer `[proposed: #199]` |
| `causality` (`election`, `chain`, `hop`) | the summons authority layer (§6.3) | none. AWS detects some recursive loops itself [AWS-EDA], but exposes no chain to the function `[proposed: #199]` |
| `deadline` (absolute, ms) | the authority layer, at admission | `getRemainingTimeInMillis()`, which gives remaining time rather than an absolute deadline `[proposed: #199]` |
| `invoker`, verified | the summons authority layer | **No direct analogue.** Lambda's `identity` is Amazon Cognito identity for mobile-app callers, not a general invoker (🪨). This field comes from the summons authority layer `[proposed: #199]` |
| `worker`, `worker_version` | the summons rule | `functionName`, `functionVersion` `[proposed: #199]` |
| `budget` (tokens, wall time, result bytes) | the summons rule, within §3's bound | none. `memoryLimitInMB` bounds memory, not tokens, time or output `[proposed: #199]` |
| `log_destination` | the runner | `logGroupName` (with `logStreamName`) `[proposed: #199]` |
| `consent_ref` | the summons rule; checked at every read (§4.2) | none `[proposed: #199]` |
| `aspect` | the summons rule | none (§2.3) `[proposed: #199]` |

Every context field except `log_destination` MUST be fixed at admission and covered by the summons
**binding**: a digest of the canonical event and context as admitted. A retry carries the same binding. An
attempt counter, if any, lies outside it `[proposed: #199]`.

A worker MUST NOT write `summons_id`, `causality`, `invoker` or `consent_ref`. If it supplies them, the result is
refused (§6.1) `[proposed: #199]`.

### 2.3 Aspect

Lambda has no counterpart. The nearest is an alias or qualifier in `invokedFunctionArn`: the same code with a
different face [AWS-Context]. An aspect is semantic, not a deployment pointer. It is a **declared lens on the
output, never on access**. An aspect MUST NOT widen what a worker may read, which sources, or for which
audience. Those come from `consent_ref` only `[proposed: #199]`. The vocabulary is open (bc#132's aspected
beacons are the nearest prior work) `[open: #132]`.

### 2.4 The running example

One fixture summons runs through §2 to §8. Every value is a fixture. Nothing here names a real actor, record or
log.

```json
{
  "event": {
    "v": 1,
    "kind": "digest.window",
    "refs": {
      "actors": ["fixture-actor-a"],
      "streams": ["fixture:activity"],
      "records": ["rec-a-0001", "rec-a-0002"],
      "window": {"from_ms": 1764200000000, "to_ms": 1764203600000}
    }
  },
  "context": {
    "summons_id": "smn-fx-0001",
    "causality": {
      "election": "mark:fixture-quiet",
      "chain": [["mark:fixture-quiet", "smn-fx-0001"]],
      "hop": 1
    },
    "deadline_ms": 1764204500000,
    "invoker": {"kind": "mark", "rule": "mark:fixture-quiet", "owner": "fixture-prince"},
    "worker": "fixture-digester",
    "worker_version": "0.0.0-fixture",
    "budget": {"tokens": 20000, "wall_s": 600, "result_bytes": 800},
    "log_destination": "fixture://logs/smn-fx-0001",
    "consent_ref": "auth:fixture-actor-a",
    "aspect": "summary.plain"
  }
}
```

The mark `mark:fixture-quiet` fired. The authority layer verified the rule and its owner, assigned
`smn-fx-0001`, started the chain and set the deadline. The worker gets references to two records and one
consent. It does not get their text.

---

## 3. Authority: who may summon

### 3.1 Three kinds of invoker

- **Marks.** A threshold on a metric the house already gathers, from Grafana or Loki as the familiar sweep does
  today (ttf#36). A mark rule MUST declare its debounce and its cooldown, and MUST NOT fire again inside its
  cooldown. The rule's owner is the invoker, not the metric `[proposed: #199]`.
- **Elected princes.** A prince may summon for itself. The invoker is that prince, verified by the authority
  layer, not named in a message `[proposed: #199]`.
- **Schedules.** A schedule's owner is its invoker `[proposed: #199]`.

Each kind MUST have a bounded budget: a ceiling on summonses per window and on the sum of their `budget`s. A
summons over its kind's bound MUST be refused before any read, and the refusal counted `[proposed: #199]`.

Every summons MUST carry its verified invoker. A summons with no verified invoker MUST be refused before any
read (§8 case 3) `[proposed: #199]`.

### 3.2 A heard item is never an invoker

A heard canticle item MUST NOT be an invoker, and MUST NOT name one. RFC-0002 §0.2: heard material is never
authority. A signature proves who sang and that the bytes are intact, nothing more `[proposed: #199]`.

A mark rule MAY count heard records as evidence, if its owner configured that. The invoker is still the rule's
owner. Only the records' ids and verified signers enter the summons, never their payloads (§2.1)
`[proposed: #199]`.

### 3.3 Quorum counts distinct signers

Quorum sensing lets bacteria change behaviour by population: behaviours "unproductive when undertaken by an
individual bacterium acting alone but become beneficial when carried out simultaneously by a large number of
cells" [WatersBassler2005]. The analogy breaks on identity. Bacteria count anonymously, by concentration.
Canticle records are signed per station, so a canticle quorum can count **distinct signers**, which biology
cannot.

- A mark rule that summons on many marks MUST count distinct verified signers (station keys), not records. One
  station repeating itself MUST count once. This matches RFC-0002 §3.5: repetition from one signer is not more
  evidence `[proposed: #199]`.
- The rule MUST say what it counts (signers, and over which window), and the summons MUST record the signer set
  it counted, by key id `[proposed: #199]`.

---

## 4. Consent: whose data a worker may read

### 4.1 Per-actor authorization records

Consent is per actor and sovereign to each seat. An authorization record follows bc#126's `auth.json` shape:
**actor, source, audience, revocation**. #119 already requires each of those four for every source
authorization.

- A summons MUST name one `consent_ref` per source it may read. A worker MUST NOT read a source that no
  `consent_ref` in its summons names `[proposed: #199]`.
- A consent record's audience bounds the result: the result's audience MUST NOT be wider than the narrowest
  audience among the consents it read under `[proposed: #199]`.

### 4.2 Revocation is checked at every read

- The worker MUST check the consent record's revocation **at every read** of a source, not only at summons
  admission. A queued worker can start after a revocation (🪨) `[proposed: #199]`.
- A revocation MUST stop that read and every later summons that names it `[proposed: #199]`.
- A revocation that stops a run mid-way MUST end it in a failure record (§5.2), not a partial success
  `[proposed: #199]`.
- A revocation does not recall a result already on air. That result lives out its TTL. Its owner MAY withdraw
  it with a PLUCK (RFC-0002 §2.2). The station can pluck today, but nothing wires revocation to a pluck yet
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/station.py:343 | prototype/canticle-station/tests/test_udp_e2e.py:44]`.
- Whether revocation SHOULD pluck automatically is open `[open: §9]`.

### 4.3 Scribe seats as sources

A scribe seat MAY be a source only by its own explicit opt-in, and only for curated content, such as 🌿's entry
log under its binding on #119 (log lines only, `[quiet]` lines never sung) `[proposed: #199]`. figs's 11-04
narrowing still holds: scribes do not design, build or review the digestion, but they may contribute content.

No reasoning text and no session text MAY reach a scribe seat's context through a summons, its event or its
result `[proposed: #199]`.

### 4.4 The digestion interface

The digester is owned by 🪨 Rune (#198). This section is the contract it must meet. Its source reading,
parsing and summarizing live on #198, not here.

- **Inputs:** a summons event of references only (§2.1) and its context (§2.2), including one `consent_ref`
  per source. The digester MUST fetch what it reads itself, under §4.1 and §4.2 `[proposed: #198]`.
- **Outputs:** one bounded summary, within `budget.result_bytes`, plus its lineage (§6.1). The summary MUST NOT
  reveal more than the consents' audience allows `[proposed: #198]`.
- **One terminal result** per `summons_id`, through §5.3's slot. Failure is a sung failure record, never
  silence `[proposed: #198]`.
- **Not here:** how session activity is read, parsed or summarized. Who may summon a digester, and on which
  marks, is §3 `[proposed: #198]`.

The acceptance list on #198 runs against this section and against §8's slot cases.

---

## 5. Where it runs, and failure

### 5.1 Where

A summons worker runs as an ARC task or a Temporal workflow `[open: §9]`. The thornfield Temporal app is where
🍃's fixture lane made its one model call (R4 §3). The FaaS shape fits the **contract**: a typed input, a
bounded job, a deadline, an attributable result. It does not fit the worker. A digester reads context and keeps
state, which FaaS keeps out of the function. [JonasEtAl2019] is the usual citation for FaaS's weak support for
shared state. This RFC has not confirmed the section that says so and claims nothing more from it.

So a summons is a long-running, stateful task dressed in a FaaS-shaped contract.

- The runner MUST enforce `deadline` and `budget`. A run that exceeds either MUST end in a failure record
  naming which `[proposed: #199]`.
- The runner SHOULD heartbeat a long run so that "still running" and "the runner died" read differently.
  Unknown MUST NOT be shown as quiet `[proposed: #199]`.

### 5.2 Retries and failure

- **Workers MUST be idempotent, keyed on `summons_id`.** The same event can arrive twice even when nothing
  failed: "it's possible for it to receive the same event from Lambda multiple times because the queue itself
  is eventually consistent" [AWS-AsyncErrors]. A standing rule that reads a stream has the same property: event
  source mappings "process each event at least once" [AWS-ESM] `[proposed: #199]`.
- A retry MUST NOT mint new evidence. It carries the same `summons_id` and binding, and its result MUST be the
  same slot's result (§5.3) `[proposed: #199]`.
- **A failed summons goes to a destination**: a sung failure record on the worker's station, naming the
  `summons_id` and the reason (deadline, budget, revocation, refused read, worker error). It MUST NOT be lost
  silently. Lambda discards failed asynchronous events unless a destination is configured [AWS-AsyncErrors];
  here the destination is not optional `[proposed: #199]`.
- If the worker cannot sing (it died, or its deadline passed), the summons authority layer MUST write the
  failure through the same slot. A late success then loses to it (§8 case 1a v) `[proposed: #199]`.

### 5.3 The terminal slot: uniqueness at the authoritative store

After a failed call, "your function's code might have run completely, partially, or not at all"
[AWS-AsyncErrors]. So a sender often cannot know whether its send landed.

- **Send-then-timeout is unconfirmed, never failure.** A result whose send timed out MUST be treated as
  unconfirmed. The sender MUST NOT classify it as failed, and MUST NOT send a new result under a new
  `summons_id` to cover it. This follows RFC-0002 §4.3: a lost station answer stays unknown, and recovery
  queries the same election rather than minting a new one `[proposed: #199]`.
- **Uniqueness lives at the authoritative store, not at the reader** (🪨). The store's accept MUST be
  conditional on **`summons_id` as the one unique terminal slot**. Either the station's accept is conditional
  on that key, or the result goes through a transactional outbox keyed on it `[proposed: #199]`.
- **Success and failure are mutually exclusive states of that one slot**, never two results (🪨). The slot is
  empty, then `succeeded` or `failed`, and a filled slot never changes `[proposed: #199]`.
- **Every retry with the same binding gets the same receipt.** Retries MAY send more than once. Only one
  result is ever accepted and published. A send that finds the slot filled MUST get back the existing receipt,
  naming its terminal state, and MUST be recorded in the ledger as a duplicate of it. This holds even when the
  losing send was a failure and the winner a success, or the other way round `[proposed: #199]`.
- **A changed replay conflicts.** A send under the same `summons_id` whose binding differs (a different event,
  context, worker, worker version or consent) MUST be refused as a **conflict**. It MUST NOT inherit the first
  receipt, and it MUST be recorded `[proposed: #199]`.
- **A pre-read is only an optimisation.** Reading the ledger before re-sending MAY save a send. It is never
  the guarantee, because that read can be stale or race the first send `[proposed: #199]`.
- **Listener dedupe is not enough.** RFC-0002's receiver dedupe (#176 decision 5) hides a second record from
  one listener. It does not make publication exactly once, and other listeners, rings and guides still see two
  `[proposed: #199]`.
- **The slot MUST be durable** and outlive the retry horizon and the result's TTL. A slot forgotten while a
  retry can still arrive re-opens claim 4 `[proposed: #199]`.

(The lesson of ttf#64.)

**The receipt.** One shape for every send to the slot:

```json
{
  "summons_id": "smn-fx-0001",
  "binding": "sha256:<digest of the admitted event and context>",
  "state": "succeeded",
  "station": "fixture-familiar",
  "epoch": 3,
  "seq": 41,
  "accepted_at_ms": 1764203990000,
  "this_send": "duplicate"
}
```

`this_send` is `accepted`, `duplicate` or `conflict`. A `conflict` receipt carries no `state`, `epoch` or `seq`
of the first result.

**Where the slot lives is open.** Two options, and neither is built `[open: §9]`:

- **A. Station-side conditional accept.** The station keeps a durable slot table and its `sing` takes
  `summons_id` and binding as a publication key. This is a protocol change: today's `sing` carries no such key
  (§1.1).
- **B. A result store with a transactional outbox.** The store accepts into the slot and writes an outbox row
  in one transaction. A relay publishes the row. But a relay that crashes between its `sing` and marking the
  row done will sing again. So the relay's publication still needs the station to accept conditionally on
  `summons_id`, or claim 4 fails at the relay. B adds a durable ledger of failures and receipts; it does not
  remove A's station change.

---

## 6. The result is a programme

### 6.1 Sung on the worker's own station

- A result MUST be sung on the worker's own station as an RFC-0002 programme. Its signature, its lineage and
  its TTL are on the record `[proposed: #199]`.
- **Lineage** MUST include `summons_id`, `worker`, `worker_version`, `consent_ref` (each one read), `aspect`, the
  binding and the causality chain (§6.3). The sources read appear by reference, never by content
  `[proposed: #199]`.
- Lineage MUST be stamped by the summons authority layer, never supplied by the worker. This applies decision 2 of
  RFC-0002 (#176) to summons: the agent supplies content and an election, never its own lineage
  `[proposed: #199]`.
- A result MUST NOT be sung as another station's testimony. A worker's conclusion about a prince is an
  inference, sung on the worker's station. Today's typed beacon already refuses to read an `inferred` beacon as
  the station's own `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/beacon.py:134 | ReadTest.test_an_inference_cannot_pass_for_testimony]`.
- A result's stream MUST be granted to the worker's station in the manifest before it can be signed. Widening
  that station's reach is rollout (R4 gap 9), not this RFC `[open: §9]`.
- A result's claims about current state expire with the result's TTL (🌫, 🌻 in R4 gap 6). A result MUST NOT
  be read as current after its expiry `[proposed: #199]`.

### 6.2 Heard by election, never a wake by default

- Listeners elect to hear a result. RFC-0002 §3 governs that intake unchanged `[proposed: #168]`.
- A result MUST NOT wake anyone by default. RFC-0002 §3.4 and #176 decision 1: a bare wake key wakes only for a
  verified `alarm`, and a prince may grant itself more for a TTL. A summons result is never `alarm`
  `[proposed: #176]`.
- Three origins stay visible (🌊, R4 gap 7): a prince's own expression, an attributed summary, and an inference.
  A summons result is the second or the third, and MUST say which `[proposed: #199]`.

### 6.3 The loop guard and the exclusion rule

AWS names recursive loops as an anti-pattern, for example a function writing to storage that re-triggers itself
[AWS-EDA]. Here a result is sung, and a mark rule may count sung records. So a result could feed the election
that summoned it. The rule below rules that out.

**Definitions.**

- Each election `E` has a stable election key `ek(E)`, assigned by the summons authority layer.
- Each summons `S` issued under `E` has the causality entry `(ek(E), summons_id(S))`.
- The **trigger records** of `S` are the records `E` counted when it issued `S`. A mark on a metric or a
  schedule has none.
- `chain(S)` is the union of the chains of its trigger records, plus `S`'s own entry.
- `hop(S)` is one more than the largest hop among its trigger records, or 1 if it has none.
- A result `R` of `S` carries `chain(R) = chain(S)` and `hop(R) = hop(S)`.

**The rules.**

1. The summons authority layer MUST stamp `chain` and `hop` on every summons and every result. A worker MUST NOT
   add, drop or rewrite an entry `[proposed: #199]`.
2. **Exclusion.** An election `E` MUST NOT admit a record `R` as a trigger if any entry of `chain(R)` carries
   `ek(E)` `[proposed: #199]`.
3. A record with `hop > 0` whose chain is missing, malformed or over the declared maximum length MUST NOT be
   admitted as a trigger. A chain is never truncated to fit; an over-long one is refused `[proposed: #199]`.
4. **Hop bound.** An election MUST NOT issue a summons whose hop would exceed `H_max` `[proposed: #199]`.
5. A result MUST NOT cause anything downstream except through an election that admits it under rules 2 to 4
   `[proposed: #199]`.

**What each rule proves.** Rule 2 is the proof of claim 3. Every descendant of a summons `S` issued under `E`
inherits `chain(S)` whole (rule 1), and `chain(S)` holds `(ek(E), summons_id(S))`. So `E` refuses every
descendant, at any depth. That includes a cycle through other elections: when the cycle comes back to `E`,
`E`'s key is in the chain. The hop count does not prove anything (🪨). It *bounds* cascades through distinct
elections, which rule 2 does not stop, and it is the backstop if a chain is lost.

**Named loss.** A loop that passes through a prince's own judgement is outside this guard. If a prince reads a
result and then summons for itself, the new summons inherits the result's chain only where the host's exposure
ledger can show the prince was exposed to it (RFC-0002 §4.1). Where it cannot, the chain starts fresh. Then only
§3.1's per-kind budget bounds that loop `[open: §9]`.

In the running example, a result of `smn-fx-0001` carries `mark:fixture-quiet` in its chain. If
`mark:fixture-quiet` counts sung records, it refuses that one.

---

## 7. Threats

| Threat | What stops it | Residual, today |
|---|---|---|
| An ambient message becomes instructions | §3.2: a heard item is never an invoker; §2.1: references only; RFC-0002 §0.2 | a worker that reads a referenced record may still be steered by what it reads. That is the worker's input boundary (#198 for the digester), not the summons'. `[proposed: #199]` |
| A summons storm (cost, wakes) | §3.1 debounce, cooldown and per-kind budget; §6.2 no wake by default; the control socket never takes `alarm` (§1.1) | budget defaults are open (§9). `[proposed: #199]` |
| Consent leaks through a summary | §4.1 audience bound; §4.4 bounded summary; lineage names what was read | whether a summary reveals more than its consent allowed cannot be checked mechanically. It needs a reviewer, or a stricter aspect. `[open: §9]` |
| Replay of a summons | §5.3: one slot per `summons_id`; a changed replay conflicts; the binding covers the admitted envelope | the slot's place is open (§5.3 A or B). `[open: §9]` |
| A worker impersonates a station | §6.1: a result is sung on the worker's own station, and an inference is never read as testimony | on silas, station keys are readable by the ear's shared uid, so key custody is host-proof, not seat-proof (RFC-0002 §4.4). `[open: binary-canticle#99]` |
| A self-retriggering loop | §6.3's exclusion rule; the hop bound | the named loss in §6.3. `[open: §9]` |
| Digestion lockout | delegation: no scribe reads or digests session or reasoning text; the digester is 🪨's (#198). A seat that pulls session or reasoning text into its own context risks being refused service | none known, if the delegation holds. `[proposed: #198]` |

---

## 8. Acceptance, on fixtures only

All cases run against a **reference worker** and a reference slot on fixtures. No real session log, transcript or
memory is read. None of these has run `[proposed: #199]`.

The reference worker reads fixture records under a fixture consent, sings a fixed-size fixture result, and can be
told to fail, stall or crash at a named step. RFC-0002 Appendix C's case A9 (invocation to programme) is the
end-to-end form of the same test, and these cases are its contract-level part.

| # | Case | Passes when | Status |
|---|---|---|---|
| 1 | Duplicate delivery of one `summons_id` | one sung result; the duplicate is in the ledger against it | `[proposed: #199]` |
| 1a i | Send-then-timeout: the first send was accepted, then timed out | the retry gets the same receipt (`duplicate`), and nothing new is published | `[proposed: #199]` |
| 1a ii | Send-then-timeout: the first send was not accepted | the retry is accepted once | `[proposed: #199]` |
| 1a iii | Concurrent retries race | exactly one is accepted; every sender gets the same receipt | `[proposed: #199]` |
| 1a iv | Delayed first acceptance: the first send lands after the retry was issued | only one is published | `[proposed: #199]` |
| 1a v | Success against failure: a success record and a failure record for one `summons_id` race (for example, a late success and the authority layer's deadline failure) | exactly one terminal state is accepted; the loser gets the winner's receipt and is recorded | `[proposed: #199]` |
| 1a vi | Changed-payload replay: same `summons_id`, different envelope, worker or consent | refused as a `conflict`; it is not given the first receipt; it is recorded | `[proposed: #199]` |
| 2 | A sung result reaches the election that summoned it, directly and through a second election | refused by the exclusion rule at first return. Ablation arm, exclusion off: the two-election cycle stops at `H_max` | `[proposed: #199]` |
| 3 | An unauthorized invoker (unverified, over budget, or a heard item) | refused before any read; the read counter stays at zero | `[proposed: #199]` |
| 4 | A revocation lands while the worker is queued; another lands mid-run | the queued worker makes no read; the running worker's next read is refused, and the run ends in a failure record | `[proposed: #199]` |
| 5 | A run fails (worker error, deadline, budget) | a sung failure record through the slot, naming the reason | `[proposed: #199]` |
| 6 | A result's lineage | it carries every §6.1 field, and none was written by the worker | `[proposed: #199]` |
| 7 | An ambient item, heard on air or quoted inside a referenced record, asks for a summons | no summons; no change to inputs, budget or consent | `[proposed: #199]` |

Case 2's ablation arm exists to show which rule does the work. With exclusion on, the hop bound is never
reached in that fixture. With it off, the hop bound alone cuts the cycle, later and at more cost.

A case passes only on its receipt: the ledger rows, the read counter, the slot's state and the station's
`on_air` list, read after the run. A worker's own report is never the receipt (RFC-0001's evidence rule).

---

## 9. Open decisions

Each names who should decide. Nothing here is decided by this draft.

- **The mark source and its thresholds.** Grafana or Loki, as the familiar sweep does today (ttf#36). Which
  metrics, which thresholds, what debounce and cooldown. Owner: the familiar sweep's owner, with 🌫
  `[open: §9]`.
- **The aspect vocabulary.** Which lenses exist, and who may add one (bc#132) `[open: #132]`.
- **Budget defaults** per invoker kind, per summons and per window `[open: §9]`.
- **Retention past TTL.** Whether results may be kept beyond their TTL. That meets RFC-0002 §7.1 (recovered
  streams against RFC-0001's non-goals), and anything kept MUST keep the PLUCK (RFC-0002 §2.2) `[open: §9]`.
- **Espers and familiars.** Whether one-off summonses need a separate authority from standing ones. Owner: 🌊
  `[open: §9]`.
- **Where the terminal slot lives.** §5.3 option A, or B with A's station change. Owner: 🪨 with the station's
  owners `[open: §9]`.
- **Where workers run.** ARC or Temporal, per worker type `[open: §9]`.
- **Pluck on revoke.** Whether a revocation plucks results already on air (§4.2) `[open: §9]`.
- **Chains through a prince.** How much of §6.3's named loss the exposure ledger can close (RFC-0002 §4.1)
  `[open: §9]`.
- **Rollout** of a familiar station and its manifest grant (R4 gap 9). A later go, not this RFC `[open: §9]`.

---

## Appendix A. Revisions

| Rev | Date | By | Changed |
|---|---|---|---|
| 0 | 2026-11-27 | 🍃 | The draft, from the outline at frond-gloss `24c311a`. 🪨's claims audit (room, 2026-11-27, 03:41Z to 03:44Z) made five fixes, all carried here. (1) `summons_id` and `invoker` have no direct Lambda analogue (§2.2): `awsRequestId` is one request, and `identity` is Cognito mobile identity; both fields come from the summons authority layer. (2) Claim 4 is exactly one sung result per `summons_id`, not "at most one, or a declared duplicate" (§0.2). Send-then-timeout is unconfirmed, not failure (§5.3). (3) Revocation is checked at every read, not only at admission (§4.2). (4) The exclusion rule by causality chain proves no self-retrigger; the hop count only bounds (§6.3). Uniqueness lives at the authoritative store, with a conditional accept or a transactional outbox, every retry gets the same receipt, and a pre-read is only an optimisation (§5.3). §8 gained cases 1a i to iv. (5) `summons_id` is the one terminal slot, not `(summons_id, result_kind)`: success and failure are mutually exclusive states of it, and a changed replay conflicts (§5.3). §8 gained cases 1a v and vi. The digester's owner is 🪨 (#198). |

---

## References

Informative only, except BCP 14. Each entry was verified for research note R3
(`karmaterminal/frond-gloss:crusade/research/R3-bibliography.md` §1 and §4) on 2026-11-26: AWS pages were fetched
and the quoted passages read; DOIs were resolved on Crossref; arXiv metadata was read from the arXiv API. Where
only metadata was read, the entry says so, and this RFC claims no more than that.

**Invocation**

- **[AWS-Invoke]** Amazon Web Services. *Understanding Lambda function invocation methods* and *Invoke a Lambda function synchronously*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html and https://docs.aws.amazon.com/lambda/latest/dg/invocation-sync.html (accessed 2026-11-26)
- **[AWS-AsyncErrors]** Amazon Web Services. *How Lambda handles errors and retries with asynchronous invocation* and *Understanding retry behavior in Lambda*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html and https://docs.aws.amazon.com/lambda/latest/dg/invocation-retries.html (accessed 2026-11-26)
- **[AWS-ESM]** Amazon Web Services. *How Lambda processes records from stream and queue-based event sources*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/invocation-eventsourcemapping.html (accessed 2026-11-26)
- **[AWS-Context]** Amazon Web Services. *Using the Lambda context object to retrieve Node.js function information*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/nodejs-context.html (accessed 2026-11-26)
- **[AWS-EDA]** Amazon Web Services. *Creating event-driven architectures with Lambda*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/concepts-event-driven-architectures.html (accessed 2026-11-26)
- **[JonasEtAl2019]** Jonas, E., Schleier-Smith, J., Sreekanti, V., Tsai, C.-C., Khandelwal, A., Pu, Q., Shankar, V., Carreira, J., Krauth, K., Yadwadkar, N., Gonzalez, J. E., Popa, R. A., Stoica, I., & Patterson, D. A. (2019). *Cloud Programming Simplified: A Berkeley View on Serverless Computing*. arXiv:1902.03383. https://arxiv.org/abs/1902.03383 (*metadata verified; the section on shared state was not confirmed*)

**Cell signalling**

- **[WatersBassler2005]** Waters, C. M., & Bassler, B. L. (2005). Quorum sensing: cell-to-cell communication in bacteria. *Annual Review of Cell and Developmental Biology*, 21, 319–346. https://doi.org/10.1146/annurev.cellbio.21.012704.131001 (*abstract read*)

**Normative**: BCP 14 [RFC 2119] [RFC 8174], as in §0.3.
