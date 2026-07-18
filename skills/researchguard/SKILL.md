---
name: researchguard
description: Route a research or investigation request to exactly one ResearchGuard member when the request crosses argument, source-discovery, or evidence-trace boundaries, or when the correct member is genuinely ambiguous. Use LogicGuard directly for argument structure, SourceGuard directly for evidence discovery planning, and TraceGuard directly for temporal or competing-storyline reconstruction.
---

# ResearchGuard

## Purpose

ResearchGuard is the single suite-level entry for three complete member skills:
`logicguard`, `sourceguard`, and `traceguard`. It coordinates them without
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

## Entrypoint Acceptance Map

- `logicguard` intent -> one LogicGuard execution.
- `sourceguard` intent -> one SourceGuard execution.
- `traceguard` intent -> one TraceGuard execution.
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

1. Classify the request by its first required native action.
2. Use `logicguard` for argument structure, warrants, assumptions, rebuttals,
   artifact structure, source-library preservation, model deepening, synthesis,
   or the LogicGuard project-library viewer.
3. Use `sourceguard` for evidence/source discovery plans, source-role gaps,
   retrieval execution, provider evidence, and claim-use qualification.
4. Use `traceguard` for temporal order, competing storylines, event/evidence
   separation, execution chains, counter-scenarios, and bounded causal stories.
5. Use the umbrella only for a genuinely cross-member or ambiguous request.
   Select exactly one member before any member executes:

```powershell
researchguard run --member logicguard -- <member arguments>
researchguard run --member sourceguard -- <member arguments>
researchguard run --member traceguard -- <member arguments>
```

Direct member commands execute the same owner and primary path:

```powershell
researchguard logic <arguments>
researchguard source <arguments>
researchguard trace <arguments>
```

A member may emit a typed `awaiting_owner` handoff. A handoff names the source
request, source member, target member, handoff kind, and payload. It does not
execute the next member. Start one new explicit member request after inspecting
the handoff. Re-entry with an active request id is blocked.

## Hard Gates

- one exact member owns each execution;
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
