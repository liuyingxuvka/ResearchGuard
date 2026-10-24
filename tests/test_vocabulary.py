"""Prevent retired interface machinery from returning to the maintained surface."""
from pathlib import Path
import ast
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_no_receipt_vocabulary():
    paths = ["src", "skills", "docs", "examples", "scripts", "tests", "openspec/specs", "README.md", "AGENTS.md"]
    try:
        probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git is unavailable")
    if probe.returncode:
        pytest.skip("installed package has no git checkout")
    result = subprocess.run(["git", "grep", "-n", "-i", "-E",
                             "receipt|blueprint_interfaces_required|interface_bindings|block_interfaces", "--", *paths],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode in (0, 1), result.stderr
    allowed_tests = {}
    for relative, names in {
        "tests/logic/test_schema.py": {"test_retired_block_interfaces_are_load_errors", "test_retired_separation_key_names_the_current_input"},
        "tests/trace/test_traceguard.py": {"test_retired_interface_bindings_are_schema_errors"},
    }.items():
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        allowed_tests[relative] = {line for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
                                   for line in range(node.lineno, node.end_lineno + 1)}
    unexpected = []
    for match in result.stdout.splitlines():
        path, line_number, text = match.split(":", 2)
        if path == "tests/test_vocabulary.py" or int(line_number) in allowed_tests.get(path, set()):
            continue
        stripped = text.strip()
        # This exact old-artifact path is denied by the privacy filter; removing it would weaken privacy.
        if path == "scripts/check_researchguard_privacy.py" and stripped == '"receipts",':
            continue
        retired_inputs = {
            "src/researchguard/logic/loader.py": "block_interfaces",
            "src/researchguard/trace/schema.py": "interface_bindings",
            "src/researchguard/logic/provenance.py": "separation_receipt_id",
        }
        key = retired_inputs.get(path)
        if key and key in text and (stripped.startswith(("if ", "raise ")) or
                                   path.endswith("trace/schema.py") and stripped.startswith("data = ")):
            continue
        unexpected.append(match)
    assert not unexpected, "Retired vocabulary outside input rejection boundaries:\n" + "\n".join(unexpected)
