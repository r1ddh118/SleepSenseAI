"""Deterministic sleep quality score (0–100) and Spark column wrapper.

DISCLAIMER: This is an academic/analytics score computed from wearable-derived
or self-reported sleep metrics. It is NOT clinically validated and does NOT
constitute a medical diagnosis or clinical sleep quality assessment.

Score weights:
  Sleep efficiency        25%
  Sleep duration          20%
  Deep sleep (N3)         15%
  REM sleep               15%
  Low wake fragmentation  10%
  HR stability            10%
  Movement stability       5%
"""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType

DISCLAIMER = (
    "This sleep score is an academic analytics metric derived from wearable or "
    "self-reported data. It is NOT clinically validated and does NOT constitute "
    "a medical diagnosis. Consult a qualified healthcare professional for clinical assessment."
)

# Optimal reference values
_OPT = {
    "sleep_efficiency": 0.90,
    "sleep_duration_hours": 8.0,
    "n3_fraction": 0.20,
    "rem_fraction": 0.22,
    "wake_fraction": 0.05,       # ideal low wake
    "hr_std": 3.0,               # ideal low variability
    "movement_std": 0.10,        # ideal low movement
}

# Score weights
_WEIGHTS = {
    "efficiency":   0.25,
    "duration":     0.20,
    "deep_sleep":   0.15,
    "rem":          0.15,
    "fragmentation":0.10,
    "hr_stability": 0.10,
    "movement":     0.05,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def calculate_sleep_score(metrics: dict[str, Any]) -> dict[str, Any]:
    """Compute a deterministic 0–100 sleep score from a metrics dict.

    Parameters
    ----------
    metrics : dict
        Must contain: sleep_efficiency, sleep_duration_hours, n3_fraction,
        rem_fraction, wake_fraction. Optional: hr_std, movement_std.

    Returns
    -------
    dict with keys: score (float), category (str), component_scores (dict),
                    disclaimer (str).
    """
    eff = float(metrics.get("sleep_efficiency", 0.85))
    dur = float(metrics.get("sleep_duration_hours", 7.0))
    n3  = float(metrics.get("n3_fraction", 0.15))
    rem = float(metrics.get("rem_fraction", 0.18))
    wk  = float(metrics.get("wake_fraction", 0.10))
    hr_std  = float(metrics.get("hr_std", 5.0))
    mov_std = float(metrics.get("movement_std", 0.2))

    # Per-component scores (0–1)
    s_eff  = _clamp(eff / _OPT["sleep_efficiency"])
    # Duration: optimal at 7–9 h; penalise both under and over
    if dur >= 7.0 and dur <= 9.0:
        s_dur = 1.0
    elif dur < 7.0:
        s_dur = _clamp(dur / 7.0)
    else:
        s_dur = _clamp(1.0 - (dur - 9.0) / 3.0)
    s_n3   = _clamp(n3 / _OPT["n3_fraction"])
    s_rem  = _clamp(rem / _OPT["rem_fraction"])
    s_frag = _clamp(1.0 - (wk / 0.30))   # 0% wake → 1.0; 30%+ → 0
    # HR stability: lower std → higher score; optimal ≤3, max penalised at ≥15
    s_hr   = _clamp(1.0 - max(0.0, hr_std - _OPT["hr_std"]) / 12.0)
    # Movement: lower std → higher score; optimal ≤0.1, penalised at ≥0.6
    s_mov  = _clamp(1.0 - max(0.0, mov_std - _OPT["movement_std"]) / 0.5)

    weighted = (
        s_eff  * _WEIGHTS["efficiency"]
        + s_dur  * _WEIGHTS["duration"]
        + s_n3   * _WEIGHTS["deep_sleep"]
        + s_rem  * _WEIGHTS["rem"]
        + s_frag * _WEIGHTS["fragmentation"]
        + s_hr   * _WEIGHTS["hr_stability"]
        + s_mov  * _WEIGHTS["movement"]
    )
    score = round(weighted * 100, 1)

    if score >= 80:
        category = "Excellent"
    elif score >= 65:
        category = "Good"
    elif score >= 50:
        category = "Fair"
    elif score >= 35:
        category = "Poor"
    else:
        category = "Very Poor"

    return {
        "score": score,
        "category": category,
        "component_scores": {
            "efficiency":    round(s_eff * 100, 1),
            "duration":      round(s_dur * 100, 1),
            "deep_sleep":    round(s_n3  * 100, 1),
            "rem":           round(s_rem * 100, 1),
            "fragmentation": round(s_frag * 100, 1),
            "hr_stability":  round(s_hr  * 100, 1),
            "movement":      round(s_mov  * 100, 1),
        },
        "disclaimer": DISCLAIMER,
    }


def calculate_sleep_score_column(df: DataFrame) -> DataFrame:
    """Add sleep_score and sleep_category columns to a nightly metrics DataFrame.

    This is the Spark path: uses column expressions (no Python UDF) for
    the weighted formula so computation stays distributed.
    """
    eff = F.coalesce(F.col("sleep_efficiency"), F.lit(0.85))
    dur = F.coalesce(F.col("sleep_duration_hours"), F.lit(7.0))
    n3  = F.coalesce(F.col("n3_fraction"), F.lit(0.15))
    rem = F.coalesce(F.col("rem_fraction"), F.lit(0.18))
    wk  = F.coalesce(F.col("wake_fraction"), F.lit(0.10))
    hr_std  = F.coalesce(F.col("hr_std"), F.lit(5.0))
    mov_std = F.coalesce(F.col("movement_std"), F.lit(0.2))

    def clamp_col(c: F.Column) -> F.Column:
        return F.greatest(F.lit(0.0), F.least(F.lit(1.0), c))

    s_eff  = clamp_col(eff / 0.90)
    s_dur  = clamp_col(
        F.when((dur >= 7.0) & (dur <= 9.0), F.lit(1.0))
        .when(dur < 7.0, dur / 7.0)
        .otherwise(1.0 - F.greatest(dur - 9.0, F.lit(0.0)) / 3.0)
    )
    s_n3   = clamp_col(n3 / 0.20)
    s_rem  = clamp_col(rem / 0.22)
    s_frag = clamp_col(1.0 - (wk / 0.30))
    s_hr   = clamp_col(1.0 - F.greatest(hr_std - 3.0, F.lit(0.0)) / 12.0)
    s_mov  = clamp_col(1.0 - F.greatest(mov_std - 0.10, F.lit(0.0)) / 0.5)

    score_col = (
        s_eff  * 0.25
        + s_dur  * 0.20
        + s_n3   * 0.15
        + s_rem  * 0.15
        + s_frag * 0.10
        + s_hr   * 0.10
        + s_mov  * 0.05
    ) * 100.0

    category_col = (
        F.when(score_col >= 80, "Excellent")
        .when(score_col >= 65, "Good")
        .when(score_col >= 50, "Fair")
        .when(score_col >= 35, "Poor")
        .otherwise("Very Poor")
    )

    return (
        df
        .withColumn("sleep_score", F.round(score_col, 1).cast(DoubleType()))
        .withColumn("sleep_category", category_col.cast(StringType()))
    )
