from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from researchguard import __version__
from researchguard.logic import mesh_store
from researchguard.logic.model_store import canonical_digest
from researchguard.logic.schema import MESH_SCHEMA_VERSION

from .model_mesh_test_support import build_definition, committed_models


def _expected_fingerprint() -> str:
    return canonical_digest(
        {
            "component": "researchguard.logic.file-model-mesh-store",
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "package_version": __version__,
            "publication_protocol": "mesh-catalog-shared-writer-lock-v1",
        }
    )


@pytest.mark.parametrize("predecessor_version", [None, "999.999.999"])
def test_predecessor_distribution_state_cannot_change_fingerprint(
    predecessor_version: str | None,
) -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    script = (
        "import importlib.metadata, json\n"
        "original = importlib.metadata.version\n"
        "queries = []\n"
        "def controlled(distribution):\n"
        "    if distribution != 'logicguard':\n"
        "        return original(distribution)\n"
        "    queries.append(distribution)\n"
        + (
            "    raise importlib.metadata.PackageNotFoundError(distribution)\n"
            if predecessor_version is None
            else f"    return {predecessor_version!r}\n"
        )
        + "importlib.metadata.version = controlled\n"
        "from researchguard import __version__\n"
        "from researchguard.logic import mesh_store\n"
        "print(json.dumps({'package_version': mesh_store._package_version(), "
        "'fingerprint': mesh_store.MESH_STORE_TOOL_FINGERPRINT, "
        "'queries': queries, 'researchguard_version': __version__}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=source_root.parent,
        env={
            **dict(os.environ),
            "PYTHONPATH": str(source_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.strip().splitlines()[-1])

    assert observed["package_version"] == observed["researchguard_version"] == __version__
    assert observed["fingerprint"] == _expected_fingerprint()
    assert observed["queries"] == []


def test_mesh_commit_receipt_uses_current_researchguard_identity(tmp_path) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = mesh_store.FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    transaction = store.begin(
        "brain-main",
        None,
        "current-package-identity",
        "package-identity-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))

    receipt = transaction.commit()

    assert receipt.package_version == __version__
    assert receipt.tool_fingerprint == _expected_fingerprint()
