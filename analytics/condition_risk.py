"""Sleep condition risk screening — rule-based engine mapping nightly metrics to risk levels.

DISCLAIMER: This module produces SCREENING INDICATORS only. It does NOT diagnose
any medical condition. Risk levels (LOW/MODERATE/HIGH) are derived from wearable or
self-reported data using heuristic rules and are NOT clinically validated.
All results must be interpreted by a qualified healthcare professional.

Four screening categories:
  1. Sleep-disordered breathing (SDB) indicator
  2. Insomnia-like pattern indicator
  3. Circadian irregularity indicator
  4. Sleep fragmentation indicator
"""

from __future__ import annotations

from typing import Any

RISK_LEVELS = ("LOW", "MODERATE", "HIGH")

MEDICAL_DISCLAIMER = (
    "SCREENING INDICATOR ONLY — NOT A MEDICAL DIAGNOSIS. "
    "These risk indicators are derived from analytics models applied to wearable "
    "or self-reported data. They are NOT clinically validated. A qualified healthcare "
    "professional must perform clinical interpretation before any treatment decision."
)


def _level(score: float) -> str:
    if score >= 2:
        return "HIGH"
    if score >= 1:
        return "MODERATE"
    return "LOW"


def assess_sleep_disordered_breathing(m: dict[str, Any]) -> dict[str, Any]:
    """Assess SDB (e.g., apnea-like) risk from event rate and SpO2."""
    reasons: list[str] = []
    score = 0.0

    event_rate = float(m.get("event_rate", 0) or 0)
    avg_spo2 = float(m.get("avg_spo2", 98) or 98)
    avg_hr = float(m.get("avg_hr", 65) or 65)
    hr_std = float(m.get("hr_std", 5) or 5)

    if event_rate > 0.05:
        reasons.append(f"Elevated breathing-event rate: {event_rate:.3f} events/obs (threshold >0.05)")
        score += 1.5
    elif event_rate > 0.02:
        reasons.append(f"Borderline breathing-event rate: {event_rate:.3f} events/obs")
        score += 0.5

    if avg_spo2 < 94:
        reasons.append(f"Low average SpO2: {avg_spo2:.1f}% (threshold <94%)")
        score += 1.5
    elif avg_spo2 < 96:
        reasons.append(f"Borderline SpO2: {avg_spo2:.1f}%")
        score += 0.5

    if hr_std > 10:
        reasons.append(f"High nocturnal HR variability: std={hr_std:.1f} bpm")
        score += 0.5

    return {
        "category": "sleep_disordered_breathing",
        "label": "Sleep-Disordered Breathing Indicator",
        "risk": _level(score),
        "score": score,
        "reasons": reasons,
        "confidence": "low" if not reasons else ("medium" if score < 2 else "medium"),
    }


def assess_insomnia_pattern(m: dict[str, Any]) -> dict[str, Any]:
    """Assess insomnia-like pattern from sleep efficiency, wake fraction, duration."""
    reasons: list[str] = []
    score = 0.0

    eff = float(m.get("sleep_efficiency", 0.85) or 0.85)
    wake_frac = float(m.get("wake_fraction", 0.10) or 0.10)
    duration = float(m.get("sleep_duration_hours", 7.0) or 7.0)
    awakenings = int(m.get("awakenings", 0) or 0)

    if eff < 0.70:
        reasons.append(f"Very low sleep efficiency: {eff*100:.0f}% (threshold <70%)")
        score += 1.5
    elif eff < 0.80:
        reasons.append(f"Below-normal sleep efficiency: {eff*100:.0f}% (threshold <80%)")
        score += 0.75

    if wake_frac > 0.25:
        reasons.append(f"High time awake: {wake_frac*100:.0f}% of night (threshold >25%)")
        score += 1.0
    elif wake_frac > 0.15:
        reasons.append(f"Elevated time awake: {wake_frac*100:.0f}% of night")
        score += 0.5

    if duration < 5.0:
        reasons.append(f"Very short sleep duration: {duration:.1f}h (threshold <5h)")
        score += 1.0
    elif duration < 6.5:
        reasons.append(f"Short sleep duration: {duration:.1f}h (threshold <6.5h)")
        score += 0.5

    if awakenings > 5:
        reasons.append(f"Frequent awakenings: {awakenings} (threshold >5)")
        score += 0.5

    return {
        "category": "insomnia_pattern",
        "label": "Insomnia-Like Pattern Indicator",
        "risk": _level(score),
        "score": score,
        "reasons": reasons,
        "confidence": "low" if not reasons else "medium",
    }


