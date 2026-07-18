"""Immutable, revision-bound evaluation overlays.

Canonical ``LogicModel`` content records authoring inputs.  Evaluated
``IN``/``OUT``/``UNDECIDED`` states belong here instead: in an immutable
artifact bound to one model revision, one requested claim scope, one
authoritative universe, and one evaluator implementation.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable

from .evaluator import evaluate_model
from .identity import EvaluationId, ModelId, ModelRevision
from .model import EvaluationResult, LogicModel, NodeEvaluation
from .schema import EVALUATION_OVERLAY_SCHEMA, SCHEMA_VERSION


EVALUATION_CLAIM_BOUNDARY = (
    "This overlay records a structural evaluation of the exact declared model "
    "revision, claim scope, authoritative universe, and evaluator. It does not "
    "establish factual truth or license claims outside that boundary."
)

_COMPLETENESS_STATES = {"complete", "partial"}
_PROFILES = {"broad", "bounded"}


class EvaluationOverlayError(ValueError):
    """Raised when an overlay is malformed or uses a non-current schema."""


@runtime_checkable
class EvaluationSnapshot(Protocol):
    """Small duck-typed boundary required by :func:`evaluate_snapshot`."""

    model_id: Any
    revision: Any
    content_digest: str

    def to_model(self) -> LogicModel: ...


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def _canonical_ids(values: Iterable[Any]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    normalized = {
        str(value)
        for value in values
        if value is not None and str(value)
    }
    return tuple(sorted(normalized))


def fingerprint_authoritative_universe(values: Iterable[Any]) -> str:
    """Return the deterministic fingerprint for a declared universe of IDs."""

    return _sha256({"authoritative_universe": list(_canonical_ids(values))})


def fingerprint_evaluator(function: Callable[..., Any] = evaluate_model) -> str:
    """Fingerprint the actual evaluator implementation used for an overlay."""

    try:
        source = inspect.getsource(function)
    except (OSError, TypeError):
        code = getattr(function, "__code__", None)
        source = repr(code.co_code if code is not None else function)
    binding = {
        "module": getattr(function, "__module__", ""),
        "qualname": getattr(function, "__qualname__", repr(function)),
        "source": source,
    }
    return _sha256(binding)


@dataclass(frozen=True)
class OverlayNodeResult:
    """Frozen projection of one native :class:`NodeEvaluation`."""

    node_id: str
    state: str
    confidence: float
    explanation: str = ""
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id:
            raise EvaluationOverlayError("overlay node result requires node_id")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise EvaluationOverlayError("overlay node confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", round(confidence, 6))
        object.__setattr__(self, "blockers", tuple(str(item) for item in self.blockers))

    @classmethod
    def from_evaluation(cls, result: NodeEvaluation) -> "OverlayNodeResult":
        return cls(
            node_id=result.node_id,
            state=result.state,
            confidence=result.confidence,
            explanation=result.explanation,
            blockers=tuple(result.blockers),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state,
            "confidence": round(self.confidence, 6),
            "explanation": self.explanation,
            "blockers": list(self.blockers),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayNodeResult":
        return cls(
            node_id=str(raw.get("node_id", "")),
            state=str(raw.get("state", "")),
            confidence=float(raw.get("confidence", 0.0)),
            explanation=str(raw.get("explanation", "")),
            blockers=tuple(str(item) for item in (raw.get("blockers") or ())),
        )


@dataclass(frozen=True)
class CurrentnessDiagnostic:
    code: str
    message: str
    blocks_binding_currentness: bool = False
    blocks_broad_currentness: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "blocks_binding_currentness": self.blocks_binding_currentness,
            "blocks_broad_currentness": self.blocks_broad_currentness,
        }


@dataclass(frozen=True)
class OverlayCurrentness:
    """Exact binding and broad-claim status for one overlay comparison."""

    binding_current: bool
    current: bool
    broad_current: bool
    diagnostics: tuple[CurrentnessDiagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.current

    @property
    def broad_claim_licensed(self) -> bool:
        return self.broad_current

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_current": self.binding_current,
            "current": self.current,
            "broad_current": self.broad_current,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class EvaluationOverlay:
    """One immutable structural evaluation of one immutable model snapshot."""

    model_id: ModelId
    revision: ModelRevision
    content_digest: str
    evaluator_fingerprint: str
    requested_claim_scope: tuple[str, ...]
    authoritative_universe_fingerprint: str
    profile: str
    completeness: str
    truncated: bool
    node_results: Mapping[str, OverlayNodeResult]
    cycles: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()
    claim_boundary: str = EVALUATION_CLAIM_BOUNDARY
    artifact_schema: str = EVALUATION_OVERLAY_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    _evaluation_id: EvaluationId | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        object.__setattr__(self, "revision", ModelRevision.parse(self.revision))
        if self.artifact_schema != EVALUATION_OVERLAY_SCHEMA:
            raise EvaluationOverlayError(
                f"unsupported evaluation overlay schema {self.artifact_schema!r}; "
                f"expected {EVALUATION_OVERLAY_SCHEMA!r}"
            )
        if self.store_schema_version != SCHEMA_VERSION:
            raise EvaluationOverlayError(
                f"unsupported store schema {self.store_schema_version!r}; "
                f"expected {SCHEMA_VERSION!r}"
            )
        if not self.content_digest:
            raise EvaluationOverlayError("evaluation overlay requires content_digest")
        if not self.evaluator_fingerprint:
            raise EvaluationOverlayError("evaluation overlay requires evaluator_fingerprint")
        if not self.authoritative_universe_fingerprint:
            raise EvaluationOverlayError(
                "evaluation overlay requires authoritative_universe_fingerprint"
            )
        if self.profile not in _PROFILES:
            raise EvaluationOverlayError(
                f"unsupported evaluation profile {self.profile!r}; expected broad or bounded"
            )
        if self.completeness not in _COMPLETENESS_STATES:
            raise EvaluationOverlayError(
                f"unsupported completeness {self.completeness!r}; expected complete or partial"
            )
        if not self.claim_boundary:
            raise EvaluationOverlayError("evaluation overlay requires claim_boundary")

        scope = _canonical_ids(self.requested_claim_scope)
        object.__setattr__(self, "requested_claim_scope", scope)
        frozen_results: dict[str, OverlayNodeResult] = {}
        for key, value in self.node_results.items():
            node_id = str(key)
            if isinstance(value, OverlayNodeResult):
                result = value
            elif isinstance(value, NodeEvaluation):
                result = OverlayNodeResult.from_evaluation(value)
            elif isinstance(value, Mapping):
                result = OverlayNodeResult.from_dict(value)
            else:
                raise EvaluationOverlayError(
                    f"node result {node_id!r} must be an OverlayNodeResult, "
                    "NodeEvaluation, or mapping"
                )
            if result.node_id != node_id:
                raise EvaluationOverlayError(
                    f"node result key {node_id!r} does not match node_id {result.node_id!r}"
                )
            frozen_results[node_id] = result
        object.__setattr__(
            self,
            "node_results",
            MappingProxyType({key: frozen_results[key] for key in sorted(frozen_results)}),
        )
        object.__setattr__(
            self,
            "cycles",
            tuple(tuple(str(node_id) for node_id in cycle) for cycle in self.cycles),
        )
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))

        if self._evaluation_id is not None:
            supplied = EvaluationId.parse(self._evaluation_id)
            object.__setattr__(self, "_evaluation_id", supplied)
            if supplied != self.evaluation_id:
                raise EvaluationOverlayError(
                    f"evaluation_id {supplied} does not match overlay fingerprint"
                )

    @property
    def evaluation_id(self) -> EvaluationId:
        digest = self.fingerprint().removeprefix("sha256:")
        return EvaluationId(f"evaluation-{digest}")

    @property
    def model_revision_id(self) -> str:
        """Compatibility-free convenience projection for result/report bindings."""

        return str(self.revision)

    @property
    def complete(self) -> bool:
        return self.completeness == "complete"

    def _fingerprint_payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "model_id": str(self.model_id),
            "revision": str(self.revision),
            "content_digest": self.content_digest,
            "evaluator_fingerprint": self.evaluator_fingerprint,
            "requested_claim_scope": list(self.requested_claim_scope),
            "authoritative_universe_fingerprint": self.authoritative_universe_fingerprint,
            "profile": self.profile,
            "completeness": self.completeness,
            "truncated": self.truncated,
            "node_results": {
                node_id: self.node_results[node_id].to_dict()
                for node_id in sorted(self.node_results)
            },
            "cycles": [list(cycle) for cycle in self.cycles],
            "warnings": list(self.warnings),
            "claim_boundary": self.claim_boundary,
        }

    def fingerprint(self) -> str:
        """Return a deterministic content fingerprint for the complete overlay."""

        return _sha256(self._fingerprint_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._fingerprint_payload(),
            "evaluation_id": str(self.evaluation_id),
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvaluationOverlay":
        required = {
            "artifact_schema",
            "store_schema_version",
            "evaluation_id",
            "fingerprint",
            "model_id",
            "revision",
            "content_digest",
            "evaluator_fingerprint",
            "requested_claim_scope",
            "authoritative_universe_fingerprint",
            "profile",
            "completeness",
            "truncated",
            "node_results",
            "cycles",
            "warnings",
            "claim_boundary",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise EvaluationOverlayError(
                f"evaluation overlay is missing required fields: {', '.join(missing)}"
            )
        node_results_raw = raw.get("node_results")
        if not isinstance(node_results_raw, Mapping):
            raise EvaluationOverlayError("evaluation overlay node_results must be a mapping")
        if not isinstance(raw.get("truncated"), bool):
            raise EvaluationOverlayError("evaluation overlay truncated must be a boolean")
        overlay = cls(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            model_id=ModelId.parse(raw.get("model_id", "")),
            revision=ModelRevision.parse(raw.get("revision", "")),
            content_digest=str(raw.get("content_digest", "")),
            evaluator_fingerprint=str(raw.get("evaluator_fingerprint", "")),
            requested_claim_scope=tuple(
                str(item) for item in (raw.get("requested_claim_scope") or ())
            ),
            authoritative_universe_fingerprint=str(
                raw.get("authoritative_universe_fingerprint", "")
            ),
            profile=str(raw.get("profile", "")),
            completeness=str(raw.get("completeness", "")),
            truncated=bool(raw.get("truncated")),
            node_results={
                str(node_id): OverlayNodeResult.from_dict(result)
                for node_id, result in node_results_raw.items()
            },
            cycles=tuple(
                tuple(str(node_id) for node_id in cycle)
                for cycle in (raw.get("cycles") or ())
            ),
            warnings=tuple(str(item) for item in (raw.get("warnings") or ())),
            claim_boundary=str(raw.get("claim_boundary", "")),
            _evaluation_id=EvaluationId.parse(raw.get("evaluation_id", "")),
        )
        if str(raw.get("fingerprint")) != overlay.fingerprint():
            raise EvaluationOverlayError("evaluation overlay fingerprint mismatch")
        return overlay

    def currentness(
        self,
        snapshot: EvaluationSnapshot,
        *,
        expected_evaluator_fingerprint: str | None = None,
        requested_claim_scope: Iterable[Any] | None = None,
        authoritative_universe: Iterable[Any] | None = None,
        authoritative_universe_fingerprint: str | None = None,
        profile: str | None = None,
    ) -> OverlayCurrentness:
        """Compare this overlay with the exact inputs expected by a caller."""

        expected_scope = (
            _canonical_ids(requested_claim_scope)
            if requested_claim_scope is not None
            else _default_claim_scope(snapshot)
        )
        expected_universe = _resolve_universe_fingerprint(
            snapshot,
            authoritative_universe=authoritative_universe,
            authoritative_universe_fingerprint=authoritative_universe_fingerprint,
        )
        expected_evaluator = (
            expected_evaluator_fingerprint
            if expected_evaluator_fingerprint is not None
            else fingerprint_evaluator()
        )
        expected_profile = profile if profile is not None else self.profile
        diagnostics: list[CurrentnessDiagnostic] = []

        def mismatch(code: str, message: str) -> None:
            diagnostics.append(
                CurrentnessDiagnostic(
                    code=code,
                    message=message,
                    blocks_binding_currentness=True,
                )
            )

        if self.model_id != ModelId.parse(snapshot.model_id):
            mismatch("model_id_mismatch", "overlay model_id differs from the snapshot")
        if self.revision != ModelRevision.parse(snapshot.revision):
            mismatch("revision_mismatch", "overlay revision differs from the snapshot")
        if self.content_digest != str(snapshot.content_digest):
            mismatch("content_digest_mismatch", "overlay content digest differs from the snapshot")
        if self.evaluator_fingerprint != expected_evaluator:
            mismatch(
                "evaluator_fingerprint_mismatch",
                "overlay evaluator fingerprint differs from the requested evaluator",
            )
        if self.requested_claim_scope != expected_scope:
            mismatch(
                "requested_claim_scope_mismatch",
                "overlay requested claim scope differs from the requested scope",
            )
        if self.authoritative_universe_fingerprint != expected_universe:
            mismatch(
                "authoritative_universe_mismatch",
                "overlay authoritative universe differs from the requested universe",
            )
        if self.profile != expected_profile:
            mismatch("profile_mismatch", "overlay profile differs from the requested profile")

        missing_claim_results = tuple(
            claim_id
            for claim_id in self.requested_claim_scope
            if claim_id not in self.node_results
        )
        if self.completeness != "complete":
            diagnostics.append(
                CurrentnessDiagnostic(
                    code="incomplete_overlay",
                    message="overlay declares partial evaluation completeness",
                )
            )
        if self.truncated:
            diagnostics.append(
                CurrentnessDiagnostic(
                    code="truncated_overlay",
                    message="overlay evaluation was truncated",
                )
            )
        if missing_claim_results:
            diagnostics.append(
                CurrentnessDiagnostic(
                    code="requested_claim_results_missing",
                    message=(
                        "overlay lacks results for requested claims: "
                        + ", ".join(missing_claim_results)
                    ),
                )
            )
        if self.profile != "broad":
            diagnostics.append(
                CurrentnessDiagnostic(
                    code="bounded_profile",
                    message="bounded profile cannot license broad currentness",
                    blocks_binding_currentness=False,
                )
            )

        binding_current = not any(
            item.blocks_binding_currentness for item in diagnostics
        )
        current = binding_current and not any(
            item.code
            in {"incomplete_overlay", "truncated_overlay", "requested_claim_results_missing"}
            for item in diagnostics
        )
        broad_current = (
            current
            and self.profile == "broad"
            and expected_profile == "broad"
            and not any(item.blocks_broad_currentness for item in diagnostics)
        )
        return OverlayCurrentness(
            binding_current=binding_current,
            current=current,
            broad_current=broad_current,
            diagnostics=tuple(diagnostics),
        )

    def is_current(self, snapshot: EvaluationSnapshot, **expectations: Any) -> bool:
        return self.currentness(snapshot, **expectations).current

    def is_broad_current(self, snapshot: EvaluationSnapshot, **expectations: Any) -> bool:
        return self.currentness(snapshot, **expectations).broad_current


def _default_claim_scope(snapshot: EvaluationSnapshot) -> tuple[str, ...]:
    model = snapshot.to_model()
    return _canonical_ids((model.root_claim,)) if model.root_claim else ()


def _default_authoritative_universe(snapshot: EvaluationSnapshot) -> tuple[str, ...]:
    model = snapshot.to_model()
    return _canonical_ids(model.nodes)


def _resolve_universe_fingerprint(
    snapshot: EvaluationSnapshot,
    *,
    authoritative_universe: Iterable[Any] | None,
    authoritative_universe_fingerprint: str | None,
) -> str:
    if authoritative_universe is None:
        if authoritative_universe_fingerprint is not None:
            return authoritative_universe_fingerprint
        authoritative_universe = _default_authoritative_universe(snapshot)
    computed = fingerprint_authoritative_universe(authoritative_universe)
    if (
        authoritative_universe_fingerprint is not None
        and authoritative_universe_fingerprint != computed
    ):
        raise EvaluationOverlayError(
            "declared authoritative_universe_fingerprint does not match its universe"
        )
    return computed


def evaluate_snapshot(
    snapshot: EvaluationSnapshot,
    *,
    requested_claim_scope: Iterable[Any] | None = None,
    authoritative_universe: Iterable[Any] | None = None,
    authoritative_universe_fingerprint: str | None = None,
    profile: str = "broad",
    completeness: str | None = None,
    truncated: bool = False,
    evaluator: Callable[..., EvaluationResult] = evaluate_model,
    evaluator_fingerprint: str | None = None,
    max_iterations: int = 25,
    claim_boundary: str = EVALUATION_CLAIM_BOUNDARY,
) -> EvaluationOverlay:
    """Evaluate a detached snapshot model and return a durable overlay.

    The native evaluator is the default and remains injectable only as an
    explicit test/tool boundary.  Evaluation never writes state back into the
    snapshot's canonical payload.
    """

    model = snapshot.to_model()
    if str(model.id) != str(snapshot.model_id):
        raise EvaluationOverlayError(
            "snapshot model payload id does not match its snapshot model_id"
        )
    scope = (
        _canonical_ids(requested_claim_scope)
        if requested_claim_scope is not None
        else (_canonical_ids((model.root_claim,)) if model.root_claim else ())
    )
    universe_fingerprint = _resolve_universe_fingerprint(
        snapshot,
        authoritative_universe=authoritative_universe,
        authoritative_universe_fingerprint=authoritative_universe_fingerprint,
    )
    result = evaluator(model, max_iterations=max_iterations)
    if str(result.model_id) != str(snapshot.model_id):
        raise EvaluationOverlayError(
            "evaluator result model_id does not match the evaluated snapshot"
        )
    actual_fingerprint = fingerprint_evaluator(evaluator)
    if evaluator_fingerprint is not None and evaluator_fingerprint != actual_fingerprint:
        raise EvaluationOverlayError(
            "declared evaluator_fingerprint does not match the evaluator implementation"
        )

    frozen_results = {
        node_id: OverlayNodeResult.from_evaluation(node_result)
        for node_id, node_result in result.node_results.items()
    }
    missing_scope = any(claim_id not in frozen_results for claim_id in scope)
    resolved_completeness = completeness or ("partial" if missing_scope else "complete")
    return EvaluationOverlay(
        model_id=ModelId.parse(snapshot.model_id),
        revision=ModelRevision.parse(snapshot.revision),
        content_digest=str(snapshot.content_digest),
        evaluator_fingerprint=actual_fingerprint,
        requested_claim_scope=scope,
        authoritative_universe_fingerprint=universe_fingerprint,
        profile=profile,
        completeness=resolved_completeness,
        truncated=bool(truncated or not result.converged),
        node_results=frozen_results,
        cycles=tuple(tuple(node_id for node_id in cycle) for cycle in result.cycles),
        warnings=tuple(result.warnings),
        claim_boundary=claim_boundary,
    )


def diagnose_currentness(
    overlay: EvaluationOverlay,
    snapshot: EvaluationSnapshot,
    **expectations: Any,
) -> OverlayCurrentness:
    """Functional form of :meth:`EvaluationOverlay.currentness`."""

    return overlay.currentness(snapshot, **expectations)


__all__ = [
    "CurrentnessDiagnostic",
    "EVALUATION_CLAIM_BOUNDARY",
    "EvaluationOverlay",
    "EvaluationOverlayError",
    "EvaluationSnapshot",
    "OverlayCurrentness",
    "OverlayNodeResult",
    "diagnose_currentness",
    "evaluate_snapshot",
    "fingerprint_authoritative_universe",
    "fingerprint_evaluator",
]
