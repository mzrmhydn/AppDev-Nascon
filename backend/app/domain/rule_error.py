# RuleError: a rejected request from a pure domain function (400/404/409 + spec error code).
# The service/route layer turns it into the {"error": {"code", "message", "details"}} body.


class RuleError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
