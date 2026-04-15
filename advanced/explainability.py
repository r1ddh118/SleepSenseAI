#!/usr/bin/env python3
"""
Standalone SHAP explainability for SleepSense (sklearn pipeline bundles).

Outputs under --out:
  - shap_values.csv
  - shap_summary_plot.png

TensorFlow ANN bundles (no sklearn pipeline) are not supported here — use API SHAP for tree models
or export sklearn-compatible features separately.

Usage:
  python advanced/explainability.py \\
    --model artifacts/best_model.pkl \\
    --data artifacts/preprocessed_inference_S002.csv \\
    --out artifacts/shap/
"""

from __future__ import annotations

import argparse
import logging
import pickle
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd
import shap

logger = logging.getLogger("explainability")
logging.basicConfig(level=logging.INFO)

DROP_COLS = {
    "SID",
    "sleep_deprivation_label",
    "recommended_sleep_hours",
    "prediction",
    "probability_sleep_deprivation",
    "prediction_label",
}


def load_sklearn_pipeline(model_path: Path):
    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    if "pipeline" not in bundle:
        raise ValueError(
            "This bundle has no sklearn 'pipeline' (e.g. TensorFlow best model). "
            "Train/select a tree-based sklearn model or use a sklearn pickle bundle."
        )
    pipeline = bundle["pipeline"]
    name = bundle.get("best_model_name", "unknown")
    return pipeline, name


def compute_shap(model_path: str, data_csv: str, out_dir: str) -> list[list[dict]]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    pipeline, model_name = load_sklearn_pipeline(Path(model_path))
    df = pd.read_csv(data_csv)
    X = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore")

    preprocessor = pipeline[:-1]
    model = pipeline.named_steps.get("model")
    if model is None:
        model = pipeline.steps[-1][1]

    X_transformed = preprocessor.transform(X)
    if hasattr(X_transformed, "toarray"):
        X_transformed = X_transformed.toarray()

    try:
        feature_names = preprocessor.get_feature_names_out()
    except Exception:
        feature_names = np.array([f"feature_{i}" for i in range(X_transformed.shape[1])])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_transformed)
            if isinstance(shap_values, list):
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        except Exception:
            logger.info("TreeExplainer failed; using KernelExplainer (slow)")
            bg = shap.sample(X_transformed, min(50, len(X_transformed)))
            explainer = shap.KernelExplainer(model.predict_proba, bg)
            shap_values = explainer.shap_values(X_transformed, nsamples=100)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            shap_values = np.asarray(shap_values)

    shap_values = np.atleast_2d(np.asarray(shap_values))
    shap_df = pd.DataFrame(shap_values, columns=list(feature_names))
    shap_df.to_csv(out_path / "shap_values.csv", index=False)
    logger.info("SHAP values saved: %s", out_path / "shap_values.csv")

    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_values,
        X_transformed,
        feature_names=list(feature_names),
        show=False,
        max_display=15,
    )
    plt.tight_layout()
    plt.savefig(out_path / "shap_summary_plot.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Summary plot: %s", out_path / "shap_summary_plot.png")

    top_per_row: list[list[dict]] = []
    for i in range(len(shap_values)):
        impact = np.abs(shap_values[i])
        top_idx = impact.argsort()[::-1][:3]
        top_per_row.append(
            [{"feature": str(feature_names[j]), "impact": float(impact[j])} for j in top_idx]
        )

    logger.info("Model: %s", model_name)
    return top_per_row


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="artifacts/best_model.pkl")
    p.add_argument("--data", required=True)
    p.add_argument("--out", default="artifacts/shap/")
    args = p.parse_args()
    compute_shap(args.model, args.data, args.out)


if __name__ == "__main__":
    main()
