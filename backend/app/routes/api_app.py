# Mobile-app reads + the events write twin + demo seed (contract §2.3–2.13). Thin: parse -> query -> shape.
# Every route (except demo-seed) needs a token and only shows the caller's tenant (super_admin sees all).
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import realtime
from app.auth import current_user
from app.db import SessionLocal, get_db
from app.domain.roster_rules import covers
from app.errors import AppError, validation_error
from app.models import (Club, League, Match, Player, PriceChange, Product, Registration, RosterLeague, Showcase,
                        Squad, Variant)
from app.routes.audit_offline import can_score
from app.services import events

router = APIRouter()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def same_tenant_or_403(user, tenant_id):
    if user["role"] != "super_admin" and tenant_id != user["tenant_id"]:
        raise AppError(403, "FORBIDDEN", "this belongs to another tenant")


def team_names(db, team_ids):
    names = {c.club_id: c.name for c in db.scalars(select(Club).where(Club.club_id.in_(team_ids))).all()}
    return [{"team_id": t, "name": names.get(t, t)} for t in team_ids]


def get_league(db, user, league_id):
    league = db.get(League, league_id)
    if league is None:
        raise AppError(404, "LEAGUE_NOT_FOUND", "league not found", {"league_id": league_id})
    same_tenant_or_403(user, league.tenant_id)
    return league


# ---------- leagues + fixtures ----------

