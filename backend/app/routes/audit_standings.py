# GET /audit/v1/standings/{league_id} — table recomputed from the event logs (FR-1.4, spec §5.10).
from fastapi import APIRouter, Depends

from app.db import get_db
from app.services.leagues import get_standings

router = APIRouter()


@router.get("/audit/v1/standings/{league_id}")
def read_standings(league_id: str, db=Depends(get_db)):
    return get_standings(db, league_id)
