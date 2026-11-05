# ResearchGuard maintenance

Every completed action is committed and pushed to main. A release records the
exact tested commit.

Releases:

- Version numbers: a release that adds features raises the second number (0.6.0 -> 0.7.0); a release with only small fixes raises the third (0.7.0 -> 0.7.1); never skip a number.
- Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project). Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result, plus any inherited technical work still open.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request.

5. Before changing state values, actions, conditions, settings or endings, update the affected `.flowguard/flow/` model first; run `python -m flowguard check`. For code claims, follow the installed `flowguard/flow/HOWTO.md` and bind only the affected actions to real public calls. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path. Keep purely functional contracts in direct production tests.
6. Run the complete native test suite and `python -m flowguard release` for the final source; CI also checks Windows boundaries and builds the distribution. The test extra pins FlowGuard v1.0.0 for this migrated workflow.

If conflicts remain in a reply, end with “需要你决定” and the relevant question and stored owner words. Repair dead ends and unreachable behavior in code; model/code drift needs reconciliation. A provisional decision applies only to eligible contradictory requested obligations; it does not settle these defects.
