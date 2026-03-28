from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .preprocessing import SleepPreprocessor
from .trainer import SleepModelTrainer


class SleepSenseApp:
    def __init__(self, dataset_dir: Path, participant_csv: Path, outdir: Path):
        self.dataset_dir = Path(dataset_dir)
        self.participant_csv = Path(participant_csv)
        self.outdir = Path(outdir)
        self.preprocessor = SleepPreprocessor(
            dataset_dir=self.dataset_dir,
            participant_csv=self.participant_csv,
            outdir=self.outdir,
        )
        self.trainer = SleepModelTrainer()

    def train(self) -> dict:
        preprocess_paths = self.preprocessor.preprocess_training_data()
        processed_df = pd.read_csv(preprocess_paths["processed_training_csv"])
        eda_paths = self.preprocessor.run_eda_on_processed(processed_df)
        train_paths = self.trainer.train_and_select(processed_df, self.outdir)

        return {
            "preprocessing": preprocess_paths,
            "eda": eda_paths,
            "training": train_paths,
        }

    def predict(self, model_pickle: Path, sensor_csv: Path, sid: str, output_csv: Path) -> dict:
        preprocessed_inference_csv = self.outdir / f"preprocessed_inference_{sid}.csv"
        input_df = self.preprocessor.preprocess_prediction_data(
            sensor_csv=sensor_csv,
            sid=sid,
            output_csv=preprocessed_inference_csv,
        )
        prediction_csv = self.trainer.predict_to_csv(
            bundle_path=model_pickle,
            input_df=input_df,
            output_csv=output_csv,
        )
        return {
            "preprocessed_inference_csv": str(preprocessed_inference_csv),
            "prediction_csv": str(prediction_csv),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SleepSense OOP model trainer and predictor")
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train", help="Preprocess + EDA + train 8 models + save best model")
    train.add_argument("--dataset-dir", type=Path, default=Path("datasets"))
    train.add_argument("--participant-csv", type=Path, default=Path("datasets/participant_info.csv"))
    train.add_argument("--outdir", type=Path, default=Path("artifacts"))

    pred = sub.add_parser("predict", help="Preprocess input sensor CSV + predict + save output CSV")
    pred.add_argument("--dataset-dir", type=Path, default=Path("datasets"))
    pred.add_argument("--participant-csv", type=Path, default=Path("datasets/participant_info.csv"))
    pred.add_argument("--outdir", type=Path, default=Path("artifacts"))
    pred.add_argument("--model-pickle", type=Path, default=Path("artifacts/best_model.pkl"))
    pred.add_argument("--sensor-csv", type=Path, required=True)
    pred.add_argument("--sid", type=str, required=True)
    pred.add_argument("--output-csv", type=Path, default=Path("artifacts/predictions.csv"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    app = SleepSenseApp(args.dataset_dir, args.participant_csv, args.outdir)

    if args.command == "train":
        result = app.train()
        print(json.dumps(result, indent=2))
    elif args.command == "predict":
        result = app.predict(
            model_pickle=args.model_pickle,
            sensor_csv=args.sensor_csv,
            sid=args.sid,
            output_csv=args.output_csv,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
