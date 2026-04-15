"""Health check: DB and Redis."""

import redis as redis_lib
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from config import settings
from database import get_db
from schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=HealthOut)
def health_check(db: DBSession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        r = redis_lib.from_url(settings.redis_url)
        r.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {e}"

    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        edge_device=settings.edge_device,
        database=db_status,
        redis=redis_status,
    )
