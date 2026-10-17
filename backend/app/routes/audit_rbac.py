# POST /audit/v1/rbac-matrix + probe routes P1–P7 (FR-5.1, spec §5.13).
# Order: 401 (token) -> 404 (target id unknown) -> 403 (policy). Probes never read the body.
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import current_user, make_token
from app.db import get_db
from app.errors import AppError
from app.models import Club, League, Player, User
from app.policy import can

router = APIRouter()

ROLE_USERS = {
    "super_admin": "user-admin",
    "league_organizer": "user-organizer",
    "club_manager": "user-manager",
    "player": "user-player",
    "viewer": "user-viewer",
}

CONTEXT = {
    "tenant_id": "tenant-alpha", "foreign_tenant_id": "tenant-beta",
    "own_league_id": "league-alpha-1", "other_league_id": "league-alpha-2",
    "foreign_league_id": "league-beta-1",
    "own_club_id": "club-alpha-1", "other_club_id": "club-alpha-2", "foreign_club_id": "club-beta-1",
    "own_player_id": "player-alpha-1", "other_player_id": "player-alpha-2",
    "foreign_player_id": "player-beta-1",
}


@router.post("/audit/v1/rbac-matrix")
def rbac_matrix(db: Session = Depends(get_db)):
    tokens = {role: make_token(db.get(User, user_id)) for role, user_id in ROLE_USERS.items()}
    return {"tokens": tokens, "context": dict(CONTEXT)}


# ---------- target lookups (404 when the id does not exist at all) ----------

def league_target(db, league_id):
    league = db.get(League, league_id)
    if league is None:
        raise AppError(404, "LEAGUE_NOT_FOUND", "league not found", {"league_id": league_id})
    return {"tenant_id": league.tenant_id, "league_id": league.league_id}


def club_target(db, club_id):
    club = db.get(Club, club_id)
    if club is None:
        # The error catalogue has no club code; a club is the squad owner, so SQUAD_NOT_FOUND is closest.
        raise AppError(404, "SQUAD_NOT_FOUND", "club not found", {"club_id": club_id})
    return {"tenant_id": club.tenant_id, "club_id": club.club_id}


def player_target(db, player_id):
    player = db.get(Player, player_id)
    if player is None:
        raise AppError(404, "PLAYER_NOT_FOUND", "player not found", {"player_id": player_id})
    return {"tenant_id": player.tenant_id, "club_id": player.club_id, "player_id": player.player_id}


def decide(user, action, target=None):
    if not can(user, action, target):
        raise AppError(403, "FORBIDDEN", f"{user['role']} may not {action}")
    return {"authorized": True}


# ---------- P1–P7 ----------

@router.post("/audit/v1/rbac/tenants")
def p1_create_tenant(user=Depends(current_user)):
    return decide(user, "create_tenant")


@router.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
def p2_manage_fixtures(league_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return decide(user, "manage_fixtures", league_target(db, league_id))


@router.post("/audit/v1/rbac/clubs/{club_id}/roster")
def p3_manage_roster(club_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return decide(user, "manage_roster", club_target(db, club_id))


@router.post("/audit/v1/rbac/clubs/{club_id}/products")
def p4_manage_products(club_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return decide(user, "manage_products", club_target(db, club_id))


@router.patch("/audit/v1/rbac/players/{player_id}")
def p5_edit_player(player_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return decide(user, "edit_player", player_target(db, player_id))


@router.get("/audit/v1/rbac/clubs/{club_id}")
def p6_view_club(club_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return decide(user, "view_club", club_target(db, club_id))


@router.get("/audit/v1/rbac/platform/config")
def p7_platform_config(user=Depends(current_user)):
    return decide(user, "platform_config")
