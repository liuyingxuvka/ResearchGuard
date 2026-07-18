from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_SKILL_ROOT = ROOT / "skills"


def test_public_docs_define_ai_selected_diagram_semantics() -> None:
    diagram_docs = (ROOT / "docs" / "diagram_semantics.md").read_text(encoding="utf-8")
    viewer_docs = (ROOT / "docs" / "project_library_viewer.md").read_text(encoding="utf-8")
    writing_docs = (ROOT / "docs" / "writing_workflow.md").read_text(encoding="utf-8")

    assert "AI should choose the clearest diagram or table" in diagram_docs
    assert "Do not turn all of these into one generic flowchart" in diagram_docs
    assert "recommended_view" in diagram_docs
    assert "It does not expose graph-mode tabs" in diagram_docs
    assert "single recommended top-level logic graph" in viewer_docs
    assert "AI-selected Mermaid diagram or table" in writing_docs


def test_committed_logicguard_skill_owns_internal_routes() -> None:
    skill_dir = COMMITTED_SKILL_ROOT / "logicguard"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    route_names = {
        path.name
        for path in (skill_dir / "references" / "routes").glob("*.md")
    }

    assert "name: logicguard" in skill_text
    assert (skill_dir / "agents" / "openai.yaml").is_file()
    assert route_names == {
        "artifact-synthesis.md",
        "model-deepening.md",
        "project-library-viewer.md",
        "source-library.md",
        "structured-artifact.md",
    }
    assert "researchguard logic" in skill_text
    assert "C:\\Users" not in skill_text
    assert "LogicGuard_20260518" not in skill_text
