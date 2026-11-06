# ResearchGuard maintenance

Every completed action is committed and pushed to main. A release records the
exact tested commit.

Releases:

- Version numbers: a release that adds features raises the second number (0.6.0 -> 0.7.0); a release with only small fixes raises the third (0.7.0 -> 0.7.1); never skip a number.
- Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project). Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

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
Run the affected tests during development. For the final source run the complete native pytest suite
and `python -m flowguard check --all`; require complete CI on the exact main commit being published.
Retain the original inputs and real assertions when migrating a contract. A static owner list does
not prove execution order, and a grey boundary does not become a passing claim.

Each member keeps its native task and authority. Repair technical defects and model/code disagreement;
use the stored owner words to resolve a genuine incompatible requirement rather than inventing a waiver.
