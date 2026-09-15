"""SQLAlchemy ORM: User, Session, Prediction, ManualSleepSession, SleepAnalytics, DoctorAlert, DoctorReport."""

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
    manual_sessions = relationship("ManualSleepSession", back_populates="user")


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


# ─── New PySpark-era models ─────────────────────────────────────────────────

class ManualSleepSession(Base):
    """Raw manual sleep entry — saved immediately, processed async by Celery/Spark."""
    __tablename__ = "manual_sleep_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_str_id = Column(String, index=True, nullable=True)   # e.g. "U034"
    date = Column(String, nullable=True)                       # YYYY-MM-DD
    bed_time = Column(String, nullable=True)                   # HH:MM
    sleep_onset = Column(String, nullable=True)
    wake_time = Column(String, nullable=True)
    sleep_duration_hours = Column(Float, nullable=True)
    awakenings = Column(Integer, nullable=True)
    caffeine_mg = Column(Float, nullable=True)
    screen_time_min = Column(Float, nullable=True)
    exercise_minutes = Column(Float, nullable=True)
    stress_level = Column(Float, nullable=True)
    nap_minutes = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    avg_spo2 = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    raw_csv_path = Column(String, nullable=True)    # written to data/raw/
    status = Column(String, default="PROCESSING")   # PROCESSING | COMPLETE | FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="manual_sessions")
    analytics = relationship("SleepAnalytics", back_populates="manual_session", uselist=False)


class SleepAnalytics(Base):
    """Spark-computed analytics results for a session — written by Celery task after pipeline."""
    __tablename__ = "sleep_analytics"

    id = Column(Integer, primary_key=True, index=True)
    manual_session_id = Column(Integer, ForeignKey("manual_sleep_sessions.id"), nullable=True)
    user_str_id = Column(String, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)
    date = Column(String, nullable=True)

    sleep_score = Column(Float, nullable=True)
    sleep_category = Column(String, nullable=True)
    sleep_efficiency = Column(Float, nullable=True)
    sleep_duration_hours = Column(Float, nullable=True)
    n3_fraction = Column(Float, nullable=True)
    rem_fraction = Column(Float, nullable=True)
    wake_fraction = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    hr_std = Column(Float, nullable=True)
    event_rate = Column(Float, nullable=True)

    # Longitudinal
    sleep_score_7d_avg = Column(Float, nullable=True)
    sleep_score_14d_avg = Column(Float, nullable=True)
    duration_7d_avg = Column(Float, nullable=True)

    risk_level = Column(String, nullable=True)          # LOW | MODERATE | HIGH
    risk_json = Column(Text, nullable=True)             # full risk_flags JSON
    recommendations_json = Column(Text, nullable=True)

    spark_job_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    manual_session = relationship("ManualSleepSession", back_populates="analytics")


class DoctorAlert(Base):
    """Alert created when persistent sleep risk is detected across multiple nights."""
    __tablename__ = "doctor_alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_str_id = Column(String, index=True, nullable=True)   # e.g. "U034"
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, nullable=True)
    severity = Column(String, nullable=False)          # HIGH | MODERATE
    reason = Column(Text, nullable=True)               # primary reason string
    evidence_json = Column(Text, nullable=True)        # structured evidence dict
    status = Column(String, default="OPEN")            # OPEN | ACKNOWLEDGED | RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])


class DoctorReport(Base):
    """Generated report file for a patient."""
    __tablename__ = "doctor_reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_str_id = Column(String, index=True, nullable=True)
    session_id = Column(String, nullable=True)
    period_start = Column(String, nullable=True)   # YYYY-MM-DD
    period_end = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    format = Column(String, nullable=True)         # json | csv | html | pdf
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("User", foreign_keys=[patient_id])
