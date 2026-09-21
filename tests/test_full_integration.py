from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from database import Base
from models_db import DoctorAlert, SleepAnalytics
from routers.frontend_adapter import get_dashboard
from routers.reports import _build_report
from routers.sessions import create_manual_session, get_session_analytics
from schemas import ManualSleepSessionCreate
import database
import spark.cleaning
import spark.feature_engineering
import spark.ingestion
import spark.longitudinal
import spark.risk_analysis
import spark.sleep_analytics
import spark.sleep_score
import spark.spark_session
import tasks


class _FakeSpark:
    def stop(self):
        return None


class _FakeFrame:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def first(self):
        with self.path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        total = len(rows)
        stages = {stage: 0 for stage in ("W", "N1", "N2", "N3", "R")}
        event_count = 0
        heart_rates: list[float] = []
        movements: list[float] = []
        for row in rows:
            stages[row["sleep_stage"]] += 1
            event_count += int(float(row["event_count"]))
            heart_rates.append(float(row["heart_rate"]))
            movements.append(abs(float(row["acc_x"])) + abs(float(row["acc_y"])) + abs(float(row["acc_z"]) - 1.0))

        wake_fraction = stages["W"] / total
        n3_fraction = stages["N3"] / total
        rem_fraction = stages["R"] / total
        event_rate = event_count / total
        avg_hr = sum(heart_rates) / total
        hr_std = (sum((hr - avg_hr) ** 2 for hr in heart_rates) / total) ** 0.5
        movement_mean = sum(movements) / total
        movement_std = (sum((movement - movement_mean) ** 2 for movement in movements) / total) ** 0.5
        score = max(
            0.0,
            min(
                100.0,
                100.0
                - wake_fraction * 120.0
                - max(0.0, 0.18 - n3_fraction) * 100.0
                - max(0.0, 0.18 - rem_fraction) * 80.0
                - event_rate * 600.0,
            ),
        )
        risk_level = "HIGH" if wake_fraction >= 0.28 or event_rate >= 0.025 or score < 50 else "LOW"
        first = rows[0]
        metrics = {
            "user_id": first["user_id"],
            "session_id": first["session_id"],
            "date": first["date"],
            "sleep_score": score,
            "sleep_category": "Poor" if score < 50 else "Good",
            "sleep_efficiency": (1.0 - wake_fraction) * 100.0,
            "sleep_efficiency_fraction": 1.0 - wake_fraction,
            "sleep_duration_hours": 7.0 * (1.0 - wake_fraction),
            "wake_fraction": wake_fraction,
            "n1_fraction": stages["N1"] / total,
            "n2_fraction": stages["N2"] / total,
            "n3_fraction": n3_fraction,
            "rem_fraction": rem_fraction,
            "event_rate": event_rate,
            "avg_hr": avg_hr,
            "hr_std": hr_std,
            "movement_std": movement_std,
            "screen_time": int(first["screen_time"]),
            "stress_level": int(first["stress_level"]),
            "caffeine": int(first["caffeine"]),
            "exercise_minutes": int(first["exercise_minutes"]),
            "nap_minutes": int(first["nap_minutes"]),
            "awakenings": int(first["awakenings"]),
            "risk_score": 0.9 if risk_level == "HIGH" else 0.1,
            "risk_level": risk_level,
            "risk_flags_json": json.dumps(
                [
                    {
                        "condition": "Sleep fragmentation",
                        "risk": risk_level,
                        "confidence": 0.9 if risk_level == "HIGH" else 0.2,
                        "reasons": [f"wake_fraction={wake_fraction:.2f}", f"event_rate={event_rate:.3f}"],
                    }
                ]
                if risk_level == "HIGH"
                else []
            ),
            "sleep_score_7d_avg": score,
            "sleep_score_7d_trend": -5.0 if risk_level == "HIGH" else 0.0,
        }
        return SimpleNamespace(asDict=lambda recursive=True: metrics)


def _patch_spark(monkeypatch):
    monkeypatch.setattr(spark.spark_session, "create_spark_session", lambda *args, **kwargs: _FakeSpark())
    monkeypatch.setattr(spark.ingestion, "load_sleep_data", lambda spark, path: _FakeFrame(path))
    monkeypatch.setattr(spark.cleaning, "clean_sleep_data", lambda df: df)
    monkeypatch.setattr(spark.feature_engineering, "add_rolling_features", lambda df: df)
    monkeypatch.setattr(spark.sleep_analytics, "nightly_metrics", lambda df: df)
    monkeypatch.setattr(spark.sleep_score, "add_sleep_score", lambda df: df)
    monkeypatch.setattr(spark.risk_analysis, "add_risk_features", lambda df: df)
    monkeypatch.setattr(spark.longitudinal, "add_longitudinal_metrics", lambda df: df)


def test_manual_to_task_to_alert_report_and_dashboard_chain(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSession)
    monkeypatch.setattr(tasks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tasks.run_sleep_analytics, "delay", lambda session_id: SimpleNamespace(id=f"test-{session_id}"))
    _patch_spark(monkeypatch)

    db = TestingSession()
    try:
        session_ids: list[str] = []
        for day in range(1, 8):
            body = ManualSleepSessionCreate(
                user_id="U034",
                date=f"2026-09-{day:02d}",
                bed_time="23:30",
                sleep_onset="00:10",
                wake_time="06:20",
                wake_fraction=0.34 if day >= 3 else 0.08,
                n3_fraction=0.06 if day >= 3 else 0.21,
                rem_fraction=0.08 if day >= 3 else 0.22,
                heart_rate=76 if day >= 3 else 62,
                event_rate=0.04 if day >= 3 else 0.005,
                screen_time=180 if day >= 3 else 30,
                stress_level=8 if day >= 3 else 3,
                caffeine=2 if day >= 3 else 0,
                exercise_minutes=5 if day >= 3 else 35,
                awakenings=7 if day >= 3 else 1,
                notes="full integration test",
            )
            accepted = create_manual_session(body, db)
            session_ids.append(accepted.session_id)
            first_response = get_session_analytics(accepted.session_id, db)
            assert first_response["status"] == "PROCESSING"

            result = tasks.run_sleep_analytics.run(int(accepted.session_id))
            assert result["status"] == "COMPLETED"

        latest_session_id = session_ids[-1]
        completed = get_session_analytics(latest_session_id, db)
        assert completed["status"] == "COMPLETED"
        assert completed["sleep_score"] < 50
        assert completed["risk_level"] == "HIGH"
        assert completed["recommendations"]

        alerts = db.query(DoctorAlert).filter(DoctorAlert.patient_id == "U034").all()
        alert_types = {alert.alert_type for alert in alerts}
        assert "persistent_high_risk" in alert_types
        assert "persistent_low_sleep_score" in alert_types

        report = _build_report(db, latest_session_id)
        assert report["sections"]["sleep_summary"]["sleep_score"] == completed["sleep_score"]
        assert report["sections"]["risk_assessment"]["risk_level"] == "HIGH"
        assert report["sections"]["recommendations"]
        assert "not clinically validated" in report["sections"]["disclaimer"]["text"]

        dashboard = get_dashboard(db)
        dashboard_session = next(item for item in dashboard["sessions"] if item["id"] == completed["sid"])
        assert dashboard_session["riskLevel"] == "high"
        assert dashboard_session["features"]["sleep_score"] == completed["sleep_score"]

        assert db.query(SleepAnalytics).filter(SleepAnalytics.status == "COMPLETED").count() == 7
    finally:
        db.close()
