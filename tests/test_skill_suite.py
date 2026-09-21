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
MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
RETIRED_SKILL_IDS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)
BLUEPRINT_REFERENCES = {
    "researchguard": "references/member-model-envelope.md",
    "logicguard": "references/domain-blueprint-contract.md",
    "sourceguard": "references/information-blueprint.md",
    "traceguard": "references/trace-blueprint-contract.md",
    "experimentguard": "references/experiment-model-protocol.md",
}

SKILLGUARD_REQUIRED_SECTIONS = (
    "Purpose",
    "Entrypoint Scope",
    "Local Material Routing",
    "Entrypoint Acceptance Map",
    "Use When",
    "Do Not Use When",
    "Required Workflow",
    "Hard Gates",
    "Output Requirements",
)

SKILLGUARD_OUTPUT_TERMS = (
    "evidence",
    "failures",
    "blockers",
    "skipped_checks",
    "residual_risk",
    "claim_boundary",
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


def test_managed_skill_entrypoints_have_current_operational_sections() -> None:
    for member in MEMBERS:
        text = (ROOT / "skills" / member / "SKILL.md").read_text(encoding="utf-8")
        headings = set(re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
        assert set(SKILLGUARD_REQUIRED_SECTIONS) <= headings, member
        lowered = text.casefold()
        assert all(term.casefold() in lowered for term in SKILLGUARD_OUTPUT_TERMS), member


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


def test_author_contracts_form_one_five_surface_unit() -> None:
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
        assert payload["schema_version"] == "skillguard.contract_source.v2"
        assert payload["repository_role"] == "skill_maintainer_source"
        assert payload["native_route_owner"] == f"owner:researchguard:{member}"
        assert payload["may_define_parallel_execution_route"] is False
        assert payload["may_define_skillguard_runtime_route"] is False
        assert payload["native_route_bindings"] == [
            {
                "binding_id": f"native:researchguard:{member}",
                "native_route_id": f"route:researchguard:{member}",
                "required_before_closure": True,
                "source": f"skills/{member}/SKILL.md",
            }
        ]


def test_member_domain_dna_and_repository_software_dna_stay_separate() -> None:
    eager_detail_terms = (
        "seven software-DNA readiness layers",
        "repository denominator",
        "canonical self-DNA export",
        "architecture reduction",
    )
    for member, reference in BLUEPRINT_REFERENCES.items():
        skill_root = ROOT / "skills" / member
        skill_text = skill_root.joinpath("SKILL.md").read_text(encoding="utf-8")
        agent_text = skill_root.joinpath("agents/openai.yaml").read_text(
            encoding="utf-8"
        )
        reference_text = skill_root.joinpath(reference).read_text(encoding="utf-8")
        for entry_text in (skill_text, agent_text):
            assert "member-domain dna" in entry_text.casefold()
            assert "ResearchGuard repository software-DNA root" in entry_text
            assert "FlowGuard-owned" in entry_text
            assert not any(term in entry_text for term in eager_detail_terms)
        assert "member-domain DNA" in reference_text
        assert "ResearchGuard repository software-DNA root" in reference_text
        assert "FlowGuard-owned" in reference_text
        if member == "researchguard":
            assert "composition transport" in reference_text
        else:
            assert "not a whole-repository software blueprint" in reference_text


def test_member_domain_dna_entrypoints_preserve_external_authority_boundary() -> None:
    reference_paths = {
        member: [reference]
        for member, reference in BLUEPRINT_REFERENCES.items()
    }
    reference_paths["researchguard"].append("references/external-domain-dna.md")

    for member, references in reference_paths.items():
        skill_root = ROOT / "skills" / member
        entry_text = "\n".join(
            (
                skill_root.joinpath("SKILL.md").read_text(encoding="utf-8"),
                skill_root.joinpath("agents/openai.yaml").read_text(
                    encoding="utf-8"
                ),
            )
        ).casefold()
        for term in (
            "external",
            "admission",
            "native",
            "persistent",
            "immutable",
            "cache",
            "unverified",
            "different target",
            "separate anchor",
            "generic",
            "issuer",
            "inline candidate-authoring",
        ):
            assert term in entry_text, (member, term)

        for reference in references:
            reference_text = skill_root.joinpath(reference).read_text(
                encoding="utf-8"
            ).casefold()
            for term in (
                "external",
                "admission",
                "native",
                "persistent",
                "immutable",
                "cache",
                "unverified",
                "different target",
                "generic",
                "issuer",
                "inline candidate-authoring",
                "exactly one",
                "replay",
            ):
                assert term in reference_text, (member, reference, term)


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
