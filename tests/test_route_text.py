"""Check route content for repeated material, dead references and unknown names."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

from flowguard.testing import check_route_texts

from researchguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/researchguard"
HELP_ARGS = [["--help"], *[[member, "--help"] for member in ("logic", "source", "trace", "experiment", "status")]]


def _cli_options():
    flags = set()
    original = argparse._ActionsContainer.add_argument

    def record(parser, *names, **kwargs):
        flags.update(name for name in names if name.startswith("-"))
        return original(parser, *names, **kwargs)

    with patch.object(argparse._ActionsContainer, "add_argument", record):
        with redirect_stdout(StringIO()):
            for args in HELP_ARGS:
                try:
                    main(args)
                except SystemExit as error:
                    assert error.code == 0
    return flags


def _check(route, texts, flags):
    check_route_texts(route, texts, flags, skill_root=SKILL, project_root=ROOT,
                      project_prefixes=('src/', 'tests/', 'examples/'))


def test_route_texts_have_no_repeats_dead_links_or_missing_names():
    flags = _cli_options()
    errors = []
    manifest = json.loads((ROOT / "scripts/prompt_bundle_manifest.json").read_text(encoding='utf-8'))
    for route in sorted((SKILL / "references/routes").glob("*.md")):
        files = {SKILL / "SKILL.md", SKILL / "references/research-tree.md"}
        todo = [route]
        while todo:
            parent = todo.pop()
            if parent in files:
                continue
            files.add(parent)
            todo.extend(
                ROOT / edge["reference"]
                for edge in manifest["reference_edges"]
                if ROOT / edge["declared_in"] == parent
            )
        try:
            for path in files:
                assert path.is_file(), f"{route.name}: missing reference: {path}"
            texts = {path: path.read_text(encoding='utf-8') for path in sorted(files)}
            _check(route.name, texts, flags)
        except AssertionError as error:
            errors.append(str(error))
        print(
            f"route {route.name}: {sum(len(p.read_text(encoding='utf-8')) for p in files if p.is_file())} characters"
        )
    assert not errors, "\n".join(errors)
