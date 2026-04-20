"""
Celery tasks for async ML jobs. Worker: celery -A tasks worker --loglevel=info
Loads the pipeline from src/main.py explicitly to avoid clashing with api/main.py.
"""

import importlib.util
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from celery import Celery

from config import REPO_ROOT, settings

logger = logging.getLogger("celery.worker")

app = Celery("sleepsense", broker=settings.redis_url, backend=settings.redis_url)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"


def _load_pipeline_main():
    """Import SleepSenseApp from repo src/main.py (not api/main.py)."""
    path = Path(settings.src_path) / "main.py"
    spec = importlib.util.spec_from_file_location("sleepsense_src_main", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load pipeline from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sleepsense_src_main"] = mod
    spec.loader.exec_module(mod)
    return mod.SleepSenseApp


def _risk_label(proba: float) -> str:
    if proba < 0.3:
        return "LOW RISK"
    if proba < 0.65:
        return "MODERATE RISK"
    return "HIGH RISK"


def _shap_top_features(bundle: dict, X_df: pd.DataFrame) -> list[dict]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        return []
    try:
        import shap

        model = pipeline.named_steps.get("model")
        if model is None:
            return []
        pre = pipeline[:-1]
        X_t = pre.transform(X_df)
        if hasattr(X_t, "toarray"):
            X_t = X_t.toarray()
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(X_t)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
        row = np.atleast_2d(np.asarray(shap_vals))[0]
        impact = np.abs(row)
        names = (
            pre.get_feature_names_out()
            if hasattr(pre, "get_feature_names_out")
            else [f"f{i}" for i in range(X_t.shape[1])]
        )
        top_idx = impact.argsort()[::-1][:3]
        return [{"feature": str(names[i]), "impact": float(impact[i])} for i in top_idx]
    except Exception as e:
        logger.warning("SHAP skipped: %s", e)
        return []


@app.task(bind=True, name="tasks.run_prediction")
def run_prediction(
    self,
    sid: str,
    sensor_csv_path: str,
    model_pickle_path: str | None = None,
) -> dict:
    SleepSenseApp = _load_pipeline_main()

    model_path = Path(model_pickle_path or settings.artifacts_path / "best_model.pkl")
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    csv_path = Path(sensor_csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Sensor CSV not found: {csv_path}")

    app = SleepSenseApp(
        settings.datasets_path,
        settings.participant_csv,
        settings.artifacts_path,
    )

    out_csv = settings.artifacts_path / f"predictions_{sid}.csv"
    logger.info("[%s] Running predict → %s", sid, out_csv)
    app.predict(
        model_pickle=model_path,
        sensor_csv=csv_path,
        sid=sid,
        output_csv=out_csv,
    )

    row = pd.read_csv(out_csv).iloc[0]
    proba = float(row["probability_sleep_deprivation"])
    pred = int(row["prediction"])
    label = _risk_label(proba)

    preprocessed_path = settings.artifacts_path / f"preprocessed_inference_{sid}.csv"
    X_df = pd.read_csv(preprocessed_path)

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    model_name = bundle.get("best_model_name", "unknown")
    shap_features = _shap_top_features(bundle, X_df)

    result = {
        "sid": sid,
        "model_name": model_name,
        "prediction": pred,
        "probability": proba,
        "label": label,
        "shap_top_features": shap_features,
        "preprocessed_csv": str(preprocessed_path),
        "predictions_csv": str(out_csv),
        "recommendations": [],
    }

    adv = str(REPO_ROOT / "advanced")
    if Path(adv).is_dir():
        if adv not in sys.path:
            sys.path.insert(0, adv)
        try:
            from recommendations import generate_recommendations

            feat_row = X_df.iloc[0].to_dict()
            result["recommendations"] = generate_recommendations(feat_row)
        except Exception as e:
            logger.warning("Recommendations skipped: %s", e)

    logger.info("[%s] Prediction complete: %s (%.2f%%)", sid, label, proba * 100)
    return result


@app.task(bind=True, name="tasks.run_training_and_prediction")
def run_training_and_prediction(self, sid: str, dataset_path: str | None = None) -> dict:
    """Train on the entire dataset (including the new session), then predict for the new session."""
    # 1. Train on all visible sessions
    SleepSenseApp = _load_pipeline_main()

    ds_root = Path(dataset_path or settings.datasets_path)
    participant = ds_root / "participant_info.csv"
    if not participant.exists():
        participant = settings.participant_csv

    logger.info("[%s] Training pipeline triggered on dataset_dir=%s", sid, ds_root)
    app_pipeline = SleepSenseApp(ds_root, participant, settings.artifacts_path)

    app_pipeline.preprocessor.preprocess_training_data()
    processed_df = app_pipeline.preprocessor.load_preprocessed_training_data()
    train_out = app_pipeline.trainer.train_and_select(processed_df, settings.artifacts_path)
    
    best_name = train_out["best_model"]
    logger.info("[%s] Cumulative Training complete. Best model: %s", sid, best_name)

    # 2. Predict on the specific session
    model_path = settings.artifacts_path / "best_model.pkl"
    csv_path = ds_root / f"compressed_{sid}_whole_df.csv"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Sensor CSV not found: {csv_path}")

    out_csv = settings.artifacts_path / f"predictions_{sid}.csv"
    logger.info("[%s] Running prediction → %s", sid, out_csv)
    app_pipeline.predict(
        model_pickle=model_path,
        sensor_csv=csv_path,
        sid=sid,
        output_csv=out_csv,
    )

    row = pd.read_csv(out_csv).iloc[0]
    proba = float(row["probability_sleep_deprivation"])
    pred = int(row["prediction"])
    label = _risk_label(proba)

    preprocessed_path = settings.artifacts_path / f"preprocessed_inference_{sid}.csv"
    X_df = pd.read_csv(preprocessed_path)

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    shap_features = _shap_top_features(bundle, X_df)

    result = {
        "sid": sid,
        "model_name": best_name,
        "prediction": pred,
        "probability": proba,
        "label": label,
        "shap_top_features": shap_features,
        "preprocessed_csv": str(preprocessed_path),
        "predictions_csv": str(out_csv),
        "recommendations": [],
    }

    adv = str(REPO_ROOT / "advanced")
    if Path(adv).is_dir():
        if adv not in sys.path:
            sys.path.insert(0, adv)
        try:
            from recommendations import generate_recommendations
            feat_row = X_df.iloc[0].to_dict()
            result["recommendations"] = generate_recommendations(feat_row)
        except Exception as e:
            logger.warning("Recommendations skipped: %s", e)

    # 3. Store prediction result in the database
    from database import SessionLocal
    from models_db import Prediction
    
    try:
        db = SessionLocal()
        from models_db import Session as SessionModel
        session_db = db.query(SessionModel).filter(SessionModel.sid == sid).first()
        if session_db:
            new_pred = Prediction(
                session_id=session_db.id,
                model_name=best_name,
                prediction=pred,
                probability=proba,
                label=label,
                shap_features=json.dumps(shap_features) if shap_features else None,
                recommendations_json=json.dumps(result["recommendations"]) if result["recommendations"] else None,
            )
            db.add(new_pred)
            db.commit()
    except Exception as e:
        logger.error("Failed to commit prediction to DB: %s", e)
    finally:
        if 'db' in locals():
            db.close()

    return result


@app.task(bind=True, name="tasks.run_training")
def run_training(self, dataset_path: str | None = None) -> dict:
    SleepSenseApp = _load_pipeline_main()

    ds_root = Path(dataset_path or settings.datasets_path)
    participant = ds_root / "participant_info.csv"
    if not participant.exists():
        participant = settings.participant_csv

    logger.info("Training pipeline: dataset_dir=%s", ds_root)
    app_pipeline = SleepSenseApp(ds_root, participant, settings.artifacts_path)

    app_pipeline.preprocessor.preprocess_training_data()
    processed_df = app_pipeline.preprocessor.load_preprocessed_training_data()
    train_out = app_pipeline.trainer.train_and_select(processed_df, settings.artifacts_path)

    lb_path = Path(train_out["leaderboard_csv"])
    leaderboard = pd.read_csv(lb_path).to_dict(orient="records")
    best_name = train_out["best_model"]

    logger.info("Training complete. Best model: %s", best_name)
    return {"best_model": best_name, "leaderboard": leaderboard}
