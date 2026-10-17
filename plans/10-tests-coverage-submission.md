# 10 — Tests, coverage bonus, submission files (continuous) — spec §1.3, §9.3, Appendix C

## Tests
- `tests/backend/` with pytest. Pure-function tests (`domain/`) need no DB → fast; service/route tests use FastAPI `TestClient` against the compose Postgres.
- Name test files by area: `test_fixtures_*.py`, `test_scoring.py`, `test_standings.py`, `test_store.py`, `test_roster.py`, `test_rbac.py`, `test_offline_sync.py`, `test_signing.py`.
- **Area → modules map** (for COVERAGE.json; keep it in `tests/coverage_areas.py`):
  - fixtures: `app/domain/fixtures_*.py`, `app/routes/audit_fixtures.py`
  - scoring: `app/domain/scoring.py`, `app/domain/sport_config.py`, `app/services/events.py`, `app/services/sports.py`
  - standings: `app/domain/standings.py`, `app/services/leagues.py`
  - store: `app/services/store.py`, `app/domain/receipt_pdf.py`, `app/services/payment_gateway.py`
  - roster: `app/domain/roster_rules.py`, `app/services/roster.py`
  - rbac: `app/auth.py`, `app/policy.py`, `app/routes/audit_rbac.py`, `app/middleware.py`

## `run_tests.sh` (repo root, executable: `git update-index --chmod=+x run_tests.sh`)
```bash
#!/usr/bin/env bash
# Runs all backend unit tests with coverage inside the api image, then writes COVERAGE.json.
set -euo pipefail
export DAY1_SALT="${DAY1_SALT:-test-salt}"
docker compose up -d --build db redis api
docker compose exec -T api pip install -q pytest pytest-cov httpx pypdf >/dev/null 2>&1 || true
docker compose cp tests api:/app/tests
docker compose exec -T api python -m pytest tests/backend -q --cov=app --cov-report=json:/app/coverage.json
docker compose exec -T api python tests/coverage_areas.py /app/coverage.json > COVERAGE.json
cat COVERAGE.json
```
(Adapt paths to the real layout; the point: **one command**, works on a judge's machine with only Docker.)
`tests/coverage_areas.py` reads coverage.py's JSON, sums covered/total statements per area, prints `{"fixtures": 91.2, …}` rounded to 1 decimal.

## COVERAGE.json
**Only commit numbers produced by `run_tests.sh`.** Judges may rerun; > 2 points lower than declared → that area's bonus is void. An area below 85 % gets no bonus anyway — still report the true number.

## README.md (required)
Run instructions (`DAY1_SALT=… docker compose up -d --build`, `./run_tests.sh`), the 5 demo accounts table (spec §8.3), how to point the app at the laptop's LAN IP, where the APK is.

## TRACEABILITY.md (required)
Table: `ID | Requirement | Source files | Tests | Status` for FR-1.1, FR-1.2, FR-1.3, FR-1.4, FR-2.1, FR-2.2, FR-2.3, FR-5.1, NFR-3, NFR-4, NFR-5, NFR-7. Update when a feature lands. The frontend dev fills the mobile rows.

## ADR.md (needed for the Day 2 viva — 8 short ADRs)
Promote from `notes/DECISIONS-*.md`: FastAPI; Postgres + row locks for NFR-3; event sourcing + compensation; policy-as-data RBAC; pure-function domain layer; Redis Streams queue; fpdf2; offline-sync conflict policy (server_wins / rebase).

## Fresh-clone check — 14:30, mandatory
```bash
cd /tmp && rm -rf check && git clone https://github.com/mzrmhydn/AppDev-Nascon check && cd check
DAY1_SALT=abc docker compose up -d --build
curl -s localhost:8080/health
curl -s -X POST localhost:8080/audit/v1/reset
```
+ the 20-thread checkout test + one RBAC probe. Then `docker compose down -v`. Fix only what's broken. Final push ≤ 14:45.

## Pre-submission checklist (spec Appendix C) — tick in chat before the final push
- [ ] compose up works on clean machine; /health 200 < 2 min
- [ ] /reset twice → identical; 5 demo accounts + all seed ids exist
- [ ] every response field name compared with spec examples character by character
- [ ] signature test vector passes
- [ ] 20 parallel checkouts on stock 1 → 1×201, 19×409, stock 0, reserved 0
- [ ] /audit not rate limited, /api/v1/ping is
- [ ] COVERAGE.json, TRACEABILITY.md, README.md, .env.example, mobile/release/app-release.apk committed + pushed
- [ ] last push before 15:05:00
