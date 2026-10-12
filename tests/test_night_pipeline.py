from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import pandas as pd
import pytest

from spark.epoching import compute_sleep_timings, epoching_and_stage_inference
from spark.night_cleaning import clean_night_stream_pandas
from spark.night_eda import compute_eda_artifacts_and_export_json
from spark.night_events import detect_night_events
from spark.night_ingestion import ingest_night_csv_pandas
from spark.night_pipeline import process_night_session
from spark.night_schema import NIGHT_SENSOR_SCHEMA, validate_night_columns


def test_night_schema_and_column_validation():
    cols = [field.name for field in NIGHT_SENSOR_SCHEMA.fields]
    valid, missing = validate_night_columns(cols)
    assert valid is True
    assert len(missing) == 0

    invalid_cols = ["hr_bpm", "timestamp_iso"]
    valid_inv, missing_inv = validate_night_columns(invalid_cols)
    assert valid_inv is False
    assert "elapsed_sec" in missing_inv


def test_night_cleaning_stream():
    raw_data = pd.DataFrame(
        {
            "timestamp_iso": ["2026-10-01T22:00:00Z", "2026-10-01T22:00:01Z"],
            "elapsed_sec": [0, 1],
            "hr_bpm": [25.0, 190.0],  # Out of range values -> clipped to [40, 140]
            "movement_magnitude": [-0.5, 2.0],
            "eda_us": [0.0, 5.0],
            "spo2_pct": [60.0, 105.0],  # Out of range -> clipped to [70, 100]
            "temp_c": [25.0, 42.0],
            "bvp_au": [0.0, 0.0],
            "resp_rpm": [2.0, 40.0],
            "ambient_lux": [-1.0, 5.0],
            "snore_decibels": [-5.0, 50.0],
            "user_id": ["U001", "U001"],
            "session_id": ["S001", "S001"],
        }
    )

    cleaned = clean_night_stream_pandas(raw_data)
    assert cleaned["hr_bpm"].min() >= 40.0
    assert cleaned["hr_bpm"].max() <= 140.0
    assert cleaned["spo2_pct"].min() >= 70.0
    assert cleaned["spo2_pct"].max() <= 100.0
    assert cleaned["movement_magnitude"].min() >= 0.0


def test_epoching_and_stage_inference():
    # Generate 60 seconds (2 epochs) of dummy data
    df_raw = pd.DataFrame(
        {
            "timestamp_iso": [f"2026-10-01T22:00:{i:02d}Z" for i in range(60)],
            "elapsed_sec": list(range(60)),
            "hr_bpm": [60.0] * 60,
            "movement_magnitude": [0.01] * 60,
            "eda_us": [3.0] * 60,
            "spo2_pct": [98.0] * 60,
            "temp_c": [35.0] * 60,
            "bvp_au": [0.0] * 60,
            "resp_rpm": [14.0] * 60,
            "ambient_lux": [0.0] * 60,
            "snore_decibels": [0.0] * 60,
            "user_id": ["U001"] * 60,
            "session_id": ["S001"] * 60,
        }
    )
    cleaned = clean_night_stream_pandas(df_raw)
    epochs = epoching_and_stage_inference(cleaned)

    assert len(epochs) == 2
    assert "inferred_stage" in epochs.columns
    assert set(epochs["inferred_stage"]).issubset({"wake", "n1", "n2", "n3", "rem"})


def test_sleep_timings_computation():
    dummy_epochs = pd.DataFrame(
        {
            "inferred_stage": ["n2", "n2", "n3", "n3", "rem", "wake"],
        }
    )
    timings = compute_sleep_timings(dummy_epochs)

    assert timings["duration_seconds"] == 180
    assert timings["sleep_efficiency"] == round((5 / 6) * 100.0, 1)
    assert timings["wake_fraction"] == round(1 / 6, 4)
    assert timings["n3_fraction"] == round(2 / 6, 4)


def test_event_detection_breathing_and_arousals():
    # Create 600s stream with 1 artificial SpO2 drop episode
    spo2_vals = [98.0] * 600
    for i in range(100, 125):
        spo2_vals[i] = 88.0  # 25s desaturation episode

    df_cleaned = pd.DataFrame(
        {
            "timestamp_iso": [f"2026-10-01T22:{i//60:02d}:{i%60:02d}Z" for i in range(600)],
            "elapsed_sec": list(range(600)),
            "hr_bpm": [60.0] * 600,
            "movement_magnitude": [0.01] * 600,
            "eda_us": [2.0] * 600,
            "spo2_pct": spo2_vals,
            "temp_c": [35.0] * 600,
            "bvp_au": [0.0] * 600,
            "resp_rpm": [14.0] * 600,
            "ambient_lux": [0.0] * 600,
            "snore_decibels": [0.0] * 600,
            "user_id": ["U001"] * 600,
            "session_id": ["S001"] * 600,
        }
    )
    events = detect_night_events(df_cleaned, tst_hours=1.0)

    assert events["desaturation_episodes_count"] >= 1
    assert events["event_count"] >= 1


def test_eda_artifacts_and_json_export(tmp_path: Path):
    df_cleaned = pd.DataFrame(
        {
            "timestamp_iso": [f"2026-10-01T22:00:{i:02d}Z" for i in range(120)],
            "elapsed_sec": list(range(120)),
            "hr_bpm": [60.0] * 120,
            "movement_magnitude": [0.01] * 120,
            "eda_us": [3.0 + (0.5 if i % 20 == 0 else 0.0) for i in range(120)],
            "spo2_pct": [98.0] * 120,
            "temp_c": [35.0] * 120,
            "bvp_au": [0.0] * 120,
            "resp_rpm": [14.0] * 120,
            "ambient_lux": [0.0] * 120,
            "snore_decibels": [0.0] * 120,
            "user_id": ["U001"] * 120,
            "session_id": ["S001"] * 120,
        }
    )

    eda_meta = compute_eda_artifacts_and_export_json(df_cleaned, "S001", "U001", tmp_path)

    json_file = tmp_path / "S001" / "eda.json"
    assert json_file.exists()
    with open(json_file) as f:
        data = json.load(f)

    assert data["session_id"] == "S001"
    assert "tonic_eda_mean_us" in data
    assert "downsampled_eda" in data


def test_full_night_pipeline_execution(tmp_path: Path):
    csv_file = Path("data/raw/nights/U001/S_U001_N01.csv")
    if not csv_file.exists():
        pytest.skip("Synthetic CSV dataset not generated yet")

    out_parquet = tmp_path / "parquet"
    out_eda = tmp_path / "eda"

    metrics = process_night_session(
        session_id="S_U001_N01",
        csv_path=csv_file,
        out_parquet_dir=out_parquet,
        out_eda_dir=out_eda,
    )

    assert metrics["session_id"] == "S_U001_N01"
    assert "sleep_score" in metrics
    assert "risk_level" in metrics
    assert "recommendations" in metrics
    assert (out_parquet / "session_id=S_U001_N01" / "epochs.parquet").exists()
    assert (out_eda / "S_U001_N01" / "eda.json").exists()
