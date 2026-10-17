# Validates and normalises a "mystery sport" JSON config (FR-1.1, spec §5.6).
# Pure functions: no DB, no HTTP. The service layer turns bad fields into 400 VALIDATION_ERROR.
import re

SCORING_MODELS = ["event", "innings", "round"]
OVERTIME_POLICIES = ["none", "extra_time", "shootout", "golden_score", "super_over"]
TIE_BREAK_TOKENS = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]

SPORT_ID_RE = re.compile(r"^[a-z0-9_-]{2,40}$")
EVENT_KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")


def is_int(x):
    # Strict: bool is a subclass of int in Python, and "1" is not an int.
    return type(x) is int


def is_bool(x):
    return type(x) is bool


def _periods_ok(model, periods):
    if not isinstance(periods, dict):
        return False
    if model == "event":
        count = periods.get("count")
        minutes = periods.get("duration_minutes")
        return is_int(count) and count >= 1 and is_int(minutes) and minutes >= 1
    if model == "innings":
        keys = ["innings_per_team", "overs_per_innings", "balls_per_over", "wickets_per_innings"]
        return all(is_int(periods.get(k)) and periods.get(k) >= 1 for k in keys)
    if model == "round":
        best_of = periods.get("best_of")
        return is_int(best_of) and best_of >= 1 and best_of % 2 == 1
    return False


def _scoring_value_ok(model, value):
    if not isinstance(value, dict):
        return False
    if model == "event":
        return is_int(value.get("points")) and value["points"] >= 1
    if model == "innings":
        return (is_int(value.get("runs")) and value["runs"] >= 0
                and is_bool(value.get("legal_ball")) and is_bool(value.get("wicket")))
    if model == "round":
        return is_int(value.get("rounds")) and value["rounds"] >= 1
    return False


def _scoring_events_ok(model, events):
    if not isinstance(events, dict) or len(events) == 0:
        return False
    for key, value in events.items():
        if not EVENT_KEY_RE.match(key) or not _scoring_value_ok(model, value):
            return False
    return True


def _overtime_ok(overtime):
    if not isinstance(overtime, dict):
        return False
    if overtime.get("policy") not in OVERTIME_POLICIES:
        return False
    if "duration_minutes" in overtime:
        minutes = overtime["duration_minutes"]
        return is_int(minutes) and minutes >= 0
    return True


def _tie_break_ok(order):
    if not isinstance(order, list):
        return False
    for token in order:
        if not isinstance(token, str) or token not in TIE_BREAK_TOKENS:
            return False
    return len(set(order)) == len(order)


def _roster_ok(roster):
    if not isinstance(roster, dict):
        return False
    lo = roster.get("min_squad_size")
    hi = roster.get("max_squad_size")
    if not (is_int(lo) and is_int(hi) and lo >= 1 and hi >= 1 and lo <= hi):
        return False
    positions = roster.get("required_positions")
    if not isinstance(positions, dict):
        return False
    return all(is_int(n) and n >= 0 for n in positions.values())


def validate_sport_config(body):
    """Return the list of bad top-level field names ([] means valid)."""
    if not isinstance(body, dict):
        return ["body"]
    bad = []

    sport_id = body.get("sport_id")
    if not isinstance(sport_id, str) or not SPORT_ID_RE.match(sport_id):
        bad.append("sport_id")

    name = body.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 80):
        bad.append("name")

    model = body.get("scoring_model")
    if model not in SCORING_MODELS:
        bad.append("scoring_model")
        # periods / scoring_events can't be checked without a valid model
        bad.append("periods")
        bad.append("scoring_events")
    else:
        if not _periods_ok(model, body.get("periods")):
            bad.append("periods")
        if not _scoring_events_ok(model, body.get("scoring_events")):
            bad.append("scoring_events")

    if not is_bool(body.get("draw_allowed")):
        bad.append("draw_allowed")

    if not _overtime_ok(body.get("overtime")):
        bad.append("overtime")

    # optional: missing or null both mean "use the default order"
    if body.get("tie_break_order") is not None and not _tie_break_ok(body["tie_break_order"]):
        bad.append("tie_break_order")

    if not _roster_ok(body.get("roster")):
        bad.append("roster")

    return bad


def normalize_tie_break_order(order):
    """Default = full list; draw_lots is always applied last, even if omitted."""
    if order is None:
        return list(TIE_BREAK_TOKENS)
    result = [token for token in order if token != "draw_lots"]
    result.append("draw_lots")
    return result


def normalize_sport_config(body):
    """Build the stored config from a VALID body. Unknown fields are dropped (spec §5.2)."""
    model = body["scoring_model"]
    if model == "event":
        period_keys = ["count", "duration_minutes"]
        event_keys = ["points"]
    elif model == "innings":
        period_keys = ["innings_per_team", "overs_per_innings", "balls_per_over", "wickets_per_innings"]
        event_keys = ["runs", "legal_ball", "wicket"]
    else:
        period_keys = ["best_of"]
        event_keys = ["rounds"]

    overtime = {"policy": body["overtime"]["policy"]}
    if "duration_minutes" in body["overtime"]:
        overtime["duration_minutes"] = body["overtime"]["duration_minutes"]

    roster = body["roster"]
    return {
        "sport_id": body["sport_id"],
        "name": body["name"],
        "scoring_model": model,
        "periods": {k: body["periods"][k] for k in period_keys},
        "scoring_events": {
            key: {k: value[k] for k in event_keys}
            for key, value in body["scoring_events"].items()
        },
        "draw_allowed": body["draw_allowed"],
        "overtime": overtime,
        "tie_break_order": normalize_tie_break_order(body.get("tie_break_order")),
        "roster": {
            "min_squad_size": roster["min_squad_size"],
            "max_squad_size": roster["max_squad_size"],
            "required_positions": dict(roster["required_positions"]),
        },
    }
