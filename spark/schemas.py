"""Explicit StructType schemas for SleepSense AI Spark DataFrames."""

from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Raw observation schema — one row per sensor reading or manual entry observation
SLEEP_SCHEMA = StructType([
    StructField("user_id", StringType(), False),
    StructField("session_id", StringType(), False),
    StructField("timestamp", TimestampType(), False),
    StructField("date", StringType(), True),          # YYYY-MM-DD; derived from timestamp if missing
    StructField("heart_rate", DoubleType(), True),
    StructField("acc_x", DoubleType(), True),
    StructField("acc_y", DoubleType(), True),
    StructField("acc_z", DoubleType(), True),
    StructField("sleep_stage", StringType(), True),   # W, N1, N2, N3, R
    StructField("bed_time", StringType(), True),      # HH:MM
    StructField("sleep_onset", StringType(), True),   # HH:MM
    StructField("wake_time", StringType(), True),     # HH:MM
    StructField("caffeine", DoubleType(), True),      # mg
    StructField("screen_time", DoubleType(), True),   # minutes
    StructField("exercise_minutes", DoubleType(), True),
    StructField("stress_level", DoubleType(), True),  # 1-10
    StructField("nap_minutes", DoubleType(), True),
    StructField("awakenings", IntegerType(), True),
    StructField("event_count", IntegerType(), True),  # breathing events
    StructField("spo2", DoubleType(), True),          # SpO2 %
])

# Nightly aggregated schema — one row per (user_id, session_id, date)
NIGHTLY_SCHEMA = StructType([
    StructField("user_id", StringType(), False),
    StructField("session_id", StringType(), False),
    StructField("date", StringType(), True),
    StructField("avg_hr", DoubleType(), True),
    StructField("hr_std", DoubleType(), True),
    StructField("min_hr", DoubleType(), True),
    StructField("max_hr", DoubleType(), True),
    StructField("avg_movement", DoubleType(), True),
    StructField("observations", IntegerType(), True),
    StructField("n3_fraction", DoubleType(), True),
    StructField("rem_fraction", DoubleType(), True),
    StructField("wake_fraction", DoubleType(), True),
    StructField("n1_fraction", DoubleType(), True),
    StructField("n2_fraction", DoubleType(), True),
    StructField("sleep_efficiency", DoubleType(), True),
    StructField("sleep_score", DoubleType(), True),
    StructField("sleep_category", StringType(), True),
    StructField("risk_level", StringType(), True),
    StructField("event_rate", DoubleType(), True),
    StructField("sleep_duration_hours", DoubleType(), True),
    StructField("sleep_score_7d_avg", DoubleType(), True),
    StructField("sleep_score_14d_avg", DoubleType(), True),
    StructField("duration_7d_avg", DoubleType(), True),
])
