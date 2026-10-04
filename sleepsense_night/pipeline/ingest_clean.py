"""
pipeline/ingest_clean.py  –  Ingest CSVs and clean sensor data
==============================================================

Two public functions
--------------------
``read_nights``          – load a folder of per-night CSVs into a single
                           DataFrame, deriving user_id and night_date from the
                           file name when they are absent from the CSV.
``detect_step_seconds``  – return the median sampling interval (seconds).
``clean``                – deduplicate, clamp ranges, forward-fill short gaps,
                           compute epoch durations, and return quality metrics.
"""

from __future__ import annotations

import re

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from sleepsense_night.config import (
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    NUMERIC_COLUMNS,
    VALID_RANGES,
    MAX_GAP_FILL_SECONDS,
    MAX_EPOCH_SECONDS,
)


# ── Ingestion ─────────────────────────────────────────────────────────

def read_nights(spark: SparkSession, input_dir: str) -> DataFrame:
    """Read all ``*.csv`` files under *input_dir* into a single DataFrame.

    Column derivation
    -----------------
    * ``user_id``   – from the file name (pattern ``U\\d+_``), else ``"unknown"``.
    * ``night_date`` – from the CSV column if present, otherwise from
                       ``first_timestamp - 12 h`` (so a midnight–07:00 recording
                       gets the previous calendar date).
    * Absent optional channels are added as ``NULL``.
    * Numeric columns are cast to ``double``; timestamps are parsed.
    """
    df = spark.read.csv(
        f"{input_dir}/*.csv",
        header=True,
        inferSchema=False,
    )

    # Validate required columns
    existing = set(df.columns)
    missing = set(REQUIRED_COLUMNS) - existing
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Add absent optional columns as NULL
    for c in OPTIONAL_COLUMNS:
        if c not in existing:
            df = df.withColumn(c, F.lit(None).cast("string"))

    # ── Derive user_id from file name when absent ──────────────────────
    # Spark 3.2+ exposes _metadata.file_path via hidden metadata column.
    # We use input_file_name() which is universally available.
    df = df.withColumn("_source_file", F.input_file_name())

    has_user_in_csv = (
        "user_id" in existing
        and df.where(F.col("user_id").isNotNull()).limit(1).count() > 0
    )

    if not has_user_in_csv:
        # Extract first "U\d+" pattern from file basename, e.g. U001_2026-09-01.csv
        df = df.withColumn(
            "user_id",
            F.coalesce(
                F.regexp_extract(F.col("_source_file"), r"/(U\d+)_", 1),
                F.lit("unknown"),
            ),
        )

    # Cast numeric columns
    for c in NUMERIC_COLUMNS:
        if c in df.columns:
            df = df.withColumn(c, F.col(c).cast("double"))

    # Parse timestamps
    df = df.withColumn("ts", F.to_timestamp("timestamp"))

    # ── Derive night_date ─────────────────────────────────────────────
    # If the CSV has a night_date column, use it; otherwise compute from
    # the first timestamp of the file minus 12 hours (handles recordings
    # that start before or after midnight).
    part_file = Window.partitionBy("_source_file")
    first_ts = F.min("ts").over(part_file)

    has_date_in_csv = (
        "night_date" in existing
        and df.where(F.col("night_date").isNotNull()).limit(1).count() > 0
    )

    if has_date_in_csv:
        df = df.withColumn(
            "night_date",
            F.coalesce(
                F.to_date("night_date"),
                F.to_date(first_ts - F.expr("INTERVAL 12 HOURS")),
            ),
        )
    else:
        df = df.withColumn(
            "night_date",
            F.to_date(first_ts - F.expr("INTERVAL 12 HOURS")),
        )

    # Drop helper column
    df = df.drop("_source_file")

    return df


def detect_step_seconds(df: DataFrame) -> int:
    """Detect the median sampling interval (seconds) across all nights.

    Uses the inter-sample delta partitioned by (user_id, night_date) so
    gaps don't pollute the estimate.
    """
    w = Window.partitionBy("user_id", "night_date").orderBy("ts")
    step_row = (
        df.withColumn("_dt",
                       F.unix_timestamp("ts") - F.unix_timestamp(F.lag("ts").over(w)))
          .where("_dt > 0 AND _dt < 120")   # ignore long gaps
          .agg(F.percentile_approx("_dt", 0.5).alias("median_step"))
          .first()
    )
    return int(step_row["median_step"]) if step_row and step_row["median_step"] else 10


