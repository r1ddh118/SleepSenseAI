"""Doctor alert lifecycle endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from database import get_db
from analytics.alerts import evaluate_persistent_alerts
from models_db import DoctorAlert

router = APIRouter(prefix="/api/v1/doctor/alerts", tags=["doctor-alerts"])


def _serialize(alert: DoctorAlert) -> dict[str, Any]:
    try:
        evidence = json.loads(alert.evidence_json or "{}")
    except json.JSONDecodeError:
        evidence = {}
    return {
        "id": alert.id,
        "patient_id": alert.patient_id,
        "doctor_id": alert.doctor_id,
        "session_id": alert.session_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "reason": alert.reason,
        "evidence": evidence,
        "status": alert.status,
        "created_at": alert.created_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
    }


def create_or_get_open_alert(db: DBSession, alert_data: dict[str, Any]) -> DoctorAlert:
    existing = (
        db.query(DoctorAlert)
        .filter(
            DoctorAlert.patient_id == str(alert_data["patient_id"]),
            DoctorAlert.alert_type == alert_data["alert_type"],
            DoctorAlert.status == "OPEN",
        )
        .first()
    )
    if existing:
        return existing

    alert = DoctorAlert(
        patient_id=str(alert_data["patient_id"]),
        doctor_id=alert_data.get("doctor_id"),
        session_id=str(alert_data["session_id"]),
        alert_type=alert_data["alert_type"],
        severity=alert_data["severity"],
        reason=alert_data["reason"],
        evidence_json=json.dumps(alert_data.get("evidence", {}), sort_keys=True),
        status=alert_data.get("status", "OPEN"),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def create_alerts_for_history(
    db: DBSession,
    nightly_rows: list[dict[str, Any]],
    doctor_id: int | None = None,
) -> list[DoctorAlert]:
    """Evaluate nightly history and persist any new OPEN doctor alerts."""
    created: list[DoctorAlert] = []
    for alert_data in evaluate_persistent_alerts(nightly_rows):
        if doctor_id is not None:
            alert_data["doctor_id"] = doctor_id
        created.append(create_or_get_open_alert(db, alert_data))
    return created


@router.get("")
def list_alerts(status: str | None = "OPEN", db: DBSession = Depends(get_db)):
    query = db.query(DoctorAlert)
    if status:
        query = query.filter(DoctorAlert.status == status.upper())
    alerts = query.order_by(DoctorAlert.created_at.desc(), DoctorAlert.id.desc()).all()
    return [_serialize(alert) for alert in alerts]


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: DBSession = Depends(get_db)):
    alert = db.query(DoctorAlert).filter(DoctorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Doctor alert {alert_id} not found")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return _serialize(alert)


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: DBSession = Depends(get_db)):
    alert = db.query(DoctorAlert).filter(DoctorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Doctor alert {alert_id} not found")
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return _serialize(alert)
