# POST /audit/v1/fixtures — pure schedule/bracket generation, stores nothing (FR-1.3, spec §5.7).
from typing import Any

from fastapi import APIRouter, Body

from app.domain.fixtures_common import validate_format_and_teams
from app.domain.fixtures_double_elim import generate_double_elim
from app.domain.fixtures_round_robin import generate_round_robin
from app.domain.fixtures_single_elim import generate_single_elim
from app.domain.fixtures_swiss import generate_swiss
from app.domain.rule_error import RuleError
from app.errors import AppError
from app.services.rule_error_bridge import as_app_error

router = APIRouter()

GENERATORS = {
    "round_robin": generate_round_robin,
    "single_elim": generate_single_elim,
    "double_elim": generate_double_elim,
    "swiss": generate_swiss,
}


@router.post("/audit/v1/fixtures")
def post_fixtures(body: Any = Body(None)):
    if not isinstance(body, dict):
        raise AppError(400, "VALIDATION_ERROR", "body must be an object", {"fields": ["body"]})
    params = body.get("params")
    if params is None:
        params = {}
    try:
        validate_format_and_teams(body.get("format"), body.get("teams"))
        return GENERATORS[body["format"]](body["teams"], params)
    except RuleError as err:
        raise as_app_error(err)
