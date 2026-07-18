# Internal TraceGuard route: case-library

Use this skill when the user wants to save, organize, search, reuse, or continue investigation material for TraceGuard.

Use it for:

- project/case-scoped source and evidence ledgers;
- messy investigation notes that are not ready for a final report;
- search directions and logic leads such as timeline, root cause, actors, motives, location, impact, contradiction, execution evidence, limiting evidence, or missing proof;
- Research Reasoning Atlas support material such as competing storylines,
  bounded causal candidates, counter-scenario questions, confounders,
  red-team narratives, and branch ids;
- thesis or paper handoff material such as literature item A to literature
  item B, technology case to method gap, method choice to validation setup,
  result to conclusion, and figure/table takeaway to later claim;
- writing TraceGuard evaluation gaps back into the investigation memory;
- preserving canonical inference-receipt history, object-universe fingerprints,
  critical object rows, temporal strata, ineffective critical perturbations,
  and expected-sensitivity gaps for later repair;
- building a TraceGuard model from saved case material.

Do not use it as a replacement for LogicGuard source library. LogicGuard source library is for durable formal source support. TraceGuard Case Library is lighter and more investigation-focused.

## Route

1. Identify the case.
2. Identify the current search direction or logic lead.
3. Save sources before extracted evidence.
4. Save evidence before events and traces.
5. Keep event facts separate from explanation candidates such as motive, effect, or future impact.
6. Before model construction, declare and prove this model instance's
   target-local prevention purpose, boundary, selected failure ids, one
   known-good, and one known-bad per selected failure.
7. Build or update the TraceGuard model from the library with that exact
   purpose contract.
8. Run TraceGuard's one canonical HL-MRF/QP evaluation.
9. Write gaps, contradictions, limiting evidence needs, execution-chain needs, handoff follow-ups, and same-class review findings back into the case.
10. When native storyline-depth evaluation runs, write unresolved alternatives,
    causal-mechanism/confounder gaps, the complete candidate-universe
    fingerprint, every untested high-impact perturbation,
    critical-uncovered ids, expected-sensitivity mismatches, and the canonical
    inference receipt id back into the case as an immutable observation; do
    not copy inferred status, rank, support, or causal license into input
    ledgers and do not reproduce the evaluator inside the library route.
11. For non-trivial investigations, preserve trace-card coverage: leads detected, trace cards created, layer coverage, missing roles, access gaps, live alternatives, and downstream handoff ids.
12. Use LogicGuard later for final claim support checks when writing a research-backed final artifact such as a report, paper, memo, brief, article, deck storyline, or public conclusion.
13. For non-trivial case-library work, update a case-library closure ledger and
    run the helper when available:

    ```powershell
    python %USERPROFILE%\\.codex\\skills\traceguard\scripts\traceguard_library_closure_check.py --ledger <trace-case-library-ledger.json> --json
    ```

    If the helper returns `partial`, `blocked`, or `downgraded`, continue with
    the named next action: build a TraceGuard model from saved case material,
    evaluate the model, write gaps back, rerun after case material changes, or
    explicitly scope the case library as saved-but-not-evaluated.

## Boundary

The current TraceGuard case library has one storage boundary: ledgers preserve typed
declarations and provenance; canonical inference receipts are append-only
observations. A later model build never merges receipt outputs back into
caller input.

Keep this chain explicit:

```text
lead/direction -> source lineage and independence group -> evidence role and polarity -> event or explanation declaration -> typed trace/hypothesis/causal candidate -> canonical inference receipt observation -> bounded final claim
```

A source is not evidence by itself. Evidence is not an event by itself. A confirmed event is not a confirmed motive or outcome by itself. A trace is not a final claim by itself.

For every investigation, keep evidence roles explicit:

```text
trigger claim or lead -> primary fact or action -> scope or boundary -> occurrence or implementation evidence -> observed outcome data -> context or motive evidence -> interpretation or commentary -> future hypothesis
```

Context, motive evidence, commentary, or concern should be saved as interpretation unless direct evidence establishes the event, implementation, outcome, or causal link. Scope-limited evidence remains scope-limited unless another source establishes broader reach.

For claims that depend on follow-through, keep the execution chain visible:

```text
announcement or claim -> planned action -> implementation signal -> operating or outcome signal -> stakeholder signal -> counter/delay/non-occurrence signal -> future trigger
```

Do not save only the announcement and later let the case read like execution happened.

For Atlas-driven investigations, save competing storylines and causal
uncertainty as declarations, not inferred results:

