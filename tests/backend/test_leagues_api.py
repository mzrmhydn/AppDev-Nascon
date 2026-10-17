# API tests for POST /audit/v1/leagues + GET /audit/v1/standings (spec §5.8, §5.10) through the real stack:
# a mystery sport created at runtime is usable for leagues, events and standings without any code change.
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from test_sport_config import KABADDI

LEAGUE = {
    "league_id": "lg-1", "sport_id": "kabaddi", "teams": ["t1", "t2", "t3", "t4"],
    "fixtures": [{"match_id": "m1", "home": "t1", "away": "t2"}, {"match_id": "m2", "home": "t3", "away": "t4"},
                 {"match_id": "m3", "home": "t1", "away": "t3"}],
    "qualification": {"spots": 2},
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/audit/v1/reset", json={"seed": 7}).status_code == 200
        assert c.post("/audit/v1/sports", json=KABADDI).status_code == 201
        yield c


def play(client, match_id, goals_home, goals_away, home, away, end=True):
    n = 0

    def send(etype, payload):
        nonlocal n
        n += 1
        r = client.post("/audit/v1/events", json={"event_id": f"{match_id}-e{n}", "match_id": match_id,
                                                  "type": etype, "payload": payload})
        assert r.status_code == 201, r.text

    send("match_start", {})
    for _ in range(goals_home):
        send("score", {"team_id": home, "event_type": "raid_point"})
    for _ in range(goals_away):
        send("score", {"team_id": away, "event_type": "all_out"})
    if end:
        send("match_end", {})


def test_create_league_and_standings(client):
    r = client.post("/audit/v1/leagues", json=LEAGUE)
    assert r.json() == {"league_id": "lg-1", "status": "created", "team_count": 4, "fixture_count": 3}
    assert r.status_code == 201
    empty = client.get("/audit/v1/standings/lg-1").json()
    assert [row["played"] for row in empty["table"]] == [0, 0, 0, 0]
    play(client, "m1", 3, 0, "t1", "t2")   # t1 3-0
    play(client, "m2", 0, 1, "t3", "t4")   # t4 2-0 (all_out = 2 points)
    play(client, "m3", 1, 0, "t1", "t3", end=False)  # in progress -> remaining
    data = client.get("/audit/v1/standings/lg-1").json()
    assert data["sport_id"] == "kabaddi" and data["qualification_spots"] == 2
    top = data["table"][0]
    assert (top["team_id"], top["points"], top["played"], top["diff"]) == ("t1", 3, 1, 3)
    assert data["h2h"]["t1"]["t2"] == {"played": 1, "points": 3, "scored": 3, "conceded": 0}
    assert {row["status"] for row in data["table"]} <= {"clinched", "eliminated", "still_possible"}


@pytest.mark.parametrize("change,expected", [
    ({"teams": ["t1"]}, (400, "VALIDATION_ERROR")),
    ({"teams": ["t1", "t1"]}, (400, "VALIDATION_ERROR")),
    ({"fixtures": [{"match_id": "m1", "home": "t1", "away": "t1"}]}, (400, "VALIDATION_ERROR")),
    ({"fixtures": [{"match_id": "m1", "home": "t1", "away": "t9"}]}, (400, "VALIDATION_ERROR")),
    ({"qualification": {"spots": 5}}, (400, "VALIDATION_ERROR")),
    ({"points": {"win": "3"}}, (400, "VALIDATION_ERROR")),
    ({"tie_break_order": ["scored", "scored"]}, (400, "VALIDATION_ERROR")),
    ({"lots_seed": "42"}, (400, "VALIDATION_ERROR")),
    ({"sport_id": "curling"}, (404, "SPORT_NOT_FOUND")),
    ({"league_id": "league-alpha-1"}, (409, "LEAGUE_EXISTS")),
])
def test_league_errors_in_order(client, change, expected):
    body = copy.deepcopy(LEAGUE)
    body.update(change)
    r = client.post("/audit/v1/leagues", json=body)
    assert (r.status_code, r.json()["error"]["code"]) == expected


def test_match_exists_and_defaults(client):
    client.post("/audit/v1/events", json={"event_id": "x1", "match_id": "m1", "type": "match_init",
                                          "payload": {"sport_id": "kabaddi", "home_team_id": "a",
                                                      "away_team_id": "b"}})
    r = client.post("/audit/v1/leagues", json=LEAGUE)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "MATCH_EXISTS")
    other = dict(copy.deepcopy(LEAGUE), league_id="lg-2",
                 fixtures=[{"match_id": "n1", "home": "t1", "away": "t2"}],
                 points={"win": 2, "draw": 1, "loss": 0}, tie_break_order=["scored"])
    assert client.post("/audit/v1/leagues", json=other).status_code == 201
    play(client, "n1", 2, 0, "t1", "t2")
    assert client.get("/audit/v1/standings/lg-2").json()["table"][0]["points"] == 2


def test_standings_errors_and_baseline_league(client):
    r = client.get("/audit/v1/standings/nope")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "LEAGUE_NOT_FOUND")
    base = client.get("/audit/v1/standings/league-alpha-2").json()
    assert base["table"] == [] and base["sport_id"] is None
    assert client.post("/audit/v1/leagues", content=b"{oops").status_code == 400
