"""Router for sample sleep dataset CSVs."""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from config import REPO_ROOT

router = APIRouter(prefix="/api/v1/sample-data", tags=["sample-data"])

SAMPLE_DIR = REPO_ROOT / "data" / "sample_data"


@router.get("")
@router.get("/")
def list_sample_data():
    """List available 1 Hz night sensor sample CSVs."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    csvs = list(SAMPLE_DIR.glob("*.csv"))
    samples = []
    for csv_file in csvs:
        samples.append(
            {
                "name": csv_file.name,
                "size_bytes": csv_file.stat().st_size,
                "download_url": f"/api/v1/sample-data/{csv_file.name}",
            }
        )
    return {"samples": samples}


@router.get("/{name}")
def get_sample_data_file(name: str):
    """Serves/downloads a demo night sensor CSV file."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SAMPLE_DIR / name
    if not file_path.exists() or not name.endswith(".csv"):
        raise HTTPException(404, f"Sample file '{name}' not found")
    return FileResponse(
        path=file_path,
        media_type="text/csv",
        filename=name,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
