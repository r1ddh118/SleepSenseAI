#!/usr/bin/env python3
"""
7-night rolling-window LSTM for longitudinal risk (TensorFlow/Keras).

Expects CSV columns: SID, night_index, sleep_deprivation_label, and feature columns below.

Usage:
  python advanced/longitudinal_model.py --features artifacts/all_nights_features.csv --out artifacts/
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("longitudinal_model")
logging.basicConfig(level=logging.INFO)

WINDOW = 7
FEATURE_COLS = [
    "HR_mean",
    "EDA_std",
    "BVP_mean",
    "TEMP_mean",
    "event_rate",
    "sleep_stage_pct_N3",
    "sleep_stage_pct_R",
    "sleep_stage_pct_W",
]


def build_sequences(df: pd.DataFrame, window: int = WINDOW):
    X_list, y_list = [], []
    for _, group in df.groupby("SID"):
        group = group.sort_values("night_index").reset_index(drop=True)
        if len(group) < window + 1:
            continue
        missing = [c for c in FEATURE_COLS if c not in group.columns]
        if missing:
            continue
        for i in range(window, len(group)):
            X_list.append(group[FEATURE_COLS].iloc[i - window : i].values)
            y_list.append(int(group["sleep_deprivation_label"].iloc[i]))
    if not X_list:
        return np.array([]), np.array([])
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)


def train_lstm(features_csv: str, out_dir: str):
    df = pd.read_csv(features_csv)
    need = FEATURE_COLS + ["sleep_deprivation_label", "SID", "night_index"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise ValueError(f"CSV missing columns: {miss}")

    df = df.dropna(subset=FEATURE_COLS + ["sleep_deprivation_label"])

    scaler = StandardScaler()
    df[FEATURE_COLS] = scaler.fit_transform(df[FEATURE_COLS])

    X, y = build_sequences(df)
    if len(X) == 0:
        raise ValueError("No sequences built — need multiple nights per SID.")

    logger.info("Sequences: X=%s y=%s positive_rate=%.2f%%", X.shape, y.shape, 100 * y.mean())

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    model = tf.keras.Sequential(
        [
            tf.keras.layers.LSTM(64, input_shape=(WINDOW, len(FEATURE_COLS)), return_sequences=False),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ]
    )

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(patience=3),
    ]

    model.fit(
        X_train,
        y_train,
        epochs=50,
        batch_size=16,
        validation_data=(X_test, y_test),
        callbacks=callbacks,
        verbose=1,
    )

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    model.save(out_path / "longitudinal_lstm.keras")
    logger.info("Saved %s", out_path / "longitudinal_lstm.keras")

    results = model.evaluate(X_test, y_test, verbose=0)
    logger.info("Test accuracy: %.4f, AUC: %.4f", results[1], results[2])
    return model


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--features", required=True)
    p.add_argument("--out", default="artifacts/")
    args = p.parse_args()
    train_lstm(args.features, args.out)


if __name__ == "__main__":
    main()
