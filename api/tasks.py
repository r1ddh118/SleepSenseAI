"""
Celery tasks for async ML jobs. Worker: celery -A tasks worker --loglevel=info
Loads the pipeline from src/main.py explicitly to avoid clashing with api/main.py.
"""

import importlib.util
import csv
import json
import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from celery import Celery

from config import REPO_ROOT, settings

logger = logging.getLogger("celery.worker")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

app = Celery("sleepsense", broker=settings.redis_url, backend=settings.redis_url)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"


def _time_or_default(value: str | None, default: str) -> str:
    return value if value else default


def _fraction_or_default(value: float | None, default: float) -> float:
    if value is None:
        return default
    return value / 100.0 if value > 1 else value


def _write_manual_observation_csv(manual, session_sid: str) -> Path:
    """Create a small observation-level CSV so the manual path still runs Spark."""
    out_dir = REPO_ROOT / "data" / "raw" / "manual"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_sid}.csv"

    n = 72
    wake_fraction = _fraction_or_default(manual.wake_fraction, 0.10)
    n3_fraction = _fraction_or_default(manual.n3_fraction, 0.16)
    rem_fraction = _fraction_or_default(manual.rem_fraction, 0.20)
    wake_count = max(1, round(n * wake_fraction))
    n3_count = max(1, round(n * n3_fraction))
    rem_count = max(1, round(n * rem_fraction))
    n1_count = max(1, round(n * 0.10))
    n2_count = max(1, n - wake_count - n3_count - rem_count - n1_count)
    stages = ["W"] * wake_count + ["N1"] * n1_count + ["N2"] * n2_count + ["N3"] * n3_count + ["R"] * rem_count
    stages = stages[:n]
    while len(stages) < n:
        stages.append("N2")

    base_hr = manual.heart_rate if manual.heart_rate is not None else 64.0
    movement_std = manual.movement_std if manual.movement_std is not None else 0.10
    event_every = None
    if manual.event_rate and manual.event_rate > 0:
        event_every = max(1, round(1 / manual.event_rate))

    fieldnames = [
        "user_id",
        "session_id",
        "timestamp",
        "date",
        "heart_rate",
        "acc_x",
        "acc_y",
        "acc_z",
        "sleep_stage",
        "bed_time",
        "sleep_onset",
        "wake_time",
        "caffeine",
        "screen_time",
        "exercise_minutes",
        "stress_level",
        "nap_minutes",
        "awakenings",
        "event_count",
        "spo2",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, stage in enumerate(stages):
            stage_hr_offset = {"W": 8, "N1": 2, "N2": -2, "N3": -6, "R": 4}.get(stage, 0)
            movement = {"W": 0.30, "N1": 0.14, "N2": 0.08, "N3": 0.035, "R": 0.10}.get(stage, 0.08)
            event_count = 1 if event_every and idx % event_every == 0 else 0
            writer.writerow(
                {
                    "user_id": manual.patient_uid,
                    "session_id": session_sid,
                    "timestamp": f"{manual.date}T00:{idx:02d}:00" if idx < 60 else f"{manual.date}T01:{idx - 60:02d}:00",
                    "date": manual.date,
                    "heart_rate": round(base_hr + stage_hr_offset + event_count * 4, 1),
                    "acc_x": round(movement + movement_std * 0.1, 4),
                    "acc_y": round(movement * 0.5, 4),
                    "acc_z": round(1.0 + movement * 0.25, 4),
                    "sleep_stage": stage,
                    "bed_time": _time_or_default(manual.bed_time, "23:00"),
                    "sleep_onset": _time_or_default(manual.sleep_onset, "23:20"),
                    "wake_time": _time_or_default(manual.wake_time, "07:00"),
                    "caffeine": manual.caffeine if manual.caffeine is not None else 0,
                    "screen_time": manual.screen_time if manual.screen_time is not None else 0,
                    "exercise_minutes": manual.exercise_minutes if manual.exercise_minutes is not None else 0,
                    "stress_level": manual.stress_level if manual.stress_level is not None else 5,
                    "nap_minutes": manual.nap_minutes if manual.nap_minutes is not None else 0,
                    "awakenings": manual.awakenings if manual.awakenings is not None else max(1, round(wake_fraction * 10)),
                    "event_count": event_count,
                    "spo2": manual.spo2 if manual.spo2 is not None else 96.0,
                }
            )
    return out_path


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


@app.task(bind=True, name="tasks.run_sleep_analytics")
def run_sleep_analytics(self, session_id: int) -> dict:
    """Run Spark-backed analytics for a manual sleep session."""
    from analytics.recommendations import generate_recommendations
    from database import SessionLocal
    from models_db import ManualSleepSession, Session as SessionModel, SleepAnalytics
    from spark.cleaning import clean_sleep_data
    from spark.feature_engineering import add_rolling_features
    from spark.ingestion import load_sleep_data
    from spark.longitudinal import add_longitudinal_metrics
    from spark.risk_analysis import add_risk_features
    from spark.sleep_analytics import nightly_metrics
    from spark.sleep_score import add_sleep_score
    from spark.spark_session import create_spark_session

    db = SessionLocal()
    spark = None
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        manual = db.query(ManualSleepSession).filter(ManualSleepSession.session_id == session_id).first()
        analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session_id).first()
        if not session or not manual:
            raise ValueError(f"Manual session {session_id} not found")
        if not analytics:
            analytics = SleepAnalytics(session_id=session_id, status="PROCESSING", spark_job_id=self.request.id)
            db.add(analytics)
            db.commit()

        logger.info("[%s] Running Spark manual sleep analytics", session.sid)
        csv_path = _write_manual_observation_csv(manual, session.sid)
        spark = create_spark_session("SleepSense Manual Analytics")
        raw = load_sleep_data(spark, csv_path)
        clean = clean_sleep_data(raw)
        featured = add_rolling_features(clean)
        nightly = nightly_metrics(featured)
        scored = add_sleep_score(nightly)
        risked = add_risk_features(scored)
        trended = add_longitudinal_metrics(risked)
        row = trended.first()
        if row is None:
            raise ValueError("Spark analytics produced no rows")
        metrics = row.asDict(recursive=True)

        sleep_metrics = {
            "sleep_efficiency": metrics.get("sleep_efficiency_fraction"),
            "sleep_duration_hours": metrics.get("sleep_duration_hours"),
            "n3_fraction": metrics.get("n3_fraction"),
            "rem_fraction": metrics.get("rem_fraction"),
            "wake_fraction": metrics.get("wake_fraction"),
        }
        risk_metrics = {
            "event_rate": metrics.get("event_rate"),
            "hr_std": metrics.get("hr_std"),
            "movement_std": metrics.get("movement_std"),
        }
        lifestyle_metrics = {
            "screen_time": metrics.get("screen_time"),
            "stress_level": metrics.get("stress_level"),
            "caffeine": metrics.get("caffeine"),
        }
        longitudinal_metrics = {
            "sleep_score_7d_trend": metrics.get("sleep_score_7d_trend"),
            "wake_7d_trend": metrics.get("wake_7d_trend"),
        }
        recommendations = generate_recommendations(
            sleep_metrics,
            risk_metrics,
            lifestyle_metrics,
            longitudinal_metrics,
        )

        analytics.status = "COMPLETED"
        analytics.sleep_score = float(metrics.get("sleep_score") or 0.0)
        analytics.sleep_category = metrics.get("sleep_category")
        analytics.sleep_efficiency = float(metrics.get("sleep_efficiency") or 0.0)
        analytics.risk_level = metrics.get("risk_level")
        analytics.risk_json = json.dumps(
            {
                "risk_score": metrics.get("risk_score"),
                "risk_level": metrics.get("risk_level"),
                "risk_flags": json.loads(metrics.get("risk_flags_json") or "[]"),
            },
            default=str,
        )
        analytics.recommendations_json = json.dumps(recommendations, default=str)
        analytics.metrics_json = json.dumps(metrics, default=str)
        analytics.spark_job_id = self.request.id
        analytics.error = None
        analytics.updated_at = datetime.utcnow()
        session.status = "COMPLETED"
        db.commit()

        logger.info("[%s] Manual Spark analytics complete", session.sid)
        return {"session_id": session_id, "status": "COMPLETED", "sleep_score": analytics.sleep_score}
    except Exception as exc:
        logger.exception("Manual Spark analytics failed for session_id=%s", session_id)
        analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session_id).first()
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if analytics:
            analytics.status = "FAILED"
            analytics.error = str(exc)
            analytics.updated_at = datetime.utcnow()
        if session:
            session.status = "FAILED"
        db.commit()
        raise
    finally:
        if spark is not None:
            spark.stop()
        db.close()
