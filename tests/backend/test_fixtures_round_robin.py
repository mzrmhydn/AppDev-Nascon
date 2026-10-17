# Property tests for domain/fixtures_round_robin.py + shared team checks (spec §5.7-A).
from collections import Counter

import pytest

from app.domain.fixtures_common import validate_format_and_teams
from app.domain.fixtures_round_robin import generate_round_robin
from app.domain.rule_error import RuleError


def teams(n):
    return [f"t{i}" for i in range(1, n + 1)]


def all_matches(result):
    return [m for rnd in result["rounds"] for m in rnd["matches"]]


@pytest.mark.parametrize("n", range(2, 41))
def test_single_leg_properties(n):
    r = generate_round_robin(teams(n), {})
    rounds_per_leg = n - 1 if n % 2 == 0 else n
    assert r["round_count"] == rounds_per_leg
    assert r["team_count"] == n and r["legs"] == 1
    for rnd in r["rounds"]:
        assert len(rnd["matches"]) == n // 2
        assert len(rnd["byes"]) == n % 2
        playing = [t for m in rnd["matches"] for t in (m["home"], m["away"])] + rnd["byes"]
        assert sorted(playing) == sorted(teams(n))  # each team exactly once per round
    pairs = Counter(frozenset((m["home"], m["away"])) for m in all_matches(r))
    assert len(pairs) == n * (n - 1) // 2 and set(pairs.values()) == {1}
    home = Counter(m["home"] for m in all_matches(r))
    away = Counter(m["away"] for m in all_matches(r))
    assert all(abs(home[t] - away[t]) <= 1 for t in teams(n))
    if n % 2:
        byes = Counter(t for rnd in r["rounds"] for t in rnd["byes"])
        assert set(byes.values()) == {1} and len(byes) == n


def test_two_legs_every_ordered_pair_once_and_global_rounds():
    r = generate_round_robin(teams(5), {"legs": 2})
    assert r["round_count"] == 10
    assert [rnd["round"] for rnd in r["rounds"]] == list(range(1, 11))
    ordered = Counter((m["home"], m["away"]) for m in all_matches(r))
    assert len(ordered) == 20 and set(ordered.values()) == {1}
    assert r["rounds"][5]["matches"][0]["match_id"] == "RR-L2-R6-M1"
    assert r["rounds"][5]["matches"][0]["leg"] == 2


def test_spec_example_shape():
    r = generate_round_robin(teams(5), {"legs": 1, "withdrawals": [{"team_id": "t3", "after_round": 2}],
                                        "withdrawal_policy": "forfeit_remaining"})
    m = r["rounds"][0]["matches"][0]
    assert m["match_id"] == "RR-L1-R1-M1"
    assert set(m) == {"match_id", "leg", "home", "away", "status", "awarded_to"}
    s = r["summary"]
    assert s["total"] == 10 and s["scheduled"] + s["forfeit"] + s["voided"] == 10
    for match in all_matches(r):
        rnd = int(match["match_id"].split("-R")[1].split("-")[0])
        if "t3" in (match["home"], match["away"]) and rnd > 2:
            assert match["status"] == "forfeit"
            assert match["awarded_to"] == (match["away"] if match["home"] == "t3" else match["home"])
        else:
            assert match["status"] == "scheduled" and match["awarded_to"] is None


def test_void_all_and_both_withdrawn():
    r = generate_round_robin(teams(4), {"withdrawals": [{"team_id": "t1", "after_round": 3}],
                                        "withdrawal_policy": "void_all"})
    assert r["summary"]["voided"] == 3 and r["summary"]["total"] == 6
    r = generate_round_robin(teams(4), {"withdrawals": [{"team_id": "t1", "after_round": 0},
                                                         {"team_id": "t2", "after_round": 0}]})
    assert r["summary"] == {"total": 6, "scheduled": 1, "forfeit": 4, "voided": 1}


@pytest.mark.parametrize("params", [
    {"legs": 3}, {"legs": True}, {"withdrawal_policy": "x"}, {"withdrawals": "x"},
    {"withdrawals": ["t1"]},
    {"withdrawals": [{"team_id": "t9", "after_round": 1}]},
    {"withdrawals": [{"team_id": "t1", "after_round": 4}]},
    {"withdrawals": [{"team_id": "t1", "after_round": -1}]},
    {"withdrawals": [{"team_id": "t1", "after_round": 1}, {"team_id": "t1", "after_round": 2}]},
])
def test_bad_params_400(params):
    with pytest.raises(RuleError) as err:
        generate_round_robin(teams(4), params)
    assert (err.value.status, err.value.code) == (400, "VALIDATION_ERROR")


def test_params_must_be_object():
    with pytest.raises(RuleError):
        generate_round_robin(teams(4), [])


@pytest.mark.parametrize("fmt,team_list", [
    ("league", teams(4)), ("round_robin", "t1"), ("round_robin", ["t1", "t1"]),
    ("round_robin", teams(1)), ("round_robin", teams(41)), ("double_elim", teams(2)),
    ("swiss", teams(65)), ("single_elim", ["ok", "bad|id"]),
])
def test_team_validation(fmt, team_list):
    with pytest.raises(RuleError):
        validate_format_and_teams(fmt, team_list)


def test_team_validation_ok():
    validate_format_and_teams("single_elim", teams(128))
