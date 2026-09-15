"""Spark SQL analytics — temp view queries for reporting and leaderboards."""

from pyspark.sql import DataFrame, SparkSession


def register_nightly_view(nightly_df: DataFrame, view_name: str = "nightly_sleep") -> None:
    """Register a nightly metrics DataFrame as a Spark SQL temp view."""
    nightly_df.createOrReplaceTempView(view_name)


def worst_sleepers_query(spark: SparkSession, nightly_df: DataFrame) -> DataFrame:
    """Return users ranked by worst average sleep score (ascending).

    Requires sleep_score column to be present (add after calculate_sleep_score_column).
    """
    register_nightly_view(nightly_df)
    return spark.sql("""
        SELECT
            user_id,
            COUNT(*) AS nights_recorded,
            AVG(sleep_score) AS avg_sleep_score,
            AVG(sleep_duration_hours) AS avg_duration_hours,
            AVG(n3_fraction) AS avg_deep_sleep_fraction,
            AVG(rem_fraction) AS avg_rem_fraction,
            AVG(sleep_efficiency) AS avg_efficiency,
            AVG(wake_fraction) AS avg_wake_fraction,
            AVG(event_rate) AS avg_event_rate
        FROM nightly_sleep
        GROUP BY user_id
        ORDER BY avg_sleep_score ASC
    """)


def stage_distribution_query(spark: SparkSession, nightly_df: DataFrame) -> DataFrame:
    """Return overall population sleep stage distribution."""
    register_nightly_view(nightly_df)
    return spark.sql("""
        SELECT
            AVG(n3_fraction)   AS pop_avg_deep,
            AVG(rem_fraction)  AS pop_avg_rem,
            AVG(n2_fraction)   AS pop_avg_n2,
            AVG(n1_fraction)   AS pop_avg_n1,
            AVG(wake_fraction) AS pop_avg_wake,
            COUNT(DISTINCT user_id) AS total_users,
            COUNT(*) AS total_nights
        FROM nightly_sleep
    """)


def user_trend_query(spark: SparkSession, nightly_df: DataFrame, user_id: str) -> DataFrame:
    """Return date-ordered trend data for a single user."""
    register_nightly_view(nightly_df)
    return spark.sql(f"""
        SELECT
            date,
            sleep_score,
            sleep_score_7d_avg,
            sleep_duration_hours,
            sleep_efficiency,
            n3_fraction,
            rem_fraction,
            wake_fraction,
            risk_level
        FROM nightly_sleep
        WHERE user_id = '{user_id}'
        ORDER BY date ASC
    """)


def high_risk_patients_query(spark: SparkSession, nightly_df: DataFrame) -> DataFrame:
    """Return patients with persistent HIGH risk (≥3 nights in last 7)."""
    register_nightly_view(nightly_df)
    return spark.sql("""
        SELECT
            user_id,
            MAX(date) AS latest_date,
            SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) AS high_risk_nights,
            AVG(sleep_score) AS avg_score,
            MAX(event_rate) AS max_event_rate
        FROM nightly_sleep
        WHERE date >= DATE_SUB(CURRENT_DATE, 7)
        GROUP BY user_id
        HAVING high_risk_nights >= 3
        ORDER BY high_risk_nights DESC
    """)
