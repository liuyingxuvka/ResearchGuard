"""A one-word edit must remain visible after status is serialized and compared."""
from research_tree_support import folder, _rewrite
from researchguard.research import load_research, research_status, compare_research_status, render_comparison


def test_one_word_quote_change_is_visible(folder):
    before = research_status(load_research(folder))
    _rewrite(folder, 'source.yaml', lambda data: data['anchors'][0].update(text='Recorded text'))
    after = research_status(load_research(folder))
    comparison = compare_research_status(before, after)
    rows = [row for row in comparison['changes'] if row['kind'] == 'evidence quote']
    assert len(rows) == 1 and rows[0]['id'] == 'a'
    shown = render_comparison(comparison)
    assert 'evidence quote changed: a' in shown
    assert 'Observed text' in shown and 'Recorded text' in shown


def test_unchanged_quote_is_not_a_change(folder):
    status = research_status(load_research(folder))
    comparison = compare_research_status(status, status)
    assert not any(row['kind'] == 'evidence quote' for row in comparison['changes'])
