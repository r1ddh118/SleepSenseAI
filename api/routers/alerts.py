"""Doctor alerts router — OPEN/ACKNOWLEDGED/RESOLVED lifecycle."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from database import get_db
from models_db import DoctorAlert, User
from schemas import AlertAcknowledgeRequest, DoctorAlertOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/doctor", tags=["doctor-alerts"])


@router.get("/alerts", response_model=list[DoctorAlertOut])
def list_alerts(
    status: str | None = None,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all doctor alerts. Optionally filter by status (OPEN/ACKNOWLEDGED/RESOLVED)."""
    q = db.query(DoctorAlert)
    if status:
        q = q.filter(DoctorAlert.status == status.upper())
    alerts = q.order_by(DoctorAlert.created_at.desc()).limit(200).all()
    result = []
    for a in alerts:
        ev = None
        if a.evidence_json:
            try:
                ev = json.loads(a.evidence_json)
            except Exception:
                pass
        result.append(DoctorAlertOut(
            id=a.id,
            patient_str_id=a.patient_str_id,
            session_id=a.session_id,
            severity=a.severity,
            reason=a.reason,
            evidence_json=ev,
            status=a.status,
            created_at=a.created_at,
            acknowledged_at=a.acknowledged_at,
        ))
    return result


@router.post("/alerts/{alert_id}/acknowledge", response_model=DoctorAlertOut)
def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledgeRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge a doctor alert (doctor action)."""
    alert = db.query(DoctorAlert).filter(DoctorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.utcnow()
    if body.note:
        ev = {}
        if alert.evidence_json:
            try:
                ev = json.loads(alert.evidence_json)
            except Exception:
                pass
        ev["doctor_note"] = body.note
        alert.evidence_json = json.dumps(ev)

    db.commit()
    db.refresh(alert)

    ev_parsed = None
    if alert.evidence_json:
        try:
            ev_parsed = json.loads(alert.evidence_json)
        except Exception:
            pass

    return DoctorAlertOut(
        id=alert.id,
        patient_str_id=alert.patient_str_id,
        session_id=alert.session_id,
        severity=alert.severity,
        reason=alert.reason,
        evidence_json=ev_parsed,
        status=alert.status,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
    )


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a doctor alert."""
    alert = db.query(DoctorAlert).filter(DoctorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"id": alert_id, "status": "RESOLVED"}


@router.get("/patients")
def list_patients(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List distinct patients who have active alerts."""
    from models_db import SleepAnalytics
    patients = (
        db.query(DoctorAlert.patient_str_id)
        .filter(DoctorAlert.status == "OPEN")
        .distinct()
        .all()
    )
    return [{"patient_str_id": p[0]} for p in patients if p[0]]


@router.get("/patients/{patient_str_id}/report")
def get_patient_latest_report(
    patient_str_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent report for a patient."""
    from models_db import DoctorReport
    report = (
        db.query(DoctorReport)
        .filter(DoctorReport.patient_str_id == patient_str_id)
        .order_by(DoctorReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(404, f"No report found for patient {patient_str_id}")
    return {
        "patient_str_id": report.patient_str_id,
        "file_path": report.file_path,
        "format": report.format,
        "created_at": report.created_at,
    }
