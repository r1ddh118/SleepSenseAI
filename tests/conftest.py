from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"

for path in (REPO_ROOT, API_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
