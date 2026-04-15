"""Prediction jobs and results."""

import json
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from config import settings
from database import get_db
from models_db import Prediction
from models_db import Session as SessionModel
from schemas import PredictRequest, PredictionOut, TaskStatus
from tasks import app as celery_app
from tasks import run_prediction

router = APIRouter(prefix="/api/v1", tags=["predictions"])


@router.post("/sessions/{sid}/predict", response_model=TaskStatus)
def trigger_prediction(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user=Depends(get_current_user),
    body: PredictRequest | None = Body(default=None),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")

    csv_path = (
        (body.sensor_csv if body and body.sensor_csv else None)
        or session.sensor_csv_path
        or str(settings.datasets_path / f"live_{sid}.csv")
    )
    if not Path(csv_path).exists():
        raise HTTPException(422, f"Sensor CSV not found: {csv_path}")

    model_path = (
        (body.model_pickle if body and body.model_pickle else None)
        or str(settings.artifacts_path / "best_model.pkl")
    )

    task = run_prediction.delay(sid, csv_path, model_path)
    session.status = "processing"
    db.commit()

    return TaskStatus(task_id=task.id, status="PENDING")


@router.get("/tasks/{task_id}", response_model=TaskStatus)
def get_task_status(
    task_id: str,
    db: DBSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = AsyncResult(task_id, app=celery_app)
    st = result.status

    if st == "SUCCESS":
        data = result.result
        sid = data.get("sid")

        session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
        if session:
            existing = (
                db.query(Prediction)
                .filter(Prediction.session_id == session.id)
                .order_by(Prediction.created_at.desc())
                .first()
            )

            if existing is None or existing.prediction is None:
                pred_row = Prediction(
                    session_id=session.id,
                    model_name=data.get("model_name"),
                    prediction=data.get("prediction"),
                    probability=data.get("probability"),
                    label=data.get("label"),
                    shap_features=json.dumps(data.get("shap_top_features", [])),
                    recommendations_json=json.dumps(data.get("recommendations", [])),
                    predictions_csv_path=data.get("predictions_csv"),
                )
                db.add(pred_row)
                session.status = "complete"
                db.commit()

        return TaskStatus(task_id=task_id, status="SUCCESS", result=data)

    if st == "FAILURE":
        err = result.result
        return TaskStatus(
            task_id=task_id,
            status="FAILURE",
            error=str(err) if err is not None else "Task failed",
        )

    return TaskStatus(task_id=task_id, status=st)


@router.get("/sessions/{sid}/predictions", response_model=list[PredictionOut])
def get_predictions(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")

    preds = (
        db.query(Prediction)
        .filter(Prediction.session_id == session.id)
        .order_by(Prediction.created_at.desc())
        .all()
    )

    out: list[dict] = []
    for p in preds:
        shap_raw = json.loads(p.shap_features) if p.shap_features else []
        rec_raw = (
            json.loads(p.recommendations_json)
            if p.recommendations_json
            else []
        )
        out.append(
            {
                "session_id": p.session_id,
                "sid": sid,
                "prediction": p.prediction if p.prediction is not None else 0,
                "probability": p.probability if p.probability is not None else 0.0,
                "label": p.label or "",
                "model_name": p.model_name,
                "shap_top_features": shap_raw,
                "recommendations": rec_raw,
                "created_at": p.created_at,
            }
        )
    return out


@router.get("/sessions/{sid}/report")
def download_report(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")

    per_session = settings.artifacts_path / f"predictions_{sid}.csv"
    if per_session.exists():
        return FileResponse(
            path=str(per_session),
            media_type="text/csv",
            filename=f"sleepsense_report_{sid}.csv",
        )

    legacy = settings.artifacts_path / "predictions.csv"
    if legacy.exists():
        return FileResponse(
            path=str(legacy),
            media_type="text/csv",
            filename=f"sleepsense_report_{sid}.csv",
        )

    raise HTTPException(
        404, "Predictions CSV not found — run predict for this session first"
    )


@router.get("/sessions/{sid}/trend")
def get_trend(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Last up to 7 sessions for the same user that have a stored prediction (chronological order)."""
    sess_row = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not sess_row:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if sess_row.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")
    if sess_row.user_id is None:
        raise HTTPException(404, "Session has no user; cannot compute trend")

    rows = (
        db.query(SessionModel, Prediction)
        .join(Prediction, Prediction.session_id == SessionModel.id)
        .filter(SessionModel.user_id == sess_row.user_id)
        .filter(Prediction.probability.isnot(None))
        .order_by(SessionModel.created_at.desc())
        .limit(7)
        .all()
    )

    return [
        {
            "date": s.created_at.isoformat() if s.created_at else None,
            "sid": s.sid,
            "probability": float(p.probability) if p.probability is not None else None,
            "label": p.label,
        }
        for s, p in reversed(rows)
    ]
