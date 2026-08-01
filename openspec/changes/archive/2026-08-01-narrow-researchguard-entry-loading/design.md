## Context

The suite already has one native owner per responsibility, typed handoffs, current task-local maturation loops, and one current FlowGuard model authority. The weakness is at the entrance: admission-v1 accepts caller-authored applicability labels, forces every umbrella request into one member even when the request contains irreducible responsibilities, and the largest consumer skills combine first-action routing with deep contracts, command catalogs, safety language, and template-pack instructions. The repository is an explicit SkillGuard author source, so changes must preserve target-owned semantics and update the same-unit contracts without making SkillGuard a consumer dependency.

## Goals / Non-Goals

**Goals:**

- Derive member admission from source-bound facts rather than caller verdicts.
- Keep direct member use direct and make ambiguous umbrella use read one compact generated index before selecting the smallest member set that can cover every primary responsibility.
- Require any necessary multi-member set to declare order, dependencies, per-member responsibilities, input/output handoffs, single field ownership, and one overall claim boundary.
- Move existing material rather than weaken or reinvent member behavior.
- Check real load edges and first-read budgets with meaningful headroom.
- Preserve current FlowGuard model ownership and exact SkillGuard maintenance-unit boundaries.

**Non-Goals:**

- No U-levels, self-rated understanding, central learner, unbounded `run all`, automatic guessing of member arguments, compatibility reader, fallback router, or new universal Guard.
- No change to LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard native domain algorithms or closure thresholds.
- No installation, Git commit, push, tag, GitHub release, or final full maintenance-unit validation in this change's implementation task.

## Decisions

### 1. Use a current task-facts packet and member-owned condition contracts

The packet contains one or more primary-responsibility facts plus optional context facts. Every fact has a stable id, typed fact kind, statement, role, and source span. Each member contract declares condition ids, accepted fact kinds, required groups, forbidden conditions, first action, and first reference. A shared structural helper validates the packet and derives results; it does not contain member semantics.

This keeps AI responsible for extracting observable request facts while removing its ability to write `applicable`. A generic natural-language classifier was rejected because it would recreate an untestable central router. Caller-authored applicability-v2 was rejected because it would preserve the admission-v1 weakness under a new schema.

### 2. Require exact forbidden-condition dispositions

Every member contract's forbidden condition must have one current disposition. A matching forbidden fact makes the condition `present`; otherwise the task-facts packet must carry an exact per-condition `absent` or `unknown` review bound to the request source. Missing, duplicate, foreign, or generic clearance blocks. The program computes the aggregate forbidden status.

Absence cannot be proven perfectly from text alone, but exact condition accounting is materially stronger and testable. Requiring a second model to judge every absence was rejected because it adds cost without independent authority.

### 3. Select the minimum sufficient member set

Only `primary_action` facts create responsibilities that must be covered. Context facts may satisfy required inputs or expose forbidden conditions but do not create another responsibility. The router computes every applicable member's coverage, finds the smallest set covering all primary facts, and blocks equal-size ambiguity rather than guessing. If one member covers all responsibilities, any larger requested set is over-selection and blocks.

When the unique minimum set has more than one member, the packet must carry one current composition. The composition's member set must exactly equal the derived set and declare a contiguous order, earlier-step dependencies, unique responsibility ownership, typed handoffs, producing-step field ownership, and an overall claim boundary. The umbrella emits `composition_ready`; it does not guess member-specific arguments or claim that native member work ran.

### 4. Generate one compact admission index from the contracts

The index is a deterministic projection of the four current contracts. A checker compares it byte-for-byte with the generated projection. The umbrella skill points only to this index; it no longer asks an agent to load all four member skills. Direct member descriptions and commands continue to bypass it.

### 5. Split member prompts by trigger, not by quality mode

Every entry keeps purpose, use/non-use boundary, first action, reference trigger map, deepening triggers, terminals, and claim boundary. Existing paragraphs move into target-owned references grouped by when they are needed: general/native protocol, task iteration and closure, route-specific workflow, commands, safe output, and validated template packs. A bounded task may stop after its native first action; a task that triggers deepening must follow the same current strict loop as before.

### 6. Add a target-owned prompt load graph

A JSON manifest declares entry bundles, route-triggered references, budgets, and prohibited sibling edges. A checker verifies paths, generated-index freshness, ownership, trigger completeness, entry byte totals, and known-bad fixtures. SkillGuard consumes the check as declared evidence; it does not decide routing semantics.

### 7. Preserve one FlowGuard suite model owner

The existing ResearchGuard suite model and common member contract model gain admission-v2 and conditional-load obligations. No parallel model is introduced. Focused model execution produces candidate evidence; current authority activation and the final parent gate remain with the orchestrating release workflow.

## Risks / Trade-offs

- **[Risk] Fact kinds may be extracted incorrectly** → Every fact is source-bound; minimum-coverage, forbidden, over-selection, and equal-set ambiguity rules block unsafe guessing, and real corrections become known-bad fixtures rather than automatic rule mutation.
- **[Risk] Moving text may accidentally weaken a member** → Maintain a source-to-reference migration ledger in the prompt manifest, reject duplicate or missing ownership, and keep all existing native closure checks.
- **[Risk] References become a new eager dump** → Every edge requires a named trigger and the load-graph checker rejects untriggered loads.
- **[Risk] A patch release contains an umbrella input-schema break** → The suite is pre-1.0, uses direct-current replacement by policy, documents the new task-facts interface, and provides no dual reader.
- **[Risk] Parallel agent work changes the same repository** → Re-read status before edits and validation, preserve all unknown writes, and never clean the existing `.flowguard/evidence/` tree.

## Migration Plan

1. Freeze the current source and peer-write inventory; use FlowGuard `0.68.2` as the final project-toolchain baseline.
2. Introduce admission-v2 and generated index, update focused routing tests, then remove admission-v1 authority in the same change.
3. Move prompt material to references and enable load-graph checks member by member.
4. Update suite models, version identity, changelog, and SkillGuard contract sources/compiled projections.
5. Run affected tests and model checks only. The parent workflow later freezes all repositories, performs final unit validation, installs, commits, pushes, tags, and releases.

Rollback before publication restores the source diff as one unit and leaves the prior installation untouched. After publication, correction requires a new immutable patch release rather than moving the tag.
