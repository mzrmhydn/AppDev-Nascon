# App auth routes: POST /api/v1/auth/login, GET /api/v1/me, GET /api/v1/ping (contract §2.1, §2.2, §2.12).
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user, make_token, unauthenticated, verify_password
from app.db import get_db
from app.errors import validation_error
from app.models import Tenant, User

router = APIRouter()


def user_json(user):
    return {
        "user_id": user.user_id, "email": user.email, "display_name": user.display_name,
        "role": user.role, "tenant_id": user.tenant_id,
        "league_id": user.league_id, "club_id": user.club_id, "player_id": user.player_id,
    }


def tenant_json(db, tenant_id):
    if tenant_id is None:
        return None  # super_admin: platform-wide, app uses its default theme
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return None
    return {"tenant_id": tenant.tenant_id, "name": tenant.name, "primary_color": tenant.primary_color,
            "accent_color": tenant.accent_color, "logo_url": None}


@router.post("/api/v1/auth/login")
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        body = json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")
    if not isinstance(body, dict):
        raise validation_error(["body"])
    bad = [k for k in ("email", "password") if not isinstance(body.get(k), str) or not body.get(k)]
    if bad:
        raise validation_error(bad)

    user = db.scalars(select(User).where(func.lower(User.email) == body["email"].strip().lower())).first()
    if user is None or not verify_password(body["password"], user.password_hash):
        raise unauthenticated("wrong email or password")
    return {"token": make_token(user), "user": user_json(user), "tenant": tenant_json(db, user.tenant_id)}


@router.get("/api/v1/me")
def me(claims=Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, claims["user_id"])
    if user is None:  # token for a user that no longer exists
        raise unauthenticated("user no longer exists")
    return {"user": user_json(user), "tenant": tenant_json(db, user.tenant_id)}


@router.get("/api/v1/ping")
def ping():
    return {"pong": True}
