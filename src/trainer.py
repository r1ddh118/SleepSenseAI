from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    from .models.base_model import ModelMetrics
    from .models.sklearn_models import (
        AdaBoostSleepModel,
        ExtraTreesSleepModel,
        KNNSleepModel,
        LogisticSleepModel,
        MLPSleepModel,
        RandomForestSleepModel,
        SVCSleepModel,
    )
    from .models.tensorflow_ann_model import TensorFlowANNSleepModel
except ImportError:  # pragma: no cover - supports direct script execution
    from models.base_model import ModelMetrics
    from models.sklearn_models import (
        AdaBoostSleepModel,
        ExtraTreesSleepModel,
        KNNSleepModel,
        LogisticSleepModel,
        MLPSleepModel,
        RandomForestSleepModel,
        SVCSleepModel,
    )
    from models.tensorflow_ann_model import TensorFlowANNSleepModel


class SleepModelTrainer:
    def __init__(self):
        self.models = [
            LogisticSleepModel(),
            RandomForestSleepModel(),
            ExtraTreesSleepModel(),
            AdaBoostSleepModel(),
            SVCSleepModel(),
            KNNSleepModel(),
            MLPSleepModel(),
            TensorFlowANNSleepModel(),
        ]

    @staticmethod
    def _metrics(name: str, y_true, y_pred, y_prob) -> ModelMetrics:
        roc = float("nan")
        if y_prob is not None and len(np.unique(y_true)) > 1:
            roc = float(roc_auc_score(y_true, y_prob))
        return ModelMetrics(
            model_name=name,
            accuracy=float(accuracy_score(y_true, y_pred)),
            f1=float(f1_score(y_true, y_pred, zero_division=0)),
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            roc_auc=roc,
        )

    def train_and_select(self, train_df: pd.DataFrame, outdir: Path) -> Dict[str, str]:
        target_col = "sleep_deprivation_label"
        drop_cols = {target_col, "recommended_sleep_hours"}
        feature_cols = [c for c in train_df.columns if c not in drop_cols]

        X = train_df[feature_cols]
        y = train_df[target_col].astype(int)
        if y.nunique() < 2:
            counts = y.value_counts().to_dict()
            raise ValueError(
                f"Need at least two target classes, but found {y.nunique()} in "
                f"'{target_col}' with counts {counts}."
            )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.4, stratify=y, random_state=42
        )

        metrics: List[ModelMetrics] = []
        trained: Dict[str, object] = {}

        for model in self.models:
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            prob = model.predict_proba(X_test)
            metrics.append(self._metrics(model.model_name, y_test.to_numpy(), pred, prob))
            trained[model.model_name] = model

        leaderboard = pd.DataFrame([m.__dict__ for m in metrics]).sort_values(
            by=["f1", "accuracy", "roc_auc"], ascending=False
        )

        outdir.mkdir(parents=True, exist_ok=True)
        leaderboard_path = outdir / "model_leaderboard.csv"
        summary_path = outdir / "training_summary.json"
        pickle_path = outdir / "best_model.pkl"
        leaderboard.to_csv(leaderboard_path, index=False)

        best_name = str(leaderboard.iloc[0]["model_name"])
        best_model = trained[best_name]

        bundle = {
            "best_model_name": best_name,
            "feature_columns": feature_cols,
            "label_map": {
                "0": "No strong sleep deprivation signal",
                "1": "Likely sleep deprivation / sleep-disordered breathing risk",
            },
        }

        if best_name == "tensorflow_ann":
            keras_path = outdir / "best_tensorflow_ann.keras"
            best_model.model.save(keras_path)
            bundle["tensorflow_model_path"] = str(keras_path)
            bundle["preprocessor"] = best_model.preprocessor
        else:
            bundle["pipeline"] = best_model.pipeline

        with open(pickle_path, "wb") as f:
            pickle.dump(bundle, f)

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "best_model": best_name,
                    "num_rows": int(len(train_df)),
                    "train_size": int(len(X_train)),
                    "test_size": int(len(X_test)),
                    "leaderboard": leaderboard.to_dict(orient="records"),
                },
                f,
                indent=2,
            )

        return {
            "leaderboard_csv": str(leaderboard_path),
            "summary_json": str(summary_path),
            "best_pickle": str(pickle_path),
            "best_model": best_name,
        }

    @staticmethod
    def predict_to_csv(bundle_path: Path, input_df: pd.DataFrame, output_csv: Path) -> Path:
        import tensorflow as tf

        with open(bundle_path, "rb") as f:
            bundle = pickle.load(f)

        X = input_df[bundle["feature_columns"]]
        model_name = bundle["best_model_name"]

        if model_name == "tensorflow_ann":
            pre = bundle["preprocessor"]
            model = tf.keras.models.load_model(bundle["tensorflow_model_path"])
            X_proc = pre.transform(X)
            if hasattr(X_proc, "toarray"):
                X_proc = X_proc.toarray()
            probs = model.predict(X_proc, verbose=0).ravel()
        else:
            pipe = bundle["pipeline"]
            probs = pipe.predict_proba(X)[:, 1]

        preds = (probs >= 0.5).astype(int)
        out = input_df.copy()
        out["prediction"] = preds
        out["probability_sleep_deprivation"] = probs
        out["prediction_label"] = out["prediction"].map(bundle["label_map"])

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_csv, index=False)
        return output_csv
