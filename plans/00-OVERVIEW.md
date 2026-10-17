# 00 — Backend overview: order of work, structure, decisions

## Points (spec §9) — this decides the order
| Area | Pts | Plan | Difficulty |
|---|---|---|---|
| Foundation (compose, health, reset, errors, signature) | 0 direct, but **everything fails without it** (−10 if not reproducible) | 01 | easy |
| RBAC 5-role matrix + security probes | 6 | 02 | **easy — do early** |
| Event-sourced scoring + mystery sport | 6 | 03 | medium |
| Standings | 6 | 04 | medium-hard |
| Fixtures (RR, Swiss, single, double elim) | 6 | 05 | RR + single = medium, Swiss + double = hard |
| Store concurrency + PDF receipt | 6 | 06 | medium |
| Roster / transfers / loans | 6 | 07 | medium |
| Offline sync (+ desk check) | 4 | 08 | easy once 03 + 07 exist |
| App API for the mobile app | (UI/HCI 10 pts depend on it) | 09 | easy |
| Tests, coverage bonus, submission files | 10% of each area | 10 | easy, continuous |

Each area: `S = 0.9·P·(passed/total vectors) + 0.1·P·[coverage ≥ 85 %]`. **Partial credit = more vectors passing** → finish the common path of every area before perfecting one.

## Suggested split (2 backend people; if only 1, do Track A then Track B)
- **Track A (platform):** 01 → 02 → 06 → 07 → 08 → 09
- **Track B (algorithms, mostly pure functions):** 03 → 04 → 05 (RR → single → double → Swiss)
- Track B can start immediately on pure functions in `backend/app/domain/` with unit tests while A builds the foundation.

