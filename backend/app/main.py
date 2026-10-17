# App factory: middleware, error handlers, routers, startup (create tables + seed baseline). NFR-7.
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app import config, realtime
from app.db import Base, SessionLocal, engine
from app.demo_seed import seed_demo_safely
from app.errors import install_error_handlers
from app.middleware import BodySizeLimit, RateLimit, limiter
from app.routes import (api_app, api_auth, audit_offline, audit_rbac, audit_reset, audit_roster, audit_store,
                        health, ws)
from app.routes import audit_events, audit_fixtures, audit_leagues, audit_sports, audit_standings
from app.seed import is_seeded, reset_baseline
from app.services import payment_gateway

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nascon")


def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not is_seeded(db):
            reset_baseline(db, config.DEFAULT_SEED, dict(config.DEFAULT_STOCK))
            log.info("baseline seeded")
    seed_demo_safely(SessionLocal)


@asynccontextmanager
async def lifespan(app: FastAPI):
    realtime.LOOP = asyncio.get_running_loop()
    startup()
    yield


app = FastAPI(title="NaSCon'26 League Platform", lifespan=lifespan)
app.add_middleware(BodySizeLimit)
app.add_middleware(RateLimit)
audit_reset.RESET_HOOKS.append(limiter.clear)
audit_reset.RESET_HOOKS.append(payment_gateway.reset_counter)
install_error_handlers(app)

# Track A routers
app.include_router(health.router)
app.include_router(audit_reset.router)
app.include_router(audit_rbac.router)
app.include_router(api_auth.router)
app.include_router(audit_store.router)
app.include_router(audit_roster.router)
app.include_router(audit_offline.router)
app.include_router(api_app.router)
app.include_router(ws.router)
# Track B routers (added when each one is committed)
app.include_router(audit_sports.router)
app.include_router(audit_events.router)
app.include_router(audit_leagues.router)
app.include_router(audit_standings.router)
app.include_router(audit_fixtures.router)
