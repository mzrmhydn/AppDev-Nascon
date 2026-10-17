# Architecture Decision Records

Short records of the decisions with real alternatives. Status of all: **accepted** (Day 1).

## ADR-1 — FastAPI + sync SQLAlchemy, one uvicorn worker
**Context:** strict JSON contracts, little time, must be explainable line by line. **Decision:** FastAPI routes stay thin; DB work is sync SQLAlchemy run in FastAPI's threadpool; one worker. **Why:** threadpool gives real parallelism for the 20-buyer burst while the code stays plain; one process keeps the rate limiter and WebSocket manager correct in memory. **Rejected:** Flask (manual validation), Django (heavy), async SQLAlchemy (harder to read), many workers (would need Redis for limiter/WebSockets). **Consequence:** scaling out later needs shared state in Redis.

## ADR-2 — PostgreSQL row locks for zero overselling (NFR-3)
**Decision:** reserve with `UPDATE variants SET stock = stock - q, reserved = reserved + q WHERE variant_id = :v AND stock >= q`, items in sorted order; rowcount 0 → rollback → 409. `CHECK (stock >= 0)` as a safety net. Payment runs between two short transactions. **Why:** the row lock serialises buyers and the `WHERE` is re-checked after the lock, so exactly one wins; sorted order prevents deadlocks. **Rejected:** read-then-write (race), SERIALIZABLE (retries), Redis locks (extra moving part).

## ADR-3 — Event sourcing with compensating events for scoring (FR-1.1)
**Decision:** `match_events` is append-only and signed; corrections are new `compensation` events; `/score` and `/standings` are rebuilt from the log on every read by pure functions. **Why:** full audit trail, replay, offline merge; a compensation after full time correctly flips results and qualification. **Rejected:** mutable score counters (spec forbids; drift). **Consequence:** O(events) per read — fine at match scale, cache later if needed.

## ADR-4 — RBAC as data (policy matrix) (FR-5.1)
**Decision:** `policy.POLICY[action][role] = rule`; six tiny rule functions; every non-`always` rule also requires the same tenant; one `can()` used by probes and app routes. **Why:** auditable in one screen, adding a role is one line per action, the whole matrix is a parametrised test. **Rejected:** if-chains in routes, Casbin/OPA (dependency + DSL).

## ADR-5 — Pure-function domain layer
**Decision:** scoring, standings, fixtures, roster rules and the receipt PDF are pure functions in `app/domain/` (no DB/HTTP); services do DB glue. **Why:** fast unit tests (coverage bonus), easy to explain and change live, the same rules serve audit routes, app routes and offline sync. **Rejected:** logic inside routes/services.

## ADR-6 — Redis Stream as the internal queue (FR-2.3)
**Decision:** order transitions `XADD` to stream `domain-events`; best effort with a 30 s circuit breaker. **Why:** one command, already in the stack as cache. **Rejected:** RabbitMQ/NATS (more setup), outbox table (more code). **Consequence:** events can be lost while Redis is down — acceptable for notifications, not for money (money lives in Postgres).

## ADR-7 — fpdf2 for server-side receipts
**Decision:** pure-Python fpdf2 with a core font; non-Latin-1 text replaced in the PDF only. **Why:** no system libraries → fast, reliable Docker build. **Rejected:** WeasyPrint (Pango/Cairo packages), ReportLab (heavier).

## ADR-8 — Offline sync: replay through the real services, server wins on conflict (NFR-4)
**Decision:** actions sorted by `queued_at`, each in its own transaction through the same `append_event` / `transfer` functions; `base_version == current` → appended, `<` and still legal → rebased_append, `>` → rejected; any rule failure → rejected/server_wins with the rule's code; every result stored per (device, action) so re-sends are duplicates. **Why:** one rule engine for online and offline; deterministic, idempotent. **Rejected:** client-wins/last-write-wins (could break scoring rules), a separate offline rule engine (two copies to keep in sync).
