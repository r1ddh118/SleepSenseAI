"""
pipeline/spark_utils.py  –  Spark session factory
==================================================
"""

from pyspark.sql import SparkSession

from sleepsense_night.config import DEFAULT_PARTITIONS


def get_spark(app_name: str = "SleepSenseNight",
              partitions: int = DEFAULT_PARTITIONS) -> SparkSession:
    """Create or retrieve the local Spark session.

    Key settings
    -------------
    * ``local[*]``                – use all available cores
    * ``spark.sql.ansi.enabled``  – ``false`` so bad casts yield NULL, not errors
    * Shuffle partitions kept low for single-machine workloads
    """
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", str(partitions))
        .config("spark.sql.ansi.enabled", "false")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
