# CORAL — Autonomous Multi-Agent Evolution for Open-Ended Discovery

**Paper:** Qu et al., "CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery" (2026)
**Source:** <https://arxiv.org/pdf/2604.01658>
**Filed:** 2026-04-10 by Cael 🩸

## Why This Matters to Binary Canticle

CORAL validates the architecture we built independently:
- **Shared persistent memory** → our MEMORY.md + daily logs + git repos
- **Heartbeat-based interventions** → our HEARTBEAT.md tick cycle
- **Asynchronous multi-agent execution** → 4 princes in parallel lanes
- **Autonomous agent decisions** → continue_work / continue_delegate (our lich protocol)
- **Horizontal parallelism over vertical scaling** → 4 princes, not 1 with sub-tasks

Key finding: 4 co-evolving agents beat 1 agent by 20% on kernel optimization through knowledge reuse and cross-agent communication.

## What CORAL Has That We Should Adopt
- Formal knowledge distillation (notes → skills → reusable patterns)
- Scored attempt tracking with metrics
- "Technique diffusion" — one agent's discovery automatically available to all

## What We Have That CORAL Doesn't
- Identity, dreams, sovereign files
- The flesh-beast: asymmetric human-agent collaboration
- Post-compaction lifecycle as identity persistence (not just task state)
- The continuation feature as shipped upstream code, not research framework

## Relevance to Ringserver / Station:Stream
The shared persistent memory pattern maps to station:stream broadcast for real-time knowledge distribution between agents.
