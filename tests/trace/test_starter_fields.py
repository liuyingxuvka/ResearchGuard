"""Keep the public trace field examples usable by first-time model authors."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re

import yaml

from researchguard.trace import schema
from researchguard.trace.cli import STARTER_MODEL
from researchguard.trace.loader import load_model
from researchguard.trace.task_iteration import EvidenceBatchObservation, VALID_QUALITY
from researchguard.trace.validation import validate_references


ROOT = Path(__file__).resolve().parents[2]
FIELD_SHEET = ROOT / "skills/researchguard/references/trace/fields.md"
MODEL_LISTS = (
    "sources", "evidence", "events", "traces", "storyline_hypotheses",
    "hypothesis_evidence_links", "hypothesis_relations", "causal_mechanisms",
    "confounder_reviews", "causal_scopes", "causal_candidates",
    "evidence_ablations", "scenario_perturbations", "expected_sensitivities",
)


def test_documented_starter_is_the_real_nonempty_create_model(tmp_path: Path) -> None:
    text = FIELD_SHEET.read_text(encoding="utf-8")
    examples = re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    assert len(examples) == 1
    payload = yaml.safe_load(examples[0])
    assert payload == STARTER_MODEL
    target = tmp_path / "starter.yaml"
    target.write_text(examples[0], encoding="utf-8")
    model = load_model(target)
    validate_references(model)
    assert len(model.events) == len(model.storyline_hypotheses) == 2
    assert len(model.traces) == 1
    assert model.traces[0].event_ids == [event.event_id for event in model.events]
    assert [event.time_interval.start for event in model.events] == [
        "2024-01-01", "2024-01-02",
    ]
    assert {link.polarity for link in model.hypothesis_evidence_links} >= {
        "support", "oppose",
    }
    assert model.causal_mechanisms and model.causal_scopes and model.causal_candidates
    assert model.confounder_reviews[0].status == "unresolved"
    assert "invented" in model.metadata["boundary"].lower()


def test_field_sheet_names_all_requested_lists_and_current_enum_values() -> None:
    text = FIELD_SHEET.read_text(encoding="utf-8")
    for name in MODEL_LISTS:
        assert f"## {name}\n" in text
    for choices in (
        schema.SOURCE_STATUSES, schema.EVIDENCE_POLARITIES,
        schema.HYPOTHESIS_RELATIONS, schema.CONFOUNDER_STATUSES,
        schema.PERTURBATION_DIRECTIONS, schema.TIME_PRECISIONS,
        schema.ENTITY_RESOLUTION_RELATIONS, schema.LOCATION_ROLES,
        schema.VALIDATION_STATUSES, schema.CAUSAL_STATUSES,
        VALID_QUALITY,
    ):
        for value in choices:
            assert f"`{value}`" in text


def test_documented_observation_has_every_current_field_and_resolves_ids() -> None:
    text = FIELD_SHEET.read_text(encoding="utf-8")
    examples = re.findall(r"```json\n(.*?)\n```", text, re.DOTALL)
    assert len(examples) == 1
    payload = json.loads(examples[0])
    observation = EvidenceBatchObservation.from_dict(payload)
    assert set(payload) == set(asdict(observation))
    assert set(observation.evidence_ids) <= {
        row["evidence_id"] for row in STARTER_MODEL["evidence"]
    }
    assert set(observation.event_ids) <= {
        row["event_id"] for row in STARTER_MODEL["events"]
    }
    assert set(observation.source_refs) <= {
        row["source_id"] for row in STARTER_MODEL["sources"]
    }
    assert observation.event_order == observation.event_ids
    assert observation.future_holdout_status == "not_run"
