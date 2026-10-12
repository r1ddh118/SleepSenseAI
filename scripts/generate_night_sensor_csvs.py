"""Synthetic Night Sensor CSV Generator for SleepSense AI (1 Hz time-series)."""

from __future__ import annotations

import argparse
import datetime
import math
import os
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

SENSOR_CSV_COLUMNS = [
    "timestamp_iso",
    "elapsed_sec",
    "hr_bpm",
    "movement_magnitude",
    "eda_us",
    "spo2_pct",
    "temp_c",
    "bvp_au",
    "resp_rpm",
    "ambient_lux",
    "snore_decibels",
    "user_id",
    "session_id",
]


def _generate_night_worker(args_tuple: tuple) -> dict:
    (
        uid,
        n_idx,
        sid,
        night_start_iso,
        duration_h,
        profile_type,
        user_seed,
        out_dir_str,
    ) = args_tuple

    rng = np.random.default_rng(user_seed)
    start_dt = datetime.datetime.fromisoformat(night_start_iso)
    num_seconds = int(duration_h * 3600)
    elapsed = np.arange(num_seconds, dtype=int)

    # Fast ISO timestamp list
    timestamps = [
        (start_dt + datetime.timedelta(seconds=int(s))).strftime("%Y-%m-%dT%H:%M:%SZ")
        for s in elapsed
    ]

    # Sleep Stage Simulation (0=Wake, 1=N1, 2=N2, 3=N3, 4=REM)
    if profile_type == "declining_u034":
        decline_factor = min(1.0, n_idx / 8.0)
        p_wake = 0.05 + 0.25 * decline_factor
        p_n3 = max(0.04, 0.22 - 0.16 * decline_factor)
        p_rem = max(0.10, 0.22 - 0.10 * decline_factor)
        p_n1 = 0.08 + 0.12 * decline_factor
        p_n2 = 1.0 - (p_wake + p_n3 + p_rem + p_n1)
        apnea_prob = 0.005 + 0.04 * decline_factor
    elif profile_type == "insomnia":
        p_wake, p_n1, p_n2, p_n3, p_rem = 0.28, 0.18, 0.38, 0.06, 0.10
        apnea_prob = 0.005
    elif profile_type == "sleep_apnea":
        p_wake, p_n1, p_n2, p_n3, p_rem = 0.18, 0.14, 0.44, 0.10, 0.14
        apnea_prob = 0.045
    else:  # healthy
        p_wake, p_n1, p_n2, p_n3, p_rem = 0.04, 0.08, 0.48, 0.22, 0.18
        apnea_prob = 0.002

    num_epochs = math.ceil(num_seconds / 30)
    epoch_stages = rng.choice(5, size=num_epochs, p=[p_wake, p_n1, p_n2, p_n3, p_rem])
    for e in range(1, num_epochs):
        if rng.random() < 0.82:
            epoch_stages[e] = epoch_stages[e - 1]
    stages_1s = np.repeat(epoch_stages, 30)[:num_seconds]

    base_hr = rng.uniform(54.0, 68.0)
    hr_offsets = np.array([15.0, 5.0, 0.0, -6.0, 4.0])
    hr_stage_effect = hr_offsets[stages_1s]
    hr_noise = rng.normal(0.0, 1.2, size=num_seconds)
    hr_bpm = np.clip(base_hr + hr_stage_effect + hr_noise, 40.0, 140.0).round(1)

    movement = rng.exponential(scale=0.015, size=num_seconds)
    wake_indices = np.where(stages_1s == 0)[0]
    if len(wake_indices) > 0:
        movement[wake_indices] += rng.uniform(0.1, 1.8, size=len(wake_indices))
    movement_magnitude = np.clip(movement, 0.0, 4.5).round(4)

    decay = np.exp(-elapsed / (num_seconds * 0.7)) * 4.0 + 2.0
    phasic = rng.exponential(scale=0.05, size=num_seconds)
    arousal_indices = np.where((stages_1s == 0) | (stages_1s == 4))[0]
    if len(arousal_indices) > 0:
        phasic[arousal_indices] += rng.uniform(0.2, 3.5, size=len(arousal_indices))
    eda_us = np.clip(decay + phasic, 0.1, 30.0).round(3)

    spo2_base = rng.uniform(96.5, 98.5, size=num_seconds)
    spo2_noise = rng.normal(0.0, 0.3, size=num_seconds)
    spo2_pct = spo2_base + spo2_noise

    num_apnea_episodes = 0
    if apnea_prob > 0:
        for sec in range(60, num_seconds - 60, 45):
            if rng.random() < apnea_prob:
                num_apnea_episodes += 1
                dur = rng.integers(15, 40)
                end_sec = min(num_seconds, sec + dur)
                drop_depth = rng.uniform(6.0, 15.0)
                spo2_pct[sec:end_sec] -= drop_depth
                hr_bpm[min(num_seconds - 1, end_sec):min(num_seconds - 1, end_sec + 15)] += rng.uniform(10.0, 25.0)
                movement_magnitude[min(num_seconds - 1, end_sec):min(num_seconds - 1, end_sec + 10)] += rng.uniform(0.5, 2.5)

    spo2_pct = np.clip(spo2_pct, 70.0, 100.0).round(1)

    base_temp = rng.uniform(34.2, 35.8)
    temp_circadian = -0.4 * np.sin(np.pi * elapsed / num_seconds)
    temp_noise = rng.normal(0.0, 0.05, size=num_seconds)
    temp_c = np.clip(base_temp + temp_circadian + temp_noise, 30.0, 39.0).round(2)

    bvp_phase = 2 * np.pi * elapsed * (hr_bpm / 60.0)
    bvp_au = np.clip(np.sin(bvp_phase) + rng.normal(0.0, 0.1, size=num_seconds), -3.0, 3.0).round(3)

    resp_base = 13.5
    resp_stage = np.array([4.0, 1.0, 0.0, -2.5, 2.0])[stages_1s]
    resp_noise = rng.normal(0.0, 0.4, size=num_seconds)
    resp_rpm = np.clip(resp_base + resp_stage + resp_noise, 6.0, 30.0).round(1)

    ambient_lux = np.zeros(num_seconds, dtype=float)
    snore_dB = np.zeros(num_seconds, dtype=float)

    if len(wake_indices) > 0 and rng.random() < 0.4:
        lux_idx = rng.choice(wake_indices, size=min(100, len(wake_indices)))
        ambient_lux[lux_idx] = rng.uniform(2.0, 15.0, size=len(lux_idx)).round(1)

    snore_eligible = np.where((stages_1s == 2) | (stages_1s == 3))[0]
    if len(snore_eligible) > 0 and (apnea_prob > 0.01 or rng.random() < 0.3):
        snore_idx = rng.choice(snore_eligible, size=min(len(snore_eligible), int(len(snore_eligible) * 0.15)))
        snore_dB[snore_idx] = rng.uniform(35.0, 65.0, size=len(snore_idx)).round(1)

    df = pd.DataFrame(
        {
            "timestamp_iso": timestamps,
            "elapsed_sec": elapsed,
            "hr_bpm": hr_bpm,
            "movement_magnitude": movement_magnitude,
            "eda_us": eda_us,
            "spo2_pct": spo2_pct,
            "temp_c": temp_c,
            "bvp_au": bvp_au,
            "resp_rpm": resp_rpm,
            "ambient_lux": ambient_lux,
            "snore_decibels": snore_dB,
            "user_id": uid,
            "session_id": sid,
        }
    )

    out_dir = Path(out_dir_str)
    user_dir = out_dir / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    csv_path = user_dir / f"{sid}.csv"
    df.to_csv(csv_path, index=False)

    return {
        "user_id": uid,
        "session_id": sid,
        "file_path": str(csv_path.relative_to(out_dir)),
        "start_timestamp": timestamps[0],
        "end_timestamp": timestamps[-1],
        "duration_sec": num_seconds,
        "num_rows": len(df),
        "profile_type": profile_type,
        "apnea_episodes": num_apnea_episodes,
    }



