from __future__ import annotations

import json

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.window import Window

from analytics.condition_risk import screen_condition_risks


def _hhmm_minutes(column_name: str) -> F.Column:
    parts = F.split(F.col(column_name), ":")
    return parts.getItem(0).cast("int") * F.lit(60) + parts.getItem(1).cast("int")


def _risk_flags_json(
    event_rate,
    wake_fraction,
    n3_fraction,
    rem_fraction,
    sleep_efficiency,
    avg_hr,
    hr_std,
    movement_std,
    bedtime_variability,
    wake_time_variability,
    duration_variability,
    awakenings,
    avg_spo2,
    min_spo2,
    sleep_duration_hours,
):
    flags = screen_condition_risks(
        {
            "event_rate": event_rate,
            "wake_fraction": wake_fraction,
            "n3_fraction": n3_fraction,
            "rem_fraction": rem_fraction,
            "sleep_efficiency": sleep_efficiency,
            "avg_hr": avg_hr,
            "hr_std": hr_std,
            "movement_std": movement_std,
            "bedtime_variability": bedtime_variability,
            "wake_time_variability": wake_time_variability,
            "duration_variability": duration_variability,
            "awakenings": awakenings,
            "avg_spo2": avg_spo2,
            "min_spo2": min_spo2,
            "sleep_duration_hours": sleep_duration_hours,
        }
    )
    return json.dumps(flags, sort_keys=True)


def add_risk_features(df: DataFrame) -> DataFrame:
    """Add non-diagnostic nightly risk-screening features."""
    event_rate = F.col("total_event_count") / F.greatest(F.col("observation_count"), F.lit(1))
    wake_fraction = F.col("sleep_stage_pct_W") / F.lit(100.0)
    n3_fraction = F.col("sleep_stage_pct_N3") / F.lit(100.0)
    rem_fraction = F.col("sleep_stage_pct_R") / F.lit(100.0)
    sleep_efficiency = F.col("sleep_efficiency") / F.lit(100.0)
    bed_minutes = _hhmm_minutes("bed_time")
    wake_minutes = _hhmm_minutes("wake_time")
    normalized_bed_minutes = F.when(bed_minutes < 12 * 60, bed_minutes + 24 * 60).otherwise(bed_minutes)
    normalized_wake_minutes = F.when(wake_minutes < 18 * 60, wake_minutes + 24 * 60).otherwise(wake_minutes)
    sleep_duration_hours = (normalized_wake_minutes - normalized_bed_minutes) / F.lit(60.0)

    risk_score = (
        event_rate * F.lit(220.0)
        + wake_fraction * F.lit(28.0)
        + F.greatest(F.lit(0.0), F.lit(0.12) - n3_fraction) * F.lit(65.0)
        + F.greatest(F.lit(0.0), F.lit(0.15) - rem_fraction) * F.lit(35.0)
        + F.greatest(F.lit(0.0), F.lit(92.0) - F.col("avg_spo2")) * F.lit(3.5)
        + F.greatest(F.lit(0.0), F.lit(88.0) - F.col("min_spo2")) * F.lit(3.0)
        + F.greatest(F.lit(0.0), F.col("stddev_heart_rate") - F.lit(8.0)) * F.lit(1.3)
        + F.greatest(F.lit(0.0), F.col("awakenings") - F.lit(3)) * F.lit(2.2)
        + F.greatest(F.lit(0.0), F.lit(65.0) - F.col("sleep_score")) * F.lit(0.45)
    )

    trend_window = Window.partitionBy("user_id").orderBy("date").rowsBetween(-6, 0)
    flags_udf = F.udf(_risk_flags_json, StringType())

    risked = (
        df.withColumn("event_rate", F.round(event_rate, 5))
        .withColumn("wake_fraction", F.round(wake_fraction, 5))
        .withColumn("n3_fraction", F.round(n3_fraction, 5))
        .withColumn("deep_sleep_fraction", F.col("n3_fraction"))
        .withColumn("rem_fraction", F.round(rem_fraction, 5))
        .withColumn("sleep_efficiency_fraction", F.round(sleep_efficiency, 5))
        .withColumn("avg_hr", F.col("avg_heart_rate"))
        .withColumn("hr_std", F.coalesce(F.col("stddev_heart_rate"), F.lit(0.0)))
        .withColumn("movement_std", F.coalesce(F.col("stddev_movement_magnitude"), F.lit(0.0)))
        .withColumn("bedtime_minutes", normalized_bed_minutes)
        .withColumn("wake_time_minutes", normalized_wake_minutes)
        .withColumn("sleep_duration_hours", F.round(sleep_duration_hours, 3))
        .withColumn("bedtime_variability", F.round(F.coalesce(F.stddev_samp("bedtime_minutes").over(trend_window), F.lit(0.0)), 3))
        .withColumn("wake_time_variability", F.round(F.coalesce(F.stddev_samp("wake_time_minutes").over(trend_window), F.lit(0.0)), 3))
        .withColumn("duration_variability", F.round(F.coalesce(F.stddev_samp("sleep_duration_hours").over(trend_window), F.lit(0.0)), 3))
        .withColumn("risk_score", F.round(F.least(F.lit(100.0), F.greatest(F.lit(0.0), risk_score)), 1))
        .withColumn(
            "risk_level",
            F.when(F.col("risk_score") >= 45, F.lit("HIGH"))
            .when(F.col("risk_score") >= 25, F.lit("MODERATE"))
            .otherwise(F.lit("LOW")),
        )
    )

    return risked.withColumn(
        "risk_flags_json",
        flags_udf(
            "event_rate",
            "wake_fraction",
            "n3_fraction",
            "rem_fraction",
            "sleep_efficiency_fraction",
            "avg_hr",
            "hr_std",
            "movement_std",
            "bedtime_variability",
            "wake_time_variability",
            "duration_variability",
            "awakenings",
            "avg_spo2",
            "min_spo2",
            "sleep_duration_hours",
        ),
    )
