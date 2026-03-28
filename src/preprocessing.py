from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

try:
    from .data_processor import SleepDataProcessor
except ImportError:  # pragma: no cover - supports direct script execution
    from data_processor import SleepDataProcessor


class SleepPreprocessor:
    """Dedicated preprocessing stage that converts raw CSVs into model-ready CSVs."""

    def __init__(self, dataset_dir: Path, participant_csv: Path, outdir: Path):
        self.dataset_dir = Path(dataset_dir)
        self.participant_csv = Path(participant_csv)
        self.outdir = Path(outdir)
        self.processor = SleepDataProcessor(dataset_dir=self.dataset_dir, participant_csv=self.participant_csv)

    def training_output_paths(self) -> Dict[str, str]:
        raw_path = self.outdir / "preprocessed_raw_features.csv"
        processed_path = self.outdir / "preprocessed_training_data.csv"
        return {
            "raw_features_csv": str(raw_path),
            "processed_training_csv": str(processed_path),
        }

    def _clean_feature_table(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()

        numeric_cols = cleaned.select_dtypes(include=["number"]).columns
        categorical_cols = [c for c in cleaned.columns if c not in numeric_cols]

        for col in numeric_cols:
            cleaned[col] = cleaned[col].fillna(cleaned[col].median())

        for col in categorical_cols:
            cleaned[col] = cleaned[col].fillna("Unknown")

        return cleaned

    def preprocess_training_data(self) -> Dict[str, str]:
        self.outdir.mkdir(parents=True, exist_ok=True)
        raw_features = self.processor.build_feature_table()
        cleaned = self._clean_feature_table(raw_features)

        raw_path = self.outdir / "preprocessed_raw_features.csv"
        processed_path = self.outdir / "preprocessed_training_data.csv"

        raw_features.to_csv(raw_path, index=False)
        cleaned.to_csv(processed_path, index=False)

        return self.training_output_paths()

    def load_preprocessed_training_data(self) -> pd.DataFrame:
        processed_path = Path(self.training_output_paths()["processed_training_csv"])
        if not processed_path.exists():
            raise FileNotFoundError(
                f"Preprocessed training data not found at {processed_path}. "
                "Run the 'preprocess' command first."
            )
        return pd.read_csv(processed_path)

    def preprocess_prediction_data(self, sensor_csv: Path, sid: str, output_csv: Path | None = None) -> pd.DataFrame:
        row_df = self.processor.build_single_prediction_row(sensor_csv=sensor_csv, sid=sid)
        cleaned = self._clean_feature_table(row_df)

        if output_csv is not None:
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            cleaned.to_csv(output_csv, index=False)

        return cleaned

    def run_eda_on_processed(self, processed_df: pd.DataFrame) -> Dict[str, str]:
        return self.processor.run_eda(processed_df, self.outdir)
