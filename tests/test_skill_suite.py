from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from researchguard.source.schema import Gap, SchemaError


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "researchguard"
ROUTES = ("logic", "source", "trace", "experiment")


def test_one_skill_with_a_route_table_and_a_short_description() -> None:
    assert sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir()) == ["researchguard"]
    text = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == "researchguard"
    assert len(metadata["description"]) <= 300
    assert re.fullmatch(r"Use for .+\. Not for .+; use [a-z-]+\.", metadata["description"])
    for route in ROUTES:
        assert f"`references/routes/{route}.md`" in text
    interface = yaml.safe_load(SKILL.joinpath("agents/openai.yaml").read_text(encoding="utf-8"))
    assert interface["interface"]["display_name"] == "ResearchGuard"
    assert "$researchguard" in interface["interface"]["default_prompt"]


def test_route_and_reference_inventory_is_exact() -> None:
    assert sorted(path.name for path in (SKILL / "references" / "routes").glob("*.md")) == sorted(
        f"{route}.md" for route in ROUTES
    )
    logic = {path.name for path in (SKILL / "references" / "logic").glob("*.md")}
    assert {
        "source-library.md",
        "structured-artifact.md",
        "model-deepening.md",
        "artifact-synthesis.md",
        "project-library-viewer.md",
    } <= logic
    assert (SKILL / "references" / "trace" / "case-library.md").is_file()
    for route in ROUTES:
        assert not (SKILL / "references" / "routes" / f"{route}.md").read_text(encoding="utf-8").startswith("---")


def test_sourceguard_rejects_retired_gap_projection() -> None:
    assert "status" not in Gap.__dataclass_fields__
    with pytest.raises(SchemaError, match="gap.status is retired"):
        Gap.from_dict(
            {
                "gap_id": "old",
                "gap_type": "unknown",
                "status": "open",
                "semantic_state": "discovered",
            }
        )


def test_current_commands_are_callable() -> None:
    for command in ("logic", "source", "trace", "experiment"):
        result = subprocess.run(
            [sys.executable, "-m", "researchguard", command, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_skill_files_name_only_existing_commands(monkeypatch) -> None:
    """Read live parsers through the dispatcher without running any command handler."""
    import argparse
    from researchguard import cli

    class ParserCaptured(BaseException):
        def __init__(self, parser):
            self.parser = parser

    def capture_parser(parser, *args, **kwargs):
        raise ParserCaptured(parser)

    parsers = {}
    with monkeypatch.context() as patch:
        patch.setattr(argparse.ArgumentParser, "parse_args", capture_parser)
        for route in (*ROUTES, "status"):
            with pytest.raises(ParserCaptured) as captured:
                cli.main([route, "--help"])
            parsers[route] = captured.value.parser

    paths = [ROOT / "README.md", SKILL / "SKILL.md", *sorted((SKILL / "references").rglob("*.md"))]
    checked = 0
    for path in paths:
        text = path.read_text(encoding="utf-8").replace("\\\n", " ")
        for match in re.finditer(r"\bresearchguard[ \t]+([^\n`]+)", text):
            command = match.group(1).strip()
            route = command.split()[0]
            if "|" in route:
                assert set(route.split("|")) <= set(parsers), (path, command)
                continue
            assert route in parsers, (path, command)
            parser = parsers[route]
            active_parsers = [parser]
            # Positional values and placeholder text cannot invoke a command here.
            tokens = re.findall(r"--[a-zA-Z][\w-]*|<[^>]+>|[a-zA-Z][\w-]*", command)[1:]
            for token in tokens:
                subcommands = next((action for action in parser._actions
                                    if isinstance(action, argparse._SubParsersAction)), None)
                if subcommands is None or token.startswith(("<", "--")):
                    break
                assert token in subcommands.choices, (path, command, token)
                parser = subcommands.choices[token]
                active_parsers.append(parser)
            options = {option for current in active_parsers for action in current._actions
                       for option in action.option_strings}
            for option in re.findall(r"(?<!\w)--[a-zA-Z][\w-]*", command):
                assert option in options, (path, command, option)
            checked += 1
    assert checked, "No documented ResearchGuard commands were found"
