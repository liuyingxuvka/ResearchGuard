## Context

ResearchGuard is the sole executable Python suite for four independently invokable consumer skills: `researchguard`, `logicguard`, `sourceguard`, and `traceguard`. All four source contracts already declare `unit:researchguard-suite`, two target-owned checks per member, and clean consumer exclusions, but their generated authority predates SkillGuard 0.4 and the repository has no current author-project manifest or managed author block.

The implementation must preserve the installed consumer boundary and all work in the old standalone repositories. OpenSpec supplies only this planning package; FlowGuard owns process, structure, and test evidence; SkillGuard supervises only the exact checks declared by each target.

## Goals / Non-Goals

**Goals:**

- Establish one current author identity for the four-member ResearchGuard maintenance unit.
- Regenerate current author authority without changing the target-owned route, semantic checks, evidence subjects, or depth.
- Model the single-suite structure and eight-check validation mesh explicitly.
- Produce current local validation and source-to-consumer projection evidence without activating an installation.

**Non-Goals:**

- No domain behavior, public command, package API, or skill routing change.
- No global installation, release, publication, Git commit, or GitHub action.
- No deletion, rewriting, or adoption of old standalone LogicGuard, SourceGuard, or TraceGuard repositories.
- No SkillGuard evidence retention redesign; old evidence remains untouched in this change.

## Decisions

1. **Keep one suite maintenance unit with four complete members.** The source contracts already agree on `unit:researchguard-suite`, and the Python package provides the only executable runtime. Splitting the unit would create duplicate runtime and validation authority. The alternative—independent author units—was rejected because it contradicts current source and runtime ownership.
2. **Use direct current replacement.** The current SkillGuard 0.4 compiler will regenerate `compiled-contract.json` and `check-manifest.json` from each unchanged `contract-source.json`. No old-schema reader, converter, alias, or dual authority will be added.
3. **Preserve target-owned depth.** The frozen TestMesh contains exactly eight checks already declared by the targets: one consumer-contract check and one native-test owner per member. SkillGuard may reconcile execution and evidence but may not add a domain check.
4. **Separate author proof from consumer projection.** Author manifests, contract trios, run state, and receipts remain author-only. A comparison stage builds the allowed consumer inventory from target runtime material and checks it against the current installed tree, but this change does not activate or modify the global installation.
5. **Treat old standalone repositories as protected external migration inputs.** Their unpushed and dirty work is outside this repository and remains untouched. Retirement is a future, separately authorized change after migration comparison.
6. **Use affected validation before one frozen unit closure.** Focused model and native checks run after their inputs stabilize. One SkillGuard unit plan owns all eight declared checks; no receipt crosses a maintenance-unit boundary.

## Risks / Trade-offs

- **Existing historical evidence is stale and unrooted** → write new run/evidence records to a distinct current run root and do not clean old stores here.
- **Installed consumers lack current target-owned release manifests** → report installation identity as incomplete while preserving exact content parity; activation is explicitly out of scope.
- **Concurrent edits could invalidate source or check identities** → inspect Git state before each write/validation phase and stop on overlapping peer changes.
- **A broad suite validation can be expensive** → run focused target-owned checks and the frozen affected unit plan; do not substitute a smaller set for the declared eight-check closure.

## Migration Plan

1. Create current OpenSpec, FlowGuard structure/process/test artifacts.
2. Add current author-project identity and managed author block.
3. Regenerate the four current contract trios directly.
4. Run model checks, focused native checks, and the frozen SkillGuard unit validation.
5. Record clean source/consumer projection differences and residual installation gaps.
6. Leave old evidence and old repositories intact. Rollback is the scoped repository diff; no external installation or publication state changes.
