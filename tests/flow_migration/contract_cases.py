"""Finite original contract cases and bad facts, without a model runner or validator."""
from dataclasses import replace
from importlib import import_module

TOPICS = ('experiment_elimination', 'iteration_kernel', 'research_ablations', 'research_tree',
          'research_verdict', 'research_views', 'researchguard_suite', 'source_library',
          'sourceguard_content_anchor', 'sourceguard_stop_decision', 'synthesis_plan',
          'trace_projection', 'wording_license')
EXPECTED = {'experiment_elimination':'Observe','iteration_kernel':'Check','research_ablations':'Status',
            'research_tree':'Status','research_verdict':'Status','research_views':'Status',
            'source_library':'Library','sourceguard_content_anchor':'EvaluateContentAnchorFinding',
            'sourceguard_stop_decision':'StopDecision','synthesis_plan':'Synthesize',
            'trace_projection':'Project','wording_license':'License'}

def module(topic):
    return import_module('tests.flow_migration.' + topic)

def cases(topic):
    m = module(topic)
    if topic == 'iteration_kernel': return tuple(m.EXPECTED)
    if topic == 'sourceguard_content_anchor': return (m.CONTENT_GOOD, m.CONTENT_BAD_ALIGNED)
    if topic == 'researchguard_suite':
        return (m.ResearchRequest('argument_licensing'), m.ResearchRequest('experiment_discrimination'),
                m.ResearchRequest('evidence_discovery', native_status='failed'),
                m.ResearchRequest('argument_licensing', handoff_target='source'),
                m.ResearchRequest('trace_reconstruction', handoff_target='logic', run_handoff=True),
                m.ResearchRequest('trace_reconstruction', already_routed=True),
                m.ResearchRequest('argument_licensing', loaded_route_files=2), m.ResearchRequest('write_the_report'))
    result = tuple(m.CASES) + tuple(getattr(m, 'UNANCHORED_CASES', ())) + tuple(getattr(m, 'SUMMARY_CASES', ()))
    if topic == 'research_views':
        result += (m.SyncQuestion('sync_unchanged', ()),
                   m.SyncQuestion('sync_added_anchor', (), new_anchor='anc-new', new_source='src-new'),
                   m.SyncQuestion('sync_added_unverifiable_source', (), new_anchor='anc-new', new_source='src-new', unverifiable=True),
                   m.SyncQuestion('sync_conflict', (), new_anchor='anc-new', conflict=True))
    return result

def expected(topic, case, mutation=''):
    m = module(topic)
    if topic == 'researchguard_suite':
        state = m.expected_PickRoute(case, m.RouteState())
        state = m.expected_LoadRouteFile(case, state)
        state = m.expected_RunRoute(case, state)
        state = m.expected_FollowHandoff(case, state)
        if mutation == 'wrong_member' and state.route == 'logic': state = replace(state, member='sourceguard')
        elif mutation == 'alternate_route': state = replace(state, alternate_attempts=1)
        elif mutation == 'reroute_on_failure' and state.terminal_status in m.FAILURES: state = replace(state, phase='routed')
        return state
    initial = m.DecisionState() if topic == 'sourceguard_stop_decision' else m.AnchorDepthState() if topic == 'sourceguard_content_anchor' else m.State()
    result = getattr(m, 'expected_' + EXPECTED[topic])(case, initial, mutation=mutation)
    if topic == 'sourceguard_stop_decision':
        if mutation == 'generated_twin_outranks_declared': result = replace(result, search_order=tuple(reversed(result.search_order)))
        elif mutation == 'unsafe_stop': result = replace(result, status='stop_sufficient')
        elif mutation == 'unaffordable_continue': result = replace(result, status='continue_search', selected='search')
        elif mutation == 'optional_never_stops': result = replace(result, status='continue_search', selected='followup')
        elif mutation == 'top_action_only' and case.candidates:
            top = sorted(case.candidates, key=lambda item: (-item.utility, item.action_id))[0]
            affordable = top.target in case.critical and top.cost <= case.budget
            result = replace(result, status='continue_search' if affordable else 'blocked_unresolved_critical', selected=top.action_id if affordable else '')
        elif mutation == 'value_vs_cost' and case.candidates and case.candidates[0].utility <= case.candidates[0].cost:
            result = replace(result, status='blocked_unresolved_critical', selected='')
    return result

def mutations(topic):
    m = module(topic)
    if hasattr(m, 'MUTATIONS'): return dict(m.MUTATIONS)
    if topic == 'iteration_kernel':
        return {'ignore_stale':m.RULE_NAMES[0], 'ignore_same_path':m.RULE_NAMES[1],
                'ignore_same_content':m.RULE_NAMES[1], 'ignore_stalled':m.RULE_NAMES[2], 'ignore_limit':m.RULE_NAMES[3]}
    if topic == 'wording_license':
        return {'assert_despite_blocker':m.RULE_NAMES[0], 'assert_without_support':m.RULE_NAMES[1], 'qualify_upgraded_to_assert':m.RULE_NAMES[2]}
    if topic == 'sourceguard_stop_decision':
        return dict(zip(('generated_twin_outranks_declared','unsafe_stop','unaffordable_continue','optional_never_stops','top_action_only','value_vs_cost'),
                        (m.RULE_NAMES[0],m.RULE_NAMES[1],m.RULE_NAMES[2],m.RULE_NAMES[3],m.RULE_NAMES[4],m.RULE_NAMES[4])))
    if topic == 'sourceguard_content_anchor':
        return {'anchor_added_without_source':m.RULE_NAMES[0], 'retired_finding':m.RULE_NAMES[1]}
    if topic == 'researchguard_suite':
        return {'wrong_member':m.RULE_NAMES[2], 'alternate_route':m.RULE_NAMES[0], 'reroute_on_failure':m.RULE_NAMES[1]}
    raise AssertionError(topic)

def bad_states(topic, mutation):
    m = module(topic)
    if topic == 'sourceguard_content_anchor':
        case = m.CONTENT_BAD_DRIFTED if mutation == 'retired_finding' else m.CONTENT_GOOD
        return (expected(topic, case, mutation == 'anchor_added_without_source'),)
    mapped = mutation.removeprefix('ignore_') if topic == 'iteration_kernel' else {
        'assert_despite_blocker':'blocked','assert_without_support':'unsupported','qualify_upgraded_to_assert':'qualified'}.get(mutation,mutation)
    return tuple(expected(topic, case, mapped) for case in cases(topic))
