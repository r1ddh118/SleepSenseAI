# Sleep Detection AI Model

This project uses an **OOP-based multi-file architecture** for sleep analysis model training and prediction.

## Architecture
- `src/data_processor.py`
  - `SleepDataProcessor` for raw CSV loading, feature extraction, and participant merge
- `src/preprocessing.py`
  - `SleepPreprocessor` dedicated preprocessing stage (first step in pipeline)
  - saves processed training/inference CSVs before modeling
- `src/models/sklearn_models.py`
  - one class per sklearn algorithm
- `src/models/tensorflow_ann_model.py`
  - TensorFlow ANN model class
- `src/trainer.py`
  - `SleepModelTrainer` for training/comparison, best-model storage, and prediction CSV output
- `src/main.py`
  - main CLI that connects all files in order:
    1) preprocess data
    2) run EDA
    3) train 8 models
    4) store best model
    5) run prediction to output CSV

## Models compared (8 total)
1. Logistic Regression
2. Random Forest
3. Extra Trees
4. AdaBoost
5. SVC (RBF)
6. KNN
7. MLP (sklearn)
8. TensorFlow ANN

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pandas numpy scikit-learn tensorflow
```

## Train (Preprocessing -> EDA -> Training)
```bash
python -m src.main train \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --outdir artifacts
```

Training outputs:
- `artifacts/preprocessed_raw_features.csv`
- `artifacts/preprocessed_training_data.csv`
- `artifacts/eda_overview.csv`
- `artifacts/eda_missing_values.csv`
- `artifacts/eda_numeric_correlation.csv`
- `artifacts/model_leaderboard.csv`
- `artifacts/training_summary.json`
- `artifacts/best_model.pkl`
- `artifacts/best_tensorflow_ann.keras` (only if ANN is best)

## Predict (Preprocessing -> Predict -> Output CSV)
```bash
python -m src.main predict \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --model-pickle artifacts/best_model.pkl \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002 \
  --output-csv artifacts/predictions.csv
```

Prediction outputs:
- `artifacts/preprocessed_inference_<SID>.csv`
- `artifacts/predictions.csv` containing:
  - `prediction` (0/1)
  - `probability_sleep_deprivation`
  - `prediction_label`

## Notes
- Current training labels are heuristic from participant fields (OAHI/AHI/Arousal Index + disorder keywords).
- Replace with clinically validated labels for production.
