"""30-second epoching and sleep stage inference module."""

from __future__ import annotations

import pandas as pd
import numpy as np


def epoching_and_stage_inference(df_cleaned: pd.DataFrame) -> pd.DataFrame:
    """Resamples 1 Hz sensor stream into 30-second epochs with stage inference."""
    df = df_cleaned.copy()
    df["epoch_index"] = df["elapsed_sec"] // 30

    grouped = df.groupby("epoch_index")

    baseline_hr = df["hr_bpm"].median()

    records = []
    for epoch_idx, epoch_df in grouped:
        start_ts = epoch_df["timestamp_iso"].iloc[0]
        end_ts = epoch_df["timestamp_iso"].iloc[-1]

        hr_m = float(epoch_df["hr_bpm"].mean())
        hr_s = float(epoch_df["hr_bpm"].std(ddof=0)) if len(epoch_df) > 1 else 0.0
        mov_m = float(epoch_df["movement_magnitude"].mean())
        eda_m = float(epoch_df["eda_us"].mean())
        spo2_m = float(epoch_df["spo2_pct"].mean())
        spo2_min = float(epoch_df["spo2_pct"].min())
        temp_m = float(epoch_df["temp_c"].mean())
        resp_m = float(epoch_df["resp_rpm"].mean())
        snore_m = float(epoch_df["snore_decibels"].mean())
        lux_m = float(epoch_df["ambient_lux"].mean())

        # Infer stage
        if mov_m > 0.12 or lux_m > 1.0 or hr_m > (baseline_hr + 8.0):
            stage = "wake"
        elif hr_s > 2.2 or resp_m > 16.5:
            stage = "rem"
        elif hr_m < (baseline_hr - 3.0) and mov_m < 0.025:
            stage = "n3"
        elif hr_m < (baseline_hr - 0.5):
            stage = "n2"
        else:
            stage = "n1"

        records.append(
            {
                "epoch_index": int(epoch_idx),
                "start_timestamp_iso": start_ts,
                "end_timestamp_iso": end_ts,
                "user_id": epoch_df["user_id"].iloc[0],
                "session_id": epoch_df["session_id"].iloc[0],
                "hr_mean": round(hr_m, 2),
                "hr_std": round(hr_s, 2),
                "movement_mean": round(mov_m, 4),
                "eda_mean": round(eda_m, 3),
                "spo2_mean": round(spo2_m, 1),
                "spo2_min": round(spo2_min, 1),
                "temp_mean": round(temp_m, 2),
                "resp_mean": round(resp_m, 1),
                "snore_mean": round(snore_m, 1),
                "ambient_lux_mean": round(lux_m, 1),
                "inferred_stage": stage,
            }
        )

    return pd.DataFrame(records)


def compute_sleep_timings(epochs_df: pd.DataFrame) -> dict:
    """Computes summary sleep timings from 30-second epoch DataFrame."""
    total_epochs = len(epochs_df)
    if total_epochs == 0:
        return {
            "total_sleep_time_seconds": 0,
            "sleep_efficiency": 0.0,
            "wake_fraction": 0.0,
            "n1_fraction": 0.0,
            "n2_fraction": 0.0,
            "n3_fraction": 0.0,
            "rem_fraction": 0.0,
            "wake_after_sleep_onset_seconds": 0,
        }

    duration_sec = total_epochs * 30
    stages = epochs_df["inferred_stage"].values

    wake_count = (stages == "wake").sum()
    n1_count = (stages == "n1").sum()
    n2_count = (stages == "n2").sum()
    n3_count = (stages == "n3").sum()
    rem_count = (stages == "rem").sum()

    sleep_epochs = total_epochs - wake_count
    tst_seconds = sleep_epochs * 30
    efficiency = (sleep_epochs / total_epochs) * 100.0

    return {
        "duration_seconds": duration_sec,
        "sleep_duration_hours": round(tst_seconds / 3600.0, 2),
        "total_sleep_time_seconds": tst_seconds,
        "sleep_efficiency": round(efficiency, 1),
        "wake_fraction": round(wake_count / total_epochs, 4),
        "n1_fraction": round(n1_count / total_epochs, 4),
        "n2_fraction": round(n2_count / total_epochs, 4),
        "n3_fraction": round(n3_count / total_epochs, 4),
        "rem_fraction": round(rem_count / total_epochs, 4),
        "wake_after_sleep_onset_seconds": int(wake_count * 30),
    }
