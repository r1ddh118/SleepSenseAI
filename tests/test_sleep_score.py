from __future__ import annotations

from analytics.sleep_score import ACADEMIC_SCORE_DISCLAIMER, calculate_sleep_score


GOOD_SYNTHETIC = {
    "sleep_efficiency": 0.92,
    "sleep_duration_hours": 7.6,
    "n3_fraction": 0.20,
    "rem_fraction": 0.22,
    "wake_fraction": 0.05,
    "hr_std": 3.0,
    "movement_std": 0.1,
}

POOR_SYNTHETIC = {
    "sleep_efficiency": 0.60,
    "sleep_duration_hours": 5.0,
    "n3_fraction": 0.05,
    "rem_fraction": 0.08,
    "wake_fraction": 0.30,
    "hr_std": 10.0,
    "movement_std": 0.5,
}


def test_known_synthetic_scores_are_deterministic_and_ordered():
    good = calculate_sleep_score(GOOD_SYNTHETIC)
    poor = calculate_sleep_score(POOR_SYNTHETIC)

    assert good["score"] == calculate_sleep_score(GOOD_SYNTHETIC)["score"]
    assert poor["score"] == calculate_sleep_score(POOR_SYNTHETIC)["score"]
    assert good["score"] > poor["score"] + 35
    assert 0 <= poor["score"] <= 100
    assert 0 <= good["score"] <= 100


def test_known_synthetic_inputs_fall_in_expected_category_bands():
    good = calculate_sleep_score(GOOD_SYNTHETIC)
    poor = calculate_sleep_score(POOR_SYNTHETIC)

    assert good["category"] == "EXCELLENT"
    assert poor["category"] == "POOR"


def test_response_labels_score_as_academic_not_clinical():
    result = calculate_sleep_score(GOOD_SYNTHETIC)

    assert result["score_type"] == "academic_analytics_sleep_score"
    assert result["clinically_validated"] is False
    assert result["disclaimer"] == ACADEMIC_SCORE_DISCLAIMER
    assert "not clinically validated" in result["disclaimer"]
    assert "not a medical diagnosis" in result["disclaimer"]


def test_percent_inputs_are_normalized_to_fractions():
    fraction_result = calculate_sleep_score(GOOD_SYNTHETIC)
    percent_result = calculate_sleep_score(
        {
            **GOOD_SYNTHETIC,
            "sleep_efficiency": 92,
            "n3_fraction": 20,
            "rem_fraction": 22,
            "wake_fraction": 5,
        }
    )

    assert percent_result["score"] == fraction_result["score"]
