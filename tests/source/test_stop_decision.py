import json
import subprocess
import sys
from pathlib import Path

from researchguard.source.loader import load_model
from researchguard.source.stop_decision import SearchStopInput, decide_model_search_stop, decide_search_stop

ROOT = Path(__file__).resolve().parents[2]


def test_critical_gap_continues_only_with_affordable_target() -> None:
    from researchguard.source.stop_decision import SearchCandidate
    inputs = SearchStopInput(3, False, ("gap:b", "gap:a"), candidates=(
        SearchCandidate("search:2", "gap:a", 2, 5),
        SearchCandidate("search:1", "gap:b", 2, 5),
    ))
    result = decide_search_stop(inputs)
    assert result.status == "continue_search"
    assert result.selected_search_id == "search:1"
    assert result.unresolved_critical_gap_ids == ("gap:a", "gap:b")


def test_critical_gap_cannot_be_hidden_by_budget_exhaustion() -> None:
    from researchguard.source.stop_decision import SearchCandidate
    result = decide_search_stop(SearchStopInput(1, True, ("gap:critical",), candidates=(
        SearchCandidate("search:1", "gap:critical", 2, 5),
    )))
    assert result.status == "blocked_unresolved_critical"
    assert result.reason_code == "critical_gap_search_over_budget"
    assert "1" in result.reason and "gap:critical" in result.reason


def test_sufficient_scope_stops_even_with_valuable_optional_search() -> None:
    from researchguard.source.stop_decision import SearchCandidate
    result = decide_search_stop(SearchStopInput(10, True, optional_gap_ids=("optional",), candidates=(
        SearchCandidate("optional-action", "optional", 1, 10),
    )))
    assert result.status == "stop_sufficient"
    assert result.optional_followups == ({"gap_id": "optional", "action_id": "optional-action"},)


def test_model_stop_decision_reads_the_plan_and_the_blocking_gaps() -> None:
    state = load_model(ROOT / "examples/source/starter_researchguard.source.yaml")
    inputs, decision = decide_model_search_stop(state, remaining_budget=1.0)
    assert inputs.unresolved_critical_gap_ids == ("gap-independent-1",)
    assert any(item.cost == 0.3 for item in inputs.candidates)
    assert decision.status == "continue_search"
    assert decision.selected_search_id in inputs.to_dict()["affordable_search_ids"]
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
    # The model still has open gaps, so the scope is not sufficient yet.
    assert searching["inputs"]["evidence_sufficient_for_scope"] is False
    assert searching["inputs"]["unresolved_critical_gap_ids"] == ["gap-baseline", "gap-counter"]
    assert searching["selected_search_id"] in searching["inputs"]["affordable_search_ids"]
    assert "marginal_information_value" not in searching["inputs"]
    assert "next_search_cost" not in searching["inputs"]

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


EVERGIVEN = Path(__file__).parent / "fixtures/evergiven"


def test_blocking_closed_nonblocking_open_and_sufficient_stops() -> None:
    state = load_model(EVERGIVEN / "src_v4.yaml")
    for budget in (0, 0.2, 1):
        inputs, result = decide_model_search_stop(state, remaining_budget=budget, evidence_sufficient_for_scope=True)
        assert not inputs.unresolved_critical_gap_ids
        assert result.status == "stop_sufficient"
        assert "gap-alt-yantian" in {item["gap_id"] for item in result.optional_followups}


def test_cheaper_critical_action_is_found_within_budget() -> None:
    state = load_model(EVERGIVEN / "src_v1.yaml")
    inputs, result = decide_model_search_stop(state, remaining_budget=0.25)
    assert result.status == "continue_search"
    assert result.selected_search_id == "act-sca-statement"
    assert len(inputs.candidates) > 1
    _, funded = decide_model_search_stop(state, remaining_budget=1)
    assert funded.status == "continue_search"


