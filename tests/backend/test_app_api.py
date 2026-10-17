# App API tests (contract §2): demo seed, read shapes, tenant isolation, write twins, WebSocket push.
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        assert c.post("/audit/v1/reset").status_code == 200
        assert c.post("/api/v1/dev/demo-seed").json() == {"status": "demo_seeded"}
        assert c.post("/api/v1/dev/demo-seed").status_code == 200  # idempotent
        yield c


def auth(client, who):
    token = client.post("/api/v1/auth/login", json={"email": f"{who}@nascon.test",
                                                    "password": "Nascon@26"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_demo_seed_keeps_baseline_stock(client):
    assert client.get("/audit/v1/inventory/var-jersey-001-M").json()["stock"] == 1
    assert client.get("/audit/v1/inventory/var-jersey-001-L").json()["stock"] == 5


def test_leagues_and_fixtures(client):
    leagues = client.get("/api/v1/leagues", headers=auth(client, "viewer")).json()["leagues"]
    assert [lg["league_id"] for lg in leagues] == ["league-alpha-1", "league-alpha-2"]
    apl = leagues[0]
    assert apl["sport_id"] == "football" and apl["teams"][0] == {"team_id": "club-alpha-1", "name": "Alpha United"}
    data = client.get("/api/v1/leagues/league-alpha-1/fixtures", headers=auth(client, "viewer")).json()
    fixtures = {f["match_id"]: f for f in data["fixtures"]}
    assert set(fixtures["demo-m1"]) == {"match_id", "round", "home", "away", "status", "scheduled_at", "venue",
                                        "home_score", "away_score", "version"}
    assert (fixtures["demo-m1"]["status"], fixtures["demo-m1"]["home_score"], fixtures["demo-m1"]["away_score"]) == \
        ("completed", 2, 1)
    assert (fixtures["demo-m3"]["home_score"], fixtures["demo-m3"]["away_score"]) == (1, 0)  # compensated goal
    assert fixtures["demo-m4"]["status"] == "in_progress"
    assert fixtures["demo-m5"]["home_score"] is None and fixtures["demo-m5"]["status"] == "upcoming"
    standings = client.get("/audit/v1/standings/league-alpha-1").json()
    assert standings["table"][0]["team_id"] == "club-alpha-1"


def test_tenant_isolation(client):
    viewer = auth(client, "viewer")
    assert client.get("/api/v1/leagues/league-beta-1/fixtures", headers=viewer).status_code == 403
    assert client.get("/api/v1/clubs/club-beta-1", headers=viewer).json()["error"]["code"] == "FORBIDDEN"
    assert client.get("/api/v1/leagues/nope/fixtures", headers=viewer).json()["error"]["code"] == "LEAGUE_NOT_FOUND"
    assert client.get("/api/v1/clubs/nope", headers=viewer).json()["error"]["code"] == "SQUAD_NOT_FOUND"
    assert client.get("/api/v1/leagues").status_code == 401
    admin = client.get("/api/v1/leagues", headers=auth(client, "admin")).json()["leagues"]
    assert len(admin) == 3


def test_clubs(client):
    clubs = client.get("/api/v1/clubs", headers=auth(client, "viewer")).json()["clubs"]
    assert {c["club_id"] for c in clubs} == {"club-alpha-1", "club-alpha-2", "demo-club-alpha-3",
                                             "demo-club-alpha-4"}
    club = client.get("/api/v1/clubs/club-alpha-1", headers=auth(client, "viewer")).json()
    assert club["short_name"] == "AUN" and club["home_venue"]["city"] == "Islamabad"
    assert {s["role"] for s in club["staff"]} == {"coach", "manager", "physio"}
    assert len(club["roster"]) == 12
    ali = next(p for p in club["roster"] if p["player_id"] == "player-alpha-1")
    assert (ali["role"], ali["position"], ali["registration_type"]) == ("captain", "gk", "initial")


def test_products_showcase_and_roster_config(client):
    products = client.get("/api/v1/products", headers=auth(client, "viewer")).json()["products"]
    jersey = next(p for p in products if p["product_id"] == "prod-jersey-001")
    assert jersey["variants"][0] == {"variant_id": "var-jersey-001-L", "size": "L", "color": "Blue",
                                     "price_minor": 450000, "currency": "PKR", "stock": 5}
    assert {p["category"] for p in products} == {"apparel", "accessory", "digital"}
    show = client.get("/api/v1/matches/demo-m4/showcase", headers=auth(client, "viewer")).json()
    assert show["product"]["product_id"] == "prod-jersey-001" and show["pinned_at"].endswith("Z")
    cfg = client.get("/api/v1/leagues/league-alpha-1/roster-config", headers=auth(client, "manager")).json()
    assert cfg["transfer_window"] == {"open": "2026-10-01", "close": "2026-10-31"}
    assert [s["player_count"] for s in cfg["squads"]] == [12, 12, 12, 12]


def test_pin_permissions(client):
    body = {"product_id": "demo-prod-scarf"}
    assert client.post("/api/v1/matches/demo-m5/showcase", json=body,
                       headers=auth(client, "viewer")).status_code == 403
    r = client.post("/api/v1/matches/demo-m5/showcase", json=body, headers=auth(client, "organizer"))
    assert r.status_code == 200 and r.json()["product"]["product_id"] == "demo-prod-scarf"
    assert client.post("/api/v1/matches/nope/showcase", json=body,
                       headers=auth(client, "admin")).json()["error"]["code"] == "MATCH_NOT_FOUND"
    assert client.post("/api/v1/matches/demo-m5/showcase", json={"product_id": "nope"},
                       headers=auth(client, "admin")).json()["error"]["code"] == "VARIANT_NOT_FOUND"


def test_events_twin_and_websocket(client):
    goal = {"event_id": "ws-goal-1", "match_id": "demo-m4", "type": "score",
            "payload": {"team_id": "club-alpha-2", "event_type": "goal"}}
    assert client.post("/api/v1/events", json=goal, headers=auth(client, "manager")).status_code == 403
    with client.websocket_connect("/ws/matches/demo-m4") as ws:
        r = client.post("/api/v1/events", json=goal, headers=auth(client, "organizer"))
        assert r.status_code == 201
        assert ws.receive_json() == {"type": "match_updated", "match_id": "demo-m4", "version": r.json()["sequence"]}
        client.post("/api/v1/matches/demo-m4/showcase", json={"product_id": "demo-prod-cap"},
                    headers=auth(client, "admin"))
        assert ws.receive_json() == {"type": "showcase_updated", "match_id": "demo-m4"}
    replay = client.post("/api/v1/events", json=goal, headers=auth(client, "organizer"))
    assert replay.status_code == 200
