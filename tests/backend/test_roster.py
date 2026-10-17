# Roster tests (spec §5.11, FR-2.2): every check in order, window edges, loans + lazy return, edge case 6, replay.
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app

SETUP = {
    "league": {"league_id": "lg-r1", "tenant_id": "tenant-alpha", "sport_id": "football",
               "transfer_window": {"open": "2026-09-01", "close": "2026-09-30"},
               "max_squad_size": 3, "required_positions": {"gk": 1}},
    "squads": [{"squad_id": "sq-a", "club_id": "club-a", "tenant_id": "tenant-alpha", "name": "A"},
               {"squad_id": "sq-b", "club_id": "club-b", "tenant_id": "tenant-alpha", "name": "B"},
               {"squad_id": "sq-x", "club_id": "club-x", "tenant_id": "tenant-beta", "name": "X"}],
    "players": [{"player_id": "p1", "name": "Ali", "position": "gk", "squad_id": "sq-a", "role": "captain"},
                {"player_id": "p2", "name": "Bilal", "position": "df", "squad_id": "sq-a", "role": "starter"},
                {"player_id": "p3", "name": "Chand", "position": "df", "squad_id": "sq-b", "role": "starter"},
                {"player_id": "p4", "name": "Dawood", "position": "df", "squad_id": "sq-b", "role": "starter"}],
    "matches_in_progress": [],
}


