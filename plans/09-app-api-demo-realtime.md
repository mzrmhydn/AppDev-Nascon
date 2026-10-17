# 09 — App API, demo data, realtime (Track A, after 02) — contract §2, spec §8

The mobile app (frontend dev) is built **right now** against `contracts/API.md` §2. Implement those routes with **exactly** those shapes. If you can't, follow `plans/FRONTEND-CONTRACT-GUARD.md`.

## A. Routes (`routes/api_app.py`, `routes/api_writes.py`) — all thin
- Every `/api/v1` route except login/ping/demo-seed uses `current_user` (plan 02) and filters by `user.tenant_id` (super_admin: no filter). Cross-tenant id → 403 `FORBIDDEN`; unknown id → 404.
- `GET /api/v1/leagues` — leagues of the tenant with `teams` (team_id + name; name = club name if a club with that id exists, else the id).
- `GET /api/v1/leagues/{id}/fixtures` — `matches` of the league + `project()` per match for status/scores/version.
- `GET /api/v1/clubs`, `GET /api/v1/clubs/{id}` — club row + `profile` JSON + current roster (registrations active today whose squad.club_id = club).
- `GET /api/v1/products` — products + variants with current price + stock.
- `GET/POST /api/v1/matches/{id}/showcase` — `showcase` table; POST checks `can()` and broadcasts.
- `GET /api/v1/leagues/{id}/roster-config` — roster league + squads with counts.
- **Write twins:** `POST /api/v1/events | /roster/transfer | /checkout | /offline-sync` = `can()` check (contract §2.11) **then** call the exact same service as the audit route and return its status + body unchanged.

## B. Demo data — `seed.py: seed_demo()` (startup + `POST /api/v1/dev/demo-seed`; NEVER from `/audit/v1/reset`)
Idempotent (skip rows that exist). All ids prefixed `demo-` except the seeded baseline ids it extends. Gives the judges something real to look at:
- **Clubs** (tenant-alpha): fill profiles of `club-alpha-1` "Alpha United" (AUN, `#0B5FFF`, Alpha Arena Islamabad 33.6844/73.0479, staff coach/manager/physio, 2 seasons of stats), `club-alpha-2` "Alpha Rovers" (ARO), and add `demo-club-alpha-3` "Margalla FC" (MFC), `demo-club-alpha-4` "Rawal City" (RCY). `club-beta-1` "Beta Strikers" for tenant-beta.
- **League `league-alpha-1`** "Alpha Premier League", season "2026", sport `football`, teams = the 4 alpha clubs, points 3/1/0, qualification spots 2. Fixtures (single round robin, 6 matches `demo-m1..demo-m6`) with `scheduled_at` today/tomorrow and `venue`:
  - demo-m1..m3 **completed** with goal events (append through the normal events service so signatures are real; use event ids `demo-evt-…`); one has a discipline event and one has a compensated goal (shows the timeline feature).
  - demo-m4 **in_progress** (started, 1–1).
  - demo-m5, demo-m6 **upcoming**.
- `league-alpha-2` "Alpha Basketball Cup" (sport basketball) with 2 upcoming fixtures — shows multi-sport.
- **Roster** for `league-alpha-1`: roster setup with `transfer_window` = **2026-10-01 → 2026-10-31** (covers judging day), max 25, required `{gk:1}`; squads `squad_id = club_id` for the 4 clubs; 12 players each (positions gk×2, df×4, mf×3, fw×3; roles captain / vice_captain / starters / substitutes). Include `player-alpha-1` (club-alpha-1, captain) and `player-alpha-2` (club-alpha-2). Realistic Pakistani names.
- **Store:** keep baseline `prod-jersey-001` (club-alpha-1, apparel, "Home Jersey 2026", Blue). Add `demo-prod-scarf` (accessory, one variant, 150000, stock 20), `demo-prod-cap` (accessory, colors Black/White, 120000, stock 10 each), `demo-prod-wallpaper` (digital, 30000, stock 999). Pin `prod-jersey-001` on `demo-m4`.
- ⚠ Demo seeding must not change the baseline jersey stock (M=1, L=5).

## C. Realtime — `realtime.py` + `routes/ws.py`
- `ConnectionManager`: `dict[match_id, set[WebSocket]]`, `connect`, `disconnect`, `broadcast(match_id, message)`.
- Services run in threadpool threads → broadcast from sync code with `anyio.from_thread.run(manager.broadcast, …)` or keep a reference to the event loop at startup and use `asyncio.run_coroutine_threadsafe`. Wrap in try/except — **a broadcast failure must never fail the request**.
- `/ws/matches/{match_id}`: accept, keep open, ignore incoming messages.
- If this gets hard, skip it: the app also polls every 5 s. Tell the frontend dev (guard file) if you drop it.

## Done when
Log in as each demo user in `/docs` → every contract §2 route returns the documented shape; WebSocket message arrives after posting an event.
