from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from researchguard import __version__
from researchguard.logic.identity import EdgeId
from researchguard.logic.mesh_store import FileModelMeshStore
from researchguard.logic.model_mesh import CrossModelEdge, MeshMembership, ModelMeshDefinition
from researchguard.logic.model_store import canonical_digest, canonical_json_bytes
from researchguard.logic.provenance import content_hash_for
from researchguard.logic.schema import MESH_SCHEMA_VERSION, SCHEMA_VERSION

from .model_mesh_test_support import (
    FIXED_ACTOR,
    FIXED_TIME,
    commit_model,
    mesh_provenance,
    model_ref,
    node_ref,
    registry_entry,
)


def load_scale_recipe(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "profile_id",
        "model_count",
        "nodes_per_model",
        "local_edges_per_model",
        "cross_edge_count",
        "membership_stride",
        "expected_qualified_nodes",
        "expected_combined_edges",
        "capped_materialization_nodes",
        "thresholds",
    }
    missing = sorted(required.difference(raw))
    if missing:
        raise ValueError("scale recipe is missing fields: " + ", ".join(missing))
    return raw


def scale_recipe_digest(recipe: Mapping[str, Any]) -> str:
    return canonical_digest(dict(recipe))


SCALE_OWNER_INPUTS = (
    "pyproject.toml",
    "src/researchguard/logic/model_store.py",
    "src/researchguard/logic/file_model_store.py",
    "src/researchguard/logic/store_validation.py",
    "src/researchguard/logic/provenance.py",
    "src/researchguard/logic/evaluation_overlay.py",
    "src/researchguard/logic/evaluator.py",
    "src/researchguard/logic/execution_depth.py",
    "src/researchguard/logic/model_mesh.py",
    "src/researchguard/logic/mesh_index.py",
    "src/researchguard/logic/mesh_materialization.py",
    "src/researchguard/logic/mesh_overlay.py",
    "src/researchguard/logic/mesh_overlay_catalog.py",
    "src/researchguard/logic/mesh_invalidation.py",
    "src/researchguard/logic/mesh_scc.py",
    "src/researchguard/logic/mesh_evaluator.py",
    "src/researchguard/logic/mesh_simulator.py",
    "tests/logic/model_mesh_scale_support.py",
    "tests/logic/test_model_mesh_scale.py",
    "tests/logic/fixtures/model_mesh_scale/profile-v1.json",
)


def scale_owner_input_digest(root: Path) -> str:
    records = []
    for relative in SCALE_OWNER_INPUTS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"scale owner input is missing: {relative}")
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return canonical_digest(records)


