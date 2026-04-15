"""
Evidence-based sleep health recommendations from one feature row (dict).
Intended for use after prediction (api/tasks.py) and for offline tooling.
"""

from __future__ import annotations

from typing import Any

THRESHOLDS = {
    "N3_low": 0.10,
    "event_rate_high": 0.05,
    "HR_mean_high": 75.0,
    "EDA_std_high": 0.5,
    "REM_low": 0.15,
    "wake_high": 0.15,
}


def generate_recommendations(features: dict[str, Any]) -> list[dict[str, str]]:
    """
    Returns [{"code": str, "message": str, "severity": str}, ...]
    severity: ok | info | warning | critical
    """
    recs: list[dict[str, str]] = []

    def add(code: str, message: str, severity: str = "info") -> None:
        recs.append({"code": code, "message": message, "severity": severity})

    n3 = float(features.get("sleep_stage_pct_N3", 1.0) or 0.0)
    if n3 < THRESHOLDS["N3_low"]:
        add(
            "low_deep_sleep",
            "Deep sleep (N3) was below 10%. Consider reducing evening caffeine (after 2pm) "
            "and maintaining a consistent sleep schedule.",
            "warning",
        )

    if float(features.get("event_rate", 0) or 0) > THRESHOLDS["event_rate_high"]:
        add(
            "elevated_apnea_rate",
            "Apnea event rate is elevated. A sleep clinic referral for PSG confirmation is recommended.",
            "critical",
        )

    if float(features.get("HR_mean", 0) or 0) > THRESHOLDS["HR_mean_high"]:
        add(
            "high_nocturnal_hr",
            "Resting heart rate during sleep was above 75 bpm. Evening breathing exercises "
            "or a 10-minute wind-down routine may help.",
            "info",
        )

    if float(features.get("EDA_std", 0) or 0) > THRESHOLDS["EDA_std_high"]:
        add(
            "high_arousal",
            "Electrodermal activity variability was high, indicating frequent arousal. "
            "Review bedroom temperature and noise exposure.",
            "warning",
        )

    rem = float(features.get("sleep_stage_pct_R", 1.0) or 0.0)
    if rem < THRESHOLDS["REM_low"]:
        add(
            "low_rem",
            "REM sleep was below 15%. Alcohol within 3 hours of bed is a common REM suppressant.",
            "info",
        )

    wake = float(features.get("sleep_stage_pct_W", 0) or 0.0)
    if wake > THRESHOLDS["wake_high"]:
        add(
            "high_wake",
            "More than 15% of the night was spent awake. Sleep restriction therapy "
            "or CBT-I may be beneficial.",
            "warning",
        )

    if not recs:
        add("normal", "Sleep metrics are within normal ranges. Keep up the good sleep habits!", "ok")

    return recs
