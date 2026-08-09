from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib
import zipfile

from admission_fixtures import (
    composition,
    native_owner_attestations,
    task_facts,
)
from researchguard.model_envelope import HandoffFieldContract
from researchguard.native_receipts import (
    _CURRENT_NATIVE_RECEIPT_PRODUCERS,
    _PORTABLE_NATIVE_RECEIPT_RECORDS,
    _portable_native_receipt_record_scope,
    _producer_descriptor_fingerprint,
)
from researchguard.portable_material import _PORTABLE_NATIVE_MATERIALS
from researchguard.routing import (
    RouteComposition,
    composition_impact,
    export_portable_composition_bundle,
    qualify_portable_composition_bundle,
    reverse_trace_composition,
    select_member_request,
)
from researchguard.target_authority import (
    _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS,
    _PORTABLE_EXPECTED_TARGET_RECORDS,
    _portable_expected_target_record_scope,
)


ARGV = ["plan", "four-member-portable-task.json"]
INTENT = "intent:four-member-portable-bundle"


def _four_member_plan() -> dict[str, object]:
    return composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
        ("logicguard", ("logic.primary.general-argument",)),
        ("experimentguard", ("experiment.primary.discriminating-set",)),
    )


def _facts(plan: dict[str, object]) -> dict[str, object]:
    return task_facts(
        argv=ARGV,
        intent=INTENT,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=(
            "trace.temporal_reconstruction",
            "logic.argument_structure",
            "experiment.discriminating_set",
        ),
        context_kinds=(
            "experiment.explicit_hypotheses",
            "experiment.finite_candidates",
            "experiment.predicted_outcomes",
        ),
        composition=plan,
    )


