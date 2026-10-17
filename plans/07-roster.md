# 07 — Roster setup, transfers, loans, history — spec FR-2.2, §5.11 (6 pts)

## Tables
- `roster_leagues(league_id PK, tenant_id, sport_id, window_open date, window_close date, max_squad_size, required_positions JSONB)`
- `squads(squad_id PK, league_id, club_id, tenant_id, name)`
- `players(player_id PK, name, position)`
- `registrations(id PK, player_id, league_id, squad_id NULL, parent_squad_id NULL, registration_type, start_date, loan_end_date NULL, role, active bool)` — the player's registration history; "current" is computed for a date.
- `roster_audit(audit_id PK "au-0001"…, seq, player_id, league_id, action, from_squad_id, to_squad_id, effective_date, state, who, when, why)` — **append only**.
- `matches_in_progress(league_id, match_id, home_squad_id, away_squad_id)`
- `idempotency` (scope `transfer`, key request_id).

## `POST /audit/v1/roster/setup`
Replace everything for that `league_id` (delete its squads/registrations/audit/in-progress rows, then insert). `max_squad_size` / `required_positions` default from the sport's roster config. Players get an `initial` registration (start = window open or today). 201 `{league_id, status:"configured", squad_counts:{squad_id: n}}`.
Validation: 400 for bad shapes/dates/roles (role ∈ captain, vice_captain, starter, substitute).

## `POST /audit/v1/roster/transfer` — `domain/roster_rules.py` + `services/roster.py`
Idempotency first after schema check: same request_id + identical body → stored response 200; (different body → treat as 409 `VALIDATION_ERROR`? spec doesn't say — **return the stored response only if identical; else 400 VALIDATION_ERROR** and log the decision).
Checks **in this exact order**, first failure wins:
1. 400 `VALIDATION_ERROR`: schema, valid dates, type ∈ transfer/loan/release, `to_squad_id` present unless release, loan needs `loan_end_date > effective_date`.
2. 404 `LEAGUE_NOT_FOUND` → `PLAYER_NOT_FOUND` → `SQUAD_NOT_FOUND` (from, then to).
3. 409 `CROSS_TENANT_TRANSFER` (from/to squad tenant ≠ league tenant).
4. 409 `NOT_IN_SQUAD` (player's current squad **as of effective_date** ≠ from_squad_id).
5. 409 `TRANSFER_WINDOW_CLOSED` (transfer/loan only; inclusive window; release any date).
6. 409 `PLAYER_ON_LOAN` (player currently on loan → any action refused).
7. 409 `SQUAD_FULL` (transfer/loan: destination count + 1 > max).
8. 409 `MIN_POSITION_VIOLATION` (from squad, after removing the player, has fewer of that position than required).
Keep `roster_rules.check(...)` a pure function taking plain data → easy to unit-test every code.

Effects:
- transfer: deactivate old registration, new one in to_squad, role `substitute`. (Old captain slot just becomes vacant.)
- loan: new registration `loan`, `parent_squad_id` = lender, `loan_end_date`; counts for borrower, not lender.
- release: no squad; `registration: null` in response.
- In-progress match (player's **current** squad is home/away in `matches_in_progress`): still accepted, `state:"deferred_until_match_end"`, `blocking_match_id`. Else `state:"active"`, `blocking_match_id:null`.
- Append one audit entry (who = requested_by, when = server now, why = reason). Rejected → nothing written.
- 201 response exactly as spec.

## `GET /audit/v1/roster/history/{player_id}?as_of=YYYY-MM-DD`
- 404 `PLAYER_NOT_FOUND`. `as_of` default = today (server date).
- **Lazy loan return:** if the player has a loan with `loan_end_date < as_of` and no `loan_return` entry for it yet → append one now (`action:"loan_return"`, who `"system"`, effective_date = loan_end_date + 1 day, from = borrower, to = lender, state active) and give the player a new registration back at the lender, role substitute, `registration_type: "transfer"` (keeps the contract's enum `initial|transfer|loan` for `GET /api/v1/clubs/{id}`). Written **once** (check before inserting; lock the player).
- `current_squad_id` / `parent_squad_id` for that date; null if released. `history` oldest-first.
- Note: `base_version` for offline sync = number of audit entries of the player.

## Tests (area `roster`)
Every error code in order, window inclusive edges, loan + as_of return written once, deferred_until_match_end (edge case 6), idempotent replay.
