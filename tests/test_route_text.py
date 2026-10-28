"""Check route content for repeated material, dead references and unknown names."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import re
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from researchguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/researchguard"
LINKS = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")
CODES = re.compile(r"`([^`\n]+)`")
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


def _slug(heading):
    return re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")


def _destination(origin, link):
    value = urlsplit(link)
    if value.scheme or value.netloc:
        return None
    path = (origin.parent / unquote(value.path)).resolve() if value.path else origin
    return path, unquote(value.fragment)


def _check(route, texts, flags):
    paragraphs = Counter(
        " ".join(part.split())
        for text in texts.values()
        for part in re.split(r"\n\s*\n", text)
        if len(part.split()) >= 8
    )
    for paragraph, count in paragraphs.items():
        assert count == 1, f"{route}: repeated paragraph: {paragraph}"
    for origin, text in texts.items():
        for link in LINKS.findall(text):
            resolved = _destination(origin, link)
            if resolved is None:
                continue
            target, fragment = resolved
            assert target.exists(), f"{route}: dead link: {link} in {origin}"
            if fragment:
                headings = re.findall(r"^#+ (.+)$", target.read_text(), re.M)
                assert fragment in {
                    _slug(heading) for heading in headings
                }, f"{route}: missing heading: {link} in {origin}"
        for code in CODES.findall(text):
            if code.startswith(
                ("grep ", "git ", "pip ", "python -m pytest", "python -m flowguard")
            ):
                continue
            for option in re.findall(r"--[a-z0-9][\w-]*", code):
                assert option in flags, f"{route}: unknown option: {code}"
            if code.startswith(("references/", "assets/", "scripts/", "agents/")):
                target = SKILL / code.split()[0].split("#", 1)[0]
            elif code.startswith(("src/", "tests/", "examples/")):
                target = ROOT / code.split()[0].split("#", 1)[0]
            else:
                continue
            if "<" in code or "*" in code:
                continue
            assert target.exists(), f"{route}: missing path: {code}"


def test_route_texts_have_no_repeats_dead_links_or_missing_names():
    flags = _cli_options()
    errors = []
    manifest = json.loads((ROOT / "scripts/prompt_bundle_manifest.json").read_text())
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
            texts = {path: path.read_text() for path in sorted(files)}
            _check(route.name, texts, flags)
        except AssertionError as error:
            errors.append(str(error))
        print(
            f"route {route.name}: {sum(len(p.read_text()) for p in files if p.is_file())} characters"
        )
    assert not errors, "\n".join(errors)
