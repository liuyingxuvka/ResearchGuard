# LogicGuard Commands

Use only the installed `researchguard logic` path.

```powershell
researchguard logic validate <model>
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

Source-library and viewer commands live in `routes/source-library.md` and `routes/project-library-viewer.md`. Load `h-wadf-quick-reference.md` before creating new node/edge/acceptance structures.
