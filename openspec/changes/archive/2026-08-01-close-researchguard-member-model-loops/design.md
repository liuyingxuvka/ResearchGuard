## Context

ResearchGuard is a versioned suite, not a fourth research mathematics engine. LogicGuard owns argument acceptance and perturbation; SourceGuard owns search planning and evidence qualification; TraceGuard owns temporal/storyline reconstruction; ExperimentGuard owns finite hypothesis discrimination. Each repository member already has its own task-local owner.

## Goals / Non-Goals

**Goals:**

- Keep all four member loops independent and target-owned.
- Make native execution-depth gaps drive the next model/evidence action.
- Add externally supplied experiment observations and prediction-matrix revisions.
- Preserve immutable revisions, protected claims, source lineage, temporal limits, holdouts, and rollback.

**Non-Goals:**

- No ResearchGuard-wide model, level, score, truth judgment, or automatic member chaining.
- ExperimentGuard never runs experiments or invents outcome probabilities.
- No compatibility readers or reuse of another member's receipts.

## Decisions

1. Add gap-transition fields to existing iteration receipts rather than create a shared iteration engine.
2. LogicGuard refuses `no_revision_needed` as closure when its current native depth receipt still contains important gaps.
3. SourceGuard distinguishes an available search action from provider/permission unavailability and finite-action exhaustion.
4. TraceGuard requires evidence/event/time/alternative/causal-boundary closure appropriate to the requested claim and never treats narrative smoothness as future prediction.
5. ExperimentGuard adds `observe` and `iterate` data paths after external execution; unexpected results create a matrix-revision gap, not a truth decision.
6. Every current task packet requires task purpose, independently bound coverage,
   explicit assumptions and unknowns, iteration/predecessor identity, base and
   candidate identity, current native receipt, computed gap lineage, and one exact
   terminal. Former packet schemas are rejected.
7. Gap transitions and progress are computed from consecutive current receipts;
   the caller cannot declare a gap resolved or a task understood.
8. Candidate closure requires a holdout whose evidence identity is disjoint from
   construction evidence. The target-native receipt remains semantic authority.
9. The umbrella consumes exactly four member-authored admission rows bound to the
   same request and current member contract fingerprints. Zero or many admitted
   rows block before execution.

## Risks / Trade-offs

- [Member prompts drift from their owners] -> update each member's SKILL.md beside its native code and run suite checks.
- [A large source/storyline loop runs too long] -> finite action budgets and explicit external/finite-exhaustion terminals remain visible.
- [A member result is mistaken for suite success] -> umbrella prompt and receipts retain member id, claim boundary, and opaque native receipt references.

## Migration Plan

Implement member by member using current schemas and current receipts, update tests and generated projections, run the ResearchGuard suite check, then install the local distribution. Existing historical OpenSpec changes remain untouched.
