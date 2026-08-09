from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")

# The repository uses a src layout. Child CLI processes must resolve the same
# current package under test instead of an older installed distribution.
existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    SRC if not existing else os.pathsep.join((SRC, existing))
)


@pytest.fixture(autouse=True)
def isolated_researchguard_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    """Give every test and child process an explicit, disposable authority root."""

    short_id = hashlib.sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:10]
    isolated_home = (tmp_path.parent / f"rh-{short_id}").resolve()
    fixture_root = (tmp_path.parent / f"rf-{short_id}").resolve()
    isolated_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    monkeypatch.setenv("RESEARCHGUARD_TEST_FIXTURE_ROOT", str(fixture_root))

    import researchguard.native_receipts as native_receipts
    import researchguard.target_authority as target_authority
    from admission_fixtures import (
        configure_test_native_fixture_root,
        install_test_native_receipt_producers,
        reset_test_native_fixture_root,
    )
    from target_material_fixtures import install_test_expected_target_producer

    prior_native = dict(native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS)
    prior_target = dict(target_authority._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS)
    native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS.clear()
    target_authority._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS.clear()
    configure_test_native_fixture_root(fixture_root)
    install_test_expected_target_producer()
    install_test_native_receipt_producers()
    try:
        yield {
            "home": isolated_home,
            "native_fixture_root": fixture_root,
            "native_authority_root": (
                isolated_home / ".researchguard" / "authority" / "native-receipt-v2"
            ),
            "target_authority_root": (
                isolated_home / ".researchguard" / "authority" / "expected-target-v2"
            ),
        }
    finally:
        reset_test_native_fixture_root()
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS.clear()
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS.update(prior_native)
        target_authority._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS.clear()
        target_authority._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS.update(
            prior_target
        )
