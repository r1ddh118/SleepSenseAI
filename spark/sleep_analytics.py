from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from spark.schemas import SLEEP_STAGES


def nightly_metrics(df: DataFrame) -> DataFrame:
    """Aggregate observation-level rows into one nightly analytics row."""
    stage_count_exprs = [
        F.sum(F.when(F.col("sleep_stage") == stage, F.lit(1)).otherwise(F.lit(0))).alias(
            f"{stage.lower()}_count"
        )
        for stage in SLEEP_STAGES
    ]

    aggregated = df.groupBy("user_id", "session_id", "date").agg(
        F.count(F.lit(1)).alias("observation_count"),
        F.avg("heart_rate").alias("avg_heart_rate"),
        F.min("heart_rate").alias("min_heart_rate"),
        F.max("heart_rate").alias("max_heart_rate"),
        F.stddev_samp("heart_rate").alias("stddev_heart_rate"),
        F.avg("movement_magnitude").alias("avg_movement_magnitude"),
        F.sum("event_count").alias("total_event_count"),
        F.avg("spo2").alias("avg_spo2"),
        F.min("spo2").alias("min_spo2"),
        F.max("caffeine").alias("caffeine"),
        F.max("screen_time").alias("screen_time"),
        F.max("exercise_minutes").alias("exercise_minutes"),
        F.max("stress_level").alias("stress_level"),
        F.max("nap_minutes").alias("nap_minutes"),
        F.max("awakenings").alias("awakenings"),
        *stage_count_exprs,
    )

    with_percentages = aggregated
    for stage in SLEEP_STAGES:
        lower = stage.lower()
        with_percentages = with_percentages.withColumn(
            f"sleep_stage_pct_{stage}",
            F.when(
                F.col("observation_count") > 0,
                F.col(f"{lower}_count") * F.lit(100.0) / F.col("observation_count"),
            ).otherwise(F.lit(0.0)),
        )

    return (
        with_percentages.withColumn(
            "sleep_efficiency",
            F.when(
                F.col("observation_count") > 0,
                (F.col("observation_count") - F.col("w_count"))
                * F.lit(100.0)
                / F.col("observation_count"),
            ).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "stage_pct_total",
            sum(F.col(f"sleep_stage_pct_{stage}") for stage in SLEEP_STAGES),
        )
        .orderBy("user_id", "date", "session_id")
    )
