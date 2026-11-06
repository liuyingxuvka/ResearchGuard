"""The real frozen identity gate accepts, refuses stale input and recovers after reset."""
import pytest
from .native_identity import IdentityWorld


@pytest.mark.parametrize('actions,expected,refused', [
    (('observe',), (0, True), False),
    (('edit', 'observe'), (1, False), True),
    (('edit', 'reset', 'observe'), (0, True), False),
])
def test_identity_flow_observes_native_refusal_and_recovery(actions, expected, refused):
    world = IdentityWorld()
    for action in actions[:-1]:
        getattr(world, action)()
    if refused:
        with pytest.raises(ValueError, match='stale_prediction: re-freeze'):
            world.observe()
    else:
        world.observe()
    assert (world.current, world.accepted) == expected
