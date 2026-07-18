from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_source_library_docs_distinguish_preservation_from_codex_completion() -> None:
    text = (ROOT / "docs" / "source_library_workflow.md").read_text(encoding="utf-8")

    assert "Default CLI intake" in text
    assert "Codex must read the source" in text
    assert "content-level shallow model" in text
    assert "preserved with modeling incomplete" in text


def test_readme_documents_ai_modeled_source_intake_gate() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Codex-facing source intake contract" in text
    assert "CLI preservation step is not enough by itself" in text
    assert "content-level model" in text
    assert "view-graph" in text
