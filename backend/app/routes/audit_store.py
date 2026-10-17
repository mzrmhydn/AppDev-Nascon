# POST /audit/v1/checkout, GET /audit/v1/inventory/{variant_id}, POST /api/v1/checkout twin (spec §5.12).
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import SessionLocal, get_db
from app.errors import validation_error
from app.services import store

router = APIRouter()


async def raw_json(request: Request):
    # Raw body, never a Pydantic dump: idempotency compares exactly what the client sent.
    try:
        return json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")


def run_checkout(body):
    with SessionLocal() as db:
        return store.checkout(db, body)


async def checkout_response(request: Request):
    body = await raw_json(request)
    # Sync DB work in the threadpool, so the 20 simultaneous buyers really run in parallel.
    status, response = await run_in_threadpool(run_checkout, body)
    return JSONResponse(status_code=status, content=response)


@router.post("/audit/v1/checkout")
async def audit_checkout(request: Request):
    return await checkout_response(request)


@router.post("/api/v1/checkout")
async def api_checkout(request: Request, user=Depends(current_user)):
    # Any logged-in role may buy (contract §2.11); the app sends customer_id = user_id.
    return await checkout_response(request)


@router.get("/audit/v1/inventory/{variant_id}")
def inventory(variant_id: str, db: Session = Depends(get_db)):
    return store.inventory(db, variant_id)
