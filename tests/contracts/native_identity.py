"""Declared edit/reset stimuli around the real shared identity owner, not a validator."""
from researchguard.iteration import baseline_identity, require_prediction_identity

class IdentityWorld:
    def __init__(self):
        self.current = 0
        self.accepted = False
        self.frozen = baseline_identity({'n': 0})

    def edit(self):
        self.current, self.accepted = 1, False

    def reset(self):
        self.current, self.accepted = 0, False

    def observe(self):
        require_prediction_identity(self.frozen, baseline_identity({'n': self.current}))
        self.accepted = True
