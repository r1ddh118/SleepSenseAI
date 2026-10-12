"""EDA signal artifact extraction and JSON exporter module."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd


def compute_eda_artifacts_and_export_json(
    df_cleaned: pd.DataFrame, session_id: str, user_id: str, out_eda_dir: Path
) -> dict:
    """Computes EDA tonic baseline, phasic peak count, and exports eda.json."""
    eda = df_cleaned["eda_us"].values
    n = len(eda)

    # 1. Tonic EDA baseline via rolling 120s min filter
    tonic = pd.Series(eda).rolling(window=120, min_periods=1, center=True).min().values
    phasic = eda - tonic

    # 2. Phasic peak detection (peaks > 0.15 uS above tonic baseline)
    peaks = (phasic[1:-1] > phasic[:-2]) & (phasic[1:-1] > phasic[2:]) & (phasic[1:-1] > 0.15)
    peak_indices = np.where(peaks)[0] + 1
    peak_count = int(len(peak_indices))
    mean_amplitude = float(np.mean(phasic[peak_indices])) if peak_count > 0 else 0.0

    # 3. Downsample EDA for UI responsiveness (e.g. 10s mean buckets)
    downsampled_factor = 10
    downsampled_eda = (
        pd.Series(eda)
        .groupby(pd.Series(eda).index // downsampled_factor)
        .mean()
        .round(3)
        .tolist()
    )

    start_ts = str(df_cleaned["timestamp_iso"].iloc[0]) if "timestamp_iso" in df_cleaned.columns and len(df_cleaned) > 0 else None
    end_ts = str(df_cleaned["timestamp_iso"].iloc[-1]) if "timestamp_iso" in df_cleaned.columns and len(df_cleaned) > 0 else None

    eda_artifact = {
        "session_id": session_id,
        "user_id": user_id,
        "num_samples": n,
        "sampling_rate_hz": 1.0,
        "start_timestamp_iso": start_ts,
        "end_timestamp_iso": end_ts,
        "downsample_seconds": downsampled_factor,
        "tonic_eda_mean_us": round(float(np.mean(tonic)), 3),
        "phasic_peak_count": peak_count,
        "mean_peak_amplitude_us": round(mean_amplitude, 3),
        "downsampled_eda": downsampled_eda,
    }

    # Save to out_eda_dir / sid / eda.json or out_eda_dir / eda_{sid}.json
    sid_dir = out_eda_dir / session_id
    sid_dir.mkdir(parents=True, exist_ok=True)
    json_path = sid_dir / "eda.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(eda_artifact, f, indent=2)

    return eda_artifact
