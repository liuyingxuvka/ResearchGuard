"""FlowGuard contract model: SourceGuard blocks a contentless anchor with one finding.

Bound to the real code: conformance replays `_anchor_depth_rows` with and
without anchor content and reads `src/researchguard/source/depth.py` to check
that it emits the declared finding and never the retired one.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
DECLARED_FINDING = 'sourceguard_blocked:contentless-anchor'
RETIRED_FINDING = 'no_content_qualified_anchor'

@dataclass(frozen=True)
class AnchorDepthInput:
    case_id: str
    content_qualified: bool
    emitted_findings: tuple[str, ...]

@dataclass(frozen=True)
class AnchorDepthState:
    case_id: str = 'not_run'
    content_qualified: bool = True
    depth_status: str = 'not_run'
    emitted_findings: tuple[str, ...] = ()
    check_status: str = 'not_run'
    added_source_present: bool = True
CONTENT_GOOD = AnchorDepthInput(case_id='content-bearing-known-good', content_qualified=True, emitted_findings=())
CONTENT_BAD_ALIGNED = AnchorDepthInput(case_id='contentless-known-bad-aligned', content_qualified=False, emitted_findings=(DECLARED_FINDING,))
CONTENT_BAD_DRIFTED = AnchorDepthInput(case_id='contentless-known-bad-drifted', content_qualified=False, emitted_findings=(RETIRED_FINDING,))

def expected_EvaluateContentAnchorFinding(input_obj: AnchorDepthInput, state: AnchorDepthState, mutation=''):
    del state
    blocked = not input_obj.content_qualified
    finding_matches = DECLARED_FINDING in input_obj.emitted_findings
    return AnchorDepthState(case_id=input_obj.case_id, content_qualified=input_obj.content_qualified, depth_status='blocked' if blocked else 'pass', emitted_findings=input_obj.emitted_findings, added_source_present=not mutation, check_status='blocked_proven' if blocked and finding_matches else 'good_proven' if not blocked and (not finding_matches) else 'identity_mismatch')

def content_anchor_identity_is_singular(state: AnchorDepthState) -> bool:
    if state.check_status == 'not_run':
        return True
    findings = set(state.emitted_findings)
    if state.content_qualified:
        if DECLARED_FINDING in findings or state.depth_status != 'pass':
            return False
        return True
    if state.depth_status != 'blocked' or DECLARED_FINDING not in findings:
        return False
    if RETIRED_FINDING in findings:
        return False
    return True

def added_anchor_belongs_to_its_source(state):
    if state.added_source_present:
        return True
    return False
RULES = (added_anchor_belongs_to_its_source, content_anchor_identity_is_singular)

def assert_native_contract():
    import sys
    from pathlib import Path
    from researchguard.source.depth import _anchor_depth_rows
    from researchguard.source.schema import BeliefState, EvidenceAnchor, SourceRecord
    observations = []
    violations = []
    for content in (True, False):
        state = BeliefState(sources=[SourceRecord(source_id='source:model', source_type='paper', source_role='primary_source', source_reliability=0.95, access_status='public')], anchors=[EvidenceAnchor(anchor_id='anchor:model', source_id='source:model', anchor_type='paragraph', locator='paragraph:1', modality='text', text='observed content' if content else '', extraction_confidence=0.95, specificity=0.95, supports=['gap:model'], usable_for_claim=True)])
        qualified = bool(_anchor_depth_rows(state)[0]['qualified'])
        if qualified != content:
            violations.append(f'native content qualification differs: {content}')
    from researchguard.source.update import add_anchor
    added = add_anchor(BeliefState(), EvidenceAnchor(anchor_id='new-a', source_id='new-s', text='quote'), source=SourceRecord(source_id='new-s', title='A named report'))
    present = any((row.source_id == 'new-s' for row in added.sources))
    if not present:
        violations.append('added anchor has no source')
    source = (Path(__file__).resolve().parents[2] / 'src' / 'researchguard' / 'source' / 'depth.py').read_text(encoding='utf-8')
    emitted = (f'"{DECLARED_FINDING}"' in source, f'"{RETIRED_FINDING}"' in source)
    if emitted != (True, False):
        violations.append(f'depth.py finding identity differs: declared/retired present = {emitted}')
    assert not violations, violations
RULE_NAMES = ('added_anchor_belongs_to_its_source', 'content_anchor_identity_is_singular')
