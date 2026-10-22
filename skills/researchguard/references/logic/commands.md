# LogicGuard Commands

Use only the installed `researchguard logic` path.

```powershell
researchguard logic validate <model> [--library-root <library>]
researchguard logic evaluate <model>
researchguard logic diagnose <model>
researchguard logic simulate <model> --mode fragility
researchguard logic argument-iteration freeze <baseline> --expected-state <IN|OUT|UNDECIDED> --mode <mode> --root <claim> --node <node> [--protect-claim <claim>] [--holdout-claim <claim>] [--iteration <n> --prior-open-gap-id <gap>] --output <prediction.json>
researchguard logic argument-iteration run <baseline> --prediction <prediction.json> [--candidate <candidate>] --decision <accept|reject> --output <result.json>
researchguard logic gaps <model>
researchguard logic minimal-sets <model> --claim <claim> [--output <sets.json>]
researchguard logic report <model>
researchguard logic outline <model>
researchguard logic structure from-markdown <outline.md> --artifact-kind report --output <model>
researchguard logic structure audit <model>
researchguard logic synthesize <model> --selection-request <selection-request.json> --delivery
researchguard logic depth <model> [--budget <n>] [--output <depth.json>]
researchguard logic import-handoff <traceguard-bundle.yaml> --output <model.yaml>
```

Source-library and viewer commands live in `source-library.md` and `project-library-viewer.md`. Load `h-wadf-quick-reference.md` before creating new node/edge/acceptance structures.

`minimal-sets` classifies dependencies by the edge entering the target claim,
including evidence behind an attacker. A node with support and attack paths is
on the support side. When no support set licenses the claim, `attack.node_ids`
reports the native evaluator's blockers, `reason_code` is `blocked_by_attack`
when blockers exist, and `reason` names their ids and types. This blocker list
is not claimed deletion-minimal. `wording_license` remains `assert`, `qualify`
or `withhold`.