## Two backend people in one folder — no-conflict rules
| File / folder | Owner |
|---|---|
| `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `app/main.py`, `config.py`, `db.py`, `errors.py`, `signing.py`, `middleware.py`, `auth.py`, `policy.py`, `seed.py`, `queue.py`, `realtime.py`, `models_platform.py` | **Track A** |
| `app/domain/*`, `services/sports.py`, `services/events.py`, `services/leagues.py`, `routes/audit_sports.py`, `audit_fixtures.py`, `audit_leagues.py`, `audit_events.py`, `audit_standings.py`, `models_league.py` (sports, leagues, matches, match_events) | **Track B** |
| `app/models.py` | just `from .models_platform import *` + `from .models_league import *` |
| `app/main.py` router list | Track A adds Track B's routers when B says "router X ready" (one line each) |
| `requirements.txt` | B asks A in chat to add a package |
- Track B starts **immediately** with pure functions in `domain/` + unit tests (no DB needed), and only needs A's foundation (`errors.py`, `signing.py`, `db.py`) after ~11:45.
- `seed.py` (A) needs the 4 sport configs → B posts them as a Python dict in `domain/seed_sports.py` (B owns) and A imports it.
- **Interfaces between tracks (agree once, don't change):**
  - B → A: `services.events.append_event(db, body: dict) -> tuple[int, dict]` (status code + response body; raises `AppError` on failure), `services.events.match_version(db, match_id) -> int`, `domain.scoring.project(...)`. A uses them in offline-sync, demo seed and `/api/v1` fixtures.
  - A → B: `errors.AppError(status, code, message, details)`, `signing.sign(id_, payload) -> str`, `db.get_db` (FastAPI dependency yielding a Session), `db.Base`.
  - Until A's files exist, B codes against these exact names; B's `domain/rule_error.py` `RuleError` is converted to `AppError` in B's services.
- `seed.py` must call `seed_demo()` inside `try/except Exception` and log the error — **a demo-seed bug must never stop startup or `/health`** (that would be the −10 non-reproducible penalty).
- Both: `git pull --rebase` before every push; commit small and often.

## Timeline (Day 1)
| Time | Target |
|---|---|
| by 12:45 | **Track A:** compose up, `/health`, errors, signing, `/reset` exact, login. **Track B:** domain functions for scoring, standings, RR, single elim with unit tests (done locally) + `models_league.py`. Push. |
| by 13:45 | **A:** RBAC + probes + ping + 413, checkout burst passes, roster, app API reads. **B:** routes/services for sports, events, score, leagues, standings, fixtures (RR + single). Push. |
| by 14:15 | **A:** offline-sync, write twins, demo seed. **B:** double elim, then Swiss. |
| 14:15 | Double elim / Swiss if time; `COVERAGE.json` from real run; README; TRACEABILITY |
| 14:30 | **Fresh-clone test** (§10). Fix only. |
| 14:45 | Final push (deadline 15:05:00) |
| 15:15 | Judges at desk: backend running on laptop, app installed, phone on hotspot |
| before 13:00 | Any spec question → organisers **in writing** |

## Requirements NOT graded by script (do last, minimal, but map them in TRACEABILITY.md)
TRACEABILITY must map **every** FR/NFR ID. These parts of the FRs have no `/audit` endpoint; give each a small, honest implementation or mark "partial" — judges/viva may ask:
- FR-1.2 multi-division, promotion/relegation, knockout/hybrid formats per season → store as league config JSON (`format`, `divisions`, `promotion_spots`); hybrid = RR groups + `single_elim` seeding from group standings (reuse plans 04/05).
- FR-1.3 manual rescheduling + conflict detection (venue double-booking, team/player overlap, min rest, venue windows) and the 6-state match status machine (upcoming, in_progress, completed, postponed, abandoned, cancelled) → one pure `domain/schedule_conflicts.py` returning `{"conflicts":[{"type","entity_ids"}]}` + a transition dict; broadcast status changes on the WebSocket.
- FR-2.3 scheduled price changes, order states Packed/Shipped/Delivered/Refunded with domain events, product pinning → plan 06 §order state machine, plan 09 showcase.
- FR-2.1 white-label tenant (logo, colors, name) → tenants table + login response (contract §2.1).

## Fixed structure (don't improvise — the app and other plans assume it)
```
docker-compose.yml          api (build ./backend, port 8080:8080) + db (postgres:16-alpine) + redis (redis:7-alpine, queue)
.env.example                DAY1_SALT=change-me, JWT_SECRET=..., DATABASE_URL=...
run_tests.sh, COVERAGE.json, README.md, TRACEABILITY.md, ADR.md
backend/
  Dockerfile                python:3.12-slim, pip install -r requirements.txt, uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1
  requirements.txt          fastapi, uvicorn[standard], sqlalchemy>=2, psycopg[binary], pyjwt, fpdf2, redis, pytest, pytest-cov, httpx, pypdf
                            (test tools are in the image on purpose: run_tests.sh must not need internet)
  app/
    main.py                 app factory, middlewares, exception handlers, routers, startup (create tables + seed)
    config.py               env vars: DAY1_SALT, JWT_SECRET, DATABASE_URL, REDIS_URL
    db.py                   engine, SessionLocal, get_db
    models.py               all SQLAlchemy tables
    errors.py               AppError(status, code, message, details) + handlers
    signing.py              canonical_json(), sign(id, payload), lots_key()
    middleware.py           body-size 413, /api/v1 rate limiter
    auth.py                 hash/verify password, make/verify JWT, current_user dependency
    policy.py               RBAC policy matrix (data table) + can(user, action, target)
    seed.py                 reset_baseline(seed, stock), seed_demo()
    queue.py                emit_domain_event() → Redis Stream "domain-events"
    realtime.py             WebSocket connection manager per match_id
    domain/                 PURE functions, no DB
      fixtures_round_robin.py, fixtures_swiss.py, fixtures_single_elim.py, fixtures_double_elim.py
      sport_config.py       validate a sport JSON (spec §5.6)
      scoring.py            project(sport_config, events) → score dict (spec §5.9)
      standings.py          compute_standings(...) (spec §5.10)
      roster_rules.py       check order 1–8 (spec §5.11)
      receipt_pdf.py        build PDF bytes
    services/               DB + domain glue (one file per area)
      sports.py, events.py, leagues.py, store.py, roster.py, offline_sync.py
    routes/
      health.py, audit_reset.py, audit_sports.py, audit_fixtures.py, audit_leagues.py, audit_events.py,
      audit_standings.py, audit_roster.py, audit_store.py, audit_rbac.py, audit_offline.py,
      api_auth.py, api_app.py (leagues, fixtures, clubs, products, showcase, roster-config), api_writes.py (twins), ws.py
tests/backend/              pytest; test files named after areas (test_fixtures_*.py, test_scoring.py, …)
```

## Pre-made decisions (log them as D-BE-000.. with these reasons)
| Decision | Why | Rejected |
|---|---|---|
| FastAPI | Pydantic validation, auto `/docs`, little code | Flask (manual validation), Django (heavy) |
| PostgreSQL 16 + SQLAlchemy 2 (sync) | Row locks / transactions for concurrency; JSONB for sport configs | SQLite (bad concurrent writes), Mongo (not approved) |
| One uvicorn worker | In-memory rate limiter + WebSocket manager stay correct; Postgres handles concurrency | Many workers (would need Redis for rate limit/WS fan-out) |
| Sync SQLAlchemy in normal `def` routes | FastAPI runs them in a threadpool → real concurrency for the 20-buyer test, simpler than async | async SQLAlchemy (harder to read/debug) |
| Pure domain functions | Unit-testable, explainable, coverage bonus | Logic inside routes |
| Redis Streams for domain events | Approved, 1 line `XADD`, already pulled | RabbitMQ (more setup), NATS |
| fpdf2 for PDF | Pure Python wheel, no system libs → fast Docker build | WeasyPrint (needs Pango/Cairo apt packages, slow build) |
| PyJWT HS256, `algorithms=["HS256"]` | Rejects `alg:none` automatically | Keycloak (huge, slow to start) |
| Password hashing: `hashlib.pbkdf2_hmac` | Stdlib, no dependency | bcrypt/passlib (extra deps) |
| Pydantic **strict** types | Spec: wrong types → 400 (lax mode would turn `"1"` into `1`) | default lax |
| Create tables + seed at startup | Fresh clone works, no migrations step | Alembic (extra step) |

Keep MinIO/RabbitMQ/NATS etc. **out** unless needed — the spec says compose brings up "database, cache, queue, object store, workers" but grading is by endpoint; Redis covers cache + queue. If you have spare time at 14:00, add `minio` to compose and store receipt PDFs there (nice viva point) — not before.
