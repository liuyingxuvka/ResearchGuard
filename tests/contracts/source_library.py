"""Personal source library: imports deduplicate by content, links need a selected source, deleting a project keeps sources."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

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

def expected_Library(operation, state, mutation=''):
    sources = operation.imports_of_same_content if mutation == 'duplicate_import_adds_a_source' else min(operation.imports_of_same_content, 1)
    accepted = operation.link and (operation.selected or mutation == 'link_without_selected_source')
    after = 0 if operation.delete_project and mutation == 'delete_project_deletes_sources' else sources
    result = State(operation, sources, accepted, after)
    return result

def rule(check):

    def invariant(state):
        if state.operation is None:
            return True
        problem = check(state, state.operation)
        return False if problem else True
    return invariant

def dedup_rule(state, operation):
    if operation.imports_of_same_content and state.sources != 1:
        return f'{operation.imports_of_same_content} imports of one content made {state.sources} sources'

def link_rule(state, operation):
    if state.link_accepted and (not operation.selected):
        return 'a project linked a node of a source it did not select'

def delete_rule(state, operation):
    if operation.delete_project and state.sources_after_delete != state.sources:
        return 'deleting a project deleted library sources'
RULES = (rule(dedup_rule), rule(link_rule), rule(delete_rule))
CASES = (Operation('reimport', imports_of_same_content=2), Operation('link_unselected', imports_of_same_content=1, link=True), Operation('link_selected', imports_of_same_content=1, selected=True, link=True), Operation('delete', imports_of_same_content=1, selected=True, delete_project=True))
MUTATIONS = {'duplicate_import_adds_a_source': 'import_deduplicates_by_content_hash', 'link_without_selected_source': 'project_link_requires_selected_source', 'delete_project_deletes_sources': 'deleting_a_project_keeps_sources'}

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
        sources = sum((1 for _ in (root / 'library' / 'sources').iterdir()))
        accepted, after = (False, sources)
        if operation.link or operation.delete_project:
            library.create_source_model(imported.source.source_id, claim='Claim')
            project = library.create_project('Project', topic='Topic')
            if operation.selected:
                library.select_source(project.project_id, imported.source.source_id)
            if operation.link:
                node = sorted(library.source_node_ids(imported.source.source_id))[0]
                try:
                    library.link_node(project.project_id, project_node_id='C1', source_id=imported.source.source_id, source_node_id=node, relation='supports')
                    accepted = True
                except SourceLibraryError:
                    accepted = False
            if operation.delete_project:
                library.delete_project(project.project_id)
                after = sum((1 for _ in (root / 'library' / 'sources').iterdir()))
                after = after if library.require_source(imported.source.source_id) else 0
        return State(operation, sources, accepted, after)

def assert_native_contract():
    observations, violations = ([], [])
    for operation in CASES:
        actual = native_state(operation)
        want = expected_Library(operation, State())
        if actual != want:
            violations.append(f'{operation.name}: real {actual} != model {want}')
    assert not violations, violations
RULE_NAMES = ('import_deduplicates_by_content_hash', 'project_link_requires_selected_source', 'deleting_a_project_keeps_sources')
