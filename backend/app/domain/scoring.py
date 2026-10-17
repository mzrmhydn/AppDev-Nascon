# Event-sourced score projection + event rule checks (FR-1.1, spec §5.9).
# Pure functions: the score is rebuilt from the event list every time. Only scoring_model and
# config values are used — never sport or event names.
from app.domain.rule_error import RuleError

EVENT_TYPES = ["match_init", "match_start", "score", "discipline",
               "tiebreak_winner", "match_end", "compensation"]
COMPENSABLE_TYPES = ["score", "discipline", "tiebreak_winner"]


def is_id(x):
    # Spec §5.2 id rule: 1–64 chars from A-Za-z0-9_.:-
    if not isinstance(x, str) or not (1 <= len(x) <= 64):
        return False
    return all(c.isascii() and (c.isalnum() or c in "_.:-") for c in x)


# ---------- payload schema (400) ----------

def payload_bad_fields(event_type, payload):
    """Return bad payload field names for this event type ([] = ok). Unknown fields are ignored."""
    if not isinstance(payload, dict):
        return ["payload"]
    bad = []
    if event_type == "match_init":
        for key in ["sport_id", "home_team_id", "away_team_id"]:
            if not is_id(payload.get(key)):
                bad.append(key)
        if payload.get("league_id") is not None and not is_id(payload.get("league_id")):
            bad.append("league_id")
        if not bad and payload["home_team_id"] == payload["away_team_id"]:
            bad.append("away_team_id")
    elif event_type == "score":
        if not is_id(payload.get("team_id")):
            bad.append("team_id")
        if not isinstance(payload.get("event_type"), str):
            bad.append("event_type")
    elif event_type == "discipline":
        if not is_id(payload.get("team_id")):
            bad.append("team_id")
        if type(payload.get("points")) is not int:
            bad.append("points")
    elif event_type == "tiebreak_winner":
        if not is_id(payload.get("team_id")):
            bad.append("team_id")
    elif event_type == "compensation":
        if not is_id(payload.get("compensates")):
            bad.append("compensates")
        if not isinstance(payload.get("reason"), str):
            bad.append("reason")
    return bad


# ---------- projection ----------

def _compensations(events):
    """Map target event_id -> compensating event_id."""
    compensated_by = {}
    for e in events:
        if e["type"] == "compensation":
            compensated_by[e["payload"]["compensates"]] = e["event_id"]
    return compensated_by


def _empty_side(team_id, model):
    innings = model == "innings"
    return {
        "team_id": team_id,
        "score": 0,
        "wickets": 0 if innings else None,
        "balls": 0 if innings else None,
        "overs": None,
        "fair_play": 0,
    }


def project(sport_config, match, events):
    """Rebuild the /score response from the log.

    match  = {"match_id", "sport_id", "league_id", "home_team_id", "away_team_id"}
    events = [{"sequence", "event_id", "type", "payload", "signature"}, ...] in sequence order
    """
    model = sport_config["scoring_model"]
    scoring_events = sport_config["scoring_events"]
    compensated_by = _compensations(events)

    home = _empty_side(match["home_team_id"], model)
    away = _empty_side(match["away_team_id"], model)
    sides = {home["team_id"]: home, away["team_id"]: away}
    status = "upcoming"
    tiebreak_team = None

    for e in events:
        etype = e["type"]
        payload = e["payload"]
        # Compensated events and compensations themselves are neutral.
        if e["event_id"] in compensated_by or etype == "compensation":
            continue
        if etype == "match_start":
            status = "in_progress"
        elif etype == "match_end":
            status = "completed"
        elif etype == "score":
            side = sides[payload["team_id"]]
            rule = scoring_events[payload["event_type"]]
            if model == "event":
                side["score"] += rule["points"]
            elif model == "innings":
                side["score"] += rule["runs"]
                if rule["legal_ball"]:
                    side["balls"] += 1
                if rule["wicket"]:
                    side["wickets"] += 1
            else:
                side["score"] += rule["rounds"]
        elif etype == "discipline":
            sides[payload["team_id"]]["fair_play"] += payload["points"]
        elif etype == "tiebreak_winner":
            tiebreak_team = payload["team_id"]

    if model == "innings":
        bpo = sport_config["periods"]["balls_per_over"]
        for side in (home, away):
            side["overs"] = f"{side['balls'] // bpo}.{side['balls'] % bpo}"

    outcome, winner = _outcome(sport_config, status, home, away, tiebreak_team)

    return {
        "match_id": match["match_id"],
        "sport_id": match["sport_id"],
        "league_id": match.get("league_id"),
        "status": status,
        "outcome": outcome,
        "winner_team_id": winner,
        "tiebreak_winner_team_id": tiebreak_team,
        "home": home,
        "away": away,
        "version": len(events),
        "events": [
            {
                "sequence": e["sequence"],
                "event_id": e["event_id"],
                "type": e["type"],
                "payload": e["payload"],
                "signature": e["signature"],
                "compensated": e["event_id"] in compensated_by,
                "compensated_by": compensated_by.get(e["event_id"]),
            }
            for e in events
        ],
    }


