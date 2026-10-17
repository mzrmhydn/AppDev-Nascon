# GET /health — 200 only when the DB answers and the baseline is seeded (spec §5.4).
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import error_response
from app.seed import is_seeded

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        seeded = is_seeded(db)
    except Exception:
        return error_response(503, "SERVICE_UNAVAILABLE", "database not reachable")
    if not seeded:
        return error_response(503, "SERVICE_UNAVAILABLE", "baseline data not seeded yet")
    return {"status": "ok"}
