RG-602: Status survives reference-only evidence and names the real error

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 1 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- changes: research_verdict.evidence_directions_match_routes by R1 "它归在已有规则 `evidence_directions_match_routes` 下：这条证据不产生任何方向行（没有锚点就没有方向）。"
  old rule:
    Invariant('evidence_directions_match_routes', 'Each evidence direction row matches its route model, logic included.', rule(directions_rule))
    def directions_rule(state, question):
        want = {(anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors}
        if question.name != 'native' and set(state.directions) != want:
            return f'evidence directions {sorted(set(state.directions) ^ want)} differ from the route models'
        bad = [row for row in state.directions if row[3] not in ('support', 'oppose', 'limit')]
        if bad:
            return f'unknown directions {bad}'
    def rule(check):
    
        def invariant(state, trace):
            if state.question is None:
                return InvariantResult.pass_()
            problem = check(state, state.question)
            return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
        return invariant
  new rule:
    Invariant('evidence_directions_match_routes', 'Each evidence direction row matches its route model, logic included.', rule(directions_rule))
    def directions_rule(state, question):
        want = {(anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors}
        if question.name != 'native' and set(state.directions) != want:
            return f'evidence directions {sorted(set(state.directions) ^ want)} differ from the route models'
        bad = [row for row in state.directions if row[3] not in ('support', 'oppose', 'limit')]
        if bad:
            return f'unknown directions {bad}'
    def rule(check):
    
        def invariant(state, trace):
            if state.question is None:
                return InvariantResult.pass_()
            problem = check(state, state.question)
            return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
        return invariant
- touch: src/researchguard/research.py:evidence_directions
- touch: src/researchguard/research.py:load_research
- touch: src/researchguard/research.py:status_main
