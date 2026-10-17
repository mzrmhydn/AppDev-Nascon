# The four baseline sports (spec §5.2 seed table), stored in the same format as POST /audit/v1/sports (§5.6).
# Seed data is the ONLY place sport/event names appear. Track A's seed.py imports SEED_SPORTS.
from app.domain.sport_config import normalize_sport_config


def _ev(points):
    return {"points": points}


def _ball(runs, legal_ball, wicket):
    return {"runs": runs, "legal_ball": legal_ball, "wicket": wicket}


_RAW = [
    {
        "sport_id": "football", "name": "Football", "scoring_model": "event",
        "periods": {"count": 2, "duration_minutes": 45},
        "scoring_events": {"goal": _ev(1)},
        "draw_allowed": True, "overtime": {"policy": "none"},
        "roster": {"min_squad_size": 11, "max_squad_size": 25, "required_positions": {"gk": 1}},
    },
    {
        "sport_id": "basketball", "name": "Basketball", "scoring_model": "event",
        "periods": {"count": 4, "duration_minutes": 12},
        "scoring_events": {"free_throw": _ev(1), "two_pointer": _ev(2), "three_pointer": _ev(3)},
        "draw_allowed": False, "overtime": {"policy": "extra_time", "duration_minutes": 5},
        "roster": {"min_squad_size": 5, "max_squad_size": 15, "required_positions": {}},
    },
    {
        "sport_id": "cricket", "name": "Cricket", "scoring_model": "innings",
        "periods": {"innings_per_team": 1, "overs_per_innings": 20, "balls_per_over": 6,
                    "wickets_per_innings": 10},
        "scoring_events": {
            "dot_ball": _ball(0, True, False), "single": _ball(1, True, False),
            "two": _ball(2, True, False), "four": _ball(4, True, False), "six": _ball(6, True, False),
            "wide": _ball(1, False, False), "no_ball": _ball(1, False, False),
            "wicket": _ball(0, True, True),
        },
        "draw_allowed": True, "overtime": {"policy": "super_over"},
        "roster": {"min_squad_size": 11, "max_squad_size": 18, "required_positions": {"wicketkeeper": 1}},
    },
    {
        "sport_id": "esports", "name": "Esports", "scoring_model": "round",
        "periods": {"best_of": 3},
        "scoring_events": {"round_win": {"rounds": 1}},
        "draw_allowed": False, "overtime": {"policy": "none"},
        "roster": {"min_squad_size": 5, "max_squad_size": 8, "required_positions": {}},
    },
]

# sport_id -> stored config
SEED_SPORTS = {raw["sport_id"]: normalize_sport_config(raw) for raw in _RAW}