def _outcome(sport_config, status, home, away, tiebreak_team):
    """Return (outcome, winner_team_id)."""
    if home["score"] > away["score"]:
        winner = home["team_id"]
    elif away["score"] > home["score"]:
        winner = away["team_id"]
    else:
        winner = tiebreak_team  # level: the active tiebreak winner, else None

    if status != "completed":
        return "pending", None
    if winner == home["team_id"]:
        return "home_win", winner
    if winner == away["team_id"]:
        return "away_win", winner
    if sport_config["draw_allowed"]:
        return "draw", None
    return "undecided", None


# ---------- limits ----------

def innings_complete(sport_config, side):
    p = sport_config["periods"]
    max_balls = p["innings_per_team"] * p["overs_per_innings"] * p["balls_per_over"]
    max_wickets = p["innings_per_team"] * p["wickets_per_innings"]
    return side["balls"] >= max_balls or side["wickets"] >= max_wickets


def series_decided(sport_config, projection):
    needed = (sport_config["periods"]["best_of"] + 1) // 2
    return projection["home"]["score"] >= needed or projection["away"]["score"] >= needed


# ---------- rule table for a new event (after match exists) ----------

def check_event(sport_config, projection, event_type, payload, target_event=None, match_id=None):
    """Raise RuleError if the event may not be appended. Checks run 400 -> 404 -> 409.

    projection   = project(...) of the match's current log
    target_event = for compensation: the event with id payload["compensates"] (any match) or None
    """
    team_ids = [projection["home"]["team_id"], projection["away"]["team_id"]]
    status = projection["status"]

    # 400 checks
    if event_type in ["score", "discipline", "tiebreak_winner"]:
        if payload["team_id"] not in team_ids:
            raise RuleError(400, "VALIDATION_ERROR", "team_id must be the home or away team",
                            {"fields": ["team_id"]})
    if event_type == "score" and payload["event_type"] not in sport_config["scoring_events"]:
        raise RuleError(400, "UNKNOWN_EVENT_TYPE", "event_type is not defined for this sport",
                        {"event_type": payload["event_type"]})

    if event_type == "match_init":
        raise RuleError(409, "MATCH_EXISTS", "match already exists")

    if event_type == "match_start":
        if status != "upcoming":
            raise RuleError(409, "ILLEGAL_TRANSITION", f"cannot start a match that is {status}")

    elif event_type == "score":
        if status != "in_progress":
            raise RuleError(409, "MATCH_NOT_IN_PROGRESS", "match is not in progress")
        model = sport_config["scoring_model"]
        if model == "innings":
            side = projection["home"] if payload["team_id"] == team_ids[0] else projection["away"]
            if innings_complete(sport_config, side):
                raise RuleError(409, "INNINGS_COMPLETE", "this team's innings is complete")
        elif model == "round":
            if series_decided(sport_config, projection):
                raise RuleError(409, "SERIES_ALREADY_DECIDED", "the series is already decided")

    elif event_type in ["discipline", "tiebreak_winner"]:
        if status != "in_progress":
            raise RuleError(409, "MATCH_NOT_IN_PROGRESS", "match is not in progress")

    elif event_type == "match_end":
        if status != "in_progress":
            raise RuleError(409, "ILLEGAL_TRANSITION", f"cannot end a match that is {status}")
        level = projection["home"]["score"] == projection["away"]["score"]
        if level and not sport_config["draw_allowed"] and projection["tiebreak_winner_team_id"] is None:
            raise RuleError(409, "TIE_NOT_ALLOWED", "score is level and draws are not allowed")

    elif event_type == "compensation":
        target_id = payload["compensates"]
        if target_event is None:
            raise RuleError(404, "EVENT_NOT_FOUND", "event to compensate not found",
                            {"event_id": target_id})
        already = any(e["compensated"] for e in projection["events"] if e["event_id"] == target_id)
        if (target_event.get("match_id") != match_id
                or target_event["type"] not in COMPENSABLE_TYPES
                or already):
            raise RuleError(409, "INVALID_COMPENSATION", "event cannot be compensated",
                            {"event_id": target_id})
