# Converts a pure-domain RuleError into Track A's AppError (same status/code/message/details).
from app.errors import AppError


def as_app_error(err):
    return AppError(err.status, err.code, err.message, err.details)
