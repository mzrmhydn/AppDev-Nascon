# Register a league with fixtures + read its standings (FR-1.4, spec §5.8, §5.10).
# Every fixture becomes a match stream (status upcoming); standings are recomputed from the logs on every call.
import re

from sqlalchemy import select, text

from app.domain.sport_config import TIE_BREAK_TOKENS
from app.domain.standings import compute_standings
from app.errors import AppError
from app.models_league import League, Match
from app.services.events import projection_for
from app.services.sports import get_sport_config

ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def _is_id(x):
    return isinstance(x, str) and ID_RE.match(x) is not None


def _is_int(x):
    return type(x) is int


def _bad_fields(body):
    """Step 1 of §5.8: list of bad field names ([] = ok)."""
    if not isinstance(body, dict):
        return ["body"]
    bad = []
    if not _is_id(body.get("league_id")):
        bad.append("league_id")
    if not _is_id(body.get("sport_id")):
        bad.append("sport_id")

    teams = body.get("teams")
    teams_ok = (isinstance(teams, list) and 2 <= len(teams) <= 40
                and all(_is_id(t) for t in teams) and len(set(teams)) == len(teams))
    if not teams_ok:
        bad.append("teams")

    fixtures = body.get("fixtures")
    fixtures_ok = isinstance(fixtures, list)
    if fixtures_ok:
        seen = set()
        for f in fixtures:
            if (not isinstance(f, dict) or not _is_id(f.get("match_id")) or f["match_id"] in seen
                    or f.get("home") == f.get("away")
                    or (teams_ok and (f.get("home") not in teams or f.get("away") not in teams))
                    or not _is_id(f.get("home")) or not _is_id(f.get("away"))):
                fixtures_ok = False
                break
            seen.add(f["match_id"])
    if not fixtures_ok:
        bad.append("fixtures")

    if "points" in body:
        p = body["points"]
        if not (isinstance(p, dict) and all(_is_int(p.get(k, 0)) for k in ("win", "draw", "loss"))):
            bad.append("points")

    if "tie_break_order" in body:
        order = body["tie_break_order"]
        if not (isinstance(order, list) and all(t in TIE_BREAK_TOKENS for t in order)
                and len(set(order)) == len(order)):
            bad.append("tie_break_order")

    q = body.get("qualification")
    spots = q.get("spots") if isinstance(q, dict) else None
    if not (_is_int(spots) and spots >= 1 and (not teams_ok or spots <= len(teams))):
        bad.append("qualification")

    if "lots_seed" in body and not _is_int(body["lots_seed"]):
        bad.append("lots_seed")
    return bad


def _last_reset_seed(db):
    # settings table belongs to Track A; fall back to 42 if it is missing or empty.
    try:
        value = db.execute(text("SELECT value FROM settings WHERE key = 'last_reset_seed'")).scalar()
        return int(value) if value is not None else 42
    except Exception:
        db.rollback()
        return 42


def create_league(db, body):
    """Return (201, response). Order: 400 -> 404 SPORT_NOT_FOUND -> 409 LEAGUE_EXISTS -> 409 MATCH_EXISTS."""
    bad = _bad_fields(body)
    if bad:
        raise AppError(400, "VALIDATION_ERROR", "invalid league", {"fields": bad})
    if get_sport_config(db, body["sport_id"]) is None:
        raise AppError(404, "SPORT_NOT_FOUND", "unknown sport", {"sport_id": body["sport_id"]})
    if db.get(League, body["league_id"]) is not None:
        raise AppError(409, "LEAGUE_EXISTS", "league already exists", {"league_id": body["league_id"]})
    match_ids = [f["match_id"] for f in body["fixtures"]]
    if match_ids:
        used = db.execute(select(Match.match_id).where(Match.match_id.in_(match_ids))).scalars().all()
        if used:
            raise AppError(409, "MATCH_EXISTS", "match id already used", {"match_ids": sorted(used)})

    points = {"win": 3, "draw": 1, "loss": 0}
    points.update(body.get("points", {}))
    db.add(League(
        league_id=body["league_id"], tenant_id=None, sport_id=body["sport_id"], teams=body["teams"],
        points={"win": points["win"], "draw": points["draw"], "loss": points["loss"]},
        tie_break_order=body.get("tie_break_order"),  # None -> the sport's order at read time
        qualification_spots=body["qualification"]["spots"],
        lots_seed=body["lots_seed"] if "lots_seed" in body else _last_reset_seed(db),
        created_via="audit",
    ))
    db.flush()  # league row first (keeps insert order obvious)
    for f in body["fixtures"]:
        db.add(Match(match_id=f["match_id"], league_id=body["league_id"], sport_id=body["sport_id"],
                     home_team_id=f["home"], away_team_id=f["away"]))
    db.commit()
    return 201, {"league_id": body["league_id"], "status": "created",
                 "team_count": len(body["teams"]), "fixture_count": len(body["fixtures"])}


def get_standings(db, league_id):
    league = db.get(League, league_id)
    if league is None:
        raise AppError(404, "LEAGUE_NOT_FOUND", "unknown league", {"league_id": league_id})
    if league.sport_id is None:
        # baseline league with no sport/fixtures yet: an empty table, not an error
        return {"league_id": league_id, "sport_id": None,
                "qualification_spots": league.qualification_spots, "table": [], "h2h": {}}
    sport_config = get_sport_config(db, league.sport_id)
    matches = db.execute(
        select(Match).where(Match.league_id == league_id).order_by(Match.match_id)
    ).scalars().all()
    # a stand-alone match_init may name this league; only fixtures between league teams count
    matches = [m for m in matches if m.home_team_id in league.teams and m.away_team_id in league.teams]
    league_dict = {
        "league_id": league.league_id, "teams": league.teams, "points": league.points,
        "tie_break_order": league.tie_break_order, "qualification_spots": league.qualification_spots,
        "lots_seed": league.lots_seed,
    }
    return compute_standings(league_dict, sport_config, [projection_for(db, m) for m in matches])
