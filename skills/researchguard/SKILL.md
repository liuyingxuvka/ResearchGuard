---
name: researchguard
description: "Use for research-quality checks: argument structure and claim support, evidence and source discovery, timelines and causal storylines, and the least costly or fewest declared experiments that tell hypotheses apart. Not for writing the finished report, paper, story or guide; use logic-writing."
---

# ResearchGuard

Pick one route and load only its file; each keeps its native commands and claim boundary.

| Work | Route file |
|---|---|
| Arguments, safe wording, source library, artifact audits and argument plans | `references/routes/logic.md` |
| Source discovery, provenance, gaps and search stop decisions | `references/routes/source.md` |
| Timelines, causal storylines and competing explanations | `references/routes/trace.md` |
| Minimum distinguishing experiments; never executes them | `references/routes/experiment.md` |

- Node: a hypothesis in `research.yaml`; a failing hypothesis shows its counterexample: the route result, copied field or anchor that disagrees.
- Parent: the question in `research.yaml`; the source, trace, logic and experiment models are its parts, joined by shared ids.
- Known-bad: `ablations:` in `research.yaml` (remove anchors, expect weaken or eliminate); each one must be caught, else `status` reports `ablation_not_caught`.
- Real binding: anchors owned by the source model; trace and logic copies are checked (`copy_drift`) and refreshed by `--into` syncs.
- Test binding: predict-observe-revise loops and experiment observations.
- Readback: `researchguard status <folder>` (verdict first; `--json`).
- Current vs target: the research folder is the current model; a candidate folder is the target and replaces it when accepted; `status <folder> --candidate <folder2>` shows before and after.

## Rules for every route

- Missing engine: `python -m pip install -e <ResearchGuard checkout>`.
- Cross-route question (`trigger:research-tree`): load `references/research-tree.md`.
- A failed route stays failed; another route cannot replace its result.
- Return native findings, evidence boundary, blockers and next action. Full JSON only as needed.
