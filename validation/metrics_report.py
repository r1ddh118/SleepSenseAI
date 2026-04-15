#!/usr/bin/env python3
"""
Clinical validation metrics: sensitivity, specificity, PPV, NPV, AUC-ROC, Cohen's kappa,
with bootstrap confidence intervals.

Usage:
  python validation/metrics_report.py \\
    --predictions artifacts/dreamt_batch_predictions.csv \\
    --ground-truth datasets/dreamt/psg_labels.csv \\
    --output validation/clinical_metrics_report.csv

Expects merged keys:
  - SID
  - prediction (0/1) and probability_sleep_deprivation in predictions CSV
  - sleep_deprivation_label_gt in ground-truth CSV
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    cohen_kappa_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metrics_report")


def _specificity(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    denom = tn + fp
    return float(tn / denom) if denom > 0 else 0.0


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn,
    n_iter: int = 1000,
    ci: float = 0.95,
    random_state: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(random_state)
    scores: list[float] = []
    n = len(y_true)
    for _ in range(n_iter):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_pred[idx]
        if len(np.unique(yt)) < 1:
            continue
        try:
            scores.append(float(metric_fn(yt, yp)))
        except Exception:
            continue
    if len(scores) < 50:
        return float("nan"), float("nan")
    alpha = (1 - ci) / 2
    lower = float(np.percentile(scores, alpha * 100))
    upper = float(np.percentile(scores, (1 - alpha) * 100))
    return round(lower, 4), round(upper, 4)


def compute_metrics(predictions_csv: str, ground_truth_csv: str, output_csv: str) -> dict:
    preds_df = pd.read_csv(predictions_csv)
    gt_df = pd.read_csv(ground_truth_csv)

    if "SID" not in preds_df.columns or "SID" not in gt_df.columns:
        raise ValueError("Both CSVs must contain a SID column.")

    merged = preds_df.merge(gt_df, on="SID", how="inner", suffixes=("_pred", "_gt"))
    if merged.empty:
        raise ValueError("Merge on SID produced zero rows — check IDs.")

    if "sleep_deprivation_label_gt" not in merged.columns:
        # allow plain label column name
        alt = [c for c in merged.columns if "sleep_deprivation" in c.lower() and c != "sleep_deprivation_label"]
        if not alt:
            raise ValueError("Ground truth must include sleep_deprivation_label_gt (or similar).")
        merged = merged.rename(columns={alt[0]: "sleep_deprivation_label_gt"})

    y_true = merged["sleep_deprivation_label_gt"].astype(int).to_numpy()
    y_pred = merged["prediction"].astype(int).to_numpy()
    y_prob = merged["probability_sleep_deprivation"].astype(float).to_numpy()

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = (int(x) for x in cm.ravel())

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = float(precision_score(y_true, y_pred, zero_division=0))
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    if len(np.unique(y_true)) < 2:
        auc = float("nan")
        logger.warning("Ground truth has a single class — AUC is undefined.")
    else:
        auc = float(roc_auc_score(y_true, y_prob))

    kappa = float(cohen_kappa_score(y_true, y_pred))

    sens_ci = bootstrap_ci(
        y_true,
        y_pred,
        lambda yt, yp: recall_score(yt, yp, zero_division=0),
    )
    spec_ci = bootstrap_ci(y_true, y_pred, _specificity)

    report = {
        "N": len(merged),
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Sensitivity": round(sensitivity, 4),
        "Sensitivity_CI_95": f"{sens_ci[0]}–{sens_ci[1]}",
        "Specificity": round(specificity, 4),
        "Specificity_CI_95": f"{spec_ci[0]}–{spec_ci[1]}",
        "PPV": round(ppv, 4),
        "NPV": round(npv, 4),
        "AUC_ROC": round(auc, 4) if auc == auc else None,
        "Cohen_Kappa": round(kappa, 4),
    }

    for k, v in report.items():
        logger.info("  %s: %s", k, v)

    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([report]).to_csv(out_path, index=False)
    logger.info("Report saved to %s", out_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="artifacts/predictions.csv")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--output", default="validation/clinical_metrics_report.csv")
    args = parser.parse_args()
    compute_metrics(args.predictions, args.ground_truth, args.output)


if __name__ == "__main__":
    main()
