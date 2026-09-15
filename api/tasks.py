"""
Celery tasks for async ML jobs. Worker: celery -A tasks worker --loglevel=info

Tasks:
  run_sleep_analytics    — NEW: Spark pipeline for manual/per-session entries
  run_prediction         — legacy sklearn prediction
  run_training_and_prediction — legacy sklearn train+predict
  run_training           — legacy sklearn training
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


# ─── NEW: PySpark analytics task ─────────────────────────────────────────────

@app.task(bind=True, name="tasks.run_sleep_analytics")
def run_sleep_analytics(
    self,
    session_id: str,
    user_id: str,
    raw_csv_path: str,
) -> dict:
    """Run the Spark pipeline for a single manual sleep entry.

    Called by Celery worker ONLY — never called inline in a FastAPI handler.
    Calls the same spark/pipeline.py functions used by the bulk path.
    Saves results to DB: SleepAnalytics, DoctorAlert (if warranted).
    """
    import sys
    import json as _json
    from pathlib import Path as P

    repo_root = P(REPO_ROOT)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    logger.info("[%s] Spark pipeline starting for user=%s", session_id, user_id)

    try:
        from spark.pipeline import run_pipeline_for_user

        parquet_output = repo_root / "data" / "parquet"
        result = run_pipeline_for_user(
            user_id=user_id,
            session_id=session_id,
            raw_csv_path=raw_csv_path,
            parquet_output_path=parquet_output,
        )
        logger.info("[%s] Spark pipeline complete: score=%s", session_id, result.get("sleep_score"))

    except Exception as e:
        logger.error("[%s] Spark pipeline failed: %s", session_id, e, exc_info=True)
        result = {"status": "failed", "error": str(e)}

    # Run analytics (risk + recommendations) on the result dict
    risk_json = None
    recommendations_json = None
    try:
        from analytics.condition_risk import assess_all_risks
        from analytics.recommendations import generate_recommendations

        risk = assess_all_risks(result)
        risk_json = _json.dumps(risk, default=str)

        recs = generate_recommendations(
            sleep_metrics=result,
            risk_metrics=risk,
            lifestyle_metrics=result,
            longitudinal_metrics=result,
        )
        recommendations_json = _json.dumps(recs, default=str)
    except Exception as e:
        logger.warning("[%s] Analytics post-processing failed: %s", session_id, e)

    # Store in DB
    from database import SessionLocal
    from models_db import DoctorAlert, ManualSleepSession, SleepAnalytics

    db = SessionLocal()
    try:
        # Update ManualSleepSession status
        manual = db.query(ManualSleepSession).filter(
            ManualSleepSession.session_id == session_id
        ).first()
        if manual:
            manual.status = "COMPLETE" if "error" not in result else "FAILED"

        # Create SleepAnalytics row
        analytics_row = SleepAnalytics(
            user_str_id=user_id,
            session_id=session_id,
            date=result.get("date"),
            sleep_score=result.get("sleep_score"),
            sleep_category=result.get("sleep_category"),
            sleep_efficiency=result.get("sleep_efficiency"),
            sleep_duration_hours=result.get("sleep_duration_hours"),
            n3_fraction=result.get("n3_fraction"),
            rem_fraction=result.get("rem_fraction"),
            wake_fraction=result.get("wake_fraction"),
            avg_hr=result.get("avg_hr"),
            hr_std=result.get("hr_std"),
            event_rate=result.get("event_rate"),
            sleep_score_7d_avg=result.get("sleep_score_7d_avg"),
            sleep_score_14d_avg=result.get("sleep_score_14d_avg"),
            duration_7d_avg=result.get("duration_7d_avg"),
            risk_level=result.get("risk_level"),
            risk_json=risk_json,
            recommendations_json=recommendations_json,
            spark_job_id=self.request.id,
        )
        if manual:
            analytics_row.manual_session_id = manual.id
        db.add(analytics_row)

        # Evaluate doctor alert persistence
        try:
            recent_analytics = (
                db.query(SleepAnalytics)
                .filter(SleepAnalytics.user_str_id == user_id)
                .order_by(SleepAnalytics.date.desc())
                .limit(7)
                .all()
            )
            recent_nights = [
                {
                    "date": r.date,
                    "sleep_score": r.sleep_score,
                    "risk_level": r.risk_level,
                    "wake_fraction": r.wake_fraction,
                    "event_rate": r.event_rate,
                }
                for r in reversed(recent_analytics)
            ]
            # Add current night to the list
            recent_nights.append({
                "date": result.get("date"),
                "sleep_score": result.get("sleep_score"),
                "risk_level": result.get("risk_level"),
                "wake_fraction": result.get("wake_fraction"),
                "event_rate": result.get("event_rate"),
            })

            from analytics.alerts import evaluate_alert
            alert_result = evaluate_alert(recent_nights)

            if alert_result["should_alert"]:
                # Check if there's already an open alert for this user
                existing = db.query(DoctorAlert).filter(
                    DoctorAlert.patient_str_id == user_id,
                    DoctorAlert.status == "OPEN",
                ).first()
                if not existing:
                    alert_row = DoctorAlert(
                        patient_str_id=user_id,
                        session_id=session_id,
                        severity=alert_result["severity"],
                        reason=alert_result["reasons"][0] if alert_result["reasons"] else "",
                        evidence_json=_json.dumps(alert_result["evidence_json"], default=str),
                        status="OPEN",
                    )
                    db.add(alert_row)
                    logger.info("[%s] DoctorAlert created: %s", session_id, alert_result["severity"])

        except Exception as e:
            logger.warning("[%s] Alert evaluation failed: %s", session_id, e)

        db.commit()
        logger.info("[%s] DB updated successfully", session_id)

    except Exception as e:
        logger.error("[%s] DB commit failed: %s", session_id, e)
    finally:
        db.close()

    return {
        "session_id": session_id,
        "user_id": user_id,
        "sleep_score": result.get("sleep_score"),
        "risk_level": result.get("risk_level"),
        "status": "complete",
    }
