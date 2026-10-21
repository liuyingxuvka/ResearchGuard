# LogicGuard Commands

Use only the installed `researchguard logic` path.

```powershell
researchguard logic validate <model>
researchguard logic evaluate <model>
researchguard logic diagnose <model>
researchguard logic simulate <model> --mode fragility
researchguard logic gaps <model>
researchguard logic report <model>
researchguard logic outline <model>
researchguard logic structure from-markdown <outline.md> --artifact-kind report --output <model>
researchguard logic structure audit <model>
researchguard logic synthesize <model> --selection-request <selection-request.json> --delivery
researchguard logic depth <model> [--budget <n>] [--output <depth.json>]
researchguard logic import-handoff <traceguard-bundle.yaml> --output <model.yaml>
researchguard logic argument-iteration freeze <baseline> --expected-state <IN|OUT|UNDECIDED> --mode <mode> --root <claim> --node <node> --protect-claim <claim> --task-id <task> --purpose <purpose> --coverage-id <claim> --iteration 0 --max-iterations 4 --holdout-claim <holdout-claim> --output <prediction.json>
researchguard logic argument-iteration run <baseline> --prediction <prediction.json> --candidate <candidate> --store-root <store> --decision <accept|reject> --output <receipt.json>
researchguard logic argument-iteration rollback --store-root <store> --model-id <model-id> --source-revision <accepted-revision> --output <receipt.json>
```

Source-library and viewer commands live in `routes/source-library.md` and `routes/project-library-viewer.md`. Load `h-wadf-quick-reference.md` before creating new node/edge/acceptance structures.
