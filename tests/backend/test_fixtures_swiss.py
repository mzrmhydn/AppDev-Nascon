# Tests for domain/fixtures_swiss.py (spec §5.7-B): round 1 exact, spec example, minimal pairing, errors.
import itertools
import random

import pytest

from app.domain.fixtures_swiss import best_pairing, generate_swiss, swiss_standings
from app.domain.rule_error import RuleError

FIVE = ["t1", "t2", "t3", "t4", "t5"]
SPEC_HISTORY = [{"round": 1, "bye": "t5", "matches": [{"home": "t1", "away": "t3", "result": "home"},
                                                      {"home": "t2", "away": "t4", "result": "draw"}]}]


def test_round_one_exact_odd_and_even():
    r = generate_swiss(FIVE, {"total_rounds": 3})
    assert r["round"] == 1 and r["total_rounds"] == 3
    assert r["pairings"] == [{"match_id": "SW-R1-M1", "home": "t1", "away": "t3"},
                             {"match_id": "SW-R1-M2", "home": "t2", "away": "t4"}]
    assert r["bye"] == "t5"
    r = generate_swiss(["a", "b", "c", "d"], {})
    assert [(p["home"], p["away"]) for p in r["pairings"]] == [("a", "c"), ("b", "d")]
    assert r["bye"] is None and r["total_rounds"] == 2
    assert r["standings"][0] == {"rank": 1, "team_id": "a", "score": 0.0, "buchholz": 0.0}


def test_spec_example_round_two():
    r = generate_swiss(FIVE, {"total_rounds": 3, "round": 2, "history": SPEC_HISTORY})
    assert [(p["home"], p["away"]) for p in r["pairings"]] == [("t1", "t2"), ("t5", "t4")]
    assert r["pairings"][0]["match_id"] == "SW-R2-M1"
    assert r["bye"] == "t3"
    assert r["standings"][:3] == [
        {"rank": 1, "team_id": "t1", "score": 1.0, "buchholz": 0.0},
        {"rank": 2, "team_id": "t5", "score": 1.0, "buchholz": 0.0},
        {"rank": 3, "team_id": "t2", "score": 0.5, "buchholz": 0.5}]


def brute_force_min(players, score, met):
    best = None
    for perm in itertools.permutations(players):
        pairs = [(perm[i], perm[i + 1]) for i in range(0, len(perm), 2)]
        if any(frozenset(p) in met for p in pairs):
            continue
        cost = sum(abs(score[a] - score[b]) for a, b in pairs)
        best = cost if best is None else min(best, cost)
    return best


def test_pairing_is_minimal_against_brute_force():
    rng = random.Random(7)
    teams = [f"t{i}" for i in range(1, 9)]
    for _ in range(40):
        history = []
        for rnd in range(1, rng.randint(2, 4)):
            shuffled = teams[:]
            rng.shuffle(shuffled)
            history.append({"round": rnd, "bye": None, "matches": [
                {"home": shuffled[i], "away": shuffled[i + 1], "result": rng.choice(["home", "away", "draw"])}
                for i in range(0, 8, 2)]})
        rows, score, met, _ = swiss_standings(teams, history)
        players = [row["team_id"] for row in rows]
        pairs = best_pairing(players, score, met)
        expected = brute_force_min(players, score, met)
        if expected is None:
            assert pairs is None
            continue
        assert all(frozenset(p) not in met for p in pairs)
        assert sorted(t for p in pairs for t in p) == sorted(teams)
        assert sum(abs(score[a] - score[b]) for a, b in pairs) == expected


def test_greedy_would_get_stuck():
    # Greedy pairs a-b first, leaving c-d who already met; optimum avoids that.
    score = {"a": 2.0, "b": 2.0, "c": 1.0, "d": 1.0}
    met = {frozenset(("c", "d")), frozenset(("a", "b"))}
    assert best_pairing(["a", "b", "c", "d"], score, met) == [("a", "c"), ("b", "d")]


def test_bye_goes_to_next_candidate_and_no_valid_pairing():
    teams = ["a", "b", "c"]
    history = [{"round": 1, "bye": "c", "matches": [{"home": "a", "away": "b", "result": "home"}]}]
    r = generate_swiss(teams, {"total_rounds": 2, "round": 2, "history": history})
    assert r["bye"] == "b" and [(p["home"], p["away"]) for p in r["pairings"]] == [("a", "c")]
    # everyone has already met everyone -> no rematch-free pairing at all
    with pytest.raises(RuleError) as err:
        generate_swiss(["a", "b", "c", "d"], {"total_rounds": 3, "round": 2, "history": [
            {"round": 1, "bye": None, "matches": [{"home": "a", "away": "b", "result": "home"},
                                                  {"home": "c", "away": "d", "result": "home"},
                                                  {"home": "a", "away": "c", "result": "home"},
                                                  {"home": "b", "away": "d", "result": "home"},
                                                  {"home": "a", "away": "d", "result": "home"},
                                                  {"home": "b", "away": "c", "result": "home"}]}]})
    assert (err.value.status, err.value.code, err.value.details) == (409, "NO_VALID_PAIRING", {"round": 2})


@pytest.mark.parametrize("params", [
    [], {"total_rounds": 5}, {"total_rounds": 0}, {"round": 4, "total_rounds": 3},
    {"round": 2, "total_rounds": 3, "history": []},
    {"round": 1, "history": SPEC_HISTORY},
    {"round": 2, "total_rounds": 3, "history": "x"},
    {"round": 2, "total_rounds": 3, "history": [{"round": 1, "bye": "zz", "matches": []}]},
    {"round": 2, "total_rounds": 3, "history": [{"round": 1, "bye": None,
                                                 "matches": [{"home": "t1", "away": "t1", "result": "home"}]}]},
    {"round": 2, "total_rounds": 3, "history": [{"round": "1", "matches": []}]},
])
def test_bad_params_400(params):
    with pytest.raises(RuleError) as err:
        generate_swiss(FIVE, params)
    assert err.value.status == 400
