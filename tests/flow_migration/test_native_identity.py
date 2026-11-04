"""Real identity calls use the shared native adapter in the command's process boundary."""
from pathlib import Path
import subprocess
import sys


def test_identity_flow_observes_native_refusal_and_recovery():
    # Loading a project model refreshes its module namespace. Keep that intended
    # command boundary separate from pytest's already imported production objects.
    root = Path(__file__).resolve().parents[2]
    script = '''from pathlib import Path
import sys
from flowguard.flow.adapter import check_trace, trace_calls
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
root = Path(sys.argv[1])
graph = check_model(load_model(root/'.flowguard/flow/iteration_identity.py', root)).graph
assert graph.complete
calls = {call.action.name:call.index for call in graph.calls}
for actions in (('observe',), ('edit','observe'), ('edit','reset','observe')):
    trace = trace_calls(graph, [calls[name] for name in actions])
    compared = check_trace(graph, trace)
    assert compared.status == 'conformant', compared.to_dict()
    if actions == ('edit','observe'):
        assert compared.native['steps'][-1]['outcome'] == 'refusal'
print('accepted/refused/recovered native identity calls')
'''
    result = subprocess.run([sys.executable, '-c', script, str(root)], cwd=root,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'accepted/refused/recovered' in result.stdout
