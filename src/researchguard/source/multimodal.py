"""
Purpose: Create and validate SourceGuard multimodal evidence-anchor structures without fake extraction.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source report <model.yaml> --model-contract <model.contract.json> --format markdown
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from .schema import EvidenceAnchor


def validate_anchor_locator(anchor: EvidenceAnchor) -> list[str]:
    warnings: list[str] = []
    if anchor.modality in {"pdf_page", "book_page", "image", "video", "audio", "table", "map"} and not anchor.locator:
        warnings.append("Multimodal anchor has no locator; do not treat it as precise evidence.")
    if anchor.modality == "video" and "timestamp=" not in anchor.locator:
        warnings.append("Video anchor locator should include timestamp=start-end.")
    if anchor.modality == "audio" and "timestamp=" not in anchor.locator:
        warnings.append("Audio anchor locator should include timestamp=start-end.")
    if anchor.modality == "pdf_page" and "page=" not in anchor.locator:
        warnings.append("PDF anchor locator should include page=N.")
    if anchor.modality == "book_page" and "page=" not in anchor.locator:
        warnings.append("Book anchor locator should include page=N.")
    return warnings


def _anchor(
    anchor_id: str,
    source_id: str,
    anchor_type: str,
    modality: str,
    locator: str,
    normalized_summary: str = "",
    text: str = "",
    notes: str = "",
) -> EvidenceAnchor:
    anchor = EvidenceAnchor(
        anchor_id=anchor_id,
        source_id=source_id,
        anchor_type=anchor_type,
        locator=locator,
        text=text,
        normalized_summary=normalized_summary,
        modality=modality,
        extraction_confidence=0.0,
        specificity=0.5 if locator else 0.0,
        usable_for_trace=False,
        usable_for_claim=False,
        notes=notes,
    )
    anchor.warnings.extend(validate_anchor_locator(anchor))
    if not text:
        anchor.warnings.append("No OCR, transcript, visual recognition, or audio extraction text was provided.")
    return anchor


def make_image_anchor(anchor_id: str, source_id: str, locator: str, normalized_summary: str = "", text: str = "") -> EvidenceAnchor:
    return _anchor(anchor_id, source_id, "image_region", "image", locator, normalized_summary, text)


def make_video_segment_anchor(anchor_id: str, source_id: str, locator: str, normalized_summary: str = "", text: str = "") -> EvidenceAnchor:
    return _anchor(anchor_id, source_id, "video_segment", "video", locator, normalized_summary, text)


def make_audio_segment_anchor(anchor_id: str, source_id: str, locator: str, normalized_summary: str = "", text: str = "") -> EvidenceAnchor:
    return _anchor(anchor_id, source_id, "audio_segment", "audio", locator, normalized_summary, text)


def make_pdf_page_anchor(anchor_id: str, source_id: str, locator: str, normalized_summary: str = "", text: str = "") -> EvidenceAnchor:
    return _anchor(anchor_id, source_id, "page", "pdf_page", locator, normalized_summary, text)


def make_book_page_anchor(anchor_id: str, source_id: str, locator: str, normalized_summary: str = "", text: str = "") -> EvidenceAnchor:
    return _anchor(anchor_id, source_id, "page", "book_page", locator, normalized_summary, text)
