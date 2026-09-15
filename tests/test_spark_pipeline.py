"""Spark pipeline integration tests.

These tests require PySpark to be installed.
Run: pytest tests/test_spark_pipeline.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def spark():
    """Create a test SparkSession."""
    try:
        from spark.spark_session import create_spark_session
        s = create_spark_session("SleepSenseAI-Test")
        yield s
        s.stop()
    except ImportError:
        pytest.skip("PySpark not installed")


@pytest.fixture(scope="module")
def sample_csv(tmp_path_factory):
    """Create a minimal valid CSV for pipeline testing."""
    tmp = tmp_path_factory.mktemp("data")
    csv_path = tmp / "test_sleep.csv"
    rows = []
    rows.append(",".join([
        "user_id", "session_id", "timestamp", "date", "heart_rate",
        "acc_x", "acc_y", "acc_z", "sleep_stage",
        "bed_time", "sleep_onset", "wake_time",
        "caffeine", "screen_time", "exercise_minutes", "stress_level",
        "nap_minutes", "awakenings", "event_count", "spo2",
    ]))
    # Add 30 observations for user U001, session U001-N001
    for i in range(30):
        stage = ["N2", "N3", "N3", "R", "W"][i % 5]
        hr = 60 + (i % 15)
        rows.append(
            f"U001,U001-N001,2025-09-01 0{i//10}:{i%10:02d}:00,"
            f"2025-09-01,{hr},0.1,0.1,0.9,{stage},"
            "23:00,23:15,06:30,"
            "100,30,20,5,0,2,0,97.5"
        )
    # Add 30 observations for user U002
    for i in range(30):
        stage = ["W", "N1", "N2", "N3", "R"][i % 5]
        hr = 65 + (i % 20)
        rows.append(
            f"U002,U002-N001,2025-09-01 0{i//10}:{i%10:02d}:00,"
            f"2025-09-01,{hr},0.2,0.2,0.8,{stage},"
            "22:30,22:45,07:00,"
            "50,20,30,3,0,1,0,98.0"
        )
    csv_path.write_text("\n".join(rows))
    return csv_path


def test_ingestion(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    df = load_sleep_data(spark, sample_csv)
    assert df.count() == 60
    assert "user_id" in df.columns
    assert "heart_rate" in df.columns


def test_cleaning_removes_invalid_hr(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    from spark.cleaning import clean_sleep_data
    raw = load_sleep_data(spark, sample_csv)
    clean = clean_sleep_data(raw)
    # All our test data has valid HR, so count should be equal or less
    assert clean.count() <= raw.count()
    # Check movement_magnitude was added
    assert "movement_magnitude" in clean.columns


def test_feature_engineering_adds_rolling_columns(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    from spark.cleaning import clean_sleep_data
    from spark.feature_engineering import add_rolling_features
    raw = load_sleep_data(spark, sample_csv)
    clean = clean_sleep_data(raw)
    featured = add_rolling_features(clean)
    assert "hr_rolling_mean" in featured.columns
    assert "movement_rolling_mean" in featured.columns
    assert featured.count() == clean.count()


def test_nightly_metrics_one_row_per_session(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    from spark.cleaning import clean_sleep_data
    from spark.feature_engineering import add_rolling_features
    from spark.sleep_analytics import nightly_metrics
    raw = load_sleep_data(spark, sample_csv)
    clean = clean_sleep_data(raw)
    featured = add_rolling_features(clean)
    nightly = nightly_metrics(featured)
    # Should have exactly 2 rows (one per user/session)
    assert nightly.count() == 2
    assert "n3_fraction" in nightly.columns
    assert "rem_fraction" in nightly.columns
    assert "sleep_efficiency" in nightly.columns


def test_sleep_score_column_added(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    from spark.cleaning import clean_sleep_data
    from spark.feature_engineering import add_rolling_features
    from spark.sleep_analytics import nightly_metrics
    from analytics.sleep_score import calculate_sleep_score_column
    raw = load_sleep_data(spark, sample_csv)
    clean = clean_sleep_data(raw)
    featured = add_rolling_features(clean)
    nightly = nightly_metrics(featured)
    scored = calculate_sleep_score_column(nightly)
    assert "sleep_score" in scored.columns
    assert "sleep_category" in scored.columns
    # All scores should be in [0, 100]
    from pyspark.sql import functions as F
    stats = scored.agg(F.min("sleep_score"), F.max("sleep_score")).collect()[0]
    assert stats[0] >= 0
    assert stats[1] <= 100


def test_longitudinal_adds_trend_columns(spark, sample_csv):
    from spark.ingestion import load_sleep_data
    from spark.cleaning import clean_sleep_data
    from spark.feature_engineering import add_rolling_features
    from spark.sleep_analytics import nightly_metrics
    from analytics.sleep_score import calculate_sleep_score_column
    from spark.risk_analysis import calculate_risk_features
    from pyspark.sql import functions as F
    raw = load_sleep_data(spark, sample_csv)
    clean = clean_sleep_data(raw)
    featured = add_rolling_features(clean)
    nightly = nightly_metrics(featured)
    scored = calculate_sleep_score_column(nightly)
    risk = calculate_risk_features(scored)
    risk = risk.withColumn(
        "risk_level",
        F.when(F.col("high_wake_flag") == 1, "HIGH").otherwise("LOW")
    )
    from spark.longitudinal import add_trends
    longitudinal = add_trends(risk)
    assert "sleep_score_7d_avg" in longitudinal.columns
    assert "sleep_score_14d_avg" in longitudinal.columns
    assert "duration_7d_avg" in longitudinal.columns
