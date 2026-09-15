"""Central Spark pipeline orchestrator — the SINGLE entry point for both data paths.

Architecture rule (from blueprint A.4):
  - Bulk/synthetic path: run_pipeline("data/synthetic/sleep_observations.csv", "data/parquet")
  - Per-session Celery path: run_pipeline_for_user(user_id, session_id, raw_csv_path)

Both paths call the SAME spark/ functions. There is no second, simplified pipeline.
FastAPI routes never call this directly — only Celery tasks do.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession

from analytics.sleep_score import calculate_sleep_score_column
from spark.cleaning import clean_sleep_data
from spark.feature_engineering import add_rolling_features
from spark.ingestion import load_sleep_data
from spark.longitudinal import add_trends
from spark.risk_analysis import calculate_risk_features
from spark.sleep_analytics import nightly_metrics
from spark.spark_session import create_spark_session

logger = logging.getLogger(__name__)


def run_pipeline(
    input_path: str | Path,
    output_path: str | Path,
    spark: SparkSession | None = None,
    user_id_filter: str | None = None,
) -> DataFrame:
    """Run the full SleepSense AI PySpark analytics pipeline.

    Parameters
    ----------
    input_path   : path to raw CSV (data/raw/ or data/synthetic/).
    output_path  : destination for Parquet analytics table (data/parquet/).
    spark        : optional existing SparkSession (caller-managed lifecycle).
                   If None, a new session is created and stopped after pipeline.
    user_id_filter : optional user_id to scope processing (for per-session path).

    Returns
    -------
    Computed longitudinal DataFrame (also written to output_path as Parquet).
    """
    owns_session = spark is None
    spark = spark or create_spark_session()
    logger.info("Pipeline start: input=%s output=%s user_filter=%s", input_path, output_path, user_id_filter)

    try:
        # ── Stage 1: Ingestion ─────────────────────────────────────────────
        raw = load_sleep_data(spark, input_path)
        logger.info("Ingested %d raw partitions", raw.rdd.getNumPartitions())

        if user_id_filter:
            raw = raw.filter(raw.user_id == user_id_filter)

        # ── Stage 2: Cleaning ─────────────────────────────────────────────
        clean = clean_sleep_data(raw)

        # ── Stage 3: Feature Engineering ──────────────────────────────────
        featured = add_rolling_features(clean)

        # Persist cleaned+featured data to data/processed/
        processed_path = Path(input_path).parent.parent / "processed"
        processed_path.mkdir(parents=True, exist_ok=True)
        (
            featured.write
            .mode("overwrite" if not user_id_filter else "append")
            .parquet(str(processed_path))
        )
        logger.info("Written processed data → %s", processed_path)

        # ── Stage 4: Nightly Aggregation ──────────────────────────────────
        nightly = nightly_metrics(featured)

        # ── Stage 5: Sleep Score ──────────────────────────────────────────
        scored = calculate_sleep_score_column(nightly)

        # ── Stage 6: Risk Features ────────────────────────────────────────
        risk = calculate_risk_features(scored)

        # Add overall risk_level column (rule-based, for Spark window use)
        from pyspark.sql import functions as F
        risk = risk.withColumn(
            "risk_level",
            F.when(
                (F.col("high_event_rate_flag") + F.col("high_wake_flag") +
                 F.col("low_n3_flag") + F.col("low_rem_flag")) >= 3,
                "HIGH"
            ).when(
                (F.col("high_event_rate_flag") + F.col("high_wake_flag") +
                 F.col("low_n3_flag") + F.col("low_rem_flag")) >= 1,
                "MODERATE"
            ).otherwise("LOW")
        )

        # ── Stage 7: Longitudinal Trends ──────────────────────────────────
        longitudinal = add_trends(risk)

        # ── Stage 8: Write final Parquet analytics table ──────────────────
        out = Path(output_path)
        out.mkdir(parents=True, exist_ok=True)
        (
            longitudinal.write
            .mode("overwrite")
            .partitionBy("user_id")
            .parquet(str(out))
        )
        logger.info("Pipeline complete → %s (rows: %d)", out, longitudinal.count())

        return longitudinal

    finally:
        if owns_session:
            spark.stop()
            logger.info("SparkSession stopped")


def run_pipeline_for_user(
    user_id: str,
    session_id: str,
    raw_csv_path: str | Path,
    parquet_output_path: str | Path,
) -> dict[str, Any]:
    """Per-session Celery entry point — calls the same run_pipeline() function.

    Reads the user's existing Parquet history first (for longitudinal context),
    appends the new session CSV, runs the full pipeline scoped to this user,
    and returns a summary dict for the Celery task to store in DB.
    """
    import pandas as pd
    from pathlib import Path as P

    spark = create_spark_session()
    try:
        # Load new raw CSV
        new_raw = load_sleep_data(spark, raw_csv_path)
        new_raw = new_raw.filter(new_raw.user_id == user_id)

        # Try to union with existing parquet history for this user
        parquet_p = P(parquet_output_path) / f"user_id={user_id}"
        if parquet_p.exists() and any(parquet_p.iterdir()):
            existing = spark.read.parquet(str(parquet_p))
            # Re-read raw processed data so we can re-run full pipeline
            proc_p = P(parquet_output_path).parent / "processed"
            if proc_p.exists():
                existing_raw = (
                    spark.read.parquet(str(proc_p))
                    .filter(spark.read.parquet(str(proc_p)).user_id == user_id)
                )
                # Union existing processed with new raw (which will be cleaned)
                combined = existing_raw.unionByName(
                    add_rolling_features(clean_sleep_data(new_raw)),
                    allowMissingColumns=True,
                )
            else:
                combined = add_rolling_features(clean_sleep_data(new_raw))
        else:
            combined = add_rolling_features(clean_sleep_data(new_raw))

        # Run from nightly aggregation onwards using combined data
        nightly = nightly_metrics(combined)
        scored = calculate_sleep_score_column(nightly)
        risk = calculate_risk_features(scored)

        from pyspark.sql import functions as F
        risk = risk.withColumn(
            "risk_level",
            F.when(
                (F.col("high_event_rate_flag") + F.col("high_wake_flag") +
                 F.col("low_n3_flag") + F.col("low_rem_flag")) >= 3,
                "HIGH"
            ).when(
                (F.col("high_event_rate_flag") + F.col("high_wake_flag") +
                 F.col("low_n3_flag") + F.col("low_rem_flag")) >= 1,
                "MODERATE"
            ).otherwise("LOW")
        )
        longitudinal = add_trends(risk)

        # Write back to parquet (overwrite user partition)
        out = P(parquet_output_path)
        out.mkdir(parents=True, exist_ok=True)
        (
            longitudinal.filter(longitudinal.user_id == user_id)
            .write
            .mode("overwrite")
            .parquet(str(out / f"user_id={user_id}"))
        )

        # Extract latest session row as a Python dict for DB storage
        latest_row = (
            longitudinal
            .filter((longitudinal.user_id == user_id) & (longitudinal.session_id == session_id))
            .orderBy(F.col("date").desc())
            .limit(1)
            .toPandas()
        )

        if latest_row.empty:
            return {"status": "completed", "user_id": user_id, "session_id": session_id}

        row_dict = latest_row.iloc[0].to_dict()
        # Convert numpy types to native Python
        return {
            k: (float(v) if hasattr(v, "item") else v)
            for k, v in row_dict.items()
        }

    finally:
        spark.stop()
