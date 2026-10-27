"""Bound prompt loads so an author reads only the reference step needed."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/researchguard'
MANIFEST = ROOT / 'scripts/prompt_bundle_manifest.json'


def test_prompt_size():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    entry = next(row for row in manifest['bundles'] if row['bundle_id'] == 'researchguard')
    assert sum((ROOT / name).stat().st_size for name in entry['entry_files']) <= entry['max_entry_bytes']
    for path in (SKILL / 'references').rglob('*.md'):
        assert len(path.read_text(encoding='utf-8')) <= 12000, path
    common = sum(len((SKILL / name).read_text(encoding='utf-8')) for name in ['SKILL.md', 'references/research-tree.md'])
    for route in ('source', 'trace', 'logic', 'experiment'):
        route_path = f'skills/researchguard/references/routes/{route}.md'
        todo = [route_path]
        seen = set()
        fields = []
        while todo:
            parent = todo.pop()
            if parent in seen:
                continue
            seen.add(parent)
            for edge in manifest['reference_edges']:
                if edge['declared_in'] == parent and edge['trigger_id'] == 'trigger:fields':
                    fields.append(ROOT / edge['reference'])
                    todo.append(edge['reference'])
        size = common + len((ROOT / route_path).read_text(encoding='utf-8')) + max((len(p.read_text(encoding='utf-8')) for p in fields), default=0)
        assert size <= 25000, (route, size)
