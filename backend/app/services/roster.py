# Roster setup, transfers/loans/releases, lazy loan returns and history (FR-2.2, spec §5.11).
# Rules live in domain/roster_rules.py; this file is the DB glue. transfer() is reused by offline sync.
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app.domain.roster_rules import (ROLES, check_transfer, current_registration, next_day, parse_date,
                                     validate_transfer)
from app.domain.scoring import is_id
from app.errors import AppError, validation_error
from app.models import (Idempotency, LiveMatch, Player, Registration, RosterAudit, RosterLeague, Sport,
                        Squad)
from app.signing import canonical


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.now(timezone.utc).date().isoformat()


def reg_dict(r):
    return {"id": r.id, "player_id": r.player_id, "league_id": r.league_id, "squad_id": r.squad_id,
            "parent_squad_id": r.parent_squad_id, "registration_type": r.registration_type,
            "start_date": r.start_date, "end_date": r.end_date, "loan_end_date": r.loan_end_date, "role": r.role}


def registration_json(r):
    return {"player_id": r.player_id, "league_id": r.league_id, "squad_id": r.squad_id,
            "parent_squad_id": r.parent_squad_id, "registration_type": r.registration_type,
            "start_date": r.start_date, "loan_end_date": r.loan_end_date, "role": r.role}


def audit_json(a):
    return {"audit_id": a.audit_id, "action": a.action, "player_id": a.player_id, "league_id": a.league_id,
            "from_squad_id": a.from_squad_id, "to_squad_id": a.to_squad_id, "effective_date": a.effective_date,
            "state": a.state, "who": a.who, "when": a.when, "why": a.why}


def append_audit(db, **fields):
    seq = (db.scalar(select(func.max(RosterAudit.seq))) or 0) + 1
    entry = RosterAudit(seq=seq, audit_id=f"au-{seq:04d}", when=now_iso(), **fields)
    db.add(entry)
    db.flush()
    return entry


# ---------- setup ----------

def _validate_setup(body):
    if not isinstance(body, dict):
        raise validation_error(["body"])
    fields = []
    league = body.get("league")
    if not isinstance(league, dict):
        raise validation_error(["league"])
    for key in ["league_id", "tenant_id", "sport_id"]:
        if not is_id(league.get(key)):
            fields.append(key)
    window = league.get("transfer_window")
    if (not isinstance(window, dict) or parse_date(window.get("open")) is None
            or parse_date(window.get("close")) is None or window["open"] > window["close"]):
        fields.append("transfer_window")
    size = league.get("max_squad_size")
    if size is not None and (type(size) is not int or size < 1):
        fields.append("max_squad_size")
    positions = league.get("required_positions")
    if positions is not None and (not isinstance(positions, dict)
                                  or not all(type(n) is int and n >= 0 for n in positions.values())):
        fields.append("required_positions")

    squads = body.get("squads")
    squad_ids = []
    if not isinstance(squads, list) or not all(
            isinstance(s, dict) and is_id(s.get("squad_id")) and isinstance(s.get("club_id"), str)
            and is_id(s.get("tenant_id")) and isinstance(s.get("name"), str) for s in squads):
        fields.append("squads")
    else:
        squad_ids = [s["squad_id"] for s in squads]
        if len(set(squad_ids)) != len(squad_ids):
            fields.append("squads")
    players = body.get("players", [])
    if not isinstance(players, list) or not all(
            isinstance(p, dict) and is_id(p.get("player_id")) and isinstance(p.get("name"), str)
            and isinstance(p.get("position"), str) and p.get("squad_id") in squad_ids
            and p.get("role") in ROLES for p in players):
        fields.append("players")
    elif len({p["player_id"] for p in players}) != len(players):
        fields.append("players")
    live = body.get("matches_in_progress", [])
    if not isinstance(live, list) or not all(
            isinstance(m, dict) and is_id(m.get("match_id")) and isinstance(m.get("home_squad_id"), str)
            and isinstance(m.get("away_squad_id"), str) for m in live):
        fields.append("matches_in_progress")
    if fields:
        raise validation_error(fields)


