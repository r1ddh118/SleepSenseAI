"""Analytics router — GET analytics, risk, recommendations for a session."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from database import get_db
from models_db import DoctorAlert, ManualSleepSession, SleepAnalytics, User
from schemas import SleepAnalyticsOut, UserSleepTrendOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["analytics"])


def _get_analytics_or_404(session_id: str, db: DBSession) -> SleepAnalytics:
    row = db.query(SleepAnalytics).filter(SleepAnalytics.session_id == session_id).first()
    if not row:
        raise HTTPException(
            404,
            detail=f"Analytics for session '{session_id}' not found. "
                   "The Spark pipeline may still be processing.",
        )
    return row


@router.get("/{session_id}/analytics", response_model=SleepAnalyticsOut)
def get_session_analytics(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return Spark-computed analytics for a session.

    Returns 404 with PROCESSING hint if Celery job hasn't completed yet.

    DISCLAIMER: sleep_score is an academic analytics metric — NOT clinically validated.
    """
    row = _get_analytics_or_404(session_id, db)
    risk_json = None
    if row.risk_json:
        try:
            risk_json = json.loads(row.risk_json)
        except Exception:
            pass
    recommendations = None
    if row.recommendations_json:
        try:
            recommendations = json.loads(row.recommendations_json)
        except Exception:
            pass

    return SleepAnalyticsOut(
        session_id=row.session_id or session_id,
        date=row.date,
        sleep_score=row.sleep_score,
        sleep_category=row.sleep_category,
        sleep_efficiency=row.sleep_efficiency,
        sleep_duration_hours=row.sleep_duration_hours,
        n3_fraction=row.n3_fraction,
        rem_fraction=row.rem_fraction,
        wake_fraction=row.wake_fraction,
        avg_hr=row.avg_hr,
        hr_std=row.hr_std,
        event_rate=row.event_rate,
        sleep_score_7d_avg=row.sleep_score_7d_avg,
        sleep_score_14d_avg=row.sleep_score_14d_avg,
        duration_7d_avg=row.duration_7d_avg,
        risk_level=row.risk_level,
        risk_json=risk_json,
        recommendations=recommendations,
    )


@router.get("/{session_id}/risk")
def get_session_risk(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return risk screening results.

    DISCLAIMER: Risk levels are SCREENING INDICATORS only — not a medical diagnosis.
    """
    row = _get_analytics_or_404(session_id, db)
    risk_data = {}
    if row.risk_json:
        try:
            risk_data = json.loads(row.risk_json)
        except Exception:
            pass

    return {
        "session_id": session_id,
        "risk_level": row.risk_level,
        "risk_assessment": risk_data,
        "disclaimer": (
            "SCREENING INDICATOR ONLY — NOT A MEDICAL DIAGNOSIS. "
            "These risk indicators are derived from analytics models. "
            "A qualified healthcare professional must perform clinical interpretation."
        ),
    }


@router.get("/{session_id}/recommendations")
def get_session_recommendations(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return personalised sleep recommendations for a session."""
    row = _get_analytics_or_404(session_id, db)
    recs = []
    if row.recommendations_json:
        try:
            recs = json.loads(row.recommendations_json)
        except Exception:
            pass

    return {
        "session_id": session_id,
        "recommendations": recs,
        "disclaimer": (
            "Recommendations are based on analytics patterns and are not medical advice."
        ),
    }