def move(rid, player="p2", kind="transfer", frm="sq-a", to="sq-b", day="2026-09-30", loan_end=None):
    return {"request_id": rid, "league_id": "lg-r1", "player_id": player, "type": kind,
            "from_squad_id": frm, "to_squad_id": to, "effective_date": day, "loan_end_date": loan_end,
            "reason": "Tactical move", "requested_by": "user-77"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/audit/v1/reset").status_code == 200
        r = c.post("/audit/v1/roster/setup", json=SETUP)
        assert r.status_code == 201
        assert r.json() == {"league_id": "lg-r1", "status": "configured",
                            "squad_counts": {"sq-a": 2, "sq-b": 2, "sq-x": 0}}
        yield c


def post(client, body):
    return client.post("/audit/v1/roster/transfer", json=body)


def code(r):
    return r.status_code, r.json()["error"]["code"]


def test_transfer_success_shape_and_replay(client):
    r = post(client, move("tr-001"))
    assert r.status_code == 201
    data = r.json()
    assert data["registration"] == {"player_id": "p2", "league_id": "lg-r1", "squad_id": "sq-b",
                                    "parent_squad_id": None, "registration_type": "transfer",
                                    "start_date": "2026-09-30", "loan_end_date": None, "role": "substitute"}
    entry = data["audit_entry"]
    assert entry["audit_id"] == "au-0001" and entry["who"] == "user-77" and entry["why"] == "Tactical move"
    assert (data["state"], data["blocking_match_id"]) == ("active", None)
    again = post(client, move("tr-001"))
    assert again.status_code == 200 and again.json() == data
    other = post(client, dict(move("tr-001"), reason="changed"))
    assert other.status_code == 400 and other.json()["error"]["details"]["fields"] == ["request_id"]
    hist = client.get("/audit/v1/roster/history/p2?as_of=2026-10-01").json()
    assert hist["current_squad_id"] == "sq-b" and len(hist["history"]) == 1


@pytest.mark.parametrize("body,expected", [
    (dict(move("e1"), type="swap"), (400, "VALIDATION_ERROR")),
    (dict(move("e1"), effective_date="2026-13-01"), (400, "VALIDATION_ERROR")),
    (move("e1", kind="loan", loan_end="2026-09-30"), (400, "VALIDATION_ERROR")),
    (dict(move("e1"), to_squad_id=None), (400, "VALIDATION_ERROR")),
    (dict(move("e1"), league_id="nope"), (404, "LEAGUE_NOT_FOUND")),
    (move("e1", player="ghost"), (404, "PLAYER_NOT_FOUND")),
    (move("e1", to="sq-zz"), (404, "SQUAD_NOT_FOUND")),
    (move("e1", to="sq-x"), (409, "CROSS_TENANT_TRANSFER")),
    (move("e1", player="p3"), (409, "NOT_IN_SQUAD")),
    (move("e1", day="2026-10-01"), (409, "TRANSFER_WINDOW_CLOSED")),
    (move("e1", day="2026-08-31"), (409, "TRANSFER_WINDOW_CLOSED")),
    (move("e1", player="p1"), (409, "MIN_POSITION_VIOLATION")),
])
def test_each_check(client, body, expected):
    assert code(post(client, body)) == expected


def test_window_edges_inclusive_and_release_any_date(client):
    assert post(client, move("w1", day="2026-09-01")).status_code == 201
    assert post(client, move("w2", player="p3", frm="sq-b", to="sq-a", day="2026-09-30")).status_code == 201
    r = post(client, move("w3", player="p4", kind="release", frm="sq-b", to=None, day="2027-02-01"))
    assert r.status_code == 201 and r.json()["registration"] is None
    assert client.get("/audit/v1/roster/history/p4?as_of=2027-03-01").json()["current_squad_id"] is None


def test_squad_full(client):
    assert post(client, move("f1", player="p3", frm="sq-b", to="sq-a")).status_code == 201  # sq-a now 3
    assert code(post(client, move("f2", player="p4", frm="sq-b", to="sq-a"))) == (409, "SQUAD_FULL")


def test_loan_on_loan_and_lazy_return_written_once(client):
    r = post(client, move("l1", kind="loan", day="2026-09-10", loan_end="2026-12-31"))
    assert r.status_code == 201
    reg = r.json()["registration"]
    assert (reg["registration_type"], reg["parent_squad_id"], reg["loan_end_date"]) == ("loan", "sq-a", "2026-12-31")
    assert code(post(client, move("l2", frm="sq-b", to="sq-a", day="2026-09-20"))) == (409, "PLAYER_ON_LOAN")

    during = client.get("/audit/v1/roster/history/p2?as_of=2026-12-31").json()
    assert (during["current_squad_id"], during["parent_squad_id"]) == ("sq-b", "sq-a")
    assert len(during["history"]) == 1
    for _ in range(3):
        after = client.get("/audit/v1/roster/history/p2?as_of=2027-01-05").json()
    assert after["current_squad_id"] == "sq-a" and after["parent_squad_id"] is None
    actions = [e["action"] for e in after["history"]]
    assert actions == ["loan", "loan_return"]
    ret = after["history"][1]
    assert (ret["who"], ret["effective_date"], ret["from_squad_id"], ret["to_squad_id"]) == \
        ("system", "2027-01-01", "sq-b", "sq-a")


def test_loaned_player_counts_for_borrower(client):
    assert post(client, move("c1", kind="loan", day="2026-09-10", loan_end="2026-12-31")).status_code == 201
    # sq-b now has 3 (p3, p4, loaned p2) -> full; sq-a has 1 (p1)
    assert code(post(client, move("c2", player="p1", frm="sq-a", to="sq-b", day="2026-09-15"))) == \
        (409, "SQUAD_FULL")


def test_in_progress_match_is_deferred(client):
    setup = copy.deepcopy(SETUP)
    setup["matches_in_progress"] = [{"match_id": "m-live", "home_squad_id": "sq-a", "away_squad_id": "sq-b"}]
    assert client.post("/audit/v1/roster/setup", json=setup).status_code == 201
    r = post(client, move("d1"))
    assert r.status_code == 201
    assert (r.json()["state"], r.json()["blocking_match_id"]) == ("deferred_until_match_end", "m-live")
    assert r.json()["audit_entry"]["state"] == "deferred_until_match_end"


def test_setup_replaces_and_validates(client):
    assert post(client, move("s1")).status_code == 201
    assert client.post("/audit/v1/roster/setup", json=SETUP).status_code == 201
    assert post(client, move("s1")).status_code == 201  # state and request ids were replaced
    bad = copy.deepcopy(SETUP)
    bad["players"][0]["role"] = "coach"
    assert client.post("/audit/v1/roster/setup", json=bad).json()["error"]["details"]["fields"] == ["players"]
    bad = copy.deepcopy(SETUP)
    bad["league"]["sport_id"] = "curling"
    assert code(client.post("/audit/v1/roster/setup", json=bad)) == (404, "SPORT_NOT_FOUND")
    defaults = copy.deepcopy(SETUP)
    del defaults["league"]["max_squad_size"]
    assert client.post("/audit/v1/roster/setup", json=defaults).status_code == 201  # football max 25


def test_history_errors(client):
    assert code(client.get("/audit/v1/roster/history/ghost")) == (404, "PLAYER_NOT_FOUND")
    assert client.get("/audit/v1/roster/history/p1?as_of=yesterday").status_code == 400
    assert client.get("/audit/v1/roster/history/p1").json()["current_squad_id"] == "sq-a"


def test_api_twin_permissions(client):
    def token(email):
        return client.post("/api/v1/auth/login", json={"email": email, "password": "Nascon@26"}).json()["token"]

    viewer = {"Authorization": f"Bearer {token('viewer@nascon.test')}"}
    assert client.post("/api/v1/roster/transfer", json=move("a1"), headers=viewer).status_code == 403
    admin = {"Authorization": f"Bearer {token('admin@nascon.test')}"}
    assert client.post("/api/v1/roster/transfer", json=move("a1"), headers=admin).status_code == 201
