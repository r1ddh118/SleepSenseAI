#!/usr/bin/env python3
"""
generate_nights.py  –  Synthetic multi-night sensor data generator
=================================================================
Creates realistic per-epoch CSV files for multiple users × nights.

Profiles
--------
- **healthy**       – regular, efficient sleep
- **insomnia**      – long latency, many wake bouts
- **sdb**           – sleep-disordered breathing (desaturations + snoring)
- **irregular**     – shifting bedtime
- **declining**     – starts healthy, degrades over nights

Data problems injected
----------------------
NaN gaps, spike artefacts, duplicate rows, and sensor-off stretches so
that the cleaning stage has real work to do.

Usage
-----
    python generate_nights.py --users 8 --nights 14 --step 10 --out data/raw
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Profiles ──────────────────────────────────────────────────────────

PROFILES = ["healthy", "insomnia", "sdb", "irregular", "declining"]

STAGE_ORDER = ["DEEP", "LIGHT", "REM", "LIGHT"]  # one 90-min cycle

HR_STAGE_OFFSET  = {"W": 12, "LIGHT": 0, "DEEP": -6, "REM": 4}
RESP_STAGE_MEAN  = {"W": 16, "LIGHT": 15, "DEEP": 12, "REM": 18}
RESP_STAGE_SD    = {"W": 1.2, "LIGHT": 0.8, "DEEP": 0.3, "REM": 1.5}


def _smooth(arr: np.ndarray, k: int = 5) -> np.ndarray:
    """Simple moving-average smoothing."""
    kernel = np.ones(k) / k
    return np.convolve(arr, kernel, mode="same")


def _generate_hypnogram(
    n_epochs: int,
    step: int,
    profile: str,
    rng: np.random.Generator,
    night_idx: int,
    total_nights: int,
) -> np.ndarray:
    """Return an array of stage labels for *n_epochs* epochs."""
    stages = np.full(n_epochs, "LIGHT", dtype="<U5")
    cycle_len = int(90 * 60 / step)  # epochs per 90-min cycle
    n_cycles = max(1, n_epochs // cycle_len)

    pos = 0
    for cyc in range(n_cycles):
        deep_frac  = max(0.05, 0.25 - 0.04 * cyc)
        rem_frac   = min(0.35, 0.10 + 0.05 * cyc)
        light_frac = 1.0 - deep_frac - rem_frac

        seg = min(cycle_len, n_epochs - pos)
        d = int(seg * deep_frac)
        r = int(seg * rem_frac)
        l = seg - d - r

        stages[pos:pos + d] = "DEEP"
        stages[pos + d:pos + d + l] = "LIGHT"
        stages[pos + d + l:pos + d + l + r] = "REM"
        pos += seg

    # Inject extra wake bouts for certain profiles
    wake_prob = 0.0
    if profile == "insomnia":
        wake_prob = 0.06
    elif profile == "sdb":
        wake_prob = 0.03
    elif profile == "declining":
        wake_prob = 0.01 + 0.04 * (night_idx / max(1, total_nights - 1))

    if wake_prob > 0:
        for i in range(n_epochs):
            if rng.random() < wake_prob:
                bout = rng.integers(2, max(3, int(5 * 60 / step)))
                stages[i:i + bout] = "W"

    # Mark first and last few epochs as wake
    wake_start = rng.integers(1, max(2, int(3 * 60 / step)))
    wake_end   = rng.integers(1, max(2, int(2 * 60 / step)))
    stages[:wake_start] = "W"
    stages[-wake_end:]  = "W"

    return stages


def _generate_signals(
    stages: np.ndarray,
    step: int,
    profile: str,
    rng: np.random.Generator,
    night_idx: int,
    total_nights: int,
) -> dict[str, np.ndarray]:
    """Build all sensor channels from the hypnogram."""
    n = len(stages)
    rhr = rng.uniform(55, 72)

    # ── Heart rate ────────────────────────────────────────────────────
    hr_offset = np.array([HR_STAGE_OFFSET[s] for s in stages], dtype=float)
    nocturnal_dip = -3.0 * np.sin(np.linspace(0, np.pi, n))
    hr_noise = _smooth(rng.normal(0, 2.5, n), k=7)
    hr = rhr + hr_offset + nocturnal_dip + hr_noise

    # ── Respiration ───────────────────────────────────────────────────
    resp_mean = np.array([RESP_STAGE_MEAN[s] for s in stages], dtype=float)
    resp_sd   = np.array([RESP_STAGE_SD[s]   for s in stages], dtype=float)
    resp = resp_mean + _smooth(rng.normal(0, 1, n), k=5) * resp_sd

    # ── SpO₂ ──────────────────────────────────────────────────────────
    spo2 = 97.2 + _smooth(rng.normal(0, 0.4, n), k=9)

    # ── Movement ──────────────────────────────────────────────────────
    movement = np.abs(rng.normal(0, 0.005, n))
    for i, s in enumerate(stages):
        if s == "W":
            movement[i] += rng.exponential(0.15)
        elif s == "REM":
            movement[i] += rng.exponential(0.01)

    # ── Skin temperature ─────────────────────────────────────────────
    skin_temp = 35.5 + _smooth(rng.normal(0, 0.3, n), k=15)
    # Slight drop during wake
    for i, s in enumerate(stages):
        if s == "W":
            skin_temp[i] -= 0.5

    # ── EDA ───────────────────────────────────────────────────────────
    eda = 2.0 + np.abs(_smooth(rng.normal(0, 1.5, n), k=11))
    for i, s in enumerate(stages):
        if s == "DEEP":
            eda[i] += rng.uniform(0.5, 2.0)

    # ── Snoring ───────────────────────────────────────────────────────
    snore = np.full(n, 25.0)  # baseline ambient
    for i, s in enumerate(stages):
        if s in ("LIGHT", "DEEP"):
            snore[i] += rng.uniform(0, 8)

    # ── Ambient light ─────────────────────────────────────────────────
    ambient = np.full(n, 5.0) + np.abs(rng.normal(0, 2, n))

    # ── Breathing events (SDB / declining) ────────────────────────────
    hours_asleep = sum(1 for s in stages if s != "W") * step / 3600
    ahi = 0
    if profile == "sdb":
        ahi = rng.uniform(10, 35)
    elif profile == "declining":
        ahi = rng.uniform(0, 5) + 10 * (night_idx / max(1, total_nights - 1))

    if ahi > 0:
        n_events = rng.poisson(ahi * hours_asleep)
        asleep_idx = [i for i, s in enumerate(stages) if s != "W"]
        for _ in range(min(n_events, len(asleep_idx) // 3)):
            idx = rng.choice(asleep_idx)
            dur = rng.integers(3, 8)  # epochs
            depth = rng.uniform(3, 9)
            end = min(idx + dur, n)
            k = end - idx
            tri = np.concatenate([np.linspace(0, 1, k // 2 + 1),
                                  np.linspace(1, 0, k - k // 2)])[:k]
            spo2[idx:end] -= depth * tri
            resp[idx:end] *= rng.uniform(0.1, 0.4)
            # Snoring before/during
            snore_start = max(0, idx - 2)
            snore[snore_start:end] += rng.uniform(12, 24)

    return {
        "hr_bpm": hr, "spo2_pct": spo2, "resp_rate_bpm": resp,
        "movement_g": movement, "skin_temp_c": skin_temp,
        "eda_us": eda, "snore_db": snore, "ambient_lux": ambient,
        "device_stage": stages,
    }


def _inject_problems(
    df: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Add realistic data problems: NaN gaps, spikes, duplicates, sensor-off."""
    n = len(df)
    numeric_cols = ["hr_bpm", "spo2_pct", "resp_rate_bpm", "movement_g",
                    "skin_temp_c", "eda_us", "snore_db"]

    # 1. NaN gaps (2–5 % of rows, random columns)
    n_nan = rng.integers(int(n * 0.02), int(n * 0.05) + 1)
    for _ in range(n_nan):
        col = rng.choice(numeric_cols)
        idx = rng.integers(0, n)
        gap_len = rng.integers(1, 6)
        df.loc[idx:idx + gap_len - 1, col] = np.nan

    # 2. Spikes (HR = 0 or 250)
    n_spikes = rng.integers(2, 8)
    for _ in range(n_spikes):
        idx = rng.integers(0, n)
        df.loc[idx, "hr_bpm"] = rng.choice([0, 250])

    # 3. Duplicate rows (5–15 copies)
    n_dups = rng.integers(5, 16)
    dup_idx = rng.choice(n, size=min(n_dups, n), replace=False)
    dups = df.iloc[dup_idx].copy()
    df = pd.concat([df, dups], ignore_index=True).sort_values("timestamp").reset_index(drop=True)

    # 4. Sensor-off stretch (one 3-min block where movement = NaN)
    off_start = rng.integers(n // 4, 3 * n // 4)
    off_len = min(18, n - off_start)  # ~3 min at 10 s step
    df.loc[off_start:off_start + off_len - 1, "movement_g"] = np.nan
    df.loc[off_start:off_start + off_len - 1, "skin_temp_c"] = np.nan

    return df


def generate_night(
    user_id: str,
    night_date: str,
    profile: str,
    step: int,
    rng: np.random.Generator,
    night_idx: int = 0,
    total_nights: int = 14,
) -> pd.DataFrame:
    """Generate one night of sensor data as a DataFrame."""
    # Bedtime varies by profile
    base_hour = 22 if profile != "irregular" else rng.integers(20, 26) % 24
    base_minute = rng.integers(0, 60)
    bedtime = pd.Timestamp(f"{night_date} {base_hour:02d}:{base_minute:02d}:00")

    # Sleep duration 6–9 hours
    if profile == "insomnia":
        total_hours = rng.uniform(4.5, 6.5)
    elif profile == "declining":
        total_hours = rng.uniform(5.5, 8.0) - 1.5 * (night_idx / max(1, total_nights - 1))
    else:
        total_hours = rng.uniform(6.5, 9.0)

    n_epochs = int(total_hours * 3600 / step)
    timestamps = pd.date_range(bedtime, periods=n_epochs, freq=f"{step}s")

    stages = _generate_hypnogram(n_epochs, step, profile, rng,
                                 night_idx, total_nights)
    signals = _generate_signals(stages, step, profile, rng,
                                night_idx, total_nights)

    df = pd.DataFrame({
        "timestamp": timestamps,
        "user_id": user_id,
        "night_date": night_date,
        **signals,
    })

    df = _inject_problems(df, rng)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic sleep nights")
    parser.add_argument("--users",  type=int, default=8,  help="Number of users")
    parser.add_argument("--nights", type=int, default=14, help="Nights per user")
    parser.add_argument("--step",   type=int, default=10, help="Epoch length in seconds")
    parser.add_argument("--out",    type=str, default="data/raw", help="Output directory")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    base_date = pd.Timestamp("2026-09-01")

    for u in range(1, args.users + 1):
        uid = f"U{u:03d}"
        # Assign profile: rotate through them, plus extras are healthy
        profile = PROFILES[u % len(PROFILES)] if u <= len(PROFILES) else "healthy"
        print(f"  {uid}  profile={profile}")

        for n in range(args.nights):
            night_date = (base_date + pd.Timedelta(n, unit="D")).strftime("%Y-%m-%d")
            df = generate_night(uid, night_date, profile, args.step, rng,
                                night_idx=n, total_nights=args.nights)
            fname = out / f"{uid}_{night_date}.csv"
            df.to_csv(fname, index=False)

    total = args.users * args.nights
    print(f"\n✓ Generated {total} night files in {out}/")


if __name__ == "__main__":
    main()
