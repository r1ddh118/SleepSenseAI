from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime
import pandas as pd
import pytest

from scripts.generate_night_sensor_csvs import SENSOR_CSV_COLUMNS, generate_dataset, generate_single_night


def test_single_night_schema_and_column_contract():
    import numpy as np

    rng = np.random.default_rng(42)
    start_dt = datetime.datetime(2026, 10, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
    df, meta = generate_single_night(
        user_id="U001",
        night_idx=0,
        session_id="S_U001_N01",
        start_dt=start_dt,
        duration_hours=7.0,
        profile_type="healthy",
        rng=rng,
    )

    assert list(df.columns) == SENSOR_CSV_COLUMNS
    assert len(df) == 7 * 3600
    assert meta["user_id"] == "U001"
    assert meta["session_id"] == "S_U001_N01"


def test_monotonic_timestamps_and_elapsed_sec():
    import numpy as np

    rng = np.random.default_rng(42)
    start_dt = datetime.datetime(2026, 10, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
    df, _ = generate_single_night(
        user_id="U002",
        night_idx=1,
        session_id="S_U002_N02",
        start_dt=start_dt,
        duration_hours=7.5,
        profile_type="insomnia",
        rng=rng,
    )

    assert (df["elapsed_sec"].values == list(range(len(df)))).all()

    dt_series = pd.to_datetime(df["timestamp_iso"])
    time_diffs = (dt_series.diff().iloc[1:]).dt.total_seconds()
    assert (time_diffs == 1.0).all()


def test_sensor_value_valid_ranges():
    import numpy as np

    rng = np.random.default_rng(42)
    start_dt = datetime.datetime(2026, 10, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
    df, _ = generate_single_night(
        user_id="U003",
        night_idx=2,
        session_id="S_U003_N03",
        start_dt=start_dt,
        duration_hours=8.0,
        profile_type="sleep_apnea",
        rng=rng,
    )

    assert df["hr_bpm"].between(40.0, 140.0).all()
    assert (df["movement_magnitude"] >= 0.0).all()
    assert (df["eda_us"] > 0.0).all()
    assert df["spo2_pct"].between(70.0, 100.0).all()
    assert df["temp_c"].between(30.0, 39.0).all()
    assert df["resp_rpm"].between(6.0, 30.0).all()
    assert (df["ambient_lux"] >= 0.0).all()
    assert (df["snore_decibels"] >= 0.0).all()


def test_u034_declining_profile_signature():
    import numpy as np

    start_dt = datetime.datetime(2026, 10, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)

    rng0 = np.random.default_rng(100)
    df_n0, meta_n0 = generate_single_night(
        user_id="U034",
        night_idx=0,
        session_id="S_U034_N01",
        start_dt=start_dt,
        duration_hours=8.0,
        profile_type="declining_u034",
        rng=rng0,
    )

    rng9 = np.random.default_rng(100)
    df_n9, meta_n9 = generate_single_night(
        user_id="U034",
        night_idx=9,
        session_id="S_U034_N10",
        start_dt=start_dt,
        duration_hours=8.0,
        profile_type="declining_u034",
        rng=rng9,
    )

    assert meta_n9["apnea_episodes"] > meta_n0["apnea_episodes"]
    assert df_n9["spo2_pct"].min() <= df_n0["spo2_pct"].min()


def test_generator_determinism_with_seed(tmp_path: Path):
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    generate_dataset(out_dir=out1, num_users=2, nights_per_user=2, seed=12345)
    generate_dataset(out_dir=out2, num_users=2, nights_per_user=2, seed=12345)

    f1 = out1 / "U001" / "S_U001_N01.csv"
    f2 = out2 / "U001" / "S_U001_N01.csv"

    df1 = pd.read_csv(f1)
    df2 = pd.read_csv(f2)

    pd.testing.assert_frame_equal(df1, df2)


def test_manifest_integrity():
    manifest_path = Path("data/raw/nights/manifest.csv")
    assert manifest_path.exists()

    df_manifest = pd.read_csv(manifest_path)
    assert len(df_manifest) >= 420
    assert set(["user_id", "session_id", "file_path", "start_timestamp", "end_timestamp", "duration_sec", "num_rows", "profile_type"]).issubset(df_manifest.columns)

    u034_rows = df_manifest[df_manifest["user_id"] == "U034"]
    assert len(u034_rows) >= 10
