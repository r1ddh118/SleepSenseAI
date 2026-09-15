"""Generate synthetic longitudinal sleep data for development, demo, and model training.

Output: data/synthetic/sleep_observations.csv
Size: ~100 users × 60 nights × ~100 obs/night = ~600,000 rows

Behavioral plausibility:
  - N3 stage → lower movement
  - Wake stage → higher movement
  - Some users are persistently poor sleepers
  - Some users have elevated event rates (SDB pattern)
  - Lifestyle factors correlated with sleep quality
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "synthetic" / "sleep_observations.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

STAGES = ["W", "N1", "N2", "N3", "R"]

# Movement range per stage
MOVEMENT_PARAMS = {
    "W":  {"mean": 0.55, "std": 0.20},
    "N1": {"mean": 0.25, "std": 0.10},
    "N2": {"mean": 0.15, "std": 0.08},
    "N3": {"mean": 0.08, "std": 0.04},
    "R":  {"mean": 0.20, "std": 0.12},
}

# HR range per stage
HR_PARAMS = {
    "W":  {"mean": 72, "std": 8},
    "N1": {"mean": 65, "std": 6},
    "N2": {"mean": 62, "std": 5},
    "N3": {"mean": 58, "std": 4},
    "R":  {"mean": 64, "std": 7},
}


def user_profile(user_id: str) -> dict:
    """Assign stable characteristics to a user."""
    rng = random.Random(hash(user_id))
    profile_type = rng.choice(["good", "moderate", "poor", "sdb", "circadian"])
    return {
        "type": profile_type,
        "base_hr": rng.gauss(63, 6),
        "n3_bias": {"good": 0.25, "moderate": 0.15, "poor": 0.08, "sdb": 0.12, "circadian": 0.18}[profile_type],
        "rem_bias": {"good": 0.22, "moderate": 0.18, "poor": 0.10, "sdb": 0.15, "circadian": 0.20}[profile_type],
        "wake_bias": {"good": 0.05, "moderate": 0.12, "poor": 0.28, "sdb": 0.20, "circadian": 0.10}[profile_type],
        "event_rate": {"good": 0.005, "moderate": 0.015, "poor": 0.025, "sdb": 0.08, "circadian": 0.010}[profile_type],
        "caffeine": rng.uniform(0, 400),
        "screen_time": rng.uniform(0, 120),
        "exercise": rng.uniform(0, 60),
        "stress": rng.gauss(4, 2),
        "bedtime_hour": {"good": 22.5, "moderate": 23.0, "poor": 0.5, "sdb": 22.0, "circadian": 1.0}[profile_type],
        "bedtime_var": {"good": 0.25, "moderate": 0.5, "poor": 0.8, "sdb": 0.3, "circadian": 2.0}[profile_type],
    }


def generate_night(user_id: str, session_id: str, night_date: datetime, profile: dict, rng: random.Random) -> list[dict]:
    """Generate ~50–200 observations for a single sleep night."""
    n_obs = rng.randint(60, 140)

    # Sleep stage sequence: W → N1 → N2 → N3 → N2 → R → (repeat cycles)
    stages_seq = []
    # Opening: some wake time
    for _ in range(rng.randint(2, 8)):
        stages_seq.append("W")
    # Sleep cycles (~90 min each → ~15 obs per cycle at 6-min intervals)
    n_cycles = rng.randint(3, 6)
    for cycle in range(n_cycles):
        light = rng.randint(2, 5)
        n2 = rng.randint(4, 8)
        n3_count = max(0, int(rng.gauss(profile["n3_bias"] * n_obs / n_cycles, 2)))
        rem_count = max(0, int(rng.gauss(profile["rem_bias"] * n_obs / n_cycles, 2))) if cycle >= 1 else 0
        wake_count = rng.randint(0, int(profile["wake_bias"] * 5))

        stages_seq.extend(["N1"] * light + ["N2"] * n2 + ["N3"] * n3_count +
                          ["N2"] * rng.randint(1, 3) + ["R"] * rem_count +
                          ["W"] * wake_count)

    # Pad/trim to n_obs
    while len(stages_seq) < n_obs:
        stages_seq.append("N2")
    stages_seq = stages_seq[:n_obs]
    rng.shuffle(stages_seq[:4])  # slight shuffle at start

    # Timing
    bed_hour = profile["bedtime_hour"] + rng.gauss(0, profile["bedtime_var"])
    bed_time = night_date.replace(hour=int(bed_hour) % 24, minute=rng.randint(0, 59), second=0)
    onset_offset = timedelta(minutes=rng.gauss(12, 5))
    obs_interval = timedelta(minutes=rng.uniform(4, 8))

    observations = []
    ts = bed_time + onset_offset
    for i, stage in enumerate(stages_seq):
        hr_p = HR_PARAMS[stage]
        mov_p = MOVEMENT_PARAMS[stage]

        hr = np.clip(
            rng.gauss(hr_p["mean"] + (profile["base_hr"] - 63) * 0.5, hr_p["std"]),
            40, 180,
        )
        mov = max(0.0, rng.gauss(mov_p["mean"], mov_p["std"]))
        acc_mag = mov
        # Random direction components that produce the magnitude
        theta = rng.uniform(0, 2 * 3.14159)
        phi = rng.uniform(0, 3.14159)
        acc_x = acc_mag * round(float(np.sin(phi) * np.cos(theta)), 4)
        acc_y = acc_mag * round(float(np.sin(phi) * np.sin(theta)), 4)
        acc_z = acc_mag * round(float(np.cos(phi)), 4)

        event = 1 if rng.random() < profile["event_rate"] else 0
        spo2 = round(rng.gauss(97.5, 0.8 if profile["event_rate"] < 0.04 else 2.0), 1)
        spo2 = float(np.clip(spo2, 88, 100))

        observations.append({
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "date": night_date.strftime("%Y-%m-%d"),
            "heart_rate": round(hr, 1),
            "acc_x": round(acc_x, 4),
            "acc_y": round(acc_y, 4),
            "acc_z": round(acc_z, 4),
            "sleep_stage": stage,
            "bed_time": bed_time.strftime("%H:%M"),
            "sleep_onset": (bed_time + onset_offset).strftime("%H:%M"),
            "wake_time": (bed_time + timedelta(hours=rng.gauss(7.5, 1.0))).strftime("%H:%M"),
            "caffeine": round(max(0, profile["caffeine"] + rng.gauss(0, 30)), 1),
            "screen_time": round(max(0, profile["screen_time"] + rng.gauss(0, 10)), 1),
            "exercise_minutes": round(max(0, profile["exercise"] + rng.gauss(0, 10)), 1),
            "stress_level": round(float(np.clip(profile["stress"] + rng.gauss(0, 1), 1, 10)), 1),
            "nap_minutes": round(max(0, rng.gauss(10, 15) if profile["type"] == "poor" else rng.gauss(0, 10)), 1),
            "awakenings": rng.randint(0, 5),
            "event_count": event,
            "spo2": spo2,
        })
        ts += obs_interval

    return observations


def main():
    n_users = 100
    n_nights = 60
    rng = random.Random(42)

    print(f"Generating {n_users} users × {n_nights} nights of synthetic sleep data...")
    print(f"Output: {OUTPUT_PATH}")

    header = [
        "user_id", "session_id", "timestamp", "date", "heart_rate",
        "acc_x", "acc_y", "acc_z", "sleep_stage",
        "bed_time", "sleep_onset", "wake_time",
        "caffeine", "screen_time", "exercise_minutes", "stress_level",
        "nap_minutes", "awakenings", "event_count", "spo2",
    ]

    total_rows = 0
    with open(OUTPUT_PATH, "w") as f:
        f.write(",".join(header) + "\n")

        for u_idx in range(n_users):
            user_id = f"U{u_idx+1:03d}"
            profile = user_profile(user_id)
            user_rng = random.Random(hash(user_id) + 99)

            start_date = datetime(2025, 9, 1)

            for n_idx in range(n_nights):
                night_date = start_date + timedelta(days=n_idx)
                session_id = f"{user_id}-N{n_idx+1:03d}"

                # For U034: inject declining scores over last 7 nights
                if user_id == "U034" and n_idx >= n_nights - 7:
                    decline_idx = n_idx - (n_nights - 7)
                    profile_copy = profile.copy()
                    profile_copy["wake_bias"] = 0.25 + decline_idx * 0.03
                    profile_copy["n3_bias"] = max(0.03, 0.15 - decline_idx * 0.02)
                    profile_copy["event_rate"] = 0.04 + decline_idx * 0.01
                    obs = generate_night(user_id, session_id, night_date, profile_copy, user_rng)
                else:
                    obs = generate_night(user_id, session_id, night_date, profile, user_rng)

                for row in obs:
                    f.write(",".join(str(row[col]) for col in header) + "\n")
                    total_rows += 1

            if (u_idx + 1) % 10 == 0:
                print(f"  {u_idx+1}/{n_users} users done ({total_rows:,} rows so far)")

    print(f"\n✅ Done! {total_rows:,} rows written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
