from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_windows_ci_enables_git_long_paths_before_install() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    long_paths = workflow.index("git config --global core.longpaths true")
    install = workflow.index('python -m pip install --upgrade pip build')

    assert "if: runner.os == 'Windows'" in workflow
    assert long_paths < install


def test_ci_verifies_one_public_flowguard_authority_after_install() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'name: Verify public FlowGuard authority' in workflow
    assert "metadata.version('flowguard') == '0.69.0'" in workflow
    assert "flowguard.SCHEMA_VERSION == '1.0'" in workflow
