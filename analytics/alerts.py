"""Doctor alert evaluation — persistence-based rules.

A doctor alert is ONLY created when sleep issues persist across multiple nights.
A single bad night never triggers an alert (to avoid noise-driven false alarms).

Persistence thresholds:
  HIGH alert:  HIGH risk level for 3 consecutive nights  (OR)
               Sleep score <50 for 5 of the last 7 nights
  MODERATE alert: HIGH risk for 2 consecutive nights  (OR)
                  Sleep score <50 for 3 of last 7 nights  (OR)
                  Single night with wake_fraction >0.35 AND event_rate >0.05
"""

from __future__ import annotations

from typing import Any


def evaluate_alert(recent_nights: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate whether a doctor alert should be created.

    Parameters
    ----------
    recent_nights : list of nightly metric dicts, ordered oldest → newest.
                    Minimum recommended: 7 nights.

    Returns
    -------
    dict with keys:
        should_alert (bool): True if an alert should be created.
        severity (str): "HIGH", "MODERATE", or "NONE".
        reasons (list[str]): human-readable evidence strings.
        evidence_json (dict): structured evidence for DB storage.
    """
    if not recent_nights:
        return {"should_alert": False, "severity": "NONE", "reasons": [], "evidence_json": {}}

    reasons: list[str] = []
    severity = "NONE"

    last_3 = recent_nights[-3:]
    last_7 = recent_nights[-7:]

    # ── HIGH alert conditions ─────────────────────────────────────────────────
    # Condition 1: HIGH risk 3 consecutive nights
    high_3_consecutive = sum(
        1 for n in last_3 if str(n.get("risk_level", "")).upper() == "HIGH"
    )
    if high_3_consecutive == 3:
        reasons.append(
            f"HIGH sleep-condition risk indicator for 3 consecutive nights "
            f"(dates: {', '.join(str(n.get('date', '?')) for n in last_3)})"
        )
        severity = "HIGH"

    # Condition 2: Poor sleep score 5 of last 7 nights
    poor_score_count = sum(
        1 for n in last_7 if float(n.get("sleep_score", 100) or 100) < 50
    )
    if poor_score_count >= 5:
        scores = [round(float(n.get("sleep_score", 100) or 100), 1) for n in last_7]
        reasons.append(
            f"Persistently poor sleep quality: score <50 for {poor_score_count} of last 7 nights "
            f"(scores: {scores})"
        )
        severity = "HIGH"

    # ── MODERATE alert conditions ─────────────────────────────────────────────
    if severity == "NONE":
        # Condition 3: HIGH risk 2 consecutive nights
        if high_3_consecutive >= 2:
            reasons.append(
                f"HIGH risk for {high_3_consecutive} consecutive nights — monitoring required"
            )
            severity = "MODERATE"

        # Condition 4: Poor score 3 of 7 nights
        if poor_score_count >= 3:
            reasons.append(
                f"Below-average sleep quality (score <50) for {poor_score_count} of last 7 nights"
            )
            severity = "MODERATE"

        # Condition 5: Single night with both high wake AND high event rate
        latest = recent_nights[-1]
        wake_frac = float(latest.get("wake_fraction", 0) or 0)
        event_rate = float(latest.get("event_rate", 0) or 0)
        if wake_frac > 0.35 and event_rate > 0.05:
            reasons.append(
                f"Last night: very high wake fraction ({wake_frac*100:.0f}%) "
                f"combined with elevated breathing-event rate ({event_rate:.3f})"
            )
            severity = "MODERATE"

    # ── Single-night noise checks (should NOT produce HIGH) ──────────────────
    # These add information reasons only when alert is already MODERATE+
    latest = recent_nights[-1]
    wake_frac = float(latest.get("wake_fraction", 0) or 0)
    event_rate = float(latest.get("event_rate", 0) or 0)

    if severity != "NONE":
        if wake_frac > 0.25:
            reasons.append(
                f"Most recent night: high sleep fragmentation "
                f"(wake fraction = {wake_frac*100:.0f}%)"
            )
        if event_rate > 0.05:
            reasons.append(
                f"Most recent night: elevated breathing-event rate ({event_rate:.3f} events/obs)"
            )

    return {
        "should_alert": severity != "NONE",
        "severity": severity,
        "reasons": reasons,
        "evidence_json": {
            "high_risk_consecutive_3": high_3_consecutive,
            "poor_score_nights_in_7": poor_score_count,
            "latest_wake_fraction": float(latest.get("wake_fraction", 0) or 0),
            "latest_event_rate": float(latest.get("event_rate", 0) or 0),
            "latest_sleep_score": float(latest.get("sleep_score", 0) or 0),
            "nights_evaluated": len(recent_nights),
        },
    }


def get_alert_status_summary(recent_nights: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a brief status summary without creating an alert."""
    result = evaluate_alert(recent_nights)
    return {
        "alert_warranted": result["should_alert"],
        "severity": result["severity"],
        "reason_count": len(result["reasons"]),
        "top_reason": result["reasons"][0] if result["reasons"] else None,
    }
