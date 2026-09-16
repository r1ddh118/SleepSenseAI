"""Celery app compatibility module.

Allows starting the worker with:

    celery -A api.celery_app worker --loglevel=info
"""

from pathlib import Path
import sys


API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent
for path in (API_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tasks import app  # noqa: E402,F401
