from config import REPO_ROOT, settings

import shutil
from pathlib import Path
from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import pandas as pd

from spark.night_schema import validate_night_columns
from spark.night_pipeline import process_night_session
from models_db import NightSession, SessionEDA, SessionReport
"""CRUD for recording sessions."""

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from kombu.exceptions import OperationalError as KombuOperationalError
import redis as redis_lib
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from config import settings
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


def _ensure_celery_broker_available() -> None:
    """Fail fast when the async analytics queue is unavailable.

    A manual session is only useful when its Celery job can be enqueued. Checking
    Redis before writing the session avoids leaving a misleading PROCESSING row
    behind when a developer has started Uvicorn without Redis.
    """
    try:
        redis_lib.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        ).ping()
    except redis_lib.RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Analytics queue is unavailable. Start Redis, then start the Celery worker and retry.",
        ) from exc


@router.post("/manual", response_model=ManualSleepSessionAccepted, deprecated=True)
def create_manual_session(body: ManualSleepSessionCreate, db: DBSession = Depends(get_db)):
    """[DEPRECATED / PRESERVED ENDPOINT] Save manual sleep input and enqueue Spark analytics; no Spark runs inline.
    The primary UI workflow now uses 1 Hz sensor CSV uploads via POST /api/v1/sessions/upload.
    """
    _ensure_celery_broker_available()
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

    try:
        task = run_sleep_analytics.delay(session.id)
    except KombuOperationalError as exc:
        # Redis may go down between the health check and task publication.
        session.status = "FAILED"
        analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session.id).first()
        if analytics:
            analytics.status = "FAILED"
            analytics.error = "Analytics queue was unavailable before the job could be started."
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Analytics queue is unavailable. Start Redis, then start the Celery worker and retry.",
        ) from exc

    analytics = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session.id).first()
    if analytics:
        analytics.spark_job_id = task.id
        db.commit()
    return ManualSleepSessionAccepted(session_id=str(session.id), id=str(session.id))


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


