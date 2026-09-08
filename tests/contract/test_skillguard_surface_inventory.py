"""Author-only regression gates for current source-to-model reverse closure."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

import pytest

from scripts.author.build_skillguard_surface_inventory import (
    MEMBERS, build_member, load_skillguard, main, semantic_rules,
)
from scripts.build_skillguard_contracts import contract


ROOT = Path(__file__).resolve().parents[2]
# Resolve before the domain tests' autouse fixture isolates USERPROFILE. This
# dependency is private to author maintenance and never enters a consumer skill.
SCANNER = load_skillguard()
SKILLGUARD_ROOT = Path(SCANNER.__file__).resolve().parents[2]


def _copy_member(tmp_path: Path, member: str = "logicguard") -> Path:
    source = ROOT / "skills" / member
    target = tmp_path / "skills" / member
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


# Keep this finite set literal so the FlowGuard test-inventory adapter can
# prove the complete parameter universe without executing pytest discovery.
@pytest.mark.parametrize(
    "member",
    ("experimentguard", "logicguard", "researchguard", "sourceguard", "traceguard"),
)
def test_current_generated_inventory_has_exact_structural_and_semantic_closure(member: str) -> None:
    mapping, inventory = build_member(ROOT, member, SCANNER)
    skill = ROOT / "skills" / member
    assert mapping == json.loads((skill / ".skillguard/surface-semantic-map.json").read_text(encoding="utf-8"))
    assert inventory == json.loads((skill / ".skillguard/surface-inventory.json").read_text(encoding="utf-8"))
    actual = SCANNER.discover_full_source_surfaces(skill)
    rows = {row["surface_id"]: row for row in inventory["full_surfaces"]}
    for surface in actual.surfaces:
        # Structural function/route identities must not be replaced with the
        # compact native route to make a shape-only inventory appear complete.
        assert all(rows[surface.surface_id][key] == value for key, value in surface.to_dict().items())
    for obligation in mapping["obligation_bindings"]:
        assert set(obligation["surface_ids"]) == {
            row["surface_id"] for row in inventory["full_surfaces"]
            if obligation["obligation_id"] in row["model_obligation_ids"]
        }
    declared = contract(member)["depth_profile"]
    assert declared["surface_inventory"]["model_deepening_check_id"] == declared["model_deepening_check_id"]
    assert set(declared["surface_inventory"]["adequacy_check_ids"]) == set(declared["native_check_ids"])
    assert all(rule["source_paths"] for rule in semantic_rules(member))


def test_unknown_source_path_requires_an_explicit_author_decision(tmp_path: Path) -> None:
    skill = _copy_member(tmp_path)
    (skill / "references/unreviewed-route.md").write_text("A newly added route with no assigned obligation.", encoding="utf-8")
    with pytest.raises(ValueError, match="no reviewed semantic decision.*unreviewed-route"):
        build_member(tmp_path, "logicguard", SCANNER)


def test_new_model_obligation_cannot_be_hidden_by_complete_contract_rule(tmp_path: Path) -> None:
    skill = _copy_member(tmp_path)
    path = skill / ".skillguard/compiled-contract.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["obligations"].append({"obligation_id": "obligation:researchguard:logicguard:unreviewed", "required_check_ids": ["check:logicguard:native-tests"]})
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="compiled obligation denominator differs"):
        build_member(tmp_path, "logicguard", SCANNER)


def test_removed_source_requires_a_reviewed_disposition(tmp_path: Path) -> None:
    skill = _copy_member(tmp_path)
    (skill / "references/commands.md").unlink()
    with pytest.raises(ValueError, match="reviewed source paths disappeared"):
        build_member(tmp_path, "logicguard", SCANNER)


def test_source_edit_invalidates_sealed_inventory(tmp_path: Path) -> None:
    skill = _copy_member(tmp_path)
    _, inventory = build_member(tmp_path, "logicguard", SCANNER)
    with (skill / "SKILL.md").open("a", encoding="utf-8") as stream:
        stream.write("\nChanged consumer instruction.\n")
    findings = SCANNER.validate_full_surface_inventory(inventory, target_root=skill)
    assert findings, "source edits must invalidate old source observations"
    with pytest.raises(ValueError, match="stale or missing"):
        main(["--root", str(tmp_path), "--member", "logicguard", "--skillguard-root", str(SKILLGUARD_ROOT), "--check"])


def test_resealing_a_removed_surface_does_not_shrink_the_denominator() -> None:
    _, original = build_member(ROOT, "logicguard", SCANNER)
    payload = copy.deepcopy(original)
    removed = payload["full_surfaces"].pop()
    payload["full_surface_ids"].remove(removed["surface_id"])
    for obligation in payload["model_obligations"]:
        if removed["surface_id"] in obligation["surface_ids"]:
            obligation["surface_ids"].remove(removed["surface_id"])
    payload["inventory_hash"] = SCANNER.surface_inventory_hash(payload)
    findings = SCANNER.validate_full_surface_inventory(payload, target_root=ROOT / "skills/logicguard")
    assert findings, "a resealed co-shrink must fail independent source discovery"


def test_wrong_structural_route_and_missing_native_deepening_are_rejected() -> None:
    _, payload = build_member(ROOT, "logicguard", SCANNER)
    payload["full_surfaces"][0]["route_id"] = "route:researchguard:logicguard"
    payload["full_surfaces"][0]["adequacy_check_ids"] = ["check:logicguard:consumer-contract"]
    payload["inventory_hash"] = SCANNER.surface_inventory_hash(payload)
    findings = SCANNER.validate_full_surface_inventory(
        payload, target_root=ROOT / "skills/logicguard",
        native_check_ids=contract("logicguard")["depth_profile"]["native_check_ids"],
        model_deepening_check_id="check:logicguard:task-model-closure",
    )
    codes = {finding.code for finding in findings}
    assert any(finding.code == "full_surface_binding_mismatch" and finding.path.endswith(".route_id") for finding in findings)
    assert any("adequacy" in code or "deepening" in code for code in codes)
