from researchguard.source.stop_decision import SearchStopInput, decide_search_stop


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
