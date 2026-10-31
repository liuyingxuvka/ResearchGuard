---
name: researchguard
description: "Use for research-quality checks: argument structure and claim support, evidence and source discovery, timelines and causal storylines, and the least costly or fewest declared experiments that tell hypotheses apart; also before you state a causal or evidential conclusion in an answer (if a research folder exists, read its status first). Not for writing the finished report, paper, story or guide; use logic-writing."
---

# ResearchGuard

## Start from the model

Quick check before a conclusion:
- A research folder exists: run `researchguard status <folder>` and read Verdict before you answer.
- No folder: name the claim and its sources; if a source is missing, say so instead of asserting.
- New evidence in a folder listing a source model: `researchguard source add-anchor`, then `researchguard sync <folder>`, then `researchguard status <current> --candidate <folder>`.

- Existing folder: run `researchguard status <folder>` first; read Verdict, Open gaps and Next; take the route Next names.
- New question: write `research.yaml` first (template: `references/research-tree.md`, "Start a question"); each route's first step builds its model, listed in `models`.
- After each route step run `status` again; discuss hypotheses, anchors and the verdict.
- Keep the source, trace, logic and experiment models as separate route models joined by shared ids, add only the routes and hypotheses the question needs, and read one hypothesis with status --hypothesis <id>.

## Choose a route

Pick one route and load only its file.

| Work | Route file |
|---|---|
| Arguments, safe wording, source library, artifact audits and argument plans | `references/routes/logic.md` |
| Source discovery, provenance, gaps and search stop decisions | `references/routes/source.md` |
| Timelines, causal storylines and competing explanations | `references/routes/trace.md` |
| Minimum distinguishing experiments; never executes them | `references/routes/experiment.md` |

- Node: a hypothesis in `research.yaml`; `status <folder> --hypothesis <id>` shows its route states, directed evidence, ablations, gaps and next actions, and a failing one shows the route result, copied field or anchor that disagrees.
- Parent: the question in `research.yaml`; the source, trace, logic and experiment models are its parts, joined by shared ids.
- Known-bad: `ablations:` in `research.yaml` (remove anchors, expect weaken or eliminate); each one must be caught, else `status` reports `ablation_not_caught`.
- Real binding: anchors owned by the source model; trace and logic copies are checked (`copy_drift`) and refreshed by `--into` syncs. In research folders that list a source model, add new source evidence with researchguard source add-anchor, then researchguard sync to keep the trace and logic copies aligned.
- Test binding: predict-observe-revise loops and experiment observations.
- Readback: `researchguard status <folder>` (verdict first; `--hypothesis <id>` for one node; `--json`).
- Current vs target: the research folder is the current model; a candidate copy is the target: `researchguard sync <copy>` brings new anchors into the copy, compare with `status <folder> --candidate <copy>`, and replace the folder with it when accepted.

## Rules for every route

- Missing engine: `python -m pip install -e <ResearchGuard checkout>`.
- Folder questions (`trigger:research-tree`): load `references/research-tree.md`.
- A failed route stays failed; another route cannot replace its result.
- Return native findings, evidence boundary, blockers and next action.
