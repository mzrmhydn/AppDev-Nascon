# Request guards: bodies over 1 MB -> 413 PAYLOAD_TOO_LARGE (spec §5.2); /api/v1 rate limiter -> 429 (§5.13, NFR-5).
import math
import threading
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import MAX_BODY_BYTES
from app.errors import error_response


class BodySizeLimit(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is not None and length.isdigit():
                too_big = int(length) > MAX_BODY_BYTES
            else:
                # No (valid) Content-Length, e.g. chunked: read it and measure.
                too_big = len(await request.body()) > MAX_BODY_BYTES
            if too_big:
                return error_response(413, "PAYLOAD_TOO_LARGE", "request body is larger than 1 MB",
                                      {"max_bytes": MAX_BODY_BYTES})
        return await call_next(request)


class RateLimiter:
    """Sliding window per client IP: at most LIMIT requests in any WINDOW seconds (spec §5.13)."""
    LIMIT = 100
    WINDOW = 10.0

    def __init__(self):
        self.hits = {}  # ip -> deque of request times
        self.lock = threading.Lock()  # sync routes run in a threadpool

    def check(self, ip, now=None):
        """Return 0 if allowed (and record the hit), else seconds to wait (>= 1)."""
        now = time.monotonic() if now is None else now
        with self.lock:
            times = self.hits.setdefault(ip, deque())
            while times and times[0] <= now - self.WINDOW:
                times.popleft()
            if len(times) >= self.LIMIT:
                return max(1, math.ceil(times[0] + self.WINDOW - now))
            times.append(now)
            return 0

    def clear(self):
        with self.lock:
            self.hits.clear()


limiter = RateLimiter()


class RateLimit(BaseHTTPMiddleware):
    """Only /api/v1/*; /audit/v1/*, /health and /ws/* are exempt."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/"):
            ip = request.client.host if request.client else "unknown"
            wait = limiter.check(ip)
            if wait:
                response = error_response(429, "RATE_LIMITED", "too many requests, slow down",
                                          {"retry_after_seconds": wait})
                response.headers["Retry-After"] = str(wait)
                return response
        return await call_next(request)
