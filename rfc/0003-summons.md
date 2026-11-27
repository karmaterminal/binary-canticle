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
2. **Every result is attributable** to one summons, one worker identity and the set of consents it read
   (🌊, review on #199). The worker identity is the one its runner attests it ran (§5.1), not only the one
   the rule configured `[proposed: #199]`. *False if* a sung result lacks any of `summons_id`, `worker`,
   `worker_version` and `worker_artifact`, a `consent_ref` for each source read, or its causality chain, or
   if any of them can be supplied by the worker rather than stamped by the summons authority layer. *Also
   false if* a success is accepted whose runner attestation is missing or names another artifact (§8 case
   10), or that read under a `consent_ref` whose record does not grant that read (§4.1, §8 case 8)
   `[proposed: #199]`.
3. **A sung result is never admitted as a trigger by the election that summoned it**, while chains are intact
   (§6.3). Two named-loss paths are outside this claim: a loop through a prince's own judgement, and a metric
   whose declared inputs are not its real inputs. Only §3.1's budget bounds those (🌿, overclaim check on
   #199) `[proposed: #199]`. *False if* any descendant of a summons issued under election `E` is admitted by
   `E`, at any depth, while chains are intact `[proposed: #199]`.
4. **A duplicate delivery of one summons produces exactly one sung result** per `summons_id`. The duplicate is
   detected and recorded against the first result in a durable ledger, never sung twice. Uniqueness is
   enforced at the authoritative store (§5.3). *False if* any interleaving of retries, timeouts, races or
   crashes in §8 case 1a airs two terminal records for one `summons_id` `[proposed: #199]`. Claim 4 has two
   halves (🪨, review on #199). **Safety:** never two published records for one `summons_id`, under every
   interleaving. A record is identified on air by `(station key, summons_id)`, so the same accepted record
   re-aired under a new seq or epoch is still one record (§6.1). **Liveness:** exactly one is eventually
   published, while the relay can replay and the station's slot lasts (§5.3). *Also false if* a slot filled
   before a crash is never published after its relay recovers (§8 case 1a vii) `[proposed: #199]`.

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

Prior art is cited where it bears, in RFC-0002 §0.9's style: what the source establishes, and **where it
breaks** for a summons. These notes are informative. Each source's entry in [References](#references) says
how much of it was read, and the note claims no more than that.

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
  `summons_id`, and stamps its causality chain. No worker may write these fields (§2.2). Nothing of it is
  built (🌿, overclaim check on #199) `[proposed: #199]`.
- **Terminal slot:** the one durable record per `summons_id` at the authoritative store. It is to be empty,
  then either `succeeded` or `failed`, never both (§5.3). It is not built (🌿, overclaim check on #199)
  `[proposed: #199]`.
- **Unconfirmed:** a send whose outcome the sender does not know. It is not a failure.
- **Attempt:** one run of the worker for one summons. A summons has at most `retry.max_attempts` of them
  (§5.2). A **send** is one delivery of a result to the slot. An attempt may make several sends.
- **Retry horizon** and **replay horizon:** the last instants at which an attempt may still send, and at
  which a filled slot may still be replayed to the station (§5.2).
- **Input key:** the digest of a summons's worker and event, without its `summons_id` (§5.2). Poison is
  counted against it, and a **parked** input key admits no summons until it is released.
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
- **The station's control-socket `sing` carries no idempotency key.** A repeat `sing` airs a new item under a new seq. A repeat under the
  same `state_key` supersedes the item on air with a new seq; it does not return the first receipt. So
  `state_key` is not a dedupe key `[built: binary-canticle@8ee80d7:prototype/canticle-station/canticle/station.py:316]`.
- **The OpenClaw binding's outbox declares duplicates** (bc#97; 🌿, overclaim check on #199). It gives the
  agent-facing `sing` an idempotency key, the caller's or one derived from session and content. A repeat with
  the same content returns the existing row with `duplicate: true`. A reused key with other content is refused
  as `key_conflict`
  `[built+tested: binary-canticle@8ee80d7:prototype/openclaw-canticle/src/outbox.ts:237 | prototype/openclaw-canticle/test/outbound.test.ts:89]`.
  A row is written ahead, durable before the station acts, and sent at most once. A send with no complete
  reply is `unknown`, and after a restart a row that was mid-send comes back `unknown` and is never re-sent.
  It waits for evidence instead. That is deliberate (🪨, receipt on #198)
  `[built+tested: binary-canticle@8ee80d7:prototype/openclaw-canticle/src/outbox.ts:147 | prototype/openclaw-canticle/test/outbound.test.ts:346]`.
  It is local to one binding. It is not an authoritative slot across senders, it has no terminal failure
  state, and it never replays.
- **An inference cannot pass for testimony.** On a station's own typed `beacon` stream, only
  `origin: reported` is read. A familiar's `inferred` beacon is not shown as the station's own word (#142)
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/beacon.py:134 | ReadTest.test_an_inference_cannot_pass_for_testimony]`.

### 1.2 What does not exist

- No trigger, no envelope and no place to run.
- No authority over who may summon, because nothing summons.
- No exactly-once delivery. The one path with declared duplicates is the OpenClaw binding's outbox (§1.1): at
  most once, per binding, with no slot shared across senders (🌿, overclaim check on #199). bc#126's delivery
  was at least once: a lost acceptance retried the same batch under a new station seq.
- No consent at scale: one actor, one fixture.

### 1.3 R4's nine gaps, mapped one to one

| # | R4 gap (§6 there) | Specified (proposed) in |
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

Every row is specified, not closed: nothing in the right-hand column is built (🌿, overclaim check on #199)
`[proposed: #199]`. Gap 9 is the one this RFC does not specify. It names what a result needs from the manifest
and leaves rollout to a later go `[open: §9]`.

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
- A reference names where to look. It never grants the right to look. That right comes from the consent
  record a `consent_ref` locates, once that record is verified at the read (§4.1). The ref itself is only a
  locator (🌊, review on #199) `[proposed: #199]`.
- **Sources are one typed list** (🌫, review on #199). `refs.sources` holds one entry per source. Each entry
  pairs one source (its `actor` and `stream`) with the scope the summons may read there (`records`, a
  `window`, and optionally `fields`) and exactly one `consent_ref`. There are no parallel arrays, and no
  scope is ever formed by combining parts of different entries `[proposed: #199]`.
- Each entry has a unique `key`, and no two entries name the same actor and stream. A summons with an entry
  that lacks its `consent_ref`, two entries for one source, or a `consent_ref` whose record is for another
  source than its entry's (§4.1) MUST be refused at admission, before any read `[proposed: #199]`.
- **An envelope with a key its schema version does not define is refused** (§5.3), not read around. This is
  deliberate, and it departs from RFC-0001 §9.5, whose frame receivers ignore unknown keys unless `crit` lists
  them. A frame is heard material and can afford to skip what it does not know. A summons envelope carries
  authority and is hashed into a binding, so an ignored key would be a field one implementation hashed and
  another did not, or a scope one reader honoured and another skipped `[proposed: #199]`.
- **A read is inside both scopes, or it is refused.** A fetched record MUST fall inside its entry's scope and
  inside the current scope of that entry's consent record. A broad consent does not widen an entry, and a
  broad entry does not widen a consent. A read that matches no entry MUST be refused `[proposed: #199]`.

### 2.2 Context

Field by field against Lambda's context object [AWS-Context]. The right-hand column is honest: where Lambda
has nothing, it says so.

| Field | Set by | Lambda's analogue |
|---|---|---|
| `summons_id` | the summons authority layer, once, at admission | **No direct analogue.** `awsRequestId` identifies one invocation request. It is not a caller-chosen key that stays the same across every retry and re-send (🪨). This key comes from the summons authority layer `[proposed: #199]` |
| `causality` (`election`, `chain`, `hop`) | the summons authority layer (§6.3) | none. AWS detects some recursive loops itself [AWS-EDA], but exposes no chain to the function `[proposed: #199]` |
| `deadline_ms` (absolute) | the authority layer, at admission | `getRemainingTimeInMillis()`, which gives remaining time rather than an absolute deadline `[proposed: #199]` |
| `invoker`, verified | the summons authority layer | **No direct analogue.** Lambda's `identity` is Amazon Cognito identity for mobile-app callers, not a general invoker (🪨). This field comes from the summons authority layer `[proposed: #199]` |
| `worker`, `worker_version` | the summons rule names them; the runner attests what actually ran (§5.1) | `functionName`, `functionVersion` `[proposed: #199]` |
| `worker_artifact` | the summons authority layer, at admission: the digest of the immutable artifact that `worker_version` resolves to in the worker registry (🌊, review on #199) | none `[proposed: #199]` |
| `budget` (tokens, wall time, result bytes) | the summons rule, within §3's bound. `wall_s` bounds each attempt; `tokens` bound the sum over all attempts | none. `memoryLimitInMB` bounds memory, not tokens, time or output `[proposed: #199]` |
| `retry` (`max_attempts`, `backoff_base_ms`) | the summons authority layer, at admission, from the worker's registered retry config (§5.2) | asynchronous retries: by default, two more attempts after an error, one minute and then two minutes apart [AWS-AsyncErrors] `[proposed: #199]` |
| `log_destination` | the runner, per attempt. What it may receive is bounded below | `logGroupName` (with `logStreamName`) `[proposed: #199]` |
| `attempt` | the runner, per attempt | none `[proposed: #199]` |
| `consent_ref`, one per `refs.sources` entry (in the event, §2.1) | the summons rule; verified at admission and at every read (§4.1, §4.2) | none `[proposed: #199]` |
| `audience` | the summons rule: the result's audience, within every consent's audience (§4.1) | none `[proposed: #199]` |
| `aspect` | the summons rule | none (§2.3) `[proposed: #199]` |

Every context field except the attempt-local ones (`log_destination` and `attempt`) MUST be fixed at
admission and covered by the summons **binding**, a digest of the admitted event and context whose exact
projection and encoding §5.3 defines. A retry carries the same binding (🌫, review on #199)
`[proposed: #199]`.

A worker MUST NOT write `summons_id`, `causality`, `invoker` or `consent_ref`. If it supplies them, the result is
refused (§6.1) `[proposed: #199]`. The same holds for `worker`, `worker_version` and `worker_artifact`: a
worker MUST NOT write them, and its own statement of what it is never counts (🌊, review on #199)
`[proposed: #199]`.

**What a log may carry.** `log_destination` is attempt-local and outside the binding. A log is not a result:
it is never sung, it has no audience, and no consent bounds its readers. So it MUST NOT carry source content
`[proposed: #199]`.

- A log line MAY carry only: `summons_id`, the binding, `attempt`, `refs.sources` keys and record ids, counters
  (reads, refusals, bytes, tokens, durations), and an error class from a closed list. Never a record's
  content, an excerpt, a model's output, or an error's free text, which can quote what was read
  `[proposed: #199]`.
- The runner MUST enforce this by a field whitelist at the log sink, not by the worker's care. It MUST drop
  every other field, and count the drops. A worker's standard output and error MUST NOT reach
  `log_destination` as text; the runner counts their bytes and nothing else `[proposed: #199]`.
- Lambda's context names the function's log group and stream [AWS-Context] and bounds nothing about what
  reaches them. Here the bound is the content boundary of §4.3, applied to logs.

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
      "sources": [
        {
          "key": "src-a",
          "actor": "fixture-actor-a",
          "stream": "fixture:activity",
          "records": ["rec-a-0001", "rec-a-0002"],
          "window": {"from_ms": 1764200000000, "to_ms": 1764203600000},
          "consent_ref": "auth:fixture-actor-a"
        }
      ]
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
    "worker_artifact": "sha256:fixture-digester-0.0.0-fixture",
    "budget": {"tokens": 20000, "wall_s": 240, "result_bytes": 800},
    "retry": {"max_attempts": 3, "backoff_base_ms": 30000},
    "log_destination": "fixture://logs/smn-fx-0001",
    "attempt": 1,
    "audience": "fixture-room",
    "aspect": "summary.plain"
  }
}
```

The mark `mark:fixture-quiet` fired. The authority layer verified the rule and its owner, assigned
`smn-fx-0001`, started the chain, set the deadline and resolved `fixture-digester` at `0.0.0-fixture` to its
artifact digest and its retry config. It admitted the summons at `1764203600000`, so 900 s remain, and three
attempts of 240 s with backoffs of 30 s and 60 s fit in 810 s (§5.2). The worker gets references to two records
and one consent. It does not get their text.

---

## 3. Authority: who may summon

### 3.1 Three kinds of invoker

- **Marks.** A threshold on a metric the house already gathers, from Grafana or Loki as the familiar sweep does
  today (ttf#36). A mark rule MUST declare its debounce and its cooldown, and MUST NOT fire again inside its
  cooldown. The rule's owner is the invoker, not the metric `[proposed: #199]`. A mark on a metric derived
  from canticle records (a Grafana or Loki series that counts or reads sung records) counts those records as
  its trigger records, even though it reads them through a metric. It MUST carry their chains into admission,
  or else it MUST NOT count summons results at all (§6.3 rule 6; 🪨, review on #199) `[proposed: #199]`.
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
`[proposed: #199]`. Their stamped causality chains enter it too, read by the authority layer from the records
themselves, whether the rule counts them directly or through a metric (§6.3 rule 6; 🪨, review on #199)
`[proposed: #199]`.

### 3.3 Quorum counts distinct key holders

Quorum sensing lets bacteria change behaviour by population: behaviours "unproductive when undertaken by an
individual bacterium acting alone but become beneficial when carried out simultaneously by a large number of
cells" [WatersBassler2005]. The analogy breaks on identity. Bacteria sense signal concentration, which tracks
"the number and/or species present in a community" [WatersBassler2005]: species, but nothing in that abstract
about telling individual senders apart. Canticle records are signed per station, so a canticle quorum can
count **distinct signers** (🌿, overclaim check on #199). But a key is not a voice. One holder can hold many
keys, so the count is of **holders**, not keys.

- A mark rule that summons on many marks MUST count distinct **key holders**, not records and not keys. A
  holder is the actor in custody of a station key. Two keys in one holder's custody count once, and one
  station repeating itself counts once. This matches RFC-0002 §3.5: repetition from one signer is not more
  evidence `[proposed: #199]`.
- The rule MUST resolve each verified signer's key to its holder through the manifest. A key whose holder it
  cannot resolve MUST count zero, not one `[proposed: #199]`.
- Custody, not the manifest, decides who holds a key. On silas, station key files are readable by the uid the
  ears share (RFC-0002 §4.4, §7 below), so every key in that custody has, in fact, one holder whatever the
  manifest says. Until custody is per seat, a quorum MUST count all keys in one shared custody as one holder
  `[proposed: #199]`.
- The rule MUST say what it counts (holders, and over which window), and the summons MUST record the holder
  set it counted, with the key ids behind each `[proposed: #199]`.

---

## 4. Consent: whose data a worker may read

### 4.1 Per-actor authorization records

Consent is per actor and sovereign to each seat. An authorization record follows bc#126's `auth.json` shape:
**actor, source, audience, revocation**. #119 already requires each of those four for every source
authorization.

- A summons MUST name one `consent_ref` per source it may read, in that source's `refs.sources` entry (§2.1;
  🌫, review on #199). A worker MUST NOT read a source that no `consent_ref` in its summons names
  `[proposed: #199]`.
- A consent record's audience bounds the result: the result's audience MUST NOT be wider than the narrowest
  audience among the consents it read under `[proposed: #199]`.

**A ref is a locator, not a grant** (🌊, review on #199). Naming a record proves nothing about it. A rule could
name an unrelated record, or a forged one, and pass the two checks above. So the record behind each ref is
verified, not only located.

This is the **confused deputy** [Hardy1988]: a component that holds authority of its own acts on a name its
caller supplied, and so lends that authority to the caller. Here the read path is the deputy, and a
`consent_ref` is the caller's name. **Where it breaks:** Hardy's subtitle points at capabilities, where the
name and the authority travel together. Here they stay apart on purpose. The ref stays a bare locator, and the
authority is what the read path verifies in the record against this summons (issuer, actor, source, audience,
grantee, revocation). Only the metadata of [Hardy1988] was read; it is cited for the name of the problem.

- An authorization record MUST carry a fifth field beside bc#126's four: its **grantee**, the worker identities
  (and, if it narrows further, the summons rules) that may read under it. A record with no grantee grants
  nothing to a summons `[proposed: #199]`.
- At admission, and again at every read, the verifier MUST resolve the ref to the current record and check all
  of the following. Any one failing refuses the read `[proposed: #199]`.
  1. **Integrity and issuer.** The record is intact and signed by its issuer, and the issuer is the actor with
     authority over the source being read: for a prince's own session activity, that prince; for a scribe
     seat, that seat, by its own opt-in (§4.3). A record issued by anyone else grants nothing.
  2. **Actor.** The record's actor is the actor whose data this read fetches.
  3. **Source.** The record's source covers exactly the stream or record being read. A record for another
     source, or one the read would widen, fails.
  4. **Audience.** The summons's `audience` (§2.2) is within the record's audience.
  5. **Grantee.** This summons's `worker` (and its rule, if the record names rules) is among the record's
     grantees.
  6. **Revocation**, as §4.2.
- **The verifier is the read path, not the worker.** At admission it is the summons authority layer. At a read
  it is the component that serves the source to the worker, which checks the summons binding and the
  `consent_ref` presented with each read. A worker's own check is never the guarantee, for the same reason a
  worker's own report is never a receipt (§8) `[proposed: #199]`.
- **Fail closed.** A check that cannot complete (the record cannot be fetched, the signature cannot be verified,
  a field is missing) MUST refuse the read. At admission, the summons is then refused before any read. Mid-run,
  the run ends in a failure record, reason refused read (§5.2) `[proposed: #199]`.
- How issuers sign their records, and where the map from a source to the actor with authority over it lives,
  are open `[open: §9]`.

### 4.2 Revocation is checked at every read

- The read path (§4.1) MUST check the consent record's revocation **at every read** of a source, not only at
  summons admission. A queued worker can start after a revocation (🪨). The worker may check too, but its check
  is not the guarantee (🌿, overclaim check on #199) `[proposed: #199]`.
- A revocation MUST stop that read and every later summons that names it `[proposed: #199]`.
- A revocation that stops a run mid-way MUST end it in a failure record (§5.2), not a partial success
  `[proposed: #199]`.
- A revocation does not recall a result already on air. That result lives out its TTL. Its owner MAY withdraw
  it with a PLUCK (RFC-0002 §2.2). The station can pluck today, but nothing wires revocation to a pluck yet
  `[built+tested: binary-canticle@8ee80d7:prototype/canticle-station/canticle/station.py:343 | prototype/canticle-station/tests/test_udp_e2e.py:44]`.
- Whether revocation SHOULD pluck automatically is open `[open: §9]`.

This is **complete mediation**: "Every access to every object must be checked for authority"
[SaltzerSchroeder1975]. **Where it breaks:** their principle mediates every access. Here mediation is complete
over reads and over the accept, and it stops at publication. A result already on air is not recalled by a later
revocation. It lives out its TTL unless its owner plucks it (below).

**Revoked after the last read, before publication** (🌊, review on #199). A run can finish its reads and then
lose a consent before its result is accepted. The read checks above cannot see that.

- The authoritative store's accept of a success (§5.3) MUST check again every consent the result read under.
  The accept is the **linearization point**: a revocation counts as before publication if the consent store
  recorded it before the accept's check read it, and as after publication if not `[proposed: #199]`.
- **Revoked before the accept: withheld, and sung as a failure.** The store MUST fill the slot `failed`, reason
  revocation, in place of the success. The success send then finds the slot filled and is answered as §5.3
  answers any such send: the existing receipt, recorded as a duplicate. Nothing read under the revoked consent
  is published. A failure record carries no content read under consent, so it needs no consent check
  `[proposed: #199]`.
- **Revoked after the accept: on air until its TTL**, like any result already on air (above). Its owner MAY
  withdraw it with a PLUCK (RFC-0002 §2.2). Under §5.3 option B this includes a result accepted into the slot
  but still `pending` publication: the relay MUST still publish it, so that claim 4 holds, and the PLUCK is
  how it is withdrawn `[proposed: #199]`.
- **Unknown is not unrevoked.** If the accept cannot read a consent's state, it MUST NOT fill the slot. The
  send is not accepted and may be retried under the same binding. The authority layer's deadline failure
  (§5.2) still bounds the run `[proposed: #199]`.
- So the revocation promise is narrow: no result is published under a consent revoked before its accept. It is
  not a promise that nothing is on air after a revocation `[proposed: #199]`.
- If the consent store and the slot are different stores, the check and the fill are two steps, and a
  revocation landing between them counts as after the accept. How stale that check may be is open
  `[open: §9]`.

**Cancel.** A cancel ends a summons before its result, and it follows the revocation rules above, with the
store's accept as the same linearization point.

- **Who may cancel.** The summons's verified invoker (§3.1), verified as at admission. A consent holder
  cancels by revoking (above), and the slot's reason is then revocation, not cancelled. No one else may
  cancel. A heard item never cancels, as it never summons (§3.2). A cancel from anyone else MUST be refused,
  counted, and leave the slot unchanged `[proposed: #199]`.
- **Cancelled before the accept.** The store MUST fill the slot `failed`, reason `cancelled`. A failure record
  is sung (§5.2). The runner MUST stop the running attempt and MUST NOT start another. A later success send
  finds the slot filled and gets its receipt as a duplicate (§5.3). A summons cancelled while queued makes no
  read `[proposed: #199]`.
- **Cancelled after the accept.** The cancel gets the existing receipt and changes nothing. The result is on air
  until its TTL, and its owner MAY withdraw it with a PLUCK (RFC-0002 §2.2) `[proposed: #199]`.
- **A cancel is idempotent per `summons_id`.** A cancel whose answer was lost MAY be sent again, and gets the
  same receipt. A cancel is never retried as an attempt failure (§5.2) `[proposed: #199]`.

### 4.3 Scribe seats as sources

A scribe seat MAY be a source only by its own explicit opt-in, and only for curated content, such as 🌿's entry
log under its binding on #119 (log lines only, `[quiet]` lines never sung) `[proposed: #199]`. figs's 11-04
ruling still holds, as he narrowed it that night (recorded on #119, 03:09Z): scribes do not design or build the
digestion, nor reason about developing it, but they may contribute content. His 11-27 ruling keeps the
digestion step itself with an OpenClaw prince (the authority note above) (🌿, overclaim check on #199).

No reasoning text and no session text MAY reach a scribe seat's context through a summons, its event, its
result or its logs (§2.2) `[proposed: #199]`.

### 4.4 The digestion interface

The digester is owned by 🪨 Rune (#198). This section is the contract it must meet. Its source reading,
parsing and summarizing live on #198, not here.

- **Inputs:** a summons event of references only (§2.1) and its context (§2.2), including one `consent_ref`
  per `refs.sources` entry (§2.1). The digester MUST fetch what it reads itself, under §2.1, §4.1 and §4.2,
  and only inside each entry's scope `[proposed: #198]`.
- **Outputs:** one bounded summary, within `budget.result_bytes`, plus its lineage (§6.1), sung inline or by
  reference as §6.1 decides. The summary MUST NOT reveal more than the consents' audience allows
  `[proposed: #198]`.
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

So a summons is a long-running, stateful task dressed in a FaaS-shaped contract. On Temporal, the Workflow Id
is the slot's natural carrier, but only under the policies §5.3's prior art names.

- The runner MUST enforce `deadline_ms` and `budget`. A run that exceeds either MUST end in a failure record
  naming which `[proposed: #199]`.
- The runner SHOULD heartbeat a long run so that "still running" and "the runner died" read differently.
  Unknown MUST NOT be shown as quiet `[proposed: #199]`.
- **The runner attests what ran** (🌊, review on #199). For each run, the runner MUST produce an execution
  attestation, signed by the runner and never by the worker, naming the `summons_id`, the binding and the
  digest of the artifact it actually started. A version the worker reports about itself is never that proof
  `[proposed: #199]`.
- Before it stamps a success's lineage (§6.1), the summons authority layer MUST check that the attestation is
  present and verifies, names this summons and this binding, and names the same digest as `worker_artifact`.
  If any check fails, the success MUST be refused, and the authority layer fills the slot `failed`, reason
  worker mismatch (§5.2, §5.3) `[proposed: #199]`.
- **The proof boundary.** This proves that the artifact the runner started is the one the stamp names. It
  trusts the runner: a runner that lies in its attestation is outside this proof, just as station key custody
  is outside what a signature proves (§7). The attestation's format depends on where workers run
  `[open: §9]`.

### 5.2 Retries and failure

- **Workers MUST be idempotent, keyed on `summons_id`.** The same event can arrive twice even when nothing
  failed: "it's possible for it to receive the same event from Lambda multiple times because the queue itself
  is eventually consistent" [AWS-AsyncErrors]. A standing rule that reads a stream has the same property: event
  source mappings "process each event at least once" [AWS-ESM] `[proposed: #199]`.
- A retry MUST NOT mint new evidence. It carries the same `summons_id` and binding, and its result MUST be the
  same slot's result (§5.3) `[proposed: #199]`.
- **A failed summons goes to a destination**: a sung failure record on the worker's station, naming the
  `summons_id` and the reason (deadline, budget, revocation, cancelled, refused read, worker mismatch,
  attempts, oversize). It MUST NOT be lost silently. Lambda discards failed asynchronous events unless a
  destination is configured [AWS-AsyncErrors]; here the destination is not optional `[proposed: #199]`.
- If the worker cannot sing (it died, or its deadline passed), the summons authority layer MUST write the
  failure through the same slot. After `deadline_ms` a success cannot win against it, because the slot's
  clock refuses the success (below) `[proposed: #199]`.

**The attempt bound and backoff.** The runner retries, but only a bounded number of times.

- Each worker registers a retry config: `max_attempts`, from 1 to 3, counting the first attempt, and
  `backoff_base_ms`, greater than 0. A config with `max_attempts` above 3 or below 1, or with no backoff, MUST
  be refused at registration, and a summons naming a worker with no valid config MUST be refused at
  admission. The authority layer copies the config into the context as `retry`, inside the binding, so no
  attempt can widen it `[proposed: #199]`.
- **Backoff is exponential.** Attempt `n` (for `n` ≥ 2) MUST NOT start until `backoff_base_ms × 2^(n−2)` after
  attempt `n − 1` ended. With three attempts, the waits are `b` and then `2b` `[proposed: #199]`.
- **Only some failures retry.** A worker error, or a runner that lost the attempt (a crash, a lost heartbeat),
  MAY be retried. Deadline, budget (`tokens`), revocation, cancelled, refused read, worker mismatch and
  oversize MUST NOT be: each fills the slot at once. A failed attempt is recorded in the ledger against the
  `summons_id`. It is not the summons's failure, and it fills nothing `[proposed: #199]`.
- **The last attempt is the last.** The runner MUST NOT start attempt `max_attempts + 1`, and the store MUST
  refuse, and record, a send whose `attempt` exceeds `retry.max_attempts`. When the last attempt fails, the
  runner sends the failure, reason attempts, with the last attempt's error class `[proposed: #199]`.
- **The attempts must fit the deadline.** At admission, with `A = retry.max_attempts`,
  `w = budget.wall_s × 1000` and `b = retry.backoff_base_ms`, the authority layer MUST refuse a summons for
  which `deadline_ms − admitted_at_ms < A·w + b·(2^(A−1) − 1)`. A bound the deadline cannot honour is not a
  bound `[proposed: #199]`.

**Two horizons.** Both follow from the deadline and the attempt bound, and the slot outlives both.

- **The retry horizon is `deadline_ms`.** No attempt starts at or after it, the runner ends every attempt by
  it, and no send started after it can be accepted as a success (below). The admission check above is what
  lets every permitted attempt run before it `[proposed: #199]`.
- **The replay horizon is `deadline_ms + r`**, where `r` is the relay bound the slot's store declares (and the
  station, under §5.3 option A). Until it, sends in flight at the deadline drain, and the relay replays any
  slot still `pending` to the station (§5.3). A slot still `pending` at the replay horizon MUST be shown as
  stuck: a named loss of liveness, never quiet and never sung `[proposed: #199]`. The value of `r` is open
  `[open: §9]`.
- **The slot, and the station's record of its conditional accept, MUST be kept at least until the replay
  horizon plus the result's TTL.** A send or replay that can still arrive must still find the slot filled, and
  while the result is on air no second record may join it `[proposed: #199]`.

**Prior art for the bound.** Lambda retries a failed asynchronous invocation "two more times, with a
one-minute wait between the first two attempts, and two minutes between the second and third attempts"
[AWS-AsyncErrors]: three attempts, doubling waits, as here. Knative's delivery spec has `retry`,
`backoffPolicy` (`linear` or `exponential`), `backoffDelay` and `deadLetterSink` [Knative-Delivery].
**Where it breaks:** Knative's `retry` excludes the initial attempt, so its `retry: 2` is this RFC's
`max_attempts: 3`. Its dead letter sink receives the failed event. Here a failure record carries references
only (§2.1), and nothing read under consent goes to a dead letter.

**The slot's clock judges the deadline.** The deadline is judged once, by one clock: the authoritative store's,
the one that holds the slot (the station under option A, the result store under option B). The worker's,
runner's and sender's clocks never judge it `[proposed: #199]`.

- A success whose accept the store would make when its clock reads after `deadline_ms` MUST be refused. If the
  slot is empty, the store fills it `failed`, reason deadline, in that same conditional write, and answers the
  send with that receipt, marked `late` (§5.3) `[proposed: #199]`.
- After `deadline_ms`, every fill of an empty slot is `failed`, reason deadline, whatever the send carried.
  Before `deadline_ms`, the store MUST refuse a deadline failure `[proposed: #199]`.
- So a late success can no longer win first-write against the authority layer's failure write. Both are
  judged against the same clock, and the order in which they reach the store does not matter
  `[proposed: #199]`.
- The runner still ends attempts at `deadline_ms` by its own clock (§5.1). That is a resource control, not the
  judgement. A runner clock that runs fast loses time and is safe; one that runs slow sends late and is
  refused. The store clock's own error against true time is outside this proof, as key custody is outside
  what a signature proves (§7) `[proposed: #199]`.

**Poison is counted, and parked.** A summons that fails on the same inputs every time is a poison message. It
must not be summoned for ever.

- **The input key.** A summons's binding includes its `summons_id`, so no two summonses share one. Poison is
  counted per **input key** instead: `sha256:` over the RFC 8785 encoding of `{"v": 1, "worker": <worker>,
  "event": <the admitted event>}`. That is the worker and its set of refs. It leaves out `worker_version` and
  `worker_artifact`, so a new version of the worker does not release a parked input on its own
  `[proposed: #199]`.
- **What counts.** A terminal failure with reason attempts, deadline or budget counts one against its input
  key. Revocation, cancelled, refused read, worker mismatch and conflict do not: those are not the input's
  fault. A success resets the count. Failures count per summons, not per attempt `[proposed: #199]`.
- **Parked after three.** When an input key reaches `N` consecutive counted failures, it is **parked**. This RFC
  proposes `N = 3` `[proposed: #199]`. The authority layer MUST then refuse admission of any summons with that
  input key, before any read, and count the refusal. A mark that fires on it is refused like any other, and
  its cooldown still runs `[proposed: #199]`.
- **A parked record is sung**, on the worker's station, as keyed live-state under one `state_key` for the
  input key. It names the input key, the worker, the `summons_id`s of the counted failures and their reasons,
  the count, and who may release it. It carries references only, never source content. It stays visible while
  the input key is parked, and its release sings its withdrawal `[proposed: #199]`.
- **Release.** Only a named releaser, a human or a prince named in the worker's registered config, may release
  a parked input key, verified like an invoker (§3.1). A heard item never releases. A release resets the count
  and is recorded in the ledger. A release from anyone else MUST be refused and counted `[proposed: #199]`.
- **The dead letter is the parked record and the ledger.** Lambda's dead-letter queue and on-failure
  destination [AWS-AsyncErrors] and Knative's `deadLetterSink` [Knative-Delivery] hold failed events one by
  one. **Where it breaks:** neither page read describes refusing the next event with the same inputs. Parking
  does that: it is a breaker on the input key, not a sink for one event.

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
- **Listener dedupe cannot help at all** (🌿, overclaim check on #199). RFC-0002's receiver dedupe (#176
  decision 5) drops repeat copies of one frame. It keys on the frame identity `(key_id, epoch, stream, seq)`
  `[built: binary-canticle@8ee80d7:prototype/canticle-station/canticle/wire.py:155]`, and a re-sing takes a
  new seq `[built: binary-canticle@8ee80d7:prototype/canticle-station/canticle/station.py:309]`. So a re-sent
  result is a new identity, and no listener dedupes it, not even one. At most, a shared `state_key` supersedes
  the older one on air, and every listener has still heard two. Nothing downstream of the station can undo a
  second publication, which is why uniqueness has to be enforced at the store, before the station signs
  `[proposed: #199]`. A result's on-air identity is therefore `(station key, summons_id)`, never the frame
  identity (§6.1).
- **The slot MUST be durable** and kept at least until the replay horizon plus the result's TTL (§5.2), so it
  outlives both horizons. A slot forgotten while a send or replay can still arrive re-opens claim 4
  `[proposed: #199]`.

(The lesson of ttf#64.)

**The binding, exactly** (🌫, review on #199). Two implementations MUST hash the same bytes for one summons, or
an honest retry reads as a conflict `[proposed: #199]`.

- **Projection.** The binding MUST be `sha256:` followed by the lowercase hex SHA-256 of the canonical encoding
  of `{"v": 1, "event": <the admitted event>, "context": <the admitted context without its attempt-local
  fields>}` `[proposed: #199]`.
- **The attempt-local fields are a closed list:** `log_destination` and `attempt`. They are left out, so a
  retry on another runner or log stream keeps its binding. Every other field of the event and the context is
  in, including `summons_id`, `causality`, `deadline_ms`, `invoker`, `worker`, `worker_version`,
  `worker_artifact`, `budget`, `retry`, `audience`, `aspect`, and every `refs.sources` entry with its `consent_ref`. A
  field not on the closed list is in. Remaining time is never a field: the context carries only the absolute
  `deadline_ms` `[proposed: #199]`.
- **Encoding.** The JSON Canonicalization Scheme [RFC 8785]: object keys sorted, no insignificant whitespace,
  strings serialized as it serializes them, with no Unicode normalization `[proposed: #199]`.
- **Numbers.** Every number MUST be an integer from −(2^53 − 1) to 2^53 − 1, so every implementation encodes it
  alike. Any other number MUST be refused at admission `[proposed: #199]`.
- **Duplicate and unknown keys are refused, never dropped.** An envelope with a duplicate key in any object, or
  a key its schema version does not define, MUST be refused at admission. Dropping either would let two
  implementations hash different bytes for one summons `[proposed: #199]`. This departs from RFC-0001's
  frames on purpose (§2.1).

**Vector 1.** The running example (§2.4) projects to these bytes (one line, no trailing newline):

```
{"context":{"aspect":"summary.plain","audience":"fixture-room","budget":{"result_bytes":800,"tokens":20000,"wall_s":240},"causality":{"chain":[["mark:fixture-quiet","smn-fx-0001"]],"election":"mark:fixture-quiet","hop":1},"deadline_ms":1764204500000,"invoker":{"kind":"mark","owner":"fixture-prince","rule":"mark:fixture-quiet"},"retry":{"backoff_base_ms":30000,"max_attempts":3},"summons_id":"smn-fx-0001","worker":"fixture-digester","worker_artifact":"sha256:fixture-digester-0.0.0-fixture","worker_version":"0.0.0-fixture"},"event":{"kind":"digest.window","refs":{"sources":[{"actor":"fixture-actor-a","consent_ref":"auth:fixture-actor-a","key":"src-a","records":["rec-a-0001","rec-a-0002"],"stream":"fixture:activity","window":{"from_ms":1764200000000,"to_ms":1764203600000}}]},"v":1},"v":1}
```

Its binding is `sha256:88cdc08ee07bc70d0885a726addba1cd40c6abad2ed3a7835cbe17885b067fd9`.
Revision 4 added `retry` to the context and changed `budget.wall_s`, so this is not revision 3's vector.
Reordering its keys, or changing `log_destination` or `attempt`, leaves the binding unchanged. Changing any
included field gives another binding, and a send under it is a conflict (§8 case 11).

**The receipt.** One shape for every send to the slot:

```json
{
  "summons_id": "smn-fx-0001",
  "binding": "sha256:<digest of the admitted event and context>",
  "state": "succeeded",
  "publication": "published",
  "station": "fixture-familiar",
  "epoch": 3,
  "seq": 41,
  "accepted_at_ms": 1764203990000,
  "this_send": "duplicate"
}
```

`this_send` is `accepted`, `duplicate`, `late` or `conflict`. A `late` receipt answers a success the slot's
clock refused after `deadline_ms` (§5.2): it names the slot's state, `failed`, reason deadline. A `conflict`
receipt carries no `state`, `epoch` or `seq` of the first result.

**Accepted is not yet sung** (🪨, review on #199). Under option B below, the slot can be filled while its
outbox row still waits for the station. A crash there leaves a filled slot and nothing on air. So the slot
carries a second attribute beside its state.

- `publication` is `pending` from the fill until the station accepts the result, then `published`. The
  terminal state (`succeeded` or `failed`) is fixed at the fill and never changes. Only `publication` moves,
  once, from `pending` to `published` `[proposed: #199]`.
- A receipt given while the slot is `pending` MUST say so. It carries the state, but no `station`, `epoch` or
  `seq`. A sender MUST NOT read a `pending` receipt as sung `[proposed: #199]`.
- **The relay replays until the station answers.** It sends the row, keyed on `summons_id` and binding, to the
  station's conditional accept. The station accepts it once. A replay after that gets the station's existing
  receipt, and the relay records that receipt's `station`, `epoch` and `seq` against the slot and marks it
  `published`. A crash at any step repeats the replay, never the fill `[proposed: #199]`.
- **Safety and liveness are separate.** Safety (never two published records for one `summons_id`) rests on the
  station's conditional accept, under every interleaving. Liveness (one is eventually published) needs more: a
  relay that recovers and replays, and a station slot that outlives the replay horizon. A slot left `pending`
  MUST be shown as pending, never as sung and never as quiet `[proposed: #199]`.
- Under option A the station's accept is the publication, so a slot is never `pending` `[proposed: #199]`.

**Prior art.** The nearest built piece is the OpenClaw binding's outbox (§1.1, bc#97). Exactly where it
matches, and where it does not (🪨, receipt on #198):

- **It matches on duplicates and conflicts.** A repeat with the same key and content returns the existing row
  with `duplicate: true`, and a reused key with other content is refused as `key_conflict`. Those are this
  section's same-receipt and changed-replay rules, for one binding
  `[built+tested: binary-canticle@8ee80d7:prototype/openclaw-canticle/src/outbox.ts:237 | prototype/openclaw-canticle/test/outbound.test.ts:89]`.
- **It matches on one half of send-then-timeout.** A send with no complete reply is `unknown`, never failed
  `[built+tested: binary-canticle@8ee80d7:prototype/openclaw-canticle/src/outbox.ts:147 | prototype/openclaw-canticle/test/outbound.test.ts:346]`.
- **It does not replay an uncertain send, on purpose.** After a restart, a row that was mid-send comes back
  `unknown` and waits for evidence; its restart test asserts that nothing is sung again (same pointer). The
  summons relay has to do the opposite: replay every `pending` slot until the station answers, which is safe
  only under the station's conditional accept on `summons_id` and binding. So the outbox's green tests prove
  its at-most-once contract, and they cannot stand in for the relay's replay, for case 1a vii or viii, or for
  liveness. The relay needs its own replay, under that accept `[proposed: #199]`.
- It is local to one binding, not an authoritative slot, and it has no terminal failure state. Whether the slot
  reuses it (option B's store, extended with a replay it does not have today) or only aligns with its
  duplicate and conflict semantics is open (🌿, overclaim check on #199) `[open: §9]`.

The slot is **Temporal's Workflow Id** under another name [Temporal-WorkflowId]. Temporal guarantees "only one
Workflow Execution with a given Workflow Id can be in an Open state at any given time". Its Id Reuse Policy
*Reject Duplicate* says a new execution "cannot exist if a previous Workflow Execution has the same Workflow
Id, regardless of the Closed status": a filled slot never reopens. Its Id Conflict Policy *Use Existing*
returns the open execution's Run Id to a second start, as a retry gets the existing receipt. **Where it
breaks:** the default reuse policy is *Allow Duplicate*, so a closed Workflow Id can run again. The policies, as
that page describes them, key on the Workflow Id alone and compare no inputs, so a changed replay would not
read as a conflict. So a Temporal runner (§5.1) MUST start each summons with Workflow Id = `summons_id` and
*Reject Duplicate*, and the binding check stays the slot's, not Temporal's. Temporal holds an execution, not a
publication: the station's conditional accept is still needed `[proposed: #199]`.

**Where the slot lives is open.** Two options, and neither is built `[open: §9]`:

- **A. Station-side conditional accept.** The station keeps a durable slot table and its `sing` takes
  `summons_id` and binding as a publication key. This is a protocol change: today's `sing` carries no such key
  (§1.1).
- **B. A result store with a transactional outbox.** The store accepts into the slot and writes an outbox row
  in one transaction. A relay publishes the row. This is the transactional outbox pattern [Outbox]. **Where it
  breaks:** the pattern accepts that a relay which crashes after publishing, before it records that it did,
  publishes again, and it puts the cure on consumers, which must be idempotent. §5.3 has shown that canticle
  listeners cannot dedupe a re-sing, so here the cure moves to the station. A relay that crashes between its
  `sing` and marking the row done will sing again. So the relay's publication still needs the station to accept conditionally on
  `summons_id`, or claim 4 fails at the relay. B adds a durable ledger of failures and receipts; it does not
  remove A's station change. The conditional accept is necessary for B but not sufficient: B also needs the
  `pending` state and the replay above (🪨, review on #199).

---

## 6. The result is a programme

### 6.1 Sung on the worker's own station

- A result MUST be sung on the worker's own station as an RFC-0002 programme. Its signature, its lineage and
  its TTL are on the record `[proposed: #199]`.
- **Lineage** MUST include `summons_id`, `worker`, `worker_version`, `consent_ref` (each one read), `aspect`, the
  binding and the causality chain (§6.3). The sources read appear by reference, never by content
  `[proposed: #199]`.
- Lineage MUST also include `worker_artifact` and a reference to the runner's execution attestation (§5.1).
  The `worker` and `worker_version` it carries are the ones the attestation backs, not the worker's word
  (🌊, review on #199) `[proposed: #199]`.
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

**The on-air identity of a result** is `(station key, summons_id)`: the key that signed it, and the
`summons_id` its lineage carries. It is never the frame identity `(key_id, epoch, stream, seq)`. The station
re-airs an item under a new seq when it refreshes it, and under a new epoch after a restart, so a count keyed
on the frame would count one result more than once.

- A listener, ledger, mark or quorum that counts or dedupes results MUST key them on `(station key,
  summons_id)`. Every airing of one accepted result under that pair is the same record, for claim 4 too
  `[proposed: #199]`.
- A record that carries a `summons_id` the slot does not hold as published under that station key is not that
  result, whatever its body says `[proposed: #199]`.
- Whether a station key rotation may carry a result on air across to the new key is open `[open: §9]`.

This is CloudEvents' rule that "`source` + `id`" is unique for each distinct event, and that consumers may
take two events with the same pair as duplicates [CloudEvents-1.0]. **Where it breaks:** CloudEvents leaves
uniqueness to its producers and lets consumers assume it. Here the pair is enforced at the slot before the
station signs (§5.3), and `source` is a verified signing key, not an unsigned URI-reference.

**Size: over budget, by reference.** An item body has a ceiling of about 980 bytes (RFC-0001 §9.6). An 800-byte
summary (`budget.result_bytes`) plus its lineage (a binding, an artifact digest, one `consent_ref` per source and
a causality chain) can exceed it.

- The authority layer MUST measure the item it would sign. If lineage plus summary fits the ceiling, the
  summary goes inline `[proposed: #199]`.
- If it does not fit, the result MUST travel **by reference**, as RFC-0001 §9.12 already lets large content
  travel: the item's `body` carries the lineage, and its `body_ref` (RFC-0001 §9.6 key 9: a URL, the SHA-256
  of the summary's bytes, and their size) points at the summary, kept in the result store `[proposed: #199]`.
- The result store MUST serve the summary only to a reader inside the result's audience, only while the
  result is live (its TTL; retention past it is §9's question), and only as the bytes the digest names. A
  reader MUST verify the digest and refuse a summary that does not match `[proposed: #199]`.
- By reference does not lift `budget.result_bytes`. The summary stays within it `[proposed: #199]`.
- **Lineage is never sent by reference.** An election must read a record's chain to apply §6.3, so the chain
  rides on air. §6.3 rule 3's maximum chain length, and the number of sources a summons may name, MUST be set
  so that lineage with no body fits the ceiling. A lineage that does not fit is never truncated: the success is
  refused, and the slot fills `failed`, reason oversize `[proposed: #199]`.
- Option A of §5.3 has no result store, so a by-reference result needs one under either option. Where it lives
  is open `[open: §9]`.

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
- The **trigger records** of `S` are the records `E` counted when it issued `S`, including records it counted
  through a metric (rule 6). A schedule, or a mark on a metric derived from no records, has none.
- `chain(S)` is the union of the chains of its trigger records, plus `S`'s own entry.
- `hop(S)` is one more than the largest hop among its trigger records, or 1 if it has none.
- A result `R` of `S` carries `chain(R) = chain(S)` and `hop(R) = hop(S)`.

**The rules.**

1. The summons authority layer MUST stamp `chain` and `hop` on every summons and every result. A worker MUST NOT
   add, drop or rewrite an entry `[proposed: #199]`.
2. **Exclusion.** An election `E` MUST NOT admit a record `R` as a trigger if any entry of `chain(R)` carries
   `ek(E)` `[proposed: #199]`. This is BGP's AS_PATH loop check: a route whose path contains an AS loop
   "should be excluded", and the check scans the full path for the local AS number [RFC 4271] (§9.1.2).
   **Where it breaks:** BGP's check says *should*, and reads one route's path as received. Here the check is
   absolute, `chain(R)` is the union of every trigger record's chain, and the authority layer stamps it (rule
   1). Claim 3 rests on that stamp, and a lost chain is a named loss (below), not something the check
   detects.
3. A record with `hop > 0` whose chain is missing, malformed or over the declared maximum length MUST NOT be
   admitted as a trigger. A chain is never truncated to fit; an over-long one is refused `[proposed: #199]`.
4. **Hop bound.** An election MUST NOT issue a summons whose hop would exceed `H_max` `[proposed: #199]`.
5. A result MUST NOT cause anything downstream except through an election that admits it under rules 2 to 4
   `[proposed: #199]`.
6. **Metric-backed marks** (🪨, review on #199). A mark whose metric is derived from records MUST name, at
   admission, the records it counted, and the authority layer MUST read their stamped chains from the records
   themselves, never from the metric. If the metric cannot name them, the mark MUST NOT count any record that
   carries a causality chain (any summons result), and its rule MUST declare the metric's inputs, so that the
   authority layer can refuse a rule whose inputs include a result stream `[proposed: #199]`.

**What each rule proves.** Rule 2 is the proof of claim 3. Every descendant of a summons `S` issued under `E`
inherits `chain(S)` whole (rule 1), and `chain(S)` holds `(ek(E), summons_id(S))`. So, while chains are
intact, `E` refuses every descendant, at any depth. That includes a cycle through other elections: when the
cycle comes back to `E`, `E`'s key is in the chain. The two named losses below are outside this proof. The hop
count does not prove anything (🪨). It *bounds* cascades through distinct elections, which rule 2 does not stop.
As a backstop it covers only a chain that lost entries but kept its hop. A missing chain on a record with
`hop > 0` is refused by rule 3. A record that lost both its chain and its hop reads as an original, and neither
rule catches it (🌿, overclaim check on #199).

On a metric-backed mark, rule 6 is what keeps the chain whole. Without it, take `E1` issuing `S1` with result
`R1`, and `E2` firing on a metric that counts `R1`. `E2`'s summons would have no trigger records, its chain
would hold only `E2`'s entry, and `E1` could admit `E2`'s result. With rule 6, `E2`'s summons inherits
`chain(R1)`, which holds `ek(E1)`, so `E1` refuses it (🪨).

**Named loss.** A loop that passes through a prince's own judgement is outside this guard. If a prince reads a
result and then summons for itself, the new summons inherits the result's chain only where the host's exposure
ledger can show the prince was exposed to it (RFC-0002 §4.1). Where it cannot, the chain starts fresh. Then only
§3.1's per-kind budget bounds that loop `[open: §9]`.

**Named loss, second path** (🪨, review on #199). A metric whose declared inputs are not its real inputs, for
example a series fed from a result by a component the rule does not name, carries no chain, and rule 6 cannot
see it. Its summons starts a fresh chain at hop 1, so neither exclusion nor the hop bound holds on that path.
As with the judgement loop, only §3.1's per-kind budget bounds it `[open: §9]`.

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
| A self-retriggering loop | §6.3's exclusion rule; the hop bound | the two named losses in §6.3. `[open: §9]` |
| A quorum inflated by one holder with many keys | §3.3: a quorum counts distinct key holders, not keys, and an unresolved key counts zero | on silas, station key files are readable by the uid the ears share (RFC-0002 §4.4), so every key in that custody counts as one holder until custody is per seat. `[proposed: #199]` |
| Source content leaks through logs | §2.2: a log carries refs, counters and error classes only, enforced by the runner's whitelist | a whitelisted field (an error class, a record id) could still be chosen to say something. The closed list keeps that small, not zero. `[proposed: #199]` |
| A poison input summoned for ever | §5.2: three attempts at most per summons; three counted failures park the input key until a named releaser releases it | `N` and the releasers are per worker, and their defaults are open (§9). `[proposed: #199]` |
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
| 1a v | Success against failure before `deadline_ms`: a success record and a failure record for one `summons_id` race (for example, a success and a cancel). After the deadline there is no race: case 13 | exactly one terminal state is accepted; the loser gets the winner's receipt and is recorded | `[proposed: #199]` |
| 1a vi | Changed-payload replay: same `summons_id`, different envelope, worker or consent | refused as a `conflict`; it is not given the first receipt; it is recorded | `[proposed: #199]` |
| 1a vii | Option B: the relay crashes after the slot fills and before the station accepts (🪨, review on #199) | while down, the slot is `pending` and a retry's receipt says `pending`, with no `epoch` or `seq`; after recovery the replay is accepted once, the slot turns `published`, and the station's receipt is recorded against it; `on_air` holds one record | `[proposed: #199]` |
| 1a viii | Option B: the relay crashes after the station accepted, before it marked the row (🪨, review on #199) | the replay gets the station's existing receipt; nothing new airs; the slot turns `published` with that receipt's `epoch` and `seq` | `[proposed: #199]` |
| 2 | A sung result reaches the election that summoned it, directly and through a second election | refused by the exclusion rule at first return. Ablation arm, exclusion off: the two-election cycle stops at `H_max` | `[proposed: #199]` |
| 2a | Metric-backed two-election path: `E1`'s result `R1` is counted by a metric behind `E2`, and `E2`'s result returns to `E1` (🪨, review on #199) | `E2`'s summons carries `chain(R1)`; `E1` refuses `E2`'s result at first return | `[proposed: #199]` |
| 2b | A mark rule whose metric cannot name its records declares a result stream among its inputs (🪨, review on #199) | the rule is refused at admission; no summons issues from it | `[proposed: #199]` |
| 3 | An unauthorized invoker (unverified, over budget, or a heard item) | refused before any read; the read counter stays at zero | `[proposed: #199]` |
| 4 | A revocation lands while the worker is queued; another lands mid-run | the queued worker makes no read; the running worker's next read is refused, and the run ends in a failure record | `[proposed: #199]` |
| 5 | A run fails (worker error, deadline, budget) | a sung failure record through the slot, naming the reason | `[proposed: #199]` |
| 6 | A result's lineage | it carries every §6.1 field, and none was written by the worker | `[proposed: #199]` |
| 7 | An ambient item, heard on air or quoted inside a referenced record, asks for a summons | no summons; no change to inputs, budget or consent | `[proposed: #199]` |
| 8 i | The `consent_ref` names a valid record for another actor (🌊, review on #199) | refused at admission, before any read; the read counter stays at zero | `[proposed: #199]` |
| 8 ii | The record's actor matches, but its source is another stream, or narrower than the read | refused before that read; the counter for that source stays at zero | `[proposed: #199]` |
| 8 iii | The record's audience is narrower than the summons's result audience | refused at admission | `[proposed: #199]` |
| 8 iv | The record's grantee names a different worker | refused at admission | `[proposed: #199]` |
| 8 v | The record is forged, altered, or issued by someone without authority over the source | refused at admission | `[proposed: #199]` |
| 8 vi | The record is valid at admission, then replaced mid-run by one that fails a check, or cannot be fetched | the next read is refused; the run ends in a failure record, reason refused read | `[proposed: #199]` |
| 9 i | A revocation lands after the last read, before the success is sent (🌊, review on #199) | the slot fills `failed`, reason revocation; a failure record is sung; nothing read under the consent is published; the success send gets that receipt and is recorded as a duplicate | `[proposed: #199]` |
| 9 ii | A revocation lands after the accept (under option B, while the slot is still `pending`) | one result is published; the revocation is recorded as after publication; the result stays on air until its TTL or a PLUCK | `[proposed: #199]` |
| 9 iii | A revocation races the accept | exactly one of 9 i or 9 ii, as ordered by the consent store; the slot holds one state | `[proposed: #199]` |
| 9 iv | The consent store cannot answer at the accept | the slot is not filled; a retry under the same binding can still be accepted; past the deadline, the authority layer's failure fills it | `[proposed: #199]` |
| 10 i | The runner's attestation names a different artifact digest from `worker_artifact` (🌊, review on #199) | the success is refused; the slot fills `failed`, reason worker mismatch | `[proposed: #199]` |
| 10 ii | No runner attestation; only the worker reports its version | refused as 10 i | `[proposed: #199]` |
| 10 iii | An attestation from another summons or binding is replayed | refused as 10 i | `[proposed: #199]` |
| 10 iv | The worker writes `worker`, `worker_version` or `worker_artifact` into its result | the result is refused (§2.2) | `[proposed: #199]` |
| 11 i | Vector 1 with its keys reordered and whitespace added (🌫, review on #199) | the binding is Vector 1's | `[proposed: #199]` |
| 11 ii | A retry of Vector 1 with another `log_destination` and `attempt` | same binding; the retry gets the first receipt as a `duplicate`, never a `conflict` | `[proposed: #199]` |
| 11 iii | Vector 1 with one change each: a record ref, the window, a `consent_ref`, `worker`, `worker_version`, `worker_artifact`, `deadline_ms`, `budget`, `retry`, `audience` | each gives another binding; a send under it is refused as a `conflict` | `[proposed: #199]` |
| 11 iv | An envelope with a duplicate key, a key its schema version does not define, a fractional number, or an integer past 2^53 − 1 | refused at admission; no binding is computed; the read counter stays at zero | `[proposed: #199]` |
| 12 i | Two sources: source A under consent A and source B under consent B (🌫, review on #199) | each read is counted against its own entry; every read falls inside both its entry's scope and its consent's | `[proposed: #199]` |
| 12 ii | Two sources, one entry missing its `consent_ref`, or carrying the other source's | refused at admission; the read counters for both sources stay at zero | `[proposed: #199]` |
| 12 iii | A valid, broad consent, and a read for a record outside its entry's `records` or `window` | that read is refused; the counter for records outside the entry stays at zero; the run ends in a failure record, reason refused read | `[proposed: #199]` |
| 12 iv | Two entries for the same actor and stream | refused at admission as ambiguous; the read counter stays at zero | `[proposed: #199]` |
| 13 i | A success sent after `deadline_ms` by the slot's clock, before the authority layer's deadline failure write | refused; the store fills the slot `failed`, reason deadline, in that write; the success gets that receipt marked `late`; the authority layer's later failure write gets it as a `duplicate`; nothing read is published | `[proposed: #199]` |
| 13 ii | The same, with the runner's clock set behind the store's, so the runner believes it is in time | refused as 13 i: only the store's clock judges | `[proposed: #199]` |
| 13 iii | A deadline failure sent before `deadline_ms` by the slot's clock | refused; the slot stays empty; a success before the deadline is still accepted | `[proposed: #199]` |
| 14 i | A worker registered with `max_attempts: 2` fails twice with a worker error; its runner then tries a third attempt | the third attempt is refused, and a send carrying `attempt: 3` is refused and recorded; the slot fills `failed`, reason attempts, after the second; the second attempt started no sooner than `backoff_base_ms` after the first ended | `[proposed: #199]` |
| 14 ii | A worker registers `max_attempts: 4`, or `0`, or no backoff | refused at registration; a summons naming it is refused at admission; the read counter stays at zero | `[proposed: #199]` |
| 14 iii | A summons whose attempts cannot fit its deadline (`deadline_ms − admitted_at_ms < A·w + b·(2^(A−1) − 1)`) | refused at admission | `[proposed: #199]` |
| 15 i | The verified invoker cancels a running summons | the slot fills `failed`, reason `cancelled`; a failure record is sung; no further attempt starts; the attempt's later success gets that receipt as a `duplicate`; nothing read is published | `[proposed: #199]` |
| 15 ii | A cancel from another prince, or from a heard item | refused and counted; the slot is unchanged; the run goes on | `[proposed: #199]` |
| 15 iii | A cancel after the success was accepted | gets the existing receipt; the slot and the air are unchanged | `[proposed: #199]` |
| 16 i | A mark summons on one input key three times, and each summons fails with reason attempts | after the third, the input key is parked and a parked record is sung, naming the input key, the three `summons_id`s and who may release; the mark's fourth summons is refused at admission; the read counter stays at zero | `[proposed: #199]` |
| 16 ii | Two of those three failures are reason revocation or cancelled | the input key is not parked | `[proposed: #199]` |
| 16 iii | A release from the named releaser, then one from anyone else on another parked key | the first resets the count and the next summons is admitted; the second is refused and counted | `[proposed: #199]` |
| 17 i | A result whose lineage plus 800-byte summary exceeds the item body ceiling | the item carries lineage in `body` and the summary by `body_ref`; the item fits the ceiling; a reader in the audience fetches the summary and its digest matches | `[proposed: #199]` |
| 17 ii | The stored summary is altered, or fetched by a reader outside the audience, or after the TTL | the reader refuses the altered bytes; the store refuses the other two | `[proposed: #199]` |
| 17 iii | A lineage that alone exceeds the ceiling | the success is refused; the slot fills `failed`, reason oversize; nothing is truncated | `[proposed: #199]` |

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
- **Metric inputs.** How a mark rule declares its metric's inputs, whether a Grafana or Loki series can name
  the records it counted, and how much of §6.3's second named loss that closes (🪨, review on #199). Owner:
  the familiar sweep's owner, with 🪨 `[open: §9]`.
- **Consent records.** How an issuer signs its record, where the map from a source to the actor with
  authority over it lives, and the grantee field's exact shape (§4.1; 🌊, review on #199). Owner: not yet
  named; 🌊 reviews `[open: §9]`.
- **Consent check staleness.** How old a consent read at the accept may be when the consent store and the
  slot are different stores (§4.2) `[open: §9]`.
- **Execution attestation.** Its format and signing key per runner (ARC or Temporal), and the worker registry
  that maps a `worker_version` to its artifact digest (§5.1, §2.2; 🌊, review on #199) `[open: §9]`.
- **Read scope fields.** What a `refs.sources` entry's `fields` may name, per source schema, and how a consent
  record states a narrower scope than its whole source (§2.1; 🌫, review on #199) `[open: §9]`.
- **The slot and the outbox.** Whether §5.3's slot reuses the OpenClaw binding's outbox (bc#97) or only aligns
  with it (§5.3 prior art; 🌿, overclaim check on #199) `[open: §9]`.
- **Where causality rides.** Whether `chain` and `hop` live in the programme's lineage or in RFC-0001's wire
  `hop` (capped at 15), and how `H_max` relates to that cap. Today's control-socket `sing` passes no `hop`, so
  everything sung through it reads hop 0. Also whether the summons authority layer that stamps lineage (§6.1)
  is the same component as RFC-0002's host daemon (#176 decision 2) (🌿, overclaim check on #199)
  `[open: §9]`.
- **Retry and parking defaults.** Each worker's `backoff_base_ms`, whether `N = 3` holds for every worker,
  and who is named to release a parked input key, per worker (§5.2) `[open: §9]`.
- **The relay bound `r`.** How long after `deadline_ms` the store and the station keep replaying and draining
  sends, which fixes the replay horizon and the slot's retention (§5.2) `[open: §9]`.
- **The log whitelist.** The closed list of error classes and counters a log may carry (§2.2) `[open: §9]`.
- **The by-reference store.** Where a result's summary lives when it travels by reference, under either slot
  option (§6.1) `[open: §9]`.
- **Key rotation and on-air identity.** Whether a result on air may be carried across a station key rotation,
  and so change the station key in its identity (§6.1) `[open: §9]`.
- **Rollout** of a familiar station and its manifest grant (R4 gap 9). A later go, not this RFC `[open: §9]`.

---

## Appendix A. Revisions

| Rev | Date | By | Changed |
|---|---|---|---|
| 0 | 2026-11-27 | 🍃 | The draft, from the outline at frond-gloss `24c311a`. 🪨's claims audit (room, 2026-11-27, 03:41Z to 03:44Z) made five fixes, all carried here. (1) `summons_id` and `invoker` have no direct Lambda analogue (§2.2): `awsRequestId` is one request, and `identity` is Cognito mobile identity; both fields come from the summons authority layer. (2) Claim 4 is exactly one sung result per `summons_id`, not "at most one, or a declared duplicate" (§0.2). Send-then-timeout is unconfirmed, not failure (§5.3). (3) Revocation is checked at every read, not only at admission (§4.2). (4) The exclusion rule by causality chain proves no self-retrigger; the hop count only bounds (§6.3). Uniqueness lives at the authoritative store, with a conditional accept or a transactional outbox, every retry gets the same receipt, and a pre-read is only an optimisation (§5.3). §8 gained cases 1a i to iv. (5) `summons_id` is the one terminal slot, not `(summons_id, result_kind)`: success and failure are mutually exclusive states of it, and a changed replay conflicts (§5.3). §8 gained cases 1a v and vi. The digester's owner is 🪨 (#198). |
| 1 | 2026-11-27 | 🍃 | Two reviews at `c5cbbb6b`. **🌊's** (comment on #199): (1) a `consent_ref` is a locator, not a grant. §4.1 now verifies the record behind it at admission and every read (integrity and issuer, actor, exact source, audience, a new grantee field, revocation), by the read path rather than the worker, failing closed; §2.1 says so. (2) Revocation after the last read and before publication: §4.2 re-checks consent at the slot's accept, which is the linearization point. Revoked before it, the slot fills `failed`; after it, the result stays on air until its TTL or a PLUCK. The promise is narrowed to match. (3) `worker`/`worker_version` are backed by a runner's execution attestation against a new `worker_artifact` digest (§2.2, §5.1, §6.1); a mismatch fills the slot `failed`. Claim 2 now reads "the set of consents it read", and its falsifier covers (1) and (3) (§0.2). **🪨's** (review on #199): (a) a metric-backed mark carries the chains of the records it counts, or must not count summons results (§3.1, §3.2, §6.3 rule 6, and a second named loss). (b) Under option B a filled slot is `pending` until the station accepts; a relay replays until it does; claim 4 is split into safety and liveness (§0.2, §5.3). §8 gained cases 1a vii and viii, 2a and 2b, 8, 9 and 10; §9 gained four entries. |
| 2 | 2026-11-27 | 🍃 | **🌫's** review on #199, at `c5cbbb6b`. (1) Sources and their consents are one typed list, `refs.sources`: one entry per source, each with its scope and exactly one `consent_ref`. There are no parallel arrays. A missing, ambiguous or mismatched association is refused at admission. A read must fall inside both its entry's scope and its consent's (§2.1, §2.2, §4.1, §4.4, the §2.4 example). The context gains `audience` and `attempt`. (2) §5.3 defines the binding exactly: the projection, a closed list of attempt-local fields (`log_destination`, `attempt`) that are left out, RFC 8785 encoding, integers only, duplicate and unknown keys refused, and a pinned Vector 1. `deadline` is `deadline_ms` everywhere. §8 gained cases 11 and 12; §9 gained one entry; References gained RFC 8785. |
| 3 | 2026-11-27 | 🍃 | **🌿's** overclaim check on #199 (at `f901de72`; all nine items re-checked at `b2599f73`, and all hold). Overclaims: §1.2 no longer says there are no declared duplicates, and §1.1 cites the OpenClaw binding's outbox as built prior art; §5.3 says listener dedupe keys on seq and so hides no re-sent result, not even from one listener, which is why uniqueness lives at the store; §4.3 quotes figs's 11-04 ruling as he gave it (no "review"); claim 3 (§0.2) and §6.3's proof are scoped to intact chains, with the two named losses outside, and §7 counts both; §6.3's hop backstop is narrowed to a chain that kept its hop; §3.3 no longer says biology cannot tell senders apart. Mis-tags: §0.4's authority-layer and terminal-slot definitions are tagged; §1.3's column is "Specified (proposed) in", and gap 9 is "not specified". Also from his notes: §4.2 puts the per-read revocation check on the read path; §5.3 gains a prior-art paragraph; §9 gains two entries (slot vs outbox; where causality rides and who stamps lineage). |
| 4 | 2026-11-27 | 🍃 | An outside reader's row-by-row completeness table against AWS Lambda, at `104c644e` (after a back-merge of `main` at `88d486cc`). Nine rows closed as this RFC's decisions. (1) **Retries** (§5.2): `max_attempts` 1 to 3, counting the first, with exponential backoff `b × 2^(n−2)`, registered per worker, refused above 3, copied into the context as `retry` inside the binding; only worker errors and lost attempts retry; admission refuses attempts that cannot fit the deadline; the **retry horizon** is `deadline_ms` and the **replay horizon** `deadline_ms + r`, and the slot is kept until the replay horizon plus the TTL. (2) **The slot's clock judges the deadline** (§5.2): the authoritative store's clock; a success after `deadline_ms` is refused and fills `failed`, reason deadline, so a late success can no longer win first-write; receipts gain `late` (§5.3). (3) **Cancel** (§4.2): by the verified invoker, or by the consent holder through revocation; fills `failed`, reason `cancelled`, linearized at the accept. (4) **Poison** (§5.2): failures counted per input key (worker and event, without `summons_id`); after three, the key is **parked**, a parked record is sung, and only a named releaser releases it. (5) **On-air identity** is `(station key, summons_id)` (§6.1, §0.2 claim 4, §5.3). (6) **Quorum** counts distinct key holders (§3.3, §7). (7) **`log_destination`** carries refs, counters and error classes only, by the runner's whitelist (§2.2, §4.3, §7). (8) **Size**: over the item ceiling, the summary goes by RFC-0001's `body_ref`, and lineage is never sent by reference (§6.1, §4.4). (9) **Unknown keys refused** is a deliberate departure from RFC-0001 §9.5 (§2.1, §5.3). The running example gains `retry` and `wall_s` 240, so Vector 1 and its binding changed. §8 gained cases 13 to 17, and 1a v and 11 iii were amended; §7 gained three rows; §9 gained five entries. Prior art cited where it bears, each with where it breaks: CloudEvents 1.0 (§6.1), Knative delivery (§5.2), Temporal Workflow Id policies (§5.1, §5.3), RFC 4271 §9.1.2 (§6.3), the transactional outbox (§5.3), Saltzer and Schroeder (§4.2), Hardy (§4.1). Also, from 🪨's receipt on #198: §1.1 and §5.3's prior art now say the OpenClaw outbox matches on duplicate and `key_conflict` but deliberately never replays an uncertain send, so its tests cannot stand in for the summons relay. |

---

## References

Informative only, except BCP 14 and RFC 8785. Each entry was verified for research note R3
(`karmaterminal/frond-gloss:crusade/research/R3-bibliography.md` §1 and §4) on 2026-11-26: AWS pages were fetched
and the quoted passages read; DOIs were resolved on Crossref; arXiv metadata was read from the arXiv API. Where
only metadata was read, the entry says so, and this RFC claims no more than that.

Revision 4's entries (marked *rev 4*) are not part of R3. Each was fetched on 2026-11-27, and each says what
was read: a page and the passages quoted, or metadata only, from Crossref.

**Invocation**

- **[AWS-Invoke]** Amazon Web Services. *Understanding Lambda function invocation methods* and *Invoke a Lambda function synchronously*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html and https://docs.aws.amazon.com/lambda/latest/dg/invocation-sync.html (accessed 2026-11-26)
- **[AWS-AsyncErrors]** Amazon Web Services. *How Lambda handles errors and retries with asynchronous invocation* and *Understanding retry behavior in Lambda*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html and https://docs.aws.amazon.com/lambda/latest/dg/invocation-retries.html (accessed 2026-11-26)
- **[AWS-ESM]** Amazon Web Services. *How Lambda processes records from stream and queue-based event sources*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/invocation-eventsourcemapping.html (accessed 2026-11-26)
- **[AWS-Context]** Amazon Web Services. *Using the Lambda context object to retrieve Node.js function information*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/nodejs-context.html (accessed 2026-11-26)
- **[AWS-EDA]** Amazon Web Services. *Creating event-driven architectures with Lambda*. AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/concepts-event-driven-architectures.html (accessed 2026-11-26)
- **[CloudEvents-1.0]** CloudEvents. *CloudEvents specification, version 1.0.2*, the `id` and `source` attributes. https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md (read at https://raw.githubusercontent.com/cloudevents/spec/v1.0.2/cloudevents/spec.md, accessed 2026-11-27; *rev 4*)
- **[Knative-Delivery]** The Knative Authors. *Handling delivery failure*, the delivery spec (`retry`, `backoffPolicy`, `backoffDelay`, `deadLetterSink`). Knative documentation. https://knative.dev/docs/eventing/event-delivery/ (accessed 2026-11-27; *rev 4*)
- **[Temporal-WorkflowId]** Temporal Technologies. *Workflow Id and Run Id*, the Workflow Id Reuse and Conflict Policies. Temporal documentation. https://docs.temporal.io/workflow-execution/workflowid-runid (accessed 2026-11-27; *rev 4*)
- **[Outbox]** Richardson, C. *Pattern: Transactional outbox*. microservices.io. https://microservices.io/patterns/data/transactional-outbox.html (accessed 2026-11-27; *rev 4*)
- **[JonasEtAl2019]** Jonas, E., Schleier-Smith, J., Sreekanti, V., Tsai, C.-C., Khandelwal, A., Pu, Q., Shankar, V., Carreira, J., Krauth, K., Yadwadkar, N., Gonzalez, J. E., Popa, R. A., Stoica, I., & Patterson, D. A. (2019). *Cloud Programming Simplified: A Berkeley View on Serverless Computing*. arXiv:1902.03383. https://arxiv.org/abs/1902.03383 (*metadata verified; the section on shared state was not confirmed*)

**Protection and routing**

- **[SaltzerSchroeder1975]** Saltzer, J. H., & Schroeder, M. D. (1975). The protection of information in computer systems. *Proceedings of the IEEE*, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939 (*metadata from Crossref; the complete-mediation sentence was read at the copy on Saltzer's MIT pages, https://web.mit.edu/Saltzer/www/publications/protection/Basic.html, accessed 2026-11-27; rev 4*)
- **[Hardy1988]** Hardy, N. (1988). The confused deputy (or why capabilities might have been invented). *ACM SIGOPS Operating Systems Review*, 22(4), 36–38. https://doi.org/10.1145/54289.871709 (*metadata only, from Crossref; rev 4*)
- **[RFC 4271]** Rekhter, Y., Ed., Li, T., Ed., and S. Hares, Ed., *A Border Gateway Protocol 4 (BGP-4)*, RFC 4271, January 2006, https://www.rfc-editor.org/rfc/rfc4271 (§9.1.2 read in the plain-text copy, accessed 2026-11-27; *rev 4*)

**Cell signalling**

- **[WatersBassler2005]** Waters, C. M., & Bassler, B. L. (2005). Quorum sensing: cell-to-cell communication in bacteria. *Annual Review of Cell and Developmental Biology*, 21, 319–346. https://doi.org/10.1146/annurev.cellbio.21.012704.131001 (*abstract read*)

**Normative**: BCP 14 [RFC 2119] [RFC 8174], as in §0.3. And [RFC 8785]: Rundgren, A., Jordan, B., and S.
Erdtman, *JSON Canonicalization Scheme (JCS)*, RFC 8785, June 2020, https://www.rfc-editor.org/rfc/rfc8785,
for §5.3's binding. It was added in revision 2, cited by number, and is not part of R3's check.
