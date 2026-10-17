# Mock payment gateway (FR-2.3, spec §5.12): authorize / capture / void driven by the payment token.
import itertools
import threading

_counter = itertools.count(1)
_lock = threading.Lock()


def _next():
    with _lock:
        return next(_counter)


def reset_counter():
    """Called on /reset so the first order after a reset gets auth_1 / cap_1."""
    global _counter
    with _lock:
        _counter = itertools.count(1)


def authorize(token):
    """Return an authorization id, or None when the card is declined."""
    if token != "tok_success" and token != "tok_capture_fail":
        return None  # tok_declined and any unknown token are declined
    return f"auth_{_next()}"


def capture(token, authorization_id):
    """Return a capture id, or None when capture fails."""
    if token == "tok_capture_fail":
        return None
    return "cap_" + authorization_id.split("_", 1)[1]


def void(authorization_id):
    """Cancel an authorization (nothing to do in the mock)."""
    return True
