RG-604: Logic evidence without a source anchor is an error when a source model exists

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 1 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- changes: research_tree_crossref.unanchored_evidence_is_an_error by R1 "新建规则 `unanchored_evidence_is_an_error`（说明 “when the folder lists a source model, logic evidence without a source anchor is an error”）"
  old rule:
    (absent: this rule did not exist)
  new rule:
    Invariant('unanchored_evidence_is_an_error', 'When the folder lists a source model, logic evidence without a source anchor is an error; without a source model it is informational.', rule(unanchored_rule))
    UNANCHORED_ERROR = 'evidence_not_in_source:logic:E_reference (its provenance names no source_id; add the anchor with researchguard source add-anchor, then run researchguard sync <folder>)'
    def rule(check):
    
        def invariant(state, trace):
            if state.question is None:
                return InvariantResult.pass_()
            problem = check(state, state.question)
            return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
        return invariant
    def unanchored_rule(state, question):
        if question.name == 'unanchored_source' and UNANCHORED_ERROR not in state.errors:
            return 'logic evidence without a source_id must be an error when a source model is listed'
        if question.name == 'unanchored_no_source' and any((code.startswith('evidence_not_in_source:') for code in state.errors)):
            return 'without a source model, unanchored evidence is informational, not an error'
- touch: src/researchguard/research.py:check_research_tree
