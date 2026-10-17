# POST /audit/v1/offline-sync and the /api/v1/offline-sync twin (NFR-4, spec §5.14, contract §2.11).
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from app.auth import current_user
from app.db import SessionLocal
from app.errors import validation_error
from app.models import Match
from app.routes.audit_roster import can_transfer
from app.services import offline_sync

router = APIRouter()


async def raw_json(request: Request):
    try:
        return json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")


def _run(body, authorize=None):
    with SessionLocal() as db:
        return offline_sync.sync(db, body, authorize)


@router.post("/audit/v1/offline-sync")
async def audit_offline_sync(request: Request):
    return await run_in_threadpool(_run, await raw_json(request))


def can_score(db, user, payload):
    """Like /api/v1/events: super_admin, or the organizer of the match's league."""
    if user["role"] == "super_admin":
        return True
    if user["role"] != "league_organizer":
        return False
    match_id = payload.get("match_id")
    match = db.get(Match, match_id) if isinstance(match_id, str) else None
    if match is not None:
        league_id = match.league_id
    else:  # match_init creates it: use the league in the payload
        inner = payload.get("payload")
        league_id = inner.get("league_id") if isinstance(inner, dict) else None
    return league_id is not None and league_id == user["league_id"]


@router.post("/api/v1/offline-sync")
async def api_offline_sync(request: Request, user=Depends(current_user)):
    body = await raw_json(request)

    def authorize(db, action):
        if action["type"] == "score_event":
            return can_score(db, user, action["payload"])
        return can_transfer(db, user, action["payload"])

    return await run_in_threadpool(_run, body, authorize)
