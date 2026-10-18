# ResearchGuard maintenance

Use the current FlowGuard 0.70.6 living map in `.flowguard/map.json`.
Read the affected component before changing its owned code. Preserve the native
model/code/test bindings in `models/software_dna/researchguard.json`.
After a change, update affected descriptions and anchors, run the existing
focused native tests and relevant executable model, and confirm affected map
components. Run one complete pytest gate only after the release source freezes.

`researchguard self-dna check` checks current map and native DNA bindings; it
reports model execution separately and does not treat static readiness as an
executed proof. `.flowguard/models/authority/`, evidence and historical adoption
logs are immutable past evidence, not current runtime prerequisites.

Every completed action is committed and pushed to main. A release increments
only the patch version and records the exact tested commit.
