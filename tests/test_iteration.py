"""The shared kernel preserves identity and never edits current models."""
from pathlib import Path

import pytest

from researchguard.iteration import baseline_identity, require_prediction_identity, select_terminal, validate_candidate


def test_prediction_identity_is_content_bound():
    before = baseline_identity({"a": 1, "b": [2]})
    assert before == baseline_identity({"b": [2], "a": 1})
    assert before.startswith("sha256:")
    require_prediction_identity(before, before)
    with pytest.raises(ValueError, match="stale_prediction: re-freeze"):
        require_prediction_identity(before, baseline_identity({"a": 2, "b": [2]}))


def test_candidate_never_overwrites_current(tmp_path: Path):
    current, candidate = tmp_path / "current", tmp_path / "candidate"
    current.write_text("current")
    with pytest.raises(ValueError, match="path must differ"):
        validate_candidate(current, current, {"x": 1}, {"x": 2})
    with pytest.raises(ValueError, match="content must differ"):
        validate_candidate(current, candidate, {"x": 1}, {"x": 1})
    validate_candidate(current, candidate, {"x": 1}, {"x": 2})
    assert current.read_text() == "current"
    assert not candidate.exists()


def test_no_progress_is_stalled():
    assert select_terminal(stalled=True) == "progress_stalled"
    assert select_terminal(closed=True) == "model_closed_for_task"
    assert select_terminal(provider_unavailable=True) == "provider_access_required"
    assert select_terminal(finite_action_exhausted=True) == "finite_action_exhausted"


def test_limit_stops_iteration():
    assert select_terminal(iteration=3, max_iterations=3) == "iteration_limit"
    assert select_terminal(iteration=2, max_iterations=3) == "continue_iteration"
