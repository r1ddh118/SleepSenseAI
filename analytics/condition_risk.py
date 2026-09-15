from __future__ import annotations

from typing import Any, Mapping


DISCLAIMER = (
    "Academic risk screening only; not clinically validated and not a medical diagnosis."
)

RISK_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def _float(features: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = features.get(key, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fraction(value: float) -> float:
    if value > 1.0:
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value))


def _risk_flag(condition: str, risk: str, confidence: float, reasons: list[str]) -> dict[str, Any]:
    return {
        "condition": condition,
        "risk": risk,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "reasons": reasons,
        "disclaimer": DISCLAIMER,
    }


def screen_condition_risks(features: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Map nightly Spark risk features to non-diagnostic academic risk flags.

    This rule engine is for academic analytics and product explainability only.
    It is not clinically validated, is not a medical diagnosis, and must not be
    used to diagnose or rule out any sleep disorder.
    """
    event_rate = _float(features, "event_rate")
    wake_fraction = _fraction(_float(features, "wake_fraction"))
    n3_fraction = _fraction(_float(features, "n3_fraction"))
    rem_fraction = _fraction(_float(features, "rem_fraction"))
    sleep_efficiency = _fraction(_float(features, "sleep_efficiency"))
    avg_hr = _float(features, "avg_hr")
    hr_std = _float(features, "hr_std")
    movement_std = _float(features, "movement_std")
    awakenings = _float(features, "awakenings")
    avg_spo2 = _float(features, "avg_spo2", 95.0)
    min_spo2 = _float(features, "min_spo2", 95.0)
    bedtime_variability = _float(features, "bedtime_variability")
    wake_time_variability = _float(features, "wake_time_variability")
    duration_variability = _float(features, "duration_variability")
    duration = _float(features, "sleep_duration_hours")

    flags: list[dict[str, Any]] = []

    breathing_reasons = []
    if event_rate >= 0.025:
        breathing_reasons.append(f"event_rate={event_rate:.3f} is elevated")
    if avg_spo2 < 92:
        breathing_reasons.append(f"avg_spo2={avg_spo2:.1f} is low")
    if min_spo2 < 88:
        breathing_reasons.append(f"min_spo2={min_spo2:.1f} shows oxygen dips")
    if breathing_reasons:
        high_markers = int(event_rate >= 0.035) + int(avg_spo2 < 90) + int(min_spo2 < 86)
        risk = "HIGH" if high_markers >= 1 and len(breathing_reasons) >= 2 else "MODERATE"
        flags.append(
            _risk_flag(
                "Sleep-disordered breathing pattern",
                risk,
                0.78 if risk == "HIGH" else 0.62,
                breathing_reasons,
            )
        )

    insomnia_reasons = []
    if sleep_efficiency < 0.72:
        insomnia_reasons.append(f"sleep_efficiency={sleep_efficiency:.2f} is low")
    if duration and duration < 6.0:
        insomnia_reasons.append(f"sleep_duration_hours={duration:.1f} is short")
    if wake_fraction >= 0.22:
        insomnia_reasons.append(f"wake_fraction={wake_fraction:.2f} is high")
    if bedtime_variability >= 75:
        insomnia_reasons.append(f"bedtime_variability={bedtime_variability:.0f} minutes is high")
    if len(insomnia_reasons) >= 2:
        risk = "HIGH" if sleep_efficiency < 0.65 or wake_fraction >= 0.30 else "MODERATE"
        flags.append(
            _risk_flag(
                "Insomnia-like pattern",
                risk,
                0.76 if risk == "HIGH" else 0.60,
                insomnia_reasons,
            )
        )

    circadian_reasons = []
    if bedtime_variability >= 60:
        circadian_reasons.append(f"bedtime_variability={bedtime_variability:.0f} minutes")
    if wake_time_variability >= 60:
        circadian_reasons.append(f"wake_time_variability={wake_time_variability:.0f} minutes")
    if duration_variability >= 1.25:
        circadian_reasons.append(f"duration_variability={duration_variability:.2f} hours")
    if len(circadian_reasons) >= 2:
        risk = "HIGH" if bedtime_variability >= 120 or wake_time_variability >= 120 else "MODERATE"
        flags.append(
            _risk_flag(
                "Circadian irregularity",
                risk,
                0.72 if risk == "HIGH" else 0.58,
                circadian_reasons,
            )
        )

    fragmentation_reasons = []
    if wake_fraction >= 0.18:
        fragmentation_reasons.append(f"wake_fraction={wake_fraction:.2f} is elevated")
    if awakenings >= 5:
        fragmentation_reasons.append(f"awakenings={awakenings:.0f} is elevated")
    if movement_std >= 0.16:
        fragmentation_reasons.append(f"movement_std={movement_std:.2f} is elevated")
    if hr_std >= 8:
        fragmentation_reasons.append(f"hr_std={hr_std:.1f} is elevated")
    if sleep_efficiency < 0.80:
        fragmentation_reasons.append(f"sleep_efficiency={sleep_efficiency:.2f} is reduced")
    if len(fragmentation_reasons) >= 2:
        risk = "HIGH" if wake_fraction >= 0.28 or awakenings >= 8 else "MODERATE"
        flags.append(
            _risk_flag(
                "Sleep fragmentation",
                risk,
                0.80 if risk == "HIGH" else 0.65,
                fragmentation_reasons,
            )
        )

    architecture_reasons = []
    if n3_fraction < 0.08:
        architecture_reasons.append(f"n3_fraction={n3_fraction:.2f} is low")
    if rem_fraction < 0.12:
        architecture_reasons.append(f"rem_fraction={rem_fraction:.2f} is low")
    if avg_hr >= 82:
        architecture_reasons.append(f"avg_hr={avg_hr:.1f} is elevated")
    if len(architecture_reasons) >= 2:
        flags.append(
            _risk_flag(
                "Sleep architecture strain",
                "MODERATE",
                0.55,
                architecture_reasons,
            )
        )

    return sorted(flags, key=lambda item: RISK_ORDER[item["risk"]], reverse=True)
