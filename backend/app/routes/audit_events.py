# POST /audit/v1/events (append, 201 / 200 replay) and GET /audit/v1/score/{match_id} (FR-1.1, spec §5.9).
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from app.db import get_db
from app.services.events import append_event, get_score

router = APIRouter()


@router.post("/audit/v1/events")
def post_event(body: Any = Body(None), db=Depends(get_db)):
    status, response = append_event(db, body)
    return JSONResponse(status_code=status, content=response)


@router.get("/audit/v1/score/{match_id}")
def read_score(match_id: str, db=Depends(get_db)):
    return get_score(db, match_id)
