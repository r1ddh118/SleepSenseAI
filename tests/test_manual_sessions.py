from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

API_DIR = Path(__file__).resolve().parent.parent / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from database import Base
from models_db import ManualSleepSession, SleepAnalytics, Session as SessionModel
from routers import sessions
from schemas import ManualSleepSessionCreate


class _FakeAsyncResult:
    id = "fake-celery-job"


class _FakeTask:
    calls: list[int] = []

    @classmethod
    def delay(cls, session_id: int):
        cls.calls.append(session_id)
        return _FakeAsyncResult()


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSession()


def test_manual_session_saves_raw_row_and_returns_processing(monkeypatch):
    import tasks

    _FakeTask.calls = []
    monkeypatch.setattr(sessions, "_ensure_celery_broker_available", lambda: None)
    monkeypatch.setattr(tasks, "run_sleep_analytics", _FakeTask)
    db = _db()
    try:
        body = ManualSleepSessionCreate(
            user_id="U034",
            date="2026-09-10",
            bed_time="23:00",
            sleep_onset="23:20",
            wake_time="07:00",
            sleep_efficiency="unknown",
            screen_time=180,
            stress_level=8,
        )
        response = sessions.create_manual_session(body, db)

        assert response.status == "PROCESSING"
        assert response.session_id.isdigit()
        assert _FakeTask.calls == [int(response.session_id)]
        assert db.query(SessionModel).count() == 1
        assert db.query(ManualSleepSession).count() == 1
        analytics = db.query(SleepAnalytics).one()
        assert analytics.status == "PROCESSING"
        assert analytics.spark_job_id == "fake-celery-job"
    finally:
        db.close()


def test_get_session_analytics_returns_processing_payload(monkeypatch):
    import tasks

    _FakeTask.calls = []
    monkeypatch.setattr(sessions, "_ensure_celery_broker_available", lambda: None)
    monkeypatch.setattr(tasks, "run_sleep_analytics", _FakeTask)
    db = _db()
    try:
        response = sessions.create_manual_session(
            ManualSleepSessionCreate(user_id="U034", date="2026-09-10"),
            db,
        )

        payload = sessions.get_session_analytics(response.session_id, db)

        assert payload["session_id"] == response.session_id
        assert payload["status"] == "PROCESSING"
        assert payload["sleep_score"] is None
    finally:
        db.close()


def test_manual_session_returns_503_without_redis_and_does_not_save_rows(monkeypatch):
    def broker_unavailable():
        raise HTTPException(status_code=503, detail="Analytics queue is unavailable")

    monkeypatch.setattr(sessions, "_ensure_celery_broker_available", broker_unavailable)
    db = _db()
    try:
        with pytest.raises(HTTPException) as exc_info:
            sessions.create_manual_session(
                ManualSleepSessionCreate(user_id="U034", date="2026-09-10"),
                db,
            )

        assert exc_info.value.status_code == 503
        assert db.query(SessionModel).count() == 0
        assert db.query(ManualSleepSession).count() == 0
        assert db.query(SleepAnalytics).count() == 0
    finally:
        db.close()
