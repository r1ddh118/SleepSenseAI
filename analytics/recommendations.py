"""Evidence-based sleep health recommendations.

Refactored from advanced/recommendations.py with an expanded signature that
accepts separate sleep, risk, lifestyle, and longitudinal metrics dicts.
Every recommendation references the specific metric that triggered it.
No generic advice is generated unless all metrics are within normal ranges.
"""

from __future__ import annotations

from typing import Any

THRESHOLDS = {
    "n3_low":              0.12,
    "n3_very_low":         0.08,
    "rem_low":             0.16,
    "event_rate_high":     0.05,
    "event_rate_moderate": 0.02,
    "hr_mean_high":        75.0,
    "hr_std_high":         8.0,
    "wake_high":           0.25,
    "wake_moderate":       0.15,
    "screen_time_high":    60.0,   # minutes within 2h of bed
    "caffeine_high":       200.0,  # mg after 2pm
    "stress_high":         7.0,    # out of 10
    "sleep_score_low":     50.0,
    "score_decline_7d":   -10.0,   # 7d avg vs current decline
    "efficiency_low":      0.80,
    "duration_short":      6.5,    # hours
    "bedtime_var_high":    1.0,    # hours
}


def generate_recommendations(
    sleep_metrics: dict[str, Any],
    risk_metrics: dict[str, Any] | None = None,
    lifestyle_metrics: dict[str, Any] | None = None,
    longitudinal_metrics: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Generate personalised sleep recommendations from multiple metric sources.

    Each recommendation references the exact metric value that triggered it.

    Parameters
    ----------
    sleep_metrics : nightly aggregated sleep data (from Spark analytics).
    risk_metrics : optional risk flags from condition_risk.assess_all_risks().
    lifestyle_metrics : optional caffeine, screen_time, stress, exercise, nap values.
    longitudinal_metrics : optional 7d/14d trend columns.

    Returns
    -------
    List of dicts: {area, code, message, severity, triggered_by}
    """
    recs: list[dict[str, str]] = []
    risk_metrics = risk_metrics or {}
    lifestyle_metrics = lifestyle_metrics or sleep_metrics  # fallback: use sleep_metrics
    longitudinal_metrics = longitudinal_metrics or {}

    def add(
        area: str,
        code: str,
        message: str,
        severity: str,
        triggered_by: str,
    ) -> None:
        recs.append({
            "area": area,
            "code": code,
            "message": message,
            "severity": severity,
            "triggered_by": triggered_by,
        })

    # ── Deep Sleep (N3) ──────────────────────────────────────────────────────
    n3 = float(sleep_metrics.get("n3_fraction", 1.0) or 0.15)
    if n3 < THRESHOLDS["n3_very_low"]:
        add(
            "deep_sleep", "critically_low_n3",
            f"Deep sleep (N3) was {n3*100:.0f}% — critically below the 8% floor. "
            "Eliminate alcohol and sedatives before bed (both suppress N3), "
            "maintain consistent wake times, and avoid vigorous exercise after 7pm.",
            "critical",
            f"n3_fraction={n3:.3f} (threshold <{THRESHOLDS['n3_very_low']})",
        )
    elif n3 < THRESHOLDS["n3_low"]:
        add(
            "deep_sleep", "low_n3",
            f"Deep sleep (N3) was {n3*100:.0f}% (target ≥12%). "
            "Consider reducing caffeine intake after 2pm and keeping a consistent "
            "sleep schedule to improve slow-wave sleep.",
            "warning",
            f"n3_fraction={n3:.3f} (threshold <{THRESHOLDS['n3_low']})",
        )

    # ── REM Sleep ─────────────────────────────────────────────────────────────
    rem = float(sleep_metrics.get("rem_fraction", 1.0) or 0.20)
    if rem < THRESHOLDS["rem_low"]:
        add(
            "rem_sleep", "low_rem",
            f"REM sleep was {rem*100:.0f}% (target ≥16%). "
            "Alcohol within 3 hours of bed is a common REM suppressant. "
            "Also review any medications that may suppress REM.",
            "warning",
            f"rem_fraction={rem:.3f} (threshold <{THRESHOLDS['rem_low']})",
        )

    # ── Sleep Fragmentation / Wake ────────────────────────────────────────────
    wake = float(sleep_metrics.get("wake_fraction", 0) or 0)
    if wake > THRESHOLDS["wake_high"]:
        add(
            "fragmentation", "high_fragmentation",
            f"You spent {wake*100:.0f}% of the night awake (threshold >25%). "
            "Cognitive Behavioural Therapy for Insomnia (CBT-I) or sleep restriction "
            "therapy may help consolidate sleep.",
            "critical",
            f"wake_fraction={wake:.3f} (threshold >{THRESHOLDS['wake_high']})",
        )
    elif wake > THRESHOLDS["wake_moderate"]:
        add(
            "fragmentation", "moderate_fragmentation",
            f"You spent {wake*100:.0f}% of the night awake (threshold >15%). "
            "Keep the bedroom cool, dark, and quiet. Avoid checking your phone if you wake.",
            "warning",
            f"wake_fraction={wake:.3f} (threshold >{THRESHOLDS['wake_moderate']})",
        )

    # ── Breathing Events ─────────────────────────────────────────────────────
    event_rate = float(sleep_metrics.get("event_rate", 0) or 0)
    if event_rate > THRESHOLDS["event_rate_high"]:
        add(
            "breathing", "elevated_event_rate",
            f"Breathing-event rate was {event_rate:.4f} events/observation "
            f"(threshold >{THRESHOLDS['event_rate_high']}). "
            "A clinical referral for polysomnography (PSG) is recommended to rule out "
            "sleep-disordered breathing.",
            "critical",
            f"event_rate={event_rate:.4f}",
        )
    elif event_rate > THRESHOLDS["event_rate_moderate"]:
        add(
            "breathing", "borderline_event_rate",
            f"Borderline breathing-event rate: {event_rate:.4f} events/obs. "
            "Avoid sleeping on your back if possible; consider a follow-up recording.",
            "warning",
            f"event_rate={event_rate:.4f}",
        )

    # ── Heart Rate ────────────────────────────────────────────────────────────
    avg_hr = float(sleep_metrics.get("avg_hr", 60) or 60)
    if avg_hr > THRESHOLDS["hr_mean_high"]:
        add(
            "heart_rate", "high_nocturnal_hr",
            f"Average nocturnal heart rate was {avg_hr:.0f} bpm "
            f"(threshold >{THRESHOLDS['hr_mean_high']} bpm). "
            "A 10-minute pre-sleep breathing routine (4-7-8 breathing) may lower resting HR.",
            "info",
            f"avg_hr={avg_hr:.1f}",
        )

    hr_std = float(sleep_metrics.get("hr_std", 0) or 0)
    if hr_std > THRESHOLDS["hr_std_high"]:
        add(
            "heart_rate", "high_hr_variability",
            f"High nocturnal HR variability (std={hr_std:.1f} bpm, threshold >{THRESHOLDS['hr_std_high']}). "
            "Elevated variability may indicate frequent arousals or autonomic stress.",
            "warning",
            f"hr_std={hr_std:.1f}",
        )

    # ── Lifestyle — Screen Time ───────────────────────────────────────────────
    screen_time = float(lifestyle_metrics.get("screen_time", 0) or 0)
    if screen_time > THRESHOLDS["screen_time_high"]:
        add(
            "lifestyle", "high_screen_time",
            f"Screen time was {screen_time:.0f} min near bedtime "
            f"(threshold >{THRESHOLDS['screen_time_high']} min). "
            "Blue-light exposure suppresses melatonin. Use night-mode or "
            "avoid screens for 60–90 min before sleep.",
            "warning",
            f"screen_time={screen_time:.0f} min",
        )

    # ── Lifestyle — Caffeine ──────────────────────────────────────────────────
    caffeine = float(lifestyle_metrics.get("caffeine", 0) or 0)
    if caffeine > THRESHOLDS["caffeine_high"]:
        add(
            "lifestyle", "high_caffeine",
            f"Caffeine intake was {caffeine:.0f} mg (threshold >{THRESHOLDS['caffeine_high']} mg). "
            "Caffeine has a half-life of ~5h; avoid intake after 2pm for better sleep onset.",
            "warning",
            f"caffeine={caffeine:.0f} mg",
        )

    # ── Lifestyle — Stress ───────────────────────────────────────────────────
    stress = float(lifestyle_metrics.get("stress_level", 5) or 5)
    if stress > THRESHOLDS["stress_high"]:
        add(
            "lifestyle", "high_stress",
            f"Self-reported stress level was {stress:.0f}/10 "
            f"(threshold >{THRESHOLDS['stress_high']}). "
            "High pre-sleep stress elevates cortisol and delays sleep onset. "
            "Try mindfulness, progressive muscle relaxation, or journaling before bed.",
            "warning",
            f"stress_level={stress:.0f}",
        )

    # ── Longitudinal — Declining Trend ───────────────────────────────────────
    score = float(sleep_metrics.get("sleep_score", 70) or 70)
    score_7d_avg = float(longitudinal_metrics.get("sleep_score_7d_avg", score) or score)
    decline = score - score_7d_avg
    if decline < THRESHOLDS["score_decline_7d"]:
        add(
            "trend", "declining_sleep_score",
            f"Your sleep score has declined by {abs(decline):.0f} points vs your 7-day average "
            f"({score_7d_avg:.0f} → {score:.0f}). Review recent changes in schedule, stress, "
            "or lifestyle factors above.",
            "warning",
            f"sleep_score={score:.0f}, sleep_score_7d_avg={score_7d_avg:.0f}",
        )

    # ── No issues found ───────────────────────────────────────────────────────
    if not recs:
        add(
            "general", "normal",
            "All sleep metrics are within normal ranges for this session. "
            "Keep up the consistent sleep habits — regularity is key to long-term sleep health!",
            "ok",
            "all metrics within normal ranges",
        )

    return recs
