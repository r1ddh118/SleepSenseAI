from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


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

    @staticmethod
    def _build_sleep_deprivation_label(info: pd.DataFrame) -> pd.Series:
        disorders = info["Sleep_Disorders"].fillna("").str.lower()
        history = info["MEDICAL_HISTORY"].fillna("").str.lower()
        apnea_flags = disorders.str.contains("apnea|difficulty breathing|snoring") | history.str.contains("sleep apnea")

        heuristic_label = (
            (info["OAHI"] >= 15)
            | (info["AHI"] >= 15)
            | (info["Arousal Index"] >= 30)
            | apnea_flags
        ).astype(int)
        if heuristic_label.nunique() > 1:
            return heuristic_label

        # Small curated datasets can collapse to a single class under the
        # clinical heuristic above. Fall back to a severity ranking so the
        # training pipeline remains usable for demos and local experiments.
        severity_score = (
            info["OAHI"].fillna(info["OAHI"].median())
            + info["AHI"].fillna(info["AHI"].median())
            + 0.5 * info["Arousal Index"].fillna(info["Arousal Index"].median())
            + 10 * apnea_flags.astype(int)
        )
        positive_count = min(max(1, len(info) // 2), len(info) - 1)
        return (severity_score.rank(method="first", ascending=False) <= positive_count).astype(int)

    def load_participant_info(self) -> pd.DataFrame:
        info = pd.read_csv(self.participant_csv)
        info.columns = [c.strip().replace("\ufeff", "") for c in info.columns]
        info["SID"] = info["SID"].astype(str).str.strip()

        for col in ["AGE", "BMI", "OAHI", "AHI", "Arousal Index"]:
            info[col] = self._safe_numeric(info[col])
        info["Mean_SaO2"] = self._safe_numeric(info["Mean_SaO2"])

        info["sleep_deprivation_label"] = self._build_sleep_deprivation_label(info)

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
        missing_plot_path = outdir / "eda_missing_values.png"
        target_plot_path = outdir / "eda_target_distribution.png"
        correlation_plot_path = outdir / "eda_correlation_heatmap.png"
        clinical_plot_path = outdir / "eda_clinical_features.png"

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

        self._plot_missing_values(missing, missing_plot_path)
        self._plot_target_distribution(train_df, target_plot_path)
        self._plot_correlation_heatmap(train_df, correlation_plot_path)
        self._plot_clinical_features(train_df, clinical_plot_path)

        return {
            "overview_csv": str(overview_path),
            "missing_csv": str(missing_path),
            "correlation_csv": str(correlation_path),
            "missing_png": str(missing_plot_path),
            "target_distribution_png": str(target_plot_path),
            "correlation_heatmap_png": str(correlation_plot_path),
            "clinical_features_png": str(clinical_plot_path),
        }

    @staticmethod
    def _save_figure(fig: plt.Figure, output_path: Path) -> None:
        fig.tight_layout()
        fig.savefig(output_path, dpi=160, bbox_inches="tight")
        plt.close(fig)

    def _plot_missing_values(self, missing_df: pd.DataFrame, output_path: Path) -> None:
        top_missing = missing_df.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(top_missing))))
        ax.barh(top_missing["column"], top_missing["missing_percent"], color="#c96f3c")
        ax.set_xlabel("Missing Percentage")
        ax.set_ylabel("Column")
        ax.set_title("Top Missing Values")
        self._save_figure(fig, output_path)

    def _plot_target_distribution(self, train_df: pd.DataFrame, output_path: Path) -> None:
        labels = train_df["sleep_deprivation_label"].astype(int).value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(["0", "1"], [labels.get(0, 0), labels.get(1, 0)], color=["#4c78a8", "#d14a61"])
        ax.set_xlabel("Sleep Deprivation Label")
        ax.set_ylabel("Count")
        ax.set_title("Target Class Distribution")
        self._save_figure(fig, output_path)

    def _plot_correlation_heatmap(self, train_df: pd.DataFrame, output_path: Path) -> None:
        candidate_cols = [
            "AGE",
            "BMI",
            "OAHI",
            "AHI",
            "Arousal Index",
            "Mean_SaO2",
            "event_rate",
            "HR_mean",
            "EDA_mean",
            "TEMP_mean",
            "sleep_deprivation_label",
        ]
        plot_cols = [col for col in candidate_cols if col in train_df.columns]
        corr = train_df[plot_cols].corr(numeric_only=True)

        fig, ax = plt.subplots(figsize=(8, 6))
        image = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(plot_cols)))
        ax.set_yticks(range(len(plot_cols)))
        ax.set_xticklabels(plot_cols, rotation=45, ha="right")
        ax.set_yticklabels(plot_cols)
        ax.set_title("Correlation Heatmap")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        self._save_figure(fig, output_path)

    def _plot_clinical_features(self, train_df: pd.DataFrame, output_path: Path) -> None:
        plot_cols = [col for col in ["BMI", "OAHI", "AHI", "Arousal Index", "Mean_SaO2"] if col in train_df.columns]
        fig, axes = plt.subplots(2, 3, figsize=(12, 7))
        axes_flat = axes.flatten()

        for ax, col in zip(axes_flat, plot_cols):
            ax.hist(train_df[col].dropna(), bins=min(8, max(3, train_df[col].nunique())), color="#5f9e6e", edgecolor="white")
            ax.set_title(col)
            ax.set_xlabel("Value")
            ax.set_ylabel("Count")

        for ax in axes_flat[len(plot_cols):]:
            ax.axis("off")

        fig.suptitle("Clinical Feature Distributions")
        self._save_figure(fig, output_path)

    def build_single_prediction_row(self, sensor_csv: Path, sid: str) -> pd.DataFrame:
        participant = self.load_participant_info()
        row = participant.loc[participant["SID"] == sid]
        if row.empty:
            raise ValueError(f"SID {sid} not found in participant info")

        features = self._aggregate_sensor_file(Path(sensor_csv))
        merged = dict(row.iloc[0])
        merged.update(features)
        return pd.DataFrame([merged])
