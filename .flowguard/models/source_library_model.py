"""Personal source library: imports deduplicate by content, links need a selected source, deleting a project keeps sources."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'source_library'
PARENT = 'logic-library'
COMPONENTS = ['logic-library']
IMPLEMENTED_BY = {'Import': 'src/researchguard/logic/source_library.py:SourceLibrary.import_source',
                  'Link': 'src/researchguard/logic/source_library.py:SourceLibrary.link_node',
                  'DeleteProject': 'src/researchguard/logic/source_library.py:SourceLibrary.delete_project'}
TESTED_BY = {
    'import_deduplicates_by_content_hash': ['tests/logic/test_source_library.py:test_import_source_deduplicates_by_content_hash'],
    'project_link_requires_selected_source': ['tests/logic/test_source_library.py:test_project_link_requires_selected_source'],
    'deleting_a_project_keeps_sources': ['tests/logic/test_source_library.py:test_delete_project_removes_project_relationships_without_deleting_sources_or_models',
                                         'tests/logic/test_source_library.py:test_project_branch_uses_references_not_source_copies'],
}
NOT_MODELED = {
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._build_layout': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_card': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_card_surface': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_dissolve_project_badge': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_export_badge': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_gradient_surface': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_import_badge': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._draw_update_badge': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._footer_row': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._load_image_assets': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._load_source_view': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._load_status_view': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._load_type_view': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._move_selection': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._nav_row': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._on_card_click': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._on_card_leave': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._on_card_motion': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._on_main_configure': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._on_sidebar_click': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._perform_search': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._render_footer': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._render_main': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._render_sidebar': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._route_row': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._run_scheduled_search': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._schedule_search': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._section_row': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp._set_searching': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp.load_route': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
    'src/researchguard/logic_viewer/desktop_app.py:KbDesktopApp.open_selected_detail': 'Desktop viewer drawing and event handlers (optional viewer extra); they read the library through SourceLibrary and change only window state.',
}


@dataclass(frozen=True)
class Operation:
    """One library operation: import the same content twice, link with or without selection, delete a project."""
    name: str
    imports_of_same_content: int = 0
    selected: bool = False
    link: bool = False
    delete_project: bool = False


@dataclass(frozen=True)
class State:
    operation: Operation | None = None
    sources: int = 0
    link_accepted: bool = False
    sources_after_delete: int = 0


class Library:
    name = 'Library'
    reads = ('operation',)
    writes = ('sources', 'link_accepted', 'sources_after_delete')
    mutation = ''

    def apply(self, operation, state):
        sources = operation.imports_of_same_content if self.mutation == 'duplicate_import_adds_a_source' else min(operation.imports_of_same_content, 1)
        accepted = operation.link and (operation.selected or self.mutation == 'link_without_selected_source')
        after = 0 if operation.delete_project and self.mutation == 'delete_project_deletes_sources' else sources
        result = State(operation, sources, accepted, after)
        yield FunctionResult(result, result, label=operation.name)


def rule(check):
    def invariant(state, trace):
        if state.operation is None:
            return InvariantResult.pass_()
        problem = check(state, state.operation)
        return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
    return invariant


def dedup_rule(state, operation):
    if operation.imports_of_same_content and state.sources != 1:
        return f'{operation.imports_of_same_content} imports of one content made {state.sources} sources'


def link_rule(state, operation):
    if state.link_accepted and not operation.selected:
        return 'a project linked a node of a source it did not select'


def delete_rule(state, operation):
    if operation.delete_project and state.sources_after_delete != state.sources:
        return 'deleting a project deleted library sources'


INVARIANTS = (
    Invariant('import_deduplicates_by_content_hash', 'Importing the same content again reuses the existing source.', rule(dedup_rule)),
    Invariant('project_link_requires_selected_source', 'A project links only nodes of sources it selected.', rule(link_rule)),
    Invariant('deleting_a_project_keeps_sources', 'Deleting a project removes its relationships and keeps every source.', rule(delete_rule)),
)
CASES = (
    Operation('reimport', imports_of_same_content=2),
    Operation('link_unselected', imports_of_same_content=1, link=True),
    Operation('link_selected', imports_of_same_content=1, selected=True, link=True),
    Operation('delete', imports_of_same_content=1, selected=True, delete_project=True),
)
MUTATIONS = {
    'duplicate_import_adds_a_source': 'import_deduplicates_by_content_hash',
    'link_without_selected_source': 'project_link_requires_selected_source',
    'delete_project_deletes_sources': 'deleting_a_project_keeps_sources',
}


def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Library())


def broken_variants():
    result = {}
    for name in MUTATIONS:
        step = Library()
        step.mutation = name
        result[name] = explorer(step)
    return result


def native_state(operation):
    """Run the operation on a real SourceLibrary in a temporary directory."""
    from researchguard.logic.source_library import SourceLibrary, SourceLibraryError
    with TemporaryDirectory() as directory:
        root = Path(directory)
        paper = root / 'paper.txt'
        paper.write_text('AI tools reduce task time in controlled maintenance tasks.', encoding='utf-8')
        library = SourceLibrary(root / 'library')
        imported = None
        for _ in range(operation.imports_of_same_content):
            imported = library.import_source(paper, title='Paper')
        sources = sum(1 for _ in (root / 'library' / 'sources').iterdir())
        accepted, after = False, sources
        if operation.link or operation.delete_project:
            library.create_source_model(imported.source.source_id, claim='Claim')
            project = library.create_project('Project', topic='Topic')
            if operation.selected:
                library.select_source(project.project_id, imported.source.source_id)
            if operation.link:
                node = sorted(library.source_node_ids(imported.source.source_id))[0]
                try:
                    library.link_node(project.project_id, project_node_id='C1', source_id=imported.source.source_id,
                                      source_node_id=node, relation='supports')
                    accepted = True
                except SourceLibraryError:
                    accepted = False
            if operation.delete_project:
                library.delete_project(project.project_id)
                after = sum(1 for _ in (root / 'library' / 'sources').iterdir())
                after = after if library.require_source(imported.source.source_id) else 0
        return State(operation, sources, accepted, after)


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    observations, violations = [], []
    for operation in CASES:
        actual = native_state(operation)
        want = next(iter(Library().apply(operation, State()))).new_state
        observations.append(ReplayObservation('Library', (actual.sources, actual.link_accepted, actual.sources_after_delete), actual))
        if actual != want:
            violations.append(ConformanceViolation(step_index=1, rule_name='Library', message=f'{operation.name}: real {actual} != model {want}'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real SourceLibrary imports, links and project deletion in a temporary library.')