# ── Cleaning ──────────────────────────────────────────────────────────

def clean(df: DataFrame, step: int) -> tuple[DataFrame, dict]:
    """Clean the raw DataFrame and return ``(cleaned_df, quality_report)``.

    Cleaning stages
    ---------------
    1. Drop exact duplicates on ``(user_id, night_date, ts)``.
    2. Clamp out-of-range values to ``NULL``.
    3. Snapshot null flags BEFORE filling (so imputed counts are accurate).
    4. Forward-fill short gaps (up to ``MAX_GAP_FILL_SECONDS``).
    5. Compute per-epoch duration, marking long gaps with ``is_gap_after``.
    6. Collect quality metrics.
    """
    rows_raw = df.count()

    # 1. Deduplicate ───────────────────────────────────────────────────
    df = df.dropDuplicates(["user_id", "night_date", "ts"])
    rows_deduped = df.count()
    dups_removed = rows_raw - rows_deduped

    # 2. Range clamping ────────────────────────────────────────────────
    artifacts = {}
    for col_name, (lo, hi) in VALID_RANGES.items():
        if col_name not in df.columns:
            continue
        oob_count = df.where(
            (F.col(col_name).isNotNull()) &
            ((F.col(col_name) < lo) | (F.col(col_name) > hi))
        ).count()
        artifacts[col_name] = oob_count
        df = df.withColumn(
            col_name,
            F.when(
                (F.col(col_name) >= lo) & (F.col(col_name) <= hi),
                F.col(col_name),
            ),  # else NULL
        )

    # 3. Snapshot null flags BEFORE filling ───────────────────────────
    # Critical: without this snapshot "rows_imputed" always reads 0 because
    # the flag checks the already-filled column.
    fill_cols = [c for c in ["hr_bpm", "spo2_pct", "resp_rate_bpm", "skin_temp_c"]
                 if c in df.columns]
    for c in fill_cols:
        df = df.withColumn(f"_{c}_was_null", F.col(c).isNull().cast("int"))

    # Also snapshot hr_was_null as a first-class column for features.py
    if "hr_bpm" in df.columns:
        df = df.withColumn("hr_was_null", F.col("hr_bpm").isNull())

    # 4. Forward-fill short gaps ───────────────────────────────────────
    fill_rows = max(1, MAX_GAP_FILL_SECONDS // step)
    w_fill = (
        Window.partitionBy("user_id", "night_date")
              .orderBy("ts")
              .rowsBetween(-fill_rows, 0)
    )
    for c in fill_cols:
        df = df.withColumn(
            c,
            F.coalesce(F.col(c), F.last(c, ignorenulls=True).over(w_fill)),
        )

    # Count imputed rows
    rows_imputed = {}
    for c in fill_cols:
        flag = f"_{c}_was_null"
        imp = df.where(
            (F.col(flag) == 1) & F.col(c).isNotNull()
        ).count()
        rows_imputed[c] = imp
        df = df.drop(flag)

    # 5. Epoch duration + gap flag ─────────────────────────────────────
    wo = Window.partitionBy("user_id", "night_date").orderBy("ts")
    nxt = F.unix_timestamp(F.lead("ts").over(wo)) - F.unix_timestamp("ts")

    # Long gaps (> MAX_EPOCH_SECONDS) are NOT counted as sleep time
    df = df.withColumn(
        "dur_s",
        F.when(nxt <= MAX_EPOCH_SECONDS, nxt).otherwise(F.lit(step)),
    )
    # is_gap_after: 1 when the interval to the next row exceeds 2 minutes
    df = df.withColumn("is_gap_after", (nxt > 120).cast("int"))

    # Count sensor gaps
    sensor_gaps = df.where("is_gap_after = 1").count()

    rows_clean = df.count()

    # 6. Quality report ────────────────────────────────────────────────
    quality = {
        "rows_raw": rows_raw,
        "rows_after_dedup": rows_deduped,
        "duplicates_removed": dups_removed,
        "artifacts_per_signal": artifacts,
        "rows_imputed": rows_imputed,
        "sensor_gaps": sensor_gaps,
        "rows_clean": rows_clean,
    }

    return df, quality
