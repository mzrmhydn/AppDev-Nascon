# Unit tests for domain/standings.py (spec §5.10, edge case 4).
from app.domain.standings import compute_standings, lots_key
from test_sport_config import INNINGS, KABADDI

EVENT = dict(KABADDI, draw_allowed=True)


def side(team, score, fp=0, balls=None, wickets=None):
    return {"team_id": team, "score": score, "fair_play": fp, "balls": balls, "wickets": wickets}


def match(home, away, hs, as_, status="completed", winner="auto", fp=(0, 0), innings=None):
    """Minimal fake project() output. innings = ((balls, wkts), (balls, wkts))."""
    if winner == "auto":
        winner = home if hs > as_ else away if as_ > hs else None
    if status != "completed":
        outcome = "pending"
    elif winner == home:
        outcome = "home_win"
    elif winner == away:
        outcome = "away_win"
    else:
        outcome = "draw"
    (hb, hw), (ab, aw) = innings or ((None, None), (None, None))
    return {"status": status, "outcome": outcome, "winner_team_id": winner,
            "home": side(home, hs, fp[0], hb, hw), "away": side(away, as_, fp[1], ab, aw)}


def league(teams, spots=2, **extra):
    base = {"league_id": "lg-1", "teams": teams, "points": {"win": 3, "draw": 1, "loss": 0},
            "tie_break_order": None, "qualification_spots": spots, "lots_seed": 42}
    base.update(extra)
    return base


def order(result):
    return [row["team_id"] for row in result["table"]]


def by_team(result):
    return {row["team_id"]: row for row in result["table"]}


def test_lots_key_matches_appendix_vector():
    assert lots_key(42, "lg-1", "t1") == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"
    assert lots_key(42, "lg-1", "t2").startswith("e3e3a14e")
    assert lots_key(42, "lg-1", "t3").startswith("c8f28e3c")


def test_all_level_falls_through_to_draw_lots():
    r = compute_standings(league(["t1", "t2", "t3"]), EVENT, [])
    assert order(r) == ["t1", "t3", "t2"]
    rows = by_team(r)
    assert rows["t1"]["resolved_by"] == "draw_lots"
    assert rows["t3"]["resolved_by"] == "draw_lots"
    assert rows["t2"]["resolved_by"] is None
    assert r["h2h"]["t1"]["t2"] == {"played": 0, "points": 0, "scored": 0, "conceded": 0}


def test_basic_row_and_h2h():
    r = compute_standings(league(["t1", "t2"]), EVENT,
                          [match("t1", "t2", 2, 1, fp=(0, -1)), match("t2", "t1", 1, 1)])
    t1 = by_team(r)["t1"]
    assert (t1["played"], t1["won"], t1["drawn"], t1["lost"]) == (2, 1, 1, 0)
    assert (t1["scored"], t1["conceded"], t1["diff"], t1["points"]) == (3, 2, 1, 4)
    assert by_team(r)["t2"]["fair_play"] == -1
    assert r["h2h"]["t1"]["t2"] == {"played": 2, "points": 4, "scored": 3, "conceded": 2}
    assert r["sport_id"] == "kabaddi" and r["qualification_spots"] == 2
    assert t1["rank"] == 1 and t1["resolved_by"] is None


def test_three_way_mini_league_restarts_on_split():
    # a, b, c all on 6 points: cycle a>b 3-0, b>c 2-0, c>a 1-0; everyone beats d.
    fixtures = [match("a", "b", 3, 0), match("b", "c", 2, 0), match("c", "a", 1, 0),
                match("a", "d", 1, 0), match("b", "d", 1, 0), match("c", "d", 5, 0)]
    r = compute_standings(league(["a", "b", "c", "d"]), EVENT, fixtures)
    # 3-way h2h_points all 3 -> h2h_diff: a +2, b -1, c -1 -> [a], [b, c]
    # {b, c} restarts from h2h_points: b beat c -> b above c (overall_diff would have put c first)
    assert order(r) == ["a", "b", "c", "d"]
    rows = by_team(r)
    assert rows["a"]["resolved_by"] == "h2h_diff"
    assert rows["b"]["resolved_by"] == "h2h_points"
    assert rows["c"]["resolved_by"] is None
    assert rows["c"]["diff"] > rows["b"]["diff"]


def test_custom_tie_break_order_and_fair_play():
    fixtures = [match("a", "b", 1, 1, fp=(-3, 0))]
    r = compute_standings(league(["a", "b"], tie_break_order=["fair_play"]), EVENT, fixtures)
    assert order(r) == ["b", "a"]
    assert by_team(r)["b"]["resolved_by"] == "fair_play"


def test_tiebreak_win_counts_as_win_and_undecided_is_remaining():
    fixtures = [match("a", "b", 1, 1, winner="b"),
                {"status": "completed", "outcome": "undecided", "winner_team_id": None,
                 "home": side("a", 0), "away": side("b", 0)}]
    r = compute_standings(league(["a", "b"], spots=1), KABADDI, fixtures)
    rows = by_team(r)
    assert rows["b"]["won"] == 1 and rows["b"]["points"] == 3
    assert rows["a"]["played"] == 1
    # a can still reach 3 with the undecided match counted as remaining
    assert rows["b"]["status"] == "still_possible"


def test_net_run_rate_with_all_out():
    # t1 120 runs off 120 balls; t2 100 all out off 90 balls -> counts as the full overs
    fixtures = [match("t1", "t2", 120, 100, innings=((120, 3), (90, 10)))]
    rows = by_team(compute_standings(league(["t1", "t2"]), INNINGS, fixtures))
    # INNINGS fixture has overs_per_innings 10 -> 120 balls = 20.0 overs, all out = 10 overs
    assert rows["t1"]["diff"] == round(120 / 20 - 100 / 10, 3)
    assert rows["t2"]["diff"] == round(100 / 10 - 120 / 20, 3)

    fixtures = [match("t1", "t2", 50, 40, innings=((45, 2), (60, 1)))]
    rows = by_team(compute_standings(league(["t1", "t2"]), INNINGS, fixtures))
    assert rows["t1"]["diff"] == round(50 / 7.5 - 40 / 10, 3)


def test_net_run_rate_zero_overs_guard():
    fixtures = [match("t1", "t2", 0, 0, innings=((0, 0), (0, 0)))]
    rows = by_team(compute_standings(league(["t1", "t2"]), dict(INNINGS, draw_allowed=True), fixtures))
    assert rows["t1"]["diff"] == 0


def test_clinched_and_eliminated():
    fixtures = [match("a", "b", 1, 0), match("a", "c", 1, 0), match("b", "d", 1, 0),
                match("c", "d", 0, 0, status="upcoming")]
    rows = by_team(compute_standings(league(["a", "b", "c", "d"], spots=1), EVENT, fixtures))
    assert [rows[t]["status"] for t in "abcd"] == ["clinched", "eliminated", "eliminated", "eliminated"]
    rows = by_team(compute_standings(league(["a", "b", "c", "d"], spots=2), EVENT, fixtures))
    assert [rows[t]["status"] for t in "abcd"] == ["clinched", "still_possible",
                                                  "still_possible", "still_possible"]
