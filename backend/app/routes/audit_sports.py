# POST /audit/v1/sports — create a mystery sport from JSON (FR-1.1, spec §5.6).
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from app.db import get_db
from app.services.sports import create_sport

router = APIRouter()


@router.post("/audit/v1/sports")
def post_sport(body: Any = Body(None), db=Depends(get_db)):
    status, response = create_sport(db, body)
    return JSONResponse(status_code=status, content=response)
