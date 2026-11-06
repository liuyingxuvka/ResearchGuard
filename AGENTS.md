# ResearchGuard maintenance

Every completed action is committed and pushed to main. A release records the
exact tested commit.

Releases:

Version numbers are independent for each project; use the same MAJOR.MINOR.PATCH rules:

- At 1.0 and later, incompatible changes to a supported public CLI, skill id, SDK or saved input format raise MAJOR; backward-compatible features raise MINOR; corrections within the existing contract raise PATCH. Internal code volume or a dependency's version is not a version criterion. Never skip a number.
- Before 1.0, keep the unstable status explicit: incompatible public changes raise MINOR and describe migration. Publish 1.0 when declaring a stable contract, not merely because the implementation changed.
- A format consumed by a documented command remains a contract even when generated. Distinguish it from disposable caches. A new required field or changed supported meaning needs a compatibility decision; do not silently reinterpret old material.
- For a changed public surface, retain a small existing valid example and a real counterexample. Explain a corrected old bug separately from a new requirement. Give rejected old material a rebuild path from original inputs; never invent verified results, source digests or evidence fields to make it load.
- Record the release classification and migration in the existing CHANGELOG. Preserve historical commits, tags and releases; append corrections instead of renumbering them. Changes limited to repository policy or maintenance tooling do not by themselves require a product release. Raise a maintenance dependency only for a capability actually used or an evidenced correctness fix required by that workflow, not merely because a new tag exists.

Public saved inputs include documented research/member models, original captures and their source references. Saved status and experiment results keep their stated evidence and conditional scope; they do not become newly observed facts after an upgrade.
- Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project). Raise that tag only when this repository uses a newer FlowGuard capability or needs a demonstrated correctness fix in its maintenance workflow; a FlowGuard release alone is no reason to change it or to release this repository.

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->

## Maintenance evidence

Store only the actual owner's words, byte for byte; never an AI plan, and never edit `.flowguard/requests/`.
Change production code and its tests together. Add `Request: R<id>` when the commit answers stored words.
Run the affected tests during development. Before a product release freeze the source and run the complete
native suite once through `python -m flowguard check --all`, using an environment outside the project;
this command includes pytest. Require complete CI on the exact main commit being published.
Retain the original inputs and real assertions when migrating a contract. A static owner list does
not prove execution order, and a grey boundary does not become a passing claim.

Each member keeps its native task and authority. Repair technical defects and model/code disagreement;
use the stored owner words to resolve a genuine incompatible requirement rather than inventing a waiver.