@router.post("/upload")
async def upload_night_session_csv(
    file: UploadFile = File(...),
    user_id: str = Form("U001"),
    session_id: str = Form(None),
    notes: str = Form(None),
    inline: bool = Form(False),
    db: DBSession = Depends(get_db),
):
    """Upload a 1 Hz night sensor CSV file, validate, store, and enqueue pipeline."""
    if not session_id:
        session_id = f"S_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    out_user_dir = REPO_ROOT / "data" / "raw" / "nights" / user_id
    out_user_dir.mkdir(parents=True, exist_ok=True)
    target_csv = out_user_dir / f"{session_id}.csv"

    with open(target_csv, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Validate CSV column contract
    try:
        df_head = pd.read_csv(target_csv, nrows=5)
        valid, missing = validate_night_columns(list(df_head.columns))
        if not valid:
            target_csv.unlink(missing_ok=True)
            raise HTTPException(400, f"CSV missing required 1 Hz night sensor columns: {missing}")
    except Exception as exc:
        target_csv.unlink(missing_ok=True)
        raise HTTPException(400, f"Failed to parse uploaded CSV: {str(exc)}")

    # Save to NightSession & SessionModel DB tables
    session_model = db.query(SessionModel).filter(SessionModel.sid == session_id).first()
    if not session_model:
        session_model = SessionModel(
            sid=session_id,
            user_id=None,
            status="queued",
            sensor_csv_path=str(target_csv),
            notes=notes or f"User {user_id} night upload",
        )
        db.add(session_model)

    night_session = db.query(NightSession).filter(NightSession.sid == session_id).first()
    if not night_session:
        night_session = NightSession(
            sid=session_id,
            user_id=user_id,
            status="queued",
            file_path=str(target_csv),
        )
        db.add(night_session)
    else:
        night_session.status = "queued"
        night_session.file_path = str(target_csv)

    db.commit()

    def _run_inline():
        out_parquet = REPO_ROOT / "data" / "parquet" / "epochs"
        out_eda = REPO_ROOT / "data" / "eda"
        metrics = process_night_session(
            session_id=session_id,
            csv_path=target_csv,
            out_parquet_dir=out_parquet,
            out_eda_dir=out_eda,
            user_id=user_id,
        )
        night_session.status = "completed"
        night_session.sleep_score = float(metrics.get("sleep_score", 0.0))
        night_session.risk_level = metrics.get("risk_level", "LOW")
        night_session.duration_seconds = metrics.get("duration_seconds", 0)
        session_model.status = "completed"

        eda_obj = db.query(SessionEDA).filter(SessionEDA.session_id == session_id).first()
        if not eda_obj:
            eda_obj = SessionEDA(
                session_id=session_id,
                user_id=user_id,
                num_samples=metrics.get("duration_seconds", 0),
                tonic_eda_mean_us=metrics.get("tonic_eda_mean_us", 0.0),
                phasic_peak_count=metrics.get("phasic_peak_count", 0),
                eda_json_path=str(out_eda / session_id / "eda.json"),
            )
            db.add(eda_obj)

        report_obj = db.query(SessionReport).filter(SessionReport.session_id == session_id).first()
        if not report_obj:
            report_obj = SessionReport(
                session_id=session_id,
                report_type="session_full",
                report_format="json",
                content=json.dumps(metrics),
                disclaimer="Academic risk screening only; not clinically validated.",
            )
            db.add(report_obj)

        db.commit()

    if inline:
        _run_inline()
    else:
        try:
            from celery_app import celery_app
            workers = celery_app.control.ping(timeout=0.15)
            if not workers:
                _run_inline()
            else:
                from tasks import run_sleep_analytics
                run_sleep_analytics.delay(session_id=session_id, source="csv_night")
        except Exception:
            _run_inline()

    return {
        "session_id": session_id,
        "status": night_session.status,
        "message": "Session uploaded successfully and processed",
    }


@router.get("/{sid}/status")
def get_session_processing_status(sid: str, db: DBSession = Depends(get_db)):
    """Poll processing status of a night session."""
    night_session = db.query(NightSession).filter(NightSession.sid == sid).first()
    session_model = db.query(SessionModel).filter(SessionModel.sid == sid).first()

    if not night_session and not session_model:
        # Check if parquet or eda output exists on disk
        eda_file = REPO_ROOT / "data" / "eda" / sid / "eda.json"
        parquet_file = REPO_ROOT / "data" / "parquet" / "epochs" / f"session_id={sid}" / "epochs.parquet"
        if eda_file.exists() and parquet_file.exists():
            return {"session_id": sid, "status": "completed"}
        raise HTTPException(404, f"Session '{sid}' not found")

    status = night_session.status if night_session else (session_model.status if session_model else "unknown")
    return {
        "session_id": sid,
        "status": status.lower(),
        "sleep_score": night_session.sleep_score if night_session else None,
        "risk_level": night_session.risk_level if night_session else None,
        "error": night_session.error if night_session else None,
    }


@router.get("/{sid}/eda")
def get_session_eda_artifact(sid: str):
    """Fetch high-resolution EDA artifact JSON."""
    json_path = REPO_ROOT / "data" / "eda" / sid / "eda.json"
    if not json_path.exists():
        json_path_alt = REPO_ROOT / "data" / "eda" / f"eda_{sid}.json"
        if json_path_alt.exists():
            json_path = json_path_alt
        else:
            raise HTTPException(404, f"EDA artifact for session '{sid}' not found")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/{sid}/epochs")
def get_session_epochs(sid: str):
    """Fetch 30-second epoch dataframe for session."""
    parquet_path = REPO_ROOT / "data" / "parquet" / "epochs" / f"session_id={sid}" / "epochs.parquet"
    if not parquet_path.exists():
        raise HTTPException(404, f"Epochs Parquet for session '{sid}' not found")

    df_epochs = pd.read_parquet(parquet_path)
    return df_epochs.to_dict(orient="records")


@router.get("/{sid}/timeline")
def get_session_timeline(sid: str):
    """Fetch hypnogram & biometric chart timeline."""
    parquet_path = REPO_ROOT / "data" / "parquet" / "epochs" / f"session_id={sid}" / "epochs.parquet"
    if not parquet_path.exists():
        raise HTTPException(404, f"Timeline Parquet for session '{sid}' not found")

    df_epochs = pd.read_parquet(parquet_path)
    timeline = []
    for idx, row in df_epochs.iterrows():
        timeline.append(
            {
                "epoch_index": int(row["epoch_index"]),
                "timestamp": row["start_timestamp_iso"],
                "stage": row["inferred_stage"],
                "hr_mean": row["hr_mean"],
                "movement_mean": row["movement_mean"],
                "spo2_mean": row["spo2_mean"],
                "eda_mean": row["eda_mean"],
                "snore_mean": row["snore_mean"],
            }
        )
    return {"session_id": sid, "timeline": timeline}


@router.get("/{sid}/report")
def get_session_report_download(
    sid: str,
    format: str = "json",
    db: DBSession = Depends(get_db),
):
    """Download session clinical report in json, csv, html, or pdf format."""
    from routers.reports import get_session_report
    return get_session_report(sid=sid, format=format, db=db)

