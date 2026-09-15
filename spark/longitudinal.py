from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_longitudinal_metrics(df: DataFrame) -> DataFrame:
    """Add 7, 14, and 30 night rolling user-level trend metrics."""
    ordered = Window.partitionBy("user_id").orderBy("date")
    result = df

    for days, frame_start in ((7, -6), (14, -13), (30, -29)):
        window = ordered.rowsBetween(frame_start, 0)
        result = (
            result.withColumn(f"sleep_score_{days}d_avg", F.round(F.avg("sleep_score").over(window), 2))
            .withColumn(
                f"sleep_efficiency_{days}d_avg",
                F.round(F.avg("sleep_efficiency").over(window), 2),
            )
            .withColumn(f"risk_score_{days}d_avg", F.round(F.avg("risk_score").over(window), 2))
            .withColumn(f"event_rate_{days}d_avg", F.round(F.avg("event_rate").over(window), 5))
            .withColumn(f"nights_in_{days}d_window", F.count(F.lit(1)).over(window))
        )

    return result
