from __future__ import annotations

from pyspark.sql import SparkSession


def create_spark_session(app_name: str = "SleepSenseAI") -> SparkSession:
    """Create a local Spark session for SleepSense analytics jobs."""
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.hadoop.fs.defaultFS", "file:///")
        .getOrCreate()
    )
