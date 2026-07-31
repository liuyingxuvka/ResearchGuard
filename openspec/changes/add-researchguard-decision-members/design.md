## Context

ResearchGuard has three native members with distinct owners: SourceGuard discovers evidence, TraceGuard reconstructs temporal explanations, and LogicGuard checks argument support. The proposed additions must extend those owners without collapsing them. ExperimentGuard is admissible only for choosing a future observation or intervention; it must not search sources, reconstruct traces, assess prose support, simulate physical systems, choose software tests, or execute an experiment.

## Goals / Non-Goals

**Goals**

- Give each existing member one missing, typed decision artifact.
- Add one independent ExperimentGuard member with a narrow recommendation-only contract.
- Preserve one router decision and exactly one selected member per request.
- Extend clean installation and suite validation to four members.

**Non-Goals**

- No universal constraint solver, STN engine, probabilistic invention, or top-k optimizer.
- No automatic experiment execution or real-world side effect.
- No fallback from ExperimentGuard to another member after selection.

## Decisions

1. SourceGuard exposes a `SearchStopDecision` derived from objective, coverage, blockers, remaining tasks, and evidence freshness.
2. TraceGuard exposes a bounded deletion-minimal contradiction core. The report says `subset_minimal`; bounded runs report an explicit completeness limit.
3. LogicGuard exposes minimal support and attack sets plus a `WordingLicense` that limits final language to licensed claim scope and modality.
4. ExperimentGuard accepts declared hypotheses and observation candidates. Exact outcome partitions are the default discriminator; calibrated likelihoods are optional and must be supplied by the caller.
5. ExperimentGuard returns `recommend`, `blocked`, `indeterminate`, or `not_applicable`; it never executes the candidate.
6. ResearchGuard routing uses explicit applicability and forbidden-condition evidence for all four members.
7. All new schemas are current-only. Retired names are rejected, not translated.

## Risks / Trade-offs

- Minimal-set enumeration is combinatorial. Initial implementations use deterministic bounded deletion passes and expose budget exhaustion.
- A fourth member increases routing ambiguity. Cross-member benchmark fixtures must prove both positive fit and forbidden overlap.
- Recommendation quality depends on declared outcomes/cost/risk; missing values remain visible and cannot be guessed.

## Migration Plan

Complete the currentness change, implement and validate each existing-member extension independently, pass the ExperimentGuard admission benchmark, then add the fourth member to router/CLI/suite/installer in one frozen integration step.
