"""CRUD for recording sessions — legacy CSV sessions + new manual entry."""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from database import get_db
from models_db import ManualSleepSession, Session as SessionModel
from models_db import User
from schemas import (
    ManualSleepSessionCreate,
    ManualSleepSessionOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    UserSleepTrendOut,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/manual", response_model=ManualSleepSessionOut, status_code=202)
def create_manual_session(
    body: ManualSleepSessionCreate,
    db: DBSession = Depends(get_db),
):
    """Submit a manual sleep entry.

    Returns 202 Accepted immediately with status=PROCESSING.
    A Celery worker will invoke the Spark pipeline asynchronously.
    Poll GET /sessions/{session_id}/analytics to check completion.
    """
    from config import settings

    session_id = f"{body.user_id}-{body.date}-{uuid.uuid4().hex[:6]}"

    # Write a minimal raw CSV for the Spark pipeline to ingest
    raw_dir = settings.data_raw_path
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_csv = raw_dir / f"{session_id}.csv"

    # Construct a single synthetic observation row from manual entry
    import csv as _csv
    header = [
        "user_id", "session_id", "timestamp", "date", "heart_rate",
        "acc_x", "acc_y", "acc_z", "sleep_stage",
        "bed_time", "sleep_onset", "wake_time",
        "caffeine", "screen_time", "exercise_minutes", "stress_level",
        "nap_minutes", "awakenings", "event_count", "spo2",
    ]
    ts = f"{body.date} 02:00:00"  # synthetic mid-sleep timestamp
    row_vals = [
        body.user_id, session_id, ts, body.date,
        str(body.avg_hr or ""),
        "0.1", "0.1", "0.9",           # minimal acc (assumed asleep)
        "N2",                            # default stage for manual entry
        body.bed_time or "",
        body.sleep_onset or "",
        body.wake_time or "",
        str(body.caffeine_mg or 0),
        str(body.screen_time_min or 0),
        str(body.exercise_minutes or 0),
        str(body.stress_level or 5),
        str(body.nap_minutes or 0),
        str(body.awakenings or 0),
        "0",
        str(body.avg_spo2 or 97),
    ]
    with open(raw_csv, "w", newline="") as f:
        writer = _csv.writer(f)
        writer.writerow(header)
        writer.writerow(row_vals)

    manual = ManualSleepSession(
        session_id=session_id,
        user_str_id=body.user_id,
        date=body.date,
        bed_time=body.bed_time,
        sleep_onset=body.sleep_onset,
        wake_time=body.wake_time,
        sleep_duration_hours=body.sleep_duration_hours,
        awakenings=body.awakenings,
        caffeine_mg=body.caffeine_mg,
        screen_time_min=body.screen_time_min,
        exercise_minutes=body.exercise_minutes,
        stress_level=body.stress_level,
        nap_minutes=body.nap_minutes,
        avg_hr=body.avg_hr,
        avg_spo2=body.avg_spo2,
        notes=body.notes,
        raw_csv_path=str(raw_csv),
        status="PROCESSING",
    )
    db.add(manual)
    db.commit()
    db.refresh(manual)

    # Enqueue Celery task — never block here
    try:
        from tasks import run_sleep_analytics
        run_sleep_analytics.delay(manual.session_id, body.user_id, str(raw_csv))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Celery enqueue failed: %s", e)

    return manual


@router.get("/users/{user_id}/sleep-trend", response_model=UserSleepTrendOut)
def get_user_sleep_trend(
    user_id: str,
    days: int = 30,
    db: DBSession = Depends(get_db),
):
    """Return the last N days of nightly sleep trend for a user."""
    from models_db import SleepAnalytics
    rows = (
        db.query(SleepAnalytics)
        .filter(SleepAnalytics.user_str_id == user_id)
        .order_by(SleepAnalytics.date.asc())
        .limit(days)
        .all()
    )
    nights = [
        {
            "date": r.date or "",
            "sleep_score": r.sleep_score,
            "sleep_score_7d_avg": r.sleep_score_7d_avg,
            "sleep_duration_hours": r.sleep_duration_hours,
            "sleep_efficiency": r.sleep_efficiency,
            "n3_fraction": r.n3_fraction,
            "rem_fraction": r.rem_fraction,
            "risk_level": r.risk_level,
        }
        for r in rows
    ]
    return UserSleepTrendOut(user_id=user_id, nights=nights)



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
