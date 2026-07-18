from __future__ import annotations

from pathlib import Path

from researchguard.logic import SourceLibrary, build_library_view_payload, build_source_graph_payload
from researchguard.logic_viewer.ui_data import build_card_detail_payload, build_route_view_payload, build_search_payload


def test_library_view_payload_is_read_only_for_missing_root(tmp_path: Path) -> None:
    library_root = tmp_path / "missing-library"

    payload = build_library_view_payload(library_root)

    assert payload["summary"]["source_count"] == 0
    assert payload["summary"]["project_count"] == 0
    assert payload["cards"] == []
    assert not library_root.exists()


def test_library_viewer_groups_sources_by_project_and_marks_graph(tmp_path: Path) -> None:
    source_file = tmp_path / "validation.pptx"
    source_file.write_text("Validation deck", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Validation Deck", year="2026", source_date="2026", coverage_period="2025-Q4")
    library.create_source_model(
        imported.source.source_id,
        claim="The validation deck is ready for customer review.",
        evidence="Measured trend matches expected behavior.",
        warrant="Trend agreement supports a bounded validation claim.",
        limitation="The result only applies inside the validated operating envelope.",
        locator="slide 1",
        importance=0.92,
        salience="core",
        importance_reason="Main source claim.",
    )
    project = library.create_project("Customer Briefing", topic="Customer-facing validation story")
    library.select_source(project.project_id, imported.source.source_id)

    payload = build_library_view_payload(library_root)
    card = payload["cards"][0]

    assert payload["summary"]["source_count"] == 1
    assert payload["summary"]["project_count"] == 1
    assert card["source_type"] == "presentation"
    assert card["source_date"] == "2026"
    assert card["coverage_period"] == "2025-Q4"
    assert card["temporal_context"]["coverage_period"] == "2025-Q4"
    assert card["project_ids"] == ["customer-briefing"]
    assert card["modeling_status"] == "modeled"
    assert card["important_node_count"] >= 1
    assert card["risk_node_count"] >= 1

    graph = build_source_graph_payload(library_root, imported.source.source_id)
    assert graph["modeled"] is True
    assert graph["root_claim"] == "C1"
    assert any(node["markers"]["important"] for node in graph["nodes"])
    assert any(node["markers"]["risk"] for node in graph["nodes"])
    assert any(edge["type"] == "qualifies" for edge in graph["edges"])


def test_copied_ui_adapter_returns_project_deck_and_graph_detail(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_text("Paper", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Efficiency Paper", source_date="2024", coverage_period="2021-2023")
    library.create_source_model(
        imported.source.source_id,
        claim="The intervention reduces task time in the studied setting.",
        evidence="Participants completed tasks faster.",
        limitation="The study does not measure long-term quality.",
    )
    project = library.create_project("Paper Project", topic="Paper synthesis")
    library.select_source(project.project_id, imported.source.source_id)

    route_payload = build_route_view_payload(library_root, route=project.project_id)
    detail = build_card_detail_payload(library_root, imported.source.source_id)

    assert route_payload["deck"][0]["id"] == imported.source.source_id
    assert route_payload["navigation_children"]
    assert detail is not None
    assert detail["graph"]["nodes"]
    assert detail["read_only"] is True
    assert detail["library_card"]["source_date"] == "2024"


def test_project_navigation_keeps_uncategorized_as_stable_project_bucket(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_text("Paper", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Loose Paper")

    payload = build_route_view_payload(library_root, language="en")
    children = payload["navigation_children"]

    assert [child["route"] for child in children] == [["uncategorized"]]
    assert children[0]["label"] == "Uncategorized"
    assert children[0]["observed_subtree_count"] == 1
    assert build_route_view_payload(library_root, route="uncategorized")["deck"][0]["id"] == imported.source.source_id


def test_route_cards_hide_internal_importance_and_risk_preview_labels(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_text("Paper", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Loose Paper")
    library.create_source_model(
        imported.source.source_id,
        claim="The paper has a bounded source claim.",
        evidence="The paper reports measured evidence.",
        limitation="The claim is limited by one dataset.",
        importance=0.8,
    )

    payload = build_route_view_payload(library_root, language="en")
    card = payload["deck"][0]

    assert "重要" not in card["predicted_result"]
    assert "风险" not in card["predicted_result"]
    assert "risk" not in build_route_view_payload(library_root, language="en")["deck"][0]["predicted_result"].lower()
    assert "important" not in build_route_view_payload(library_root, language="en")["deck"][0]["predicted_result"].lower()


def test_source_graph_payload_localizes_model_content_and_view_modes(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_text("Paper", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Copper Selenide Paper")
    library.create_source_model(
        imported.source.source_id,
        claim="The composite improves lithium-sulfur cathode behavior.",
        method="The paper prepares a graphene and copper selenide composite separator.",
        evidence="Cycling and rate tests show better capacity retention.",
        result="The modified separator limits polysulfide loss.",
        limitation="The conclusion is bounded by the tested material ratios.",
        i18n={
            "en": {
                "title": "Graphene copper selenide composite in lithium-sulfur batteries",
                "claim": "The composite improves lithium-sulfur cathode behavior.",
                "method": "The paper prepares a graphene and copper selenide composite separator.",
                "evidence": "Cycling and rate tests show better capacity retention.",
                "result": "The modified separator limits polysulfide loss.",
                "limitation": "The conclusion is bounded by the tested material ratios.",
            },
            "zh-CN": {
                "title": "石墨烯/硒化铜复合材料用于锂硫电池",
                "claim": "该复合材料改善了锂硫电池正极表现。",
                "method": "论文制备石墨烯和硒化铜复合隔膜。",
                "evidence": "循环和倍率测试显示容量保持更好。",
                "result": "改性隔膜限制了多硫化物损失。",
                "limitation": "结论受测试材料配比限制。",
            },
        },
    )

    graph_en = build_source_graph_payload(library_root, imported.source.source_id, language="en")
    graph_zh = build_source_graph_payload(library_root, imported.source.source_id, language="zh-CN")
    detail_zh = build_card_detail_payload(library_root, imported.source.source_id, language="zh-CN")

    assert graph_en["model"]["title"].startswith("Graphene copper")
    assert graph_zh["model"]["title"].startswith("石墨烯")
    assert any(node["text"].startswith("该复合材料") for node in graph_zh["nodes"])
    assert graph_zh["views"]["argument_map"]["label"] == "论证图"
    assert graph_zh["views"]["argument_map"]["diagram_kind"] == "argument_support"
    assert graph_zh["views"]["argument_map"]["visible"] is False
    assert graph_zh["views"]["research_flow"]["diagram_kind"] == "process_timeline"
    assert graph_zh["views"]["research_flow"]["visible"] is True
    assert graph_zh["views"]["research_flow"]["edges"]
    assert graph_zh["preferred_view"] == "research_flow"
    assert graph_zh["recommended_view"] == "research_flow"
    assert graph_zh["recommended_diagram_kind"] == "process_timeline"
    assert "推荐" in graph_zh["recommendation_reason"]
    assert detail_zh is not None
    assert detail_zh["title"].startswith("石墨烯")
    assert detail_zh["graph"]["nodes"][0]["text"] != graph_en["nodes"][0]["text"]


def test_desktop_graph_canvas_supports_pan_zoom_reset_and_text_only_nodes() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "researchguard"
        / "logic_viewer"
        / "desktop_app.py"
    ).read_text(encoding="utf-8")
    draw_method = source.split("def _draw_graph_node", 1)[1].split("def _refresh_after_language_change", 1)[0]

    assert "on_pan_start" in source
    assert "on_pan_move" in source
    assert "on_zoom" in source
    assert "reset_graph_view" in source
    assert "graph_interaction_hint" in source
    assert "_recommended_graph_view_id" in source
    assert "recommended_graph" in source
    assert "argument_map_tab" not in source
    assert "research_flow_tab" not in source
    assert "_draw_process_timeline" in source
    assert "diagram_kind" in source
    assert "reset_button.place" in source
    assert "fit_scale = max(0.68" in source
    assert "pad - min_y * fit_scale" in source
    assert "Projects: Uncategorized" not in source
    assert "draw_reset_button" in source
    assert 'cursor="hand2"' in source
    assert "reset_button.bind(\"<Enter>\"" in source
    assert "reset_button.bind(\"<ButtonRelease-1>\"" in source
    assert "_round_rect" not in draw_method
    assert "create_text" in draw_method
    assert "fill=TEXT" in draw_method
    assert "create_oval" in draw_method


def test_detail_header_meta_hides_internal_source_noise() -> None:
    from researchguard.logic_viewer.desktop_app import _detail_header_meta_line

    card = {
        "type": "paper",
        "status": "risk",
        "confidence": 0.52,
        "read_only": True,
        "source_info": {"kind": "local", "scope": "library"},
        "library_card": {
            "modeling_status": "modeled",
            "temporal_context": {"added_at": "2022-11-25T00:23:05Z"},
            "project_ids": [],
        },
    }

    meta = _detail_header_meta_line(card, "zh-CN")

    assert meta == "论文 · 已建模 · 加入 2022-11-25 · 未归入项目"
    assert "重要性" not in meta
    assert "0.52" not in meta
    assert "本地" not in meta
    assert "Library" not in meta
    assert "只读" not in meta
    assert "有风险点" not in meta


def test_viewer_search_matches_temporal_context(tmp_path: Path) -> None:
    source_file = tmp_path / "report.pdf"
    source_file.write_text("Report", encoding="utf-8")
    library_root = tmp_path / "library"
    imported = SourceLibrary(library_root).import_source(
        source_file,
        title="Timeline Report",
        source_date="2025",
        coverage_period="2021-2024",
    )

    result = build_search_payload(library_root, "2021-2024")

    assert result["results"][0]["id"] == imported.source.source_id
