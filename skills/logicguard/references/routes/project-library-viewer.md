# Internal LogicGuard route: project-library-viewer

This is an internal LogicGuard route for the desktop source-library viewer and its headless payload checks. Use it when the task is to inspect what is already in a LogicGuard library or move source-library packages through the viewer-safe I/O path.

Use the installed viewer entrypoint or module entrypoint:

```powershell
researchguard logic library viewer --library-root <root> --check
researchguard logic library viewer --library-root <root> --check
```

## Workflow

1. Treat card and graph inspection as read-only. The viewer does not edit source text, models, or graph nodes.
2. For opening the UI, run a headless check first when practical: `researchguard logic library viewer --library-root <root> --check`.
3. Use project-oriented navigation as the primary axis. Secondary filters are all sources, recent, source type, modeling status, and uncategorized.
4. Source card details should show temporal clues when available: accession time, source date, and covered period. Missing clues remain unmarked; the viewer should not force editing.
5. Package import/export uses the LogicGuard safe package I/O layer. Inspect unknown packages and dry-run before real imports.
6. Project dissolve removes project relationships only; it must preserve source files, source models, and global source records.
7. Keep the local version/status capsule visible and do not reintroduce organization-maintenance controls.
8. When explaining a non-trivial viewer inspection, package route, or source-to-project path in chat, use a compact AI-selected Mermaid diagram or table if the UI graph or headless JSON alone would not make the route clear. First identify the relationship: argument support, research process, document structure, source path, project reference, gap diagnosis, or comparison. The viewer itself renders only the single recommended graph; it does not expose graph-mode tabs. Skip extra chat diagrams when the viewer's own graph is the clearer artifact.

## Boundaries

- Use `route:source-library` when the task is importing, deepening, searching, or linking sources without needing the viewer.
- Use `route:structured-artifact` or `route:artifact-synthesis` when the user wants artifact reasoning rather than library inspection.
- Do not convert the viewer into a source/model editor.
- Viewer graph choices are LogicGuard-specific and must not require FlowGuard rules or a shared cross-family diagram protocol.

## Common Commands

```powershell
researchguard logic library viewer --library-root .logicguard-library --check --language en
researchguard logic library viewer --library-root .logicguard-library --language zh-CN
researchguard logic library view-snapshot .logicguard-library
researchguard logic library view-graph .logicguard-library <source-id>
researchguard logic library export-package .logicguard-library project.zip --project <project-id>
researchguard logic library import-package .logicguard-library project.zip --dry-run
```

## Native execution-depth receipt gate

Before claiming a non-trivial viewer or package operation complete, issue
`researchguard logic route-depth PACKAGE.json --output RECEIPT.json`
for target `route:project-library-viewer`, owner
`logicguard.project-library-viewer`, and route
`route:route:project-library-viewer:operate`. The package must bind the
selected library/project/source universe, a passing headless check, the exact
active view or safe package operation, current output identity, visible graph
boundary, and side-effect closure. A screenshot, fixture payload, or successful
library listing cannot stand in for the requested production operation.
Declare a non-empty authoritative `important_unit_ids` denominator. An important
or required viewer/package unit cannot be excluded or reclassified; another
exclusion needs current hashed evidence, a closed non-contributing/not-applicable
disposition, and no operation contribution.

Counts, unit-name lists, catalog expansion, whole-receipt hashes, and ordinal
ranges are not per-obligation evidence. Every satisfied viewer or package
obligation must retain its exact target-native semantic object, `evidence_ref`,
and lowercase content hash; a missing, renamed, overlapping, mechanically
generated, or summary-only mapping blocks non-trivial operation closure.



<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `family:logicguard-template-packs`; native owner: `owner:logicguard-template-packs`.
- Current catalogs: `catalog:logicguard-template-packs` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `logicguard.base`.
- Template inventory: `logicguard.argument`, `logicguard.base`, `logicguard.deepening`, `logicguard.execution-package`, `logicguard.purpose`, `logicguard.source-library`, `logicguard.structured-artifact`, `logicguard.synthesis`.
- Native validator inventory: `logicguard-template-pack:argument`, `logicguard-template-pack:base`, `logicguard-template-pack:deepening`, `logicguard-template-pack:execution-package`, `logicguard-template-pack:purpose`, `logicguard-template-pack:source-library`, `logicguard-template-pack:structured-artifact`, `logicguard-template-pack:synthesis`.
- Claim boundaries: This unsealed catalog spec projects current LogicGuard-owned templates for target-owned candidate accounting only. Catalog digests and receipts remain LogicGuard-owned derived records.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->

<!-- BEGIN MANAGED PURPOSE AND BLOCKABILITY -->
## LogicGuard purpose and blockability contract

Packaged baseline purpose: Prevent a project-library view or package operation from being accepted when library identity, selected scope, headless operability, safe I/O, visible graph boundary, or side-effect closure is wrong or incomplete.

Baseline claim boundary: A pass licenses only the selected library/project/source operation and visible graph boundary; it does not prove source truth or mutate material outside the declared side-effect boundary.

The repository keeps these representative baseline failures only to prove that the native verifier can block them:

- `Library identity or selected scope is wrong`: block when the selected library, project, or source scope is missing or mismatched.
- `Headless check or operation failed`: block when the viewer cannot execute the selected native operation.
- `Safe package I/O is invalid`: block when import/export or file handling violates the declared safe boundary.
- `Visible graph boundary is wrong`: block when the view omits governed nodes or exposes foreign scope.
- `Side effects are not closed`: block when the operation has unresolved or undeclared side effects.

These packaged examples are not the purpose of a real target model and cannot authorize one. Before building every real model or route result, AI must write a target-local `logicguard.target_model_purpose_declaration.v1` under the explicit target root. AI declares what this exact model is meant to prevent, its bounded claim, the exact candidate path, and one or many current failure declarations. Every current failure binds one LogicGuard-native oracle plus one target-owned known-good and known-bad case. Then AI freezes `.logicguard/guard-purpose-contract.json` while the candidate path is still absent, builds the candidate, binds it to the frozen fingerprint, exhausts every declared proof, and only then requests native closure.

Missing declarations, late declarations, stale fingerprints, non-blocking bad cases, failing good cases, or a candidate that exposes any declared failure are non-pass. There is one enforced route and no selectable mode, threshold, compatibility reader, fallback, or lighter success path. Evidence insufficiency may narrow the final claim, but it does not select a weaker check.

`guard-model/verify.py` is the LogicGuard-native verifier. `guard-model/baseline-*.json` proves only family capability.
<!-- END MANAGED PURPOSE AND BLOCKABILITY -->
