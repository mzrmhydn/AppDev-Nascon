# Offline sync tests (spec §5.14, NFR-4): resolutions, ordering, duplicates, base versions, rule codes.
import pytest
from fastapi.testclient import TestClient

from app.main import app
from test_roster import SETUP, move


def ev(event_id, etype, payload, match="m1"):
    return {"event_id": event_id, "match_id": match, "type": etype, "payload": payload}


INIT = ev("e1", "match_init", {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"})
START = ev("e2", "match_start", {})


def goal(event_id, team="t1"):
    return ev(event_id, "score", {"team_id": team, "event_type": "goal"})


def act(action_id, kind, payload, base=0, at="2026-10-17T11:00:00Z"):
    return {"action_id": action_id, "type": kind, "queued_at": at, "base_version": base, "payload": payload}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/audit/v1/reset").status_code == 200
        assert c.post("/audit/v1/roster/setup", json=SETUP).status_code == 201
        for body in (INIT, START):
            assert c.post("/audit/v1/events", json=body).status_code == 201
        yield c


def sync(client, actions, device="dev-1"):
    r = client.post("/audit/v1/offline-sync", json={"device_id": device, "actions": actions})
    assert r.status_code == 200, r.text
    return r.json()


def test_appended_rebased_and_resend_duplicates(client):
    actions = [act("a1", "score_event", goal("e3"), base=2),
               act("a2", "score_event", goal("e4"), base=2, at="2026-10-17T11:00:05Z")]
    data = sync(client, actions)
    a1, a2 = data["results"]
    assert (a1["status"], a1["resolution"], a1["server_version"], a1["processed_order"]) == \
        ("applied", "appended", 3, 1)
    assert (a2["status"], a2["resolution"], a2["server_version"]) == ("applied", "rebased_append", 4)
    assert len(a1["signature"]) == 64 and a1["error_code"] is None
    assert data["summary"] == {"applied": 2, "rejected": 0, "duplicate": 0}
    again = sync(client, actions)
    assert [r["status"] for r in again["results"]] == ["duplicate", "duplicate"]
    assert again["results"][0]["resolution"] == "skipped_duplicate"
    assert again["results"][0]["server_version"] == 4 and again["results"][0]["signature"] is None
    assert client.get("/audit/v1/score/m1").json()["version"] == 4  # nothing changed


def test_same_event_already_sent_online_is_duplicate(client):
    client.post("/audit/v1/events", json=goal("e3"))
    data = sync(client, [act("b1", "score_event", goal("e3"), base=3)])
    assert data["results"][0]["status"] == "duplicate"


def test_base_version_too_high_and_rule_codes(client):
    data = sync(client, [
        act("c1", "score_event", goal("e3"), base=9),
        act("c2", "score_event", goal("e4", team="t9"), base=2),
        act("c3", "score_event", goal("e5"), base=2) | {"payload": goal("e5") | {"match_id": "nope"}},
        act("c4", "score_event", {"event_id": "bad|id"}, base=0),
        act("c5", "score_event", ev("e1", "match_start", {}), base=2),
    ])
    codes = [r["error_code"] for r in data["results"]]
    assert codes == ["INVALID_BASE_VERSION", "VALIDATION_ERROR", "MATCH_NOT_FOUND", "VALIDATION_ERROR",
                     "DUPLICATE_EVENT_ID"]
    assert all(r["resolution"] == "server_wins" for r in data["results"])
    assert data["results"][0]["server_version"] == 2
    assert data["summary"]["rejected"] == 5


def test_processing_order_by_queued_at_results_in_request_order(client):
    late = act("d1", "score_event", ev("e9", "match_end", {}), base=3, at="2026-10-17T12:00:00Z")
    early = act("d2", "score_event", goal("e3"), base=2, at="2026-10-17T11:00:00Z")
    data = sync(client, [late, early])
    assert [r["action_id"] for r in data["results"]] == ["d1", "d2"]
    assert [r["processed_order"] for r in data["results"]] == [2, 1]
    assert [r["status"] for r in data["results"]] == ["applied", "applied"]  # goal first, then end


def test_roster_actions(client):
    data = sync(client, [
        act("r1", "roster_transfer", move("tr-1"), base=0),
        act("r2", "roster_transfer", move("tr-2", player="p3", frm="sq-b", to="sq-a"), base=0,
            at="2026-10-17T11:00:01Z"),
        act("r3", "roster_transfer", move("tr-3", player="ghost"), base=0, at="2026-10-17T11:00:02Z"),
        act("r4", "roster_transfer", move("tr-4", player="p1"), base=5, at="2026-10-17T11:00:03Z"),
    ])
    results = data["results"]
    assert (results[0]["status"], results[0]["server_version"], results[0]["signature"]) == ("applied", 1, None)
    assert results[1]["status"] == "applied"
    assert (results[2]["error_code"], results[2]["server_version"]) == ("PLAYER_NOT_FOUND", 0)
    assert results[3]["error_code"] == "INVALID_BASE_VERSION"
    stale = sync(client, [act("r5", "roster_transfer", move("tr-5", player="p2", frm="sq-b", to="sq-a"), base=0)])
    # stale device (base 0, player now has 1 audit entry) but the move is legal -> rebased
    assert (stale["results"][0]["status"], stale["results"][0]["resolution"],
            stale["results"][0]["server_version"]) == ("applied", "rebased_append", 2)
    full = sync(client, [act("r6", "roster_transfer", move("tr-6", player="p4", frm="sq-b", to="sq-a"), base=0)])
    assert full["results"][0]["error_code"] == "SQUAD_FULL"  # sq-a = p1, p3, p2


def test_match_init_through_sync(client):
    init = ev("n1", "match_init", {"sport_id": "football", "home_team_id": "a", "away_team_id": "b"}, match="m9")
    data = sync(client, [act("i1", "score_event", init, base=0)])
    assert (data["results"][0]["status"], data["results"][0]["server_version"]) == ("applied", 1)


@pytest.mark.parametrize("body", [
    {"device_id": "dev-1", "actions": []},
    {"device_id": "dev-1", "actions": [act(f"x{i}", "score_event", goal(f"g{i}")) for i in range(101)]},
    {"device_id": "dev|1", "actions": [act("x", "score_event", goal("g"))]},
    {"device_id": "dev-1", "actions": [act("x", "score_event", goal("g"), at="yesterday")]},
    {"device_id": "dev-1", "actions": [act("x", "chat", goal("g"))]},
    {"device_id": "dev-1", "actions": [act("x", "score_event", goal("g"), base=-1)]},
])
def test_bad_envelope_400(client, body):
    r = client.post("/audit/v1/offline-sync", json=body)
    assert (r.status_code, r.json()["error"]["code"]) == (400, "VALIDATION_ERROR")


def test_api_twin_forbidden_actions(client):
    token = client.post("/api/v1/auth/login", json={"email": "viewer@nascon.test",
                                                    "password": "Nascon@26"}).json()["token"]
    r = client.post("/api/v1/offline-sync", headers={"Authorization": f"Bearer {token}"},
                    json={"device_id": "phone-1", "actions": [act("v1", "score_event", goal("e3"), base=2)]})
    assert r.status_code == 200
    assert (r.json()["results"][0]["status"], r.json()["results"][0]["error_code"]) == ("rejected", "FORBIDDEN")
    assert client.post("/api/v1/offline-sync", json={"device_id": "x", "actions": []}).status_code == 401
