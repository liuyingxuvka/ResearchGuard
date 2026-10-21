from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from researchguard.source.schema import Gap, SchemaError


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "researchguard"
ROUTES = ("logic", "source", "trace", "experiment")


def test_one_skill_with_a_route_table_and_a_short_description() -> None:
    assert sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir()) == ["researchguard"]
    text = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == "researchguard"
    assert len(metadata["description"]) <= 300
    assert re.fullmatch(r"Use for .+\. Not for .+; use [a-z-]+\.", metadata["description"])
    for route in ROUTES:
        assert f"`references/routes/{route}.md`" in text
    interface = yaml.safe_load(SKILL.joinpath("agents/openai.yaml").read_text(encoding="utf-8"))
    assert interface["interface"]["display_name"] == "ResearchGuard"
    assert "$researchguard" in interface["interface"]["default_prompt"]


def test_route_and_reference_inventory_is_exact() -> None:
    assert sorted(path.name for path in (SKILL / "references" / "routes").glob("*.md")) == sorted(
        f"{route}.md" for route in ROUTES
    )
    logic = {path.name for path in (SKILL / "references" / "logic").glob("*.md")}
    assert {
        "source-library.md",
        "structured-artifact.md",
        "model-deepening.md",
        "artifact-synthesis.md",
        "project-library-viewer.md",
    } <= logic
    assert (SKILL / "references" / "trace" / "case-library.md").is_file()
    for route in ROUTES:
        assert not (SKILL / "references" / "routes" / f"{route}.md").read_text(encoding="utf-8").startswith("---")


def test_sourceguard_rejects_retired_gap_projection() -> None:
    assert "status" not in Gap.__dataclass_fields__
    with pytest.raises(SchemaError, match="gap.status is retired"):
        Gap.from_dict(
            {
                "gap_id": "old",
                "gap_type": "unknown",
                "status": "open",
                "semantic_state": "discovered",
            }
        )


def test_current_commands_are_callable() -> None:
    for command in ("logic", "source", "trace", "experiment"):
        result = subprocess.run(
            [sys.executable, "-m", "researchguard", command, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
