from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from researchguard.source.schema import Gap, SchemaError


ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard")
RETIRED_SKILL_IDS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)


def test_consumer_skill_inventory_and_metadata_are_exact() -> None:
    assert sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir()) == sorted(
        MEMBERS
    )
    for member in MEMBERS:
        skill_root = ROOT / "skills" / member
        frontmatter = skill_root.joinpath("SKILL.md").read_text(encoding="utf-8").split(
            "---", 2
        )[1]
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == member
        interface = yaml.safe_load(
            skill_root.joinpath("agents/openai.yaml").read_text(encoding="utf-8")
        )
        assert interface["interface"]["display_name"]
        assert interface["interface"]["short_description"]
        assert f"${member}" in interface["interface"]["default_prompt"]


def test_internal_route_inventory_is_exact() -> None:
    logic_routes = {
        path.name
        for path in (ROOT / "skills/logicguard/references/routes").glob("*.md")
    }
    assert logic_routes == {
        "source-library.md",
        "structured-artifact.md",
        "model-deepening.md",
        "artifact-synthesis.md",
        "project-library-viewer.md",
    }
    assert (
        ROOT / "skills/traceguard/references/routes/case-library.md"
    ).is_file()


def test_consumer_projection_has_no_retired_skill_or_launcher() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "skills").rglob("*")
        if path.is_file()
        and ".skillguard" not in path.parts
        and path.suffix.lower() in {".md", ".py", ".yaml", ".yml"}
    )
    assert not any(skill_id in text for skill_id in RETIRED_SKILL_IDS)
    assert "python -m logicguard" not in text
    assert "python -m sourceguard" not in text
    assert "python -m traceguard" not in text
    assert "run_logicguard.py" not in text
    assert "run_sourceguard.py" not in text
    assert "run_traceguard.py" not in text


def test_author_contracts_form_one_four_member_unit() -> None:
    for member in MEMBERS:
        payload = json.loads(
            (
                ROOT
                / "skills"
                / member
                / ".skillguard"
                / "contract-source.json"
            ).read_text(encoding="utf-8")
        )
        assert payload["maintenance_unit_id"] == "unit:researchguard-suite"
        assert payload["member_skill_ids"] == list(MEMBERS)
        assert payload["skill_id"] == member
        assert payload["integration_mode"] == "native-integrated"
        assert payload["may_define_skillguard_runtime_route"] is False


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
    for command in ("logic", "source", "trace"):
        result = subprocess.run(
            [sys.executable, "-m", "researchguard", command, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
