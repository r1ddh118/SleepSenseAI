from __future__ import annotations

from typing import Any, Mapping


ACADEMIC_SCORE_DISCLAIMER = (
    "Academic analytics score only; not clinically validated and not a medical diagnosis."
)

WEIGHTS = {
    "efficiency": 0.25,
    "duration": 0.20,
    "deep_sleep": 0.15,
    "rem_sleep": 0.15,
    "wake_fragmentation": 0.10,
    "hr_stability": 0.10,
    "movement_stability": 0.05,
}


def _as_float(metrics: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _fraction(value: float) -> float:
    """Accept either 0-1 fractions or 0-100 percentages."""
    if value > 1.0:
        return _clamp(value / 100.0)
    return _clamp(value)


def _category(score: float) -> str:
    if score >= 85:
        return "EXCELLENT"
    if score >= 70:
        return "GOOD"
    if score >= 55:
        return "FAIR"
    return "POOR"


def calculate_sleep_score(nightly_metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate a deterministic academic/analytics sleep score.

    This 0-100 score is intended for academic analytics and product
    explainability only. It is not clinically validated, is not a medical
    diagnosis, and must not be presented as a disease screening result.
    """
    efficiency = _fraction(_as_float(nightly_metrics, "sleep_efficiency"))
    duration_hours = _as_float(nightly_metrics, "sleep_duration_hours")
    n3_fraction = _fraction(_as_float(nightly_metrics, "n3_fraction"))
    rem_fraction = _fraction(_as_float(nightly_metrics, "rem_fraction"))
    wake_fraction = _fraction(_as_float(nightly_metrics, "wake_fraction"))
    hr_std = max(0.0, _as_float(nightly_metrics, "hr_std"))
    movement_std = max(0.0, _as_float(nightly_metrics, "movement_std"))

    component_scores = {
        "efficiency": efficiency,
        "duration": _clamp(duration_hours / 8.0),
        "deep_sleep": _clamp(n3_fraction / 0.20),
        "rem_sleep": _clamp(rem_fraction / 0.22),
        "wake_fragmentation": _clamp(1.0 - wake_fraction / 0.25),
        "hr_stability": _clamp(1.0 - hr_std / 12.0),
        "movement_stability": _clamp(1.0 - movement_std / 0.60),
    }

    score = round(
        100.0
        * sum(component_scores[name] * weight for name, weight in WEIGHTS.items()),
        1,
    )

    return {
        "score": score,
        "category": _category(score),
        "score_type": "academic_analytics_sleep_score",
        "clinically_validated": False,
        "disclaimer": ACADEMIC_SCORE_DISCLAIMER,
        "metrics": {
            "inputs": {
                "sleep_efficiency": efficiency,
                "sleep_duration_hours": duration_hours,
                "n3_fraction": n3_fraction,
                "rem_fraction": rem_fraction,
                "wake_fraction": wake_fraction,
                "hr_std": hr_std,
                "movement_std": movement_std,
            },
            "component_scores": {key: round(value * 100.0, 1) for key, value in component_scores.items()},
            "weights": {key: int(value * 100) for key, value in WEIGHTS.items()},
        },
    }
