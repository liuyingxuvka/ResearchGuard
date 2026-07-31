from researchguard.logic.minimal_sets import license_conclusion


def test_support_and_attack_are_deletion_minimal() -> None:
    result = license_conclusion(
        ("s3", "s2", "s1"),
        ("a2", "a1"),
        supports_conclusion=lambda ids: {"s1", "s2"} <= set(ids),
        defeats_conclusion=lambda ids: {"a1"} <= set(ids),
    )
    assert result.wording_license == "qualify"
    assert result.support is not None
    assert result.support.node_ids == ("s1", "s2")
    assert result.support.deletion_minimal
    assert result.attack is not None
    assert result.attack.node_ids == ("a1",)


def test_missing_support_withholds_conclusion() -> None:
    result = license_conclusion(
        ("s1",),
        (),
        supports_conclusion=lambda _ids: False,
        defeats_conclusion=lambda _ids: False,
    )
    assert result.wording_license == "withhold"