def generate_single_night(user_id: str, night_idx: int, session_id: str, start_dt: datetime.datetime, duration_hours: float, profile_type: str, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    task_seed = int(rng.integers(0, 1000000))
    res = _generate_night_worker((user_id, night_idx, session_id, start_dt.isoformat(), duration_hours, profile_type, task_seed, 'data/raw/nights'))
    out_dir = Path('data/raw/nights')
    user_dir = out_dir / user_id
    csv_path = user_dir / f'{session_id}.csv'
    df = pd.read_csv(csv_path)
    return df, res

def generate_dataset(
    out_dir: Path,
    num_users: int = 30,
    nights_per_user: int = 14,
    seed: int = 42,
    single_user: str | None = None,
) -> Path:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    user_ids = [f"U{i:03d}" for i in range(1, num_users + 1)]
    if "U034" not in user_ids:
        user_ids[-1] = "U034"

    if single_user:
        user_ids = [single_user]

    profiles = ["healthy", "insomnia", "sleep_apnea"]
    base_start_date = datetime.datetime(2026, 9, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)

    tasks = []
    for u_idx, uid in enumerate(user_ids):
        if uid == "U034":
            profile_type = "declining_u034"
        else:
            profile_type = profiles[u_idx % len(profiles)]

        for n_idx in range(nights_per_user):
            sid = f"S_{uid}_N{n_idx+1:02d}"
            night_start = base_start_date + datetime.timedelta(days=n_idx, minutes=int(rng.integers(-20, 20)))
            duration_h = float(rng.uniform(7.0, 9.0))
            task_seed = int(rng.integers(0, 1000000))
            tasks.append(
                (
                    uid,
                    n_idx,
                    sid,
                    night_start.isoformat(),
                    duration_h,
                    profile_type,
                    task_seed,
                    str(out_dir),
                )
            )

    print(f"Dispatching {len(tasks)} night CSV generation tasks across CPU cores...")
    manifest_rows = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(_generate_night_worker, task) for task in tasks]
        for future in as_completed(futures):
            res = future.result()
            manifest_rows.append(res)

    manifest_df = pd.DataFrame(manifest_rows).sort_values(by=["user_id", "session_id"])
    manifest_path = out_dir / "manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)
    print(f"Successfully wrote manifest to {manifest_path} ({len(manifest_df)} records)")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic 1 Hz night sensor CSV dataset for SleepSense AI")
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw/nights"), help="Output directory")
    parser.add_argument("--num-users", type=int, default=30, help="Number of users (default 30)")
    parser.add_argument("--nights-per-user", type=int, default=14, help="Nights per user (default 14)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism (default 42)")
    parser.add_argument("--single-user", type=str, default=None, help="Generate single user only (e.g. U034)")

    args = parser.parse_args()
    generate_dataset(
        out_dir=args.out_dir,
        num_users=args.num_users,
        nights_per_user=args.nights_per_user,
        seed=args.seed,
        single_user=args.single_user,
    )


if __name__ == "__main__":
    main()
