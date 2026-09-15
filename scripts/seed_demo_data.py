"""Seed U034 with 7 nights of progressively declining sleep quality for demo/testing.

Seeds the DB with SleepAnalytics rows for user U034 spanning 7 consecutive nights
with worsening metrics — should trigger a doctor alert upon evaluation.

Run: python scripts/seed_demo_data.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.database import SessionLocal, init_db

init_db()
db = SessionLocal()

USER_ID = "U034"
BASE_DATE = datetime(2025, 9, 1)

# Declining profile over 7 nights
NIGHTS = [
    {"sleep_score": 65.0, "risk_level": "LOW",      "wake_fraction": 0.10, "n3_fraction": 0.18, "rem_fraction": 0.20, "event_rate": 0.01, "sleep_efficiency": 0.90},
    {"sleep_score": 60.0, "risk_level": "LOW",      "wake_fraction": 0.12, "n3_fraction": 0.16, "rem_fraction": 0.18, "event_rate": 0.015, "sleep_efficiency": 0.87},
    {"sleep_score": 55.0, "risk_level": "MODERATE", "wake_fraction": 0.16, "n3_fraction": 0.13, "rem_fraction": 0.15, "event_rate": 0.025, "sleep_efficiency": 0.83},
    {"sleep_score": 48.0, "risk_level": "MODERATE", "wake_fraction": 0.20, "n3_fraction": 0.10, "rem_fraction": 0.13, "event_rate": 0.035, "sleep_efficiency": 0.78},
    {"sleep_score": 42.0, "risk_level": "HIGH",     "wake_fraction": 0.27, "n3_fraction": 0.07, "rem_fraction": 0.10, "event_rate": 0.055, "sleep_efficiency": 0.71},
    {"sleep_score": 38.0, "risk_level": "HIGH",     "wake_fraction": 0.30, "n3_fraction": 0.05, "rem_fraction": 0.09, "event_rate": 0.065, "sleep_efficiency": 0.68},
    {"sleep_score": 35.0, "risk_level": "HIGH",     "wake_fraction": 0.33, "n3_fraction": 0.04, "rem_fraction": 0.08, "event_rate": 0.075, "sleep_efficiency": 0.64},
]

print(f"Seeding U034 with {len(NIGHTS)} declining sleep nights...")

try:
    from api.models_db import SleepAnalytics, ManualSleepSession, DoctorAlert

    for i, night_data in enumerate(NIGHTS):
        date_str = (BASE_DATE + timedelta(days=i)).strftime("%Y-%m-%d")
        session_id = f"{USER_ID}-SEED-N{i+1:02d}"

        # Create ManualSleepSession
        ms = ManualSleepSession(
            session_id=session_id,
            user_str_id=USER_ID,
            date=date_str,
            bed_time="23:00",
            sleep_onset="23:15",
            wake_time="06:30",
            sleep_duration_hours=7.0 - i * 0.2,
            awakenings=2 + i,
            stress_level=5.0 + i * 0.5,
            status="COMPLETE",
        )
        db.add(ms)
        db.flush()

        score_7d = sum(n["sleep_score"] for n in NIGHTS[max(0, i-6):i+1]) / min(i+1, 7)

        analytics = SleepAnalytics(
            manual_session_id=ms.id,
            user_str_id=USER_ID,
            session_id=session_id,
            date=date_str,
            sleep_score=night_data["sleep_score"],
            sleep_category="Poor" if night_data["sleep_score"] < 50 else "Fair",
            sleep_efficiency=night_data["sleep_efficiency"],
            sleep_duration_hours=7.0 - i * 0.2,
            n3_fraction=night_data["n3_fraction"],
            rem_fraction=night_data["rem_fraction"],
            wake_fraction=night_data["wake_fraction"],
            avg_hr=65.0 + i * 1.5,
            hr_std=5.0 + i * 0.5,
            event_rate=night_data["event_rate"],
            sleep_score_7d_avg=score_7d,
            sleep_score_14d_avg=score_7d,
            duration_7d_avg=7.0 - i * 0.15,
            risk_level=night_data["risk_level"],
            risk_json=json.dumps({
                "overall_risk_level": night_data["risk_level"],
                "risk_flags": [],
                "evidence": [f"Auto-seeded declining night {i+1}"],
            }),
        )
        db.add(analytics)
        print(f"  Night {i+1} ({date_str}): score={night_data['sleep_score']}, risk={night_data['risk_level']}")

    # Evaluate alert for the full 7-night sequence
    from analytics.alerts import evaluate_alert
    recent_nights = [
        {"date": n_data["sleep_score"], "sleep_score": n_data["sleep_score"],
         "risk_level": n_data["risk_level"], "wake_fraction": n_data["wake_fraction"],
         "event_rate": n_data["event_rate"]}
        for n_data in NIGHTS
    ]
    alert_result = evaluate_alert(recent_nights)

    if alert_result["should_alert"]:
        alert = DoctorAlert(
            patient_str_id=USER_ID,
            session_id=f"{USER_ID}-SEED-N07",
            severity=alert_result["severity"],
            reason=alert_result["reasons"][0] if alert_result["reasons"] else "Declining sleep quality",
            evidence_json=json.dumps(alert_result["evidence_json"]),
            status="OPEN",
        )
        db.add(alert)
        print(f"\n✅ Doctor alert created: {alert_result['severity']}")
        for reason in alert_result["reasons"]:
            print(f"   - {reason}")

    db.commit()
    print(f"\n✅ Seeding complete for user {USER_ID}")

except Exception as e:
    db.rollback()
    print(f"❌ Error: {e}")
    raise
finally:
    db.close()
