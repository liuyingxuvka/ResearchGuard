"""The single viewer boundary still reaches each original public projection."""
import pytest

from researchguard.logic.library_viewer import _graph_edge, _graph_node, _model_counts
from tests.intent_helpers import viewer_model


@pytest.mark.rule('VIEWER_IMPORTANT')
@pytest.mark.parametrize(('importance', 'expected'), [(0.74, False), (0.75, True), (0.76, True)])
@pytest.mark.parametrize('projection', ['count', 'node', 'edge'])
def test_original_viewer_projections(importance, expected, projection):
    model = viewer_model(importance)
    if projection == 'count':
        result = bool(_model_counts(model)['important_node_count'])
    elif projection == 'node':
        result = _graph_node(model, 'C', model.nodes['C'])['markers']['important']
    else:
        result = _graph_edge(model, model.edges[0])['markers']['important']
    assert result is expected