def _rebind_bundle_identity(raw: dict[str, object]) -> bytes:
    core = {
        key: value
        for key, value in raw.items()
        if key not in {"bundle_id", "bundle_fingerprint"}
    }
    body = json.dumps(
        core, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    raw["bundle_fingerprint"] = fingerprint
    raw["bundle_id"] = "portable-composition:" + fingerprint[7:]
    return json.dumps(
        raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _build_temporary_wheel(repository: Path, wheelhouse: Path) -> Path:
    """Build one ordinary pure-Python wheel without requiring the wheel package."""

    project = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
    distribution = "researchguard"
    dist_info = f"{distribution}-{version}.dist-info"
    wheel_path = wheelhouse / f"{distribution}-{version}-py3-none-any.whl"
    rows: list[tuple[str, str, str]] = []

    def add_bytes(archive: zipfile.ZipFile, name: str, body: bytes) -> None:
        archive.writestr(name, body)
        digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=")
        rows.append((name, "sha256=" + digest.decode("ascii"), str(len(body))))

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        package_root = repository / "src" / "researchguard"
        for source in sorted(package_root.rglob("*")):
            if (
                not source.is_file()
                or "__pycache__" in source.parts
                or source.suffix in {".pyc", ".pyo"}
            ):
                continue
            add_bytes(
                archive,
                source.relative_to(repository / "src").as_posix(),
                source.read_bytes(),
            )
        add_bytes(
            archive,
            f"{dist_info}/METADATA",
            (
                "Metadata-Version: 2.1\n"
                "Name: researchguard\n"
                f"Version: {version}\n"
                "Summary: Isolated ResearchGuard portable-bundle test wheel\n\n"
            ).encode("utf-8"),
        )
        add_bytes(
            archive,
            f"{dist_info}/WHEEL",
            (
                "Wheel-Version: 1.0\n"
                "Generator: researchguard-test\n"
                "Root-Is-Purelib: true\n"
                "Tag: py3-none-any\n\n"
            ).encode("utf-8"),
        )
        add_bytes(
            archive,
            f"{dist_info}/top_level.txt",
            b"researchguard\n",
        )
        record_name = f"{dist_info}/RECORD"
        record_buffer = io.StringIO(newline="")
        writer = csv.writer(record_buffer, lineterminator="\n")
        writer.writerows([*rows, (record_name, "", "")])
        archive.writestr(record_name, record_buffer.getvalue().encode("utf-8"))
    return wheel_path


def _test_trusted_descriptor_fingerprints() -> tuple[str, ...]:
    """Return fixture trust roots from the test owner, never from bundle bytes."""

    result: set[str] = set()
    for key, descriptor in _CURRENT_NATIVE_RECEIPT_PRODUCERS.items():
        result.add(_producer_descriptor_fingerprint(key, descriptor))
    for key, descriptor in _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS.items():
        result.add(
            _digest(
                {
                    "admission_owner_id": key[0],
                    "admission_producer_id": key[1],
                    "admission_producer_version": key[2],
                    "signing_key_id": str(descriptor["key_id"]),
                    "signature_algorithm": str(descriptor["algorithm"]),
                    "public_key_fingerprint": _digest(
                        {
                            "algorithm": str(descriptor["algorithm"]),
                            "public_exponent": int(descriptor["public_exponent"]),
                            "public_modulus_hex": str(
                                descriptor["public_modulus_hex"]
                            ).lower(),
                        }
                    ),
                }
            )
        )
    return tuple(sorted(result))


def test_four_member_bundle_is_deterministic_bundle_only_and_atomic(
    tmp_path: Path,
) -> None:
    plan = _four_member_plan()
    attestations = native_owner_attestations(plan)
    ready = select_member_request(
        _facts(plan),
        ARGV,
        business_intent_id=INTENT,
        native_owner_attestations=attestations,
    )
    assert isinstance(ready, RouteComposition)
    assert ready.status == "composition_ready"
    assert set(ready.member_ids) == {
        "logicguard",
        "sourceguard",
        "traceguard",
        "experimentguard",
    }

    bundle = export_portable_composition_bundle(ready)
    assert bundle == export_portable_composition_bundle(ready)
    parsed = json.loads(bundle)
    assert len(parsed["portable_member_envelopes"]) == 4
    assert len(parsed["expected_target_records"]) == 4
    # Four member-owner receipts plus every native receipt transitively consumed
    # by the Source/Trace/Logic/Experiment blueprint replays.
    assert len(parsed["native_receipt_records"]) == 27
    assert {
        item["material_id"] for item in parsed["native_material_records"]
    } == {
        "experimentguard:frozen-spec",
        "logicguard:target-proof-material",
        "sourceguard:target-proof-material",
        "traceguard:target-proof-material",
    }
    assert {
        case["behavior_id"] for case in parsed["behavior_transition_cases"]
    } == {
        "researchguard.composition.qualification",
        "researchguard.composition.impact",
        "researchguard.composition.reverse-trace",
        "researchguard.portable-bundle.handoff",
    }
    required_case_fields = {
        "schema_version",
        "case_id",
        "behavior_id",
        "input",
        "pre_state",
        "permitted_output",
        "post_state",
        "effect",
        "protected_failure",
        "oracle",
    }
    assert all(set(case) == required_case_fields for case in parsed["behavior_transition_cases"])

    self_consistent = qualify_portable_composition_bundle(bundle)
    assert self_consistent["status"] == "handoff_self_consistent"
    assert self_consistent["producer_authenticity"] == "not_licensed"
    assert self_consistent["partial_result_suppressed"] is True
    assert self_consistent["member_envelopes"] == []
    assert self_consistent["first_gap"]["code"] == "portable-producer-trust-not-licensed"
    assert self_consistent["member_object_dna_status"] == "self_consistent"
    assert {
        item["status"] for item in self_consistent["member_object_dna_results"]
    } == {"self_consistent"}
    assert _PORTABLE_NATIVE_RECEIPT_RECORDS.get() is None
    assert _PORTABLE_EXPECTED_TARGET_RECORDS.get() is None
    assert _PORTABLE_NATIVE_MATERIALS.get() is None

    # Nested scopes restore their exact outer view, and ContextVar isolation
    # keeps parallel qualifiers from sharing a temporary portable authority.
    with _portable_expected_target_record_scope(parsed["expected_target_records"]):
        outer_targets = _PORTABLE_EXPECTED_TARGET_RECORDS.get()
        with _portable_expected_target_record_scope(
            parsed["expected_target_records"][:1]
        ):
            assert len(_PORTABLE_EXPECTED_TARGET_RECORDS.get() or {}) == 1
        assert _PORTABLE_EXPECTED_TARGET_RECORDS.get() == outer_targets
    with _portable_native_receipt_record_scope(parsed["native_receipt_records"]):
        outer_receipts = _PORTABLE_NATIVE_RECEIPT_RECORDS.get()
        with _portable_native_receipt_record_scope(
            parsed["native_receipt_records"][:1]
        ):
            assert len(_PORTABLE_NATIVE_RECEIPT_RECORDS.get() or {}) == 1
        assert _PORTABLE_NATIVE_RECEIPT_RECORDS.get() == outer_receipts
    assert _PORTABLE_NATIVE_RECEIPT_RECORDS.get() is None
    assert _PORTABLE_EXPECTED_TARGET_RECORDS.get() is None
    native_registry_before = dict(_CURRENT_NATIVE_RECEIPT_PRODUCERS)
    target_registry_before = dict(_CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS)
    with ThreadPoolExecutor(max_workers=2) as executor:
        parallel = list(
            executor.map(lambda _: qualify_portable_composition_bundle(bundle), range(4))
        )
    assert {item["status"] for item in parallel} == {"handoff_self_consistent"}
    assert _CURRENT_NATIVE_RECEIPT_PRODUCERS == native_registry_before
    assert _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS == target_registry_before

    trusted_descriptors = _test_trusted_descriptor_fingerprints()
    local = qualify_portable_composition_bundle(
        bundle,
        trusted_producer_descriptor_fingerprints=trusted_descriptors,
    )
    assert local["status"] == "handoff_qualified"
    assert local["producer_authenticity"] == "licensed"
    assert local["first_gap"] is None
    assert local["partial_result_suppressed"] is False
    assert local["member_object_dna_status"] == "licensed"
    assert {item["status"] for item in local["member_object_dna_results"]} == {
        "licensed"
    }

    bundle_path = tmp_path / "portable-bundle.json"
    bundle_path.write_bytes(bundle)
    fresh_home = tmp_path / "fresh-independent-home"
    fresh_home.mkdir()
    repository = Path(__file__).resolve().parents[1]
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _build_temporary_wheel(repository, wheelhouse)
    installed_site = tmp_path / "clean-installed-site"
    installed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--target",
            str(installed_site),
            str(wheel),
        ],
        cwd=fresh_home,
        check=False,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    child = textwrap.dedent(
        """
        import base64, json, os
        from pathlib import Path
        import sys

        installed_site = Path(sys.argv[1]).resolve()
        repository = Path(sys.argv[2]).resolve()
        bundle_path = Path(sys.argv[3]).resolve()
        sys.path.insert(0, str(installed_site))
        bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        forbidden_material_roots = set()
        for record in bundle_payload["native_material_records"]:
            if record["material_id"] == "experimentguard:frozen-spec":
                continue
            material = json.loads(base64.b64decode(record["material_bytes_b64"]))
            if "target_root_locator" in material:
                forbidden_material_roots.add(Path(material["target_root_locator"]).resolve())
            if "contract_locator" in material:
                forbidden_material_roots.add(Path(material["contract_locator"]).resolve().parent)
            if "candidate_locator" in material:
                forbidden_material_roots.add(Path(material["candidate_locator"]).resolve().parent)

        def reject_repository_reads(event, args):
            if event != "open" or not args:
                return
            try:
                candidate = Path(os.fspath(args[0])).resolve()
            except (OSError, TypeError, ValueError):
                return
            if candidate == repository or repository in candidate.parents:
                raise RuntimeError(f"fresh handoff tried to read repository: {candidate}")
            if candidate.name == "spec.json" and installed_site not in candidate.parents:
                raise RuntimeError(f"fresh handoff tried to reopen native spec: {candidate}")
            if any(candidate == root or root in candidate.parents for root in forbidden_material_roots):
                raise RuntimeError(f"fresh handoff tried to reopen native proof files: {candidate}")
            if "researchguard-external-domain-dna-compiler-" in candidate.as_posix().lower():
                raise RuntimeError(f"fresh handoff tried to read compiler temporary material: {candidate}")

        sys.addaudithook(reject_repository_reads)
        from researchguard.cli import main
        from researchguard.native_receipts import _CURRENT_NATIVE_RECEIPT_PRODUCERS
        from researchguard.target_authority import _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS

        assert _CURRENT_NATIVE_RECEIPT_PRODUCERS == {}
        assert _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS == {}
        from researchguard.portable_material import _PORTABLE_NATIVE_MATERIALS
        assert _PORTABLE_NATIVE_MATERIALS.get() is None
        import researchguard
        assert installed_site in Path(researchguard.__file__).resolve().parents
        exit_code = main(["portable", str(bundle_path), *sys.argv[4:]])
        assert _CURRENT_NATIVE_RECEIPT_PRODUCERS == {}
        assert _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS == {}
        raise SystemExit(exit_code)
        """
    )
    environment = os.environ.copy()
    environment["HOME"] = str(fresh_home)
    environment["USERPROFILE"] = str(fresh_home)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("RESEARCHGUARD_TEST_FIXTURE_ROOT", None)
    environment.pop("PYTHONPATH", None)
    trust_args = [
        item
        for fingerprint in trusted_descriptors
        for item in (
            "--trusted-producer-descriptor-fingerprint",
            fingerprint,
        )
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            child,
            str(installed_site),
            str(repository),
            str(bundle_path),
            *trust_args,
        ],
        cwd=fresh_home,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    independent = json.loads(completed.stdout)
    assert independent["status"] == "handoff_qualified"
    assert independent["first_gap"] is None
    assert independent["bundle_fingerprint"] == parsed["bundle_fingerprint"]
    assert independent["producer_authenticity"] == "licensed"
    assert independent["member_object_dna_status"] == "licensed"
    assert {item["member_id"] for item in independent["member_summaries"]} == set(
        ready.member_ids
    )
    assert "detail" not in independent
    assert "portable_member_envelopes" not in independent
    default_output_bytes = len(completed.stdout.encode("utf-8"))
    assert default_output_bytes < 16_384
    assert default_output_bytes * 10 < len(bundle)

    drilled = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            child,
            str(installed_site),
            str(repository),
            str(bundle_path),
            *trust_args,
            "--behavior",
            "logicguard.argument-artifact-qualification",
        ],
        cwd=fresh_home,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert drilled.returncode == 0, drilled.stdout + drilled.stderr
    drilled_payload = json.loads(drilled.stdout)
    assert drilled_payload["query_status"] == "found"
    assert drilled_payload["detail"]["behavior_id"] == "logicguard.argument-artifact-qualification"
    assert not (fresh_home / ".researchguard").exists()

    tampered = deepcopy(parsed)
    descriptor = tampered["native_receipt_records"][0]["producer_descriptor"]
    modulus = descriptor["public_modulus_hex"]
    descriptor["public_modulus_hex"] = modulus[:-1] + (
        "0" if modulus[-1] != "0" else "1"
    )
    rejected = qualify_portable_composition_bundle(
        _rebind_bundle_identity(tampered),
        trusted_producer_descriptor_fingerprints=trusted_descriptors,
    )
    assert rejected["status"] == "handoff_blocked"
    assert rejected["partial_result_suppressed"] is True
    assert rejected["member_envelopes"] == []
    assert {
        item["code"] for item in rejected["gaps"]
    } >= {
        "portable-native-receipt-producer-descriptor-mismatch",
        "portable-native-receipt-signature-invalid",
    }

    forged_case = deepcopy(parsed)
    forged_case["behavior_transition_cases"][1]["permitted_output"][
        "affected_step_ids"
    ] = []
    forged_case["behavior_transition_cases"][2]["oracle"][
        "entrypoint"
    ] = "researchguard.routing:caller_selected_oracle"
    case_rejected = qualify_portable_composition_bundle(
        _rebind_bundle_identity(forged_case),
        trusted_producer_descriptor_fingerprints=trusted_descriptors,
    )
    assert case_rejected["status"] == "handoff_blocked"
    assert {
        item["code"] for item in case_rejected["gaps"]
    } >= {"portable-behavior-case-canonical-mismatch"}

    blocked_plan = deepcopy(plan)
    contract = HandoffFieldContract.from_dict(
        blocked_plan["handoff_field_contracts"][-1]
    )
    rejected_acknowledgement = replace(
        contract.acknowledgements[0],
        status="rejected",
        rejection_reason="experimentguard rejected the declared upstream field",
    )
    blocked_plan["handoff_field_contracts"][-1] = replace(
        contract, acknowledgements=(rejected_acknowledgement,)
    ).to_dict()
    blocked = select_member_request(
        _facts(blocked_plan),
        ARGV,
        business_intent_id=INTENT,
        native_owner_attestations=attestations,
    )
    assert isinstance(blocked, RouteComposition)
    assert blocked.status == "composition_blocked"
    impact = composition_impact(blocked, [contract.payload_fingerprint])
    assert impact["partial_result_suppressed"] is True
    assert impact["affected_step_ids"] == []
    assert impact["affected_handoff_field_ids"] == []
    assert impact["unaffected_step_ids"] == []
    reverse = reverse_trace_composition(blocked, "overall")
    assert reverse["partial_result_suppressed"] is True
    assert reverse["steps"] == []
    assert reverse["handoff_fields"] == []
    try:
        export_portable_composition_bundle(blocked)
    except ValueError as exc:
        assert "composition_ready" in str(exc)
    else:
        raise AssertionError("blocked composition must not export a portable bundle")
