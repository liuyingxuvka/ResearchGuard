from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")

# The repository uses a src layout. Child CLI processes must resolve the same
# current package under test instead of an older installed distribution.
existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    SRC if not existing else os.pathsep.join((SRC, existing))
)
