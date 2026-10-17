# Tests for domain/fixtures_double_elim.py (spec §5.7-D): counts, routing graph, bracket reset.
from collections import Counter

import pytest

from app.domain.fixtures_double_elim import generate_double_elim
from app.domain.rule_error import RuleError


def teams(n):
    return [f"t{i}" for i in range(1, n + 1)]


def all_matches(r):
    return ([m for rnd in r["winners"] for m in rnd["matches"]]
            + [m for rnd in r["losers"] for m in rnd["matches"]] + r["grand_final"])


@pytest.mark.parametrize("size", [4, 8, 16])
def test_counts_and_ids(size):
    r = generate_double_elim(teams(size), {"bracket_reset": True})
    k = size.bit_length() - 1
    assert r["bracket_size"] == size and r["bracket_reset"] is True
    assert [len(rnd["matches"]) for rnd in r["winners"]] == [size // 2 ** j for j in range(1, k + 1)]
    expected_lr = []
    for j in range(1, k):
        expected_lr += [size // 2 ** (j + 1)] * 2
    assert [len(rnd["matches"]) for rnd in r["losers"]] == expected_lr
    assert sum(expected_lr) == size - 2
    assert r["losers"][0]["matches"][0]["match_id"] == "LR1M1"
    assert [m["match_id"] for m in r["grand_final"]] == ["GF1", "GF2"]


@pytest.mark.parametrize("size", [4, 8, 16])
def test_routing_graph_every_slot_fed_once(size):
    r = generate_double_elim(teams(size), {"bracket_reset": False})
    sources = Counter()
    for m in all_matches(r):
        for link in (m["winner_to"], m["loser_to"]):
            if link is not None:
                sources[(link["match_id"], link["slot"])] += 1
        if m["bracket"] == "winners":
            assert m["loser_to"] is not None
        if m["bracket"] == "losers":
            assert m["loser_to"] is None
    slots = {(m["match_id"], s) for m in all_matches(r) if not m["match_id"].startswith("WR1M")
             for s in ("home", "away")}
    assert set(sources) == slots
    assert set(sources.values()) == {1}
    by_id = {m["match_id"]: m for m in all_matches(r)}
    k = size.bit_length() - 1
    wr_final = by_id[f"WR{k}M1"]
    assert wr_final["winner_to"] == {"match_id": "GF1", "slot": "home"}
    assert wr_final["loser_to"] == {"match_id": f"LR{2 * k - 2}M1", "slot": "away"}
    assert by_id[f"LR{2 * k - 2}M1"]["winner_to"] == {"match_id": "GF1", "slot": "away"}
    assert by_id["GF1"]["winner_to"] is None and len(r["grand_final"]) == 1


def play(results, reset=True):
    return {m["match_id"]: m for m in all_matches(
        generate_double_elim(["a", "b", "c", "d"], {"bracket_reset": reset, "results": results}))}


BASE = [{"match_id": "WR1M1", "winner": "a"}, {"match_id": "WR1M2", "winner": "b"},
        {"match_id": "WR2M1", "winner": "a"}, {"match_id": "LR1M1", "winner": "c"},
        {"match_id": "LR2M1", "winner": "c"}]


def test_losers_champion_wins_gf1_forces_reset():
    m = play(BASE + [{"match_id": "GF1", "winner": "c"}])
    assert (m["LR1M1"]["home"], m["LR1M1"]["away"]) == ("d", "c")
    assert (m["LR2M1"]["home"], m["LR2M1"]["away"]) == ("c", "b")
    assert (m["GF1"]["home"], m["GF1"]["away"]) == ("a", "c")
    assert m["GF2"]["conditional"] is True and m["GF2"]["required"] is True
    assert {m["GF2"]["home"], m["GF2"]["away"]} == {"a", "c"}
    assert "conditional" not in m["GF1"]


def test_winners_champion_wins_gf1_no_reset():
    m = play(BASE)
    assert m["GF2"]["required"] is None
    m = play(BASE + [{"match_id": "GF1", "winner": "a"}])
    assert m["GF2"]["required"] is False


def test_byes_like_single_elim():
    r = generate_double_elim(teams(3), {})
    wr1 = r["winners"][0]["matches"]
    assert wr1[0]["bye"] is True and wr1[0]["winner"] == "t1"
    assert r["bracket_reset"] is False


@pytest.mark.parametrize("params", [[], {"bracket_reset": "yes"},
                                    {"results": [{"match_id": "GF1", "winner": "a"}]}])
def test_bad_params_400(params):
    with pytest.raises(RuleError):
        generate_double_elim(["a", "b", "c", "d"], params)
