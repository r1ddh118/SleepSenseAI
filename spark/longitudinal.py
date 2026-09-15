"""Longitudinal trend analytics — 7d, 14d, 30d rolling window aggregations.

Uses PySpark Window functions partitioned by user_id, ordered by date.
All operations are distributed — no Python loops.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_trends(df: DataFrame) -> DataFrame:
    """Compute rolling longitudinal trend metrics per user.

    Windows:
    - 7-day:  rows -6 to 0 (current + 6 preceding nights)
    - 14-day: rows -13 to 0
    - 30-day: rows -29 to 0

    All windows are partitioned by user_id and ordered by date (string YYYY-MM-DD sorts correctly).
    """
    w7  = Window.partitionBy("user_id").orderBy("date").rowsBetween(-6, 0)
    w14 = Window.partitionBy("user_id").orderBy("date").rowsBetween(-13, 0)
    w30 = Window.partitionBy("user_id").orderBy("date").rowsBetween(-29, 0)

    return (
        df
        # Sleep score trends
        .withColumn("sleep_score_7d_avg",  F.avg("sleep_score").over(w7))
        .withColumn("sleep_score_14d_avg", F.avg("sleep_score").over(w14))
        .withColumn("sleep_score_30d_avg", F.avg("sleep_score").over(w30))
        # Duration trends
        .withColumn("duration_7d_avg",  F.avg("sleep_duration_hours").over(w7))
        .withColumn("duration_14d_avg", F.avg("sleep_duration_hours").over(w14))
        # Efficiency trends
        .withColumn("efficiency_7d_avg",  F.avg("sleep_efficiency").over(w7))
        .withColumn("efficiency_14d_avg", F.avg("sleep_efficiency").over(w14))
        # N3/REM trends
        .withColumn("n3_7d_avg",  F.avg("n3_fraction").over(w7))
        .withColumn("rem_7d_avg", F.avg("rem_fraction").over(w7))
        # Risk flag rolling counts (for alert persistence logic)
        .withColumn("high_risk_last_7d",   F.sum("high_wake_flag").over(w7))
        .withColumn("high_event_last_7d",  F.sum("high_event_rate_flag").over(w7))
        # Count of nights with poor sleep score (<50) in last 7 days
        .withColumn(
            "poor_score_count_7d",
            F.sum(F.when(F.col("sleep_score") < 50, 1).otherwise(0)).over(w7),
        )
        # Count of consecutive HIGH risk nights (last 3)
        .withColumn(
            "high_risk_consecutive_3",
            F.sum(
                F.when(F.col("risk_level") == "HIGH", 1).otherwise(0)
            ).over(Window.partitionBy("user_id").orderBy("date").rowsBetween(-2, 0)),
        )
    )
