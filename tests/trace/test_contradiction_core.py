from researchguard.trace.inference.contradiction_core import (
    find_deletion_minimal_contradiction_core,
)


def test_finds_deterministic_deletion_minimal_core() -> None:
    def is_consistent(ids: tuple[str, ...]) -> bool:
        values = set(ids)
        return not ({"a", "b"} <= values)

    result = find_deletion_minimal_contradiction_core(
        ("noise", "b", "a"),
        is_consistent=is_consistent,
    )
    assert result.status == "core_found"
    assert result.constraint_ids == ("a", "b")
    assert all(value for _, value in result.necessity_witnesses)


def test_consistent_inventory_returns_no_core() -> None:
    result = find_deletion_minimal_contradiction_core(
        ("a", "b"),
        is_consistent=lambda _ids: True,
    )
    assert result.status == "consistent"
    assert result.constraint_ids == ()
