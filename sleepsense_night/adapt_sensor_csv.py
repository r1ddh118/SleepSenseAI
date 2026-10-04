#!/usr/bin/env python3
"""
adapt_sensor_csv.py  –  Adapt real wearable CSV exports for the pipeline
=========================================================================

Supports DREAMT-style and Empatica E4-style exports.

Typical usage
-------------
    python adapt_sensor_csv.py \
        --input  raw_exports/           \
        --output data/raw_adapted/      \
        --bedtime 22:30                 \
        --acc-scale 64                  \
        --target-seconds 10

Column mapping
--------------
The script maps common column aliases to pipeline names:

    Wearable alias           →  Pipeline column
    ──────────────────────── ─  ──────────────────────
    HR / heart_rate          →  hr_bpm
    EDA / gsr                →  eda_us
    TEMP / temperature       →  skin_temp_c
    BVP                      →  (dropped)
    Sleep_Stage / label      →  device_stage
    ACC_X/Y/Z or x/y/z      →  movement_g (std of mag)
    timestamp / time / t     →  timestamp
    SpO2 / spo2              →  spo2_pct
    RR / resp / resp_rate    →  resp_rate_bpm
    snore                    →  snore_db

Stage label mapping
-------------------
    R → REM,  P → W (PSGW),  W → W,  N → LIGHT,
    1/2 → LIGHT,  3/4 → DEEP,  0 → W
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ── Column alias map ─────────────────────────────────────────────────

ALIAS_MAP = {
    # HR
    "hr": "hr_bpm", "heart_rate": "hr_bpm", "heartrate": "hr_bpm",
    # SpO₂
    "spo2": "spo2_pct", "spO2": "spo2_pct",
    # Respiration
    "rr": "resp_rate_bpm", "resp": "resp_rate_bpm",
    "resp_rate": "resp_rate_bpm", "respiratory_rate": "resp_rate_bpm",
    # EDA
    "eda": "eda_us", "gsr": "eda_us",
    # Temp
    "temp": "skin_temp_c", "temperature": "skin_temp_c",
    # Snore
    "snore": "snore_db",
    # Stage
    "sleep_stage": "device_stage", "label": "device_stage",
    "stage": "device_stage",
    # Timestamp
    "time": "timestamp", "t": "timestamp",
    "elapsed": "timestamp", "seconds": "timestamp",
}

STAGE_MAP = {
    "r": "REM", "rem": "REM",
    "p": "W", "w": "W", "wake": "W", "0": "W",
    "n": "LIGHT", "n1": "LIGHT", "n2": "LIGHT", "1": "LIGHT", "2": "LIGHT",
    "n3": "DEEP",  "n4": "DEEP",  "3": "DEEP",  "4": "DEEP",
    "deep": "DEEP", "light": "LIGHT",
}

ACC_COLS_PATTERNS = [
    re.compile(r"acc_?x", re.I),
    re.compile(r"acc_?y", re.I),
    re.compile(r"acc_?z", re.I),
    re.compile(r"^x$", re.I),
    re.compile(r"^y$", re.I),
    re.compile(r"^z$", re.I),
]


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns using ALIAS_MAP (case-insensitive)."""
    renamed = {}
    for c in df.columns:
        key = c.lower().strip()
        if key in ALIAS_MAP:
            renamed[c] = ALIAS_MAP[key]
    df = df.rename(columns=renamed)
    return df


def _build_movement(df: pd.DataFrame, acc_scale: float) -> pd.DataFrame:
    """Compute movement_g from ACC columns (std of vector magnitude)."""
    acc_found = []
    for pattern in ACC_COLS_PATTERNS:
        matches = [c for c in df.columns if pattern.match(c)]
        acc_found.extend(matches)
    acc_found = list(dict.fromkeys(acc_found))[:3]  # up to 3 axes

    if len(acc_found) >= 1:
        mag = np.sqrt(sum(df[c].fillna(0).astype(float) ** 2 for c in acc_found))
        mag /= acc_scale
        df["movement_g"] = mag
        df = df.drop(columns=acc_found, errors="ignore")
    return df


