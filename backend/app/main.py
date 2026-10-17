# App factory: middleware, error handlers, routers, startup (create tables + seed baseline). NFR-7.
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app import config
from app.db import Base, SessionLocal, engine
from app.errors import install_error_handlers
from app.middleware import BodySizeLimit
from app.routes import audit_reset, health
from app.seed import is_seeded, reset_baseline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nascon")


def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not is_seeded(db):
            reset_baseline(db, config.DEFAULT_SEED, dict(config.DEFAULT_STOCK))
            log.info("baseline seeded")


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield


app = FastAPI(title="NaSCon'26 League Platform", lifespan=lifespan)
app.add_middleware(BodySizeLimit)
install_error_handlers(app)

# Track A routers
app.include_router(health.router)
app.include_router(audit_reset.router)
# Track B routers (added when each one is committed)
