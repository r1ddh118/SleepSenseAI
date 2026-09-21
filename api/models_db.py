"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="patient")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    sid = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="created")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    sensor_csv_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    predictions = relationship("Prediction", back_populates="session")
    manual_sleep_session = relationship("ManualSleepSession", back_populates="session", uselist=False)
    sleep_analytics = relationship("SleepAnalytics", back_populates="session", uselist=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    model_name = Column(String, nullable=True)
    prediction = Column(Integer, nullable=True)
    probability = Column(Float, nullable=True)
    label = Column(String, nullable=True)
    shap_features = Column(Text, nullable=True)
    recommendations_json = Column(Text, nullable=True)
    predictions_csv_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="predictions")


class DoctorAlert(Base):
    __tablename__ = "doctor_alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, index=True, nullable=False)
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=False)
    status = Column(String, default="OPEN", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    doctor = relationship("User")


class ManualSleepSession(Base):
    __tablename__ = "manual_sleep_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)
    patient_uid = Column(String, index=True, nullable=False)
    date = Column(String, index=True, nullable=False)
    bed_time = Column(String, nullable=True)
    sleep_onset = Column(String, nullable=True)
    wake_time = Column(String, nullable=True)
    sleep_duration_hours = Column(Float, nullable=True)
    sleep_efficiency = Column(Float, nullable=True)
    n3_fraction = Column(Float, nullable=True)
    rem_fraction = Column(Float, nullable=True)
    wake_fraction = Column(Float, nullable=True)
    heart_rate = Column(Float, nullable=True)
    hr_std = Column(Float, nullable=True)
    movement_std = Column(Float, nullable=True)
    event_rate = Column(Float, nullable=True)
    spo2 = Column(Float, nullable=True)
    caffeine = Column(Integer, nullable=True)
    screen_time = Column(Integer, nullable=True)
    exercise_minutes = Column(Integer, nullable=True)
    stress_level = Column(Integer, nullable=True)
    nap_minutes = Column(Integer, nullable=True)
    awakenings = Column(Integer, nullable=True)
    raw_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="manual_sleep_session")


class SleepAnalytics(Base):
    __tablename__ = "sleep_analytics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)
    status = Column(String, default="PROCESSING", index=True)
    sleep_score = Column(Float, nullable=True)
    sleep_category = Column(String, nullable=True)
    sleep_efficiency = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    risk_json = Column(Text, nullable=True)
    recommendations_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    spark_job_id = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="sleep_analytics")
