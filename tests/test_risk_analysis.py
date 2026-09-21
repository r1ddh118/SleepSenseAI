from __future__ import annotations

from analytics.condition_risk import screen_condition_risks


def _find(flags, condition):
    return next(flag for flag in flags if flag["condition"] == condition)


def test_high_wake_fraction_flags_sleep_fragmentation():
    flags = screen_condition_risks(
        {
            "event_rate": 0.006,
            "wake_fraction": 0.31,
            "n3_fraction": 0.10,
            "rem_fraction": 0.16,
            "sleep_efficiency": 0.64,
            "avg_hr": 72,
            "hr_std": 9.5,
            "movement_std": 0.22,
            "bedtime_variability": 25,
            "wake_time_variability": 30,
            "duration_variability": 0.5,
            "awakenings": 9,
            "avg_spo2": 95,
            "min_spo2": 92,
            "sleep_duration_hours": 6.8,
        }
    )

    fragmentation = _find(flags, "Sleep fragmentation")
    assert fragmentation["risk"] == "HIGH"
    assert fragmentation["confidence"] >= 0.75
    assert any("wake_fraction" in reason for reason in fragmentation["reasons"])


def test_good_sleeper_has_no_material_risk_flags():
    flags = screen_condition_risks(
        {
            "event_rate": 0.002,
            "wake_fraction": 0.05,
            "n3_fraction": 0.20,
            "rem_fraction": 0.22,
            "sleep_efficiency": 0.92,
            "avg_hr": 62,
            "hr_std": 3.0,
            "movement_std": 0.08,
            "bedtime_variability": 18,
            "wake_time_variability": 20,
            "duration_variability": 0.25,
            "awakenings": 1,
            "avg_spo2": 96,
            "min_spo2": 93,
            "sleep_duration_hours": 7.7,
        }
    )

    assert flags == []


def test_breathing_pattern_uses_events_and_spo2_without_diagnosis():
    flags = screen_condition_risks(
        {
            "event_rate": 0.04,
            "wake_fraction": 0.16,
            "n3_fraction": 0.11,
            "rem_fraction": 0.18,
            "sleep_efficiency": 0.81,
            "avg_hr": 70,
            "hr_std": 6.0,
            "movement_std": 0.12,
            "bedtime_variability": 20,
            "wake_time_variability": 28,
            "duration_variability": 0.4,
            "awakenings": 4,
            "avg_spo2": 89.8,
            "min_spo2": 85.5,
            "sleep_duration_hours": 7.1,
        }
    )

    breathing = _find(flags, "Sleep-disordered breathing pattern")
    assert breathing["risk"] == "HIGH"
    assert "not clinically validated" in breathing["disclaimer"]
    assert "not a medical diagnosis" in breathing["disclaimer"]


def test_circadian_irregularity_uses_timing_variability():
    flags = screen_condition_risks(
        {
            "event_rate": 0.003,
            "wake_fraction": 0.10,
            "n3_fraction": 0.16,
            "rem_fraction": 0.19,
            "sleep_efficiency": 0.85,
            "avg_hr": 64,
            "hr_std": 4.0,
            "movement_std": 0.09,
            "bedtime_variability": 135,
            "wake_time_variability": 128,
            "duration_variability": 1.6,
            "awakenings": 2,
            "avg_spo2": 96,
            "min_spo2": 92,
            "sleep_duration_hours": 7.4,
        }
    )

    circadian = _find(flags, "Circadian irregularity")
    assert circadian["risk"] == "HIGH"
    assert len(circadian["reasons"]) >= 2
