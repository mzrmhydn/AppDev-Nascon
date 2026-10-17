# RBAC negative-authorization suite: the whole spec §5.13 matrix + token attacks + rate limit + login.
import base64
import json
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import JWT_SECRET
from app.main import app
from app.middleware import RateLimiter

ROLES = ["super_admin", "league_organizer", "club_manager", "player", "viewer"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        assert c.post("/audit/v1/reset").status_code == 200
        yield c


@pytest.fixture(scope="module")
def matrix(client):
    r = client.post("/audit/v1/rbac-matrix")
    assert r.status_code == 200
    return r.json()


def call(client, token, method, path):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if method == "GET":
        return client.get(path, headers=headers)
    return client.request(method, path, headers=headers, json={})


# (method, path template, context key or None, expected per role in ROLES order: A = allowed, D = denied)
MATRIX = [
    ("POST", "/audit/v1/rbac/tenants", None, "ADDDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "own_league_id", "AADDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "other_league_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "foreign_league_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "own_club_id", "ADADD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "other_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "foreign_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "own_club_id", "ADADD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "other_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "foreign_club_id", "ADDDD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "own_player_id", "ADAAD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "other_player_id", "ADDDD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "foreign_player_id", "ADDDD"),
    ("GET", "/audit/v1/rbac/clubs/{}", "own_club_id", "AAAAA"),
    ("GET", "/audit/v1/rbac/clubs/{}", "other_club_id", "AAAAA"),
    ("GET", "/audit/v1/rbac/clubs/{}", "foreign_club_id", "ADDDD"),
    ("GET", "/audit/v1/rbac/platform/config", None, "ADDDD"),
]


@pytest.mark.parametrize("method,template,key,expected", MATRIX)
def test_full_matrix(client, matrix, method, template, key, expected):
    path = template.format(matrix["context"][key]) if key else template
    for role, want in zip(ROLES, expected):
        r = call(client, matrix["tokens"][role], method, path)
        if want == "A":
            assert (r.status_code, r.json()) == (200, {"authorized": True}), (role, path)
        else:
            assert r.status_code == 403, (role, path)
            assert r.json()["error"]["code"] == "FORBIDDEN"


def test_matrix_context(matrix):
    assert set(matrix["tokens"]) == set(ROLES)
    assert matrix["context"]["foreign_player_id"] == "player-beta-1"


def tamper(token):
    head, body, sig = token.split(".")
    first = "A" if sig[0] != "A" else "B"
    return f"{head}.{body}.{first}{sig[1:]}"


def b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def alg_none(token):
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{token.split('.')[1]}."


def expired(token):
    return jwt.encode({"sub": "user-admin", "role": "super_admin", "exp": int(time.time()) - 10},
                      JWT_SECRET, algorithm="HS256")


def wrong_secret(token):
    return jwt.encode({"sub": "user-admin", "role": "super_admin", "exp": int(time.time()) + 60},
                      "wrong-secret", algorithm="HS256")


@pytest.mark.parametrize("make_bad", [lambda t: None, tamper, alg_none, expired, wrong_secret,
                                      lambda t: "garbage"])
def test_bad_tokens_401(client, matrix, make_bad):
    r = call(client, make_bad(matrix["tokens"]["super_admin"]), "GET", "/audit/v1/rbac/platform/config")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_unknown_ids_404_after_auth(client, matrix):
    admin = matrix["tokens"]["super_admin"]
    r = call(client, admin, "POST", "/audit/v1/rbac/leagues/nope/fixtures")
    assert r.json()["error"]["code"] == "LEAGUE_NOT_FOUND"
    assert call(client, admin, "GET", "/audit/v1/rbac/clubs/nope").status_code == 404
    r = call(client, admin, "PATCH", "/audit/v1/rbac/players/nope")
    assert r.json()["error"]["code"] == "PLAYER_NOT_FOUND"
    assert call(client, None, "GET", "/audit/v1/rbac/clubs/nope").status_code == 401


def login(client, email, password="Nascon@26"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_all_users_and_me(client):
    for email, role in [("admin@nascon.test", "super_admin"), ("ORGANIZER@nascon.test", "league_organizer"),
                        ("manager@nascon.test", "club_manager"), ("player@nascon.test", "player"),
                        ("viewer@nascon.test", "viewer")]:
        r = login(client, email)
        assert r.status_code == 200, email
        data = r.json()
        assert data["user"]["role"] == role
        me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {data['token']}"})
        assert me.json()["user"] == data["user"]
    manager = login(client, "manager@nascon.test").json()
    assert manager["user"]["club_id"] == "club-alpha-1" and manager["user"]["league_id"] is None
    assert manager["tenant"] == {"tenant_id": "tenant-alpha", "name": "Alpha Sports",
                                 "primary_color": "#0B5FFF", "accent_color": "#FFB020", "logo_url": None}
    admin = login(client, "admin@nascon.test").json()
    assert admin["tenant"] is None and admin["user"]["tenant_id"] is None


def test_login_failures(client):
    r = login(client, "admin@nascon.test", "nope")
    assert (r.status_code, r.json()["error"]["code"]) == (401, "UNAUTHENTICATED")
    r = client.post("/api/v1/auth/login", json={"email": 5})
    assert r.status_code == 400 and r.json()["error"]["details"]["fields"] == ["email", "password"]
    assert client.post("/api/v1/auth/login", content=b"{bad").status_code == 400


def test_rate_limit_window():
    limiter = RateLimiter()
    assert all(limiter.check("ip", now=i * 0.01) == 0 for i in range(100))
    assert limiter.check("ip", now=1.5) >= 1
    assert limiter.check("other", now=1.5) == 0
    assert limiter.check("ip", now=11.0) == 0  # the oldest hits have expired


def test_ping_rate_limited_then_recovers(client):
    client.post("/audit/v1/reset")  # reset also clears the limiter
    codes = [client.get("/api/v1/ping").status_code for _ in range(150)]
    assert codes[0] == 200 and codes.count(429) >= 40
    r = client.get("/api/v1/ping")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert client.get("/health").status_code == 200  # exempt
    client.post("/audit/v1/reset")
    assert client.get("/api/v1/ping").json() == {"pong": True}


def test_injection_like_ids_are_plain_data(client, matrix):
    r = call(client, matrix["tokens"]["super_admin"], "GET", "/audit/v1/rbac/clubs/x%27%3B%20DROP%20TABLE%20clubs")
    assert r.status_code == 404
