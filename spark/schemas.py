from __future__ import annotations

from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


RAW_SLEEP_OBSERVATION_SCHEMA = StructType(
    [
        StructField("user_id", StringType(), nullable=False),
        StructField("session_id", StringType(), nullable=False),
        StructField("timestamp", TimestampType(), nullable=False),
        StructField("date", DateType(), nullable=False),
        StructField("heart_rate", DoubleType(), nullable=True),
        StructField("acc_x", DoubleType(), nullable=True),
        StructField("acc_y", DoubleType(), nullable=True),
        StructField("acc_z", DoubleType(), nullable=True),
        StructField("sleep_stage", StringType(), nullable=True),
        StructField("bed_time", StringType(), nullable=True),
        StructField("sleep_onset", StringType(), nullable=True),
        StructField("wake_time", StringType(), nullable=True),
        StructField("caffeine", IntegerType(), nullable=True),
        StructField("screen_time", IntegerType(), nullable=True),
        StructField("exercise_minutes", IntegerType(), nullable=True),
        StructField("stress_level", IntegerType(), nullable=True),
        StructField("nap_minutes", IntegerType(), nullable=True),
        StructField("awakenings", IntegerType(), nullable=True),
        StructField("event_count", IntegerType(), nullable=True),
        StructField("spo2", DoubleType(), nullable=True),
    ]
)


SLEEP_STAGES = ("W", "N1", "N2", "N3", "R")
