"""User-owned argument model workflow for LogicGuard."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import yaml


def create_argument_model(
    output: str | Path,
    *,
    model_id: str,
    title: str,
    root_claim: str,
    section_claims: Iterable[str] = (),
    metadata: Mapping[str, object] | None = None,
) -> Path:
    """Create a small LogicGuard model for the user's own argument."""

    path = Path(output)
    model_metadata = dict(metadata or {})
    raw: dict[str, object] = {
        "model": {
            "id": model_id,
            "title": title,
            "root_claim": "C0",
            **model_metadata,
        },
        "nodes": {
            "C0": {
                "type": "Claim",
                "text": root_claim,
                "level": "root",
            }
        },
        "edges": [],
        "acceptance": {},
        "hierarchy": {"C0": []},
    }
    nodes = raw["nodes"]  # type: ignore[index]
    edges = raw["edges"]  # type: ignore[index]
    children: list[str] = []
    for index, claim in enumerate(section_claims, start=1):
        node_id = f"C{index}"
        nodes[node_id] = {  # type: ignore[index]
            "type": "Claim",
            "text": str(claim),
            "level": "section",
            "parent": "C0",
        }
        edges.append({"source": node_id, "target": "C0", "type": "supports", "weight": 0.7})  # type: ignore[union-attr]
        children.append(node_id)
    raw["hierarchy"] = {"C0": children}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return path