def setup(db, body):
    _validate_setup(body)
    league = body["league"]
    league_id = league["league_id"]
    sport = db.get(Sport, league["sport_id"])
    if sport is None:
        raise AppError(404, "SPORT_NOT_FOUND", "sport not found", {"sport_id": league["sport_id"]})
    roster_cfg = sport.config["roster"]

    # Re-sending the same league_id replaces that league's roster state.
    for model in [Squad, Registration, RosterAudit, LiveMatch]:
        db.execute(delete(model).where(model.league_id == league_id))
    for row in db.scalars(select(Idempotency).where(Idempotency.scope == "transfer")).all():
        if row.request.get("league_id") == league_id:
            db.delete(row)
    db.execute(delete(RosterLeague).where(RosterLeague.league_id == league_id))
    db.flush()

    db.add(RosterLeague(
        league_id=league_id, tenant_id=league["tenant_id"], sport_id=league["sport_id"],
        window_open=league["transfer_window"]["open"], window_close=league["transfer_window"]["close"],
        max_squad_size=league.get("max_squad_size") or roster_cfg["max_squad_size"],
        required_positions=(league["required_positions"] if league.get("required_positions") is not None
                            else roster_cfg["required_positions"]),
    ))
    squads = {}
    for s in body["squads"]:
        squads[s["squad_id"]] = s
        # A squad id may exist from another league's setup: replace it.
        db.execute(delete(Squad).where(Squad.squad_id == s["squad_id"]))
        db.add(Squad(squad_id=s["squad_id"], league_id=league_id, club_id=s["club_id"],
                     tenant_id=s["tenant_id"], name=s["name"]))
    counts = {squad_id: 0 for squad_id in squads}
    for p in body.get("players", []):
        squad = squads[p["squad_id"]]
        player = db.get(Player, p["player_id"])
        if player is None:
            player = Player(player_id=p["player_id"])
            db.add(player)
        player.name, player.position = p["name"], p["position"]
        player.club_id, player.tenant_id = squad["club_id"], squad["tenant_id"]
        db.add(Registration(player_id=p["player_id"], league_id=league_id, squad_id=p["squad_id"],
                            registration_type="initial", start_date=league["transfer_window"]["open"],
                            role=p["role"]))
        counts[p["squad_id"]] += 1
    for m in body.get("matches_in_progress", []):
        db.add(LiveMatch(league_id=league_id, match_id=m["match_id"],
                         home_squad_id=m["home_squad_id"], away_squad_id=m["away_squad_id"]))
    db.commit()
    return {"league_id": league_id, "status": "configured", "squad_counts": counts}


# ---------- lazy loan return ----------

def materialize_loan_returns(db, player_id, as_of):
    """Write each due loan_return exactly once (the day after loan_end_date the player is back)."""
    db.get(Player, player_id, with_for_update=True)  # serialise concurrent callers (no-op on SQLite)
    loans = db.scalars(select(Registration).where(Registration.player_id == player_id,
                                                  Registration.registration_type == "loan")
                       .order_by(Registration.id)).all()
    for loan in loans:
        if not loan.loan_end_date < as_of:
            continue
        done = db.scalar(select(RosterAudit).where(RosterAudit.loan_registration_id == loan.id))
        if done is not None:
            continue
        back = next_day(loan.loan_end_date)
        db.add(Registration(player_id=player_id, league_id=loan.league_id, squad_id=loan.parent_squad_id,
                            registration_type="transfer", start_date=back, role="substitute"))
        append_audit(db, player_id=player_id, league_id=loan.league_id, action="loan_return",
                     from_squad_id=loan.squad_id, to_squad_id=loan.parent_squad_id, effective_date=back,
                     state="active", who="system", why="Automatic loan return", loan_registration_id=loan.id)
    db.flush()


# ---------- transfer ----------

def _replay(db, body):
    stored = db.get(Idempotency, ("transfer", body["request_id"]))
    if stored is None:
        return None
    if canonical(stored.request) != canonical(body):
        # Spec defines no code for this; same request_id with a different body is a bad request.
        raise validation_error(["request_id"], "request_id already used with a different body")
    return 200, stored.response


