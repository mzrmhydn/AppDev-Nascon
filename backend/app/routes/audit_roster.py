# Roster routes (FR-2.2, spec §5.11) + the /api/v1/roster/transfer twin (contract §2.11).
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import SessionLocal, get_db
from app.errors import AppError, validation_error
from app.models import Squad
from app.services import roster

router = APIRouter()


async def raw_json(request: Request):
    try:
        return json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")


def _run(fn, body):
    with SessionLocal() as db:
        return fn(db, body)


@router.post("/audit/v1/roster/setup", status_code=201)
async def roster_setup(request: Request):
    return await run_in_threadpool(_run, roster.setup, await raw_json(request))


@router.post("/audit/v1/roster/transfer")
async def roster_transfer(request: Request):
    status, body = await run_in_threadpool(_run, roster.transfer, await raw_json(request))
    return JSONResponse(status_code=status, content=body)


@router.get("/audit/v1/roster/history/{player_id}")
def roster_history(player_id: str, as_of: str | None = None, db: Session = Depends(get_db)):
    return roster.history(db, player_id, as_of)


def can_transfer(db, user, body):
    """super_admin, or a club_manager whose club owns from_squad_id. Checked before validation."""
    if user["role"] == "super_admin":
        return True
    if user["role"] != "club_manager" or not isinstance(body, dict):
        return False
    squad_id = body.get("from_squad_id")
    squad = db.get(Squad, squad_id) if isinstance(squad_id, str) else None
    return squad is not None and squad.club_id == user["club_id"]


@router.post("/api/v1/roster/transfer")
async def api_roster_transfer(request: Request, user=Depends(current_user)):
    body = await raw_json(request)

    def run():
        with SessionLocal() as db:
            if not can_transfer(db, user, body):
                raise AppError(403, "FORBIDDEN", "not allowed to move this player")
            return roster.transfer(db, body)

    status, response = await run_in_threadpool(run)
    return JSONResponse(status_code=status, content=response)
