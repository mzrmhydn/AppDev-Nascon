# Request guards: bodies over 1 MB -> 413 PAYLOAD_TOO_LARGE (spec §5.2). Rate limiter is added in plan 02.
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
