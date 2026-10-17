# Unit tests for domain/scoring.py (spec §5.9): projection, limits, rule table.
import pytest

from app.domain.scoring import RuleError, check_event, payload_bad_fields, project
from test_sport_config import INNINGS, KABADDI, ROUND

MATCH = {"match_id": "m1", "sport_id": "kabaddi", "league_id": None,
         "home_team_id": "t1", "away_team_id": "t2"}


def build(*items):
    """items = (type, payload) pairs -> event rows with sequence/event_id/signature."""
    events = [{"type": "match_init", "payload": {}}] + [{"type": t, "payload": p} for t, p in items]
    return [dict(e, sequence=i + 1, event_id=f"e{i + 1}", signature="sig", match_id="m1")
            for i, e in enumerate(events)]


def score(team, event_type):
    return ("score", {"team_id": team, "event_type": event_type})


START = ("match_start", {})
END = ("match_end", {})


def test_upcoming_match_is_empty_and_pending():
    p = project(KABADDI, MATCH, build())
    assert p["status"] == "upcoming"
    assert p["outcome"] == "pending"
    assert p["winner_team_id"] is None
    assert p["home"] == {"team_id": "t1", "score": 0, "wickets": None, "balls": None,
                         "overs": None, "fair_play": 0}
    assert p["version"] == 1


def test_event_model_kabaddi_points_from_config():
    events = build(START, score("t1", "all_out"), score("t1", "raid_point"),
                   score("t2", "tackle_point"), ("discipline", {"team_id": "t2", "points": -1}), END)
    p = project(KABADDI, MATCH, events)
    assert p["status"] == "completed"
    assert p["home"]["score"] == 3
    assert p["away"]["score"] == 1
    assert p["away"]["fair_play"] == -1
    assert p["outcome"] == "home_win"
    assert p["winner_team_id"] == "t1"
    assert p["version"] == 7
    assert [e["sequence"] for e in p["events"]] == [1, 2, 3, 4, 5, 6, 7]


def test_innings_model_overs_string():
    balls = [score("t1", "super_six")] * 19 + [score("t1", "bye_run"), score("t1", "out")]
    p = project(INNINGS, MATCH, build(START, *balls))
    assert p["home"]["balls"] == 20
    assert p["home"]["overs"] == "3.2"
    assert p["home"]["wickets"] == 1
    assert p["home"]["score"] == 19 * 6 + 1
    assert p["away"]["overs"] == "0.0"


def test_compensation_after_completion_changes_outcome():
    events = build(START, score("t1", "raid_point"), END,
                   ("compensation", {"compensates": "e3", "reason": "review"}))
    p = project(KABADDI, MATCH, events)
    assert p["home"]["score"] == 0
    assert p["outcome"] == "undecided"  # level, no draws, no tiebreak winner
    target = p["events"][2]
    assert target["compensated"] is True
    assert target["compensated_by"] == "e5"
    assert p["events"][4]["compensated"] is False


def test_tiebreak_winner_decides_level_match_and_draw():
    events = build(START, ("tiebreak_winner", {"team_id": "t2"}), END)
    p = project(KABADDI, MATCH, events)
    assert p["outcome"] == "away_win"
    assert p["winner_team_id"] == "t2"
    assert p["tiebreak_winner_team_id"] == "t2"
    drawable = dict(KABADDI, draw_allowed=True)
    p = project(drawable, MATCH, build(START, END))
    assert p["outcome"] == "draw"
    assert p["winner_team_id"] is None


def test_round_model_counts_rounds():
    p = project(ROUND, MATCH, build(START, score("t2", "map_win"), END))
    assert p["away"]["score"] == 1
    assert p["outcome"] == "away_win"


# ---------- rule table ----------

def rule(config, items, event_type, payload, target=None):
    with pytest.raises(RuleError) as err:
        check_event(config, project(config, MATCH, build(*items)), event_type, payload,
                    target_event=target, match_id="m1")
    return err.value.status, err.value.code


def ok(config, items, event_type, payload, target=None):
    check_event(config, project(config, MATCH, build(*items)), event_type, payload,
                target_event=target, match_id="m1")


def test_transitions():
    assert rule(KABADDI, [], "match_init", {}) == (409, "MATCH_EXISTS")
    ok(KABADDI, [], "match_start", {})
    assert rule(KABADDI, [START], "match_start", {}) == (409, "ILLEGAL_TRANSITION")
    assert rule(KABADDI, [], "match_end", {}) == (409, "ILLEGAL_TRANSITION")
    assert rule(KABADDI, [START, ("tiebreak_winner", {"team_id": "t1"}), END], "match_end", {}) == \
        (409, "ILLEGAL_TRANSITION")


