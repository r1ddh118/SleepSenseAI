from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def add_sleep_score(df: DataFrame) -> DataFrame:
    """Add an explainable 0-100 sleep score to nightly metrics."""
    efficiency_penalty = F.greatest(F.lit(0.0), F.lit(85.0) - F.col("sleep_efficiency")) * F.lit(0.70)
    wake_penalty = F.col("sleep_stage_pct_W") * F.lit(0.25)
    deep_penalty = F.greatest(F.lit(0.0), F.lit(15.0) - F.col("sleep_stage_pct_N3")) * F.lit(0.80)
    rem_penalty = F.greatest(F.lit(0.0), F.lit(18.0) - F.col("sleep_stage_pct_R")) * F.lit(0.50)
    event_rate = F.col("total_event_count") / F.greatest(F.col("observation_count"), F.lit(1))
    event_penalty = F.least(event_rate * F.lit(260.0), F.lit(22.0))
    spo2_penalty = (
        F.greatest(F.lit(0.0), F.lit(94.0) - F.col("avg_spo2")) * F.lit(2.0)
        + F.greatest(F.lit(0.0), F.lit(90.0) - F.col("min_spo2")) * F.lit(1.5)
    )
    lifestyle_penalty = (
        F.greatest(F.lit(0.0), F.col("stress_level") - F.lit(4)) * F.lit(1.3)
        + F.col("caffeine") / F.lit(90.0)
        + F.col("screen_time") / F.lit(140.0)
        + F.col("nap_minutes") / F.lit(80.0)
        - F.least(F.col("exercise_minutes") / F.lit(120.0), F.lit(1.8))
    )

    raw_score = (
        F.lit(100.0)
        - efficiency_penalty
        - wake_penalty
        - deep_penalty
        - rem_penalty
        - event_penalty
        - spo2_penalty
        - lifestyle_penalty
    )
    score = F.round(F.least(F.lit(100.0), F.greatest(F.lit(0.0), raw_score)), 1)

    return (
        df.withColumn("sleep_score", score)
        .withColumn(
            "sleep_category",
            F.when(F.col("sleep_score") >= 85, F.lit("EXCELLENT"))
            .when(F.col("sleep_score") >= 70, F.lit("GOOD"))
            .when(F.col("sleep_score") >= 55, F.lit("FAIR"))
            .otherwise(F.lit("POOR")),
        )
    )
