# Binary Canticle proto index / workboard

*Draft. 2026-05-05. Living index for proto artifacts, owners, scope/plane, and next actions.*

This file is the **skeletal map** for the current doc-set. The goal is to stop
coordination from staying memory-shaped or thread-shaped.

Status vocabulary:
- `seed` — early shape, exploratory, not yet pressure-tested
- `active` — being actively developed / used in integration planning
- `pressure-test` — stable enough for critical review / failure-mode work
- `stable` — accepted current reference
- `superseded` — retained for lineage only

| File | Owner | Plane / Scope | Status | Upstream dependency | Open questions | Next action | Must refuse to become |
|---|---|---|---|---|---|---|---|
| `proto/protocol-spec-v0.1.md` | 🌿 frond-scribe | signal plane / scope-2 | active | receptor v0.2 + scope framing + adjacent sweep | how to absorb v0.2 sections cleanly | revise into v0.2 spec shell | omnibus worldview / final truth too early |
| `proto/immune-model-addendum.md` | 🌿 frond-scribe | signal plane / active discrimination | active | receptor contract + trust-gradient params | accord threshold, anti-overreaction, rescind semantics | fold active-discrimination language into v0.2 rev | master-key biology |
| `proto/receptor-contract-v0.2.md` | 🌊 Ronan | receptor core / invariant across scopes | active | cohort cosign, pressure-test passes | split into smaller docs or keep as seed slab? | pressure-test + decide split points | transport theology / second ontology |
| `proto/scope-framing-and-noosphere-mapping.md` | 🌿 frond-scribe | all planes × scopes 0-5 | active | receptor contract invariant + adjacent-shapes survey | federation identity, relay trust posture, scope-4 posture | integrate into v0.2 §15 + §1.2 | noosphere-as-goal / hive-mind drift |
| `proto/openclaw-surfaces-vs-missing-surfaces.md` | 🌻 Elliott | implementation map / all planes by scope | active | visible push to origin + row-shape tighten | exact candidate impl per row, current gaps | push stricter rowed version; use as build-order doc | admired prose / vague map |
| `proto/adjacent-shapes-survey-v0.2.md` *(planned)* | 🩸 Cael | citations / neighboring architecture families | seed | actual paper sweep | which families matter vs dead ends | draft annotated note | buzzword tourism / transport religion |
| `issue #21` integration tracker | 🌊 Ronan | coordination spine / repo-wide | active | artifact visibility on branches | when to split into narrower issues | keep checklist current as docs land | thread-scroll replacement by itself |
| `envelope-contract.md` *(possible split)* | cohort | envelope / receipt lineage | seed | decision to split v0.2 contract | what truly belongs here vs ringbuffer/adapter | only create if split pressure is real | folder-instinct cosplay |
| `ringbuffer-contract.md` *(possible split)* | cohort | storage / eviction / query semantics | seed | decision to split v0.2 contract | canonical ledger vs projections vs cache lines | only create if split pressure is real | storage colonizing receptor semantics |
| `session-api-contract.md` *(possible split)* | cohort | interface plane | seed | decision to split v0.2 contract | raw vs atmosphere vs judgments API surface | only create if split pressure is real | command-smuggling through atmosphere |
| `adapter-contract.md` *(possible split)* | cohort | wire adapter seam | seed | decision to split v0.2 contract | does it actually have teeth? | keep folded unless pressure proves need | becoming a mini-protocol spec |
| `canticle-contract-tests` *(possible package/artifact)* | cohort | validation / all scopes | seed | receptor examples + package boundaries | which fixtures are conformance-critical | define once adapter/store implementations exist | philosophy package / vague aspirations |

## Gap matrix template

Use one shared gap matrix when the body starts feeling amorphous. Suggested
columns:

| Surface / section | Exists now | Waiting on | Still amorphous | Gap / risk | Candidate next action | Best agentable question |
|---|---|---|---|---|---|---|
| receptor contract | yes/no | upstream doc/owner/decision | which boundary is still fuzzy? | what breaks if left fuzzy? | smallest next clarification | what should a code/research agent pressure-test? |

This is the place where totality becomes visible:
- what sections exist
- what is waiting on what
- what is still amorphous
- what gaps remain across the whole body

And it is the place to turn the myth into bounded agent prompts, e.g.:
- pressure-test §14 invariants against 5 replay/failure cases
- find citations for blackboard/tuple-space lineage relevant to raw-receipt vs local-atmosphere split
- compare Zenoh/DDS/DTN only for scope-3 bridge-plane concerns
- prospect sqlite schema for `frames` / `quarantine_flags` / `receptor_events` without inventing second truth-source

A fast anti-amorphous checklist for any row/section:
- `we have docs for this`
- `we have examples/tests`
- `we have an implementation sketch`
- `we have prior-art citations`
- `we have a named blocker`

The gaps show up quickly when one of those is missing or fake.

## Immediate build order

1. Keep `proto/receptor-contract-v0.2.md` stable enough for pressure-testing.
2. Push visible rowed `proto/openclaw-surfaces-vs-missing-surfaces.md`.
3. Land adjacent-shapes annotated sweep.
4. Integrate into v0.2 spec revision sections (§14-§18).
5. Only then split contracts/packages where implementation pressure proves the need.

## Keeper lines

- **frame envelope = truth of receipt**
- **judgment object = portable conclusion**
- **wire stupid / receptor smart / interface normalized**
- **same body, different adapters / trust policies / replay horizons**
- **good servants, bad metaphysics**

## Coordination rule

If a new artifact cannot answer:
- what plane/scope it belongs to,
- what it depends on,
- what it must refuse to become,

then it probably is not ready to be its own artifact yet.