def test_score_rules_order_400_before_409():
    assert rule(KABADDI, [], "score", {"team_id": "t9", "event_type": "raid_point"}) == \
        (400, "VALIDATION_ERROR")
    assert rule(KABADDI, [], "score", {"team_id": "t1", "event_type": "goal"}) == \
        (400, "UNKNOWN_EVENT_TYPE")
    assert rule(KABADDI, [], "score", {"team_id": "t1", "event_type": "raid_point"}) == \
        (409, "MATCH_NOT_IN_PROGRESS")
    assert rule(KABADDI, [START], "discipline", {"team_id": "t3", "points": -1})[0] == 400
    assert rule(KABADDI, [], "tiebreak_winner", {"team_id": "t1"}) == (409, "MATCH_NOT_IN_PROGRESS")
    ok(KABADDI, [START], "score", {"team_id": "t1", "event_type": "raid_point"})


def test_tie_not_allowed():
    assert rule(KABADDI, [START], "match_end", {}) == (409, "TIE_NOT_ALLOWED")
    ok(KABADDI, [START, score("t1", "raid_point")], "match_end", {})
    ok(KABADDI, [START, ("tiebreak_winner", {"team_id": "t1"})], "match_end", {})
    ok(dict(KABADDI, draw_allowed=True), [START], "match_end", {})


def test_innings_complete_by_wickets_and_balls():
    tiny = dict(INNINGS, periods={"innings_per_team": 1, "overs_per_innings": 1,
                                  "balls_per_over": 2, "wickets_per_innings": 1})
    six = {"team_id": "t1", "event_type": "super_six"}
    assert rule(tiny, [START, score("t1", "out")], "score", six) == (409, "INNINGS_COMPLETE")
    full = [START, score("t1", "super_six"), score("t1", "super_six")]
    assert rule(tiny, full, "score", six) == (409, "INNINGS_COMPLETE")
    ok(tiny, full, "score", {"team_id": "t2", "event_type": "super_six"})
    # a compensated wicket no longer counts toward the limit
    ok(tiny, [START, score("t1", "out"), ("compensation", {"compensates": "e3", "reason": "x"})],
       "score", six)


def test_series_already_decided():
    win = {"team_id": "t1", "event_type": "map_win"}
    two = [START, score("t1", "map_win"), score("t1", "map_win")]
    ok(ROUND, two[:2], "score", win)
    assert rule(ROUND, [START] + [score("t1", "map_win")] * 3, "score", win) == \
        (409, "SERIES_ALREADY_DECIDED")


def test_compensation_rules():
    items = [START, score("t1", "raid_point"), END]
    target = {"event_id": "e3", "type": "score", "match_id": "m1"}
    assert rule(KABADDI, items, "compensation", {"compensates": "nope", "reason": "x"}) == \
        (404, "EVENT_NOT_FOUND")
    ok(KABADDI, items, "compensation", {"compensates": "e3", "reason": "x"}, target)
    assert rule(KABADDI, items, "compensation", {"compensates": "e2", "reason": "x"},
                {"event_id": "e2", "type": "match_start", "match_id": "m1"}) == \
        (409, "INVALID_COMPENSATION")
    assert rule(KABADDI, items, "compensation", {"compensates": "x9", "reason": "x"},
                {"event_id": "x9", "type": "score", "match_id": "m2"}) == \
        (409, "INVALID_COMPENSATION")
    done = items + [("compensation", {"compensates": "e3", "reason": "x"})]
    assert rule(KABADDI, done, "compensation", {"compensates": "e3", "reason": "x"}, target) == \
        (409, "INVALID_COMPENSATION")


def test_payload_schema():
    assert payload_bad_fields("score", {"team_id": "t1", "event_type": "a"}) == []
    assert payload_bad_fields("score", {"team_id": 1}) == ["team_id", "event_type"]
    assert payload_bad_fields("discipline", {"team_id": "t1", "points": True}) == ["points"]
    assert payload_bad_fields("tiebreak_winner", {}) == ["team_id"]
    assert payload_bad_fields("compensation", {"compensates": "e1"}) == ["reason"]
    assert payload_bad_fields("match_start", {}) == []
    assert payload_bad_fields("match_end", "x") == ["payload"]
    init = {"sport_id": "kabaddi", "home_team_id": "t1", "away_team_id": "t2"}
    assert payload_bad_fields("match_init", init) == []
    assert payload_bad_fields("match_init", dict(init, league_id="lg|1")) == ["league_id"]
    assert payload_bad_fields("match_init", dict(init, away_team_id="t1")) == ["away_team_id"]
    assert payload_bad_fields("match_init", {"sport_id": "x" * 65}) == \
        ["sport_id", "home_team_id", "away_team_id"]