```text
storyline id
branch id
storyline claim
supporting evidence ids
opposing evidence ids
alternative explanation relation
confounders or scope limits
causal-chain weakest link
counter-scenario question
declared importance and scope
latest canonical receipt id
next evidence task
```

The case library should preserve red-team storylines and live alternatives instead of smoothing them into the preferred narrative.

## Deep Investigation Handoff

For investigations that will become final artifacts, preserve a compact handoff for each important lead:

```text
lead id
lead question or hypothesis
supporting evidence ids
source registry ids or citation markers when known
Atlas branch ids or debate rows when known
counter or support-limiting evidence ids
execution evidence ids when the lead concerns outcomes
execution-chain status: complete | supported-incomplete | candidate | gap | access-gap | not-supported | not-applicable
competing-storyline status
causal-chain weakest link
counter-scenario question
confounder or scope limit
missing evidence
latest canonical receipt id and projection locator
safe wording draft, clearly marked non-authoritative until projection
unsafe wording risk when overclaim risk is material
target artifact locator such as paragraph, section, page, slide, or report slot when known
source structure unit, destination structure unit, relation to previous, and
trace layer when the lead is a thesis section handoff
next search task
```

The handoff should support later paragraph-level citations and LogicGuard claim audits. If TraceGuard emits duplicate-lead, duplicate-evidence, false-friend, or same-class overclaim review findings, save them as follow-up work instead of silently merging records.

For trace-model-mesh work, also preserve a compact coverage row:

```text
trace id
lead id
trace card ids
event fact status
sequence status
mechanism or causal link status
execution or outcome status when relevant
counter or limiting evidence status
live alternatives
missing evidence roles
access gaps
safe wording
unsafe wording
LogicGuard model-card id when known
SourceGuard trace-gap id when more evidence is needed
```

When a lead concerns a claimed action, rollout, execution, outcome, or causal effect, record checked and missing signals such as actor, action record, timing, scope, affected population, rule or mechanism, implementation owner, observed execution, outcome measure, baseline, and limiting or contrary evidence. These missing signals become search tasks, not silent assumptions.

When final prose is being drafted from a case, preserve which evidence ids support announcement, implementation, outcome, stakeholder, counter/limiting, and future-trigger roles. If a required role is missing, write a SourceGuard search task or a safe downgrade note.

When final thesis or paper prose is being drafted from a case, preserve which
evidence ids support literature progression, method derivation, validation
result, figure/table takeaway, and conclusion transfer. If a review item only
points back to the parent topic and does not progress to a later item or claim,
save that as a handoff gap rather than a completed trace.
The case library preserves investigation and handoff material. The upper-level
writing workflow still owns final thesis-native prose integration and final
placement decisions.

When final prose depends on a preferred conclusion, also preserve the strongest
opposing storyline, live alternatives, and counter-scenario uncertainty so
LogicGuard can run a conclusion tournament.

## Commands

```powershell
researchguard trace library init <library-root> --name "TraceGuard Investigation Memory"
researchguard trace library create-case <library-root> <case-id> --title "<title>"
researchguard trace library add-direction <library-root> <case-id> <direction-id> --title "<title>"
researchguard trace library add-source <library-root> <case-id> <direction-id> --source-id <source-id> --title "<title>" --lineage-id <lineage-id> --independence-group <group-id>
researchguard trace library add-evidence <library-root> <case-id> <direction-id> --evidence-id <evidence-id> --source-id <source-id> --text "<evidence text>"
researchguard trace library list <library-root> --pretty
researchguard trace library search <library-root> <query> --pretty
researchguard trace library build-model <library-root> <case-id> --purpose-contract <task-purpose.json> --output <model.yaml> --pretty
researchguard trace evaluate <model.yaml> --pretty
researchguard trace library write-back-gaps <library-root> <case-id> --result <evaluation.json> --pretty
researchguard trace library validate <library-root> --pretty
```

## Safe Output

When explaining results, say:

```text
The library saved these sources/evidence items under this case and direction.
TraceGuard can now build a bounded storyline model from them.
The current gaps are search tasks, not failed conclusions.
The current lead map shows which explanations are findings, hypotheses, or gaps.
The execution-chain status shows where announcement evidence stops and implementation or outcome evidence begins.
The competing-storyline map shows which explanations remain live and what evidence would distinguish them.
```

Avoid:

```text
The saved sources prove the final story.
The case library already validated the claim.
The event evidence proves the motive or future impact.
The announcement evidence proves execution or outcome.
The preferred storyline can ignore live alternatives.
The saved thesis handoff material is already final prose.
```

## Guard model purpose gate

