"""Build real, small viewer inputs; do not implement the importance decision."""
from researchguard.logic import load_model_from_dict


def viewer_model(importance):
    return load_model_from_dict({
        'model': {'id': 'viewer-boundary', 'root_claim': 'C'},
        'nodes': {
            'C': {'type': 'Claim', 'text': 'Claim', 'confidence': 1, 'importance': importance},
            'E': {'type': 'Evidence', 'text': 'Evidence', 'confidence': 1, 'importance': 0},
        },
        'edges': [{'source': 'E', 'target': 'C', 'type': 'supports', 'weight': 0.1, 'importance': importance}],
    })
