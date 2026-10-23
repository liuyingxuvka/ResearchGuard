from researchguard.source.handoff import export_traceguard_seed
from researchguard.source.loader import load_model


def test_export_traceguard_seed_does_not_generate_validated_trace():
    seed = export_traceguard_seed(load_model("examples/source/multimodal_report_video_discovery.yaml"))
    assert seed["events"] == []
    assert seed["traces"] == []
    assert "not validated" in seed["metadata"]["boundary"]


def test_metadata_boundary_exists():
    seed = export_traceguard_seed(load_model("examples/source/starter_researchguard.source.yaml"))
    assert seed["metadata"]["boundary"]


def test_exports_accept_a_model_written_by_an_older_release():
    state = load_model("examples/source/fuel_cell_project_discovery.yaml")
    state.metadata["version"] = "0.5.8"
    assert export_traceguard_seed(state)["metadata"]["source_model_version"] == "0.5.8"


def test_traceguard_seed_loads_as_a_traceguard_model():
    from researchguard.trace.schema import TraceGuardModel
    from researchguard.trace.validation import validate_references

    state = load_model("examples/source/paper_citation_discovery.yaml")
    model = TraceGuardModel.from_dict(export_traceguard_seed(state))
    validate_references(model)
    assert model.sources and model.evidence and not model.traces
