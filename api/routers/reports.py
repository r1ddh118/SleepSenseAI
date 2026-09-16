"""Doctor report endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session as DBSession

from analytics.report_builder import build_report_payload, render_report_csv, render_report_html
from database import get_db
from models_db import DoctorAlert, Prediction, Session as SessionModel

router = APIRouter(prefix="/api/v1", tags=["reports"])


def _load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _resolve_session(db: DBSession, sid: str) -> SessionModel | None:
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if session:
        return session
    if sid.isdigit():
        return db.query(SessionModel).filter(SessionModel.id == int(sid)).first()
    return None


def _latest_prediction(db: DBSession, session_id: int) -> Prediction | None:
    return (
        db.query(Prediction)
        .filter(Prediction.session_id == session_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )


def _session_alerts(db: DBSession, session: SessionModel) -> list[dict[str, Any]]:
    rows = (
        db.query(DoctorAlert)
        .filter(DoctorAlert.session_id.in_([session.sid, str(session.id)]))
        .order_by(DoctorAlert.created_at.desc())
        .all()
    )
    alerts = []
    for row in rows:
        alerts.append(
            {
                "id": row.id,
                "alert_type": row.alert_type,
                "severity": row.severity,
                "status": row.status,
                "reason": row.reason,
                "evidence": _load_json(row.evidence_json, {}),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
        )
    return alerts


def _build_report(db: DBSession, sid: str) -> dict[str, Any]:
    session = _resolve_session(db, sid)
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")

    prediction = _latest_prediction(db, session.id)
    recommendations = _load_json(prediction.recommendations_json, []) if prediction else []
    shap_features = _load_json(prediction.shap_features, []) if prediction else []

    patient_info = {
        "patient_id": session.user_id,
        "session_id": session.sid,
        "database_session_id": session.id,
        "status": session.status,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "notes": session.notes,
    }
    if session.user:
        patient_info["patient_email"] = session.user.email
        patient_info["patient_role"] = session.user.role

    sleep_summary = {
        "duration_seconds": session.duration_seconds,
        "prediction_label": prediction.label if prediction else "Not available",
        "prediction_probability": prediction.probability if prediction else None,
        "prediction": prediction.prediction if prediction else None,
        "predictions_csv_path": prediction.predictions_csv_path if prediction else None,
    }

    risk_assessment = {
        "risk_level": prediction.label if prediction else "Not available",
        "probability": prediction.probability if prediction else None,
        "shap_top_features": shap_features,
    }

    model_info = {
        "model_name": prediction.model_name if prediction else "Not available",
        "model_output_type": "legacy prediction row" if prediction else "Not available",
        "clinically_validated": False,
    }

    return build_report_payload(
        session_id=session.sid,
        generated_at=datetime.utcnow().isoformat(),
        patient_info=patient_info,
        sleep_summary=sleep_summary,
        longitudinal_trend={
            "status": "Not available in DB yet",
            "source": "Spark Parquet analytics table will populate this section in the DB bridge phase.",
        },
        risk_assessment=risk_assessment,
        lifestyle={
            "status": "Not available in DB yet",
            "source": "Manual session/lifestyle fields will populate this section in the DB bridge phase.",
        },
        recommendations=recommendations,
        alerts=_session_alerts(db, session),
        model_info=model_info,
    )


@router.get("/sessions/{sid}/report")
def get_session_report(
    sid: str,
    format: str = Query(default="json", pattern="^(json|csv|html)$"),
    db: DBSession = Depends(get_db),
):
    report = _build_report(db, sid)
    if format == "json":
        return JSONResponse(report)
    if format == "csv":
        return Response(
            render_report_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="sleepsense_report_{sid}.csv"'},
        )
    return HTMLResponse(render_report_html(report))
