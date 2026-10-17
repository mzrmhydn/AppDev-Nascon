# Append-only match event log + score read (FR-1.1, spec §5.9). DB glue only; all rules live in domain/scoring.py.
# append_event() is shared by /audit/v1/events, /api/v1/events, offline-sync and the demo seed.
import json
import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.domain.rule_error import RuleError
from app.domain.scoring import EVENT_TYPES, check_event, payload_bad_fields, project
from app.errors import AppError
from app.models_league import Match, MatchEvent
from app.services.rule_error_bridge import as_app_error
from app.services.sports import get_sport_config
from app.signing import sign

ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _check_envelope(body):
    """Step 1: 400 for a bad envelope or payload. Returns nothing; raises AppError."""
    if not isinstance(body, dict):
        raise AppError(400, "VALIDATION_ERROR", "body must be an object", {"fields": ["body"]})
    bad = []
    for key in ["event_id", "match_id"]:
        if not isinstance(body.get(key), str) or not ID_RE.match(body[key]):
            bad.append(key)
    if body.get("type") not in EVENT_TYPES:
        bad.append("type")
    if not isinstance(body.get("payload"), dict):
        bad.append("payload")
    if not bad:
        bad = payload_bad_fields(body["type"], body["payload"])
    if bad:
        raise AppError(400, "VALIDATION_ERROR", "invalid event", {"fields": bad})


def _match_dict(match):
    return {
        "match_id": match.match_id, "sport_id": match.sport_id, "league_id": match.league_id,
        "home_team_id": match.home_team_id, "away_team_id": match.away_team_id,
    }


def _events_of(db, match_id):
    rows = db.execute(
        select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.sequence)
    ).scalars().all()
    return [row.as_dict() for row in rows]


def append_event(db, body, _retry=True):
    """Return (status_code, response). Raises AppError on any rejection. body = raw JSON as received."""
    _check_envelope(body)
    event_id, match_id, etype, payload = body["event_id"], body["match_id"], body["type"], body["payload"]

    # Step 2: idempotency — event ids are unique across all matches.
    existing = db.execute(select(MatchEvent).where(MatchEvent.event_id == event_id)).scalar_one_or_none()
    if existing is not None:
        if _canonical(existing.request) == _canonical(body):
            return 200, existing.response
        raise AppError(409, "DUPLICATE_EVENT_ID", "event_id already used with a different body",
                       {"event_id": event_id})

    # Step 3: stream existence.
    if etype == "match_init":
        sport_config = get_sport_config(db, payload["sport_id"])
        if sport_config is None:
            raise AppError(404, "SPORT_NOT_FOUND", "unknown sport", {"sport_id": payload["sport_id"]})
        if db.get(Match, match_id) is not None:
            raise AppError(409, "MATCH_EXISTS", "match already exists", {"match_id": match_id})
        db.add(Match(match_id=match_id, league_id=payload.get("league_id"), sport_id=payload["sport_id"],
                     home_team_id=payload["home_team_id"], away_team_id=payload["away_team_id"]))
        try:
            db.flush()
        except IntegrityError:
            # Two identical match_init requests raced: redo from step 2 (gives 200 replay or 409).
            db.rollback()
            if _retry:
                return append_event(db, body, _retry=False)
            raise AppError(409, "MATCH_EXISTS", "match already exists", {"match_id": match_id})
        events = []
    else:
        if db.get(Match, match_id) is None:
            raise AppError(404, "MATCH_NOT_FOUND", "unknown match", {"match_id": match_id})
        # Step 4: lock the match row so two appends can't take the same sequence number.
        match = db.execute(select(Match).where(Match.match_id == match_id).with_for_update()).scalar_one()
        sport_config = get_sport_config(db, match.sport_id)
        events = _events_of(db, match_id)
        projection = project(sport_config, _match_dict(match), events)

        target = None
        if etype == "compensation":
            row = db.execute(
                select(MatchEvent).where(MatchEvent.event_id == payload["compensates"])
            ).scalar_one_or_none()
            target = row.as_dict() if row is not None else None
        try:
            check_event(sport_config, projection, etype, payload, target_event=target, match_id=match_id)
        except RuleError as err:
            db.rollback()
            raise as_app_error(err)

    sequence = len(events) + 1
    signature = sign(event_id, payload)
    response = {"event_id": event_id, "match_id": match_id, "type": etype,
                "sequence": sequence, "match_version": sequence, "signature": signature}
    db.add(MatchEvent(match_id=match_id, sequence=sequence, event_id=event_id, type=etype,
                      payload=payload, signature=signature, request=body, response=response))
    try:
        db.commit()
    except IntegrityError:
        # Same event_id inserted by a parallel request: answer like a replay.
        db.rollback()
        if _retry:
            return append_event(db, body, _retry=False)
        raise
    _notify(match_id, sequence)
    return 201, response


def _notify(match_id, version):
    # A broadcast failure must never fail the request (plan 09).
    try:
        from app import realtime
        realtime.notify(match_id, {"type": "match_updated", "match_id": match_id, "version": version})
    except Exception:
        pass


def match_version(db, match_id):
    """Number of events of a match (0 for a league fixture with no events)."""
    return db.execute(
        select(func.count()).select_from(MatchEvent).where(MatchEvent.match_id == match_id)
    ).scalar_one()


def projection_for(db, match):
    """project() of one Match row (used by /score and standings)."""
    return project(get_sport_config(db, match.sport_id), _match_dict(match), _events_of(db, match.match_id))


def get_score(db, match_id):
    match = db.get(Match, match_id)
    if match is None:
        raise AppError(404, "MATCH_NOT_FOUND", "unknown match", {"match_id": match_id})
    return projection_for(db, match)
