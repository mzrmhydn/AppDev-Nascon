# Offline sync: replay a device's queued actions through the SAME services as /events and /roster/transfer
# (NFR-4, spec §5.14). Only a bad envelope is a 400; every per-action outcome is reported inside a 200.
from datetime import datetime

from sqlalchemy import select

from app.domain.roster_rules import validate_transfer
from app.domain.rule_error import RuleError
from app.domain.scoring import is_id
from app.errors import AppError, validation_error
from app.models import (Idempotency, Match, MatchEvent, OfflineAction, Player, RosterLeague, Squad)
from app.services import events, roster
from app.signing import canonical

ACTION_TYPES = ["score_event", "roster_transfer"]


def _is_timestamp(text):
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except (TypeError, ValueError):
        return False


def validate_envelope(body):
    if not isinstance(body, dict):
        raise validation_error(["body"])
    fields = []
    if not is_id(body.get("device_id")):
        fields.append("device_id")
    actions = body.get("actions")
    if not isinstance(actions, list) or not (1 <= len(actions) <= 100):
        fields.append("actions")
    else:
        for a in actions:
            if (not isinstance(a, dict) or not is_id(a.get("action_id")) or a.get("type") not in ACTION_TYPES
                    or not _is_timestamp(a.get("queued_at")) or type(a.get("base_version")) is not int
                    or a["base_version"] < 0 or not isinstance(a.get("payload"), dict)):
                fields.append("actions")
                break
    if fields:
        raise validation_error(fields)


class Rejected(Exception):
    def __init__(self, code):
        self.code = code


class _Duplicate(Exception):
    pass


# ---------- versions ----------

def score_version(db, payload):
    match_id = payload.get("match_id")
    return events.match_version(db, match_id) if isinstance(match_id, str) else 0


def roster_version(db, payload):
    player_id = payload.get("player_id")
    if not isinstance(player_id, str) or db.get(Player, player_id) is None:
        return 0
    return roster.audit_count(db, player_id)


def current_version(db, action):
    if action["type"] == "score_event":
        return score_version(db, action["payload"])
    return roster_version(db, action["payload"])


# ---------- steps 2-4 per type ----------

def _score_precheck(db, payload):
    """Schema (400) -> identical event already stored (duplicate) -> unknown match (404). True = duplicate."""
    try:
        events._check_envelope(payload)
    except AppError as err:
        raise Rejected(err.code)
    existing = db.scalar(select(MatchEvent).where(MatchEvent.event_id == payload["event_id"]))
    if existing is not None and canonical(existing.request) == canonical(payload):
        return True
    if payload["type"] != "match_init" and db.get(Match, payload["match_id"]) is None:
        raise Rejected("MATCH_NOT_FOUND")
    return False


def _roster_precheck(db, payload):
    """Schema (400) -> identical request_id replay (duplicate) -> 404s in the spec order. True = duplicate."""
    try:
        validate_transfer(payload)
    except RuleError as err:
        raise Rejected(err.code)
    stored = db.get(Idempotency, ("transfer", payload["request_id"]))
    if stored is not None and canonical(stored.request) == canonical(payload):
        return True
    if db.get(RosterLeague, payload["league_id"]) is None:
        raise Rejected("LEAGUE_NOT_FOUND")
    if db.get(Player, payload["player_id"]) is None:
        raise Rejected("PLAYER_NOT_FOUND")
    for squad_id in [payload["from_squad_id"], payload.get("to_squad_id")]:
        if squad_id is not None and db.get(Squad, squad_id) is None:
            raise Rejected("SQUAD_NOT_FOUND")
    roster.materialize_loan_returns(db, payload["player_id"], payload["effective_date"])
    return False


# ---------- one action ----------

def process_action(db, device_id, action, authorize=None):
    """Return the result dict (without processed_order). Runs in its own transaction."""
    payload = action["payload"]
    result = {"action_id": action["action_id"], "status": "applied", "resolution": "appended",
              "error_code": None, "server_version": 0, "signature": None}
    try:
        if db.get(OfflineAction, (device_id, action["action_id"])) is not None:
            raise _Duplicate()
        if authorize is not None and not authorize(db, action):
            raise Rejected("FORBIDDEN")
        precheck = _score_precheck if action["type"] == "score_event" else _roster_precheck
        if precheck(db, payload):
            raise _Duplicate()
        current = current_version(db, action)
        if action["base_version"] > current:
            raise Rejected("INVALID_BASE_VERSION")
        try:
            if action["type"] == "score_event":
                _, body = events.append_event(db, payload)
                result["signature"] = body["signature"]
            else:
                roster.transfer(db, payload)
        except (AppError, RuleError) as err:
            raise Rejected(err.code)
        if action["base_version"] < current:
            result["resolution"] = "rebased_append"
    except _Duplicate:
        db.rollback()
        result.update(status="duplicate", resolution="skipped_duplicate")
    except Rejected as rej:
        db.rollback()
        result.update(status="rejected", resolution="server_wins", error_code=rej.code, signature=None)
    result["server_version"] = current_version(db, action)
    return result


def sync(db, body, authorize=None):
    validate_envelope(body)
    device_id = body["device_id"]
    actions = body["actions"]
    order = sorted(range(len(actions)), key=lambda i: (actions[i]["queued_at"], i))  # ties: array order
    results = [None] * len(actions)
    for position, index in enumerate(order, start=1):
        action = actions[index]
        result = process_action(db, device_id, action, authorize)
        result["processed_order"] = position
        results[index] = result
        # Remember every outcome, so re-sending the same request answers "duplicate" for every action.
        if db.get(OfflineAction, (device_id, action["action_id"])) is None:
            db.add(OfflineAction(device_id=device_id, action_id=action["action_id"], request=action,
                                 result=result))
        db.commit()
    keys = ["action_id", "status", "resolution", "error_code", "processed_order", "server_version", "signature"]
    ordered = [{k: r[k] for k in keys} for r in results]
    summary = {s: sum(1 for r in ordered if r["status"] == s) for s in ["applied", "rejected", "duplicate"]}
    return {"device_id": device_id, "results": ordered, "summary": summary}
