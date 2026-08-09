from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_fixture_import_has_no_registry_or_authority_side_effect(
    tmp_path: Path,
) -> None:
    isolated_home = tmp_path / "fresh-import-home"
    isolated_home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(isolated_home)
    environment["USERPROFILE"] = str(isolated_home)
    environment["RESEARCHGUARD_TEST_FIXTURE_ROOT"] = str(
        tmp_path / "fresh-import-fixtures"
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    repository = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(repository / "tests"))
    )
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import json
from pathlib import Path
import researchguard.native_receipts as native_receipts
import researchguard.target_authority as target_authority
import admission_fixtures
import target_material_fixtures
home = Path.home()
print(json.dumps({
    'native_registry_count': len(native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS),
    'target_registry_count': len(target_authority._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS),
    'authority_exists': (home / '.researchguard' / 'authority').exists(),
    'fixture_root_exists': Path(admission_fixtures._native_fixture_root()).exists(),
}))
""",
        ],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert child.returncode == 0, child.stderr
    result = json.loads(child.stdout)
    assert result == {
        "native_registry_count": 0,
        "target_registry_count": 0,
        "authority_exists": False,
        "fixture_root_exists": False,
    }
