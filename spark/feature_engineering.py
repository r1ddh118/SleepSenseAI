from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_rolling_features(df: DataFrame) -> DataFrame:
    """Add short rolling physiology and movement features per session."""
    session_window = (
        Window.partitionBy("user_id", "session_id")
        .orderBy("timestamp")
        .rowsBetween(-5, 0)
    )

    return (
        df.withColumn("hr_rolling_mean", F.avg("heart_rate").over(session_window))
        .withColumn("hr_rolling_std", F.stddev_samp("heart_rate").over(session_window))
        .withColumn("movement_rolling_mean", F.avg("movement_magnitude").over(session_window))
        .withColumn(
            "movement_rolling_std",
            F.stddev_samp("movement_magnitude").over(session_window),
        )
    )
