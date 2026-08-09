"""Run the researchguard composition kernel checks."""

from __future__ import annotations

import model


def main() -> int:
    model.run_model()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
