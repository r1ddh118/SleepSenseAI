from __future__ import annotations

import os
from typing import Optional

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf

from .base_model import BaseSleepModel


class TensorFlowANNSleepModel(BaseSleepModel):
    def __init__(self, epochs: int = 80, batch_size: int = 16):
        super().__init__("tensorflow_ann")
        self.epochs = epochs
        self.batch_size = batch_size
        self.preprocessor: Optional[ColumnTransformer] = None
        self.model: Optional[tf.keras.Model] = None

    @staticmethod
    def _build_preprocessor(X) -> ColumnTransformer:
        categorical_cols = [c for c in X.columns if X[c].dtype == "object"]
        numeric_cols = [c for c in X.columns if c not in categorical_cols]

        return ColumnTransformer(
            transformers=[
                (
                    "num",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]),
                    numeric_cols,
                ),
                (
                    "cat",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]),
                    categorical_cols,
                ),
            ]
        )

    def fit(self, X_train, y_train) -> None:
        self.preprocessor = self._build_preprocessor(X_train)
        X_proc = self.preprocessor.fit_transform(X_train)
        if hasattr(X_proc, "toarray"):
            X_proc = X_proc.toarray()

        self.model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(X_proc.shape[1],)),
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.Dropout(0.25),
                tf.keras.layers.Dense(32, activation="relu"),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )
        self.model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
        self.model.fit(
            X_proc,
            y_train.to_numpy(),
            validation_split=0.25,
            epochs=self.epochs,
            batch_size=self.batch_size,
            verbose=0,
        )

    def _transform(self, X):
        X_proc = self.preprocessor.transform(X)
        if hasattr(X_proc, "toarray"):
            X_proc = X_proc.toarray()
        return X_proc

    def predict_proba(self, X_test) -> Optional[np.ndarray]:
        X_proc = self._transform(X_test)
        return self.model.predict(X_proc, verbose=0).ravel()

    def predict(self, X_test):
        proba = self.predict_proba(X_test)
        return (proba >= 0.5).astype(int)
