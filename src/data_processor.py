from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


class SleepDataProcessor:
    """Loads, cleans, analyzes, and feature-engineers sleep datasets."""

    SENSOR_COLUMNS = ["BVP", "ACC_X", "ACC_Y", "ACC_Z", "TEMP", "EDA", "HR", "IBI"]
    EVENT_COLUMNS = ["Obstructive_Apnea", "Central_Apnea", "Hypopnea", "Multiple_Events"]
    SLEEP_STAGE_COL = "Sleep_Stage"

    def __init__(self, dataset_dir: Path, participant_csv: Path):
        self.dataset_dir = Path(dataset_dir)
        self.participant_csv = Path(participant_csv)

    @staticmethod
    def _safe_numeric(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series.astype(str).str.replace("%", "", regex=False), errors="coerce")

    @staticmethod
    def _extract_sid(file_path: Path) -> str:
        match = re.search(r"(S\d{3})", file_path.name)
        if not match:
            raise ValueError(f"Could not infer SID from filename: {file_path.name}")
        return match.group(1)

    def load_participant_info(self) -> pd.DataFrame:
        info = pd.read_csv(self.participant_csv)
        info.columns = [c.strip().replace("\ufeff", "") for c in info.columns]
        info["SID"] = info["SID"].astype(str).str.strip()

        for col in ["AGE", "BMI", "OAHI", "AHI", "Arousal Index"]:
            info[col] = self._safe_numeric(info[col])
        info["Mean_SaO2"] = self._safe_numeric(info["Mean_SaO2"])

        disorders = info["Sleep_Disorders"].fillna("").str.lower()
        history = info["MEDICAL_HISTORY"].fillna("").str.lower()
        apnea_flags = disorders.str.contains("apnea|difficulty breathing|snoring") | history.str.contains("sleep apnea")

        info["sleep_deprivation_label"] = (
            (info["OAHI"] >= 15)
            | (info["AHI"] >= 15)
            | (info["Arousal Index"] >= 30)
            | apnea_flags
        ).astype(int)

        info["recommended_sleep_hours"] = (
            8.0
            + 0.02 * (info["BMI"].fillna(info["BMI"].median()) - 25)
            + 0.015 * info["Arousal Index"].fillna(info["Arousal Index"].median())
            + 0.01 * info["AHI"].fillna(info["AHI"].median())
            - 0.03 * (info["Mean_SaO2"].fillna(info["Mean_SaO2"].median()) - 94)
        ).clip(6, 10)
        return info

    def _aggregate_sensor_file(self, path: Path) -> Dict[str, float]:
        df = pd.read_csv(path)
        sid = self._extract_sid(path)
        features: Dict[str, float] = {"SID": sid, "records": float(len(df))}

        for col in self.SENSOR_COLUMNS:
            vals = pd.to_numeric(df.get(col), errors="coerce")
            features[f"{col}_mean"] = float(vals.mean())
            features[f"{col}_std"] = float(vals.std())
            features[f"{col}_min"] = float(vals.min())
            features[f"{col}_max"] = float(vals.max())

        for col in self.EVENT_COLUMNS:
            features[f"{col}_count"] = float(df.get(col, pd.Series(dtype=float)).notna().sum())

        total_events = sum(features[f"{c}_count"] for c in self.EVENT_COLUMNS)
        features["event_rate"] = float(total_events / max(len(df), 1))

        sleep_stage = df.get(self.SLEEP_STAGE_COL, pd.Series(dtype=str)).fillna("Unknown").astype(str)
        stage_dist = sleep_stage.value_counts(normalize=True)
        for stage in ["W", "N1", "N2", "N3", "R", "P", "Unknown"]:
            features[f"sleep_stage_pct_{stage}"] = float(stage_dist.get(stage, 0.0))

        return features

    def build_feature_table(self) -> pd.DataFrame:
        participant = self.load_participant_info()
        sensor_paths = sorted(self.dataset_dir.glob("compressed_*_whole_df.csv"))
        if not sensor_paths:
            raise FileNotFoundError(f"No sensor files found in: {self.dataset_dir}")

        sensor_features = [self._aggregate_sensor_file(path) for path in sensor_paths]
        sensor_df = pd.DataFrame(sensor_features)
        merged = sensor_df.merge(participant, on="SID", how="inner")
        if merged.empty:
            raise ValueError("Merged dataset is empty. Check SID alignment.")
        return merged

    def run_eda(self, train_df: pd.DataFrame, outdir: Path) -> Dict[str, str]:
        outdir.mkdir(parents=True, exist_ok=True)
        overview_path = outdir / "eda_overview.csv"
        missing_path = outdir / "eda_missing_values.csv"
        correlation_path = outdir / "eda_numeric_correlation.csv"

        desc = train_df.describe(include="all").transpose()
        desc.to_csv(overview_path)

        missing = pd.DataFrame({
            "column": train_df.columns,
            "missing_count": train_df.isna().sum().values,
            "missing_percent": (train_df.isna().mean() * 100).values,
        }).sort_values("missing_percent", ascending=False)
        missing.to_csv(missing_path, index=False)

        numeric_cols = train_df.select_dtypes(include=["number"]).columns
        corr = train_df[numeric_cols].corr(numeric_only=True)
        corr.to_csv(correlation_path)

        return {
            "overview_csv": str(overview_path),
            "missing_csv": str(missing_path),
            "correlation_csv": str(correlation_path),
        }

    def build_single_prediction_row(self, sensor_csv: Path, sid: str) -> pd.DataFrame:
        participant = self.load_participant_info()
        row = participant.loc[participant["SID"] == sid]
        if row.empty:
            raise ValueError(f"SID {sid} not found in participant info")

        features = self._aggregate_sensor_file(Path(sensor_csv))
        merged = dict(row.iloc[0])
        merged.update(features)
        return pd.DataFrame([merged])
