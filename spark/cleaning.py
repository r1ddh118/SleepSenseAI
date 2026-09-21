from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from spark.schemas import SLEEP_STAGES


def clean_sleep_data(df: DataFrame) -> DataFrame:
    """Dedupe, validate, and enrich raw observation-level sleep data."""
    lifestyle_defaults = {
        "caffeine": 0,
        "screen_time": 0,
        "exercise_minutes": 0,
        "stress_level": 5,
        "nap_minutes": 0,
        "awakenings": 0,
        "event_count": 0,
    }

    return (
        df.dropDuplicates(["user_id", "session_id", "timestamp"])
        .filter(F.col("user_id").isNotNull())
        .filter(F.col("session_id").isNotNull())
        .filter(F.col("timestamp").isNotNull())
        .filter(F.col("date").isNotNull())
        .filter(F.col("heart_rate").between(45.0, 130.0))
        .filter(F.col("sleep_stage").isin(*SLEEP_STAGES))
        .fillna(lifestyle_defaults)
        .fillna({"spo2": 95.0})
        .withColumn(
            "movement_magnitude",
            F.sqrt(
                F.pow(F.coalesce(F.col("acc_x"), F.lit(0.0)), F.lit(2.0))
                + F.pow(F.coalesce(F.col("acc_y"), F.lit(0.0)), F.lit(2.0))
                + F.pow(F.coalesce(F.col("acc_z"), F.lit(0.0)), F.lit(2.0))
            ),
        )
    )
