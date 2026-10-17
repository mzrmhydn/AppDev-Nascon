# Password hashing (stdlib PBKDF2) + HS256 JWT + current_user dependency (FR-5.1, NFR-5, spec §5.13).
import hashlib
import hmac
import os
import time

import jwt
from fastapi import Request

from app.config import JWT_SECRET
from app.errors import AppError

ITERATIONS = 100_000


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, stored):
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
    return hmac.compare_digest(check, digest)


# ---------- JWT (HS256) ----------
TOKEN_HOURS = 12
CLAIMS = ["role", "tenant_id", "league_id", "club_id", "player_id"]


def make_token(user):
    """user = User row or dict with user_id + CLAIMS."""
    get = user.get if isinstance(user, dict) else (lambda k: getattr(user, k))
    now = int(time.time())
    claims = {"sub": get("user_id"), "iat": now, "exp": now + TOKEN_HOURS * 3600}
    for key in CLAIMS:
        claims[key] = get(key)
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def unauthenticated(message="missing or invalid token"):
    return AppError(401, "UNAUTHENTICATED", message)


def decode_token(token):
    # algorithms=["HS256"] rejects alg:none and any other algorithm; decode also checks signature + exp.
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise unauthenticated()
    user = {"user_id": claims["sub"]}
    for key in CLAIMS:
        user[key] = claims.get(key)
    return user


def current_user(request: Request):
    """FastAPI dependency: the caller's claims as a dict, or 401."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthenticated()
    return decode_token(token.strip())
