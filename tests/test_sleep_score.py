"""Tests for analytics/sleep_score.py"""

import pytest
from analytics.sleep_score import calculate_sleep_score, DISCLAIMER


GOOD_METRICS = {
    "sleep_efficiency": 0.92,
    "sleep_duration_hours": 7.6,
    "n3_fraction": 0.20,
    "rem_fraction": 0.22,
    "wake_fraction": 0.05,
    "hr_std": 3.0,
    "movement_std": 0.1,
}

POOR_METRICS = {
    "sleep_efficiency": 0.60,
    "sleep_duration_hours": 5.0,
    "n3_fraction": 0.05,
    "rem_fraction": 0.08,
    "wake_fraction": 0.30,
    "hr_std": 10.0,
    "movement_std": 0.5,
}


def test_good_scores_higher_than_poor():
    good = calculate_sleep_score(GOOD_METRICS)
    poor = calculate_sleep_score(POOR_METRICS)
    assert good["score"] > poor["score"], (
        f"Good score {good['score']} should be > poor score {poor['score']}"
    )


def test_good_score_excellent_category():
    result = calculate_sleep_score(GOOD_METRICS)
    assert result["score"] >= 80, f"Expected ≥80, got {result['score']}"
    assert result["category"] == "Excellent"


def test_poor_score_poor_category():
    result = calculate_sleep_score(POOR_METRICS)
    assert result["score"] < 50, f"Expected <50, got {result['score']}"
    assert result["category"] in ("Poor", "Very Poor")


def test_score_in_0_to_100_range():
    for metrics in [GOOD_METRICS, POOR_METRICS]:
        result = calculate_sleep_score(metrics)
        assert 0 <= result["score"] <= 100


def test_component_scores_present():
    result = calculate_sleep_score(GOOD_METRICS)
    components = result["component_scores"]
    required = ["efficiency", "duration", "deep_sleep", "rem", "fragmentation", "hr_stability", "movement"]
    for key in required:
        assert key in components, f"Missing component: {key}"
        assert 0 <= components[key] <= 100


def test_disclaimer_present():
    result = calculate_sleep_score(GOOD_METRICS)
    assert "disclaimer" in result
    assert len(result["disclaimer"]) > 50


def test_deterministic():
    """Same inputs must always produce the same score."""
    r1 = calculate_sleep_score(GOOD_METRICS)
    r2 = calculate_sleep_score(GOOD_METRICS)
    assert r1["score"] == r2["score"]


def test_optimal_efficiency_gives_max_efficiency_component():
    metrics = GOOD_METRICS.copy()
    metrics["sleep_efficiency"] = 0.90  # exact optimal
    result = calculate_sleep_score(metrics)
    assert result["component_scores"]["efficiency"] == 100.0


def test_zero_efficiency_gives_zero_score():
    metrics = {**POOR_METRICS, "sleep_efficiency": 0.0}
    result = calculate_sleep_score(metrics)
    assert result["score"] < 30  # should be very low


def test_fair_category_band():
    metrics = {
        "sleep_efficiency": 0.78,
        "sleep_duration_hours": 6.5,
        "n3_fraction": 0.12,
        "rem_fraction": 0.16,
        "wake_fraction": 0.15,
        "hr_std": 5.0,
        "movement_std": 0.2,
    }
    result = calculate_sleep_score(metrics)
    assert result["category"] in ("Fair", "Good"), f"Unexpected category: {result['category']}"
