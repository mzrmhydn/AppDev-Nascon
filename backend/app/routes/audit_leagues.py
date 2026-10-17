# POST /audit/v1/leagues — register teams, fixtures and standings config (FR-1.4, spec §5.8).
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from app.db import get_db
from app.services.leagues import create_league

router = APIRouter()


@router.post("/audit/v1/leagues")
def post_league(body: Any = Body(None), db=Depends(get_db)):
    status, response = create_league(db, body)
    return JSONResponse(status_code=status, content=response)
