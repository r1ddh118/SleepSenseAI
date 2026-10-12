"""Cleaning and signal quality clipping module for 1 Hz night sensor streams."""

from __future__ import annotations

import pandas as pd
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F


def clean_night_stream_spark(df: SparkDataFrame) -> SparkDataFrame:
    """Cleans 1 Hz sensor stream using PySpark column expressions."""
    cleaned = (
        df.withColumn("hr_bpm", F.when(F.col("hr_bpm").between(40.0, 140.0), F.col("hr_bpm")).otherwise(None))
        .withColumn("spo2_pct", F.when(F.col("spo2_pct").between(70.0, 100.0), F.col("spo2_pct")).otherwise(None))
        .withColumn("temp_c", F.when(F.col("temp_c").between(30.0, 39.0), F.col("temp_c")).otherwise(None))
        .withColumn("resp_rpm", F.when(F.col("resp_rpm").between(6.0, 30.0), F.col("resp_rpm")).otherwise(None))
        .withColumn("eda_us", F.when(F.col("eda_us") > 0.0, F.col("eda_us")).otherwise(0.1))
        .withColumn("movement_magnitude", F.greatest(F.col("movement_magnitude"), F.lit(0.0)))
        .withColumn("ambient_lux", F.greatest(F.col("ambient_lux"), F.lit(0.0)))
        .withColumn("snore_decibels", F.greatest(F.col("snore_decibels"), F.lit(0.0)))
    )

    # Impute missing values with forward/backward window fill or mean
    return cleaned.na.fill(
        {
            "hr_bpm": 60.0,
            "spo2_pct": 97.0,
            "temp_c": 35.0,
            "resp_rpm": 14.0,
            "movement_magnitude": 0.01,
            "eda_us": 2.0,
            "ambient_lux": 0.0,
            "snore_decibels": 0.0,
            "bvp_au": 0.0,
        }
    )


def clean_night_stream_pandas(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans 1 Hz sensor stream using Pandas."""
    out = df.copy()

    out["hr_bpm"] = out["hr_bpm"].clip(lower=40.0, upper=140.0).ffill().bfill().fillna(60.0)
    out["spo2_pct"] = out["spo2_pct"].clip(lower=70.0, upper=100.0).ffill().bfill().fillna(97.0)
    out["temp_c"] = out["temp_c"].clip(lower=30.0, upper=39.0).ffill().bfill().fillna(35.0)
    out["resp_rpm"] = out["resp_rpm"].clip(lower=6.0, upper=30.0).ffill().bfill().fillna(14.0)
    out["eda_us"] = out["eda_us"].clip(lower=0.01, upper=50.0).ffill().bfill().fillna(2.0)
    out["movement_magnitude"] = out["movement_magnitude"].clip(lower=0.0).fillna(0.01)
    out["ambient_lux"] = out["ambient_lux"].clip(lower=0.0).fillna(0.0)
    out["snore_decibels"] = out["snore_decibels"].clip(lower=0.0).fillna(0.0)
    out["bvp_au"] = out["bvp_au"].fillna(0.0)

    return out
