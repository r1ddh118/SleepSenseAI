"""Tests for analytics/condition_risk.py"""

import pytest
from analytics.condition_risk import (
    assess_all_risks,
    assess_insomnia_pattern,
    assess_sleep_disordered_breathing,
    assess_circadian_irregularity,
    assess_sleep_fragmentation,
    MEDICAL_DISCLAIMER,
)


GOOD_METRICS = {
    "sleep_efficiency": 0.90,
    "sleep_duration_hours": 7.5,
    "n3_fraction": 0.20,
    "rem_fraction": 0.22,
    "wake_fraction": 0.05,
    "event_rate": 0.005,
    "avg_hr": 62.0,
    "hr_std": 3.0,
    "avg_movement": 0.2,
    "avg_spo2": 98.0,
    "awakenings": 1,
    "bedtime_variability": 0.2,
    "wake_time_variability": 0.2,
    "duration_variability": 0.3,
    "nap_minutes": 10,
}

SDB_METRICS = {
    **GOOD_METRICS,
    "event_rate": 0.08,
    "avg_spo2": 93.5,
    "hr_std": 12.0,
    "wake_fraction": 0.22,
}

INSOMNIA_METRICS = {
    **GOOD_METRICS,
    "sleep_efficiency": 0.65,
    "wake_fraction": 0.28,
    "sleep_duration_hours": 4.5,
    "awakenings": 8,
}

CIRCADIAN_METRICS = {
    **GOOD_METRICS,
    "bedtime_variability": 2.0,
    "wake_time_variability": 2.0,
    "nap_minutes": 120,
}

FRAGMENTATION_METRICS = {
    **GOOD_METRICS,
    "n3_fraction": 0.05,
    "rem_fraction": 0.08,
    "wake_fraction": 0.30,
    "avg_movement": 0.6,
    "hr_std": 9.0,
}


def test_good_metrics_all_low_risk():
    result = assess_all_risks(GOOD_METRICS)
    assert result["overall_risk_level"] == "LOW"
    for flag in result["risk_flags"]:
        assert flag["risk"] in ("LOW", "MODERATE")


def test_sdb_metrics_high_risk():
    result = assess_sleep_disordered_breathing(SDB_METRICS)
    assert result["risk"] == "HIGH", f"Expected HIGH, got {result['risk']}"
    assert len(result["reasons"]) > 0


def test_insomnia_metrics_moderate_or_high():
    result = assess_insomnia_pattern(INSOMNIA_METRICS)
    assert result["risk"] in ("MODERATE", "HIGH")
    assert any("efficiency" in r.lower() or "wake" in r.lower() or "duration" in r.lower()
               for r in result["reasons"])


def test_circadian_irregularity_detected():
    result = assess_circadian_irregularity(CIRCADIAN_METRICS)
    assert result["risk"] in ("MODERATE", "HIGH")
    assert any("variability" in r.lower() for r in result["reasons"])


def test_fragmentation_detected():
    result = assess_sleep_fragmentation(FRAGMENTATION_METRICS)
    assert result["risk"] in ("MODERATE", "HIGH")
    assert any("N3" in r or "REM" in r or "wake" in r.lower() for r in result["reasons"])


def test_disclaimer_present():
    result = assess_all_risks(GOOD_METRICS)
    assert "disclaimer" in result
    assert "NOT A MEDICAL DIAGNOSIS" in result["disclaimer"].upper() or "NOT" in result["disclaimer"]


def test_all_four_categories_present():
    result = assess_all_risks(GOOD_METRICS)
    categories = {f["category"] for f in result["risk_flags"]}
    assert "sleep_disordered_breathing" in categories
    assert "insomnia_pattern" in categories
    assert "circadian_irregularity" in categories
    assert "sleep_fragmentation" in categories


def test_overall_risk_is_max_of_flags():
    result = assess_all_risks(SDB_METRICS)
    flag_risks = [f["risk"] for f in result["risk_flags"]]
    level_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
    expected_max = max(flag_risks, key=lambda r: level_order[r])
    assert result["overall_risk_level"] == expected_max
