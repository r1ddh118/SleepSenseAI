"""Compatibility wrapper for recommendation rules.

The active implementation lives in `analytics.recommendations` and requires
separate sleep, risk, lifestyle, and longitudinal metric dictionaries.
"""

from __future__ import annotations

from typing import Any

from analytics.recommendations import generate_recommendations as _generate_recommendations


def generate_recommendations(features: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt an old single-row feature dict to the new metric-triggered API."""
    sleep_metrics = {
        "sleep_efficiency": features.get("sleep_efficiency"),
        "sleep_duration_hours": features.get("sleep_duration_hours"),
        "n3_fraction": features.get("n3_fraction", features.get("sleep_stage_pct_N3")),
        "rem_fraction": features.get("rem_fraction", features.get("sleep_stage_pct_R")),
        "wake_fraction": features.get("wake_fraction", features.get("sleep_stage_pct_W")),
    }
    risk_metrics = {
        "event_rate": features.get("event_rate"),
        "hr_std": features.get("hr_std", features.get("HR_std")),
        "movement_std": features.get("movement_std"),
    }
    lifestyle_metrics = {
        "screen_time": features.get("screen_time"),
        "stress_level": features.get("stress_level"),
        "caffeine": features.get("caffeine"),
    }
    longitudinal_metrics = {
        "sleep_score_7d_trend": features.get("sleep_score_7d_trend"),
        "wake_7d_trend": features.get("wake_7d_trend"),
    }
    return _generate_recommendations(
        sleep_metrics,
        risk_metrics,
        lifestyle_metrics,
        longitudinal_metrics,
    )
