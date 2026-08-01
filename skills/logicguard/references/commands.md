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
researchguard logic synthesize <model> --goal <goal> --delivery
researchguard logic depth <model> --output <receipt.json>
researchguard logic argument-iteration freeze <baseline> --expected-state <IN|OUT|UNDECIDED> --mode <mode> --root <claim> --node <node> --protect-claim <claim> --output <prediction.json>
researchguard logic argument-iteration run <baseline> --prediction <prediction.json> --candidate <candidate> --store-root <store> --decision <accept|reject> --output <receipt.json>
researchguard logic argument-iteration rollback <accepted-revision> --store-root <store> --output <receipt.json>
```

Source-library and viewer commands live in `routes/source-library.md` and `routes/project-library-viewer.md`. Load `h-wadf-quick-reference.md` before creating new node/edge/acceptance structures.
