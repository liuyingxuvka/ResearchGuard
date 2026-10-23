# Internal LogicGuard route: project-library-viewer

This is an internal LogicGuard route for the desktop source-library viewer and its headless payload checks. Use it when the task is to inspect what is already in a LogicGuard library or move source-library packages through the viewer-safe I/O path.

Use the installed viewer entrypoint or module entrypoint:

```powershell
researchguard logic library viewer --library-root <root> --check
```

## Workflow

1. Treat card and graph inspection as read-only. The viewer does not edit source text, models, or graph nodes.
2. For opening the UI, run a headless check first when practical: `researchguard logic library viewer --library-root <root> --check`.
3. Use project-oriented navigation as the primary axis. Secondary filters are all sources, recent, source type, modeling status, and uncategorized.
4. Source card details should show temporal clues when available: accession time, source date, and covered period. Missing clues remain unmarked; the viewer should not force editing.
5. Package import/export uses the LogicGuard safe package I/O layer. Inspect unknown packages and dry-run before real imports.
6. Project dissolve removes project relationships only; it must preserve source files, source models, and global source records.
7. Keep the local version/status capsule visible and do not reintroduce organization-maintenance controls.
8. When explaining a non-trivial viewer inspection, package route, or source-to-project path in chat, use a compact AI-selected Mermaid diagram or table if the UI graph or headless JSON alone would not make the route clear. First identify the relationship: argument support, research process, document structure, source path, project reference, gap diagnosis, or comparison. The viewer itself renders only the single recommended graph; it does not expose graph-mode tabs. Skip extra chat diagrams when the viewer's own graph is the clearer artifact.

## Boundaries

- Use `route:source-library` when the task is importing, deepening, searching, or linking sources without needing the viewer.
- Use `route:structured-artifact` or `route:artifact-synthesis` when the user wants artifact reasoning rather than library inspection.
- Do not convert the viewer into a source/model editor.
- Viewer graph choices are LogicGuard-specific and must not require FlowGuard rules or a shared cross-family diagram protocol.

## Common Commands

```powershell
researchguard logic library viewer --library-root .logicguard-library --check --language en
researchguard logic library viewer --library-root .logicguard-library --language zh-CN
researchguard logic library view-snapshot .logicguard-library
researchguard logic library view-graph .logicguard-library <source-id>
researchguard logic library export-package .logicguard-library project.zip --project <project-id>
researchguard logic library import-package .logicguard-library project.zip --dry-run
```

## Native completion and stopping

1. Select the real library root and project/source scope; check path and package identity.
2. Call view-snapshot/view-graph or open the existing viewer. Use native package import/export only when requested.
3. Report the visible project/graph and actual operation status. Inspection ends here.

Stop when the selected view is available or report the actual I/O or identity error.


The optional desktop viewer requires the `viewer` extra
(`python -m pip install -e ".[viewer]"`) and Python with tkinter.
Core argument, source, trace and experiment commands do not require Pillow.
