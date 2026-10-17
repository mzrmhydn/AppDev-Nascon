# 02 — Auth, RBAC, security probes — spec §5.13, FR-5.1, NFR-5 (6 pts, easy → do early)

## JWT (auth.py)
- HS256 with `JWT_SECRET`. Claims: `sub` (user_id), `role`, `tenant_id`, `league_id`, `club_id`, `player_id`, `exp` (now + 12 h), `iat`.
- Verify with `jwt.decode(token, SECRET, algorithms=["HS256"])` → this rejects `alg:none`, tampered signatures and expired tokens. Any failure → 401 `UNAUTHENTICATED`. Missing/garbled header → 401.
- `current_user` dependency: decode token → load nothing else (claims are enough) → user dict.
- Passwords: `pbkdf2_hmac("sha256", pw, salt, 100_000)`; store `salt$hash` hex.

## `POST /audit/v1/rbac-matrix` (no auth)
Return 5 fresh tokens for the 5 seeded users + the exact `context` block of the spec (ids are the seeded ids).
The demo users map to the scenario: organizer → `league_id: league-alpha-1`; manager → `club_id: club-alpha-1`; player → `player_id: player-alpha-1`, `club_id: club-alpha-1`; viewer → tenant-alpha only; admin → platform.

## Policy matrix (policy.py) — keep it a DATA TABLE, not if-chains
```python
# action -> rule name per role. Rules are tiny functions below.
POLICY = {
  "create_tenant":    {"super_admin": "always"},
  "manage_fixtures":  {"super_admin": "always", "league_organizer": "own_league"},
  "manage_roster":    {"super_admin": "always", "club_manager": "own_club"},
  "manage_products":  {"super_admin": "always", "club_manager": "own_club"},
  "edit_player":      {"super_admin": "always", "club_manager": "own_club_player", "player": "self"},
  "view_club":        {"super_admin": "always", "league_organizer": "same_tenant", "club_manager": "same_tenant",
                       "player": "same_tenant", "viewer": "same_tenant"},
  "platform_config":  {"super_admin": "always"},
}
```
Rules: `always`; `same_tenant` (target's tenant == user's tenant); `own_league` (league_id == user.league_id **and** same tenant); `own_club` (club_id == user.club_id); `own_club_player` (player's club == user.club_id); `self` (player_id == user.player_id). Role not in the dict → deny.
`can(user, action, target) -> bool`. One function, used by probes **and** the real `/api/v1` routes. Great viva answer: "the policy is data; adding a role is one line".

## Probe routes P1–P7 (spec table)
- Order: **auth first** (401) → look up the target's tenant/owner → if the id doesn't exist at all → 404 (with the matching `*_NOT_FOUND` — use `LEAGUE_NOT_FOUND`, `SQUAD_NOT_FOUND` for clubs?, `PLAYER_NOT_FOUND`) → `can()` → 200 `{"authorized":true}` or 403 `FORBIDDEN`.
  - Note: cross-tenant must be **403 not 404**. All grader ids exist (seeded), so 404 only for truly unknown ids.
- Do not validate or use the body. PATCH P5 gets `{}`.
- Write a pytest that loops over the **entire expected matrix** from the spec (it's ~65 checks) — this is also our negative-auth test suite (FR-5.1 requires it) and gives coverage for the `rbac` area.

## Rate limit (middleware.py)
- Only `/api/v1/*`. Sliding window per client IP: keep a `deque` of timestamps per IP; drop entries older than 10 s; if `len >= 100` → 429 `RATE_LIMITED`, header `Retry-After: <seconds until oldest expires, ≥1>`; else append + continue.
- Use a `threading.Lock` (routes run in a threadpool).
- `/audit/v1/*`, `/health`, `/ws/*` exempt.
- `GET /api/v1/ping` → 200 `{"pong":true}`, no auth.
- Spec probe: 150 req in 5 s → first 100 pass, ≥ 40 get 429, 11 s later 200. ✓ with this design.

## Input validation probes
- `sport_id = "x'; DROP TABLE sports;--"` → 400 `VALIDATION_ERROR` (regex check, plan 03). SQLAlchemy parameters already prevent injection — never build SQL with f-strings.
- `customer_id` with quotes / `<script>` → stored and returned as plain text, never 5xx.
- Body > 1 MB → 413 (plan 01).

## Login + me (`routes/api_auth.py`) — contract §2.1, §2.2
- Look up user by email (case-insensitive), verify password → token + user + tenant (tenant row: name, colors; `logo_url: null`).
- Seed tenant colors: alpha `#0B5FFF` / `#FFB020`, beta `#0E9F6E` / `#F05252`.

## Done when
Full matrix test green, alg:none/tampered/expired → 401, ping limiter passes, login works for all 5 accounts. Log decisions. Push.
