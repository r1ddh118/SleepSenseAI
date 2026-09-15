"""Spark data ingestion — CSV and Parquet readers with explicit schemas."""

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from spark.schemas import SLEEP_SCHEMA


def load_sleep_data(spark: SparkSession, path: str | Path) -> DataFrame:
    """Read raw sleep observation CSV with explicit schema.

    Never reads with pandas — this is a distributed Spark read.
    """
    return (
        spark.read
        .option("header", True)
        .option("timestampFormat", "yyyy-MM-dd HH:mm:ss")
        .schema(SLEEP_SCHEMA)
        .csv(str(path))
    )


def load_processed(spark: SparkSession, path: str | Path) -> DataFrame:
    """Read cleaned + feature-enriched Parquet from data/processed/."""
    return spark.read.parquet(str(path))


def load_parquet_analytics(spark: SparkSession, path: str | Path) -> DataFrame:
    """Read final aggregated Parquet analytics table from data/parquet/."""
    return spark.read.parquet(str(path))


def load_user_history(
    spark: SparkSession, parquet_path: str | Path, user_id: str
) -> DataFrame:
    """Load existing Parquet history for a single user (for per-session path)."""
    p = Path(parquet_path)
    if not p.exists() or not any(p.iterdir()):
        # Return empty DataFrame with correct schema if no history exists yet
        from spark.schemas import NIGHTLY_SCHEMA
        return spark.createDataFrame([], NIGHTLY_SCHEMA)
    return (
        spark.read.parquet(str(p))
        .filter(F.col("user_id") == user_id)
    )
