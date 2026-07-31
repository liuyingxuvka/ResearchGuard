---
name: researchguard
description: Route a research or investigation request to exactly one ResearchGuard member when the request crosses argument, source-discovery, evidence-trace, or experiment-selection boundaries, or when the correct member is genuinely ambiguous. Use LogicGuard for argument structure, SourceGuard for evidence discovery, TraceGuard for temporal reconstruction, and ExperimentGuard for discriminating-test recommendations.
---

# ResearchGuard

## Purpose

ResearchGuard is the single suite-level entry for four complete native member skills:
`logicguard`, `sourceguard`, `traceguard`, and `experimentguard`. It coordinates them without
duplicating their native work or silently trying another member.

## Entrypoint Scope

This umbrella owns suite-level classification and explicit handoff only. Each
member remains a complete direct skill and the sole owner of its native work.

## Local Material Routing

- Read `logicguard` for argument structure, source-library work, artifact
  structure, deepening, synthesis, and project-library inspection.
- Read `sourceguard` for evidence-discovery planning, retrieval, provenance,
  source-role gaps, and claim-use qualification.
- Read `traceguard` for temporal order, competing storylines, execution chains,
  counter-scenarios, and bounded causal narratives.
- Read `experimentguard` for minimum finite experiment sets that distinguish
  caller-declared hypotheses.

## Entrypoint Acceptance Map

- `logicguard` intent -> one LogicGuard execution.
- `sourceguard` intent -> one SourceGuard execution.
- `traceguard` intent -> one TraceGuard execution.
- `experimentguard` intent -> one ExperimentGuard execution.
- genuine ambiguity -> visible blocked result before member execution.
- typed cross-member need -> `awaiting_owner` handoff, never automatic
  execution of another member.

## Use When

Use the umbrella for genuinely cross-member or ambiguous research requests.
Use a member directly when its native owner is already clear.

## Do Not Use When

Do not use the umbrella to retry a failed member, combine member results into a
stronger claim, or create a second implementation of member work.

## Required Workflow

1. Freeze the business intent and exact member arguments, then ask each of the
   four members for its current, member-authored admission evidence over that
   same request fingerprint. Do not infer admission from keywords.
2. Use `logicguard` for argument structure, warrants, assumptions, rebuttals,
   artifact structure, source-library preservation, model deepening, synthesis,
   or the LogicGuard project-library viewer.
3. Use `sourceguard` for evidence/source discovery plans, source-role gaps,
   retrieval execution, provider evidence, and claim-use qualification.
4. Use `traceguard` for temporal order, competing storylines, event/evidence
   separation, execution chains, counter-scenarios, and bounded causal stories.
5. Use `experimentguard` for recommendation-only discriminating experiment
   selection from explicit hypotheses and predicted outcomes.
6. Use the umbrella only for a genuinely cross-member or ambiguous request.
   Supply the exact four-row admission set; the umbrella executes only when
   exactly one current member contract reports `applicable` and all forbidden
   conditions for that member are explicitly absent:

```powershell
researchguard run --business-intent-id <intent-id> --admission-evidence <four-member.json> -- <member arguments>
```

Missing, malformed, stale, zero-match, or many-match admission blocks before
member execution. `--member` is not an umbrella selector and lexical fallback
is not a current route.

## Task-Local Deepening Boundary

When the selected member is used for a non-trivial task, the member—not this
umbrella—owns the iterative model loop. The member freezes task purpose and
coverage, derives predictions and falsifiers, applies native observations, and
returns gap transitions, next actions, and an explicit terminal reason. The
umbrella must preserve the member's native receipt and must not replace it with a self-report
such as "understood" or run a second member to manufacture closure. A result
with open gaps remains open or is visibly stopped as stalled, limited, or
external-input-required; only the selected member can declare its task model
closed.

Direct member commands execute the same owner and primary path:

```powershell
researchguard logic <arguments>
researchguard source <arguments>
researchguard trace <arguments>
researchguard experiment <arguments>
```

A member may emit a typed `awaiting_owner` handoff. A handoff names the source
request, source member, target member, handoff kind, and payload. It does not
execute the next member. Start one new explicit member request after inspecting
the handoff. Re-entry with an active request id is blocked.

## Hard Gates

- one exact member owns each execution;
- the umbrella accepts exactly one member only from current member-authored
  admission evidence bound to the exact request;
- direct and umbrella entry bind to the same native owner;
- ambiguity, recursion, unknown members, and terminal member failure are
  visible blocked results;
- no member result is upgraded by another member;
- no old command, skill id, alias, forwarding shell, or alternate runtime is
  part of the suite.

## Output Requirements

Report the selected member and path, evidence, failures, blockers, skipped checks,
residual risk, any typed handoff, and the claim boundary. A failed,
blocked, ambiguous, recursive, or not-run member remains visible and terminal.
