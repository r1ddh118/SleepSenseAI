"""Phase 6 Gate Verification: Doctor portal full report and patient assignment authorization tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from database import init_db, get_db, SessionLocal
init_db()

import pytest
from fastapi.testclient import TestClient
from main import app
from config import REPO_ROOT
from auth import create_access_token, hash_password
from models_db import User, DoctorPatientAssignment, NightSession

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_users_and_assignments():
    """Setup a doctor, a patient, another doctor, and assignments."""
    db = SessionLocal()
    try:
        # 1. Clean existing test users if any
        db.query(DoctorPatientAssignment).filter(DoctorPatientAssignment.patient_uid == "p6_patient_01").delete()
        db.query(User).filter(User.email.in_(["p6_doc1@hospital.com", "p6_doc2@hospital.com", "p6_patient_01@hospital.com"])).delete()
        db.commit()

        # 2. Create Doctor 1 (Assigned)
        doc1 = User(
            email="p6_doc1@hospital.com",
            hashed_password=hash_password("docpass123"),
            role="doctor",
            is_active=True,
        )
        # 3. Create Doctor 2 (Unassigned)
        doc2 = User(
            email="p6_doc2@hospital.com",
            hashed_password=hash_password("docpass123"),
            role="doctor",
            is_active=True,
        )
        # 4. Create Patient
        patient = User(
            email="p6_patient_01@hospital.com",
            hashed_password=hash_password("patpass123"),
            role="patient",
            is_active=True,
        )
        db.add_all([doc1, doc2, patient])
        db.commit()
        db.refresh(doc1)
        db.refresh(doc2)
        db.refresh(patient)

        # 5. Create Doctor-Patient Assignment for doc1
        assignment = DoctorPatientAssignment(
            doctor_id=doc1.id,
            patient_uid="p6_patient_01",
        )
        db.add(assignment)
        db.commit()

        doc1_token = create_access_token({"sub": doc1.email, "role": "doctor"})
        doc2_token = create_access_token({"sub": doc2.email, "role": "doctor"})
        patient_token = create_access_token({"sub": patient.email, "role": "patient"})

        return {
            "doc1_token": doc1_token,
            "doc2_token": doc2_token,
            "patient_token": patient_token,
            "patient_uid": "p6_patient_01",
            "doc1_id": doc1.id,
        }
    finally:
        db.close()


def test_doctor_portal_full_report_and_authorization_gate(setup_users_and_assignments):
    """Gate test:
    1. A doctor sees every section the patient sees, plus doctor-only ones.
    2. A non-doctor (patient) gets 403 on doctor routes.
    3. An unassigned doctor gets 403 on patient sessions.
    4. Doctor session list and full multi-format reports work as specified in Blueprint Section 8.
    """
    tokens = setup_users_and_assignments
    doc1_auth = {"Authorization": f"Bearer {tokens['doc1_token']}"}
    doc2_auth = {"Authorization": f"Bearer {tokens['doc2_token']}"}
    patient_auth = {"Authorization": f"Bearer {tokens['patient_token']}"}
    p_uid = tokens["patient_uid"]

    # 1. Create a session for this patient
    test_sid = "GATE_P6_DOCTOR_SESSION_01"
    sample_file = REPO_ROOT / "data" / "sample_data" / "healthy_night.csv"
    assert sample_file.exists(), "Sample test file healthy_night.csv must exist"

    with open(sample_file, "rb") as f:
        resp_upload = client.post(
            "/api/v1/sessions/upload",
            files={"file": ("healthy_night.csv", f, "text/csv")},
            data={
                "user_id": p_uid,
                "session_id": test_sid,
                "notes": "Phase 6 Doctor Clinical Session",
                "inline": "true",
            },
        )
    assert resp_upload.status_code == 200

    # 2. Security Test: Patient calling doctor route gets 403 Forbidden
    resp_pat_list = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions", headers=patient_auth)
    assert resp_pat_list.status_code == 403, "Non-doctor must get 403 Forbidden on doctor routes"

    resp_pat_report = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions/{test_sid}/report", headers=patient_auth)
    assert resp_pat_report.status_code == 403, "Non-doctor must get 403 Forbidden on doctor report route"

    # 3. Security Test: Unassigned doctor gets 403 Forbidden
    resp_unassigned = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions", headers=doc2_auth)
    assert resp_unassigned.status_code == 403, "Unassigned doctor must get 403 Forbidden"

    # 4. Assigned Doctor can list patient sessions
    resp_doc_list = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions", headers=doc1_auth)
    assert resp_doc_list.status_code == 200
    sessions_list = resp_doc_list.json()
    assert isinstance(sessions_list, list)
    assert any(s["session_id"] == test_sid for s in sessions_list)

    # 5. Assigned Doctor sees every section the patient sees, plus doctor-only sections
    resp_doc_report = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions/{test_sid}/report?format=json", headers=doc1_auth)
    assert resp_doc_report.status_code == 200
    report_data = resp_doc_report.json()

    assert report_data["session_id"] == test_sid
    sections = report_data["sections"]

    # Shared sections (Patient + Doctor):
    assert "sleep_summary" in sections
    assert "sensor_biometrics" in sections
    assert "eda_assessment" in sections
    assert "risk_assessment" in sections
    assert "longitudinal_trend" in sections
    assert "recommendations" in sections
    assert "disclaimer" in sections

    # Doctor-only sections (Blueprint Section 8):
    assert "doctor_clinical_notes" in sections
    assert "data_quality" in sections
    assert "events" in sections
    assert "stages" in sections

    assert sections["doctor_clinical_notes"]["compliance_status"] is not None
    assert sections["data_quality"]["quality_grade"] is not None
    assert "micro_arousals_total" in sections["events"]
    assert "wake_minutes" in sections["stages"]

    # 6. Verify multi-format downloads for doctor endpoint
    # HTML
    resp_doc_html = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions/{test_sid}/report?format=html", headers=doc1_auth)
    assert resp_doc_html.status_code == 200
    assert "text/html" in resp_doc_html.headers["content-type"]
    assert "Clinical Notes" in resp_doc_html.text
    assert "Data Quality" in resp_doc_html.text

    # PDF
    resp_doc_pdf = client.get(f"/api/v1/doctor/patients/{p_uid}/sessions/{test_sid}/report?format=pdf", headers=doc1_auth)
    assert resp_doc_pdf.status_code == 200
    assert resp_doc_pdf.headers["content-type"] == "application/pdf"
    assert resp_doc_pdf.content.startswith(b"%PDF")
