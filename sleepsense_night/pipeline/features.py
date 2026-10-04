"""
pipeline/features.py  –  Per-epoch feature engineering
======================================================

Adds rolling statistics, infers sleep stage (or uses device stage),
detects sleep onset, desaturation events, and wake bouts.

Stage inference hierarchy
--------------------------
1. ``device_stage`` when it contains a valid label.
2. When ``resp_roll_std`` is available (full sensor set):
   - WAKE: movement > threshold OR hr_rel > threshold
   - DEEP: hr_rel low AND resp_std low
   - REM: resp_std high AND hr_rel high
   - LIGHT: default
3. HR-only fallback (no respiration channel):
   - WAKE: movement > threshold OR hr_rel very high
   - DEEP: hr_rel very low
   - REM: hr_rel mildly elevated
   - LIGHT: default
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from sleepsense_night.config import (
    STAGE_THRESHOLDS as ST,
    ONSET_SLEEP_FRACTION,
    ONSET_WINDOW_MINUTES,
    DESAT_THRESHOLD_PCT,
    DESAT_BASELINE_MINUTES,
)


def add_features(df: DataFrame, cfg=None, step: int = 10) -> DataFrame:
    """Add rolling stats, sleep stage, onset, desat events, wake bouts.

    Parameters
    ----------
    df   : cleaned epoch DataFrame.
    cfg  : PipelineConfig (unused currently, kept for forward compat).
    step : sampling interval in seconds.
    """

    part = ["user_id", "night_date"]
    wo = Window.partitionBy(*part).orderBy("ts")

    # ── Rolling windows (centred 2.5 min) ─────────────────────────────
    half = max(1, int(2.5 * 60 / step / 2))
    wc = wo.rowsBetween(-half, half)

    df = (
        df
        .withColumn("hr_roll_mean",   F.avg("hr_bpm").over(wc))
        .withColumn("hr_roll_std",    F.stddev("hr_bpm").over(wc))
        .withColumn("mov_roll_mean",  F.avg("movement_g").over(wc))
    )

    # Respiration rolling std (only when resp_rate_bpm is present)
    has_resp = "resp_rate_bpm" in df.columns
    if has_resp:
        df = df.withColumn("resp_roll_std", F.stddev("resp_rate_bpm").over(wc))
    else:
        df = df.withColumn("resp_roll_std", F.lit(None).cast("double"))

    # SpO₂ rolling mean
    if "spo2_pct" in df.columns:
        df = df.withColumn("spo2_roll_mean", F.avg("spo2_pct").over(wc))
    else:
        df = df.withColumn("spo2_roll_mean", F.lit(None).cast("double"))

    # ── Nightly median HR and relative HR ────────────────────────────
    w_night = Window.partitionBy(*part)
    df = df.withColumn(
        "night_median_hr",
        F.percentile_approx("hr_bpm", 0.5).over(w_night),
    )
    df = df.withColumn(
        "hr_rel",
        F.col("hr_roll_mean") - F.col("night_median_hr"),
    )

    # ── Sleep-stage inference ─────────────────────────────────────────
    mov_roll_mean = F.col("mov_roll_mean")
    hr_rel        = F.col("hr_rel")
    resp_roll_std = F.col("resp_roll_std")
    hr_roll_mean  = F.col("hr_roll_mean")

    resp_available = resp_roll_std.isNotNull()

    # Full-sensor inference (respiration present)
    inferred_full = (
        F.when(
            (mov_roll_mean > ST["wake_movement"]) | (hr_rel > ST["wake_hr_rel"]),
            "W",
        )
        .when(
            resp_available &
            (hr_rel < ST["deep_hr_rel"]) &
            (resp_roll_std < ST["deep_resp_std"]),
            "DEEP",
        )
        .when(
            resp_available &
            (resp_roll_std > ST["rem_resp_std"]) &
            (hr_rel > ST["rem_hr_rel"]),
            "REM",
        )
        # HR-only fallbacks when resp is NULL for this epoch
        .when(~resp_available & (hr_rel < -4.0), "DEEP")
        .when(~resp_available & (hr_rel > 1.5),  "REM")
        .when(hr_roll_mean.isNotNull(), "LIGHT")
    )

    # Prefer the device-reported stage if available
    stage_device = None
    if "device_stage" in df.columns:
        stage_device = F.when(
            F.col("device_stage").isin("W", "LIGHT", "DEEP", "REM"),
            F.col("device_stage"),
        )

    df = df.withColumn(
        "stage",
        F.coalesce(stage_device, inferred_full) if stage_device is not None
        else inferred_full,
    )

    df = df.withColumn("is_sleep", (F.col("stage") != "W").cast("int"))

    # ── Sleep onset ───────────────────────────────────────────────────
    # First epoch where ≥90 % of the next 10 min is sleep
    onset_rows = max(1, int(ONSET_WINDOW_MINUTES * 60 / step))
    w_fwd = wo.rowsBetween(0, onset_rows)
    df = df.withColumn(
        "_fwd_sleep_frac",
        F.avg("is_sleep").over(w_fwd),
    )
    df = df.withColumn(
        "onset_candidate",
        (F.col("_fwd_sleep_frac") >= ONSET_SLEEP_FRACTION).cast("int"),
    )

    # ── Desaturation events ───────────────────────────────────────────
    if "spo2_pct" in df.columns:
        desat_rows = max(1, int(DESAT_BASELINE_MINUTES * 60 / step / 2))
        w_base = wo.rowsBetween(-desat_rows, desat_rows)
        df = df.withColumn(
            "spo2_baseline",
            F.max("spo2_pct").over(w_base),
        )
        df = df.withColumn(
            "desat_flag",
            (
                (F.col("spo2_baseline") - F.col("spo2_pct")) >= DESAT_THRESHOLD_PCT
            ).cast("int"),
        )
        df = df.withColumn(
            "desat_event_start",
            F.when(
                (F.col("desat_flag") == 1) &
                ((F.lag("desat_flag", 1).over(wo) != 1) |
                 F.lag("desat_flag", 1).over(wo).isNull()),
                F.lit(1),
            ).otherwise(F.lit(0)),
        )
    else:
        df = df.withColumn("spo2_baseline",    F.lit(None).cast("double"))
        df = df.withColumn("desat_flag",        F.lit(0).cast("int"))
        df = df.withColumn("desat_event_start", F.lit(0).cast("int"))

    # ── Wake/sleep run-length encoding (for events.py and nightly.py) ─
    # Step 1: mark boundary rows (change OR first row of partition)
    df = df.withColumn(
        "_chg",
        F.coalesce(
            (F.col("is_sleep") != F.lag("is_sleep").over(wo)).cast("int"),
            F.lit(1),
        ),
    )
    # Step 2: cumulative sum gives each run a unique id
    cum_w = wo.rowsBetween(Window.unboundedPreceding, 0)
    df = df.withColumn("run_id", F.sum("_chg").over(cum_w))

    # ── Stage run-length encoding (for events.py) ─────────────────────
    df = df.withColumn(
        "_stage_chg",
        F.coalesce(
            (F.col("stage") != F.lag("stage").over(wo)).cast("int"),
            F.lit(1),
        ),
    )
    df = df.withColumn("stage_run_id", F.sum("_stage_chg").over(cum_w))

    # Clean up helpers
    df = df.drop("_fwd_sleep_frac", "_chg", "_stage_chg")

    return df
