"""Executable owner for TraceGuard to LogicGuard domain export separation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "trace_domain_export"
CODE_OWNER = "src/researchguard/trace/export_logicguard.py"
TEST_OWNER = "tests/trace/test_traceguard.py"
PROTECTED_FAILURE_IDS = (
    "researchguard:trace_domain_export:domain-proposition-missing",
    "researchguard:trace_domain_export:mechanism-reference-missing",
    "researchguard:trace_domain_export:audit-context-promoted-to-domain",
    "researchguard:trace_domain_export:temporal-order-promoted-to-causality",
)
KNOWN_GOOD_CASE_ID = "native:trace_domain_export:current-good"
KNOWN_BAD_CASE_IDS = (
    "case:trace_domain_export:domain-proposition-missing",
    "case:trace_domain_export:mechanism-reference-missing",
    "case:trace_domain_export:audit-context-promoted-to-domain",
    "case:trace_domain_export:temporal-order-promoted-to-causality",
)
DOMAIN_FIELDS = (
    "domain_proposition",
    "trace_title",
    "trace_id",
    "domain_mechanism_refs",
    "evidence_ids",
    "domain_assumption_refs",
    "object_scope",
    "material_alternatives",
)


@dataclass(frozen=True)
class ExportState:
    proposition_present: bool
    mechanism_refs_present: bool
    audit_context_is_separate: bool
    temporal_causality_not_inferred: bool

    @property
    def accepted(self) -> bool:
        return all((
            self.proposition_present,
            self.mechanism_refs_present,
            self.audit_context_is_separate,
            self.temporal_causality_not_inferred,
        ))


def run_model() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from researchguard.trace.export_logicguard import validate_logicguard_bundle
    try:
        validate_logicguard_bundle({})
    except ValueError as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("legacy empty LogicGuard export was accepted")
    assert "domain_proposition" in DOMAIN_FIELDS
    assert "audit_context" not in DOMAIN_FIELDS
    good = ExportState(True, True, True, True)
    assert good.accepted
    for index in range(4):
        values = [True] * 4
        values[index] = False
        assert not ExportState(*values).accepted


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
