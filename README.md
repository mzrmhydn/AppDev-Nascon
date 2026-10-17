# AppDev-Nascon — Multi-Sport League & Club Operations Platform (NaSCon'26 Part I)

## Run the backend
```bash
DAY1_SALT=<your-salt> docker compose up -d --build
curl http://localhost:8080/health   # {"status":"ok"} once the baseline is seeded (~10-20 s)
```
- API on host port **8080**; interactive docs at `http://localhost:8080/docs`.
- Services: `api` (FastAPI, 1 uvicorn worker), `db` (PostgreSQL 16), `redis` (cache + domain-event queue, Redis Stream `domain-events`).
- No manual steps: tables are created and the spec §5.5 baseline + demo data are seeded at startup.
- `POST /audit/v1/reset` restores the exact spec baseline (demo data is only added at startup or via `POST /api/v1/dev/demo-seed`).

### Environment variables (see `.env.example`)
| Variable | Purpose | Default in compose |
|---|---|---|
| `DAY1_SALT` | HMAC key for event/receipt signatures — **from the environment only, never committed** | forwarded from your shell / `.env` |
| `JWT_SECRET` | HS256 key for login + RBAC tokens | `dev-jwt-secret-change-me` |
| `DATABASE_URL` | SQLAlchemy URL | `postgresql+psycopg://nascon:nascon@db:5432/nascon` |
| `REDIS_URL` | Redis for the domain-event queue | `redis://redis:6379/0` |

## Run the tests
```bash
./run_tests.sh      # builds the stack, runs pytest + coverage inside the api container (real Postgres), writes COVERAGE.json
```
Without Docker (pure functions + API tests on a throw-away SQLite file):
```bash
python -m pip install -r backend/requirements.txt
python -m pytest tests/backend -q
```

## Mobile app
- APK: `mobile/release/app-release.apk` (Android 10+).
- Settings screen → server address: emulator `http://10.0.2.2:8080`, phone on the same Wi-Fi/hotspot `http://<laptop-LAN-IP>:8080` (find it with `ipconfig` / `ip addr`).
- Live match updates: WebSocket `ws://<host>:8080/ws/matches/{match_id}` (+ 5 s polling fallback).

## Demo accounts (spec §8.3 — password for all: `Nascon@26`)
| Role | Email | Scope |
|---|---|---|
| Platform Super-Admin | admin@nascon.test | all tenants |
| League Organizer | organizer@nascon.test | league-alpha-1 (tenant-alpha) |
| Club Manager | manager@nascon.test | club-alpha-1 (tenant-alpha) |
| Player | player@nascon.test | player-alpha-1, club-alpha-1 |
| General Viewer | viewer@nascon.test | read-only, tenant-alpha |

## Demo data (startup)
Alpha Premier League (football, 4 clubs, 6 fixtures: 3 completed incl. a compensated goal, 1 live, 2 upcoming), Alpha Basketball Cup, 48 registered players, club profiles, store with jersey/scarf/cap/wallpaper and a product pinned on the live match.

## Repo map
`backend/app/domain/` pure algorithms (scoring, standings, fixtures, roster rules, receipt PDF) · `backend/app/services/` DB glue · `backend/app/routes/` thin HTTP routes · `tests/backend/` pytest · `mobile/` React Native (Expo) app · `contracts/API.md` app ↔ backend contract · `TRACEABILITY.md` requirement → code → tests · `ADR.md` architecture decisions.
