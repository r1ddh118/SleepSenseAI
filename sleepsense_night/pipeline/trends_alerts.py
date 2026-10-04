"""
pipeline/trends_alerts.py  –  Multi-night trends and doctor alerts
==================================================================

Moving averages, trend labels, circadian-regularity flag, and
gaps-and-islands based consecutive-night alert streaks.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from sleepsense_night.config import (
    TREND_DECLINE_POINTS,
    CIRCADIAN_STD_MINUTES,
    ALERT_CONSECUTIVE_NIGHTS,
)


def add_trends(nightly: DataFrame) -> DataFrame:
    """Add 7/14/30-night moving averages, trend label, circadian flag."""

    w_user = Window.partitionBy("user_id").orderBy("night_date")

    # Moving averages
    for days in (7, 14, 30):
        w = w_user.rowsBetween(-(days - 1), 0)
        nightly = nightly.withColumn(
            f"sleep_score_ma{days}",
            F.round(F.avg("sleep_score").over(w), 1),
        )
        nightly = nightly.withColumn(
            f"tst_ma{days}",
            F.round(F.avg("tst_min").over(w), 1),
        )

    # Trend label: compare current 7-night MA to 7 nights before
    w_prior = w_user.rowsBetween(-13, -7)
    nightly = nightly.withColumn(
        "_prior_ma7",
        F.avg("sleep_score").over(w_prior),
    )
    nightly = nightly.withColumn(
        "trend_label",
        F.when(
            F.col("sleep_score_ma7") - F.col("_prior_ma7") <= -TREND_DECLINE_POINTS,
            F.lit("declining"),
        ).when(
            F.col("sleep_score_ma7") - F.col("_prior_ma7") >= TREND_DECLINE_POINTS,
            F.lit("improving"),
        ).otherwise(F.lit("stable")),
    ).drop("_prior_ma7")

    # Circadian regularity flag: bedtime σ over 7 nights > threshold
    w7 = w_user.rowsBetween(-6, 0)
    nightly = nightly.withColumn(
        "_bedtime_minutes",
        F.hour("bedtime_ts") * 60 + F.minute("bedtime_ts"),
    )
    nightly = nightly.withColumn(
        "bedtime_std_min",
        F.round(F.stddev("_bedtime_minutes").over(w7), 1),
    )
    nightly = nightly.withColumn(
        "flag_circadian",
        F.coalesce(F.col("bedtime_std_min") > CIRCADIAN_STD_MINUTES, F.lit(False)),
    ).drop("_bedtime_minutes")

    return nightly


def doctor_alerts(nightly: DataFrame) -> DataFrame:
    """Find streaks of ≥ ALERT_CONSECUTIVE_NIGHTS high-risk nights.

    Uses the gaps-and-islands trick: consecutive calendar dates that are
    all high-risk share the same ``island`` value.
    """
    user_by_date = Window.partitionBy("user_id").orderBy("night_date")

    flagged = nightly.where("high_risk_night = true")
    flagged = flagged.withColumn("rn", F.row_number().over(user_by_date))
    flagged = flagged.withColumn(
        "island",
        F.date_sub(F.col("night_date"), F.col("rn")),
    )

    streaks = (
        flagged
        .groupBy("user_id", "island")
        .agg(
            F.count("*").alias("streak_nights"),
            F.min("night_date").alias("streak_start"),
            F.max("night_date").alias("streak_end"),
            F.round(F.avg("sleep_score"), 1).alias("avg_score"),
            F.round(F.avg("odi"), 1).alias("avg_odi"),
            F.collect_list("score_drivers").alias("drivers"),
        )
    )

    alerts = (
        streaks
        .where(F.col("streak_nights") >= ALERT_CONSECUTIVE_NIGHTS)
        .drop("island")
    )

    return alerts
