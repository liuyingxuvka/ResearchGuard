"""The sole ResearchGuard console entrypoint."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence

from . import __version__


MemberMain = Callable[[list[str] | None], int]


def _member_main(member_id: str) -> MemberMain:
    if member_id == "logicguard":
        from .logic.cli import main

        return main
    if member_id == "sourceguard":
        from .source.cli import main

        return main
    if member_id == "traceguard":
        from .trace.cli import main

        return main
    if member_id == "experimentguard":
        from .experiment.cli import main

        return main
    raise ValueError(f"unknown member: {member_id}")


def _execute(member_id: str, member_argv: Sequence[str]) -> int:
    return _member_main(member_id)(list(member_argv))


def _print_help() -> None:
    print(
        "\n".join(
            (
                "usage: researchguard {logic|source|trace|experiment} ...",
                "",
                "logic   execute the LogicGuard native owner",
                "source  execute the SourceGuard native owner",
                "trace   execute the TraceGuard native owner",
                "status  inspect a research folder and check shared ids",
                "experiment  execute the ExperimentGuard recommendation owner",
            )
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _print_help()
        return 0
    if args[0] == "--version":
        print(f"researchguard {__version__}")
        return 0
    command = args[0]
    command_argv = args[1:]
    if command == "status":
        from .research import status_main

        return status_main(command_argv)
    if command in {"logic", "source", "trace", "experiment"}:
        return _execute(f"{command}guard", command_argv)
    print(
        json.dumps(
            {"status": "blocked", "code": "unknown-command", "message": f"Unknown ResearchGuard command: {command}"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

