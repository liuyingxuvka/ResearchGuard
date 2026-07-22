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
