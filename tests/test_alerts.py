"""Tests for analytics/alerts.py — persistence-based doctor alert rules."""

import pytest
from analytics.alerts import evaluate_alert


def _night(date: str, score: float, risk: str = "LOW", wake: float = 0.10, events: float = 0.01):
    return {"date": date, "sleep_score": score, "risk_level": risk, "wake_fraction": wake, "event_rate": events}


# ── No-alert scenarios ───────────────────────────────────────────────────────

def test_single_bad_night_no_alert():
    """A single bad night must NEVER create an alert."""
    nights = [_night("2025-01-01", 45.0, "HIGH", 0.30, 0.06)]
    result = evaluate_alert(nights)
    assert not result["should_alert"], "Single bad night should not trigger alert"


def test_two_bad_nights_no_high_alert():
    """Two consecutive HIGH nights should produce at most MODERATE, never HIGH."""
    nights = [
        _night("2025-01-01", 45.0, "HIGH", 0.30),
        _night("2025-01-02", 42.0, "HIGH", 0.28),
    ]
    result = evaluate_alert(nights)
    if result["should_alert"]:
        assert result["severity"] != "HIGH", "Two nights should not produce HIGH alert"


def test_good_sleeper_no_alert():
    nights = [_night(f"2025-01-{i:02d}", 78.0, "LOW", 0.08, 0.005) for i in range(1, 8)]
    result = evaluate_alert(nights)
    assert not result["should_alert"]


# ── Alert-triggering scenarios ───────────────────────────────────────────────

def test_three_consecutive_high_risk_creates_high_alert():
    """Blueprint requirement: HIGH risk 3 consecutive nights → HIGH alert."""
    nights = [
        _night("2025-01-05", 55.0, "LOW"),
        _night("2025-01-06", 48.0, "HIGH", 0.28, 0.06),
        _night("2025-01-07", 44.0, "HIGH", 0.30, 0.07),
        _night("2025-01-08", 42.0, "HIGH", 0.32, 0.08),
    ]
    result = evaluate_alert(nights)
    assert result["should_alert"]
    assert result["severity"] == "HIGH"
    assert len(result["reasons"]) > 0


def test_five_of_seven_poor_scores_creates_high_alert():
    """Blueprint requirement: score <50 for 5 of 7 nights → HIGH alert."""
    nights = [
        _night("2025-01-01", 45.0, "MODERATE"),
        _night("2025-01-02", 80.0, "LOW"),       # good night (2/7)
        _night("2025-01-03", 46.0, "MODERATE"),
        _night("2025-01-04", 82.0, "LOW"),        # good night (2/7)
        _night("2025-01-05", 47.0, "MODERATE"),
        _night("2025-01-06", 44.0, "MODERATE"),
        _night("2025-01-07", 43.0, "MODERATE"),
    ]
    result = evaluate_alert(nights)
    assert result["should_alert"]
    assert result["severity"] == "HIGH"


def test_three_poor_nights_moderate_alert():
    """3 of 7 nights with score <50 → at minimum MODERATE alert."""
    nights = [
        _night(f"2025-01-{i:02d}", 80.0, "LOW") for i in range(1, 5)
    ] + [
        _night("2025-01-05", 45.0, "MODERATE"),
        _night("2025-01-06", 47.0, "MODERATE"),
        _night("2025-01-07", 46.0, "MODERATE"),
    ]
    result = evaluate_alert(nights)
    assert result["should_alert"]
    assert result["severity"] in ("MODERATE", "HIGH")


# ── Evidence structure ───────────────────────────────────────────────────────

def test_alert_includes_evidence_json():
    nights = [
        _night("2025-01-06", 44.0, "HIGH", 0.32, 0.07),
        _night("2025-01-07", 42.0, "HIGH", 0.34, 0.08),
        _night("2025-01-08", 40.0, "HIGH", 0.36, 0.09),
    ]
    result = evaluate_alert(nights)
    assert result["should_alert"]
    ev = result["evidence_json"]
    assert "high_risk_consecutive_3" in ev
    assert "poor_score_nights_in_7" in ev
    assert "nights_evaluated" in ev


def test_empty_nights_no_alert():
    result = evaluate_alert([])
    assert not result["should_alert"]
    assert result["severity"] == "NONE"
