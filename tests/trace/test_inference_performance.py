from __future__ import annotations

from time import perf_counter

from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import TraceGuardModel


PERFORMANCE_CASE_SIZE = 120
PERFORMANCE_BUDGET_SECONDS = 8.0


def _large_sparse_payload(size: int = PERFORMANCE_CASE_SIZE) -> dict:
    payload: dict[str, object] = {
        "metadata": {"schema_version": "researchguard.trace.model.v2"},
        "sources": [],
        "evidence": [],
        "events": [],
        "traces": [],
        "storyline_hypotheses": [],
        "hypothesis_evidence_links": [],
    }
    for index in range(size):
        payload["sources"].append(
            {
                "source_id": f"source-{index}",
                "title": f"Independent source {index}",
                "source_type": "government_database",
                "source_reliability": 0.9,
                "source_status": "stable_keep",
                "lineage_id": f"lineage-{index}",
                "independence_group": f"group-{index}",
            }
        )
        payload["evidence"].append(
            {
                "evidence_id": f"evidence-{index}",
                "source_id": f"source-{index}",
                "raw_text": f"Observed event {index}.",
                "evidence_type": "official_project_page",
                "extraction_confidence": 0.9,
                "evidence_specificity": 0.9,
                "usable_as_trace_evidence": True,
            }
        )
        payload["events"].append(
            {
                "event_id": f"event-{index}",
                "action": f"Observed action {index}",
                "time_start": f"2025-01-{index % 28 + 1:02d}",
                "evidence_ids": [f"evidence-{index}"],
            }
        )
        payload["traces"].append(
            {
                "trace_id": f"trace-{index}",
                "title": f"Sparse trace {index}",
                "trace_type": "incident",
                "event_ids": [f"event-{index}"],
                "current_stage": "observed",
            }
        )
        payload["storyline_hypotheses"].append(
            {
                "hypothesis_id": f"hypothesis-{index}",
                "claim": f"Bounded explanation {index}",
                "role": "primary" if index == 0 else "alternative",
                "trace_ids": [f"trace-{index}"],
                "event_ids": [f"event-{index}"],
                "bounded_non_causal": True,
            }
        )
        payload["hypothesis_evidence_links"].append(
            {
                "link_id": f"support-{index}",
                "hypothesis_id": f"hypothesis-{index}",
                "evidence_id": f"evidence-{index}",
                "polarity": "support",
            }
        )
    return payload


def test_fixed_sparse_performance_budget() -> None:
    model = TraceGuardModel.from_dict(_large_sparse_payload())
    started = perf_counter()
    result = evaluate_model(model, include_storyline_depth=False)
    elapsed = perf_counter() - started
    assert len(result.traces) == PERFORMANCE_CASE_SIZE
    assert len(result.inference_receipt.contributions) == PERFORMANCE_CASE_SIZE * 6
    assert result.inference_receipt.solver_status in {"solved", "solved inaccurate"}
    assert elapsed <= PERFORMANCE_BUDGET_SECONDS
