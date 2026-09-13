from __future__ import annotations

import json
from pathlib import Path

from scripts.check_researchguard_privacy import scan_staged_diff, scan_tree


def test_clean_candidate_tree_passes(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("Public consumer instructions\n", encoding="utf-8")
    (tmp_path / "consumer-release.json").write_text("{}\n", encoding="utf-8")

    result = scan_tree(tmp_path, label="clean")

    assert result["status"] == "passed"
    assert result["files_scanned"] == 2
    assert result["findings"] == []
    assert str(result["report_fingerprint"]).startswith("sha256:")


def test_private_control_and_machine_path_are_blocked(tmp_path: Path) -> None:
    private = tmp_path / ".flowguard" / "evidence"
    private.mkdir(parents=True)
    (private / "run.json").write_text(
        '{"locator":"D:\\\\Users\\\\liu_y\\\\private"}\n',
        encoding="utf-8",
    )

    result = scan_tree(tmp_path, label="unsafe")
    codes = {row["code"] for row in result["findings"]}

    assert result["status"] == "blocked"
    assert "private_control_path" in codes
    assert "machine_path_leak" in codes


def test_placeholder_and_public_words_are_not_secrets(tmp_path: Path) -> None:
    (tmp_path / "references.md").write_text(
        "Use %USERPROFILE% in the local setup. Evidence and token boundaries remain descriptive.\n",
        encoding="utf-8",
    )

    result = scan_tree(tmp_path, label="placeholder")

    assert result["status"] == "passed"


def test_credential_shaped_content_is_blocked(tmp_path: Path) -> None:
    (tmp_path / "config.txt").write_text(
        "api_key = sk-123456789012345678901234\n",
        encoding="utf-8",
    )

    result = scan_tree(tmp_path, label="credential")
    codes = {row["code"] for row in result["findings"]}

    assert result["status"] == "blocked"
    assert "credential_like_value" in codes
    assert "credential_like_assignment" in codes


def test_staged_diff_empty_is_fail_closed(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = scan_staged_diff(tmp_path)
    assert result["status"] == "blocked"
    assert result["findings"][0]["code"] == "git_unavailable"
