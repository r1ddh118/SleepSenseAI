"""Phase 4 Gate Verification: End-to-end night upload and timeline/EDA clock time population."""

from pathlib import Path
from datetime import datetime, timezone
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from database import init_db
init_db()

from fastapi.testclient import TestClient
from main import app
from config import REPO_ROOT

client = TestClient(app)


def test_phase4_upload_gate_and_clock_time_population():
    """Verify that uploading a generated night sensor CSV populates all tabs with valid clock times."""
    sample_file = REPO_ROOT / "data" / "sample_data" / "healthy_night.csv"
    assert sample_file.exists(), "Sample test file healthy_night.csv must exist"

    test_sid = f"GATE_P4_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # 1. Upload night sensor CSV with inline processing enabled
    with open(sample_file, "rb") as f:
        resp_upload = client.post(
            "/api/v1/sessions/upload",
            files={"file": ("healthy_night.csv", f, "text/csv")},
            data={
                "user_id": "U001",
                "session_id": test_sid,
                "notes": "Phase 4 Gate Verification",
                "inline": "true",
            },
        )
    assert resp_upload.status_code == 200, f"Upload failed: {resp_upload.text}"
    body = resp_upload.json()
    assert body["session_id"] == test_sid

    # 2. Poll status to completion
    resp_status = client.get(f"/api/v1/sessions/{test_sid}/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["status"] == "completed"

    # 3. Check Hypnogram and Cardiorespiratory Timeline (Tab 1 & Tab 3 data source)
    resp_timeline = client.get(f"/api/v1/sessions/{test_sid}/timeline")
    assert resp_timeline.status_code == 200, f"Timeline fetch failed: {resp_timeline.text}"
    timeline_data = resp_timeline.json()
    timeline = timeline_data.get("timeline", [])
    assert len(timeline) > 0, "Timeline should contain epochs"

    # Verify timestamps represent genuine clock times with HH:MM:SS
    first_epoch = timeline[0]
    last_epoch = timeline[-1]
    assert "timestamp" in first_epoch
    assert "stage" in first_epoch
    assert "hr_mean" in first_epoch
    assert "spo2_mean" in first_epoch

    first_ts = datetime.fromisoformat(first_epoch["timestamp"].replace("Z", "+00:00"))
    last_ts = datetime.fromisoformat(last_epoch["timestamp"].replace("Z", "+00:00"))
    assert last_ts > first_ts, "Timeline timestamps must be monotonically increasing"

    # Clock time string formatting verification
    clock_str = first_ts.strftime("%H:%M")
    assert len(clock_str) == 5 and ":" in clock_str, "Must format to valid HH:MM clock time"

    # 4. Check High-Res EDA Waveform Artifact (Tab 2 data source)
    resp_eda = client.get(f"/api/v1/sessions/{test_sid}/eda")
    assert resp_eda.status_code == 200, f"EDA fetch failed: {resp_eda.text}"
    eda_data = resp_eda.json()
    assert "tonic_eda_mean_us" in eda_data
    assert "phasic_peak_count" in eda_data
    assert "downsampled_eda" in eda_data
    assert len(eda_data["downsampled_eda"]) > 0
    assert "start_timestamp_iso" in eda_data
    assert eda_data["start_timestamp_iso"] is not None

    # Verify EDA start timestamp matches the timeline start clock time
    eda_start_ts = datetime.fromisoformat(eda_data["start_timestamp_iso"].replace("Z", "+00:00"))
    assert abs((eda_start_ts - first_ts).total_seconds()) < 60, "EDA clock time must match session bedtime"
