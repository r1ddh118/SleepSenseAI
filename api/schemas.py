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


# ─── PySpark-era schemas ────────────────────────────────────────────────────

class ManualSleepSessionCreate(BaseModel):
    """Manual sleep entry submitted from the frontend form."""
    user_id: str                          # e.g. "U034"
    date: str                             # YYYY-MM-DD
    bed_time: Optional[str] = None        # HH:MM or "Unknown"
    sleep_onset: Optional[str] = None
    wake_time: Optional[str] = None
    sleep_duration_hours: Optional[float] = None
    awakenings: Optional[int] = None
    caffeine_mg: Optional[float] = None
    screen_time_min: Optional[float] = None
    exercise_minutes: Optional[float] = None
    stress_level: Optional[float] = None  # 1–10
    nap_minutes: Optional[float] = None
    avg_hr: Optional[float] = None        # if available (wearable)
    avg_spo2: Optional[float] = None
    notes: Optional[str] = None


class ManualSleepSessionOut(BaseModel):
    id: int
    session_id: str
    user_str_id: Optional[str]
    date: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SleepAnalyticsOut(BaseModel):
    """Spark-computed analytics for a session."""
    session_id: str
    date: Optional[str]
    sleep_score: Optional[float]
    sleep_category: Optional[str]
    sleep_efficiency: Optional[float]
    sleep_duration_hours: Optional[float]
    n3_fraction: Optional[float]
    rem_fraction: Optional[float]
    wake_fraction: Optional[float]
    avg_hr: Optional[float]
    hr_std: Optional[float]
    event_rate: Optional[float]
    sleep_score_7d_avg: Optional[float]
    sleep_score_14d_avg: Optional[float]
    duration_7d_avg: Optional[float]
    risk_level: Optional[str]
    risk_json: Optional[dict] = None
    recommendations: Optional[list] = None
    disclaimer: str = (
        "This sleep score is an academic analytics metric — NOT clinically validated. "
        "Consult a qualified healthcare professional for clinical assessment."
    )
    model_config = {"from_attributes": True}


class DoctorAlertOut(BaseModel):
    id: int
    patient_str_id: Optional[str]
    session_id: Optional[str]
    severity: str
    reason: Optional[str]
    evidence_json: Optional[dict] = None
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertAcknowledgeRequest(BaseModel):
    note: Optional[str] = None


class DoctorReportOut(BaseModel):
    id: int
    patient_str_id: Optional[str]
    session_id: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]
    file_path: Optional[str]
    format: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SleepTrendPoint(BaseModel):
    date: str
    sleep_score: Optional[float]
    sleep_score_7d_avg: Optional[float]
    sleep_duration_hours: Optional[float]
    sleep_efficiency: Optional[float]
    n3_fraction: Optional[float]
    rem_fraction: Optional[float]
    risk_level: Optional[str]


class UserSleepTrendOut(BaseModel):
    user_id: str
    nights: List[SleepTrendPoint]