@router.get("/api/v1/leagues")
def list_leagues(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(League).order_by(League.league_id)
    if user["role"] != "super_admin":
        query = query.where(League.tenant_id == user["tenant_id"])
    return {"leagues": [
        {"league_id": lg.league_id, "tenant_id": lg.tenant_id, "name": lg.name, "sport_id": lg.sport_id,
         "season": lg.season, "teams": team_names(db, lg.teams or [])}
        for lg in db.scalars(query).all()
    ]}


@router.get("/api/v1/leagues/{league_id}/fixtures")
def league_fixtures(league_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    league = get_league(db, user, league_id)
    matches = db.scalars(select(Match).where(Match.league_id == league_id)).all()
    matches = sorted(matches, key=lambda m: (m.scheduled_at is None, m.scheduled_at or "", m.match_id))
    fixtures = []
    for m in matches:
        score = events.projection_for(db, m)
        upcoming = score["status"] == "upcoming"
        home, away = team_names(db, [m.home_team_id, m.away_team_id])
        fixtures.append({
            "match_id": m.match_id, "round": m.round, "home": home, "away": away,
            "status": score["status"], "scheduled_at": m.scheduled_at, "venue": m.venue,
            "home_score": None if upcoming else score["home"]["score"],
            "away_score": None if upcoming else score["away"]["score"],
            "version": score["version"],
        })
    return {"league_id": league.league_id, "sport_id": league.sport_id, "fixtures": fixtures}


# ---------- clubs ----------

def club_summary(c):
    return {"club_id": c.club_id, "tenant_id": c.tenant_id, "name": c.name, "short_name": c.short_name,
            "primary_color": c.primary_color}


@router.get("/api/v1/clubs")
def list_clubs(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(Club).order_by(Club.club_id)
    if user["role"] != "super_admin":
        query = query.where(Club.tenant_id == user["tenant_id"])
    return {"clubs": [club_summary(c) for c in db.scalars(query).all()]}


def club_roster(db, club_id):
    """Players whose current squad (today) belongs to this club."""
    today = datetime.now(timezone.utc).date().isoformat()
    squad_ids = [s.squad_id for s in db.scalars(select(Squad).where(Squad.club_id == club_id)).all()]
    if not squad_ids:
        return []
    regs = db.scalars(select(Registration).where(Registration.squad_id.in_(squad_ids))
                      .order_by(Registration.id)).all()
    roster = []
    for r in regs:
        reg = {"registration_type": r.registration_type, "start_date": r.start_date, "end_date": r.end_date}
        if not covers(reg, today):
            continue
        player = db.get(Player, r.player_id)
        roster.append({"player_id": r.player_id, "name": player.name if player else r.player_id,
                       "position": player.position if player else None, "role": r.role,
                       "league_id": r.league_id, "squad_id": r.squad_id,
                       "registration_type": r.registration_type, "parent_squad_id": r.parent_squad_id})
    return roster


@router.get("/api/v1/clubs/{club_id}")
def club_detail(club_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    club = db.get(Club, club_id)
    if club is None:
        raise AppError(404, "SQUAD_NOT_FOUND", "club not found", {"club_id": club_id})
    same_tenant_or_403(user, club.tenant_id)
    profile = club.profile or {}
    body = club_summary(club)
    body.update({
        "home_venue": profile.get("home_venue"),
        "socials": profile.get("socials", {"instagram": None, "x": None, "facebook": None}),
        "staff": profile.get("staff", []),
        "stats": profile.get("stats", []),
        "roster": club_roster(db, club_id),
    })
    return body


# ---------- products + showcase ----------

def current_price(db, variant):
    """Latest scheduled price that is already in effect, else the base price (FR-2.3)."""
    change = db.scalars(select(PriceChange).where(PriceChange.variant_id == variant.variant_id,
                                                  PriceChange.effective_at <= now_iso())
                        .order_by(PriceChange.effective_at.desc())).first()
    return change.price_minor if change else variant.price_minor


def product_json(db, p):
    variants = db.scalars(select(Variant).where(Variant.product_id == p.product_id)
                          .order_by(Variant.variant_id)).all()
    return {
        "product_id": p.product_id, "tenant_id": p.tenant_id, "club_id": p.club_id, "name": p.name,
        "category": p.category, "description": p.description, "image_url": None,
        "variants": [{"variant_id": v.variant_id, "size": v.size, "color": v.color,
                      "price_minor": current_price(db, v), "currency": "PKR", "stock": v.stock} for v in variants],
    }


@router.get("/api/v1/products")
def list_products(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(Product).order_by(Product.product_id)
    if user["role"] != "super_admin":
        query = query.where(Product.tenant_id == user["tenant_id"])
    return {"products": [product_json(db, p) for p in db.scalars(query).all()]}


def showcase_json(db, match_id):
    pin = db.get(Showcase, match_id)
    product = db.get(Product, pin.product_id) if pin else None
    return {"match_id": match_id, "product": product_json(db, product) if product else None,
            "pinned_at": pin.pinned_at.strftime("%Y-%m-%dT%H:%M:%SZ") if pin else None}


def get_match(db, match_id):
    match = db.get(Match, match_id)
    if match is None:
        raise AppError(404, "MATCH_NOT_FOUND", "match not found", {"match_id": match_id})
    return match


@router.get("/api/v1/matches/{match_id}/showcase")
def get_showcase(match_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    get_match(db, match_id)
    return showcase_json(db, match_id)


@router.post("/api/v1/matches/{match_id}/showcase")
async def pin_showcase(match_id: str, request: Request, user=Depends(current_user)):
    try:
        body = json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")
    if not isinstance(body, dict) or not isinstance(body.get("product_id"), str):
        raise validation_error(["product_id"])

    def run():
        with SessionLocal() as db:
            match = get_match(db, match_id)
            product = db.get(Product, body["product_id"])
            if product is None:
                raise AppError(404, "VARIANT_NOT_FOUND", "product not found", {"product_id": body["product_id"]})
            allowed = (user["role"] == "super_admin"
                       or (user["role"] == "league_organizer" and match.league_id is not None
                           and match.league_id == user["league_id"])
                       or (user["role"] == "club_manager" and product.club_id == user["club_id"]))
            if not allowed:
                raise AppError(403, "FORBIDDEN", "not allowed to pin a product on this match")
            pin = db.get(Showcase, match_id)
            if pin is None:
                db.add(Showcase(match_id=match_id, product_id=product.product_id,
                                pinned_at=datetime.now(timezone.utc)))
            else:
                pin.product_id, pin.pinned_at = product.product_id, datetime.now(timezone.utc)
            db.commit()
            return showcase_json(db, match_id)

    result = await run_in_threadpool(run)
    realtime.notify(match_id, {"type": "showcase_updated", "match_id": match_id})
    return result


# ---------- roster config ----------

@router.get("/api/v1/leagues/{league_id}/roster-config")
def roster_config(league_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    rl = db.get(RosterLeague, league_id)
    if rl is None:
        raise AppError(404, "LEAGUE_NOT_FOUND", "league has no roster setup", {"league_id": league_id})
    same_tenant_or_403(user, rl.tenant_id)
    today = datetime.now(timezone.utc).date().isoformat()
    regs = db.scalars(select(Registration).where(Registration.league_id == league_id)).all()
    squads = []
    for s in db.scalars(select(Squad).where(Squad.league_id == league_id).order_by(Squad.squad_id)).all():
        count = sum(1 for r in regs if r.squad_id == s.squad_id and covers(
            {"registration_type": r.registration_type, "start_date": r.start_date, "end_date": r.end_date}, today))
        squads.append({"squad_id": s.squad_id, "club_id": s.club_id, "name": s.name, "player_count": count})
    return {"league_id": league_id, "transfer_window": {"open": rl.window_open, "close": rl.window_close},
            "max_squad_size": rl.max_squad_size, "required_positions": rl.required_positions or {},
            "squads": squads}


# ---------- events write twin ----------

@router.post("/api/v1/events")
async def api_events(request: Request, user=Depends(current_user)):
    try:
        body = json.loads(await request.body())
    except ValueError:
        raise validation_error(["body"], "malformed JSON")

    def run():
        with SessionLocal() as db:
            # Authorization before validation (contract §2.11).
            if not isinstance(body, dict) or not can_score(db, user, body):
                raise AppError(403, "FORBIDDEN", "not allowed to score this match")
            return events.append_event(db, body)

    status, response = await run_in_threadpool(run)
    return JSONResponse(status_code=status, content=response)


# ---------- demo seed ----------

@router.post("/api/v1/dev/demo-seed")
def demo_seed():
    from app.demo_seed import seed_demo
    with SessionLocal() as db:
        seed_demo(db)
    return {"status": "demo_seeded"}
