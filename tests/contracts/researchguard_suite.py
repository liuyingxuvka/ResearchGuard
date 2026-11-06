"""FlowGuard contract model: one researchguard skill, four routes, one console.

It is bound to the real things it describes: the console dispatch
(`src/researchguard/cli.py:_member_main`) and the installer
(`scripts/install_skill.py:main`) are replayed, the route table in
`skills/researchguard/SKILL.md` and the skill folders are read as code facts,
and the package member table `researchguard.MEMBER_IDS` is compared.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
ROUTES = {'argument_licensing': ('logic', 'logicguard'), 'evidence_discovery': ('source', 'sourceguard'), 'trace_reconstruction': ('trace', 'traceguard'), 'experiment_discrimination': ('experiment', 'experimentguard')}
MEMBER_BY_ROUTE = dict(ROUTES.values())
RETIRED_SKILLS = ('logicguard', 'sourceguard', 'traceguard', 'experimentguard')
FAILURES = {'failed', 'blocked', 'stale', 'timeout', 'unsupported', 'unavailable'}

@dataclass(frozen=True)
class ResearchRequest:
    intent: str
    loaded_route_files: int = 1
    native_status: str = 'pass'
    handoff_target: str = ''
    run_handoff: bool = False
    already_routed: bool = False

@dataclass(frozen=True)
class RouteState:
    phase: str = 'unrouted'
    route: str = ''
    member: str = ''
    terminal_status: str = ''
    handoff_target: str = ''
    alternate_attempts: int = 0

def expected_PickRoute(request: ResearchRequest, state: RouteState, mutation=''):
    if request.already_routed or state.phase != 'unrouted':
        return replace(state, phase='blocked', terminal_status='recursion')
        return
    selected = ROUTES.get(request.intent)
    if selected is None:
        return replace(state, phase='blocked', terminal_status='no_route')
        return
    route, member = selected
    return replace(state, phase='routed', route=route, member=member)

def expected_LoadRouteFile(request: ResearchRequest, state: RouteState, mutation=''):
    if state.phase != 'routed':
        return state
        return
    if request.loaded_route_files != 1:
        return replace(state, phase='blocked', terminal_status='route_load_invalid')
        return
    return state

def expected_RunRoute(request: ResearchRequest, state: RouteState, mutation=''):
    if state.phase != 'routed':
        return state
        return
    if request.native_status != 'pass':
        return replace(state, phase='terminal', terminal_status=request.native_status)
        return
    if request.handoff_target:
        return replace(state, phase='awaiting_owner', terminal_status='handoff_requested', handoff_target=request.handoff_target)
        return
    return replace(state, phase='terminal', terminal_status='pass')

def expected_FollowHandoff(request: ResearchRequest, state: RouteState, mutation=''):
    if state.phase != 'awaiting_owner':
        return state
        return
    if not request.run_handoff:
        return state
        return
    member = MEMBER_BY_ROUTE.get(state.handoff_target)
    if member is None:
        return replace(state, phase='blocked', terminal_status='invalid_handoff')
        return
    return replace(state, phase='routed', route=state.handoff_target, member=member, terminal_status='', handoff_target='')

def _no_alternate_success(state: RouteState) -> bool:
    if state.alternate_attempts:
        return False
    return True

def _failure_stays_terminal(state: RouteState) -> bool:
    if state.terminal_status in FAILURES and state.phase != 'terminal':
        return False
    return True

def _route_matches_member(state: RouteState) -> bool:
    if state.route and MEMBER_BY_ROUTE.get(state.route) != state.member:
        return False
    return True
RULES = (_no_alternate_success, _failure_stays_terminal, _route_matches_member)

def assert_native_contract():
    import contextlib
    import importlib.util
    import io
    import sys
    import tempfile
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    from researchguard import MEMBER_IDS
    from researchguard.cli import _member_main, main
    observations = []
    violations = []

    def check(rule: str, expected, actual) -> None:
        if expected != actual:
            violations.append(f'{rule}: expected {expected!r}, got {actual!r}')
    for intent, (route, member) in ROUTES.items():
        picked = expected_PickRoute(ResearchRequest(intent), RouteState())
        check(f'route:{route}', f'researchguard.{picked.route}.cli', _member_main(picked.member).__module__)
    with contextlib.redirect_stdout(io.StringIO()):
        check('retired_umbrella_run', 2, main(['run']))
    sync_help = io.StringIO()
    with contextlib.redirect_stdout(sync_help):
        try:
            sync_exit = main(['sync', '--help'])
        except SystemExit as exc:
            sync_exit = exc.code
    check('sync_public_command', 0, sync_exit)
    check('sync_help', True, 'researchguard sync' in sync_help.getvalue())
    check('member_ids', tuple(MEMBER_BY_ROUTE.values()), tuple(MEMBER_IDS))
    skill = (root / 'skills' / 'researchguard' / 'SKILL.md').read_text(encoding='utf-8')
    for route in MEMBER_BY_ROUTE:
        reference = f'references/routes/{route}.md'
        check(f'route_file:{route}', True, reference in skill and (root / 'skills' / 'researchguard' / reference).is_file())
    check('skill_dirs', ['researchguard'], sorted((path.name for path in (root / 'skills').iterdir() if path.is_dir())))
    spec = importlib.util.spec_from_file_location('researchguard_install_skill', root / 'scripts' / 'install_skill.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    saved_argv = sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'skills'
        for name in RETIRED_SKILLS:
            (target / name).mkdir(parents=True)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                sys.argv = ['install_skill.py', '--target', str(target)]
                installed = installer.main()
                sys.argv = ['install_skill.py', '--target', str(target), '--check']
                checked = installer.main()
        finally:
            sys.argv = saved_argv
        check('install', (0, 0, ['researchguard']), (installed, checked, sorted((path.name for path in target.iterdir()))))
    assert not violations, violations
RULE_NAMES = ('no_alternate_success', 'terminal_failure_stays_terminal', 'route_matches_member')
