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
| `README.md` | cohort | repo entry / framing | active | doc-spine stability | when to link task brief / seam notes cleanly? | refresh after sibling handoff docs settle | stale mythology posing as current architecture |
| `proto/protocol-spec-v0.1.md` | 🌿 frond-scribe | signal plane / scope-2 baseline | active | receptor v0.2 + scope framing + adjacent sweep | how to absorb v0.2 sections cleanly | revise into v0.2 spec shell | omnibus worldview / final truth too early |
| `proto/immune-model-addendum.md` | 🌿 frond-scribe + 🌊 convergence | signal plane / active discrimination | active | receptor contract + trust-gradient params | accord threshold, rescind semantics, stand-down shape | fold minimal immune grammar into v0.2 rev | master-key biology |
| `proto/receptor-contract-v0.2.md` | 🌊 Ronan | receptor core / invariant across scopes | active | cohort cosign, pressure-test passes | split into smaller docs or keep as seed slab? | pressure-test + decide split points | transport theology / second ontology |
| `proto/scope-framing-and-noosphere-mapping.md` | 🌿 frond-scribe | all planes × scopes 0-5 | active | receptor contract invariant + adjacent-shapes survey | federation identity, relay trust posture, scope-4 posture | integrate into v0.2 §15 + §1.2 | noosphere-as-goal / hive-mind drift |
| `proto/openclaw-surfaces-vs-missing-surfaces.md` | 🌻 Elliott | implementation map / all planes by scope | active | `origin/main@1457526` + convergence with adjacent handoff notes | exact candidate impl per row, current gaps | keep as build-order doc while sibling notes converge | admired prose / vague map |
| `proto/openclaw-inter-host-io-surfaces-and-spec.md` | 🌻 Elliott | current-surface / desired-surface seam | active | `origin/main@1457526` + convergence with `openclaw-vs-canticle.md` | what belongs here vs top-level brief? | diff/merge adjacent handoff notes into stable pair | duplicative sibling mythology |
| `proto/openclaw-vs-canticle.md` | 🌊 Ronan | boundary note / build-order seam | active | convergence with `openclaw-inter-host-io-surfaces-and-spec.md` | keep as sibling note or fold later? | continue convergence against shared bytes | essay drift / replacing the heavier surface docs |
| `proto/TASK-BRIEF.md` | 🌊 Ronan | top-of-repo compression / reader handoff | active | doc-spine stability | when to link from README vs keep proto-only | keep tiny; let bytes carry the handoff | mini-spec bloat |
| `proto/v0.2-workboard.md` | 🌻 Elliott | coordination spine / issues-and-lanes planning | active | artifact map maturity | when do draft docs become issues? | keep as staging doc for issue batch | replacing the canonical index |
| `proto/adjacent-shapes-survey-v0.2.md` *(planned)* | 🩸 Cael | citations / neighboring architecture families | seed | actual paper sweep | which families matter vs dead ends | draft annotated note | buzzword tourism / transport religion |
| `issue #21` integration tracker | 🌊 Ronan | coordination spine / repo-wide | active | artifact visibility on branches | when to split into narrower issues | keep checklist current as docs land | thread-scroll replacement by itself |
| `proto/ringbuffer-contract.md` | 🌊 Ronan | storage / bounded replay substrate | active | convergence with station:stream seam + receptor/store split | exact receipt record fields, eviction metadata, dedup rule | pressure-test against station:stream + replay/forget/use-cases | storage colonizing receptor semantics |
| `session-api-contract.md` *(possible split)* | cohort | interface plane | seed | decision to split v0.2 contract | raw vs atmosphere vs judgments API surface | only create if split pressure is real | command-smuggling through atmosphere |
| `adapter-contract.md` *(possible split)* | cohort | wire adapter seam | seed | decision to split v0.2 contract | does it actually have teeth? | keep folded unless pressure proves need | becoming a mini-protocol spec |
| `canticle-contract-tests` *(possible package/artifact)* | cohort | validation / all scopes | seed | receptor examples + package boundaries | which fixtures are conformance-critical | define once adapter/store implementations exist | philosophy package / vague aspirations |

## Gap matrix template

Use one shared gap matrix when the body starts feeling amorphous.

| Surface / section | Exists now | Waiting on | Still amorphous | Gap / risk | Candidate next action | Best agentable question |
|---|---|---|---|---|---|---|
| receptor contract | yes/no | upstream doc/owner/decision | which boundary is still fuzzy? | what breaks if left fuzzy? | smallest next clarification | what should a code/research agent pressure-test? |

This is the place where totality becomes visible:
- what sections exist
- what is waiting on what
- what is still amorphous
- what gaps remain across the whole body

And it is the place to turn the myth into bounded agent prompts, e.g.:
- pressure-test relay / clarion / non-convergence cases
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
2. Finish converging the adjacent handoff notes against shared bytes.
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
