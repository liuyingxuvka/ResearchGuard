from researchguard.source.handoff import export_logicguard_source_candidates, export_traceguard_seed
from researchguard.source.loader import load_model


def test_export_traceguard_seed_does_not_generate_validated_trace():
    seed = export_traceguard_seed(load_model("examples/source/multimodal_report_video_discovery.yaml", "examples/source/multimodal_report_video_discovery.contract.json"))
    assert seed["events"] == []
    assert seed["traces"] == []
    assert "not validated" in seed["metadata"]["boundary"]


def test_export_logicguard_source_candidates_does_not_claim_source_modeled():
    bundle = export_logicguard_source_candidates(load_model("examples/source/fuel_cell_project_discovery.yaml", "examples/source/fuel_cell_project_discovery.contract.json"))
    assert bundle["source_candidates"]
    assert "must still be preserved and modeled" in bundle["metadata"]["boundary"]
    assert all("LogicGuard has not modeled" in candidate["boundary"] for candidate in bundle["source_candidates"])


def test_structural_source_fields_survive_logicguard_export():
    bundle = export_logicguard_source_candidates(load_model("examples/source/structural_source_gap.yaml", "examples/source/structural_source_gap.contract.json"))
    candidate = bundle["source_candidates"][0]
    gap = bundle["source_gap_rows"][0]
    assert candidate["can_support_structural_use"]
    assert candidate["cannot_support_structural_use"]
    assert gap["structure_unit_id"] == "chapter_3.technology_summary"
    assert gap["downstream_consumer"] == "chapter_4.method_gap"


def test_metadata_boundary_exists():
    seed = export_traceguard_seed(load_model("examples/source/starter_researchguard.source.yaml", "examples/source/starter_researchguard.source.contract.json"))
    bundle = export_logicguard_source_candidates(load_model("examples/source/starter_researchguard.source.yaml", "examples/source/starter_researchguard.source.contract.json"))
    assert seed["metadata"]["boundary"]
    assert bundle["metadata"]["boundary"]
