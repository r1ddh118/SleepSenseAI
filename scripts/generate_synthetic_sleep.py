from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARTICIPANTS = REPO_ROOT / "datasets" / "participant_info.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "synthetic" / "sleep_observations.csv"

STAGES = ("W", "N1", "N2", "N3", "R")
FIELDNAMES = [
    "user_id",
    "session_id",
    "timestamp",
    "date",
    "heart_rate",
    "acc_x",
    "acc_y",
    "acc_z",
    "sleep_stage",
    "bed_time",
    "sleep_onset",
    "wake_time",
    "caffeine",
    "screen_time",
    "exercise_minutes",
    "stress_level",
    "nap_minutes",
    "awakenings",
    "event_count",
    "spo2",
]


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    age: float
    bmi: float
    baseline_hr: float
    poor_sleeper: bool
    elevated_events: bool
    base_spo2: float
    event_rate: float
    stress_bias: float


def _safe_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip().replace("%", ""))
    except ValueError:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _read_seed_profiles(path: Path, rng: random.Random) -> list[UserProfile]:
    if not path.exists():
        return []

    profiles: list[UserProfile] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            user_id = (row.get("SID") or "").strip()
            if not user_id:
                continue

            age = _safe_float(row.get("AGE"), rng.uniform(24, 72))
            bmi = _safe_float(row.get("BMI"), rng.uniform(20, 36))
            ahi = _safe_float(row.get("AHI"), 5.0)
            arousal = _safe_float(row.get("Arousal Index"), 12.0)
            spo2 = _safe_float(row.get("Mean_SaO2"), rng.uniform(94, 98))
            poor_sleeper = ahi >= 15 or arousal >= 30 or bmi >= 35
            elevated_events = ahi >= 15 or spo2 < 93
            event_rate = _clamp(0.003 + ahi / 4500.0, 0.002, 0.05)
            baseline_hr = _clamp(58 + (age - 40) * 0.08 + (bmi - 25) * 0.35 + rng.gauss(0, 4), 48, 86)

            profiles.append(
                UserProfile(
                    user_id=user_id,
                    age=age,
                    bmi=bmi,
                    baseline_hr=baseline_hr,
                    poor_sleeper=poor_sleeper,
                    elevated_events=elevated_events,
                    base_spo2=_clamp(spo2, 88, 99),
                    event_rate=event_rate,
                    stress_bias=rng.uniform(-0.4, 1.0) + (0.7 if poor_sleeper else 0.0),
                )
            )
    return profiles


def _make_profiles(count: int, participant_csv: Path, rng: random.Random) -> list[UserProfile]:
    profiles = _read_seed_profiles(participant_csv, rng)
    existing_ids = {p.user_id for p in profiles}
    next_idx = 1

    while len(profiles) < count:
        user_id = f"U{next_idx:04d}"
        next_idx += 1
        if user_id in existing_ids:
            continue

        age = _clamp(rng.gauss(43, 14), 18, 82)
        bmi = _clamp(rng.gauss(27, 5.5), 18, 48)
        poor_sleeper = rng.random() < 0.22
        elevated_events = rng.random() < (0.18 + (0.12 if bmi > 32 else 0.0))
        base_spo2 = _clamp(rng.gauss(96.5, 1.2) - (2.3 if elevated_events else 0.0), 88, 99)
        event_rate = rng.uniform(0.002, 0.009) + (rng.uniform(0.008, 0.035) if elevated_events else 0)
        baseline_hr = _clamp(57 + (age - 40) * 0.07 + (bmi - 25) * 0.28 + rng.gauss(0, 5), 48, 88)

        profiles.append(
            UserProfile(
                user_id=user_id,
                age=age,
                bmi=bmi,
                baseline_hr=baseline_hr,
                poor_sleeper=poor_sleeper,
                elevated_events=elevated_events,
                base_spo2=base_spo2,
                event_rate=_clamp(event_rate, 0.001, 0.06),
                stress_bias=rng.uniform(-0.7, 0.8) + (0.9 if poor_sleeper else 0.0),
            )
        )
    return profiles[:count]


