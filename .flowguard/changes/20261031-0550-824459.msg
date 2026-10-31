RG-603: One sync command; a synced folder syncs to no change

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 0 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- changes: research_views.sync_changes_only_the_new_anchor by R1 "新建规则 `sync_changes_only_the_new_anchor`（说明 “a sync of an unchanged folder changes nothing; after one added anchor, the candidate view shows only that anchor”）。"
  old rule:
    (absent: this rule did not exist)
  new rule:
    Invariant('sync_changes_only_the_new_anchor', 'A sync of an unchanged folder changes nothing; after one added anchor, the candidate view shows only that anchor; a conflict writes nothing.', rule(sync_rule))
    def rule(check):
    
        def invariant(state, trace):
            if state.question is None:
                return InvariantResult.pass_()
            problem = check(state, state.question)
            return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
        return invariant
    def sync_rule(state, question):
        if isinstance(question, SyncQuestion):
            want = (('evidence', question.new_anchor),) if question.new_anchor and (not question.conflict) else ()
            if state.changes != want:
                return f'sync changed {state.changes}, expected only {want}'
- touch: src/researchguard/research.py:sync_main
- touch: src/researchguard/cli.py:main
- touch: src/researchguard/cli.py:_print_help
