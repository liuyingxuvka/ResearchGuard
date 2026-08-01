"""The sole ResearchGuard console entrypoint."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import __version__
from .routing import (
    RouteBinding,
    RouteComposition,
    TypedGap,
    bind_member_request,
    select_member_request,
)


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


def _print_machine(payload: RouteBinding | RouteComposition | TypedGap) -> None:
    print(json.dumps(payload.to_dict(), ensure_ascii=False, sort_keys=True))


def _execute(member_id: str, member_argv: Sequence[str]) -> int:
    binding = bind_member_request(member_id, member_argv)
    if isinstance(binding, TypedGap):
        _print_machine(binding)
        return 2
    return _member_main(binding.member_id)(list(member_argv))


def _run_umbrella(argv: Sequence[str]) -> int:
    business_intent_id: str | None = None
    active_request_id: str | None = None
    task_facts_path: Path | None = None
    member_argv: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            member_argv = list(argv[index + 1 :])
            break
        if token in {
            "--task-facts",
            "--business-intent-id",
            "--active-request-id",
        }:
            if index + 1 >= len(argv):
                gap = TypedGap(
                    status="blocked",
                    code="missing-option-value",
                    message=f"{token} requires a value.",
                )
                _print_machine(gap)
                return 2
            value = argv[index + 1]
            if token == "--task-facts":
                task_facts_path = Path(value)
            elif token == "--business-intent-id":
                business_intent_id = value
            else:
                active_request_id = value
            index += 2
            continue
        gap = TypedGap(
            status="blocked",
            code="unknown-umbrella-option",
            message=(
                f"Unknown umbrella option {token!r}. Put member arguments after "
                "`--`."
            ),
        )
        _print_machine(gap)
        return 2
    if not business_intent_id or task_facts_path is None:
        gap = TypedGap(
            status="blocked",
            code="member-admission-required",
            message=(
                "The umbrella requires --business-intent-id and one current "
                "--task-facts artifact with source-bound facts and exact forbidden reviews."
            ),
        )
        _print_machine(gap)
        return 2
    try:
        task_facts_payload = json.loads(
            task_facts_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        gap = TypedGap(
            status="blocked",
            code="task-facts-unreadable",
            message=str(exc),
        )
        _print_machine(gap)
        return 2
    if not isinstance(task_facts_payload, dict):
        gap = TypedGap(
            status="blocked",
            code="task-facts-invalid",
            message="Task facts must be a JSON object.",
        )
        _print_machine(gap)
        return 2
    binding = select_member_request(
        task_facts_payload,
        member_argv,
        business_intent_id=business_intent_id,
        active_request_id=active_request_id,
    )
    if isinstance(binding, TypedGap):
        _print_machine(binding)
        return 2
    if isinstance(binding, RouteComposition):
        # The umbrella coordinates the minimum sufficient set but never guesses
        # member-specific arguments or treats a plan as completed native work.
        _print_machine(binding)
        return 0
    return _member_main(binding.member_id)(member_argv)


def _print_help() -> None:
    print(
        "\n".join(
            (
                "usage: researchguard {run|logic|source|trace|experiment} ...",
                "",
                "run     route to one member or emit one minimum-sufficient composition",
                "logic   execute the LogicGuard native owner",
                "source  execute the SourceGuard native owner",
                "trace   execute the TraceGuard native owner",
                "experiment  execute the ExperimentGuard recommendation owner",
                "",
                "umbrella form:",
                "  researchguard run --business-intent-id ID --task-facts FILE -- ARGS",
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
    if command == "run":
        return _run_umbrella(command_argv)
    if command in {"logic", "source", "trace", "experiment"}:
        return _execute(f"{command}guard", command_argv)
    print(
        json.dumps(
            TypedGap(
                status="blocked",
                code="unknown-command",
                message=f"Unknown ResearchGuard command: {command}",
            ).to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

