"""SparkSession factory for SleepSense AI."""

from pyspark.sql import SparkSession


def create_spark_session(app_name: str = "SleepSenseAI-BigData") -> SparkSession:
    """Create and return a local SparkSession.

    Uses local[*] so every core is used without requiring a cluster.
    Call spark.stop() when done to release resources.
    """
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )
