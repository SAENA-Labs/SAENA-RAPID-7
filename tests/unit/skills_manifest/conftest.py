"""Path setup for the skill-manifest validator tests (w6-01).

Unique-basename convention: shared fixtures live in `_manifest_fixtures.py`
(NOT `conftest`) and test modules are prefixed `test_skill_manifest_*` —
plain basenames like `test_cli.py` / `from conftest import ...` collide
across this repo's non-package test leaf dirs in a combined session
(rootdir-wide module cache; same footgun w6-08/w6-11 hit).
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent.parent
_VALIDATION_DIR = _REPO_ROOT / "tools" / "validation"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
if str(_VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATION_DIR))
