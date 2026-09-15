from __future__ import annotations

from typing import Any, Mapping


def _value(metrics: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_value(metrics: Mapping[str, Any], key: str) -> float | None:
    if key not in metrics or metrics.get(key) is None:
        return None
    try:
        return float(metrics[key])
    except (TypeError, ValueError):
        return None


def _fraction(metrics: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = _value(metrics, key, default)
    if value > 1.0:
        return value / 100.0
    return value


def _optional_fraction(metrics: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _optional_value(metrics, key)
        if value is None:
            continue
        if value > 1.0:
            return value / 100.0
        return value
    return None


def _add(
    recommendations: list[dict[str, Any]],
    *,
    code: str,
    area: str,
    severity: str,
    metric: str,
    value: float,
    threshold: str,
    message: str,
) -> None:
    recommendations.append(
        {
            "code": code,
            "area": area,
            "severity": severity,
            "trigger": {
                "metric": metric,
                "value": round(value, 4),
                "threshold": threshold,
            },
            "message": message,
        }
    )


def generate_recommendations(
    sleep_metrics: Mapping[str, Any],
    risk_metrics: Mapping[str, Any],
    lifestyle_metrics: Mapping[str, Any],
    longitudinal_metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Generate metric-triggered sleep recommendations.

    Every returned recommendation references the exact metric that triggered it.
    This is an academic analytics aid, not clinical advice or a diagnosis.
    """
    recs: list[dict[str, Any]] = []

    n3 = _optional_fraction(sleep_metrics, "n3_fraction", "sleep_stage_pct_N3")
    if n3 is not None and n3 < 0.12:
        _add(
            recs,
            code="low_n3_sleep",
            area="deep_sleep",
            severity="warning" if n3 >= 0.08 else "critical",
            metric="n3_fraction",
            value=n3,
            threshold="< 0.12",
            message=f"n3_fraction was {n3:.0%}, below the 12% analytics threshold; prioritize a consistent wind-down window and avoid late intense stimulation.",
        )

    rem = _optional_fraction(sleep_metrics, "rem_fraction", "sleep_stage_pct_R")
    if rem is not None and rem < 0.15:
        _add(
            recs,
            code="low_rem_sleep",
            area="rem_sleep",
            severity="info" if rem >= 0.10 else "warning",
            metric="rem_fraction",
            value=rem,
            threshold="< 0.15",
            message=f"rem_fraction was {rem:.0%}, below the 15% analytics threshold; review late alcohol, irregular timing, or sleep truncation if present.",
        )

    wake = _optional_fraction(sleep_metrics, "wake_fraction", "sleep_stage_pct_W")
    if wake is not None and wake > 0.18:
        _add(
            recs,
            code="high_wake_fraction",
            area="fragmentation",
            severity="warning" if wake < 0.28 else "critical",
            metric="wake_fraction",
            value=wake,
            threshold="> 0.18",
            message=f"wake_fraction was {wake:.0%}, above the 18% analytics threshold; focus on reducing awakenings and reviewing sleep timing consistency.",
        )

    efficiency = _optional_fraction(sleep_metrics, "sleep_efficiency")
    if efficiency is not None and efficiency < 0.80:
        _add(
            recs,
            code="low_sleep_efficiency",
            area="efficiency",
            severity="warning" if efficiency >= 0.70 else "critical",
            metric="sleep_efficiency",
            value=efficiency,
            threshold="< 0.80",
            message=f"sleep_efficiency was {efficiency:.0%}, below the 80% analytics threshold; check whether bed time is exceeding actual sleep opportunity.",
        )

    duration = _optional_value(sleep_metrics, "sleep_duration_hours")
    if duration is not None and duration < 6.5:
        _add(
            recs,
            code="short_sleep_duration",
            area="duration",
            severity="warning" if duration >= 5.5 else "critical",
            metric="sleep_duration_hours",
            value=duration,
            threshold="< 6.5",
            message=f"sleep_duration_hours was {duration:.1f}, below the 6.5 hour analytics threshold; extend sleep opportunity before optimizing smaller habits.",
        )

    event_rate = _optional_value(risk_metrics, "event_rate")
    if event_rate is not None and event_rate > 0.025:
        _add(
            recs,
            code="elevated_event_rate",
            area="breathing_events",
            severity="warning" if event_rate < 0.04 else "critical",
            metric="event_rate",
            value=event_rate,
            threshold="> 0.025",
            message=f"event_rate was {event_rate:.3f}, above the 0.025 analytics threshold; track persistence and consider clinician review if this repeats.",
        )

    hr_std = _optional_value(risk_metrics, "hr_std")
    if hr_std is not None and hr_std > 8.0:
        _add(
            recs,
            code="high_hr_variability",
            area="hr_stability",
            severity="info" if hr_std < 12.0 else "warning",
            metric="hr_std",
            value=hr_std,
            threshold="> 8.0",
            message=f"hr_std was {hr_std:.1f}, above the 8 bpm analytics threshold; review stress, late exercise, or fragmented sleep on this night.",
        )

    movement_std = _optional_value(risk_metrics, "movement_std")
    if movement_std is not None and movement_std > 0.16:
        _add(
            recs,
            code="high_movement_variability",
            area="movement_stability",
            severity="info" if movement_std < 0.25 else "warning",
            metric="movement_std",
            value=movement_std,
            threshold="> 0.16",
            message=f"movement_std was {movement_std:.2f}, above the 0.16 analytics threshold; check whether awakenings or restlessness drove the night.",
        )

    screen_time = _optional_value(lifestyle_metrics, "screen_time")
    if screen_time is not None and screen_time > 120:
        _add(
            recs,
            code="high_screen_time",
            area="screen_time",
            severity="info" if screen_time < 180 else "warning",
            metric="screen_time",
            value=screen_time,
            threshold="> 120",
            message=f"screen_time was {screen_time:.0f} minutes, above the 120 minute analytics threshold; reduce late screen exposure on similar nights.",
        )

    stress = _optional_value(lifestyle_metrics, "stress_level")
    if stress is not None and stress > 6:
        _add(
            recs,
            code="high_stress",
            area="stress",
            severity="info" if stress < 8 else "warning",
            metric="stress_level",
            value=stress,
            threshold="> 6",
            message=f"stress_level was {stress:.0f}/10, above the analytics threshold of 6; use a wind-down routine and compare against calmer nights.",
        )

    caffeine = _optional_value(lifestyle_metrics, "caffeine")
    if caffeine is not None and caffeine > 200:
        _add(
            recs,
            code="high_caffeine",
            area="caffeine",
            severity="info" if caffeine < 300 else "warning",
            metric="caffeine",
            value=caffeine,
            threshold="> 200",
            message=f"caffeine was {caffeine:.0f} mg, above the 200 mg analytics threshold; compare deep sleep and awakenings on lower-caffeine days.",
        )

    score_trend = _optional_value(longitudinal_metrics, "sleep_score_7d_trend")
    if score_trend is not None and score_trend < -5:
        _add(
            recs,
            code="declining_sleep_score",
            area="longitudinal_trend",
            severity="warning" if score_trend > -12 else "critical",
            metric="sleep_score_7d_trend",
            value=score_trend,
            threshold="< -5",
            message=f"sleep_score_7d_trend is {score_trend:.1f}, below the -5 point analytics threshold; review which recent metric changed most before adding new goals.",
        )

    wake_trend = _optional_value(longitudinal_metrics, "wake_7d_trend")
    if wake_trend is not None and wake_trend > 0.05:
        _add(
            recs,
            code="rising_wake_trend",
            area="wake_trend",
            severity="info" if wake_trend < 0.10 else "warning",
            metric="wake_7d_trend",
            value=wake_trend,
            threshold="> 0.05",
            message=f"wake_7d_trend is {wake_trend:.0%}, above the 5% analytics threshold; inspect timing, stress, and environment for this night.",
        )

    return recs
