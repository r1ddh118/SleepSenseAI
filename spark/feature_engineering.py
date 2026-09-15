"""Spark feature engineering — rolling window features per session.

Uses PySpark Window functions partitioned by (user_id, session_id) ordered by timestamp.
No Python loops — all computation is distributed.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_rolling_features(df: DataFrame) -> DataFrame:
    """Add rolling statistics over a 6-observation window within each session.

    Window: 6 preceding rows → current row (i.e., last 6 observations including current).
    Partitioned by (user_id, session_id) so windows never cross session boundaries.
    """
    w = (
        Window.partitionBy("user_id", "session_id")
        .orderBy("timestamp")
        .rowsBetween(-5, 0)
    )

    return (
        df
        # Heart rate rolling stats
        .withColumn("hr_rolling_mean", F.avg("heart_rate").over(w))
        .withColumn("hr_rolling_std", F.stddev("heart_rate").over(w))
        .withColumn("hr_rolling_min", F.min("heart_rate").over(w))
        .withColumn("hr_rolling_max", F.max("heart_rate").over(w))
        # Movement rolling stats
        .withColumn("movement_rolling_mean", F.avg("movement_magnitude").over(w))
        .withColumn("movement_rolling_std", F.stddev("movement_magnitude").over(w))
        # Encode sleep stage as numeric (for rolling avg stage score)
        .withColumn(
            "stage_numeric",
            F.when(F.col("sleep_stage") == "N3", 4)
            .when(F.col("sleep_stage") == "N2", 3)
            .when(F.col("sleep_stage") == "N1", 2)
            .when(F.col("sleep_stage") == "R", 1)
            .when(F.col("sleep_stage") == "W", 0)
            .otherwise(None),
        )
        .withColumn("stage_rolling_mean", F.avg("stage_numeric").over(w))
    )
