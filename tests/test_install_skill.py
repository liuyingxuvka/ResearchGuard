from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_install(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "install_skill.py"), *map(str, args)], text=True, capture_output=True)


def test_install_copies_five_skills_and_check_detects_drift(tmp_path):
    target = tmp_path / "skills"
    assert run_install("--target", target).returncode == 0
    assert sorted(p.name for p in target.iterdir()) == ["experimentguard", "logicguard", "researchguard", "sourceguard", "traceguard"]
    assert run_install("--target", target, "--check").returncode == 0
    (target / "logicguard" / "SKILL.md").write_text("changed")
    assert run_install("--target", target, "--check").returncode == 1


def test_install_accepts_a_symlinked_skills_home(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert run_install("--target", link / "skills").returncode == 0
    assert (real / "skills" / "researchguard" / "SKILL.md").is_file()
