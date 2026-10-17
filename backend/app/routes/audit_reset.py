# POST /audit/v1/reset — wipe all state and re-create the exact baseline (spec §5.5).
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.errors import validation_error
from app.seed import SPORT_ORDER, TENANT_ORDER, reset_baseline

router = APIRouter()


async def read_optional_json(request: Request):
    raw = await request.body()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        raise validation_error(["body"], "malformed JSON")


def parse_reset_body(body):
    """Return (seed, stock) or raise 400. Unknown fields are ignored (spec §5.2)."""
    if not isinstance(body, dict):
        raise validation_error(["body"])
    seed = body.get("seed", config.DEFAULT_SEED)
    if type(seed) is not int:
        raise validation_error(["seed"])
    stock = dict(config.DEFAULT_STOCK)
    given = body.get("stock", {})
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise validation_error(["stock"])
    for variant_id, qty in given.items():
        if variant_id not in stock or type(qty) is not int or qty < 0:
            raise validation_error(["stock"], "stock must map known variant ids to integers >= 0")
        stock[variant_id] = qty
    return seed, stock


@router.post("/audit/v1/reset")
async def reset(request: Request, db: Session = Depends(get_db)):
    seed, stock = parse_reset_body(await read_optional_json(request))
    reset_baseline(db, seed, stock)
    reset_hooks_run()
    return {
        "status": "reset_complete",
        "seed": seed,
        "sports": list(SPORT_ORDER),
        "tenants": list(TENANT_ORDER),
        "stock": stock,
    }


# In-memory state (rate limiter, WebSocket manager, ...) registers a callback here to be cleared on reset.
RESET_HOOKS = []


def reset_hooks_run():
    for hook in RESET_HOOKS:
        hook()