def test_zero_budget_blocks_only_while_a_blocking_gap_is_open() -> None:
    state = load_model(EVERGIVEN / "src_v1.yaml")
    for budget in (0, 0.1):
        _, result = decide_model_search_stop(state, remaining_budget=budget)
        assert result.status == "blocked_unresolved_critical"
    empty = decide_search_stop(SearchStopInput(0, False))
    assert empty.status == "stop_sufficient"
    assert decide_search_stop(SearchStopInput(-1, True)).status == "not_run"
    assert decide_search_stop(SearchStopInput(float("nan"), True)).status == "not_run"


def test_optional_budget_and_declared_then_id_ties() -> None:
    from researchguard.source.stop_decision import SearchCandidate
    candidates = (SearchCandidate("a-generated", "optional", 0.2, 0.1),
                  SearchCandidate("z-declared", "optional", 0.2, 0.1, True),
                  SearchCandidate("b-declared", "optional", 0.2, 0.1, True))
    for budget, status in ((0, "stop_sufficient"), (1, "continue_search")):
        result = decide_search_stop(SearchStopInput(budget, False, optional_gap_ids=("optional", "no-action"), candidates=candidates))
        assert result.status == status
        assert result.optional_followups == ({"gap_id": "no-action", "action_id": ""},
                                            {"gap_id": "optional", "action_id": "b-declared"})
        if budget:
            assert result.selected_search_id == "b-declared"
            assert "pass --sufficient" in result.reason


def test_blocked_and_permission_gaps_still_prevent_sufficient_stop() -> None:
    from researchguard.source.schema import BeliefState, Gap
    for gap in (Gap("blocked", blocking=True, semantic_state="blocked"),
                Gap("permission", gap_type="permission_gap", blocking=True)):
        inputs, result = decide_model_search_stop(BeliefState(gaps=[gap]), remaining_budget=0, evidence_sufficient_for_scope=True)
        assert inputs.unresolved_critical_gap_ids == (gap.gap_id,)
        assert result.status == "blocked_unresolved_critical"
        if gap.gap_type == "permission_gap":
            assert result.reason_code == "critical_gap_without_search"
            assert gap.gap_id in result.reason


def test_complete_catalog_is_not_capped_to_a_top_n() -> None:
    from researchguard.source.schema import BeliefState, Gap, SearchAction
    actions = [SearchAction(f"expensive-{i}", target_gap_id="critical", cost=1, query=str(i)) for i in range(1001)]
    actions.append(SearchAction("last-affordable", target_gap_id="critical", cost=0.01, query="last"))
    inputs, result = decide_model_search_stop(BeliefState(gaps=[Gap("critical", blocking=True)], actions=actions), remaining_budget=0.01)
    assert len(inputs.candidates) > 1001
    assert result.selected_search_id == "last-affordable"


def test_counter_source_that_answers_a_counter_gap_opens_no_new_gap() -> None:
    from dataclasses import replace
    import yaml
    from researchguard.source.schema import Observation
    from researchguard.source.update import detect_basic_contradiction
    observation = Observation.from_dict(yaml.safe_load((EVERGIVEN / "obs3.yaml").read_text()))
    state = load_model(EVERGIVEN / "src_v1.yaml")
    assert not detect_basic_contradiction(state, observation)
    unrelated = replace(observation, observed_anchors=[])
    assert [gap.gap_id for gap in detect_basic_contradiction(state, unrelated)] == ["counter-source-src-unctad-rmt2021"]
    explicit = replace(observation, contradictions=["A real contradiction remains."])
    assert [gap.gap_id for gap in detect_basic_contradiction(state, explicit)] == ["contradiction-obs-unctad-pretrend-1"]


def test_stop_decision_model_replays_native_owner_and_kills_each_bad_variant() -> None:
    import importlib.util
    path = ROOT / ".flowguard/models/sourceguard_stop_decision_model.py"
    spec = importlib.util.spec_from_file_location("stop_decision_model", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.conformance().ok
    for name, explorer in module.broken_variants().items():
        report = explorer.explore()
        assert not report.ok, name
