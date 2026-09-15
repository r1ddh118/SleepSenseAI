"""Spark cleaning — deduplication, null handling, validation, movement magnitude.

All operations are distributed DataFrame transformations — no Python row loops.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def clean_sleep_data(df: DataFrame) -> DataFrame:
    """Clean raw sleep observations.

    Steps:
    1. Drop exact duplicates on (user_id, session_id, timestamp).
    2. Filter impossible heart rate values (35–220 bpm).
    3. Compute movement_magnitude from accelerometer axes.
    4. Fill nulls in lifestyle features with sensible defaults.
    5. Derive 'date' column from timestamp if missing.
    6. Validate sleep_stage values; replace out-of-range with None.
    """
    valid_stages = ["W", "N1", "N2", "N3", "R"]

    return (
        df
        .dropDuplicates(["user_id", "session_id", "timestamp"])
        .filter(F.col("heart_rate").between(35, 220))
        # Compute movement magnitude from accelerometer vector
        .withColumn(
            "movement_magnitude",
            F.sqrt(
                F.pow(F.coalesce(F.col("acc_x"), F.lit(0.0)), 2)
                + F.pow(F.coalesce(F.col("acc_y"), F.lit(0.0)), 2)
                + F.pow(F.coalesce(F.col("acc_z"), F.lit(0.0)), 2)
            ),
        )
        # Fill lifestyle feature nulls
        .fillna({
            "exercise_minutes": 0.0,
            "screen_time": 0.0,
            "stress_level": 5.0,
            "caffeine": 0.0,
            "nap_minutes": 0.0,
            "awakenings": 0,
            "event_count": 0,
        })
        # Derive date from timestamp if not already present
        .withColumn(
            "date",
            F.when(
                F.col("date").isNull() | (F.col("date") == ""),
                F.date_format(F.col("timestamp"), "yyyy-MM-dd"),
            ).otherwise(F.col("date")),
        )
        # Validate sleep_stage — null out invalid values
        .withColumn(
            "sleep_stage",
            F.when(F.col("sleep_stage").isin(valid_stages), F.col("sleep_stage"))
            .otherwise(None),
        )
    )
