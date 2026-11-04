"""An observation must match its frozen baseline; a changed baseline is refused.

Only this finite identity boundary is native-backed. Other kernel contracts remain
independent production unit tests; this model makes no inference about every workflow.
"""
from flowguard.flow import Model, need
from flowguard.flow.adapter import fields
m = Model('frozen iteration identity', covers=['src/researchguard/iteration.py'])
m.field('current', (0, 1), 0)
m.field('accepted', (False, True), False)
@m.action()
def edit(s):
    s['current'], s['accepted'] = 1, False
@m.action()
def reset(s):
    s['current'], s['accepted'] = 0, False
@m.action()
def observe(s):
    need(s['current'] == 0, 'the current baseline must match the frozen prediction')
    s['accepted'] = True
m.always('stale_prediction_is_refused', lambda s: s['current'] == 0 or not s['accepted'])
m.after('editing marks the new baseline', 'edit', lambda before, after: after['current'] == 1)
m.after('reset invalidates an earlier observation', 'reset', lambda before, after: not after['accepted'])
m.reach('a matching prediction is observed', lambda s: s['accepted'])
m.bind_adapter({'system':'tests.flow_migration.native_identity:IdentityWorld',
                'classes':['tests.flow_migration.native_identity:IdentityWorld'], 'refusal':['builtins:ValueError']},
               state=lambda snapshot: fields(snapshot, names=('current', 'accepted')),
               operations={'edit':'edit','reset':'reset','observe':'observe'})
MODEL = m
