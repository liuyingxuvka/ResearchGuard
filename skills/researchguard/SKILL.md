---
name: researchguard
description: "Use for research-quality checks: argument structure and claim support, evidence and source discovery, timelines and causal storylines, and the least costly or fewest declared experiments that tell hypotheses apart. Not for writing the finished report, paper, story or guide; use logic-writing."
---

# ResearchGuard

Pick one route, then load only its file. Each route runs its own `researchguard <route>` commands.

| The request | Route file |
|---|---|
| Argument structure, claim support and safe wording; a source library; structured artifacts (papers, reports, decks); deepening a model; synthesis plans; the project library viewer | `references/routes/logic.md` |
| Plan or run evidence and source discovery: source roles, retrieval, provenance, lineage, open gaps, when to stop searching | `references/routes/source.md` |
| Reconstruct and stress-test a timeline, an execution or effect chain, or competing causal storylines from evidence | `references/routes/trace.md` |
| Recommend the least costly or fewest declared experiments that tell hypotheses apart (never runs them) | `references/routes/experiment.md` |

## Rules for every route

- If `researchguard --help` fails, install the engine once with `python -m pip install -e <ResearchGuard checkout>`.
- Several domains: run the routes one after another (usually source, then trace, then logic; experiment when hypotheses and candidate experiments are declared). Pass results with `researchguard source export-traceguard`, `researchguard trace export-logicguard` and `researchguard logic import-handoff`.
- A route's result is only that route's claim; a failed result stays visible and is not retried through another route.
- Return the native result, evidence and claim boundary, blockers and next action; include full JSON only when it is needed or requested.
