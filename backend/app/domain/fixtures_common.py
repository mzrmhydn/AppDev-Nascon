# Shared input checks for POST /audit/v1/fixtures (FR-1.3, spec §5.7): format, team list, size limits.
from app.domain.rule_error import RuleError
from app.domain.scoring import is_id

# format -> (min teams, max teams)
TEAM_LIMITS = {
    "round_robin": (2, 40),
    "swiss": (2, 64),
    "single_elim": (2, 128),
    "double_elim": (3, 128),
}


def bad_request(fields, message="invalid request"):
    return RuleError(400, "VALIDATION_ERROR", message, {"fields": fields})


def validate_format_and_teams(fmt, teams):
    """Raise 400 unless format is known and teams is a list of unique ids within the format's limits."""
    if fmt not in TEAM_LIMITS:
        raise bad_request(["format"])
    if not isinstance(teams, list) or not all(is_id(t) for t in teams):
        raise bad_request(["teams"])
    if len(set(teams)) != len(teams):
        raise bad_request(["teams"], "team ids must be unique")
    low, high = TEAM_LIMITS[fmt]
    if not (low <= len(teams) <= high):
        raise bad_request(["teams"], f"{fmt} needs {low}-{high} teams")
