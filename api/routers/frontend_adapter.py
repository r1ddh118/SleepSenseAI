"""Frontend-facing adapter endpoints.

These routes expose payloads that match the current frontend's expected shapes,
while sourcing data from the existing DB + generated artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models_db import Prediction
from models_db import Session as SessionModel
from models_db import User

router = APIRouter(prefix="/api/v1/frontend", tags=["frontend"])


def _risk_level(probability: float) -> str:
    if probability >= 0.7:
        return "high"
    if probability >= 0.4:
        return "moderate"
    return "low"


def _safe_json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _load_features_by_sid() -> dict[str, dict[str, Any]]:
    path = Path("artifacts/preprocessed_training_data.csv")
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}

    if "SID" not in df.columns:
        return {}

    rows: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        sid = str(row.get("SID", "")).strip()
        if not sid:
            continue
        rows[sid] = {
            "HR_mean": float(row.get("HR_mean", 0.0) or 0.0),
            "HR_std": float(row.get("HR_std", 0.0) or 0.0),
            "EDA_mean": float(row.get("EDA_mean", 0.0) or 0.0),
            "TEMP_mean": float(row.get("TEMP_mean", 0.0) or 0.0),
            "event_rate": float(row.get("event_rate", 0.0) or 0.0),
            # Synthetic but useful UI proxy for now.
            "sleep_efficiency": max(
                0.0,
                min(
                    100.0,
                    100.0
                    - float(row.get("sleep_stage_pct_W", 0.0) or 0.0) * 100.0
                    - float(row.get("event_rate", 0.0) or 0.0) * 200.0,
                ),
            ),
            "sleepStages": {
                "wake": round(float(row.get("sleep_stage_pct_W", 0.0) or 0.0) * 100),
                "n1": round(float(row.get("sleep_stage_pct_N1", 0.0) or 0.0) * 100),
                "n2": round(float(row.get("sleep_stage_pct_N2", 0.0) or 0.0) * 100),
                "n3": round(float(row.get("sleep_stage_pct_N3", 0.0) or 0.0) * 100),
                "rem": round(float(row.get("sleep_stage_pct_R", 0.0) or 0.0) * 100),
            },
        }
    return rows


def _latest_prediction(db: DBSession, session_id: int) -> Prediction | None:
    return (
        db.query(Prediction)
        .filter(Prediction.session_id == session_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )


@router.get("/dashboard")
def get_dashboard(db: DBSession = Depends(get_db)):
    sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
    features_by_sid = _load_features_by_sid()

    out_sessions: list[dict[str, Any]] = []
    risk_values: list[float] = []
    efficiency_values: list[float] = []
    deep_sleep_values: list[float] = []

    for s in sessions:
        pred = _latest_prediction(db, s.id)
        probability = float(pred.probability) if pred and pred.probability is not None else 0.0
        risk_values.append(probability)

        feature_row = features_by_sid.get(s.sid, {})
        features = {
            "HR_mean": feature_row.get("HR_mean", 0.0),
            "HR_std": feature_row.get("HR_std", 0.0),
            "EDA_mean": feature_row.get("EDA_mean", 0.0),
            "TEMP_mean": feature_row.get("TEMP_mean", 0.0),
            "event_rate": feature_row.get("event_rate", 0.0),
            "sleep_efficiency": feature_row.get("sleep_efficiency", 0.0),
        }
        sleep_stages = feature_row.get(
            "sleepStages",
            {"wake": 0, "n1": 0, "n2": 0, "n3": 0, "rem": 0},
        )

        efficiency_values.append(float(features["sleep_efficiency"]))
        deep_sleep_values.append(float(sleep_stages.get("n3", 0)))

        out_sessions.append(
            {
                "id": s.sid,
                "sid": s.sid,
                "date": (s.created_at.isoformat() if s.created_at else None),
                "duration": int((s.duration_seconds or 0) / 60),
                "riskProbability": probability,
                "riskLevel": _risk_level(probability),
                "status": s.status if s.status in ("completed", "processing", "recording") else "completed",
                "sleepStages": sleep_stages,
                "features": features,
            }
        )

    # lightweight patient block for current UI card
    first_user: User | None = db.query(User).order_by(User.created_at.asc()).first()
    patient_info = {
        "name": first_user.email if first_user else "SleepSense User",
        "patientId": f"PT-{first_user.id:04d}" if first_user else "PT-0000",
        "age": None,
        "deviceId": "E4-RPi5-001",
        "totalSessions": len(out_sessions),
        "avgRiskScore": (sum(risk_values) / len(risk_values)) if risk_values else 0.0,
        "lastSessionDate": out_sessions[0]["date"] if out_sessions else None,
    }

    summary = {
        "avgRisk": (sum(risk_values) / len(risk_values)) if risk_values else 0.0,
        "avgEfficiency": (sum(efficiency_values) / len(efficiency_values)) if efficiency_values else 0.0,
        "avgDeepSleep": (sum(deep_sleep_values) / len(deep_sleep_values)) if deep_sleep_values else 0.0,
        "totalSessions": len(out_sessions),
    }

    return {
        "patientInfo": patient_info,
        "summary": summary,
        "sessions": out_sessions,
    }


@router.get("/sessions/{sid}")
def get_session_detail(sid: str, db: DBSession = Depends(get_db)):
    s = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not s:
        return {"error": f"Session '{sid}' not found"}

    features_by_sid = _load_features_by_sid()
    feature_row = features_by_sid.get(
        sid,
        {
            "HR_mean": 0.0,
            "HR_std": 0.0,
            "EDA_mean": 0.0,
            "TEMP_mean": 0.0,
            "event_rate": 0.0,
            "sleep_efficiency": 0.0,
            "sleepStages": {"wake": 0, "n1": 0, "n2": 0, "n3": 0, "rem": 0},
        },
    )
    pred = _latest_prediction(db, s.id)
    probability = float(pred.probability) if pred and pred.probability is not None else 0.0

    return {
        "id": s.sid,
        "sid": s.sid,
        "date": (s.created_at.isoformat() if s.created_at else None),
        "duration": int((s.duration_seconds or 0) / 60),
        "riskProbability": probability,
        "riskLevel": _risk_level(probability),
        "status": s.status if s.status in ("completed", "processing", "recording") else "completed",
        "sleepStages": feature_row["sleepStages"],
        "features": {
            "HR_mean": feature_row["HR_mean"],
            "HR_std": feature_row["HR_std"],
            "EDA_mean": feature_row["EDA_mean"],
            "TEMP_mean": feature_row["TEMP_mean"],
            "event_rate": feature_row["event_rate"],
            "sleep_efficiency": feature_row["sleep_efficiency"],
        },
        "prediction": {
            "label": pred.label if pred else "",
            "model_name": pred.model_name if pred else None,
            "recommendations": _safe_json_loads(pred.recommendations_json if pred else None, []),
            "shap_top_features": _safe_json_loads(pred.shap_features if pred else None, []),
        },
        "reportUrl": f"/api/v1/sessions/{sid}/report",
    }


@router.get("/models/leaderboard")
def get_models_leaderboard():
    path = Path("artifacts/model_leaderboard.csv")
    summary_path = Path("artifacts/training_summary.json")
    if not path.exists():
        return []

    active_name = None
    if summary_path.exists():
        try:
            with open(summary_path, encoding="utf-8") as f:
                active_name = json.load(f).get("best_model")
        except Exception:
            active_name = None

    df = pd.read_csv(path)
    out = []
    for _, row in df.iterrows():
        model_name = str(row.get("model_name", ""))
        out.append(
            {
                "name": model_name,
                "accuracy": float(row.get("accuracy", 0.0) or 0.0),
                "precision": float(row.get("precision", 0.0) or 0.0),
                "recall": float(row.get("recall", 0.0) or 0.0),
                "f1Score": float(row.get("f1", 0.0) or 0.0),
                "aucRoc": float(row.get("roc_auc", 0.0) or 0.0),
                # Training duration per-model is not persisted in current backend.
                "trainTime": 0.0,
                "isActive": model_name == active_name,
            }
        )
    return sorted(out, key=lambda r: r["aucRoc"], reverse=True)

