# ResearchGuard maintenance

Use the FlowGuard living map in `.flowguard/map.json`. Maintenance needs
FlowGuard >= 0.70.6 (`pip install -e <FlowGuard checkout>`).
Read the affected component before changing its owned code.
After a change, update affected descriptions and anchors, run the existing
focused native tests and relevant executable model, and confirm affected map
components. Run one complete pytest gate only after the release source freezes.

Use `python -m flowguard change` after edits and `python -m flowguard release`
before a release.

Every completed action is committed and pushed to main. A release increments
only the patch version and records the exact tested commit.
