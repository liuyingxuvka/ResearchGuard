---
name: traceguard
description: Reconstruct and stress-test evidence-backed temporal traces, competing storylines, execution and effect chains, counter-scenarios, and bounded causal narratives. It does not discover sources or license final arguments.
---

# TraceGuard

## Purpose

TraceGuard owns evidence-trace reconstruction with one general route and one internal case-library route. First declare the trace scope, evidence objects, event/evidence boundary, and live alternatives before inference.

## Entrypoint Scope

TraceGuard owns temporal order, event and evidence separation, execution and effect chains, competing storylines, bounded causal review, contradictions, counter-scenarios, and evidence-backed trace reconstruction. Source discovery and final argument licensing remain typed handoffs to SourceGuard and LogicGuard.

## Route map

- `route:general-trace` → temporal, process, execution, outcome, causal, counter-scenario, or competing-storyline work. Read `references/routes/general-trace.md` and the authoritative `references/unified_inference_protocol.md` only when building or checking the mathematical inference path.
- `route:case-library` → preserve messy case material and search directions before model construction. Read `references/routes/case-library.md`.

The case library is an internal route, not another installed skill.

## Local Material Routing

Read only the reference declared by the selected route. Load the unified inference protocol only when building or checking the mathematical inference path, and load depth, iteration, command, or safe-output references only when their triggers fire.

## Entrypoint Acceptance Map

- Accept `route:general-trace` after the trace scope, evidence objects, event/evidence boundary, and live alternatives are declared.
- Accept `route:case-library` only for preserving messy case material and search directions before model construction.
- Accept inference, depth, iteration, command, or safe-output work only after its trigger-specific reference is loaded.
- If lineage, critical objects, perturbations, or alternatives are missing, return a visible non-closure terminal rather than infer from chronology.

## Conditional depth map

- `trigger:task-iteration`: later evidence or a future event will test a prediction, a model miss appears, or a trace revision is needed → read `references/task-iteration.md`.
- `trigger:depth-closure`: broad, complete, causal, deep, predictive, high-impact, robustness, or competing-storyline wording → read `references/depth-and-closure.md`.
- `trigger:commands-handoffs`: actual CLI execution or SourceGuard/LogicGuard handoff construction → read `references/commands-and-handoffs.md`.
- `trigger:safe-output`: event/explanation/outcome separation, scope transfer, weakest-link, or downgrade wording → read `references/safe-output.md`.

These are loading triggers, not quality modes. Once depth is required, use the same canonical solver, perturbation, lineage, holdout, and native closure gates until closure or a visible non-closure terminal.

## Use When

Use TraceGuard for event/evidence separation, temporal order, incidents, requirements history, research lineage, execution/effect chains, competing storylines, bounded causal review, contradictions, and counter-scenarios.

## Do Not Use When

Do not use TraceGuard to infer causality from chronology, upgrade an announcement into operation or outcome, search for missing sources, license a final argument, invent a future prediction, or retry through heuristic or legacy scoring.

## Required Workflow

1. Freeze the trace scope, target, evidence objects, event/evidence boundary, and live alternatives.
2. Read the selected route reference and every active trigger-specific reference.
3. Reconstruct the trace with the canonical solver, preserve lineage, and separate events, explanations, and outcomes.
4. Run required perturbation, residual, holdout, and contradiction checks; keep scope transfers and live alternatives explicit.
5. Close only at `model_closed_for_task` with current evaluation and depth results, or return the visible terminal and weakest links.
6. Return safe wording, typed handoffs, and the full claim boundary.

## Hard Gates

- Chronology alone cannot establish causality, and announcements cannot be upgraded into operation or outcome.
- Solver failure, unacceptable residuals, missing lineage, unresolved critical objects, ineffective critical perturbations, scope transfer, live alternatives, or unsupported predictive holdout block broad closure.
- A member result cannot silently license a final argument or source claim.

## Native closure

Solver failure, unacceptable residuals, missing lineage, unresolved critical objects, ineffective critical perturbations, scope transfer, live alternatives, or unsupported predictive holdout blocks broad closure. `model_closed_for_task` is the only task-model closure. `progress_stalled`, `iteration_limit`, `external_input_required`, and `scope_excluded` remain visible. A self-report never substitutes for current evaluation and depth results.

## Output Requirements

Return the native result, evidence and claim boundary, blockers and next action.
Include full JSON only when it is needed or requested.
