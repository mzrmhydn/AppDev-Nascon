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
   - `players(player_id PK, name, position, club_id NULL, tenant_id NULL)` — **one players table for everything**: baseline RBAC players (`player-alpha-1` → club `club-alpha-1`, tenant-alpha; `player-alpha-2` → `club-alpha-2`; `player-beta-1` → `club-beta-1`, tenant-beta) and players created by `/roster/setup` (plan 07 upserts them). RBAC P5 "own club's players" reads `players.club_id`.
   - `settings(key PK, value)` — stores `last_reset_seed`.
   - `db.py`: `create_engine(DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True)` — the default pool (5+10) would queue the 20 simultaneous checkouts.
4b. **Request models:** Pydantic `model_config = ConfigDict(extra="ignore", strict=True)` — spec §5.2: unknown fields are **ignored**, missing fields / wrong types → 400. Ids: 1–64 chars from `A-Za-z0-9_.:-` (never `|`), stored and returned verbatim — use one helper `ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,64}$"`.
   - ⚠ In strict mode Pydantic does **not** turn `"2026-09-30"` into a `date`. Type every date/timestamp field as `str` and validate it yourself with `date.fromisoformat()` / `datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")` → 400 `VALIDATION_ERROR` with that field name.
   - ⚠ **Never sign or compare a Pydantic-dumped body.** For signatures and idempotency use the **raw JSON** exactly as received (`body = await request.json()` or `Body(...)` as `dict`), because dumping can drop unknown keys or add defaults and the grader signs what it sent.
4c. **Compose extras (P2, after 13:45 if time):** spec §1.3 says compose brings up "database, cache, queue, object store, workers". Redis already = cache + queue. Cheap extras: a `worker` service (same image, `command: python -m app.worker`) that reads the `domain-events` Redis Stream and logs each event; and `minio` (`minio/minio:RELEASE.2024-09-22T00-33-43Z`, `server /data`) for receipt PDFs. Neither must be on the critical path: the API must stay healthy even if they fail. Keep total RAM well under the grader's 8 GB.
5. **errors.py**
   - `class AppError(Exception): status, code, message, details={}`.
   - Handler → `{"error":{"code","message","details"}}`.
   - Override FastAPI's `RequestValidationError` → **400** `VALIDATION_ERROR`, `details.fields` = list of field names (last element of each `loc`). Malformed JSON → 400 too.
   - Catch-all `Exception` handler → 500 `INTERNAL_ERROR` (should never happen; log it).
   - Also register a handler for `starlette.exceptions.HTTPException` so unknown routes (404) and wrong methods (405) use the same error body (`code` `NOT_FOUND` / `METHOD_NOT_ALLOWED` — these never reach the grader's checked routes, but keep every non-2xx in one shape).
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
   - In **one transaction**: `TRUNCATE` every table `RESTART IDENTITY CASCADE`, then insert the baseline exactly:
     - tenants: `tenant-alpha` "Alpha Sports" (`#0B5FFF` / `#FFB020`), `tenant-beta` "Beta Athletics" (`#0E9F6E` / `#F05252`)
     - product `prod-jersey-001` (tenant-alpha, club `club-alpha-1`, apparel, "Home Jersey 2026"); variants `var-jersey-001-M` (size M, Blue) and `var-jersey-001-L` (size L, Blue), each `price_minor` 450000, stock from the request (default M=1, L=5), reserved 0; discount `WELCOME10` = 10 %
     - leagues `league-alpha-1` "Alpha Premier League", `league-alpha-2` "Alpha Basketball Cup" (tenant-alpha), `league-beta-1` "Beta League" (tenant-beta) — season "2026", no sport/teams yet
     - clubs `club-alpha-1` "Alpha United", `club-alpha-2` "Alpha Rovers" (tenant-alpha), `club-beta-1` "Beta Strikers" (tenant-beta)
     - players `player-alpha-1` "Ali Khan" (gk, club-alpha-1), `player-alpha-2` "Bilal Ahmed" (df, club-alpha-2), `player-beta-1` "Hamza Raza" (fw, club-beta-1)
     - the 5 users of `contracts/API.md` §3 (ids, emails, roles, password `Nascon@26`; organizer `league_id` = league-alpha-1; manager `club_id` = club-alpha-1; player `club_id` = club-alpha-1, `player_id` = player-alpha-1; all except admin have `tenant_id` = tenant-alpha)
     - the 4 seed sports from `domain/seed_sports.py` (Track B) — same stored format as `POST /audit/v1/sports`.
   - Store the `seed` (e.g. in a `settings` table) — default `lots_seed` for later leagues.
   - Reset the in-memory rate limiter too.
   - Response exactly as spec, `sports` in order `["football","basketball","cricket","esports"]`, `tenants` `["tenant-alpha","tenant-beta"]`, `stock` = the stock used. Must finish < 10 s and be repeatable.
   - Does **not** call `seed_demo()`.

## Seed sport configs
Already written by Track B in `backend/app/domain/seed_sports.py` (`SEED_SPORTS`, validated by a unit test against spec §5.5). `seed.py` imports it — do not retype the configs.

## `.env.example` must list every variable
```
DAY1_SALT=change-me
JWT_SECRET=dev-jwt-secret-change-me
DATABASE_URL=postgresql+psycopg://nascon:nascon@db:5432/nascon
REDIS_URL=redis://redis:6379/0
```

## Done when
- Fresh clone + compose up → health 200 in < 120 s; `/reset` twice gives identical results; signature test vector passes.
- Log decisions (D-BE-0xx) + walkthrough. Push.
