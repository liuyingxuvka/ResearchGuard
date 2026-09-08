# Existing Model Preflight: SkillGuard 0.4 Maintenance

## Task

Refresh author maintenance for the four ResearchGuard consumer skills without changing their domain behavior, adding a second runtime, writing predecessor repositories, or activating a global installation.

## Model search

- Canonical plane: `development_process`; related `agent_operation` targets remain owned by each consumer skill.
- Search paths: `.flowguard/*skill_contract_model.py`, `.flowguard/researchguard_suite_model.py`, `skills/*/.skillguard/contract-source.json`, OpenSpec change `refresh-skillguard-0-4-maintenance`.
- Primary hits:
  - `researchguard.researchguard.contract.current`
  - `researchguard.logicguard.contract.current`
  - `researchguard.sourceguard.contract.current`
  - `researchguard.traceguard.contract.current`
  - parent `researchguard.suite.route-authority.current`
- OpenSpec context is read-only planning context for FlowGuard and is not a model, test owner, receipt, or product-runtime authority.

## Software-DNA integration boundary

- The one source-native software-DNA authority is
  `models/software_dna/researchguard.json`. It contains one repository root,
  four recursively decomposed member subtrees, a provider-neutral inventory
  contract, exact forward/reverse indexes, affected-only closure, and seven
  readiness layers.
- `src/researchguard/software_dna.py` independently enumerates the repository
  boundary before reading surface-owner bindings. Unknown adapters, parse
  failures, duplicate owners, dangling edges, and unknown impact ids block;
  no Python-only subset, caller path list, retry, alias, or fallback is allowed.
- FlowGuard consumes that report read-only through the suite model runner. It
  remains the sole canonical projection owner; member-domain DNA and SkillGuard
  contracts are not copied into the repository root model.
- The imported FlowGuard 0.68.14 source checkout must be clean before applying
  its project-upgrade or generating new FlowGuard/SkillGuard evidence. A dirty
  peer checkout leaves those writes visibly blocked.

## Existing ownership

- FunctionBlocks: each member model owns its consumer-contract validator and native-test validator.
- State: `unit:researchguard-suite` owns author-maintenance state; each member owns its target domain state.
- Side effects: current contract generation writes only the member's `compiled-contract.json` and `check-manifest.json`; validation writes only private author run/evidence records.
- Public entrypoints: four standalone consumer `SKILL.md` files; the single `researchguard` Python distribution remains the executable suite facade.
- Responsibilities: SkillGuard owns inventory/evidence reconciliation only; each target owns route, semantics, checks, and depth.

## Reuse decision

`extend_existing`: reuse the four current contract models and the suite route-authority model, adding one maintenance-process model that derives its StructureMesh and TestMesh from those owners. No new domain boundary is introduced.

## Duplicate-risk check

- Old standalone LogicGuard, SourceGuard, and TraceGuard repositories are protected external migration inputs. They are not enrolled, read as current authority, modified, or deleted by this change.
- The four consumer skill paths are separate entrypoints but not separate Python runtimes.
- OpenSpec artifacts and consumer installations cannot own or satisfy SkillGuard checks.

## Downstream routes

- `flowguard-development-process-flow`: lifecycle and freshness owner.
- `flowguard-structure-mesh`: single-suite/four-entrypoint structural parity.
- `flowguard-test-mesh`: eight declared checks and one owner per check.
- `skillguard`: current author adoption, direct compile, same-unit execution, and clean projection audit.

## Claim boundary

This preflight selects existing owners and records duplicate risks. It does not prove current compilation, check execution, installation, publication, predecessor retirement, or future AI behavior.
