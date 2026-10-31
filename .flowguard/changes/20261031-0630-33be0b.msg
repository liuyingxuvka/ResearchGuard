RG-605: A number in an evidence summary must occur in its quote or anchor

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 1 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- changes: research_verdict.summary_numbers_come_from_the_source by R1 "新建规则 `summary_numbers_come_from_the_source`（说明 “a number in an evidence summary that occurs in neither its quote nor its anchor is warned once”）"
  old rule:
    (absent: this rule did not exist)
  new rule:
    Invariant('summary_numbers_come_from_the_source', 'A literal number absent from the evidence quote and matched anchor is warned once per node.', rule(summary_numbers_rule))
    def rule(check):
    
        def invariant(state, trace):
            if state.question is None:
                return InvariantResult.pass_()
            problem = check(state, state.question)
            return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
        return invariant
    def summary_numbers_rule(state, question):
        expected = summary_warnings(question)
        if sorted(state.summary_warnings) != sorted(expected):
            return f'summary warnings {state.summary_warnings} != {expected} (one warning per node, literal source tokens)'
    def summary_warnings(question):
        return tuple((f'summary_number_not_in_quote:{node}' for node, summary, source in getattr(question, 'summaries', ()) if any((number not in source for number in summary))))
- touch: src/researchguard/research.py:research_status
