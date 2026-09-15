"""Reports router — JSON, CSV, HTML report generation and download."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session as DBSession

from auth import get_current_user
from config import settings
from database import get_db
from models_db import DoctorReport, SleepAnalytics, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["reports"])


@router.get("/{session_id}/report")
def get_session_report(
    session_id: str,
    format: str = "json",
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and return a sleep analytics report for a session.

    Formats: json (default), csv, html

    All formats include the mandatory disclaimer:
    'This report is an analytical screening tool and does not constitute a
     medical diagnosis. Clinical interpretation should be performed by a
     qualified healthcare professional.'
    """
    analytics = db.query(SleepAnalytics).filter(
        SleepAnalytics.session_id == session_id
    ).first()

    if not analytics:
        raise HTTPException(
            404,
            detail=f"No analytics found for session '{session_id}'. "
                   "Spark pipeline may still be processing.",
        )

    # Build metrics dict from DB row
    sleep_metrics: dict = {
        "session_id": analytics.session_id,
        "date": analytics.date,
        "sleep_score": analytics.sleep_score,
        "sleep_category": analytics.sleep_category,
        "sleep_efficiency": analytics.sleep_efficiency,
        "sleep_duration_hours": analytics.sleep_duration_hours,
        "n3_fraction": analytics.n3_fraction,
        "rem_fraction": analytics.rem_fraction,
        "wake_fraction": analytics.wake_fraction,
        "avg_hr": analytics.avg_hr,
        "hr_std": analytics.hr_std,
        "event_rate": analytics.event_rate,
        "sleep_score_7d_avg": analytics.sleep_score_7d_avg,
        "sleep_score_14d_avg": analytics.sleep_score_14d_avg,
        "duration_7d_avg": analytics.duration_7d_avg,
    }

    risk_assessment = {}
    if analytics.risk_json:
        try:
            risk_assessment = json.loads(analytics.risk_json)
        except Exception:
            pass

    recommendations = []
    if analytics.recommendations_json:
        try:
            recommendations = json.loads(analytics.recommendations_json)
        except Exception:
            pass

    from analytics.report_builder import (
        build_csv_report,
        build_html_report,
        build_json_report,
        save_report,
    )

    user_id = analytics.user_str_id or "unknown"
    fmt = format.lower()

    if fmt == "json":
        content = build_json_report(
            session_id, user_id, sleep_metrics,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
        )
        # Save to disk
        path = save_report("json", content, settings.reports_path, session_id)
        _save_report_db(db, user_id, session_id, path, "json")
        return PlainTextResponse(content, media_type="application/json")

    elif fmt == "csv":
        content = build_csv_report(
            session_id, user_id, sleep_metrics,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
        )
        path = save_report("csv", content, settings.reports_path, session_id)
        _save_report_db(db, user_id, session_id, path, "csv")
        return PlainTextResponse(content, media_type="text/csv")

    elif fmt == "html":
        content = build_html_report(
            session_id, user_id, sleep_metrics,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
        )
        path = save_report("html", content, settings.reports_path, session_id)
        _save_report_db(db, user_id, session_id, path, "html")
        return HTMLResponse(content)

    else:
        raise HTTPException(400, f"Unsupported format '{format}'. Use: json, csv, html")


def _save_report_db(
    db: DBSession, user_id: str, session_id: str, file_path: str, fmt: str
) -> None:
    try:
        report = DoctorReport(
            patient_str_id=user_id,
            session_id=session_id,
            file_path=file_path,
            format=fmt,
        )
        db.add(report)
        db.commit()
    except Exception as e:
        logger.warning("Could not save report to DB: %s", e)
