from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pyspark.sql import DataFrame, SparkSession

from spark.schemas import RAW_SLEEP_OBSERVATION_SCHEMA


def _spark_path(path: str | Path) -> str:
    path_str = str(path)
    if urlparse(path_str).scheme:
        return path_str
    return Path(path_str).resolve().as_uri()


def load_sleep_data(spark: SparkSession, path: str | Path) -> DataFrame:
    """Load raw sleep observations from CSV using the explicit raw schema."""
    return (
        spark.read.option("header", True)
        .option("mode", "PERMISSIVE")
        .schema(RAW_SLEEP_OBSERVATION_SCHEMA)
        .csv(_spark_path(path))
    )


def load_processed_data(spark: SparkSession, path: str | Path) -> DataFrame:
    """Load processed SleepSense data from Parquet."""
    return spark.read.parquet(_spark_path(path))
