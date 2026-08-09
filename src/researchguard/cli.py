"""The sole ResearchGuard console entrypoint."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import __version__
from .domain_dna import (
    ExternalDomainDnaError,
    export_external_domain_dna,
    project_external_domain_dna,
)
from .routing import (
    RouteBinding,
    RouteComposition,
    TypedGap,
    bind_member_request,
    composition_impact,
    export_portable_composition_bundle,
    project_portable_composition_bundle,
    reverse_trace_composition,
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


def _print_machine(payload: RouteBinding | RouteComposition | TypedGap | dict[str, object]) -> None:
    value = payload.to_dict() if hasattr(payload, "to_dict") else payload
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


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
    native_attestations_path: Path | None = None
    changed_ids: list[str] = []
    reverse_trace_output: str | None = None
    portable_bundle_out: Path | None = None
    member_argv: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            member_argv = list(argv[index + 1 :])
            break
        if token in {
            "--task-facts",
            "--native-owner-attestations",
            "--business-intent-id",
            "--active-request-id",
            "--changed-id",
            "--reverse-trace-output",
            "--portable-bundle-out",
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
            elif token == "--native-owner-attestations":
                native_attestations_path = Path(value)
            elif token == "--business-intent-id":
                business_intent_id = value
            elif token == "--changed-id":
                changed_ids.append(value)
            elif token == "--reverse-trace-output":
                reverse_trace_output = value
            elif token == "--portable-bundle-out":
                portable_bundle_out = Path(value)
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
    native_attestations_payload: list[dict[str, object]] = []
    if native_attestations_path is not None:
        try:
            loaded_attestations = json.loads(
                native_attestations_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="native-owner-attestations-unreadable",
                    message=str(exc),
                )
            )
            return 2
        if not isinstance(loaded_attestations, list) or any(
            not isinstance(item, dict) for item in loaded_attestations
        ):
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="native-owner-attestations-invalid",
                    message="Native owner attestations must be a JSON array of current objects.",
                )
            )
            return 2
        native_attestations_payload = loaded_attestations
    binding = select_member_request(
        task_facts_payload,
        member_argv,
        business_intent_id=business_intent_id,
        active_request_id=active_request_id,
        native_owner_attestations=native_attestations_payload,
    )
    if isinstance(binding, TypedGap):
        _print_machine(binding)
        return 2
    if isinstance(binding, RouteComposition):
        # The umbrella coordinates the minimum sufficient set but never guesses
        # member-specific arguments or treats a plan as completed native work.
        if sum(bool(item) for item in (changed_ids, reverse_trace_output, portable_bundle_out)) > 1:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="composition-operation-conflict",
                    message=(
                        "Select exactly one of affected-only impact, reverse trace, "
                        "or portable bundle export for one umbrella call."
                    ),
                )
            )
            return 2
        if changed_ids:
            payload = composition_impact(binding, changed_ids)
            _print_machine(payload)
            return 3 if payload["unknown_ownership"] or payload["partial_result_suppressed"] else 0
        if reverse_trace_output:
            try:
                payload = reverse_trace_composition(binding, reverse_trace_output)
                _print_machine(payload)
                return 3 if payload["partial_result_suppressed"] else 0
            except ValueError as exc:
                _print_machine(
                    TypedGap(status="blocked", code="composition-trace-unresolved", message=str(exc))
                )
                return 2
        if portable_bundle_out is not None:
            if binding.status != "composition_ready":
                _print_machine(
                    TypedGap(
                        status="blocked",
                        code="portable-composition-not-ready",
                        message="A portable bundle can be exported only from composition_ready.",
                    )
                )
                return 3
            try:
                bundle = export_portable_composition_bundle(binding)
                portable_bundle_out.parent.mkdir(parents=True, exist_ok=True)
                portable_bundle_out.write_bytes(bundle)
            except (OSError, ValueError) as exc:
                _print_machine(
                    TypedGap(status="blocked", code="portable-bundle-export-failed", message=str(exc))
                )
                return 2
            projection = project_portable_composition_bundle(bundle)
            projection["export_path"] = str(portable_bundle_out.resolve())
            projection["export_status"] = "portable_bundle_exported"
            _print_machine(projection)
            return 0
        _print_machine(binding)
        return 0 if binding.status == "composition_ready" else 3
    return _member_main(binding.member_id)(member_argv)


def _run_portable(argv: Sequence[str]) -> int:
    """Inspect one disk bundle through a compact default or one ID drill-down."""

    if not argv:
        _print_machine(
            TypedGap(
                status="blocked",
                code="portable-bundle-path-required",
                message="portable requires one bundle path",
            )
        )
        return 2
    bundle_path = Path(argv[0])
    trusted: list[str] = []
    query_kind: str | None = None
    object_id = ""
    option_to_kind = {
        "--member": "member",
        "--behavior": "behavior",
        "--handoff": "handoff",
        "--impact": "impact",
        "--reverse": "reverse",
    }
    index = 1
    while index < len(argv):
        token = argv[index]
        if token not in {
            "--trusted-producer-descriptor-fingerprint",
            *option_to_kind,
        } or index + 1 >= len(argv):
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="portable-option-invalid",
                    message=f"Unknown or incomplete portable option {token!r}.",
                )
            )
            return 2
        value = argv[index + 1]
        if token == "--trusted-producer-descriptor-fingerprint":
            trusted.append(value)
        else:
            if query_kind is not None:
                _print_machine(
                    TypedGap(
                        status="blocked",
                        code="portable-query-conflict",
                        message="Select only one explicit portable drill-down per call.",
                    )
                )
                return 2
            query_kind = option_to_kind[token]
            object_id = value
        index += 2
    try:
        bundle = bundle_path.read_bytes()
        projection = project_portable_composition_bundle(
            bundle,
            trusted_producer_descriptor_fingerprints=trusted,
            query_kind=query_kind,  # type: ignore[arg-type]
            object_id=object_id,
        )
    except (OSError, ValueError) as exc:
        _print_machine(
            TypedGap(status="blocked", code="portable-bundle-unreadable", message=str(exc))
        )
        return 2
    _print_machine(projection)
    if projection.get("status") != "handoff_qualified":
        return 3
    if query_kind is not None and projection.get("query_status") != "found":
        return 3
    return 0


def _run_domain_dna(argv: Sequence[str]) -> int:
    """Build or inspect one generic external-object DNA artifact."""

    if not argv or argv[0] not in {"build", "inspect"}:
        _print_machine(
            TypedGap(
                status="blocked",
                code="domain-dna-operation-required",
                message="domain-dna requires build or inspect",
            )
        )
        return 2
    operation = argv[0]
    if operation == "build":
        if len(argv) < 5:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="domain-dna-build-arguments-invalid",
                    message=(
                        "domain-dna build requires SPEC OUTPUT "
                        "--native-composition BUNDLE and optional "
                        "--scope-authority RECORD / --material-root ROOT"
                    ),
                )
            )
            return 2
        spec_path = Path(argv[1])
        output_path = Path(argv[2])
        native_composition_path: Path | None = None
        scope_authority_path: Path | None = None
        material_root: Path | None = None
        index = 3
        while index < len(argv):
            token = argv[index]
            if token not in {"--native-composition", "--scope-authority", "--material-root"} or index + 1 >= len(argv):
                _print_machine(
                    TypedGap(
                        status="blocked",
                        code="domain-dna-build-arguments-invalid",
                        message=f"Unknown or incomplete domain-DNA build option {token!r}.",
                    )
                )
                return 2
            value = Path(argv[index + 1])
            if token == "--native-composition":
                if native_composition_path is not None:
                    _print_machine(
                        TypedGap(
                            status="blocked",
                            code="domain-dna-native-composition-duplicate",
                            message="Select exactly one member-native composition bundle.",
                        )
                    )
                    return 2
                native_composition_path = value
            elif token == "--scope-authority":
                if scope_authority_path is not None:
                    _print_machine(
                        TypedGap(
                            status="blocked",
                            code="domain-dna-scope-authority-duplicate",
                            message="Select at most one independent scope-authority record.",
                        )
                    )
                    return 2
                scope_authority_path = value
            else:
                if material_root is not None:
                    _print_machine(
                        TypedGap(
                            status="blocked",
                            code="domain-dna-material-root-duplicate",
                            message="Select only one external-domain-DNA material root.",
                        )
                    )
                    return 2
                material_root = value
            index += 2
        if native_composition_path is None:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="domain-dna-native-composition-required",
                    message="External-domain DNA requires one current four-member native composition.",
                )
            )
            return 2
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                raise ExternalDomainDnaError("external domain DNA spec must be an object")
            bundle = export_external_domain_dna(
                spec,
                native_composition_bundle=native_composition_path.read_bytes(),
                scope_authority_record=(
                    scope_authority_path.read_bytes()
                    if scope_authority_path is not None
                    else None
                ),
                material_root=material_root,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(bundle)
            projection = project_external_domain_dna(bundle)
        except (OSError, json.JSONDecodeError, ExternalDomainDnaError) as exc:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="domain-dna-build-failed",
                    message=str(exc),
                )
            )
            return 2
        projection["export_path"] = str(output_path.resolve())
        projection["export_status"] = "external_domain_dna_exported"
        _print_machine(projection)
        return 0

    if len(argv) < 2:
        _print_machine(
            TypedGap(
                status="blocked",
                code="domain-dna-bundle-path-required",
                message="domain-dna inspect requires one bundle path",
            )
        )
        return 2
    bundle_path = Path(argv[1])
    trusted: list[str] = []
    trusted_producers: list[str] = []
    trusted_scope_authorities: list[str] = []
    trusted_scope_authority_producers: list[str] = []
    material_root: Path | None = None
    query_kind: str | None = None
    object_id = ""
    option_to_kind = {
        "--member": "member",
        "--behavior": "behavior",
        "--object": "object",
        "--impact": "impact",
        "--reverse": "reverse",
        "--scope": "scope",
    }
    index = 2
    while index < len(argv):
        token = argv[index]
        if token not in {
            "--trusted-artifact-sha256",
            "--trusted-producer-descriptor-fingerprint",
            "--trusted-scope-authority-fingerprint",
            "--trusted-scope-authority-producer-descriptor-fingerprint",
            "--material-root",
            *option_to_kind,
        } or index + 1 >= len(argv):
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="domain-dna-option-invalid",
                    message=f"Unknown or incomplete domain-DNA option {token!r}.",
                )
            )
            return 2
        value = argv[index + 1]
        if token == "--trusted-artifact-sha256":
            trusted.append(value)
        elif token == "--trusted-producer-descriptor-fingerprint":
            trusted_producers.append(value)
        elif token == "--trusted-scope-authority-fingerprint":
            trusted_scope_authorities.append(value)
        elif token == "--trusted-scope-authority-producer-descriptor-fingerprint":
            trusted_scope_authority_producers.append(value)
        elif token == "--material-root":
            if material_root is not None:
                _print_machine(
                    TypedGap(
                        status="blocked",
                        code="domain-dna-material-root-duplicate",
                        message="Select only one external-domain-DNA material root.",
                    )
                )
                return 2
            material_root = Path(value)
        elif query_kind is not None:
            _print_machine(
                TypedGap(
                    status="blocked",
                    code="domain-dna-query-conflict",
                    message="Select only one external-domain-DNA drill-down.",
                )
            )
            return 2
        else:
            query_kind = option_to_kind[token]
            object_id = value
        index += 2
    try:
        projection = project_external_domain_dna(
            bundle_path.read_bytes(),
            trusted_artifact_sha256=trusted,
            trusted_producer_descriptor_fingerprints=trusted_producers,
            trusted_scope_authority_fingerprints=trusted_scope_authorities,
            trusted_scope_authority_producer_descriptor_fingerprints=(
                trusted_scope_authority_producers
            ),
            material_root=material_root,
            query_kind=query_kind,  # type: ignore[arg-type]
            object_id=object_id,
        )
    except (OSError, ExternalDomainDnaError) as exc:
        _print_machine(
            TypedGap(status="blocked", code="domain-dna-unreadable", message=str(exc))
        )
        return 2
    _print_machine(projection)
    if projection.get("status") == "dna_blocked":
        return 3
    if query_kind is not None and projection.get("query_status") != "found":
        return 3
    return 0


def _print_help() -> None:
    print(
        "\n".join(
            (
                "usage: researchguard {run|portable|domain-dna|self-dna|logic|source|trace|experiment} ...",
                "",
                "run     route to one member or emit one minimum-sufficient composition",
                "portable  inspect a complete disk bundle through a compact default or one ID query",
                "domain-dna  build or inspect one external paper/model/workflow DNA artifact",
                "self-dna  explicitly audit or export ResearchGuard's FlowGuard-owned software DNA",
                "logic   execute the LogicGuard native owner",
                "source  execute the SourceGuard native owner",
                "trace   execute the TraceGuard native owner",
                "experiment  execute the ExperimentGuard recommendation owner",
                "",
                "umbrella form:",
                "  researchguard run --business-intent-id ID --task-facts FILE [--native-owner-attestations FILE] [--changed-id ID | --reverse-trace-output ID | --portable-bundle-out FILE] -- ARGS",
                "portable form:",
                "  researchguard portable BUNDLE [--trusted-producer-descriptor-fingerprint SHA256] [--member ID | --behavior ID | --handoff ID | --impact ID | --reverse ID]",
                "domain-DNA forms:",
                "  researchguard domain-dna build SPEC OUTPUT --native-composition BUNDLE [--scope-authority RECORD] [--material-root ROOT]",
                "  researchguard domain-dna inspect BUNDLE [--trusted-artifact-sha256 SHA256] [--trusted-producer-descriptor-fingerprint SHA256] [--trusted-scope-authority-fingerprint SHA256 | --trusted-scope-authority-producer-descriptor-fingerprint SHA256] [--material-root ROOT] [--member ID | --behavior ID | --object ID | --impact ID | --reverse ID | --scope ID]",
                "self-DNA forms:",
                "  researchguard self-dna check [--root ROOT] [--compact]",
                "  researchguard self-dna export [--root ROOT] --output OUTSIDE_REPOSITORY",
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
    if command == "portable":
        return _run_portable(command_argv)
    if command == "domain-dna":
        return _run_domain_dna(command_argv)
    if command == "self-dna":
        from .self_dna import main as self_dna_main

        return self_dna_main(command_argv)
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

