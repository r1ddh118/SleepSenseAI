"""MLlib model registry — save, load, and version management."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "models"


def save_model(model, name: str, metadata: dict | None = None) -> str:
    """Save a PipelineModel and write metadata JSON alongside it."""
    from pyspark.ml import PipelineModel

    version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = MODEL_DIR / f"{name}_v{version}"
    path.mkdir(parents=True, exist_ok=True)

    model_path = path / "model"
    model.write().overwrite().save(str(model_path))

    meta = {
        "name": name,
        "version": version,
        "saved_at": datetime.utcnow().isoformat(),
        "split_methodology": (
            "USER-LEVEL split: train=U001-U070, val=U071-U085, test=U086-U100. "
            "No user in both train and test sets."
        ),
        **(metadata or {}),
    }
    meta_path = path / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    logger.info("Model saved: %s (version %s)", name, version)
    return str(model_path)


def load_latest_model(name: str):
    """Load the most recent version of a named model."""
    from pyspark.ml import PipelineModel

    candidates = sorted(MODEL_DIR.glob(f"{name}_v*"))
    if not candidates:
        raise FileNotFoundError(f"No model versions found for '{name}' in {MODEL_DIR}")

    latest = candidates[-1] / "model"
    logger.info("Loading model from %s", latest)
    return PipelineModel.load(str(latest))


def list_models() -> list[dict]:
    """List all saved model versions with their metadata."""
    result = []
    for d in sorted(MODEL_DIR.glob("*_v*")):
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                result.append(json.loads(meta_path.read_text()))
            except Exception:
                result.append({"path": str(d)})
    return result
