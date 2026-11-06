"""One visual classification must not drift between card count and graph markers."""
from flowguard.intent import rule, row, structure_rule


@rule('VIEWER_IMPORTANT', decides='viewer importance marker', fields={'importance': float},
      source='doc docs/development/intent-contracts.md "The viewer counts and marks an element important when its declared/inferred importance is at least 0.75."')
def VIEWER_IMPORTANT(importance):
    """The viewer count and both graph markers share the 0.75 boundary."""
    if not 0 <= importance <= 1:
        return None
    return importance >= 0.75


VIEWER_IMPORTANT.rows(
    row(importance=0.74, expect=False, why='an element below the display threshold is not marked'),
    row(importance=0.75, expect=True, why='the shared display boundary is inclusive'),
    row(importance=0.76, expect=True, why='an element above the shared threshold remains visible'))


@VIEWER_IMPORTANT.home('researchguard.logic.library_viewer:_is_important')
def viewer_boundary(c, fn):
    return fn(c.importance)


@structure_rule('VIEWER_IMPORTANT_OWNER',
    source='doc docs/development/intent-contracts.md "The viewer count and both graph markers call the same importance decision owner."')
def viewer_uses_one_owner(graph):
    owner = '_is_important'
    callers = ('_model_counts', '_graph_node', '_graph_edge')
    calls = {(call['node'], call['resolved']) for call in graph.calls()}
    return [f'researchguard.logic.library_viewer:{name}' for name in callers
            if (f'researchguard.logic.library_viewer:{name}', owner) not in calls]