def _clock(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _sample_bed_time(profile: UserProfile, rng: random.Random) -> int:
    mean = 23 * 60 + 5
    if profile.poor_sleeper:
        mean += 25
    return int(_clamp(rng.gauss(mean, 38), 21 * 60, 25 * 60 + 20))


def _stage_at(progress: float, poor_sleeper: bool, rng: random.Random) -> str:
    if progress < 0.04 or progress > 0.96:
        base = [("W", 0.55), ("N1", 0.35), ("N2", 0.10)]
    elif progress < 0.16:
        base = [("N1", 0.30), ("N2", 0.50), ("N3", 0.17), ("W", 0.03)]
    elif progress < 0.46:
        base = [("N2", 0.43), ("N3", 0.42), ("R", 0.08), ("N1", 0.05), ("W", 0.02)]
    elif progress < 0.74:
        base = [("N2", 0.48), ("R", 0.24), ("N3", 0.16), ("N1", 0.08), ("W", 0.04)]
    else:
        base = [("R", 0.38), ("N2", 0.36), ("N1", 0.14), ("W", 0.09), ("N3", 0.03)]

    if poor_sleeper:
        adjusted = []
        for stage, weight in base:
            if stage == "W":
                weight *= 1.9
            elif stage == "N3":
                weight *= 0.58
            elif stage == "N1":
                weight *= 1.25
            adjusted.append((stage, weight))
        base = adjusted

    roll = rng.random() * sum(weight for _, weight in base)
    cumulative = 0.0
    for stage, weight in base:
        cumulative += weight
        if roll <= cumulative:
            return stage
    return "N2"


def _night_context(profile: UserProfile, night: int, start_date: date, rng: random.Random) -> dict[str, object]:
    current_date = start_date + timedelta(days=night)
    weekend = current_date.weekday() >= 5
    stress = int(round(_clamp(rng.gauss(4.6 + profile.stress_bias, 1.7), 1, 10)))
    caffeine = int(_clamp(rng.gauss(110 + 18 * stress + (25 if weekend else 0), 70), 0, 420))
    screen_time = int(_clamp(rng.gauss(85 + 11 * stress + (25 if profile.poor_sleeper else 0), 42), 0, 260))
    exercise = int(_clamp(rng.gauss(36 - 1.4 * stress, 24), 0, 140))
    nap = int(_clamp(rng.gauss(18 + (12 if profile.poor_sleeper else 0) - exercise * 0.08, 19), 0, 120))

    bed_minutes = _sample_bed_time(profile, rng) + (18 if weekend else 0)
    onset_delay = int(_clamp(rng.gauss(16 + stress * 2.2 + caffeine * 0.025 + screen_time * 0.04 + nap * 0.06, 11), 4, 95))
    sleep_minutes = int(
        _clamp(
            rng.gauss(455, 42)
            - stress * 5
            - caffeine * 0.035
            - screen_time * 0.06
            + exercise * 0.22
            - (42 if profile.poor_sleeper else 0),
            270,
            570,
        )
    )
    awakenings = int(_clamp(rng.gauss(2.2, 1.5), 0, 8))
    if profile.poor_sleeper:
        awakenings += rng.randint(1, 4)
    if profile.elevated_events:
        awakenings += rng.randint(0, 2)
    awakenings = int(_clamp(awakenings, 0, 12))

    onset_minutes = bed_minutes + onset_delay
    wake_minutes = onset_minutes + sleep_minutes + awakenings * rng.randint(2, 6)
    return {
        "date": current_date,
        "bed_minutes": bed_minutes,
        "onset_minutes": onset_minutes,
        "wake_minutes": wake_minutes,
        "sleep_minutes": sleep_minutes,
        "caffeine": caffeine,
        "screen_time": screen_time,
        "exercise_minutes": exercise,
        "stress_level": stress,
        "nap_minutes": nap,
        "awakenings": awakenings,
    }


def _event_count(profile: UserProfile, stage: str, stress: int, rng: random.Random) -> int:
    rate = profile.event_rate * (1.4 if stage in {"R", "N1"} else 1.0) * (0.65 if stage == "W" else 1.0)
    rate *= 1.0 + max(stress - 5, 0) * 0.05
    if rng.random() >= rate:
        return 0
    return 1 + int(rng.random() < 0.08)


def _observation_values(
    profile: UserProfile,
    stage: str,
    event_count: int,
    stress: int,
    rng: random.Random,
) -> tuple[float, float, float, float, float]:
    hr_offsets = {"W": 8.5, "N1": 2.5, "N2": -2.5, "N3": -7.0, "R": 4.0}
    movement = {"W": 0.32, "N1": 0.13, "N2": 0.075, "N3": 0.035, "R": 0.09}[stage]
    if event_count:
        movement *= 1.8

    heart_rate = profile.baseline_hr + hr_offsets[stage] + stress * 0.45 + event_count * 5.5 + rng.gauss(0, 3.0)
    heart_rate = _clamp(heart_rate, 42, 128)

    acc_x = rng.gauss(0.0, movement)
    acc_y = rng.gauss(0.0, movement)
    acc_z = rng.gauss(1.0, movement * 0.75)

    spo2_drop = event_count * rng.uniform(1.1, 3.8) + (0.4 if stage == "R" and profile.elevated_events else 0.0)
    spo2 = _clamp(profile.base_spo2 - spo2_drop + rng.gauss(0, 0.45), 82, 100)
    return heart_rate, acc_x, acc_y, acc_z, spo2


def generate(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    profiles = _make_profiles(args.users, args.participant_csv, rng)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    row_count = 0

    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for profile in profiles:
            for night in range(args.nights):
                context = _night_context(profile, night, start_date, rng)
                observations = rng.randint(args.min_observations, args.max_observations)
                session_id = f"{profile.user_id}_{context['date'].strftime('%Y%m%d')}"
                onset_dt = datetime.combine(context["date"], time()) + timedelta(minutes=int(context["onset_minutes"]))
                interval = float(context["sleep_minutes"]) / max(observations - 1, 1)

                for obs_idx in range(observations):
                    progress = obs_idx / max(observations - 1, 1)
                    stage = _stage_at(progress, profile.poor_sleeper, rng)

                    if context["awakenings"] and rng.random() < min(0.13, context["awakenings"] / observations * 2.2):
                        stage = "W"

                    event_count = _event_count(profile, stage, int(context["stress_level"]), rng)
                    heart_rate, acc_x, acc_y, acc_z, spo2 = _observation_values(
                        profile,
                        stage,
                        event_count,
                        int(context["stress_level"]),
                        rng,
                    )
                    timestamp = onset_dt + timedelta(minutes=obs_idx * interval)

                    writer.writerow(
                        {
                            "user_id": profile.user_id,
                            "session_id": session_id,
                            "timestamp": timestamp.isoformat(timespec="seconds"),
                            "date": context["date"].isoformat(),
                            "heart_rate": f"{heart_rate:.1f}",
                            "acc_x": f"{acc_x:.4f}",
                            "acc_y": f"{acc_y:.4f}",
                            "acc_z": f"{acc_z:.4f}",
                            "sleep_stage": stage,
                            "bed_time": _clock(int(context["bed_minutes"])),
                            "sleep_onset": _clock(int(context["onset_minutes"])),
                            "wake_time": _clock(int(context["wake_minutes"])),
                            "caffeine": context["caffeine"],
                            "screen_time": context["screen_time"],
                            "exercise_minutes": context["exercise_minutes"],
                            "stress_level": context["stress_level"],
                            "nap_minutes": context["nap_minutes"],
                            "awakenings": context["awakenings"],
                            "event_count": event_count,
                            "spo2": f"{spo2:.1f}",
                        }
                    )
                    row_count += 1

    return row_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate longitudinal synthetic SleepSense observations.")
    parser.add_argument("--users", type=int, default=120, help="Number of users to generate; minimum enforced at 100.")
    parser.add_argument("--nights", type=int, default=70, help="Nights per user; minimum enforced at 60.")
    parser.add_argument("--min-observations", type=int, default=100, help="Minimum observations per user-night.")
    parser.add_argument("--max-observations", type=int, default=200, help="Maximum observations per user-night.")
    parser.add_argument("--start-date", default="2026-01-01", help="First synthetic night as YYYY-MM-DD.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output.")
    parser.add_argument("--participant-csv", type=Path, default=DEFAULT_PARTICIPANTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.users = max(args.users, 100)
    args.nights = max(args.nights, 60)
    args.min_observations = int(_clamp(args.min_observations, 50, 200))
    args.max_observations = int(_clamp(args.max_observations, args.min_observations, 200))
    return args


def main() -> int:
    args = parse_args()
    row_count = generate(args)
    print(f"Wrote {row_count:,} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
