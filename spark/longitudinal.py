from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_longitudinal_metrics(df: DataFrame) -> DataFrame:
    """Add rolling user-level averages and trend deltas.

    The 7-day and 14-day windows are the primary longitudinal analytics windows
    for demos and dashboards. The 30-day columns are retained for the existing
    pipeline output.
    """
    ordered = Window.partitionBy("user_id").orderBy("date")
    result = df

    signals = {
        "sleep_score": "sleep_score",
        "sleep_efficiency": "sleep_efficiency",
        "duration": "sleep_duration_hours",
        "rem": "rem_fraction",
        "n3": "n3_fraction",
        "wake": "wake_fraction",
        "hr": "avg_hr",
        "stress": "stress_level",
        "risk_score": "risk_score",
        "event_rate": "event_rate",
    }

    for days, frame_start in ((7, -6), (14, -13), (30, -29)):
        window = ordered.rowsBetween(frame_start, 0)
        result = result.withColumn(f"nights_in_{days}d_window", F.count(F.lit(1)).over(window))

        for output_name, source_col in signals.items():
            result = (
                result.withColumn(
                    f"{output_name}_{days}d_avg",
                    F.round(F.avg(source_col).over(window), 4),
                )
                .withColumn(
                    f"{output_name}_{days}d_trend",
                    F.round(F.col(source_col) - F.col(f"{output_name}_{days}d_avg"), 4),
                )
            )

    return result
