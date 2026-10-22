import pytest

from researchguard.gap_lineage import gap_lineage


@pytest.mark.parametrize("before,after,expected", [
    ([], [], ((), (), ())),
    (["b", "a", "a"], ["c", "b"], (("a",), ("b",), ("c",))),
    (["b", "a"], [], (("a", "b"), (), ())),
])
def test_gap_lineage_is_sorted_disjoint_and_set_based(before, after, expected):
    result = gap_lineage(before, after)
    assert result[:3] == expected
    assert result.gap_transitions == {
        **dict.fromkeys(expected[0], "resolved"), **dict.fromkeys(expected[1], "persisted"),
        **dict.fromkeys(expected[2], "introduced"),
    }
