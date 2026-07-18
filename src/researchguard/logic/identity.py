"""Stable, portable identities for durable LogicGuard artifacts."""

from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping, TypeVar


class IdentityError(ValueError):
    """Raised when a durable identity is unsafe or non-portable."""


_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[/\\]")


@dataclass(frozen=True, order=True)
class _StringIdentity:
    """Validated string-backed identity base class.

    Values are deliberately preserved byte-for-byte after NFC validation.  In
    particular, identities are never lower-cased or rewritten for a platform.
    Filesystem projection is handled separately by :func:`encode_path_segment`.
    """

    value: str
    kind: ClassVar[str] = "identity"

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise IdentityError(f"{self.kind} must be a string")
        if not self.value:
            raise IdentityError(f"{self.kind} must not be empty")
        if unicodedata.normalize("NFC", self.value) != self.value:
            raise IdentityError(f"{self.kind} must already use NFC normalization")
        if any(ord(char) < 32 or ord(char) == 127 for char in self.value):
            raise IdentityError(f"{self.kind} contains a control character")
        if "/" in self.value or "\\" in self.value:
            raise IdentityError(f"{self.kind} contains a non-portable path separator")
        if self.value in {".", ".."} or ".." in self.value:
            raise IdentityError(f"{self.kind} contains a traversal segment")
        if _DRIVE_PATH_PATTERN.match(self.value):
            raise IdentityError(f"{self.kind} must not be an absolute path")
        if not _IDENTITY_PATTERN.fullmatch(self.value):
            raise IdentityError(
                f"{self.kind} must match portable grammar {_IDENTITY_PATTERN.pattern!r}"
            )

    def __str__(self) -> str:
        return self.value

    def to_dict(self) -> str:
        return self.value

    @classmethod
    def parse(cls: type[_IdentityT], value: Any) -> _IdentityT:
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise IdentityError(f"{cls.kind} must be a string")
        return cls(value)


_IdentityT = TypeVar("_IdentityT", bound=_StringIdentity)


@dataclass(frozen=True, order=True)
class ModelId(_StringIdentity):
    kind: ClassVar[str] = "model_id"


@dataclass(frozen=True, order=True)
class ModelRevision(_StringIdentity):
    kind: ClassVar[str] = "model_revision"


@dataclass(frozen=True, order=True)
class NodeId(_StringIdentity):
    kind: ClassVar[str] = "node_id"


@dataclass(frozen=True, order=True)
class EdgeId(_StringIdentity):
    kind: ClassVar[str] = "edge_id"


@dataclass(frozen=True, order=True)
class BlockId(_StringIdentity):
    kind: ClassVar[str] = "block_id"


@dataclass(frozen=True, order=True)
class TransactionId(_StringIdentity):
    kind: ClassVar[str] = "transaction_id"


@dataclass(frozen=True, order=True)
class EvaluationId(_StringIdentity):
    kind: ClassVar[str] = "evaluation_id"


@dataclass(frozen=True, order=True)
class ReceiptId(_StringIdentity):
    kind: ClassVar[str] = "receipt_id"


@dataclass(frozen=True, order=True)
class MeshId(_StringIdentity):
    kind: ClassVar[str] = "mesh_id"


@dataclass(frozen=True, order=True)
class MeshRevision(_StringIdentity):
    kind: ClassVar[str] = "mesh_revision"


@dataclass(frozen=True, order=True)
class MeshTransactionId(_StringIdentity):
    kind: ClassVar[str] = "mesh_transaction_id"


@dataclass(frozen=True, order=True)
class MeshReceiptId(_StringIdentity):
    kind: ClassVar[str] = "mesh_receipt_id"


@dataclass(frozen=True, order=True)
class MeshEvaluationId(_StringIdentity):
    kind: ClassVar[str] = "mesh_evaluation_id"


@dataclass(frozen=True, order=True)
class OverlayCatalogRevision(_StringIdentity):
    kind: ClassVar[str] = "overlay_catalog_revision"


@dataclass(frozen=True, order=True)
class QualifiedModelRef:
    """One exact immutable physical model version selected by a mesh."""

    model_id: ModelId
    revision: ModelRevision

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        if self.revision in (None, ""):
            raise IdentityError("qualified model reference is missing required revision field")
        object.__setattr__(self, "revision", ModelRevision.parse(self.revision))

    def to_dict(self) -> dict[str, str]:
        return {"model_id": str(self.model_id), "revision": str(self.revision)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QualifiedModelRef":
        if not raw.get("revision"):
            raise IdentityError("qualified model reference is missing required revision field")
        return cls(
            model_id=ModelId.parse(raw.get("model_id", "")),
            revision=ModelRevision.parse(raw["revision"]),
        )


@dataclass(frozen=True, order=True)
class QualifiedNodeRef:
    """A durable node reference pinned to one immutable model revision."""

    model_id: ModelId
    revision: ModelRevision
    node_id: NodeId

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        if self.revision in (None, ""):
            raise IdentityError("qualified node reference is missing required revision field")
        object.__setattr__(self, "revision", ModelRevision.parse(self.revision))
        object.__setattr__(self, "node_id", NodeId.parse(self.node_id))

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": str(self.model_id),
            "revision": str(self.revision),
            "node_id": str(self.node_id),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QualifiedNodeRef":
        if not raw.get("revision"):
            raise IdentityError("qualified node reference is missing required revision field")
        return cls(
            model_id=ModelId.parse(raw.get("model_id", "")),
            revision=ModelRevision.parse(raw["revision"]),
            node_id=NodeId.parse(raw.get("node_id", "")),
        )


def encode_path_segment(identity: _StringIdentity | str) -> str:
    """Encode an identity as a reversible, platform-neutral path segment."""

    value = str(identity)
    # Validate raw strings before they become path material.
    _StringIdentity(value)
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return f"id-{encoded}"


def decode_path_segment(segment: str) -> str:
    """Reverse :func:`encode_path_segment` and revalidate the result."""

    if not isinstance(segment, str) or not segment.startswith("id-"):
        raise IdentityError("encoded identity path segment must start with 'id-'")
    encoded = segment[3:]
    if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise IdentityError("encoded identity path segment is malformed")
    padding = "=" * (-len(encoded) % 4)
    try:
        value = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise IdentityError("encoded identity path segment is malformed") from exc
    _StringIdentity(value)
    if encode_path_segment(value) != segment:
        raise IdentityError("encoded identity path segment is not canonical")
    return value


__all__ = [
    "BlockId",
    "EdgeId",
    "EvaluationId",
    "IdentityError",
    "MeshEvaluationId",
    "MeshId",
    "MeshReceiptId",
    "MeshRevision",
    "MeshTransactionId",
    "ModelId",
    "ModelRevision",
    "NodeId",
    "OverlayCatalogRevision",
    "QualifiedModelRef",
    "QualifiedNodeRef",
    "ReceiptId",
    "TransactionId",
    "decode_path_segment",
    "encode_path_segment",
]
