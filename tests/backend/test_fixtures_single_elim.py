# Tests for domain/fixtures_single_elim.py (spec §5.7-C, exact parts).
import pytest

from app.domain.fixtures_single_elim import bracket_size, generate_single_elim, seed_order
from app.domain.rule_error import RuleError

SIX = ["t1", "t2", "t3", "t4", "t5", "t6"]


def by_id(result):
    return {m["match_id"]: m for rnd in result["rounds"] for m in rnd["matches"]}


def test_seed_order_and_size():
    assert seed_order(2) == [1, 2]
    assert seed_order(8) == [1, 8, 4, 5, 2, 7, 3, 6]
    assert seed_order(16)[:4] == [1, 16, 8, 9]
    assert [bracket_size(n) for n in (2, 3, 4, 5, 8, 9, 128)] == [2, 4, 4, 8, 8, 16, 128]


def test_spec_example_n6():
    r = generate_single_elim(SIX, {})
    assert r["format"] == "single_elim" and r["bracket_size"] == 8
    assert [rnd["round"] for rnd in r["rounds"]] == [1, 2, 3]
    m = by_id(r)
    assert (m["R1M1"]["home"], m["R1M1"]["away"], m["R1M1"]["bye"], m["R1M1"]["winner"]) == \
        ("t1", None, True, "t1")
    assert m["R1M2"] == {
        "match_id": "R1M2", "bracket": "main", "round": 1, "index": 2,
        "home": "t4", "away": "t5", "home_seed": 4, "away_seed": 5, "bye": False,
        "winner": None, "loser": None,
        "winner_to": {"match_id": "R2M1", "slot": "away"}, "loser_to": None,
    }
    assert m["R1M3"]["home"] == "t2" and m["R1M3"]["bye"] is True
    assert (m["R1M4"]["home"], m["R1M4"]["away"]) == ("t3", "t6")
    # bye winners propagated immediately
    assert m["R2M1"]["home"] == "t1" and m["R2M1"]["away"] is None
    assert m["R2M1"]["home_seed"] == 1 and m["R2M1"]["away_seed"] is None
    assert m["R2M2"]["home"] == "t2"
    assert m["R3M1"]["winner_to"] is None


def test_results_propagate_to_final():
    r = generate_single_elim(SIX, {"results": [
        {"match_id": "R1M2", "winner": "t4"}, {"match_id": "R1M4", "winner": "t6"},
        {"match_id": "R2M1", "winner": "t4"}, {"match_id": "R2M2", "winner": "t2"},
        {"match_id": "R3M1", "winner": "t2"}]})
    m = by_id(r)
    assert m["R1M2"]["loser"] == "t5"
    assert m["R2M1"]["away"] == "t4" and m["R2M1"]["loser"] == "t1"
    assert m["R2M1"]["away_seed"] == 4 and m["R3M1"]["away_seed"] == 2
    assert (m["R3M1"]["home"], m["R3M1"]["away"], m["R3M1"]["winner"]) == ("t4", "t2", "t2")


def test_third_place_match():
    r = generate_single_elim(["a", "b", "c", "d"], {"third_place_match": True, "results": [
        {"match_id": "R1M1", "winner": "a"}, {"match_id": "R1M2", "winner": "c"}]})
    m = by_id(r)
    assert m["R1M1"]["loser_to"] == {"match_id": "TP", "slot": "home"}
    assert m["R1M2"]["loser_to"] == {"match_id": "TP", "slot": "away"}
    assert m["TP"]["bracket"] == "third_place"
    assert (m["TP"]["home"], m["TP"]["away"]) == ("d", "b")
    assert (m["TP"]["home_seed"], m["TP"]["away_seed"]) == (4, 2)


def test_two_teams_one_round():
    r = generate_single_elim(["a", "b"], {"third_place_match": True})
    assert len(r["rounds"]) == 1 and by_id(r)["R1M1"]["winner_to"] is None


@pytest.mark.parametrize("params", [
    [], {"third_place_match": "yes"}, {"results": "x"},
    {"results": [{"match_id": "R9M9", "winner": "t1"}]},
    {"results": [{"match_id": "R1M2", "winner": "t1"}]},
    {"results": [{"match_id": "R2M1", "winner": "t4"}]},  # t4 not placed yet
    {"results": ["R1M2"]},
])
def test_bad_results_400(params):
    with pytest.raises(RuleError) as err:
        generate_single_elim(SIX, params)
    assert err.value.status == 400
