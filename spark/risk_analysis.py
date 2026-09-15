"""Risk feature calculation — distributes additional risk metrics over nightly data.

Computes per-session risk indicators used by analytics/condition_risk.py.
All operations are Spark DataFrame transformations.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def calculate_risk_features(df: DataFrame) -> DataFrame:
    """Add risk-relevant features to the nightly aggregated DataFrame.

    Features added:
    - bedtime_variability: stddev of bed_time across user's history (Spark window)
    - wake_time_variability: stddev of wake_time across user's history
    - duration_variability: stddev of sleep_duration_hours across user's 7-day window
    - high_event_rate_flag: 1 if event_rate > 0.05 threshold
    - high_wake_flag: 1 if wake_fraction > 0.25
    - low_n3_flag: 1 if n3_fraction < 0.10
    - low_rem_flag: 1 if rem_fraction < 0.15
    """
    # 30-day window for variability calculations
    w_var = Window.partitionBy("user_id").orderBy("date").rowsBetween(-29, 0)

    # Parse bed_time / wake_time as fractional hours for numeric stddev
    # Format assumed: "HH:MM"
    def time_str_to_hours(col_name: str) -> F.Column:
        parts = F.split(F.col(col_name), ":")
        return (
            F.when(
                F.col(col_name).isNotNull() & (F.length(F.col(col_name)) >= 4),
                parts.getItem(0).cast("double") + parts.getItem(1).cast("double") / 60.0,
            ).otherwise(None)
        )

    return (
        df
        .withColumn("bed_time_hours", time_str_to_hours("bed_time"))
        .withColumn("wake_time_hours", time_str_to_hours("wake_time"))
        .withColumn("bedtime_variability", F.stddev("bed_time_hours").over(w_var))
        .withColumn("wake_time_variability", F.stddev("wake_time_hours").over(w_var))
        .withColumn(
            "duration_variability",
            F.stddev("sleep_duration_hours").over(w_var),
        )
        # Binary risk flags
        .withColumn(
            "high_event_rate_flag",
            F.when(F.col("event_rate") > 0.05, 1).otherwise(0),
        )
        .withColumn(
            "high_wake_flag",
            F.when(F.col("wake_fraction") > 0.25, 1).otherwise(0),
        )
        .withColumn(
            "low_n3_flag",
            F.when(F.col("n3_fraction") < 0.10, 1).otherwise(0),
        )
        .withColumn(
            "low_rem_flag",
            F.when(F.col("rem_fraction") < 0.15, 1).otherwise(0),
        )
        .withColumn(
            "high_hr_flag",
            F.when(F.col("avg_hr") > 75.0, 1).otherwise(0),
        )
        .withColumn(
            "high_hr_std_flag",
            F.when(F.col("hr_std") > 8.0, 1).otherwise(0),
        )
    )
