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


@pytest.mark.parametrize('url,reason', [
    # Review round 4: a port that is no number counted as a link, and a valid IPv6 link was called no link at all.
    ('https://slack.com:abc/', "the port 'abc' of https://slack.com:abc/ is not a number from 0 to 65535"),
    ('https://slack.com:99999/x', "the port '99999' of https://slack.com:99999/x is not a number from 0 to 65535"),
    ('https://slack.com:80:90/x', "the port '80:90' of https://slack.com:80:90/x is not a number from 0 to 65535"),
    ('http://[::1]/x', 'the host ::1 of http://[::1]/x is a loopback IP address, not a public host name'),
    ('https://[2001:DB8::1]:8443/x', 'the host 2001:db8::1 of https://[2001:DB8::1]:8443/x is an IP address, not a public host name'),
    ('http://[::ffff:192.0.2.1]/x', 'the host ::ffff:192.0.2.1 of http://[::ffff:192.0.2.1]/x is an IP address, not a public host name'),
    ('https://127.0.0.1/x', 'the host 127.0.0.1 of https://127.0.0.1/x is a loopback IP address, not a public host name'),
    ('https://10.0.0.1:8080/x', 'the host 10.0.0.1 of https://10.0.0.1:8080/x is an IP address, not a public host name'),
    ('https://[zz]/x', "'https://[zz]/x' is not an http or https link, a DOI, an ISBN or an arXiv id"),
    ('https://[::1/x', "'https://[::1/x' is not an http or https link, a DOI, an ISBN or an arXiv id"),
    ('https://[1.2.3.4]/x', "'https://[1.2.3.4]/x' is not an http or https link, a DOI, an ISBN or an arXiv id"),
    ('https://[::1]x/', "'https://[::1]x/' is not an http or https link, a DOI, an ISBN or an arXiv id"),
    ('https://[fe80::1%25eth0]/x', "'https://[fe80::1%25eth0]/x' is not an http or https link, a DOI, an ISBN or an arXiv id"),
])
def test_why_a_link_is_not_an_outside_locator(url, reason):
    from researchguard.source.update import outside_locator
    assert outside_locator(url) == ('', reason)


@pytest.mark.parametrize('url,well_formed', [
    ('https://slack.com:abc/', False),
    ('https://slack.com:99999/x', False),
    ('https://slack.com:/x', True),        # an empty port is allowed by the URL standard
    ('https://slack.com:65535/x', True),
    ('https://slack.com:000080/x', True),
    ('https://slack.com:000000/x', True),
    ('https://slack.com:00065535/x', True),
    ('https://slack.com:00065536/x', False),
    ('http://[::1]/x', True),              # a well-formed link, but no outside locator
    ('https://[2001:db8::1]/x', True),
    ('https://[zz]/x', False),
])
def test_a_link_with_a_bad_port_is_malformed_and_an_ip_literal_is_not(url, well_formed):
    from researchguard.source.update import source_identity
    identity = source_identity(SourceRecord(source_id='src', title="Lloyd's List", url=url))
    assert (not identity.problems) is well_formed, identity.problems
    public = url.startswith('https://slack.com:') and well_formed
    assert bool(identity.unverifiable) is not public, identity.unverifiable


def test_no_url_makes_the_locator_check_raise():
    import random
    from researchguard.source.update import outside_locator, source_identity
    rng = random.Random(801)
    for _ in range(20000):
        url = rng.choice(('https://', 'http://', 'HTTP://', '')) + ''.join(
            rng.choice('[]:@/?#.%-a1fz:[]') for _ in range(rng.randint(0, 24)))
        kind, reason = outside_locator(url)
        assert bool(kind) is not bool(reason), url
        source_identity(SourceRecord(source_id='src', title='T', url=url))


def test_the_ipv6_check_accepts_exactly_what_the_address_parser_accepts():
    """The URL parser and ipaddress raise on a bracketed host they reject, so ResearchGuard checks it first."""
    import ipaddress
    import random
    from researchguard.source.update import _ipv6_literal
    rng = random.Random(803)
    samples = ['::', '::1', '1::', '1:2:3:4:5:6:7:8', '1:2:3:4:5:6:7::', '::2:3:4:5:6:7:8', '1:2:3:4:5:6:7:8:9', '1:2:3',
               ':1::2', '1::2::3', '::ffff:1.2.3.4', '::ffff:01.2.3.4', '1:2:3:4:5:6:1.2.3.4', '1:2:3:4:5:6:7:1.2.3.4',
               '12345::', 'g::', '::1.2.3', '::256.1.1.1', '', ':', ':::', '1:', ':1', '::1%eth0', '1:2:3:4:5:6:7:8::']
    samples += [''.join(rng.choice('0123456789abcdefABCDEF:.g%') for _ in range(rng.randint(0, 40))) for _ in range(20000)]
    for text in samples:
        try:
            expected = isinstance(ipaddress.ip_address(text), ipaddress.IPv6Address) and '%' not in text
        except ValueError:
            expected = False
        assert _ipv6_literal(text) is expected, text


def test_a_title_never_makes_a_source_verifiable():
    from researchguard.source.update import source_identity
    for title in ("Colleague's note, 2021", 'Slack message', 'Personal communication, J. Smith',
                  "Lloyd's List, 29 March 2021, p. 3", 'https://www.lloydslist.com/ (title only)'):
        identity = source_identity(SourceRecord(source_id='src', title=title, source_date='2021-04'))
        assert identity.unverifiable, title
    assert not source_identity(SourceRecord(source_id='src', title='x', url='https://www.lloydslist.com/a')).unverifiable