def _fix_timestamps(df: pd.DataFrame, bedtime: str) -> pd.DataFrame:
    """Convert relative-second timestamps to absolute ISO timestamps."""
    if "timestamp" not in df.columns:
        raise ValueError("No timestamp column found after alias mapping.")

    col = df["timestamp"]
    # If already datetime-like, try to parse directly
    try:
        df["timestamp"] = pd.to_datetime(col)
        return df
    except Exception:
        pass

    # Try numeric (relative seconds since start of recording)
    try:
        rel = col.astype(float)
        anchor = pd.Timestamp(f"2026-01-01 {bedtime}:00")
        df["timestamp"] = anchor + pd.to_timedelta(rel, unit="s")
        return df
    except Exception:
        pass

    # Last resort: leave as-is and let the pipeline fail with a clear error
    return df


def _map_stages(df: pd.DataFrame) -> pd.DataFrame:
    if "device_stage" not in df.columns:
        return df
    df["device_stage"] = (
        df["device_stage"]
        .astype(str)
        .str.lower()
        .str.strip()
        .map(STAGE_MAP)
    )
    return df


def _resample(df: pd.DataFrame, target_s: int) -> pd.DataFrame:
    """Resample to *target_s* second intervals using median aggregation."""
    if "timestamp" not in df.columns:
        return df
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    rule = f"{target_s}s"
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols     = [c for c in df.columns if c not in numeric_cols]

    agg = {}
    for c in numeric_cols:
        agg[c] = "median"
    for c in cat_cols:
        agg[c] = lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan

    resampled = df.resample(rule).agg(agg).reset_index()
    return resampled


def adapt_file(
    src: Path,
    dst: Path,
    bedtime: str = "22:30",
    acc_scale: float = 64.0,
    target_s: int = 10,
) -> None:
    """Convert one wearable CSV to pipeline format and write to *dst*."""
    df = pd.read_csv(str(src))
    df = _map_columns(df)
    df = _build_movement(df, acc_scale)
    df = _fix_timestamps(df, bedtime)
    df = _map_stages(df)
    df = _resample(df, target_s)

    # Drop columns not understood by the pipeline
    keep = {
        "timestamp", "hr_bpm", "movement_g",
        "user_id", "night_date", "spo2_pct", "resp_rate_bpm",
        "skin_temp_c", "eda_us", "snore_db", "ambient_lux", "device_stage",
    }
    df = df[[c for c in df.columns if c in keep]]

    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(dst), index=False)
    print(f"  {src.name} → {dst.name}  ({len(df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adapt wearable CSV exports to SleepSense Night pipeline format"
    )
    parser.add_argument("--input",  required=True, help="Folder of raw CSVs")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--bedtime", default="22:30",
                        help="Anchor time for relative-second timestamps (HH:MM)")
    parser.add_argument("--acc-scale", type=float, default=64.0,
                        help="ACC full-scale divisor (64 for E4, 1 for g units)")
    parser.add_argument("--target-seconds", type=int, default=10,
                        help="Resample to this epoch length (seconds)")
    args = parser.parse_args()

    src_dir = Path(args.input)
    dst_dir = Path(args.output)
    dst_dir.mkdir(parents=True, exist_ok=True)

    csvs = sorted(src_dir.glob("*.csv"))
    if not csvs:
        print(f"No CSV files found in {src_dir}")
        return

    for src in csvs:
        dst = dst_dir / src.name
        try:
            adapt_file(src, dst,
                       bedtime=args.bedtime,
                       acc_scale=args.acc_scale,
                       target_s=args.target_seconds)
        except Exception as e:
            print(f"  ERROR {src.name}: {e}")

    print(f"\n✓ Adapted {len(csvs)} file(s) → {dst_dir}/")


if __name__ == "__main__":
    main()
