from researchguard.source.schema import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    Observation,
    SourceRecord,
)
from researchguard.source.update import apply_observation


def _guard(state: BeliefState, model_id: str) -> BeliefState:
    return state


def test_observation_can_add_source_and_anchor():
    state = _guard(BeliefState(), "test-update-add-source")
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1", title="Paper s1", source_type="paper")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", anchor_type="paragraph", locator="section=1", modality="text")],
    )
    updated = apply_observation(state, obs)
    assert updated.sources[0].source_id == "s1"
    assert updated.anchors[0].anchor_id == "a1"


def test_permission_gated_source_does_not_close_gap():
    state = _guard(
        BeliefState(gaps=[Gap(gap_id="g1", gap_type="missing_primary_source")]),
        "test-update-permission",
    )
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1", title="Gated report s1", source_status="permission_gated", access_status="permission_gated")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", locator="page=1", supports=["g1"], modality="pdf_page")],
    )
    updated = apply_observation(state, obs)
    assert updated.gaps[0].semantic_state == "blocked"
    assert updated.metadata["warnings"]


def test_missing_locator_produces_warning():
    state = _guard(BeliefState(), "test-update-locator")
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1", title="Image source s1")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", modality="image")],
    )
    updated = apply_observation(state, obs)
    assert any("no locator" in warning.lower() for warning in updated.metadata["warnings"])


def test_counterevidence_does_not_overwrite_support():
    state = _guard(
        BeliefState(gaps=[Gap(gap_id="g1", gap_type="one_sided_support")]),
        "test-update-counterevidence",
    )
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s-counter", title="Counter report", source_role="counter_evidence")],
    )
    updated = apply_observation(state, obs)
    assert any(gap.gap_id == "g1" and gap.semantic_state == "discovered" for gap in updated.gaps)
    assert any(gap.gap_type == "contradiction" for gap in updated.gaps)


import pytest


@pytest.mark.parametrize('url,kind', [
    ('https://www.lloydslist.com/LL1136183/Rates', 'link'),
    ('https://www.suezcanal.gov.eg/', 'link'),
    ('http://例子.中国/x', 'link'),
    ('https://user@WWW.Example-Press.co.uk:8443/a?b=c', 'link'),
    ('doi:10.1000/xyz123', 'DOI'),
    ('10.1000/xyz123', 'DOI'),
    ('isbn:978-0-13-110362-7', 'ISBN'),
    ('ISBN 0-13-110362-8', 'ISBN'),
    ('urn:isbn:9780131103627', 'ISBN'),
    ('arXiv:2101.01234v2', 'arXiv id'),
    ('arxiv:hep-th/9901001', 'arXiv id'),
])
def test_an_outside_locator_is_a_link_doi_isbn_or_arxiv_id_the_tool_can_parse(url, kind):
    from researchguard.source.update import outside_locator
    assert outside_locator(url) == (kind, '')


@pytest.mark.parametrize('url', [
    '',
    'Slack message',
    'email 2021',
    'https://example.org/lloyds',          # reserved for examples
    'https://www.example.com/a',
    'https://notes.local/bob',            # not a top-level domain of the root zone
    'https://intranet.internal/memo',
    'https://colleague.note/bob',
    'https://bob',
    'http://localhost/x',
    'https://127.0.0.1/x',                # an address, not a host name
    'https://[2001:db8::1]/x',
    'https://[zz]/x',                     # used to raise inside the URL parser
    'https://1.0.0.127.in-addr.arpa/',
    'https://abc.onion/',
    'ftp://ftp.lloydslist.com/x',
    'isbn:978-0-13-110362-8',             # wrong check digit
    'arXiv:2113.01234',                   # no month 13
])
def test_anything_else_is_not_an_outside_locator_and_says_why(url):
    from researchguard.source.update import outside_locator
    kind, reason = outside_locator(url)
    assert kind == '' and reason


def test_a_title_never_makes_a_source_verifiable():
    from researchguard.source.update import source_identity
    for title in ("Colleague's note, 2021", 'Slack message', 'Personal communication, J. Smith',
                  "Lloyd's List, 29 March 2021, p. 3", 'https://www.lloydslist.com/ (title only)'):
        identity = source_identity(SourceRecord(source_id='src', title=title, source_date='2021-04'))
        assert identity.unverifiable, title
    assert not source_identity(SourceRecord(source_id='src', title='x', url='https://www.lloydslist.com/a')).unverifiable