def transfer(db, body):
    validate_transfer(body)
    replay = _replay(db, body)
    if replay is not None:
        return replay

    league = db.get(RosterLeague, body["league_id"])
    if league is None:
        raise AppError(404, "LEAGUE_NOT_FOUND", "roster league not found", {"league_id": body["league_id"]})
    if db.get(Player, body["player_id"]) is None:
        raise AppError(404, "PLAYER_NOT_FOUND", "player not found", {"player_id": body["player_id"]})
    squads = {}
    for squad_id in [body["from_squad_id"], body.get("to_squad_id")]:
        if squad_id is None:
            continue
        squad = db.get(Squad, squad_id)
        if squad is None:
            raise AppError(404, "SQUAD_NOT_FOUND", "squad not found", {"squad_id": squad_id})
        squads[squad_id] = {"tenant_id": squad.tenant_id}

    day = body["effective_date"]
    materialize_loan_returns(db, body["player_id"], day)
    rows = db.scalars(select(Registration).where(Registration.league_id == league.league_id)
                      .order_by(Registration.id)).all()
    all_regs = [reg_dict(r) for r in rows]
    player_regs = [r for r in all_regs if r["player_id"] == body["player_id"]]
    member_ids = {r["player_id"] for r in all_regs}
    positions = {p.player_id: p.position for p in
                 db.scalars(select(Player).where(Player.player_id.in_(member_ids))).all()}
    league_data = {"tenant_id": league.tenant_id, "window_open": league.window_open,
                   "window_close": league.window_close, "max_squad_size": league.max_squad_size,
                   "required_positions": league.required_positions or {}}
    current = check_transfer(body, league_data, squads, player_regs, all_regs, positions)

    # Effects: close the current registration, open the new one.
    old = db.get(Registration, current["id"])
    old.end_date = day
    new_reg = None
    if body["type"] == "transfer":
        new_reg = Registration(player_id=body["player_id"], league_id=league.league_id,
                               squad_id=body["to_squad_id"], registration_type="transfer",
                               start_date=day, role="substitute")
    elif body["type"] == "loan":
        new_reg = Registration(player_id=body["player_id"], league_id=league.league_id,
                               squad_id=body["to_squad_id"], parent_squad_id=body["from_squad_id"],
                               registration_type="loan", start_date=day, end_date=next_day(body["loan_end_date"]),
                               loan_end_date=body["loan_end_date"], role="substitute")
    if new_reg is not None:
        db.add(new_reg)

    # Edge case 6: the player's squad is playing right now -> accepted but deferred.
    live = db.scalars(select(LiveMatch).where(LiveMatch.league_id == league.league_id)
                      .order_by(LiveMatch.match_id)).all()
    blocking = next((m.match_id for m in live if current["squad_id"] in (m.home_squad_id, m.away_squad_id)), None)
    state = "deferred_until_match_end" if blocking else "active"

    entry = append_audit(db, player_id=body["player_id"], league_id=league.league_id, action=body["type"],
                         from_squad_id=body["from_squad_id"], to_squad_id=body.get("to_squad_id"),
                         effective_date=day, state=state, who=body["requested_by"], why=body["reason"])
    response = {
        "request_id": body["request_id"], "status": "accepted", "state": state, "blocking_match_id": blocking,
        "registration": registration_json(new_reg) if new_reg is not None else None,
        "audit_entry": audit_json(entry),
    }
    db.add(Idempotency(scope="transfer", key=body["request_id"], request=body, status_code=201, response=response))
    db.commit()
    return 201, response


# ---------- history ----------

def history(db, player_id, as_of=None):
    if as_of is None:
        as_of = today()
    elif parse_date(as_of) is None:
        raise validation_error(["as_of"])
    if db.get(Player, player_id) is None:
        raise AppError(404, "PLAYER_NOT_FOUND", "player not found", {"player_id": player_id})
    materialize_loan_returns(db, player_id, as_of)
    db.commit()

    regs = [reg_dict(r) for r in db.scalars(select(Registration).where(Registration.player_id == player_id)
                                             .order_by(Registration.id)).all()]
    league_id = regs[-1]["league_id"] if regs else None
    current = current_registration([r for r in regs if r["league_id"] == league_id], as_of)
    entries = db.scalars(select(RosterAudit).where(RosterAudit.player_id == player_id)
                         .order_by(RosterAudit.seq)).all()
    return {
        "player_id": player_id, "as_of": as_of, "league_id": league_id,
        "current_squad_id": current["squad_id"] if current else None,
        "parent_squad_id": current["parent_squad_id"] if current else None,
        "history": [audit_json(a) for a in entries],
    }


def audit_count(db, player_id):
    """base_version for offline sync = number of audit entries of the player."""
    return db.scalar(select(func.count()).select_from(RosterAudit).where(RosterAudit.player_id == player_id))
