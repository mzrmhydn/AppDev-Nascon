# Create and load sport configs (FR-1.1, spec §5.6). A new sport is usable at once: every request reads the DB.
from app.domain.sport_config import normalize_sport_config, validate_sport_config
from app.errors import AppError
from app.models_league import Sport


def create_sport(db, body):
    """Return (201, response). Order: 400 VALIDATION_ERROR -> 409 SPORT_EXISTS."""
    fields = validate_sport_config(body)
    if fields:
        raise AppError(400, "VALIDATION_ERROR", "invalid sport config", {"fields": fields})
    if db.get(Sport, body["sport_id"]) is not None:
        raise AppError(409, "SPORT_EXISTS", "sport already exists", {"sport_id": body["sport_id"]})
    config = normalize_sport_config(body)
    db.add(Sport(sport_id=config["sport_id"], config=config, is_seed=False))
    db.commit()
    return 201, {"sport_id": config["sport_id"], "status": "created", "config": config}


def get_sport_config(db, sport_id):
    """Stored config dict, or None if the sport doesn't exist."""
    sport = db.get(Sport, sport_id)
    return sport.config if sport is not None else None
