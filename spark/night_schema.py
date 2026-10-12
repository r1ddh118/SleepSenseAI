"""PySpark schema and validation for 1 Hz night sensor CSV data."""

from __future__ import annotations

from typing import List, Tuple
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

NIGHT_SENSOR_SCHEMA = StructType(
    [
        StructField("timestamp_iso", StringType(), False),
        StructField("elapsed_sec", IntegerType(), False),
        StructField("hr_bpm", DoubleType(), True),
        StructField("movement_magnitude", DoubleType(), True),
        StructField("eda_us", DoubleType(), True),
        StructField("spo2_pct", DoubleType(), True),
        StructField("temp_c", DoubleType(), True),
        StructField("bvp_au", DoubleType(), True),
        StructField("resp_rpm", DoubleType(), True),
        StructField("ambient_lux", DoubleType(), True),
        StructField("snore_decibels", DoubleType(), True),
        StructField("user_id", StringType(), False),
        StructField("session_id", StringType(), False),
    ]
)

REQUIRED_NIGHT_COLUMNS = [field.name for field in NIGHT_SENSOR_SCHEMA.fields]


def validate_night_columns(columns: List[str]) -> Tuple[bool, List[str]]:
    """Validates if input CSV header contains all required 1 Hz night sensor columns."""
    missing = [col for col in REQUIRED_NIGHT_COLUMNS if col not in columns]
    return len(missing) == 0, missing
