"""ResearchGuard public package."""

from __future__ import annotations

__version__ = "0.5.16"

SUITE_ID = "researchguard-suite"
MEMBER_IDS = ("logicguard", "sourceguard", "traceguard", "experimentguard")

__all__ = ["MEMBER_IDS", "SUITE_ID", "__version__"]
