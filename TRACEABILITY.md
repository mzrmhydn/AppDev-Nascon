# Traceability matrix

| ID | Requirement | Source files | Automated tests | Status |
|---|---|---|---|---|
| FR-1.1 | Multi-sport taxonomy, mystery sport, event-sourced scoring | backend/app/domain/sport_config.py, domain/scoring.py, services/events.py | tests/backend/test_scoring.py | todo |
| FR-1.2 | League & tournament setup | backend/app/services/leagues.py | tests/backend/test_standings.py | todo |
| FR-1.3 | Fixture scheduling (RR, Swiss, single, double elim) | backend/app/domain/fixtures_*.py | tests/backend/test_fixtures_*.py | todo |
| FR-1.4 | Standings, tie-breakers, qualification | backend/app/domain/standings.py | tests/backend/test_standings.py | todo |
| FR-2.1 | Club profiles, tenant isolation | backend/app/routes/api_app.py; mobile/app/club | tests/backend/test_rbac.py | todo |
| FR-2.2 | Roster, transfers, loans, audit trail | backend/app/domain/roster_rules.py, services/roster.py | tests/backend/test_roster.py | todo |
| FR-2.3 | Merchandise store, checkout, PDF receipt | backend/app/services/store.py, domain/receipt_pdf.py; mobile/app/store | tests/backend/test_store.py | todo |
| FR-5.1 | 5-tier RBAC | backend/app/policy.py, auth.py, routes/audit_rbac.py | tests/backend/test_rbac.py | todo |
| NFR-3 | Concurrency correctness | backend/app/services/store.py | tests/backend/test_store.py (20-thread burst) | todo |
| NFR-4 | Offline tolerance | backend/app/services/offline_sync.py; mobile/src/offline/* | tests/backend/test_offline_sync.py | todo |
| NFR-5 | Security (JWT, rate limit, validation, secure storage) | backend/app/middleware.py, auth.py; mobile/src/auth* | tests/backend/test_rbac.py | todo |
| NFR-7 | Reproducibility | docker-compose.yml, backend/Dockerfile | run_tests.sh | todo |
