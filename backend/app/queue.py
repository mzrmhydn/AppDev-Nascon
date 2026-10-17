# Domain events -> Redis Stream "domain-events" (FR-2.3: each order transition emits a structured event).
# Best effort: a Redis outage must never fail a checkout, so every error is logged and swallowed.
import json
import logging
import time
from datetime import datetime, timezone

from app.config import REDIS_URL

log = logging.getLogger("nascon")
STREAM = "domain-events"
_client = None
_down_until = 0.0  # after a failure, skip Redis for 30 s so requests never wait on it


def _redis():
    global _client
    if _client is None:
        import redis
        _client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
    return _client


def emit_domain_event(event_type, data):
    global _down_until
    if time.monotonic() < _down_until:
        log.warning("domain event %s skipped: redis marked down", event_type)
        return
    event = {
        "type": event_type,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": json.dumps(data, sort_keys=True),
    }
    try:
        _redis().xadd(STREAM, event, maxlen=10000)
    except Exception as exc:  # Redis down / not installed locally
        _down_until = time.monotonic() + 30
        log.warning("domain event %s not queued: %s", event_type, exc)
