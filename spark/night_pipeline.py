"""Night Sensor CSV Pipeline Orchestrator for SleepSense AI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import numpy as np
import pandas as pd

from analytics.condition_risk import evaluate_condition_risk
from analytics.recommendations import generate_recommendations
from analytics.sleep_score import calculate_sleep_score
from spark.epoching import compute_sleep_timings, epoching_and_stage_inference
from spark.night_cleaning import clean_night_stream_pandas
from spark.night_eda import compute_eda_artifacts_and_export_json
from spark.night_events import detect_night_events
from spark.night_ingestion import ingest_night_csv_pandas


def process_night_session(
    session_id: str,
    csv_path: str | Path,
    out_parquet_dir: str | Path,
    out_eda_dir: str | Path,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Processes a single 1 Hz night sensor CSV end-to-end."""
    csv_path = Path(csv_path)
    out_parquet_dir = Path(out_parquet_dir)
    out_eda_dir = Path(out_eda_dir)

    # 1. Ingest & Clean
    df_raw = ingest_night_csv_pandas(csv_path)
    if user_id is None:
        user_id = str(df_raw["user_id"].iloc[0])
    df_cleaned = clean_night_stream_pandas(df_raw)

    # 2. 30-second Epoching & Stage Inference
    epochs_df = epoching_and_stage_inference(df_cleaned)

    # 3. Sleep Timings & Fractions
    timings = compute_sleep_timings(epochs_df)

    # 4. Event Detection
    events = detect_night_events(df_cleaned, timings["sleep_duration_hours"])

    # 5. EDA Artifacts & JSON Export
    eda_meta = compute_eda_artifacts_and_export_json(df_cleaned, session_id, user_id, out_eda_dir)

    # 6. Aggregated Night Metrics
    hr_mean = float(df_cleaned["hr_bpm"].mean())
    hr_std = float(df_cleaned["hr_bpm"].std(ddof=0))
    mov_mean = float(df_cleaned["movement_magnitude"].mean())
    mov_std = float(df_cleaned["movement_magnitude"].std(ddof=0))
    eda_mean = float(df_cleaned["eda_us"].mean())
    spo2_mean = float(df_cleaned["spo2_pct"].mean())
    spo2_min = float(df_cleaned["spo2_pct"].min())
    temp_mean = float(df_cleaned["temp_c"].mean())

    metrics = {
        "session_id": session_id,
        "user_id": user_id,
        "duration_seconds": timings["duration_seconds"],
        "sleep_duration_hours": timings["sleep_duration_hours"],
        "sleep_efficiency": timings["sleep_efficiency"],
        "wake_fraction": timings["wake_fraction"],
        "n1_fraction": timings["n1_fraction"],
        "n2_fraction": timings["n2_fraction"],
        "n3_fraction": timings["n3_fraction"],
        "rem_fraction": timings["rem_fraction"],
        "hr_mean": round(hr_mean, 2),
        "hr_std": round(hr_std, 2),
        "movement_mean": round(mov_mean, 4),
        "movement_std": round(mov_std, 4),
        "eda_mean": round(eda_mean, 3),
        "spo2_mean": round(spo2_mean, 1),
        "spo2_min": round(spo2_min, 1),
        "temp_mean": round(temp_mean, 2),
        "event_rate": events["event_rate"],
        "event_count": events["event_count"],
        "micro_arousals_count": events["micro_arousals_count"],
        "desaturation_episodes_count": events["desaturation_episodes_count"],
        "desaturation_index": events["desaturation_index"],
        "snore_minutes": events["snore_minutes"],
        "tonic_eda_mean_us": eda_meta["tonic_eda_mean_us"],
        "phasic_peak_count": eda_meta["phasic_peak_count"],
    }

    # 7. Feed Analytics Engine (Sleep Score, Risk Screening, Recs)
    score_res = calculate_sleep_score(metrics)
    risk_res = evaluate_condition_risk(metrics)
    recs = generate_recommendations(metrics, risk_res, metrics, {})

    metrics["sleep_score"] = score_res["score"]
    metrics["sleep_category"] = score_res["category"]
    metrics["risk_level"] = risk_res["risk_level"]
    metrics["risk_flags"] = risk_res["risk_flags"]
    metrics["recommendations"] = recs

    # 8. Write Parquet output for 30s Epochs
    partition_dir = out_parquet_dir / f"session_id={session_id}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = partition_dir / "epochs.parquet"
    epochs_df.to_parquet(parquet_path, index=False)

    return metrics
