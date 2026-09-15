from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping


OPEN = "OPEN"
ACKNOWLEDGED = "ACKNOWLEDGED"
RESOLVED = "RESOLVED"
VALID_STATUSES = {OPEN, ACKNOWLEDGED, RESOLVED}


def _float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_value(row: Mapping[str, Any]) -> date:
    value = row.get("date")
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _risk(row: Mapping[str, Any]) -> str:
    return str(row.get("risk_level") or "").upper()


def _session_id(row: Mapping[str, Any]) -> str:
    return str(row.get("session_id") or "")


def _consecutive_suffix(rows: list[Mapping[str, Any]], predicate) -> list[Mapping[str, Any]]:
    streak: list[Mapping[str, Any]] = []
    for row in reversed(rows):
        if predicate(row):
            streak.append(row)
        else:
            break
    return list(reversed(streak))


def _base_alert(
    rows: list[Mapping[str, Any]],
    *,
    alert_type: str,
    severity: str,
    reason: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    latest = rows[-1]
    return {
        "patient_id": str(latest.get("user_id")),
        "session_id": _session_id(latest),
        "alert_type": alert_type,
        "severity": severity,
        "reason": reason,
        "evidence": evidence,
        "status": OPEN,
    }


def evaluate_persistent_alerts(nightly_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate persistence-based doctor alerts from user nightly analytics.

    Alerts are generated only for sustained patterns. A single noisy night must
    not create an alert.
    """
    rows = sorted(list(nightly_rows), key=_date_value)
    if not rows:
        return []

    alerts: list[dict[str, Any]] = []
    latest_7 = rows[-7:]
    high_streak = _consecutive_suffix(rows, lambda row: _risk(row) == "HIGH")
    if len(high_streak) >= 3:
        alerts.append(
            _base_alert(
                rows,
                alert_type="persistent_high_risk",
                severity="HIGH",
                reason="Risk level was HIGH for at least 3 consecutive nights.",
                evidence={
                    "rule": "risk_level == HIGH for >=3 consecutive nights",
                    "consecutive_nights": len(high_streak),
                    "dates": [str(_date_value(row)) for row in high_streak[-3:]],
                    "risk_levels": [_risk(row) for row in high_streak[-3:]],
                },
            )
        )

    low_score_rows = [row for row in latest_7 if _float(row, "sleep_score") < 50]
    if len(low_score_rows) >= 5:
        alerts.append(
            _base_alert(
                rows,
                alert_type="persistent_low_sleep_score",
                severity="HIGH",
                reason="Sleep score was below 50 on at least 5 of the last 7 nights.",
                evidence={
                    "rule": "sleep_score < 50 for >=5 of last 7 nights",
                    "matching_nights": len(low_score_rows),
                    "window_dates": [str(_date_value(row)) for row in latest_7],
                    "low_score_dates": [str(_date_value(row)) for row in low_score_rows],
                    "scores": [_float(row, "sleep_score") for row in latest_7],
                },
            )
        )

    elevated_event_rows = [row for row in latest_7 if _float(row, "event_rate") >= 0.025]
    event_streak = _consecutive_suffix(rows, lambda row: _float(row, "event_rate") >= 0.025)
    if len(elevated_event_rows) >= 4 or len(event_streak) >= 3:
        severity = "HIGH" if len(event_streak) >= 3 else "MODERATE"
        alerts.append(
            _base_alert(
                rows,
                alert_type="sustained_elevated_event_rate",
                severity=severity,
                reason="Event rate was elevated across multiple recent nights.",
                evidence={
                    "rule": "event_rate >= 0.025 for >=4 of last 7 nights or >=3 consecutive nights",
                    "matching_nights": len(elevated_event_rows),
                    "consecutive_nights": len(event_streak),
                    "event_rates": [_float(row, "event_rate") for row in latest_7],
                    "window_dates": [str(_date_value(row)) for row in latest_7],
                },
            )
        )

    return alerts


def strongest_alert(nightly_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-priority persistent alert for a nightly history."""
    alerts = evaluate_persistent_alerts(nightly_rows)
    if not alerts:
        return None
    severity_rank = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
    return sorted(alerts, key=lambda alert: severity_rank.get(alert["severity"], 0), reverse=True)[0]