def assess_circadian_irregularity(m: dict[str, Any]) -> dict[str, Any]:
    """Assess circadian rhythm irregularity from bed/wake time variability."""
    reasons: list[str] = []
    score = 0.0

    bedtime_var = float(m.get("bedtime_variability", 0) or 0)
    wake_var = float(m.get("wake_time_variability", 0) or 0)
    dur_var = float(m.get("duration_variability", 0) or 0)
    nap_min = float(m.get("nap_minutes", 0) or 0)

    if bedtime_var > 1.5:
        reasons.append(f"High bedtime variability: ±{bedtime_var:.1f}h across recent nights (threshold >1.5h)")
        score += 1.5
    elif bedtime_var > 0.75:
        reasons.append(f"Moderate bedtime variability: ±{bedtime_var:.1f}h")
        score += 0.5

    if wake_var > 1.5:
        reasons.append(f"High wake-time variability: ±{wake_var:.1f}h (threshold >1.5h)")
        score += 1.0
    elif wake_var > 0.75:
        reasons.append(f"Moderate wake-time variability: ±{wake_var:.1f}h")
        score += 0.5

    if dur_var > 1.5:
        reasons.append(f"High sleep duration variability: ±{dur_var:.1f}h (threshold >1.5h)")
        score += 0.5

    if nap_min > 90:
        reasons.append(f"Long daytime nap: {nap_min:.0f} min (may disrupt circadian rhythm)")
        score += 0.5

    return {
        "category": "circadian_irregularity",
        "label": "Circadian Irregularity Indicator",
        "risk": _level(score),
        "score": score,
        "reasons": reasons,
        "confidence": "low" if not reasons else "medium",
    }


def assess_sleep_fragmentation(m: dict[str, Any]) -> dict[str, Any]:
    """Assess sleep fragmentation from wake fraction, N3/REM proportions, and movement."""
    reasons: list[str] = []
    score = 0.0

    n3_frac = float(m.get("n3_fraction", 0.15) or 0.15)
    rem_frac = float(m.get("rem_fraction", 0.20) or 0.20)
    wake_frac = float(m.get("wake_fraction", 0.10) or 0.10)
    avg_movement = float(m.get("avg_movement", 0.3) or 0.3)
    hr_std = float(m.get("hr_std", 5) or 5)

    if n3_frac < 0.08:
        reasons.append(f"Very low deep sleep (N3): {n3_frac*100:.0f}% (threshold <8%)")
        score += 1.0
    elif n3_frac < 0.12:
        reasons.append(f"Low deep sleep (N3): {n3_frac*100:.0f}% (threshold <12%)")
        score += 0.5

    if rem_frac < 0.12:
        reasons.append(f"Very low REM sleep: {rem_frac*100:.0f}% (threshold <12%)")
        score += 1.0
    elif rem_frac < 0.16:
        reasons.append(f"Low REM sleep: {rem_frac*100:.0f}% (threshold <16%)")
        score += 0.5

    if wake_frac > 0.25:
        reasons.append(f"High fragmentation: {wake_frac*100:.0f}% wake time (threshold >25%)")
        score += 1.0

    if avg_movement > 0.5:
        reasons.append(f"Elevated nocturnal movement: avg={avg_movement:.2f} (threshold >0.5)")
        score += 0.5

    if hr_std > 8:
        reasons.append(f"High HR variability: std={hr_std:.1f} bpm (threshold >8)")
        score += 0.5

    return {
        "category": "sleep_fragmentation",
        "label": "Sleep Fragmentation Indicator",
        "risk": _level(score),
        "score": score,
        "reasons": reasons,
        "confidence": "low" if not reasons else "medium",
    }


def assess_all_risks(metrics: dict[str, Any]) -> dict[str, Any]:
    """Run all four risk screeners and return a combined risk assessment.

    Parameters
    ----------
    metrics : dict
        Nightly aggregated metrics row (from Spark analytics, converted to dict).

    Returns
    -------
    dict with keys:
        overall_risk_level (str): highest risk level across all categories.
        risk_flags (list[dict]): per-category risk results.
        evidence (list[str]): all evidence reasons.
        disclaimer (str): mandatory medical disclaimer.
    """
    flags = [
        assess_sleep_disordered_breathing(metrics),
        assess_insomnia_pattern(metrics),
        assess_circadian_irregularity(metrics),
        assess_sleep_fragmentation(metrics),
    ]

    # Overall risk = highest across categories
    level_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
    overall = max(flags, key=lambda f: level_order[f["risk"]])["risk"]

    all_evidence = [r for f in flags for r in f["reasons"]]

    return {
        "overall_risk_level": overall,
        "risk_flags": flags,
        "evidence": all_evidence,
        "disclaimer": MEDICAL_DISCLAIMER,
    }
