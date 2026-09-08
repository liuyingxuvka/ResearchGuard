"""Build the five target-owned author inventories from reviewed source rules.

This author tool uses SkillGuard's public structural scanner. The semantic
decisions below belong to ResearchGuard; a new path or model obligation blocks
generation until its actual responsibility has been declared here. Consumer
skills neither import this module nor need SkillGuard installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard")
DEPTH_REFERENCES = {
    "logicguard": "broad-depth-and-closure.md domain-blueprint-contract.md routes/model-deepening.md routes/source-library.md routes/structured-artifact.md structural-contribution.md task-model-maturation.md validated-template-pack.md",
    "sourceguard": "broad-depth-and-closure.md information-blueprint.md retrieval-workflow.md source-model-protocol.md task-iteration.md validated-template-pack.md",
    "traceguard": "depth-and-closure.md task-iteration.md trace-blueprint-contract.md unified_inference_protocol.md validated-template-pack.md",
    "experimentguard": "experiment-model-protocol.md",
    "researchguard": "external-domain-dna.md member-admission-index.md member-model-envelope.md",
}
OTHER_REFERENCES = {
    "logicguard": "citation-grounding.md commands.md general-argument.md h-wadf-quick-reference.md routes/artifact-synthesis.md routes/project-library-viewer.md",
    "sourceguard": "commands.md safe-output.md",
    "traceguard": "commands-and-handoffs.md routes/case-library.md routes/general-trace.md safe-output.md",
    "experimentguard": "",
    "researchguard": "",
}
CLAIM_BOUNDARY = (
    "The declared member skill root is the source-discovery boundary. Its native "
    "package is separately bound by the contract's implementation paths and check "
    "inputs. This author map proves neither native check execution nor domain "
    "correctness, installation, release, or future AI behavior."
)


def load_skillguard(explicit_root: Path | None = None) -> Any:
    """Resolve an explicit author dependency without a consumer fallback."""
    root = explicit_root or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "skillguard"
    scripts = root.resolve() / "scripts"
    if not (scripts / "skillguard_v2" / "surface_inventory.py").is_file():
        raise ValueError("author SkillGuard installation missing; supply --skillguard-root")
    sys.path.insert(0, str(scripts))
    from skillguard_v2 import surface_inventory
    return surface_inventory


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(payload: dict[str, Any]) -> str:
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def semantic_rules(member: str) -> list[dict[str, Any]]:
    prefix = f"obligation:researchguard:{member}:"
    normal = [prefix + kind for kind in ("consumer-contract", "prompt-load", "native-tests", "task-model-closure")]
    declared = normal + ([prefix + "consumer-install-transaction"] if member == "researchguard" else [])
    depth = {"references/" + p for p in DEPTH_REFERENCES[member].split()}
    other = {"references/" + p for p in OTHER_REFERENCES[member].split()}
    scripts = {f"scripts/{member}_closure_check.py"} if member in {"logicguard", "sourceguard", "traceguard"} else set()
    if member == "traceguard":
        scripts.add("scripts/traceguard_library_closure_check.py")
    decisions = (
        ("complete-target-declaration", declared, {".skillguard/contract-source.json"},
         "The exact target contract declares every current member obligation, including the umbrella installation transaction where applicable."),
        ("consumer-prompt", [prefix + "consumer-contract", prefix + "prompt-load"], {"SKILL.md", "agents/openai.yaml"} | depth | other,
         "These explicit consumer entry and reference files define the member boundary and its selected prompt loading."),
        ("native-closure-boundary", [prefix + "task-model-closure", prefix + "native-tests"], depth | scripts,
         "These explicit protocol references and closure adapters describe or execute native model closure; native target tests own its meaning."),
    )
    return [{"rule_id": f"decision:{member}:{name}", "model_obligation_ids": sorted(ids),
             "source_paths": sorted(paths), "reason": reason,
             "proof_ref": ".skillguard/contract-source.json#closure_profiles"}
            for name, ids, paths, reason in decisions]


def build_member(repository_root: Path, member: str, scanner: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if member not in MEMBERS:
        raise ValueError(f"unknown maintained member: {member}")
    skill = repository_root.resolve() / "skills" / member
    source = _read(skill / ".skillguard/contract-source.json")
    compiled = _read(skill / ".skillguard/compiled-contract.json")
    checks = {item["check_id"]: item for item in source["checks"]}
    obligations = {item["obligation_id"]: item for item in compiled["obligations"]}
    rules = semantic_rules(member)
    reviewed_ids = {oid for rule in rules for oid in rule["model_obligation_ids"]}
    if set(obligations) != reviewed_ids:
        raise ValueError(f"{member}: compiled obligation denominator differs from reviewed decisions")
    if set(source["closure_profiles"][0]["required_obligation_ids"]) != reviewed_ids:
        raise ValueError(f"{member}: source and compiled obligation denominators differ")
    depth = source["depth_profile"]
    deepening = depth["model_deepening_check_id"]
    if deepening != f"check:{member}:task-model-closure" or set(depth["native_check_ids"]) != set(checks):
        raise ValueError(f"{member}: native check or model-deepening identity changed")
    route_id = f"route:researchguard:{member}"
    if depth["native_route_ids"] != [route_id]:
        raise ValueError(f"{member}: native route identity changed")
    owner_id = depth["native_owner_id"]
    scan = scanner.discover_full_source_surfaces(skill)
    if scan.findings:
        raise ValueError(f"{member}: unclean source discovery: {[r.to_dict() for r in scan.findings]}")
    reviewed_paths = {path for rule in rules for path in rule["source_paths"]}
    missing_paths = reviewed_paths - set(scan.source_paths)
    if missing_paths:
        raise ValueError(f"{member}: reviewed source paths disappeared: {sorted(missing_paths)}")
    surfaces = sorted(scan.surfaces, key=lambda item: item.surface_id)
    rows: list[dict[str, Any]] = []
    row_rules: dict[str, set[str]] = {}
    for surface in surfaces:
        matching = [rule for rule in rules if surface.source_path in rule["source_paths"]]
        if not matching:
            raise ValueError(f"{member}: no reviewed semantic decision for {surface.source_path}")
        row = surface.to_dict()
        row["model_obligation_ids"] = sorted({oid for rule in matching for oid in rule["model_obligation_ids"]})
        row_rules[surface.surface_id] = {rule["rule_id"] for rule in matching}
        rows.append(row)
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["review_granularity"] == "component":
            groups.setdefault(row["review_group_id"], []).append(row)
    for group in groups.values():
        ids = sorted({oid for row in group for oid in row["model_obligation_ids"]})
        rule_ids = {rid for row in group for rid in row_rules[row["surface_id"]]}
        for row in group:
            row["model_obligation_ids"] = ids
            row_rules[row["surface_id"]] = rule_ids
    inverse = {oid: [] for oid in sorted(obligations)}
    for row in rows:
        ids = row["model_obligation_ids"]
        required = sorted({cid for oid in ids for cid in obligations[oid]["required_check_ids"]})
        adequacy = sorted(set(required) | {deepening, f"check:{member}:consumer-contract"})
        if not set(adequacy) <= set(checks):
            raise ValueError(f"{member}: obligation references undeclared checks")
        row.update({
            "disposition": "governed", "owner_id": owner_id,
            "intent_id": f"intent:{member}:" + hashlib.sha256("|".join(sorted(row_rules[row["surface_id"]])).encode()).hexdigest()[:24],
            "obligation_ids": ids, "required_check_ids": required, "adequacy_check_ids": adequacy,
            "execution_owner_ids": sorted({checks[cid]["execution_owner_id"] for cid in adequacy}),
            "evidence_subject_ids": sorted({checks[cid]["evidence_subject_id"] for cid in adequacy}),
            "lifecycle_phase": "author-maintenance" if row["source_path"].startswith(".skillguard/") else "native-consumer-runtime",
            "consumer_exposure": "excluded-author-contract" if row["source_path"].startswith(".skillguard/") else "declared-member-skill",
            "write_authority": "author-contract-only" if row["source_path"].startswith(".skillguard/") else "target-owned-native-route",
        })
        for oid in ids:
            inverse[oid].append(row["surface_id"])
    if any(not surface_ids for surface_ids in inverse.values()):
        raise ValueError(f"{member}: an obligation has no source surface")
    obligation_bindings = [{"obligation_id": oid, "disposition": "governed", "surface_ids": sorted(surface_ids),
                            "reason": "Explicit member author rules bind these source surfaces to this compiled obligation.",
                            "proof_ref": ".skillguard/surface-semantic-map.json#decision_rules"}
                           for oid, surface_ids in inverse.items()]
    mapping = {
        "schema_version": "skillguard.surface_semantic_map.v1", "map_id": f"map:researchguard:{member}:surface-semantics",
        "target_skill_id": member, "source_discovery_fingerprint": scan.discovery_fingerprint,
        "full_surface_ids": [row["surface_id"] for row in rows], "current_obligation_ids": sorted(obligations),
        "decision_rules": rules, "surface_bindings": [
            {"surface_id": row["surface_id"], "model_obligation_ids": row["model_obligation_ids"],
             "rule_ids": sorted(row_rules[row["surface_id"]]),
             "decision": "explicit-author-component-group-closure" if row["review_granularity"] == "component" else "explicit-author-rule"}
            for row in rows], "obligation_bindings": obligation_bindings, "claim_boundary": CLAIM_BOUNDARY,
    }
    mapping["map_hash"] = _hash(mapping)
    categories = {"option": "command", "export": "api", "prompt": "template"}
    observed_categories = {categories.get(row["kind"], row["kind"]) for row in rows}
    inventory = {
        "schema_version": "skillguard.surface_inventory.v1", "inventory_id": f"inventory:researchguard:{member}:surfaces",
        "target_skill_id": member, "source_kind": "target-owned-full-source-discovery", "source_paths": list(scan.source_paths),
        "observed_surface_ids": [route_id], "owner_ids": [owner_id],
        "rows": [{"surface_id": route_id, "kind": "route", "name": f"{member} native route", "disposition": "governed",
                  "intent_id": f"intent:researchguard:{member}", "owner_id": owner_id, "route_id": route_id,
                  "function_id": f"function:researchguard:{member}", "required_check_ids": sorted(checks),
                  "adequacy_check_ids": sorted(checks), "evidence_subject_ids": sorted({row["evidence_subject_id"] for row in checks.values()})}],
        "current_obligation_ids": sorted(obligations), "model_obligations": obligation_bindings,
        "full_surface_ids": mapping["full_surface_ids"], "full_surfaces": rows,
        "surface_category_dispositions": {
            category: {"disposition": "governed" if category in observed_categories else "not_applicable_proven",
                       "reason": f"Current skill-root scan {'contains explicitly mapped' if category in observed_categories else 'contains no'} {category} surfaces; this says nothing about native package surfaces outside that root.",
                       "proof_ref": ".skillguard/surface-inventory.json#full_discovery_fingerprint"}
            for category in scanner.FULL_SURFACE_CATEGORIES},
        "full_discovery_fingerprint": scan.discovery_fingerprint, "adequacy_check_ids": sorted(checks),
        "model_deepening_check_id": deepening, "claim_boundary": CLAIM_BOUNDARY,
    }
    inventory["inventory_hash"] = scanner.surface_inventory_hash(inventory)
    findings = list(scanner.validate_surface_inventory(inventory, target_skill_id=member, native_check_ids=checks, model_deepening_check_id=deepening))
    findings += scanner.validate_full_surface_inventory(inventory, target_root=skill, native_check_ids=checks, model_deepening_check_id=deepening)
    if findings:
        raise ValueError(f"{member}: invalid generated inventory: {[f.to_dict() for f in findings]}")
    return mapping, inventory


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--member", choices=(*MEMBERS, "all"), default="all")
    parser.add_argument("--skillguard-root", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    scanner = load_skillguard(args.skillguard_root)
    members = MEMBERS if args.member == "all" else (args.member,)
    results = []
    # Validate every requested member before any projection write.
    generated = [(member, *build_member(args.root, member, scanner)) for member in members]
    for member, mapping, inventory in generated:
        directory = args.root / "skills" / member / ".skillguard"
        for filename, payload in (("surface-semantic-map.json", mapping), ("surface-inventory.json", inventory)):
            path = directory / filename
            if args.write:
                _write(path, payload)
            elif not path.is_file() or _read(path) != payload:
                raise ValueError(f"{member}: stale or missing {filename}; regenerate from current reviewed rules")
        results.append({"member": member, "surface_count": len(inventory["full_surfaces"]),
                        "obligation_count": len(inventory["current_obligation_ids"]), "inventory_hash": inventory["inventory_hash"]})
    print(json.dumps({"status": "written" if args.write else "current", "members": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
