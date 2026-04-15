"""Pydantic v2 request/response models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "patient"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionCreate(BaseModel):
    sid: str
    duration_seconds: int = 28800
    notes: Optional[str] = None


class SessionUpdate(BaseModel):
    status: Optional[str] = None
    sensor_csv_path: Optional[str] = None
    notes: Optional[str] = None


class SessionOut(BaseModel):
    id: int
    sid: str
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PredictRequest(BaseModel):
    sensor_csv: Optional[str] = None
    model_pickle: Optional[str] = None


class ShapFeature(BaseModel):
    feature: str
    impact: float


class Recommendation(BaseModel):
    code: str
    message: str
    severity: str


class PredictionOut(BaseModel):
    session_id: int
    sid: str
    prediction: int
    probability: float
    label: str
    model_name: Optional[str]
    shap_top_features: Optional[List[ShapFeature]]
    recommendations: Optional[List[Recommendation]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    model_name: str
    accuracy: Optional[float]
    f1: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    roc_auc: Optional[float]


class TrainRequest(BaseModel):
    dataset_path: Optional[str] = None
    force_retrain: bool = False


class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class HealthOut(BaseModel):
    status: str
    edge_device: str
    database: str
    redis: str
    version: str = "1.0.0"
