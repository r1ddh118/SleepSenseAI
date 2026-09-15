from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

API_DIR = Path(__file__).resolve().parent.parent / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from analytics.alerts import evaluate_persistent_alerts
from database import Base
from models_db import DoctorAlert
from routers.alerts import acknowledge_alert, create_alerts_for_history, create_or_get_open_alert


def _nightly_rows(
    user_id: str,
    *,
    start: date = date(2026, 1, 1),
    scores: list[float],
    risk_levels: list[str] | None = None,
    event_rates: list[float] | None = None,
) -> list[dict]:
    rows = []
    risk_levels = risk_levels or ["LOW"] * len(scores)
    event_rates = event_rates or [0.003] * len(scores)
    for idx, score in enumerate(scores):
        rows.append(
            {
                "user_id": user_id,
                "session_id": f"{user_id}_{idx + 1:03d}",
                "date": start + timedelta(days=idx),
                "sleep_score": score,
                "risk_level": risk_levels[idx],
                "event_rate": event_rates[idx],
            }
        )
    return rows


def test_sustained_decline_patient_creates_expected_high_alert():
    rows = _nightly_rows(
        "U034",
        scores=[82, 78, 44, 46, 42, 39, 41],
        risk_levels=["LOW", "LOW", "HIGH", "HIGH", "HIGH", "HIGH", "HIGH"],
        event_rates=[0.004, 0.006, 0.028, 0.032, 0.035, 0.031, 0.034],
    )

    alerts = evaluate_persistent_alerts(rows)
    alert_types = {alert["alert_type"] for alert in alerts}

    assert "persistent_high_risk" in alert_types
    assert "persistent_low_sleep_score" in alert_types
    high_alert = next(alert for alert in alerts if alert["alert_type"] == "persistent_high_risk")
    assert high_alert["severity"] == "HIGH"
    assert high_alert["patient_id"] == "U034"
    assert high_alert["evidence"]["consecutive_nights"] >= 3
    assert "risk_level == HIGH" in high_alert["evidence"]["rule"]


def test_single_bad_night_does_not_create_alert():
    rows = _nightly_rows(
        "CONTROL",
        scores=[86, 88, 42, 87, 90, 84, 89],
        risk_levels=["LOW", "LOW", "HIGH", "LOW", "LOW", "LOW", "LOW"],
        event_rates=[0.003, 0.004, 0.040, 0.005, 0.004, 0.003, 0.004],
    )

    assert evaluate_persistent_alerts(rows) == []


def test_acknowledge_flips_status_to_acknowledged():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    try:
        alert = create_or_get_open_alert(
            db,
            {
                "patient_id": "U034",
                "session_id": "U034_007",
                "alert_type": "persistent_high_risk",
                "severity": "HIGH",
                "reason": "Risk level was HIGH for at least 3 consecutive nights.",
                "evidence": {"dates": ["2026-01-05", "2026-01-06", "2026-01-07"]},
            },
        )

        response = acknowledge_alert(alert.id, db)
        stored = db.query(DoctorAlert).filter(DoctorAlert.id == alert.id).one()

        assert response["status"] == "ACKNOWLEDGED"
        assert stored.status == "ACKNOWLEDGED"
        assert stored.acknowledged_at is not None
        assert json.loads(stored.evidence_json)["dates"] == [
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
        ]
    finally:
        db.close()


def test_create_alerts_for_history_persists_alert_once():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    try:
        rows = _nightly_rows(
            "U034",
            scores=[82, 78, 64, 61, 58, 55, 52],
            risk_levels=["LOW", "LOW", "LOW", "LOW", "HIGH", "HIGH", "HIGH"],
        )

        first = create_alerts_for_history(db, rows)
        second = create_alerts_for_history(db, rows)

        assert len(first) == 1
        assert first[0].severity == "HIGH"
        assert first[0].status == "OPEN"
        assert len(second) == 1
        assert second[0].id == first[0].id
        assert db.query(DoctorAlert).count() == 1
    finally:
        db.close()
