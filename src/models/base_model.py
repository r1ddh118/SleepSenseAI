from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ModelMetrics:
    model_name: str
    accuracy: float
    f1: float
    precision: float
    recall: float
    roc_auc: float


class BaseSleepModel(ABC):
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def fit(self, X_train, y_train) -> None:
        ...

    @abstractmethod
    def predict(self, X_test):
        ...

    @abstractmethod
    def predict_proba(self, X_test) -> Optional[np.ndarray]:
        ...
