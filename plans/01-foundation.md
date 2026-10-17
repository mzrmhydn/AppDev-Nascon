# 01 — Foundation (Track A, do first) — spec §1.2, §1.3, §5.2–5.5, NFR-7

Goal for the 11:45 push: `DAY1_SALT=x docker compose up -d --build` → `GET localhost:8080/health` = 200.

## Steps
1. **docker-compose.yml**
   - `db`: `postgres:16-alpine`, env `POSTGRES_USER/PASSWORD/DB=nascon`, healthcheck `pg_isready -U nascon`. **No host port needed.** No named volume required (fresh each run is fine; an anonymous volume is OK).
   - `redis`: `redis:7-alpine`, healthcheck `redis-cli ping`.
   - `api`: `build: ./backend`, `ports: ["8080:8080"]`, `environment: DAY1_SALT: ${DAY1_SALT}`, `JWT_SECRET: ${JWT_SECRET:-dev-jwt-secret-change-me}`, `DATABASE_URL: postgresql+psycopg://nascon:nascon@db:5432/nascon`, `REDIS_URL: redis://redis:6379/0`; `depends_on: db/redis: condition: service_healthy`; `restart: unless-stopped`.
2. **Dockerfile** (`python:3.12-slim`): copy `requirements.txt` first, `pip install --no-cache-dir`, then copy `app/`. CMD uvicorn on 0.0.0.0:8080, **1 worker**.
3. **config.py** reads env. `DAY1_SALT` read as-is (no strip!). If missing, start anyway with `""` and log a warning (grader always sets it).
4. **db.py / models.py** — tables (JSONB for configs). Suggested:
   - `tenants(tenant_id PK, name, primary_color, accent_color)`
   - `users(user_id PK, email UNIQUE, password_hash, role, display_name, tenant_id, league_id, club_id, player_id)`
   - `sports(sport_id PK, config JSONB, is_seed bool)`
   - `leagues(league_id PK, tenant_id NULL, name, season, sport_id NULL, teams JSONB, points JSONB, tie_break_order JSONB, qualification_spots, lots_seed, created_via)`
   - `matches(match_id PK, league_id NULL, sport_id, home_team_id, away_team_id, round NULL, scheduled_at NULL, venue NULL)`
   - `match_events(id serial PK, match_id, sequence, event_id UNIQUE, type, payload JSONB, signature, request_hash, response JSONB, created_at)` — **append only, never UPDATE/DELETE** (except `/reset`)
   - `clubs(club_id PK, tenant_id, name, short_name, primary_color, profile JSONB)` (venue, socials, staff, stats)
   - roster tables → plan 07; store tables → plan 06; `idempotency(scope, key, request_hash, status_code, response JSONB, PK(scope,key))`; `offline_actions(device_id, action_id, result JSONB, PK)`; `showcase(match_id PK, product_id, pinned_at)`
   - Startup: `Base.metadata.create_all()` then `reset_baseline(42, defaults)` + `seed_demo()` if not seeded.
5. **errors.py**
   - `class AppError(Exception): status, code, message, details={}`.
   - Handler → `{"error":{"code","message","details"}}`.
   - Override FastAPI's `RequestValidationError` → **400** `VALIDATION_ERROR`, `details.fields` = list of field names (last element of each `loc`). Malformed JSON → 400 too.
   - Catch-all `Exception` handler → 500 `INTERNAL_ERROR` (should never happen; log it).
   - Helper for hand validation: `raise AppError(400, "VALIDATION_ERROR", "...", {"fields": ["x"]})`.
6. **middleware.py**
   - Body > 1 MB (1 048 576 bytes) on any POST/PATCH → 413 `PAYLOAD_TOO_LARGE` (check `Content-Length`, and if absent read the body and check length).
   - Rate limiter only for paths starting `/api/v1/` → plan 02.
7. **signing.py** — copy spec Appendix A exactly:
   `canonical(obj) = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`;
   `sign(id_, payload) = hmac.new(SALT.encode(), (id_+"|"+canonical(payload)).encode(), sha256).hexdigest()`.
   **Unit test** with Appendix A test vector 1 (salt `demo-salt` → `972a8b55…c501`) and vector 2 (lots keys).
   ⚠ Canonical JSON of floats: payloads here contain ints/strings only — keep ints as ints (don't let Pydantic turn them into floats).
8. **`GET /health`** → 200 `{"status":"ok"}` only if `SELECT 1` works **and** baseline seeded (e.g. tenant-alpha exists); else 503 with error body.
9. **`POST /audit/v1/reset`** (spec §5.5) — body optional. `seed` int default 42; `stock` map default `{M:1, L:5}`. Validate: seed must be int, stock values ints ≥ 0 → else 400.
   - In **one transaction**: `TRUNCATE` every table `RESTART IDENTITY CASCADE`, then insert the baseline exactly (tenants, product + 2 variants @ 450000 + `WELCOME10`, leagues `league-alpha-1/-2` (tenant-alpha), `league-beta-1` (tenant-beta), clubs `club-alpha-1/-2`, `club-beta-1`, players `player-alpha-1/-2`, `player-beta-1`, 5 demo users, 4 seed sports as JSON configs — same schema as plan 03).
   - Store the `seed` (e.g. in a `settings` table) — default `lots_seed` for later leagues.
   - Reset the in-memory rate limiter too.
   - Response exactly as spec, `sports` in order `["football","basketball","cricket","esports"]`, `tenants` `["tenant-alpha","tenant-beta"]`, `stock` = the stock used. Must finish < 10 s and be repeatable.
   - Does **not** call `seed_demo()`.

## Seed sport configs (as JSON data, spec §5.5 table)
- football: `event`, periods `{count:2,duration_minutes:45}`, scoring `{goal:{points:1}}`, draw true, overtime `{policy:"none"}`, roster `{min_squad_size:11,max_squad_size:25,required_positions:{gk:1}}`.
- basketball: `event`, `{count:4,duration_minutes:12}`, `{free_throw:{points:1},two_pointer:{points:2},three_pointer:{points:3}}`, draw false, `{policy:"extra_time",duration_minutes:5}`, roster `{5,15,{}}`.
- cricket: `innings`, `{innings_per_team:1,overs_per_innings:20,balls_per_over:6,wickets_per_innings:10}`, scoring: `dot_ball{0,legal:true,wicket:false}`, `single{1,T,F}`, `two{2,T,F}`, `four{4,T,F}`, `six{6,T,F}`, `wide{1,legal:false,F}`, `no_ball{1,F,F}`, `wicket{0,T,wicket:true}`; draw true; `{policy:"super_over"}`; roster `{11,18,{wicketkeeper:1}}`.
- esports: `round`, `{best_of:3}`, `{round_win:{rounds:1}}`, draw false, `{policy:"none"}`, roster `{5,8,{}}`.
- tie_break_order default = full list for all.

## Done when
- Fresh clone + compose up → health 200 in < 120 s; `/reset` twice gives identical results; signature test vector passes.
- Log decisions (D-BE-0xx) + walkthrough. Push.
