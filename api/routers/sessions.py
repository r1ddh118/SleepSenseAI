"""CRUD for recording sessions."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from database import get_db
from models_db import Session as SessionModel
from models_db import User
from schemas import SessionCreate, SessionOut, SessionUpdate

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


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
        if body.status == "recording":
            session.started_at = datetime.utcnow()
        elif body.status in ("complete", "failed"):
            session.ended_at = datetime.utcnow()
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
