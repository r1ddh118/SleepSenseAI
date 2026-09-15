from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame

from spark.cleaning import clean_sleep_data
from spark.feature_engineering import add_rolling_features
from spark.ingestion import _spark_path, load_sleep_data
from spark.longitudinal import add_longitudinal_metrics
from spark.risk_analysis import add_risk_features
from spark.sleep_analytics import nightly_metrics
from spark.sleep_score import add_sleep_score
from spark.spark_session import create_spark_session
from spark.spark_sql import average_sleep_score_by_user, register_nightly_sleep_view


def build_analytics_table(raw: DataFrame) -> DataFrame:
    """Run the in-memory Spark analytics chain from raw rows to nightly output."""
    clean = clean_sleep_data(raw)
    featured = add_rolling_features(clean)
    nightly = nightly_metrics(featured)
    scored = add_sleep_score(nightly)
    risked = add_risk_features(scored)
    return add_longitudinal_metrics(risked)


def run_pipeline(
    input_path: str | Path = "data/synthetic/sleep_observations.csv",
    output_path: str | Path = "data/parquet",
) -> DataFrame:
    """Run the full Spark analytics pipeline and write the Parquet analytics table."""
    spark = create_spark_session()
    raw = load_sleep_data(spark, input_path)
    analytics = build_analytics_table(raw)
    register_nightly_sleep_view(analytics)
    average_sleep_score_by_user(spark).show(10, truncate=False)
    analytics.write.mode("overwrite").parquet(_spark_path(output_path))
    return analytics
