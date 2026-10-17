# All settings come from environment variables (spec §5.2: DAY1_SALT only from env, never committed).
import logging
import os

log = logging.getLogger("nascon")

# Read as-is: the salt is used as raw UTF-8 bytes, not trimmed (spec §5.3).
DAY1_SALT = os.environ.get("DAY1_SALT")
if not DAY1_SALT:
    log.warning("DAY1_SALT is not set - signatures will not match the grader")
    DAY1_SALT = ""

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://nascon:nascon@localhost:5432/nascon")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

MAX_BODY_BYTES = 1_048_576  # 1 MB (spec §5.2)
DEFAULT_SEED = 42
DEFAULT_STOCK = {"var-jersey-001-M": 1, "var-jersey-001-L": 5}
