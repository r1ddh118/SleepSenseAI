from __future__ import annotations

from analytics.recommendations import generate_recommendations


def test_bad_sleep_recommendations_reference_triggering_metrics_only():
    recs = generate_recommendations(
        sleep_metrics={
            "sleep_efficiency": 0.74,
            "sleep_duration_hours": 6.2,
            "n3_fraction": 0.06,
            "rem_fraction": 0.18,
            "wake_fraction": 0.21,
        },
        risk_metrics={
            "event_rate": 0.010,
            "hr_std": 5.0,
            "movement_std": 0.11,
        },
        lifestyle_metrics={
            "screen_time": 185,
            "stress_level": 8,
            "caffeine": 90,
        },
        longitudinal_metrics={
            "sleep_score_7d_trend": -3,
            "wake_7d_trend": 0.02,
        },
    )

    areas = {rec["area"] for rec in recs}
    trigger_metrics = {rec["trigger"]["metric"] for rec in recs}

    assert "screen_time" in areas
    assert "stress" in areas
    assert "deep_sleep" in areas
    assert "caffeine" not in areas
    assert "screen_time" in trigger_metrics
    assert "stress_level" in trigger_metrics
    assert "n3_fraction" in trigger_metrics
    assert all(rec["trigger"]["metric"] in rec["message"] for rec in recs)


def test_no_generic_recommendations_for_good_metrics():
    recs = generate_recommendations(
        sleep_metrics={
            "sleep_efficiency": 0.91,
            "sleep_duration_hours": 7.6,
            "n3_fraction": 0.19,
            "rem_fraction": 0.22,
            "wake_fraction": 0.07,
        },
        risk_metrics={
            "event_rate": 0.003,
            "hr_std": 3.0,
            "movement_std": 0.08,
        },
        lifestyle_metrics={
            "screen_time": 45,
            "stress_level": 3,
            "caffeine": 80,
        },
        longitudinal_metrics={
            "sleep_score_7d_trend": 1.5,
            "wake_7d_trend": -0.01,
        },
    )

    assert recs == []


def test_each_recommendation_has_metric_value_and_threshold():
    recs = generate_recommendations(
        sleep_metrics={"wake_fraction": 0.30},
        risk_metrics={"event_rate": 0.05},
        lifestyle_metrics={"caffeine": 320},
        longitudinal_metrics={"sleep_score_7d_trend": -8},
    )

    assert recs
    for rec in recs:
        assert rec["trigger"]["metric"]
        assert isinstance(rec["trigger"]["value"], float)
        assert rec["trigger"]["threshold"]
