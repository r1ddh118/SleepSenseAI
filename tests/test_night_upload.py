from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from database import init_db
init_db()

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_sample_data_list_and_download():
    resp_list = client.get("/api/v1/sample-data")
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert "samples" in data_list
    assert len(data_list["samples"]) >= 1

    sample_name = data_list["samples"][0]["name"]
    resp_file = client.get(f"/api/v1/sample-data/{sample_name}")
    assert resp_file.status_code == 200
    assert "Content-Disposition" in resp_file.headers
    assert sample_name in resp_file.headers["Content-Disposition"]


def test_post_session_upload_csv(tmp_path: Path):
    sample_csv = Path("data/sample_data/healthy_night.csv")
    if not sample_csv.exists():
        pytest.skip("Sample CSV not prepared yet")

    sid = "S_TEST_UPLOAD_001"
    with open(sample_csv, "rb") as f:
        resp = client.post(
            "/api/v1/sessions/upload",
            data={"user_id": "UTEST", "session_id": sid, "notes": "Test upload"},
            files={"file": ("healthy_night.csv", f, "text/csv")},
        )

    assert resp.status_code == 200
    res = resp.json()
    assert res["session_id"] == sid
    assert res["status"] in ["queued", "completed", "processing"]


def test_get_session_status_and_artifacts():
    sid = "S_U001_N01"

    # 1. Status
    resp_status = client.get(f"/api/v1/sessions/{sid}/status")
    assert resp_status.status_code in [200, 404]
    if resp_status.status_code == 200:
        assert resp_status.json()["session_id"] == sid

    # 2. EDA
    resp_eda = client.get(f"/api/v1/sessions/{sid}/eda")
    assert resp_eda.status_code == 200
    eda = resp_eda.json()
    assert eda["session_id"] == sid
    assert "tonic_eda_mean_us" in eda
    assert "downsampled_eda" in eda

    # 3. Epochs
    resp_epochs = client.get(f"/api/v1/sessions/{sid}/epochs")
    assert resp_epochs.status_code == 200
    epochs = resp_epochs.json()
    assert isinstance(epochs, list)
    assert len(epochs) > 0
    assert "inferred_stage" in epochs[0]

    # 4. Timeline
    resp_timeline = client.get(f"/api/v1/sessions/{sid}/timeline")
    assert resp_timeline.status_code == 200
    timeline = resp_timeline.json()
    assert timeline["session_id"] == sid
    assert "timeline" in timeline
    assert len(timeline["timeline"]) > 0
