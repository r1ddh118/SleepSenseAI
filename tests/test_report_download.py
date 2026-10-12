"""Phase 5 Gate Verification: Automated test for multi-format report download and EDA verification."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from database import init_db
init_db()

import pytest
from fastapi.testclient import TestClient
from main import app
from config import REPO_ROOT

client = TestClient(app)


def test_session_report_all_four_formats_download_and_eda():
    """Verify that GET /api/v1/sessions/{sid}/report supports json, csv, html, and pdf with Content-Disposition attachment."""
    # First ensure a valid processed night session exists
    sid = "GATE_P5_REPORT_TEST"
    sample_file = REPO_ROOT / "data" / "sample_data" / "healthy_night.csv"
    assert sample_file.exists(), "Sample test file healthy_night.csv must exist"

    with open(sample_file, "rb") as f:
        resp_upload = client.post(
            "/api/v1/sessions/upload",
            files={"file": ("healthy_night.csv", f, "text/csv")},
            data={
                "user_id": "U001",
                "session_id": sid,
                "notes": "Phase 5 Report Download Test",
                "inline": "true",
            },
        )
    assert resp_upload.status_code == 200

    # 1. Test JSON format
    resp_json = client.get(f"/api/v1/sessions/{sid}/report?format=json")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"].startswith("application/json")
    assert "attachment" in resp_json.headers["content-disposition"]
    assert f"sleepsense_report_{sid}.json" in resp_json.headers["content-disposition"]
    data = resp_json.json()
    assert data["session_id"] == sid
    assert "sections" in data
    assert "eda_assessment" in data["sections"]
    assert "sensor_biometrics" in data["sections"]
    assert data["sections"]["eda_assessment"]["tonic_eda_mean_us"] is not None

    # 2. Test CSV format
    resp_csv = client.get(f"/api/v1/sessions/{sid}/report?format=csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "attachment" in resp_csv.headers["content-disposition"]
    assert f"sleepsense_report_{sid}.csv" in resp_csv.headers["content-disposition"]
    csv_rows = list(csv.reader(StringIO(resp_csv.text)))
    assert len(csv_rows) > 10
    sections_found = {row[0] for row in csv_rows[1:]}
    assert "eda_assessment" in sections_found
    assert "sleep_summary" in sections_found
    assert "risk_assessment" in sections_found

    # 3. Test HTML format
    resp_html = client.get(f"/api/v1/sessions/{sid}/report?format=html")
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]
    assert "attachment" in resp_html.headers["content-disposition"]
    assert f"sleepsense_report_{sid}.html" in resp_html.headers["content-disposition"]
    html_text = resp_html.text
    assert "SleepSense AI Clinical Report" in html_text
    assert "Electrodermal Activity (EDA)" in html_text
    assert "Sensor Biometrics" in html_text
    assert "not clinically validated" in html_text

    # 4. Test PDF format
    resp_pdf = client.get(f"/api/v1/sessions/{sid}/report?format=pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert "attachment" in resp_pdf.headers["content-disposition"]
    assert f"sleepsense_report_{sid}.pdf" in resp_pdf.headers["content-disposition"]
    pdf_bytes = resp_pdf.content
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
