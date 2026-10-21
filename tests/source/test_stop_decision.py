import json
import subprocess
import sys
from pathlib import Path

from researchguard.source.loader import load_model
from researchguard.source.stop_decision import SearchStopInput, decide_model_search_stop, decide_search_stop

ROOT = Path(__file__).resolve().parents[2]


def test_critical_gap_continues_only_with_justified_search() -> None:
    result = decide_search_stop(
        SearchStopInput(
            marginal_information_value=5,
            next_search_cost=2,
            remaining_budget=3,
            evidence_sufficient_for_scope=False,
            unresolved_critical_gap_ids=("gap:b", "gap:a"),
            candidate_search_ids=("search:2", "search:1"),
        )
    )
    assert result.status == "continue_search"
    assert result.selected_search_id == "search:1"
    assert result.unresolved_critical_gap_ids == ("gap:a", "gap:b")


def test_critical_gap_cannot_be_hidden_by_budget_exhaustion() -> None:
    result = decide_search_stop(
        SearchStopInput(
            marginal_information_value=5,
            next_search_cost=2,
            remaining_budget=1,
            evidence_sufficient_for_scope=True,
            unresolved_critical_gap_ids=("gap:critical",),
            candidate_search_ids=("search:1",),
        )
    )
    assert result.status == "blocked_unresolved_critical"


def test_sufficient_scope_stops_when_marginal_value_is_not_higher() -> None:
    result = decide_search_stop(
        SearchStopInput(
            marginal_information_value=1,
            next_search_cost=1,
            remaining_budget=10,
            evidence_sufficient_for_scope=True,
        )
    )
    assert result.status == "stop_sufficient"


def test_model_stop_decision_reads_the_plan_and_the_blocking_gaps() -> None:
    state = load_model(ROOT / "examples/source/starter_researchguard.source.yaml")
    inputs, decision = decide_model_search_stop(state, remaining_budget=1.0)
    assert inputs.unresolved_critical_gap_ids == ("gap-independent-1",)
    assert inputs.next_search_cost == 0.3
    assert decision.status == "continue_search"
    assert decision.selected_search_id == inputs.candidate_search_ids[0]
    _, starved = decide_model_search_stop(state, remaining_budget=0.1)
    assert starved.status == "blocked_unresolved_critical"


def _source_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "researchguard", "source", *args],
                          cwd=ROOT, capture_output=True, text=True)


def test_stop_decision_cli_prints_its_inputs_and_the_decision(tmp_path) -> None:
    result = _source_cli("stop-decision", "examples/source/paper_citation_discovery.yaml", "--budget", "1")
    assert result.returncode == 0, result.stderr
    searching = json.loads(result.stdout)
    assert searching["status"] == "continue_search"
    assert searching["inputs"]["remaining_budget"] == 1.0
    assert searching["inputs"]["unresolved_critical_gap_ids"] == ["gap-baseline", "gap-counter"]
    assert searching["selected_search_id"] == searching["inputs"]["candidate_search_ids"][0]

    # The example observation closes the starter model's only blocking gap, so the grown model may stop.
    grown = tmp_path / "grown.yaml"
    added = _source_cli("add-observation", "examples/source/starter_researchguard.source.yaml",
                        "--observation", "examples/source/qualified_observation.yaml", "--output", str(grown))
    assert added.returncode == 0, added.stdout + added.stderr
    assert [(gap.gap_id, gap.semantic_state) for gap in load_model(grown).gaps] == [("gap-independent-1", "closed")]
    result = _source_cli("stop-decision", str(grown), "--budget", "1")
    assert result.returncode == 0, result.stderr
    stopped = json.loads(result.stdout)
    assert stopped["status"] == "stop_sufficient"
    assert stopped["inputs"]["evidence_sufficient_for_scope"] is True
    assert stopped["inputs"]["unresolved_critical_gap_ids"] == []
