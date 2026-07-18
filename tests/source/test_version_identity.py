from __future__ import annotations

from pathlib import Path

import yaml

from researchguard import __version__


ROOT = Path(__file__).resolve().parents[2]


def test_current_source_examples_use_active_suite_version() -> None:
    example_paths = sorted((ROOT / "examples" / "source").glob("*.yaml"))
    assert example_paths
    for path in example_paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata") or {}
        if "version" in metadata:
            assert str(metadata["version"]) == __version__, path