def _scale_model_payload(model_index: int, recipe: Mapping[str, Any]) -> dict[str, Any]:
    model_id = f"scale-model-{model_index:03d}"
    nodes: dict[str, dict[str, Any]] = {
        "claim-root": {
            "type": "Claim",
            "text": f"Reference conclusion {model_index:03d}",
        }
    }
    evidence_ids = []
    for node_index in range(int(recipe["nodes_per_model"]) - 1):
        node_id = f"evidence-{node_index:03d}"
        text = f"Reference observation {model_index:03d}/{node_index:03d}"
        evidence_ids.append(node_id)
        nodes[node_id] = {
            "type": "Evidence",
            "text": text,
            "provenance": [
                {
                    "origin_kind": "test_result",
                    "source_id": f"scale-source-{model_index:03d}-{node_index:03d}",
                    "content_hash": content_hash_for(text),
                    "observed_at": FIXED_TIME,
                    "independence_group": (
                        f"scale-group-{model_index:03d}-{node_index:03d}"
                    ),
                }
            ],
        }
    edges = []
    for node_index, node_id in enumerate(evidence_ids):
        edges.append(
            {
                "id": f"support-{node_index:03d}",
                "source": node_id,
                "target": "claim-root",
                "type": "supports",
            }
        )
        edges.append(
            {
                "id": f"context-{node_index:03d}",
                "source": node_id,
                "target": "claim-root",
                "type": "contextualizes",
            }
        )
    edges.append(
        {
            "id": "root-context-loop-boundary",
            "source": "claim-root",
            "target": evidence_ids[0],
            "type": "contextualizes",
        }
    )
    if len(edges) != int(recipe["local_edges_per_model"]):
        raise AssertionError("scale recipe local edge count does not match generator")
    return {
        "model": {
            "id": model_id,
            "title": f"Reference model {model_index:03d}",
            "root_claim": "claim-root",
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": nodes,
        "edges": edges,
        "acceptance": {},
        "hierarchy": {},
        "blocks": {
            "block-root": {
                "id": "block-root",
                "title": f"Reference card {model_index:03d}",
                "root_claim": "claim-root",
                "member_nodes": ["claim-root", *evidence_ids],
                "input_nodes": evidence_ids,
                "output_claims": ["claim-root"],
            }
        },
    }


def build_scale_store(root: Path, recipe: Mapping[str, Any]):
    from researchguard.logic.file_model_store import FileModelStore

    p0 = FileModelStore(root / "p0")
    snapshots = tuple(
        commit_model(
            p0,
            f"scale-model-{index:03d}",
            payload=_scale_model_payload(index, recipe),
            idempotency_key=f"scale-model-{index:03d}",
        )
        for index in range(int(recipe["model_count"]))
    )
    memberships = []
    stride = int(recipe["membership_stride"])
    for model_index, snapshot in enumerate(snapshots):
        target = snapshots[(model_index + 1) % len(snapshots)]
        for node_index in range(0, int(recipe["nodes_per_model"]), stride):
            node_id = "claim-root" if node_index == 0 else f"evidence-{node_index - 1:03d}"
            memberships.append(
                MeshMembership(
                    owner=node_ref(snapshot, node_id),
                    logical_model=model_ref(target),
                    roles=("reference-cross-membership",),
                    role_metadata={"fixture": str(recipe["profile_id"])},
                    provenance=(mesh_provenance(f"scale-membership-{model_index}-{node_index}"),),
                )
            )
    cross_edges = tuple(
        CrossModelEdge(
            id=EdgeId(f"scale-cross-{index:03d}"),
            source=node_ref(snapshot, "evidence-000"),
            target=node_ref(snapshots[(index + 1) % len(snapshots)], "claim-root"),
            type="supports",
            explanation="Reference ring dependency with grounded evidence",
            provenance=(mesh_provenance(f"scale-cross-{index:03d}"),),
        )
        for index, snapshot in enumerate(snapshots)
    )
    definition = ModelMeshDefinition(
        mesh_id="brain-scale-reference",
        registry=tuple(registry_entry(snapshot) for snapshot in snapshots),
        memberships=tuple(memberships),
        cross_model_edges=cross_edges,
        provenance=(mesh_provenance("scale-mesh"),),
        metadata={
            "fixture_profile": str(recipe["profile_id"]),
            "fixture_digest": scale_recipe_digest(recipe),
        },
    )
    store = FileModelMeshStore(root / "mesh", model_store=p0)
    transaction = store.begin(
        definition.mesh_id,
        None,
        "scale-mesh-first",
        FIXED_ACTOR,
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(definition)
    receipt = transaction.commit()
    return p0, snapshots, store, receipt


def current_rss_bytes() -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        class ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        handle = kernel32.GetCurrentProcess()
        try:
            get_memory_info = kernel32.K32GetProcessMemoryInfo
        except AttributeError:
            get_memory_info = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        get_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCountersEx),
            wintypes.DWORD,
        ]
        get_memory_info.restype = wintypes.BOOL
        ok = get_memory_info(
            handle, ctypes.byref(counters), counters.cb
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.WorkingSetSize)
    statm = Path("/proc/self/statm")
    if statm.exists():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    import resource

    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return maximum if sys.platform == "darwin" else maximum * 1024


def available_memory_bytes() -> int:
    if sys.platform == "win32":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.ullAvailPhys)
    page_size = os.sysconf("SC_PAGE_SIZE")
    return int(os.sysconf("SC_AVPHYS_PAGES")) * page_size


@dataclass
class PeakRssSampler:
    interval_seconds: float = 0.005

    def __post_init__(self) -> None:
        self.baseline = current_rss_bytes()
        self.peak = self.baseline
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="mesh-scale-rss", daemon=False)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.peak = max(self.peak, current_rss_bytes())

    def __enter__(self) -> "PeakRssSampler":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.peak = max(self.peak, current_rss_bytes())
        self._stop.set()
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise RuntimeError("RSS sampler did not terminate")

    @property
    def additional_peak_bytes(self) -> int:
        return max(self.peak - self.baseline, 0)


def environment_evidence() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "researchguard_version": __version__,
        "model_store_schema": SCHEMA_VERSION,
        "mesh_schema": MESH_SCHEMA_VERSION,
        "cpu": platform.processor() or platform.machine() or "unknown",
        "logical_cpu_count": os.cpu_count() or 1,
        "available_memory_bytes_at_receipt": available_memory_bytes(),
        "clock": "time.perf_counter",
        "memory_method": "5ms current-process RSS sampler",
    }


def write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_json_bytes(dict(payload)) + b"\n")
    temporary.replace(path)


__all__ = [
    "PeakRssSampler",
    "build_scale_store",
    "environment_evidence",
    "load_scale_recipe",
    "scale_owner_input_digest",
    "scale_recipe_digest",
    "write_receipt",
]
