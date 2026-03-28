from __future__ import annotations

from typing import Optional

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import AdaBoostClassifier, ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

from .base_model import BaseSleepModel


class SklearnSleepModel(BaseSleepModel):
    def __init__(self, model_name: str, estimator):
        super().__init__(model_name)
        self.estimator = estimator
        self.pipeline: Optional[Pipeline] = None

    @staticmethod
    def build_preprocessor(X) -> ColumnTransformer:
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
        pre = self.build_preprocessor(X_train)
        self.pipeline = Pipeline([("preprocessor", pre), ("model", self.estimator)])
        self.pipeline.fit(X_train, y_train)

    def predict(self, X_test):
        return self.pipeline.predict(X_test)

    def predict_proba(self, X_test) -> Optional[np.ndarray]:
        if hasattr(self.pipeline, "predict_proba"):
            return self.pipeline.predict_proba(X_test)[:, 1]
        return None


class LogisticSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("logistic_regression", LogisticRegression(max_iter=1000))


class RandomForestSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("random_forest", RandomForestClassifier(n_estimators=300, random_state=42))


class ExtraTreesSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("extra_trees", ExtraTreesClassifier(n_estimators=300, random_state=42))


class AdaBoostSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("adaboost", AdaBoostClassifier(random_state=42))


class SVCSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("svc_rbf", SVC(kernel="rbf", probability=True, random_state=42))


class KNNSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("knn", KNeighborsClassifier(n_neighbors=3))


class MLPSleepModel(SklearnSleepModel):
    def __init__(self):
        super().__init__("mlp_classifier", MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=800, random_state=42))
