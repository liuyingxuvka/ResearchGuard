from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _install(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "install_skill.py"), *args], text=True, capture_output=True)


def _install_in_process(*args: str) -> subprocess.CompletedProcess[str]:
    spec = importlib.util.spec_from_file_location("researchguard_native_installer", ROOT / "scripts" / "install_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stdout, stderr = io.StringIO(), io.StringIO()
    previous = sys.argv
    try:
        sys.argv = [str(ROOT / "scripts" / "install_skill.py"), *args]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main()
    finally:
        sys.argv = previous
    return subprocess.CompletedProcess(sys.argv, code, stdout.getvalue(), stderr.getvalue())


def test_install_copies_one_skill_removes_retired_members_and_check_detects_drift(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    (target / "logicguard").mkdir(parents=True)
    (target / "logicguard" / "SKILL.md").write_text("old member", encoding="utf-8")
    assert _install_in_process("--target", str(target), "--check").returncode == 1
    installed = _install_in_process("--target", str(target))
    assert installed.returncode == 0, installed.stderr
    assert "removed retired" in installed.stdout
    assert sorted(path.name for path in target.iterdir()) == ["researchguard"]
    assert _install_in_process("--target", str(target), "--check").returncode == 0
    copied = target / "researchguard" / "SKILL.md"
    original = copied.read_bytes()
    before = copied.stat()
    copied.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    os.utime(copied, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert copied.stat().st_size == before.st_size
    assert copied.stat().st_mtime_ns == before.st_mtime_ns
    assert _install_in_process("--target", str(target), "--check").returncode == 1
    copied.write_text("changed", encoding="utf-8")
    assert _install_in_process("--target", str(target), "--check").returncode == 1
    copied.unlink()
    copied.mkdir()
    mismatch = _install_in_process("--target", str(target), "--check")
    assert mismatch.returncode == 1
    assert "cannot compare: SKILL.md" in mismatch.stdout


def test_install_accepts_a_symlinked_skills_home(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert _install("--target", str(link / "skills")).returncode == 0
    assert (real / "skills" / "researchguard" / "SKILL.md").is_file()
