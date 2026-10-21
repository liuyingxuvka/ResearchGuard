from pathlib import Path
import subprocess
import os
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_install(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "install_skill.py"), *map(str, args)], text=True, capture_output=True)


def test_install_copies_five_skills_and_check_detects_drift(tmp_path):
    target = tmp_path / "skills"
    assert run_install("--target", target).returncode == 0
    assert sorted(p.name for p in target.iterdir()) == ["experimentguard", "logicguard", "researchguard", "sourceguard", "traceguard"]
    assert run_install("--target", target, "--check").returncode == 0
    installed = target / "logicguard" / "SKILL.md"
    original = installed.read_bytes()
    before = installed.stat()
    installed.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    os.utime(installed, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert installed.stat().st_size == before.st_size
    assert installed.stat().st_mtime_ns == before.st_mtime_ns
    assert run_install("--target", target, "--check").returncode == 1
    (target / "logicguard" / "SKILL.md").write_text("changed")
    assert run_install("--target", target, "--check").returncode == 1
    installed.unlink()
    installed.mkdir()
    mismatch = run_install("--target", target, "--check")
    assert mismatch.returncode == 1
    assert "cannot compare: SKILL.md" in mismatch.stdout


def test_install_accepts_a_symlinked_skills_home(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert run_install("--target", link / "skills").returncode == 0
    assert (real / "skills" / "researchguard" / "SKILL.md").is_file()
