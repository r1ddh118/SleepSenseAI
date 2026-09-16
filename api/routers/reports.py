"""Doctor report endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session as DBSession

from analytics.report_builder import MEDICAL_DISCLAIMER, build_report_payload, render_report_csv, render_report_html
from database import get_db
from models_db import DoctorAlert, ManualSleepSession, Prediction, Session as SessionModel, SleepAnalytics

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


def _analytics(db: DBSession, session_id: int) -> SleepAnalytics | None:
    return db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session_id).first()


def _manual_session(db: DBSession, session_id: int) -> ManualSleepSession | None:
    return db.query(ManualSleepSession).filter(ManualSleepSession.session_id == session_id).first()


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
    analytics = _analytics(db, session.id)
    manual = _manual_session(db, session.id)
    metrics = _load_json(analytics.metrics_json, {}) if analytics else {}
    risk_payload = _load_json(analytics.risk_json, {}) if analytics else {}
    recommendations = (
        _load_json(analytics.recommendations_json, [])
        if analytics and analytics.recommendations_json
        else (_load_json(prediction.recommendations_json, []) if prediction else [])
    )

    shap_features = _load_json(prediction.shap_features, []) if prediction else []

    patient_info = {
        "patient_id": manual.patient_uid if manual else session.user_id,
        "session_id": session.sid,
        "database_session_id": session.id,
        "status": session.status,
        "analytics_status": analytics.status if analytics else "Not available",
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
        "date": manual.date if manual else None,
        "sleep_score": analytics.sleep_score if analytics else None,
        "sleep_category": analytics.sleep_category if analytics else None,
        "sleep_efficiency": analytics.sleep_efficiency if analytics else None,
        "sleep_duration_hours": metrics.get("sleep_duration_hours"),
        "stage_fractions": {
            "wake": metrics.get("wake_fraction"),
            "n1": metrics.get("n1_fraction"),
            "n2": metrics.get("n2_fraction"),
            "n3": metrics.get("n3_fraction"),
            "rem": metrics.get("rem_fraction"),
        },
        "prediction_label": prediction.label if prediction else "Not available",
        "prediction_probability": prediction.probability if prediction else None,
        "prediction": prediction.prediction if prediction else None,
        "predictions_csv_path": prediction.predictions_csv_path if prediction else None,
    }

    risk_assessment = {
        "risk_level": analytics.risk_level if analytics else (prediction.label if prediction else "Not available"),
        "risk_score": risk_payload.get("risk_score"),
        "risk_flags": risk_payload.get("risk_flags", []),
        "event_rate": metrics.get("event_rate"),
        "probability": prediction.probability if prediction else None,
        "shap_top_features": shap_features,
    }

    lifestyle = {
        "caffeine": metrics.get("caffeine", manual.caffeine if manual else None),
        "screen_time": metrics.get("screen_time", manual.screen_time if manual else None),
        "exercise_minutes": metrics.get("exercise_minutes", manual.exercise_minutes if manual else None),
        "stress_level": metrics.get("stress_level", manual.stress_level if manual else None),
        "nap_minutes": metrics.get("nap_minutes", manual.nap_minutes if manual else None),
        "awakenings": metrics.get("awakenings", manual.awakenings if manual else None),
    }

    longitudinal_trend = {
        key: value
        for key, value in metrics.items()
        if key.endswith(("_7d_avg", "_14d_avg", "_30d_avg", "_7d_trend", "_14d_trend", "_30d_trend"))
    }
    if not longitudinal_trend:
        longitudinal_trend = {"status": "Not available for this session yet"}

    model_info = {
        "model_name": prediction.model_name if prediction else "Spark analytics rule pipeline",
        "model_output_type": "Spark nightly analytics" if analytics else ("legacy prediction row" if prediction else "Not available"),
        "clinically_validated": False,
        "analytics_label": "Academic analytics score and screening rules; not clinically validated.",
    }

    return build_report_payload(
        session_id=session.sid,
        generated_at=datetime.utcnow().isoformat(),
        patient_info=patient_info,
        sleep_summary=sleep_summary,
        longitudinal_trend=longitudinal_trend,
        risk_assessment=risk_assessment,
        lifestyle=lifestyle,
        recommendations=recommendations,
        alerts=_session_alerts(db, session),
        model_info=model_info,
    )


def _build_patient_report(db: DBSession, patient_id: str) -> dict[str, Any]:
    rows = (
        db.query(ManualSleepSession, SessionModel, SleepAnalytics)
        .join(SessionModel, ManualSleepSession.session_id == SessionModel.id)
        .outerjoin(SleepAnalytics, SleepAnalytics.session_id == SessionModel.id)
        .filter(ManualSleepSession.patient_uid == patient_id)
        .order_by(ManualSleepSession.date.asc(), SessionModel.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(404, f"Patient '{patient_id}' has no manual sleep sessions")

    nightly_history = []
    recommendations: list[dict[str, Any]] = []
    alerts = (
        db.query(DoctorAlert)
        .filter(DoctorAlert.patient_id == patient_id)
        .order_by(DoctorAlert.created_at.desc(), DoctorAlert.id.desc())
        .all()
    )
    for manual, session, analytics in rows:
        metrics = _load_json(analytics.metrics_json, {}) if analytics else {}
        risk_payload = _load_json(analytics.risk_json, {}) if analytics else {}
        recs = _load_json(analytics.recommendations_json, []) if analytics else []
        recommendations.extend(recs)
        nightly_history.append(
            {
                "date": manual.date,
                "session_id": session.sid,
                "database_session_id": session.id,
                "status": analytics.status if analytics else session.status,
                "sleep_score": analytics.sleep_score if analytics else None,
                "sleep_category": analytics.sleep_category if analytics else None,
                "sleep_efficiency": analytics.sleep_efficiency if analytics else None,
                "risk_level": analytics.risk_level if analytics else None,
                "event_rate": metrics.get("event_rate"),
                "wake_fraction": metrics.get("wake_fraction", manual.wake_fraction),
                "n3_fraction": metrics.get("n3_fraction", manual.n3_fraction),
                "rem_fraction": metrics.get("rem_fraction", manual.rem_fraction),
                "risk_flags": risk_payload.get("risk_flags", []),
                "lifestyle": {
                    "caffeine": metrics.get("caffeine", manual.caffeine),
                    "screen_time": metrics.get("screen_time", manual.screen_time),
                    "exercise_minutes": metrics.get("exercise_minutes", manual.exercise_minutes),
                    "stress_level": metrics.get("stress_level", manual.stress_level),
                    "nap_minutes": metrics.get("nap_minutes", manual.nap_minutes),
                    "awakenings": metrics.get("awakenings", manual.awakenings),
                },
            }
        )

    latest_metrics = {}
    for _, _, analytics in reversed(rows):
        if analytics and analytics.metrics_json:
            latest_metrics = _load_json(analytics.metrics_json, {})
            break
    longitudinal_trend = {
        key: value
        for key, value in latest_metrics.items()
        if key.endswith(("_7d_avg", "_14d_avg", "_30d_avg", "_7d_trend", "_14d_trend", "_30d_trend"))
    }

    return {
        "report_type": "doctor_patient_sleep_report",
        "patient_id": patient_id,
        "generated_at": datetime.utcnow().isoformat(),
        "sections": {
            "patient_info": {
                "patient_id": patient_id,
                "night_count": len(nightly_history),
                "first_date": nightly_history[0]["date"],
                "latest_date": nightly_history[-1]["date"],
            },
            "nightly_history": nightly_history,
            "longitudinal_trend": longitudinal_trend or {"status": "Not available for this patient yet"},
            "risk_assessment": {
                "latest_risk_level": nightly_history[-1]["risk_level"],
                "open_alert_count": len([alert for alert in alerts if alert.status == "OPEN"]),
            },
            "recommendations": recommendations,
            "alerts": [
                {
                    "id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "status": alert.status,
                    "reason": alert.reason,
                    "evidence": _load_json(alert.evidence_json, {}),
                }
                for alert in alerts
            ],
            "model_info": {
                "model_name": "Spark analytics rule pipeline",
                "model_output_type": "Patient-level nightly analytics summary",
                "clinically_validated": False,
                "analytics_label": "Academic analytics score and screening rules; not clinically validated.",
            },
            "disclaimer": {"text": MEDICAL_DISCLAIMER},
        },
    }


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


@router.get("/doctor/patients/{patient_id}/report")
def get_patient_report(
    patient_id: str,
    format: str = Query(default="json", pattern="^(json|csv|html)$"),
    db: DBSession = Depends(get_db),
):
    report = _build_patient_report(db, patient_id)
    if format == "json":
        return JSONResponse(report)
    if format == "csv":
        return Response(
            render_report_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="sleepsense_patient_report_{patient_id}.csv"'},
        )
    return HTMLResponse(render_report_html(report))
