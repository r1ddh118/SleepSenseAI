# SleepSense AI

SleepSense AI is a small end-to-end sleep analysis pipeline built around an OOP Python CLI. It turns raw participant and sensor CSV files into:

- preprocessed training data
- EDA tables and visualizations
- trained classification models
- prediction CSV outputs for new sensor files

The project is organized so preprocessing, EDA, training, and prediction can be run as separate steps.

## Project Structure

- `src/main.py`
  Main CLI entrypoint with `preprocess`, `eda`, `train`, and `predict` commands.
- `src/data_processor.py`
  Raw data loading, feature extraction, participant merge, label construction, and EDA output generation.
- `src/preprocessing.py`
  Cleans and saves training and inference-ready feature tables.
- `src/trainer.py`
  Trains multiple models, compares them, and saves the best model bundle.
- `src/models/sklearn_models.py`
  Scikit-learn model wrappers.
- `src/models/tensorflow_ann_model.py`
  TensorFlow ANN model wrapper.

## Dataset Inputs

Expected inputs:

- `datasets/participant_info.csv`
  Participant-level metadata and clinical columns such as `BMI`, `OAHI`, `AHI`, `Arousal Index`, and history/disorder fields.
- `datasets/compressed_*_whole_df.csv`
  Per-participant sensor/event CSV files. The filename must contain a participant ID like `S002`.

The pipeline merges sensor-derived features with participant metadata using `SID`.

## Models Compared

The trainer evaluates 8 models:

1. Logistic Regression
2. Random Forest
3. Extra Trees
4. AdaBoost
5. SVC (RBF)
6. KNN
7. MLP Classifier
8. TensorFlow ANN

## Installation

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

If you prefer manual installation:

```bash
pip install pandas numpy scikit-learn tensorflow matplotlib
```

## CLI Workflow

Recommended order:

```bash
python -m src.main preprocess
python -m src.main eda
python -m src.main train
```

You can inspect command help with:

```bash
python -m src.main -h
python -m src.main preprocess -h
python -m src.main eda -h
python -m src.main train -h
python -m src.main predict -h
```

## 1. Preprocess

Build and save model-ready training data from the raw dataset files.

```bash
python -m src.main preprocess \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --outdir artifacts
```

Outputs:

- `artifacts/preprocessed_raw_features.csv`
- `artifacts/preprocessed_training_data.csv`

## 2. EDA

Run exploratory data analysis from the saved preprocessed training CSV.

```bash
python -m src.main eda \
  --outdir artifacts
```

Outputs:

- `artifacts/eda_overview.csv`
- `artifacts/eda_missing_values.csv`
- `artifacts/eda_numeric_correlation.csv`
- `artifacts/eda_missing_values.png`
- `artifacts/eda_target_distribution.png`
- `artifacts/eda_correlation_heatmap.png`
- `artifacts/eda_clinical_features.png`

## 3. Train

Train all models using the saved preprocessed training CSV and store the best-performing model.

```bash
python -m src.main train \
  --outdir artifacts
```

Outputs:

- `artifacts/model_leaderboard.csv`
- `artifacts/training_summary.json`
- `artifacts/best_model.pkl`
- `artifacts/best_tensorflow_ann.keras`
  Only created when the TensorFlow ANN is selected as the best model.

## 4. Predict

Generate predictions for a new sensor CSV using the saved best model.

```bash
python -m src.main predict \
  --dataset-dir datasets \
  --participant-csv datasets/participant_info.csv \
  --model-pickle artifacts/best_model.pkl \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002 \
  --output-csv artifacts/predictions.csv
```

Outputs:

- `artifacts/preprocessed_inference_<SID>.csv`
- `artifacts/predictions.csv`

Prediction CSV columns include:

- `prediction`
- `probability_sleep_deprivation`
- `prediction_label`

## Notes on Labels

The project currently builds `sleep_deprivation_label` heuristically from participant clinical fields and history. On very small datasets, that heuristic can collapse into a single class; in that case the pipeline falls back to a severity-based split so local experiments and demos can still run.

This is useful for development, but it is not a substitute for clinically validated labels.

## Artifacts Directory

Most generated outputs are written to `artifacts/`. This directory is ignored by git, so you can rerun experiments without polluting version control.

## Common Issues

### `Need at least two target classes`

This means the training labels collapsed to one class. In the current project, a fallback label split is used for tiny datasets, but if this still happens, inspect:

- `artifacts/preprocessed_training_data.csv`
- `artifacts/eda_target_distribution.png`

### TensorFlow oneDNN / CUDA messages

Messages about oneDNN or missing CUDA devices are usually informational in this project. Training and inference can still run on CPU.

## Example End-to-End Run

```bash
python -m src.main preprocess
python -m src.main eda
python -m src.main train
python -m src.main predict \
  --sensor-csv datasets/compressed_S002_whole_df.csv \
  --sid S002
```
