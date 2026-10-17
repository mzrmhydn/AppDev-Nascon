# Roster rules as pure functions: request schema, "current squad on a date", and checks 3-8 of spec §5.11
# in the exact order (FR-2.2). Registrations are plain dicts:
# {player_id, squad_id, parent_squad_id, registration_type, start_date, end_date (exclusive or None), ...}
from datetime import date, timedelta

from app.domain.rule_error import RuleError
from app.domain.scoring import is_id

TYPES = ["transfer", "loan", "release"]
ROLES = ["captain", "vice_captain", "starter", "substitute"]


def parse_date(text):
    """'YYYY-MM-DD' -> date, else None."""
    if not isinstance(text, str) or len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def next_day(text):
    return (date.fromisoformat(text) + timedelta(days=1)).isoformat()


def bad(fields, message="invalid transfer request"):
    return RuleError(400, "VALIDATION_ERROR", message, {"fields": fields})


# ---------- check 1: schema (400) ----------

def validate_transfer(body):
    if not isinstance(body, dict):
        raise bad(["body"])
    fields = []
    for key in ["request_id", "league_id", "player_id", "from_squad_id"]:
        if not is_id(body.get(key)):
            fields.append(key)
    kind = body.get("type")
    if kind not in TYPES:
        fields.append("type")
    to_squad = body.get("to_squad_id")
    if kind == "release":
        if to_squad is not None and not is_id(to_squad):
            fields.append("to_squad_id")
    elif not is_id(to_squad):
        fields.append("to_squad_id")
    effective = parse_date(body.get("effective_date"))
    if effective is None:
        fields.append("effective_date")
    loan_end = body.get("loan_end_date")
    if kind == "loan":
        end = parse_date(loan_end)
        if end is None or effective is None or end <= effective:
            fields.append("loan_end_date")
    elif loan_end is not None and parse_date(loan_end) is None:
        fields.append("loan_end_date")
    for key in ["reason", "requested_by"]:
        if not isinstance(body.get(key), str):
            fields.append(key)
    if fields:
        raise bad(fields)


# ---------- date logic ----------

def covers(reg, day):
    """Is this registration active on `day` (ISO strings compare correctly)?"""
    starts_ok = reg["registration_type"] == "initial" or reg["start_date"] <= day
    return starts_ok and (reg["end_date"] is None or day < reg["end_date"])


def current_registration(player_regs, day):
    """The player's registration on `day`, or None (released / never registered)."""
    active = [r for r in player_regs if covers(r, day)]
    return active[-1] if active else None


def squad_members(all_regs, squad_id, day):
    return [r for r in all_regs if r["squad_id"] == squad_id and covers(r, day)]


# ---------- checks 3-8 (409), first failure wins ----------

def check_transfer(body, league, squads, player_regs, all_regs, positions):
    """league = {tenant_id, window_open, window_close, max_squad_size, required_positions}
    squads = {squad_id: {"tenant_id"}}; positions = {player_id: position}."""
    kind = body["type"]
    day = body["effective_date"]
    from_id, to_id = body["from_squad_id"], body.get("to_squad_id")

    # 3. both squads in the league's tenant
    for squad_id in [from_id, to_id]:
        if squad_id is not None and squads[squad_id]["tenant_id"] != league["tenant_id"]:
            raise RuleError(409, "CROSS_TENANT_TRANSFER", "squad belongs to another tenant",
                            {"squad_id": squad_id})

    # 4. player's current squad must be from_squad_id
    current = current_registration(player_regs, day)
    if current is None or current["squad_id"] != from_id:
        raise RuleError(409, "NOT_IN_SQUAD", "player is not in from_squad_id on effective_date",
                        {"player_id": body["player_id"], "squad_id": from_id})

    # 5. window (inclusive) for transfer / loan
    if kind != "release" and not (league["window_open"] <= day <= league["window_close"]):
        raise RuleError(409, "TRANSFER_WINDOW_CLOSED", "effective_date is outside the transfer window",
                        {"window_open": league["window_open"], "window_close": league["window_close"]})

    # 6. a loaned player can't be moved
    if current["registration_type"] == "loan":
        raise RuleError(409, "PLAYER_ON_LOAN", "player is currently on loan", {"player_id": body["player_id"]})

    # 7. destination has room
    if kind != "release" and len(squad_members(all_regs, to_id, day)) + 1 > league["max_squad_size"]:
        raise RuleError(409, "SQUAD_FULL", "destination squad is full",
                        {"squad_id": to_id, "max_squad_size": league["max_squad_size"]})

    # 8. from squad keeps its minimum for the player's position
    position = positions.get(body["player_id"])
    required = league["required_positions"].get(position, 0)
    same_position = [r for r in squad_members(all_regs, from_id, day) if positions.get(r["player_id"]) == position]
    if len(same_position) - 1 < required:
        raise RuleError(409, "MIN_POSITION_VIOLATION", "from squad would drop below the minimum for this position",
                        {"squad_id": from_id, "position": position, "required": required})
    return current
