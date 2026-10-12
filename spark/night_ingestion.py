"""PySpark ingestion layer for 1 Hz night sensor CSV files."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from pyspark.sql import DataFrame as SparkDataFrame, SparkSession
from spark.night_schema import NIGHT_SENSOR_SCHEMA, validate_night_columns


def ingest_night_csv_spark(spark: SparkSession, csv_path: str | Path) -> SparkDataFrame:
    """Ingests a 1 Hz night sensor CSV into a PySpark DataFrame with strict schema."""
    path_str = str(csv_path)
    df = (
        spark.read.option("header", "true")
        .option("mode", "DROPMALFORMED")
        .schema(NIGHT_SENSOR_SCHEMA)
        .csv(path_str)
    )

    valid, missing = validate_night_columns(df.columns)
    if not valid:
        raise ValueError(f"CSV '{csv_path}' is missing required columns: {missing}")

    return df


def ingest_night_csv_pandas(csv_path: str | Path) -> pd.DataFrame:
    """Fallback pandas ingestion for 1 Hz night sensor CSV files."""
    df = pd.read_csv(csv_path)
    valid, missing = validate_night_columns(list(df.columns))
    if not valid:
        raise ValueError(f"CSV '{csv_path}' is missing required columns: {missing}")

    df["elapsed_sec"] = df["elapsed_sec"].astype(int)
    for num_col in ["hr_bpm", "movement_magnitude", "eda_us", "spo2_pct", "temp_c", "bvp_au", "resp_rpm", "ambient_lux", "snore_decibels"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    return df
