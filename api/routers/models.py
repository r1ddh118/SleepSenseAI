"""Model leaderboard and retraining."""

import csv

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from auth import require_clinician
from config import REPO_ROOT, settings
from schemas import LeaderboardEntry, TaskStatus, TrainRequest
from tasks import run_training

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _float_or_none(val: str | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        x = float(val)
        if x != x:  # NaN
            return None
        return x
    except ValueError:
        return None


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(current_user=Depends(require_clinician)):
    csv_path = settings.artifacts_path / "model_leaderboard.csv"
    if not csv_path.exists():
        raise HTTPException(404, "Leaderboard not found — run training first")

    entries: list[LeaderboardEntry] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                LeaderboardEntry(
                    model_name=row.get("model_name", ""),
                    accuracy=_float_or_none(row.get("accuracy")),
                    f1=_float_or_none(row.get("f1")),
                    precision=_float_or_none(row.get("precision")),
                    recall=_float_or_none(row.get("recall")),
                    roc_auc=_float_or_none(row.get("roc_auc")),
                )
            )
    return sorted(entries, key=lambda e: e.f1 or 0, reverse=True)


@router.post("/train", response_model=TaskStatus)
def trigger_training(
    body: TrainRequest,
    current_user=Depends(require_clinician),
):
    task = run_training.delay(dataset_path=body.dataset_path)
    return TaskStatus(task_id=task.id, status="PENDING")


@router.get("/clinical-metrics")
def get_clinical_metrics(current_user=Depends(require_clinician)):
    path = REPO_ROOT / "validation" / "clinical_metrics_report.csv"
    if not path.exists():
        raise HTTPException(404, "Clinical metrics not yet generated")
    return pd.read_csv(path).to_dict(orient="records")
