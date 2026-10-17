# Unit tests for domain/sport_config.py (spec §5.6).
import copy

from app.domain.sport_config import (normalize_sport_config, normalize_tie_break_order,
                                     validate_sport_config)

KABADDI = {
    "sport_id": "kabaddi",
    "name": "Kabaddi",
    "scoring_model": "event",
    "periods": {"count": 2, "duration_minutes": 20},
    "scoring_events": {"raid_point": {"points": 1}, "tackle_point": {"points": 1},
                       "all_out": {"points": 2}},
    "draw_allowed": False,
    "overtime": {"policy": "golden_score", "duration_minutes": 5},
    "tie_break_order": ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"],
    "roster": {"min_squad_size": 7, "max_squad_size": 12,
               "required_positions": {"raider": 2, "defender": 3}},
}

INNINGS = dict(KABADDI, sport_id="mini_cricket", scoring_model="innings",
               periods={"innings_per_team": 1, "overs_per_innings": 10, "balls_per_over": 6,
                        "wickets_per_innings": 10},
               scoring_events={"super_six": {"runs": 6, "legal_ball": True, "wicket": False},
                               "bye_run": {"runs": 1, "legal_ball": False, "wicket": False},
                               "out": {"runs": 0, "legal_ball": True, "wicket": True}})

ROUND = dict(KABADDI, sport_id="chess_bo5", scoring_model="round",
             periods={"best_of": 5}, scoring_events={"map_win": {"rounds": 1}})


def with_field(field, value):
    body = copy.deepcopy(KABADDI)
    body[field] = value
    return body


def test_valid_examples_from_spec():
    assert validate_sport_config(KABADDI) == []
    assert validate_sport_config(INNINGS) == []
    assert validate_sport_config(ROUND) == []


def test_strict_types_reject_bool_and_string_numbers():
    assert validate_sport_config(with_field("periods", {"count": True, "duration_minutes": 20})) == ["periods"]
    assert validate_sport_config(with_field("periods", {"count": "2", "duration_minutes": 20})) == ["periods"]
    assert validate_sport_config(with_field("draw_allowed", 0)) == ["draw_allowed"]


def test_collects_all_bad_fields():
    body = copy.deepcopy(KABADDI)
    body["sport_id"] = "Bad Id!"
    body["name"] = ""
    body["roster"] = {"min_squad_size": 5, "max_squad_size": 3, "required_positions": {}}
    assert validate_sport_config(body) == ["sport_id", "name", "roster"]


def test_missing_required_fields():
    assert validate_sport_config({}) == ["sport_id", "name", "scoring_model", "periods",
                                         "scoring_events", "draw_allowed", "overtime", "roster"]
    assert validate_sport_config([]) == ["body"]


def test_round_best_of_must_be_odd():
    body = copy.deepcopy(ROUND)
    body["periods"] = {"best_of": 4}
    assert validate_sport_config(body) == ["periods"]


def test_scoring_event_rules():
    assert validate_sport_config(with_field("scoring_events", {})) == ["scoring_events"]
    assert validate_sport_config(with_field("scoring_events", {"Bad-Key": {"points": 1}})) == ["scoring_events"]
    assert validate_sport_config(with_field("scoring_events", {"x": {"points": 0}})) == ["scoring_events"]
    body = copy.deepcopy(INNINGS)
    body["scoring_events"] = {"x": {"runs": -1, "legal_ball": True, "wicket": False}}
    assert validate_sport_config(body) == ["scoring_events"]


def test_overtime_and_tie_break_rules():
    assert validate_sport_config(with_field("overtime", {"policy": "penalties"})) == ["overtime"]
    assert validate_sport_config(with_field("overtime", {"policy": "none"})) == []
    assert validate_sport_config(with_field("overtime", {"policy": "none", "duration_minutes": -1})) == ["overtime"]
    assert validate_sport_config(with_field("tie_break_order", ["scored", "scored"])) == ["tie_break_order"]
    assert validate_sport_config(with_field("tie_break_order", ["goals"])) == ["tie_break_order"]
    body = copy.deepcopy(KABADDI)
    del body["tie_break_order"]
    assert validate_sport_config(body) == []


def test_tie_break_normalisation_puts_draw_lots_last():
    assert normalize_tie_break_order(None)[-1] == "draw_lots"
    assert len(normalize_tie_break_order(None)) == 6
    assert normalize_tie_break_order(["scored"]) == ["scored", "draw_lots"]
    assert normalize_tie_break_order(["draw_lots", "scored"]) == ["scored", "draw_lots"]


def test_normalize_drops_unknown_fields():
    body = copy.deepcopy(INNINGS)
    body["extra"] = 1
    body["periods"]["extra"] = 1
    body["scoring_events"]["super_six"]["extra"] = 1
    stored = normalize_sport_config(body)
    assert "extra" not in stored
    assert "extra" not in stored["periods"]
    assert stored["scoring_events"]["super_six"] == {"runs": 6, "legal_ball": True, "wicket": False}
    assert stored["overtime"] == {"policy": "golden_score", "duration_minutes": 5}


def test_normalize_round_and_event():
    assert normalize_sport_config(ROUND)["periods"] == {"best_of": 5}
    body = copy.deepcopy(KABADDI)
    body["overtime"] = {"policy": "none"}
    assert normalize_sport_config(body)["overtime"] == {"policy": "none"}


def test_seed_sports_are_valid_and_normalised():
    from app.domain.seed_sports import _RAW, SEED_SPORTS
    for raw in _RAW:
        assert validate_sport_config(raw) == []
    assert sorted(SEED_SPORTS) == ["basketball", "cricket", "esports", "football"]
    assert SEED_SPORTS["football"]["tie_break_order"][-1] == "draw_lots"
