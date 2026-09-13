"""Fail-closed privacy scan for ResearchGuard publication candidates.

The scanner is deliberately scoped to a candidate tree (consumer projection,
unpacked distribution, or another release staging directory) and to the
contents of the current staged Git diff.  It is not a replacement for
SkillGuard's projection audit or the installer currentness check.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, Mapping, Sequence


SCHEMA_VERSION = "researchguard.privacy-scan.v1"

# These are author/control or runtime residue names.  A public document may
# discuss evidence or tokens, so only path components and file names that
# unambiguously identify private material are rejected here.
FORBIDDEN_COMPONENTS = frozenset(
    {
        ".git",
        ".flowguard",
        ".skillguard",
        "__pycache__",
        ".pytest_cache",
        "evidence",
        "receipts",
        "attempts",
        "implementation-round5-evidence",
        "implementation-round6-evidence",
        "tmp-native-probe",
    }
)
FORBIDDEN_NAME = re.compile(
    r"(?ix)"
    r"(?:^|[-_.])(?:"
    r"cookie|cookies|credential|credentials|secret|secrets|"
    r"access[-_]?token|api[-_]?key|private[-_]?key|session|"
    r"raw[-_]?log|events"
    r")(?:$|[-_.])"
)
FORBIDDEN_SUFFIXES = frozenset({".log", ".jsonl", ".sqlite", ".db"})

# Placeholder variables such as %USERPROFILE% are safe documentation text;
# actual resolved user/home paths are not.  Keep the patterns conservative so
# ordinary technical prose containing the word "path" is not rejected.
WINDOWS_USER_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]+users[\\/]+)[^\\/\r\n\"']+")
POSIX_USER_PATH = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^/\r\n\"']+")
OPENAI_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
SECRET_ASSIGNMENT = re.compile(
    r"(?is)\b(?:api[-_]?key|access[-_]?token|secret|password|private[-_]?key)\b"
    r"\s*[:=]\s*[\"']?([A-Za-z0-9+/=_-]{16,})"
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "detail": self.detail}


def _normal_relative(path: str | Path) -> str:
    # Remove only explicit ``./`` prefixes.  A leading dot is meaningful for
    # control directories such as ``.skillguard`` and ``.flowguard`` and must
    # remain visible to the path policy.
    value = Path(path).as_posix()
    while value.startswith("./"):
        value = value[2:]
    return value or "."


def _path_findings(relative: str) -> list[Finding]:
    path = Path(relative)
    parts = tuple(part for part in path.parts if part not in {"", "."})
    findings: list[Finding] = []
    for component in parts:
        if component in FORBIDDEN_COMPONENTS:
            findings.append(
                Finding(
                    "private_control_path",
                    _normal_relative(relative),
                    f"path component is reserved for author or runtime control data: {component}",
                )
            )
    name = path.name
    if FORBIDDEN_NAME.search(name) or path.suffix.lower() in FORBIDDEN_SUFFIXES:
        findings.append(
            Finding(
                "private_artifact_name",
                _normal_relative(relative),
                "file name identifies a private credential, session, event, or runtime log artifact",
            )
        )
    return findings


def _content_findings(relative: str, data: bytes) -> list[Finding]:
    # Binary assets are checked by path only.  UTF-8 decoding with replacement
    # makes the scan deterministic while avoiding false positives from binary
    # byte sequences.
    text = data.decode("utf-8", errors="replace")
    findings: list[Finding] = []
    if WINDOWS_USER_PATH.search(text):
        findings.append(
            Finding(
                "machine_path_leak",
                _normal_relative(relative),
                "content contains a resolved Windows user path",
            )
        )
    if POSIX_USER_PATH.search(text):
        findings.append(
            Finding(
                "machine_path_leak",
                _normal_relative(relative),
                "content contains a resolved POSIX user path",
            )
        )
    if OPENAI_TOKEN.search(text) or GITHUB_TOKEN.search(text):
        findings.append(
            Finding(
                "credential_like_value",
                _normal_relative(relative),
                "content contains a credential-shaped token",
            )
        )
    if SECRET_ASSIGNMENT.search(text):
        findings.append(
            Finding(
                "credential_like_assignment",
                _normal_relative(relative),
                "content contains a non-placeholder secret or credential assignment",
            )
        )
    return findings


def _scan_file(relative: str, data: bytes) -> list[Finding]:
    return _path_findings(relative) + _content_findings(relative, data)


def _report(
    *,
    scope: str,
    roots: Sequence[str],
    files_scanned: int,
    findings: Iterable[Finding],
    source_fingerprint: str = "",
) -> dict[str, object]:
    rows = sorted(
        (finding.as_dict() for finding in findings),
        key=lambda row: (row["path"], row["code"], row["detail"]),
    )
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": scope,
        "roots": list(roots),
        "files_scanned": files_scanned,
        "findings": rows,
        "status": "blocked" if rows else "passed",
        "claim_boundary": (
            "This scan checks only candidate publication paths and their bytes; "
            "it does not prove semantic correctness, package installation, or GitHub publication."
        ),
    }
    if source_fingerprint:
        body["source_fingerprint"] = source_fingerprint
    body["report_fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return body


def scan_tree(root: Path, *, label: str | None = None) -> dict[str, object]:
    """Scan one candidate tree without following links or reparse points."""

    lexical = Path(root).expanduser()
    root_label = label or str(lexical)
    findings: list[Finding] = []
    files_scanned = 0
    if not lexical.exists() or not lexical.is_dir():
        findings.append(Finding("root_missing", ".", "candidate root is missing or not a directory"))
        return _report(scope="tree", roots=[root_label], files_scanned=0, findings=findings)
    for item in sorted(lexical.rglob("*"), key=lambda path: path.as_posix().lower()):
        try:
            relative = item.relative_to(lexical)
            if item.is_symlink() or bool(getattr(item.stat(), "st_file_attributes", 0) & 0x400):
                findings.append(
                    Finding("unsafe_link", _normal_relative(relative), "candidate tree contains a link or reparse point")
                )
                continue
            if not item.is_file():
                continue
            files_scanned += 1
            findings.extend(_scan_file(_normal_relative(relative), item.read_bytes()))
        except (OSError, RuntimeError) as exc:
            findings.append(
                Finding("read_error", _normal_relative(relative), f"candidate file could not be read: {type(exc).__name__}")
            )
    return _report(scope="tree", roots=[root_label], files_scanned=files_scanned, findings=findings)


def _git_output(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[:240]
        raise RuntimeError(f"git command failed ({completed.returncode}): {detail}")
    return completed.stdout


def scan_staged_diff(repo_root: Path) -> dict[str, object]:
    """Scan added/copied/modified staged blobs by their index bytes."""

    repo = Path(repo_root).expanduser().resolve()
    findings: list[Finding] = []
    files_scanned = 0
    try:
        raw = _git_output(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    except (OSError, RuntimeError) as exc:
        findings.append(Finding("git_unavailable", ".", str(exc)))
        return _report(scope="staged-diff", roots=[str(repo)], files_scanned=0, findings=findings)
    names = [name.decode("utf-8", errors="strict") for name in raw.split(b"\0") if name]
    if not names:
        findings.append(Finding("staged_diff_empty", ".", "no added, copied, or modified staged files were found"))
    for name in names:
        relative = _normal_relative(name)
        findings.extend(_path_findings(relative))
        try:
            data = _git_output(repo, "show", f":{name}")
        except (OSError, RuntimeError) as exc:
            findings.append(Finding("staged_blob_unreadable", relative, str(exc)))
            continue
        files_scanned += 1
        findings.extend(_content_findings(relative, data))
    return _report(scope="staged-diff", roots=[str(repo)], files_scanned=files_scanned, findings=findings)


def scan_trees(roots: Sequence[Path]) -> dict[str, object]:
    all_findings: list[Finding] = []
    labels: list[str] = []
    files_scanned = 0
    for root in roots:
        result = scan_tree(root)
        labels.extend(str(item) for item in result["roots"])
        files_scanned += int(result["files_scanned"])
        all_findings.extend(
            Finding(str(row["code"]), f"{root.name}/{row['path']}", str(row["detail"]))
            for row in result["findings"]
        )
    return _report(scope="trees", roots=labels, files_scanned=files_scanned, findings=all_findings)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, default=[], help="candidate tree to scan (repeatable)")
    parser.add_argument("--git-root", type=Path, help="scan the current staged diff of this repository")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.root and args.git_root is None:
        _parser().error("provide --root at least once or --git-root")
    reports: list[dict[str, object]] = []
    if args.root:
        reports.append(scan_trees(args.root))
    if args.git_root is not None:
        reports.append(scan_staged_diff(args.git_root))
    if len(reports) == 1:
        result = reports[0]
    else:
        result = {
            "schema_version": SCHEMA_VERSION,
            "scope": "combined",
            "reports": reports,
            "status": "blocked" if any(report["status"] != "passed" for report in reports) else "passed",
            "claim_boundary": "Combined privacy result; each child report retains its own candidate scope.",
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
