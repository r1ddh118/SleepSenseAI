"""Nightly sleep metrics — one aggregated row per (user_id, session_id, date).

Uses Spark groupBy + agg — no Python loops, no pandas.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def nightly_metrics(df: DataFrame) -> DataFrame:
    """Compute per-night aggregate metrics from cleaned observation-level data.

    Returns one row per (user_id, session_id, date) with:
    - Average/std/min/max heart rate
    - Average movement magnitude
    - Sleep stage fractions (N1, N2, N3, REM, Wake)
    - Sleep efficiency (1 - wake_fraction)
    - Estimated sleep duration in hours
    - Breathing event rate (events per observation)
    """
    agg = (
        df.groupBy("user_id", "session_id", "date")
        .agg(
            F.avg("heart_rate").alias("avg_hr"),
            F.stddev("heart_rate").alias("hr_std"),
            F.min("heart_rate").alias("min_hr"),
            F.max("heart_rate").alias("max_hr"),
            F.avg("movement_magnitude").alias("avg_movement"),
            F.stddev("movement_magnitude").alias("movement_std"),
            F.count("*").alias("observations"),
            # Sleep stage counts
            F.sum(F.when(F.col("sleep_stage") == "N3", 1).otherwise(0)).alias("n3_count"),
            F.sum(F.when(F.col("sleep_stage") == "R", 1).otherwise(0)).alias("rem_count"),
            F.sum(F.when(F.col("sleep_stage") == "W", 1).otherwise(0)).alias("wake_count"),
            F.sum(F.when(F.col("sleep_stage") == "N1", 1).otherwise(0)).alias("n1_count"),
            F.sum(F.when(F.col("sleep_stage") == "N2", 1).otherwise(0)).alias("n2_count"),
            # Lifestyle aggregates (per-night session values — take first non-null)
            F.first(F.col("caffeine"), ignorenulls=True).alias("caffeine"),
            F.first(F.col("screen_time"), ignorenulls=True).alias("screen_time"),
            F.first(F.col("exercise_minutes"), ignorenulls=True).alias("exercise_minutes"),
            F.first(F.col("stress_level"), ignorenulls=True).alias("stress_level"),
            F.first(F.col("nap_minutes"), ignorenulls=True).alias("nap_minutes"),
            F.first(F.col("awakenings"), ignorenulls=True).alias("awakenings"),
            F.sum(F.col("event_count")).alias("total_events"),
            F.avg("spo2").alias("avg_spo2"),
            # Bed/wake times (session-level)
            F.first(F.col("bed_time"), ignorenulls=True).alias("bed_time"),
            F.first(F.col("sleep_onset"), ignorenulls=True).alias("sleep_onset"),
            F.first(F.col("wake_time"), ignorenulls=True).alias("wake_time"),
            # Timestamp bounds for duration estimation
            F.min("timestamp").alias("first_obs"),
            F.max("timestamp").alias("last_obs"),
        )
    )

    total = F.col("observations")

    return (
        agg
        .withColumn("n3_fraction", F.col("n3_count") / total)
        .withColumn("rem_fraction", F.col("rem_count") / total)
        .withColumn("wake_fraction", F.col("wake_count") / total)
        .withColumn("n1_fraction", F.col("n1_count") / total)
        .withColumn("n2_fraction", F.col("n2_count") / total)
        .withColumn("sleep_efficiency", 1.0 - F.col("wake_fraction"))
        # Estimate duration: (last_obs - first_obs) in hours, minimum 0
        .withColumn(
            "sleep_duration_hours",
            F.greatest(
                (F.col("last_obs").cast("long") - F.col("first_obs").cast("long")) / 3600.0,
                F.lit(0.0),
            ),
        )
        # Event rate: breathing events per observation
        .withColumn(
            "event_rate",
            F.when(total > 0, F.col("total_events") / total).otherwise(0.0),
        )
    )
