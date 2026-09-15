"""MLlib inference — score a single session feature row."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO_ROOT / "models" / "sleep_risk_rf"


def predict_risk(features: dict) -> dict:
    """Predict sleep risk level for a single session feature dict.

    Parameters
    ----------
    features : dict with keys matching FEATURE_COLS in train_spark_model.py.

    Returns
    -------
    dict with: prediction (0/1), risk_level (str), probability (float), disclaimer (str).
    """
    from spark.spark_session import create_spark_session
    from ml.train_spark_model import FEATURE_COLS

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. "
            "Run: python ml/train_spark_model.py first."
        )

    spark = create_spark_session("SleepSenseAI-Inference")
    try:
        from pyspark.ml import PipelineModel

        model = PipelineModel.load(str(MODEL_PATH))

        # Build a single-row DataFrame
        row_data = {col: float(features.get(col, 0.0)) for col in FEATURE_COLS}
        row_data["user_id"] = str(features.get("user_id", "unknown"))

        df = spark.createDataFrame([row_data])
        preds = model.transform(df)

        row = preds.select("prediction", "probability").first()
        pred_label = int(row["prediction"])
        prob_high = float(row["probability"][1])  # probability of class 1 (HIGH)

        return {
            "prediction": pred_label,
            "risk_level": "HIGH" if pred_label == 1 else "LOW",
            "probability_high": round(prob_high, 4),
            "disclaimer": (
                "ML prediction is an academic screening tool only — NOT clinically validated. "
                "Based on synthetic data. Not for clinical use."
            ),
        }
    finally:
        spark.stop()
