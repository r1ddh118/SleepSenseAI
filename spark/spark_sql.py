from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession


def register_nightly_sleep_view(nightly: DataFrame, view_name: str = "nightly_sleep") -> None:
    """Register the nightly analytics table as a Spark SQL temp view."""
    nightly.createOrReplaceTempView(view_name)


def average_sleep_score_by_user(spark: SparkSession, view_name: str = "nightly_sleep") -> DataFrame:
    """Run a representative SQL query over nightly sleep analytics."""
    return spark.sql(
        f"""
        SELECT
            user_id,
            ROUND(AVG(sleep_score), 2) AS avg_sleep_score,
            ROUND(AVG(risk_score), 2) AS avg_risk_score,
            COUNT(*) AS nights
        FROM {view_name}
        GROUP BY user_id
        ORDER BY avg_sleep_score ASC, user_id ASC
        """
    )
