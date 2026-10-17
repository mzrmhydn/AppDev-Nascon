# One error shape for every non-2xx response: {"error": {"code", "message", "details"}} (spec §5.2).
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.rule_error import RuleError

log = logging.getLogger("nascon")


class AppError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(status, code, message, details=None):
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=body)


def validation_error(fields, message="invalid request"):
    return AppError(400, "VALIDATION_ERROR", message, {"fields": fields})


HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE"}


def install_error_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RuleError)
    async def rule_error(request: Request, exc: RuleError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def request_validation(request: Request, exc: RequestValidationError):
        # FastAPI's default is 422; the spec wants 400 with the offending field names.
        fields = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part != "body"]
            name = loc[-1] if loc else "body"
            if name not in fields:
                fields.append(name)
        return error_response(400, "VALIDATION_ERROR", "invalid request", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "INTERNAL_ERROR", "unexpected server error")