Before the AI builds or materially changes a TraceGuard model from a case
library, it must first write one target-local task-model-instance purpose
contract. State in plain language what this particular model must prevent and
what remains outside its boundary; select a non-empty one-or-many set of
TraceGuard failure ids; retain one task-local native known-good; and bind
exactly one task-local native known-bad to every selected failure. Pass that
contract through `library build-model --purpose-contract ...`; construction
must block until all selected cases pass their TraceGuard-native oracles.

The files under this skill's own `guard-model/` directory are only the
TraceGuard Library family capability baseline. They prove that the library
skill's native package checks react to their regression cases. They do not
choose the purpose of a model built from a real case library, cannot be copied
as that model's production declaration, and cannot substitute for the
target-local TraceGuard task contract. The generated candidate must retain the
exact task-contract/proof binding so the formal TraceGuard bridge can require
the request, candidate, task contract, one known-good, and every selected
known-bad as the exact target-input set.

This is one fixed `enforced` workflow. There is no routine, functional,
release, highest-quality, quick, advisory, or other selectable closure mode.
TraceGuard and TraceGuard Library define their own failure classes, fixtures,
and native decisions. TraceGuard Library executes and reconciles its declared
checks and exact current inputs without inventing, broadening, weakening, or
reinterpreting library or storyline semantics.

## Native execution-depth receipt gate

Before claiming non-trivial case-library closure, issue
`researchguard trace library-depth PACKAGE.json --output RECEIPT.json` for
target `traceguard.case-library`, owner `traceguard.case-library`, and route
`route:traceguard:case-library`. The package must freeze the selected
library/project/case/direction identity; reconcile every declared, discovered,
required, excluded, and evaluated case, direction, source, evidence item,
event, lead, trace, and gap; and provide the required relationship rows for
each eligible object. It must preserve source-before-evidence,
evidence-before-event/trace, fact-versus-explanation, competing-storyline,
current evaluation, and gap-write-back boundaries. Saving a few records,
relabeling the primary TraceGuard storyline receipt, or copying a catalog into
the evaluated list is shallow and must block. The native library receipt
records this boundary without taking over storyline evaluation or library writes.
Declare a non-empty authoritative `important_object_ids` denominator. An
important or required library object cannot be excluded or reclassified; any
other exclusion needs current hashed evidence, a closed non-contributing or
not-applicable disposition, and no relationship/closure contribution.

An object count, relationship-kind list, catalog expansion, whole-receipt hash,
or ordinal range is not proof of an individual library obligation. Every
satisfied governed object and required relationship must retain its exact
target-native semantic object, `evidence_ref`, and lowercase content hash.
Missing, renamed, overlapping, mechanically generated, or summary-only mappings
block non-trivial library closure.

## Scheduled-production depth closure

For a real use, capability and calibration fixtures are not closure evidence.
Before a non-trivial or depth-dependent library claim, write the target-owned
execution package to
`.traceguard/case-library-scheduled-production.json` under the task target
root. The package must identify this exact skill, `traceguard.library`, and
`route:traceguard:case-library`; carry a target-owned
`scheduled_production_identity` that binds its trigger, execution, current
library scope, and runtime fingerprint; reconcile the complete governed library
object and relationship universe; retain exact per-obligation and per-object
evidence; and reference every supporting target file by safe relative path and
content SHA-256. The current depth check evaluates those files under the current
target-owned run and emits `scheduled_production` evidence. Repository fixtures
remain `fixture_calibration` or source-only capability evidence and can never
close production use.

The production package MUST be created by the target-native scheduled
constructor from the canonical current case-library root and MUST contain
`input_origin=target_native_scheduled_execution`. The adapter independently
re-discovers that root, requires the exact case/direction/source/evidence/event/
trace/gap object and relationship universe to equal the package, resolves the
declared files, recomputes their hashes, and verifies target/run/route semantic
ids and native range anchors. Copying or relabeling calibration data, shrinking
every self-reported universe list together, or supplying generic placeholder
evidence is invalid production evidence.


<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `traceguard`; native owner: `traceguard.template_packs`.
- Current catalogs: `traceguard.template-pack.catalog` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `purpose`.
- Template inventory: `case-library`, `causal`, `competing-storyline`, `counterfactual`, `handoff`, `incident`, `purpose`, `research-lineage`, `technology-progression`.
- Native validator inventory: `traceguard.template_packs.validate_native_payload`.
- Claim boundaries: TraceGuard template instances are non-factual model skeletons; source rows are not evidence, evidence must precede events, events must precede traces, and generated traces are not validated.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->
