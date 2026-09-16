"""CRUD for recording sessions."""

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from database import get_db
from models_db import ManualSleepSession, SleepAnalytics
from models_db import Session as SessionModel
from models_db import User
from schemas import ManualSleepSessionAccepted, ManualSleepSessionCreate, SessionCreate, SessionOut, SessionUpdate

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _is_unknown(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in {"", "unknown", "unk", "na", "n/a"})


def _float_or_none(value):
    if _is_unknown(value):
        return None
    return float(value)


def _int_or_none(value):
    if _is_unknown(value):
        return None
    return int(float(value))


@router.post("/manual", response_model=ManualSleepSessionAccepted)
def create_manual_session(body: ManualSleepSessionCreate, db: DBSession = Depends(get_db)):
    """Save manual sleep input and enqueue Spark analytics; no Spark runs inline."""
    sid = f"{body.user_id}_{body.date}_{uuid4().hex[:8]}"
    session = SessionModel(
        sid=sid,
        user_id=None,
        status="PROCESSING",
        notes=body.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    manual = ManualSleepSession(
        session_id=session.id,
        patient_uid=body.user_id,
        date=body.date,
        bed_time=None if _is_unknown(body.bed_time) else body.bed_time,
        sleep_onset=None if _is_unknown(body.sleep_onset) else body.sleep_onset,
        wake_time=None if _is_unknown(body.wake_time) else body.wake_time,
        sleep_duration_hours=_float_or_none(body.sleep_duration_hours),
        sleep_efficiency=_float_or_none(body.sleep_efficiency),
        n3_fraction=_float_or_none(body.n3_fraction),
        rem_fraction=_float_or_none(body.rem_fraction),
        wake_fraction=_float_or_none(body.wake_fraction),
        heart_rate=_float_or_none(body.heart_rate),
        hr_std=_float_or_none(body.hr_std),
        movement_std=_float_or_none(body.movement_std),
        event_rate=_float_or_none(body.event_rate),
        spo2=_float_or_none(body.spo2),
        caffeine=_int_or_none(body.caffeine),
        screen_time=_int_or_none(body.screen_time),
        exercise_minutes=_int_or_none(body.exercise_minutes),
        stress_level=_int_or_none(body.stress_level),
        nap_minutes=_int_or_none(body.nap_minutes),
        awakenings=_int_or_none(body.awakenings),
        raw_json=body.model_dump_json(),
    )
    db.add(manual)
    db.add(SleepAnalytics(session_id=session.id, status="PROCESSING"))
    db.commit()

    from tasks import run_sleep_analytics

    task = run_sleep_analytics.delay(session.id)
    analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session.id).first()
    if analytics:
        analytics.spark_job_id = task.id
        db.commit()
    return ManualSleepSessionAccepted(session_id=str(session.id))


@router.get("/{sid}/analytics")
def get_session_analytics(sid: str, db: DBSession = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if session is None and sid.isdigit():
        session = db.query(SessionModel).filter(SessionModel.id == int(sid)).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")

    analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session.id).first()
    if not analytics:
        return {"session_id": str(session.id), "status": session.status or "PROCESSING"}
    return {
        "session_id": str(session.id),
        "sid": session.sid,
        "status": analytics.status,
        "sleep_score": analytics.sleep_score,
        "sleep_category": analytics.sleep_category,
        "sleep_efficiency": analytics.sleep_efficiency,
        "risk_level": analytics.risk_level,
        "risk": json.loads(analytics.risk_json or "{}"),
        "recommendations": json.loads(analytics.recommendations_json or "[]"),
        "metrics": json.loads(analytics.metrics_json or "{}"),
        "spark_job_id": analytics.spark_job_id,
        "error": analytics.error,
    }


@router.post("/", response_model=SessionOut)
def create_session(
    body: SessionCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(SessionModel).filter(SessionModel.sid == body.sid).first()
    if existing:
        raise HTTPException(400, f"Session '{body.sid}' already exists")

    session = SessionModel(
        sid=body.sid,
        user_id=current_user.id,
        status="created",
        duration_seconds=body.duration_seconds,
        notes=body.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/", response_model=list[SessionOut])
def list_sessions(
    skip: int = 0,
    limit: int = 50,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role in ("clinician", "admin"):
        return (
            db.query(SessionModel)
            .order_by(SessionModel.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    return (
        db.query(SessionModel)
        .filter(SessionModel.user_id == current_user.id)
        .order_by(SessionModel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{sid}", response_model=SessionOut)
def get_session(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")
    return session


@router.patch("/{sid}", response_model=SessionOut)
def update_session(
    sid: str,
    body: SessionUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")

    if body.status is not None:
        session.status = body.status
        from ws_manager import ws_manager
        
        if body.status == "recording":
            session.started_at = datetime.utcnow()
            ws_manager.set_recording_session(sid)
            
        elif body.status in ("complete", "completed", "failed"):
            session.ended_at = datetime.utcnow()
            ws_manager.set_recording_session(None)
            if body.status in ("complete", "completed"):
                # Trigger cumulative training and prediction
                from tasks import run_training_and_prediction
                run_training_and_prediction.delay(sid=sid)

    if body.sensor_csv_path is not None:
        session.sensor_csv_path = body.sensor_csv_path
    if body.notes is not None:
        session.notes = body.notes

    db.commit()
    db.refresh(session)
    return session


@router.post("/{sid}/complete")
def mark_complete(sid: str, db: DBSession = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if session:
        session.status = "complete"
        session.ended_at = datetime.utcnow()
        db.commit()
        
        from ws_manager import ws_manager
        ws_manager.set_recording_session(None)
        
        from tasks import run_training_and_prediction
        run_training_and_prediction.delay(sid=sid)
        
    return {"status": "ok"}


@router.delete("/{sid}")
def delete_session(
    sid: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(SessionModel).filter(SessionModel.sid == sid).first()
    if not session:
        raise HTTPException(404, f"Session '{sid}' not found")
    if current_user.role not in ("clinician", "admin"):
        if session.user_id != current_user.id:
            raise HTTPException(404, f"Session '{sid}' not found")
    db.delete(session)
    db.commit()
    return {"deleted": sid}
